"""Itens extraídos de um contrato, com o produto do catálogo (ou nenhum)."""

from app.services import catalogo, contratos_repo, medicoes_repo

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
    assert isinstance(resposta.json()["detail"], list)
    resposta = await client.get("/api/v1/contratos/999/medicoes")
    assert resposta.status_code == 404
    assert resposta.json()["detail"] == "Contrato 999 não encontrado."
