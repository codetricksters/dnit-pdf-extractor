"""API de índices: edição manual, importação com prévia e exportação."""

import csv
import io
from datetime import date
from decimal import Decimal
from pathlib import Path

import openpyxl
import pytest

from app.routers.api import indices as rotas_indices
from app.services import importadores
from app.services.delta_p import ANP_PRODUTO_CAP

ANP_OFICIAL = Path("tests/fixtures/anp_semanal.xls")
SEMANA = {
    "vigencia_inicio": "2023-01-09",
    "vigencia_fim": "2023-01-15",
    "regiao": "Nordeste",
    "preco": "3.28568",
}


def _igp(*meses) -> bytes:
    return importadores.gerar_template_igp_di(
        [{"mes_ref": m, "valor": Decimal(v)} for m, v in meses]
    )


async def test_cobertura_vazia(client):
    corpo = (await client.get("/api/v1/indices/cobertura")).json()
    assert corpo["anp"]["registros"] == 0 and corpo["igp_di"]["registros"] == 0
    assert corpo["regioes"] == []


async def test_semana_manual_listar_e_excluir(client):
    resposta = await client.put("/api/v1/indices/anp", json=SEMANA)
    assert resposta.status_code == 200, resposta.text
    semana = resposta.json()
    assert semana["produto"] == ANP_PRODUTO_CAP
    assert semana["preco"] == "3.28568" and semana["origem"] == "manual"

    lista = (await client.get("/api/v1/indices/anp", params={"regiao": "nordeste"})).json()
    assert [s["id"] for s in lista] == [semana["id"]]
    fora = await client.get("/api/v1/indices/anp", params={"de": "2023-02-01"})
    assert fora.json() == []

    assert (await client.delete(f"/api/v1/indices/anp/{semana['id']}")).status_code == 204
    assert (await client.delete(f"/api/v1/indices/anp/{semana['id']}")).status_code == 404


async def test_semana_sem_cotacao_e_aceita(client):
    resposta = await client.put("/api/v1/indices/anp", json={**SEMANA, "preco": None})
    assert resposta.status_code == 200
    assert resposta.json()["preco"] is None


async def test_semana_sobreposta_e_422(client):
    await client.put("/api/v1/indices/anp", json=SEMANA)
    resposta = await client.put(
        "/api/v1/indices/anp",
        json={**SEMANA, "vigencia_inicio": "2023-01-12", "vigencia_fim": "2023-01-18"},
    )
    assert resposta.status_code == 422
    assert "sobrepõe" in resposta.json()["detail"]


async def test_igp_manual_listar_e_excluir(client):
    resposta = await client.put("/api/v1/indices/igp-di/2023-02", json={"valor": "1144.271"})
    assert resposta.status_code == 200, resposta.text
    assert resposta.json()["mes"] == "2023-02"
    assert resposta.json()["valor"] == "1144.271"

    lista = (await client.get("/api/v1/indices/igp-di", params={"de": "2023-01"})).json()
    assert [m["mes"] for m in lista] == ["2023-02"]

    assert (await client.delete("/api/v1/indices/igp-di/2023-02")).status_code == 204
    assert (await client.delete("/api/v1/indices/igp-di/2023-02")).status_code == 404


@pytest.mark.parametrize(
    "mes,valor", [("2023-13", "1"), ("23-01", "1"), ("2023-01", "0")]
)
async def test_igp_manual_invalido_e_422(client, mes, valor):
    resposta = await client.put(f"/api/v1/indices/igp-di/{mes}", json={"valor": valor})
    assert resposta.status_code == 422


async def test_importar_igp_previa_preserva_e_sobrescreve_manual(client):
    await client.put("/api/v1/indices/igp-di/2023-01", json={"valor": "1000"})
    arquivo = {"arquivo": ("igp.xlsx", _igp((date(2023, 1, 1), "1100"), (date(2023, 2, 1), "1144.271")))}
    url = "/api/v1/indices/igp-di/importar"

    previa = (await client.post(url, params={"simular": "true"}, files=arquivo)).json()
    assert previa["simulacao"] is True
    assert previa["inseridos"] == 1
    assert previa["conflitos_manuais"][0]["chave"] == {"mes": "2023-01"}
    assert previa["conflitos_manuais"][0]["valor_banco"] == "1000"
    assert len((await client.get("/api/v1/indices/igp-di")).json()) == 1

    gravado = (await client.post(url, files=arquivo)).json()
    assert gravado["manuais_preservados"] == 1
    meses = {m["mes"]: m for m in (await client.get("/api/v1/indices/igp-di")).json()}
    assert meses["2023-01"]["valor"] == "1000"
    assert meses["2023-02"]["origem"] == "upload:igp.xlsx"

    vencedor = (await client.post(url, params={"sobrescrever_manuais": "true"}, files=arquivo)).json()
    assert vencedor["atualizados"] == [
        {"chave": {"mes": "2023-01"}, "antes": "1000", "depois": "1100"}
    ]
    meses = {m["mes"]: m for m in (await client.get("/api/v1/indices/igp-di")).json()}
    assert meses["2023-01"]["valor"] == "1100"
    assert meses["2023-01"]["origem"] == "upload:igp.xlsx"


async def test_importar_arquivo_invalido_lista_os_erros(client):
    resposta = await client.post(
        "/api/v1/indices/anp/importar", files={"arquivo": ("x.xls", b"nao e planilha")}
    )
    assert resposta.status_code == 422
    corpo = resposta.json()
    assert "ANP" in corpo["detail"] and "erros" in corpo


async def test_upload_vazio_e_acima_do_limite(client, monkeypatch):
    url = "/api/v1/indices/igp-di/importar"
    vazio = await client.post(url, files={"arquivo": ("igp.xlsx", b"")})
    assert vazio.status_code == 422
    monkeypatch.setattr(rotas_indices, "LIMITE_UPLOAD", 10)
    grande = await client.post(url, files={"arquivo": ("igp.xlsx", b"x" * 11)})
    assert grande.status_code == 413
    assert "limite" in grande.json()["detail"]


async def test_importar_anp_oficial_em_previa_nao_grava(client):
    resposta = await client.post(
        "/api/v1/indices/anp/importar",
        params={"simular": "true"},
        files={"arquivo": ("anp.xls", ANP_OFICIAL.read_bytes())},
    )
    assert resposta.status_code == 200, resposta.text
    corpo = resposta.json()
    assert corpo["inseridos"] == 60114
    assert len(corpo["avisos"]) == 1 and "GLP" in corpo["avisos"][0]
    assert (await client.get("/api/v1/indices/cobertura")).json()["anp"]["registros"] == 0


async def test_exportar_anp_csv_e_xlsx(client):
    await client.put("/api/v1/indices/anp", json=SEMANA)

    resposta = await client.get("/api/v1/indices/anp/exportar", params={"formato": "csv"})
    assert resposta.status_code == 200
    assert "precos_anp.csv" in resposta.headers["content-disposition"]
    (linha,) = list(csv.DictReader(io.StringIO(resposta.text)))
    assert linha["vigencia_inicio"] == "2023-01-09" and linha["preco"] == "3.28568"

    resposta = await client.get("/api/v1/indices/anp/exportar")
    assert "precos_anp.xlsx" in resposta.headers["content-disposition"]
    assert "Preços ANP" in openpyxl.load_workbook(io.BytesIO(resposta.content)).sheetnames


async def test_template_e_exportacao_do_igp_sao_reimportaveis(client):
    vazio = await client.get("/api/v1/indices/igp-di/template")
    assert "igp_di_template.xlsx" in vazio.headers["content-disposition"]
    with pytest.raises(importadores.ArquivoInvalido):
        importadores.ler_igp_di(vazio.content)  # só o cabeçalho

    await client.put("/api/v1/indices/igp-di/2023-02", json={"valor": "1144.271"})
    for rota in ("/api/v1/indices/igp-di/template", "/api/v1/indices/igp-di/exportar"):
        leitura = importadores.ler_igp_di((await client.get(rota)).content)
        assert [(r["mes_ref"], r["valor"]) for r in leitura.registros] == [
            (date(2023, 2, 1), Decimal("1144.271"))
        ]

    resposta = await client.get("/api/v1/indices/igp-di/exportar", params={"formato": "csv"})
    assert "igp_di.csv" in resposta.headers["content-disposition"]
    assert resposta.text.splitlines()[0] == "mes,valor,origem,atualizado_em"
