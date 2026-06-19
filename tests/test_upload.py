"""Tests for POST /upload — async job creation and processing."""
import asyncio
import json
from unittest.mock import patch

import pytest

from .conftest import make_rows
from .pdf_factory import corrupt_pdf, no_table_pdf


async def _post_files(client, files_bytes: dict[str, bytes]):
    files = [
        ("files", (name, data, "application/pdf"))
        for name, data in files_bytes.items()
    ]
    return await client.post("/upload", files=files)


async def _wait_for_job(client, job_id: str, timeout: float = 5.0):
    """Poll job status until completed or timeout."""
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        res = await client.get(f"/jobs/{job_id}/status")
        data = res.json()
        if data["completed"]:
            return data
        await asyncio.sleep(0.1)
    raise TimeoutError(f"Job {job_id} did not complete in {timeout}s")


# --- Input validation ---

async def test_upload_no_files_returns_422(client):
    response = await client.post("/upload")
    assert response.status_code == 422


# --- Happy path (mocked extractor) ---

@patch("app.services.file_processor.is_image_pdf", return_value=False)
@patch("app.services.file_processor.extract_from_pdf")
async def test_upload_returns_job_id(mock_extract, mock_classify, client):
    mock_extract.side_effect = lambda fb, sn: make_rows(sn)
    files = [("files", ("medicao.pdf", b"fakepdfbytes", "application/pdf"))]
    response = await client.post("/upload", files=files)
    assert response.status_code == 200
    data = response.json()
    assert "job_id" in data
    assert len(data["job_id"]) == 12


@patch("app.services.file_processor.is_image_pdf", return_value=False)
@patch("app.services.file_processor.extract_from_pdf")
async def test_upload_job_completes_successfully(mock_extract, mock_classify, client):
    mock_extract.side_effect = lambda fb, sn: make_rows(sn)
    files = [("files", ("medicao.pdf", b"fakepdfbytes", "application/pdf"))]
    response = await client.post("/upload", files=files)
    job_id = response.json()["job_id"]
    status = await _wait_for_job(client, job_id)
    assert status["files"]["medicao.pdf"]["status"] == "completed"


@patch("app.services.file_processor.is_image_pdf", return_value=False)
@patch("app.services.file_processor.extract_from_pdf")
async def test_upload_multiple_files_all_complete(mock_extract, mock_classify, client):
    mock_extract.side_effect = lambda fb, sn: make_rows(sn)
    files = [
        ("files", ("file1.pdf", b"fakepdfbytes", "application/pdf")),
        ("files", ("file2.pdf", b"fakepdfbytes", "application/pdf")),
    ]
    response = await client.post("/upload", files=files)
    job_id = response.json()["job_id"]
    status = await _wait_for_job(client, job_id)
    assert status["files"]["file1.pdf"]["status"] == "completed"
    assert status["files"]["file2.pdf"]["status"] == "completed"


@patch("app.services.file_processor.is_image_pdf", return_value=False)
@patch("app.services.file_processor.extract_from_pdf")
async def test_download_single_file_json(mock_extract, mock_classify, client):
    mock_extract.side_effect = lambda fb, sn: make_rows(sn)
    files = [("files", ("medicao.pdf", b"fakepdfbytes", "application/pdf"))]
    response = await client.post("/upload", files=files)
    job_id = response.json()["job_id"]
    await _wait_for_job(client, job_id)

    dl = await client.get(f"/jobs/{job_id}/download/medicao.pdf")
    assert dl.status_code == 200
    assert "application/json" in dl.headers["content-type"]
    data = json.loads(dl.content)
    assert isinstance(data, list)
    assert len(data) == 2
    assert data[0]["Serviço"] == "56988"


@patch("app.services.file_processor.is_image_pdf", return_value=False)
@patch("app.services.file_processor.extract_from_pdf")
async def test_download_zip(mock_extract, mock_classify, client):
    mock_extract.side_effect = lambda fb, sn: make_rows(sn)
    files = [
        ("files", ("file1.pdf", b"fakepdfbytes", "application/pdf")),
        ("files", ("file2.pdf", b"fakepdfbytes", "application/pdf")),
    ]
    response = await client.post("/upload", files=files)
    job_id = response.json()["job_id"]
    await _wait_for_job(client, job_id)

    dl = await client.get(f"/jobs/{job_id}/download")
    assert dl.status_code == 200
    assert "application/zip" in dl.headers["content-type"]
    assert "resultados.zip" in dl.headers.get("content-disposition", "")


async def test_corrupt_pdf_marks_file_failed(client):
    files = [("files", ("bad.pdf", corrupt_pdf(), "application/pdf"))]
    response = await client.post("/upload", files=files)
    job_id = response.json()["job_id"]
    status = await _wait_for_job(client, job_id)
    assert status["files"]["bad.pdf"]["status"] == "failed"
    assert status["files"]["bad.pdf"]["error"] is not None


@patch("app.services.file_processor.is_image_pdf", return_value=False)
@patch("app.services.file_processor.extract_from_pdf")
async def test_mixed_success_and_failure(mock_extract, mock_classify, client):
    """One good file and one corrupt file — good one succeeds, bad one fails."""
    def fake_extract(file_bytes, source_name):
        if source_name == "good.pdf":
            return make_rows(source_name)
        raise Exception("cannot parse")

    mock_extract.side_effect = fake_extract
    files = [
        ("files", ("good.pdf", b"fakepdfbytes", "application/pdf")),
        ("files", ("bad.pdf", b"fakepdfbytes", "application/pdf")),
    ]
    response = await client.post("/upload", files=files)
    job_id = response.json()["job_id"]
    status = await _wait_for_job(client, job_id)
    assert status["files"]["good.pdf"]["status"] == "completed"
    assert status["files"]["bad.pdf"]["status"] == "failed"
