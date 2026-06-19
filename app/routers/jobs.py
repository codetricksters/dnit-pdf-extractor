import io
import json
import zipfile
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from ..models.job import FileStatus
from ..services.job_manager import get_job, notify_change, wait_for_change

router = APIRouter(prefix="/jobs", tags=["jobs"])


def _job_status_dict(job) -> dict:
    return {
        "job_id": job.job_id,
        "completed": job.completed,
        "files": {
            fname: {
                "status": fr.status.value,
                "error": fr.error,
            }
            for fname, fr in job.files.items()
        },
    }


@router.get("/{job_id}/status")
async def job_status(job_id: str):
    job = get_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    return _job_status_dict(job)


@router.get("/{job_id}/events")
async def job_events(job_id: str):
    job = get_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found")

    async def event_generator():
        while True:
            current_job = get_job(job_id)
            if not current_job:
                break
            data = json.dumps(_job_status_dict(current_job), ensure_ascii=False)
            yield f"data: {data}\n\n"
            if current_job.completed:
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
    job = get_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    fr = job.files.get(filename)
    if not fr:
        raise HTTPException(404, "File not found in job")
    if fr.status != FileStatus.COMPLETED or not fr.result_data:
        raise HTTPException(409, "File not ready or failed")

    json_name = Path(filename).stem + "_resultado.json"
    buffer = io.BytesIO(fr.result_data.encode("utf-8"))

    return StreamingResponse(
        buffer,
        media_type="application/json",
        headers={"Content-Disposition": f"attachment; filename={json_name}"},
    )


@router.get("/{job_id}/download")
async def download_all(job_id: str):
    job = get_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    if not job.completed:
        raise HTTPException(409, "Job still processing")

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for fname, fr in job.files.items():
            if fr.status == FileStatus.COMPLETED and fr.result_data:
                json_name = Path(fname).stem + "_resultado.json"
                zf.writestr(json_name, fr.result_data)

    buffer.seek(0)
    return StreamingResponse(
        buffer,
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=resultados.zip"},
    )
