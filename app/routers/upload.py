import asyncio
from typing import List

from fastapi import APIRouter, File, Request, UploadFile
from fastapi.templating import Jinja2Templates
from pathlib import Path

from ..models.job import FileStatus
from ..services.file_processor import classify_file, process_ocr_pdf, process_text_pdf
from ..services.job_manager import (
    create_job,
    mark_job_completed,
    notify_change,
    update_file_status,
)

router = APIRouter()

templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))


@router.get("/", include_in_schema=False)
async def index(request: Request):
    return templates.TemplateResponse(request, "index.html")


@router.post("/upload", tags=["extraction"])
async def upload(request: Request, files: List[UploadFile] = File(...)):
    file_data: list[tuple[str, bytes]] = []
    for f in files:
        content = await f.read()
        file_data.append((f.filename or "unknown.pdf", content))

    filenames = [name for name, _ in file_data]
    job = create_job(filenames)

    executor = request.app.state.executor
    ocr_executor = request.app.state.ocr_executor
    asyncio.create_task(_process_job(job.job_id, file_data, executor, ocr_executor))

    return {"job_id": job.job_id}


async def _process_job(
    job_id: str,
    file_data: list[tuple[str, bytes]],
    executor,
    ocr_executor,
):
    loop = asyncio.get_event_loop()

    async def _run_one(filename: str, content: bytes):
        update_file_status(job_id, filename, FileStatus.PROCESSING)
        notify_change(job_id)
        try:
            needs_ocr = await loop.run_in_executor(
                executor, classify_file, content, filename
            )
            if needs_ocr:
                json_content, error = await loop.run_in_executor(
                    ocr_executor, process_ocr_pdf, content, filename
                )
            else:
                json_content, error = await loop.run_in_executor(
                    executor, process_text_pdf, content, filename
                )
            if error:
                update_file_status(job_id, filename, FileStatus.FAILED, error=error)
            else:
                update_file_status(
                    job_id, filename, FileStatus.COMPLETED, result_data=json_content
                )
        except Exception as e:
            update_file_status(job_id, filename, FileStatus.FAILED, error=str(e))
        notify_change(job_id)

    await asyncio.gather(*[_run_one(name, content) for name, content in file_data])

    mark_job_completed(job_id)
    notify_change(job_id)
