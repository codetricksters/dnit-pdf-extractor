import asyncio
import uuid
from datetime import datetime, timedelta

from ..models.job import FileResult, FileStatus, Job

_jobs: dict[str, Job] = {}
_job_events: dict[str, asyncio.Event] = {}


def create_job(filenames: list[str]) -> Job:
    job_id = uuid.uuid4().hex[:12]
    job = Job(job_id=job_id)
    for fname in filenames:
        job.files[fname] = FileResult(filename=fname)
    _jobs[job_id] = job
    _job_events[job_id] = asyncio.Event()
    return job


def get_job(job_id: str) -> Job | None:
    return _jobs.get(job_id)


def update_file_status(
    job_id: str,
    filename: str,
    status: FileStatus,
    *,
    error: str | None = None,
    result_data: str | None = None,
) -> None:
    job = _jobs.get(job_id)
    if not job:
        return
    fr = job.files.get(filename)
    if not fr:
        return
    fr.status = status
    if status == FileStatus.PROCESSING:
        fr.started_at = datetime.now()
    if status in (FileStatus.COMPLETED, FileStatus.FAILED):
        fr.completed_at = datetime.now()
    if error is not None:
        fr.error = error
    if result_data is not None:
        fr.result_data = result_data


def mark_job_completed(job_id: str) -> None:
    job = _jobs.get(job_id)
    if job:
        job.completed = True


def notify_change(job_id: str) -> None:
    ev = _job_events.get(job_id)
    if ev:
        ev.set()


async def wait_for_change(job_id: str) -> None:
    ev = _job_events.get(job_id)
    if ev:
        await ev.wait()
        ev.clear()


def cleanup_stale_jobs(max_age: timedelta = timedelta(minutes=30)) -> None:
    now = datetime.now()
    stale = [jid for jid, job in _jobs.items() if now - job.created_at > max_age]
    for jid in stale:
        _jobs.pop(jid, None)
        _job_events.pop(jid, None)
