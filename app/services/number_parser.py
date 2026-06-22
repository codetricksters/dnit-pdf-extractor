import re

NUMERIC_COLUMNS = {
    "Preço Unitário",
    "Quantidade Acumulada",
    "Valor a PI Acumulado",
    "Valor a PI Líquido",
    "Fator",
    "Reajustamento Líquido",
    "Ajuste Contratual Líquido",
}


def parse_br_number(value: str) -> float | None:
    """Parse a Brazilian-formatted number, tolerating OCR artifacts.

    Brazilian format: dots as thousands separators, comma for decimals
    (e.g. "1.872.240,49"). OCR may produce malformed variants like
    "99,.999,00" or "99.,999,00" or "99.999,.0000".

    Strategy: the rightmost separator with 2-4 trailing digits is the
    decimal mark. All other dots/commas are thousands noise.

    Returns None if the string contains no digits.
    """
    if not value or not value.strip():
        return None

    s = value.strip()
    negative = s.startswith("-")
    s = s.lstrip("-").strip()

    s = re.sub(r"[^\d.,]", "", s)

    if not s or not any(c.isdigit() for c in s):
        return None

    last_dot = s.rfind(".")
    last_comma = s.rfind(",")
    last_sep = max(last_dot, last_comma)

    if last_sep == -1:
        result = float(s)
    else:
        decimal_part = s[last_sep + 1:]
        integer_part = s[:last_sep]
        integer_part = integer_part.replace(".", "").replace(",", "")
        result = float(f"{integer_part}.{decimal_part}")

    return -result if negative else result


def convert_numeric_columns(record: dict) -> dict:
    """Convert known numeric columns from string to float in-place."""
    for col in NUMERIC_COLUMNS:
        raw = record.get(col, "")
        if isinstance(raw, str) and raw.strip():
            parsed = parse_br_number(raw)
            record[col] = parsed if parsed is not None else 0.0
        elif isinstance(raw, str):
            record[col] = 0.0
    return record
