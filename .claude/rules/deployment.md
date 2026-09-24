# Deployment

## Dependencies

`requirements.txt` for pip/Docker alongside `pyproject.toml` (managed by `uv`).
Current runtime set:

```
fastapi
uvicorn[standard]
pdfplumber
pandas
openpyxl
python-multipart
jinja2
aiofiles
python-dotenv
easyocr
pytesseract
pymupdf
psycopg[binary,pool]
dash
dash-bootstrap-components
a2wsgi
xlrd
```

`psycopg[binary,pool]` is the only database driver — plain SQL, no ORM, no
alembic. `a2wsgi` mounts the synchronous Dash app inside the async FastAPI app.
`xlrd` reads the ANP's legacy `.xls` in the importer.

## System Dependencies

The `Dockerfile` installs:

- `gcc`, `libgl1`, `libglib2.0-0` — pdfplumber / easyocr.
- `tesseract-ocr` + `tesseract-ocr-por` — the primary OCR engine. Without it the
  app falls back to EasyOCR silently.
- `postgresql-client-16` from the **PGDG** repository — `pg_dump` / `pg_restore`
  for the backup feature. The client major must match the server: pg_dump emits
  directives from its own version, so a dump taken by a newer client cannot be
  restored (PG 17+ emits `SET transaction_timeout`, which 16 does not know).
  Debian's own `postgresql-client` tracks the distribution, hence the pin.

## Environment Variables

`.env.example` is the committed template; `.env` is **git-ignored** because it
carries the database password. On a new machine:

```bash
cp .env.example .env    # then replace TROQUE_ESTA_SENHA
```

The password in `DATABASE_URL` must match `POSTGRES_PASSWORD` in
`docker-compose.yml`. When a variable is added, add it to `.env.example` and to
the table below in the same change.

| Variable | Default | Purpose |
|---|---|---|
| `APP_ENV` | `development` | Runtime environment label |
| `DATABASE_URL` | `postgresql://dnit:dnit@localhost:5433/dnit` | Application database |
| `DATABASE_URL_TEST` | `postgresql://dnit:dnit@localhost:5433/dnit_test` | Test suite only |
| `STORAGE_PATH` | `<project>/data` | Uploads and JSON extraction artefacts |
| `BACKUP_DIR` | `$STORAGE_PATH/backups` | Where `pg_dump` writes |
| `BACKUP_RETENTION` | `14` | Newest dumps kept |
| `BACKUP_INTERVAL_HOURS` | `24` | Scheduled backup interval |
| `PG_BIN` | unset | Directory holding `pg_dump`/`pg_restore`; set it when the client on `PATH` is a different major than the server |

Load in code with:
```python
from dotenv import load_dotenv
load_dotenv()
```

## Database

Migrations are numbered SQL files in `migrations/`, applied in order by
`apply_migrations()` during the FastAPI lifespan and recorded in
`schema_migrations`. Nothing to run by hand: starting the app brings the schema
up to date.

Migration 006 runs `CREATE EXTENSION IF NOT EXISTS btree_gist` (shipped with the
`postgres:16` image); the database user must be allowed to create extensions —
the Compose user is.

The packaged Excel template is seeded into the `template` table on first start
(`template_repo.garantir_semente`), only when the table is empty.

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

## Running Locally

```bash
docker compose up -d postgres            # server on host port 5433
uv run uvicorn main:app --reload --port 8000
```

Point `DATABASE_URL` at `localhost:5433` for a non-Docker run. Sample input PDFs
go in `tmp/` (not committed).

## Running Tests

The suite needs a real PostgreSQL server; the `postgres` service above provides
it. Each test drops and rebuilds the `public` schema of `dnit_test` from
`migrations/`.

```bash
docker compose up -d postgres
uv run pytest -q
```

The backup tests skip themselves when no usable `pg_dump` is on `PATH`. To run
them against a PG 16 server with a newer client installed:

```bash
PG_BIN=/usr/lib/postgresql/16/bin uv run pytest -q
```

`tests/test_e2e_reequilibrio.py` imports the full official ANP file and takes a
few seconds; it reads only the versioned `tests/fixtures/`.

## Running in Production

```bash
docker compose up -d
```

or, directly:

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 2
```

Workers > 1 is safe: no shared in-memory state, and the periodic housekeeping in
`_cleanup_loop` (stale-job cleanup and the scheduled backup) is guarded by
PostgreSQL advisory locks, so only one worker performs each.

## Volumes

`docker-compose.yml` defines two named volumes, both required for state to
survive the container:

| Volume | Mount | Contents |
|---|---|---|
| `pgdata` | `/var/lib/postgresql/data` | The database — contracts, índices, items, templates |
| `appdata` | `/app/data` | Extraction artefacts (job JSON) and database backups |

`./tmp` is bind-mounted for convenience when testing with local PDFs.

## Backups

The app takes its own backups: `pg_dump -Fc` into `BACKUP_DIR` every
`BACKUP_INTERVAL_HOURS`, keeping `BACKUP_RETENTION` files. Everything the user
owns is inside that single dump — índices, contracts, measurement items and the
Excel templates.

Since the user runs in Docker and should not need `docker cp` or a shell, all of
it is reachable from the interface (Dash tab *Templates e backup*, routes under
`/admin/backups`): generate now, list, download, upload a `.dump`, restore and
delete. Restoring requires typing the backup's name to confirm, validates the
file with `pg_restore --list` before touching the database, and writes a safety
dump of the current state first.

## Static Files

`/static/*` is served by FastAPI's `StaticFiles` mount. In production behind a
reverse proxy (nginx, Caddy), consider serving `app/static/` from the proxy
directly to bypass the Python process.

## Notes

- PDF extraction is in-memory; uploads and JSON results are written under
  `STORAGE_PATH`, and dumps under `BACKUP_DIR`.
- Large PDFs with many pages may spike memory per request. Process pages in a
  streaming fashion inside `extractor.py` if this becomes an issue.
