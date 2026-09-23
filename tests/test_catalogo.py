"""Catalogue: code → product mapping, family suggestion and pending review."""

import pytest

from app.services import catalogo
from app.services.delta_p import FAMILIA_CAP, FAMILIA_EMULSOES


@pytest.mark.parametrize(
    "descricao,esperado",
    [
        ("AQUISIÇÃO DE CIMENTO ASFÁLTICO CAP 50/70", FAMILIA_CAP),
        ("AQUISICAO DE CAP 50/70", FAMILIA_CAP),  # OCR without accents
        ("AQUISIÇÃO DE EMULSÃO ASFÁLTICA RR-1C", FAMILIA_EMULSOES),
        ("AQUISIÇÃO DE EMULSÃO ASFÁLTICA PARA IMPRIMAÇÃO", FAMILIA_EMULSOES),
        ("AQUISIÇÃO RC-1C-E P/ MICROREVESTIMENTO", FAMILIA_EMULSOES),
        ("AQUISIÇÃO DE EMULSÃO ASFALTICA - RR-2C - TSD", FAMILIA_EMULSOES),
        ("AQUISIÇÃO DE EAI PARA IMPRIMAÇÃO", FAMILIA_EMULSOES),
        # Unrelated services must not be guessed into a family.
        ("ESCAVAÇÃO, CARGA E TRANSPORTE DE MATERIAL", None),
        ("DRENAGEM PROFUNDA", None),
        ("", None),
    ],
)
async def test_sugerir_familia(descricao, esperado):
    assert catalogo.sugerir_familia(descricao) == esperado


async def test_codigos_semeados_estao_confirmados():
    """The nine codes seen in the already-extracted results ship confirmed."""
    confirmados = catalogo.codigos_confirmados()
    assert confirmados["8300980"]["descricao_export"] == "AQUISIÇÃO DE CAP 50/70"
    assert confirmados["8300980"]["familia"] == FAMILIA_CAP
    # Several codes map onto the same product, with the export description.
    assert (
        confirmados["60112"]["produto_id"] == confirmados["92704"]["produto_id"]
    )
    assert confirmados["29083"]["familia"] == FAMILIA_EMULSOES
    assert len(confirmados) == 9


async def test_codigo_novo_gera_pendencia_com_familia_sugerida():
    pendencia = catalogo.registrar_pendencia(
        "777123", "AQUISIÇÃO DE EMULSÃO ASFÁLTICA RR-2C - TSD"
    )
    assert pendencia["familia"] == FAMILIA_EMULSOES
    assert pendencia["confirmado"] is False
    assert "777123" in {p["codigo_servico"] for p in catalogo.listar_pendencias()}
    # Excluded from the calculation until reviewed.
    assert "777123" not in catalogo.codigos_confirmados()


async def test_codigo_sem_familia_reconhecivel_nao_cria_produto():
    assert catalogo.registrar_pendencia("777124", "DRENAGEM PROFUNDA") is None
    assert catalogo.buscar_por_codigo("777124") is None


async def test_pendencia_nao_sobrescreve_codigo_confirmado():
    """A confirmed mapping is the user's decision and must survive reprocessing."""
    antes = catalogo.buscar_por_codigo("8300980")
    catalogo.registrar_pendencia("8300980", "AQUISIÇÃO DE EMULSÃO ASFÁLTICA RR-1C")
    depois = catalogo.buscar_por_codigo("8300980")
    assert depois["produto_id"] == antes["produto_id"]
    assert depois["familia"] == FAMILIA_CAP
    assert depois["confirmado"] is True
    # The PDF description is still refreshed, for diagnosis.
    assert depois["descricao_pdf"] == "AQUISIÇÃO DE EMULSÃO ASFÁLTICA RR-1C"


async def test_confirmar_codigo_o_traz_para_o_calculo():
    catalogo.registrar_pendencia("777125", "AQUISIÇÃO DE EMULSÃO ASFÁLTICA RR-1C")
    assert "777125" not in catalogo.codigos_confirmados()
    assert catalogo.confirmar_codigo("777125") is True
    assert "777125" in catalogo.codigos_confirmados()


async def test_reapontar_codigo_para_outro_produto():
    produtos = {p["descricao_export"]: p["id"] for p in catalogo.listar_produtos()}
    destino = produtos["AQUISIÇÃO DE EMULSÃO ASFÁLTICA RR-1C"]
    catalogo.registrar_codigo("8300980", destino)
    assert catalogo.buscar_por_codigo("8300980")["produto_id"] == destino


async def test_criar_produto_recusa_familia_invalida():
    with pytest.raises(ValueError):
        catalogo.criar_produto("AQUISIÇÃO DE BRITA", "BRITA")
