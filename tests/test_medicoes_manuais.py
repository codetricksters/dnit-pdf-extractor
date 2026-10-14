"""Registros de medição editados à mão sobrevivem ao reprocessamento do PDF."""

from datetime import date
from decimal import Decimal

import pytest

from app.db import acquire_sync
from app.services import contratos_repo, indices_repo, medicoes_repo
from app.services.medicoes_repo import MedicaoInvalida
from tests.indices_factory import semana

HEADER = {"Contrato": "15 00716/2022 - HWN ENGENHARIA LTDA", "Data Base": "01/01/2022"}
FEV = "01/02/2023 - 28/02/2023"


def _linha(codigo="60112", valor=412300.0, fator=0.148, arquivo="1ª MP.pdf"):
    return {"Serviço": codigo, "Descrição": "Fornecimento de CAP 50/70",
            "Valor a PI Líquido": valor, "Fator": fator, "Período Líquido": FEV,
            "Source_File": arquivo}


def _sql(sql, *params):
    with acquire_sync() as conn:
        conn.execute(sql, params)


def test_reprocessar_nao_sobrescreve_registro_editado():
    contrato_id = contratos_repo.registrar_do_pdf(HEADER)
    medicoes_repo.gravar_itens(contrato_id, [_linha()])
    _sql("UPDATE medicao_item SET valor_pi = 1, origem = 'editado'")

    assert medicoes_repo.gravar_itens(contrato_id, [_linha()]) == 1

    [item] = medicoes_repo.listar_itens(contrato_id)
    assert item["valor_pi"] == 1 and item["origem"] == "editado"


def test_reprocessar_nao_ressuscita_registro_excluido():
    contrato_id = contratos_repo.registrar_do_pdf(HEADER)
    medicoes_repo.gravar_itens(contrato_id, [_linha()])
    _sql("UPDATE medicao_item SET excluido = true")

    medicoes_repo.gravar_itens(contrato_id, [_linha()])

    assert medicoes_repo.listar_itens(contrato_id) == []
    assert medicoes_repo.itens_para_export(contrato_id) == []
    assert medicoes_repo.meses_do_contrato(contrato_id) == []
    [resumo] = contratos_repo.listar()
    assert resumo["itens"] == 0 and resumo["medicoes"] == 0


def test_reprocessar_registro_do_pdf_continua_atualizando():
    contrato_id = contratos_repo.registrar_do_pdf(HEADER)
    medicoes_repo.gravar_itens(contrato_id, [_linha(valor=10.0)])
    medicoes_repo.gravar_itens(contrato_id, [_linha(valor=20.0)])
    [item] = medicoes_repo.listar_itens(contrato_id)
    assert item["valor_pi"] == 20 and item["origem"] == "pdf"
    assert item["regiao_cap"] is None and item["regiao_emulsoes"] is None


def _regioes():
    indices_repo.gravar_precos_anp(
        [semana(date(2023, 1, 9), "3.28568", regiao="Nordeste"),
         semana(date(2023, 1, 9), "3.45", regiao="Sul")]
    )


def _novo(**extra):
    return {"mes": "2023-02", "codigo": "60112", "descricao_pdf": "CAP manual",
            "valor_pi": "100.00", "fator": "0.148", **extra}


def test_incluir_registro_manual():
    _regioes()
    contrato_id = contratos_repo.registrar_do_pdf(HEADER)
    item_id = medicoes_repo.incluir_item(contrato_id, _novo(regiao_cap="SUL"))
    item = medicoes_repo.buscar_item(contrato_id, item_id)
    assert item["origem"] == "manual" and item["arquivo"] == "manual"
    assert item["mes"] == date(2023, 2, 1) and item["valor_pi"] == Decimal("100.00")
    assert item["regiao_cap"] == "Sul"  # grafia do arquivo da ANP


def test_dois_manuais_do_mesmo_codigo_e_mes_coexistem():
    contrato_id = contratos_repo.registrar_do_pdf(HEADER)
    medicoes_repo.incluir_item(contrato_id, _novo())
    medicoes_repo.incluir_item(contrato_id, _novo())
    assert len(medicoes_repo.listar_itens(contrato_id)) == 2


def test_incluir_em_contrato_inexistente():
    assert medicoes_repo.incluir_item(999, _novo()) is None


@pytest.mark.parametrize("dados, trecho", [
    ({"codigo": "12"}, "codigo"),
    ({"mes": "2023-13"}, "mes"),
    ({"valor_pi": "abc"}, "valor_pi"),
    ({"fator": None}, "fator"),
    ({"regiao_cap": "Marte"}, "regiao_cap"),
])
def test_incluir_recusa_campo_invalido(dados, trecho):
    _regioes()
    contrato_id = contratos_repo.registrar_do_pdf(HEADER)
    with pytest.raises(MedicaoInvalida, match=trecho):
        medicoes_repo.incluir_item(contrato_id, _novo(**dados))
    assert medicoes_repo.listar_itens(contrato_id) == []


def test_editar_registro_do_pdf_marca_editado_e_fixa_regiao():
    _regioes()
    contrato_id = contratos_repo.registrar_do_pdf(HEADER)
    medicoes_repo.gravar_itens(contrato_id, [_linha()])
    [item] = medicoes_repo.listar_itens(contrato_id)

    assert medicoes_repo.atualizar_item(
        contrato_id, item["id"], {"valor_pi": "5.00", "regiao_emulsoes": "nordeste"}
    )
    item = medicoes_repo.buscar_item(contrato_id, item["id"])
    assert item["origem"] == "editado" and item["valor_pi"] == Decimal("5.00")
    assert item["regiao_emulsoes"] == "Nordeste"

    medicoes_repo.atualizar_item(contrato_id, item["id"], {"regiao_emulsoes": ""})
    assert medicoes_repo.buscar_item(contrato_id, item["id"])["regiao_emulsoes"] is None


def test_registro_do_pdf_nao_muda_codigo_nem_mes():
    contrato_id = contratos_repo.registrar_do_pdf(HEADER)
    medicoes_repo.gravar_itens(contrato_id, [_linha()])
    [item] = medicoes_repo.listar_itens(contrato_id)
    with pytest.raises(MedicaoInvalida, match="código e mês"):
        medicoes_repo.atualizar_item(contrato_id, item["id"], {"codigo": "99999"})


def test_editar_campo_desconhecido_e_recusado():
    contrato_id = contratos_repo.registrar_do_pdf(HEADER)
    item_id = medicoes_repo.incluir_item(contrato_id, _novo())
    with pytest.raises(MedicaoInvalida, match="source_file"):
        medicoes_repo.atualizar_item(contrato_id, item_id, {"source_file": "x"})


def test_item_de_outro_contrato_nao_e_encontrado():
    contrato_id = contratos_repo.registrar_do_pdf(HEADER)
    item_id = medicoes_repo.incluir_item(contrato_id, _novo())
    assert medicoes_repo.buscar_item(contrato_id + 1, item_id) is None
    assert medicoes_repo.atualizar_item(contrato_id + 1, item_id, {"fator": "1"}) is False
    assert medicoes_repo.excluir_item(contrato_id + 1, item_id) is False


def test_excluir_manual_apaga_e_excluir_do_pdf_e_logico():
    contrato_id = contratos_repo.registrar_do_pdf(HEADER)
    medicoes_repo.gravar_itens(contrato_id, [_linha()])
    [do_pdf] = medicoes_repo.listar_itens(contrato_id)
    manual = medicoes_repo.incluir_item(contrato_id, _novo())

    assert medicoes_repo.excluir_item(contrato_id, manual)
    assert medicoes_repo.excluir_item(contrato_id, do_pdf["id"])
    assert medicoes_repo.listar_itens(contrato_id) == []
    with acquire_sync() as conn:
        restantes = conn.execute("SELECT origem, excluido FROM medicao_item").fetchall()
    assert [dict(r) for r in restantes] == [{"origem": "pdf", "excluido": True}]
    assert medicoes_repo.excluir_item(contrato_id, do_pdf["id"]) is False
