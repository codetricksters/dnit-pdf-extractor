"""Tests for GET / — the upload UI page."""


async def test_index_returns_200(client):
    response = await client.get("/")
    assert response.status_code == 200


async def test_index_content_type_is_html(client):
    response = await client.get("/")
    assert "text/html" in response.headers["content-type"]


async def test_index_contains_upload_form(client):
    response = await client.get("/")
    body = response.text
    assert "<form" in body
    # The form is submitted by script.js to /upload; an `action` on the tag
    # itself would make the browser navigate away and lose the SSE progress.
    tag = body[body.index("<form"):]
    tag = tag[: tag.index(">")]
    assert "action" not in tag
    assert 'type="file"' in body


async def test_index_file_input_has_multiple(client):
    response = await client.get("/")
    assert "multiple" in response.text


async def test_index_contains_dnit_branding(client):
    response = await client.get("/")
    assert "DNIT" in response.text
