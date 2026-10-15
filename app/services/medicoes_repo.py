"""Persisting the measurement rows extracted from the PDFs.

Replaces the previous arrangement where the dashboard globbed
``data/jobs/*/results/*.json``: the rows have to live next to the índices to be
crossed with them. The JSON files remain as the extraction artefact.
"""

import logging
import re
from datetime import date
from decimal import Decimal, InvalidOperation

from ..db import acquire_sync
from . import indices_repo
from .catalogo import padrao_ilike
from .contratos_repo import mes_da_medicao

logger = logging.getLogger(__name__)

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


_SELECT_ITEM = (
    "SELECT m.id, m.mes_medicao AS mes, m.codigo_servico AS codigo, "
    "       m.descricao_pdf, round(m.valor_pi, 2) AS valor_pi, m.fator, "
    "       trunc(m.valor_pi * m.fator, 2) AS reajuste, "
    "       m.source_file AS arquivo, m.origem, m.regiao_cap, m.regiao_emulsoes, "
    "       p.id AS produto_id, p.descricao_export AS produto, p.familia "
    "FROM medicao_item m "
    "LEFT JOIN produto_codigo pc ON pc.codigo_servico = m.codigo_servico "
    "LEFT JOIN produto p ON p.id = pc.produto_id "
)


def gravar_itens(
    contrato_id: int,
    rows: list[dict],
    job_id: str | None = None,
    *,
    atualizar: bool = False,
    limpar_regioes: bool = False,
) -> int:
    """Store the item rows of one extracted file; returns how many were stored.

    Idempotent: the ``UNIQUE (contrato_id, codigo_servico, mes_medicao,
    source_file)`` key means reprocessing the same PDF updates its rows instead
    of duplicating them. Rows the user edited (``origem = 'editado'``) or deleted
    (``excluido``) are left alone — unless ``atualizar``, the user's explicit
    "Atualizar registros já importados": then those rows take the PDF's values
    again and come back as ``'pdf'``, keeping a pinned region unless
    ``limpar_regioes``. Manual records have no source file and are never touched.

    Every item with a service code is stored, associated in the catalogue or
    not: associating a code later brings its past items into the calculation
    without reprocessing the PDFs.

    A service code can recur within the same month/file across more than one
    work group of the contract (e.g. the same material measured under both
    "conservação corretiva" and "conservação preventiva"), or as a reversal/
    audit line the PDF prints under "ESTORNOS/RESSARCIMENTOS" with ``Fator``
    always ``0`` — real or not (a reversal can carry a genuine, sometimes
    negative, ``Valor a PI Líquido``). ``Fator = 0`` on its own is **not** a
    reliable "this line is a reversal" signal: a code measured for the first
    time, before its first reajustamento, legitimately has ``Fator = 0`` too
    — and there ``Fator = 0`` is every occurrence of that (código, mês,
    arquivo), because no other group offers anything better.

    So the rule only discards a ``Fator = 0`` occurrence when a **better**
    occurrence exists for the same (código, mês, arquivo) — one with
    ``Fator != 0``: those are summed, keeping the shared ``Fator`` (confirmed
    identical across every real occurrence within one file). When every
    occurrence of a (código, mês, arquivo) has ``Fator = 0``, they are kept
    and summed as-is — there being nothing else to prefer over them.
    """
    grupos: dict[tuple[str, date, str], list[dict]] = {}

    for row in rows:
        codigo = str(row.get("Serviço") or "").strip()
        if not _CODIGO_RE.match(codigo):
            continue
        mes = mes_da_medicao(row.get("Período Líquido"))
        valor_pi = _decimal(row.get("Valor a PI Líquido"))
        fator = _decimal(row.get("Fator"))
        if mes is None or valor_pi is None or fator is None:
            continue

        source_file = str(row.get("Source_File") or "")
        chave = (codigo, mes, source_file)
        grupos.setdefault(chave, []).append(
            {
                "descricao_pdf": str(row.get("Descrição") or "").strip(),
                "valor_pi": valor_pi,
                "fator": fator,
            }
        )

    registros = []
    for (codigo, mes, source_file), ocorrencias in grupos.items():
        com_fator = [o for o in ocorrencias if o["fator"] != 0] or ocorrencias
        if com_fator is not ocorrencias:
            for descartada in ocorrencias:
                if descartada["fator"] == 0 and descartada["valor_pi"] != 0:
                    logger.warning(
                        "'%s' código %s, %s: ocorrência com Fator 0 e valor"
                        " %s descartada (existe alternativa com Fator != 0).",
                        source_file, codigo, mes, descartada["valor_pi"],
                    )
        fatores = {o["fator"] for o in com_fator}
        if len(fatores) > 1:
            logger.warning(
                "'%s' código %s, %s: fatores divergentes entre ocorrências (%s);"
                " usando o da primeira.",
                source_file, codigo, mes, sorted(fatores),
            )
        primeira = com_fator[0]
        registros.append(
            {
                "contrato_id": contrato_id,
                "codigo_servico": codigo,
                "descricao_pdf": primeira["descricao_pdf"],
                "mes_medicao": mes,
                "valor_pi": sum(o["valor_pi"] for o in com_fator),
                "fator": primeira["fator"],
                "source_file": source_file,
                "job_id": job_id,
            }
        )

    if atualizar:
        # O usuário pediu e confirmou: o PDF vence o trabalho manual.
        restaurar = ", origem = 'pdf', excluido = false, atualizado_em = now()"
        if limpar_regioes:
            restaurar += ", regiao_cap = NULL, regiao_emulsoes = NULL"
        condicao = ""
    else:
        # Trabalho manual vence o PDF: um registro editado ou excluído pelo
        # usuário não é sobrescrito nem volta ao reprocessar.
        restaurar = ""
        condicao = " WHERE medicao_item.origem = 'pdf' AND NOT medicao_item.excluido"

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
                    "  WHERE origem <> 'manual' "
                    "DO UPDATE SET valor_pi = EXCLUDED.valor_pi, "
                    "  fator = EXCLUDED.fator, job_id = EXCLUDED.job_id, "
                    "  descricao_pdf = EXCLUDED.descricao_pdf" + restaurar + condicao,
                    registros,
                )

    return len(registros)


def itens_para_export(contrato_id: int) -> list[dict]:
    """Items that belong in the spreadsheet, ordered family → product → month.

    Only codes associated with a product: the rest stays out of the calculation.
    """
    with acquire_sync() as conn:
        cur = conn.execute(
            "SELECT m.id, m.mes_medicao, m.codigo_servico, m.valor_pi, m.fator, "
            "       m.source_file, m.origem, m.regiao_cap, m.regiao_emulsoes, "
            "       p.descricao_export, p.familia, p.ordem, p.id AS produto_id "
            "FROM medicao_item m "
            "JOIN produto_codigo pc ON pc.codigo_servico = m.codigo_servico "
            "JOIN produto p ON p.id = pc.produto_id "
            "WHERE m.contrato_id = %s AND NOT m.excluido "
            # When the same measurement arrives under two file names, the export
            # keeps the first row: a user-edited one wins, else the most recently
            # stored (m.id DESC).
            "ORDER BY p.familia, p.ordem, p.descricao_export, m.mes_medicao, "
            "  (m.origem = 'editado') DESC, m.id DESC",
            (contrato_id,),
        )
        return [dict(r) for r in cur.fetchall()]


def listar_itens(
    contrato_id: int,
    *,
    mes: date | None = None,
    no_calculo: bool | None = None,
    q: str | None = None,
    arquivo: str | None = None,
) -> list[dict]:
    """Every extracted item of a contract, with its catalogue product or None.

    The read-only view of the measurements: unlike ``itens_para_export`` it keeps
    the codes without a product, which is how the user finds what to associate.
    ``reajuste`` truncates like column F of the spreadsheet. ``arquivo`` is the
    source file (``'manual'`` for the records the user created).
    """
    with acquire_sync() as conn:
        cur = conn.execute(
            _SELECT_ITEM +
            "WHERE m.contrato_id = %(contrato)s AND NOT m.excluido "
            "  AND (%(mes)s::date IS NULL OR m.mes_medicao = %(mes)s) "
            "  AND (%(no_calculo)s::boolean IS NULL "
            "       OR (p.id IS NOT NULL) = %(no_calculo)s) "
            "  AND (%(padrao)s::text IS NULL "
            "       OR m.codigo_servico ILIKE %(padrao)s "
            "       OR m.descricao_pdf ILIKE %(padrao)s) "
            "  AND (%(arquivo)s::text IS NULL OR m.source_file = %(arquivo)s) "
            "ORDER BY m.mes_medicao, m.codigo_servico, m.id",
            {"contrato": contrato_id, "mes": mes, "no_calculo": no_calculo,
             "padrao": padrao_ilike(q), "arquivo": arquivo},
        )
        return [dict(r) for r in cur.fetchall()]


def meses_do_contrato(contrato_id: int) -> list:
    with acquire_sync() as conn:
        cur = conn.execute(
            "SELECT DISTINCT mes_medicao FROM medicao_item WHERE contrato_id = %s "
            "  AND NOT excluido ORDER BY mes_medicao",
            (contrato_id,),
        )
        return [r["mes_medicao"] for r in cur.fetchall()]


class MedicaoInvalida(ValueError):
    """Registro de medição recusado, com mensagem para o usuário."""


CAMPOS_ITEM = ("mes", "codigo", "descricao_pdf", "valor_pi", "fator",
               "regiao_cap", "regiao_emulsoes")
# A chave com que o reprocessamento reencontra um registro do PDF: mudá-la
# faria o PDF reenviado criar um registro novo, duplicado.
_CHAVE_PDF = ("mes", "codigo")
_COLUNA = {"mes": "mes_medicao", "codigo": "codigo_servico"}
_MES_RE = re.compile(r"^(\d{4})-(0[1-9]|1[0-2])$")


def _validar(dados: dict, *, completo: bool) -> dict:
    """Os campos de *dados* convertidos para as colunas, ou MedicaoInvalida.

    Tudo é validado antes de qualquer escrita, e todos os problemas são
    relatados de uma vez.
    """
    desconhecidos = sorted(set(dados) - set(CAMPOS_ITEM))
    if desconhecidos:
        raise MedicaoInvalida(f"Campo(s) não editável(is): {', '.join(desconhecidos)}.")
    obrigatorios = ("mes", "codigo", "valor_pi", "fator") if completo else ()
    erros = [f"{c}: obrigatório." for c in obrigatorios if dados.get(c) in (None, "")]
    colunas: dict = {}
    for campo, valor in dados.items():
        if campo in obrigatorios and valor in (None, ""):
            continue
        if campo == "mes":
            mes = _mes("mes", valor, erros)
            if mes is not None:
                colunas["mes_medicao"] = mes
        elif campo == "codigo":
            codigo = str(valor or "").strip()
            if not _CODIGO_RE.match(codigo):
                erros.append("codigo: o código de serviço tem 4 ou mais dígitos.")
                continue
            colunas["codigo_servico"] = codigo
        elif campo in ("valor_pi", "fator"):
            numero = None if valor is None else _decimal(valor)
            if numero is None or not numero.is_finite():
                erros.append(f"{campo}: informe um número.")
                continue
            colunas[campo] = numero
        elif campo == "descricao_pdf":
            colunas[campo] = (str(valor).strip() or None) if valor is not None else None
        else:  # regiao_cap / regiao_emulsoes
            colunas[campo] = _regiao(campo, valor, erros)
    if erros:
        raise MedicaoInvalida("\n".join(erros))
    return colunas


def _regiao(campo: str, valor, erros: list[str]) -> str | None:
    """A região na grafia do arquivo da ANP; vazio é seguir o contrato."""
    if valor in (None, ""):
        return None
    grafia = indices_repo.normalizar_regiao(str(valor))
    if grafia is None:
        erros.append(
            f"{campo}: região {valor!r} sem preços ANP do CAP 50/70; "
            "escolha uma das regiões importadas."
        )
    return grafia


def _mes(campo: str, valor, erros: list[str]) -> date | None:
    achado = _MES_RE.match(str(valor or ""))
    if not achado:
        erros.append(f"{campo}: mês inválido; use AAAA-MM.")
        return None
    return date(int(achado[1]), int(achado[2]), 1)


_COLUNA_REGIAO = {"CAP": "regiao_cap", "EMULSOES": "regiao_emulsoes"}
_ROTULO_FAMILIA = {"CAP": "CAP", "EMULSOES": "Emulsões"}


def _conferir_familia(conn, codigo: str, colunas: dict) -> None:
    """Recusa a região da família a que o código não pertence.

    O cálculo só lê a região da família do produto (``_anotar_regioes``): a da
    outra seria gravada e mostrada na lista sem efeito nenhum no cálculo nem na
    planilha. Limpar é sempre aceito, e um código sem produto aceita as duas.
    """
    linha = conn.execute(
        "SELECT p.familia FROM produto_codigo pc JOIN produto p ON p.id = pc.produto_id "
        "WHERE pc.codigo_servico = %s",
        (codigo,),
    ).fetchone()
    if linha is None:
        return
    familia = linha["familia"]
    erros = [
        f"{coluna}: o código {codigo} é de {_ROTULO_FAMILIA[familia]}; "
        f"só a região de {_ROTULO_FAMILIA[familia]} vale para ele."
        for outra, coluna in _COLUNA_REGIAO.items()
        if outra != familia and colunas.get(coluna) is not None
    ]
    if erros:
        raise MedicaoInvalida("\n".join(erros))


def aplicar_regiao(contrato_id: int, familia: str, mes_de: str, mes_ate: str,
                   regiao: str | None, *, simular: bool = False) -> int:
    """Fixa *regiao* em todos os registros da família no período; devolve quantos.

    É a mesma região por registro de ``atualizar_item``, gravada de uma vez nos
    registros cujo código pertence a um produto da *familia* e cujo mês está entre
    *mes_de* e *mes_ate* (``AAAA-MM``, inclusive). Região vazia volta a seguir o
    contrato. Um registro do PDF passa a 'editado'. ``simular`` só conta, para a
    tela confirmar antes de gravar.
    """
    erros: list[str] = []
    coluna = _COLUNA_REGIAO.get(familia)
    if coluna is None:
        erros.append("familia: use CAP ou EMULSOES.")
    inicio = _mes("mes_de", mes_de, erros)
    fim = _mes("mes_ate", mes_ate, erros)
    if inicio and fim and inicio > fim:
        erros.append("mes_ate: o período termina antes de começar.")
    grafia = _regiao("regiao", regiao, erros)
    if erros:
        raise MedicaoInvalida("\n".join(erros))
    produtos = "produto_codigo pc JOIN produto p ON p.id = pc.produto_id"
    alcance = (
        "WHERE pc.codigo_servico = m.codigo_servico AND p.familia = %(familia)s "
        "  AND m.contrato_id = %(contrato)s AND NOT m.excluido "
        "  AND m.mes_medicao BETWEEN %(inicio)s AND %(fim)s"
    )
    params = {"regiao": grafia, "familia": familia, "contrato": contrato_id,
              "inicio": inicio, "fim": fim}
    with acquire_sync() as conn:
        if simular:
            return conn.execute(
                f"SELECT count(*) AS n FROM medicao_item m, {produtos} {alcance}", params
            ).fetchone()["n"]
        cur = conn.execute(
            f"UPDATE medicao_item m SET {coluna} = %(regiao)s, atualizado_em = now(), "
            "  origem = CASE m.origem WHEN 'pdf' THEN 'editado' ELSE m.origem END "
            f"FROM {produtos} {alcance}",
            params,
        )
        return cur.rowcount


def buscar_item(contrato_id: int, item_id: int) -> dict | None:
    with acquire_sync() as conn:
        cur = conn.execute(
            _SELECT_ITEM + "WHERE m.contrato_id = %s AND m.id = %s AND NOT m.excluido",
            (contrato_id, item_id),
        )
        linha = cur.fetchone()
        return dict(linha) if linha else None


def incluir_item(contrato_id: int, dados: dict) -> int | None:
    """Inclui um registro manual; None quando o contrato não existe."""
    colunas = _validar(dados, completo=True)
    with acquire_sync() as conn:
        if conn.execute("SELECT 1 FROM contrato WHERE id = %s", (contrato_id,)).fetchone() is None:
            return None
        _conferir_familia(conn, colunas["codigo_servico"], colunas)
        cur = conn.execute(
            "INSERT INTO medicao_item (contrato_id, codigo_servico, descricao_pdf, "
            "  mes_medicao, valor_pi, fator, source_file, origem, regiao_cap, "
            "  regiao_emulsoes, atualizado_em) "
            "VALUES (%(contrato_id)s, %(codigo_servico)s, %(descricao_pdf)s, "
            "  %(mes_medicao)s, %(valor_pi)s, %(fator)s, 'manual', 'manual', "
            "  %(regiao_cap)s, %(regiao_emulsoes)s, now()) RETURNING id",
            {"contrato_id": contrato_id, "descricao_pdf": None, "regiao_cap": None,
             "regiao_emulsoes": None, **colunas},
        )
        return cur.fetchone()["id"]


def atualizar_item(contrato_id: int, item_id: int, dados: dict) -> bool:
    """Altera um registro; um registro do PDF passa a 'editado'.

    Código e mês só mudam num registro manual (ver ``_CHAVE_PDF``).
    """
    colunas = _validar(dados, completo=False)
    with acquire_sync() as conn:
        atual = conn.execute(
            "SELECT origem, codigo_servico FROM medicao_item "
            "WHERE contrato_id = %s AND id = %s AND NOT excluido",
            (contrato_id, item_id),
        ).fetchone()
        if atual is None:
            return False
        if atual["origem"] != "manual" and any(_COLUNA[c] in colunas for c in _CHAVE_PDF):
            raise MedicaoInvalida(
                "O código e mês de um registro extraído do PDF não podem ser "
                "alterados: exclua-o e inclua um registro manual."
            )
        if not colunas:
            return True
        _conferir_familia(conn, colunas.get("codigo_servico", atual["codigo_servico"]), colunas)
        atribuicoes = ", ".join(f"{c} = %({c})s" for c in colunas)
        conn.execute(
            f"UPDATE medicao_item SET {atribuicoes}, atualizado_em = now(), "
            "  origem = CASE origem WHEN 'pdf' THEN 'editado' ELSE origem END "
            "WHERE id = %(id)s",
            {**colunas, "id": item_id},
        )
        return True


def excluir_item(contrato_id: int, item_id: int) -> bool:
    """Apaga um registro manual; um do PDF é só marcado, para não voltar."""
    return excluir_itens(contrato_id, [item_id]) > 0


def excluir_itens(contrato_id: int, ids: list[int]) -> int:
    """``excluir_item`` para vários registros, numa transação; devolve quantos.

    Ids de outro contrato, inexistentes ou já excluídos não contam.
    """
    with acquire_sync() as conn:
        apagados = conn.execute(
            "DELETE FROM medicao_item "
            "WHERE contrato_id = %s AND id = ANY(%s) AND origem = 'manual'",
            (contrato_id, ids),
        ).rowcount
        marcados = conn.execute(
            "UPDATE medicao_item SET excluido = true, atualizado_em = now() "
            "WHERE contrato_id = %s AND id = ANY(%s) AND NOT excluido",
            (contrato_id, ids),
        ).rowcount
        return apagados + marcados
