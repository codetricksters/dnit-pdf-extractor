import json
import math
from pathlib import Path

import pandas as pd

from ..config import STORAGE_PATH


JOBS_DIR = STORAGE_PATH / "jobs"

DEFAULT_LUCRO = 0.0511


def _truncate(value: float, decimals: int) -> float:
    factor = 10 ** decimals
    return math.trunc(value * factor) / factor


def load_reequilibrio_data() -> dict[str, pd.DataFrame]:
    """Load all JSON results, filter AQUISIÇÃO items, group by Descrição.

    Returns a dict mapping item description to a DataFrame with columns:
    Período, Descrição, Valor a PI, Fator de Reajuste, Reajustamento da Medição (R),
    ∆P, Reajustamento Total Base Produtor, REF Bruto com Lucro, REF sem Lucro.
    """
    records = _load_all_json_records()

    aquisicao_records = [
        r for r in records
        if "AQUI" in (r.get("Descrição") or "").upper()
    ]

    if not aquisicao_records:
        return {}

    df = pd.DataFrame(aquisicao_records)

    grouped = {}
    for desc, group_df in df.groupby("Descrição"):
        table_df = _build_item_table(group_df)
        if not table_df.empty:
            grouped[desc] = table_df

    return grouped


def _load_all_json_records() -> list[dict]:
    records = []
    if not JOBS_DIR.exists():
        return records

    for json_file in JOBS_DIR.glob("*/results/*.json"):
        try:
            with open(json_file) as f:
                data = json.load(f)
            if isinstance(data, list):
                records.extend(data)
        except (json.JSONDecodeError, OSError):
            continue

    return records


def _build_item_table(group_df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, record in group_df.iterrows():
        valor_pi = _to_float(record.get("Valor a PI Líquido", 0))
        fator = _to_float(record.get("Fator", 0))
        reajustamento_medicao = _truncate(fator * valor_pi, 2)

        rows.append({
            "Período": record.get("Período Líquido", ""),
            "Descrição": record.get("Descrição", ""),
            "Valor a PI": valor_pi,
            "Fator de Reajuste": fator,
            "Reajustamento da Medição (R)": reajustamento_medicao,
            "∆P": 0.0,
            "Reajustamento Total Base Produtor": 0.0,
            "REF Bruto com Lucro": 0.0 - reajustamento_medicao,
            "REF sem Lucro": (0.0 - reajustamento_medicao) * (1 - DEFAULT_LUCRO),
        })

    return pd.DataFrame(rows)


def compute_ref_columns(df: pd.DataFrame, delta_p: float, lucro: float = DEFAULT_LUCRO) -> pd.DataFrame:
    """Recompute REF columns given a new ∆P value and lucro percentage."""
    df = df.copy()
    df["∆P"] = delta_p
    df["Reajustamento Total Base Produtor"] = df["Valor a PI"] * delta_p
    df["REF Bruto com Lucro"] = (
        df["Reajustamento Total Base Produtor"] - df["Reajustamento da Medição (R)"]
    )
    df["REF sem Lucro"] = df["REF Bruto com Lucro"] * (1 - lucro)
    return df


def _to_float(value) -> float:
    if value is None:
        return 0.0
    try:
        return float(value)
    except (ValueError, TypeError):
        return 0.0
