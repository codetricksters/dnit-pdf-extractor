"""ΔP — variação do preço do produtor (art. 16).

Until now ΔP was the one number the user typed by hand into the dashboard. The
rules below were reverse-engineered from the reference workbook and verified
numerically against it (see tests/test_delta_p.py).

Two properties are easy to get wrong and are the reason this module exists
separately from the database code:

**Fixed base.** Every variation is measured against a single reference month
derived from the contract's *Data Base* — never against the previous month of
the series. The denominator is identical on every line (the absolute ``$C$6``
of the spreadsheet).

**One-month offset.** The IGP-DI always sits one month ahead of the ANP price,
in the base as well as in each measurement:

=================  ====================  ==================
\\                  ANP month             IGP-DI month
=================  ====================  ==================
Base (fixed)       Data Base − 1 month   Data Base
Measurement ``m``  ``m`` − 1 month       ``m``
=================  ====================  ==================

So, for a measurement in month ``m``::

    ΔP_cap(m)  = P(m−1) / P(base_anp) − 1
    ΔP_emul(m) = 0,75 · ΔP_cap(m) + 0,25 · (IGP(m) / IGP(Data Base) − 1)

The ANP publishes no price for emulsions — none of the products in its series
is one — which is precisely why the emulsion formula blends 75% of the CAP
variation with 25% of the IGP-DI.

All arithmetic is in ``Decimal``: the user audits these numbers cell by cell
against a spreadsheet, so binary float drift would show up as a discrepancy.
"""

from calendar import monthrange
from datetime import date
from decimal import Decimal
from typing import Protocol

FAMILIA_CAP = "CAP"
FAMILIA_EMULSOES = "EMULSOES"
FAMILIAS = (FAMILIA_CAP, FAMILIA_EMULSOES)

# Both families anchor on the same ANP product.
ANP_PRODUTO_CAP = "Cimento Asfáltico de Petróleo 50 70 (R$/kg)"
INDICE_IGP_DI = "IGP - DI"

# Base do número-índice publicado pela FGV; gravada em indice_mensal.base_label.
BASE_IGP_DI = "ago/1994 = 100"

PESO_ANP = Decimal("0.75")
PESO_IGP = Decimal("0.25")


class IndiceIndisponivel(Exception):
    """A price or index needed for the calculation is missing from the database.

    Raised instead of returning zero or skipping the line: a silently absent
    index would understate the reequilíbrio without anyone noticing.
    """


class FonteIndices(Protocol):
    """What ΔP needs from the outside world.

    A protocol rather than a direct database dependency, so the calculation can
    be tested against the reference values without a database.
    """

    def preco_anp(self, produto: str, regiao: str, mes: date) -> Decimal | None: ...

    def indice_mensal(self, indice: str, mes: date) -> Decimal | None: ...


def inicio_do_mes(d: date) -> date:
    return d.replace(day=1)


def soma_meses(d: date, n: int) -> date:
    """Shift *d* by *n* months, clamping the day to the target month's length."""
    total = (d.year * 12 + d.month - 1) + n
    ano, mes = divmod(total, 12)
    mes += 1
    dia = min(d.day, monthrange(ano, mes)[1])
    return date(ano, mes, dia)


def _preco(fonte: FonteIndices, regiao: str, mes: date, rotulo: str) -> Decimal:
    valor = fonte.preco_anp(ANP_PRODUTO_CAP, regiao, inicio_do_mes(mes))
    if valor is None:
        raise IndiceIndisponivel(
            f"Sem preço ANP de {ANP_PRODUTO_CAP} para a região {regiao} "
            f"em {mes:%m/%Y} ({rotulo})."
        )
    if valor == 0:
        raise IndiceIndisponivel(
            f"Preço ANP igual a zero para a região {regiao} em {mes:%m/%Y} "
            f"({rotulo}); não é possível calcular a variação."
        )
    return valor


def _indice(fonte: FonteIndices, mes: date, rotulo: str) -> Decimal:
    valor = fonte.indice_mensal(INDICE_IGP_DI, inicio_do_mes(mes))
    if valor is None:
        raise IndiceIndisponivel(
            f"Sem valor de {INDICE_IGP_DI} para {mes:%m/%Y} ({rotulo})."
        )
    if valor == 0:
        raise IndiceIndisponivel(
            f"{INDICE_IGP_DI} igual a zero em {mes:%m/%Y} ({rotulo})."
        )
    return valor


def delta_p_cap(
    *, mes_medicao: date, data_base: date, regiao: str, fonte: FonteIndices
) -> Decimal:
    base = _preco(fonte, regiao, soma_meses(data_base, -1), "data base")
    atual = _preco(fonte, regiao, soma_meses(mes_medicao, -1), "mês da medição")
    return atual / base - 1


def delta_p_emulsoes(
    *, mes_medicao: date, data_base: date, regiao: str, fonte: FonteIndices
) -> Decimal:
    componente_anp = delta_p_cap(
        mes_medicao=mes_medicao, data_base=data_base, regiao=regiao, fonte=fonte
    )
    igp_base = _indice(fonte, data_base, "data base")
    igp_atual = _indice(fonte, mes_medicao, "mês da medição")
    componente_igp = igp_atual / igp_base - 1
    return PESO_ANP * componente_anp + PESO_IGP * componente_igp


def delta_p(
    familia: str,
    *,
    mes_medicao: date,
    data_base: date,
    regiao: str,
    fonte: FonteIndices,
) -> Decimal:
    """ΔP for *familia*, using the ANP region chosen for that family.

    The region is per family and independent: the CAP component inside the
    emulsion ΔP uses the *emulsion* family's region, so the two families can
    yield different CAP variations for the same month.
    """
    if familia == FAMILIA_CAP:
        calc = delta_p_cap
    elif familia == FAMILIA_EMULSOES:
        calc = delta_p_emulsoes
    else:
        raise ValueError(f"Família desconhecida: {familia!r}")
    return calc(
        mes_medicao=mes_medicao, data_base=data_base, regiao=regiao, fonte=fonte
    )
