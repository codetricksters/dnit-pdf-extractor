"""Admin routes: the interface's only access to template and backup files."""

from pathlib import Path

import pytest

from app.services import backup, template_repo

TEMPLATE = Path("app/templates_xlsx/reequilibrio_template.xlsx")


@pytest.fixture
def valido() -> bytes:
    return TEMPLATE.read_bytes()


async def test_enviar_template_valido_e_ativa(client, valido):
    r = await client.post(
        "/admin/templates",
        files={"arquivo": ("meu.xlsx", valido)},
        data={"observacao": "revisado"},
    )
    assert r.status_code == 200
    assert template_repo.ativo()["id"] == r.json()["id"]

    lista = (await client.get("/admin/templates")).json()
    assert [t["nome"] for t in lista] == ["meu.xlsx"]
    # The bytes are not in the listing: a template is megabytes of XML.
    assert "arquivo" not in lista[0]


async def test_template_invalido_explica_o_motivo(client):
    r = await client.post(
        "/admin/templates", files={"arquivo": ("meu.xlsx", b"nao sou planilha")}
    )
    assert r.status_code == 422
    assert ".xlsx" in r.json()["detail"]


async def test_baixar_template_devolve_o_arquivo_original(client, valido):
    template_id = template_repo.salvar("meu.xlsx", valido)
    r = await client.get(f"/admin/templates/{template_id}/download")
    assert r.status_code == 200
    assert r.content == valido
    assert "meu.xlsx" in r.headers["content-disposition"]


async def test_ativar_e_excluir_template(client, valido):
    primeiro = template_repo.salvar("um.xlsx", valido, ativar=True)
    segundo = template_repo.salvar("dois.xlsx", valido, ativar=True)

    assert (await client.post(f"/admin/templates/{primeiro}/ativar")).status_code == 200
    assert template_repo.ativo()["id"] == primeiro

    # The active one is protected; the other can go.
    recusa = await client.delete(f"/admin/templates/{primeiro}")
    assert recusa.status_code == 422
    assert "ativo" in recusa.json()["detail"]
    assert (await client.delete(f"/admin/templates/{segundo}")).status_code == 200


async def test_template_inexistente_e_404(client):
    assert (await client.get("/admin/templates/999/download")).status_code == 404
    assert (await client.post("/admin/templates/999/ativar")).status_code == 404


async def test_gerar_listar_e_baixar_backup(client, pg_dump_utilizavel):
    r = await client.post("/admin/backups")
    assert r.status_code == 200
    nome = r.json()["nome"]

    lista = (await client.get("/admin/backups")).json()
    assert [b["nome"] for b in lista] == [nome]

    download = await client.get(f"/admin/backups/{nome}/download")
    assert download.status_code == 200
    assert download.content == backup.caminho_de(nome).read_bytes()


async def test_restaurar_exige_confirmacao_pela_rota(client, pg_dump_utilizavel):
    nome = backup.gerar().name
    r = await client.post(
        f"/admin/backups/{nome}/restaurar", data={"confirmacao": "sim"}
    )
    assert r.status_code == 422
    assert "nome exato" in r.json()["detail"]


async def test_backup_inexistente_e_404(client):
    r = await client.get("/admin/backups/20240101-000000-manual.dump/download")
    assert r.status_code == 404


async def test_nome_de_backup_fora_do_padrao_e_recusado(client):
    """Only a plain dump name resolves to a path.

    A name with separators never even reaches the handler — the router has no
    route for the extra segments. The client normalises ``..`` before sending,
    so the path lands outside ``/admin`` entirely; the only route left that
    matches it there is the SPA catch-all's GET, which makes a DELETE to it
    405 (path exists, wrong method) rather than 404 — still never touching the
    backup service. Anything else outside the allowed characters is refused by
    the service.
    """
    assert (await client.delete("/admin/backups/../../etc/passwd.dump")).status_code == 405

    r = await client.delete("/admin/backups/passwd$;.dump")
    assert r.status_code == 422
    assert "inválido" in r.json()["detail"]
