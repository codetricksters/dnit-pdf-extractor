import os
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import MagicMock

import pytest
from httpx2 import ASGITransport, AsyncClient

from app.services.extractor import EXPECTED_COLUMNS

# A real PostgreSQL server is required. Start it with:
#   docker compose up -d postgres
DATABASE_URL_TEST = os.getenv(
    "DATABASE_URL_TEST", "postgresql://dnit:dnit@localhost:5433/dnit_test"
)


@pytest.fixture(autouse=True)
async def setup_storage(tmp_path):
    """Give each test a private storage directory and a virgin database schema.

    The schema is dropped and rebuilt from ``migrations/`` per test: with a
    server-side database there is no per-test file to point at, so isolation has
    to come from resetting the schema instead.
    """
    os.environ["STORAGE_PATH"] = str(tmp_path / "data")
    import app.config as config
    config.STORAGE_PATH = tmp_path / "data"
    config.DATABASE_URL = DATABASE_URL_TEST
    # Read at call time by the backup service, so this keeps dumps out of the
    # developer's real data directory.
    config.BACKUP_DIR = tmp_path / "data" / "backups"
    config.STORAGE_PATH.mkdir(parents=True, exist_ok=True)
    (config.STORAGE_PATH / "jobs").mkdir(exist_ok=True)

    from app import db
    await db.open_pools()
    async with db.acquire() as conn:
        await conn.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public")
    await db.apply_migrations()

    from app.services.job_manager import init_db, close_db
    await init_db()
    yield
    await close_db()
    await db.close_pools()


@pytest.fixture()
async def client():
    from app.main import app
    app.state.executor = ThreadPoolExecutor(max_workers=2)
    app.state.ocr_executor = ThreadPoolExecutor(max_workers=1)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.state.executor.shutdown(wait=False)
    app.state.ocr_executor.shutdown(wait=False)


def make_rows(source: str) -> list[dict]:
    """Build two realistic data rows tagged with *source* as the filename."""
    def _row(service: str, desc: str) -> dict:
        row = {col: "" for col in EXPECTED_COLUMNS}
        row["Serviço"] = service
        row["Descrição"] = desc
        row["Código SICRO"] = "1234567"
        row["Unidade"] = "m²"
        row["Preço Unitário"] = 1234.56
        row["Quantidade Acumulada"] = 100.0
        row["Valor a PI Acumulado"] = 123456.0
        row["Valor a PI Líquido"] = 100000.0
        row["Fator"] = 1.0
        row["Reajustamento Líquido"] = 0.0
        row["Ajuste Contratual Líquido"] = 0.0
        row["Source_File"] = source
        return row

    return [_row("56988", "Pavimentação asfáltica"), _row("54393", "Terraplenagem geral")]


def make_result(source: str) -> dict:
    """Build a full extract_from_pdf-style result dict for use in mocks."""
    return {
        "header": {
            "Contrato": "TEST-CONTRACT",
            "Data Base": "01/01/2021",
            "Período Líquido": "01/02/2024 - 29/02/2024",
            "Número do Processo": "50606.000509/2021-44",
        },
        "rows": make_rows(source),
    }


def make_pdfplumber_mock(tables_per_page: list[list[list]], page_text: str = "") -> MagicMock:
    """Return a mock that mimics pdfplumber's context-manager + pages API."""
    mock_pdf = MagicMock()
    pages = []
    for tables in tables_per_page:
        page = MagicMock()
        page.extract_tables.return_value = tables
        page.extract_text.return_value = page_text
        pages.append(page)
    mock_pdf.pages = pages
    mock_pdf.__enter__ = lambda self: self
    mock_pdf.__exit__ = MagicMock(return_value=False)
    return mock_pdf


SAMPLE_TABLE = [
    [
        "Serviço", "Descrição", "Código SICRO", "Unidade",
        "Preço Unitário", "Quantidade Acumulada", "Valor a PI Acumulado",
        "Valor a PI Líquido", "Fator", "Reajustamento Líquido", "Ajuste Contratual Líquido",
    ],
    ["56988", "Pavimentação asfáltica", "1234567", "m²", "1.234,56", "100,00", "123.456,00", "100.000,00", "1,0000", "0,00", "0,00"],
    ["54393", "Terraplenagem geral", "7654321", "m³", "890,00", "200,00", "178.000,00", "150.000,00", "1,0000", "0,00", "0,00"],
]
