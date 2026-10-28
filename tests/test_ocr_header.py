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
