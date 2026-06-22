import shutil
from pathlib import Path

from ..config import STORAGE_PATH


def job_dir(job_id: str) -> Path:
    return STORAGE_PATH / "jobs" / job_id


def results_dir(job_id: str) -> Path:
    d = job_dir(job_id) / "results"
    d.mkdir(parents=True, exist_ok=True)
    return d


def pages_dir(job_id: str) -> Path:
    d = job_dir(job_id) / "pages"
    d.mkdir(parents=True, exist_ok=True)
    return d


def uploads_dir(job_id: str) -> Path:
    d = job_dir(job_id) / "uploads"
    d.mkdir(parents=True, exist_ok=True)
    return d


def save_upload(job_id: str, filename: str, content: bytes) -> Path:
    dest = uploads_dir(job_id) / filename
    dest.write_bytes(content)
    return dest


def save_result(job_id: str, filename: str, json_content: str) -> str:
    stem = Path(filename).stem
    dest = results_dir(job_id) / f"{stem}_resultado.json"
    dest.write_text(json_content, encoding="utf-8")
    return str(dest.relative_to(STORAGE_PATH))


def read_result(relative_path: str) -> str:
    return (STORAGE_PATH / relative_path).read_text(encoding="utf-8")


def save_page_image(job_id: str, page_num: int, image_bytes: bytes) -> Path:
    dest = pages_dir(job_id) / f"page_{page_num:04d}.png"
    dest.write_bytes(image_bytes)
    return dest


def cleanup_job_files(job_id: str) -> None:
    d = job_dir(job_id)
    if d.exists():
        shutil.rmtree(d)
