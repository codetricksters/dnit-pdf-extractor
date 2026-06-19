import io
import re

import pdfplumber

from .exceptions import ExtractionError

MAIN_HEADER_KEYWORDS = {"serviço", "descrição", "código"}
INDICES_KEYWORDS = {"adloc", "conser", "emuimp", "índices", "indices"}

# Pre-compiled whole-word patterns — prevents "conser" matching "CONSERVAÇÃO", etc.
_INDICES_PATTERNS = [
    re.compile(r"\b" + kw + r"\b", re.IGNORECASE) for kw in INDICES_KEYWORDS
]

EXPECTED_COLUMNS = [
    "Serviço",
    "Descrição",
    "Código SICRO",
    "Unidade",
    "Preço Unitário",
    "Quantidade Acumulada",
    "Valor a PI Acumulado",
    "Valor a PI Líquido",
    "Fator",
    "Reajustamento Líquido",
    "Ajuste Contratual Líquido",
]

_SERVICE_CODE_RE = re.compile(r"^\d{4,}")
_PERIODO_LIQUIDO_RE = re.compile(
    r"Per[ií]odo\s+L[ií]quido:\s*(\d{2}/\d{2}/\d{4})\s*-\s*(\d{2}/\d{2}/\d{4})",
    re.IGNORECASE,
)

# Matches section header rows: "1,0 - GRUPO 1 -", "17,1 - GRUPO 6 -", etc.
_SECTION_HEADER_RE = re.compile(r"^\d+[,.]\d+\s*-")


def parse_br_number(value: str) -> float:
    return float(value.replace(".", "").replace(",", "."))


def _is_indices_row(row: list) -> bool:
    """True only when a cell is an exact Índices label (whole-word match).

    Substring search would trigger on "CONSERVAÇÃO" matching "conser", etc.
    """
    cells = [str(c) for c in row if c]
    return any(pat.search(cell) for cell in cells for pat in _INDICES_PATTERNS)


def _is_header_row(row: list) -> bool:
    """True when the first cell contains a main-table column header keyword.

    Only checking row[0] prevents description cells (e.g. 'CAMINHO DE SERVIÇO EM...')
    from being misidentified as header rows.
    """
    first = str(row[0]).lower() if row and row[0] else ""
    return any(kw in first for kw in MAIN_HEADER_KEYWORDS)


def _is_section_header(raw_row: list) -> bool:
    """True for rows like ['1,0 - GRUPO 1 - ...', None, None, ...] — exactly one
    non-empty cell at index 0 that matches the section numbering pattern."""
    if not raw_row:
        return False
    first = raw_row[0]
    if not first or not str(first).strip():
        return False
    non_empty = [c for c in raw_row if c is not None and str(c).strip()]
    return len(non_empty) == 1 and bool(_SECTION_HEADER_RE.match(str(first).strip()))


def _is_new_record(service_cell: str | None) -> bool:
    if not service_cell:
        return False
    val = service_cell.strip()
    return bool(_SERVICE_CODE_RE.match(val)) or val.upper().startswith("SUBTOTAL")


def _row_is_dangling(row_dict: dict) -> bool:
    """True when all columns except Descrição are empty — continuation fragment."""
    for col in EXPECTED_COLUMNS:
        if col == "Descrição":
            continue
        if row_dict.get(col):
            return False
    return True


def _clean_cell(value) -> str:
    if value is None:
        return ""
    return str(value).strip().replace("\n", " ")


def _map_row(raw_row: list, header: list) -> dict:
    record: dict = {col: "" for col in EXPECTED_COLUMNS}
    for i, col in enumerate(header):
        if col in record and i < len(raw_row):
            record[col] = _clean_cell(raw_row[i])
    # Some PDF pages emit a trailing phantom column in the header (None at the end),
    # shifting the real "Ajuste Contratual Líquido" value one position to the right.
    # If the last expected column is still empty, scan forward from the last known
    # canonical header position to pick up the shifted value.
    last_col = EXPECTED_COLUMNS[-1]
    if not record[last_col]:
        last_known_idx = max((i for i, c in enumerate(header) if c), default=0)
        for i in range(last_known_idx, len(raw_row)):
            v = _clean_cell(raw_row[i])
            if v:
                record[last_col] = v
                break
    return record


def _normalize_header(raw_header: list) -> list:
    """Map raw PDF header cells to canonical column names.

    PDF cells often use newlines inside multi-word labels (e.g. 'Código\\nSICRO');
    normalise both sides to spaces before comparing.
    """
    mapping: dict[str, str] = {}
    for expected in EXPECTED_COLUMNS:
        expected_norm = expected.lower().replace("\n", " ")
        for cell in raw_header:
            if not cell:
                continue
            cell_norm = str(cell).lower().replace("\n", " ")
            if expected_norm in cell_norm:
                mapping[str(cell)] = expected
                break

    result = []
    for cell in raw_header:
        result.append(mapping.get(str(cell) if cell else "", str(cell) if cell else ""))
    return result


def extract_from_pdf(file_bytes: bytes, source_name: str) -> list[dict]:
    try:
        pdf = pdfplumber.open(io.BytesIO(file_bytes))
    except Exception as exc:
        raise ExtractionError(f"Could not open '{source_name}': {exc}")

    header: list | None = None
    records: list[dict] = []
    current_record: dict | None = None
    periodo_liquido: str = ""

    with pdf:
        for page in pdf.pages:
            if not periodo_liquido:
                page_text = page.extract_text() or ""
                m = _PERIODO_LIQUIDO_RE.search(page_text)
                if m:
                    periodo_liquido = f"{m.group(1)} - {m.group(2)}"
            tables = page.extract_tables()
            for table in tables:
                if not table:
                    continue

                # Skip standalone narrow tables (subtotal pairs like ['1.872.240,49', '0,00'])
                max_width = max(
                    sum(1 for c in row if c is not None and str(c).strip())
                    for row in table
                    if any(c is not None and str(c).strip() for c in row)
                ) if any(any(c is not None and str(c).strip() for c in row) for row in table) else 0
                if max_width <= 3:
                    continue

                for raw_row in table:
                    if not any(raw_row):
                        continue

                    if _is_indices_row(raw_row):
                        continue

                    if _is_header_row(raw_row):
                        if header is None:
                            header = _normalize_header(raw_row)
                        continue

                    if _is_section_header(raw_row):
                        continue

                    if header is None:
                        continue

                    row_dict = _map_row(raw_row, header)
                    service_val = row_dict.get("Serviço", "")
                    desc_val = row_dict.get("Descrição", "")

                    # Skip embedded subtotal rows (e.g. [None, None, ..., '1.330.960,19', '0,00', None, ...])
                    if not service_val and not desc_val:
                        continue

                    if _is_new_record(service_val):
                        if current_record is not None:
                            records.append(current_record)
                        current_record = row_dict
                    elif current_record is not None and _row_is_dangling(row_dict):
                        if desc_val:
                            sep = " " if current_record["Descrição"] else ""
                            current_record["Descrição"] += sep + desc_val
                    else:
                        if current_record is not None:
                            records.append(current_record)
                        current_record = row_dict

    if current_record is not None:
        records.append(current_record)

    if not records:
        raise ExtractionError(
            f"No recognisable main-table data found in '{source_name}'."
        )

    for row in records:
        row["Período Líquido"] = periodo_liquido
        row["Source_File"] = source_name

    return records
