# Deployment

## Dependencies

`requirements.txt` for pip/Docker alongside `pyproject.toml` (managed by `uv`):

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
```

## Environment Variables

Declared in `.env` (committed as a template). Copy to `.env.local` for local overrides — `.env.local` is git-ignored.

| Variable | Default | Purpose |
|---|---|---|
| `APP_ENV` | `development` | Runtime environment label |

Load in code with:
```python
from dotenv import load_dotenv
load_dotenv()
```

## Running Locally

```bash
uv run uvicorn main:app --reload --port 8000
```

## Running in Production

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 2
```

Workers > 1 is safe — the app is stateless (no shared in-memory state between requests). All PDF and Excel processing is done in-memory per request.

## Static Files

`/static/*` is served directly by FastAPI's `StaticFiles` mount. In production behind a reverse proxy (nginx, Caddy), consider serving `app/static/` directly from the proxy for better performance and bypass the Python process entirely.

## Notes

- No temporary files are written to disk — all processing is in-memory.
- Large PDFs with many pages may spike memory per request. Process pages in a streaming fashion inside `extractor.py` if this becomes an issue.
