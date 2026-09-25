"""Pequenas adições da API pedidas pelo frontend React."""

import asyncio
from datetime import date

from app.models.job import FileStatus
from app.routers.api.calculo import nome_do_arquivo
from app.services import catalogo, contratos_repo, file_processor, indices_repo, job_manager, medicoes_repo
from app.services.delta_p import ANP_PRODUTO_CAP

from .indices_factory import mes_igp, semana
from .test_api_calculo import _contrato as contrato_calculavel

HEADER = {"Contrato": "15 00716/2022 - HWN ENGENHARIA LTDA", "Data Base": "01/01/2022"}
DIESEL = "Óleo Diesel (R$/l)"


def _extrair(*codigos: str) -> int:
    contrato_id = contratos_repo.registrar_do_pdf(HEADER)
    medicoes_repo.gravar_itens(
        contrato_id,
        [{"Serviço": c, "Descrição": f"Item {c}", "Valor a PI Líquido": 10.0, "Fator": 0.1,
          "Período Líquido": "01/02/2023 - 28/02/2023", "Source_File": "1ª MP.pdf"}
         for c in codigos],
    )
    return contrato_id


# ── Catálogo ────────────────────────────────────────────────────────────────


async def test_codigos_filtrados_por_produto(client):
    _extrair("60112", "60113", "40210")
    cap = catalogo.novo_produto("CAP 50/70", "CAP")
    emul = catalogo.novo_produto("Emulsão RR-1C", "EMULSOES")
    catalogo.registrar_codigo("60112", cap)
    catalogo.registrar_codigo("60113", emul)
    resposta = await client.get("/api/v1/codigos", params={"produto_id": cap})
    assert [c["codigo"] for c in resposta.json()] == ["60112"]
    resposta = await client.get("/api/v1/codigos", params={"produto_id": cap, "q": "40210"})
    assert resposta.json() == []


async def test_associar_codigos_em_lote(client):
    _extrair("60112", "60113", "40210")
    cap = catalogo.novo_produto("CAP 50/70", "CAP")
    emul = catalogo.novo_produto("Emulsão RR-1C", "EMULSOES")
    catalogo.registrar_codigo("60113", emul)

    resposta = await client.put(
        f"/api/v1/produtos/{cap}/codigos",
        # 60113 muda de produto, 99999 ainda não foi extraído, 60112 repetido.
        json={"codigos": ["60112", "60113", "99999", "60112"]},
    )
    assert resposta.status_code == 200, resposta.text
    assert resposta.json()["id"] == cap and resposta.json()["codigos"] == 3
    assert catalogo.buscar_produto(emul)["codigos"] == 0
    codigos = await client.get("/api/v1/codigos", params={"produto_id": cap})
    assert [c["codigo"] for c in codigos.json()] == ["60112", "60113", "99999"]


async def test_associar_em_lote_produto_inexistente_nao_grava(client):
    # Código fora da semente do catálogo (60112 e outros já vêm associados por
    # migration 003), para garantir que nada foi gravado com o produto 999.
    _extrair("77001")
    resposta = await client.put("/api/v1/produtos/999/codigos", json={"codigos": ["77001"]})
    assert resposta.status_code == 404
    assert resposta.json()["detail"] == "Produto 999 não encontrado."
    assert catalogo.buscar_por_codigo("77001") is None


async def test_associar_em_lote_valida_o_corpo(client):
    cap = catalogo.novo_produto("CAP 50/70", "CAP")
    for corpo in ({"codigos": []}, {"codigos": ["12"]}, {"codigos": ["60112"], "extra": 1}):
        resposta = await client.put(f"/api/v1/produtos/{cap}/codigos", json=corpo)
        assert resposta.status_code == 422, corpo
        assert isinstance(resposta.json()["detail"], list)


# ── Índices ─────────────────────────────────────────────────────────────────


async def test_produtos_anp(client):
    indices_repo.gravar_precos_anp([semana(date(2023, 1, 9), "3.2")])
    indices_repo.gravar_precos_anp([semana(date(2023, 1, 9), "6.1", produto=DIESEL)])
    resposta = await client.get("/api/v1/indices/anp/produtos")
    assert resposta.status_code == 200
    assert resposta.json() == [ANP_PRODUTO_CAP, DIESEL]


async def test_cobertura_conta_os_valores_manuais(client):
    indices_repo.gravar_precos_anp([semana(date(2023, 1, 2), "3.1")], origem="seed")
    indices_repo.gravar_indices_mensais([mes_igp(date(2022, 12, 1), "1100.5")], origem="seed")
    resposta = await client.put(
        "/api/v1/indices/anp",
        json={"vigencia_inicio": "2023-01-09", "vigencia_fim": "2023-01-15",
              "regiao": "Nordeste", "preco": "3.2"},
    )
    assert resposta.status_code == 200, resposta.text
    resposta = await client.put("/api/v1/indices/igp-di/2023-01", json={"valor": "1110.4"})
    assert resposta.status_code == 200, resposta.text

    corpo = (await client.get("/api/v1/indices/cobertura")).json()
    assert corpo["anp"]["registros"] == 2 and corpo["anp"]["manuais"] == 1
    assert corpo["igp_di"]["registros"] == 2 and corpo["igp_di"]["manuais"] == 1


# ── Cálculo ─────────────────────────────────────────────────────────────────


async def test_calculo_informa_o_nome_do_arquivo(client):
    contrato_id = contrato_calculavel()
    url = f"/api/v1/contratos/{contrato_id}"
    corpo = (await client.get(f"{url}/calculo")).json()
    assert corpo["arquivo"] == "Reequilibrio_15-00716-2022.xlsx"

    params = {"regiao_cap": "Sul"}
    corpo = (await client.get(f"{url}/calculo", params=params)).json()
    assert corpo["arquivo"] == nome_do_arquivo("15 00716/2022", {"CAP": "Sul"})
    planilha = await client.get(f"{url}/planilha", params=params)
    assert corpo["arquivo"] in planilha.headers["content-disposition"]


# ── Jobs ────────────────────────────────────────────────────────────────────

RESULTADO = {
    "header": HEADER,
    "rows": [{"Serviço": "60112", "Descrição": "CAP", "Valor a PI Líquido": 10.0,
              "Fator": 0.1, "Período Líquido": "01/02/2023 - 28/02/2023",
              "Source_File": "a.pdf"},
             {"Serviço": "60113", "Descrição": "Emulsão", "Valor a PI Líquido": 5.0,
              "Fator": 0.1, "Período Líquido": "01/02/2023 - 28/02/2023",
              "Source_File": "a.pdf"}],
}


async def test_status_do_job_liga_o_arquivo_ao_contrato(client):
    job_id = await job_manager.create_job(["a.pdf", "b.pdf"])
    await asyncio.to_thread(file_processor._persistir, RESULTADO, "a.pdf", job_id)

    arquivos = (await client.get(f"/jobs/{job_id}/status")).json()["files"]
    contrato = contratos_repo.buscar("15 00716/2022")
    assert arquivos["a.pdf"]["contrato_id"] == contrato["id"]
    assert arquivos["a.pdf"]["itens"] == 2
    assert arquivos["b.pdf"]["contrato_id"] is None and arquivos["b.pdf"]["itens"] is None


async def test_tentar_de_novo_limpa_o_vinculo(client):
    job_id = await job_manager.create_job(["a.pdf"])
    await asyncio.to_thread(file_processor._persistir, RESULTADO, "a.pdf", job_id)
    await job_manager.update_file_status(job_id, "a.pdf", FileStatus.FAILED, error="x")
    await job_manager.reset_file_for_retry(job_id, "a.pdf")

    arquivo = (await client.get(f"/jobs/{job_id}/status")).json()["files"]["a.pdf"]
    assert arquivo["contrato_id"] is None and arquivo["itens"] is None
