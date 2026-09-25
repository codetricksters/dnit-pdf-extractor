"""Deixa o banco de teste no estado inicial dos testes ponta a ponta.

Chamado pelo ``webServer`` de ``frontend/playwright.config.ts`` antes de subir
o servidor, com ``DATABASE_URL`` apontando para ``dnit_test``:

    DATABASE_URL=postgresql://dnit:dnit@localhost:5433/dnit_test \\
        uv run python scripts/preparar_e2e.py

Zera o schema, aplica as migrações, importa os índices de ``tests/fixtures/``,
grava o contrato fictício como um PDF processado e deixa no catálogo só dois
produtos com um código cada. Recusa qualquer banco cujo nome não termine em
``_test``: o primeiro passo apaga tudo.
"""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import config, db  # noqa: E402
from app.services import catalogo, importacao, indices_repo, template_repo  # noqa: E402
from app.services.file_processor import _persistir  # noqa: E402

FIXTURES = config.PROJECT_ROOT / "tests" / "fixtures"

PRODUTOS = (
    ("Aquisição de CAP 50/70", "CAP", "60112"),
    ("Aquisição de Emulsão RR-1C", "EMULSOES", "29083"),
)


def _preparar() -> None:
    for funcao, arquivo in (
        (importacao.importar_anp, "anp_semanal.xls"),
        (importacao.importar_igp_di, "igp_di.xlsx"),
    ):
        caminho = FIXTURES / arquivo
        funcao(caminho.read_bytes(), caminho.name, origem=indices_repo.ORIGEM_SEED)

    ficticio = json.loads((FIXTURES / "contrato_ficticio.json").read_text(encoding="utf-8"))
    for medicao in ficticio["arquivos"]:
        _persistir({"header": ficticio["header"], "rows": medicao["rows"]}, medicao["arquivo"], "e2e")

    with db.acquire_sync() as conn:
        conn.execute("DELETE FROM produto_codigo")
        conn.execute("DELETE FROM produto")
    for ordem, (descricao, familia, codigo) in enumerate(PRODUTOS, start=1):
        produto_id = catalogo.criar_produto(descricao, familia, ordem)
        catalogo.registrar_codigo(codigo, produto_id)

    template_repo.garantir_semente()


async def _rodar() -> int:
    nome = config.DATABASE_URL.rsplit("/", 1)[-1].split("?", 1)[0]
    if not nome.endswith("_test"):
        print(f"preparar_e2e: recusado, o banco '{nome}' não é de teste.", file=sys.stderr)
        return 1
    await db.open_pools()
    try:
        async with db.acquire() as conn:
            await conn.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public")
        await db.apply_migrations()
        await asyncio.to_thread(_preparar)
    finally:
        await db.close_pools()
    print(f"preparar_e2e: {nome} pronto.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(_rodar()))
