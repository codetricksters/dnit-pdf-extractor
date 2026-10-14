"""Registros de medição editados à mão sobrevivem ao reprocessamento do PDF."""

from app.db import acquire_sync
from app.services import contratos_repo, medicoes_repo

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
