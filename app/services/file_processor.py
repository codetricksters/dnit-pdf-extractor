import json

from .exceptions import ExtractionError
from .extractor import extract_from_pdf
from .ocr_extractor import extract_from_pdf_ocr
from .pdf_classifier import is_image_pdf
from .storage import save_result


def classify_file(file_bytes: bytes, filename: str) -> bool:
    try:
        return is_image_pdf(file_bytes, filename)
    except Exception:
        return False


def process_text_pdf(file_bytes: bytes, filename: str, job_id: str) -> tuple[str, str | None]:
    try:
        rows = extract_from_pdf(file_bytes, filename)
    except ExtractionError as e:
        return ("", str(e))
    except Exception as e:
        return ("", f"Unexpected error processing '{filename}': {e}")

    json_content = json.dumps(rows, ensure_ascii=False, indent=2)
    result_path = save_result(job_id, filename, json_content)
    return (result_path, None)


def process_ocr_pdf(file_bytes: bytes, filename: str, job_id: str) -> tuple[str, str | None]:
    try:
        rows = extract_from_pdf_ocr(file_bytes, filename, job_id=job_id)
    except ExtractionError as e:
        return ("", str(e))
    except Exception as e:
        return ("", f"Unexpected error processing '{filename}': {e}")

    json_content = json.dumps(rows, ensure_ascii=False, indent=2)
    result_path = save_result(job_id, filename, json_content)
    return (result_path, None)
