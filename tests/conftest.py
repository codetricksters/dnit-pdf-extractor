from concurrent.futures import ThreadPoolExecutor
from unittest.mock import MagicMock

import pytest
from httpx2 import ASGITransport, AsyncClient

from app.main import app
from app.services.extractor import EXPECTED_COLUMNS


@pytest.fixture()
async def client():
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
        row["Preço Unitário"] = "1.234,56"
        row["Quantidade Acumulada"] = "100,00"
        row["Valor a PI Acumulado"] = "123.456,00"
        row["Valor a PI Líquido"] = "100.000,00"
        row["Fator"] = "1,0000"
        row["Reajustamento Líquido"] = "0,00"
        row["Ajuste Contratual Líquido"] = "0,00"
        row["Source_File"] = source
        return row

    return [_row("56988", "Pavimentação asfáltica"), _row("54393", "Terraplenagem geral")]


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
