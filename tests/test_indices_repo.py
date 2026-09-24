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

from .indices_factory import mes_igp, semana

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


async def test_gravacao_registra_origem_e_so_regrava_o_que_mudou():
    indices_repo.gravar_precos_anp([semana(date(2023, 1, 9), "3.28568")], origem="upload:a.xls")
    (antes,) = indices_repo.listar_precos_anp(regiao="Nordeste")
    assert antes["origem"] == "upload:a.xls"

    indices_repo.gravar_precos_anp([semana(date(2023, 1, 9), "3.285680")], origem="upload:b.xls")
    (igual,) = indices_repo.listar_precos_anp(regiao="Nordeste")
    assert igual["origem"] == "upload:a.xls"
    assert igual["atualizado_em"] == antes["atualizado_em"]

    indices_repo.gravar_precos_anp([semana(date(2023, 1, 9), "3.3")], origem="upload:b.xls")
    (mudou,) = indices_repo.listar_precos_anp(regiao="Nordeste")
    assert mudou["origem"] == "upload:b.xls"
    assert mudou["preco"] == Decimal("3.3")


async def test_origem_padrao_e_manual():
    indices_repo.gravar_precos_anp([semana(date(2023, 1, 9), "3.28568")])
    indices_repo.gravar_indices_mensais([mes_igp(date(2023, 1, 1), "1143.861")])
    assert indices_repo.listar_precos_anp()[0]["origem"] == indices_repo.ORIGEM_MANUAL
    assert indices_repo.listar_indices_mensais()[0]["origem"] == indices_repo.ORIGEM_MANUAL


async def test_indice_mensal_so_regrava_o_que_mudou():
    indices_repo.gravar_indices_mensais([mes_igp(date(2023, 1, 1), "1143.861")], origem="seed")
    indices_repo.gravar_indices_mensais([mes_igp(date(2023, 1, 1), "1143.8610")], origem="upload:x")
    assert indices_repo.buscar_indice(date(2023, 1, 1))["origem"] == "seed"


async def test_banco_proibe_semanas_sobrepostas():
    indices_repo.gravar_precos_anp([semana(date(2023, 1, 9), "3.28")])
    with pytest.raises(indices_repo.SemanaSobreposta):
        indices_repo.gravar_precos_anp([semana(date(2023, 1, 15), "3.30")])
    # Outra região não conflita.
    indices_repo.gravar_precos_anp([semana(date(2023, 1, 15), "3.30", regiao="Sul")])


async def test_sobrescrever_manuais_falso_nao_regrava_linha_que_virou_manual():
    """Fecha a corrida entre o plano e a gravação: mesmo que o chamador não
    saiba que a linha passou a manual (por exemplo, planejou contra uma
    leitura anterior do banco), a gravação em si tem de preservá-la quando
    ``sobrescrever_manuais=False``."""
    indices_repo.gravar_precos_anp([semana(date(2023, 1, 9), "3.28")], origem="upload:a.xls")
    indices_repo.gravar_semana_manual(
        {"vigencia_inicio": date(2023, 1, 9), "vigencia_fim": date(2023, 1, 15),
         "regiao": "Nordeste", "preco": "9.99"}
    )
    indices_repo.gravar_precos_anp(
        [semana(date(2023, 1, 9), "3.30")], origem="upload:b.xls", sobrescrever_manuais=False
    )
    salvo = indices_repo.buscar_semana(ANP_PRODUTO_CAP, "Nordeste", date(2023, 1, 9))
    assert salvo["preco"] == Decimal("9.99") and salvo["origem"] == indices_repo.ORIGEM_MANUAL

    indices_repo.gravar_precos_anp(
        [semana(date(2023, 1, 9), "3.30")], origem="upload:b.xls", sobrescrever_manuais=True
    )
    salvo = indices_repo.buscar_semana(ANP_PRODUTO_CAP, "Nordeste", date(2023, 1, 9))
    assert salvo["preco"] == Decimal("3.30") and salvo["origem"] == "upload:b.xls"


async def test_sobrescrever_manuais_falso_no_indice_mensal_tambem_preserva():
    indices_repo.gravar_indices_mensais([mes_igp(date(2023, 1, 1), "1000")], origem="upload:a")
    indices_repo.gravar_indice_manual(date(2023, 1, 1), "9999")
    indices_repo.gravar_indices_mensais(
        [mes_igp(date(2023, 1, 1), "1234")], origem="upload:b", sobrescrever_manuais=False
    )
    assert indices_repo.buscar_indice(date(2023, 1, 1))["valor"] == Decimal("9999")


async def test_vigencia_invertida_e_recusada_pelo_banco():
    with pytest.raises(indices_repo.IndiceInvalido):
        indices_repo.gravar_precos_anp([semana(date(2023, 1, 9), "3.28", dias=-1)])


async def test_semana_manual_normaliza_regiao_e_marca_manual():
    salvo = indices_repo.gravar_semana_manual(
        {
            "vigencia_inicio": date(2023, 1, 9),
            "vigencia_fim": date(2023, 1, 15),
            "regiao": "NORDESTE",
            "preco": Decimal("3.28568"),
        }
    )
    assert salvo["regiao"] == "Nordeste"
    assert salvo["produto"] == ANP_PRODUTO_CAP
    assert salvo["origem"] == indices_repo.ORIGEM_MANUAL
    assert salvo["preco"] == Decimal("3.28568")


async def test_semana_manual_corrige_a_mesma_semana():
    indices_repo.gravar_precos_anp([semana(date(2023, 1, 9), "3.28")], origem="seed")
    salvo = indices_repo.gravar_semana_manual(
        {"vigencia_inicio": date(2023, 1, 9), "vigencia_fim": date(2023, 1, 15),
         "regiao": "Nordeste", "preco": "3.5"}
    )
    assert salvo["preco"] == Decimal("3.5")
    assert salvo["origem"] == indices_repo.ORIGEM_MANUAL


async def test_semana_manual_sobreposta_indica_a_semana_em_conflito():
    indices_repo.gravar_precos_anp([semana(date(2023, 1, 9), "3.28")])
    with pytest.raises(indices_repo.SemanaSobreposta) as erro:
        indices_repo.gravar_semana_manual(
            {"vigencia_inicio": date(2023, 1, 12), "vigencia_fim": date(2023, 1, 18),
             "regiao": "Nordeste", "preco": "3.3"}
        )
    assert "09/01/2023" in str(erro.value)
    assert "15/01/2023" in str(erro.value)


@pytest.mark.parametrize(
    "alteracao",
    [
        {"vigencia_fim": date(2023, 1, 8)},
        {"preco": "-1"},
        {"regiao": "Marte"},
    ],
)
async def test_semana_manual_invalida(alteracao):
    registro = {"vigencia_inicio": date(2023, 1, 9), "vigencia_fim": date(2023, 1, 15),
                "regiao": "Nordeste", "preco": "3.28"}
    with pytest.raises(indices_repo.IndiceInvalido):
        indices_repo.gravar_semana_manual({**registro, **alteracao})


async def test_semana_sem_cotacao_pode_ser_gravada():
    salvo = indices_repo.gravar_semana_manual(
        {"vigencia_inicio": date(2023, 1, 9), "vigencia_fim": date(2023, 1, 15),
         "regiao": "Centro-Oeste", "preco": None}
    )
    assert salvo["preco"] is None


async def test_indice_manual():
    salvo = indices_repo.gravar_indice_manual(date(2023, 1, 1), Decimal("1143.861"))
    assert salvo["origem"] == indices_repo.ORIGEM_MANUAL
    assert salvo["base_label"] == "ago/1994 = 100"
    assert salvo["mes_ref"] == date(2023, 1, 1)
    with pytest.raises(indices_repo.IndiceInvalido):
        indices_repo.gravar_indice_manual(date(2023, 2, 1), 0)


async def test_excluir_semana_e_mes():
    indices_repo.gravar_precos_anp([semana(date(2023, 1, 9), "3.28")])
    (linha,) = indices_repo.listar_precos_anp()
    assert indices_repo.excluir_preco_anp(linha["id"]) is True
    assert indices_repo.excluir_preco_anp(linha["id"]) is False

    indices_repo.gravar_indice_manual(date(2023, 1, 1), 1)
    assert indices_repo.excluir_indice_mensal(date(2023, 1, 1)) is True
    assert indices_repo.excluir_indice_mensal(date(2023, 1, 1)) is False


async def test_listar_precos_filtra_periodo_e_regiao_sem_diferenciar_maiusculas():
    _semear_anp()
    linhas = indices_repo.listar_precos_anp(
        regiao="nordeste", de=date(2022, 12, 1), ate=date(2023, 1, 31)
    )
    assert [l["vigencia_inicio"] for l in linhas] == [date(2023, 1, 9), date(2022, 12, 12)]
    assert len(indices_repo.listar_precos_anp(limite=None)) == len(SEMANAS)


async def test_listar_indices_filtra_periodo():
    _semear_igp()
    meses = indices_repo.listar_indices_mensais(de=date(2023, 1, 1), ate=date(2023, 12, 1))
    assert [m["mes_ref"] for m in meses] == [date(2023, 2, 1), date(2023, 1, 1)]


async def test_regioes_disponiveis_e_normalizacao():
    _semear_anp("Nordeste")
    assert indices_repo.regioes_disponiveis() == ["Nordeste"]
    assert indices_repo.normalizar_regiao("  NORDESTE ") == "Nordeste"
    assert indices_repo.normalizar_regiao("Sul") is None
    assert indices_repo.normalizar_regiao("") is None


async def test_mapas_por_chave():
    _semear_anp()
    _semear_igp()
    precos = indices_repo.precos_anp_por_chave({ANP_PRODUTO_CAP})
    chave = (ANP_PRODUTO_CAP, date(2021, 12, 13), "Nordeste")
    assert precos[chave]["preco"] == Decimal("4.02073")
    assert precos[chave]["origem"] == indices_repo.ORIGEM_MANUAL
    assert indices_repo.indices_por_mes()[date(2022, 1, 1)]["valor"] == Decimal("1110.398")
