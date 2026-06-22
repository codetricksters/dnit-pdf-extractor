import asyncio
from typing import List

from fastapi import APIRouter, File, Request, UploadFile
from fastapi.templating import Jinja2Templates
from pathlib import Path

from ..models.job import FileStatus
from ..services.file_processor import classify_file, process_ocr_pdf, process_text_pdf
from ..services.job_manager import (
    create_job,
    check_job_completed,
    mark_job_completed,
    notify_change,
    update_file_status,
)
from ..services.storage import save_upload

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
    job_id = await create_job(filenames)

    for name, content in file_data:
        save_upload(job_id, name, content)

    executor = request.app.state.executor
    ocr_executor = request.app.state.ocr_executor
    asyncio.create_task(_process_job(job_id, file_data, executor, ocr_executor))

    return {"job_id": job_id}


async def _process_job(
    job_id: str,
    file_data: list[tuple[str, bytes]],
    executor,
    ocr_executor,
):
    loop = asyncio.get_event_loop()

    async def _run_one(filename: str, content: bytes):
        await update_file_status(job_id, filename, FileStatus.PROCESSING)
        notify_change(job_id)
        try:
            needs_ocr = await loop.run_in_executor(
                executor, classify_file, content, filename
            )
            await update_file_status(job_id, filename, FileStatus.PROCESSING, needs_ocr=needs_ocr)
            if needs_ocr:
                json_content, error = await loop.run_in_executor(
                    ocr_executor, process_ocr_pdf, content, filename, job_id
                )
            else:
                json_content, error = await loop.run_in_executor(
                    executor, process_text_pdf, content, filename, job_id
                )
            if error:
                await update_file_status(job_id, filename, FileStatus.FAILED, error=error)
            else:
                await update_file_status(
                    job_id, filename, FileStatus.COMPLETED, result_path=json_content
                )
        except Exception as e:
            await update_file_status(job_id, filename, FileStatus.FAILED, error=str(e))
        notify_change(job_id)

    await asyncio.gather(*[_run_one(name, content) for name, content in file_data])

    if await check_job_completed(job_id):
        await mark_job_completed(job_id)
        notify_change(job_id)
