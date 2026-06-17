"""Tests for GET / — the upload UI page."""


def test_index_returns_200(client):
    response = client.get("/")
    assert response.status_code == 200


def test_index_content_type_is_html(client):
    response = client.get("/")
    assert "text/html" in response.headers["content-type"]


def test_index_contains_upload_form(client):
    response = client.get("/")
    body = response.text
    assert "<form" in body
    assert 'action' not in body or '/upload' in body
    assert 'type="file"' in body


def test_index_file_input_has_multiple(client):
    response = client.get("/")
    assert "multiple" in response.text


def test_index_contains_dnit_branding(client):
    response = client.get("/")
    assert "DNIT" in response.text
