"""Unit tests for app/services/extractor.py."""
from unittest.mock import patch

import pytest
from app.services.exceptions import ExtractionError

from app.services.extractor import (
    EXPECTED_COLUMNS,
    _clean_cell,
    _is_header_row,
    _is_indices_row,
    _is_new_record,
    _map_row,
    _normalize_header,
    _row_is_dangling,
    extract_from_pdf,
    parse_br_number,
)

from .conftest import SAMPLE_TABLE, make_pdfplumber_mock
from .pdf_factory import corrupt_pdf, no_table_pdf


# --- parse_br_number ---

def test_parse_br_number_basic():
    assert parse_br_number("1.234,56") == pytest.approx(1234.56)


def test_parse_br_number_large():
    assert parse_br_number("1.872.240,49") == pytest.approx(1872240.49)


def test_parse_br_number_integer_like():
    assert parse_br_number("100,00") == pytest.approx(100.0)


# --- _clean_cell ---

def test_clean_cell_strips_whitespace():
    assert _clean_cell("  hello  ") == "hello"


def test_clean_cell_replaces_newline():
    assert _clean_cell("line1\nline2") == "line1 line2"


def test_clean_cell_none_returns_empty():
    assert _clean_cell(None) == ""


# --- _is_indices_row ---

def test_is_indices_row_detects_adloc():
    assert _is_indices_row(["ADLOC", "1,2345", None])


def test_is_indices_row_detects_conser():
    assert _is_indices_row([None, "CONSER", "0,9876"])


def test_is_indices_row_false_for_normal_row():
    assert not _is_indices_row(["56988", "Pavimentação", "1234567"])


# --- _is_header_row ---

def test_is_header_row_detects_servico():
    assert _is_header_row(["Serviço", "Descrição", "Código SICRO"])


def test_is_header_row_detects_partial_match():
    assert _is_header_row(["Código", "Unidade", "Valor"])


def test_is_header_row_false_for_data_row():
    assert not _is_header_row(["56988", "Some description", "100,00"])


# --- _is_new_record ---

def test_is_new_record_numeric_code():
    assert _is_new_record("56988")


def test_is_new_record_subtotal_marker():
    assert _is_new_record("SUBTOTAL")
    assert _is_new_record("subtotal")


def test_is_new_record_false_for_empty():
    assert not _is_new_record("")
    assert not _is_new_record(None)


def test_is_new_record_false_for_short_number():
    assert not _is_new_record("123")


# --- _row_is_dangling ---

def test_row_is_dangling_only_descricao():
    row = {col: "" for col in EXPECTED_COLUMNS}
    row["Descrição"] = "continuation text"
    assert _row_is_dangling(row)


def test_row_is_dangling_false_when_has_other_values():
    row = {col: "" for col in EXPECTED_COLUMNS}
    row["Descrição"] = "some text"
    row["Serviço"] = "56988"
    assert not _row_is_dangling(row)


# --- _normalize_header ---

def test_normalize_header_maps_known_columns():
    raw = ["Serviço", "Descrição", "Código SICRO", "Unidade"]
    result = _normalize_header(raw)
    assert result[0] == "Serviço"
    assert result[1] == "Descrição"
    assert result[2] == "Código SICRO"


def test_normalize_header_passes_unknown_through():
    raw = ["Unknown Column", None]
    result = _normalize_header(raw)
    assert result[0] == "Unknown Column"


# --- _map_row ---

def test_map_row_fills_known_columns():
    header = ["Serviço", "Descrição", "Código SICRO"]
    raw = ["56988", "Pavimentação asfáltica", "1234567"]
    result = _map_row(raw, header)
    assert result["Serviço"] == "56988"
    assert result["Descrição"] == "Pavimentação asfáltica"
    assert result["Código SICRO"] == "1234567"


def test_map_row_defaults_missing_columns_to_empty():
    header = ["Serviço"]
    raw = ["56988"]
    result = _map_row(raw, header)
    assert result["Descrição"] == ""
    assert result["Unidade"] == ""


# --- extract_from_pdf (error cases use real corrupt/empty PDFs) ---

def test_extract_raises_on_corrupt_pdf():
    with pytest.raises(ExtractionError) as exc_info:
        extract_from_pdf(corrupt_pdf(), "corrupt.pdf")
    assert "corrupt.pdf" in str(exc_info.value)


def test_extract_raises_when_no_table_found():
    with pytest.raises(ExtractionError):
        extract_from_pdf(no_table_pdf(), "empty.pdf")


# --- extract_from_pdf (happy path — mock pdfplumber) ---

def test_extract_returns_list_of_dicts():
    mock_pdf = make_pdfplumber_mock([[SAMPLE_TABLE]])
    with patch("app.services.extractor.pdfplumber.open", return_value=mock_pdf):
        result = extract_from_pdf(b"fakebytes", "medicao.pdf")
    assert isinstance(result, list)
    assert len(result) == 2


def test_extract_each_row_has_source_file():
    mock_pdf = make_pdfplumber_mock([[SAMPLE_TABLE]])
    with patch("app.services.extractor.pdfplumber.open", return_value=mock_pdf):
        result = extract_from_pdf(b"fakebytes", "medicao.pdf")
    for row in result:
        assert row.get("Source_File") == "medicao.pdf"


def test_extract_rows_have_expected_columns():
    mock_pdf = make_pdfplumber_mock([[SAMPLE_TABLE]])
    with patch("app.services.extractor.pdfplumber.open", return_value=mock_pdf):
        result = extract_from_pdf(b"fakebytes", "medicao.pdf")
    for row in result:
        for col in EXPECTED_COLUMNS:
            assert col in row


def test_extract_dangling_row_merged_into_previous():
    """A row with only Descrição text should be appended to the preceding record."""
    table = [
        SAMPLE_TABLE[0],
        ["56988", "First part", "", "", "", "", "", "", "", "", ""],
        ["", "continuation", "", "", "", "", "", "", "", "", ""],
    ]
    mock_pdf = make_pdfplumber_mock([[table]])
    with patch("app.services.extractor.pdfplumber.open", return_value=mock_pdf):
        result = extract_from_pdf(b"fakebytes", "merge.pdf")
    assert len(result) == 1
    assert "continuation" in result[0]["Descrição"]


def test_extract_indices_rows_are_skipped():
    table = [
        SAMPLE_TABLE[0],
        SAMPLE_TABLE[1],
        ["ADLOC", "1,2345", "", "", "", "", "", "", "", "", ""],
    ]
    mock_pdf = make_pdfplumber_mock([[table]])
    with patch("app.services.extractor.pdfplumber.open", return_value=mock_pdf):
        result = extract_from_pdf(b"fakebytes", "test.pdf")
    services = [r["Serviço"] for r in result]
    assert "ADLOC" not in services


def test_extract_repeated_header_rows_are_ignored():
    """Repeated header rows on page 2 should not produce duplicate records."""
    table_page2 = [
        SAMPLE_TABLE[0],  # repeated header
        SAMPLE_TABLE[2],
    ]
    mock_pdf = make_pdfplumber_mock([[SAMPLE_TABLE], [table_page2]])
    with patch("app.services.extractor.pdfplumber.open", return_value=mock_pdf):
        result = extract_from_pdf(b"fakebytes", "multi.pdf")
    # 2 from page 1 + 1 from page 2 (header skipped) = 3
    assert len(result) == 3
