# Architecture

## File Layout

```
main.py                        # Thin entry point — re-exports app for uvicorn (main:app)
.env                           # Environment variable template (commit this; ignore .env.local)
app/
├── __init__.py
├── main.py                    # FastAPI app: mounts /static, registers Jinja2Templates, includes routers
├── static/                    # Client-side assets served at /static/*
│   ├── css/style.css
│   ├── js/script.js
│   └── images/                # Logo and other images
├── templates/                 # Jinja2 HTML templates
│   ├── base.html              # Shared layout: <head>, CSS/JS links, block slots
│   └── index.html             # Upload page — extends base.html
├── routers/
│   ├── __init__.py
│   └── upload.py              # GET / (TemplateResponse) and POST /upload (returns .xlsx)
└── services/
    ├── __init__.py
    └── extractor.py           # PDF parsing: pdfplumber loop, row-merging, cleanup
requirements.txt               # Flat dependency list (used by pip / Docker)
```

The package follows the [FastAPI "bigger applications" pattern](https://fastapi.tiangolo.com/tutorial/bigger-applications/). Routes live in `app/routers/`, business logic in `app/services/`, HTML in `app/templates/`, and client assets in `app/static/`.

## Routing

| Route | Handler | Notes |
|---|---|---|
| `GET /` | `upload.index` | Renders `index.html` via `TemplateResponse` |
| `POST /upload` | `upload.upload` | Accepts `multipart/form-data`, returns `.xlsx` stream |
| `GET /static/*` | `StaticFiles` | Auto-mounted in `app/main.py` |

## Adding a New Router

1. Create `app/routers/<name>.py` with `router = APIRouter(prefix="/...", tags=["..."])`.
2. Register it in `app/main.py` with `app.include_router(<name>.router)`.
3. Add any new templates to `app/templates/`, extending `base.html`.

## Data Flow

1. User uploads one or more PDFs via `POST /upload`.
2. `upload.py` reads each file in-memory and calls `extractor.extract_from_pdf()` per file.
3. All row dicts are concatenated into a single `pandas.DataFrame`.
4. `openpyxl` writes the DataFrame to a single sheet (`Sheet1`) with auto-sized columns.
5. The workbook is streamed back as a `.xlsx` download.

## Main Table Schema

| Column | Notes |
|---|---|
| `Serviço` | Item/service code (e.g. `56988`) — row identity key |
| `Descrição` | Long text, often multi-line in the PDF |
| `Código SICRO` | Always `"Não"` in DNIT PDFs |
| `Unidade` | |
| `Preço Unitário` | Latin-formatted number (`1.872.240,49`) |
| `Quantidade Acumulada` | |
| `Valor a PI Acumulado` | |
| `Valor a PI Líquido` | |
| `Fator` | |
| `Reajustamento Líquido` | |
| `Ajuste Contratual Líquido` | |
| `Source_File` | Appended at export — original filename for traceability |

## Row Identity Rule

A row starts a **new record** when its `Serviço` cell contains a 4+-digit numeric code or `SUBTOTAL`. A row with dangling text and otherwise-empty structural columns is merged back into the preceding record's `Descrição`.

## Side-Table Filter

Pages contain `Índices` side-tables (rows labelled `ADLOC`, `CONSER`, `EMUIMP`, etc.) and standalone 2-column subtotal tables. Both are detected and skipped — they corrupt the main table schema if included.
