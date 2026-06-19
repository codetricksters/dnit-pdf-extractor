import io
import re

import easyocr
import numpy as np
import pdfplumber
import torch
from .exceptions import ExtractionError
from PIL import Image

from .extractor import EXPECTED_COLUMNS, _PERIODO_LIQUIDO_RE

_SERVICE_CODE_RE = re.compile(r"^\d{4,}")

_HEADER_KEYWORDS = ("serviço", "servico", "descrição", "descricao", "código", "codigo")
_INDICES_KEYWORDS = {"adloc", "conser", "emuimp", "índices", "indices"}

_COLUMN_HEADER_MAP = [
    ("serviço", "servico"),
    ("descrição", "descricao"),
    ("código", "codigo", "sicro"),
    ("unidade",),
    ("preço", "preco", "unitário", "unitario"),
    ("quantidade", "acumulada"),
    ("valor a pi", "acumulado"),
    ("valor a pi", "liquido", "líquido"),
    ("fator",),
    ("reajustamento",),
    ("ajuste", "contratual"),
]

_reader: easyocr.Reader | None = None

gpu_available = torch.cuda.is_available()


def _get_reader() -> easyocr.Reader:
    global _reader
    if _reader is None:
        _reader = easyocr.Reader(["pt"], gpu=gpu_available)
    return _reader


def _pdf_page_to_image(page) -> Image.Image:
    return page.to_image(resolution=300).original.convert("RGB")


def _ocr_image(image: np.ndarray) -> list[tuple]:
    reader = _get_reader()
    return reader.readtext(image, paragraph=False)


def _detect_orientation(pil_image: Image.Image) -> int:
    """Detect if the page needs rotation. Returns the rotation angle (0 or -90).

    Runs OCR on original and rotated versions of the first page, comparing
    average text length to determine correct orientation.
    """
    image = np.array(pil_image)
    results = _ocr_image(image)

    if not results:
        return 0

    texts = [text for _, text, _ in results]
    avg_len = sum(len(t) for t in texts) / len(texts)

    if avg_len >= 3:
        return 0

    rotated = pil_image.rotate(-90, expand=True)
    rotated_image = np.array(rotated)
    results_rotated = _ocr_image(rotated_image)

    if not results_rotated:
        return 0

    texts_rotated = [text for _, text, _ in results_rotated]
    avg_len_rotated = sum(len(t) for t in texts_rotated) / len(texts_rotated)

    if avg_len_rotated > avg_len:
        return -90
    return 0


def _prepare_page_image(pil_image: Image.Image, rotation: int) -> np.ndarray:
    if rotation != 0:
        pil_image = pil_image.rotate(rotation, expand=True)
    return np.array(pil_image)


def _cluster_rows(results: list[tuple], tolerance: int = 20) -> list[list[dict]]:
    """Group OCR results into rows based on vertical (Y) proximity."""
    if not results:
        return []

    items = []
    for bbox, text, conf in results:
        y_center = (bbox[0][1] + bbox[2][1]) / 2
        x_left = bbox[0][0]
        x_right = bbox[2][0]
        items.append({"y": y_center, "x": x_left, "xr": x_right, "text": text, "conf": conf})

    items.sort(key=lambda it: (it["y"], it["x"]))

    rows: list[list[dict]] = []
    current_row: list[dict] = [items[0]]
    current_y = items[0]["y"]

    for item in items[1:]:
        if abs(item["y"] - current_y) <= tolerance:
            current_row.append(item)
        else:
            rows.append(current_row)
            current_row = [item]
            current_y = item["y"]
    rows.append(current_row)

    for row in rows:
        row.sort(key=lambda it: it["x"])

    return rows


def _is_header_row(row: list[dict]) -> bool:
    """True when the row contains at least 3 distinct column-header keywords.

    A single match (e.g. 'Versão dos Serviços') is not enough — the real
    table header always has Serviço + Descrição + Código + ... together.
    """
    row_text = " ".join(it["text"] for it in row).lower()
    matches = sum(1 for kw in _HEADER_KEYWORDS if kw in row_text)
    return matches >= 3


def _find_header_row(all_rows: list[list[dict]]) -> tuple[int, list[float]] | None:
    """Find the header row and extract column X-boundary positions.

    The header spans two clustered rows (main labels + sub-labels like 'SICRO', 'Unitário').
    Returns the index of the LAST header sub-row and column boundary X-positions.
    """
    for i, row in enumerate(all_rows):
        if not _is_header_row(row):
            continue

        header_items = list(row)
        if i + 1 < len(all_rows):
            next_row = all_rows[i + 1]
            next_text = " ".join(it["text"] for it in next_row).lower()
            if "sicro" in next_text or "unitário" in next_text or "unitario" in next_text:
                header_items.extend(next_row)
                return (i + 1, _extract_column_boundaries(header_items))

        return (i, _extract_column_boundaries(header_items))

    return None


def _extract_column_boundaries(header_items: list[dict]) -> list[float]:
    """Extract column boundary X-positions from header items.

    Groups header items into the 11 expected columns by matching keywords,
    then returns the left-X of each column group.
    """
    column_positions: list[float] = []

    matched_items: list[tuple[int, dict]] = []
    for item in header_items:
        text_lower = item["text"].lower()
        for col_idx, keywords in enumerate(_COLUMN_HEADER_MAP):
            if any(kw in text_lower for kw in keywords):
                matched_items.append((col_idx, item))
                break

    matched_items.sort(key=lambda t: t[1]["x"])

    seen_cols: set[int] = set()
    col_x: dict[int, float] = {}
    for col_idx, item in matched_items:
        if col_idx not in seen_cols:
            col_x[col_idx] = item["x"]
            seen_cols.add(col_idx)

    for col_idx in range(len(EXPECTED_COLUMNS)):
        if col_idx in col_x:
            column_positions.append(col_x[col_idx])
        elif column_positions:
            column_positions.append(column_positions[-1] + 150)
        else:
            column_positions.append(col_idx * 300)

    return column_positions


def _assign_to_columns(row_items: list[dict], col_boundaries: list[float]) -> list[str]:
    """Assign OCR text items to the nearest column boundary (leftward).

    Each item is assigned to the column whose left boundary is closest
    without exceeding the item's X position (with a small tolerance).

    Special handling for Serviço/Descrição (cols 0/1): the service code is
    a short numeric at the far left, while the description text starts in
    the gap between the Serviço and Descrição header positions. Items that
    start past the service code but before the Código boundary go to col 1.
    """
    num_cols = len(col_boundaries)
    cells = [""] * num_cols

    # Boundary between col 0 (Serviço) and col 1 (Descrição) in data rows:
    # service codes are narrow (~80px wide), descriptions start ~432px.
    # Use a split point between service code right edge and Descrição header.
    desc_split = col_boundaries[0] + 120 if num_cols > 1 else float("inf")

    for item in row_items:
        x = item["x"]

        if x < desc_split:
            col_idx = 0
        elif num_cols > 2 and x < col_boundaries[2] - 50:
            col_idx = 1
        else:
            col_idx = 0
            for i in range(num_cols - 1, -1, -1):
                if x >= col_boundaries[i] - 50:
                    col_idx = i
                    break

        sep = " " if cells[col_idx] else ""
        cells[col_idx] += sep + item["text"]

    return cells


def _is_indices_row(row: list[dict]) -> bool:
    row_text = " ".join(it["text"] for it in row).lower()
    return any(kw in row_text for kw in _INDICES_KEYWORDS)


_PAGE_NOISE_KEYWORDS = (
    "solicitado por", "período líquido", "período acumulado",
    "resumo da", "medição", "versão dos serviços",
)


def _is_page_noise(row: list[dict]) -> bool:
    """True for page header/footer rows that repeat on every page."""
    row_text = " ".join(it["text"] for it in row).lower()
    return any(kw in row_text for kw in _PAGE_NOISE_KEYWORDS)


_SECTION_HEADER_OCR_RE = re.compile(r"^\d+[,.]\d+")


def _is_section_header_row(row: list[dict]) -> bool:
    """True for section headers like '1,0 - GRUPO 1' or ['7,0', 'TRANSPORTES'].

    These rows have a section number in the first item and no numeric data
    columns (no prices, quantities, etc.).
    """
    first_text = row[0]["text"].strip()
    if not _SECTION_HEADER_OCR_RE.match(first_text):
        return False
    row_text = " ".join(it["text"] for it in row)
    has_price_pattern = bool(re.search(r"\d{1,3}\.\d{3}", row_text))
    return not has_price_pattern


def _is_new_record(service_val: str) -> bool:
    val = service_val.strip()
    return bool(_SERVICE_CODE_RE.match(val)) or val.upper().startswith("SUBTOTAL")


def _is_continuation_row(row: list[dict], cells: list[str]) -> bool:
    """A continuation row has only text in the Descrição area (column 1).

    Detected when: few items (1-3), no service code, and all items fall
    within the Descrição column's X-range.
    """
    if len(row) > 3:
        return False
    service_val = cells[0].strip() if cells else ""
    if service_val and _SERVICE_CODE_RE.match(service_val):
        return False
    non_empty = [c for c in cells if c.strip()]
    if len(non_empty) > 2:
        return False
    if cells[0].strip():
        return False
    return bool(cells[1].strip()) if len(cells) > 1 else False


def extract_from_pdf_ocr(file_bytes: bytes, source_name: str) -> list[dict]:
    """Extract tabular data from an image-based PDF using OCR."""
    try:
        pdf = pdfplumber.open(io.BytesIO(file_bytes))
    except Exception as exc:
        raise ExtractionError(f"Could not open '{source_name}': {exc}")

    periodo_liquido: str = ""

    with pdf:
        pages = pdf.pages
        if not pages:
            raise ExtractionError(f"No pages found in '{source_name}'.")

        page_text = pages[0].extract_text() or ""
        m = _PERIODO_LIQUIDO_RE.search(page_text)
        if m:
            periodo_liquido = f"{m.group(1)} - {m.group(2)}"

        first_image = _pdf_page_to_image(pages[0])
        rotation = _detect_orientation(first_image)

        all_page_rows: list[list[dict]] = []
        for page in pages:
            pil_image = _pdf_page_to_image(page)
            image = _prepare_page_image(pil_image, rotation)
            results = _ocr_image(image)
            if results:
                rows = _cluster_rows(results)
                all_page_rows.extend(rows)

    if not all_page_rows:
        raise ExtractionError(
            f"OCR could not extract any text from '{source_name}'."
        )

    if not periodo_liquido:
        ocr_text = " ".join(
            item["text"] for row in all_page_rows for item in row
        )
        m = _PERIODO_LIQUIDO_RE.search(ocr_text)
        if m:
            periodo_liquido = f"{m.group(1)} - {m.group(2)}"

    header_result = _find_header_row(all_page_rows)
    if header_result is None:
        raise ExtractionError(
            f"No table header found in '{source_name}' (OCR)."
        )

    header_end_idx, col_boundaries = header_result

    records: list[dict] = []
    current_record: dict | None = None

    for row_items in all_page_rows[header_end_idx + 1:]:
        if _is_indices_row(row_items):
            continue

        if _is_header_row(row_items):
            continue

        if _is_page_noise(row_items):
            continue

        if _is_section_header_row(row_items):
            continue

        cells = _assign_to_columns(row_items, col_boundaries)

        while len(cells) < len(EXPECTED_COLUMNS):
            cells.append("")

        row_dict = {col: cells[i].strip() for i, col in enumerate(EXPECTED_COLUMNS)}
        service_val = row_dict["Serviço"]
        desc_val = row_dict["Descrição"]

        if not service_val and not desc_val:
            continue

        if _is_new_record(service_val):
            if current_record is not None:
                records.append(current_record)
            current_record = row_dict
        elif current_record is not None and _is_continuation_row(row_items, cells):
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
            f"No recognisable main-table data found in '{source_name}' (OCR)."
        )

    for row in records:
        row["Período Líquido"] = periodo_liquido
        row["Source_File"] = source_name

    return records
