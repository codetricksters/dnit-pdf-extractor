"""Persisting the measurement rows extracted from the PDFs.

Replaces the previous arrangement where the dashboard globbed
``data/jobs/*/results/*.json``: the rows have to live next to the índices to be
crossed with them. The JSON files remain as the extraction artefact.
"""

import re
from datetime import date
from decimal import Decimal, InvalidOperation

from ..db import acquire_sync
from .catalogo import padrao_ilike
from .contratos_repo import mes_da_medicao

# Same rule the extractor uses to recognise a record: a 4+-digit service code.
# Anything else on that column ("SUBTOTAL", section labels) is not an item.
_CODIGO_RE = re.compile(r"^\d{4,}$")


def _decimal(valor) -> Decimal | None:
    """Convert an extracted value to Decimal.

    Values reach here as floats (the extractor parses the Latin format), so the
    conversion goes through ``str`` to keep the parsed figure exactly as printed
    rather than its binary approximation.
    """
    if valor is None or valor == "":
        return None
    try:
        return Decimal(str(valor))
    except (InvalidOperation, ValueError):
        return None


def gravar_itens(contrato_id: int, rows: list[dict], job_id: str | None = None) -> int:
    """Store the item rows of one extracted file; returns how many were stored.

    Idempotent: the ``UNIQUE (contrato_id, codigo_servico, mes_medicao,
    source_file)`` key means reprocessing the same PDF updates its rows instead
    of duplicating them.

    Every item with a service code is stored, associated in the catalogue or
    not: associating a code later brings its past items into the calculation
    without reprocessing the PDFs.

    A service code can recur within the same month/file across more than one
    work group of the contract (e.g. the same material measured under both
    "conservação corretiva" and "conservação preventiva"), or as a zeroed-out
    reversal/audit line the PDF prints under "ESTORNOS/RESSARCIMENTOS" with
    ``Fator`` always ``0`` — the DNIT PDF never assigns a real factor to those
    lines, real or not. A row whose ``Fator`` is ``0`` never enters the
    calculation; every other occurrence of the same
    (código, mês, arquivo) has its ``Valor a PI Líquido`` summed into one row,
    keeping the shared ``Fator`` (confirmed identical across real occurrences
    within one file) and the description of the first one seen.
    """
    acumulados: dict[tuple[str, date, str], dict] = {}

    for row in rows:
        codigo = str(row.get("Serviço") or "").strip()
        if not _CODIGO_RE.match(codigo):
            continue
        mes = mes_da_medicao(row.get("Período Líquido"))
        valor_pi = _decimal(row.get("Valor a PI Líquido"))
        fator = _decimal(row.get("Fator"))
        if mes is None or valor_pi is None or fator is None:
            continue
        if fator == 0:
            # Reversal/audit line ("EST.QTDE.LQDA. …"): the PDF always prints
            # Fator 0 here and it never enters the calculation, whether or
            # not the line itself carries a value.
            continue

        source_file = str(row.get("Source_File") or "")
        chave = (codigo, mes, source_file)
        existente = acumulados.get(chave)
        if existente is None:
            acumulados[chave] = {
                "contrato_id": contrato_id,
                "codigo_servico": codigo,
                "descricao_pdf": str(row.get("Descrição") or "").strip(),
                "mes_medicao": mes,
                "valor_pi": valor_pi,
                "fator": fator,
                "source_file": source_file,
                "job_id": job_id,
            }
        else:
            existente["valor_pi"] += valor_pi

    registros = list(acumulados.values())

    if registros:
        with acquire_sync() as conn:
            with conn.cursor() as cur:
                cur.executemany(
                    "INSERT INTO medicao_item (contrato_id, codigo_servico, "
                    "  descricao_pdf, mes_medicao, valor_pi, fator, source_file, job_id) "
                    "VALUES (%(contrato_id)s, %(codigo_servico)s, %(descricao_pdf)s, "
                    "  %(mes_medicao)s, %(valor_pi)s, %(fator)s, %(source_file)s, "
                    "  %(job_id)s) "
                    "ON CONFLICT (contrato_id, codigo_servico, mes_medicao, source_file) "
                    "DO UPDATE SET valor_pi = EXCLUDED.valor_pi, "
                    "  fator = EXCLUDED.fator, job_id = EXCLUDED.job_id, "
                    "  descricao_pdf = EXCLUDED.descricao_pdf",
                    registros,
                )

    return len(registros)


def itens_para_export(contrato_id: int) -> list[dict]:
    """Items that belong in the spreadsheet, ordered family → product → month.

    Only codes associated with a product: the rest stays out of the calculation.
    """
    with acquire_sync() as conn:
        cur = conn.execute(
            "SELECT m.mes_medicao, m.codigo_servico, m.valor_pi, m.fator, "
            "       m.source_file, p.descricao_export, p.familia, p.ordem, "
            "       p.id AS produto_id "
            "FROM medicao_item m "
            "JOIN produto_codigo pc ON pc.codigo_servico = m.codigo_servico "
            "JOIN produto p ON p.id = pc.produto_id "
            "WHERE m.contrato_id = %s "
            # m.id DESC last so that, when the same measurement arrives under two
            # file names, the most recently stored row comes first and the export
            # keeps that one.
            "ORDER BY p.familia, p.ordem, p.descricao_export, m.mes_medicao, m.id DESC",
            (contrato_id,),
        )
        return [dict(r) for r in cur.fetchall()]


def listar_itens(
    contrato_id: int,
    *,
    mes: date | None = None,
    no_calculo: bool | None = None,
    q: str | None = None,
) -> list[dict]:
    """Every extracted item of a contract, with its catalogue product or None.

    The read-only view of the measurements: unlike ``itens_para_export`` it keeps
    the codes without a product, which is how the user finds what to associate.
    ``reajuste`` truncates like column F of the spreadsheet.
    """
    with acquire_sync() as conn:
        cur = conn.execute(
            "SELECT m.id, m.mes_medicao AS mes, m.codigo_servico AS codigo, "
            "       m.descricao_pdf, round(m.valor_pi, 2) AS valor_pi, m.fator, "
            "       trunc(m.valor_pi * m.fator, 2) AS reajuste, "
            "       m.source_file AS arquivo, p.id AS produto_id, "
            "       p.descricao_export AS produto, p.familia "
            "FROM medicao_item m "
            "LEFT JOIN produto_codigo pc ON pc.codigo_servico = m.codigo_servico "
            "LEFT JOIN produto p ON p.id = pc.produto_id "
            "WHERE m.contrato_id = %(contrato)s "
            "  AND (%(mes)s::date IS NULL OR m.mes_medicao = %(mes)s) "
            "  AND (%(no_calculo)s::boolean IS NULL "
            "       OR (p.id IS NOT NULL) = %(no_calculo)s) "
            "  AND (%(padrao)s::text IS NULL "
            "       OR m.codigo_servico ILIKE %(padrao)s "
            "       OR m.descricao_pdf ILIKE %(padrao)s) "
            "ORDER BY m.mes_medicao, m.codigo_servico, m.id",
            {"contrato": contrato_id, "mes": mes, "no_calculo": no_calculo,
             "padrao": padrao_ilike(q)},
        )
        return [dict(r) for r in cur.fetchall()]


def meses_do_contrato(contrato_id: int) -> list:
    with acquire_sync() as conn:
        cur = conn.execute(
            "SELECT DISTINCT mes_medicao FROM medicao_item WHERE contrato_id = %s "
            "ORDER BY mes_medicao",
            (contrato_id,),
        )
        return [r["mes_medicao"] for r in cur.fetchall()]
