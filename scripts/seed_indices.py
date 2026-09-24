"""Carga inicial dos índices, pela mesma importação que a API usa.

Uso único, pela linha de comando; depois disso os usuários mantêm os índices
pela API (edição manual ou upload de arquivos).

    uv run python scripts/seed_indices.py                          # só a ANP
    uv run python scripts/seed_indices.py --igp-di igp_di.xlsx     # ANP e IGP-DI
    uv run python scripts/seed_indices.py --sem-anp --igp-di igp_di.xlsx

* ANP: o ``.xls`` padrão de preços semanais da ANP; por padrão
  ``data/precos-medios-ponderados-semanais-2013.xls``. Todos os produtos do
  arquivo são gravados; o cálculo consulta só o CAP 50/70. ``data/`` não é
  versionado: numa máquina nova, use ``--anp tests/fixtures/anp_semanal.xls``,
  a cópia versionada do arquivo oficial.
* IGP-DI: um arquivo no formato do template (``GET /api/v1/indices/igp-di/template``).

Os valores entram com ``origem = 'seed'``. Correções manuais já feitas pelos
usuários são preservadas: rodar o seed de novo não as desfaz.
"""

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import config, db  # noqa: E402
from app.services import importacao, indices_repo  # noqa: E402
from app.services.importadores import ArquivoInvalido  # noqa: E402

ARQUIVO_ANP = config.PROJECT_ROOT / "data" / "precos-medios-ponderados-semanais-2013.xls"


def _importar(rotulo: str, funcao, caminho: Path) -> None:
    resultado = funcao(caminho.read_bytes(), caminho.name, origem=indices_repo.ORIGEM_SEED)
    periodo = resultado["periodo"]
    print(
        f"[{rotulo}] {caminho.name}: {resultado['inseridos']} inseridos, "
        f"{len(resultado['atualizados'])} atualizados, {resultado['inalterados']} inalterados "
        f"({periodo['de']} a {periodo['ate']})"
    )
    if resultado["manuais_preservados"]:
        print(
            f"[{rotulo}] {resultado['manuais_preservados']} correção(ões) manual(is) "
            "preservada(s)"
        )
    for aviso in resultado["avisos"]:
        print(f"[{rotulo}] aviso: {aviso}")


def executar(anp: Path | None, igp_di: Path | None) -> int:
    """Importa os arquivos informados; 0 em sucesso, 1 no primeiro erro.

    Síncrono e sem abrir conexões: quem chama já abriu os pools e aplicou as
    migrações. Um arquivo recusado não grava nada (a importação é tudo ou nada).
    """
    etapas = []
    if anp is not None:
        etapas.append(("ANP", importacao.importar_anp, anp))
    if igp_di is not None:
        etapas.append(("IGP-DI", importacao.importar_igp_di, igp_di))

    for rotulo, funcao, caminho in etapas:
        if not caminho.exists():
            print(f"[{rotulo}] arquivo não encontrado: {caminho}", file=sys.stderr)
            return 1
        try:
            _importar(rotulo, funcao, caminho)
        except ArquivoInvalido as e:
            print(f"[{rotulo}] {caminho.name}: {e.mensagem}", file=sys.stderr)
            for erro in e.erros:
                print(f"  - {erro}", file=sys.stderr)
            return 1
        except indices_repo.IndiceInvalido as e:
            print(f"[{rotulo}] {caminho.name}: {e}", file=sys.stderr)
            return 1

    if igp_di is None:
        print(
            "[IGP-DI] nenhum arquivo informado. Baixe o template em "
            "GET /api/v1/indices/igp-di/template, preencha-o e rode de novo com "
            "--igp-di <arquivo>, ou importe-o pela API."
        )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Carga inicial dos índices (ANP e IGP-DI) pela importação da aplicação."
    )
    parser.add_argument(
        "--anp", type=Path, default=ARQUIVO_ANP,
        help=f".xls de preços semanais da ANP (padrão: {ARQUIVO_ANP})",
    )
    parser.add_argument("--sem-anp", action="store_true", help="não importa a ANP")
    parser.add_argument(
        "--igp-di", type=Path, default=None,
        help="arquivo no formato do template de IGP-DI",
    )
    args = parser.parse_args(argv)

    async def rodar() -> int:
        await db.open_pools()
        try:
            await db.apply_migrations()
            return await asyncio.to_thread(
                executar, None if args.sem_anp else args.anp, args.igp_di
            )
        finally:
            await db.close_pools()

    return asyncio.run(rodar())


if __name__ == "__main__":
    sys.exit(main())
