# Frontend

## Template System

FastAPI serves HTML via **Jinja2Templates**. Templates live in `app/templates/` and are rendered with `TemplateResponse("template.html", {"request": request, ...})`. Every `TemplateResponse` call must include `"request": request` — Jinja2 needs it to resolve `url_for()`.

### base.html

Shared layout providing:
- `<head>` with charset, viewport, and title block
- `<link>` to `/static/css/style.css` via `url_for('static', path='css/style.css')`
- `{% block title %}`, `{% block head %}`, `{% block content %}`, `{% block scripts %}` slots
- Default `<script>` tag for `/static/js/script.js` inside `{% block scripts %}`

New pages extend `base.html`:
```html
{% extends "base.html" %}
{% block title %}My Page{% endblock %}
{% block content %}...{% endblock %}
```

### index.html

Upload page — extends `base.html`. Contains only the card markup; no inline CSS or JS.

## Static Assets

All client-side assets are served from `app/static/` at the `/static/` URL prefix.

| Path | Purpose |
|---|---|
| `static/css/style.css` | All page styles — card layout, drop-zone, button states |
| `static/js/script.js` | Upload flow: drag-and-drop, `POST /upload`, SSE progress, result downloads |
| `static/images/` | Logo and other images |

**Rules:**
- No inline `<style>` or `<script>` tags — keep styles in `style.css` and behaviour in `script.js`.
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
templates — `index.html` links to it in the navbar. It has its own conventions
(see `architecture.md` and `backend.md`): `layout.py` builds only the shell,
`views.py` renders each tab, `callbacks.py` wires them. Styling there is Dash
component props and `dash_bootstrap_components`, so `style.css` does not apply.
