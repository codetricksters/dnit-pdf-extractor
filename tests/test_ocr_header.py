"""Header read from the OCR'd lines of a scanned PDF."""
from app.services.ocr_extractor import _header_from_ocr


def _linha(texto: str) -> list[dict]:
    return [{"text": palavra} for palavra in texto.split()]


def test_header_from_ocr_reads_contract_data_base_and_process():
    linhas = [
        _linha("CONTRATO: 18 00632/2024 - HWN ENGENHARIA LTDA Índices 10 iM K"),
        _linha("Data Base: 01/10/2023 Número do Processo: 50618.000129/2024-13 EMUL 857,397"),
    ]
    assert _header_from_ocr(linhas) == {
        "Contrato": "18 00632/2024 - HWN ENGENHARIA LTDA Índices 10 iM K",
        "Data Base": "01/10/2023",
        "Número do Processo": "50618.000129/2024-13",
    }


def test_header_from_ocr_omits_what_was_not_read():
    assert _header_from_ocr([_linha("RESUMO DA MEDIÇÃO")]) == {}


# --- filtro de índices, continuação, orientação e conferência de subtotais ---

from unittest.mock import patch

from PIL import Image

from app.services import ocr_extractor as O


def test_indices_row_does_not_match_conservacao_item():
    item = _linha("90105 CONSERVAÇÃO ROTINEIRA - DESEMPENHO Não MES 41.852,7300")
    assert not O._is_indices_row(item)
    assert O._is_indices_row(_linha("CONSER 423,349 443,242 0,0470"))


def test_continuation_row_accepts_wrapped_description_of_any_length():
    cells = ["", "COM SERRA CORTA PISO"] + [""] * 9
    assert O._is_continuation_row(_linha("COM SERRA CORTA PISO"), cells)
    assert not O._is_continuation_row([], ["", "TEXTO", "Não"] + [""] * 8)
    assert not O._is_continuation_row([], ["54394", "TEXTO"] + [""] * 9)


def test_orientation_uses_osd_rotation():
    imagem = Image.new("RGB", (10, 10))
    osd = {"rotate": 90, "orientation_conf": 8.0}
    with patch.object(O, "_tesseract_available", return_value=True), \
         patch("pytesseract.image_to_osd", return_value=osd):
        # OSD asks for 90° clockwise = 270° in PIL's counter-clockwise terms
        assert O._detect_orientation(imagem) == 270


def test_orientation_ignores_low_confidence_osd():
    imagem = Image.new("RGB", (10, 10))
    osd = {"rotate": 180, "orientation_conf": 0.5}
    with patch.object(O, "_tesseract_available", return_value=True), \
         patch("pytesseract.image_to_osd", return_value=osd), \
         patch.object(O, "_ocr_image", return_value=[]):
        assert O._detect_orientation(imagem) == 0


def _reg(servico, acum=0.0, liq=0.0, reaj=0.0):
    return {"Serviço": servico, "Valor a PI Acumulado": acum,
            "Valor a PI Líquido": liq, "Reajustamento Líquido": reaj}


def test_conferir_subtotais_flags_section_that_does_not_add_up(caplog):
    registros = [
        _reg("49299", 10, 10, 1), _reg("SUBTOTAL", 10, 10, 1),
        _reg("49321", 8.0, 0.0, 1), _reg("51054", 5, 5, 1), _reg("SUBTOTAL", 13, 13, 2),
    ]
    assert O._conferir_subtotais(registros, "x.pdf") == ["49321, 51054"]
    assert "49321, 51054" in caplog.text
