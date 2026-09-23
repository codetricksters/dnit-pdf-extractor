"""Administration routes: export templates and database backups.

The application runs in Docker and the user has no comfortable access to
container files, so every file operation these features need — uploading and
downloading a template, generating, downloading and restoring a backup — is
exposed here and driven from the dashboard.

The blocking work (``pg_dump``, ``pg_restore``, opening the workbook to validate
it) runs in a thread: these are synchronous services and would otherwise hold the
event loop for the duration of a dump.
"""

import asyncio

from fastapi import APIRouter, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response

from ..services import backup, template_repo
from ..services.xlsx_drawings import TemplateInvalido

router = APIRouter(prefix="/admin", tags=["admin"])


def _erro(e: Exception) -> HTTPException:
    """Turn a refusal into a 422 the interface can show verbatim.

    The messages are written for the user — they say what is wrong with the file
    or why the operation was refused — so they are passed through instead of
    being replaced by a generic error.
    """
    return HTTPException(422, str(e))


@router.get("/templates")
async def listar_templates():
    return await asyncio.to_thread(template_repo.listar)


@router.post("/templates")
async def enviar_template(
    arquivo: UploadFile,
    observacao: str | None = Form(None),
    ativar: bool = Form(True),
):
    conteudo = await arquivo.read()
    try:
        template_id = await asyncio.to_thread(
            template_repo.salvar,
            arquivo.filename or "template.xlsx",
            conteudo,
            observacao,
            ativar,
        )
    except TemplateInvalido as e:
        raise _erro(e) from e
    return {"id": template_id, "ativo": ativar}


@router.get("/templates/{template_id}/download")
async def baixar_template(template_id: int):
    template = await asyncio.to_thread(template_repo.buscar, template_id)
    if template is None:
        raise HTTPException(404, "Template não encontrado.")
    return Response(
        content=bytes(template["arquivo"]),
        media_type=(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ),
        headers={
            "Content-Disposition": f'attachment; filename="{template["nome"]}"'
        },
    )


@router.post("/templates/{template_id}/ativar")
async def ativar_template(template_id: int):
    if not await asyncio.to_thread(template_repo.ativar, template_id):
        raise HTTPException(404, "Template não encontrado.")
    return {"ativo": template_id}


@router.delete("/templates/{template_id}")
async def excluir_template(template_id: int):
    try:
        await asyncio.to_thread(template_repo.excluir, template_id)
    except TemplateInvalido as e:
        raise _erro(e) from e
    return {"excluido": template_id}


@router.get("/backups")
async def listar_backups():
    return await asyncio.to_thread(backup.listar)


@router.post("/backups")
async def gerar_backup():
    try:
        caminho = await asyncio.to_thread(backup.gerar, "manual")
    except backup.BackupIndisponivel as e:
        raise _erro(e) from e
    return {"nome": caminho.name, "tamanho": caminho.stat().st_size}


@router.get("/backups/{nome}/download")
async def baixar_backup(nome: str):
    try:
        caminho = backup.caminho_de(nome)
    except backup.BackupIndisponivel as e:
        raise _erro(e) from e
    if not caminho.exists():
        raise HTTPException(404, f"Backup '{nome}' não encontrado.")
    return FileResponse(
        caminho, media_type="application/octet-stream", filename=nome
    )


@router.post("/backups/upload")
async def enviar_backup(arquivo: UploadFile):
    conteudo = await arquivo.read()
    try:
        caminho = await asyncio.to_thread(
            backup.receber_envio, arquivo.filename or "backup.dump", conteudo
        )
    except backup.BackupIndisponivel as e:
        raise _erro(e) from e
    return {"nome": caminho.name}


@router.post("/backups/{nome}/restaurar")
async def restaurar_backup(nome: str, confirmacao: str = Form(...)):
    """Destructive: replaces the whole database.

    *confirmacao* must repeat the backup's name — the service checks it again, so
    a caller that skips the dashboard's own confirmation still cannot restore by
    accident.
    """
    try:
        return await asyncio.to_thread(backup.restaurar, nome, confirmacao)
    except backup.BackupIndisponivel as e:
        raise _erro(e) from e


@router.delete("/backups/{nome}")
async def excluir_backup(nome: str):
    try:
        await asyncio.to_thread(backup.excluir, nome)
    except backup.BackupIndisponivel as e:
        raise _erro(e) from e
    return {"excluido": nome}
