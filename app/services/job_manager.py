import asyncio
import uuid
from datetime import datetime, timedelta

import aiosqlite

from ..config import DB_PATH
from ..models.job import FileStatus
from .storage import cleanup_job_files

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS jobs (
    job_id     TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    completed  INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS file_results (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id       TEXT NOT NULL REFERENCES jobs(job_id) ON DELETE CASCADE,
    filename     TEXT NOT NULL,
    status       TEXT NOT NULL DEFAULT 'pending',
    error        TEXT,
    result_path  TEXT,
    needs_ocr    INTEGER,
    started_at   TEXT,
    completed_at TEXT,
    UNIQUE(job_id, filename)
);

CREATE INDEX IF NOT EXISTS idx_file_results_job_id ON file_results(job_id);
CREATE INDEX IF NOT EXISTS idx_file_results_status ON file_results(status);
"""

_job_events: dict[str, asyncio.Event] = {}
_db: aiosqlite.Connection | None = None


async def init_db() -> None:
    global _db
    _db = await aiosqlite.connect(str(DB_PATH))
    _db.row_factory = aiosqlite.Row
    await _db.execute("PRAGMA journal_mode=WAL")
    await _db.execute("PRAGMA foreign_keys=ON")
    await _db.executescript(_SCHEMA_SQL)
    await _db.commit()
    await _db.execute(
        "UPDATE file_results SET status = ?, error = ? WHERE status = ?",
        (FileStatus.FAILED.value, "Server restarted during processing", FileStatus.PROCESSING.value),
    )
    await _db.commit()


async def close_db() -> None:
    global _db
    if _db:
        await _db.close()
        _db = None


async def create_job(filenames: list[str]) -> str:
    job_id = uuid.uuid4().hex[:12]
    now = datetime.now().isoformat()
    await _db.execute(
        "INSERT INTO jobs (job_id, created_at, updated_at) VALUES (?, ?, ?)",
        (job_id, now, now),
    )
    for fname in filenames:
        await _db.execute(
            "INSERT INTO file_results (job_id, filename, status) VALUES (?, ?, ?)",
            (job_id, fname, FileStatus.PENDING.value),
        )
    await _db.commit()
    _job_events[job_id] = asyncio.Event()
    return job_id


async def get_job(job_id: str) -> dict | None:
    async with _db.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)) as cur:
        row = await cur.fetchone()
    if not row:
        return None
    job = dict(row)
    async with _db.execute(
        "SELECT * FROM file_results WHERE job_id = ?", (job_id,)
    ) as cur:
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
    sets = ["status = ?"]
    params: list = [status.value]
    if status == FileStatus.PROCESSING:
        sets.append("started_at = ?")
        params.append(datetime.now().isoformat())
    if status in (FileStatus.COMPLETED, FileStatus.FAILED):
        sets.append("completed_at = ?")
        params.append(datetime.now().isoformat())
    if error is not None:
        sets.append("error = ?")
        params.append(error)
    if result_path is not None:
        sets.append("result_path = ?")
        params.append(result_path)
    if needs_ocr is not None:
        sets.append("needs_ocr = ?")
        params.append(int(needs_ocr))
    params.extend([job_id, filename])
    await _db.execute(
        f"UPDATE file_results SET {', '.join(sets)} WHERE job_id = ? AND filename = ?",
        params,
    )
    await _db.execute(
        "UPDATE jobs SET updated_at = ? WHERE job_id = ?",
        (datetime.now().isoformat(), job_id),
    )
    await _db.commit()


async def mark_job_completed(job_id: str) -> None:
    await _db.execute(
        "UPDATE jobs SET completed = 1, updated_at = ? WHERE job_id = ?",
        (datetime.now().isoformat(), job_id),
    )
    await _db.commit()


async def check_job_completed(job_id: str) -> bool:
    async with _db.execute(
        "SELECT COUNT(*) FROM file_results WHERE job_id = ? AND status NOT IN (?, ?)",
        (job_id, FileStatus.COMPLETED.value, FileStatus.FAILED.value),
    ) as cur:
        row = await cur.fetchone()
    return row[0] == 0


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
    await _db.execute(
        "UPDATE file_results SET status = ?, error = NULL, result_path = NULL, "
        "started_at = NULL, completed_at = NULL "
        "WHERE job_id = ? AND filename = ? AND status = ?",
        (FileStatus.PENDING.value, job_id, filename, FileStatus.FAILED.value),
    )
    await _db.execute(
        "UPDATE jobs SET completed = 0, updated_at = ? WHERE job_id = ?",
        (datetime.now().isoformat(), job_id),
    )
    await _db.commit()


async def list_jobs(status_filter: str | None = None) -> list[dict]:
    if status_filter == "active":
        where = "WHERE j.completed = 0"
    elif status_filter == "completed":
        where = "WHERE j.completed = 1"
    else:
        where = ""

    query = f"""
        SELECT j.job_id, j.created_at, j.completed,
               COUNT(f.id) AS file_count,
               SUM(CASE WHEN f.status = 'completed' THEN 1 ELSE 0 END) AS completed_count,
               SUM(CASE WHEN f.status = 'failed' THEN 1 ELSE 0 END) AS failed_count,
               SUM(CASE WHEN f.status = 'processing' THEN 1 ELSE 0 END) AS processing_count,
               SUM(CASE WHEN f.status = 'pending' THEN 1 ELSE 0 END) AS pending_count
        FROM jobs j
        LEFT JOIN file_results f ON j.job_id = f.job_id
        {where}
        GROUP BY j.job_id
        ORDER BY j.created_at DESC
        LIMIT 50
    """
    async with _db.execute(query) as cur:
        rows = await cur.fetchall()
    return [dict(r) for r in rows]


async def cleanup_stale_jobs(max_age_minutes: int = 1440) -> None:
    cutoff = (datetime.now() - timedelta(minutes=max_age_minutes)).isoformat()
    async with _db.execute(
        "SELECT job_id FROM jobs WHERE updated_at < ?", (cutoff,)
    ) as cur:
        rows = await cur.fetchall()
    for row in rows:
        cleanup_job_files(row["job_id"])
        _job_events.pop(row["job_id"], None)
    await _db.execute("DELETE FROM jobs WHERE updated_at < ?", (cutoff,))
    await _db.commit()
