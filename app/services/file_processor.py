import json

from .exceptions import ExtractionError
from .extractor import extract_from_pdf
from .ocr_extractor import extract_from_pdf_ocr
from .pdf_classifier import is_image_pdf


def classify_file(file_bytes: bytes, filename: str) -> bool:
    """Return True if OCR is needed. Runs in the general thread pool."""
    try:
        return is_image_pdf(file_bytes, filename)
    except Exception:
        return False


def process_text_pdf(file_bytes: bytes, filename: str) -> tuple[str, str | None]:
    """Extract from text-based PDF. Runs in the general thread pool."""
    try:
        rows = extract_from_pdf(file_bytes, filename)
    except ExtractionError as e:
        return ("", str(e))
    except Exception as e:
        return ("", f"Unexpected error processing '{filename}': {e}")

    json_content = json.dumps(rows, ensure_ascii=False, indent=2)
    return (json_content, None)


def process_ocr_pdf(file_bytes: bytes, filename: str) -> tuple[str, str | None]:
    """Extract from image-based PDF. Runs in the OCR queue (1 worker)."""
    try:
        rows = extract_from_pdf_ocr(file_bytes, filename)
    except ExtractionError as e:
        return ("", str(e))
    except Exception as e:
        return ("", f"Unexpected error processing '{filename}': {e}")

    json_content = json.dumps(rows, ensure_ascii=False, indent=2)
    return (json_content, None)
