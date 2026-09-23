"""Download route for the Reequilíbrio spreadsheet.

The contract number is a query parameter, not a path segment: numbers look like
``15 00716/2022`` — the slash would split into path segments and the space would
have to be escaped.
"""

import asyncio
import re

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from ..services import template_repo
from ..services.reequilibrio_export import ExportacaoImpossivel, exportar
from ..services.xlsx_drawings import TemplateInvalido

router = APIRouter(prefix="/reequilibrio", tags=["reequilibrio"])


def _nome_do_arquivo(numero: str) -> str:
    return "Reequilibrio - " + re.sub(r"[^A-Za-z0-9._-]+", "-", numero) + ".xlsx"


@router.get("/planilha")
async def baixar_planilha(contrato: str):
    try:
        template = await asyncio.to_thread(template_repo.conteudo_ativo)
        resultado = await asyncio.to_thread(exportar, contrato, template)
    except (ExportacaoImpossivel, TemplateInvalido) as e:
        # 422 with the service's own message: it names exactly what the user has
        # to register or publish before the spreadsheet can be produced.
        raise HTTPException(422, str(e)) from e

    return Response(
        content=resultado.conteudo,
        media_type=(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ),
        headers={
            "Content-Disposition": (
                f'attachment; filename="{_nome_do_arquivo(contrato)}"'
            ),
            # Read by the dashboard to show what was left out without having to
            # parse the spreadsheet it just downloaded.
            "X-Avisos": " | ".join(resultado.avisos),
        },
    )
