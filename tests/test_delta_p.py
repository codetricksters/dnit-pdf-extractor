"""ΔP against the reference workbook.

Every expected value below was read from
``data/Reequilíbrio - 26 - Contrato 716-22.xlsx``, sheet
``CÁLCULO DA VARIAÇÃO DE PREÇOS`` (columns D and J), so a regression here means
the app and the spreadsheet the user audits against have diverged.

Contract 15 00716/2022: Data Base = 2022-01-01, both families in NORDESTE.
"""

from datetime import date
from decimal import Decimal

import pytest

from app.services.delta_p import (
    ANP_PRODUTO_CAP,
    FAMILIA_CAP,
    FAMILIA_EMULSOES,
    INDICE_IGP_DI,
    IndiceIndisponivel,
    delta_p,
    soma_meses,
)

DATA_BASE = date(2022, 1, 1)
REGIAO = "Nordeste"

# ANP weekly price (Nordeste) for the week containing the 15th of each month.
PRECOS_ANP = {
    date(2021, 12, 1): Decimal("4.02073"),  # base: Data Base − 1 month
    date(2022, 12, 1): Decimal("3.71611"),
    date(2023, 1, 1): Decimal("3.28568"),
    date(2023, 2, 1): Decimal("3.29281"),
    date(2023, 3, 1): Decimal("3.18603"),
}

IGP_DI = {
    date(2022, 1, 1): Decimal("1110.398"),  # base: the Data Base month itself
    date(2023, 1, 1): Decimal("1143.861"),
    date(2023, 2, 1): Decimal("1144.271"),
    date(2023, 3, 1): Decimal("1140.357"),
    date(2023, 4, 1): Decimal("1128.805"),
}


class FonteFalsa:
    """In-memory FonteIndices, so the calculation is tested without a database."""

    def __init__(self, precos=None, indices=None):
        self.precos = PRECOS_ANP if precos is None else precos
        self.indices = IGP_DI if indices is None else indices

    def preco_anp(self, produto, regiao, mes):
        assert produto == ANP_PRODUTO_CAP
        assert regiao == REGIAO
        return self.precos.get(mes)

    def indice_mensal(self, indice, mes):
        assert indice == INDICE_IGP_DI
        return self.indices.get(mes)


def _delta(familia, mes):
    return delta_p(
        familia,
        mes_medicao=mes,
        data_base=DATA_BASE,
        regiao=REGIAO,
        fonte=FonteFalsa(),
    )


def _arredondado(valor: Decimal) -> str:
    """Round to the 4 decimals the spreadsheet displays."""
    return str(valor.quantize(Decimal("0.0001")))


# (measurement month, ΔP CAP, ΔP emulsions) — rows 7..10 of the calc sheet.
CASOS = [
    (date(2023, 1, 1), "-0.0758", "-0.0493"),
    (date(2023, 2, 1), "-0.1828", "-0.1295"),
    (date(2023, 3, 1), "-0.1810", "-0.1290"),
    (date(2023, 4, 1), "-0.2076", "-0.1516"),
]


@pytest.mark.parametrize("mes,esperado_cap,esperado_emul", CASOS)
def test_delta_p_reproduz_a_planilha(mes, esperado_cap, esperado_emul):
    assert _arredondado(_delta(FAMILIA_CAP, mes)) == esperado_cap
    assert _arredondado(_delta(FAMILIA_EMULSOES, mes)) == esperado_emul


def test_base_e_fixa_nao_mes_anterior():
    """Guards the rule that was initially misread.

    Both months share the same denominator (the Data Base price), so the CAP ΔP
    of Feb-23 is NOT the ratio between Feb-23 and Jan-23.
    """
    fev = _delta(FAMILIA_CAP, date(2023, 2, 1))
    mes_a_mes = PRECOS_ANP[date(2023, 1, 1)] / PRECOS_ANP[date(2022, 12, 1)] - 1
    assert _arredondado(fev) == "-0.1828"
    assert _arredondado(mes_a_mes) != "-0.1828"


def test_deslocamento_de_um_mes_entre_anp_e_igp():
    """The ANP month lags the measurement; the IGP-DI month does not.

    Removing either month from the source makes the calculation fail, which
    pins the offset down in both directions.
    """
    mes = date(2023, 2, 1)

    sem_anp_anterior = {k: v for k, v in PRECOS_ANP.items() if k != date(2023, 1, 1)}
    with pytest.raises(IndiceIndisponivel):
        delta_p(
            FAMILIA_CAP,
            mes_medicao=mes,
            data_base=DATA_BASE,
            regiao=REGIAO,
            fonte=FonteFalsa(precos=sem_anp_anterior),
        )

    sem_igp_do_mes = {k: v for k, v in IGP_DI.items() if k != mes}
    with pytest.raises(IndiceIndisponivel):
        delta_p(
            FAMILIA_EMULSOES,
            mes_medicao=mes,
            data_base=DATA_BASE,
            regiao=REGIAO,
            fonte=FonteFalsa(indices=sem_igp_do_mes),
        )


def test_emulsoes_e_a_media_ponderada_declarada():
    mes = date(2023, 2, 1)
    cap = _delta(FAMILIA_CAP, mes)
    igp = IGP_DI[mes] / IGP_DI[DATA_BASE] - 1
    esperado = Decimal("0.75") * cap + Decimal("0.25") * igp
    assert _delta(FAMILIA_EMULSOES, mes) == esperado


def test_preco_ausente_nao_vira_zero():
    """A missing index must interrupt the calculation, not understate it."""
    with pytest.raises(IndiceIndisponivel, match="Sem preço ANP"):
        delta_p(
            FAMILIA_CAP,
            mes_medicao=date(2024, 7, 1),
            data_base=DATA_BASE,
            regiao=REGIAO,
            fonte=FonteFalsa(),
        )


def test_preco_zero_nao_divide_por_zero():
    """'***' in the source becomes NULL, but a stored zero must not crash."""
    precos = PRECOS_ANP | {date(2021, 12, 1): Decimal("0")}
    with pytest.raises(IndiceIndisponivel, match="igual a zero"):
        delta_p(
            FAMILIA_CAP,
            mes_medicao=date(2023, 2, 1),
            data_base=DATA_BASE,
            regiao=REGIAO,
            fonte=FonteFalsa(precos=precos),
        )


def test_familia_desconhecida_e_recusada():
    with pytest.raises(ValueError):
        delta_p(
            "BRITA",
            mes_medicao=date(2023, 2, 1),
            data_base=DATA_BASE,
            regiao=REGIAO,
            fonte=FonteFalsa(),
        )


@pytest.mark.parametrize(
    "origem,n,esperado",
    [
        (date(2022, 1, 1), -1, date(2021, 12, 1)),
        (date(2022, 1, 31), -1, date(2021, 12, 31)),
        (date(2022, 3, 31), -1, date(2022, 2, 28)),  # day clamped to month length
        (date(2022, 12, 1), 1, date(2023, 1, 1)),
        (date(2022, 6, 15), 0, date(2022, 6, 15)),
    ],
)
def test_soma_meses(origem, n, esperado):
    assert soma_meses(origem, n) == esperado
