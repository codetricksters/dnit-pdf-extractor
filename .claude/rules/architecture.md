# Architecture

## File Layout

```
main.py                        # Thin entry point — re-exports app for uvicorn (main:app)
.env.example                   # Committed template for the environment variables
.env                           # Local copy with the real password (untracked)
migrations/                    # Numbered SQL migrations, applied in order at startup
├── 001_jobs.sql               # jobs, file_results, schema_migrations
├── 002_indices.sql            # anp_preco_semanal, indice_mensal
├── 003_catalogo.sql           # produto, produto_codigo
├── 004_contrato.sql           # contrato, contrato_familia_regiao, medicao_item
├── 005_template.sql           # template (xlsx blobs)
└── 006_catalogo_indices.sql   # drops confirmado; origem/atualizado_em; btree_gist + no-overlap constraint
scripts/
├── seed_indices.py            # Initial load through the importers (--anp, --igp-di)
├── gerar_fixtures_e2e.py      # One-off: builds tests/fixtures/ from the reference spreadsheet
└── build_template.py          # Rebuilds app/templates_xlsx/reequilibrio_template.xlsx
app/
├── __init__.py
├── main.py                    # FastAPI app: lifespan (pools, migrations, seed, periodic tasks), routers, /dashboard mount
├── config.py                  # Env-driven settings (DATABASE_URL, STORAGE_PATH, backup knobs, PG_BIN)
├── db.py                      # psycopg pools (async + sync), advisory locks, migration runner
├── static/                    # Client-side assets served at /static/*
├── templates/                 # Jinja2 HTML (base.html shell, _sidebar, _topbar, index.html)
├── templates_xlsx/
│   └── reequilibrio_template.xlsx   # Seed template only; the live source is the database
├── models/
│   └── job.py                 # Job/FileStatus enums and dataclasses
├── routers/
│   ├── upload.py              # GET / and POST /upload (starts an async job)
│   ├── jobs.py                # Job status, SSE stream, result downloads, retry
│   ├── admin.py               # Template and backup management (/admin)
│   ├── reequilibrio.py        # GET /reequilibrio/planilha — the .xlsx export
│   └── api/                   # REST API /api/v1: contratos, catalogo, indices, calculo, schemas, erros
├── services/
│   ├── extractor.py           # Text-PDF parsing (pdfplumber)
│   ├── ocr_extractor.py       # Scanned-PDF parsing
│   ├── pdf_classifier.py      # Chooses text vs OCR path
│   ├── file_processor.py      # Per-file pipeline: extract → JSON → database
│   ├── storage.py             # Upload and result files under STORAGE_PATH
│   ├── job_manager.py         # Job state in Postgres + SSE pub/sub
│   ├── indices_repo.py        # ANP weekly prices and monthly índices
│   ├── importadores.py        # Pure readers: ANP .xls, IGP-DI template (and its generator)
│   ├── importacao.py          # Preview/write against the database, manual values preserved
│   ├── exportadores.py        # CSV/XLSX of both índice series
│   ├── catalogo.py            # Products, service-code associations, code search
│   ├── contratos_repo.py      # Contract: PDF fields + user registration, region per family
│   ├── medicoes_repo.py       # Idempotent persistence of measurement items
│   ├── progresso.py           # The six-step trail and the counters shown in the shell
│   ├── delta_p.py             # ΔP per family, pure Decimal arithmetic
│   ├── reequilibrio_export.py # .xlsx generation from the active template (live formulas)
│   ├── reequilibrio_layout.py # Cell addresses and formula strings of the template
│   ├── xlsx_drawings.py       # Text-box (equation) extraction and re-injection
│   ├── template_repo.py       # Templates in the database: validate, list, activate, delete
│   └── backup.py              # pg_dump/pg_restore, retention, scheduled run
└── dashboard/                 # Dash app mounted at /dashboard via a2wsgi (synchronous)
    ├── __init__.py            # create_dash_app()
    ├── layout.py              # Shell only: sidebar, step trail, contract selector, styles
    ├── views.py                # Pure render functions, one per screen
    ├── callbacks.py           # Wiring: read the DB, render, write through the services
    └── data_loader.py         # Reads the DB and reuses the export's calculation
requirements.txt               # Flat dependency list (used by pip / Docker)
```

Routes live in `app/routers/`, business logic in `app/services/`, HTML in
`app/templates/`, client assets in `app/static/`.

## Database

PostgreSQL, accessed with **`psycopg` 3 and plain SQL** — no ORM, no alembic.
The driver serves both halves of the app with one grammar: FastAPI is async, and
the Dash dashboard runs **synchronously** under `a2wsgi.WSGIMiddleware`. Hence
`app/db.py` exposes both `acquire()` (async) and `acquire_sync()`.

- Money and índices are `NUMERIC` (mapped to `Decimal`), never `double precision`
  — the user audits these numbers against a spreadsheet.
- Reference months are `DATE` on the first day of the month, not `YYYY-MM` text.
- `id` columns are `GENERATED ALWAYS AS IDENTITY`; upserts use `ON CONFLICT`.
- Migrations are numbered SQL files applied in order and recorded in
  `schema_migrations` by `apply_migrations()` in the lifespan.

### Advisory locks

`deployment.md` recommends `--workers 2`, and the periodic task in the lifespan
runs in every worker. `advisory_lock(key)` wraps `pg_try_advisory_lock` so only
one worker acts: `LOCK_CLEANUP = 8474001` (stale jobs), `LOCK_BACKUP = 8474002`
(scheduled backup).

## Routing

| Route | Handler | Notes |
|---|---|---|
| `GET /` | `upload.index` | Renders `index.html` |
| `POST /upload` | `upload.upload` | `multipart/form-data`; returns `{"job_id": …}` and processes in the background |
| `GET /jobs/…` | `jobs` | Status, SSE events, per-file and zipped downloads, retry |
| `GET/POST /admin/templates…` | `admin` | Upload, download, activate, delete |
| `GET/POST /admin/backups…` | `admin` | Generate, list, download, upload, restore, delete |
| `GET /reequilibrio/planilha` | `reequilibrio.baixar_planilha` | `?contrato=15 00716/2022` → `.xlsx` |
| `/api/v1/…` | `routers/api` | Contratos, catálogo, índices, cálculo e planilha; OpenAPI em `/docs` |
| `GET /static/*` | `StaticFiles` | Mounted in `app/main.py` |
| `/dashboard` | Dash app | Mounted WSGI app |

## Adding a New Router

1. Create `app/routers/<name>.py` with `router = APIRouter(prefix="/...", tags=["..."])`.
2. Register it in `app/main.py` with `app.include_router(<name>.router)`.
3. Add any new templates to `app/templates/`, extending `base.html`.

## Data Flow

```
PDF → pdf_classifier → extractor / ocr_extractor → {header, rows}
        ↓ file_processor
   JSON artefact under STORAGE_PATH/jobs/<job_id>/results/
        ↓
   contrato + medicao_item ──┐
   contract registration  ───┤
   (Edital, Rodovia, …)      ├→ delta_p → reequilibrio_export → .xlsx
   anp_preco_semanal ────────┤                (active template +
   indice_mensal ────────────┘                 live formulas + memória de cálculo)
        ↑                     produto / família
   user input + seed script   + region per família
```

The dashboard reads the same path (`data_loader` → `montar_grupos` /
`calcular_deltas`), so the screen and the downloaded spreadsheet cannot diverge.

## Extracted Table Schema

| Column | Notes |
|---|---|
| `Serviço` | Item/service code (e.g. `56988`) — row identity key, and the catalogue key |
| `Descrição` | Long text, often multi-line in the PDF |
| `Código SICRO` | Always `"Não"` in DNIT PDFs |
| `Unidade` | |
| `Preço Unitário` | Latin-formatted number (`1.872.240,49`) |
| `Quantidade Acumulada` | |
| `Valor a PI Acumulado` | |
| `Valor a PI Líquido` | Column `a` of the reequilíbrio calculation |
| `Fator` | The reajustamento factor, already computed in the PDF |
| `Reajustamento Líquido` | |
| `Ajuste Contratual Líquido` | |
| `Source_File` | Original filename, for traceability |

## Row Identity Rule

A row starts a **new record** when its `Serviço` cell contains a 4+-digit numeric
code or `SUBTOTAL`. A row with dangling text and otherwise-empty structural
columns is merged back into the preceding record's `Descrição`.

## Side-Table Filter

Pages contain `Índices` side-tables (rows labelled `ADLOC`, `CONSER`, `EMUIMP`,
etc.) and standalone 2-column subtotal tables. Both are detected and skipped —
they corrupt the main table schema if included. The reequilíbrio calculation does
not need them: ΔP comes from the database, and `Fator` is already in the PDF.
