# Frontend

## Template System

FastAPI serves HTML via **Jinja2Templates**. Templates live in `app/templates/` and are rendered with `TemplateResponse("template.html", {"request": request, ...})`. Every `TemplateResponse` call must include `"request": request` — Jinja2 needs it to resolve `url_for()`.

### base.html

The application shell, not just a `<head>`: sidebar, step trail and the main
column, so a page only writes its own content.

- `<head>` with charset, viewport, title block and `style.css` via
  `url_for('static', path='css/style.css')` — fonts are self-hosted through
  `@font-face` rules inside that stylesheet (`static/fonts/*.woff2`), so there is
  nothing font-related to link in `<head>` itself
- `{% include "_sidebar.html" %}` and `{% include "_topbar.html" %}`
- `{% block title %}`, `{% block head %}`, `{% block content %}` (inside
  `<main class="main-content">`), `{% block scripts %}` slots
- Default `<script>` tag for `/static/js/script.js` inside `{% block scripts %}`

New pages extend `base.html`:
```html
{% extends "base.html" %}
{% block title %}My Page{% endblock %}
{% block content %}...{% endblock %}
```

### _sidebar.html / _topbar.html

The shell's two halves, and the reason the upload page has to pass context:

- `_sidebar.html` — brand, the **Contrato ativo** panel, and two navigation
  groups (*Extrator de dados*, whose items switch the views on `/` through
  `data-view`; *Reequilíbrio & auditoria*, which deep-links to
  `/dashboard/?aba=…`).
- `_topbar.html` — the **six-step trail** (`1. Upload dos PDFs` → `6. Exportação`).

Both read a `resumo` from `app/services/progresso.py`, so every handler that
renders a page under this shell must pass it:

```python
resumo = await asyncio.to_thread(progresso.resumo)
return templates.TemplateResponse(request, "index.html", {"resumo": resumo, "visao": "upload"})
```

The step statuses are `done`/`current`/`pending`/`blocked`, which are also the
CSS suffixes (`step-done`, …) and map to Material Symbols — the same vocabulary
the Dash shell renders, so the trail cannot say two different things.

### index.html

Upload page — extends `base.html`. Stat cards, drop zone, the *Arquivos no Lote
Atual* table and the action bar; no inline CSS or JS.

## Static Assets

All client-side assets are served from `app/static/` at the `/static/` URL prefix.

| Path | Purpose |
|---|---|
| `static/css/style.css` | The whole design system — tokens, shell, panels, tables, badges, buttons, forms, and the Dash overrides |
| `static/js/script.js` | Upload flow: drag-and-drop, `POST /upload`, SSE progress, result downloads |
| `static/images/logo.svg` | The brand mark, used by the sidebar and as the favicon |
| `static/fonts/*.woff2` | Inter, JetBrains Mono and Material Symbols Outlined, self-hosted. Declared via `@font-face` at the top of `style.css` — never link a Google Fonts (or any other) stylesheet from `<head>` |

`style.css` opens with the token block (`--surface-*`, `--text-*`, `--primary*`,
`--tertiary*` (warning), `--error*`/`--critical*` (critical/negative-value red),
`--success*`, `--border-*`, `--row-height*`, radii, spacing, `--sidebar-width`,
`--header-height`). **New colours and sizes go in that block, not inline** — the
dashboard reproduces the same tokens and drifting them apart is how the two
halves of the application start looking like two products. The token values and
the component look (card borders, badge colours, dense-table row heights) come
from the Stitch project's generated design system and screens — when in doubt,
match those rather than inventing a new value.

**Rules:**
- No inline `<style>` or `<script>` tags — keep styles in `style.css` and behaviour in `script.js`. Prefer a class over a `style` attribute; `mt-sm`/`mt-md`/`mt-lg` exist for spacing.
- **No emoji anywhere in the interface.** Icons are Material Symbols Outlined and always carry a text label — the product generates an official document reviewed by engineers and fiscal inspectors, and emoji renders inconsistently across systems and breaks numeric column alignment.
- No external CDN dependencies. Add new libraries to `static/` and reference them locally.
- `url_for('static', path='...')` must be used in templates to generate correct asset URLs.

## API Contract

| Route | Method | Input | Response |
|---|---|---|---|
| `/` | GET | — | `TemplateResponse` (`index.html`) |
| `/upload` | POST | `multipart/form-data` with `files[]` | `{"job_id": "..."}` — processing continues in the background |
| `/jobs?status=active\|completed` | GET | — | JSON list, used to repopulate the page on load |
| `/jobs/{job_id}/status` | GET | — | JSON job state, per file |
| `/jobs/{job_id}/events` | GET | — | SSE stream; `script.js` opens an `EventSource` and falls back to polling `/status` |
| `/jobs/{job_id}/download` | GET | — | ZIP of every result |
| `/jobs/{job_id}/download/{filename}` | GET | — | One result file |
| `/jobs/{job_id}/retry/{filename}` | POST | — | Re-runs a failed file |
| `/reequilibrio/planilha?contrato=…` | GET | — | The `.xlsx` export; `X-Avisos` lists non-fatal gaps |

Upload is asynchronous: the POST returns a `job_id` immediately and progress
arrives over SSE. Errors use FastAPI's standard `HTTPException` JSON format
(`{"detail": "..."}`); `script.js` reads `err.detail` to surface the message.

## Dashboard

The reequilíbrio screens are a **Dash** app mounted at `/dashboard`, not Jinja
templates — the sidebar links to each of them. It has its own conventions (see
`architecture.md` and `backend.md`): `layout.py` builds only the shell,
`views.py` renders each screen, `callbacks.py` wires them.

`create_dash_app()` loads **`/static/css/style.css`** through
`external_stylesheets`, so the dashboard wears the same design system as the
Jinja pages — same origin, still no CDN for the stylesheet. Therefore prefer
`className="panel"`, `"btn btn-primary"`, `"badge badge-ok"`, `"data-table"`,
`"field"` over ad-hoc `style` dicts. Style dicts remain necessary where CSS
cannot reach: `dash_table.DataTable` (`STYLE_HEADER`, `STYLE_CELL`,
`STYLE_DATA_CONDITIONAL`, `STYLE_FILTER`) and `STYLE_INPUT`, all in `layout.py`.

Navigation is the **sidebar**, not a tab strip: `aba` is a `dcc.Store` written by
the sidebar's pattern-matching items (`{"tipo": "nav-aba", "aba": …}`) and by
`?aba=…` on the URL, which is what makes the deep links in the step trail and in
the blocked-export notice work. `layout.trilha()` and `layout.painel_contrato()`
render the same shell blocks as the Jinja partials, from the same `progresso`
summary.
