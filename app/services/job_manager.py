import asyncio
import uuid
from datetime import datetime, timedelta, timezone

from ..db import acquire, acquire_sync
from ..models.job import FileStatus
from .storage import cleanup_job_files

_job_events: dict[str, asyncio.Event] = {}


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def init_db() -> None:
    """Recover from an unclean shutdown.

    Schema creation lives in ``migrations/``; this only fixes rows left mid
    flight, which can never finish because their executor died with the process.
    """
    async with acquire() as conn:
        await conn.execute(
            "UPDATE file_results SET status = %s, error = %s WHERE status = %s",
            (
                FileStatus.FAILED.value,
                "Server restarted during processing",
                FileStatus.PROCESSING.value,
            ),
        )


async def close_db() -> None:
    """Kept for API compatibility; the pool is closed by the app lifespan."""
    return None


async def create_job(filenames: list[str]) -> str:
    job_id = uuid.uuid4().hex[:12]
    now = _now()
    async with acquire() as conn:
        await conn.execute(
            "INSERT INTO jobs (job_id, created_at, updated_at) VALUES (%s, %s, %s)",
            (job_id, now, now),
        )
        for fname in filenames:
            await conn.execute(
                "INSERT INTO file_results (job_id, filename, status) VALUES (%s, %s, %s)",
                (job_id, fname, FileStatus.PENDING.value),
            )
    _job_events[job_id] = asyncio.Event()
    return job_id


async def get_job(job_id: str) -> dict | None:
    async with acquire() as conn:
        cur = await conn.execute("SELECT * FROM jobs WHERE job_id = %s", (job_id,))
        row = await cur.fetchone()
        if not row:
            return None
        job = dict(row)
        cur = await conn.execute(
            "SELECT * FROM file_results WHERE job_id = %s", (job_id,)
        )
        files = await cur.fetchall()
    job["files"] = {f["filename"]: dict(f) for f in files}
    return job


async def update_file_status(
    job_id: str,
    filename: str,
    status: FileStatus,
    *,
    error: str | None = None,
    result_path: str | None = None,
    needs_ocr: bool | None = None,
) -> None:
    sets = ["status = %s"]
    params: list = [status.value]
    if status == FileStatus.PROCESSING:
        sets.append("started_at = %s")
        params.append(_now())
    if status in (FileStatus.COMPLETED, FileStatus.FAILED):
        sets.append("completed_at = %s")
        params.append(_now())
    if error is not None:
        sets.append("error = %s")
        params.append(error)
    if result_path is not None:
        sets.append("result_path = %s")
        params.append(result_path)
    if needs_ocr is not None:
        sets.append("needs_ocr = %s")
        params.append(needs_ocr)
    params.extend([job_id, filename])
    async with acquire() as conn:
        await conn.execute(
            f"UPDATE file_results SET {', '.join(sets)} WHERE job_id = %s AND filename = %s",
            params,
        )
        await conn.execute(
            "UPDATE jobs SET updated_at = %s WHERE job_id = %s", (_now(), job_id)
        )


def vincular_contrato(job_id: str, filename: str, contrato_id: int, itens: int) -> None:
    """Record which contract a processed file fed and how many items it stored.

    Synchronous: it is called from ``file_processor._persistir``, which runs in
    the executor thread alongside the synchronous repositories.
    """
    with acquire_sync() as conn:
        conn.execute(
            "UPDATE file_results SET contrato_id = %s, itens = %s "
            "WHERE job_id = %s AND filename = %s",
            (contrato_id, itens, job_id, filename),
        )


async def mark_job_completed(job_id: str) -> None:
    async with acquire() as conn:
        await conn.execute(
            "UPDATE jobs SET completed = TRUE, updated_at = %s WHERE job_id = %s",
            (_now(), job_id),
        )


async def check_job_completed(job_id: str) -> bool:
    async with acquire() as conn:
        cur = await conn.execute(
            "SELECT COUNT(*) AS pendentes FROM file_results "
            "WHERE job_id = %s AND status NOT IN (%s, %s)",
            (job_id, FileStatus.COMPLETED.value, FileStatus.FAILED.value),
        )
        row = await cur.fetchone()
    return row["pendentes"] == 0


def notify_change(job_id: str) -> None:
    ev = _job_events.get(job_id)
    if ev:
        ev.set()


async def wait_for_change(job_id: str) -> None:
    ev = _job_events.get(job_id)
    if not ev:
        _job_events[job_id] = asyncio.Event()
        ev = _job_events[job_id]
    await ev.wait()
    ev.clear()


async def reset_file_for_retry(job_id: str, filename: str) -> None:
    async with acquire() as conn:
        await conn.execute(
            "UPDATE file_results SET status = %s, error = NULL, result_path = NULL, "
            "started_at = NULL, completed_at = NULL, contrato_id = NULL, itens = NULL "
            "WHERE job_id = %s AND filename = %s AND status = %s",
            (FileStatus.PENDING.value, job_id, filename, FileStatus.FAILED.value),
        )
        await conn.execute(
            "UPDATE jobs SET completed = FALSE, updated_at = %s WHERE job_id = %s",
            (_now(), job_id),
        )


async def list_jobs(status_filter: str | None = None) -> list[dict]:
    if status_filter == "active":
        where = "WHERE j.completed = FALSE"
    elif status_filter == "completed":
        where = "WHERE j.completed = TRUE"
    else:
        where = ""

    query = f"""
        SELECT j.job_id, j.created_at, j.completed,
               COUNT(f.id) AS file_count,
               COUNT(*) FILTER (WHERE f.status = 'completed')  AS completed_count,
               COUNT(*) FILTER (WHERE f.status = 'failed')     AS failed_count,
               COUNT(*) FILTER (WHERE f.status = 'processing')  AS processing_count,
               COUNT(*) FILTER (WHERE f.status = 'pending')     AS pending_count
        FROM jobs j
        LEFT JOIN file_results f ON j.job_id = f.job_id
        {where}
        GROUP BY j.job_id, j.created_at, j.completed
        ORDER BY j.created_at DESC
        LIMIT 50
    """
    async with acquire() as conn:
        cur = await conn.execute(query)
        rows = await cur.fetchall()
    return [dict(r) for r in rows]


async def cleanup_stale_jobs(max_age_minutes: int = 1440) -> None:
    cutoff = _now() - timedelta(minutes=max_age_minutes)
    async with acquire() as conn:
        cur = await conn.execute(
            "SELECT job_id FROM jobs WHERE updated_at < %s", (cutoff,)
        )
        rows = await cur.fetchall()
        for row in rows:
            cleanup_job_files(row["job_id"])
            _job_events.pop(row["job_id"], None)
        await conn.execute("DELETE FROM jobs WHERE updated_at < %s", (cutoff,))
