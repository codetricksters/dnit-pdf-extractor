"""O FastAPI serve o build do frontend sem capturar as rotas do backend."""

import pytest

from app import spa

INDEX = "<!doctype html><div id=root></div><!-- spa -->"


@pytest.fixture
def dist(tmp_path, monkeypatch):
    (tmp_path / "assets").mkdir()
    (tmp_path / "index.html").write_text(INDEX, encoding="utf-8")
    (tmp_path / "assets" / "app.js").write_text("console.log('ok')", encoding="utf-8")
    monkeypatch.setattr(spa, "DIST", tmp_path)
    return tmp_path


@pytest.mark.parametrize(
    "rota", ["/", "/contratos", "/contratos/12", "/contratos/12/calculo", "/upload", "/indices/anp"]
)
async def test_rotas_do_spa_devolvem_o_index(client, dist, rota):
    resposta = await client.get(rota)
    assert resposta.status_code == 200
    assert "<!-- spa -->" in resposta.text
    assert resposta.headers["cache-control"] == "no-cache"


async def test_arquivo_do_build_e_servido_como_esta(client, dist):
    resposta = await client.get("/assets/app.js")
    assert resposta.status_code == 200
    assert resposta.text == "console.log('ok')"


async def test_caminho_para_fora_do_dist_cai_no_index(client, dist):
    resposta = await client.get("/assets/..%2F..%2Fpyproject.toml")
    assert resposta.status_code == 200
    assert "<!-- spa -->" in resposta.text


@pytest.mark.parametrize(
    "rota",
    ["/api/v1/nao-existe", "/jobs/a/b/c/d", "/admin/nada", "/reequilibrio/nada", "/static/nada.css"],
)
async def test_prefixos_do_backend_nao_sao_capturados(client, dist, rota):
    resposta = await client.get(rota)
    assert resposta.status_code == 404
    assert "<!-- spa -->" not in resposta.text


async def test_backend_continua_respondendo(client, dist):
    assert (await client.get("/api/v1/contratos")).json() == []
    assert (await client.get("/jobs?status=active")).status_code == 200
    assert (await client.get("/openapi.json")).status_code == 200
    assert (await client.get("/docs")).status_code == 200
    # POST /upload continua sendo o envio: sem arquivos, a validação recusa.
    assert (await client.post("/upload")).status_code == 422


async def test_rota_do_spa_fica_fora_do_openapi(client, dist):
    caminhos = (await client.get("/openapi.json")).json()["paths"]
    assert not any("caminho" in c for c in caminhos)


async def test_sem_build_mostra_como_gerar(client, tmp_path, monkeypatch):
    monkeypatch.setattr(spa, "DIST", tmp_path / "nao-existe")
    resposta = await client.get("/contratos/12")
    assert resposta.status_code == 200
    assert "npm run build" in resposta.text
