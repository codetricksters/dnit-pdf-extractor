"""Product catalogue: service code → export description → calculation family.

The service *code* is the key, never the description. OCR corrupts descriptions
but not numeric codes, and the same material appears under several codes across
contracts — while the spreadsheet the user validates needs one stable
description per product ("AQUISIÇÃO DE CAP 50/70", not the PDF's "AQUISIÇÃO DE
CIMENTO ASFÁLTICO CAP 50/70").

Codes not in the catalogue are recorded as pending with a *suggested* family and
excluded from the calculation until a human confirms them, so that a new
material cannot silently land in the wrong family and distort the result.
"""

import re
import unicodedata

from ..db import acquire_sync
from .delta_p import FAMILIA_CAP, FAMILIA_EMULSOES

# Checked before the CAP pattern: an emulsion description never contains "CAP"
# as a word, but ordering the tests makes the intent explicit.
_PADROES_EMULSOES = re.compile(
    r"\bEMULSAO\b|\bEMULSOES\b|\bRR-?\d|\bRC-?\d|\bEAI\b|\bIMPRIMACAO\b"
)
_PADRAO_CAP = re.compile(r"\bCAP\b|\bCIMENTO ASFALTICO\b")


def _sem_acento(texto: str) -> str:
    """Upper-case and strip accents, so OCR variations still match."""
    decomposto = unicodedata.normalize("NFKD", texto or "")
    return "".join(c for c in decomposto if not unicodedata.combining(c)).upper()


def sugerir_familia(descricao: str) -> str | None:
    """Guess the family from a PDF description, or None when unclear.

    Only a suggestion: it is stored unconfirmed and shown to the user for
    review.
    """
    texto = _sem_acento(descricao)
    if _PADROES_EMULSOES.search(texto):
        return FAMILIA_EMULSOES
    if _PADRAO_CAP.search(texto):
        return FAMILIA_CAP
    return None


def buscar_por_codigo(codigo: str) -> dict | None:
    with acquire_sync() as conn:
        cur = conn.execute(
            "SELECT pc.codigo_servico, pc.confirmado, pc.descricao_pdf, "
            "       p.id AS produto_id, p.descricao_export, p.familia, p.ordem "
            "FROM produto_codigo pc JOIN produto p ON p.id = pc.produto_id "
            "WHERE pc.codigo_servico = %s",
            (codigo,),
        )
        row = cur.fetchone()
    return dict(row) if row else None


def listar_produtos() -> list[dict]:
    with acquire_sync() as conn:
        cur = conn.execute(
            "SELECT p.*, "
            "  (SELECT COUNT(*) FROM produto_codigo pc WHERE pc.produto_id = p.id) "
            "    AS codigos "
            "FROM produto p ORDER BY p.familia, p.ordem, p.descricao_export"
        )
        return [dict(r) for r in cur.fetchall()]


def criar_produto(descricao_export: str, familia: str, ordem: int = 0) -> int:
    if familia not in (FAMILIA_CAP, FAMILIA_EMULSOES):
        raise ValueError(f"Família desconhecida: {familia!r}")
    with acquire_sync() as conn:
        cur = conn.execute(
            "INSERT INTO produto (descricao_export, familia, ordem) "
            "VALUES (%s, %s, %s) "
            "ON CONFLICT (descricao_export) DO UPDATE SET "
            "familia = EXCLUDED.familia, ordem = EXCLUDED.ordem RETURNING id",
            (descricao_export, familia, ordem),
        )
        return cur.fetchone()["id"]


def registrar_codigo(
    codigo: str, produto_id: int, *, descricao_pdf: str | None = None,
    confirmado: bool = True,
) -> None:
    """Point *codigo* at *produto_id*, confirming it by default.

    Used both by the user (confirming a pending code) and when moving a code
    from one product to another.
    """
    with acquire_sync() as conn:
        conn.execute(
            "INSERT INTO produto_codigo "
            "(codigo_servico, produto_id, descricao_pdf, confirmado) "
            "VALUES (%s, %s, %s, %s) "
            "ON CONFLICT (codigo_servico) DO UPDATE SET "
            "produto_id = EXCLUDED.produto_id, confirmado = EXCLUDED.confirmado, "
            "descricao_pdf = COALESCE(EXCLUDED.descricao_pdf, "
            "                         produto_codigo.descricao_pdf)",
            (codigo, produto_id, descricao_pdf, confirmado),
        )


def registrar_pendencia(codigo: str, descricao_pdf: str) -> dict | None:
    """Record an unknown code seen in a PDF, for later review.

    Returns the pending row, or None when the family could not even be guessed —
    in that case there is no product to attach it to and the user has to create
    one. Never overwrites an existing mapping: a confirmed code keeps whatever
    the user decided, and the PDF description is only refreshed for diagnosis.
    """
    existente = buscar_por_codigo(codigo)
    if existente:
        with acquire_sync() as conn:
            conn.execute(
                "UPDATE produto_codigo SET descricao_pdf = %s WHERE codigo_servico = %s",
                (descricao_pdf, codigo),
            )
        return existente

    familia = sugerir_familia(descricao_pdf)
    if familia is None:
        return None

    with acquire_sync() as conn:
        cur = conn.execute(
            "SELECT id FROM produto WHERE descricao_export = %s", (descricao_pdf,)
        )
        row = cur.fetchone()
        if row:
            produto_id = row["id"]
        else:
            # The PDF description becomes a provisional export description; the
            # user renames it when confirming.
            cur = conn.execute(
                "INSERT INTO produto (descricao_export, familia, ordem) "
                "VALUES (%s, %s, 99) RETURNING id",
                (descricao_pdf, familia),
            )
            produto_id = cur.fetchone()["id"]

    registrar_codigo(
        codigo, produto_id, descricao_pdf=descricao_pdf, confirmado=False
    )
    return buscar_por_codigo(codigo)


def listar_pendencias() -> list[dict]:
    with acquire_sync() as conn:
        cur = conn.execute(
            "SELECT pc.codigo_servico, pc.descricao_pdf, p.id AS produto_id, "
            "       p.descricao_export, p.familia "
            "FROM produto_codigo pc JOIN produto p ON p.id = pc.produto_id "
            "WHERE NOT pc.confirmado ORDER BY pc.codigo_servico"
        )
        return [dict(r) for r in cur.fetchall()]


def confirmar_codigo(codigo: str) -> bool:
    with acquire_sync() as conn:
        cur = conn.execute(
            "UPDATE produto_codigo SET confirmado = TRUE WHERE codigo_servico = %s",
            (codigo,),
        )
        return cur.rowcount > 0


def codigos_confirmados() -> dict[str, dict]:
    """Every confirmed code, keyed by code — what the export is allowed to use."""
    with acquire_sync() as conn:
        cur = conn.execute(
            "SELECT pc.codigo_servico, p.id AS produto_id, p.descricao_export, "
            "       p.familia, p.ordem "
            "FROM produto_codigo pc JOIN produto p ON p.id = pc.produto_id "
            "WHERE pc.confirmado"
        )
        return {r["codigo_servico"]: dict(r) for r in cur.fetchall()}
