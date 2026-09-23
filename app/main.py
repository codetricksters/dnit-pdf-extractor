import asyncio
import os
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .db import (
    LOCK_BACKUP,
    LOCK_CLEANUP,
    advisory_lock,
    apply_migrations,
    close_pools,
    open_pools,
)
from .routers import upload
from .routers import jobs
from .dashboard import create_dash_app
from .services import backup, template_repo
from .services.job_manager import cleanup_stale_jobs, init_db, close_db

BASE_DIR = Path(__file__).parent


@asynccontextmanager
async def lifespan(app: FastAPI):
    await open_pools()
    await apply_migrations()
    await init_db()
    # Runs after the migrations because it writes to the template table. Only
    # installs the packaged template when the table is empty, so a restart never
    # undoes what the user uploaded or activated.
    await asyncio.to_thread(template_repo.garantir_semente)
    app.state.executor = ThreadPoolExecutor(
        max_workers=min(4, os.cpu_count() or 2)
    )
    app.state.ocr_executor = ThreadPoolExecutor(max_workers=1)
    task = asyncio.create_task(_cleanup_loop())
    yield
    task.cancel()
    app.state.executor.shutdown(wait=False)
    app.state.ocr_executor.shutdown(wait=False)
    await close_db()
    await close_pools()


async def _cleanup_loop():
    while True:
        await asyncio.sleep(300)
        # Every uvicorn worker runs this loop. The advisory lock keeps them from
        # deleting the same stale jobs concurrently.
        async with advisory_lock(LOCK_CLEANUP) as got:
            if got:
                await cleanup_stale_jobs()
        # Same loop rather than a second task: both are periodic housekeeping,
        # and the backup decides for itself whether the configured interval has
        # elapsed. pg_dump blocks, hence the thread.
        async with advisory_lock(LOCK_BACKUP) as got:
            if got:
                await asyncio.to_thread(backup.executar_agendado)


app = FastAPI(
    title="DNIT PDF Extractor",
    description="Upload DNIT Medição PDFs and download a consolidated Excel spreadsheet.",
    version="0.1.0",
    lifespan=lifespan,
)

app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

app.include_router(upload.router)
app.include_router(jobs.router)

app.mount("/dashboard", create_dash_app())
