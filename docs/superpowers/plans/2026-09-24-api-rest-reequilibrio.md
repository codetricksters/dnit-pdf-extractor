# API REST e correção do modelo do reequilíbrio — Plano de implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Corrigir o modelo de domínio (catálogo sem pendências, índices globais editáveis com origem, Data Base editável, simulação de região na exportação) e expor tudo numa API REST em `/api/v1`, validada por um teste ponta a ponta com índices reais.

**Architecture:** Os repositórios síncronos existentes (`app/services/*_repo.py`, `catalogo.py`) ganham as operações novas; dois módulos puros (`importadores.py`, `exportadores.py`) leem e escrevem os arquivos de índices, e `importacao.py` orquestra prévia/gravação contra o banco. Routers FastAPI finos em `app/routers/api/` chamam os serviços via `asyncio.to_thread`, com schemas Pydantic. O cálculo JSON e a planilha saem da mesma função (`reequilibrio_export.calcular`).

**Tech Stack:** Python 3.12, FastAPI 0.137, Pydantic 2.13, psycopg 3 (SQL puro), PostgreSQL 16 + `btree_gist`, openpyxl, xlrd 2, pytest (`asyncio_mode=auto`), httpx2 `ASGITransport`.

**Spec:** `docs/superpowers/specs/2026-09-24-api-rest-reequilibrio-design.md`

## Global Constraints

- Documentação, mensagens ao usuário e mensagens de commit em **português**. Todo commit termina com a linha `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- **O Dash fica congelado durante A.** Só as edições mínimas de compatibilidade listadas nas tarefas; testes do Dash que quebrarem recebem `@pytest.mark.skip(reason="Dash congelado até o subprojeto B")`.
- As rotas atuais (`/upload`, `/jobs`, `/admin`, `/reequilibrio/planilha`) continuam funcionando sem alteração de contrato.
- A planilha `Reequilíbrio - 26 - Contrato 716-22.xlsx` **nunca** é lida pelo seed nem pela aplicação. Só `scripts/gerar_fixtures_e2e.py` a lê, uma vez, para gerar as fixtures versionadas.
- Dinheiro e índices em `NUMERIC`/`Decimal`; nunca `float` antes da escrita na célula xlsx.
- Semana ANP: intervalo `[início, fim]` com pontas inclusas; o mês `m` usa a semana que contém o **dia 15**. Semanas sobrepostas são proibidas (mesmo produto e região). Semana sem cotação no dia de referência **recusa** o cálculo; sem fallback.
- Importação é **tudo ou nada**; `origem = 'manual'` é preservada por padrão (`sobrescrever_manuais=false`); `simular=true` não grava.
- Limite de upload de índices: **20 MB** (`413` acima disso).
- Valores do cabeçalho `X-Avisos` precisam ser latin-1: acentos do português servem; `Δ`, travessão (`–`) e reticências (`…`) não. Mensagens que vão para `X-Avisos` não podem conter Δ, – ou …; use hífen e escreva "variação" em vez de "ΔP".
- Testes precisam do PostgreSQL: `docker compose up -d postgres` (porta 5433). Cada teste recria o schema `public`. O cliente `ASGITransport` **não** executa o lifespan: testes que exportam planilha chamam `template_repo.garantir_semente()` antes.
- Upload em testes: `files={"arquivo": (nome, bytes)}`.

---

## Mapa de arquivos

| Arquivo | Ação | Responsabilidade |
|---|---|---|
| `migrations/006_catalogo_indices.sql` | criar | tira `confirmado`; `origem`/`atualizado_em` nos índices; `btree_gist` + exclusão de sobreposição |
| `app/services/catalogo.py` | reescrever | produtos (CRUD), associação de códigos, `buscar_codigos(q, associado)` |
| `app/services/medicoes_repo.py` | modificar | `gravar_itens` devolve `int`; `itens_para_export` sem filtro `confirmado` |
| `app/services/file_processor.py` | modificar | loga a contagem de itens |
| `app/services/progresso.py` | modificar | `pendencias = 0`, sem importar `catalogo` |
| `app/dashboard/callbacks.py` | modificar | duas linhas de compatibilidade |
| `app/services/indices_repo.py` | modificar | origem, sobreposição, edição manual, exclusão, filtros, normalização de região |
| `app/services/delta_p.py` | modificar | constante `BASE_IGP_DI` |
| `app/services/importadores.py` | criar | leitura pura do `.xls` ANP e do template IGP-DI; geração do template; detecção de sobreposição |
| `app/services/importacao.py` | criar | prévia/gravação contra o banco, com proteção de valores manuais |
| `app/services/exportadores.py` | criar | CSV/XLSX dos índices |
| `app/services/contratos_repo.py` | modificar | `atualizar` (campos, `data_base`, regiões validadas), `buscar_por_id`, `listar(numero)` |
| `app/services/reequilibrio_export.py` | modificar | `regioes_override`, `calcular`/`gerar`/`serializar`, `faltando` estruturado |
| `app/routers/api/__init__.py` | criar | `APIRouter(prefix="/api/v1")` que inclui os demais |
| `app/routers/api/erros.py` | criar | `ErroApi` + handler (`detail` com campos extras) |
| `app/routers/api/schemas.py` | criar | modelos Pydantic |
| `app/routers/api/contratos.py` | criar | `GET/PATCH /contratos` |
| `app/routers/api/catalogo.py` | criar | `/produtos`, `/codigos` |
| `app/routers/api/indices.py` | criar | `/indices/...` |
| `app/routers/api/calculo.py` | criar | `/contratos/{id}/calculo`, `/planilha` |
| `app/main.py` | modificar | inclui `api.router` e registra o handler de `ErroApi` |
| `scripts/seed_indices.py` | reescrever | usa `importacao`; `--anp`, `--igp-di` |
| `scripts/gerar_fixtures_e2e.py` | criar | gera as fixtures a partir da planilha do usuário (uso único) |
| `tests/fixtures/*` | criar | `anp_semanal.xls`, `igp_di.xlsx`, `delta_p_referencia.csv`, `contrato_ficticio.json` |
| `tests/indices_factory.py` | criar | construtores de registros ANP/IGP e de `.xls`/`.xlsx` de teste |
| `tests/test_catalogo.py` | reescrever | catálogo novo |
| `tests/test_importadores.py`, `tests/test_importacao.py`, `tests/test_exportadores.py` | criar | |
| `tests/test_api_contratos.py`, `tests/test_api_catalogo.py`, `tests/test_api_indices.py`, `tests/test_api_calculo.py` | criar | |
| `tests/test_seed.py`, `tests/test_e2e_reequilibrio.py` | criar | |
| `pyproject.toml`, `requirements.txt` | modificar | `xlrd` em runtime |
| `README.md`, `.claude/rules/{backend,architecture,deployment}.md` | modificar | Tarefa 11 |

Ordem: 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9 → 10 → 11. Cada tarefa deixa `uv run pytest -q` verde.

---

### Task 1: Catálogo sem pendências e migração 006

**Files:**
- Create: `migrations/006_catalogo_indices.sql`
- Rewrite: `app/services/catalogo.py`
- Modify: `app/services/medicoes_repo.py`, `app/services/file_processor.py:37-45`, `app/services/progresso.py:19,150`, `app/dashboard/callbacks.py:133-135,210`
- Rewrite: `tests/test_catalogo.py`
- Modify: `tests/test_contratos_repo.py`, `tests/test_reequilibrio_export.py:325`, `tests/test_dashboard.py:159`

**Interfaces:**
- Consumes: `delta_p.FAMILIA_CAP`, `FAMILIA_EMULSOES`, `FAMILIAS`; `db.acquire_sync`.
- Produces:
  - `catalogo.ROTULOS_FAMILIA: dict[str, str]`
  - `catalogo.ErroCatalogo(ValueError)`, `catalogo.ProdutoDuplicado(ErroCatalogo)`
  - `catalogo.listar_produtos() -> list[dict]` (colunas de `produto` + `codigos: int`)
  - `catalogo.buscar_produto(produto_id: int) -> dict | None`
  - `catalogo.criar_produto(descricao_export, familia, ordem=0) -> int` (upsert, mantido)
  - `catalogo.novo_produto(descricao_export, familia, ordem=0) -> int` (duplicado → `ProdutoDuplicado`)
  - `catalogo.atualizar_produto(produto_id, *, descricao_export=None, familia=None, ordem=None) -> dict | None`
  - `catalogo.excluir_produto(produto_id) -> bool`
  - `catalogo.buscar_por_codigo(codigo) -> dict | None`
  - `catalogo.registrar_codigo(codigo, produto_id, *, descricao_pdf=None) -> None` (produto inexistente → `ErroCatalogo`)
  - `catalogo.desassociar_codigo(codigo) -> bool`
  - `catalogo.codigos_associados() -> dict[str, dict]`
  - `catalogo.buscar_codigos(q=None, associado=None, limite=500) -> list[dict]` com chaves `codigo, descricao_pdf, contratos, ocorrencias, produto_id, descricao_export, familia`
  - `medicoes_repo.gravar_itens(...) -> int`

- [ ] **Step 1: Conferir o banco de desenvolvimento antes da constraint**

A exclusão de sobreposição falha se o banco de desenvolvimento já tiver semanas sobrepostas. Rode:

```bash
docker compose exec postgres psql -U dnit dnit -c "
SELECT a.produto, a.regiao, a.vigencia_inicio, a.vigencia_fim, b.vigencia_inicio, b.vigencia_fim
FROM anp_preco_semanal a JOIN anp_preco_semanal b
  ON a.produto = b.produto AND a.regiao = b.regiao AND a.id < b.id
 AND daterange(a.vigencia_inicio, a.vigencia_fim, '[]') && daterange(b.vigencia_inicio, b.vigencia_fim, '[]')
LIMIT 20;"
```

Expected: `(0 rows)`. Se houver linhas, **pare** e leve a lista ao usuário — a migração não pode escolher sozinha qual semana apagar.

- [ ] **Step 2: Escrever os testes do catálogo novo**

Substitua `tests/test_catalogo.py` inteiro por:

```python
"""Catálogo: produtos do usuário e a associação código → produto."""

import pytest

from app.db import acquire_sync
from app.services import catalogo, contratos_repo, medicoes_repo
from app.services.delta_p import FAMILIA_CAP, FAMILIA_EMULSOES

HEADER = {
    "Contrato": "15 00716/2022 - HWN ENGENHARIA LTDA",
    "Data Base": "01/01/2022",
}


def _item(codigo, descricao, mes=1, valor=100.0, fonte="1ª MP.pdf"):
    return {
        "Serviço": codigo,
        "Descrição": descricao,
        "Valor a PI Líquido": valor,
        "Fator": 0.1,
        "Período Líquido": f"01/{mes:02d}/2023 - 28/{mes:02d}/2023",
        "Source_File": fonte,
    }


async def test_codigos_semeados_estao_associados():
    associados = catalogo.codigos_associados()
    assert len(associados) == 9
    assert associados["8300980"]["descricao_export"] == "AQUISIÇÃO DE CAP 50/70"
    assert associados["60112"]["produto_id"] == associados["92704"]["produto_id"]
    assert associados["29083"]["familia"] == FAMILIA_EMULSOES


async def test_coluna_confirmado_nao_existe_mais():
    with acquire_sync() as conn:
        cur = conn.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'produto_codigo'"
        )
        colunas = {r["column_name"] for r in cur.fetchall()}
    assert "confirmado" not in colunas


async def test_codigo_desconhecido_nao_cria_nada():
    contrato_id = contratos_repo.registrar_do_pdf(HEADER)
    produtos_antes = len(catalogo.listar_produtos())
    gravados = medicoes_repo.gravar_itens(
        contrato_id, [_item("777123", "AQUISIÇÃO DE EMULSÃO RR-2C - TSD")]
    )
    assert gravados == 1
    assert catalogo.buscar_por_codigo("777123") is None
    assert len(catalogo.listar_produtos()) == produtos_antes
    assert medicoes_repo.itens_para_export(contrato_id) == []


async def test_associacao_e_retroativa_e_desassociar_remove_do_calculo():
    contrato_id = contratos_repo.registrar_do_pdf(HEADER)
    medicoes_repo.gravar_itens(contrato_id, [_item("777123", "RR-2C TSD")])

    produto_id = catalogo.novo_produto("Aquisição de RR-2C", FAMILIA_EMULSOES)
    catalogo.registrar_codigo("777123", produto_id)
    itens = medicoes_repo.itens_para_export(contrato_id)
    assert [i["codigo_servico"] for i in itens] == ["777123"]
    assert itens[0]["descricao_export"] == "Aquisição de RR-2C"

    assert catalogo.desassociar_codigo("777123") is True
    assert medicoes_repo.itens_para_export(contrato_id) == []
    assert catalogo.desassociar_codigo("777123") is False


async def test_associar_codigo_ainda_nao_extraido():
    produto_id = catalogo.novo_produto("Aquisição de CAP 30/45", FAMILIA_CAP)
    catalogo.registrar_codigo("999001", produto_id)
    assert catalogo.buscar_por_codigo("999001")["produto_id"] == produto_id


async def test_associar_a_produto_inexistente_e_recusado():
    with pytest.raises(catalogo.ErroCatalogo):
        catalogo.registrar_codigo("999001", 987654)


async def test_reapontar_codigo_para_outro_produto():
    novo = catalogo.novo_produto("Aquisição de CAP (outro)", FAMILIA_CAP)
    catalogo.registrar_codigo("60112", novo)
    assert catalogo.buscar_por_codigo("60112")["produto_id"] == novo


async def test_criar_produto_recusa_familia_invalida():
    with pytest.raises(ValueError):
        catalogo.criar_produto("X", "ASFALTO")
    with pytest.raises(catalogo.ErroCatalogo):
        catalogo.novo_produto("X", "ASFALTO")


async def test_descricao_vazia_e_recusada():
    with pytest.raises(catalogo.ErroCatalogo):
        catalogo.novo_produto("   ", FAMILIA_CAP)


async def test_novo_produto_duplicado():
    catalogo.novo_produto("Aquisição de CAP 50/70 (meu)", FAMILIA_CAP)
    with pytest.raises(catalogo.ProdutoDuplicado):
        catalogo.novo_produto("Aquisição de CAP 50/70 (meu)", FAMILIA_CAP)


async def test_atualizar_produto():
    produto_id = catalogo.novo_produto("Provisório", FAMILIA_CAP)
    atualizado = catalogo.atualizar_produto(
        produto_id, descricao_export="Definitivo", familia=FAMILIA_EMULSOES, ordem=7
    )
    assert atualizado["descricao_export"] == "Definitivo"
    assert atualizado["familia"] == FAMILIA_EMULSOES
    assert atualizado["ordem"] == 7
    assert catalogo.atualizar_produto(987654, ordem=1) is None


async def test_atualizar_para_descricao_existente_e_recusado():
    produto_id = catalogo.novo_produto("Provisório", FAMILIA_CAP)
    with pytest.raises(catalogo.ProdutoDuplicado) as erro:
        catalogo.atualizar_produto(produto_id, descricao_export="AQUISIÇÃO DE CAP 50/70")
    assert "AQUISIÇÃO DE CAP 50/70" in str(erro.value)


async def test_excluir_produto_remove_as_associacoes():
    produto_id = catalogo.novo_produto("Temporário", FAMILIA_CAP)
    catalogo.registrar_codigo("999002", produto_id)
    assert catalogo.excluir_produto(produto_id) is True
    assert catalogo.buscar_por_codigo("999002") is None
    assert catalogo.buscar_produto(produto_id) is None
    assert catalogo.excluir_produto(produto_id) is False


async def test_buscar_codigos_lista_extraidos_e_associados():
    contrato_id = contratos_repo.registrar_do_pdf(HEADER)
    medicoes_repo.gravar_itens(
        contrato_id,
        [
            _item("60112", "AQUISIÇÃO DE CIMENTO ASFÁLTICO CAP 50/70", mes=1),
            _item("60112", "AQUISIÇÃO DE CIMENTO ASFÁLTICO CAP 50/70", mes=2),
            _item("54393", "ESCAVAÇÃO, CARGA E TRANSPORTE", mes=1),
        ],
    )
    por_codigo = {c["codigo"]: c for c in catalogo.buscar_codigos()}

    assert por_codigo["60112"]["ocorrencias"] == 2
    assert por_codigo["60112"]["contratos"] == 1
    assert por_codigo["60112"]["descricao_export"] == "AQUISIÇÃO DE CAP 50/70"
    assert por_codigo["54393"]["produto_id"] is None
    # Associado mas nunca extraído também aparece, com contagem zero.
    assert por_codigo["133004"]["ocorrencias"] == 0
    assert por_codigo["133004"]["descricao_pdf"] is None


async def test_buscar_codigos_filtra_por_codigo_ou_descricao():
    contrato_id = contratos_repo.registrar_do_pdf(HEADER)
    medicoes_repo.gravar_itens(
        contrato_id,
        [_item("54393", "Escavação, carga e transporte"), _item("54394", "Drenagem")],
    )
    assert [c["codigo"] for c in catalogo.buscar_codigos("ESCAVA")] == ["54393"]
    assert [c["codigo"] for c in catalogo.buscar_codigos("5439")] == ["54393", "54394"]
    # Em branco = sem filtro.
    assert len(catalogo.buscar_codigos("  ")) == len(catalogo.buscar_codigos())


async def test_buscar_codigos_trata_curinga_como_texto():
    contrato_id = contratos_repo.registrar_do_pdf(HEADER)
    medicoes_repo.gravar_itens(
        contrato_id,
        [_item("54393", "Reajuste 100% pago"), _item("54394", "Reajuste 100 pago")],
    )
    assert [c["codigo"] for c in catalogo.buscar_codigos("100%")] == ["54393"]
    assert catalogo.buscar_codigos("_") == []


async def test_buscar_codigos_usa_a_descricao_mais_recente():
    contrato_id = contratos_repo.registrar_do_pdf(HEADER)
    medicoes_repo.gravar_itens(contrato_id, [_item("54393", "DESCRICAO ANTIGA", mes=1)])
    medicoes_repo.gravar_itens(contrato_id, [_item("54393", "DESCRICAO NOVA", mes=2)])
    (codigo,) = catalogo.buscar_codigos("54393")
    assert codigo["descricao_pdf"] == "DESCRICAO NOVA"


async def test_buscar_codigos_filtra_associados():
    contrato_id = contratos_repo.registrar_do_pdf(HEADER)
    medicoes_repo.gravar_itens(contrato_id, [_item("54393", "Escavação")])
    livres = {c["codigo"] for c in catalogo.buscar_codigos(associado=False)}
    associados = {c["codigo"] for c in catalogo.buscar_codigos(associado=True)}
    assert livres == {"54393"}
    assert len(associados) == 9
```

- [ ] **Step 3: Rodar e ver falhar**

Run: `uv run pytest tests/test_catalogo.py -q`
Expected: FAIL (`AttributeError: module 'app.services.catalogo' has no attribute 'codigos_associados'` e outros).

- [ ] **Step 4: Criar a migração 006**

`migrations/006_catalogo_indices.sql`:

```sql
-- Catálogo sem pendências e índices com origem e sem sobreposição.
--
-- 1. Um código de serviço está associado a um produto ou não está no catálogo.
--    O estado "sugerido, aguardando confirmação" deixa de existir: as sugestões
--    automáticas não confirmadas são apagadas, e a linha existente passa a
--    significar "associado".
DELETE FROM produto_codigo WHERE NOT confirmado;
ALTER TABLE produto_codigo DROP COLUMN confirmado;

-- 2. Origem e data da última gravação de cada índice, para a importação
--    preservar o que o usuário corrigiu à mão. O que já está no banco veio do
--    seed; o padrão das próximas linhas é 'manual'.
ALTER TABLE anp_preco_semanal
    ADD COLUMN origem TEXT NOT NULL DEFAULT 'seed',
    ADD COLUMN atualizado_em TIMESTAMPTZ NOT NULL DEFAULT now();
ALTER TABLE anp_preco_semanal ALTER COLUMN origem SET DEFAULT 'manual';

ALTER TABLE indice_mensal
    ADD COLUMN origem TEXT NOT NULL DEFAULT 'seed',
    ADD COLUMN atualizado_em TIMESTAMPTZ NOT NULL DEFAULT now();
ALTER TABLE indice_mensal ALTER COLUMN origem SET DEFAULT 'manual';

-- 3. Semanas sobrepostas proibidas para o mesmo produto e região: o "dia 15"
--    de um mês nunca cai em duas semanas, então não há desempate a escolher.
--    Pontas inclusas ('[]'), como na regra de consulta.
CREATE EXTENSION IF NOT EXISTS btree_gist;

ALTER TABLE anp_preco_semanal
    ADD CONSTRAINT anp_vigencia_ordenada CHECK (vigencia_fim >= vigencia_inicio);

ALTER TABLE anp_preco_semanal
    ADD CONSTRAINT anp_sem_sobreposicao EXCLUDE USING gist (
        produto WITH =,
        regiao WITH =,
        daterange(vigencia_inicio, vigencia_fim, '[]') WITH &&
    );
```

- [ ] **Step 5: Reescrever `app/services/catalogo.py`**

```python
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


def _padrao_ilike(q: str | None) -> str | None:
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
    q: str | None = None, associado: bool | None = None, limite: int = 500
) -> list[dict]:
    """Códigos distintos extraídos ou associados, para localizar e associar.

    *q* filtra código **ou** descrição do PDF, sem diferenciar maiúsculas — uma
    caixa de texto livre. *associado* restringe a associados (True) ou livres
    (False).
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
            "ORDER BY c.codigo_servico LIMIT %(limite)s",
            {"padrao": _padrao_ilike(q), "associado": associado, "limite": limite},
        )
        return [dict(r) for r in cur.fetchall()]
```

Nota: `criar_produto` levanta `ErroCatalogo`, que é `ValueError` — o teste antigo `pytest.raises(ValueError)` continua valendo.

- [ ] **Step 6: Ajustar `app/services/medicoes_repo.py`**

Remova `from . import catalogo`. Substitua a docstring e o corpo de `gravar_itens` até o `return`, e o filtro de `itens_para_export`:

```python
def gravar_itens(contrato_id: int, rows: list[dict], job_id: str | None = None) -> int:
    """Store the item rows of one extracted file; returns how many were stored.

    Idempotent: the ``UNIQUE (contrato_id, codigo_servico, mes_medicao,
    source_file)`` key means reprocessing the same PDF updates its rows instead
    of duplicating them.

    Every item with a service code is stored, associated in the catalogue or
    not: associating a code later brings its past items into the calculation
    without reprocessing the PDFs.
    """
    registros = []

    for row in rows:
        codigo = str(row.get("Serviço") or "").strip()
        if not _CODIGO_RE.match(codigo):
            continue
        mes = mes_da_medicao(row.get("Período Líquido"))
        valor_pi = _decimal(row.get("Valor a PI Líquido"))
        fator = _decimal(row.get("Fator"))
        if mes is None or valor_pi is None or fator is None:
            continue

        registros.append(
            {
                "contrato_id": contrato_id,
                "codigo_servico": codigo,
                "descricao_pdf": str(row.get("Descrição") or "").strip(),
                "mes_medicao": mes,
                "valor_pi": valor_pi,
                "fator": fator,
                "source_file": str(row.get("Source_File") or ""),
                "job_id": job_id,
            }
        )
```

O bloco `if registros: ... executemany(...)` fica igual; troque o `return` por:

```python
    return len(registros)
```

Em `itens_para_export`, a docstring vira `"""Items that belong in the spreadsheet, ordered family → product → month.\n\n    Only codes associated with a product: the rest stays out of the calculation.\n    """` e a cláusula SQL `"WHERE m.contrato_id = %s AND pc.confirmado "` vira `"WHERE m.contrato_id = %s "`.

- [ ] **Step 7: Ajustar os chamadores**

`app/services/file_processor.py`, linhas 37–45, substitua por:

```python
        itens = medicoes_repo.gravar_itens(
            contrato_id, result.get("rows") or [], job_id=job_id
        )
        logger.info("'%s': %d item(ns) gravado(s) no banco.", filename, itens)
```

`app/services/progresso.py`: a linha 19, `from . import catalogo, contratos_repo`, vira `from . import contratos_repo`; e a linha 150, `pendencias = len(catalogo.listar_pendencias())`, vira:

```python
    # Códigos sem associação deixaram de ser pendência (subprojeto A); a
    # trilha inteira é revista no subprojeto B.
    pendencias = 0
```

`app/dashboard/callbacks.py` (o import de `catalogo` na linha 21 continua em uso):
- linhas 133–135, a chamada `views.tela_pendencias(catalogo.listar_pendencias(), catalogo.listar_produtos())`, vira
  `return views.tela_pendencias([], catalogo.listar_produtos())`;
- linha 210: `catalogo.registrar_codigo(codigo, produto_id, confirmado=True)` vira `catalogo.registrar_codigo(codigo, produto_id)`.

Confira que nada mais usa os nomes removidos:

Run: `grep -rn "registrar_pendencia\|listar_pendencias\|confirmar_codigo\|codigos_confirmados\|sugerir_familia\|confirmado" app/ scripts/`
Expected: nenhuma ocorrência (comentários em `views.py` sobre a tela de pendências podem ficar — o Dash está congelado).

- [ ] **Step 8: Ajustar os testes existentes**

`tests/test_contratos_repo.py`:
- a linha 8, `from app.services import catalogo, contratos_repo, medicoes_repo`, vira `from app.services import contratos_repo, medicoes_repo` — o único uso de `catalogo` está no teste apagado abaixo;
- em `test_gravar_itens_e_idempotente`: `assert primeiro == 2` e `assert segundo == 2` (e renomeie as variáveis se preferir);
- em `test_linhas_sem_codigo_de_servico_sao_ignoradas`: `assert resumo == 1`;
- em `test_item_sem_mes_e_descartado`: `assert resumo == 0`;
- apague `test_codigo_nao_confirmado_fica_fora_do_export` (coberto por `test_associacao_e_retroativa_e_desassociar_remove_do_calculo`);
- substitua `test_servico_alheio_nao_gera_pendencia` por:

```python
async def test_servico_sem_associacao_e_gravado_mas_fica_fora_do_calculo():
    contrato_id = contratos_repo.registrar_do_pdf(HEADER)
    gravados = medicoes_repo.gravar_itens(
        contrato_id, [_linha("54393", "ESCAVAÇÃO, CARGA E TRANSPORTE", 500.0, 1.0)]
    )
    assert gravados == 1
    assert medicoes_repo.itens_para_export(contrato_id) == []
```

`tests/test_reequilibrio_export.py`, a função da linha 325 vira:

```python
async def test_exportar_sem_codigos_associados(template):
    contratos_repo.registrar_do_pdf(HEADER)
    with pytest.raises(ExportacaoImpossivel) as erro:
        reequilibrio_export.exportar("15 00716/2022", template)
    assert "associado" in str(erro.value)
```

e, em `app/services/reequilibrio_export.py`, a mensagem de `exportar` para itens vazios vira:

```python
        raise ExportacaoImpossivel(
            "Nenhum código de serviço deste contrato está associado a um produto. "
            "Associe os códigos no catálogo ou processe as medições."
        )
```

`tests/test_dashboard.py`, acima de `test_tela_de_pendencias_oferece_os_produtos_existentes` (linha 159):

```python
@pytest.mark.skip(reason="Dash congelado até o subprojeto B")
```

(importe `pytest` no topo se ainda não estiver importado).

- [ ] **Step 9: Rodar a suíte inteira**

Run: `uv run pytest -q`
Expected: tudo PASS (skips do Dash e de backup permitidos). Se algum teste do Dash quebrar por causa do catálogo, marque-o com o mesmo `skip` — não altere o Dash além do Step 7.

- [ ] **Step 10: Commit**

```bash
git add migrations/006_catalogo_indices.sql app/services/catalogo.py app/services/medicoes_repo.py \
  app/services/file_processor.py app/services/progresso.py app/services/reequilibrio_export.py \
  app/dashboard/callbacks.py tests/test_catalogo.py tests/test_contratos_repo.py \
  tests/test_reequilibrio_export.py tests/test_dashboard.py
git commit -m "$(cat <<'EOF'
feat: catálogo sem pendências e migração 006

Código de serviço passa a estar associado a um produto ou fora do catálogo;
a associação é retroativa. A migração também prepara os índices (origem,
atualizado_em) e proíbe semanas ANP sobrepostas com btree_gist.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 2: Índices com origem, edição manual e sobreposição proibida

**Files:**
- Modify: `app/services/delta_p.py` (constante nova)
- Rewrite: `app/services/indices_repo.py`
- Create: `tests/indices_factory.py`
- Modify: `tests/test_indices_repo.py` (testes novos no fim)

**Interfaces:**
- Consumes: migração 006 (Task 1).
- Produces:
  - `delta_p.BASE_IGP_DI = "ago/1994 = 100"`
  - `indices_repo.ORIGEM_MANUAL = "manual"`, `ORIGEM_SEED = "seed"`, `origem_upload(arquivo: str) -> str` (`"upload:<arquivo>"`)
  - `indices_repo.IndiceInvalido(ValueError)`, `indices_repo.SemanaSobreposta(IndiceInvalido)`
  - `gravar_precos_anp(registros: list[dict], origem: str = ORIGEM_MANUAL) -> int` — só regrava o que mudou
  - `gravar_indices_mensais(registros: list[dict], origem: str = ORIGEM_MANUAL) -> int` — idem
  - `regioes_disponiveis(produto=ANP_PRODUTO_CAP) -> list[str]`
  - `normalizar_regiao(regiao: str | None, produto=ANP_PRODUTO_CAP) -> str | None`
  - `buscar_semana(produto, regiao, vigencia_inicio) -> dict | None`
  - `gravar_semana_manual(registro: dict) -> dict` (chaves `produto` opcional, `vigencia_inicio`, `vigencia_fim`, `regiao`, `preco`)
  - `buscar_indice(mes: date, indice=INDICE_IGP_DI) -> dict | None`
  - `gravar_indice_manual(mes: date, valor) -> dict`
  - `excluir_preco_anp(preco_id: int) -> bool`, `excluir_indice_mensal(mes: date, indice=INDICE_IGP_DI) -> bool`
  - `precos_anp_por_chave(produtos: set[str]) -> dict[tuple[str, date, str], dict]` — chave `(produto, vigencia_inicio, regiao)`
  - `indices_por_mes(indice=INDICE_IGP_DI) -> dict[date, dict]`
  - `listar_precos_anp(produto=ANP_PRODUTO_CAP, regiao=None, limite: int | None = 500, *, de=None, ate=None)`
  - `listar_indices_mensais(indice=INDICE_IGP_DI, limite: int | None = 500, *, de=None, ate=None)`
  - Linha de preço: `id, produto, regiao, vigencia_inicio, vigencia_fim, preco, origem, atualizado_em`. Linha de índice: `id, indice, base_label, mes_ref, valor, origem, atualizado_em`.
  - `tests/indices_factory.py`: `semana(...)`, `mes_igp(...)`, `serial(...)`, `linha_anp(...)`, `linhas_anp(...)`

- [ ] **Step 1: Criar `tests/indices_factory.py`**

```python
"""Construtores de índices para os testes: registros e planilhas ANP mínimas."""

from datetime import date, timedelta
from decimal import Decimal

from app.services.delta_p import ANP_PRODUTO_CAP, BASE_IGP_DI, INDICE_IGP_DI

EPOCA_EXCEL = date(1899, 12, 30)


def semana(inicio: date, preco, *, regiao="Nordeste", produto=ANP_PRODUTO_CAP, dias=6) -> dict:
    return {
        "produto": produto,
        "vigencia_inicio": inicio,
        "vigencia_fim": inicio + timedelta(days=dias),
        "regiao": regiao,
        "preco": None if preco is None else Decimal(str(preco)),
    }


def mes_igp(mes: date, valor) -> dict:
    return {
        "indice": INDICE_IGP_DI,
        "mes_ref": mes,
        "valor": Decimal(str(valor)),
        "base_label": BASE_IGP_DI,
    }


def serial(d: date) -> float:
    """Data como o xlrd a devolve: número serial do Excel."""
    return float((d - EPOCA_EXCEL).days)


def linha_anp(produto: str, inicio: date, precos: list, dias: int = 6) -> list:
    """Uma linha de dados da aba ANP: produto, início, fim e seis preços."""
    return [produto, serial(inicio), serial(inicio + timedelta(days=dias)), *precos]


def linhas_anp(dados: list[list]) -> list[list]:
    """A aba ANP como lista de linhas, com o cabeçalho e o rodapé do arquivo oficial."""
    cabecalho = [
        ["Produto", "Período", "", "Região", "", "", "", "", "Brasil", ""],
        ["", "(A partir de 2013)", "", "Norte", "Nordeste", "Centro-Oeste", "Sul", "Sudeste", "", ""],
    ]
    return (
        [[""] * 10 for _ in range(7)]
        + cabecalho
        + [list(linha) for linha in dados]
        + [["Notas: não inclui ICMS.", ""]]
    )
```

- [ ] **Step 2: Escrever os testes novos**

Acrescente ao fim de `tests/test_indices_repo.py` (e `from .indices_factory import mes_igp, semana` junto dos imports do topo):

```python
async def test_gravacao_registra_origem_e_so_regrava_o_que_mudou():
    indices_repo.gravar_precos_anp([semana(date(2023, 1, 9), "3.28568")], origem="upload:a.xls")
    (antes,) = indices_repo.listar_precos_anp(regiao="Nordeste")
    assert antes["origem"] == "upload:a.xls"

    indices_repo.gravar_precos_anp([semana(date(2023, 1, 9), "3.285680")], origem="upload:b.xls")
    (igual,) = indices_repo.listar_precos_anp(regiao="Nordeste")
    assert igual["origem"] == "upload:a.xls"
    assert igual["atualizado_em"] == antes["atualizado_em"]

    indices_repo.gravar_precos_anp([semana(date(2023, 1, 9), "3.3")], origem="upload:b.xls")
    (mudou,) = indices_repo.listar_precos_anp(regiao="Nordeste")
    assert mudou["origem"] == "upload:b.xls"
    assert mudou["preco"] == Decimal("3.3")


async def test_origem_padrao_e_manual():
    indices_repo.gravar_precos_anp([semana(date(2023, 1, 9), "3.28568")])
    indices_repo.gravar_indices_mensais([mes_igp(date(2023, 1, 1), "1143.861")])
    assert indices_repo.listar_precos_anp()[0]["origem"] == indices_repo.ORIGEM_MANUAL
    assert indices_repo.listar_indices_mensais()[0]["origem"] == indices_repo.ORIGEM_MANUAL


async def test_indice_mensal_so_regrava_o_que_mudou():
    indices_repo.gravar_indices_mensais([mes_igp(date(2023, 1, 1), "1143.861")], origem="seed")
    indices_repo.gravar_indices_mensais([mes_igp(date(2023, 1, 1), "1143.8610")], origem="upload:x")
    assert indices_repo.buscar_indice(date(2023, 1, 1))["origem"] == "seed"


async def test_banco_proibe_semanas_sobrepostas():
    indices_repo.gravar_precos_anp([semana(date(2023, 1, 9), "3.28")])
    with pytest.raises(indices_repo.SemanaSobreposta):
        indices_repo.gravar_precos_anp([semana(date(2023, 1, 15), "3.30")])
    # Outra região não conflita.
    indices_repo.gravar_precos_anp([semana(date(2023, 1, 15), "3.30", regiao="Sul")])


async def test_vigencia_invertida_e_recusada_pelo_banco():
    with pytest.raises(indices_repo.IndiceInvalido):
        indices_repo.gravar_precos_anp([semana(date(2023, 1, 9), "3.28", dias=-1)])


async def test_semana_manual_normaliza_regiao_e_marca_manual():
    salvo = indices_repo.gravar_semana_manual(
        {
            "vigencia_inicio": date(2023, 1, 9),
            "vigencia_fim": date(2023, 1, 15),
            "regiao": "NORDESTE",
            "preco": Decimal("3.28568"),
        }
    )
    assert salvo["regiao"] == "Nordeste"
    assert salvo["produto"] == ANP_PRODUTO_CAP
    assert salvo["origem"] == indices_repo.ORIGEM_MANUAL
    assert salvo["preco"] == Decimal("3.28568")


async def test_semana_manual_corrige_a_mesma_semana():
    indices_repo.gravar_precos_anp([semana(date(2023, 1, 9), "3.28")], origem="seed")
    salvo = indices_repo.gravar_semana_manual(
        {"vigencia_inicio": date(2023, 1, 9), "vigencia_fim": date(2023, 1, 15),
         "regiao": "Nordeste", "preco": "3.5"}
    )
    assert salvo["preco"] == Decimal("3.5")
    assert salvo["origem"] == indices_repo.ORIGEM_MANUAL


async def test_semana_manual_sobreposta_indica_a_semana_em_conflito():
    indices_repo.gravar_precos_anp([semana(date(2023, 1, 9), "3.28")])
    with pytest.raises(indices_repo.SemanaSobreposta) as erro:
        indices_repo.gravar_semana_manual(
            {"vigencia_inicio": date(2023, 1, 12), "vigencia_fim": date(2023, 1, 18),
             "regiao": "Nordeste", "preco": "3.3"}
        )
    assert "09/01/2023" in str(erro.value)
    assert "15/01/2023" in str(erro.value)


@pytest.mark.parametrize(
    "alteracao",
    [
        {"vigencia_fim": date(2023, 1, 8)},
        {"preco": "-1"},
        {"regiao": "Marte"},
    ],
)
async def test_semana_manual_invalida(alteracao):
    registro = {"vigencia_inicio": date(2023, 1, 9), "vigencia_fim": date(2023, 1, 15),
                "regiao": "Nordeste", "preco": "3.28"}
    with pytest.raises(indices_repo.IndiceInvalido):
        indices_repo.gravar_semana_manual({**registro, **alteracao})


async def test_semana_sem_cotacao_pode_ser_gravada():
    salvo = indices_repo.gravar_semana_manual(
        {"vigencia_inicio": date(2023, 1, 9), "vigencia_fim": date(2023, 1, 15),
         "regiao": "Centro-Oeste", "preco": None}
    )
    assert salvo["preco"] is None


async def test_indice_manual():
    salvo = indices_repo.gravar_indice_manual(date(2023, 1, 1), Decimal("1143.861"))
    assert salvo["origem"] == indices_repo.ORIGEM_MANUAL
    assert salvo["base_label"] == "ago/1994 = 100"
    assert salvo["mes_ref"] == date(2023, 1, 1)
    with pytest.raises(indices_repo.IndiceInvalido):
        indices_repo.gravar_indice_manual(date(2023, 2, 1), 0)


async def test_excluir_semana_e_mes():
    indices_repo.gravar_precos_anp([semana(date(2023, 1, 9), "3.28")])
    (linha,) = indices_repo.listar_precos_anp()
    assert indices_repo.excluir_preco_anp(linha["id"]) is True
    assert indices_repo.excluir_preco_anp(linha["id"]) is False

    indices_repo.gravar_indice_manual(date(2023, 1, 1), 1)
    assert indices_repo.excluir_indice_mensal(date(2023, 1, 1)) is True
    assert indices_repo.excluir_indice_mensal(date(2023, 1, 1)) is False


async def test_listar_precos_filtra_periodo_e_regiao_sem_diferenciar_maiusculas():
    _semear_anp()
    linhas = indices_repo.listar_precos_anp(
        regiao="nordeste", de=date(2022, 12, 1), ate=date(2023, 1, 31)
    )
    assert [l["vigencia_inicio"] for l in linhas] == [date(2023, 1, 9), date(2022, 12, 12)]
    assert len(indices_repo.listar_precos_anp(limite=None)) == len(SEMANAS)


async def test_listar_indices_filtra_periodo():
    _semear_igp()
    meses = indices_repo.listar_indices_mensais(de=date(2023, 1, 1), ate=date(2023, 12, 1))
    assert [m["mes_ref"] for m in meses] == [date(2023, 2, 1), date(2023, 1, 1)]


async def test_regioes_disponiveis_e_normalizacao():
    _semear_anp("Nordeste")
    assert indices_repo.regioes_disponiveis() == ["Nordeste"]
    assert indices_repo.normalizar_regiao("  NORDESTE ") == "Nordeste"
    assert indices_repo.normalizar_regiao("Sul") is None
    assert indices_repo.normalizar_regiao("") is None


async def test_mapas_por_chave():
    _semear_anp()
    _semear_igp()
    precos = indices_repo.precos_anp_por_chave({ANP_PRODUTO_CAP})
    chave = (ANP_PRODUTO_CAP, date(2021, 12, 13), "Nordeste")
    assert precos[chave]["preco"] == Decimal("4.02073")
    assert precos[chave]["origem"] == indices_repo.ORIGEM_MANUAL
    assert indices_repo.indices_por_mes()[date(2022, 1, 1)]["valor"] == Decimal("1110.398")
```

- [ ] **Step 3: Rodar e ver falhar**

Run: `uv run pytest tests/test_indices_repo.py -q`
Expected: FAIL — `ImportError: cannot import name 'BASE_IGP_DI'` (coleta do módulo).

- [ ] **Step 4: Constante em `app/services/delta_p.py`**

Logo abaixo de `INDICE_IGP_DI = "IGP - DI"`:

```python
# Base do número-índice publicado pela FGV; gravada em indice_mensal.base_label.
BASE_IGP_DI = "ago/1994 = 100"
```

- [ ] **Step 5: Reescrever `app/services/indices_repo.py`**

Mantém `REGIOES`, `_dia_de_referencia`, `FonteBanco`, `buscar_preco_anp`, `buscar_indice_mensal` e `cobertura` exatamente como estão; o arquivo completo fica:

```python
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


def gravar_precos_anp(registros: list[dict], origem: str = ORIGEM_MANUAL) -> int:
    """Insert or update weekly ANP prices, rewriting only what changed.

    Each record needs ``produto``, ``vigencia_inicio``, ``vigencia_fim``,
    ``regiao`` and ``preco`` (``None`` where the source publishes ``***``).
    """
    if not registros:
        return 0
    linhas = [{**r, "origem": origem} for r in registros]
    _executar_anp(_UPSERT_ANP + _SO_SE_MUDOU_ANP, linhas)
    return len(linhas)


def gravar_indices_mensais(registros: list[dict], origem: str = ORIGEM_MANUAL) -> int:
    """Insert or update monthly indices, rewriting only what changed.

    Each record needs ``indice``, ``mes_ref``, ``valor`` and optionally
    ``base_label``.
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
    _executar_indices(_UPSERT_INDICE + _SO_SE_MUDOU_INDICE, linhas)
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
        if preco < 0:
            raise IndiceInvalido("O preço não pode ser negativo.")
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
```

- [ ] **Step 6: Rodar os testes de índices e a suíte**

Run: `uv run pytest tests/test_indices_repo.py -q && uv run pytest -q`
Expected: PASS. Se um teste antigo gravar semanas sobrepostas de propósito, ele agora falha com `SemanaSobreposta` — corrija o dado do teste (a regra mudou), não a regra.

- [ ] **Step 7: Commit**

```bash
git add app/services/delta_p.py app/services/indices_repo.py tests/indices_factory.py tests/test_indices_repo.py
git commit -m "$(cat <<'EOF'
feat: índices com origem, edição manual e sobreposição proibida

Cada preço e índice registra origem e data da última gravação; importações
só regravam o que mudou. Semanas digitadas à mão são validadas e a
sobreposição é recusada indicando a semana em conflito.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 3: Importadores (ANP e IGP-DI) e o fluxo prévia → gravação

**Files:**
- Create: `app/services/importadores.py` (puro, sem banco)
- Create: `app/services/importacao.py` (compara com o banco e grava)
- Create: `tests/fixtures/anp_semanal.xls` (cópia do arquivo oficial)
- Create: `tests/test_importadores.py`, `tests/test_importacao.py`
- Modify: `pyproject.toml`, `requirements.txt` (`xlrd` em runtime)

**Interfaces:**
- Consumes (Task 2): `indices_repo.precos_anp_por_chave`, `indices_por_mes`, `gravar_precos_anp`, `gravar_indices_mensais`, `ORIGEM_MANUAL`, `origem_upload`; `delta_p.BASE_IGP_DI`; `tests/indices_factory.linha_anp/linhas_anp/mes_igp`.
- Produces:
  - `importadores.ArquivoInvalido(mensagem: str, erros: list[str] | None = None)` — `ValueError` com `.mensagem` e `.erros`
  - `importadores.Leitura(registros: list[dict], avisos: list[str])`
  - `importadores.ler_anp(conteudo: bytes) -> Leitura`, `ler_linhas_anp(linhas: list[list]) -> Leitura`
  - `importadores.ler_igp_di(conteudo: bytes) -> Leitura`, `ler_linhas_igp_di(linhas: list[list]) -> Leitura`
  - `importadores.gerar_template_igp_di(registros: list[dict]) -> bytes` (registros com `mes_ref`, `valor`)
  - `importadores.sobreposicoes(novos: list[dict], existentes: dict) -> list[str]`
  - `importadores.limitar(erros: list[str]) -> list[str]`, `MAX_ERROS = 50`
  - `importacao.importar_anp(conteudo, arquivo, *, simular=False, sobrescrever_manuais=False, origem=None) -> dict`
  - `importacao.importar_igp_di(conteudo, arquivo, *, simular=False, sobrescrever_manuais=False, origem=None) -> dict`
  - Resposta: `arquivo, simulacao, periodo{de, ate}, inseridos, atualizados[{chave, antes, depois}], inalterados, conflitos_manuais[{chave, valor_banco, valor_arquivo, atualizado_em}], manuais_preservados, avisos`. `chave` é um dict de strings: ANP `{produto, regiao, vigencia_inicio, vigencia_fim}` (datas ISO), IGP-DI `{mes: "AAAA-MM"}`.

**Regra do GLP (decidida no plano, vetável pelo usuário):** no arquivo oficial, só
o GLP tem semanas repetidas (374 inícios duplicados — são séries distintas
publicadas sob o mesmo nome). Um produto com semana repetida é **pulado inteiro**,
com aviso, em vez de recusar o arquivo: recusar impediria importar o CAP, que é o
que o cálculo usa. Resultado no arquivo oficial: 20 produtos, 60.114 registros.

- [ ] **Step 1: Versionar a fixture e tornar `xlrd` dependência de runtime**

```bash
mkdir -p tests/fixtures
cp data/precos-medios-ponderados-semanais-2013.xls tests/fixtures/anp_semanal.xls
```

Em `pyproject.toml`, remova `"xlrd>=2.0.2",` do grupo `dev` e acrescente-o à lista
`dependencies` (ordem alfabética não é exigida; ponha-o no fim). Em
`requirements.txt`, acrescente a linha `xlrd>=2.0.2`. Depois:

Run: `uv sync && uv run python -c "import xlrd; print(xlrd.__version__)"`
Expected: `2.0.2` (ou superior).

- [ ] **Step 2: Escrever `tests/test_importadores.py`**

```python
"""Leitura dos arquivos de índices: layout, validação por linha, tudo ou nada."""

import io
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

import openpyxl
import pytest

from app.services import importadores
from app.services.delta_p import ANP_PRODUTO_CAP, BASE_IGP_DI, INDICE_IGP_DI
from app.services.importadores import ArquivoInvalido

from .indices_factory import linha_anp, linhas_anp, mes_igp, semana

OFICIAL = Path("tests/fixtures/anp_semanal.xls")
CAP = ANP_PRODUTO_CAP
PRECOS = [3.1, 4.02073, "***", 3.45, 3.3, 3.9]


# --- ANP ---------------------------------------------------------------------

def test_linha_vira_seis_registros_com_sem_cotacao_nulo():
    leitura = importadores.ler_linhas_anp(linhas_anp([linha_anp(CAP, date(2021, 12, 13), PRECOS)]))
    assert len(leitura.registros) == 6
    por_regiao = {r["regiao"]: r for r in leitura.registros}
    assert por_regiao["Nordeste"]["preco"] == Decimal("4.02073")
    assert por_regiao["Centro-Oeste"]["preco"] is None
    assert por_regiao["Brasil"]["preco"] == Decimal("3.90000")
    assert por_regiao["Nordeste"]["vigencia_inicio"] == date(2021, 12, 13)
    assert por_regiao["Nordeste"]["vigencia_fim"] == date(2021, 12, 19)
    assert leitura.avisos == []


def test_preco_e_quantizado_em_cinco_casas():
    precos = [1.2935999999999999] * 6
    leitura = importadores.ler_linhas_anp(linhas_anp([linha_anp(CAP, date(2013, 1, 1), precos)]))
    assert {r["preco"] for r in leitura.registros} == {Decimal("1.29360")}


def test_rodape_encerra_a_leitura():
    linhas = linhas_anp([linha_anp(CAP, date(2023, 1, 9), PRECOS)])
    linhas.append([CAP, "texto", "", 1, 1, 1, 1, 1, 1])  # depois do rodapé: ignorada
    assert len(importadores.ler_linhas_anp(linhas).registros) == 6


@pytest.mark.parametrize(
    "linha,trecho",
    [
        (linha_anp(CAP, date(2023, 1, 9), ["abc", 1, 1, 1, 1, 1]), "linha 10, Norte"),
        (linha_anp(CAP, date(2023, 1, 9), [1, -2, 1, 1, 1, 1]), "linha 10, Nordeste"),
        (linha_anp(CAP, date(2023, 1, 9), PRECOS, dias=-3), "linha 10: a semana termina"),
    ],
)
def test_linha_invalida_recusa_o_arquivo_inteiro(linha, trecho):
    boa = linha_anp(CAP, date(2023, 1, 16), PRECOS)
    with pytest.raises(ArquivoInvalido) as erro:
        importadores.ler_linhas_anp(linhas_anp([linha, boa]))
    assert "nada foi gravado" in erro.value.mensagem
    assert any(trecho in e for e in erro.value.erros)


def test_layout_errado_e_recusado():
    linhas = linhas_anp([linha_anp(CAP, date(2023, 1, 9), PRECOS)])
    linhas[8][4] = "Nordestee"
    with pytest.raises(ArquivoInvalido) as erro:
        importadores.ler_linhas_anp(linhas)
    assert "não é o arquivo de preços semanais da ANP" in erro.value.mensagem


def test_bytes_que_nao_sao_xls_sao_recusados():
    with pytest.raises(ArquivoInvalido) as erro:
        importadores.ler_anp(b"isto nao e uma planilha")
    assert "não é o arquivo de preços semanais da ANP" in erro.value.mensagem


def test_arquivo_sem_semanas_e_recusado():
    with pytest.raises(ArquivoInvalido):
        importadores.ler_linhas_anp(linhas_anp([]))


def test_produto_com_semana_repetida_e_pulado_com_aviso():
    glp = "Gás Liquefeito de Petróleo - GLP (R$/kg)"
    linhas = linhas_anp(
        [
            linha_anp(glp, date(2023, 1, 9), PRECOS),
            linha_anp(glp, date(2023, 1, 9), PRECOS),
            linha_anp(CAP, date(2023, 1, 9), PRECOS),
        ]
    )
    leitura = importadores.ler_linhas_anp(linhas)
    assert {r["produto"] for r in leitura.registros} == {CAP}
    (aviso,) = leitura.avisos
    assert glp in aviso and "não foi importado" in aviso


def test_limitar_resume_o_excesso():
    erros = [f"linha {i}" for i in range(80)]
    limitados = importadores.limitar(erros)
    assert len(limitados) == importadores.MAX_ERROS + 1
    assert limitados[-1] == "… e mais 30 erro(s)."


def test_arquivo_oficial():
    leitura = importadores.ler_anp(OFICIAL.read_bytes())
    assert len(leitura.registros) == 60114
    assert len({r["produto"] for r in leitura.registros}) == 20
    assert len(leitura.avisos) == 1 and "GLP" in leitura.avisos[0]
    chave = {(r["produto"], r["regiao"], r["vigencia_inicio"]): r["preco"] for r in leitura.registros}
    assert chave[(CAP, "Nordeste", date(2021, 12, 13))] == Decimal("4.02073")
    assert chave[(CAP, "Sul", date(2022, 12, 12))] == Decimal("3.45000")
    assert chave[(CAP, "Centro-Oeste", date(2021, 12, 13))] is None


# --- sobreposições -------------------------------------------------------------

def test_sobreposicao_dentro_do_arquivo():
    novos = [semana(date(2023, 1, 9), 1), semana(date(2023, 1, 12), 1)]
    (erro,) = importadores.sobreposicoes(novos, {})
    assert "do próprio arquivo" in erro and "12/01/2023" in erro


def test_sobreposicao_com_semana_cadastrada():
    existente = semana(date(2023, 1, 9), 1)
    existentes = {(CAP, existente["vigencia_inicio"], "Nordeste"): existente}
    (erro,) = importadores.sobreposicoes([semana(date(2023, 1, 12), 1)], existentes)
    assert "já cadastrada" in erro and "09/01/2023" in erro


def test_mesma_semana_do_arquivo_substitui_a_cadastrada():
    existente = semana(date(2023, 1, 9), 1, dias=10)
    existentes = {(CAP, existente["vigencia_inicio"], "Nordeste"): existente}
    novos = [semana(date(2023, 1, 9), 1), semana(date(2023, 1, 16), 1)]
    assert importadores.sobreposicoes(novos, existentes) == []


def test_sobreposicao_entre_cadastradas_nao_e_do_arquivo():
    """Só se reporta o que envolve o arquivo; o banco já proíbe o resto."""
    a, b = semana(date(2023, 1, 9), 1), semana(date(2023, 1, 12), 1)
    existentes = {(CAP, s["vigencia_inicio"], "Nordeste"): s for s in (a, b)}
    assert importadores.sobreposicoes([semana(date(2023, 2, 6), 1)], existentes) == []


# --- IGP-DI ----------------------------------------------------------------------

def _planilha(linhas, aba=importadores.ABA_IGP) -> bytes:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = aba
    for linha in linhas:
        ws.append(linha)
    saida = io.BytesIO()
    wb.save(saida)
    return saida.getvalue()


def test_template_gerado_e_reimportavel():
    registros = [mes_igp(date(2023, 1, 1), "1143.861"), mes_igp(date(2022, 1, 1), "1110.398")]
    conteudo = importadores.gerar_template_igp_di(registros)
    leitura = importadores.ler_igp_di(conteudo)
    assert [(r["mes_ref"], r["valor"]) for r in leitura.registros] == [
        (date(2022, 1, 1), Decimal("1110.398")),
        (date(2023, 1, 1), Decimal("1143.861")),
    ]
    assert all(r["indice"] == INDICE_IGP_DI and r["base_label"] == BASE_IGP_DI for r in leitura.registros)
    wb = openpyxl.load_workbook(io.BytesIO(conteudo))
    assert wb.sheetnames == [importadores.ABA_IGP, importadores.ABA_INSTRUCOES]
    assert wb[importadores.ABA_IGP]["A2"].number_format == "mmm/yyyy"


def test_template_vazio_tem_so_o_cabecalho():
    wb = openpyxl.load_workbook(io.BytesIO(importadores.gerar_template_igp_di([])))
    assert [c.value for c in wb[importadores.ABA_IGP][1]] == ["Mês", "Valor"]
    assert wb[importadores.ABA_IGP].max_row == 1


def test_igp_aceita_mes_como_texto_e_ignora_linhas_em_branco():
    conteudo = _planilha([["Mês", "Valor"], ["03/2023", 1150.5], [None, None], [datetime(2023, 4, 1), 1151]])
    leitura = importadores.ler_igp_di(conteudo)
    assert [r["mes_ref"] for r in leitura.registros] == [date(2023, 3, 1), date(2023, 4, 1)]
    assert leitura.registros[1]["valor"] == Decimal("1151")


@pytest.mark.parametrize(
    "linhas,trecho",
    [
        ([["Mês", "Valor"], ["13/2023", 1]], "linha 2: mês"),
        ([["Mês", "Valor"], ["01/2023", 0]], "linha 2: valor"),
        ([["Mês", "Valor"], ["01/2023", "mil"]], "linha 2: valor"),
        ([["Mês", "Valor"], ["01/2023", 1], ["01/2023", 2]], "linha 3: o mês 01/2023 já aparece na linha 2"),
    ],
)
def test_igp_linha_invalida_recusa_o_arquivo(linhas, trecho):
    with pytest.raises(ArquivoInvalido) as erro:
        importadores.ler_igp_di(_planilha(linhas))
    assert any(trecho in e for e in erro.value.erros)


def test_igp_cabecalho_ou_aba_errados():
    with pytest.raises(ArquivoInvalido):
        importadores.ler_igp_di(_planilha([["Data", "Índice"], ["01/2023", 1]]))
    with pytest.raises(ArquivoInvalido):
        importadores.ler_igp_di(_planilha([["Mês", "Valor"]], aba="Plan1"))
    with pytest.raises(ArquivoInvalido):
        importadores.ler_igp_di(b"nao e xlsx")
    with pytest.raises(ArquivoInvalido):
        importadores.ler_igp_di(_planilha([["Mês", "Valor"]]))
```

- [ ] **Step 3: Rodar e ver falhar**

Run: `uv run pytest tests/test_importadores.py -q`
Expected: FAIL — `ImportError: cannot import name 'importadores'`.

- [ ] **Step 4: Criar `app/services/importadores.py`**

```python
"""Leitura dos arquivos de índices: o .xls semanal da ANP e o template do IGP-DI.

Módulo puro: recebe bytes, devolve registros validados ou ``ArquivoInvalido``
com a lista de erros por linha. Não toca o banco — a comparação e a gravação são
de ``importacao``. Seed, API e testes passam por aqui, então o arquivo aceito
pelo seed é exatamente o aceito pela tela.
"""

import io
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal

import openpyxl
import xlrd
from openpyxl.styles import Font

from .delta_p import BASE_IGP_DI, INDICE_IGP_DI, inicio_do_mes

# Layout do arquivo "precos-medios-ponderados-semanais-2013.xls" da ANP. Linhas
# em base 0, como o xlrd as devolve; as mensagens usam a numeração do Excel.
ABA_ANP = "Preços Produtor e Importador"
LINHA_CABECALHO_ANP = 7
LINHA_REGIOES_ANP = 8
PRIMEIRA_LINHA_ANP = 9
REGIOES_ANP = ("Norte", "Nordeste", "Centro-Oeste", "Sul", "Sudeste", "Brasil")
COL_PRIMEIRA_REGIAO = 3
EPOCA_EXCEL = date(1899, 12, 30)
CASAS_ANP = Decimal("0.00001")
SEM_COTACAO = "***"
LAYOUT_ANP_ERRADO = "Este não é o arquivo de preços semanais da ANP: {motivo}."

ABA_IGP = "IGP-DI"
ABA_INSTRUCOES = "Instruções"
CABECALHO_IGP = ("Mês", "Valor")
INSTRUCOES_IGP = (
    "Template de importação do IGP-DI (FGV).",
    "",
    f"Aba '{ABA_IGP}': uma linha por mês, a partir da linha 2.",
    "Coluna A (Mês): data (qualquer dia do mês) ou texto MM/AAAA.",
    "Coluna B (Valor): o número-índice publicado pela FGV, maior que zero.",
    f"Base do índice: {BASE_IGP_DI}.",
    "Linhas em branco são ignoradas; um mês repetido recusa o arquivo.",
    "Qualquer linha inválida recusa o arquivo inteiro: nada é gravado.",
)

MAX_ERROS = 50
_MES_TEXTO = re.compile(r"^\s*(\d{1,2})/(\d{4})\s*$")


class ArquivoInvalido(ValueError):
    """Arquivo recusado; ``erros`` lista os problemas linha a linha."""

    def __init__(self, mensagem: str, erros: list[str] | None = None) -> None:
        super().__init__(mensagem)
        self.mensagem = mensagem
        self.erros = list(erros or [])


@dataclass
class Leitura:
    registros: list[dict]
    avisos: list[str] = field(default_factory=list)


def limitar(erros: list[str]) -> list[str]:
    """No máximo ``MAX_ERROS`` linhas de erro, e quantas ficaram de fora."""
    if len(erros) <= MAX_ERROS:
        return erros
    return erros[:MAX_ERROS] + [f"… e mais {len(erros) - MAX_ERROS} erro(s)."]


def _recusar(erros: list[str]) -> ArquivoInvalido:
    return ArquivoInvalido(
        f"O arquivo tem {len(erros)} erro(s); nada foi gravado.", limitar(erros)
    )


def _semana(inicio: date, fim: date) -> str:
    return f"{inicio:%d/%m/%Y}–{fim:%d/%m/%Y}"


# --- ANP -----------------------------------------------------------------------

def _layout(motivo: str) -> ArquivoInvalido:
    return ArquivoInvalido(LAYOUT_ANP_ERRADO.format(motivo=motivo))


def _textos(linha, tamanho: int = 10) -> list[str]:
    return [str(c).strip() for c in list(linha) + [""] * tamanho][:tamanho]


def _conferir_layout_anp(linhas: list[list]) -> None:
    if len(linhas) <= PRIMEIRA_LINHA_ANP:
        raise _layout("o arquivo tem menos linhas que o cabeçalho da ANP")
    cab = _textos(linhas[LINHA_CABECALHO_ANP])
    if (cab[0], cab[1], cab[3], cab[8]) != ("Produto", "Período", "Região", "Brasil"):
        raise _layout("a linha 8 não traz as colunas Produto, Período, Região e Brasil")
    regioes = _textos(linhas[LINHA_REGIOES_ANP])
    if tuple(regioes[COL_PRIMEIRA_REGIAO:COL_PRIMEIRA_REGIAO + 5]) != REGIOES_ANP[:5]:
        raise _layout("a linha 9 não lista Norte, Nordeste, Centro-Oeste, Sul e Sudeste")


def _serial(valor) -> bool:
    return isinstance(valor, (int, float)) and not isinstance(valor, bool) and valor > 0


def _data(serial: float) -> date:
    return EPOCA_EXCEL + timedelta(days=int(serial))


def _preco(valor) -> Decimal | None:
    if isinstance(valor, str):
        texto = valor.strip()
        if texto in ("", SEM_COTACAO):
            return None
        raise ValueError(f"preço {texto!r} não é um número")
    preco = Decimal(str(valor))
    if preco < 0:
        raise ValueError(f"preço negativo ({preco})")
    return preco.quantize(CASAS_ANP)


def ler_linhas_anp(linhas: list[list]) -> Leitura:
    """Registros semanais de uma aba ANP já lida como lista de linhas.

    Separado de ``ler_anp`` para que os testes montem abas mínimas sem precisar
    escrever um .xls (o xlwt não é dependência).
    """
    _conferir_layout_anp(linhas)
    registros: list[dict] = []
    erros: list[str] = []
    inicios: dict[str, Counter] = defaultdict(Counter)

    for i in range(PRIMEIRA_LINHA_ANP, len(linhas)):
        linha = list(linhas[i]) + [""] * 10
        produto = str(linha[0]).strip()
        # O rodapé ("Notas: …") tem texto na coluna A mas nenhuma data serial.
        if not produto or not (_serial(linha[1]) and _serial(linha[2])):
            break
        numero = i + 1
        inicio, fim = _data(linha[1]), _data(linha[2])
        if fim < inicio:
            erros.append(
                f"linha {numero}: a semana termina ({fim:%d/%m/%Y}) antes de "
                f"começar ({inicio:%d/%m/%Y})."
            )
            continue
        inicios[produto][inicio] += 1
        for k, regiao in enumerate(REGIOES_ANP):
            try:
                preco = _preco(linha[COL_PRIMEIRA_REGIAO + k])
            except ValueError as e:
                erros.append(f"linha {numero}, {regiao}: {e}.")
                continue
            registros.append(
                {
                    "produto": produto,
                    "vigencia_inicio": inicio,
                    "vigencia_fim": fim,
                    "regiao": regiao,
                    "preco": preco,
                }
            )

    if erros:
        raise _recusar(erros)

    # Semanas repetidas num produto são séries distintas publicadas sob o mesmo
    # nome (no arquivo oficial, só o GLP). Não há como escolher uma: o produto
    # fica de fora, e os demais — entre eles o CAP — são importados.
    avisos = []
    excluidos = set()
    for produto, contagem in inicios.items():
        repetidas = sum(1 for n in contagem.values() if n > 1)
        if repetidas:
            excluidos.add(produto)
            avisos.append(
                f"{produto}: {repetidas} semana(s) aparecem mais de uma vez no "
                "arquivo — séries distintas sob o mesmo nome; o produto não foi "
                "importado."
            )
    registros = [r for r in registros if r["produto"] not in excluidos]
    if not registros:
        raise ArquivoInvalido("O arquivo não tem nenhuma semana de preços.")
    return Leitura(registros, avisos)


def ler_anp(conteudo: bytes) -> Leitura:
    try:
        livro = xlrd.open_workbook(file_contents=conteudo)
    except Exception as e:
        raise _layout("não é uma planilha .xls legível") from e
    if ABA_ANP not in livro.sheet_names():
        raise _layout(f"falta a aba '{ABA_ANP}'")
    aba = livro.sheet_by_name(ABA_ANP)
    return ler_linhas_anp([aba.row_values(i) for i in range(aba.nrows)])


def sobreposicoes(novos: list[dict], existentes: dict) -> list[str]:
    """Semanas do arquivo que se sobrepõem entre si ou às já cadastradas.

    *existentes* vem de ``indices_repo.precos_anp_por_chave``. Uma semana do
    arquivo com o mesmo início de uma cadastrada a substitui (é uma correção),
    então só a do arquivo entra na verificação. Sobreposições só entre semanas
    cadastradas não são reportadas: a constraint do banco já as impede.
    """
    semanas: dict[tuple[str, str], dict[date, tuple[date, bool]]] = defaultdict(dict)
    for (produto, inicio, regiao), linha in existentes.items():
        semanas[(produto, regiao)][inicio] = (linha["vigencia_fim"], False)
    for r in novos:
        semanas[(r["produto"], r["regiao"])][r["vigencia_inicio"]] = (r["vigencia_fim"], True)

    erros = []
    for (produto, regiao), por_inicio in semanas.items():
        anterior: tuple[date, date, bool] | None = None  # a de maior fim até aqui
        for inicio in sorted(por_inicio):
            fim, do_arquivo = por_inicio[inicio]
            if anterior and inicio <= anterior[1] and (do_arquivo or anterior[2]):
                a_ini, a_fim, a_arq = anterior
                if do_arquivo and a_arq:
                    texto = (f"a semana {_semana(inicio, fim)} se sobrepõe à semana "
                             f"{_semana(a_ini, a_fim)} do próprio arquivo.")
                elif do_arquivo:
                    texto = (f"a semana {_semana(inicio, fim)} se sobrepõe à semana "
                             f"{_semana(a_ini, a_fim)} já cadastrada.")
                else:
                    texto = (f"a semana {_semana(a_ini, a_fim)} do arquivo se sobrepõe "
                             f"à semana {_semana(inicio, fim)} já cadastrada.")
                erros.append(f"{produto}, {regiao}: {texto}")
            if anterior is None or fim > anterior[1]:
                anterior = (inicio, fim, do_arquivo)
    return erros


# --- IGP-DI ----------------------------------------------------------------------

def _mes(valor) -> date | None:
    # datetime antes de date: datetime é subclasse de date.
    if isinstance(valor, datetime):
        return inicio_do_mes(valor.date())
    if isinstance(valor, date):
        return inicio_do_mes(valor)
    if isinstance(valor, str):
        m = _MES_TEXTO.match(valor)
        if m and 1 <= int(m.group(1)) <= 12:
            return date(int(m.group(2)), int(m.group(1)), 1)
    return None


def _valor_igp(valor) -> Decimal | None:
    if isinstance(valor, bool) or not isinstance(valor, (int, float, Decimal)):
        return None
    numero = Decimal(str(valor))
    return numero if numero > 0 else None


def _vazia(celulas) -> bool:
    return all(c is None or (isinstance(c, str) and not c.strip()) for c in celulas)


def ler_linhas_igp_di(linhas: list[list]) -> Leitura:
    cabecalho = [str(c or "").strip().casefold() for c in (list(linhas[0]) if linhas else [])[:2]]
    if cabecalho != [c.casefold() for c in CABECALHO_IGP]:
        raise ArquivoInvalido(
            f"A aba '{ABA_IGP}' deve ter Mês e Valor nas colunas A e B da linha 1."
        )
    registros: list[dict] = []
    erros: list[str] = []
    vistos: dict[date, int] = {}
    for numero, linha in enumerate(linhas[1:], start=2):
        bruto_mes, bruto_valor = (list(linha) + [None, None])[:2]
        if _vazia((bruto_mes, bruto_valor)):
            continue
        mes = _mes(bruto_mes)
        if mes is None:
            erros.append(f"linha {numero}: mês {bruto_mes!r} ilegível; use uma data ou MM/AAAA.")
            continue
        valor = _valor_igp(bruto_valor)
        if valor is None:
            erros.append(f"linha {numero}: valor {bruto_valor!r} não é um número maior que zero.")
            continue
        if mes in vistos:
            erros.append(f"linha {numero}: o mês {mes:%m/%Y} já aparece na linha {vistos[mes]}.")
            continue
        vistos[mes] = numero
        registros.append(
            {"indice": INDICE_IGP_DI, "mes_ref": mes, "valor": valor, "base_label": BASE_IGP_DI}
        )
    if erros:
        raise _recusar(erros)
    if not registros:
        raise ArquivoInvalido("O arquivo não tem nenhum mês preenchido.")
    return Leitura(registros)


def ler_igp_di(conteudo: bytes) -> Leitura:
    try:
        livro = openpyxl.load_workbook(io.BytesIO(conteudo), read_only=True, data_only=True)
    except Exception as e:
        raise ArquivoInvalido("O arquivo não é uma planilha .xlsx legível.") from e
    try:
        if ABA_IGP not in livro.sheetnames:
            raise ArquivoInvalido(
                f"O arquivo não tem a aba '{ABA_IGP}'. Use o template de importação do IGP-DI."
            )
        linhas = [list(r) for r in livro[ABA_IGP].iter_rows(values_only=True)]
    finally:
        livro.close()
    return ler_linhas_igp_di(linhas)


def gerar_template_igp_di(registros: list[dict]) -> bytes:
    """O template de importação, preenchido com *registros* (``mes_ref``, ``valor``).

    O mesmo arquivo serve de exportação: reimportá-lo não altera nada.
    """
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = ABA_IGP
    ws.append(list(CABECALHO_IGP))
    for celula in ws[1]:
        celula.font = Font(bold=True)
    for r in sorted(registros, key=lambda r: r["mes_ref"]):
        ws.append([r["mes_ref"], float(r["valor"])])
        ws.cell(ws.max_row, 1).number_format = "mmm/yyyy"
    ws.freeze_panes = "A2"
    ws.column_dimensions["A"].width = 12
    ws.column_dimensions["B"].width = 14

    instrucoes = wb.create_sheet(ABA_INSTRUCOES)
    for texto in INSTRUCOES_IGP:
        instrucoes.append([texto])
    instrucoes.column_dimensions["A"].width = 90

    saida = io.BytesIO()
    wb.save(saida)
    return saida.getvalue()
```

- [ ] **Step 5: Rodar os testes dos importadores**

Run: `uv run pytest tests/test_importadores.py -q`
Expected: PASS. `test_arquivo_oficial` leva alguns segundos (60 mil registros).

- [ ] **Step 6: Escrever `tests/test_importacao.py`**

```python
"""Importação contra o banco: prévia, inalterados, conflito manual, tudo ou nada."""

from datetime import date
from decimal import Decimal

import pytest

from app.services import importacao, importadores, indices_repo
from app.services.delta_p import ANP_PRODUTO_CAP
from app.services.importadores import ArquivoInvalido, Leitura

from .indices_factory import mes_igp, semana

CAP = ANP_PRODUTO_CAP


def _leitura(*semanas):
    return Leitura(list(semanas))


def _anp(leitura, **opcoes):
    return importacao.importar_precos(leitura, arquivo="anp.xls", **opcoes)


async def test_primeira_importacao_insere_e_a_segunda_nao_muda_nada():
    leitura = _leitura(semana(date(2023, 1, 9), "3.28568"), semana(date(2023, 1, 16), "3.3"))
    primeira = _anp(leitura)
    assert primeira["inseridos"] == 2 and primeira["inalterados"] == 0
    assert primeira["periodo"] == {"de": date(2023, 1, 9), "ate": date(2023, 1, 22)}
    assert indices_repo.listar_precos_anp()[0]["origem"] == "upload:anp.xls"

    segunda = importacao.importar_precos(leitura, arquivo="outro.xls")
    assert segunda["inseridos"] == 0 and segunda["inalterados"] == 2
    assert segunda["atualizados"] == []
    assert {l["origem"] for l in indices_repo.listar_precos_anp()} == {"upload:anp.xls"}


async def test_simulacao_nao_grava():
    resposta = _anp(_leitura(semana(date(2023, 1, 9), "3.28")), simular=True)
    assert resposta["simulacao"] is True and resposta["inseridos"] == 1
    assert indices_repo.listar_precos_anp() == []


async def test_atualizacao_lista_antes_e_depois():
    indices_repo.gravar_precos_anp([semana(date(2023, 1, 9), "3.28")], origem="seed")
    resposta = _anp(_leitura(semana(date(2023, 1, 9), "3.30")))
    (alteracao,) = resposta["atualizados"]
    assert alteracao["antes"] == Decimal("3.28") and alteracao["depois"] == Decimal("3.30")
    assert alteracao["chave"] == {
        "produto": CAP, "regiao": "Nordeste",
        "vigencia_inicio": "2023-01-09", "vigencia_fim": "2023-01-15",
    }


async def test_valor_manual_e_preservado_por_padrao():
    indices_repo.gravar_semana_manual(
        {"vigencia_inicio": date(2023, 1, 9), "vigencia_fim": date(2023, 1, 15),
         "regiao": "Nordeste", "preco": "9.99"}
    )
    resposta = _anp(_leitura(semana(date(2023, 1, 9), "3.28"), semana(date(2023, 1, 16), "3.3")))
    assert resposta["manuais_preservados"] == 1 and resposta["inseridos"] == 1
    (conflito,) = resposta["conflitos_manuais"]
    assert conflito["valor_banco"] == Decimal("9.99") and conflito["valor_arquivo"] == Decimal("3.28")
    assert conflito["atualizado_em"] is not None
    salvo = indices_repo.buscar_semana(CAP, "Nordeste", date(2023, 1, 9))
    assert salvo["preco"] == Decimal("9.99") and salvo["origem"] == indices_repo.ORIGEM_MANUAL


async def test_sobrescrever_manuais_faz_o_arquivo_vencer():
    indices_repo.gravar_semana_manual(
        {"vigencia_inicio": date(2023, 1, 9), "vigencia_fim": date(2023, 1, 15),
         "regiao": "Nordeste", "preco": "9.99"}
    )
    resposta = _anp(_leitura(semana(date(2023, 1, 9), "3.28")), sobrescrever_manuais=True)
    assert resposta["manuais_preservados"] == 0
    assert len(resposta["conflitos_manuais"]) == 1 and len(resposta["atualizados"]) == 1
    salvo = indices_repo.buscar_semana(CAP, "Nordeste", date(2023, 1, 9))
    assert salvo["preco"] == Decimal("3.28") and salvo["origem"] == "upload:anp.xls"


async def test_sobreposicao_recusa_o_arquivo_sem_gravar_nada():
    indices_repo.gravar_precos_anp([semana(date(2023, 1, 9), "3.28")])
    with pytest.raises(ArquivoInvalido) as erro:
        _anp(_leitura(semana(date(2023, 1, 30), "3.1"), semana(date(2023, 1, 12), "3.3")))
    assert "sobreposta" in erro.value.mensagem
    assert len(indices_repo.listar_precos_anp()) == 1


async def test_origem_explicita_para_o_seed():
    _anp(_leitura(semana(date(2023, 1, 9), "3.28")), origem=indices_repo.ORIGEM_SEED)
    assert indices_repo.listar_precos_anp()[0]["origem"] == "seed"


async def test_importar_igp_di_do_template():
    indices_repo.gravar_indice_manual(date(2023, 1, 1), "1000")
    conteudo = importadores.gerar_template_igp_di(
        [mes_igp(date(2022, 1, 1), "1110.398"), mes_igp(date(2023, 1, 1), "1143.861")]
    )
    resposta = importacao.importar_igp_di(conteudo, "igp.xlsx")
    assert resposta["inseridos"] == 1 and resposta["manuais_preservados"] == 1
    assert resposta["conflitos_manuais"][0]["chave"] == {"mes": "2023-01"}
    assert resposta["periodo"] == {"de": date(2022, 1, 1), "ate": date(2023, 1, 1)}
    assert indices_repo.buscar_indice(date(2022, 1, 1))["origem"] == "upload:igp.xlsx"
    assert indices_repo.buscar_indice(date(2023, 1, 1))["valor"] == Decimal("1000")


async def test_importar_anp_repassa_o_erro_de_leitura():
    with pytest.raises(ArquivoInvalido):
        importacao.importar_anp(b"lixo", "x.xls")
```

- [ ] **Step 7: Rodar e ver falhar**

Run: `uv run pytest tests/test_importacao.py -q`
Expected: FAIL — `ImportError: cannot import name 'importacao'`.

- [ ] **Step 8: Criar `app/services/importacao.py`**

```python
"""O que uma importação de índices faz com o banco.

``importadores`` diz se o arquivo é válido; este módulo compara com o que está
gravado e decide o que regravar: valores iguais ficam como estão (origem e data
preservadas), valores ``origem = 'manual'`` só são sobrescritos quando o usuário
pede, e ``simular`` devolve o mesmo relatório sem gravar — a prévia que a tela
mostra antes da pergunta "Deseja sobrescrever as N alterações manuais?".
"""

from dataclasses import dataclass, field

from . import importadores, indices_repo
from .importadores import ArquivoInvalido, Leitura


@dataclass
class Plano:
    gravar: list[dict] = field(default_factory=list)
    inseridos: int = 0
    atualizados: list[dict] = field(default_factory=list)
    inalterados: int = 0
    conflitos_manuais: list[dict] = field(default_factory=list)


def planejar(novos, existentes, *, chave, comparavel, valor, mostrar, sobrescrever_manuais) -> Plano:
    """Classifica cada registro do arquivo contra o banco."""
    plano = Plano()
    for registro in novos:
        atual = existentes.get(chave(registro))
        if atual is None:
            plano.inseridos += 1
            plano.gravar.append(registro)
            continue
        if comparavel(atual) == comparavel(registro):
            plano.inalterados += 1
            continue
        if atual["origem"] == indices_repo.ORIGEM_MANUAL:
            plano.conflitos_manuais.append(
                {
                    "chave": mostrar(registro),
                    "valor_banco": valor(atual),
                    "valor_arquivo": valor(registro),
                    "atualizado_em": atual["atualizado_em"],
                }
            )
            if not sobrescrever_manuais:
                continue
        plano.atualizados.append(
            {"chave": mostrar(registro), "antes": valor(atual), "depois": valor(registro)}
        )
        plano.gravar.append(registro)
    return plano


def _resposta(arquivo, simular, sobrescrever_manuais, plano: Plano, avisos, de, ate) -> dict:
    return {
        "arquivo": arquivo,
        "simulacao": simular,
        "periodo": {"de": de, "ate": ate},
        "inseridos": plano.inseridos,
        "atualizados": plano.atualizados,
        "inalterados": plano.inalterados,
        "conflitos_manuais": plano.conflitos_manuais,
        "manuais_preservados": 0 if sobrescrever_manuais else len(plano.conflitos_manuais),
        "avisos": list(avisos),
    }


def importar_precos(
    leitura: Leitura, *, arquivo: str, simular: bool = False,
    sobrescrever_manuais: bool = False, origem: str | None = None,
) -> dict:
    novos = leitura.registros
    existentes = indices_repo.precos_anp_por_chave({r["produto"] for r in novos})
    conflitos = importadores.sobreposicoes(novos, existentes)
    if conflitos:
        raise ArquivoInvalido(
            f"O arquivo tem {len(conflitos)} semana(s) sobreposta(s); nada foi gravado.",
            importadores.limitar(conflitos),
        )
    plano = planejar(
        novos,
        existentes,
        chave=lambda r: (r["produto"], r["vigencia_inicio"], r["regiao"]),
        comparavel=lambda r: (r["vigencia_fim"], r["preco"]),
        valor=lambda r: r["preco"],
        mostrar=lambda r: {
            "produto": r["produto"],
            "regiao": r["regiao"],
            "vigencia_inicio": r["vigencia_inicio"].isoformat(),
            "vigencia_fim": r["vigencia_fim"].isoformat(),
        },
        sobrescrever_manuais=sobrescrever_manuais,
    )
    if not simular:
        indices_repo.gravar_precos_anp(
            plano.gravar, origem=origem or indices_repo.origem_upload(arquivo)
        )
    return _resposta(
        arquivo, simular, sobrescrever_manuais, plano, leitura.avisos,
        min(r["vigencia_inicio"] for r in novos), max(r["vigencia_fim"] for r in novos),
    )


def importar_indices(
    leitura: Leitura, *, arquivo: str, simular: bool = False,
    sobrescrever_manuais: bool = False, origem: str | None = None,
) -> dict:
    novos = leitura.registros
    plano = planejar(
        novos,
        indices_repo.indices_por_mes(),
        chave=lambda r: r["mes_ref"],
        comparavel=lambda r: r["valor"],
        valor=lambda r: r["valor"],
        mostrar=lambda r: {"mes": f"{r['mes_ref']:%Y-%m}"},
        sobrescrever_manuais=sobrescrever_manuais,
    )
    if not simular:
        indices_repo.gravar_indices_mensais(
            plano.gravar, origem=origem or indices_repo.origem_upload(arquivo)
        )
    return _resposta(
        arquivo, simular, sobrescrever_manuais, plano, leitura.avisos,
        min(r["mes_ref"] for r in novos), max(r["mes_ref"] for r in novos),
    )


def importar_anp(conteudo: bytes, arquivo: str, **opcoes) -> dict:
    return importar_precos(importadores.ler_anp(conteudo), arquivo=arquivo, **opcoes)


def importar_igp_di(conteudo: bytes, arquivo: str, **opcoes) -> dict:
    return importar_indices(importadores.ler_igp_di(conteudo), arquivo=arquivo, **opcoes)
```

- [ ] **Step 9: Rodar os testes de importação e a suíte**

Run: `uv run pytest tests/test_importadores.py tests/test_importacao.py -q && uv run pytest -q`
Expected: PASS.

- [ ] **Step 10: Commit**

```bash
git add app/services/importadores.py app/services/importacao.py tests/fixtures/anp_semanal.xls \
        tests/test_importadores.py tests/test_importacao.py pyproject.toml uv.lock requirements.txt
git commit -m "$(cat <<'EOF'
feat: importação do .xls da ANP e do template do IGP-DI

Leitura validada linha a linha, tudo ou nada, com prévia sem gravar e
preservação das alterações manuais. Produto com semanas repetidas (o GLP
no arquivo oficial) é pulado com aviso. xlrd passa a ser dependência de
runtime; o arquivo oficial da ANP é versionado como fixture.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 4: Exportação dos índices (CSV e XLSX)

**Files:**
- Create: `app/services/exportadores.py`
- Create: `tests/test_exportadores.py`

**Interfaces:**
- Consumes: linhas de `indices_repo.listar_precos_anp` / `listar_indices_mensais` (Task 2); `importadores.gerar_template_igp_di` (Task 3).
- Produces:
  - `exportadores.COLUNAS_ANP = ("produto", "vigencia_inicio", "vigencia_fim", "regiao", "preco", "origem", "atualizado_em")`
  - `exportadores.COLUNAS_IGP = ("mes", "valor", "origem", "atualizado_em")`
  - `precos_csv(linhas) -> bytes`, `precos_xlsx(linhas) -> bytes`, `indices_csv(linhas) -> bytes`, `indices_xlsx(linhas) -> bytes`

- [ ] **Step 1: Escrever `tests/test_exportadores.py`**

```python
"""Exportação dos índices: uma linha por semana e região, valores exatos."""

import csv
import io
from datetime import date, datetime, timezone
from decimal import Decimal

import openpyxl

from app.services import exportadores, importadores

ATUALIZADO = datetime(2026, 9, 24, 13, 5, tzinfo=timezone.utc)
PRECOS = [
    {"id": 1, "produto": "CAP", "regiao": "Nordeste", "vigencia_inicio": date(2021, 12, 13),
     "vigencia_fim": date(2021, 12, 19), "preco": Decimal("4.02073"), "origem": "seed",
     "atualizado_em": ATUALIZADO},
    {"id": 2, "produto": "CAP", "regiao": "Centro-Oeste", "vigencia_inicio": date(2021, 12, 13),
     "vigencia_fim": date(2021, 12, 19), "preco": None, "origem": "manual",
     "atualizado_em": ATUALIZADO},
]
INDICES = [
    {"id": 1, "indice": "IGP - DI", "base_label": "ago/1994 = 100", "mes_ref": date(2022, 1, 1),
     "valor": Decimal("1110.398"), "origem": "seed", "atualizado_em": ATUALIZADO},
]


def _csv(conteudo: bytes) -> list[dict]:
    return list(csv.DictReader(io.StringIO(conteudo.decode("utf-8"))))


def test_precos_csv():
    linhas = _csv(exportadores.precos_csv(PRECOS))
    assert list(linhas[0]) == list(exportadores.COLUNAS_ANP)
    assert linhas[0]["preco"] == "4.02073"
    assert linhas[0]["vigencia_inicio"] == "2021-12-13"
    assert linhas[0]["atualizado_em"] == "2026-09-24T13:05:00+00:00"
    assert linhas[1]["preco"] == ""


def test_precos_xlsx():
    ws = openpyxl.load_workbook(io.BytesIO(exportadores.precos_xlsx(PRECOS))).active
    assert [c.value for c in ws[1]] == list(exportadores.COLUNAS_ANP)
    assert ws["E2"].value == 4.02073
    assert ws["B2"].value.date() == date(2021, 12, 13)
    assert ws["E3"].value is None
    assert ws["G2"].value == "2026-09-24T13:05:00+00:00"


def test_indices_csv():
    (linha,) = _csv(exportadores.indices_csv(INDICES))
    assert linha == {"mes": "2022-01", "valor": "1110.398", "origem": "seed",
                     "atualizado_em": "2026-09-24T13:05:00+00:00"}


def test_indices_xlsx_e_o_template_reimportavel():
    leitura = importadores.ler_igp_di(exportadores.indices_xlsx(INDICES))
    assert [(r["mes_ref"], r["valor"]) for r in leitura.registros] == [
        (date(2022, 1, 1), Decimal("1110.398"))
    ]
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `uv run pytest tests/test_exportadores.py -q`
Expected: FAIL — `ImportError: cannot import name 'exportadores'`.

- [ ] **Step 3: Criar `app/services/exportadores.py`**

```python
"""Exportação dos índices gravados, para conferência ou edição fora da aplicação.

CSV em UTF-8 com datas ISO e decimais com ponto — pensado para curl e scripts.
O XLSX do IGP-DI é o próprio template de importação preenchido, então editar e
reenviar o arquivo exportado é o caminho de edição em massa.
"""

import csv
import io

import openpyxl
from openpyxl.styles import Font

from .importadores import gerar_template_igp_di

COLUNAS_ANP = ("produto", "vigencia_inicio", "vigencia_fim", "regiao", "preco", "origem", "atualizado_em")
COLUNAS_IGP = ("mes", "valor", "origem", "atualizado_em")


def _texto(valor) -> str:
    if valor is None:
        return ""
    if hasattr(valor, "isoformat"):
        return valor.isoformat()
    return str(valor)  # Decimal por str: sem passar por float


def _csv(colunas, linhas) -> bytes:
    saida = io.StringIO()
    escritor = csv.writer(saida, lineterminator="\n")
    escritor.writerow(colunas)
    escritor.writerows([[_texto(v) for v in linha] for linha in linhas])
    return saida.getvalue().encode("utf-8")


def _valores_anp(linha: dict) -> list:
    return [linha[c] for c in COLUNAS_ANP]


def precos_csv(linhas: list[dict]) -> bytes:
    return _csv(COLUNAS_ANP, [_valores_anp(l) for l in linhas])


def precos_xlsx(linhas: list[dict]) -> bytes:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Preços ANP"
    ws.append(list(COLUNAS_ANP))
    for celula in ws[1]:
        celula.font = Font(bold=True)
    for linha in linhas:
        # openpyxl não grava datetime com fuso; atualizado_em vai como texto ISO.
        ws.append([
            linha["produto"], linha["vigencia_inicio"], linha["vigencia_fim"], linha["regiao"],
            None if linha["preco"] is None else float(linha["preco"]),
            linha["origem"], _texto(linha["atualizado_em"]),
        ])
        for coluna in (2, 3):
            ws.cell(ws.max_row, coluna).number_format = "dd/mm/yyyy"
    ws.freeze_panes = "A2"
    ws.column_dimensions["A"].width = 48
    saida = io.BytesIO()
    wb.save(saida)
    return saida.getvalue()


def indices_csv(linhas: list[dict]) -> bytes:
    return _csv(
        COLUNAS_IGP,
        [[f"{l['mes_ref']:%Y-%m}", l["valor"], l["origem"], l["atualizado_em"]] for l in linhas],
    )


def indices_xlsx(linhas: list[dict]) -> bytes:
    return gerar_template_igp_di(linhas)
```

- [ ] **Step 4: Rodar os testes**

Run: `uv run pytest tests/test_exportadores.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/services/exportadores.py tests/test_exportadores.py
git commit -m "$(cat <<'EOF'
feat: exportação dos índices em CSV e XLSX

Preços ANP com uma linha por semana e região, origem e data de
atualização; o XLSX do IGP-DI é o template de importação preenchido.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 5: Contrato editável e cálculo com simulação de região

**Files:**
- Modify: `app/services/contratos_repo.py`
- Modify: `app/services/reequilibrio_export.py`
- Modify: `tests/test_contratos_repo.py`, `tests/test_reequilibrio_export.py`

**Interfaces:**
- Consumes: `indices_repo.normalizar_regiao`, `regioes_disponiveis` (Task 2); `catalogo.ROTULOS_FAMILIA` (Task 1); `tests/indices_factory.semana/mes_igp` (Task 2).
- Produces:
  - `contratos_repo.CAMPOS_EDITAVEIS = CAMPOS_CADASTRO + ("data_base",)`
  - `contratos_repo.CadastroInvalido(ValueError)`
  - `contratos_repo.buscar_por_id(contrato_id: int) -> dict | None` (com `regioes`)
  - `contratos_repo.atualizar(contrato_id: int, dados: dict, regioes: dict[str, str] | None = None) -> bool` — `False` se o contrato não existe
  - `contratos_repo.listar(numero: str | None = None) -> list[dict]` — acrescenta `medicoes` (meses distintos), `regioes`, `faltantes`
  - `reequilibrio_export.ExportacaoImpossivel(mensagem, faltando: list[str] | None = None)` com `.mensagem` e `.faltando`
  - `reequilibrio_export.regioes_efetivas(contrato, override) -> tuple[dict[str, str], dict[str, str]]` — `(efetivas, simuladas)`
  - `reequilibrio_export.calcular_deltas(contrato, itens, regioes_override=None)`
  - `reequilibrio_export.Calculo(contrato, regioes, simuladas, grupos, descartadas, avisos)`
  - `reequilibrio_export.calcular(contrato: dict, regioes_override=None) -> Calculo`
  - `reequilibrio_export.gerar(calculo: Calculo, template: bytes) -> Resultado`
  - `reequilibrio_export.serializar(calculo: Calculo) -> dict` — chaves `contrato{id, numero}`, `parametros{data_base, regioes, simulacao, lucro}`, `familias[{familia, rotulo, subtotal, produtos[{descricao, subtotal, linhas[{mes, a, fator, b, d, c, e, f}]}]}]`, `total`, `avisos`
  - `reequilibrio_export.exportar(numero_contrato, template, regioes_override=None) -> Resultado`
  - Aviso de simulação: `"Simulação: CAP calculado com a região Sul (cadastro: Nordeste)."` — só caracteres latin-1, porque vai para `X-Avisos`.

- [ ] **Step 1: Escrever os testes de contrato**

Em `tests/test_contratos_repo.py`, substitua `test_cadastro_nao_pode_alterar_a_data_base` inteiro por:

```python
async def test_cadastro_pode_corrigir_a_data_base():
    """A Data Base vem sugerida pelo PDF e é editável (spec, regra 1)."""
    contratos_repo.registrar_do_pdf(HEADER)
    contratos_repo.salvar_cadastro(
        "06 00134/2022", {"data_base": "15/01/2019", "rodovia": "BR-135/MA"}
    )
    contrato = contratos_repo.buscar("06 00134/2022")
    assert contrato["data_base"] == date(2019, 1, 1)
    assert contrato["rodovia"] == "BR-135/MA"
    # E reprocessar o PDF não desfaz a correção.
    contratos_repo.registrar_do_pdf(HEADER)
    assert contratos_repo.buscar("06 00134/2022")["data_base"] == date(2019, 1, 1)
```

E acrescente ao fim do arquivo (com `from app.services import indices_repo` e
`from .indices_factory import semana` nos imports do topo):

```python
def _precos(*regioes):
    indices_repo.gravar_precos_anp([semana(date(2023, 1, 9), "3.2", regiao=r) for r in regioes])


async def test_atualizar_campos_data_base_e_regioes():
    _precos("Nordeste", "Sul")
    contrato_id = contratos_repo.registrar_do_pdf(HEADER)
    assert contratos_repo.atualizar(
        contrato_id,
        {"rodovia": "BR-316/MA", "extensao": "188,7", "data_base": "2022-01"},
        regioes={"CAP": "NORDESTE", "EMULSOES": "sul"},
    ) is True
    contrato = contratos_repo.buscar_por_id(contrato_id)
    assert contrato["rodovia"] == "BR-316/MA"
    assert contrato["extensao"] == Decimal("188.7")
    assert contrato["data_base"] == date(2022, 1, 1)
    assert contrato["regioes"] == {FAMILIA_CAP: "Nordeste", FAMILIA_EMULSOES: "Sul"}


async def test_atualizar_contrato_inexistente():
    assert contratos_repo.atualizar(999, {"rodovia": "x"}) is False
    assert contratos_repo.buscar_por_id(999) is None


@pytest.mark.parametrize(
    "dados,regioes,trecho",
    [
        ({"numero": "1"}, None, "numero"),
        ({"data_base": ""}, None, "Data Base"),
        ({"data_base": "janeiro"}, None, "ilegível"),
        ({}, {"ASFALTO": "Nordeste"}, "Família"),
        ({}, {"CAP": "Marte"}, "Nordeste"),
    ],
)
async def test_atualizar_recusa_sem_gravar_nada(dados, regioes, trecho):
    _precos("Nordeste")
    contrato_id = contratos_repo.registrar_do_pdf(HEADER)
    with pytest.raises(contratos_repo.CadastroInvalido) as erro:
        contratos_repo.atualizar(contrato_id, {"rodovia": "BR-1", **dados}, regioes)
    assert trecho in str(erro.value)
    assert contratos_repo.buscar_por_id(contrato_id)["rodovia"] is None


async def test_regiao_sem_precos_importados_orienta_a_importar():
    contrato_id = contratos_repo.registrar_do_pdf(HEADER)
    with pytest.raises(contratos_repo.CadastroInvalido) as erro:
        contratos_repo.atualizar(contrato_id, {}, {"CAP": "Nordeste"})
    assert "importe os preços ANP" in str(erro.value)


async def test_listar_traz_resumo_e_filtra_por_numero():
    contrato_id = contratos_repo.registrar_do_pdf(HEADER)
    contratos_repo.definir_regiao("06 00134/2022", FAMILIA_CAP, "Nordeste")
    medicoes_repo.gravar_itens(
        contrato_id,
        [
            {"Serviço": "60112", "Descrição": "CAP", "Valor a PI Líquido": 1.0, "Fator": 0.1,
             "Período Líquido": f"01/0{m}/2023 - 28/0{m}/2023", "Source_File": f"{m}.pdf"}
            for m in (1, 2)
        ],
    )
    (linha,) = contratos_repo.listar()
    assert linha["itens"] == 2 and linha["medicoes"] == 2
    assert linha["regioes"] == {FAMILIA_CAP: "Nordeste"}
    assert "regiao_emulsoes" in linha["faltantes"]
    assert contratos_repo.listar("00134") == [linha]
    assert contratos_repo.listar("99999") == []
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `uv run pytest tests/test_contratos_repo.py -q`
Expected: FAIL — `test_cadastro_pode_corrigir_a_data_base` (a data base não muda) e `AttributeError: ... 'atualizar'`.

- [ ] **Step 3: Implementar em `app/services/contratos_repo.py`**

Troque o import de `delta_p` e acrescente o de `indices_repo`:

```python
from . import indices_repo
from .delta_p import FAMILIA_CAP, FAMILIA_EMULSOES, FAMILIAS, inicio_do_mes
```

Logo depois de `CAMPOS_CADASTRO`, acrescente:

```python
# Data Base: sugerida pelo PDF, corrigível pelo usuário (define o mês-base do ΔP).
CAMPOS_EDITAVEIS = CAMPOS_CADASTRO + ("data_base",)

_FORMATOS_DATA_BASE = ("%d/%m/%Y", "%Y-%m-%d", "%m/%Y", "%Y-%m")


class CadastroInvalido(ValueError):
    """Alteração de cadastro recusada, com mensagem para o usuário."""
```

Substitua `buscar`, `listar` e `salvar_cadastro` por:

```python
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
    if numero:
        sql += " WHERE c.numero ILIKE %s"
        params.append(f"%{numero.strip()}%")
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
```

Atualize o docstring do topo do módulo: troque "The rest (Edital, …) is
registered by the user and keyed by contract number." por "The rest (Edital, …)
is registered by the user, who may also correct the Data Base the PDF suggested."

- [ ] **Step 4: Rodar os testes de contrato**

Run: `uv run pytest tests/test_contratos_repo.py -q`
Expected: PASS.

- [ ] **Step 5: Escrever os testes do cálculo**

Em `tests/test_reequilibrio_export.py`:

1. Acrescente aos imports: `from app.services import indices_repo`, `Calculo`,
   `serializar` e `regioes_efetivas` no bloco `from app.services.reequilibrio_export import (...)`,
   e `from .indices_factory import mes_igp, semana`.
2. `test_exportar_sem_codigos_associados` (criado na Task 1) continua valendo:
   a mensagem de itens vazios se muda para `calcular` com o mesmo texto.
3. Acrescente ao fim:

```python
def _indices_para_fevereiro():
    """Base dez/2021 e jan/2023 (ANP do mês de fev/2023) em Nordeste e Sul."""
    for regiao, base, janeiro in (("Nordeste", "4.02073", "3.28568"), ("Sul", "4.29019", "3.45")):
        indices_repo.gravar_precos_anp(
            [semana(date(2021, 12, 13), base, regiao=regiao),
             semana(date(2023, 1, 9), janeiro, regiao=regiao)]
        )
    indices_repo.gravar_indices_mensais(
        [mes_igp(date(2022, 1, 1), "1110.398"), mes_igp(date(2023, 2, 1), "1144.271")]
    )


def _d(calculo) -> Decimal:
    return calculo.grupos[0].linhas[0].delta_p


async def test_simulacao_troca_a_regiao_so_nesta_geracao(template):
    await _contrato_com_medicoes()
    _indices_para_fevereiro()
    contrato = contratos_repo.buscar("15 00716/2022")

    padrao = reequilibrio_export.calcular(contrato)
    assert padrao.simuladas == {}
    assert abs(_d(padrao) - (Decimal("3.28568") / Decimal("4.02073") - 1)) < Decimal("1e-20")

    simulado = reequilibrio_export.calcular(contrato, {"CAP": "sul"})
    assert simulado.regioes[FAMILIA_CAP] == "Sul"
    assert simulado.simuladas == {FAMILIA_CAP: "Sul"}
    assert abs(_d(simulado) - (Decimal("3.45") / Decimal("4.29019") - 1)) < Decimal("1e-20")
    assert "Simulação: CAP calculado com a região Sul (cadastro: Nordeste)." in simulado.avisos
    for aviso in simulado.avisos:
        aviso.encode("latin-1")  # vai para o cabeçalho X-Avisos
    assert contratos_repo.buscar("15 00716/2022")["regioes"][FAMILIA_CAP] == "Nordeste"

    resultado = reequilibrio_export.exportar("15 00716/2022", template, {"CAP": "Sul"})
    assert resultado.avisos == simulado.avisos


async def test_override_igual_ao_cadastro_nao_e_simulacao():
    _indices_para_fevereiro()
    contrato = {"regioes": {FAMILIA_CAP: "Nordeste"}}
    efetivas, simuladas = regioes_efetivas(contrato, {"CAP": "NORDESTE", "EMULSOES": None})
    assert efetivas == {FAMILIA_CAP: "Nordeste"} and simuladas == {}


async def test_override_com_regiao_sem_preco_e_recusado():
    _indices_para_fevereiro()
    with pytest.raises(ExportacaoImpossivel) as erro:
        regioes_efetivas({"regioes": {}}, {"EMULSOES": "Centro-Oeste"})
    assert erro.value.faltando == ["regiao_emulsoes"]


async def test_sem_data_base_informa_o_campo():
    contrato_id = contratos_repo.registrar_do_pdf({**HEADER, "Data Base": ""})
    with pytest.raises(ExportacaoImpossivel) as erro:
        reequilibrio_export.calcular(contratos_repo.buscar_por_id(contrato_id))
    assert erro.value.faltando == ["data_base"]


async def test_indices_ausentes_vem_na_lista_faltando():
    await _contrato_com_medicoes()
    with pytest.raises(ExportacaoImpossivel) as erro:
        reequilibrio_export.calcular(contratos_repo.buscar("15 00716/2022"))
    assert erro.value.faltando
    assert all(f in erro.value.mensagem for f in erro.value.faltando)


def test_serializar_aplica_as_formulas_do_art_16():
    a, fator, d = Decimal("208133.17"), Decimal("-0.1839"), Decimal("-0.0758")
    calculo = Calculo(
        contrato={"id": 7, "numero": "15 00716/2022", "data_base": date(2022, 1, 1)},
        regioes={FAMILIA_CAP: "Nordeste"},
        simuladas={},
        grupos=[Grupo("AQUISIÇÃO DE CAP 50/70", FAMILIA_CAP, [Linha(date(2023, 1, 1), a, fator, d)])],
        descartadas=0,
        avisos=[],
    )
    dados = serializar(calculo)
    (familia,) = dados["familias"]
    assert familia["rotulo"] == "Aquisição de CAP"
    (linha,) = familia["produtos"][0]["linhas"]
    assert linha["b"] == Decimal("-38275.68")  # TRUNC(-38275.689963, 2)
    assert linha["c"] == a * d
    assert linha["e"] == a * d - Decimal("-38275.68")
    assert linha["f"] == linha["e"] * (1 - Decimal("0.0511"))
    assert familia["produtos"][0]["subtotal"] == familia["subtotal"] == dados["total"] == linha["f"]
    assert dados["parametros"] == {
        "data_base": date(2022, 1, 1), "regioes": {FAMILIA_CAP: "Nordeste"},
        "simulacao": False, "lucro": Decimal("0.0511"),
    }
    assert dados["contrato"] == {"id": 7, "numero": "15 00716/2022"}
```

- [ ] **Step 6: Rodar e ver falhar**

Run: `uv run pytest tests/test_reequilibrio_export.py -q`
Expected: FAIL — `ImportError: cannot import name 'Calculo'`.

- [ ] **Step 7: Implementar em `app/services/reequilibrio_export.py`**

Imports: troque `from decimal import Decimal` por `from decimal import ROUND_DOWN, Decimal`,
`from . import contratos_repo, medicoes_repo, xlsx_drawings` por
`from . import contratos_repo, indices_repo, medicoes_repo, xlsx_drawings`,
`from .delta_p import IndiceIndisponivel, delta_p` por
`from .delta_p import FAMILIAS, IndiceIndisponivel, delta_p`, e acrescente
`from .catalogo import ROTULOS_FAMILIA`.

Substitua a classe `ExportacaoImpossivel` por:

```python
class ExportacaoImpossivel(Exception):
    """The export cannot be produced, with a reason to show the user.

    ``faltando`` lists every missing piece (índices, data_base, a region), so
    the API can return them all at once instead of one per attempt.
    """

    def __init__(self, mensagem: str, faltando: list[str] | None = None) -> None:
        super().__init__(mensagem)
        self.mensagem = mensagem
        self.faltando = list(faltando or [])
```

Depois de `class Resultado`, acrescente:

```python
@dataclass
class Calculo:
    """Everything the JSON and the spreadsheet share, computed once."""

    contrato: dict
    regioes: dict[str, str]
    simuladas: dict[str, str]
    grupos: list[Grupo]
    descartadas: int
    avisos: list[str] = field(default_factory=list)


CENTAVO = Decimal("0.01")
```

Substitua `calcular_deltas` e `exportar` (do fim do arquivo) por:

```python
def regioes_efetivas(contrato: dict, override: dict | None = None) -> tuple[dict, dict]:
    """The regions this generation uses: the registered ones, replaced by
    *override* for this export only (a simulation). Returns ``(efetivas,
    simuladas)``; ``simuladas`` holds only families whose region changed."""
    cadastro = dict(contrato.get("regioes") or {})
    efetivas = dict(cadastro)
    simuladas: dict[str, str] = {}
    for familia, regiao in (override or {}).items():
        if not regiao:
            continue
        campo = f"regiao_{familia.lower()}"
        if familia not in FAMILIAS:
            raise ExportacaoImpossivel(f"Família desconhecida: {familia!r}.", [campo])
        grafia = indices_repo.normalizar_regiao(regiao)
        if grafia is None:
            raise ExportacaoImpossivel(
                f"Região {regiao!r} sem preços ANP do CAP 50/70; escolha uma das "
                "regiões importadas.",
                [campo],
            )
        efetivas[familia] = grafia
        if grafia != cadastro.get(familia):
            simuladas[familia] = grafia
    return efetivas, simuladas


def _deltas(contrato: dict, itens: list[dict], regioes: dict) -> tuple[dict, list[str]]:
    fonte = FonteBanco()
    deltas: dict[tuple[str, date], Decimal] = {}
    faltando: list[str] = []

    for item in itens:
        chave = (item["familia"], item["mes_medicao"])
        if chave in deltas:
            continue
        regiao = regioes.get(item["familia"])
        if not regiao:
            _anotar(faltando, f"Escolha a região da ANP para a família {item['familia']}.")
            continue
        try:
            deltas[chave] = delta_p(
                item["familia"],
                mes_medicao=item["mes_medicao"],
                data_base=contrato["data_base"],
                regiao=regiao,
                fonte=fonte,
            )
        except IndiceIndisponivel as e:
            _anotar(faltando, str(e))

    return deltas, faltando


def calcular_deltas(
    contrato: dict, itens: list[dict], regioes_override: dict | None = None
) -> tuple[dict, list[str]]:
    """ΔP for every (família, mês) the spreadsheet needs.

    A família whose region was never chosen, or a month with no published índice,
    blocks the export: a spreadsheet missing ΔP would look complete and be wrong.
    """
    regioes, _ = regioes_efetivas(contrato, regioes_override)
    return _deltas(contrato, itens, regioes)


def calcular(contrato: dict, regioes_override: dict | None = None) -> Calculo:
    """The whole calculation for a contract, shared by the JSON and the .xlsx."""
    if contrato.get("data_base") is None:
        raise ExportacaoImpossivel(
            "O contrato está sem Data Base, e sem ela não há como calcular o ΔP.",
            ["data_base"],
        )
    regioes, simuladas = regioes_efetivas(contrato, regioes_override)

    itens = medicoes_repo.itens_para_export(contrato["id"])
    if not itens:
        raise ExportacaoImpossivel(
            "Nenhum código de serviço deste contrato está associado a um produto. "
            "Associe os códigos no catálogo ou processe as medições."
        )

    deltas, faltando = _deltas(contrato, itens, regioes)
    if faltando:
        raise ExportacaoImpossivel(
            "Faltam dados para calcular o ΔP:\n- " + "\n- ".join(faltando), faltando
        )

    grupos, descartadas = montar_grupos(itens, deltas)

    avisos = []
    for familia, regiao in simuladas.items():
        cadastrada = (contrato.get("regioes") or {}).get(familia) or "sem região"
        avisos.append(
            f"Simulação: {familia} calculado com a região {regiao} (cadastro: {cadastrada})."
        )
    if descartadas:
        avisos.append(
            f"{descartadas} linha(s) repetida(s) foram ignoradas: a mesma medição "
            "consta de mais de um arquivo enviado."
        )
    faltam_cadastro = contratos_repo.campos_faltantes(contrato)
    if faltam_cadastro:
        avisos.append(
            "Campos do contrato ainda não cadastrados: " + ", ".join(faltam_cadastro)
        )

    return Calculo(contrato, regioes, simuladas, grupos, descartadas, avisos)


def gerar(calculo: Calculo, template: bytes) -> Resultado:
    return Resultado(
        conteudo=gerar_planilha(calculo.contrato, calculo.grupos, template),
        grupos=len(calculo.grupos),
        linhas=sum(len(g.linhas) for g in calculo.grupos),
        descartadas=calculo.descartadas,
        avisos=calculo.avisos,
    )


def serializar(calculo: Calculo) -> dict:
    """The calculation as data, with the spreadsheet's formulas evaluated.

    Same letters as row 16 of the template: ``b = TRUNC(a·fator, 2)``,
    ``c = a·d``, ``e = c − b``, ``f = e·(1 − lucro)``. TRUNC rounds toward zero,
    which is ``ROUND_DOWN`` in Decimal.
    """
    fator_lucro = 1 - Decimal(LUCRO)
    familias: list[dict] = []
    por_familia: dict[str, dict] = {}
    total = Decimal(0)
    for grupo in calculo.grupos:
        familia = por_familia.get(grupo.familia)
        if familia is None:
            familia = {
                "familia": grupo.familia,
                "rotulo": ROTULOS_FAMILIA.get(grupo.familia, grupo.familia),
                "subtotal": Decimal(0),
                "produtos": [],
            }
            por_familia[grupo.familia] = familia
            familias.append(familia)
        linhas = []
        subtotal = Decimal(0)
        for linha in grupo.linhas:
            b = (linha.valor_pi * linha.fator).quantize(CENTAVO, rounding=ROUND_DOWN)
            c = linha.valor_pi * linha.delta_p
            e = c - b
            f = e * fator_lucro
            linhas.append({"mes": linha.mes, "a": linha.valor_pi, "fator": linha.fator,
                           "b": b, "d": linha.delta_p, "c": c, "e": e, "f": f})
            subtotal += f
        familia["produtos"].append(
            {"descricao": grupo.descricao, "subtotal": subtotal, "linhas": linhas}
        )
        familia["subtotal"] += subtotal
        total += subtotal
    return {
        "contrato": {"id": calculo.contrato["id"], "numero": calculo.contrato["numero"]},
        "parametros": {
            "data_base": calculo.contrato["data_base"],
            "regioes": calculo.regioes,
            "simulacao": bool(calculo.simuladas),
            "lucro": Decimal(LUCRO),
        },
        "familias": familias,
        "total": total,
        "avisos": calculo.avisos,
    }


def exportar(
    numero_contrato: str, template: bytes, regioes_override: dict | None = None
) -> Resultado:
    """Assemble the spreadsheet for a contract from what is in the database."""
    contrato = contratos_repo.buscar(numero_contrato)
    if contrato is None:
        raise ExportacaoImpossivel(f"Contrato '{numero_contrato}' não cadastrado.")
    return gerar(calcular(contrato, regioes_override), template)
```

`catalogo` não importa `reequilibrio_export`, então o import novo não cria ciclo.

- [ ] **Step 8: Rodar os testes do cálculo e a suíte**

Run: `uv run pytest tests/test_reequilibrio_export.py tests/test_contratos_repo.py -q && uv run pytest -q`
Expected: PASS. O Dash (`data_loader`) continua chamando `calcular_deltas(contrato, itens)` sem override — compatível.

- [ ] **Step 9: Commit**

```bash
git add app/services/contratos_repo.py app/services/reequilibrio_export.py \
        tests/test_contratos_repo.py tests/test_reequilibrio_export.py
git commit -m "$(cat <<'EOF'
feat: Data Base editável e cálculo com simulação de região

O cadastro passa a aceitar correção da Data Base e grava regiões
validadas contra os preços ANP importados. O cálculo é uma função única
para o JSON e a planilha, aceita trocar a região por família só naquela
geração e informa em faltando tudo o que impede o ΔP.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 6: API `/api/v1` — contratos e catálogo

**Files:**
- Create: `app/routers/api/__init__.py`, `app/routers/api/erros.py`, `app/routers/api/schemas.py`, `app/routers/api/contratos.py`, `app/routers/api/catalogo.py`
- Modify: `app/main.py`
- Test: `tests/test_api_contratos.py`, `tests/test_api_catalogo.py`

**Interfaces:**
- Consumes: `contratos_repo.listar/buscar_por_id/atualizar/campos_faltantes/CadastroInvalido` (Task 5); `catalogo.listar_produtos/buscar_produto/novo_produto/atualizar_produto/excluir_produto/buscar_codigos/registrar_codigo/buscar_por_codigo/desassociar_codigo/ErroCatalogo/ProdutoDuplicado` (Task 1); `tests/indices_factory.semana` (Task 2).
- Produces:
  - `app.routers.api.router` — `APIRouter(prefix="/api/v1")`; as Tasks 7 e 8 acrescentam `router.include_router(...)` em `app/routers/api/__init__.py`
  - `app.routers.api.erros.ErroApi(status: int, detail: str, **extra)` e `tratar_erro_api(request, exc) -> JSONResponse` com corpo `{"detail": …, **extra}`
  - `app.routers.api.schemas` — `ContratoResumo`, `Contrato`, `ContratoPatch`, `Produto`, `ProdutoNovo`, `ProdutoPatch`, `Codigo`, `CodigoAssociado`, `Associacao`; as Tasks 7 e 8 acrescentam schemas ao mesmo arquivo
  - `CODIGO_SERVICO = r"^\d{4,}$"` em `schemas.py`

- [ ] **Step 1: Escrever os testes de rota dos contratos**

`tests/test_api_contratos.py`:

```python
"""API de contratos: lista, detalhe e PATCH do cadastro."""

from datetime import date

from app.services import contratos_repo, indices_repo, medicoes_repo

from .indices_factory import semana

HEADER = {
    "Contrato": "15 00716/2022 - HWN ENGENHARIA LTDA",
    "Data Base": "01/01/2022",
    "Número do Processo": "50615.000404/2022-67",
}


def _contrato() -> int:
    contrato_id = contratos_repo.registrar_do_pdf(HEADER)
    medicoes_repo.gravar_itens(
        contrato_id,
        [{"Serviço": "8300980", "Descrição": "CAP 50/70", "Valor a PI Líquido": 10.0,
          "Fator": 0.1, "Período Líquido": "01/02/2023 - 28/02/2023",
          "Source_File": "1ª MP.pdf"}],
    )
    return contrato_id


async def test_lista_e_filtro_por_numero(client):
    contrato_id = _contrato()
    resposta = await client.get("/api/v1/contratos")
    assert resposta.status_code == 200
    (linha,) = resposta.json()
    assert linha["id"] == contrato_id
    assert linha["numero"] == "15 00716/2022"
    assert linha["data_base"] == "2022-01-01"
    assert linha["itens"] == 1 and linha["medicoes"] == 1
    assert linha["regioes"] == {}
    assert "regiao_cap" in linha["faltantes"]

    assert (await client.get("/api/v1/contratos", params={"numero": "716"})).json()
    assert (await client.get("/api/v1/contratos", params={"numero": "999"})).json() == []


async def test_detalhe_e_404(client):
    contrato_id = _contrato()
    corpo = (await client.get(f"/api/v1/contratos/{contrato_id}")).json()
    assert corpo["numero_processo"] == "50615.000404/2022-67"
    assert corpo["faltantes"]

    resposta = await client.get("/api/v1/contratos/999")
    assert resposta.status_code == 404
    assert resposta.json() == {"detail": "Contrato 999 não encontrado."}


async def test_patch_grava_cadastro_data_base_e_regioes(client):
    indices_repo.gravar_precos_anp(
        [semana(date(2023, 1, 9), "3.2", regiao=r) for r in ("Nordeste", "Sul")]
    )
    contrato_id = _contrato()
    resposta = await client.patch(
        f"/api/v1/contratos/{contrato_id}",
        json={
            "rodovia": "BR-316/MA",
            "extensao": "188,7",
            "data_base": "01/2021",
            "regioes": {"CAP": "nordeste", "EMULSOES": "Sul"},
        },
    )
    assert resposta.status_code == 200, resposta.text
    corpo = resposta.json()
    assert corpo["rodovia"] == "BR-316/MA"
    assert corpo["extensao"] == "188.7"
    assert corpo["data_base"] == "2021-01-01"
    assert corpo["regioes"] == {"CAP": "Nordeste", "EMULSOES": "Sul"}
    assert "regiao_cap" not in corpo["faltantes"]


async def test_patch_regiao_sem_precos_e_422(client):
    indices_repo.gravar_precos_anp([semana(date(2023, 1, 9), "3.2")])
    contrato_id = _contrato()
    resposta = await client.patch(
        f"/api/v1/contratos/{contrato_id}", json={"regioes": {"CAP": "Marte"}}
    )
    assert resposta.status_code == 422
    assert "Nordeste" in resposta.json()["detail"]


async def test_patch_campo_desconhecido_e_422(client):
    contrato_id = _contrato()
    resposta = await client.patch(f"/api/v1/contratos/{contrato_id}", json={"numero": "1"})
    assert resposta.status_code == 422


async def test_patch_contrato_inexistente_e_404(client):
    resposta = await client.patch("/api/v1/contratos/999", json={"rodovia": "x"})
    assert resposta.status_code == 404
```

- [ ] **Step 2: Escrever os testes de rota do catálogo**

`tests/test_api_catalogo.py`:

```python
"""API do catálogo: produtos do usuário e associação de códigos."""

from app.services import contratos_repo, medicoes_repo

HEADER = {"Contrato": "15 00716/2022 - HWN ENGENHARIA LTDA", "Data Base": "01/01/2022"}


def _extrair(codigo: str, descricao: str) -> int:
    contrato_id = contratos_repo.registrar_do_pdf(HEADER)
    medicoes_repo.gravar_itens(
        contrato_id,
        [{"Serviço": codigo, "Descrição": descricao, "Valor a PI Líquido": 10.0,
          "Fator": 0.1, "Período Líquido": "01/02/2023 - 28/02/2023",
          "Source_File": "1ª MP.pdf"}],
    )
    return contrato_id


async def _novo(client, descricao="AQUISIÇÃO DE CAP 50/70 (TESTE)", familia="CAP") -> dict:
    resposta = await client.post(
        "/api/v1/produtos", json={"descricao_export": descricao, "familia": familia}
    )
    assert resposta.status_code == 201, resposta.text
    return resposta.json()


async def test_criar_listar_editar_e_excluir_produto(client):
    produto = await _novo(client)
    assert produto["familia"] == "CAP" and produto["codigos"] == 0

    ids = [p["id"] for p in (await client.get("/api/v1/produtos")).json()]
    assert produto["id"] in ids

    resposta = await client.patch(
        f"/api/v1/produtos/{produto['id']}", json={"familia": "EMULSOES", "ordem": 3}
    )
    assert resposta.status_code == 200
    assert resposta.json()["familia"] == "EMULSOES" and resposta.json()["ordem"] == 3

    assert (await client.delete(f"/api/v1/produtos/{produto['id']}")).status_code == 204
    assert (await client.delete(f"/api/v1/produtos/{produto['id']}")).status_code == 404
    resposta = await client.patch(f"/api/v1/produtos/{produto['id']}", json={"ordem": 1})
    assert resposta.status_code == 404


async def test_produto_duplicado_e_409_e_familia_invalida_e_422(client):
    await _novo(client, "PRODUTO X")
    resposta = await client.post(
        "/api/v1/produtos", json={"descricao_export": "PRODUTO X", "familia": "CAP"}
    )
    assert resposta.status_code == 409
    assert "PRODUTO X" in resposta.json()["detail"]
    resposta = await client.post(
        "/api/v1/produtos", json={"descricao_export": "Y", "familia": "ASFALTO"}
    )
    assert resposta.status_code == 422
    resposta = await client.post(
        "/api/v1/produtos", json={"descricao_export": "  ", "familia": "CAP"}
    )
    assert resposta.status_code == 422


async def test_associar_filtrar_e_desassociar_codigo(client):
    _extrair("54393", "ESCAVAÇÃO, CARGA E TRANSPORTE")
    produto = await _novo(client)

    livres = (await client.get("/api/v1/codigos", params={"q": "escava"})).json()
    assert [c["codigo"] for c in livres] == ["54393"]
    assert livres[0]["produto_id"] is None and livres[0]["ocorrencias"] == 1

    resposta = await client.put("/api/v1/codigos/54393", json={"produto_id": produto["id"]})
    assert resposta.status_code == 200
    assert resposta.json()["descricao_export"] == produto["descricao_export"]

    associados = (await client.get("/api/v1/codigos", params={"associado": "true", "q": "543"})).json()
    assert [c["codigo"] for c in associados] == ["54393"]

    assert (await client.delete("/api/v1/codigos/54393")).status_code == 204
    assert (await client.delete("/api/v1/codigos/54393")).status_code == 404


async def test_associar_codigo_ainda_nao_extraido(client):
    produto = await _novo(client)
    resposta = await client.put("/api/v1/codigos/777777", json={"produto_id": produto["id"]})
    assert resposta.status_code == 200
    assert resposta.json()["codigo_servico"] == "777777"


async def test_associar_a_produto_inexistente_e_codigo_invalido(client):
    resposta = await client.put("/api/v1/codigos/54393", json={"produto_id": 99999})
    assert resposta.status_code == 422
    assert "99999" in resposta.json()["detail"]
    resposta = await client.put("/api/v1/codigos/abc", json={"produto_id": 1})
    assert resposta.status_code == 422
```

- [ ] **Step 3: Rodar e ver falhar**

Run: `uv run pytest tests/test_api_contratos.py tests/test_api_catalogo.py -q`
Expected: FAIL — todas as rotas respondem `404` (`/api/v1` ainda não existe).

- [ ] **Step 4: Criar o pacote `app/routers/api/`**

`app/routers/api/erros.py`:

```python
"""Erros da API com campos além de ``detail``.

``HTTPException`` só carrega ``detail``; o cálculo precisa devolver também
``faltando`` e a importação, ``erros``. ``ErroApi`` leva esses campos e
``tratar_erro_api`` os põe no corpo, ao lado de ``detail``.
"""

from fastapi import Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse


class ErroApi(Exception):
    def __init__(self, status: int, detail: str, **extra) -> None:
        super().__init__(detail)
        self.status = status
        self.detail = detail
        self.extra = extra


async def tratar_erro_api(request: Request, exc: ErroApi) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status,
        content={"detail": exc.detail, **jsonable_encoder(exc.extra)},
    )
```

`app/routers/api/schemas.py`:

```python
"""Modelos de resposta e de entrada da API.

``Decimal`` sai como string no JSON (Pydantic 2): o usuário confere esses números
contra a planilha, e um float binário não é o valor que está no banco.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict

Familia = Literal["CAP", "EMULSOES"]

CODIGO_SERVICO = r"^\d{4,}$"


class ContratoResumo(BaseModel):
    id: int
    numero: str
    data_base: date | None
    contratada: str | None
    rodovia: str | None
    regioes: dict[str, str]
    itens: int
    medicoes: int
    primeiro_mes: date | None
    ultimo_mes: date | None
    faltantes: list[str]


class Contrato(BaseModel):
    id: int
    numero: str
    numero_processo: str | None
    data_base: date | None
    edital: str | None
    rodovia: str | None
    trecho: str | None
    subtrecho: str | None
    segmento: str | None
    extensao: Decimal | None
    contratada: str | None
    regioes: dict[str, str]
    faltantes: list[str]
    atualizado_em: datetime


class ContratoPatch(BaseModel):
    """Só os campos enviados são gravados (``exclude_unset``)."""

    model_config = ConfigDict(extra="forbid")

    edital: str | None = None
    rodovia: str | None = None
    trecho: str | None = None
    subtrecho: str | None = None
    segmento: str | None = None
    extensao: Decimal | str | None = None
    contratada: str | None = None
    data_base: str | None = None
    regioes: dict[str, str] | None = None


class Produto(BaseModel):
    id: int
    descricao_export: str
    familia: Familia
    ordem: int
    codigos: int


class ProdutoNovo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    descricao_export: str
    familia: Familia
    ordem: int = 0


class ProdutoPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    descricao_export: str | None = None
    familia: Familia | None = None
    ordem: int | None = None


class Codigo(BaseModel):
    codigo: str
    descricao_pdf: str | None
    contratos: int
    ocorrencias: int
    produto_id: int | None
    descricao_export: str | None
    familia: Familia | None


class CodigoAssociado(BaseModel):
    codigo_servico: str
    descricao_pdf: str | None
    produto_id: int
    descricao_export: str
    familia: Familia


class Associacao(BaseModel):
    model_config = ConfigDict(extra="forbid")

    produto_id: int
```

`app/routers/api/contratos.py`:

```python
"""Contratos: lista, detalhe e edição do cadastro (inclui Data Base e regiões)."""

import asyncio

from fastapi import APIRouter

from ...services import contratos_repo
from .erros import ErroApi
from .schemas import Contrato, ContratoPatch, ContratoResumo

router = APIRouter(prefix="/contratos", tags=["contratos"])


def _detalhe(contrato_id: int) -> dict:
    contrato = contratos_repo.buscar_por_id(contrato_id)
    if contrato is None:
        raise ErroApi(404, f"Contrato {contrato_id} não encontrado.")
    contrato["faltantes"] = contratos_repo.campos_faltantes(contrato)
    return contrato


@router.get("", response_model=list[ContratoResumo])
async def listar(numero: str | None = None):
    return await asyncio.to_thread(contratos_repo.listar, numero)


@router.get("/{contrato_id}", response_model=Contrato)
async def detalhar(contrato_id: int):
    return await asyncio.to_thread(_detalhe, contrato_id)


@router.patch("/{contrato_id}", response_model=Contrato)
async def atualizar(contrato_id: int, patch: ContratoPatch):
    dados = patch.model_dump(exclude_unset=True)
    regioes = dados.pop("regioes", None)
    try:
        existe = await asyncio.to_thread(
            contratos_repo.atualizar, contrato_id, dados, regioes
        )
    except contratos_repo.CadastroInvalido as e:
        raise ErroApi(422, str(e)) from e
    if not existe:
        raise ErroApi(404, f"Contrato {contrato_id} não encontrado.")
    return await asyncio.to_thread(_detalhe, contrato_id)
```

`app/routers/api/catalogo.py`:

```python
"""Catálogo: produtos do usuário e a associação código de serviço → produto."""

import asyncio
from typing import Annotated

from fastapi import APIRouter, Path, Query, Response

from ...services import catalogo
from .erros import ErroApi
from .schemas import (
    CODIGO_SERVICO,
    Associacao,
    Codigo,
    CodigoAssociado,
    Produto,
    ProdutoNovo,
    ProdutoPatch,
)

router = APIRouter(tags=["catálogo"])

CodigoServico = Annotated[
    str, Path(pattern=CODIGO_SERVICO, description="Código de serviço do PDF")
]


def _erro_catalogo(e: catalogo.ErroCatalogo) -> ErroApi:
    status = 409 if isinstance(e, catalogo.ProdutoDuplicado) else 422
    return ErroApi(status, str(e))


@router.get("/produtos", response_model=list[Produto])
async def listar_produtos():
    return await asyncio.to_thread(catalogo.listar_produtos)


@router.post("/produtos", response_model=Produto, status_code=201)
async def criar_produto(novo: ProdutoNovo):
    try:
        produto_id = await asyncio.to_thread(
            catalogo.novo_produto, novo.descricao_export, novo.familia, novo.ordem
        )
    except catalogo.ErroCatalogo as e:
        raise _erro_catalogo(e) from e
    return await asyncio.to_thread(catalogo.buscar_produto, produto_id)


@router.patch("/produtos/{produto_id}", response_model=Produto)
async def atualizar_produto(produto_id: int, patch: ProdutoPatch):
    try:
        produto = await asyncio.to_thread(
            lambda: catalogo.atualizar_produto(
                produto_id, **patch.model_dump(exclude_unset=True)
            )
        )
    except catalogo.ErroCatalogo as e:
        raise _erro_catalogo(e) from e
    if produto is None:
        raise ErroApi(404, f"Produto {produto_id} não encontrado.")
    return produto


@router.delete("/produtos/{produto_id}", status_code=204)
async def excluir_produto(produto_id: int):
    if not await asyncio.to_thread(catalogo.excluir_produto, produto_id):
        raise ErroApi(404, f"Produto {produto_id} não encontrado.")
    return Response(status_code=204)


@router.get("/codigos", response_model=list[Codigo])
async def listar_codigos(
    q: str | None = Query(None, description="Trecho do código ou da descrição"),
    associado: bool | None = None,
    limite: int = Query(500, ge=1, le=5000),
):
    return await asyncio.to_thread(catalogo.buscar_codigos, q, associado, limite)


@router.put("/codigos/{codigo}", response_model=CodigoAssociado)
async def associar_codigo(codigo: CodigoServico, associacao: Associacao):
    try:
        await asyncio.to_thread(catalogo.registrar_codigo, codigo, associacao.produto_id)
    except catalogo.ErroCatalogo as e:
        raise _erro_catalogo(e) from e
    return await asyncio.to_thread(catalogo.buscar_por_codigo, codigo)


@router.delete("/codigos/{codigo}", status_code=204)
async def desassociar_codigo(codigo: CodigoServico):
    if not await asyncio.to_thread(catalogo.desassociar_codigo, codigo):
        raise ErroApi(404, f"O código {codigo} não está associado a nenhum produto.")
    return Response(status_code=204)
```

`app/routers/api/__init__.py`:

```python
"""API REST em ``/api/v1``: o que o frontend novo, o curl e scripts consomem.

A documentação interativa (OpenAPI) fica em ``/docs``.
"""

from fastapi import APIRouter

from . import catalogo, contratos
from .erros import ErroApi, tratar_erro_api

router = APIRouter(prefix="/api/v1")
router.include_router(contratos.router)
router.include_router(catalogo.router)

__all__ = ["ErroApi", "router", "tratar_erro_api"]
```

- [ ] **Step 5: Registrar em `app/main.py`**

Junto aos outros imports de routers:

```python
from .routers import api
```

E logo depois de `app.include_router(reequilibrio.router)`:

```python
app.include_router(api.router)
app.add_exception_handler(api.ErroApi, api.tratar_erro_api)
```

- [ ] **Step 6: Rodar os testes de rota e a suíte**

Run: `uv run pytest tests/test_api_contratos.py tests/test_api_catalogo.py -q && uv run pytest -q`
Expected: PASS.

- [ ] **Step 7: Conferir a documentação interativa**

Run: `uv run python -c "from app.main import app; import json; print(sorted(p for p in app.openapi()['paths'] if p.startswith('/api/v1')))"`
Expected: `['/api/v1/codigos', '/api/v1/codigos/{codigo}', '/api/v1/contratos', '/api/v1/contratos/{contrato_id}', '/api/v1/produtos', '/api/v1/produtos/{produto_id}']`

- [ ] **Step 8: Commit**

```bash
git add app/routers/api app/main.py tests/test_api_contratos.py tests/test_api_catalogo.py
git commit -m "$(cat <<'EOF'
feat: API /api/v1 de contratos e catálogo

Contratos podem ser listados, consultados e editados (cadastro, Data
Base e regiões por família); o catálogo expõe produtos do usuário e a
associação de códigos de serviço, com busca livre por código ou
descrição.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 7: API `/api/v1/indices` — edição, importação e exportação

**Files:**
- Create: `app/routers/api/indices.py`
- Modify: `app/routers/api/__init__.py`, `app/routers/api/schemas.py`
- Test: `tests/test_api_indices.py`

**Interfaces:**
- Consumes: `indices_repo.cobertura/listar_precos_anp/gravar_semana_manual/excluir_preco_anp/listar_indices_mensais/gravar_indice_manual/excluir_indice_mensal/IndiceInvalido` (Task 2); `importacao.importar_anp/importar_igp_di` e `importadores.ArquivoInvalido/ler_igp_di/gerar_template_igp_di` (Task 3); `exportadores.precos_csv/precos_xlsx/indices_csv/indices_xlsx` (Task 4); `ErroApi` (Task 6).
- Produces:
  - `indices.LIMITE_UPLOAD = 20 * 1024 * 1024`
  - `indices.MES = r"^\d{4}-(0[1-9]|1[0-2])$"`
  - `indices.ler_upload(arquivo: UploadFile) -> bytes` — `413` acima do limite, `422` vazio
  - `schemas.SemanaAnp`, `SemanaAnpEntrada`, `IndiceMensal`, `IndiceEntrada`, `Cobertura`, `ResultadoImportacao`
  - Nomes de download: `precos_anp.csv`, `precos_anp.xlsx`, `igp_di.csv`, `igp_di.xlsx`, `igp_di_template.xlsx`

- [ ] **Step 1: Escrever os testes de rota**

`tests/test_api_indices.py`:

```python
"""API de índices: edição manual, importação com prévia e exportação."""

import csv
import io
from datetime import date
from decimal import Decimal
from pathlib import Path

import openpyxl
import pytest

from app.routers.api import indices as rotas_indices
from app.services import importadores
from app.services.delta_p import ANP_PRODUTO_CAP

ANP_OFICIAL = Path("tests/fixtures/anp_semanal.xls")
SEMANA = {
    "vigencia_inicio": "2023-01-09",
    "vigencia_fim": "2023-01-15",
    "regiao": "Nordeste",
    "preco": "3.28568",
}


def _igp(*meses) -> bytes:
    return importadores.gerar_template_igp_di(
        [{"mes_ref": m, "valor": Decimal(v)} for m, v in meses]
    )


async def test_cobertura_vazia(client):
    corpo = (await client.get("/api/v1/indices/cobertura")).json()
    assert corpo["anp"]["registros"] == 0 and corpo["igp_di"]["registros"] == 0
    assert corpo["regioes"] == []


async def test_semana_manual_listar_e_excluir(client):
    resposta = await client.put("/api/v1/indices/anp", json=SEMANA)
    assert resposta.status_code == 200, resposta.text
    semana = resposta.json()
    assert semana["produto"] == ANP_PRODUTO_CAP
    assert semana["preco"] == "3.28568" and semana["origem"] == "manual"

    lista = (await client.get("/api/v1/indices/anp", params={"regiao": "nordeste"})).json()
    assert [s["id"] for s in lista] == [semana["id"]]
    fora = await client.get("/api/v1/indices/anp", params={"de": "2023-02-01"})
    assert fora.json() == []

    assert (await client.delete(f"/api/v1/indices/anp/{semana['id']}")).status_code == 204
    assert (await client.delete(f"/api/v1/indices/anp/{semana['id']}")).status_code == 404


async def test_semana_sem_cotacao_e_aceita(client):
    resposta = await client.put("/api/v1/indices/anp", json={**SEMANA, "preco": None})
    assert resposta.status_code == 200
    assert resposta.json()["preco"] is None


async def test_semana_sobreposta_e_422(client):
    await client.put("/api/v1/indices/anp", json=SEMANA)
    resposta = await client.put(
        "/api/v1/indices/anp",
        json={**SEMANA, "vigencia_inicio": "2023-01-12", "vigencia_fim": "2023-01-18"},
    )
    assert resposta.status_code == 422
    assert "sobrepõe" in resposta.json()["detail"]


async def test_igp_manual_listar_e_excluir(client):
    resposta = await client.put("/api/v1/indices/igp-di/2023-02", json={"valor": "1144.271"})
    assert resposta.status_code == 200, resposta.text
    assert resposta.json()["mes"] == "2023-02"
    assert resposta.json()["valor"] == "1144.271"

    lista = (await client.get("/api/v1/indices/igp-di", params={"de": "2023-01"})).json()
    assert [m["mes"] for m in lista] == ["2023-02"]

    assert (await client.delete("/api/v1/indices/igp-di/2023-02")).status_code == 204
    assert (await client.delete("/api/v1/indices/igp-di/2023-02")).status_code == 404


@pytest.mark.parametrize(
    "mes,valor", [("2023-13", "1"), ("23-01", "1"), ("2023-01", "0")]
)
async def test_igp_manual_invalido_e_422(client, mes, valor):
    resposta = await client.put(f"/api/v1/indices/igp-di/{mes}", json={"valor": valor})
    assert resposta.status_code == 422


async def test_importar_igp_previa_preserva_e_sobrescreve_manual(client):
    await client.put("/api/v1/indices/igp-di/2023-01", json={"valor": "1000"})
    arquivo = {"arquivo": ("igp.xlsx", _igp((date(2023, 1, 1), "1100"), (date(2023, 2, 1), "1144.271")))}
    url = "/api/v1/indices/igp-di/importar"

    previa = (await client.post(url, params={"simular": "true"}, files=arquivo)).json()
    assert previa["simulacao"] is True
    assert previa["inseridos"] == 1
    assert previa["conflitos_manuais"][0]["chave"] == {"mes": "2023-01"}
    assert previa["conflitos_manuais"][0]["valor_banco"] == "1000"
    assert len((await client.get("/api/v1/indices/igp-di")).json()) == 1

    gravado = (await client.post(url, files=arquivo)).json()
    assert gravado["manuais_preservados"] == 1
    meses = {m["mes"]: m for m in (await client.get("/api/v1/indices/igp-di")).json()}
    assert meses["2023-01"]["valor"] == "1000"
    assert meses["2023-02"]["origem"] == "upload:igp.xlsx"

    vencedor = (await client.post(url, params={"sobrescrever_manuais": "true"}, files=arquivo)).json()
    assert vencedor["atualizados"] == [
        {"chave": {"mes": "2023-01"}, "antes": "1000", "depois": "1100"}
    ]
    meses = {m["mes"]: m for m in (await client.get("/api/v1/indices/igp-di")).json()}
    assert meses["2023-01"]["valor"] == "1100"
    assert meses["2023-01"]["origem"] == "upload:igp.xlsx"


async def test_importar_arquivo_invalido_lista_os_erros(client):
    resposta = await client.post(
        "/api/v1/indices/anp/importar", files={"arquivo": ("x.xls", b"nao e planilha")}
    )
    assert resposta.status_code == 422
    corpo = resposta.json()
    assert "ANP" in corpo["detail"] and "erros" in corpo


async def test_upload_vazio_e_acima_do_limite(client, monkeypatch):
    url = "/api/v1/indices/igp-di/importar"
    vazio = await client.post(url, files={"arquivo": ("igp.xlsx", b"")})
    assert vazio.status_code == 422
    monkeypatch.setattr(rotas_indices, "LIMITE_UPLOAD", 10)
    grande = await client.post(url, files={"arquivo": ("igp.xlsx", b"x" * 11)})
    assert grande.status_code == 413
    assert "limite" in grande.json()["detail"]


async def test_importar_anp_oficial_em_previa_nao_grava(client):
    resposta = await client.post(
        "/api/v1/indices/anp/importar",
        params={"simular": "true"},
        files={"arquivo": ("anp.xls", ANP_OFICIAL.read_bytes())},
    )
    assert resposta.status_code == 200, resposta.text
    corpo = resposta.json()
    assert corpo["inseridos"] == 60114
    assert len(corpo["avisos"]) == 1 and "GLP" in corpo["avisos"][0]
    assert (await client.get("/api/v1/indices/cobertura")).json()["anp"]["registros"] == 0


async def test_exportar_anp_csv_e_xlsx(client):
    await client.put("/api/v1/indices/anp", json=SEMANA)

    resposta = await client.get("/api/v1/indices/anp/exportar", params={"formato": "csv"})
    assert resposta.status_code == 200
    assert "precos_anp.csv" in resposta.headers["content-disposition"]
    (linha,) = list(csv.DictReader(io.StringIO(resposta.text)))
    assert linha["vigencia_inicio"] == "2023-01-09" and linha["preco"] == "3.28568"

    resposta = await client.get("/api/v1/indices/anp/exportar")
    assert "precos_anp.xlsx" in resposta.headers["content-disposition"]
    assert "Preços ANP" in openpyxl.load_workbook(io.BytesIO(resposta.content)).sheetnames


async def test_template_e_exportacao_do_igp_sao_reimportaveis(client):
    vazio = await client.get("/api/v1/indices/igp-di/template")
    assert "igp_di_template.xlsx" in vazio.headers["content-disposition"]
    with pytest.raises(importadores.ArquivoInvalido):
        importadores.ler_igp_di(vazio.content)  # só o cabeçalho

    await client.put("/api/v1/indices/igp-di/2023-02", json={"valor": "1144.271"})
    for rota in ("/api/v1/indices/igp-di/template", "/api/v1/indices/igp-di/exportar"):
        leitura = importadores.ler_igp_di((await client.get(rota)).content)
        assert [(r["mes_ref"], r["valor"]) for r in leitura.registros] == [
            (date(2023, 2, 1), Decimal("1144.271"))
        ]

    resposta = await client.get("/api/v1/indices/igp-di/exportar", params={"formato": "csv"})
    assert "igp_di.csv" in resposta.headers["content-disposition"]
    assert resposta.text.splitlines()[0] == "mes,valor,origem,atualizado_em"
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `uv run pytest tests/test_api_indices.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.routers.api.indices'`.

- [ ] **Step 3: Acrescentar os schemas em `app/routers/api/schemas.py`**

Ao fim do arquivo:

```python
class SemanaAnp(BaseModel):
    id: int
    produto: str
    regiao: str
    vigencia_inicio: date
    vigencia_fim: date
    preco: Decimal | None
    origem: str
    atualizado_em: datetime


class SemanaAnpEntrada(BaseModel):
    """Uma semana digitada; ``preco`` nulo = semana sem cotação."""

    model_config = ConfigDict(extra="forbid")

    produto: str | None = None
    vigencia_inicio: date
    vigencia_fim: date
    regiao: str
    preco: Decimal | None


class IndiceMensal(BaseModel):
    mes: str
    valor: Decimal
    origem: str
    atualizado_em: datetime


class IndiceEntrada(BaseModel):
    model_config = ConfigDict(extra="forbid")

    valor: Decimal


class PeriodoCoberto(BaseModel):
    de: date | None
    ate: date | None
    registros: int


class Cobertura(BaseModel):
    anp: PeriodoCoberto
    igp_di: PeriodoCoberto
    regioes: list[str]


class Periodo(BaseModel):
    de: date | None
    ate: date | None


class Alteracao(BaseModel):
    chave: dict[str, str]
    antes: Decimal | None
    depois: Decimal | None


class ConflitoManual(BaseModel):
    chave: dict[str, str]
    valor_banco: Decimal | None
    valor_arquivo: Decimal | None
    atualizado_em: datetime


class ResultadoImportacao(BaseModel):
    arquivo: str
    simulacao: bool
    periodo: Periodo
    inseridos: int
    atualizados: list[Alteracao]
    inalterados: int
    conflitos_manuais: list[ConflitoManual]
    manuais_preservados: int
    avisos: list[str]
```

- [ ] **Step 4: Criar `app/routers/api/indices.py`**

```python
"""Índices globais: preços semanais da ANP e IGP-DI mensal.

Não dependem de contrato. Qualquer usuário grava ou corrige um valor
(``origem = 'manual'``) ou importa um arquivo inteiro, com prévia
(``simular``) e preservação das correções manuais (``sobrescrever_manuais``).
"""

import asyncio
from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Path, Query, Response, UploadFile

from ...services import exportadores, importacao, indices_repo
from ...services.delta_p import ANP_PRODUTO_CAP
from ...services.importadores import ArquivoInvalido
from .erros import ErroApi
from .schemas import (
    Cobertura,
    IndiceEntrada,
    IndiceMensal,
    ResultadoImportacao,
    SemanaAnp,
    SemanaAnpEntrada,
)

router = APIRouter(prefix="/indices", tags=["índices"])

LIMITE_UPLOAD = 20 * 1024 * 1024
MES = r"^\d{4}-(0[1-9]|1[0-2])$"
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

Mes = Annotated[str, Path(pattern=MES, description="Mês no formato AAAA-MM")]
MesFiltro = Annotated[str | None, Query(pattern=MES, description="AAAA-MM")]
Formato = Literal["xlsx", "csv"]


def _mes(texto: str) -> date:
    return date(int(texto[:4]), int(texto[5:7]), 1)


def _indice(linha: dict) -> dict:
    return {
        "mes": f"{linha['mes_ref']:%Y-%m}",
        "valor": linha["valor"],
        "origem": linha["origem"],
        "atualizado_em": linha["atualizado_em"],
    }


def _download(conteudo: bytes, nome: str, formato: Formato) -> Response:
    return Response(
        content=conteudo,
        media_type=XLSX if formato == "xlsx" else "text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{nome}"'},
    )


async def ler_upload(arquivo: UploadFile) -> bytes:
    """O conteúdo do upload, recusando vazio ou acima de ``LIMITE_UPLOAD``.

    Lê no máximo um byte além do limite: basta para saber que passou, sem
    carregar um arquivo gigante na memória.
    """
    conteudo = await arquivo.read(LIMITE_UPLOAD + 1)
    if len(conteudo) > LIMITE_UPLOAD:
        raise ErroApi(413, f"O arquivo passa do limite de {LIMITE_UPLOAD // (1024 * 1024)} MB.")
    if not conteudo:
        raise ErroApi(422, "O arquivo enviado está vazio.")
    return conteudo


async def _importar(funcao, arquivo: UploadFile, simular: bool, sobrescrever_manuais: bool):
    conteudo = await ler_upload(arquivo)
    nome = arquivo.filename or "arquivo"
    try:
        return await asyncio.to_thread(
            lambda: funcao(
                conteudo, nome, simular=simular, sobrescrever_manuais=sobrescrever_manuais
            )
        )
    except ArquivoInvalido as e:
        raise ErroApi(422, e.mensagem, erros=e.erros) from e
    except indices_repo.IndiceInvalido as e:
        raise ErroApi(422, str(e)) from e


@router.get("/cobertura", response_model=Cobertura)
async def cobertura():
    return await asyncio.to_thread(indices_repo.cobertura)


# ── ANP ─────────────────────────────────────────────────────────────────────


@router.get("/anp", response_model=list[SemanaAnp])
async def listar_anp(
    produto: str = ANP_PRODUTO_CAP,
    regiao: str | None = None,
    de: date | None = None,
    ate: date | None = None,
    limite: int = Query(500, ge=1, le=100000),
):
    return await asyncio.to_thread(
        lambda: indices_repo.listar_precos_anp(produto, regiao, limite, de=de, ate=ate)
    )


@router.put("/anp", response_model=SemanaAnp)
async def gravar_semana(semana: SemanaAnpEntrada):
    try:
        return await asyncio.to_thread(indices_repo.gravar_semana_manual, semana.model_dump())
    except indices_repo.IndiceInvalido as e:
        raise ErroApi(422, str(e)) from e


@router.delete("/anp/{preco_id}", status_code=204)
async def excluir_semana(preco_id: int):
    if not await asyncio.to_thread(indices_repo.excluir_preco_anp, preco_id):
        raise ErroApi(404, f"Semana {preco_id} não encontrada.")
    return Response(status_code=204)


@router.post("/anp/importar", response_model=ResultadoImportacao)
async def importar_anp(
    arquivo: UploadFile, simular: bool = False, sobrescrever_manuais: bool = False
):
    return await _importar(importacao.importar_anp, arquivo, simular, sobrescrever_manuais)


@router.get("/anp/exportar")
async def exportar_anp(
    produto: str = ANP_PRODUTO_CAP,
    regiao: str | None = None,
    de: date | None = None,
    ate: date | None = None,
    formato: Formato = "xlsx",
):
    linhas = await asyncio.to_thread(
        lambda: indices_repo.listar_precos_anp(produto, regiao, None, de=de, ate=ate)
    )
    gerar = exportadores.precos_xlsx if formato == "xlsx" else exportadores.precos_csv
    return _download(gerar(linhas), f"precos_anp.{formato}", formato)


# ── IGP-DI ──────────────────────────────────────────────────────────────────


@router.get("/igp-di", response_model=list[IndiceMensal])
async def listar_igp_di(de: MesFiltro = None, ate: MesFiltro = None):
    linhas = await asyncio.to_thread(
        lambda: indices_repo.listar_indices_mensais(
            limite=None,
            de=_mes(de) if de else None,
            ate=_mes(ate) if ate else None,
        )
    )
    return [_indice(l) for l in linhas]


@router.put("/igp-di/{mes}", response_model=IndiceMensal)
async def gravar_igp_di(mes: Mes, entrada: IndiceEntrada):
    try:
        linha = await asyncio.to_thread(indices_repo.gravar_indice_manual, _mes(mes), entrada.valor)
    except indices_repo.IndiceInvalido as e:
        raise ErroApi(422, str(e)) from e
    return _indice(linha)


@router.delete("/igp-di/{mes}", status_code=204)
async def excluir_igp_di(mes: Mes):
    if not await asyncio.to_thread(indices_repo.excluir_indice_mensal, _mes(mes)):
        raise ErroApi(404, f"Não há IGP-DI cadastrado para {mes}.")
    return Response(status_code=204)


async def _todos_os_meses() -> list[dict]:
    return await asyncio.to_thread(lambda: indices_repo.listar_indices_mensais(limite=None))


@router.get("/igp-di/template")
async def template_igp_di():
    """O template de importação, já preenchido com o que está no banco."""
    conteudo = exportadores.indices_xlsx(await _todos_os_meses())
    return _download(conteudo, "igp_di_template.xlsx", "xlsx")


@router.post("/igp-di/importar", response_model=ResultadoImportacao)
async def importar_igp_di(
    arquivo: UploadFile, simular: bool = False, sobrescrever_manuais: bool = False
):
    return await _importar(importacao.importar_igp_di, arquivo, simular, sobrescrever_manuais)


@router.get("/igp-di/exportar")
async def exportar_igp_di(formato: Formato = "xlsx"):
    linhas = await _todos_os_meses()
    gerar = exportadores.indices_xlsx if formato == "xlsx" else exportadores.indices_csv
    return _download(gerar(linhas), f"igp_di.{formato}", formato)
```

O `gravar_semana_manual` levanta `SemanaSobreposta` (subclasse de `IndiceInvalido`), então o `except` único cobre sobreposição, região desconhecida e preço negativo.

- [ ] **Step 5: Registrar o router**

Em `app/routers/api/__init__.py`, troque `from . import catalogo, contratos` por
`from . import catalogo, contratos, indices` e acrescente
`router.include_router(indices.router)` depois de `router.include_router(catalogo.router)`.

- [ ] **Step 6: Rodar os testes**

Run: `uv run pytest tests/test_api_indices.py -q && uv run pytest -q`
Expected: PASS. `test_importar_anp_oficial_em_previa_nao_grava` leva alguns segundos (lê o arquivo oficial inteiro).

- [ ] **Step 7: Commit**

```bash
git add app/routers/api tests/test_api_indices.py
git commit -m "$(cat <<'EOF'
feat: API de índices com edição, importação e exportação

Preços ANP e IGP-DI podem ser consultados, corrigidos um a um, importados
com prévia e preservação das correções manuais, e exportados em CSV ou
XLSX. O template do IGP-DI sai preenchido com o banco e é reimportável.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 8: API do cálculo e da planilha, com simulação de região

**Files:**
- Create: `app/routers/api/calculo.py`
- Modify: `app/routers/api/__init__.py`, `app/routers/api/schemas.py`
- Test: `tests/test_api_calculo.py`

**Interfaces:**
- Consumes: `reequilibrio_export.calcular/gerar/serializar/ExportacaoImpossivel` (Task 5); `contratos_repo.buscar_por_id/atualizar` (Task 5); `template_repo.conteudo_ativo/garantir_semente`; `xlsx_drawings.TemplateInvalido`; `ErroApi` (Task 6).
- Produces:
  - `GET /api/v1/contratos/{id}/calculo?regiao_cap=&regiao_emulsoes=` → `CalculoResposta`
  - `GET /api/v1/contratos/{id}/planilha?regiao_cap=&regiao_emulsoes=` → `.xlsx`, `X-Avisos`
  - `calculo.nome_do_arquivo(numero: str, simuladas: dict[str, str]) -> str` — `Reequilibrio_15-00716-2022.xlsx`, `Reequilibrio_15-00716-2022_SIMULACAO_CAP-Sul.xlsx`
  - `calculo.cabecalho_avisos(avisos: list[str]) -> str` — latin-1 garantido
  - `schemas.CalculoResposta` (e `LinhaCalculo`, `ProdutoCalculo`, `FamiliaCalculo`, `ParametrosCalculo`, `ContratoRef`)

- [ ] **Step 1: Escrever os testes de rota**

`tests/test_api_calculo.py`:

```python
"""API do cálculo: JSON e planilha saem da mesma função, com simulação de região."""

import io
from datetime import date
from decimal import Decimal

import openpyxl
import pytest

from app.routers.api.calculo import cabecalho_avisos, nome_do_arquivo
from app.services import contratos_repo, indices_repo, medicoes_repo, template_repo, xlsx_drawings
from app.services.reequilibrio_layout import ABA

from .indices_factory import mes_igp, semana

HEADER = {
    "Contrato": "15 00716/2022 - HWN ENGENHARIA LTDA",
    "Data Base": "01/01/2022",
    "Número do Processo": "50615.000404/2022-67",
}
BASE = {"Nordeste": "4.02073", "Sul": "4.29019"}
JANEIRO = {"Nordeste": "3.28568", "Sul": "3.45"}


def _contrato(*, com_indices=True) -> int:
    contrato_id = contratos_repo.registrar_do_pdf(HEADER)
    medicoes_repo.gravar_itens(
        contrato_id,
        [{"Serviço": "8300980", "Descrição": "AQUISIÇÃO DE CAP 50/70",
          "Valor a PI Líquido": 208133.17, "Fator": -0.1839,
          "Período Líquido": "01/02/2023 - 28/02/2023", "Source_File": "1ª MP.pdf"}],
    )
    indices_repo.gravar_precos_anp(
        [semana(date(2023, 1, 9), JANEIRO["Nordeste"])]
    )
    contratos_repo.atualizar(contrato_id, {}, {"CAP": "Nordeste", "EMULSOES": "Nordeste"})
    if com_indices:
        for regiao in BASE:
            if regiao != "Nordeste":
                indices_repo.gravar_precos_anp([semana(date(2023, 1, 9), JANEIRO[regiao], regiao=regiao)])
            indices_repo.gravar_precos_anp([semana(date(2021, 12, 13), BASE[regiao], regiao=regiao)])
        indices_repo.gravar_indices_mensais(
            [mes_igp(date(2022, 1, 1), "1110.398"), mes_igp(date(2023, 2, 1), "1144.271")]
        )
    template_repo.garantir_semente()
    return contrato_id


def _delta(regiao: str) -> Decimal:
    return Decimal(JANEIRO[regiao]) / Decimal(BASE[regiao]) - 1


async def test_calculo_json(client):
    contrato_id = _contrato()
    resposta = await client.get(f"/api/v1/contratos/{contrato_id}/calculo")
    assert resposta.status_code == 200, resposta.text
    corpo = resposta.json()
    assert corpo["contrato"] == {"id": contrato_id, "numero": "15 00716/2022"}
    assert corpo["parametros"]["data_base"] == "2022-01-01"
    assert corpo["parametros"]["regioes"] == {"CAP": "Nordeste", "EMULSOES": "Nordeste"}
    assert corpo["parametros"]["simulacao"] is False
    assert corpo["parametros"]["lucro"] == "0.0511"

    (familia,) = corpo["familias"]
    assert familia["familia"] == "CAP" and familia["rotulo"] == "Aquisição de CAP"
    (linha,) = familia["produtos"][0]["linhas"]
    assert linha["mes"] == "2023-02-01"
    assert linha["a"] == "208133.17" and linha["b"] == "-38275.68"
    assert abs(Decimal(linha["d"]) - _delta("Nordeste")) < Decimal("1e-20")
    assert Decimal(corpo["total"]) == Decimal(linha["f"])


async def test_simulacao_nao_altera_o_cadastro(client):
    contrato_id = _contrato()
    corpo = (
        await client.get(f"/api/v1/contratos/{contrato_id}/calculo", params={"regiao_cap": "sul"})
    ).json()
    assert corpo["parametros"]["simulacao"] is True
    assert corpo["parametros"]["regioes"]["CAP"] == "Sul"
    linha = corpo["familias"][0]["produtos"][0]["linhas"][0]
    assert abs(Decimal(linha["d"]) - _delta("Sul")) < Decimal("1e-20")
    assert "Simulação: CAP calculado com a região Sul (cadastro: Nordeste)." in corpo["avisos"]

    cadastro = (await client.get(f"/api/v1/contratos/{contrato_id}")).json()
    assert cadastro["regioes"]["CAP"] == "Nordeste"


async def test_planilha_tem_formulas_vivas_e_a_equacao(client):
    contrato_id = _contrato()
    resposta = await client.get(f"/api/v1/contratos/{contrato_id}/planilha")
    assert resposta.status_code == 200, resposta.text
    assert 'filename="Reequilibrio_15-00716-2022.xlsx"' in resposta.headers["content-disposition"]

    ws = openpyxl.load_workbook(io.BytesIO(resposta.content))[ABA]
    linhas = [
        r for r in range(1, ws.max_row + 1)
        if str(ws.cell(r, 6).value or "").startswith("=TRUNC(")
    ]
    assert linhas
    r = linhas[0]
    assert ws.cell(r, 8).value == f"=D{r}*G{r}"
    assert ws.cell(r, 9).value == f"=H{r}-F{r}"
    assert ws.cell(r, 10).value == f"=I{r}*(1-0.0511)"
    assert isinstance(ws.cell(r, 7).value, float)
    assert xlsx_drawings.contem_equacao(resposta.content, ABA)


async def test_planilha_simulada_no_nome_e_nos_avisos(client):
    contrato_id = _contrato()
    resposta = await client.get(
        f"/api/v1/contratos/{contrato_id}/planilha", params={"regiao_cap": "Sul"}
    )
    assert resposta.status_code == 200
    assert "Reequilibrio_15-00716-2022_SIMULACAO_CAP-Sul.xlsx" in resposta.headers["content-disposition"]
    avisos = dict(resposta.headers.raw)[b"x-avisos"].decode("latin-1")
    assert "Simulação: CAP calculado com a região Sul (cadastro: Nordeste)." in avisos


async def test_contrato_inexistente_e_404(client):
    for rota in ("calculo", "planilha"):
        resposta = await client.get(f"/api/v1/contratos/999/{rota}")
        assert resposta.status_code == 404


async def test_indices_ausentes_sao_422_com_faltando(client):
    contrato_id = _contrato(com_indices=False)
    for rota in ("calculo", "planilha"):
        resposta = await client.get(f"/api/v1/contratos/{contrato_id}/{rota}")
        assert resposta.status_code == 422
        corpo = resposta.json()
        assert corpo["faltando"]
        assert all(f in corpo["detail"] for f in corpo["faltando"])


async def test_regiao_sem_precos_na_simulacao_e_422(client):
    contrato_id = _contrato()
    resposta = await client.get(
        f"/api/v1/contratos/{contrato_id}/calculo", params={"regiao_emulsoes": "Centro-Oeste"}
    )
    assert resposta.status_code == 422
    assert resposta.json()["faltando"] == ["regiao_emulsoes"]


@pytest.mark.parametrize(
    "simuladas,esperado",
    [
        ({}, "Reequilibrio_15-00716-2022.xlsx"),
        ({"CAP": "Sul"}, "Reequilibrio_15-00716-2022_SIMULACAO_CAP-Sul.xlsx"),
        (
            {"CAP": "Sul", "EMULSOES": "Centro-Oeste"},
            "Reequilibrio_15-00716-2022_SIMULACAO_CAP-Sul_EMULSOES-Centro-Oeste.xlsx",
        ),
    ],
)
def test_nome_do_arquivo(simuladas, esperado):
    assert nome_do_arquivo("15 00716/2022", simuladas) == esperado


def test_cabecalho_avisos_e_latin1():
    texto = cabecalho_avisos(["Região Sul", "ΔP – sem índice…"])
    texto.encode("latin-1")
    assert texto.startswith("Região Sul | ")
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `uv run pytest tests/test_api_calculo.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.routers.api.calculo'`.

- [ ] **Step 3: Acrescentar os schemas em `app/routers/api/schemas.py`**

Ao fim do arquivo:

```python
class LinhaCalculo(BaseModel):
    """Uma linha da planilha, com as letras da linha 16 do template."""

    mes: date
    a: Decimal
    fator: Decimal
    b: Decimal
    d: Decimal
    c: Decimal
    e: Decimal
    f: Decimal


class ProdutoCalculo(BaseModel):
    descricao: str
    subtotal: Decimal
    linhas: list[LinhaCalculo]


class FamiliaCalculo(BaseModel):
    familia: Familia
    rotulo: str
    subtotal: Decimal
    produtos: list[ProdutoCalculo]


class ParametrosCalculo(BaseModel):
    data_base: date
    regioes: dict[str, str]
    simulacao: bool
    lucro: Decimal


class ContratoRef(BaseModel):
    id: int
    numero: str


class CalculoResposta(BaseModel):
    contrato: ContratoRef
    parametros: ParametrosCalculo
    familias: list[FamiliaCalculo]
    total: Decimal
    avisos: list[str]
```

- [ ] **Step 4: Criar `app/routers/api/calculo.py`**

```python
"""Cálculo do reequilíbrio de um contrato, em JSON ou como planilha.

As duas rotas chamam ``reequilibrio_export.calcular`` — o mesmo cálculo — e só
diferem na saída. ``regiao_cap``/``regiao_emulsoes`` trocam a região de uma
família só nesta geração (simulação); o cadastro não muda.
"""

import asyncio
import re

from fastapi import APIRouter, Response

from ...services import contratos_repo, reequilibrio_export, template_repo
from ...services.delta_p import FAMILIA_CAP, FAMILIA_EMULSOES
from ...services.reequilibrio_export import Calculo, ExportacaoImpossivel
from ...services.xlsx_drawings import TemplateInvalido
from .erros import ErroApi
from .schemas import CalculoResposta

router = APIRouter(prefix="/contratos", tags=["cálculo"])

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _seguro(texto: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "-", texto).strip("-")


def nome_do_arquivo(numero: str, simuladas: dict[str, str]) -> str:
    """``Reequilibrio_<numero>[_SIMULACAO_<FAMILIA>-<Regiao>…].xlsx``.

    A simulação fica no nome porque o template não tem célula de região: é o
    que distingue, na pasta de downloads, a planilha simulada da oficial.
    """
    nome = f"Reequilibrio_{_seguro(numero)}"
    if simuladas:
        nome += "_SIMULACAO_" + "_".join(
            f"{familia}-{_seguro(regiao)}" for familia, regiao in simuladas.items()
        )
    return nome + ".xlsx"


def cabecalho_avisos(avisos: list[str]) -> str:
    """Os avisos num valor de cabeçalho HTTP, que só aceita latin-1.

    Os avisos são escritos sem Δ, travessão ou reticências; o ``replace`` é a
    rede de segurança para que um aviso novo não derrube a resposta inteira.
    """
    return " | ".join(avisos).encode("latin-1", errors="replace").decode("latin-1")


def _calcular(contrato_id: int, regiao_cap: str | None, regiao_emulsoes: str | None) -> Calculo:
    contrato = contratos_repo.buscar_por_id(contrato_id)
    if contrato is None:
        raise ErroApi(404, f"Contrato {contrato_id} não encontrado.")
    override = {FAMILIA_CAP: regiao_cap, FAMILIA_EMULSOES: regiao_emulsoes}
    try:
        return reequilibrio_export.calcular(contrato, override)
    except ExportacaoImpossivel as e:
        raise ErroApi(422, e.mensagem, faltando=e.faltando) from e


@router.get("/{contrato_id}/calculo", response_model=CalculoResposta)
async def calculo(
    contrato_id: int, regiao_cap: str | None = None, regiao_emulsoes: str | None = None
):
    resultado = await asyncio.to_thread(_calcular, contrato_id, regiao_cap, regiao_emulsoes)
    return reequilibrio_export.serializar(resultado)


@router.get("/{contrato_id}/planilha")
async def planilha(
    contrato_id: int, regiao_cap: str | None = None, regiao_emulsoes: str | None = None
):
    resultado = await asyncio.to_thread(_calcular, contrato_id, regiao_cap, regiao_emulsoes)
    try:
        template = await asyncio.to_thread(template_repo.conteudo_ativo)
        gerado = await asyncio.to_thread(reequilibrio_export.gerar, resultado, template)
    except TemplateInvalido as e:
        raise ErroApi(422, str(e)) from e
    nome = nome_do_arquivo(resultado.contrato["numero"], resultado.simuladas)
    return Response(
        content=gerado.conteudo,
        media_type=XLSX,
        headers={
            "Content-Disposition": f'attachment; filename="{nome}"',
            "X-Avisos": cabecalho_avisos(gerado.avisos),
        },
    )
```

- [ ] **Step 5: Registrar o router**

Em `app/routers/api/__init__.py`, troque `from . import catalogo, contratos, indices` por
`from . import calculo, catalogo, contratos, indices` e acrescente
`router.include_router(calculo.router)` depois de `router.include_router(indices.router)`.

- [ ] **Step 6: Rodar os testes**

Run: `uv run pytest tests/test_api_calculo.py -q && uv run pytest -q`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add app/routers/api tests/test_api_calculo.py
git commit -m "$(cat <<'EOF'
feat: API do cálculo e da planilha com simulação de região

O cálculo sai em JSON, com as colunas a–f da memória de cálculo, ou como
a planilha com fórmulas vivas. Trocar a região de uma família vale só
para aquela geração e fica marcado no nome do arquivo e nos avisos.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 9: Seed pelos importadores, sem a planilha de referência

**Files:**
- Rewrite: `scripts/seed_indices.py`
- Create: `tests/test_seed.py`

**Interfaces:**
- Consumes (Task 3): `importacao.importar_anp(conteudo, arquivo, *, origem=…) -> dict`, `importacao.importar_igp_di(...)`, `importacao.importar_precos(leitura, *, arquivo, origem=…)`, `importadores.ArquivoInvalido`, `importadores.ler_linhas_anp`, `importadores.gerar_template_igp_di`; (Task 2) `indices_repo.ORIGEM_SEED`, `indices_repo.IndiceInvalido`, `listar_precos_anp`, `listar_indices_mensais`.
- Produces: `scripts/seed_indices.py` com `ARQUIVO_ANP: Path`, `executar(anp: Path | None, igp_di: Path | None) -> int` (síncrono, pools já abertos; 0 = sucesso, 1 = erro) e `main(argv: list[str] | None = None) -> int`. Sai a opção `--todos-produtos`: o importador sempre grava todos os produtos do arquivo.

O seed atual lê o IGP-DI da planilha `Reequilíbrio - 26 - Contrato 716-22.xlsx`,
o que é proibido (Global Constraints). Ele passa a ser só uma casca de linha de
comando sobre `importacao`: o mesmo código da API, com `origem = 'seed'`, então um
valor corrigido à mão pelo usuário continua preservado quando o seed roda de novo.

- [ ] **Step 1: Escrever `tests/test_seed.py`**

```python
"""scripts/seed_indices.py: casca de linha de comando sobre a importação."""

import importlib.util
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from app.services import importacao, importadores, indices_repo
from app.services.delta_p import ANP_PRODUTO_CAP

from .indices_factory import linha_anp, linhas_anp

SCRIPT = Path("scripts/seed_indices.py")


def _seed():
    spec = importlib.util.spec_from_file_location("seed_indices", SCRIPT)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


@pytest.fixture()
def anp_pequeno(monkeypatch):
    """Troca a leitura do .xls oficial (60 mil registros) por uma semana só.

    O resto do caminho — plano, gravação e ``origem`` — é o real.
    """
    leitura = importadores.ler_linhas_anp(
        linhas_anp([linha_anp(ANP_PRODUTO_CAP, date(2023, 1, 9), [3.1, 3.28568, 3.2, 3.45, 3.3, 3.9])])
    )

    def importar_anp(conteudo, arquivo, **opcoes):
        return importacao.importar_precos(leitura, arquivo=arquivo, **opcoes)

    monkeypatch.setattr(importacao, "importar_anp", importar_anp)


def test_seed_grava_anp_e_igp_com_origem_seed(tmp_path, anp_pequeno):
    anp = tmp_path / "anp.xls"
    anp.write_bytes(b"conteudo irrelevante: a leitura foi trocada")
    igp = tmp_path / "igp.xlsx"
    igp.write_bytes(
        importadores.gerar_template_igp_di(
            [{"mes_ref": date(2022, 1, 1), "valor": Decimal("1110.398")}]
        )
    )

    assert _seed().executar(anp, igp) == 0

    precos = indices_repo.listar_precos_anp()
    assert len(precos) == 6
    assert {p["origem"] for p in precos} == {indices_repo.ORIGEM_SEED}
    (indice,) = indices_repo.listar_indices_mensais()
    assert indice["valor"] == Decimal("1110.398")
    assert indice["origem"] == indices_repo.ORIGEM_SEED


def test_seed_preserva_correcao_manual(tmp_path, anp_pequeno):
    indices_repo.gravar_indice_manual(date(2022, 1, 1), Decimal("1000"))
    igp = tmp_path / "igp.xlsx"
    igp.write_bytes(
        importadores.gerar_template_igp_di(
            [{"mes_ref": date(2022, 1, 1), "valor": Decimal("1110.398")}]
        )
    )

    assert _seed().executar(None, igp) == 0

    (indice,) = indices_repo.listar_indices_mensais()
    assert indice["valor"] == Decimal("1000")
    assert indice["origem"] == indices_repo.ORIGEM_MANUAL


def test_sem_igp_orienta_pelo_template(capsys, tmp_path, anp_pequeno):
    anp = tmp_path / "anp.xls"
    anp.write_bytes(b"x")
    assert _seed().executar(anp, None) == 0
    assert "/api/v1/indices/igp-di/template" in capsys.readouterr().out


def test_arquivo_inexistente_e_erro(capsys, tmp_path):
    assert _seed().executar(tmp_path / "nao-existe.xls", None) == 1
    assert "arquivo não encontrado" in capsys.readouterr().err
    assert indices_repo.listar_precos_anp() == []


def test_arquivo_invalido_e_erro_sem_gravar(capsys, tmp_path):
    igp = tmp_path / "igp.xlsx"
    igp.write_bytes(b"isto nao e um xlsx")
    assert _seed().executar(None, igp) == 1
    assert capsys.readouterr().err
    assert indices_repo.listar_indices_mensais() == []


def test_seed_nao_le_a_planilha_de_referencia():
    assert "Reequilíbrio" not in SCRIPT.read_text(encoding="utf-8")
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `uv run pytest tests/test_seed.py -q`
Expected: FAIL — `AttributeError: module 'seed_indices' has no attribute 'executar'` e a guarda
`test_seed_nao_le_a_planilha_de_referencia` falhando.

- [ ] **Step 3: Reescrever `scripts/seed_indices.py`**

```python
"""Carga inicial dos índices, pela mesma importação que a API usa.

Uso único, pela linha de comando; depois disso os usuários mantêm os índices
pela API (edição manual ou upload de arquivos).

    uv run python scripts/seed_indices.py                          # só a ANP
    uv run python scripts/seed_indices.py --igp-di igp_di.xlsx     # ANP e IGP-DI
    uv run python scripts/seed_indices.py --sem-anp --igp-di igp_di.xlsx

* ANP: o ``.xls`` padrão de preços semanais da ANP; por padrão
  ``data/precos-medios-ponderados-semanais-2013.xls``. Todos os produtos do
  arquivo são gravados; o cálculo consulta só o CAP 50/70. ``data/`` não é
  versionado: numa máquina nova, use ``--anp tests/fixtures/anp_semanal.xls``,
  a cópia versionada do arquivo oficial.
* IGP-DI: um arquivo no formato do template (``GET /api/v1/indices/igp-di/template``).

Os valores entram com ``origem = 'seed'``. Correções manuais já feitas pelos
usuários são preservadas: rodar o seed de novo não as desfaz.
"""

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import config, db  # noqa: E402
from app.services import importacao, indices_repo  # noqa: E402
from app.services.importadores import ArquivoInvalido  # noqa: E402

ARQUIVO_ANP = config.PROJECT_ROOT / "data" / "precos-medios-ponderados-semanais-2013.xls"


def _importar(rotulo: str, funcao, caminho: Path) -> None:
    resultado = funcao(caminho.read_bytes(), caminho.name, origem=indices_repo.ORIGEM_SEED)
    periodo = resultado["periodo"]
    print(
        f"[{rotulo}] {caminho.name}: {resultado['inseridos']} inseridos, "
        f"{len(resultado['atualizados'])} atualizados, {resultado['inalterados']} inalterados "
        f"({periodo['de']} a {periodo['ate']})"
    )
    if resultado["manuais_preservados"]:
        print(
            f"[{rotulo}] {resultado['manuais_preservados']} correção(ões) manual(is) "
            "preservada(s)"
        )
    for aviso in resultado["avisos"]:
        print(f"[{rotulo}] aviso: {aviso}")


def executar(anp: Path | None, igp_di: Path | None) -> int:
    """Importa os arquivos informados; 0 em sucesso, 1 no primeiro erro.

    Síncrono e sem abrir conexões: quem chama já abriu os pools e aplicou as
    migrações. Um arquivo recusado não grava nada (a importação é tudo ou nada).
    """
    etapas = []
    if anp is not None:
        etapas.append(("ANP", importacao.importar_anp, anp))
    if igp_di is not None:
        etapas.append(("IGP-DI", importacao.importar_igp_di, igp_di))

    for rotulo, funcao, caminho in etapas:
        if not caminho.exists():
            print(f"[{rotulo}] arquivo não encontrado: {caminho}", file=sys.stderr)
            return 1
        try:
            _importar(rotulo, funcao, caminho)
        except ArquivoInvalido as e:
            print(f"[{rotulo}] {caminho.name}: {e.mensagem}", file=sys.stderr)
            for erro in e.erros:
                print(f"  - {erro}", file=sys.stderr)
            return 1
        except indices_repo.IndiceInvalido as e:
            print(f"[{rotulo}] {caminho.name}: {e}", file=sys.stderr)
            return 1

    if igp_di is None:
        print(
            "[IGP-DI] nenhum arquivo informado. Baixe o template em "
            "GET /api/v1/indices/igp-di/template, preencha-o e rode de novo com "
            "--igp-di <arquivo>, ou importe-o pela API."
        )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Carga inicial dos índices (ANP e IGP-DI) pela importação da aplicação."
    )
    parser.add_argument(
        "--anp", type=Path, default=ARQUIVO_ANP,
        help=f".xls de preços semanais da ANP (padrão: {ARQUIVO_ANP})",
    )
    parser.add_argument("--sem-anp", action="store_true", help="não importa a ANP")
    parser.add_argument(
        "--igp-di", type=Path, default=None,
        help="arquivo no formato do template de IGP-DI",
    )
    args = parser.parse_args(argv)

    async def rodar() -> int:
        await db.open_pools()
        try:
            await db.apply_migrations()
            return await asyncio.to_thread(
                executar, None if args.sem_anp else args.anp, args.igp_di
            )
        finally:
            await db.close_pools()

    return asyncio.run(rodar())


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Rodar os testes**

Run: `uv run pytest tests/test_seed.py -q && uv run pytest -q`
Expected: PASS.

- [ ] **Step 5: Conferir o script contra o banco de desenvolvimento**

Run: `uv run python scripts/seed_indices.py --help && uv run python scripts/seed_indices.py`
Expected: a ajuda sem `--todos-produtos`; depois uma linha `[ANP] precos-medios-ponderados-semanais-2013.xls: … inseridos, … atualizados, … inalterados (2013-… a 2026-…)`,
o aviso do GLP e a orientação sobre o template de IGP-DI. Numa segunda execução, tudo aparece como `inalterados`.

- [ ] **Step 6: Commit**

```bash
git add scripts/seed_indices.py tests/test_seed.py
git commit -m "$(cat <<'EOF'
refactor: seed dos índices pela importação da aplicação

O seed passa a usar os mesmos importadores da API, com origem 'seed',
e deixa de ler a planilha de referência do contrato 716-22. O IGP-DI
entra só por um arquivo no formato do template (--igp-di); correções
manuais são preservadas quando o seed roda de novo.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 10: Fixtures reais e o teste ponta a ponta pela API

**Files:**
- Create: `scripts/gerar_fixtures_e2e.py` (uso único; a única leitura permitida da planilha de referência)
- Create: `tests/fixtures/igp_di.xlsx`, `tests/fixtures/delta_p_referencia.csv`, `tests/fixtures/contrato_ficticio.json` (gerados e versionados)
- Create: `tests/test_e2e_reequilibrio.py`

**Interfaces:**
- Consumes: `importadores.gerar_template_igp_di` (Task 3); `tests/fixtures/anp_semanal.xls` (Task 3); `file_processor._persistir(result, filename, job_id)` (Task 1); rotas `/api/v1` das Tasks 6–8; `template_repo.garantir_semente`, `xlsx_drawings.contem_equacao`, `reequilibrio_layout.ABA`.
- Produces: as quatro fixtures em `tests/fixtures/` e o teste `tests/test_e2e_reequilibrio.py`.

**De onde vêm os dados** (conferido no plano, antes da implementação):
- `tmp/Reequilíbrio - 26 - Contrato 716-22.xlsx` (não versionada), aba
  `CÁLCULO DA VARIAÇÃO DE PREÇOS`: a linha 6 tem a base (`C6 = 4.02073`, CAP
  Nordeste da semana de 15/12/2021; `I6 = 1110.398`, IGP-DI de jan/2022). A partir
  da linha 7: `H` = mês da medição `m`, `D` = ΔP CAP, `I` = IGP-DI de `m`,
  `J` = ΔP Emulsões. Os números acabam na linha 50 (ago/2026); daí em diante há `#N/A`.
- A aba `IGP - DI`: linha 3 com os meses a partir da coluna C (jan/2023); linha 26
  com o IGP-DI (`ago/1994 = 100`).
- Recalculando o ΔP CAP do oráculo a partir de `anp_semanal.xls` pela regra do dia
  15, a diferença é **zero** nos 44 meses: o oráculo e o arquivo da ANP concordam.
- `data/jobs/37135d545e7a/results/{10ª..21ª} MP_resultado.json` (não versionados):
  medições reais de jan a dez/2023 de **outro** contrato (06 00134/2022). Só os
  itens são aproveitados; o cabeçalho é fictício, com a Data Base do oráculo
  (jan/2022). Na 10ª, o código 60112 (CAP) tem `a = 21862.28`, e o 51796
  (imprimação) tem `a = 0.0`.
- Centro-Oeste não tem cotação de CAP (`***`) até maio/2023: é a região usada para
  testar a recusa.

Os arquivos de origem ficam fora do git, então o gerador roda uma vez, na máquina
de quem tem esses arquivos. As fixtures geradas é que são versionadas; o teste nunca
lê `tmp/` nem `data/`.

- [ ] **Step 1: Criar `scripts/gerar_fixtures_e2e.py`**

```python
"""Gera as fixtures do teste ponta a ponta (uso único).

    uv run python scripts/gerar_fixtures_e2e.py

É o único código do projeto que lê a planilha de referência
``tmp/Reequilíbrio - 26 - Contrato 716-22.xlsx``, e só para produzir as fixtures
versionadas em ``tests/fixtures/``. O seed e a aplicação nunca a leem.

* ``igp_di.xlsx``: o IGP-DI de jan/2022 (a base, célula I6 do oráculo) e os meses
  da aba ``IGP - DI``, no formato do template de importação;
* ``delta_p_referencia.csv``: ``mes, delta_cap, delta_emul`` do oráculo,
  calculados pelo Excel, de forma independente da aplicação;
* ``contrato_ficticio.json``: itens reais de jan a dez/2023 extraídos de outro
  contrato, sob um cabeçalho fictício com a Data Base do oráculo.
"""

import csv
import json
import sys
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

import openpyxl

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import config  # noqa: E402
from app.services.importadores import gerar_template_igp_di  # noqa: E402

PLANILHA = config.PROJECT_ROOT / "tmp" / "Reequilíbrio - 26 - Contrato 716-22.xlsx"
RESULTADOS = config.PROJECT_ROOT / "data" / "jobs" / "37135d545e7a" / "results"
MEDICOES = [f"{n}ª MP_resultado.json" for n in range(10, 22)]  # jan–dez/2023
DESTINO = config.PROJECT_ROOT / "tests" / "fixtures"

ABA_ORACULO = "CÁLCULO DA VARIAÇÃO DE PREÇOS"
ABA_IGP = "IGP - DI"
LINHA_IGP = 26  # "IGP - DI", base ago/1994 = 100
BASE_IGP = (date(2022, 1, 1), "I6")

CABECALHO_FICTICIO = {
    "Contrato": "99 99999/2099 - CONSTRUTORA FICTÍCIA LTDA",
    "Data Base": "01/01/2022",
    "Número do Processo": "99999.999999/2099-99",
}


def _mes(valor) -> date:
    return (valor.date() if isinstance(valor, datetime) else valor).replace(day=1)


def _numero(valor) -> bool:
    return isinstance(valor, (int, float)) and not isinstance(valor, bool)


def igp_di(livro) -> dict[date, Decimal]:
    ws = livro[ABA_IGP]
    rotulo = ws.cell(LINHA_IGP, 1).value
    if not isinstance(rotulo, str) or "IGP" not in rotulo:
        raise SystemExit(f"A linha {LINHA_IGP} da aba '{ABA_IGP}' não é o IGP-DI: {rotulo!r}")
    valores = {}
    for celula in ws[3][2:]:
        if isinstance(celula.value, datetime):
            valor = ws.cell(LINHA_IGP, celula.column).value
            if _numero(valor):
                valores[_mes(celula.value)] = Decimal(str(valor))
    mes_base, endereco = BASE_IGP
    valores[mes_base] = Decimal(str(livro[ABA_ORACULO][endereco].value))
    return valores


def oraculo(livro, igp: dict[date, Decimal]) -> list[dict]:
    ws = livro[ABA_ORACULO]
    linhas = []
    for r in range(7, ws.max_row + 1):
        mes, cap, igp_mes, emul = (ws.cell(r, c).value for c in (8, 4, 9, 10))
        if not (_numero(cap) and _numero(emul)):
            break
        mes = _mes(mes)
        # A coluna I do oráculo e a aba IGP - DI têm de ser a mesma série.
        if Decimal(str(igp_mes)) != igp.get(mes):
            raise SystemExit(f"IGP-DI de {mes:%m/%Y} diverge entre as abas: {igp_mes} x {igp.get(mes)}")
        linhas.append({"mes": mes.isoformat(), "delta_cap": repr(cap), "delta_emul": repr(emul)})
    return linhas


def contrato() -> dict:
    arquivos = []
    for nome in MEDICOES:
        dados = json.loads((RESULTADOS / nome).read_text(encoding="utf-8"))
        arquivos.append({"arquivo": nome.replace("_resultado.json", ".pdf"), "rows": dados["rows"]})
    return {"header": CABECALHO_FICTICIO, "arquivos": arquivos}


def main() -> None:
    DESTINO.mkdir(parents=True, exist_ok=True)
    livro = openpyxl.load_workbook(PLANILHA, data_only=True)

    igp = igp_di(livro)
    (DESTINO / "igp_di.xlsx").write_bytes(
        gerar_template_igp_di([{"mes_ref": m, "valor": v} for m, v in igp.items()])
    )

    linhas = oraculo(livro, igp)
    with (DESTINO / "delta_p_referencia.csv").open("w", newline="", encoding="utf-8") as f:
        escritor = csv.DictWriter(f, fieldnames=["mes", "delta_cap", "delta_emul"])
        escritor.writeheader()
        escritor.writerows(linhas)

    (DESTINO / "contrato_ficticio.json").write_text(
        json.dumps(contrato(), ensure_ascii=False, indent=1), encoding="utf-8"
    )
    print(f"igp_di.xlsx: {len(igp)} meses; delta_p_referencia.csv: {len(linhas)} meses; "
          f"contrato_ficticio.json: {len(MEDICOES)} medições")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Gerar as fixtures e conferir**

Run: `uv run python scripts/gerar_fixtures_e2e.py && head -3 tests/fixtures/delta_p_referencia.csv`
Expected: `igp_di.xlsx: 44 meses; delta_p_referencia.csv: 44 meses; contrato_ficticio.json: 12 medições`,
(o IGP-DI tem jan/2022 mais os 43 meses numéricos da aba `IGP - DI`),
seguido de

```
mes,delta_cap,delta_emul
2023-01-01,-0.07576236156120908,-0.04928776084307834
```

Se o script parar com "diverge entre as abas", **não** contorne: leve a divergência
ao usuário.

- [ ] **Step 3: Escrever `tests/test_e2e_reequilibrio.py`**

```python
"""Ponta a ponta, só pela API, com índices reais e itens reais de medição.

O oráculo é a aba ``CÁLCULO DA VARIAÇÃO DE PREÇOS`` da planilha de referência
(contrato 716-22, Data Base jan/2022, Nordeste), calculada pelo Excel sem
nenhum código desta aplicação. Se o ΔP divergir, é divergência de regra a levar
ao usuário: o oráculo não é ajustado para o teste passar.
"""

import csv
import io
import json
from datetime import date
from decimal import ROUND_DOWN, Decimal
from pathlib import Path

import openpyxl
import pytest

from app.services import template_repo, xlsx_drawings
from app.services.file_processor import _persistir
from app.services.reequilibrio_layout import ABA

FIXTURES = Path("tests/fixtures")
NUMERO = "99 99999/2099"
TOLERANCIA = Decimal("1e-9")
LUCRO = Decimal("0.0511")
CENTAVO = Decimal("0.01")


def _oraculo() -> dict[str, dict[str, Decimal]]:
    with (FIXTURES / "delta_p_referencia.csv").open(encoding="utf-8") as f:
        return {
            linha["mes"]: {"CAP": Decimal(linha["delta_cap"]), "EMULSOES": Decimal(linha["delta_emul"])}
            for linha in csv.DictReader(f)
        }


async def _importar(client, rota: str, arquivo: Path) -> dict:
    resposta = await client.post(
        f"/api/v1/indices/{rota}/importar",
        files={"arquivo": (arquivo.name, arquivo.read_bytes())},
    )
    assert resposta.status_code == 200, resposta.text
    return resposta.json()


async def _preparar(client) -> int:
    # 1. Índices reais, pelos endpoints de importação.
    anp = await _importar(client, "anp", FIXTURES / "anp_semanal.xls")
    assert anp["inseridos"] == 60114
    igp = await _importar(client, "igp-di", FIXTURES / "igp_di.xlsx")
    assert igp["periodo"]["de"] == "2022-01-01"

    # 2. O contrato, pelo mesmo caminho de um PDF processado.
    ficticio = json.loads((FIXTURES / "contrato_ficticio.json").read_text(encoding="utf-8"))
    for medicao in ficticio["arquivos"]:
        _persistir({"header": ficticio["header"], "rows": medicao["rows"]}, medicao["arquivo"], "e2e")
    (resumo,) = (await client.get("/api/v1/contratos", params={"numero": NUMERO})).json()
    contrato_id = resumo["id"]

    # 3. Cadastro completo, com a região em grafia diferente da do arquivo ANP.
    resposta = await client.patch(
        f"/api/v1/contratos/{contrato_id}",
        json={
            "edital": "999/2099-99", "rodovia": "BR-999", "trecho": "Trecho fictício",
            "subtrecho": "Subtrecho fictício", "segmento": "km 0,0 ao km 10,0",
            "extensao": "10.0", "contratada": "CONSTRUTORA FICTÍCIA LTDA",
            "regioes": {"CAP": "nordeste", "EMULSOES": "Nordeste"},
        },
    )
    assert resposta.status_code == 200, resposta.text
    assert resposta.json()["regioes"] == {"CAP": "Nordeste", "EMULSOES": "Nordeste"}

    # 4. Catálogo do zero: a migração traz associações prontas; o teste as remove
    #    para provar que só o que o usuário associa entra no cálculo.
    for codigo in (await client.get("/api/v1/codigos", params={"associado": "true"})).json():
        assert (await client.delete(f"/api/v1/codigos/{codigo['codigo']}")).status_code == 204

    # 5. Dois produtos customizados e só dois códigos associados.
    cap = await client.post(
        "/api/v1/produtos", json={"descricao_export": "Aquisição de CAP 50/70", "familia": "CAP"}
    )
    emulsao = await client.post(
        "/api/v1/produtos",
        json={"descricao_export": "Aquisição de Emulsão RR-1C", "familia": "EMULSOES"},
    )
    assert cap.status_code == emulsao.status_code == 201
    for codigo, produto in (("60112", cap), ("29083", emulsao)):
        resposta = await client.put(
            f"/api/v1/codigos/{codigo}", json={"produto_id": produto.json()["id"]}
        )
        assert resposta.status_code == 200, resposta.text

    template_repo.garantir_semente()
    return contrato_id


def _linhas(corpo: dict):
    for familia in corpo["familias"]:
        for produto in familia["produtos"]:
            for linha in produto["linhas"]:
                yield familia["familia"], produto["descricao"], linha


async def test_ponta_a_ponta(client):
    contrato_id = await _preparar(client)
    oraculo = _oraculo()

    # --- cálculo em JSON ---------------------------------------------------
    resposta = await client.get(f"/api/v1/contratos/{contrato_id}/calculo")
    assert resposta.status_code == 200, resposta.text
    corpo = resposta.json()
    assert corpo["parametros"]["data_base"] == "2022-01-01"
    assert corpo["parametros"]["simulacao"] is False

    # Só os dois produtos associados; os outros códigos ficam fora sem bloquear.
    assert {(f["familia"], p["descricao"]) for f in corpo["familias"] for p in f["produtos"]} == {
        ("CAP", "Aquisição de CAP 50/70"),
        ("EMULSOES", "Aquisição de Emulsão RR-1C"),
    }

    linhas = list(_linhas(corpo))
    meses = {linha["mes"] for _, _, linha in linhas}
    assert meses <= {f"2023-{m:02d}-01" for m in range(1, 13)}
    assert "2023-01-01" in meses

    total = Decimal(0)
    for familia, _, linha in linhas:
        a, fator, d = Decimal(linha["a"]), Decimal(linha["fator"]), Decimal(linha["d"])
        # ΔP contra o oráculo do Excel.
        assert abs(d - oraculo[linha["mes"]][familia]) < TOLERANCIA, (familia, linha["mes"])
        # As fórmulas do art. 16, recalculadas aqui.
        b = (a * fator).quantize(CENTAVO, rounding=ROUND_DOWN)
        c = a * d
        e = c - b
        f = e * (1 - LUCRO)
        assert Decimal(linha["b"]) == b
        assert Decimal(linha["c"]) == c
        assert Decimal(linha["e"]) == e
        assert Decimal(linha["f"]) == f
        total += f
    assert Decimal(corpo["total"]) == total

    janeiro_cap = [l for fam, _, l in linhas if fam == "CAP" and l["mes"] == "2023-01-01"]
    assert [l["a"] for l in janeiro_cap] == ["21862.28"]
    # De março em diante cada PDF traz o 60112 duas vezes (uma linha zerada e a
    # linha com valor); o banco guarda a última. Ver a nota do Step 4.
    marco_cap = [l for fam, _, l in linhas if fam == "CAP" and l["mes"] == "2023-03-01"]
    assert [l["a"] for l in marco_cap] == ["13926.57"]

    # --- a planilha ----------------------------------------------------------
    resposta = await client.get(f"/api/v1/contratos/{contrato_id}/planilha")
    assert resposta.status_code == 200, resposta.text
    assert 'filename="Reequilibrio_99-99999-2099.xlsx"' in resposta.headers["content-disposition"]
    ws = openpyxl.load_workbook(io.BytesIO(resposta.content))[ABA]
    formulas = [
        r for r in range(1, ws.max_row + 1)
        if str(ws.cell(r, 6).value or "").startswith("=TRUNC(")
    ]
    assert len(formulas) == len(linhas)
    deltas = sorted(float(linha["d"]) for _, _, linha in linhas)
    assert sorted(ws.cell(r, 7).value for r in formulas) == pytest.approx(deltas, abs=1e-12)
    for r in formulas:
        assert ws.cell(r, 6).value == f"=TRUNC(E{r}*D{r},2)"
        assert ws.cell(r, 8).value == f"=D{r}*G{r}"
        assert ws.cell(r, 9).value == f"=H{r}-F{r}"
        assert ws.cell(r, 10).value == f"=I{r}*(1-0.0511)"
    assert xlsx_drawings.contem_equacao(resposta.content, ABA)

    # --- simulação de região -------------------------------------------------
    simulada = await client.get(
        f"/api/v1/contratos/{contrato_id}/planilha", params={"regiao_cap": "Sul"}
    )
    assert simulada.status_code == 200, simulada.text
    assert "SIMULACAO_CAP-Sul" in simulada.headers["content-disposition"]
    corpo_sul = (
        await client.get(f"/api/v1/contratos/{contrato_id}/calculo", params={"regiao_cap": "Sul"})
    ).json()
    assert corpo_sul["parametros"]["simulacao"] is True
    cap_nordeste = {l["mes"]: l["d"] for fam, _, l in linhas if fam == "CAP"}
    cap_sul = {l["mes"]: l["d"] for fam, _, l in _linhas(corpo_sul) if fam == "CAP"}
    assert cap_sul.keys() == cap_nordeste.keys()
    assert all(cap_sul[m] != cap_nordeste[m] for m in cap_sul)
    cadastro = (await client.get(f"/api/v1/contratos/{contrato_id}")).json()
    assert cadastro["regioes"] == {"CAP": "Nordeste", "EMULSOES": "Nordeste"}

    # --- recusas -------------------------------------------------------------
    # Centro-Oeste não tem cotação de CAP até maio/2023: o cálculo é recusado.
    sem_cotacao = await client.get(
        f"/api/v1/contratos/{contrato_id}/calculo", params={"regiao_cap": "Centro-Oeste"}
    )
    assert sem_cotacao.status_code == 422
    assert sem_cotacao.json()["faltando"]
    inexistente = await client.get(
        f"/api/v1/contratos/{contrato_id}/calculo", params={"regiao_cap": "Atlântida"}
    )
    assert inexistente.status_code == 422
```

- [ ] **Step 4: Rodar o teste**

Run: `uv run pytest tests/test_e2e_reequilibrio.py -v`
Expected: PASS, em ~15 s.

Se a asserção do ΔP contra o oráculo falhar, **pare**: não mexa no CSV nem na
tolerância. Relate ao usuário o mês, a família, o valor da aplicação e o do
oráculo; é divergência de regra.

Atenção a um comportamento já existente, que o teste documenta sem esconder: de
março a dezembro, cada PDF traz o 60112 e o 29083 **duas vezes** no mesmo mês —
uma linha com `a = 0.0` e outra com o valor. A chave única de `medicao_item`
(`contrato_id, codigo_servico, mes_medicao, source_file`) guarda só a **última**
linha gravada, que nesses arquivos é a que tem valor (13926.57 em março). O
resultado está certo por causa da ordem das linhas no PDF, não por regra; somar
as linhas repetidas é decisão do usuário e fica fora de A. Se a asserção de
março falhar, a ordem de gravação mudou: relate, não ajuste o número.

- [ ] **Step 5: Rodar a suíte inteira**

Run: `uv run pytest -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add scripts/gerar_fixtures_e2e.py tests/fixtures/igp_di.xlsx \
  tests/fixtures/delta_p_referencia.csv tests/fixtures/contrato_ficticio.json \
  tests/test_e2e_reequilibrio.py
git commit -m "$(cat <<'EOF'
test: ponta a ponta do reequilíbrio com índices e medições reais

Importa o arquivo oficial da ANP e o IGP-DI pela API, cria um contrato
fictício com itens reais de jan a dez/2023, associa só dois códigos e
confere cada ΔP com o oráculo calculado no Excel (tolerância 1e-9), as
colunas b-f com as fórmulas do art. 16, a planilha com fórmulas vivas
e a simulação de região. As fixtures vêm de um gerador de uso único,
único código que lê a planilha de referência.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 11: Documentação — README e regras

**Files:**
- Modify: `README.md`
- Modify: `.claude/rules/backend.md`, `.claude/rules/architecture.md`, `.claude/rules/deployment.md`

**Interfaces:**
- Consumes: tudo o que as Tasks 1–10 criaram; nada é produzido para outras tarefas.

Regra do projeto (`.claude/rules/documentation.md`): o README entra na mesma
alteração que muda o comportamento, em português, sem descrever o que não existe.
A documentação do Dash **não** é reescrita (fica para C); só sai dela o que deixou
de ser verdade sobre pendências. Faça cada troca abaixo com a ferramenta de edição,
texto antigo → texto novo.

- [ ] **Step 1: README — *O que a aplicação faz***

Troque o parágrafo **Mapeamento por código de serviço** inteiro por:

```markdown
**Catálogo de produtos por código de serviço.** O código é a chave confiável — o
OCR corrompe a descrição, nunca o código. O usuário cadastra os produtos que
entram na planilha, com a descrição que quiser e a família (*Aquisição de CAP* ou
*Aquisição de Emulsões*), e associa a eles **alguns** códigos extraídos (o
`8300980`, "AQUISIÇÃO DE CIMENTO ASFÁLTICO CAP 50/70" no PDF, pode sair como
"AQUISIÇÃO DE CAP 50/70"). Código sem associação simplesmente fica fora do
cálculo: não é pendência e não bloqueia nada. A associação vale para tudo o que
já foi extraído, sem reprocessar PDFs.
```

Troque o parágrafo **ΔP automático** inteiro por:

```markdown
**ΔP automático.** A variação do preço do produtor (art. 16) é calculada pela
aplicação a partir dos preços semanais da ANP e do IGP-DI, sempre contra a *Data
Base* do contrato. Cada família (CAP e EMULSÕES) tem a sua região da ANP,
cadastrada no contrato. O preço do mês é o da semana que contém o dia 15 do mês
anterior; uma semana sem cotação, ou um índice ainda não cadastrado, **recusa** o
cálculo com a lista do que falta — nunca vira zero.

**Índices globais, editáveis por qualquer usuário.** Os preços da ANP e o IGP-DI
não pertencem a contrato nenhum. Podem ser corrigidos um a um ou importados em
massa: o `.xls` de preços semanais publicado pela ANP e um template próprio para o
IGP-DI, que a aplicação gera já preenchido com o que está no banco. Toda
importação tem prévia, é tudo ou nada e **preserva as correções manuais**, a menos
que se peça para sobrescrevê-las. As duas séries também podem ser exportadas em
CSV ou XLSX.

**Simulação de região.** Na exportação, a região de cada família pode ser trocada
só para aquela geração, sem alterar o cadastro; o arquivo sai com `SIMULACAO` no
nome. Para comparar regiões, exporta-se duas vezes.

**API REST.** Tudo o que o cálculo usa — contratos, catálogo, índices, cálculo e
planilha — está em `/api/v1`, utilizável por `curl` ou por qualquer cliente, com a
documentação interativa em `/docs`.
```

Troque o parágrafo **Cadastro do contrato** inteiro por:

```markdown
**Cadastro do contrato.** Os campos que nenhum PDF traz (Edital, Rodovia, Trecho,
Subtrecho, Segmento, Extensão, Contratada) são cadastrados por contrato e
preenchem o cabeçalho da planilha. A *Data Base* vem sugerida pelo PDF e pode ser
corrigida; a região da ANP de cada família é obrigatória para calcular.
```

- [ ] **Step 2: README — *Telas***

Troque as duas últimas linhas da tabela por:

```markdown
| `/dashboard` | Reequilíbrio: cálculo na tela, cadastro do contrato, códigos, índices, templates e backup |
| `/docs` | Documentação interativa da API REST (`/api/v1`), gerada pelo FastAPI |
```

- [ ] **Step 3: README — *Setup em um ambiente novo***

No bloco de comandos, troque o passo 5:

```bash
# 5. Carga inicial dos preços da ANP (cópia versionada do arquivo oficial)
uv run python scripts/seed_indices.py --anp tests/fixtures/anp_semanal.xls
```

Logo depois do parágrafo "Rodando fora do Docker, …", acrescente:

```markdown
O seed grava todos os produtos do arquivo da ANP (o cálculo usa só o CAP 50/70).
O IGP-DI não vem de arquivo público padronizado: baixe o template em
`GET /api/v1/indices/igp-di/template`, preencha os meses e importe-o por
`POST /api/v1/indices/igp-di/importar` ou por
`uv run python scripts/seed_indices.py --sem-anp --igp-di <arquivo>`. Rodar o seed
de novo não desfaz correções manuais. Arquivos mais novos da ANP entram por
`POST /api/v1/indices/anp/importar`.
```

Troque o parágrafo "Depois disso, no navegador: …" por:

```markdown
Depois disso: suba os PDFs em `http://localhost:8000/`, complete o cadastro do
contrato e as regiões da ANP, associe os códigos de CAP e de emulsão a produtos
do catálogo e baixe a planilha — pelo `/dashboard` ou pela API (`/docs`).
```

- [ ] **Step 4: README — *Testes* e *Estrutura do projeto***

Em *Testes*, depois do primeiro bloco de comandos, acrescente:

```markdown
O teste ponta a ponta (`tests/test_e2e_reequilibrio.py`) importa o arquivo
oficial da ANP e leva alguns segundos. Ele usa só as fixtures versionadas em
`tests/fixtures/`, que incluem o ΔP calculado de forma independente no Excel como
oráculo.
```

Em *Estrutura do projeto*, troque as linhas de `scripts/`, `routers/` e `tests/`:

```
scripts/           Carga inicial dos índices, geração das fixtures do teste
                   ponta a ponta e reconstrução do template
├── routers/       Rotas HTTP: upload, jobs, admin, reequilíbrio e a API REST
│                  em api/ (/api/v1)
tests/             Suíte pytest; fixtures/ com índices reais e o oráculo do ΔP
```

- [ ] **Step 5: `.claude/rules/backend.md`**

Troque a seção `### catalogo.py` inteira por:

```markdown
### catalogo.py

The **service code** is the key, not the description: a code maps to exactly one
material, and OCR corrupts descriptions but not codes. Products are created by the
user (free `descricao_export` + family `CAP`/`EMULSOES`); several codes can point
at one product.

- A row in `produto_codigo` **is** the association. A code without one is simply
  out of the calculation — not a pendência, no warning, nothing blocked.
- `criar_produto`/`atualizar_produto`/`excluir_produto` (deleting cascades the
  associations); duplicates raise `ProdutoDuplicado`, other refusals `ErroCatalogo`.
- `registrar_codigo(codigo, produto_id)` associates or re-points a code, even one
  not yet extracted; `desassociar_codigo(codigo)` removes it. Associations are
  retroactive: `medicao_item` keeps every extracted item.
- `buscar_codigos(q, associado, limite)` — distinct extracted codes, `q` filtering
  code **or** description with `ILIKE '%q%'`.
```

Na seção `### medicoes_repo.py`, troque a última frase por:
"`itens_para_export` returns the rows joined to the catalogue — only associated codes."
e acrescente: "`gravar_itens` returns the number of items stored."

Troque a seção `### indices_repo.py` inteira por:

```markdown
### indices_repo.py

`gravar_precos_anp` / `gravar_indices_mensais` upsert with an `origem`
(`'manual'`, `'upload:<arquivo>'`, `'seed'`) and rewrite a row only when the value
changed (`IS DISTINCT FROM`), stamping `atualizado_em`. `gravar_semana_manual` /
`gravar_indice_manual` are the single-value edits (`origem = 'manual'`).

Weeks of the same product and region **must not overlap**: the importer reports
it per line, and `EXCLUDE USING gist (… daterange(vigencia_inicio, vigencia_fim,
'[]') WITH &&)` (migration 006, `btree_gist`) is the final guarantee, surfaced as
`SemanaSobreposta`. Regions are compared case-insensitively
(`normalizar_regiao`) and stored in the ANP file's spelling.

`buscar_preco_anp(produto, regiao, mes)` resolves a month to the weekly row whose
vigência contains **day 15** (`_dia_de_referencia`); `cobertura()` returns
`{"anp": {de, ate, registros}, "igp_di": {…}, "regioes": [...]}`. `FonteBanco`
caches per instance — one export asks for the same base month on every line.

### importadores.py / importacao.py / exportadores.py

`importadores` is pure (bytes in, validated rows or `ArquivoInvalido` with
per-line `erros` out): the ANP's standard `.xls` (read with `xlrd`, layout checked
first, `***` → NULL, 5 decimal places; a product with repeated weeks — only GLP
in the official file — is skipped with a warning) and the IGP-DI template it also
generates. `importacao` compares with the database: **all or nothing**,
`simular=True` writes nothing, and `origem = 'manual'` rows are preserved unless
`sobrescrever_manuais=True`. The API, the seed and the tests share this path.
`exportadores` writes both series as CSV or XLSX; the IGP-DI XLSX is the template,
so it can be re-imported unchanged.
```

Na seção `## delta_p.py — ΔP`, troque a última frase ("The export refuses; the
dashboard surfaces it as a pendência.") por: "The export refuses, and the API
answers 422 with every missing índice in `faltando`."

Na seção `## reequilibrio_export.py — The Spreadsheet`, depois do primeiro parágrafo, acrescente:

```markdown
`calcular(contrato, regioes_override)` is the single calculation behind both the
JSON (`serializar`, columns `a`–`f` of row 16) and the file (`gerar`). An override
changes a family's region for that generation only — never the registration — and
is reported in `avisos` and in the filename (`…_SIMULACAO_CAP-Sul.xlsx`).
`ExportacaoImpossivel` carries a structured `faltando` list.
```

Na seção `## Routers`, acrescente ao fim:

```markdown
### api/ — `/api/v1`

Thin routers over the synchronous services (`asyncio.to_thread`), Pydantic
schemas in `schemas.py` (Decimal serialised as string). `ErroApi(status, detail,
**extra)` and its handler produce `{"detail": …}` plus fields such as `faltando`
or `erros`. Contracts are addressed by numeric `id`; `GET /contratos?numero=`
finds one by number. Index uploads are capped at 20 MB (413).
```

- [ ] **Step 6: `.claude/rules/architecture.md`**

No *File Layout*: acrescente `└── 006_catalogo_indices.sql       # drops confirmado; origem/atualizado_em; btree_gist + no-overlap constraint`
depois de `005_template.sql` (e troque o `└──` da 005 por `├──`); troque a linha de
`seed_indices.py` por
`├── seed_indices.py            # Initial load through the importers (--anp, --igp-di)`
e acrescente abaixo
`├── gerar_fixtures_e2e.py      # One-off: builds tests/fixtures/ from the reference spreadsheet`;
em `routers/`, acrescente
`│   └── api/                   # REST API /api/v1: contratos, catalogo, indices, calculo, schemas, erros`
(e troque o `└──` de `reequilibrio.py` por `├──`); em `services/`, troque a linha de
`catalogo.py` por `# Products, service-code associations, code search` e
acrescente depois de `indices_repo.py`:

```
│   ├── importadores.py        # Pure readers: ANP .xls, IGP-DI template (and its generator)
│   ├── importacao.py          # Preview/write against the database, manual values preserved
│   ├── exportadores.py        # CSV/XLSX of both índice series
```

Na tabela *Routing*, acrescente antes de `GET /static/*`:

```markdown
| `/api/v1/…` | `routers/api` | Contratos, catálogo, índices, cálculo e planilha; OpenAPI em `/docs` |
```

- [ ] **Step 7: `.claude/rules/deployment.md`**

Na lista de dependências, acrescente `xlrd` depois de `a2wsgi`, e ao parágrafo
seguinte: "`xlrd` reads the ANP's legacy `.xls` in the importer."

Em `## Database`, depois do primeiro parágrafo, acrescente: "Migration 006 runs
`CREATE EXTENSION IF NOT EXISTS btree_gist` (shipped with the `postgres:16`
image); the database user must be allowed to create extensions — the Compose
user is."

Troque a subseção `### Initial data load` inteira por:

````markdown
### Initial data load

The índices are user-maintained; the seed is a command-line shell over the same
importers the API uses, writing `origem = 'seed'` and preserving manual edits:

```bash
uv run python scripts/seed_indices.py --anp tests/fixtures/anp_semanal.xls   # ANP (all products)
uv run python scripts/seed_indices.py --sem-anp --igp-di <template preenchido>
```

Without `--anp` it reads `data/precos-medios-ponderados-semanais-2013.xls`. The
script applies the migrations itself, so it can run before the app's first start.
It never reads the reference spreadsheet `Reequilíbrio - 26 - Contrato
716-22.xlsx`; only `scripts/gerar_fixtures_e2e.py` does, to build the test
fixtures.
````

Em `## Running Tests`, acrescente ao fim: "`tests/test_e2e_reequilibrio.py` imports
the full official ANP file and takes a few seconds; it reads only the versioned
`tests/fixtures/`."

- [ ] **Step 8: Verificar os comandos do README como estão escritos**

Num banco limpo (a regra de documentação pede executar, não só ler):

```bash
docker compose up -d postgres
docker compose exec postgres dropdb -U dnit --if-exists dnit_seed_check
docker compose exec postgres createdb -U dnit dnit_seed_check
DATABASE_URL="$(grep '^DATABASE_URL=' .env | cut -d= -f2- | sed 's#/dnit$#/dnit_seed_check#')" \
  uv run python scripts/seed_indices.py --anp tests/fixtures/anp_semanal.xls
docker compose exec postgres dropdb -U dnit dnit_seed_check
uv run pytest -q
```

Expected: o seed imprime `60114 inseridos` e o aviso do GLP; a suíte passa.
Confira também que nenhum comando, rota ou arquivo citado no README deixou de
existir: `grep -niE "todos-produtos|\bpend[êe]ncias?\b" README.md .claude/rules/*.md` não deve
achar nada.

- [ ] **Step 9: Commit**

```bash
git add README.md .claude/rules/backend.md .claude/rules/architecture.md .claude/rules/deployment.md
git commit -m "$(cat <<'EOF'
docs: README e regras para a API REST e o catálogo sem pendências

Documenta a API em /api/v1, o catálogo de produtos por código, os
índices globais com importação, prévia e preservação das correções
manuais, a simulação de região na exportação e o novo seed.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
)"
```
