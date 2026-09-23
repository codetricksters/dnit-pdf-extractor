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

### Header Normalisation

`_normalize_header` normalises both sides to spaces before comparing (PDF labels use `\n` in multi-word column names like `"Código\nSICRO"`).

### 12-Column Phantom Trailing None

Some pages emit a 12-col header with a trailing `None`, shifting `Ajuste Contratual Líquido` to index 11. `_map_row` detects this and scans forward to fill the last expected column if it is empty after the main mapping pass.

### Number Handling

Latin-formatted numbers (`1.872.240,49`) are preserved as strings in the
extraction output. `number_parser.parse_br_number` converts them, and the
repositories call it when writing to `NUMERIC` columns. Do **not** call it during
extraction — the JSON artefact keeps the raw strings.

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
  Trecho, Subtrecho, Segmento, Extensão, Contratada).
- `definir_regiao(numero, familia, regiao)` — one ANP region **per family**; CAP
  and EMULSOES are independent.
- `campos_faltantes(contrato)` drives the export's warnings.

### medicoes_repo.py

`gravar_itens(contrato_id, rows, job_id=None)` is idempotent through
`UNIQUE (contrato_id, codigo_servico, mes_medicao, source_file)` plus
`ON CONFLICT … DO UPDATE`, so reprocessing the same PDF does not duplicate rows.
`itens_para_export` returns the rows joined to the catalogue.

### catalogo.py

The **service code** is the key, not the description: a code maps to exactly one
material, and OCR corrupts descriptions but not codes. Several codes point at one
`produto` with a custom `descricao_export`.

- `sugerir_familia(descricao)` — `CAP` → CAP; `EMULSÃO`/`RR-`/`RC-`/`EAI`/`IMPRIMAÇÃO` → EMULSOES.
- `registrar_pendencia(codigo, descricao_pdf)` records an unknown code with
  `confirmado = false`. **Unconfirmed codes stay out of the calculation** — a new
  material classified wrongly must not contaminate the result silently.
- `registrar_codigo(codigo, produto_id, *, descricao_pdf=…, confirmado=…)` is how
  the dashboard resolves a pendência.

### indices_repo.py

`gravar_precos_anp` / `gravar_indices_mensais` upsert the user-supplied series;
`buscar_preco_anp(produto, regiao, mes)` resolves a month to the weekly row whose
vigência contains **day 15** (`_dia_de_referencia`); `cobertura()` returns
`{"anp": {de, ate, registros}, "igp_di": {…}, "regioes": [...]}` for the Índices
screen. `FonteBanco` caches per instance — one export asks for the same base
month on every line.

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

A missing price or index raises `IndiceIndisponivel` — never zero, never a skipped
line. The export refuses; the dashboard surfaces it as a pendência.

## reequilibrio_export.py — The Spreadsheet

`exportar(numero_contrato, template) -> Resultado` loads the contract and items,
calls `calcular_deltas`, groups with `montar_grupos` (família → produto, subtotal
per product and a grand total) and writes into the template. Refuses with
`ExportacaoImpossivel` when the contract is unknown or a ΔP cannot be computed —
a spreadsheet without ΔP would look finished. `Resultado.avisos` carries the
non-fatal gaps (e.g. unregistered contract fields).

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

`GET /` renders `index.html`. `POST /upload` reads each file in memory, saves it
under `STORAGE_PATH`, creates a job and returns `{"job_id": …}` immediately; the
files are processed in background tasks. `file_processor` writes the JSON artefact
and then persists the contract (`contratos_repo.registrar_do_pdf`) and the items
(`medicoes_repo.gravar_itens`).

### jobs.py

Status, an SSE stream of changes, per-file and zipped result downloads, and retry.

### admin.py

`/admin/templates` (list, upload, download, activate, delete) and
`/admin/backups` (list, generate, download, upload, restore, delete). All blocking
work goes through `asyncio.to_thread`; service exceptions become
`HTTPException(422, str(e))`.

### reequilibrio.py

`GET /reequilibrio/planilha?contrato=…` — a query parameter because contract
numbers contain a slash and a space (`15 00716/2022`). Returns the `.xlsx` with a
`Content-Disposition` filename and an `X-Avisos` header joining `Resultado.avisos`.

## Dashboard

`layout.py` builds only the shell; each tab's content is rendered by a callback
through `views.py`, so the screen reflects the database at the moment the user
looks rather than at process start. `callbacks.py` computes nothing — ΔP,
grouping and the REF columns come from the services, so the screen and the
downloaded spreadsheet cannot disagree. Every write bumps the `recarregar`
`dcc.Store` counter to force a re-render from the database.

`data_loader.compute_ref_columns(df, lucro)` exists for the on-screen lucro field;
the export always keeps the contractual 5,11%. `_truncate` uses `math.trunc` — the
spreadsheet truncates column F, it does not round.
