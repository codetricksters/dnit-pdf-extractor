import io
import re

import pdfplumber

from .exceptions import ExtractionError
from .number_parser import convert_numeric_columns
from .number_parser import parse_br_number  # noqa: F401 — re-exported for external callers

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
    r"Per[ií]odo\s*L[ií]quido:\s*(\d{2}/\d{2}/\d{4})\s*-\s*(\d{2}/\d{2}/\d{4})",
    re.IGNORECASE,
)

# Matches section header rows: "1,0 - GRUPO 1 -", "17,1 - GRUPO 6 -", etc.
_SECTION_HEADER_RE = re.compile(r"^\d+[,.]\d+\s*-")

_CONTRATO_RE = re.compile(
    r"\bCONTRATO:\s*(.+?)(?:\n|$)",
    re.IGNORECASE,
)
_DATA_BASE_RE = re.compile(
    r"Data\s*Base:\s*(\d{2}/\d{2}/\d{4})",
    re.IGNORECASE,
)
_NUMERO_PROCESSO_RE = re.compile(
    r"N[uú]mero\s*do\s*Processo:\s*([\d./\-]+)",
    re.IGNORECASE,
)
# One item line of the main table as pdfplumber's text extraction prints it:
# "60112 AQUISIÇÃO DE CAP 50/70 T 3.289,5400 2,583 8.496,88 8.496,88 0,5731 4.869,56 0,00"
# = code, description, [Código SICRO], unit and the seven numeric columns. The last
# figure is sometimes cut by the PDF itself ("1.750.027,"), so decimals are optional.
_NUM = r"-?\d[\d.]*,\d*"
_ITEM_LINE_RE = re.compile(
    rf"^(\d{{4,}})\s+(.+?)\s+(?:(N[ãa]o|Sim)\s+)?(\S+)\s+((?:{_NUM}\s+){{6}}{_NUM})$",
    re.IGNORECASE,
)
_NUMERIC_COLUMNS_ORDER = [
    "Preço Unitário",
    "Quantidade Acumulada",
    "Valor a PI Acumulado",
    "Valor a PI Líquido",
    "Fator",
    "Reajustamento Líquido",
    "Ajuste Contratual Líquido",
]


def _records_from_text(text: str) -> list[dict]:
    """Item records read from the page's text lines, one per item line.

    Some PDFs draw each cell as a loose rectangle, so there is no single grid and
    ``extract_tables`` splits the columns into separate tables (code and
    description in one, unit in another, the numbers in a third) while the text
    stays intact. A description that wraps onto a second line is kept only up to
    its first line here; the code — the key everything hangs off — is unaffected.
    """
    records = []
    for line in text.split("\n"):
        m = _ITEM_LINE_RE.match(line.strip())
        if not m:
            continue
        record: dict = {col: "" for col in EXPECTED_COLUMNS}
        record["Serviço"] = m.group(1)
        record["Descrição"] = m.group(2).strip()
        record["Código SICRO"] = m.group(3) or ""
        record["Unidade"] = m.group(4)
        for col, value in zip(_NUMERIC_COLUMNS_ORDER, m.group(5).split()):
            record[col] = value
        records.append(record)
    return records


def _grid_is_broken(table_records: list[dict], text_records: list[dict]) -> bool:
    """True when the tables of a page do not hold what its text lines show.

    Either some "record" is not a service item (a column of numbers read as rows),
    or a code printed on the page never made it into the tables.
    """
    if any(not _is_new_record(r.get("Serviço", "")) for r in table_records):
        return True
    return not {r["Serviço"] for r in text_records} <= {r["Serviço"] for r in table_records}


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
    last_mapped_idx = max((i for i, c in enumerate(header) if c in record), default=0)
    previous: str | None = None
    for i, col in enumerate(header):
        if i >= len(raw_row):
            break
        if col in record:
            record[col] = _clean_cell(raw_row[i])
            previous = col
        elif not col and previous and i < last_mapped_idx and not record[previous]:
            # Phantom column in the middle of the header: the PDF spans the previous
            # column over it, so its value may land here (e.g. "Preço Unitário").
            record[previous] = _clean_cell(raw_row[i])
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


def _sem_espacos(texto) -> str:
    return re.sub(r"\s+", "", str(texto).lower())


def _normalize_header(raw_header: list) -> list:
    """Map raw PDF header cells to canonical column names.

    PDF cells often use newlines inside multi-word labels (e.g. 'Código\\nSICRO'),
    and some PDFs lose the spaces altogether ('ValoraPI\\nAcumulado'); whitespace
    is dropped on both sides before comparing.
    """
    mapping: dict[str, str] = {}
    for expected in EXPECTED_COLUMNS:
        expected_norm = _sem_espacos(expected)
        for cell in raw_header:
            if not cell:
                continue
            cell_norm = _sem_espacos(cell)
            if expected_norm in cell_norm:
                mapping[str(cell)] = expected
                break

    result = []
    for cell in raw_header:
        result.append(mapping.get(str(cell) if cell else "", str(cell) if cell else ""))
    return result


def extract_header(file_bytes: bytes, source_name: str) -> dict:
    result = {"Contrato": "", "Data Base": "", "Período Líquido": "", "Número do Processo": ""}
    try:
        pdf = pdfplumber.open(io.BytesIO(file_bytes))
    except Exception:
        return result
    with pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            if not result["Contrato"]:
                m = _CONTRATO_RE.search(text)
                if m:
                    result["Contrato"] = m.group(1).strip()
            if not result["Data Base"]:
                m = _DATA_BASE_RE.search(text)
                if m:
                    result["Data Base"] = m.group(1)
            if not result["Período Líquido"]:
                m = _PERIODO_LIQUIDO_RE.search(text)
                if m:
                    result["Período Líquido"] = f"{m.group(1)} - {m.group(2)}"
            if not result["Número do Processo"]:
                m = _NUMERO_PROCESSO_RE.search(text)
                if m:
                    result["Número do Processo"] = m.group(1)
            if all(result.values()):
                break
    return result


def extract_from_pdf(file_bytes: bytes, source_name: str) -> dict:
    try:
        pdf = pdfplumber.open(io.BytesIO(file_bytes))
    except Exception as exc:
        raise ExtractionError(f"Could not open '{source_name}': {exc}")

    header: list | None = None
    records: list[dict] = []
    current_record: dict | None = None
    contrato: str = ""
    data_base: str = ""
    periodo_liquido: str = ""
    numero_processo: str = ""
    _header_done: bool = False

    with pdf:
        for page in pdf.pages:
            # A page can lay its columns out differently from page 1 (e.g. a phantom
            # None column right after "Preço Unitário"), so rows are mapped by the
            # header of their own page; the document's first header is the fallback.
            page_header: list | None = None
            page_text = page.extract_text() or ""
            antes = len(records)
            antes_corrente = dict(current_record) if current_record is not None else None
            if not _header_done:
                if not contrato:
                    m = _CONTRATO_RE.search(page_text)
                    if m:
                        contrato = m.group(1).strip()
                if not data_base:
                    m = _DATA_BASE_RE.search(page_text)
                    if m:
                        data_base = m.group(1)
                if not periodo_liquido:
                    m = _PERIODO_LIQUIDO_RE.search(page_text)
                    if m:
                        periodo_liquido = f"{m.group(1)} - {m.group(2)}"
                if not numero_processo:
                    m = _NUMERO_PROCESSO_RE.search(page_text)
                    if m:
                        numero_processo = m.group(1)
                _header_done = bool(contrato and data_base and periodo_liquido and numero_processo)
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
                        candidate = _normalize_header(raw_row)
                        # Section titles ("6,0 - DEMAIS SERVIÇOS …") also match
                        # _is_header_row; only a row naming the key columns is a header.
                        if {"Serviço", "Descrição"} <= set(candidate):
                            page_header = candidate
                            if header is None:
                                header = candidate
                        continue

                    if _is_section_header(raw_row):
                        continue

                    if header is None:
                        continue

                    row_dict = _map_row(raw_row, page_header or header)
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

            text_records = _records_from_text(page_text)
            desta_pagina = records[antes:] + ([current_record] if current_record is not None else [])
            if text_records and _grid_is_broken(desta_pagina, text_records):
                # Discard what the tables produced for this page and read its lines.
                del records[antes:]
                current_record = antes_corrente
                if current_record is not None:
                    records.append(current_record)
                records.extend(text_records[:-1])
                current_record = text_records[-1]

    if current_record is not None:
        records.append(current_record)

    if not records:
        raise ExtractionError(
            f"No recognisable main-table data found in '{source_name}'."
        )

    for row in records:
        row["Período Líquido"] = periodo_liquido
        row["Source_File"] = source_name
        convert_numeric_columns(row)

    header_dict = {
        "Contrato": contrato,
        "Data Base": data_base,
        "Período Líquido": periodo_liquido,
        "Número do Processo": numero_processo,
    }
    return {"header": header_dict, "rows": records}
