"""Migrações: o lock bloqueante (LOCK_MIGRATIONS) que protege contra dois
workers aplicando o schema ao mesmo tempo (deployment.md recomenda
``--workers 2``)."""

import asyncio

from app import db


async def test_migrations_lock_e_liberado_apos_aplicar():
    """``setup_storage`` já aplicou tudo; chamar de novo não deve deixar o
    lock preso (senão um segundo worker travaria para sempre)."""
    aplicado = await db.apply_migrations()
    assert aplicado == []

    async with db.acquire() as conn:
        cur = await conn.execute(
            "SELECT pg_try_advisory_lock(%s) AS got", (db.LOCK_MIGRATIONS,)
        )
        got = (await cur.fetchone())["got"]
        if got:
            await conn.execute("SELECT pg_advisory_unlock(%s)", (db.LOCK_MIGRATIONS,))
    assert got is True


async def test_migrations_espera_o_lock_ser_liberado():
    """Um segundo worker (aqui, simulado por quem já detém o lock numa outra
    conexão) tem de esperar — não seguir e ler ``schema_migrations`` antes do
    primeiro terminar, que é o que ``pg_try_advisory_lock`` (não bloqueante)
    permitiria."""
    async with db.acquire() as conn:
        await conn.execute("SELECT pg_advisory_lock(%s)", (db.LOCK_MIGRATIONS,))
        await conn.commit()

        tarefa = asyncio.create_task(db.apply_migrations())
        await asyncio.sleep(0.2)
        assert not tarefa.done()  # ainda esperando o lock, preso pelo teste

        await conn.execute("SELECT pg_advisory_unlock(%s)", (db.LOCK_MIGRATIONS,))
        await conn.commit()

        resultado = await asyncio.wait_for(tarefa, timeout=5)
    assert resultado == []  # nada pendente: setup_storage já aplicou tudo
