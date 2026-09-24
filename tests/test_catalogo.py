"""Catálogo: produtos do usuário e a associação código → produto."""

import pytest

from app.db import acquire_sync
from app.services import catalogo, contratos_repo, medicoes_repo
from app.services.delta_p import FAMILIA_CAP, FAMILIA_EMULSOES

HEADER = {
    "Contrato": "15 00716/2022 - HWN ENGENHARIA LTDA",
    "Data Base": "01/01/2022",
}


def _item(codigo, descricao, mes=1, valor=100.0, fonte="1ª MP.pdf"):
    return {
        "Serviço": codigo,
        "Descrição": descricao,
        "Valor a PI Líquido": valor,
        "Fator": 0.1,
        "Período Líquido": f"01/{mes:02d}/2023 - 28/{mes:02d}/2023",
        "Source_File": fonte,
    }


async def test_codigos_semeados_estao_associados():
    associados = catalogo.codigos_associados()
    assert len(associados) == 9
    assert associados["8300980"]["descricao_export"] == "AQUISIÇÃO DE CAP 50/70"
    assert associados["60112"]["produto_id"] == associados["92704"]["produto_id"]
    assert associados["29083"]["familia"] == FAMILIA_EMULSOES


async def test_coluna_confirmado_nao_existe_mais():
    with acquire_sync() as conn:
        cur = conn.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'produto_codigo'"
        )
        colunas = {r["column_name"] for r in cur.fetchall()}
    assert "confirmado" not in colunas


async def test_codigo_desconhecido_nao_cria_nada():
    contrato_id = contratos_repo.registrar_do_pdf(HEADER)
    produtos_antes = len(catalogo.listar_produtos())
    gravados = medicoes_repo.gravar_itens(
        contrato_id, [_item("777123", "AQUISIÇÃO DE EMULSÃO RR-2C - TSD")]
    )
    assert gravados == 1
    assert catalogo.buscar_por_codigo("777123") is None
    assert len(catalogo.listar_produtos()) == produtos_antes
    assert medicoes_repo.itens_para_export(contrato_id) == []


async def test_associacao_e_retroativa_e_desassociar_remove_do_calculo():
    contrato_id = contratos_repo.registrar_do_pdf(HEADER)
    medicoes_repo.gravar_itens(contrato_id, [_item("777123", "RR-2C TSD")])

    produto_id = catalogo.novo_produto("Aquisição de RR-2C", FAMILIA_EMULSOES)
    catalogo.registrar_codigo("777123", produto_id)
    itens = medicoes_repo.itens_para_export(contrato_id)
    assert [i["codigo_servico"] for i in itens] == ["777123"]
    assert itens[0]["descricao_export"] == "Aquisição de RR-2C"

    assert catalogo.desassociar_codigo("777123") is True
    assert medicoes_repo.itens_para_export(contrato_id) == []
    assert catalogo.desassociar_codigo("777123") is False


async def test_associar_codigo_ainda_nao_extraido():
    produto_id = catalogo.novo_produto("Aquisição de CAP 30/45", FAMILIA_CAP)
    catalogo.registrar_codigo("999001", produto_id)
    assert catalogo.buscar_por_codigo("999001")["produto_id"] == produto_id


async def test_associar_a_produto_inexistente_e_recusado():
    with pytest.raises(catalogo.ErroCatalogo):
        catalogo.registrar_codigo("999001", 987654)


async def test_reapontar_codigo_para_outro_produto():
    novo = catalogo.novo_produto("Aquisição de CAP (outro)", FAMILIA_CAP)
    catalogo.registrar_codigo("60112", novo)
    assert catalogo.buscar_por_codigo("60112")["produto_id"] == novo


async def test_criar_produto_recusa_familia_invalida():
    with pytest.raises(ValueError):
        catalogo.criar_produto("X", "ASFALTO")
    with pytest.raises(catalogo.ErroCatalogo):
        catalogo.novo_produto("X", "ASFALTO")


async def test_descricao_vazia_e_recusada():
    with pytest.raises(catalogo.ErroCatalogo):
        catalogo.novo_produto("   ", FAMILIA_CAP)


async def test_novo_produto_duplicado():
    catalogo.novo_produto("Aquisição de CAP 50/70 (meu)", FAMILIA_CAP)
    with pytest.raises(catalogo.ProdutoDuplicado):
        catalogo.novo_produto("Aquisição de CAP 50/70 (meu)", FAMILIA_CAP)


async def test_atualizar_produto():
    produto_id = catalogo.novo_produto("Provisório", FAMILIA_CAP)
    atualizado = catalogo.atualizar_produto(
        produto_id, descricao_export="Definitivo", familia=FAMILIA_EMULSOES, ordem=7
    )
    assert atualizado["descricao_export"] == "Definitivo"
    assert atualizado["familia"] == FAMILIA_EMULSOES
    assert atualizado["ordem"] == 7
    assert catalogo.atualizar_produto(987654, ordem=1) is None


async def test_atualizar_para_descricao_existente_e_recusado():
    produto_id = catalogo.novo_produto("Provisório", FAMILIA_CAP)
    with pytest.raises(catalogo.ProdutoDuplicado) as erro:
        catalogo.atualizar_produto(produto_id, descricao_export="AQUISIÇÃO DE CAP 50/70")
    assert "AQUISIÇÃO DE CAP 50/70" in str(erro.value)


async def test_excluir_produto_remove_as_associacoes():
    produto_id = catalogo.novo_produto("Temporário", FAMILIA_CAP)
    catalogo.registrar_codigo("999002", produto_id)
    assert catalogo.excluir_produto(produto_id) is True
    assert catalogo.buscar_por_codigo("999002") is None
    assert catalogo.buscar_produto(produto_id) is None
    assert catalogo.excluir_produto(produto_id) is False


async def test_buscar_codigos_lista_extraidos_e_associados():
    contrato_id = contratos_repo.registrar_do_pdf(HEADER)
    medicoes_repo.gravar_itens(
        contrato_id,
        [
            _item("60112", "AQUISIÇÃO DE CIMENTO ASFÁLTICO CAP 50/70", mes=1),
            _item("60112", "AQUISIÇÃO DE CIMENTO ASFÁLTICO CAP 50/70", mes=2),
            _item("54393", "ESCAVAÇÃO, CARGA E TRANSPORTE", mes=1),
        ],
    )
    por_codigo = {c["codigo"]: c for c in catalogo.buscar_codigos()}

    assert por_codigo["60112"]["ocorrencias"] == 2
    assert por_codigo["60112"]["contratos"] == 1
    assert por_codigo["60112"]["descricao_export"] == "AQUISIÇÃO DE CAP 50/70"
    assert por_codigo["54393"]["produto_id"] is None
    # Associado mas nunca extraído também aparece, com contagem zero.
    assert por_codigo["133004"]["ocorrencias"] == 0
    assert por_codigo["133004"]["descricao_pdf"] is None


async def test_buscar_codigos_filtra_por_codigo_ou_descricao():
    contrato_id = contratos_repo.registrar_do_pdf(HEADER)
    medicoes_repo.gravar_itens(
        contrato_id,
        [_item("54393", "Escavação, carga e transporte"), _item("54394", "Drenagem")],
    )
    assert [c["codigo"] for c in catalogo.buscar_codigos("ESCAVA")] == ["54393"]
    assert [c["codigo"] for c in catalogo.buscar_codigos("5439")] == ["54393", "54394"]
    # Em branco = sem filtro.
    assert len(catalogo.buscar_codigos("  ")) == len(catalogo.buscar_codigos())


async def test_buscar_codigos_trata_curinga_como_texto():
    contrato_id = contratos_repo.registrar_do_pdf(HEADER)
    medicoes_repo.gravar_itens(
        contrato_id,
        [_item("54393", "Reajuste 100% pago"), _item("54394", "Reajuste 100 pago")],
    )
    assert [c["codigo"] for c in catalogo.buscar_codigos("100%")] == ["54393"]
    assert catalogo.buscar_codigos("_") == []


async def test_buscar_codigos_usa_a_descricao_mais_recente():
    contrato_id = contratos_repo.registrar_do_pdf(HEADER)
    medicoes_repo.gravar_itens(contrato_id, [_item("54393", "DESCRICAO ANTIGA", mes=1)])
    medicoes_repo.gravar_itens(contrato_id, [_item("54393", "DESCRICAO NOVA", mes=2)])
    (codigo,) = catalogo.buscar_codigos("54393")
    assert codigo["descricao_pdf"] == "DESCRICAO NOVA"


async def test_buscar_codigos_filtra_associados():
    contrato_id = contratos_repo.registrar_do_pdf(HEADER)
    medicoes_repo.gravar_itens(contrato_id, [_item("54393", "Escavação")])
    livres = {c["codigo"] for c in catalogo.buscar_codigos(associado=False)}
    associados = {c["codigo"] for c in catalogo.buscar_codigos(associado=True)}
    assert livres == {"54393"}
    assert len(associados) == 9
