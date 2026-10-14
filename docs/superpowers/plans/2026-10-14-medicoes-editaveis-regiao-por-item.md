# Medições editáveis e região ANP por item — Plano de implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Permitir incluir, alterar e excluir um registro de medição por vez e definir, por registro, a região ANP (CAP/Emulsões) que prevalece no cálculo do ΔP, com a marcação `*` + cor + nota na planilha e na tela.

**Architecture:** A migração 008 dá a `medicao_item` uma origem (`pdf`/`editado`/`manual`), uma exclusão lógica e duas regiões opcionais. `medicoes_repo` ganha o CRUD e passa a preservar o trabalho manual quando o PDF é reprocessado. `reequilibrio_export` resolve a região de cada item (item > simulação > cadastro), calcula o ΔP por `(família, mês, região)` e agrega por produto × mês × fator × região manual. Do outro lado ficam a API REST (`/api/v1/contratos/{id}/medicoes[/{item_id}]`) e a aba *Medições* do SPA, que ganha as ações.

**Tech Stack:** Python 3.12, FastAPI, psycopg 3 (SQL puro), openpyxl, pytest; React + TypeScript, TanStack Query, react-hook-form, Vitest + MSW, Playwright.

**Spec:** `docs/superpowers/specs/2026-10-14-medicoes-editaveis-regiao-por-item-design.md`

## Global Constraints

- Dinheiro e fator em `NUMERIC`/`Decimal`; na API, `Decimal` trafega como **string**; o frontend nunca converte para `number` nem calcula.
- Mês de referência é `DATE` no dia 1; na API de entrada, `AAAA-MM` (padrão `MES` de `app/routers/api/erros.py`).
- SQL puro com psycopg, sem ORM; repositórios **síncronos** (`acquire_sync`), chamados pela API via `asyncio.to_thread`.
- Recusas de negócio: exceção do serviço → `ErroApi(422, str(e))`, com `detail` em texto.
- Fórmulas vivas F, H, I, J inalteradas; a coluna G (ΔP) continua literal; endereços, textos e cores da planilha ficam em `reequilibrio_layout.py`.
- Frontend: sem `style` inline, sem emoji, sem CDN; cores novas viram token em `styles/tokens.css`; ação destrutiva pede `ConfirmarDialogo`; componentes de tela usam `export function`; mensagens de negócio vêm do backend.
- Precedência de região: **região do item > simulação (`?regiao_*`) > cadastro do contrato**.
- Mensagens ao usuário, docs e commits em **português**.

**Refinamento da spec (decidido aqui):** em registros vindos do PDF (`pdf`/`editado`), **código e mês não são editáveis**. São a chave com que o reprocessamento reencontra a linha; se mudassem, o PDF reenviado criaria um registro duplicado. Para corrigir esses campos, o usuário exclui o registro e inclui um manual. Em registros `manual`, todos os campos são editáveis.

## Review Focus

1. **Reprocessar o mesmo PDF depois de editar ou excluir** → o valor editado e a exclusão sobrevivem, e o contador de itens devolvido continua o mesmo (teste na Task 1).
2. **Registro manual com o mesmo código × mês de um registro do PDF** → os dois somam; a deduplicação "mesmo PDF com dois nomes" não pode descartar o manual (teste na Task 3).
3. **Região manual sem índice ANP para o mês** → aparece em `faltando` com a região no texto; não pode virar zero nem sumir (teste na Task 3).
4. **Simulação `?regiao_cap=Sul` com um item fixado em `Nordeste`** → o item continua em Nordeste (teste na Task 3).
5. **Duas linhas do mesmo produto e mês na tabela do Cálculo** (por fator ou região) → chaves React únicas, sem aviso nem linha sumindo (teste na Task 7).

---

### Task 1: Migração 008 e preservação do trabalho manual no reprocessamento

**Files:**
- Create: `migrations/008_medicao_manual.sql`
- Modify: `app/services/medicoes_repo.py` (`gravar_itens`, `itens_para_export`, `listar_itens`, `meses_do_contrato`)
- Modify: `app/services/contratos_repo.py:146-151` (contagens de `listar`)
- Modify: `app/services/catalogo.py:229-231` (busca de códigos)
- Test: `tests/test_medicoes_manuais.py` (novo)

**Interfaces:**
- Produces: colunas `medicao_item.origem`, `excluido`, `regiao_cap`, `regiao_emulsoes`, `atualizado_em`; índice único parcial `uq_medicao_item_pdf`. `listar_itens` passa a devolver também `origem`, `regiao_cap` e `regiao_emulsoes`; `itens_para_export` devolve também `id`, `origem`, `regiao_cap` e `regiao_emulsoes`.

- [ ] **Step 1: Escrever o teste que falha**

```python
"""Registros de medição editados à mão sobrevivem ao reprocessamento do PDF."""

from app.db import acquire_sync
from app.services import contratos_repo, medicoes_repo

HEADER = {"Contrato": "15 00716/2022 - HWN ENGENHARIA LTDA", "Data Base": "01/01/2022"}
FEV = "01/02/2023 - 28/02/2023"


def _linha(codigo="60112", valor=412300.0, fator=0.148, arquivo="1ª MP.pdf"):
    return {"Serviço": codigo, "Descrição": "Fornecimento de CAP 50/70",
            "Valor a PI Líquido": valor, "Fator": fator, "Período Líquido": FEV,
            "Source_File": arquivo}


def _sql(sql, *params):
    with acquire_sync() as conn:
        conn.execute(sql, params)


def test_reprocessar_nao_sobrescreve_registro_editado():
    contrato_id = contratos_repo.registrar_do_pdf(HEADER)
    medicoes_repo.gravar_itens(contrato_id, [_linha()])
    _sql("UPDATE medicao_item SET valor_pi = 1, origem = 'editado'")

    assert medicoes_repo.gravar_itens(contrato_id, [_linha()]) == 1

    [item] = medicoes_repo.listar_itens(contrato_id)
    assert item["valor_pi"] == 1 and item["origem"] == "editado"


def test_reprocessar_nao_ressuscita_registro_excluido():
    contrato_id = contratos_repo.registrar_do_pdf(HEADER)
    medicoes_repo.gravar_itens(contrato_id, [_linha()])
    _sql("UPDATE medicao_item SET excluido = true")

    medicoes_repo.gravar_itens(contrato_id, [_linha()])

    assert medicoes_repo.listar_itens(contrato_id) == []
    assert medicoes_repo.itens_para_export(contrato_id) == []
    assert medicoes_repo.meses_do_contrato(contrato_id) == []
    [resumo] = contratos_repo.listar()
    assert resumo["itens"] == 0 and resumo["medicoes"] == 0


def test_reprocessar_registro_do_pdf_continua_atualizando():
    contrato_id = contratos_repo.registrar_do_pdf(HEADER)
    medicoes_repo.gravar_itens(contrato_id, [_linha(valor=10.0)])
    medicoes_repo.gravar_itens(contrato_id, [_linha(valor=20.0)])
    [item] = medicoes_repo.listar_itens(contrato_id)
    assert item["valor_pi"] == 20 and item["origem"] == "pdf"
    assert item["regiao_cap"] is None and item["regiao_emulsoes"] is None
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `uv run pytest tests/test_medicoes_manuais.py -v`
Expected: FAIL com `column "origem" does not exist`.

- [ ] **Step 3: Escrever a migração**

`migrations/008_medicao_manual.sql`:

```sql
-- Registros de medição editáveis à mão, e a região ANP fixada num registro.
--
-- origem: 'pdf' veio da extração e o reprocessamento ainda o atualiza;
-- 'editado' veio do PDF e foi alterado pelo usuário (o reprocessamento não o
-- toca mais); 'manual' foi incluído pelo usuário.
-- excluido: exclusão lógica de um registro do PDF — se fosse apagado, o
-- reprocessamento o traria de volta. Um registro 'manual' é apagado de fato.
-- regiao_cap / regiao_emulsoes: quando preenchidas, prevalecem sobre a região
-- do contrato e sobre a simulação da exportação para este registro.

ALTER TABLE medicao_item
    ADD COLUMN origem TEXT NOT NULL DEFAULT 'pdf'
        CHECK (origem IN ('pdf', 'editado', 'manual')),
    ADD COLUMN excluido BOOLEAN NOT NULL DEFAULT false,
    ADD COLUMN regiao_cap TEXT,
    ADD COLUMN regiao_emulsoes TEXT,
    ADD COLUMN atualizado_em TIMESTAMPTZ;

-- A UNIQUE de 004 tem nome gerado pelo Postgres; procura-se pelo catálogo.
DO $$
DECLARE
    nome text;
BEGIN
    SELECT conname INTO nome FROM pg_constraint
     WHERE conrelid = 'medicao_item'::regclass AND contype = 'u';
    IF nome IS NOT NULL THEN
        EXECUTE format('ALTER TABLE medicao_item DROP CONSTRAINT %I', nome);
    END IF;
END $$;

-- Só os registros do PDF precisam da chave de idempotência; vários registros
-- manuais podem ter o mesmo código e mês.
CREATE UNIQUE INDEX uq_medicao_item_pdf
    ON medicao_item (contrato_id, codigo_servico, mes_medicao, source_file)
    WHERE origem <> 'manual';
```

(`apply_migrations` em `app/db.py:143-144` executa o arquivo inteiro com um `execute`, e o bloco `DO` funciona assim.)

- [ ] **Step 4: Ajustar `gravar_itens` e as leituras**

Em `gravar_itens` (`app/services/medicoes_repo.py`), troque a cláusula `ON CONFLICT` e acrescente ao docstring a frase sobre preservação:

```python
                    "ON CONFLICT (contrato_id, codigo_servico, mes_medicao, source_file) "
                    "  WHERE origem <> 'manual' "
                    "DO UPDATE SET valor_pi = EXCLUDED.valor_pi, "
                    "  fator = EXCLUDED.fator, job_id = EXCLUDED.job_id, "
                    "  descricao_pdf = EXCLUDED.descricao_pdf "
                    # Trabalho manual vence o PDF: um registro editado ou excluído
                    # pelo usuário não é sobrescrito nem volta ao reprocessar.
                    "WHERE medicao_item.origem = 'pdf' AND NOT medicao_item.excluido",
```

Docstring: depois de "…updates its rows instead of duplicating them.", acrescente: "Rows the user edited (``origem = 'editado'``) or deleted (``excluido``) are left alone."

Em `itens_para_export`, o SELECT passa a ser:

```python
            "SELECT m.id, m.mes_medicao, m.codigo_servico, m.valor_pi, m.fator, "
            "       m.source_file, m.origem, m.regiao_cap, m.regiao_emulsoes, "
            "       p.descricao_export, p.familia, p.ordem, p.id AS produto_id "
            "FROM medicao_item m "
            "JOIN produto_codigo pc ON pc.codigo_servico = m.codigo_servico "
            "JOIN produto p ON p.id = pc.produto_id "
            "WHERE m.contrato_id = %s AND NOT m.excluido "
```

Em `listar_itens`, extraia o SELECT para uma constante de módulo (a Task 2 reaproveita) e filtre os excluídos:

```python
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
```

e, em `listar_itens`, `_SELECT_ITEM + "WHERE m.contrato_id = %(contrato)s AND NOT m.excluido " + …` (os filtros e o ORDER BY seguem iguais). Em `meses_do_contrato`: `WHERE contrato_id = %s AND NOT excluido`.

Em `contratos_repo.py:146-151`, acrescente `AND NOT m.excluido` às quatro subconsultas (`COUNT(*)`, `COUNT(DISTINCT …)`, `MIN`, `MAX`). Em `catalogo.py:229-231`, acrescente `WHERE NOT excluido` (ou `AND NOT excluido`, se já houver WHERE) às duas leituras de `medicao_item`. Leia as linhas antes de editar, para encaixar a condição na consulta que já existe.

- [ ] **Step 5: Rodar os testes**

Run: `uv run pytest tests/test_medicoes_manuais.py tests/test_api_medicoes.py tests/test_contratos_repo.py tests/test_catalogo.py tests/test_upload.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add migrations/008_medicao_manual.sql app/services/medicoes_repo.py app/services/contratos_repo.py app/services/catalogo.py tests/test_medicoes_manuais.py
git commit -m "feat(backend): preserva medições editadas e excluídas no reprocessamento"
```

---

### Task 2: CRUD de um registro de medição no repositório

**Files:**
- Modify: `app/services/medicoes_repo.py`
- Test: `tests/test_medicoes_manuais.py`

**Interfaces:**
- Consumes: `_SELECT_ITEM` (Task 1); `indices_repo.normalizar_regiao(regiao) -> str | None`; `contratos_repo.buscar_por_id`.
- Produces:
  - `class MedicaoInvalida(ValueError)`
  - `CAMPOS_ITEM = ("mes", "codigo", "descricao_pdf", "valor_pi", "fator", "regiao_cap", "regiao_emulsoes")`
  - `buscar_item(contrato_id: int, item_id: int) -> dict | None` (mesmas chaves de `listar_itens`)
  - `incluir_item(contrato_id: int, dados: dict) -> int | None` (id novo; `None` se o contrato não existe)
  - `atualizar_item(contrato_id: int, item_id: int, dados: dict) -> bool` (`False` se o item não existe)
  - `excluir_item(contrato_id: int, item_id: int) -> bool`
  - Formato de `dados`: `mes` = `"AAAA-MM"`, `valor_pi`/`fator` = `Decimal` ou texto com ponto decimal, regiões = texto ou `None`/`""` (que significa seguir o contrato).

- [ ] **Step 1: Escrever os testes que falham** (acrescentar a `tests/test_medicoes_manuais.py`)

```python
from datetime import date
from decimal import Decimal

import pytest

from app.services import indices_repo
from app.services.medicoes_repo import MedicaoInvalida
from tests.indices_factory import semana


def _regioes():
    indices_repo.gravar_precos_anp(
        [semana(date(2023, 1, 9), "3.28568", regiao="Nordeste"),
         semana(date(2023, 1, 9), "3.45", regiao="Sul")]
    )


def _novo(**extra):
    return {"mes": "2023-02", "codigo": "60112", "descricao_pdf": "CAP manual",
            "valor_pi": "100.00", "fator": "0.148", **extra}


def test_incluir_registro_manual():
    _regioes()
    contrato_id = contratos_repo.registrar_do_pdf(HEADER)
    item_id = medicoes_repo.incluir_item(contrato_id, _novo(regiao_cap="SUL"))
    item = medicoes_repo.buscar_item(contrato_id, item_id)
    assert item["origem"] == "manual" and item["arquivo"] == "manual"
    assert item["mes"] == date(2023, 2, 1) and item["valor_pi"] == Decimal("100.00")
    assert item["regiao_cap"] == "Sul"  # grafia do arquivo da ANP


def test_dois_manuais_do_mesmo_codigo_e_mes_coexistem():
    contrato_id = contratos_repo.registrar_do_pdf(HEADER)
    medicoes_repo.incluir_item(contrato_id, _novo())
    medicoes_repo.incluir_item(contrato_id, _novo())
    assert len(medicoes_repo.listar_itens(contrato_id)) == 2


def test_incluir_em_contrato_inexistente():
    assert medicoes_repo.incluir_item(999, _novo()) is None


@pytest.mark.parametrize("dados, trecho", [
    ({"codigo": "12"}, "código"),
    ({"mes": "2023-13"}, "mês"),
    ({"valor_pi": "abc"}, "valor_pi"),
    ({"fator": None}, "fator"),
    ({"regiao_cap": "Marte"}, "regiao_cap"),
])
def test_incluir_recusa_campo_invalido(dados, trecho):
    _regioes()
    contrato_id = contratos_repo.registrar_do_pdf(HEADER)
    with pytest.raises(MedicaoInvalida, match=trecho):
        medicoes_repo.incluir_item(contrato_id, _novo(**dados))
    assert medicoes_repo.listar_itens(contrato_id) == []


def test_editar_registro_do_pdf_marca_editado_e_fixa_regiao():
    _regioes()
    contrato_id = contratos_repo.registrar_do_pdf(HEADER)
    medicoes_repo.gravar_itens(contrato_id, [_linha()])
    [item] = medicoes_repo.listar_itens(contrato_id)

    assert medicoes_repo.atualizar_item(
        contrato_id, item["id"], {"valor_pi": "5.00", "regiao_emulsoes": "nordeste"}
    )
    item = medicoes_repo.buscar_item(contrato_id, item["id"])
    assert item["origem"] == "editado" and item["valor_pi"] == Decimal("5.00")
    assert item["regiao_emulsoes"] == "Nordeste"

    medicoes_repo.atualizar_item(contrato_id, item["id"], {"regiao_emulsoes": ""})
    assert medicoes_repo.buscar_item(contrato_id, item["id"])["regiao_emulsoes"] is None


def test_registro_do_pdf_nao_muda_codigo_nem_mes():
    contrato_id = contratos_repo.registrar_do_pdf(HEADER)
    medicoes_repo.gravar_itens(contrato_id, [_linha()])
    [item] = medicoes_repo.listar_itens(contrato_id)
    with pytest.raises(MedicaoInvalida, match="código e mês"):
        medicoes_repo.atualizar_item(contrato_id, item["id"], {"codigo": "99999"})


def test_editar_campo_desconhecido_e_recusado():
    contrato_id = contratos_repo.registrar_do_pdf(HEADER)
    item_id = medicoes_repo.incluir_item(contrato_id, _novo())
    with pytest.raises(MedicaoInvalida, match="source_file"):
        medicoes_repo.atualizar_item(contrato_id, item_id, {"source_file": "x"})


def test_item_de_outro_contrato_nao_e_encontrado():
    contrato_id = contratos_repo.registrar_do_pdf(HEADER)
    item_id = medicoes_repo.incluir_item(contrato_id, _novo())
    assert medicoes_repo.buscar_item(contrato_id + 1, item_id) is None
    assert medicoes_repo.atualizar_item(contrato_id + 1, item_id, {"fator": "1"}) is False
    assert medicoes_repo.excluir_item(contrato_id + 1, item_id) is False


def test_excluir_manual_apaga_e_excluir_do_pdf_e_logico():
    contrato_id = contratos_repo.registrar_do_pdf(HEADER)
    medicoes_repo.gravar_itens(contrato_id, [_linha()])
    [do_pdf] = medicoes_repo.listar_itens(contrato_id)
    manual = medicoes_repo.incluir_item(contrato_id, _novo())

    assert medicoes_repo.excluir_item(contrato_id, manual)
    assert medicoes_repo.excluir_item(contrato_id, do_pdf["id"])
    assert medicoes_repo.listar_itens(contrato_id) == []
    with acquire_sync() as conn:
        restantes = conn.execute("SELECT origem, excluido FROM medicao_item").fetchall()
    assert [dict(r) for r in restantes] == [{"origem": "pdf", "excluido": True}]
    assert medicoes_repo.excluir_item(contrato_id, do_pdf["id"]) is False
```

(Confira a assinatura de `semana` em `tests/indices_factory.py`, que `tests/test_reequilibrio_export.py:394-404` já usa assim.)

- [ ] **Step 2: Rodar e ver falhar**

Run: `uv run pytest tests/test_medicoes_manuais.py -v`
Expected: FAIL com `ImportError: cannot import name 'MedicaoInvalida'`.

- [ ] **Step 3: Implementar** (em `app/services/medicoes_repo.py`; acrescente `from . import indices_repo` aos imports)

```python
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
            achado = _MES_RE.match(str(valor or ""))
            if not achado:
                erros.append("mes: mês inválido; use AAAA-MM.")
                continue
            colunas["mes_medicao"] = date(int(achado[1]), int(achado[2]), 1)
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
            if valor in (None, ""):
                colunas[campo] = None
                continue
            grafia = indices_repo.normalizar_regiao(str(valor))
            if grafia is None:
                erros.append(
                    f"{campo}: região {valor!r} sem preços ANP do CAP 50/70; "
                    "escolha uma das regiões importadas."
                )
                continue
            colunas[campo] = grafia
    if erros:
        raise MedicaoInvalida("\n".join(erros))
    return colunas


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
            "SELECT origem FROM medicao_item "
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
    with acquire_sync() as conn:
        cur = conn.execute(
            "DELETE FROM medicao_item "
            "WHERE contrato_id = %s AND id = %s AND origem = 'manual'",
            (contrato_id, item_id),
        )
        if cur.rowcount:
            return True
        cur = conn.execute(
            "UPDATE medicao_item SET excluido = true, atualizado_em = now() "
            "WHERE contrato_id = %s AND id = %s AND NOT excluido",
            (contrato_id, item_id),
        )
        return cur.rowcount > 0
```

As colunas usadas no `f-string` vêm de `_validar`, que só devolve nomes fixos do código, nunca texto do usuário.

- [ ] **Step 4: Rodar os testes**

Run: `uv run pytest tests/test_medicoes_manuais.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/services/medicoes_repo.py tests/test_medicoes_manuais.py
git commit -m "feat(backend): inclui, altera e exclui um registro de medição"
```

---

### Task 3: Região por item no cálculo do ΔP e na agregação

**Files:**
- Modify: `app/services/reequilibrio_export.py` (`Linha`, `montar_grupos`, `_deltas`, `calcular`, `calcular_deltas`, `serializar`)
- Modify: `app/dashboard/data_loader.py` **somente se** ele chamar `montar_grupos`/`calcular_deltas` diretamente (rode `grep -n "montar_grupos\|calcular_deltas" app/dashboard/*.py`; se chamar, troque para a mesma anotação `_anotar_regioes` descrita abaixo, porque o dashboard está congelado mas precisa continuar funcionando)
- Test: `tests/test_reequilibrio_export.py`

**Interfaces:**
- Consumes: os campos `id`, `origem`, `regiao_cap` e `regiao_emulsoes` de `itens_para_export` (Task 1).
- Produces:
  - `Linha.regiao_manual: str | None = None`
  - a chave de `deltas` passa a ser `(familia, mes, regiao)`
  - `_anotar_regioes(itens, regioes) -> None` grava em cada item `regiao` (a efetiva) e `regiao_manual`
  - `serializar` passa a emitir `"regiao_manual"` em cada linha.

- [ ] **Step 1: Atualizar os testes de `montar_grupos` e escrever os novos**

Em `tests/test_reequilibrio_export.py`, os três testes de `montar_grupos` (linhas 207-245) usam `deltas = {(FAMILIA_CAP, date(2023, 1, 1)): …}`. Troque essa chave para `(FAMILIA_CAP, date(2023, 1, 1), None)` (o item sem `regiao` tem chave com `None`). Depois acrescente:

```python
async def test_regiao_manual_vira_linha_separada():
    mes = date(2023, 1, 1)
    deltas = {(FAMILIA_CAP, mes, "Nordeste"): Decimal("-0.07"),
              (FAMILIA_CAP, mes, "Sul"): Decimal("-0.19")}
    comum = {**_item("CAP", FAMILIA_CAP, "60112", mes, "100.00"), "regiao": "Nordeste"}
    fixado = {**_item("CAP", FAMILIA_CAP, "92704", mes, "50.00"), "regiao": "Sul",
              "regiao_manual": "Sul"}
    grupos, _ = montar_grupos([comum, fixado], deltas)
    linhas = grupos[0].linhas
    assert [(l.valor_pi, l.delta_p, l.regiao_manual) for l in linhas] == [
        (Decimal("100.00"), Decimal("-0.07"), None),
        (Decimal("50.00"), Decimal("-0.19"), "Sul"),
    ]


async def test_registro_manual_nao_e_descartado_como_repeticao():
    mes = date(2023, 1, 1)
    deltas = {(FAMILIA_CAP, mes, None): Decimal("-0.07")}
    do_pdf = {**_item("CAP", FAMILIA_CAP, "60112", mes, "100.00"), "id": 1, "origem": "pdf"}
    manual = {**_item("CAP", FAMILIA_CAP, "60112", mes, "5.00"), "id": 2, "origem": "manual"}
    grupos, descartadas = montar_grupos([do_pdf, manual], deltas)
    assert descartadas == 0
    assert [l.valor_pi for l in grupos[0].linhas] == [Decimal("105.00")]


def _fixar_regiao(regiao):
    contrato = contratos_repo.buscar("15 00716/2022")
    [item] = medicoes_repo.listar_itens(contrato["id"])
    medicoes_repo.atualizar_item(contrato["id"], item["id"], {"regiao_cap": regiao})
    return contrato


async def test_regiao_do_item_prevalece_sobre_cadastro_e_simulacao():
    await _contrato_com_medicoes()
    _indices_para_fevereiro()
    contrato = _fixar_regiao("Sul")  # cadastro: Nordeste
    sul = Decimal("3.45") / Decimal("4.29019") - 1

    for override in (None, {"CAP": "Nordeste"}):
        calculo = reequilibrio_export.calcular(contrato, override)
        [linha] = calculo.grupos[0].linhas
        assert linha.regiao_manual == "Sul"
        assert abs(linha.delta_p - sul) < Decimal("1e-20")
    assert any("região própria" in a for a in calculo.avisos)
    assert reequilibrio_export.serializar(calculo)["familias"][0]["produtos"][0][
        "linhas"][0]["regiao_manual"] == "Sul"


async def test_regiao_manual_sem_indice_aparece_em_faltando():
    await _contrato_com_medicoes()
    _indices_para_fevereiro()
    indices_repo.gravar_precos_anp([semana(date(2023, 1, 9), "3.1", regiao="Norte")])
    contrato = _fixar_regiao("Norte")  # Norte não tem a semana-base de dez/2021
    with pytest.raises(ExportacaoImpossivel) as erro:
        reequilibrio_export.calcular(contrato)
    assert any("Norte" in f for f in erro.value.faltando)
```

Garanta que `medicoes_repo`, `indices_repo` e `semana` estejam importados no topo do arquivo de teste (provavelmente já estão; confira as linhas 1-50).

- [ ] **Step 2: Rodar e ver falhar**

Run: `uv run pytest tests/test_reequilibrio_export.py -v`
Expected: FAIL (`KeyError` na chave de `deltas` e `Linha` sem o atributo `regiao_manual`).

- [ ] **Step 3: Implementar**

`Linha` ganha um campo novo:

```python
    delta_p: Decimal
    # A região fixada no registro, quando difere da família (None = segue o
    # contrato ou a simulação). Faz a linha separada, marcada com '*'.
    regiao_manual: str | None = None
```

Uma nova função, antes de `_deltas`:

```python
def _anotar_regioes(itens: list[dict], regioes: dict) -> None:
    """A região de cada item: a fixada no registro vence a da família
    (cadastro ou simulação). Grava ``regiao`` e ``regiao_manual`` no item."""
    for item in itens:
        manual = item.get(f"regiao_{item['familia'].lower()}")
        item["regiao_manual"] = manual
        item["regiao"] = manual or regioes.get(item["familia"])
```

Em `montar_grupos`, troque o tipo de `deltas` para `dict[tuple[str, date, str | None], Decimal]` e altere três pontos:

```python
    for item in itens:
        # Um registro manual é deliberado, não um PDF reenviado com outro nome.
        if item.get("origem") == "manual":
            por_codigo[("manual", item["id"])] = item
            continue
        chave = (item["descricao_export"], item["codigo_servico"], item["mes_medicao"])
        ...
    acumulado: dict[tuple[date, Decimal, str | None, str | None], Decimal] = {}

    def fechar() -> None:
        if atual is None:
            return
        for (mes, fator, regiao, manual), valor in sorted(
            acumulado.items(), key=lambda kv: (kv[0][0], kv[0][1], kv[0][3] or "")
        ):
            atual.linhas.append(
                Linha(mes=mes, valor_pi=valor, fator=fator,
                      delta_p=deltas[(atual.familia, mes, regiao)], regiao_manual=manual)
            )
        ...
        chave = (item["mes_medicao"], item["fator"], item.get("regiao"), item.get("regiao_manual"))
```

Atualize o docstring de `montar_grupos` com uma frase: "Items with a region of their own (``regiao_manual``) keep separate rows: their ΔP differs."

Em `_deltas`, a chave e a região passam a ser as do item:

```python
    deltas: dict[tuple[str, date, str | None], Decimal] = {}
    processados: set[tuple[str, date, str | None]] = set()

    for item in itens:
        chave = (item["familia"], item["mes_medicao"], item.get("regiao"))
        if chave in processados:
            continue
        processados.add(chave)
        familia, mes_medicao, regiao = chave

        if not regiao:
            ...  # mesma mensagem regiao_<familia> de hoje
```

Ajuste também o docstring ("ΔP por (família, mês, região)…") e remova a linha `regiao = regioes.get(familia)`.

Em `calcular_deltas` e em `calcular`, chame `_anotar_regioes(itens, regioes)` antes de `_deltas(...)`. Em `calcular`, depois do aviso de descartadas:

```python
    proprias = sum(1 for i in itens if i.get("regiao_manual"))
    if proprias:
        avisos.append(
            f"{proprias} registro(s) com região própria: calculados pela região do "
            "registro, não pela do contrato nem pela simulação."
        )
```

(O texto é latin-1 seguro, porque vai para `X-Avisos`.)

Em `serializar`, a linha passa a ser:

```python
            linhas.append({"mes": linha.mes, "a": linha.valor_pi, "fator": linha.fator,
                           "b": b, "d": linha.delta_p, "c": c, "e": e, "f": f,
                           "regiao_manual": linha.regiao_manual})
```

- [ ] **Step 4: Rodar os testes**

Run: `uv run pytest tests/test_reequilibrio_export.py tests/test_api_calculo.py tests/test_e2e_reequilibrio.py tests/test_dashboard.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/services/reequilibrio_export.py tests/test_reequilibrio_export.py app/dashboard/data_loader.py
git commit -m "feat(backend): calcula o ΔP pela região fixada no registro de medição"
```

---

### Task 4: Marcação `*`, cor e nota na planilha

**Files:**
- Modify: `app/services/reequilibrio_layout.py`
- Modify: `app/services/reequilibrio_export.py` (`_escrever_tabela`, `gerar_planilha`)
- Test: `tests/test_reequilibrio_export.py`

**Interfaces:**
- Consumes: `Linha.regiao_manual`, `Grupo.familia` e `ROTULOS_FAMILIA` (`catalogo.py`).
- Produces: as constantes `COR_REGIAO_MANUAL`, `MARCA_REGIAO_MANUAL` e `NOTA_REGIAO_MANUAL` em `reequilibrio_layout.py`.

- [ ] **Step 1: Escrever o teste que falha**

```python
async def test_linha_com_regiao_manual_e_marcada_na_planilha(template):
    grupos = [
        Grupo("Aquisição de CAP 50/70", FAMILIA_CAP, [
            Linha(date(2023, 2, 1), Decimal("100"), Decimal("-0.18"), Decimal("-0.07")),
            Linha(date(2023, 2, 1), Decimal("50"), Decimal("-0.18"), Decimal("-0.19"), "Sul"),
        ])
    ]
    contrato = {"numero": "15 00716/2022", "data_base": date(2022, 1, 1)}
    ws = _aba(gerar_planilha(contrato, grupos, template))

    comum, marcada = PRIMEIRA_LINHA + 1, PRIMEIRA_LINHA + 2
    assert ws.cell(comum, COL_DESCRICAO).value == f"=B{PRIMEIRA_LINHA}"
    assert ws.cell(marcada, COL_DESCRICAO).value == f'=B{PRIMEIRA_LINHA}&" *"'
    assert ws.cell(marcada, COL_MES).fill.fgColor.rgb.endswith(COR_REGIAO_MANUAL)
    assert not ws.cell(comum, COL_MES).fill.fgColor.rgb.endswith(COR_REGIAO_MANUAL)
    assert ws.cell(marcada, COL_REAJUSTAMENTO).value == f"=TRUNC(E{marcada}*D{marcada},2)"

    textos = [ws.cell(r, COL_INICIO).value for r in range(marcada, ws.max_row + 1)]
    assert "* Região ANP definida no registro: CAP — Sul" in textos


async def test_sem_regiao_manual_nao_ha_nota(template):
    ws = _aba(gerar_planilha({"numero": "x", "data_base": date(2022, 1, 1)}, _grupos(), template))
    textos = [str(ws.cell(r, COL_INICIO).value or "") for r in range(PRIMEIRA_LINHA, ws.max_row + 1)]
    assert not any(t.startswith("*") for t in textos)
```

Importe no teste `Grupo`, `Linha` e `gerar_planilha` de `reequilibrio_export`, e `COR_REGIAO_MANUAL`, `PRIMEIRA_LINHA`, `COL_DESCRICAO`, `COL_MES`, `COL_REAJUSTAMENTO` e `COL_INICIO` de `reequilibrio_layout`. O rótulo de família usado na nota vem de `ROTULOS_FAMILIA`; se para `CAP` ele não for `"CAP"`, ajuste o texto esperado ao valor real (`grep -n ROTULOS_FAMILIA -A4 app/services/catalogo.py`).

- [ ] **Step 2: Rodar e ver falhar**

Run: `uv run pytest tests/test_reequilibrio_export.py -k "regiao_manual or nao_ha_nota" -v`
Expected: FAIL com `ImportError: COR_REGIAO_MANUAL`.

- [ ] **Step 3: Implementar**

Em `reequilibrio_layout.py`, depois das colunas:

```python
# Linha calculada com a região fixada no registro de medição, e não com a do
# contrato: '*' na descrição, fundo nesta cor e uma nota abaixo do total.
MARCA_REGIAO_MANUAL = " *"
COR_REGIAO_MANUAL = "FFF2CC"
NOTA_REGIAO_MANUAL = "* Região ANP definida no registro: {familia} — {regiao}"
```

Em `reequilibrio_export.py`: importe `PatternFill` de `openpyxl.styles` e as três constantes. Em `_escrever_tabela`, dentro do laço das linhas:

```python
            descricao = f"=B{linha_grupo}"
            if item.regiao_manual:
                descricao += f'&"{MARCA_REGIAO_MANUAL}"'
            ws.cell(linha, COL_DESCRICAO).value = descricao
            ...  # demais colunas como hoje
            if item.regiao_manual:
                for col in range(COL_INICIO, COL_FIM + 1):
                    ws.cell(linha, col).fill = PatternFill(
                        "solid", fgColor=COR_REGIAO_MANUAL
                    )
                notas.setdefault(
                    (grupo.familia, item.regiao_manual), None
                )
```

com `notas: dict[tuple[str, str], None] = {}` declarado no início da função (um dict, para manter a ordem e eliminar repetições). Depois da linha do total:

```python
    for deslocamento, (familia, regiao) in enumerate(notas, start=2):
        ws.cell(linha + deslocamento, COL_INICIO).value = NOTA_REGIAO_MANUAL.format(
            familia=ROTULOS_FAMILIA.get(familia, familia), regiao=regiao
        )
```

- [ ] **Step 4: Rodar os testes**

Run: `uv run pytest tests/test_reequilibrio_export.py tests/test_template_repo.py -v`
Expected: PASS. Os testes de formatação das linhas-modelo e de memória de cálculo continuam passando.

- [ ] **Step 5: Commit**

```bash
git add app/services/reequilibrio_layout.py app/services/reequilibrio_export.py tests/test_reequilibrio_export.py
git commit -m "feat(backend): marca na planilha as linhas com região própria"
```

---

### Task 5: Endpoints da API

**Files:**
- Modify: `app/routers/api/schemas.py`
- Modify: `app/routers/api/contratos.py`
- Test: `tests/test_api_medicoes.py`

**Interfaces:**
- Consumes: `medicoes_repo.incluir_item`, `atualizar_item`, `excluir_item`, `buscar_item` e `MedicaoInvalida` (Task 2).
- Produces:
  - `POST /api/v1/contratos/{id}/medicoes` → 201 `ItemMedicao`
  - `PATCH /api/v1/contratos/{id}/medicoes/{item_id}` → 200 `ItemMedicao`
  - `DELETE /api/v1/contratos/{id}/medicoes/{item_id}` → 204
  - `ItemMedicao` ganha `origem: Literal["pdf","editado","manual"]`, `regiao_cap: str | None` e `regiao_emulsoes: str | None`
  - `LinhaCalculo` ganha `regiao_manual: str | None = None`.

- [ ] **Step 1: Escrever os testes que falham** (em `tests/test_api_medicoes.py`)

```python
from datetime import date

from app.services import indices_repo
from tests.indices_factory import semana

NOVO = {"mes": "2023-02", "codigo": "60112", "descricao_pdf": "CAP manual",
        "valor_pi": "100.00", "fator": "0.148"}


async def test_incluir_alterar_e_excluir_um_registro(client):
    indices_repo.gravar_precos_anp([semana(date(2023, 1, 9), "3.45", regiao="Sul")])
    contrato_id = _contrato()
    base = f"/api/v1/contratos/{contrato_id}/medicoes"

    criado = await client.post(base, json={**NOVO, "regiao_cap": "sul"})
    assert criado.status_code == 201, criado.text
    item = criado.json()
    assert item["origem"] == "manual" and item["regiao_cap"] == "Sul"
    assert item["valor_pi"] == "100.00" and item["produto"] == "Aquisição de CAP 50/70"

    alterado = await client.patch(f"{base}/{item['id']}", json={"fator": "0.2"})
    assert alterado.status_code == 200 and alterado.json()["fator"] == "0.2"

    assert (await client.delete(f"{base}/{item['id']}")).status_code == 204
    assert len(await _medicoes(client, contrato_id)) == 3


async def test_regiao_invalida_e_422_com_texto(client):
    contrato_id = _contrato()
    resposta = await client.post(f"/api/v1/contratos/{contrato_id}/medicoes",
                                 json={**NOVO, "regiao_cap": "Marte"})
    assert resposta.status_code == 422
    assert "regiao_cap" in resposta.json()["detail"]


async def test_corpo_malformado_e_422_do_pydantic(client):
    contrato_id = _contrato()
    resposta = await client.post(f"/api/v1/contratos/{contrato_id}/medicoes",
                                 json={**NOVO, "mes": "2023-13"})
    assert resposta.status_code == 422 and isinstance(resposta.json()["detail"], list)


async def test_contrato_ou_item_inexistente_e_404(client):
    contrato_id = _contrato()
    assert (await client.post("/api/v1/contratos/999/medicoes", json=NOVO)).status_code == 404
    base = f"/api/v1/contratos/{contrato_id}/medicoes"
    assert (await client.patch(f"{base}/999999", json={"fator": "1"})).status_code == 404
    assert (await client.delete(f"{base}/999999")).status_code == 404


async def test_lista_traz_origem_e_regioes(client):
    contrato_id = _contrato()
    [item, *_] = await _medicoes(client, contrato_id)
    assert item["origem"] == "pdf"
    assert item["regiao_cap"] is None and item["regiao_emulsoes"] is None
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `uv run pytest tests/test_api_medicoes.py -v`
Expected: FAIL com 405 Method Not Allowed.

- [ ] **Step 3: Implementar**

`schemas.py`: acrescente `from .erros import MES` (se der import circular, copie a constante com um comentário apontando a origem) e:

```python
class ItemMedicao(BaseModel):
    ...  # campos de hoje
    origem: Literal["pdf", "editado", "manual"]
    regiao_cap: str | None
    regiao_emulsoes: str | None


class MedicaoNova(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mes: Annotated[str, StringConstraints(pattern=MES)]
    codigo: Annotated[str, StringConstraints(pattern=CODIGO_SERVICO)]
    descricao_pdf: str | None = None
    valor_pi: Decimal
    fator: Decimal
    regiao_cap: str | None = None
    regiao_emulsoes: str | None = None


class MedicaoPatch(BaseModel):
    """Só os campos enviados são gravados (``exclude_unset``)."""

    model_config = ConfigDict(extra="forbid")

    mes: Annotated[str, StringConstraints(pattern=MES)] | None = None
    codigo: Annotated[str, StringConstraints(pattern=CODIGO_SERVICO)] | None = None
    descricao_pdf: str | None = None
    valor_pi: Decimal | None = None
    fator: Decimal | None = None
    regiao_cap: str | None = None
    regiao_emulsoes: str | None = None
```

Em `LinhaCalculo`, acrescente `regiao_manual: str | None = None`.

`contratos.py` (importe `Response` de `fastapi` e `MedicaoNova`/`MedicaoPatch` de `.schemas`):

```python
def _item(contrato_id: int, item_id: int) -> dict:
    item = medicoes_repo.buscar_item(contrato_id, item_id)
    if item is None:
        raise ErroApi(404, f"Registro {item_id} não encontrado neste contrato.")
    return item


def _incluir(contrato_id: int, dados: dict) -> dict:
    try:
        item_id = medicoes_repo.incluir_item(contrato_id, dados)
    except medicoes_repo.MedicaoInvalida as e:
        raise ErroApi(422, str(e)) from e
    if item_id is None:
        raise ErroApi(404, f"Contrato {contrato_id} não encontrado.")
    return _item(contrato_id, item_id)


def _alterar(contrato_id: int, item_id: int, dados: dict) -> dict:
    try:
        existe = medicoes_repo.atualizar_item(contrato_id, item_id, dados)
    except medicoes_repo.MedicaoInvalida as e:
        raise ErroApi(422, str(e)) from e
    if not existe:
        raise ErroApi(404, f"Registro {item_id} não encontrado neste contrato.")
    return _item(contrato_id, item_id)


def _excluir(contrato_id: int, item_id: int) -> None:
    if not medicoes_repo.excluir_item(contrato_id, item_id):
        raise ErroApi(404, f"Registro {item_id} não encontrado neste contrato.")


@router.post("/{contrato_id}/medicoes", response_model=ItemMedicao, status_code=201)
async def incluir_medicao(contrato_id: int, novo: MedicaoNova):
    return await asyncio.to_thread(_incluir, contrato_id, novo.model_dump())


@router.patch("/{contrato_id}/medicoes/{item_id}", response_model=ItemMedicao)
async def alterar_medicao(contrato_id: int, item_id: int, patch: MedicaoPatch):
    return await asyncio.to_thread(
        _alterar, contrato_id, item_id, patch.model_dump(exclude_unset=True)
    )


@router.delete("/{contrato_id}/medicoes/{item_id}", status_code=204)
async def excluir_medicao(contrato_id: int, item_id: int):
    await asyncio.to_thread(_excluir, contrato_id, item_id)
    return Response(status_code=204)
```

`model_dump()` devolve `Decimal`, que `_validar` aceita através de `_decimal(str(...))`.

- [ ] **Step 4: Rodar os testes**

Run: `uv run pytest tests/test_api_medicoes.py tests/test_api_calculo.py tests/test_api_adicoes_frontend.py -v`
Expected: PASS.

- [ ] **Step 5: Rodar a suíte inteira do backend**

Run: `uv run pytest -q`
Expected: tudo PASS (os testes de backup podem ser pulados sem `pg_dump`).

- [ ] **Step 6: Commit**

```bash
git add app/routers/api/schemas.py app/routers/api/contratos.py tests/test_api_medicoes.py
git commit -m "feat(api): endpoints para incluir, alterar e excluir um registro de medição"
```

---

### Task 6: Aba *Medições* com inclusão, edição e exclusão

**Files:**
- Modify: `frontend/src/api/tipos.ts`, `frontend/src/api/contratos.ts`, `frontend/src/api/invalidar.ts`
- Create: `frontend/src/pages/contrato/DialogoMedicao.tsx`
- Create: `frontend/src/pages/contrato/medicao.ts` (valores do formulário e montagem do corpo, sem JSX)
- Modify: `frontend/src/pages/contrato/AbaMedicoes.tsx`
- Modify: `frontend/src/styles/telas.css` (somente se precisar de classe nova; reaproveite `field`, `input`, `btn`, `badge`, `erro-campo`)
- Test: `frontend/tests/medicoes.test.tsx`

**Interfaces:**
- Consumes: a API da Task 5; `pedir` (`api/client.ts`); `ErroApi.campos` (`api/erros.ts`); `paraDecimal` e `exato` (`lib/formato.ts`); `CampoMesAno`, `Dialogo`, `ConfirmarDialogo` e `MensagemErro`; `buscarCobertura` e `chaves.cobertura`.
- Produces:
  - `incluirMedicao(id, corpo): Promise<ItemMedicao>`
  - `alterarMedicao(id, itemId, corpo): Promise<ItemMedicao>`
  - `excluirMedicao(id, itemId): Promise<void>`
  - `aposMedicao(qc, contratoId)`
  - os tipos `MedicaoCorpo` e `OrigemMedicao`.

- [ ] **Step 1: Escrever os testes que falham** (em `frontend/tests/medicoes.test.tsx`; acrescente a `umItem` os campos `origem: 'pdf', regiao_cap: null, regiao_emulsoes: null`)

```tsx
import { umaCobertura } from './fabricas'

function prepararEdicao(itens: ItemMedicao[]) {
  const corpos: unknown[] = []
  preparar(itens)
  servidor.use(
    http.get('/api/v1/indices/cobertura', () => HttpResponse.json(umaCobertura())),
    http.post('/api/v1/contratos/1/medicoes', async ({ request }) => {
      corpos.push(await request.json())
      return HttpResponse.json(umItem({ id: 9, origem: 'manual' }), { status: 201 })
    }),
    http.patch('/api/v1/contratos/1/medicoes/:item', async ({ request }) => {
      corpos.push(await request.json())
      return HttpResponse.json(umItem({ origem: 'editado', regiao_cap: 'Sul' }))
    }),
    http.delete('/api/v1/contratos/1/medicoes/:item', () => new HttpResponse(null, { status: 204 })),
  )
  return corpos
}

it('inclui um registro manual com a digitação brasileira', async () => {
  const corpos = prepararEdicao([umItem()])
  const { usuario } = renderApp('/contratos/1/medicoes')
  await usuario.click(await screen.findByRole('button', { name: /Incluir registro/ }))
  const dialogo = screen.getByRole('dialog')
  await usuario.selectOptions(within(dialogo).getByLabelText('Mês'), '02')
  await usuario.type(within(dialogo).getByLabelText('Ano'), '2023')
  await usuario.type(within(dialogo).getByLabelText('Código'), '60112')
  await usuario.type(within(dialogo).getByLabelText('Valor PI líquido'), '1.234,56')
  await usuario.type(within(dialogo).getByLabelText('Fator'), '0,148')
  await usuario.click(within(dialogo).getByRole('button', { name: 'Salvar' }))
  await waitFor(() => expect(corpos).toEqual([
    { mes: '2023-02', codigo: '60112', descricao_pdf: null, valor_pi: '1234.56',
      fator: '0.148', regiao_cap: null, regiao_emulsoes: null },
  ]))
})

it('em registro do PDF, envia só o que mudou e trava código e mês', async () => {
  const corpos = prepararEdicao([umItem()])
  const { usuario } = renderApp('/contratos/1/medicoes')
  const linha = (await screen.findByText('60112')).closest('tr')!
  await usuario.click(within(linha).getByRole('button', { name: /Editar/ }))
  const dialogo = screen.getByRole('dialog')
  expect(within(dialogo).getByLabelText('Código')).toBeDisabled()
  await usuario.selectOptions(within(dialogo).getByLabelText('Região ANP — CAP'), 'Sul')
  await usuario.click(within(dialogo).getByRole('button', { name: 'Salvar' }))
  await waitFor(() => expect(corpos).toEqual([{ regiao_cap: 'Sul' }]))
})

it('mostra no campo o erro 422 do backend', async () => {
  prepararEdicao([umItem()])
  servidor.use(
    http.patch('/api/v1/contratos/1/medicoes/:item', () =>
      HttpResponse.json({ detail: 'fator: informe um número.' }, { status: 422 })),
  )
  const { usuario } = renderApp('/contratos/1/medicoes')
  const linha = (await screen.findByText('60112')).closest('tr')!
  await usuario.click(within(linha).getByRole('button', { name: /Editar/ }))
  const dialogo = screen.getByRole('dialog')
  await usuario.clear(within(dialogo).getByLabelText('Fator'))
  await usuario.type(within(dialogo).getByLabelText('Fator'), '2')
  await usuario.click(within(dialogo).getByRole('button', { name: 'Salvar' }))
  expect(await within(dialogo).findByText('fator: informe um número.')).toBeInTheDocument()
  expect(within(dialogo).getByLabelText('Fator')).toHaveAttribute('aria-invalid', 'true')
})

it('exclui só depois de confirmar', async () => {
  prepararEdicao([umItem()])
  let excluiu = false
  servidor.use(http.delete('/api/v1/contratos/1/medicoes/1', () => {
    excluiu = true
    return new HttpResponse(null, { status: 204 })
  }))
  const { usuario } = renderApp('/contratos/1/medicoes')
  const linha = (await screen.findByText('60112')).closest('tr')!
  await usuario.click(within(linha).getByRole('button', { name: /Excluir/ }))
  expect(excluiu).toBe(false)
  await usuario.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Excluir registro' }))
  await waitFor(() => expect(excluiu).toBe(true))
})

it('marca origem e região própria na lista', async () => {
  prepararEdicao([umItem({ origem: 'editado', regiao_cap: 'Sul' })])
  renderApp('/contratos/1/medicoes')
  const linha = (await screen.findByText('60112')).closest('tr')!
  expect(within(linha).getByText('editado')).toBeInTheDocument()
  expect(within(linha).getByText('CAP: Sul *')).toBeInTheDocument()
})
```

Os rótulos 'Mês' e 'Ano' dependem de como o `CampoMesAno` rotula os seus dois campos. Confira em `frontend/tests/cadastro.test.tsx` como o teste do cadastro preenche a Data Base e use exatamente o mesmo caminho. Importe `waitFor` de `@testing-library/react`.

- [ ] **Step 2: Rodar e ver falhar**

Run: `cd frontend && npm run test -- medicoes`
Expected: FAIL (o botão 'Incluir registro' não existe).

- [ ] **Step 3: Camada de API**

`tipos.ts`:

```ts
export type OrigemMedicao = 'pdf' | 'editado' | 'manual'

export interface ItemMedicao {
  ...  // campos de hoje
  origem: OrigemMedicao
  regiao_cap: string | null
  regiao_emulsoes: string | null
}

// Corpo de POST (completo) e PATCH (só o que mudou). Decimal em texto, com ponto.
export interface MedicaoCorpo {
  mes?: string
  codigo?: string
  descricao_pdf?: string | null
  valor_pi?: Decimal
  fator?: Decimal
  regiao_cap?: string | null
  regiao_emulsoes?: string | null
}
```

e, em `LinhaCalculo`, `regiao_manual: string | null`.

`contratos.ts`:

```ts
export const incluirMedicao = (id: number, corpo: MedicaoCorpo) =>
  pedir<ItemMedicao>(`${BASE}/${id}/medicoes`, { metodo: 'POST', json: corpo })

export const alterarMedicao = (id: number, itemId: number, corpo: MedicaoCorpo) =>
  pedir<ItemMedicao>(`${BASE}/${id}/medicoes/${itemId}`, { metodo: 'PATCH', json: corpo })

export const excluirMedicao = (id: number, itemId: number) =>
  pedir<void>(`${BASE}/${id}/medicoes/${itemId}`, { metodo: 'DELETE' })
```

`invalidar.ts`:

```ts
// Registro de medição incluído, alterado ou excluído: muda a lista, as
// contagens do contrato e o cálculo.
export function aposMedicao(qc: QueryClient, contratoId: number) {
  return Promise.all([
    qc.invalidateQueries({ queryKey: chaves.todasMedicoes }),
    qc.invalidateQueries({ queryKey: chaves.contrato(contratoId) }),
    qc.invalidateQueries({ queryKey: chaves.contratos }),
    qc.invalidateQueries({ queryKey: chaves.calculos }),
  ])
}
```

- [ ] **Step 4: `medicao.ts` (formulário ↔ corpo)**

```ts
import type { ItemMedicao, MedicaoCorpo } from '../../api/tipos'
import { exato, paraDecimal } from '../../lib/formato'

// O formulário do registro como strings, na digitação brasileira.
export interface ValoresMedicao {
  mes: string // AAAA-MM, de CampoMesAno
  codigo: string
  descricao_pdf: string
  valor_pi: string
  fator: string
  regiao_cap: string // '' = segue o contrato
  regiao_emulsoes: string
}

export type CampoMedicao = keyof ValoresMedicao

export function valoresIniciais(item?: ItemMedicao): ValoresMedicao {
  if (!item) return { mes: '', codigo: '', descricao_pdf: '', valor_pi: '', fator: '', regiao_cap: '', regiao_emulsoes: '' }
  return {
    mes: item.mes.slice(0, 7),
    codigo: item.codigo,
    descricao_pdf: item.descricao_pdf ?? '',
    valor_pi: exato(item.valor_pi).replace(/\./g, ''),
    fator: exato(item.fator).replace(/\./g, ''),
    regiao_cap: item.regiao_cap ?? '',
    regiao_emulsoes: item.regiao_emulsoes ?? '',
  }
}

// Inclusão manda tudo; edição, só os campos sujos.
export function montarCorpo(v: ValoresMedicao, sujos?: Partial<Record<CampoMedicao, unknown>>): MedicaoCorpo {
  const todos: MedicaoCorpo = {
    mes: v.mes,
    codigo: v.codigo.trim(),
    descricao_pdf: v.descricao_pdf.trim() || null,
    valor_pi: paraDecimal(v.valor_pi) ?? v.valor_pi,
    fator: paraDecimal(v.fator) ?? v.fator,
    regiao_cap: v.regiao_cap || null,
    regiao_emulsoes: v.regiao_emulsoes || null,
  }
  if (!sujos) return todos
  return Object.fromEntries(Object.entries(todos).filter(([campo]) => sujos[campo as CampoMedicao])) as MedicaoCorpo
}

// O 422 do backend vem em texto "campo: mensagem" por linha; cada linha vai
// para o seu campo, e o resto para a mensagem geral.
export function errosPorCampo(detail: string): Partial<Record<CampoMedicao | 'geral', string>> {
  const saida: Partial<Record<CampoMedicao | 'geral', string>> = {}
  for (const linha of detail.split('\n')) {
    const campo = linha.split(':')[0].trim() as CampoMedicao
    const chave = campo in valoresIniciais() ? campo : 'geral'
    saida[chave] = saida[chave] ? `${saida[chave]}\n${linha}` : linha
  }
  return saida
}
```

Confira a assinatura de `paraDecimal` em `lib/formato.ts`, que pode devolver `null` ou lançar erro para entrada ilegível, e ajuste o `?? v.x`. Se devolver `null` para entrada ilegível, valide antes de enviar e use `setError` com uma mensagem do frontend ("Número ilegível."), como o cadastro faz com a extensão. O `campoDoErro` de `cadastro.ts` resolve o mesmo problema para o cadastro: leia-o e, se ele já fizer essa separação de forma genérica, reaproveite-o em vez de `errosPorCampo`.

- [ ] **Step 5: `DialogoMedicao.tsx`**

```tsx
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Controller, useForm } from 'react-hook-form'
import { chaves } from '../../api/chaves'
import { alterarMedicao, incluirMedicao } from '../../api/contratos'
import { ErroApi } from '../../api/erros'
import { buscarCobertura } from '../../api/indices'
import { aposMedicao } from '../../api/invalidar'
import type { ItemMedicao } from '../../api/tipos'
import { CampoMesAno } from '../../components/CampoMesAno'
import { Dialogo } from '../../components/Dialogo'
import { MensagemErro } from '../../components/MensagemErro'
import { errosPorCampo, montarCorpo, valoresIniciais, type CampoMedicao, type ValoresMedicao } from './medicao'

interface Props {
  contratoId: number
  item?: ItemMedicao // ausente = inclusão
  aoFechar: () => void
}

// Inclusão e edição de um registro. Num registro do PDF, código e mês ficam
// travados: são a chave com que o reprocessamento o reencontra.
export function DialogoMedicao({ contratoId, item, aoFechar }: Props) {
  const qc = useQueryClient()
  const [erroGeral, setErroGeral] = useState<unknown>(null)
  const cobertura = useQuery({ queryKey: chaves.cobertura, queryFn: buscarCobertura })
  const { control, register, handleSubmit, setError, formState } = useForm<ValoresMedicao>({
    defaultValues: valoresIniciais(item),
  })
  const travado = item !== undefined && item.origem !== 'manual'
  const regioes = cobertura.data?.regioes ?? []

  const salvar = useMutation({
    mutationFn: (v: ValoresMedicao) =>
      item
        ? alterarMedicao(contratoId, item.id, montarCorpo(v, formState.dirtyFields))
        : incluirMedicao(contratoId, montarCorpo(v)),
    onSuccess: async () => {
      await aposMedicao(qc, contratoId)
      aoFechar()
    },
    onError: (erro) => {
      if (!(erro instanceof ErroApi) || Object.keys(erro.campos).length) return setErroGeral(erro)
      for (const [campo, msg] of Object.entries(errosPorCampo(erro.detail))) {
        if (campo === 'geral') setErroGeral(new ErroApi(erro.status, msg!))
        else setError(campo as CampoMedicao, { type: 'servidor', message: msg })
      }
    },
  })

  function erro(campo: CampoMedicao) {
    const msg = formState.errors[campo]?.message
    return msg ? <p className="erro-campo" id={`erro-medicao-${campo}`}>{msg}</p> : null
  }
  function aria(campo: CampoMedicao) {
    const tem = Boolean(formState.errors[campo])
    return { 'aria-invalid': tem || undefined, 'aria-describedby': tem ? `erro-medicao-${campo}` : undefined }
  }

  return (
    <Dialogo
      titulo={item ? 'Editar registro' : 'Incluir registro'}
      aoFechar={aoFechar}
      acoes={
        <>
          <button type="button" className="btn" onClick={aoFechar}>Cancelar</button>
          <button type="submit" form="form-medicao" className="btn btn-primary" disabled={salvar.isPending}>
            Salvar
          </button>
        </>
      }
    >
      <form id="form-medicao" onSubmit={handleSubmit((v) => salvar.mutate(v))}>
        <MensagemErro erro={erroGeral} />
        <div className="field">
          <label className="field-label" htmlFor="medicao-mes">Mês da medição</label>
          <Controller
            name="mes"
            control={control}
            render={({ field }) => (
              <CampoMesAno id="medicao-mes" valor={field.value} aoMudar={field.onChange}
                invalido={Boolean(formState.errors.mes)} />
            )}
          />
          {erro('mes')}
        </div>
        <div className="field">
          <label className="field-label" htmlFor="medicao-codigo">Código</label>
          <input id="medicao-codigo" className="input" disabled={travado} {...register('codigo')} {...aria('codigo')} />
          {erro('codigo')}
        </div>
        <div className="field">
          <label className="field-label" htmlFor="medicao-descricao">Descrição</label>
          <input id="medicao-descricao" className="input" {...register('descricao_pdf')} {...aria('descricao_pdf')} />
          {erro('descricao_pdf')}
        </div>
        <div className="field">
          <label className="field-label" htmlFor="medicao-valor">Valor PI líquido</label>
          <input id="medicao-valor" className="input" inputMode="decimal" {...register('valor_pi')} {...aria('valor_pi')} />
          {erro('valor_pi')}
        </div>
        <div className="field">
          <label className="field-label" htmlFor="medicao-fator">Fator</label>
          <input id="medicao-fator" className="input" inputMode="decimal" {...register('fator')} {...aria('fator')} />
          {erro('fator')}
        </div>
        {(['regiao_cap', 'regiao_emulsoes'] as const).map((campo) => (
          <div className="field" key={campo}>
            <label className="field-label" htmlFor={`medicao-${campo}`}>
              {campo === 'regiao_cap' ? 'Região ANP — CAP' : 'Região ANP — Emulsões'}
            </label>
            <select id={`medicao-${campo}`} className="input" {...register(campo)} {...aria(campo)}>
              <option value="">Seguir o contrato</option>
              {regioes.map((r) => <option key={r} value={r}>{r}</option>)}
            </select>
            {erro(campo)}
          </div>
        ))}
      </form>
    </Dialogo>
  )
}
```

No mês travado: `CampoMesAno` não aceita `disabled`. Se `travado`, mostre o mês como texto (`<p>{mesAno(item.mes)}</p>`) no lugar do `Controller`, porque o `CampoMesAno` não deve ganhar uma prop só para isso. Confira se o `Dialogo` repassa `role="dialog"`, de que os testes dependem; os testes do `ConfirmarDialogo` já usam isso.

- [ ] **Step 6: Ações na `AbaMedicoes.tsx`**

- Estado `const [editando, setEditando] = useState<ItemMedicao | 'novo' | null>(null)` e `const [excluindo, setExcluindo] = useState<ItemMedicao | null>(null)`.
- Antes de `<span className="espaco" />`, no fim do `<form className="barra">`: `<button type="button" className="btn btn-primary" onClick={() => setEditando('novo')}><Icone nome="add" /> Incluir registro</button>`.
- Colunas novas antes de *Arquivo*: `<th>Origem</th><th>Região</th>`, e ao fim `<th><span className="sr-only">Ações</span></th>`. Se `sr-only` não existir em `componentes.css`, use `<th>Ações</th>`.
- Por linha:

```tsx
<td>{item.origem !== 'pdf' && <span className="badge">{item.origem}</span>}</td>
<td>
  {item.regiao_cap && <span className="badge badge-regiao">CAP: {item.regiao_cap} *</span>}{' '}
  {item.regiao_emulsoes && <span className="badge badge-regiao">Emulsões: {item.regiao_emulsoes} *</span>}
</td>
<td>{item.arquivo}</td>
<td>
  <button type="button" className="btn btn-sm" onClick={() => setEditando(item)}>
    <Icone nome="edit" /> Editar
  </button>{' '}
  <button type="button" className="btn btn-sm" onClick={() => setExcluindo(item)}>
    <Icone nome="delete" /> Excluir
  </button>
</td>
```

- Depois da tabela:

```tsx
{editando && (
  <DialogoMedicao
    contratoId={contrato.id}
    item={editando === 'novo' ? undefined : editando}
    aoFechar={() => setEditando(null)}
  />
)}
{excluindo && (
  <ConfirmarDialogo
    titulo="Excluir registro"
    mensagem={`Excluir o registro ${excluindo.codigo} de ${mesAno(excluindo.mes)}? Ele sai do cálculo e não volta ao reprocessar o PDF.`}
    rotuloConfirmar="Excluir registro"
    perigoso
    pendente={excluir.isPending}
    erro={excluir.error}
    aoConfirmar={() => excluir.mutate(excluindo.id)}
    aoCancelar={() => setExcluindo(null)}
  />
)}
```

com:

```tsx
const qc = useQueryClient()
const excluir = useMutation({
  mutationFn: (itemId: number) => excluirMedicao(contrato.id, itemId),
  onSuccess: async () => {
    setExcluindo(null)
    await aposMedicao(qc, contrato.id)
  },
})
```

O botão *Incluir registro* precisa aparecer também quando a lista está vazia, e ele já fica na barra. Atualize o comentário do topo do componente: "Os itens como o PDF os trouxe, editáveis um a um; …".

- [ ] **Step 7: Rodar os testes**

Run: `cd frontend && npm run test`
Expected: PASS (todos, inclusive os antigos de `medicoes.test.tsx`).

- [ ] **Step 8: Commit**

```bash
git add frontend/src/api frontend/src/pages/contrato frontend/src/styles frontend/tests/medicoes.test.tsx
git commit -m "feat(frontend): inclui, edita e exclui registros na aba Medições"
```

---

### Task 7: Marcação na aba *Cálculo* e token de cor

**Files:**
- Modify: `frontend/src/styles/tokens.css`, `frontend/src/styles/telas.css`
- Modify: `frontend/src/pages/contrato/TabelaCalculo.tsx`
- Test: `frontend/tests/calculo.test.tsx`

**Interfaces:**
- Consumes: `LinhaCalculo.regiao_manual` (Task 6, tipos).
- Produces: o token `--row-regiao-manual` e as classes `.linha-regiao-manual` e `.badge-regiao`.

- [ ] **Step 1: Escrever o teste que falha** (em `frontend/tests/calculo.test.tsx`; use a fábrica de cálculo que o arquivo já usa e acrescente `regiao_manual: null` às linhas da fábrica em `fabricas.ts`)

```tsx
it('marca a linha com região própria e explica na nota', async () => {
  // duas linhas do mesmo mês no mesmo produto: uma segue o contrato, outra é Sul
  prepararCalculo(umCalculoComLinhas([
    { mes: '2023-02-01', regiao_manual: null },
    { mes: '2023-02-01', regiao_manual: 'Sul' },
  ]))
  renderApp('/contratos/1/calculo')
  const marcada = (await screen.findByText('Sul *')).closest('tr')!
  expect(marcada).toHaveClass('linha-regiao-manual')
  expect(screen.getAllByText('fev/2023')).toHaveLength(2)
  expect(screen.getByText(/Região ANP definida no registro/)).toBeInTheDocument()
})
```

`prepararCalculo` e `umCalculoComLinhas` representam os auxiliares que `calculo.test.tsx`/`fabricas.ts` já têm para montar o JSON do cálculo. Leia o arquivo e use os nomes reais; se não existir auxiliar que aceite linhas, monte o objeto `Calculo` direto no teste a partir da fábrica existente, sobrescrevendo `familias[0].produtos[0].linhas`.

- [ ] **Step 2: Rodar e ver falhar**

Run: `cd frontend && npm run test -- calculo`
Expected: FAIL (o texto 'Sul *' não é encontrado).

- [ ] **Step 3: Implementar**

`tokens.css`, junto aos tokens `--row-*`:

```css
  /* Linha do cálculo com região ANP fixada no registro (mesma cor da planilha). */
  --row-regiao-manual: #fff2cc;
```

`telas.css`:

```css
.data-table tr.linha-regiao-manual td { background: var(--row-regiao-manual); }
.badge-regiao { background: var(--row-regiao-manual); }
```

`TabelaCalculo.tsx`, nas linhas (a chave deixa de ser `l.mes`, que repete quando o fator ou a região separam linhas):

```tsx
{produto.linhas.map((l, i) => (
  <tr key={`${l.mes}-${i}`} className={l.regiao_manual ? 'linha-regiao-manual' : undefined}>
    <td>
      {mesAno(l.mes)}
      {l.regiao_manual && <> <span className="badge badge-regiao">{l.regiao_manual} *</span></>}
    </td>
    ...
```

Depois da `</table>`, se alguma linha tiver `regiao_manual`, monte as notas por família (sem calcular nada, só listar):

```tsx
const notas = calculo.familias.flatMap((f) =>
  [...new Set(f.produtos.flatMap((p) => p.linhas.map((l) => l.regiao_manual)).filter(Boolean))]
    .map((r) => `* Região ANP definida no registro: ${f.rotulo} — ${r}`),
)
...
{notas.map((n) => <p key={n} className="contagem mt-md">{n}</p>)}
```

- [ ] **Step 4: Rodar os testes**

Run: `cd frontend && npm run test`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/styles frontend/src/pages/contrato/TabelaCalculo.tsx frontend/tests
git commit -m "feat(frontend): destaca no Cálculo as linhas com região própria"
```

---

### Task 8: Cenário e2e e documentação

**Files:**
- Create: `frontend/e2e/04-medicoes.spec.ts`
- Modify: `.claude/rules/architecture.md`, `.claude/rules/backend.md`, `.claude/rules/frontend.md`, `README.md`

- [ ] **Step 1: Escrever o cenário e2e**

Leia `frontend/e2e/01-cadastro-calculo.spec.ts` e `e2e/apoio.ts` para descobrir qual contrato a fixture carrega, qual URL usar e quais auxiliares existem. O cenário:

```ts
import { expect, test } from '@playwright/test'
// importe de './apoio' o auxiliar que abre o contrato da fixture, como 01-cadastro-calculo faz

test('região fixada num registro aparece marcada no Cálculo', async ({ page }) => {
  // 1. abrir /contratos/<id da fixture>/medicoes
  // 2. na primeira linha que tem produto, clicar em "Editar"
  // 3. em "Região ANP — CAP" (ou Emulsões, conforme a família da linha), escolher uma região diferente da do cadastro
  // 4. Salvar; esperar o badge "<Região> *" na linha
  // 5. abrir a aba Cálculo e esperar uma linha com a classe linha-regiao-manual e a nota "Região ANP definida no registro"
  // 6. voltar a Medições, Editar, escolher "Seguir o contrato", Salvar — deixa a fixture como estava para os specs seguintes
})
```

Transforme cada passo comentado numa chamada real (`page.goto`, `page.getByRole('button', { name: 'Editar' }).first().click()`, `page.getByLabel('Região ANP — CAP').selectOption('Sul')`, `expect(page.locator('tr.linha-regiao-manual')).toBeVisible()`). O spec roda em série, depois dos três que já existem. O passo 6 importa porque o banco é compartilhado entre os specs.

- [ ] **Step 2: Rodar o e2e**

Run: `cd frontend && npm run e2e` (antes, garanta que o pytest **não** está rodando e que `docker compose up -d postgres` está de pé)
Expected: os quatro specs PASS.

- [ ] **Step 3: Atualizar a documentação**

- `architecture.md`: em `migrations/`, acrescente `└── 008_medicao_manual.sql  # medicao_item: origem, exclusão lógica, região por registro` (e troque o `└──` da 007 por `├──`).
- `backend.md`, em *medicoes_repo.py*:
  - o ON CONFLICT agora só atualiza `origem = 'pdf' AND NOT excluido`;
  - `incluir_item`/`atualizar_item`/`excluir_item`/`buscar_item` e `MedicaoInvalida`;
  - código e mês travados em registros do PDF;
  - exclusão lógica de um registro do PDF, apagamento de um manual.
- `backend.md`, em *reequilibrio_export.py*:
  - precedência da região (item > simulação > cadastro) via `_anotar_regioes`;
  - ΔP por `(família, mês, região)`;
  - agregação produto × mês × fator × região manual;
  - registro manual fora da deduplicação;
  - a marcação `*`/cor/nota, com as constantes em `reequilibrio_layout.py`.
- `backend.md`, em *api/*: os três endpoints novos.
- `frontend.md`, em *Camada de API*: `aposMedicao`. Em *Regras de tela*: excluir registro de medição entra na lista de ações com `ConfirmarDialogo`.
- `README.md`, em *O que a aplicação faz*: um parágrafo, do ponto de vista do usuário: corrigir, incluir e excluir registros na aba *Medições*, fixar a região ANP de um registro, e preservação das edições quando o PDF é reenviado.

- [ ] **Step 4: Verificação final**

Run: `uv run pytest -q && (cd frontend && npm run test && npm run build)`
Expected: tudo PASS e o build sem erros de tipo.

Verificação manual:
1. `uv run uvicorn main:app --reload --port 8000`.
2. Editar a região de um registro na aba *Medições*.
3. Baixar a planilha e abrir no Excel/LibreOffice.
4. Conferir na linha marcada o `*`, o fundo `FFF2CC` e a nota abaixo do total.
5. Conferir que as fórmulas de F, H, I e J são clicáveis e que a equação da memória de cálculo está lá.

- [ ] **Step 5: Commit**

```bash
git add frontend/e2e/04-medicoes.spec.ts .claude/rules README.md
git commit -m "docs: documenta medições editáveis e região por registro"
```
