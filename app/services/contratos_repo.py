"""Contract registration: the fields the PDFs carry, plus the ones only the user
can supply.

The export's header block needs eleven fields; the PDF header yields three. The
rest (Edital, Rodovia, Trecho, Subtrecho, Segmento, Extensão, Contratada) is
registered by the user and keyed by contract number.
"""

import re
from datetime import date, datetime
from decimal import Decimal

from ..db import acquire_sync
from .delta_p import FAMILIA_CAP, FAMILIA_EMULSOES, inicio_do_mes
from .number_parser import parse_br_number

# Fields the user owns. PDF-derived fields are deliberately absent: see
# salvar_cadastro.
CAMPOS_CADASTRO = (
    "edital",
    "rodovia",
    "trecho",
    "subtrecho",
    "segmento",
    "extensao",
    "contratada",
)

# The PDF header's "Contrato" arrives polluted, uniformly across every file seen:
#   "06 00134/2022 - HWN ENGENHARIA LTDA Índices I0 I1 K Índices I0 I1 K"
# The number is the only reliable key, so it is extracted before use.
_NUMERO_RE = re.compile(r"(\d{2}\s*\d{5}/\d{4})")
_CONTRATADA_RE = re.compile(r"-\s*(.+?)(?:\s+[ÍI]ndices\b|$)", re.IGNORECASE)


def normalizar_numero(bruto: str) -> str | None:
    """Extract the contract number from the raw header value."""
    m = _NUMERO_RE.search(bruto or "")
    if not m:
        return None
    return re.sub(r"\s+", " ", m.group(1)).strip()


def extrair_contratada(bruto: str) -> str | None:
    """Pull the contractor's name out of the same polluted field.

    Only a suggestion for the registration form — the user confirms it.
    """
    m = _CONTRATADA_RE.search(bruto or "")
    if not m:
        return None
    nome = m.group(1).strip()
    return nome or None


def parse_data(valor: str | None) -> date | None:
    """Parse the dd/mm/yyyy dates the PDFs use."""
    if not valor:
        return None
    try:
        return datetime.strptime(valor.strip(), "%d/%m/%Y").date()
    except ValueError:
        return None


def mes_da_medicao(periodo_liquido: str | None) -> date | None:
    """Month of a "01/09/2025 - 30/09/2025" period, as the first of that month.

    Taken from the start date: some periods begin mid-month
    ("16/12/2024 - 31/12/2024") but still belong to that month.
    """
    if not periodo_liquido:
        return None
    inicio = parse_data(periodo_liquido.split("-")[0])
    return inicio_do_mes(inicio) if inicio else None


def registrar_do_pdf(header: dict) -> int | None:
    """Create or find the contract described by a PDF header.

    Returns the contract id, or None when the header carries no usable number.

    PDF-derived fields are written only when still empty (``COALESCE`` keeps the
    stored value), so reprocessing a file never overwrites what the user
    corrected by hand.
    """
    numero = normalizar_numero(header.get("Contrato", ""))
    if not numero:
        return None
    data_base = parse_data(header.get("Data Base"))
    processo = header.get("Número do Processo") or None
    contratada = extrair_contratada(header.get("Contrato", ""))

    with acquire_sync() as conn:
        cur = conn.execute(
            "INSERT INTO contrato (numero, data_base, numero_processo, contratada) "
            "VALUES (%s, %s, %s, %s) "
            "ON CONFLICT (numero) DO UPDATE SET "
            "  data_base = COALESCE(contrato.data_base, EXCLUDED.data_base), "
            "  numero_processo = COALESCE(contrato.numero_processo, "
            "                             EXCLUDED.numero_processo), "
            "  contratada = COALESCE(contrato.contratada, EXCLUDED.contratada) "
            "RETURNING id",
            (numero, data_base, processo, contratada),
        )
        return cur.fetchone()["id"]


def buscar(numero: str) -> dict | None:
    with acquire_sync() as conn:
        cur = conn.execute("SELECT * FROM contrato WHERE numero = %s", (numero,))
        row = cur.fetchone()
        if not row:
            return None
        contrato = dict(row)
        cur = conn.execute(
            "SELECT familia, regiao FROM contrato_familia_regiao WHERE contrato_id = %s",
            (contrato["id"],),
        )
        contrato["regioes"] = {r["familia"]: r["regiao"] for r in cur.fetchall()}
    return contrato


def listar() -> list[dict]:
    with acquire_sync() as conn:
        cur = conn.execute(
            "SELECT c.*, "
            "  (SELECT COUNT(*) FROM medicao_item m WHERE m.contrato_id = c.id) "
            "    AS itens, "
            "  (SELECT MIN(m.mes_medicao) FROM medicao_item m "
            "     WHERE m.contrato_id = c.id) AS primeiro_mes, "
            "  (SELECT MAX(m.mes_medicao) FROM medicao_item m "
            "     WHERE m.contrato_id = c.id) AS ultimo_mes "
            "FROM contrato c ORDER BY c.numero"
        )
        return [dict(r) for r in cur.fetchall()]


def _extensao(valor) -> float | None:
    """Coerce the Extensão field to a number.

    The column is NUMERIC but the form is a text box labelled "Extensão (km)",
    so the natural entry is Brazilian — ``45,7``. Handing that to Postgres raised
    ``invalid input syntax for type numeric`` and lost the whole form, so the
    comma is parsed here instead. A value with no digits at all becomes NULL:
    the export reports the field as missing, which is truthful, rather than
    refusing to save the other six fields.
    """
    if valor is None or isinstance(valor, (int, float, Decimal)):
        return valor
    return parse_br_number(str(valor))


def salvar_cadastro(numero: str, dados: dict) -> bool:
    """Save the user-owned fields of a contract.

    Only ``CAMPOS_CADASTRO`` are accepted; ``data_base`` and ``numero_processo``
    come from the PDF and are not editable here, so a typo in this form cannot
    move the ΔP base month.
    """
    campos = {k: v for k, v in dados.items() if k in CAMPOS_CADASTRO}
    if not campos:
        return False
    if "extensao" in campos:
        campos["extensao"] = _extensao(campos["extensao"])
    atribuicoes = ", ".join(f"{k} = %({k})s" for k in campos)
    campos["numero"] = numero
    with acquire_sync() as conn:
        cur = conn.execute(
            f"UPDATE contrato SET {atribuicoes}, atualizado_em = now() "
            "WHERE numero = %(numero)s",
            campos,
        )
        return cur.rowcount > 0


def definir_regiao(numero: str, familia: str, regiao: str) -> None:
    """Set the ANP region for one family of one contract.

    Per family and independent by design: the user may quote CAP in one region
    and emulsions in another.
    """
    if familia not in (FAMILIA_CAP, FAMILIA_EMULSOES):
        raise ValueError(f"Família desconhecida: {familia!r}")
    with acquire_sync() as conn:
        conn.execute(
            "INSERT INTO contrato_familia_regiao (contrato_id, familia, regiao) "
            "SELECT id, %s, %s FROM contrato WHERE numero = %s "
            "ON CONFLICT (contrato_id, familia) DO UPDATE SET regiao = EXCLUDED.regiao",
            (familia, regiao, numero),
        )


def campos_faltantes(contrato: dict) -> list[str]:
    """Which registration fields are still empty.

    The export needs all of them to fill the header block, so the UI can say
    what is missing before the user asks for a spreadsheet.
    """
    faltam = [c for c in CAMPOS_CADASTRO if contrato.get(c) in (None, "")]
    if not contrato.get("data_base"):
        faltam.append("data_base")
    regioes = contrato.get("regioes") or {}
    faltam += [
        f"regiao_{f.lower()}" for f in (FAMILIA_CAP, FAMILIA_EMULSOES)
        if f not in regioes
    ]
    return faltam
