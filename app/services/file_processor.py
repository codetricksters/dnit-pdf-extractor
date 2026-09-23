import json
import logging

from . import contratos_repo, medicoes_repo
from .exceptions import ExtractionError
from .extractor import extract_from_pdf, extract_header
from .ocr_extractor import extract_from_pdf_ocr
from .pdf_classifier import is_image_pdf
from .storage import save_result

logger = logging.getLogger(__name__)


def classify_file(file_bytes: bytes, filename: str) -> bool:
    try:
        return is_image_pdf(file_bytes, filename)
    except Exception:
        return False


def _persistir(result: dict, filename: str, job_id: str) -> None:
    """Store the extraction in the database, alongside the JSON artefact.

    Failures here are logged, not raised: the extraction itself succeeded and the
    JSON is already on disk, so the user should still get their result. The rows
    can be recovered later by reprocessing, which is idempotent.
    """
    try:
        contrato_id = contratos_repo.registrar_do_pdf(result.get("header") or {})
        if contrato_id is None:
            logger.warning(
                "'%s': cabeçalho sem número de contrato reconhecível; "
                "itens não gravados no banco.",
                filename,
            )
            return
        resumo = medicoes_repo.gravar_itens(
            contrato_id, result.get("rows") or [], job_id=job_id
        )
        if resumo["pendencias"]:
            logger.info(
                "'%s': códigos novos aguardando confirmação: %s",
                filename,
                ", ".join(resumo["pendencias"]),
            )
    except Exception:
        logger.exception("'%s': falha ao gravar a extração no banco.", filename)


def process_text_pdf(file_bytes: bytes, filename: str, job_id: str) -> tuple[str, str | None]:
    try:
        result = extract_from_pdf(file_bytes, filename)
    except ExtractionError as e:
        return ("", str(e))
    except Exception as e:
        return ("", f"Unexpected error processing '{filename}': {e}")

    json_content = json.dumps(result, ensure_ascii=False, indent=2)
    result_path = save_result(job_id, filename, json_content)
    _persistir(result, filename, job_id)
    return (result_path, None)


def process_ocr_pdf(file_bytes: bytes, filename: str, job_id: str) -> tuple[str, str | None]:
    try:
        header = extract_header(file_bytes, filename)
        rows = extract_from_pdf_ocr(file_bytes, filename, job_id=job_id)
    except ExtractionError as e:
        return ("", str(e))
    except Exception as e:
        return ("", f"Unexpected error processing '{filename}': {e}")

    result = {"header": header, "rows": rows}
    json_content = json.dumps(result, ensure_ascii=False, indent=2)
    result_path = save_result(job_id, filename, json_content)
    _persistir(result, filename, job_id)
    return (result_path, None)
