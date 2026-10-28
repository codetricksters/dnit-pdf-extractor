import io
import logging
import re
import shutil

import numpy as np
import pdfplumber
from .exceptions import ExtractionError
from PIL import Image

from .extractor import (
    EXPECTED_COLUMNS,
    _CONTRATO_RE,
    _DATA_BASE_RE,
    _NUMERO_PROCESSO_RE,
    _PERIODO_LIQUIDO_RE,
)
from .number_parser import convert_numeric_columns

# More tolerant regex for OCR text: colon is optional, "/" can be misread, dash between dates optional
_PERIODO_LIQUIDO_OCR_RE = re.compile(
    r"Per[ií]odo\s+L[ií]quido[:\s]*(\d{2}[/lI|]\d{2}[/lI|]\d{4})\s*[-–—]?\s*(\d{2}[/lI|]\d{2}[/lI|]\d{4})",
    re.IGNORECASE,
)

logger = logging.getLogger(__name__)

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

# --- Tesseract (primary OCR engine) ---

_TESSERACT_AVAILABLE: bool | None = None  # None = not yet checked


def _tesseract_available() -> bool:
    global _TESSERACT_AVAILABLE
    if _TESSERACT_AVAILABLE is None:
        _TESSERACT_AVAILABLE = shutil.which("tesseract") is not None
    return _TESSERACT_AVAILABLE


def _ocr_image_tesseract(pil_image: Image.Image) -> list[tuple]:
    """Run Tesseract and return results in EasyOCR-compatible format."""
    import pytesseract

    # psm 4 (one column of variable-size text) keeps one-letter cells such as the
    # unit "T", which psm 3 drops; rows are rebuilt from the coordinates anyway.
    config = r"--oem 3 --psm 4 -l por+eng"
    data = pytesseract.image_to_data(
        pil_image.convert("L"),  # grayscale
        config=config,
        output_type=pytesseract.Output.DICT,
    )

    results = []
    for i in range(len(data["text"])):
        text = data["text"][i].strip()
        conf = int(data["conf"][i])
        if conf < 10 or not text:
            continue
        x = data["left"][i]
        y = data["top"][i]
        w = data["width"][i]
        h = data["height"][i]
        bbox = [[x, y], [x + w, y], [x + w, y + h], [x, y + h]]
        results.append((bbox, text, conf / 100.0))
    return results


# --- EasyOCR (fallback when Tesseract is not installed) ---

_reader = None
_reader_cpu = None
_use_gpu = False

try:
    import torch
    import easyocr
    _use_gpu = torch.cuda.is_available()
    _EASYOCR_AVAILABLE = True
except ImportError:
    _EASYOCR_AVAILABLE = False


def _get_reader(gpu: bool = True):
    global _reader, _reader_cpu, _use_gpu
    if gpu and _use_gpu:
        if _reader is None:
            _reader = easyocr.Reader(["pt"], gpu=True)
        return _reader
    else:
        if _reader_cpu is None:
            _reader_cpu = easyocr.Reader(["pt"], gpu=False)
        return _reader_cpu


def _ocr_image_easyocr(image: np.ndarray) -> list[tuple]:
    global _use_gpu
    if _use_gpu:
        try:
            return _get_reader(gpu=True).readtext(image, paragraph=False)
        except Exception:
            _use_gpu = False
    return _get_reader(gpu=False).readtext(image, paragraph=False)


def _pdf_page_to_image(page) -> Image.Image:
    return page.to_image(resolution=300).original.convert("RGB")


def _ocr_image(pil_image: Image.Image) -> list[tuple]:
    """Run OCR using Tesseract (preferred) or EasyOCR (fallback)."""
    if _tesseract_available():
        return _ocr_image_tesseract(pil_image)
    if _EASYOCR_AVAILABLE:
        return _ocr_image_easyocr(np.array(pil_image))
    raise ExtractionError(
        "No OCR engine available. Install Tesseract: "
        "sudo apt-get install tesseract-ocr tesseract-ocr-por"
    )


_OSD_MIN_CONFIDENCE = 2.0


def _orientation_from_osd(pil_image: Image.Image) -> int | None:
    """Rotation to apply (PIL's counter-clockwise degrees) according to Tesseract's
    orientation detection, or None when it is unavailable or not confident."""
    if not _tesseract_available():
        return None
    import pytesseract

    try:
        # OSD does not need the full 300 dpi render.
        reduzida = pil_image.convert("L")
        reduzida.thumbnail((1800, 1800))
        osd = pytesseract.image_to_osd(reduzida, output_type=pytesseract.Output.DICT)
    except Exception:
        return None
    if float(osd.get("orientation_conf", 0)) < _OSD_MIN_CONFIDENCE:
        return None
    # "rotate" is the clockwise angle that makes the text upright.
    return -int(osd.get("rotate", 0)) % 360 or 0


def _detect_orientation(pil_image: Image.Image) -> int:
    """Detect if the page needs rotation. Returns the angle to pass to PIL's
    ``rotate`` (0, 90, 180 or 270; the heuristic fallback only finds 0 or -90)."""
    osd = _orientation_from_osd(pil_image)
    if osd is not None:
        return osd

    results = _ocr_image(pil_image)

    if not results:
        return 0

    texts = [text for _, text, _ in results]
    avg_len = sum(len(t) for t in texts) / len(texts)

    if avg_len >= 3:
        return 0

    rotated = pil_image.rotate(-90, expand=True)
    results_rotated = _ocr_image(rotated)

    if not results_rotated:
        return 0

    texts_rotated = [text for _, text, _ in results_rotated]
    avg_len_rotated = sum(len(t) for t in texts_rotated) / len(texts_rotated)

    if avg_len_rotated > avg_len:
        return -90
    return 0


def _prepare_page_image(pil_image: Image.Image, rotation: int) -> Image.Image:
    if rotation != 0:
        pil_image = pil_image.rotate(rotation, expand=True)
    return pil_image


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


# Whole-word patterns: "conser" must not match the "CONSERVAÇÃO ROTINEIRA" item.
_INDICES_PATTERNS = [
    re.compile(r"\b" + kw + r"\b", re.IGNORECASE) for kw in _INDICES_KEYWORDS
]


def _is_indices_row(row: list[dict]) -> bool:
    row_text = " ".join(it["text"] for it in row)
    return any(pat.search(row_text) for pat in _INDICES_PATTERNS)


_PAGE_NOISE_KEYWORDS = (
    "solicitado por", "período líquido", "período acumulado",
    "resumo da", "medição", "versão dos serviços",
    "superintendência", "data base:", "periodo liquido", "número do processo",
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
    """A continuation row only has text in the Descrição column.

    The wrapped line of a description can have any number of words, so the test
    is on the columns, not on how many items the row has.
    """
    if len(cells) < 2 or cells[0].strip() or not cells[1].strip():
        return False
    return not any(c.strip() for c in cells[2:])


_SOMAS = ("Valor a PI Acumulado", "Valor a PI Líquido", "Reajustamento Líquido")


def _conferir_subtotais(records: list[dict], source_name: str) -> list[str]:
    """Sections whose SUBTOTAL line differs from the sum of the items read.

    OCR can swallow a figure (e.g. two equal values read as one), which no rule
    can rebuild; the SUBTOTAL printed on the page is what exposes it. Returns the
    codes of each divergent section and logs a warning for it.
    """
    divergentes: list[str] = []
    codigos: list[str] = []
    somas = dict.fromkeys(_SOMAS, 0.0)
    for r in records:
        servico = r["Serviço"].strip()
        if _SERVICE_CODE_RE.match(servico):
            codigos.append(servico)
            for col in _SOMAS:
                somas[col] += r.get(col) or 0.0
        elif servico.upper().startswith("SUBTOTAL"):
            if any(abs(somas[c] - (r.get(c) or 0.0)) > 0.05 for c in _SOMAS):
                divergentes.append(", ".join(codigos))
                logger.warning(
                    "'%s' (OCR): o SUBTOTAL não fecha com os itens lidos (%s); "
                    "confira esses códigos.", source_name, ", ".join(codigos),
                )
            codigos = []
            somas = dict.fromkeys(_SOMAS, 0.0)
    return divergentes


def _extract_pages_via_disk(pdf, source_name: str, job_id: str) -> list[list[dict]]:
    """Split PDF pages to disk as PNGs, then OCR each one at a time."""
    from .storage import save_page_image, pages_dir

    with pdf:
        pages = pdf.pages
        if not pages:
            raise ExtractionError(f"No pages found in '{source_name}'.")

        first_image = _pdf_page_to_image(pages[0])
        rotation = _detect_orientation(first_image)
        del first_image

        page_image_paths = []
        for i, page in enumerate(pages):
            pil_image = _pdf_page_to_image(page)
            buf = io.BytesIO()
            pil_image.save(buf, format="PNG")
            path = save_page_image(job_id, i, buf.getvalue())
            page_image_paths.append(path)
            del pil_image, buf

    all_page_rows: list[list[dict]] = []
    for path in page_image_paths:
        pil_image = Image.open(path)
        prepared = _prepare_page_image(pil_image, rotation)
        results = _ocr_image(prepared)
        if results:
            rows = _cluster_rows(results)
            all_page_rows.extend(rows)
        del prepared, pil_image
        path.unlink(missing_ok=True)

    return all_page_rows


def _header_from_ocr(all_page_rows: list[list[dict]]) -> dict:
    """Contrato, Data Base and Número do Processo read from the OCR'd lines.

    A scanned PDF has no text layer, so ``extractor.extract_header`` finds nothing
    in it; without the contract number the items cannot be stored at all.
    """
    text = "\n".join(" ".join(it["text"] for it in row) for row in all_page_rows)
    header: dict = {}
    for chave, padrao in (
        ("Contrato", _CONTRATO_RE),
        ("Data Base", _DATA_BASE_RE),
        ("Número do Processo", _NUMERO_PROCESSO_RE),
    ):
        m = padrao.search(text)
        if m:
            header[chave] = m.group(1).strip()
    return header


def extract_from_pdf_ocr(
    file_bytes: bytes,
    source_name: str,
    *,
    job_id: str | None = None,
    header_out: dict | None = None,
) -> list[dict]:
    """Extract tabular data from an image-based PDF using OCR.

    When ``header_out`` is given, the contract header read from the OCR text is
    written into it.

    When job_id is provided, pages are split to disk and processed one at a
    time to avoid holding all page images in memory simultaneously.
    """
    try:
        pdf = pdfplumber.open(io.BytesIO(file_bytes))
    except Exception as exc:
        raise ExtractionError(f"Could not open '{source_name}': {exc}")

    periodo_liquido: str = ""

    if job_id:
        with pdf:
            pages = pdf.pages
            if not pages:
                raise ExtractionError(f"No pages found in '{source_name}'.")
            for page in pages:
                page_text = page.extract_text() or ""
                m = _PERIODO_LIQUIDO_RE.search(page_text)
                if m:
                    periodo_liquido = f"{m.group(1)} - {m.group(2)}"
                    break

        pdf2 = pdfplumber.open(io.BytesIO(file_bytes))
        all_page_rows = _extract_pages_via_disk(pdf2, source_name, job_id)
    else:
        with pdf:
            pages = pdf.pages
            if not pages:
                raise ExtractionError(f"No pages found in '{source_name}'.")

            for page in pages:
                page_text = page.extract_text() or ""
                m = _PERIODO_LIQUIDO_RE.search(page_text)
                if m:
                    periodo_liquido = f"{m.group(1)} - {m.group(2)}"
                    break

            first_image = _pdf_page_to_image(pages[0])
            rotation = _detect_orientation(first_image)

            all_page_rows: list[list[dict]] = []
            for page in pages:
                pil_image = _pdf_page_to_image(page)
                prepared = _prepare_page_image(pil_image, rotation)
                results = _ocr_image(prepared)
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
        m = _PERIODO_LIQUIDO_RE.search(ocr_text) or _PERIODO_LIQUIDO_OCR_RE.search(ocr_text)
        if m:
            d1 = re.sub(r"[lI|]", "/", m.group(1))
            d2 = re.sub(r"[lI|]", "/", m.group(2))
            periodo_liquido = f"{d1} - {d2}"

    if header_out is not None:
        header_out.update(_header_from_ocr(all_page_rows))

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
        convert_numeric_columns(row)

    _conferir_subtotais(records, source_name)
    return records
