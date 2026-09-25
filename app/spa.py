"""Serve o frontend React construído em ``frontend/dist``.

Qualquer GET que nenhuma rota do backend atendeu chega aqui: um arquivo real do
build é devolvido como está, e o resto recebe ``index.html`` para o roteador do
React decidir a tela. Os prefixos do backend nunca caem no SPA — um caminho
errado em ``/api`` tem de ser 404, não uma página HTML.

Sem ``dist/`` (checkout novo, suíte de testes), ``/`` responde uma página que
explica como gerar o build: o backend não depende de Node para subir.
"""

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, HTMLResponse

DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"

RESERVADOS = frozenset(
    {"api", "jobs", "admin", "reequilibrio", "static", "dashboard", "docs", "redoc", "openapi.json"}
)

SEM_BUILD = """<!doctype html>
<html lang="pt-BR">
<head><meta charset="utf-8"><title>DNIT · frontend não construído</title></head>
<body>
<h1>Frontend não construído</h1>
<p>Gere o build do frontend e recarregue a página:</p>
<pre>cd frontend
npm ci
npm run build</pre>
<p>A API continua disponível em <a href="/docs">/docs</a>.</p>
</body>
</html>
"""

router = APIRouter(include_in_schema=False)


@router.get("/{caminho:path}")
async def spa(caminho: str):
    if caminho.split("/", 1)[0] in RESERVADOS:
        raise HTTPException(404)
    dist = DIST.resolve()
    indice = dist / "index.html"
    if not indice.is_file():
        return HTMLResponse(SEM_BUILD)
    if caminho:
        alvo = (dist / caminho).resolve()
        if alvo.is_relative_to(dist) and alvo.is_file():
            return FileResponse(alvo)
    # index.html não pode ficar em cache: é ele que aponta para os assets com
    # hash do build atual.
    return FileResponse(indice, headers={"Cache-Control": "no-cache"})
