"""Database backups, driven from the interface.

Everything the app owns now lives in PostgreSQL — índices, contracts, measurement
items and the export templates — so one dump is the whole state. The user runs in
Docker and cannot comfortably reach container files, so generating, listing,
downloading, restoring and deleting are all app operations rather than shell
ones.

``pg_dump -Fc`` (custom format, compressed) is used instead of plain SQL because
it is what ``pg_restore`` can inspect before applying: a file the user uploads is
verified with ``pg_restore --list`` before anything is written.

Scheduling reuses the periodic task already in ``app/main.py``'s lifespan rather
than adding APScheduler or cron, guarded by an advisory lock — production runs
``--workers 2`` and every worker would otherwise dump on its own.
"""

import logging
import os
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from .. import config

logger = logging.getLogger(__name__)

# Dumping the whole database takes seconds at this size; the ceiling is there so
# a hung child process cannot block the scheduled task forever.
TIMEOUT = 600

_NOME_SEGURO = re.compile(r"^[A-Za-z0-9._-]+\.dump$")


class BackupIndisponivel(Exception):
    """Backups cannot run, or the file offered is not usable."""


def _binario(nome: str) -> str:
    caminho = shutil.which(nome, path=config.PG_BIN) if config.PG_BIN else None
    caminho = caminho or shutil.which(nome)
    if caminho is None:
        raise BackupIndisponivel(
            f"'{nome}' não está instalado neste ambiente. O backup depende do "
            "postgresql-client, presente na imagem Docker da aplicação."
        )
    return caminho


def _versao_cliente(binario: str) -> int:
    """Major version of a client binary, from ``--version``."""
    saida = subprocess.run(
        [binario, "--version"], capture_output=True, text=True, timeout=30
    ).stdout
    encontrado = re.search(r"(\d+)", saida)
    if encontrado is None:
        raise BackupIndisponivel(f"Não foi possível ler a versão de '{binario}'.")
    return int(encontrado.group(1))


def _versao_servidor() -> int:
    from ..db import acquire_sync

    with acquire_sync() as conn:
        numero = conn.execute("SHOW server_version_num").fetchone()
        valor = next(iter(numero.values())) if isinstance(numero, dict) else numero[0]
    return int(valor) // 10000


def verificar_compatibilidade() -> None:
    """Refuse to work with a client newer than the server.

    ``pg_dump`` writes directives based on its *own* version, so a newer client
    produces a dump the server cannot read back (PostgreSQL 17 emits
    ``SET transaction_timeout``, unknown to 16, and the restore aborts). Checked
    before dumping, because the failure would otherwise only appear on the day
    the user needs the backup — when it is too late.
    """
    cliente = _versao_cliente(_binario("pg_dump"))
    servidor = _versao_servidor()
    if cliente > servidor:
        raise BackupIndisponivel(
            f"O cliente do PostgreSQL é da versão {cliente} e o servidor é da "
            f"versão {servidor}. Um backup gerado por um cliente mais novo não "
            f"pode ser restaurado no servidor. Instale o postgresql-client-"
            f"{servidor} ou aponte PG_BIN para ele."
        )


def _diretorio() -> Path:
    config.BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    return config.BACKUP_DIR


def _caminho(nome: str) -> Path:
    """Resolve a backup name to a path, rejecting anything but a plain name.

    The name arrives from the interface, so a traversal like ``../../etc`` must
    not resolve outside the backup directory.
    """
    if not _NOME_SEGURO.match(nome):
        raise BackupIndisponivel(f"Nome de backup inválido: '{nome}'.")
    return _diretorio() / nome


def caminho_de(nome: str) -> Path:
    """Where a backup with this name lives, for callers that serve the file."""
    return _caminho(nome)


def _executar(comando: list[str], erro: str) -> subprocess.CompletedProcess:
    resultado = subprocess.run(
        comando,
        capture_output=True,
        text=True,
        timeout=TIMEOUT,
        # Silences the password prompt: without it a missing credential turns
        # into a hang instead of an error.
        env={**os.environ, "PGCONNECT_TIMEOUT": "10"},
    )
    if resultado.returncode != 0:
        saida = (resultado.stderr or resultado.stdout or "").strip()
        raise BackupIndisponivel(f"{erro}\n{saida}")
    return resultado


def gerar(motivo: str = "manual") -> Path:
    """Write a new dump and apply retention. Returns its path."""
    pg_dump = _binario("pg_dump")
    verificar_compatibilidade()
    marca = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    destino = _diretorio() / f"{marca}-{motivo}.dump"

    _executar(
        [pg_dump, "-Fc", "--no-owner", "--no-privileges",
         "-d", config.DATABASE_URL, "-f", str(destino)],
        "Falha ao gerar o backup do banco.",
    )
    aplicar_retencao()
    logger.info("Backup gerado: %s", destino.name)
    return destino


def listar() -> list[dict]:
    """Existing backups, most recent first."""
    if not config.BACKUP_DIR.exists():
        return []
    arquivos = []
    for caminho in config.BACKUP_DIR.glob("*.dump"):
        info = caminho.stat()
        arquivos.append(
            {
                "nome": caminho.name,
                "tamanho": info.st_size,
                "criado_em": datetime.fromtimestamp(info.st_mtime, timezone.utc),
            }
        )
    return sorted(arquivos, key=lambda a: a["criado_em"], reverse=True)


def aplicar_retencao() -> list[str]:
    """Keep only the newest ``BACKUP_RETENTION`` dumps. Returns what went."""
    excedentes = listar()[config.BACKUP_RETENTION:]
    for backup in excedentes:
        _caminho(backup["nome"]).unlink(missing_ok=True)
    if excedentes:
        logger.info(
            "Retenção de backups: %d arquivo(s) removido(s).", len(excedentes)
        )
    return [b["nome"] for b in excedentes]


def excluir(nome: str) -> None:
    caminho = _caminho(nome)
    if not caminho.exists():
        raise BackupIndisponivel(f"Backup '{nome}' não encontrado.")
    caminho.unlink()


def validar(caminho: Path) -> None:
    """Check the file is a readable custom-format dump.

    Run before restoring so an invalid or truncated upload is refused *before*
    anything in the database is touched.
    """
    pg_restore = _binario("pg_restore")
    if not caminho.exists():
        raise BackupIndisponivel(f"Arquivo não encontrado: {caminho.name}.")
    _executar(
        [pg_restore, "--list", str(caminho)],
        f"'{caminho.name}' não é um backup válido do PostgreSQL.",
    )


def receber_envio(nome: str, conteudo: bytes) -> Path:
    """Store an uploaded dump, validating it before keeping it."""
    seguro = re.sub(r"[^A-Za-z0-9._-]", "_", nome)
    if not seguro.endswith(".dump"):
        seguro += ".dump"
    marca = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    destino = _diretorio() / f"{marca}-enviado-{seguro}"
    destino.write_bytes(conteudo)
    try:
        validar(destino)
    except BackupIndisponivel:
        destino.unlink(missing_ok=True)
        raise
    return destino


def restaurar(nome: str, confirmacao: str) -> dict:
    """Replace the current database contents with a backup's.

    Destructive and hard to undo, so: the caller must echo the backup's name
    back as *confirmacao*; the file is validated first; and a dump of the current
    state is taken before anything is dropped, so the operation can be walked
    back.
    """
    if confirmacao != nome:
        raise BackupIndisponivel(
            "Confirme a restauração digitando o nome exato do backup."
        )

    caminho = _caminho(nome)
    validar(caminho)

    pg_restore = _binario("pg_restore")
    seguranca = gerar(motivo="antes-de-restaurar")

    _executar(
        [pg_restore, "--clean", "--if-exists", "--no-owner", "--no-privileges",
         # Errors would otherwise be reported one by one and leave the database
         # half-restored; this makes the restore all-or-nothing.
         "--single-transaction",
         "-d", config.DATABASE_URL, str(caminho)],
        f"Falha ao restaurar o backup '{nome}'. O banco não foi alterado; o "
        f"estado anterior também está salvo em '{seguranca.name}'.",
    )
    logger.warning("Banco restaurado a partir de %s", nome)
    return {"restaurado": nome, "seguranca": seguranca.name}


def precisa_de_backup() -> bool:
    """Whether the configured interval has elapsed since the last dump."""
    backups = listar()
    if not backups:
        return True
    idade = datetime.now(timezone.utc) - backups[0]["criado_em"]
    return idade.total_seconds() >= config.BACKUP_INTERVAL_HOURS * 3600


def executar_agendado() -> Path | None:
    """The scheduled task's entry point. Never raises: a failed backup must not
    take down the loop that also cleans up stale jobs."""
    try:
        if not precisa_de_backup():
            return None
        return gerar(motivo="automatico")
    except Exception:
        logger.exception("Backup automático falhou.")
        return None
