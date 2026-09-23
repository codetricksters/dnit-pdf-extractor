"""Data behind the Reequilíbrio screen.

Reads from the database rather than from the extraction JSON, and — the reason
this module is thin — reuses the export's own grouping and ΔP calculation
(``reequilibrio_export``). The screen and the spreadsheet the user downloads must
not be able to disagree: if they did, whichever the user checked first would be
the one they trusted.

``compute_ref_columns`` stays because it is still what recalculates the table when
the user tries a different lucro on screen. F is truncated, not rounded
(``math.trunc``), which is what the PDF and the spreadsheet's ``TRUNC`` do.
"""

import math

import pandas as pd

from ..services import contratos_repo, medicoes_repo
from ..services.reequilibrio_export import calcular_deltas, montar_grupos

DEFAULT_LUCRO = 0.0511

COLUNAS = [
    "Período",
    "Descrição",
    "Valor a PI",
    "Fator de Reajuste",
    "Reajustamento da Medição (R)",
    "∆P",
    "Reajustamento Total Base Produtor",
    "REF Bruto com Lucro",
    "REF sem Lucro",
]


def _truncate(value: float, decimals: int) -> float:
    factor = 10 ** decimals
    return math.trunc(value * factor) / factor


def listar_contratos() -> list[dict]:
    return contratos_repo.listar()


def load_reequilibrio_data(numero_contrato: str) -> tuple[dict[str, pd.DataFrame], list[str]]:
    """Tables per product for a contract, plus what is missing to compute ΔP.

    The pendências are returned instead of raised: the screen shows the tables it
    can and tells the user what to fill in, where the export refuses outright —
    a spreadsheet missing ΔP would look finished and be wrong.
    """
    contrato = contratos_repo.buscar(numero_contrato)
    if contrato is None:
        return {}, [f"Contrato '{numero_contrato}' não cadastrado."]
    if contrato.get("data_base") is None:
        return {}, ["O contrato está sem Data Base, e sem ela não há ΔP."]

    itens = medicoes_repo.itens_para_export(contrato["id"])
    if not itens:
        return {}, ["Nenhum item confirmado para este contrato."]

    deltas, faltando = calcular_deltas(contrato, itens)
    # Only the items whose ΔP could be computed can become rows.
    utilizaveis = [i for i in itens if (i["familia"], i["mes_medicao"]) in deltas]
    grupos, _descartadas = montar_grupos(utilizaveis, deltas)

    return {grupo.descricao: _tabela(grupo) for grupo in grupos}, faltando


def _tabela(grupo) -> pd.DataFrame:
    linhas = []
    for item in grupo.linhas:
        valor_pi = float(item.valor_pi)
        fator = float(item.fator)
        delta_p = float(item.delta_p)
        reajustamento = _truncate(fator * valor_pi, 2)
        total_produtor = valor_pi * delta_p
        bruto = total_produtor - reajustamento
        linhas.append(
            {
                "Período": item.mes.strftime("%m/%Y"),
                "Descrição": grupo.descricao,
                "Valor a PI": valor_pi,
                "Fator de Reajuste": fator,
                "Reajustamento da Medição (R)": reajustamento,
                "∆P": delta_p,
                "Reajustamento Total Base Produtor": total_produtor,
                "REF Bruto com Lucro": bruto,
                "REF sem Lucro": bruto * (1 - DEFAULT_LUCRO),
            }
        )
    return pd.DataFrame(linhas, columns=COLUNAS)


def compute_ref_columns(df: pd.DataFrame, lucro: float = DEFAULT_LUCRO) -> pd.DataFrame:
    """Recompute the REF columns for a different lucro percentage.

    ΔP is no longer an argument: it comes from the índices in the database and is
    not something the user types any more.
    """
    df = df.copy()
    if df.empty:
        return df
    df["Reajustamento Total Base Produtor"] = df["Valor a PI"] * df["∆P"]
    df["REF Bruto com Lucro"] = (
        df["Reajustamento Total Base Produtor"] - df["Reajustamento da Medição (R)"]
    )
    df["REF sem Lucro"] = df["REF Bruto com Lucro"] * (1 - lucro)
    return df
