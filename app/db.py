"""PostgreSQL access: connection pools, migrations and advisory locks.

Two pools are exposed because the application runs in two execution models:
FastAPI is async, while the Dash dashboard runs synchronously under
``a2wsgi.WSGIMiddleware``. ``psycopg`` 3 serves both with one driver and one
SQL dialect, so the split is only in the pool, never in the queries.

Config values are read through the ``config`` module (not imported by name) so
that tests can repoint ``DATABASE_URL`` before the pools are opened.
"""

import logging
from contextlib import asynccontextmanager, contextmanager

from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool, ConnectionPool

from . import config

logger = logging.getLogger(__name__)

# Keys for pg_advisory_lock. Arbitrary but must stay stable across releases:
# changing one lets two workers run the same task concurrently.
LOCK_CLEANUP = 8474001
LOCK_BACKUP = 8474002

_apool: AsyncConnectionPool | None = None
_spool: ConnectionPool | None = None


async def open_pools() -> None:
    """Open both pools. Safe to call once, from the app lifespan."""
    global _apool, _spool
    if _apool is None:
        _apool = AsyncConnectionPool(
            config.DATABASE_URL,
            min_size=1,
            max_size=10,
            kwargs={"row_factory": dict_row},
            open=False,
        )
        await _apool.open(wait=True, timeout=30)
    if _spool is None:
        _spool = ConnectionPool(
            config.DATABASE_URL,
            min_size=1,
            max_size=5,
            kwargs={"row_factory": dict_row},
            open=False,
        )
        _spool.open(wait=True, timeout=30)


async def close_pools() -> None:
    global _apool, _spool
    if _apool is not None:
        await _apool.close()
        _apool = None
    if _spool is not None:
        _spool.close()
        _spool = None


@asynccontextmanager
async def acquire():
    """Async connection from the pool, committed on clean exit."""
    if _apool is None:
        raise RuntimeError("Database pool is not open; call open_pools() first.")
    async with _apool.connection() as conn:
        yield conn


@contextmanager
def acquire_sync():
    """Sync connection from the pool, for the Dash dashboard."""
    if _spool is None:
        raise RuntimeError("Database pool is not open; call open_pools() first.")
    with _spool.connection() as conn:
        yield conn


@asynccontextmanager
async def advisory_lock(key: int):
    """Yield True only to the caller that wins the session-level lock.

    ``pg_try_advisory_lock`` never waits, so a worker that loses simply skips
    the task. Production runs ``--workers 2`` (see deployment.md) and every
    worker runs the same periodic loop; without this, scheduled work would be
    duplicated once per worker.

    The lock is held for the lifetime of the connection, so it must be taken on
    a dedicated connection rather than one shared with the task's own queries.
    """
    if _apool is None:
        raise RuntimeError("Database pool is not open; call open_pools() first.")
    async with _apool.connection() as conn:
        cur = await conn.execute("SELECT pg_try_advisory_lock(%s) AS got", (key,))
        got = (await cur.fetchone())["got"]
        try:
            yield got
        finally:
            if got:
                await conn.execute("SELECT pg_advisory_unlock(%s)", (key,))


_MIGRATIONS_TABLE = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    filename   TEXT PRIMARY KEY,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
)
"""


async def apply_migrations() -> list[str]:
    """Apply pending ``migrations/*.sql`` in filename order.

    Each file runs in its own transaction and is recorded in
    ``schema_migrations``, so a failure leaves the database at the last good
    migration instead of half-applied.
    """
    applied: list[str] = []
    files = sorted(p for p in config.MIGRATIONS_PATH.glob("*.sql"))
    async with acquire() as conn:
        await conn.execute(_MIGRATIONS_TABLE)
        cur = await conn.execute("SELECT filename FROM schema_migrations")
        done = {r["filename"] for r in await cur.fetchall()}

    for path in files:
        if path.name in done:
            continue
        sql = path.read_text(encoding="utf-8")
        async with acquire() as conn:
            await conn.execute(sql)
            await conn.execute(
                "INSERT INTO schema_migrations (filename) VALUES (%s)", (path.name,)
            )
        applied.append(path.name)
        logger.info("Applied migration %s", path.name)
    return applied
