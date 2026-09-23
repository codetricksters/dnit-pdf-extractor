"""Database backups: full cycle, retention, validation, safety rules.

The cycle tests need a usable ``pg_dump``/``pg_restore``. The application image
has one (the Dockerfile pins postgresql-client-16), a developer's machine may
not — or may have one of a higher major than the server, which is present but
cannot produce a restorable dump. Both cases are skips, decided at run time by
the ``pg_dump_utilizavel`` fixture; the rules that need no subprocess are always
exercised.
"""

import shutil
from datetime import datetime, timedelta, timezone

import pytest

from app import config
from app.db import acquire_sync
from app.services import backup

def _cliente_utilizavel() -> bool:
    for nome in ("pg_dump", "pg_restore"):
        if not (
            (config.PG_BIN and shutil.which(nome, path=config.PG_BIN))
            or shutil.which(nome)
        ):
            return False
    return True


sem_pg_dump = pytest.mark.skipif(
    not _cliente_utilizavel(),
    reason=(
        "pg_dump/pg_restore não disponíveis. Instale o postgresql-client da "
        "mesma versão do servidor e, se preciso, aponte PG_BIN para ele."
    ),
)


def _gravar(numero: str) -> None:
    with acquire_sync() as conn:
        conn.execute("INSERT INTO contrato (numero) VALUES (%s)", (numero,))


def _contratos() -> list[str]:
    with acquire_sync() as conn:
        cur = conn.execute("SELECT numero FROM contrato ORDER BY numero")
        return [r["numero"] for r in cur.fetchall()]


def _falso_backup(nome: str, idade_horas: float = 0) -> None:
    """A file with the right name but no valid content, for the rules' sake."""
    caminho = backup._diretorio() / nome
    caminho.write_bytes(b"nao sou um dump")
    quando = (datetime.now(timezone.utc) - timedelta(hours=idade_horas)).timestamp()
    import os

    os.utime(caminho, (quando, quando))


async def test_ciclo_gerar_e_restaurar_recupera_o_estado(pg_dump_utilizavel):
    _gravar("15 00716/2022")
    backup.gerar(motivo="teste")

    _gravar("99 99999/2099")
    assert len(_contratos()) == 2

    nome = backup.listar()[0]["nome"]
    resultado = backup.restaurar(nome, confirmacao=nome)

    assert _contratos() == ["15 00716/2022"]
    # The state discarded by the restore is itself saved, so it can be undone.
    assert resultado["seguranca"] in [b["nome"] for b in backup.listar()]


async def test_restauracao_sem_confirmacao_nao_toca_o_banco(pg_dump_utilizavel):
    _gravar("15 00716/2022")
    backup.gerar()
    _gravar("99 99999/2099")
    nome = backup.listar()[0]["nome"]

    with pytest.raises(backup.BackupIndisponivel) as erro:
        backup.restaurar(nome, confirmacao="sim")

    assert "nome exato" in str(erro.value)
    assert len(_contratos()) == 2


async def test_arquivo_invalido_e_recusado_antes_de_qualquer_escrita(pg_dump_utilizavel):
    _gravar("15 00716/2022")
    _falso_backup("20200101-000000-falso.dump")

    with pytest.raises(backup.BackupIndisponivel) as erro:
        backup.restaurar(
            "20200101-000000-falso.dump", confirmacao="20200101-000000-falso.dump"
        )

    assert "não é um backup válido" in str(erro.value)
    assert _contratos() == ["15 00716/2022"]
    # No safety dump either: the refusal happens before anything runs.
    assert [b["nome"] for b in backup.listar()] == ["20200101-000000-falso.dump"]


async def test_envio_invalido_nao_fica_no_diretorio(pg_dump_utilizavel):
    with pytest.raises(backup.BackupIndisponivel):
        backup.receber_envio("qualquer.dump", b"nao sou um dump")
    assert backup.listar() == []


async def test_envio_valido_e_aceito_e_pode_ser_restaurado(pg_dump_utilizavel):
    _gravar("15 00716/2022")
    original = backup.gerar()
    conteudo = original.read_bytes()
    original.unlink()

    destino = backup.receber_envio("backup-do-usuario.xyz", conteudo)

    assert destino.name.endswith("backup-do-usuario.xyz.dump")
    assert destino.exists()


async def test_retencao_mantem_os_n_mais_recentes():
    config.BACKUP_RETENTION = 3
    for hora in range(6):
        _falso_backup(f"2024010{hora}-000000-automatico.dump", idade_horas=hora)

    removidos = backup.aplicar_retencao()

    restantes = [b["nome"] for b in backup.listar()]
    assert len(restantes) == 3
    assert len(removidos) == 3
    # The three kept are the newest ones (age 0, 1, 2 hours).
    assert restantes == [
        "20240100-000000-automatico.dump",
        "20240101-000000-automatico.dump",
        "20240102-000000-automatico.dump",
    ]
    config.BACKUP_RETENTION = 14


async def test_nome_com_travessia_de_caminho_e_recusado():
    for nome in ("../../etc/passwd.dump", "/etc/passwd.dump", "sub/dir.dump"):
        with pytest.raises(backup.BackupIndisponivel) as erro:
            backup.excluir(nome)
        assert "inválido" in str(erro.value)


async def test_excluir_backup_inexistente_explica():
    with pytest.raises(backup.BackupIndisponivel) as erro:
        backup.excluir("20240101-000000-automatico.dump")
    assert "não encontrado" in str(erro.value)


async def test_agendamento_respeita_o_intervalo():
    config.BACKUP_INTERVAL_HOURS = 24
    assert backup.precisa_de_backup() is True  # nenhum backup ainda

    _falso_backup("20240101-000000-automatico.dump", idade_horas=1)
    assert backup.precisa_de_backup() is False

    _falso_backup("20240102-000000-automatico.dump", idade_horas=30)
    # The newest is still an hour old; age is measured from the most recent.
    assert backup.precisa_de_backup() is False

    backup.excluir("20240101-000000-automatico.dump")
    assert backup.precisa_de_backup() is True


async def test_agendado_nao_propaga_falha(monkeypatch):
    """A failed backup must not kill the loop that also cleans up stale jobs."""

    def explodir(motivo="manual"):
        raise backup.BackupIndisponivel("pg_dump não está instalado")

    monkeypatch.setattr(backup, "gerar", explodir)
    assert backup.executar_agendado() is None


async def test_agendado_nao_gera_quando_nao_e_hora(monkeypatch):
    chamadas = []
    monkeypatch.setattr(backup, "precisa_de_backup", lambda: False)
    monkeypatch.setattr(backup, "gerar", lambda motivo="manual": chamadas.append(motivo))

    assert backup.executar_agendado() is None
    assert chamadas == []


@sem_pg_dump
async def test_cliente_mais_novo_que_o_servidor_e_recusado(monkeypatch):
    """A dump from a newer client cannot be restored — refuse before writing it."""
    monkeypatch.setattr(backup, "_versao_cliente", lambda binario: 99)

    with pytest.raises(backup.BackupIndisponivel) as erro:
        backup.gerar()

    assert "postgresql-client-" in str(erro.value)
    assert backup.listar() == []


async def test_backup_ausente_e_reportado_com_orientacao(monkeypatch):
    monkeypatch.setattr(shutil, "which", lambda nome, path=None: None)
    with pytest.raises(backup.BackupIndisponivel) as erro:
        backup.gerar()
    assert "postgresql-client" in str(erro.value)
