# Backend

## extractor.py — PDF Parsing Service

### Entry Point

```python
def extract_from_pdf(file_bytes: bytes, source_name: str) -> dict:
```

Returns `{"header": {...}, "rows": [...]}`. The header carries `Contrato`,
`Data Base`, `Período Líquido` and `Número do Processo`; the rows match the
extracted table schema in `architecture.md`. Called once per uploaded file.
`ocr_extractor.extract_from_pdf` is the equivalent for scanned PDFs, chosen by
`pdf_classifier`.

### pdfplumber Strategy

- Open with `pdfplumber.open(io.BytesIO(file_bytes))` — always in-memory, never to disk.
- Use **default** `page.extract_tables()` — the PDF uses drawn borders, so `lines` strategy outperforms `text`.
- Tables with `max_non_empty_columns ≤ 3` are skipped (standalone subtotal pairs like `['1.872.240,49', '0,00']`).
- Use the **first** row whose `row[0]` contains a `MAIN_HEADER_KEYWORDS` match as the global header. Discard repeated header rows on later pages.

### Row Classification (in order of precedence)

| Check | Action |
|---|---|
| Any cell is empty and `any(row)` is False | Skip |
| `_is_indices_row` — whole-word match for `ADLOC`, `CONSER`, `EMUIMP` etc. | Skip |
| `_is_header_row` — `row[0]` contains `"serviço"`, `"descrição"`, or `"código"` | Set header (first time) or skip |
| `_is_section_header` — single non-empty cell matching `^\d+[,.]\d+\s*-` | Skip |
| `Serviço` is empty and `Descrição` is empty | Skip (embedded subtotal row) |
| `_is_new_record` — `Serviço` matches `^\d{4,}` or starts with `SUBTOTAL` | Start new record |
| `_row_is_dangling` — all columns except `Descrição` are empty | Merge `Descrição` into previous record |
| Otherwise | Save previous record, start new one |

### Pages whose grid is broken

Some PDFs (the first measurements of a contract, e.g. contrato 134/2022, MP 01–09)
draw each cell as a loose rectangle, so there is no single grid and
`extract_tables()` splits the columns into separate tables: code and description
in one, the unit in another, the numbers in a third. Read as rows, the numbers
become junk records and the code is lost (a 3-column table is dropped by the
"≤ 3 columns" filter). No `extract_tables` setting fixes it — `snap`/`join`
tolerances either leave the fragments or collapse everything — but the page's text
lines are intact.

`_records_from_text` therefore reads the item lines
(`code description [Não] unit` + the seven numeric columns), and `_grid_is_broken`
decides per page: if a record the tables produced is not a service item, or a code
printed on the page is missing from the tables, the page's table records are
discarded and its text records used. A page with an intact grid never takes this
path, so descriptions that wrap onto several lines are still merged by the table
path; on the fallback path a wrapped description keeps only its first line (the
code, which everything hangs off, is unaffected).

Validate against a real series by comparing the extracted totals with the
`SOMA` line printed on each page (PI Líquido, Reajustamento, Ajuste): all 53
PDFs of contrato 134/2022 reconcile.

### Header Normalisation

`_normalize_header` normalises both sides to spaces before comparing (PDF labels use `\n` in multi-word column names like `"Código\nSICRO"`).

### 12-Column Phantom Trailing None

Some pages emit a 12-col header with a trailing `None`, shifting `Ajuste Contratual Líquido` to index 11. `_map_row` detects this and scans forward to fill the last expected column if it is empty after the main mapping pass.

### Number Handling

Latin-formatted numbers (`1.872.240,49`) arrive from `pdfplumber`/OCR as strings.
`number_parser.convert_numeric_columns` (over `parse_br_number`) is called once
per record **during extraction** — both `extractor.py` and `ocr_extractor.py`
call it before the record is emitted — so the `NUMERIC_COLUMNS` fields land in
the JSON artefact and in `medicoes_repo` already as `float`, not as raw strings.

### Error Handling

Raise `HTTPException(status_code=422)` if:
- `pdfplumber` cannot open the file (corrupt or password-protected).
- No records are found after processing all pages.

## Persistence

All repositories are **synchronous** (`db.acquire_sync`), because the Dash
dashboard is their main consumer and runs synchronously under `a2wsgi`. Async
callers wrap them in `asyncio.to_thread` instead of keeping two flavours of every
query.

### contratos_repo.py

- `normalizar_numero` extracts `15 00716/2022` from the polluted header value
  (`"15 00716/2022 - HWN ENGENHARIA LTDA Índices I0 I1 K …"`); the contract number
  is the key everything else hangs off, so it must be normalised before use.
  `extrair_contratada` mines the same string for a registration suggestion.
- `registrar_do_pdf(header)` inserts the PDF-derived fields **once** and never
  overwrites what the user has since edited.
- `salvar_cadastro(numero, dados)` stores the user's fields (Edital, Rodovia,
  Trecho, Subtrecho, Segmento, Extensão, Contratada); `atualizar(contrato_id,
  dados, regioes)` is the same write keyed by `id`, and also accepts `data_base`
  — the API's `PATCH /contratos/{id}` exposes it, so a wrong Data Base the PDF
  suggested can be corrected. Both validate everything before opening the
  transaction, so a bad field never leaves half the form written; refusals raise
  `CadastroInvalido`.
- `buscar_por_id(contrato_id)` / `buscar(numero)` — the same row, by `id` or by
  number; `listar(numero=None)` lists every contract with its item/measurement
  counts, `numero` filtering with `ILIKE`.
- `definir_regiao(numero, familia, regiao)` — one ANP region **per family**; CAP
  and EMULSOES are independent.
- `campos_faltantes(contrato)` drives the export's warnings.

### medicoes_repo.py

`gravar_itens(contrato_id, rows, job_id=None)` is idempotent through
the partial unique index `uq_medicao_item_pdf` (`contrato_id, codigo_servico,
mes_medicao, source_file WHERE origem <> 'manual'`) plus `ON CONFLICT … DO UPDATE
… WHERE origem = 'pdf' AND NOT excluido`: reprocessing the same PDF does not
duplicate rows, and never overwrites or brings back what the user edited or deleted
— unless `atualizar=True`, the user's confirmed choice on upload: the `WHERE` is
dropped and the row also gets `origem = 'pdf'`, `excluido = false`, keeping
`regiao_cap`/`regiao_emulsoes` unless `limpar_regioes=True`. The match is the same
key, so it only reaches rows of the **same filename**; manual records are outside
the index and never touched, and rows absent from the new extraction stay as they
are.
`itens_para_export` returns the rows joined to the catalogue — only associated
codes. `gravar_itens` returns the number of items stored.

`listar_itens(contrato_id, mes=None, no_calculo=None, q=None, arquivo=None)`
serves the *Medições* tab: every extracted item of the contract with its
associated product (or none), `no_calculo` filtering on whether the code has one,
`q` matching code or description with `ILIKE`, `arquivo` on the `source_file`
(`'manual'` for the records the user created).

Records can be edited one at a time. `medicao_item.origem` is `'pdf'` (extracted,
still updated by reprocessing), `'editado'` (extracted, then changed by the user)
or `'manual'` (created by the user, `source_file = 'manual'`). `incluir_item`,
`atualizar_item`, `excluir_item` and `buscar_item` validate everything before
opening the transaction and refuse with `MedicaoInvalida`. **Código and mês of an
extracted record are locked**: they are the key with which reprocessing finds the
row again, so changing them would duplicate it; to fix them, delete the record
and add a manual one. Deleting is **logical** for an extracted record
(`excluido = true`, so the PDF does not bring it back) and a real `DELETE` for a
manual one; `excluir_itens(contrato_id, ids)` does the same for several records in
one transaction, ignoring ids of another contract. `regiao_cap`/`regiao_emulsoes` pin an ANP region on the record
(normalised against `cobertura()["regioes"]`; empty means follow the contract).
Only the column of the code's product family is ever read (`_anotar_regioes`), so
`incluir_item`/`atualizar_item` refuse a region for the **other** family
(`_conferir_familia`) — it would show in the list with no effect on the
calculation or the file. Clearing is always accepted, and a code without a
product accepts both.
`listar_itens` and `itens_para_export` ignore `excluido`.

`aplicar_regiao(contrato_id, ids, regiao, simular=False)` is the same pin
written in bulk on the records the user selected: one `UPDATE` sets, on each
non-deleted record of the contract among `ids`, the region column of **its
product's family** (`regiao_cap` or `regiao_emulsoes`), so a mixed selection works;
records whose code has no product, and ids of another contract, are skipped. It
turns `'pdf'` into `'editado'` like a single edit. It is a write, not a rule: records
imported later arrive without the region. `simular=True` only
counts, so the screen can confirm before writing.

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
- `buscar_codigos(q, associado, limite, produto_id)` — distinct extracted codes,
  `q` filtering code **or** description with `ILIKE '%q%'`, `produto_id` to one
  product's codes.
- `associar_codigos(produto_id, codigos)` associates or re-points several codes
  in one transaction; `False` when the product does not exist.

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
`{"anp": {de, ate, registros, manuais}, "igp_di": {…}, "regioes": [...]}`.
`FonteBanco.preco_anp` applies one fallback, to `REGIAO_REFERENCIA`: when **any
region other than Brasil** has no price for the month (no week, a `NULL` price or
a zero) it uses **Brasil**'s. Zero is never a price — at the base month it would
divide by zero, elsewhere it would silently zero the ΔP — so Brasil itself with no
price or a zero is `None` (índice indisponível) and falls back nowhere.
`buscar_preco_anp` does not fall back, so the ANP grid and `cobertura()` keep
showing the real gaps. Each
substitution is recorded in `FonteBanco.substituicoes`.
`produtos_anp()` lists the distinct ANP products in the database (the filter of
the ANP grid). `FonteBanco` caches per instance — one export asks for the same
base month on every line.

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

## delta_p.py — ΔP

Pure `Decimal` arithmetic over a `FonteIndices` protocol, so it is testable
without a database.

- **Fixed base:** every variation is measured against the contract's *Data Base*,
  never against the previous month.
- **One-month offset:** ANP month is `m − 1`, IGP-DI month is `m`; base months are
  `Data Base − 1` and `Data Base` respectively.

```
ΔP_cap(m)  = P(m−1) / P(base_anp) − 1
ΔP_emul(m) = 0,75 · ΔP_cap(m) + 0,25 · (IGP(m) / IGP(Data Base) − 1)
```

The emulsion blend exists because the ANP publishes no emulsion price. The CAP
component inside `ΔP_emul` uses the **EMULSOES** family's region, so the two
families can produce different `ΔP_cap` for the same month.

The Brasil price fallback (`indices_repo.FonteBanco`) is
transparent to ΔP; `reequilibrio_export` turns every substitution into an
`avisos` line ("Preço ANP de Centro-Oeste indisponível em 03/2024; usado o preço
de Brasil.") and writes the same text as a note below the total in the file.

A missing price or index raises `IndiceIndisponivel` — never zero, never a skipped
line. The export refuses, and the API answers 422 with every missing índice in
`faltando`.

## reequilibrio_export.py — The Spreadsheet

`exportar(numero_contrato, template) -> Resultado` loads the contract and items,
calls `calcular_deltas`, groups with `montar_grupos` (família → produto, subtotal
per product and a grand total) and writes into the template. Refuses with
`ExportacaoImpossivel` when the contract is unknown or a ΔP cannot be computed —
a spreadsheet without ΔP would look finished. `Resultado.avisos` carries the
non-fatal gaps (e.g. unregistered contract fields).

`calcular(contrato, regioes_override)` is the single calculation behind both the
JSON (`serializar`, columns `a`–`f` of row 16) and the file (`gerar`). An override
changes a family's region for that generation only — never the registration — and
is reported in `avisos` and in the filename (`…_SIMULACAO_CAP-Sul.xlsx`).
`ExportacaoImpossivel` carries a structured `faltando` list: field codes
(`data_base`, `regiao_<familia>`) and prose strings for missing índices, all
collected at once rather than stopping at the first — `regioes_efetivas` checks
every família in an override before raising, and `calcular`/`_deltas` walk every
(família, mês, região) the export needs.

**Region precedence: record > simulation > registration.** `_anotar_regioes`
writes into each item its `regiao` (the effective one) and `regiao_manual` (the
one pinned on the record, else `None`). ΔP is computed per `(família, mês,
região)`, and `montar_grupos` aggregates by produto × mês × fator × `regiao_manual`:
a record with a region of its own keeps its own row (`Linha.regiao_manual`) and
is exposed as `regiao_manual` in `serializar`. A `manual` record is never
discarded as a "same PDF uploaded twice" repeat. A missing índice for a pinned
region lands in `faltando` like any other. `avisos` reports how many records use
their own region.

In the file, such a row has `*` appended to its description formula, a fill and a
note below the total (`MARCA_REGIAO_MANUAL`, `COR_REGIAO_MANUAL`,
`NOTA_REGIAO_MANUAL` in `reequilibrio_layout.py`); formulas F, H, I and J are
unchanged and column G stays a literal.

### Live formulas

Auditability is the point of the file, so **F, H, I and J are written as Excel
formulas**, not values (`=TRUNC(E17*D17,2)`, `=D17*G17`, `=H17-F17`,
`=I17*(1-0.0511)`). Only ΔP (column G) is a literal — the app computes it.
Row 16 carries the letters tying each column to the equation
(`a`, `b`, `d`, `c = a*d`, `e = c - b`, `f = e * (1-(5,11/100))`).

All cell addresses, labels and formula strings live in **`reequilibrio_layout.py`**
so the three places that must agree cannot drift: `scripts/build_template.py`,
the export, and `template_repo.validar`.

### openpyxl caveats

- **openpyxl deletes text boxes.** Saving a file strips the memória de cálculo
  equation from `drawing2.xml` while keeping the logo. `xlsx_drawings.py`
  therefore re-reads the shapes from the template at export time and re-injects
  them into the generated file — including the source root's namespace
  declarations. Reading from the template (rather than embedding XML in the code)
  is what keeps the user's equation the source of truth.
- **`delete_rows` leaves merged ranges behind.** Remove them with
  `ws.merged_cells.ranges.remove(faixa)`; `unmerge_cells()` does not help.
- openpyxl serialises numbers with 17 significant digits and an xlsx number cell
  is a float64. The no-drift guarantee lives in Postgres `NUMERIC`, not in the
  file's text.

## template_repo.py — Templates in the Database

Templates are `BYTEA` rows with `sha256`, `ativo` and a history, guarded by a
partial unique index `ON template (ativo) WHERE ativo`. Storing them in the
database means the database backup already covers them — one artefact to save and
restore.

`validar(conteudo)` refuses an upload that would silently produce a broken
spreadsheet: not a readable `.xlsx`, the `REEQUILÍBRIO` sheet missing, the header
block out of position, or the memória de cálculo equation absent from the
drawings. `garantir_semente()` installs the packaged template only when the table
is empty, so a restart never undoes a user's upload. `excluir` refuses to delete
the **active** template (activate another first) and never leaves the table empty.

## backup.py — pg_dump / pg_restore

`pg_dump -Fc` into `config.BACKUP_DIR`, with `BACKUP_RETENTION` newest kept.
`-Fc` is the format because `pg_restore --list` can inspect a dump *before* it is
applied, which is how an invalid upload is refused without any write.

- `verificar_compatibilidade()` refuses to dump when the **client major is newer
  than the server**: pg_dump emits directives from its own version (PG 17+ emits
  `SET transaction_timeout`, unknown to 16), so such a dump cannot be restored.
  `config.PG_BIN` points at a matching client when several are installed.
- `restaurar(nome, confirmacao)` requires `confirmacao == nome`, takes a safety
  dump of the current state first, and applies
  `pg_restore --clean --if-exists --no-owner --no-privileges --single-transaction`.
- `executar_agendado()` decides for itself whether `BACKUP_INTERVAL_HOURS` has
  elapsed and never raises; it is called from `_cleanup_loop` under `LOCK_BACKUP`.
- Filenames must match `^[A-Za-z0-9._-]+\.dump$` — path traversal is refused.

Error messages in this module are written **for the user** and are passed through
verbatim by the routers and callbacks.

## Routers

### upload.py

`POST /upload` reads each file in memory, saves it under `STORAGE_PATH`, creates
a job and returns `{"job_id": …}` immediately; the files are processed in
background tasks. `file_processor` writes the JSON artefact and then persists the
contract (`contratos_repo.registrar_do_pdf`) and the items
(`medicoes_repo.gravar_itens`), and records on the file which contract it fed and
how many items it stored (`job_manager.vincular_contrato`, migration 007). `GET /`
is no longer here: the SPA serves it.

The form fields `atualizar` and `limpar_regioes` ("Atualizar registros já
importados" on the screen) are stored on the job (migration 009), and
`_persistir` reads them back with `job_manager.opcoes_de_gravacao` instead of
receiving them, so retrying a failed file writes the same way the upload did.

### jobs.py

Status, an SSE stream of changes, per-file and zipped result downloads, and
retry. Each file in the status carries `contrato_id` and `itens` once persisted,
which is how the upload screen links a result to its contract.

### admin.py

`/admin/templates` (list, upload, download, activate, delete) and
`/admin/backups` (list, generate, download, upload, restore, delete). All blocking
work goes through `asyncio.to_thread`; service exceptions become
`HTTPException(422, str(e))`.

### reequilibrio.py

`GET /reequilibrio/planilha?contrato=…` — a query parameter because contract
numbers contain a slash and a space (`15 00716/2022`). Returns the `.xlsx` with a
`Content-Disposition` filename and an `X-Avisos` header joining `Resultado.avisos`.

### api/ — `/api/v1`

Thin routers over the synchronous services (`asyncio.to_thread`), Pydantic
schemas in `schemas.py` (Decimal serialised as string). `ErroApi(status, detail,
**extra)` and its handler produce `{"detail": …}` plus fields such as `faltando`
or `erros`. Contracts are addressed by numeric `id`; `GET /contratos?numero=`
finds one by number. Index uploads are capped at 20 MB (413). The `X-Avisos`
header (`calculo.py`) is sanitised to latin-1, since HTTP headers only accept it.

Endpoints that exist for the React interface: `GET /contratos/{id}/medicoes?mes=&no_calculo=&q=&arquivo=`
(404 for an unknown contract), `GET /codigos?produto_id=`,
`PUT /produtos/{id}/codigos` with `{"codigos": [...]}` (404 for an unknown
product), `GET /indices/anp/produtos`, `manuais` in each series of
`GET /indices/cobertura`, `POST /contratos/{id}/medicoes` (201),
`PATCH /contratos/{id}/medicoes/{item_id}` and `DELETE …/{item_id}` (204),
`POST /contratos/{id}/medicoes/regiao?simular=` (`{ids: [...], regiao}` →
`{"alterados": n}`), `POST /contratos/{id}/medicoes/excluir` (`{"ids":
[...]}` → `{"excluidos": n}`; POST because proxies drop a DELETE body) — 404
for an unknown contract or record, `MedicaoInvalida` becomes `ErroApi(422)` with a
text `detail` of `campo: mensagem` lines — and `arquivo` in the cálculo JSON — the filename the
spreadsheet download would get, so the screen can show it during a simulation.

Two different shapes of 422 reach the client, and there is no global exception
handler smoothing them into one — callers must expect both:

- **Pydantic validation** (a malformed body, an out-of-pattern path param) is
  FastAPI's own 422, with `detail` as a **list of objects** (`loc`, `msg`,
  `type`), before any router code runs.
- **`ErroApi`** (`erros.py`) is raised deliberately by a router or a service
  exception it catches (`ExportacaoImpossivel`, `TemplateInvalido`,
  `IndiceInvalido`/`SemanaSobreposta`, `ArquivoInvalido`) — `detail` is a
  **plain string**, optionally alongside `faltando` (cálculo/planilha) or
  `erros` (importação de índices).

## Dashboard

Frozen: kept mounted and working, off the menu, receiving no new features; the
React interface replaces it.

`layout.py` builds only the shell; each tab's content is rendered by a callback
through `views.py`, so the screen reflects the database at the moment the user
looks rather than at process start. `callbacks.py` computes nothing — ΔP,
grouping and the REF columns come from the services, so the screen and the
downloaded spreadsheet cannot disagree. Every write bumps the `recarregar`
`dcc.Store` counter to force a re-render from the database.

`data_loader.compute_ref_columns(df, lucro)` exists for the on-screen lucro field;
the export always keeps the contractual 5,11%. `_truncate` uses `math.trunc` — the
spreadsheet truncates column F, it does not round.
