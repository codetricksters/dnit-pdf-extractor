"""Contract registration, header normalisation and measurement persistence."""

from datetime import date
from decimal import Decimal

import pytest

from app.services import catalogo, contratos_repo, medicoes_repo
from app.services.delta_p import FAMILIA_CAP, FAMILIA_EMULSOES

# Exactly as it comes out of the PDFs: the number, the contractor and the
# leftovers of the índices side-table, all in one field.
CONTRATO_BRUTO = (
    "06 00134/2022 - HWN ENGENHARIA LTDA Índices I0 I1 K Índices I0 I1 K"
)

HEADER = {
    "Contrato": CONTRATO_BRUTO,
    "Data Base": "01/01/2021",
    "Período Líquido": "01/03/2023 - 31/03/2023",
    "Número do Processo": "50606.000509/2021-44",
}


def _linha(codigo, descricao, valor_pi, fator, periodo="01/03/2023 - 31/03/2023",
           source="3ª MP.pdf"):
    return {
        "Serviço": codigo,
        "Descrição": descricao,
        "Valor a PI Líquido": valor_pi,
        "Fator": fator,
        "Período Líquido": periodo,
        "Source_File": source,
    }


@pytest.mark.parametrize(
    "bruto,esperado",
    [
        (CONTRATO_BRUTO, "06 00134/2022"),
        ("15 00716/2022 - HWN ENGENHARIA LTDA Índices I0 I1 K", "15 00716/2022"),
        ("15 00831/2024 - OUTRA EMPRESA S/A", "15 00831/2024"),
        ("sem número aqui", None),
        ("", None),
    ],
)
async def test_normalizar_numero(bruto, esperado):
    assert contratos_repo.normalizar_numero(bruto) == esperado


async def test_extrair_contratada_para_o_cadastro():
    assert contratos_repo.extrair_contratada(CONTRATO_BRUTO) == "HWN ENGENHARIA LTDA"


@pytest.mark.parametrize(
    "periodo,esperado",
    [
        ("01/09/2025 - 30/09/2025", date(2025, 9, 1)),
        # Periods that start mid-month still belong to that month.
        ("16/12/2024 - 31/12/2024", date(2024, 12, 1)),
        ("03/03/2023 - 31/03/2023", date(2023, 3, 1)),
        ("", None),
        (None, None),
    ],
)
async def test_mes_da_medicao(periodo, esperado):
    assert contratos_repo.mes_da_medicao(periodo) == esperado


async def test_registrar_do_pdf_usa_o_numero_normalizado_como_chave():
    contrato_id = contratos_repo.registrar_do_pdf(HEADER)
    contrato = contratos_repo.buscar("06 00134/2022")
    assert contrato["id"] == contrato_id
    assert contrato["data_base"] == date(2021, 1, 1)
    assert contrato["numero_processo"] == "50606.000509/2021-44"
    assert contrato["contratada"] == "HWN ENGENHARIA LTDA"


async def test_header_sem_numero_nao_cria_contrato():
    assert contratos_repo.registrar_do_pdf({"Contrato": "ilegível"}) is None
    assert contratos_repo.listar() == []


async def test_reprocessar_nao_sobrescreve_o_cadastro_do_usuario():
    """The user's corrections must survive re-running the same PDF."""
    contratos_repo.registrar_do_pdf(HEADER)
    contratos_repo.salvar_cadastro(
        "06 00134/2022",
        {
            "contratada": "HWN ENGENHARIA LTDA (razão corrigida)",
            "rodovia": "BR-316/MA",
            "extensao": Decimal("188.7"),
        },
    )
    contratos_repo.registrar_do_pdf(HEADER)

    contrato = contratos_repo.buscar("06 00134/2022")
    assert contrato["contratada"] == "HWN ENGENHARIA LTDA (razão corrigida)"
    assert contrato["rodovia"] == "BR-316/MA"
    assert len(contratos_repo.listar()) == 1


async def test_extensao_aceita_o_numero_como_o_usuario_digita():
    """The form is a text box labelled "Extensão (km)" over a NUMERIC column.

    Typing ``45,7`` used to abort the whole save with ``invalid input syntax for
    type numeric``, losing the other six fields with it.
    """
    contratos_repo.registrar_do_pdf(HEADER)
    contratos_repo.salvar_cadastro(
        "06 00134/2022", {"extensao": "45,7", "rodovia": "BR-116/PB"}
    )

    contrato = contratos_repo.buscar("06 00134/2022")
    assert contrato["extensao"] == Decimal("45.7")
    assert contrato["rodovia"] == "BR-116/PB"


async def test_extensao_sem_digitos_fica_nula_e_nao_perde_o_resto():
    contratos_repo.registrar_do_pdf(HEADER)
    contratos_repo.salvar_cadastro(
        "06 00134/2022", {"extensao": "a definir", "rodovia": "BR-116/PB"}
    )

    contrato = contratos_repo.buscar("06 00134/2022")
    assert contrato["extensao"] is None
    assert contrato["rodovia"] == "BR-116/PB"
    # And the export is told, rather than printing a blank as if it were fine.
    assert "extensao" in contratos_repo.campos_faltantes(contrato)


async def test_cadastro_nao_pode_alterar_a_data_base():
    """data_base sets the ΔP denominator, so it stays PDF-owned."""
    contratos_repo.registrar_do_pdf(HEADER)
    contratos_repo.salvar_cadastro(
        "06 00134/2022", {"data_base": date(2019, 1, 1), "rodovia": "BR-135/MA"}
    )
    contrato = contratos_repo.buscar("06 00134/2022")
    assert contrato["data_base"] == date(2021, 1, 1)
    assert contrato["rodovia"] == "BR-135/MA"


async def test_regiao_por_familia_e_independente():
    contratos_repo.registrar_do_pdf(HEADER)
    contratos_repo.definir_regiao("06 00134/2022", FAMILIA_CAP, "Nordeste")
    contratos_repo.definir_regiao("06 00134/2022", FAMILIA_EMULSOES, "Sudeste")
    regioes = contratos_repo.buscar("06 00134/2022")["regioes"]
    assert regioes == {FAMILIA_CAP: "Nordeste", FAMILIA_EMULSOES: "Sudeste"}

    contratos_repo.definir_regiao("06 00134/2022", FAMILIA_EMULSOES, "Sul")
    assert contratos_repo.buscar("06 00134/2022")["regioes"][FAMILIA_EMULSOES] == "Sul"


async def test_campos_faltantes_lista_o_que_falta_para_exportar():
    contratos_repo.registrar_do_pdf(HEADER)
    faltam = contratos_repo.campos_faltantes(contratos_repo.buscar("06 00134/2022"))
    assert "rodovia" in faltam and "edital" in faltam
    assert "regiao_cap" in faltam and "regiao_emulsoes" in faltam
    # Came from the PDF, so neither is missing.
    assert "contratada" not in faltam and "data_base" not in faltam


async def test_gravar_itens_e_idempotente():
    contrato_id = contratos_repo.registrar_do_pdf(HEADER)
    linhas = [
        _linha("8300980", "AQUISIÇÃO DE CIMENTO ASFÁLTICO CAP 50/70", 100000.0, 1.0512),
        _linha("29083", "AQUISIÇÃO DE EMULSÃO ASFÁLTICA RR-1C", 50000.0, 1.0512),
    ]
    primeiro = medicoes_repo.gravar_itens(contrato_id, linhas, job_id="job1")
    assert primeiro["itens"] == 2

    segundo = medicoes_repo.gravar_itens(contrato_id, linhas, job_id="job2")
    assert segundo["itens"] == 2
    assert len(medicoes_repo.itens_para_export(contrato_id)) == 2


async def test_linhas_sem_codigo_de_servico_sao_ignoradas():
    contrato_id = contratos_repo.registrar_do_pdf(HEADER)
    resumo = medicoes_repo.gravar_itens(
        contrato_id,
        [
            _linha("SUBTOTAL", "", 999.0, 1.0),
            _linha("", "texto solto", 1.0, 1.0),
            _linha("8300980", "AQUISIÇÃO DE CAP 50/70", 10.0, 1.0),
        ],
    )
    assert resumo["itens"] == 1


async def test_item_sem_mes_e_descartado():
    """Without a measurement month there is no line to place in the spreadsheet."""
    contrato_id = contratos_repo.registrar_do_pdf(HEADER)
    resumo = medicoes_repo.gravar_itens(
        contrato_id, [_linha("8300980", "AQUISIÇÃO DE CAP 50/70", 10.0, 1.0, periodo="")]
    )
    assert resumo["itens"] == 0


async def test_codigo_nao_confirmado_fica_fora_do_export():
    contrato_id = contratos_repo.registrar_do_pdf(HEADER)
    resumo = medicoes_repo.gravar_itens(
        contrato_id,
        [
            _linha("8300980", "AQUISIÇÃO DE CAP 50/70", 100.0, 1.0),
            _linha("777126", "AQUISIÇÃO DE EMULSÃO ASFÁLTICA RR-2C - TSD", 200.0, 1.0),
        ],
    )
    assert resumo["pendencias"] == ["777126"]

    codigos = {i["codigo_servico"] for i in medicoes_repo.itens_para_export(contrato_id)}
    assert codigos == {"8300980"}

    # Confirming brings it in without reprocessing the PDF.
    catalogo.confirmar_codigo("777126")
    codigos = {i["codigo_servico"] for i in medicoes_repo.itens_para_export(contrato_id)}
    assert codigos == {"8300980", "777126"}


async def test_servico_alheio_nao_gera_pendencia():
    """Terraplenagem and friends must not flood the review list."""
    contrato_id = contratos_repo.registrar_do_pdf(HEADER)
    resumo = medicoes_repo.gravar_itens(
        contrato_id, [_linha("54393", "ESCAVAÇÃO, CARGA E TRANSPORTE", 500.0, 1.0)]
    )
    assert resumo["itens"] == 1  # the fact is stored
    assert resumo["pendencias"] == []  # but nothing to review
    assert medicoes_repo.itens_para_export(contrato_id) == []


async def test_itens_para_export_vem_agrupado_por_familia_e_produto():
    contrato_id = contratos_repo.registrar_do_pdf(HEADER)
    medicoes_repo.gravar_itens(
        contrato_id,
        [
            _linha("29083", "RR-1C", 1.0, 1.0, periodo="01/04/2023 - 30/04/2023"),
            _linha("8300980", "CAP", 2.0, 1.0, periodo="01/04/2023 - 30/04/2023"),
            _linha("8300980", "CAP", 3.0, 1.0, periodo="01/03/2023 - 31/03/2023"),
        ],
    )
    itens = medicoes_repo.itens_para_export(contrato_id)
    assert [(i["familia"], i["mes_medicao"].month) for i in itens] == [
        (FAMILIA_CAP, 3),
        (FAMILIA_CAP, 4),
        (FAMILIA_EMULSOES, 4),
    ]
    assert itens[0]["descricao_export"] == "AQUISIÇÃO DE CAP 50/70"
    assert itens[0]["valor_pi"] == Decimal("3")


async def test_valores_chegam_ao_banco_como_decimal_exato():
    """Money is NUMERIC end to end, so the user's audit finds no float drift."""
    contrato_id = contratos_repo.registrar_do_pdf(HEADER)
    medicoes_repo.gravar_itens(
        contrato_id, [_linha("8300980", "CAP", 1872240.49, 1.0512)]
    )
    item = medicoes_repo.itens_para_export(contrato_id)[0]
    assert item["valor_pi"] == Decimal("1872240.49")
    assert item["fator"] == Decimal("1.0512")


async def test_meses_do_contrato():
    contrato_id = contratos_repo.registrar_do_pdf(HEADER)
    medicoes_repo.gravar_itens(
        contrato_id,
        [
            _linha("8300980", "CAP", 1.0, 1.0, periodo="01/04/2023 - 30/04/2023"),
            _linha("8300980", "CAP", 2.0, 1.0, periodo="01/03/2023 - 31/03/2023"),
        ],
    )
    assert medicoes_repo.meses_do_contrato(contrato_id) == [
        date(2023, 3, 1),
        date(2023, 4, 1),
    ]
