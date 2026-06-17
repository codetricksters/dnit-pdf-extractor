from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .routers import upload

BASE_DIR = Path(__file__).parent

app = FastAPI(
    title="DNIT PDF Extractor",
    description="Upload DNIT Medição PDFs and download a consolidated Excel spreadsheet.",
    version="0.1.0",
)

app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

app.include_router(upload.router)
