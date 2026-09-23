import asyncio
import os
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .db import LOCK_CLEANUP, advisory_lock, apply_migrations, close_pools, open_pools
from .routers import upload
from .routers import jobs
from .dashboard import create_dash_app
from .services.job_manager import cleanup_stale_jobs, init_db, close_db

BASE_DIR = Path(__file__).parent


@asynccontextmanager
async def lifespan(app: FastAPI):
    await open_pools()
    await apply_migrations()
    await init_db()
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
