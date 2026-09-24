"""Contract registration: the fields the PDFs carry, plus the ones only the user
can supply.

The export's header block needs eleven fields; the PDF header yields three. The
rest (Edital, Rodovia, Trecho, Subtrecho, Segmento, Extensão, Contratada) is
registered by the user, who may also correct the Data Base the PDF suggested.
"""

import re
from datetime import date, datetime
from decimal import Decimal

from ..db import acquire_sync
from . import indices_repo
from .catalogo import _padrao_ilike
from .delta_p import FAMILIA_CAP, FAMILIA_EMULSOES, FAMILIAS, inicio_do_mes
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

# Data Base: sugerida pelo PDF, corrigível pelo usuário (define o mês-base do ΔP).
CAMPOS_EDITAVEIS = CAMPOS_CADASTRO + ("data_base",)

_FORMATOS_DATA_BASE = ("%d/%m/%Y", "%Y-%m-%d", "%m/%Y", "%Y-%m")


class CadastroInvalido(ValueError):
    """Alteração de cadastro recusada, com mensagem para o usuário."""


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


def _com_regioes(conn, contrato: dict) -> dict:
    cur = conn.execute(
        "SELECT familia, regiao FROM contrato_familia_regiao WHERE contrato_id = %s",
        (contrato["id"],),
    )
    contrato["regioes"] = {r["familia"]: r["regiao"] for r in cur.fetchall()}
    return contrato


def buscar(numero: str) -> dict | None:
    with acquire_sync() as conn:
        row = conn.execute("SELECT * FROM contrato WHERE numero = %s", (numero,)).fetchone()
        return _com_regioes(conn, dict(row)) if row else None


def buscar_por_id(contrato_id: int) -> dict | None:
    with acquire_sync() as conn:
        row = conn.execute("SELECT * FROM contrato WHERE id = %s", (contrato_id,)).fetchone()
        return _com_regioes(conn, dict(row)) if row else None


def listar(numero: str | None = None) -> list[dict]:
    """Contratos com o resumo da tela de lista; *numero* filtra por trecho."""
    sql = (
        "SELECT c.*, "
        "  (SELECT COUNT(*) FROM medicao_item m WHERE m.contrato_id = c.id) AS itens, "
        "  (SELECT COUNT(DISTINCT m.mes_medicao) FROM medicao_item m "
        "     WHERE m.contrato_id = c.id) AS medicoes, "
        "  (SELECT MIN(m.mes_medicao) FROM medicao_item m "
        "     WHERE m.contrato_id = c.id) AS primeiro_mes, "
        "  (SELECT MAX(m.mes_medicao) FROM medicao_item m "
        "     WHERE m.contrato_id = c.id) AS ultimo_mes "
        "FROM contrato c"
    )
    params: list = []
    padrao = _padrao_ilike(numero)
    if padrao:
        sql += " WHERE c.numero ILIKE %s"
        params.append(padrao)
    sql += " ORDER BY c.numero"
    with acquire_sync() as conn:
        contratos = [_com_regioes(conn, dict(r)) for r in conn.execute(sql, params).fetchall()]
    for contrato in contratos:
        contrato["faltantes"] = campos_faltantes(contrato)
    return contratos


def _data_base(valor) -> date:
    """A Data Base como primeiro dia do mês, a partir do que o usuário digitou."""
    if isinstance(valor, datetime):
        return inicio_do_mes(valor.date())
    if isinstance(valor, date):
        return inicio_do_mes(valor)
    texto = str(valor or "").strip()
    if not texto:
        raise CadastroInvalido("A Data Base não pode ficar vazia: sem ela não há ΔP.")
    for formato in _FORMATOS_DATA_BASE:
        try:
            return inicio_do_mes(datetime.strptime(texto, formato).date())
        except ValueError:
            continue
    raise CadastroInvalido(f"Data Base {texto!r} ilegível; use MM/AAAA ou AAAA-MM-DD.")


def _regioes_validas(regioes: dict | None) -> dict[str, str]:
    """Família → grafia gravada da região, recusando o que não tem preço ANP."""
    validas = {}
    for familia, regiao in (regioes or {}).items():
        if familia not in FAMILIAS:
            raise CadastroInvalido(
                f"Família desconhecida: {familia!r}. Use {' ou '.join(FAMILIAS)}."
            )
        grafia = indices_repo.normalizar_regiao(regiao)
        if grafia is None:
            disponiveis = indices_repo.regioes_disponiveis()
            lista = (", ".join(disponiveis) if disponiveis
                     else "nenhuma — importe os preços ANP primeiro")
            raise CadastroInvalido(
                f"Região {regiao!r} sem preços ANP do CAP 50/70. "
                f"Regiões disponíveis: {lista}."
            )
        validas[familia] = grafia
    return validas


def atualizar(contrato_id: int, dados: dict, regioes: dict | None = None) -> bool:
    """Grava campos do cadastro, a Data Base e as regiões, tudo ou nada.

    Valida antes de abrir a transação, para que um campo errado não deixe metade
    do formulário gravada. Devolve False quando o contrato não existe.
    """
    desconhecidos = sorted(set(dados) - set(CAMPOS_EDITAVEIS))
    if desconhecidos:
        raise CadastroInvalido(f"Campo(s) não editável(is): {', '.join(desconhecidos)}.")
    campos = dict(dados)
    if "extensao" in campos:
        campos["extensao"] = _extensao(campos["extensao"])
    if "data_base" in campos:
        campos["data_base"] = _data_base(campos["data_base"])
    regioes_ok = _regioes_validas(regioes)

    with acquire_sync() as conn:
        existe = conn.execute(
            "SELECT 1 FROM contrato WHERE id = %s FOR UPDATE", (contrato_id,)
        ).fetchone()
        if not existe:
            return False
        if campos:
            atribuicoes = ", ".join(f"{k} = %({k})s" for k in campos)
            conn.execute(
                f"UPDATE contrato SET {atribuicoes}, atualizado_em = now() "
                "WHERE id = %(id)s",
                {**campos, "id": contrato_id},
            )
        for familia, regiao in regioes_ok.items():
            conn.execute(
                "INSERT INTO contrato_familia_regiao (contrato_id, familia, regiao) "
                "VALUES (%s, %s, %s) "
                "ON CONFLICT (contrato_id, familia) DO UPDATE SET regiao = EXCLUDED.regiao",
                (contrato_id, familia, regiao),
            )
    return True


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
    """Grava os campos editáveis de um contrato identificado pelo número.

    Chaves fora de ``CAMPOS_EDITAVEIS`` são ignoradas (o formulário do Dash manda
    o que tem); a API usa ``atualizar``, que as recusa.
    """
    contrato = buscar(numero)
    if contrato is None:
        return False
    campos = {k: v for k, v in dados.items() if k in CAMPOS_EDITAVEIS}
    if not campos:
        return False
    return atualizar(contrato["id"], campos)


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
