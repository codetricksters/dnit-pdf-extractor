"""Reading and writing the price indices the users maintain.

Synchronous throughout: the Dash dashboard runs synchronously under ``a2wsgi``,
and the queries are short lookups. Async callers wrap these in
``asyncio.to_thread`` rather than duplicating each query in two flavours.

Every row records its ``origem`` — ``'seed'``, ``'upload:<arquivo>'`` or
``'manual'`` — and when it was last written, so an import can preserve what a
user corrected by hand. Weeks of the same product and region may not overlap
(``anp_sem_sobreposicao``), so the "day 15" of a month never falls in two weeks.
"""

from datetime import date
from decimal import Decimal

import psycopg

from ..db import acquire_sync
from .delta_p import ANP_PRODUTO_CAP, BASE_IGP_DI, INDICE_IGP_DI, inicio_do_mes

# Regions the ANP publishes, in the file's spelling. Stored as plain text so an
# unforeseen region is a row rather than a migration.
REGIOES = ("Norte", "Nordeste", "Centro-Oeste", "Sul", "Sudeste", "Brasil")

ORIGEM_MANUAL = "manual"
ORIGEM_SEED = "seed"

_COLUNAS_ANP = "id, produto, regiao, vigencia_inicio, vigencia_fim, preco, origem, atualizado_em"
_COLUNAS_INDICE = "id, indice, base_label, mes_ref, valor, origem, atualizado_em"


def origem_upload(arquivo: str) -> str:
    return f"upload:{arquivo}"


class IndiceInvalido(ValueError):
    """Gravação de índice recusada, com mensagem para o usuário."""


class SemanaSobreposta(IndiceInvalido):
    """A semana se sobrepõe a outra do mesmo produto e região."""


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


# Upserts. The bulk variants add a WHERE so that re-importing an identical file
# rewrites nothing — origem and atualizado_em keep saying where the value came
# from. A manual write always stamps itself, even when the value is the same.
_UPSERT_ANP = (
    "INSERT INTO anp_preco_semanal AS a "
    "(produto, vigencia_inicio, vigencia_fim, regiao, preco, origem) "
    "VALUES (%(produto)s, %(vigencia_inicio)s, %(vigencia_fim)s, %(regiao)s, "
    "%(preco)s, %(origem)s) "
    "ON CONFLICT (produto, vigencia_inicio, regiao) DO UPDATE SET "
    "vigencia_fim = EXCLUDED.vigencia_fim, preco = EXCLUDED.preco, "
    "origem = EXCLUDED.origem, atualizado_em = now()"
)
_SO_SE_MUDOU_ANP = (
    " WHERE (a.vigencia_fim, a.preco) IS DISTINCT FROM "
    "(EXCLUDED.vigencia_fim, EXCLUDED.preco)"
)
_UPSERT_INDICE = (
    "INSERT INTO indice_mensal AS i (indice, base_label, mes_ref, valor, origem) "
    "VALUES (%(indice)s, %(base_label)s, %(mes_ref)s, %(valor)s, %(origem)s) "
    "ON CONFLICT (indice, mes_ref) DO UPDATE SET "
    "valor = EXCLUDED.valor, "
    "base_label = COALESCE(EXCLUDED.base_label, i.base_label), "
    "origem = EXCLUDED.origem, atualizado_em = now()"
)
_SO_SE_MUDOU_INDICE = " WHERE i.valor IS DISTINCT FROM EXCLUDED.valor"
# Acrescentado quando a gravação deve preservar o que é manual mesmo que o
# planejamento (feito antes, contra uma leitura anterior do banco) não tenha
# visto isso: fecha a corrida entre planejar() e a gravação de fato.
_PRESERVAR_MANUAL_ANP = " AND a.origem <> 'manual'"
_PRESERVAR_MANUAL_INDICE = " AND i.origem <> 'manual'"


def _executar_anp(sql: str, linhas: list[dict]) -> None:
    """Run an ANP upsert in one transaction, translating constraint errors."""
    try:
        with acquire_sync() as conn:
            with conn.cursor() as cur:
                cur.executemany(sql, linhas)
    except psycopg.errors.ExclusionViolation as e:
        raise SemanaSobreposta(
            "Uma semana se sobrepõe a outra já cadastrada para o mesmo produto "
            "e região; nada foi gravado."
        ) from e
    except psycopg.errors.CheckViolation as e:
        raise IndiceInvalido(
            "A vigência de uma semana termina antes de começar; nada foi gravado."
        ) from e


def _executar_indices(sql: str, linhas: list[dict]) -> None:
    with acquire_sync() as conn:
        with conn.cursor() as cur:
            cur.executemany(sql, linhas)


def gravar_precos_anp(
    registros: list[dict], origem: str = ORIGEM_MANUAL, *, sobrescrever_manuais: bool = True
) -> int:
    """Insert or update weekly ANP prices, rewriting only what changed.

    Each record needs ``produto``, ``vigencia_inicio``, ``vigencia_fim``,
    ``regiao`` and ``preco`` (``None`` where the source publishes ``***``).

    ``sobrescrever_manuais=False`` refuses to rewrite a row that is
    ``origem = 'manual'`` **no momento da gravação** — não apenas no
    planejamento —, o que fecha a corrida em que a linha passa a manual entre
    o plano e a escrita. O padrão (``True``) preserva o comportamento anterior:
    a semente e a gravação manual sempre sobrescrevem.
    """
    if not registros:
        return 0
    linhas = [{**r, "origem": origem} for r in registros]
    sql = _UPSERT_ANP + _SO_SE_MUDOU_ANP
    if not sobrescrever_manuais:
        sql += _PRESERVAR_MANUAL_ANP
    _executar_anp(sql, linhas)
    return len(linhas)


def gravar_indices_mensais(
    registros: list[dict], origem: str = ORIGEM_MANUAL, *, sobrescrever_manuais: bool = True
) -> int:
    """Insert or update monthly indices, rewriting only what changed.

    Each record needs ``indice``, ``mes_ref``, ``valor`` and optionally
    ``base_label``. See ``gravar_precos_anp`` for ``sobrescrever_manuais``.
    """
    if not registros:
        return 0
    linhas = [
        {
            "indice": r["indice"],
            "base_label": r.get("base_label"),
            "mes_ref": inicio_do_mes(r["mes_ref"]),
            "valor": r["valor"],
            "origem": origem,
        }
        for r in registros
    ]
    sql = _UPSERT_INDICE + _SO_SE_MUDOU_INDICE
    if not sobrescrever_manuais:
        sql += _PRESERVAR_MANUAL_INDICE
    _executar_indices(sql, linhas)
    return len(linhas)


def regioes_disponiveis(produto: str = ANP_PRODUTO_CAP) -> list[str]:
    """Regions that have prices for *produto* — the ones a contract may use."""
    with acquire_sync() as conn:
        cur = conn.execute(
            "SELECT DISTINCT regiao FROM anp_preco_semanal WHERE produto = %s "
            "ORDER BY regiao",
            (produto,),
        )
        return [r["regiao"] for r in cur.fetchall()]


def _grafia(regiao: str | None, candidatas) -> str | None:
    alvo = (regiao or "").strip().casefold()
    if not alvo:
        return None
    return next((c for c in candidatas if c.casefold() == alvo), None)


def normalizar_regiao(regiao: str | None, produto: str = ANP_PRODUTO_CAP) -> str | None:
    """The stored spelling of *regiao* (``NORDESTE`` → ``Nordeste``), or None
    when *produto* has no prices in that region."""
    return _grafia(regiao, regioes_disponiveis(produto))


def _semana(inicio: date, fim: date) -> str:
    return f"{inicio:%d/%m/%Y}–{fim:%d/%m/%Y}"


def buscar_semana(produto: str, regiao: str, vigencia_inicio: date) -> dict | None:
    with acquire_sync() as conn:
        cur = conn.execute(
            f"SELECT {_COLUNAS_ANP} FROM anp_preco_semanal "
            "WHERE produto = %s AND regiao = %s AND vigencia_inicio = %s",
            (produto, regiao, vigencia_inicio),
        )
        row = cur.fetchone()
    return dict(row) if row else None


def gravar_semana_manual(registro: dict) -> dict:
    """Grava ou corrige uma semana digitada pelo usuário (``origem = 'manual'``).

    A mesma semana (mesmo início) é corrigida; uma semana que se sobrepõe a
    outra é recusada, indicando qual.
    """
    produto = (registro.get("produto") or ANP_PRODUTO_CAP).strip()
    inicio = registro["vigencia_inicio"]
    fim = registro["vigencia_fim"]
    if fim < inicio:
        raise IndiceInvalido(
            f"A semana termina ({fim:%d/%m/%Y}) antes de começar ({inicio:%d/%m/%Y})."
        )
    preco = registro.get("preco")
    if preco is not None:
        preco = Decimal(str(preco))
        if preco <= 0:
            raise IndiceInvalido("O preço deve ser maior que zero.")
    candidatas = list(dict.fromkeys([*REGIOES, *regioes_disponiveis(produto)]))
    regiao = _grafia(registro.get("regiao"), candidatas)
    if regiao is None:
        raise IndiceInvalido(
            f"Região desconhecida: {registro.get('regiao')!r}. "
            f"Use uma de: {', '.join(candidatas)}."
        )

    with acquire_sync() as conn:
        conflito = conn.execute(
            "SELECT vigencia_inicio, vigencia_fim FROM anp_preco_semanal "
            "WHERE produto = %s AND regiao = %s AND vigencia_inicio <> %s "
            "AND daterange(vigencia_inicio, vigencia_fim, '[]') "
            "    && daterange(%s, %s, '[]') "
            "ORDER BY vigencia_inicio LIMIT 1",
            (produto, regiao, inicio, inicio, fim),
        ).fetchone()
    if conflito:
        raise SemanaSobreposta(
            f"A semana {_semana(inicio, fim)} se sobrepõe à semana já cadastrada "
            f"{_semana(conflito['vigencia_inicio'], conflito['vigencia_fim'])} "
            f"({produto}, {regiao})."
        )

    _executar_anp(
        _UPSERT_ANP,
        [{"produto": produto, "vigencia_inicio": inicio, "vigencia_fim": fim,
          "regiao": regiao, "preco": preco, "origem": ORIGEM_MANUAL}],
    )
    return buscar_semana(produto, regiao, inicio)


def buscar_indice(mes: date, indice: str = INDICE_IGP_DI) -> dict | None:
    with acquire_sync() as conn:
        cur = conn.execute(
            f"SELECT {_COLUNAS_INDICE} FROM indice_mensal "
            "WHERE indice = %s AND mes_ref = %s",
            (indice, inicio_do_mes(mes)),
        )
        row = cur.fetchone()
    return dict(row) if row else None


def gravar_indice_manual(mes: date, valor) -> dict:
    """Grava ou corrige um mês do IGP-DI digitado pelo usuário."""
    valor = Decimal(str(valor))
    if valor <= 0:
        raise IndiceInvalido("O valor do índice deve ser maior que zero.")
    _executar_indices(
        _UPSERT_INDICE,
        [{"indice": INDICE_IGP_DI, "base_label": BASE_IGP_DI,
          "mes_ref": inicio_do_mes(mes), "valor": valor, "origem": ORIGEM_MANUAL}],
    )
    return buscar_indice(mes)


def excluir_preco_anp(preco_id: int) -> bool:
    with acquire_sync() as conn:
        cur = conn.execute("DELETE FROM anp_preco_semanal WHERE id = %s", (preco_id,))
        return cur.rowcount > 0


def excluir_indice_mensal(mes: date, indice: str = INDICE_IGP_DI) -> bool:
    with acquire_sync() as conn:
        cur = conn.execute(
            "DELETE FROM indice_mensal WHERE indice = %s AND mes_ref = %s",
            (indice, inicio_do_mes(mes)),
        )
        return cur.rowcount > 0


def precos_anp_por_chave(produtos: set[str]) -> dict[tuple[str, date, str], dict]:
    """Every stored week of *produtos*, keyed ``(produto, vigencia_inicio, regiao)``
    — what an import compares its file against."""
    with acquire_sync() as conn:
        cur = conn.execute(
            f"SELECT {_COLUNAS_ANP} FROM anp_preco_semanal WHERE produto = ANY(%s)",
            (list(produtos),),
        )
        return {
            (r["produto"], r["vigencia_inicio"], r["regiao"]): dict(r)
            for r in cur.fetchall()
        }


def indices_por_mes(indice: str = INDICE_IGP_DI) -> dict[date, dict]:
    with acquire_sync() as conn:
        cur = conn.execute(
            f"SELECT {_COLUNAS_INDICE} FROM indice_mensal WHERE indice = %s",
            (indice,),
        )
        return {r["mes_ref"]: dict(r) for r in cur.fetchall()}


def listar_precos_anp(
    produto: str = ANP_PRODUTO_CAP,
    regiao: str | None = None,
    limite: int | None = 500,
    *,
    de: date | None = None,
    ate: date | None = None,
) -> list[dict]:
    """Weeks of *produto*, newest first. *de*/*ate* keep the weeks that touch
    the period; ``limite=None`` returns all of them (``LIMIT NULL``)."""
    sql = f"SELECT {_COLUNAS_ANP} FROM anp_preco_semanal WHERE produto = %s"
    params: list = [produto]
    if regiao:
        sql += " AND lower(regiao) = lower(%s)"
        params.append(regiao.strip())
    if de:
        sql += " AND vigencia_fim >= %s"
        params.append(de)
    if ate:
        sql += " AND vigencia_inicio <= %s"
        params.append(ate)
    sql += " ORDER BY vigencia_inicio DESC, regiao LIMIT %s"
    params.append(limite)
    with acquire_sync() as conn:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]


def listar_indices_mensais(
    indice: str = INDICE_IGP_DI,
    limite: int | None = 500,
    *,
    de: date | None = None,
    ate: date | None = None,
) -> list[dict]:
    sql = f"SELECT {_COLUNAS_INDICE} FROM indice_mensal WHERE indice = %s"
    params: list = [indice]
    if de:
        sql += " AND mes_ref >= %s"
        params.append(inicio_do_mes(de))
    if ate:
        sql += " AND mes_ref <= %s"
        params.append(inicio_do_mes(ate))
    sql += " ORDER BY mes_ref DESC LIMIT %s"
    params.append(limite)
    with acquire_sync() as conn:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]


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
