"""Index storage and the weekly→monthly lookup, against a real database."""

from datetime import date
from decimal import Decimal

import pytest

from app.services.delta_p import (
    ANP_PRODUTO_CAP,
    FAMILIA_CAP,
    FAMILIA_EMULSOES,
    INDICE_IGP_DI,
    delta_p,
)
from app.services import indices_repo

# Real weeks from the reference workbook (Nordeste), each containing the 15th of
# its month, plus the neighbouring weeks that must NOT be selected.
SEMANAS = [
    (date(2021, 12, 6), date(2021, 12, 12), Decimal("9.99999")),
    (date(2021, 12, 13), date(2021, 12, 19), Decimal("4.02073")),
    (date(2021, 12, 20), date(2021, 12, 26), Decimal("8.88888")),
    (date(2022, 12, 12), date(2022, 12, 18), Decimal("3.71611")),
    (date(2023, 1, 9), date(2023, 1, 15), Decimal("3.28568")),
    (date(2023, 2, 13), date(2023, 2, 19), Decimal("3.29281")),
]


def _semear_anp(regiao="Nordeste"):
    indices_repo.gravar_precos_anp(
        [
            {
                "produto": ANP_PRODUTO_CAP,
                "vigencia_inicio": ini,
                "vigencia_fim": fim,
                "regiao": regiao,
                "preco": preco,
            }
            for ini, fim, preco in SEMANAS
        ]
    )


def _semear_igp():
    indices_repo.gravar_indices_mensais(
        [
            {"indice": INDICE_IGP_DI, "mes_ref": mes, "valor": valor,
             "base_label": "ago/1994 = 100"}
            for mes, valor in [
                (date(2022, 1, 1), Decimal("1110.398")),
                (date(2023, 1, 1), Decimal("1143.861")),
                (date(2023, 2, 1), Decimal("1144.271")),
            ]
        ]
    )


@pytest.mark.parametrize(
    "mes,esperado",
    [
        (date(2021, 12, 1), "4.02073"),
        (date(2022, 12, 1), "3.71611"),
        (date(2023, 1, 1), "3.28568"),
    ],
)
async def test_preco_do_mes_e_a_semana_que_contem_o_dia_15(mes, esperado):
    _semear_anp()
    assert indices_repo.buscar_preco_anp(ANP_PRODUTO_CAP, "Nordeste", mes) == Decimal(
        esperado
    )


async def test_mes_sem_cotacao_retorna_none():
    _semear_anp()
    assert indices_repo.buscar_preco_anp(ANP_PRODUTO_CAP, "Nordeste", date(2024, 5, 1)) is None


async def test_regiao_sem_cotacao_retorna_none():
    """Each family picks its own region; asking for an unfed one must not fall
    back to another region's price."""
    _semear_anp(regiao="Nordeste")
    assert indices_repo.buscar_preco_anp(ANP_PRODUTO_CAP, "Sul", date(2021, 12, 1)) is None


async def test_preco_ausente_na_fonte_fica_nulo():
    """'***' in the ANP source means no quotation that week, stored as NULL."""
    indices_repo.gravar_precos_anp(
        [
            {
                "produto": ANP_PRODUTO_CAP,
                "vigencia_inicio": date(2024, 3, 11),
                "vigencia_fim": date(2024, 3, 17),
                "regiao": "Centro-Oeste",
                "preco": None,
            }
        ]
    )
    assert (
        indices_repo.buscar_preco_anp(ANP_PRODUTO_CAP, "Centro-Oeste", date(2024, 3, 1))
        is None
    )


async def test_regravar_a_mesma_semana_corrige_em_vez_de_duplicar():
    _semear_anp()
    indices_repo.gravar_precos_anp(
        [
            {
                "produto": ANP_PRODUTO_CAP,
                "vigencia_inicio": date(2021, 12, 13),
                "vigencia_fim": date(2021, 12, 19),
                "regiao": "Nordeste",
                "preco": Decimal("4.11111"),
            }
        ]
    )
    assert indices_repo.buscar_preco_anp(
        ANP_PRODUTO_CAP, "Nordeste", date(2021, 12, 1)
    ) == Decimal("4.11111")
    precos = indices_repo.listar_precos_anp(regiao="Nordeste")
    assert len(precos) == len(SEMANAS)


async def test_indice_mensal_ida_e_volta():
    _semear_igp()
    assert indices_repo.buscar_indice_mensal(INDICE_IGP_DI, date(2023, 1, 1)) == Decimal(
        "1143.861"
    )
    # Any day of the month resolves to the month's row.
    assert indices_repo.buscar_indice_mensal(
        INDICE_IGP_DI, date(2023, 1, 27)
    ) == Decimal("1143.861")
    assert indices_repo.buscar_indice_mensal(INDICE_IGP_DI, date(2024, 1, 1)) is None


async def test_delta_p_ponta_a_ponta_pelo_banco():
    """The same reference values as test_delta_p.py, now sourced from the
    database — this is what proves the weekly→monthly rule feeds ΔP correctly."""
    _semear_anp()
    _semear_igp()
    fonte = indices_repo.FonteBanco()
    kwargs = dict(data_base=date(2022, 1, 1), regiao="Nordeste", fonte=fonte)

    cap = delta_p(FAMILIA_CAP, mes_medicao=date(2023, 2, 1), **kwargs)
    emul = delta_p(FAMILIA_EMULSOES, mes_medicao=date(2023, 2, 1), **kwargs)
    assert str(cap.quantize(Decimal("0.0001"))) == "-0.1828"
    assert str(emul.quantize(Decimal("0.0001"))) == "-0.1295"


async def test_cobertura_relata_o_que_existe():
    _semear_anp()
    _semear_igp()
    c = indices_repo.cobertura()
    assert c["anp"]["de"] == date(2021, 12, 6)
    assert c["anp"]["ate"] == date(2023, 2, 19)
    assert c["anp"]["registros"] == len(SEMANAS)
    assert c["regioes"] == ["Nordeste"]
    assert c["igp_di"]["registros"] == 3
