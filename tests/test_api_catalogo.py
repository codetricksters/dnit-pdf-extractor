"""API do catálogo: produtos do usuário e associação de códigos."""

from app.services import contratos_repo, medicoes_repo

HEADER = {"Contrato": "15 00716/2022 - HWN ENGENHARIA LTDA", "Data Base": "01/01/2022"}


def _extrair(codigo: str, descricao: str) -> int:
    contrato_id = contratos_repo.registrar_do_pdf(HEADER)
    medicoes_repo.gravar_itens(
        contrato_id,
        [{"Serviço": codigo, "Descrição": descricao, "Valor a PI Líquido": 10.0,
          "Fator": 0.1, "Período Líquido": "01/02/2023 - 28/02/2023",
          "Source_File": "1ª MP.pdf"}],
    )
    return contrato_id


async def _novo(client, descricao="AQUISIÇÃO DE CAP 50/70 (TESTE)", familia="CAP") -> dict:
    resposta = await client.post(
        "/api/v1/produtos", json={"descricao_export": descricao, "familia": familia}
    )
    assert resposta.status_code == 201, resposta.text
    return resposta.json()


async def test_criar_listar_editar_e_excluir_produto(client):
    produto = await _novo(client)
    assert produto["familia"] == "CAP" and produto["codigos"] == 0

    ids = [p["id"] for p in (await client.get("/api/v1/produtos")).json()]
    assert produto["id"] in ids

    resposta = await client.patch(
        f"/api/v1/produtos/{produto['id']}", json={"familia": "EMULSOES", "ordem": 3}
    )
    assert resposta.status_code == 200
    assert resposta.json()["familia"] == "EMULSOES" and resposta.json()["ordem"] == 3

    assert (await client.delete(f"/api/v1/produtos/{produto['id']}")).status_code == 204
    assert (await client.delete(f"/api/v1/produtos/{produto['id']}")).status_code == 404
    resposta = await client.patch(f"/api/v1/produtos/{produto['id']}", json={"ordem": 1})
    assert resposta.status_code == 404


async def test_produto_duplicado_e_409_e_familia_invalida_e_422(client):
    await _novo(client, "PRODUTO X")
    resposta = await client.post(
        "/api/v1/produtos", json={"descricao_export": "PRODUTO X", "familia": "CAP"}
    )
    assert resposta.status_code == 409
    assert "PRODUTO X" in resposta.json()["detail"]
    resposta = await client.post(
        "/api/v1/produtos", json={"descricao_export": "Y", "familia": "ASFALTO"}
    )
    assert resposta.status_code == 422
    resposta = await client.post(
        "/api/v1/produtos", json={"descricao_export": "  ", "familia": "CAP"}
    )
    assert resposta.status_code == 422


async def test_associar_filtrar_e_desassociar_codigo(client):
    _extrair("54393", "ESCAVAÇÃO, CARGA E TRANSPORTE")
    produto = await _novo(client)

    livres = (await client.get("/api/v1/codigos", params={"q": "escava"})).json()
    assert [c["codigo"] for c in livres] == ["54393"]
    assert livres[0]["produto_id"] is None and livres[0]["ocorrencias"] == 1

    resposta = await client.put("/api/v1/codigos/54393", json={"produto_id": produto["id"]})
    assert resposta.status_code == 200
    assert resposta.json()["descricao_export"] == produto["descricao_export"]

    associados = (await client.get("/api/v1/codigos", params={"associado": "true", "q": "543"})).json()
    assert [c["codigo"] for c in associados] == ["54393"]

    assert (await client.delete("/api/v1/codigos/54393")).status_code == 204
    assert (await client.delete("/api/v1/codigos/54393")).status_code == 404


async def test_associar_codigo_ainda_nao_extraido(client):
    produto = await _novo(client)
    resposta = await client.put("/api/v1/codigos/777777", json={"produto_id": produto["id"]})
    assert resposta.status_code == 200
    assert resposta.json()["codigo_servico"] == "777777"


async def test_associar_a_produto_inexistente_e_codigo_invalido(client):
    resposta = await client.put("/api/v1/codigos/54393", json={"produto_id": 99999})
    assert resposta.status_code == 422
    assert "99999" in resposta.json()["detail"]
    resposta = await client.put("/api/v1/codigos/abc", json={"produto_id": 1})
    assert resposta.status_code == 422
