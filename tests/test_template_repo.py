"""Template management: validation on upload, activation, deletion rules."""

import io
from pathlib import Path

import openpyxl
import pytest

from app.services import template_repo
from app.services.reequilibrio_layout import ABA
from app.services.xlsx_drawings import TemplateInvalido

VALIDO = Path("app/templates_xlsx/reequilibrio_template.xlsx")


@pytest.fixture
def valido() -> bytes:
    return VALIDO.read_bytes()


def _alterado(conteudo: bytes, mudanca) -> bytes:
    """Re-save the template with *mudanca* applied, losing the equation.

    Saving through openpyxl is itself what strips the text box, so anything
    produced here is invalid for that reason too; each test asserts on the
    message of the check it is exercising, which runs before the equation check.
    """
    wb = openpyxl.load_workbook(io.BytesIO(conteudo))
    mudanca(wb)
    saida = io.BytesIO()
    wb.save(saida)
    return saida.getvalue()


async def test_semente_e_instalada_e_fica_ativa():
    template_repo.garantir_semente()
    atual = template_repo.ativo()
    assert atual is not None
    assert atual["nome"] == "reequilibrio_template.xlsx"
    assert len(template_repo.listar()) == 1


async def test_semente_nao_e_reinstalada_e_nao_desfaz_escolha_do_usuario(valido):
    template_repo.garantir_semente()
    outro = template_repo.salvar("outro.xlsx", valido, ativar=True)

    template_repo.garantir_semente()  # reinício da aplicação

    assert len(template_repo.listar()) == 2
    assert template_repo.ativo()["id"] == outro


async def test_arquivo_que_nao_e_xlsx_e_recusado():
    with pytest.raises(TemplateInvalido) as erro:
        template_repo.salvar("qualquer.xlsx", b"nao sou uma planilha")
    assert ".xlsx" in str(erro.value)


async def test_aba_com_outro_nome_e_recusada(valido):
    def renomear(wb):
        wb[ABA].title = "Planilha1"

    with pytest.raises(TemplateInvalido) as erro:
        template_repo.salvar("x.xlsx", _alterado(valido, renomear))
    assert ABA in str(erro.value)


async def test_cabecalho_deslocado_e_recusado(valido):
    """A shifted B3:C13 block would put the contract values on wrong rows."""

    def deslocar(wb):
        wb[ABA].insert_rows(3)

    with pytest.raises(TemplateInvalido) as erro:
        template_repo.salvar("x.xlsx", _alterado(valido, deslocar))
    assert "B3" in str(erro.value) or "B12" in str(erro.value)


async def test_cabecalho_da_tabela_diferente_e_recusado(valido):
    def trocar(wb):
        wb[ABA]["D14"] = "VALOR QUALQUER"

    with pytest.raises(TemplateInvalido) as erro:
        template_repo.salvar("x.xlsx", _alterado(valido, trocar))
    assert "D14" in str(erro.value)


async def test_sem_linhas_modelo_e_recusado(valido):
    """Deleting the model band in Excel takes its merges with it."""

    def apagar(wb):
        wb[ABA].merged_cells.ranges.remove(
            next(m for m in wb[ABA].merged_cells.ranges if str(m) == "B17:J17")
        )
        wb[ABA].delete_rows(17, 10)

    with pytest.raises(TemplateInvalido) as erro:
        template_repo.salvar("x.xlsx", _alterado(valido, apagar))
    assert "modelo" in str(erro.value)


async def test_sem_memoria_de_calculo_e_recusado(valido):
    """openpyxl strips text boxes, so a template round-tripped through it fails."""

    def nada(wb):
        return None

    with pytest.raises(TemplateInvalido) as erro:
        template_repo.salvar("x.xlsx", _alterado(valido, nada))
    assert "memória de cálculo" in str(erro.value)


async def test_ativar_troca_o_template_em_uso(valido):
    primeiro = template_repo.salvar("um.xlsx", valido, ativar=True)
    segundo = template_repo.salvar("dois.xlsx", valido, ativar=True)
    assert template_repo.ativo()["id"] == segundo

    assert template_repo.ativar(primeiro) is True
    assert template_repo.ativo()["id"] == primeiro
    # Exactly one active at a time, enforced by the partial unique index.
    assert [t["ativo"] for t in template_repo.listar()].count(True) == 1


async def test_template_ativo_nao_pode_ser_excluido(valido):
    template_repo.salvar("um.xlsx", valido, ativar=True)
    ativo_id = template_repo.salvar("dois.xlsx", valido, ativar=True)

    with pytest.raises(TemplateInvalido) as erro:
        template_repo.excluir(ativo_id)
    assert "ativo" in str(erro.value)
    assert len(template_repo.listar()) == 2


async def test_sempre_resta_ao_menos_um_template(valido):
    unico = template_repo.salvar("um.xlsx", valido, ativar=False)
    with pytest.raises(TemplateInvalido) as erro:
        template_repo.excluir(unico)
    assert "ao menos um" in str(erro.value)


async def test_excluir_inativo_nao_afeta_a_exportacao(valido):
    inativo = template_repo.salvar("velho.xlsx", valido, ativar=False)
    template_repo.salvar("novo.xlsx", valido, ativar=True)

    template_repo.excluir(inativo)

    assert [t["id"] for t in template_repo.listar()] != [inativo]
    assert template_repo.conteudo_ativo() == valido


async def test_conteudo_ativo_sem_template_ativo_explica(valido):
    template_repo.salvar("um.xlsx", valido, ativar=False)
    with pytest.raises(TemplateInvalido) as erro:
        template_repo.conteudo_ativo()
    assert "Ative" in str(erro.value)


async def test_sha256_permite_reconhecer_o_mesmo_arquivo(valido):
    import hashlib

    template_repo.salvar("um.xlsx", valido)
    assert template_repo.listar()[0]["sha256"] == hashlib.sha256(valido).hexdigest()
