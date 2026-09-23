"""Reading and writing the price indices the users maintain.

Synchronous throughout: the Dash dashboard — the main consumer — runs
synchronously under ``a2wsgi``, and the queries are short lookups. Async callers
should wrap these in ``asyncio.to_thread`` rather than duplicating each query in
two flavours.
"""

from datetime import date
from decimal import Decimal

from ..db import acquire_sync
from .delta_p import ANP_PRODUTO_CAP, INDICE_IGP_DI, inicio_do_mes

# Regions the ANP publishes. Stored as plain text so an unforeseen region is a
# row rather than a migration; this list only drives the UI.
REGIOES = ("Norte", "Nordeste", "Centro-Oeste", "Sul", "Sudeste", "Brasil")


def _dia_de_referencia(mes: date) -> date:
    """The 15th of *mes*.

    The ANP publishes weekly ranges, so a month has no single price. The rule
    taken from the reference workbook is: use the week that contains the 15th.
    Verified against Dec-21, Dec-22 and Jan-23, which reproduce 4.02073,
    3.71611 and 3.28568 exactly.
    """
    return inicio_do_mes(mes).replace(day=15)


class FonteBanco:
    """``FonteIndices`` backed by PostgreSQL, with a per-instance cache.

    A single export calls ΔP once per product per month, and the base month is
    the same on every line, so the same rows would otherwise be fetched dozens
    of times. The cache lives as long as the instance — create a fresh one per
    export so that newly entered indices are picked up.
    """

    def __init__(self) -> None:
        self._precos: dict[tuple[str, str, date], Decimal | None] = {}
        self._indices: dict[tuple[str, date], Decimal | None] = {}

    def preco_anp(self, produto: str, regiao: str, mes: date) -> Decimal | None:
        chave = (produto, regiao, inicio_do_mes(mes))
        if chave not in self._precos:
            self._precos[chave] = buscar_preco_anp(produto, regiao, mes)
        return self._precos[chave]

    def indice_mensal(self, indice: str, mes: date) -> Decimal | None:
        chave = (indice, inicio_do_mes(mes))
        if chave not in self._indices:
            self._indices[chave] = buscar_indice_mensal(indice, mes)
        return self._indices[chave]


def buscar_preco_anp(produto: str, regiao: str, mes: date) -> Decimal | None:
    dia = _dia_de_referencia(mes)
    with acquire_sync() as conn:
        cur = conn.execute(
            "SELECT preco FROM anp_preco_semanal "
            "WHERE produto = %s AND regiao = %s "
            "AND vigencia_inicio <= %s AND vigencia_fim >= %s "
            "ORDER BY vigencia_inicio DESC LIMIT 1",
            (produto, regiao, dia, dia),
        )
        row = cur.fetchone()
    return row["preco"] if row else None


def buscar_indice_mensal(indice: str, mes: date) -> Decimal | None:
    with acquire_sync() as conn:
        cur = conn.execute(
            "SELECT valor FROM indice_mensal WHERE indice = %s AND mes_ref = %s",
            (indice, inicio_do_mes(mes)),
        )
        row = cur.fetchone()
    return row["valor"] if row else None


def gravar_precos_anp(registros: list[dict]) -> int:
    """Insert or update weekly ANP prices.

    Each record needs ``produto``, ``vigencia_inicio``, ``vigencia_fim``,
    ``regiao`` and ``preco`` (``None`` where the source publishes ``***``).
    Upsert rather than insert so that re-entering a corrected week overwrites it
    instead of failing.
    """
    if not registros:
        return 0
    with acquire_sync() as conn:
        with conn.cursor() as cur:
            cur.executemany(
                "INSERT INTO anp_preco_semanal "
                "(produto, vigencia_inicio, vigencia_fim, regiao, preco) "
                "VALUES (%(produto)s, %(vigencia_inicio)s, %(vigencia_fim)s, "
                "%(regiao)s, %(preco)s) "
                "ON CONFLICT (produto, vigencia_inicio, regiao) DO UPDATE SET "
                "vigencia_fim = EXCLUDED.vigencia_fim, preco = EXCLUDED.preco",
                registros,
            )
    return len(registros)


def gravar_indices_mensais(registros: list[dict]) -> int:
    """Insert or update monthly indices.

    Each record needs ``indice``, ``mes_ref``, ``valor`` and optionally
    ``base_label``.
    """
    if not registros:
        return 0
    normalizados = [
        {
            "indice": r["indice"],
            "base_label": r.get("base_label"),
            "mes_ref": inicio_do_mes(r["mes_ref"]),
            "valor": r["valor"],
        }
        for r in registros
    ]
    with acquire_sync() as conn:
        with conn.cursor() as cur:
            cur.executemany(
                "INSERT INTO indice_mensal (indice, base_label, mes_ref, valor) "
                "VALUES (%(indice)s, %(base_label)s, %(mes_ref)s, %(valor)s) "
                "ON CONFLICT (indice, mes_ref) DO UPDATE SET "
                "valor = EXCLUDED.valor, base_label = EXCLUDED.base_label",
                normalizados,
            )
    return len(normalizados)


def listar_precos_anp(
    produto: str = ANP_PRODUTO_CAP, regiao: str | None = None, limite: int = 500
) -> list[dict]:
    sql = "SELECT * FROM anp_preco_semanal WHERE produto = %s"
    params: list = [produto]
    if regiao:
        sql += " AND regiao = %s"
        params.append(regiao)
    sql += " ORDER BY vigencia_inicio DESC LIMIT %s"
    params.append(limite)
    with acquire_sync() as conn:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]


def listar_indices_mensais(
    indice: str = INDICE_IGP_DI, limite: int = 500
) -> list[dict]:
    with acquire_sync() as conn:
        cur = conn.execute(
            "SELECT * FROM indice_mensal WHERE indice = %s "
            "ORDER BY mes_ref DESC LIMIT %s",
            (indice, limite),
        )
        return [dict(r) for r in cur.fetchall()]


def cobertura() -> dict:
    """Range of data on hand, so the UI can say what still needs entering."""
    with acquire_sync() as conn:
        anp = conn.execute(
            "SELECT MIN(vigencia_inicio) AS de, MAX(vigencia_fim) AS ate, "
            "COUNT(*) AS registros FROM anp_preco_semanal WHERE produto = %s",
            (ANP_PRODUTO_CAP,),
        ).fetchone()
        igp = conn.execute(
            "SELECT MIN(mes_ref) AS de, MAX(mes_ref) AS ate, COUNT(*) AS registros "
            "FROM indice_mensal WHERE indice = %s",
            (INDICE_IGP_DI,),
        ).fetchone()
        regioes = conn.execute(
            "SELECT DISTINCT regiao FROM anp_preco_semanal WHERE produto = %s "
            "ORDER BY regiao",
            (ANP_PRODUTO_CAP,),
        ).fetchall()
    return {
        "anp": dict(anp),
        "igp_di": dict(igp),
        "regioes": [r["regiao"] for r in regioes],
    }
