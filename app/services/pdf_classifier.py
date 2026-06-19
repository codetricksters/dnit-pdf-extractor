import io

import pdfplumber

from .exceptions import ExtractionError


def is_image_pdf(file_bytes: bytes, source_name: str) -> bool:
    """Determine whether a PDF is image-based (needs OCR) or text-based.

    A page is considered image-based when it has no extractable text characters
    but does contain embedded images. If more than half the pages are image-based,
    the PDF is classified as needing OCR.
    """
    try:
        pdf = pdfplumber.open(io.BytesIO(file_bytes))
    except Exception as exc:
        raise ExtractionError(f"Could not open '{source_name}': {exc}")

    image_pages = 0
    total_pages = 0

    with pdf:
        for page in pdf.pages:
            total_pages += 1
            text = page.extract_text() or ""
            has_text = len(text.strip()) > 50
            has_images = bool(page.images)

            if not has_text and has_images:
                image_pages += 1

    if total_pages == 0:
        return False

    return image_pages > (total_pages / 2)
