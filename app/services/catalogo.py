"""Catálogo de produtos: código de serviço → produto → família do cálculo.

O *código* é a chave, nunca a descrição: o OCR corrompe descrições mas não
códigos numéricos, e o mesmo material aparece sob vários códigos entre
contratos. O usuário cadastra os produtos que quer ver na planilha (descrição
livre + família) e associa a eles *alguns* códigos. Código sem associação fica
fora do cálculo — não é pendência e não bloqueia nada. A associação é
retroativa: ``medicao_item`` guarda todos os itens extraídos, então associar um
código traz para o cálculo tudo o que já foi processado com ele.
"""

import psycopg

from ..db import acquire_sync
from .delta_p import FAMILIA_CAP, FAMILIA_EMULSOES, FAMILIAS

# Rótulos de exibição das famílias. Ficam no código porque as famílias são as
# duas fórmulas do art. 16, não dados do usuário.
ROTULOS_FAMILIA = {
    FAMILIA_CAP: "Aquisição de CAP",
    FAMILIA_EMULSOES: "Aquisição de Emulsões",
}

_COLUNAS_PRODUTO = "p.id, p.descricao_export, p.familia, p.ordem"


class ErroCatalogo(ValueError):
    """Operação recusada, com mensagem para o usuário."""


class ProdutoDuplicado(ErroCatalogo):
    """Já existe um produto com essa descrição de exportação."""


def _validar_familia(familia: str) -> None:
    if familia not in FAMILIAS:
        raise ErroCatalogo(
            f"Família desconhecida: {familia!r}. Use {FAMILIA_CAP} ou {FAMILIA_EMULSOES}."
        )


def _validar_descricao(descricao: str | None) -> str:
    texto = (descricao or "").strip()
    if not texto:
        raise ErroCatalogo("A descrição do produto não pode ficar vazia.")
    return texto


def listar_produtos() -> list[dict]:
    with acquire_sync() as conn:
        cur = conn.execute(
            f"SELECT {_COLUNAS_PRODUTO}, "
            "  (SELECT COUNT(*) FROM produto_codigo pc WHERE pc.produto_id = p.id) "
            "    AS codigos "
            "FROM produto p ORDER BY p.familia, p.ordem, p.descricao_export"
        )
        return [dict(r) for r in cur.fetchall()]


def buscar_produto(produto_id: int) -> dict | None:
    with acquire_sync() as conn:
        cur = conn.execute(
            f"SELECT {_COLUNAS_PRODUTO}, "
            "  (SELECT COUNT(*) FROM produto_codigo pc WHERE pc.produto_id = p.id) "
            "    AS codigos "
            "FROM produto p WHERE p.id = %s",
            (produto_id,),
        )
        row = cur.fetchone()
    return dict(row) if row else None


def criar_produto(descricao_export: str, familia: str, ordem: int = 0) -> int:
    """Cria ou atualiza pela descrição (upsert). Usado pelo Dash e por testes."""
    _validar_familia(familia)
    with acquire_sync() as conn:
        cur = conn.execute(
            "INSERT INTO produto (descricao_export, familia, ordem) "
            "VALUES (%s, %s, %s) "
            "ON CONFLICT (descricao_export) DO UPDATE SET "
            "familia = EXCLUDED.familia, ordem = EXCLUDED.ordem RETURNING id",
            (descricao_export, familia, ordem),
        )
        return cur.fetchone()["id"]


def novo_produto(descricao_export: str, familia: str, ordem: int = 0) -> int:
    """Cria um produto; descrição já usada é recusada, não sobrescrita."""
    descricao = _validar_descricao(descricao_export)
    _validar_familia(familia)
    try:
        with acquire_sync() as conn:
            cur = conn.execute(
                "INSERT INTO produto (descricao_export, familia, ordem) "
                "VALUES (%s, %s, %s) RETURNING id",
                (descricao, familia, ordem),
            )
            return cur.fetchone()["id"]
    except psycopg.errors.UniqueViolation as e:
        raise ProdutoDuplicado(
            f"Já existe um produto com a descrição '{descricao}'."
        ) from e


def atualizar_produto(
    produto_id: int,
    *,
    descricao_export: str | None = None,
    familia: str | None = None,
    ordem: int | None = None,
) -> dict | None:
    """Altera os campos informados. Devolve o produto, ou None se não existe."""
    campos: dict = {}
    if descricao_export is not None:
        campos["descricao_export"] = _validar_descricao(descricao_export)
    if familia is not None:
        _validar_familia(familia)
        campos["familia"] = familia
    if ordem is not None:
        campos["ordem"] = ordem
    if campos:
        atribuicoes = ", ".join(f"{k} = %({k})s" for k in campos)
        campos["id"] = produto_id
        try:
            with acquire_sync() as conn:
                conn.execute(
                    f"UPDATE produto SET {atribuicoes} WHERE id = %(id)s", campos
                )
        except psycopg.errors.UniqueViolation as e:
            raise ProdutoDuplicado(
                f"Já existe um produto com a descrição '{campos['descricao_export']}'."
            ) from e
    return buscar_produto(produto_id)


def excluir_produto(produto_id: int) -> bool:
    """Remove o produto e, em cascata, as associações de código."""
    with acquire_sync() as conn:
        cur = conn.execute("DELETE FROM produto WHERE id = %s", (produto_id,))
        return cur.rowcount > 0


def buscar_por_codigo(codigo: str) -> dict | None:
    with acquire_sync() as conn:
        cur = conn.execute(
            "SELECT pc.codigo_servico, pc.descricao_pdf, "
            "       p.id AS produto_id, p.descricao_export, p.familia, p.ordem "
            "FROM produto_codigo pc JOIN produto p ON p.id = pc.produto_id "
            "WHERE pc.codigo_servico = %s",
            (codigo,),
        )
        row = cur.fetchone()
    return dict(row) if row else None


def registrar_codigo(
    codigo: str, produto_id: int, *, descricao_pdf: str | None = None
) -> None:
    """Associa *codigo* a *produto_id*, ou troca o produto de um já associado.

    Aceita código ainda não extraído: o usuário pode preparar o catálogo antes
    de enviar os PDFs.
    """
    try:
        with acquire_sync() as conn:
            conn.execute(
                "INSERT INTO produto_codigo (codigo_servico, produto_id, descricao_pdf) "
                "VALUES (%s, %s, %s) "
                "ON CONFLICT (codigo_servico) DO UPDATE SET "
                "produto_id = EXCLUDED.produto_id, "
                "descricao_pdf = COALESCE(EXCLUDED.descricao_pdf, "
                "                         produto_codigo.descricao_pdf)",
                (codigo, produto_id, descricao_pdf),
            )
    except psycopg.errors.ForeignKeyViolation as e:
        raise ErroCatalogo(f"Produto {produto_id} não existe.") from e


def desassociar_codigo(codigo: str) -> bool:
    with acquire_sync() as conn:
        cur = conn.execute(
            "DELETE FROM produto_codigo WHERE codigo_servico = %s", (codigo,)
        )
        return cur.rowcount > 0


def codigos_associados() -> dict[str, dict]:
    """Todo código associado, pela chave do código — o que entra no cálculo."""
    with acquire_sync() as conn:
        cur = conn.execute(
            "SELECT pc.codigo_servico, p.id AS produto_id, p.descricao_export, "
            "       p.familia, p.ordem "
            "FROM produto_codigo pc JOIN produto p ON p.id = pc.produto_id"
        )
        return {r["codigo_servico"]: dict(r) for r in cur.fetchall()}


def padrao_ilike(q: str | None) -> str | None:
    """``%q%`` com os curingas do usuário escapados, ou None se *q* está vazio.

    ``%`` e ``_`` digitados são texto: quem procura "100%" quer o sinal, não
    "qualquer coisa depois de 100".
    """
    texto = (q or "").strip()
    if not texto:
        return None
    escapado = texto.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escapado}%"


def buscar_codigos(
    q: str | None = None,
    associado: bool | None = None,
    limite: int = 500,
    produto_id: int | None = None,
) -> list[dict]:
    """Códigos distintos extraídos ou associados, para localizar e associar.

    *q* filtra código **ou** descrição do PDF, sem diferenciar maiúsculas — uma
    caixa de texto livre. *associado* restringe a associados (True) ou livres
    (False); *produto_id*, aos códigos de um produto.
    """
    with acquire_sync() as conn:
        cur = conn.execute(
            "WITH extraidos AS ("
            "  SELECT codigo_servico, COUNT(*) AS ocorrencias, "
            "         COUNT(DISTINCT contrato_id) AS contratos, "
            "         (ARRAY_AGG(descricao_pdf ORDER BY id DESC))[1] AS descricao_pdf "
            "  FROM medicao_item GROUP BY codigo_servico"
            "), codigos AS ("
            "  SELECT codigo_servico FROM medicao_item "
            "  UNION SELECT codigo_servico FROM produto_codigo"
            ") "
            "SELECT c.codigo_servico AS codigo, "
            "       COALESCE(e.descricao_pdf, pc.descricao_pdf) AS descricao_pdf, "
            "       COALESCE(e.contratos, 0) AS contratos, "
            "       COALESCE(e.ocorrencias, 0) AS ocorrencias, "
            "       p.id AS produto_id, p.descricao_export, p.familia "
            "FROM codigos c "
            "LEFT JOIN extraidos e ON e.codigo_servico = c.codigo_servico "
            "LEFT JOIN produto_codigo pc ON pc.codigo_servico = c.codigo_servico "
            "LEFT JOIN produto p ON p.id = pc.produto_id "
            "WHERE (%(padrao)s::text IS NULL "
            "       OR c.codigo_servico ILIKE %(padrao)s "
            "       OR COALESCE(e.descricao_pdf, pc.descricao_pdf) ILIKE %(padrao)s) "
            "  AND (%(associado)s::boolean IS NULL "
            "       OR (p.id IS NOT NULL) = %(associado)s) "
            "  AND (%(produto_id)s::bigint IS NULL OR p.id = %(produto_id)s) "
            "ORDER BY c.codigo_servico LIMIT %(limite)s",
            {"padrao": padrao_ilike(q), "associado": associado,
             "produto_id": produto_id, "limite": limite},
        )
        return [dict(r) for r in cur.fetchall()]


def associar_codigos(produto_id: int, codigos: list[str]) -> bool:
    """Point several codes at one product in a single transaction.

    Codes already on another product are re-pointed, like ``registrar_codigo``.
    Returns False — and writes nothing — when the product does not exist.
    """
    unicos = list(dict.fromkeys(codigos))
    with acquire_sync() as conn, conn.transaction():
        if conn.execute(
            "SELECT 1 FROM produto WHERE id = %s FOR UPDATE", (produto_id,)
        ).fetchone() is None:
            return False
        with conn.cursor() as cur:
            cur.executemany(
                "INSERT INTO produto_codigo (codigo_servico, produto_id) VALUES (%s, %s) "
                "ON CONFLICT (codigo_servico) DO UPDATE SET produto_id = EXCLUDED.produto_id",
                [(codigo, produto_id) for codigo in unicos],
            )
    return True
