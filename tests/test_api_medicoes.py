"""Itens extraídos de um contrato, com o produto do catálogo (ou nenhum)."""

from datetime import date

from app.services import catalogo, contratos_repo, indices_repo, medicoes_repo
from tests.indices_factory import semana

HEADER = {"Contrato": "15 00716/2022 - HWN ENGENHARIA LTDA", "Data Base": "01/01/2022"}
FEV = "01/02/2023 - 28/02/2023"
MAR = "01/03/2023 - 31/03/2023"


def _item(codigo, descricao, valor, fator, periodo, arquivo="1ª MP.pdf") -> dict:
    return {"Serviço": codigo, "Descrição": descricao, "Valor a PI Líquido": valor,
            "Fator": fator, "Período Líquido": periodo, "Source_File": arquivo}


def _contrato() -> int:
    contrato_id = contratos_repo.registrar_do_pdf(HEADER)
    medicoes_repo.gravar_itens(
        contrato_id,
        [
            _item("60112", "Fornecimento de CAP 50/70", 412300.0, 0.148, FEV),
            _item("40210", "Escavação de material de 1ª categoria", 10.0, 0.12399, FEV),
            _item("60112", "Fornecimento de CAP 50/70", 100.0, -0.1839, MAR, "2ª MP.pdf"),
        ],
    )
    produto_id = catalogo.novo_produto("Aquisição de CAP 50/70", "CAP")
    catalogo.registrar_codigo("60112", produto_id)
    return contrato_id


async def _medicoes(client, contrato_id, **params):
    resposta = await client.get(f"/api/v1/contratos/{contrato_id}/medicoes", params=params)
    assert resposta.status_code == 200, resposta.text
    return resposta.json()


async def test_lista_itens_com_produto_e_reajuste_truncado(client):
    contrato_id = _contrato()
    itens = await _medicoes(client, contrato_id)
    assert [(i["mes"], i["codigo"]) for i in itens] == [
        ("2023-02-01", "40210"), ("2023-02-01", "60112"), ("2023-03-01", "60112"),
    ]
    escavacao, cap_fev, cap_mar = itens
    assert cap_fev["produto"] == "Aquisição de CAP 50/70" and cap_fev["familia"] == "CAP"
    assert cap_fev["valor_pi"] == "412300.00" and cap_fev["reajuste"] == "61020.40"
    assert cap_fev["arquivo"] == "1ª MP.pdf"
    # 10 · 0,12399 = 1,2399 → 1,23: trunca, não arredonda (coluna F da planilha).
    assert escavacao["reajuste"] == "1.23"
    assert escavacao["produto_id"] is None and escavacao["produto"] is None
    assert escavacao["familia"] is None
    assert cap_mar["reajuste"] == "-18.39" and cap_mar["arquivo"] == "2ª MP.pdf"


async def test_filtros_de_mes_calculo_e_busca(client):
    contrato_id = _contrato()
    assert [i["codigo"] for i in await _medicoes(client, contrato_id, mes="2023-03")] == ["60112"]
    no_calculo = await _medicoes(client, contrato_id, no_calculo="true")
    assert {i["codigo"] for i in no_calculo} == {"60112"} and len(no_calculo) == 2
    assert [i["codigo"] for i in await _medicoes(client, contrato_id, no_calculo="false")] == ["40210"]
    assert [i["codigo"] for i in await _medicoes(client, contrato_id, q="escava")] == ["40210"]
    assert len(await _medicoes(client, contrato_id, q="601")) == 2
    assert await _medicoes(client, contrato_id, mes="2023-03", no_calculo="false") == []


async def test_mes_invalido_e_contrato_inexistente(client):
    contrato_id = _contrato()
    resposta = await client.get(f"/api/v1/contratos/{contrato_id}/medicoes", params={"mes": "2023-13"})
    assert resposta.status_code == 422
    detalhe = resposta.json()["detail"]
    assert isinstance(detalhe, list)
    assert detalhe[0]["loc"] == ["query", "mes"]
    assert detalhe[0]["msg"] == "Mês inválido. Use o formato AAAA-MM, com o mês de 01 a 12, por exemplo 2023-02."
    resposta = await client.get("/api/v1/contratos/999/medicoes")
    assert resposta.status_code == 404
    assert resposta.json()["detail"] == "Contrato 999 não encontrado."


NOVO = {"mes": "2023-02", "codigo": "60112", "descricao_pdf": "CAP manual",
        "valor_pi": "100.00", "fator": "0.148"}


async def test_incluir_alterar_e_excluir_um_registro(client):
    indices_repo.gravar_precos_anp([semana(date(2023, 1, 9), "3.45", regiao="Sul")])
    contrato_id = _contrato()
    base = f"/api/v1/contratos/{contrato_id}/medicoes"

    criado = await client.post(base, json={**NOVO, "regiao_cap": "sul"})
    assert criado.status_code == 201, criado.text
    item = criado.json()
    assert item["origem"] == "manual" and item["regiao_cap"] == "Sul"
    assert item["valor_pi"] == "100.00" and item["produto"] == "Aquisição de CAP 50/70"

    alterado = await client.patch(f"{base}/{item['id']}", json={"fator": "0.2"})
    assert alterado.status_code == 200 and alterado.json()["fator"] == "0.2"

    assert (await client.delete(f"{base}/{item['id']}")).status_code == 204
    assert len(await _medicoes(client, contrato_id)) == 3


async def test_regiao_invalida_e_422_com_texto(client):
    contrato_id = _contrato()
    resposta = await client.post(f"/api/v1/contratos/{contrato_id}/medicoes",
                                 json={**NOVO, "regiao_cap": "Marte"})
    assert resposta.status_code == 422
    assert "regiao_cap" in resposta.json()["detail"]


async def test_corpo_malformado_e_422_do_pydantic(client):
    contrato_id = _contrato()
    resposta = await client.post(f"/api/v1/contratos/{contrato_id}/medicoes",
                                 json={**NOVO, "mes": "2023-13"})
    assert resposta.status_code == 422 and isinstance(resposta.json()["detail"], list)


async def test_contrato_ou_item_inexistente_e_404(client):
    contrato_id = _contrato()
    assert (await client.post("/api/v1/contratos/999/medicoes", json=NOVO)).status_code == 404
    base = f"/api/v1/contratos/{contrato_id}/medicoes"
    assert (await client.patch(f"{base}/999999", json={"fator": "1"})).status_code == 404
    assert (await client.delete(f"{base}/999999")).status_code == 404


async def test_lista_traz_origem_e_regioes(client):
    contrato_id = _contrato()
    [item, *_] = await _medicoes(client, contrato_id)
    assert item["origem"] == "pdf"
    assert item["regiao_cap"] is None and item["regiao_emulsoes"] is None


async def test_aplicar_regiao_nos_selecionados(client):
    indices_repo.gravar_precos_anp([semana(date(2023, 1, 9), "3.45", regiao="Sul")])
    contrato_id = _contrato()
    url = f"/api/v1/contratos/{contrato_id}/medicoes/regiao"
    itens = await _medicoes(client, contrato_id)
    [fev] = [i for i in itens if i["codigo"] == "60112" and i["mes"] == "2023-02-01"]
    [sem_produto] = [i for i in itens if i["codigo"] == "40210"]
    corpo = {"ids": [fev["id"], sem_produto["id"]], "regiao": "sul"}

    previa = await client.post(url, json=corpo, params={"simular": "true"})
    assert previa.status_code == 200 and previa.json() == {"alterados": 1}
    resposta = await client.post(url, json=corpo)
    assert resposta.status_code == 200, resposta.text
    assert resposta.json() == {"alterados": 1}
    regioes = {i["id"]: i["regiao_cap"] for i in await _medicoes(client, contrato_id)}
    assert regioes[fev["id"]] == "Sul"
    assert [r for i, r in regioes.items() if i != fev["id"]] == [None, None]

    invalida = await client.post(url, json={**corpo, "regiao": "Marte"})
    assert invalida.status_code == 422 and "regiao" in invalida.json()["detail"]
    vazia = await client.post(url, json={**corpo, "ids": []})
    assert vazia.status_code == 422 and isinstance(vazia.json()["detail"], list)
    antiga = await client.post(url, json={"familia": "CAP", "mes_de": "2023-02",
                                          "mes_ate": "2023-03", "regiao": "Sul"})
    assert antiga.status_code == 422
    ausente = await client.post("/api/v1/contratos/999/medicoes/regiao", json=corpo)
    assert ausente.status_code == 404


async def test_filtro_de_arquivo_e_exclusao_em_massa(client):
    contrato_id = _contrato()
    base = f"/api/v1/contratos/{contrato_id}/medicoes"
    do_primeiro = await _medicoes(client, contrato_id, arquivo="1ª MP.pdf")
    assert {i["arquivo"] for i in do_primeiro} == {"1ª MP.pdf"} and len(do_primeiro) == 2

    resposta = await client.post(f"{base}/excluir", json={"ids": [i["id"] for i in do_primeiro]})
    assert resposta.status_code == 200, resposta.text
    assert resposta.json() == {"excluidos": 2}
    assert [i["arquivo"] for i in await _medicoes(client, contrato_id)] == ["2ª MP.pdf"]

    assert (await client.post(f"{base}/excluir", json={"ids": []})).status_code == 422
    assert (await client.post("/api/v1/contratos/999/medicoes/excluir", json={"ids": [1]})).status_code == 404
