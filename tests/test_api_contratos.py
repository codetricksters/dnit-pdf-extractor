"""API de contratos: lista, detalhe e PATCH do cadastro."""

from datetime import date

from app.services import contratos_repo, indices_repo, medicoes_repo

from .indices_factory import semana

HEADER = {
    "Contrato": "15 00716/2022 - HWN ENGENHARIA LTDA",
    "Data Base": "01/01/2022",
    "Número do Processo": "50615.000404/2022-67",
}


def _contrato() -> int:
    contrato_id = contratos_repo.registrar_do_pdf(HEADER)
    medicoes_repo.gravar_itens(
        contrato_id,
        [{"Serviço": "8300980", "Descrição": "CAP 50/70", "Valor a PI Líquido": 10.0,
          "Fator": 0.1, "Período Líquido": "01/02/2023 - 28/02/2023",
          "Source_File": "1ª MP.pdf"}],
    )
    return contrato_id


async def test_lista_e_filtro_por_numero(client):
    contrato_id = _contrato()
    resposta = await client.get("/api/v1/contratos")
    assert resposta.status_code == 200
    (linha,) = resposta.json()
    assert linha["id"] == contrato_id
    assert linha["numero"] == "15 00716/2022"
    assert linha["data_base"] == "2022-01-01"
    assert linha["itens"] == 1 and linha["medicoes"] == 1
    assert linha["regioes"] == {}
    assert "regiao_cap" in linha["faltantes"]

    assert (await client.get("/api/v1/contratos", params={"numero": "716"})).json()
    assert (await client.get("/api/v1/contratos", params={"numero": "999"})).json() == []


async def test_detalhe_e_404(client):
    contrato_id = _contrato()
    corpo = (await client.get(f"/api/v1/contratos/{contrato_id}")).json()
    assert corpo["numero_processo"] == "50615.000404/2022-67"
    assert corpo["faltantes"]

    resposta = await client.get("/api/v1/contratos/999")
    assert resposta.status_code == 404
    assert resposta.json() == {"detail": "Contrato 999 não encontrado."}


async def test_patch_grava_cadastro_data_base_e_regioes(client):
    indices_repo.gravar_precos_anp(
        [semana(date(2023, 1, 9), "3.2", regiao=r) for r in ("Nordeste", "Sul")]
    )
    contrato_id = _contrato()
    resposta = await client.patch(
        f"/api/v1/contratos/{contrato_id}",
        json={
            "rodovia": "BR-316/MA",
            "extensao": "188,7",
            "data_base": "01/2021",
            "regioes": {"CAP": "nordeste", "EMULSOES": "Sul"},
        },
    )
    assert resposta.status_code == 200, resposta.text
    corpo = resposta.json()
    assert corpo["rodovia"] == "BR-316/MA"
    assert corpo["extensao"] == "188.7"
    assert corpo["data_base"] == "2021-01-01"
    assert corpo["regioes"] == {"CAP": "Nordeste", "EMULSOES": "Sul"}
    assert "regiao_cap" not in corpo["faltantes"]


async def test_patch_regiao_sem_precos_e_422(client):
    indices_repo.gravar_precos_anp([semana(date(2023, 1, 9), "3.2")])
    contrato_id = _contrato()
    resposta = await client.patch(
        f"/api/v1/contratos/{contrato_id}", json={"regioes": {"CAP": "Marte"}}
    )
    assert resposta.status_code == 422
    assert "Nordeste" in resposta.json()["detail"]


async def test_patch_campo_desconhecido_e_422(client):
    contrato_id = _contrato()
    resposta = await client.patch(f"/api/v1/contratos/{contrato_id}", json={"numero": "1"})
    assert resposta.status_code == 422


async def test_patch_contrato_inexistente_e_404(client):
    resposta = await client.patch("/api/v1/contratos/999", json={"rodovia": "x"})
    assert resposta.status_code == 404
