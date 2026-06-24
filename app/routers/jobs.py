import asyncio
import io
import json
import zipfile
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from ..models.job import FileStatus
from ..services.file_processor import classify_file, process_ocr_pdf, process_text_pdf
from ..services.job_manager import (
    check_job_completed,
    get_job,
    list_jobs,
    mark_job_completed,
    notify_change,
    reset_file_for_retry,
    update_file_status,
    wait_for_change,
)
from ..services.storage import read_result, job_dir

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("")
async def get_jobs(status: str | None = None):
    if status and status not in ("active", "completed"):
        raise HTTPException(400, "status must be 'active' or 'completed'")
    jobs = await list_jobs(status)
    return jobs


def _job_status_dict(job: dict) -> dict:
    return {
        "job_id": job["job_id"],
        "completed": bool(job["completed"]),
        "files": {
            fname: {
                "status": fr["status"],
                "error": fr.get("error"),
            }
            for fname, fr in job["files"].items()
        },
    }


@router.get("/{job_id}/status")
async def job_status(job_id: str):
    job = await get_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    return _job_status_dict(job)


@router.get("/{job_id}/events")
async def job_events(job_id: str):
    job = await get_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found")

    async def event_generator():
        while True:
            current_job = await get_job(job_id)
            if not current_job:
                break
            data = json.dumps(_job_status_dict(current_job), ensure_ascii=False)
            yield f"data: {data}\n\n"
            if current_job["completed"]:
                yield "event: complete\ndata: done\n\n"
                break
            await wait_for_change(job_id)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/{job_id}/download/{filename}")
async def download_file(job_id: str, filename: str):
    job = await get_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    fr = job["files"].get(filename)
    if not fr:
        raise HTTPException(404, "File not found in job")
    if fr["status"] != FileStatus.COMPLETED.value or not fr.get("result_path"):
        raise HTTPException(409, "File not ready or failed")

    json_content = read_result(fr["result_path"])
    json_name = Path(filename).stem + "_resultado.json"
    buffer = io.BytesIO(json_content.encode("utf-8"))

    return StreamingResponse(
        buffer,
        media_type="application/json",
        headers={"Content-Disposition": f"attachment; filename={json_name}"},
    )


@router.get("/{job_id}/download")
async def download_all(job_id: str):
    job = await get_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    if not job["completed"]:
        raise HTTPException(409, "Job still processing")

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for fname, fr in job["files"].items():
            if fr["status"] == FileStatus.COMPLETED.value and fr.get("result_path"):
                json_content = read_result(fr["result_path"])
                json_name = Path(fname).stem + "_resultado.json"
                zf.writestr(json_name, json_content)

    buffer.seek(0)
    return StreamingResponse(
        buffer,
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=resultados.zip"},
    )


@router.post("/{job_id}/retry/{filename}")
async def retry_file(job_id: str, filename: str, request: Request):
    job = await get_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    fr = job["files"].get(filename)
    if not fr:
        raise HTTPException(404, "File not found in job")
    if fr["status"] != FileStatus.FAILED.value:
        raise HTTPException(409, "File is not in failed state")

    upload_path = job_dir(job_id) / "uploads" / filename
    if not upload_path.exists():
        raise HTTPException(410, "Original file no longer available")

    content = upload_path.read_bytes()
    await reset_file_for_retry(job_id, filename)
    notify_change(job_id)

    executor = request.app.state.executor
    ocr_executor = request.app.state.ocr_executor
    asyncio.create_task(_process_single_file(job_id, filename, content, executor, ocr_executor))

    return {"status": "retrying", "filename": filename}


async def _process_single_file(
    job_id: str,
    filename: str,
    content: bytes,
    executor,
    ocr_executor,
):
    loop = asyncio.get_event_loop()
    await update_file_status(job_id, filename, FileStatus.PROCESSING)
    notify_change(job_id)
    try:
        needs_ocr = await loop.run_in_executor(executor, classify_file, content, filename)
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
            await update_file_status(job_id, filename, FileStatus.COMPLETED, result_path=json_content)
    except Exception as e:
        await update_file_status(job_id, filename, FileStatus.FAILED, error=str(e))
    notify_change(job_id)

    if await check_job_completed(job_id):
        await mark_job_completed(job_id)
        notify_change(job_id)
