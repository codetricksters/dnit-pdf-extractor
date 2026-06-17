# Backend

## extractor.py — PDF Parsing Service

### Entry Point

```python
def extract_from_pdf(file_bytes: bytes, source_name: str) -> list[dict]:
```

Returns a list of row dicts matching the main table schema. Called once per uploaded file.

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

Latin-formatted numbers (`1.872.240,49`) are preserved as strings. A helper is available:

```python
def parse_br_number(value: str) -> float:
    return float(value.replace(".", "").replace(",", "."))
```

Do **not** call this automatically during extraction — keep raw strings so Excel formatting stays intact.

### Error Handling

Raise `HTTPException(status_code=422)` if:
- `pdfplumber` cannot open the file (corrupt or password-protected).
- No records are found after processing all pages.

## upload.py — Router

### `GET /`

Returns `templates.TemplateResponse("index.html", {"request": request})`.

### `POST /upload`

- Reads each file in-memory with `await file.read()`.
- Calls `extract_from_pdf(content, file.filename)` per file.
- Builds one `pandas.DataFrame` from all rows (`EXPECTED_COLUMNS + ["Source_File"]`).
- Writes to `io.BytesIO` via `openpyxl` — single sheet `Sheet1`, auto-column widths capped at 60.
- Returns `StreamingResponse` with `Content-Disposition: attachment; filename=medicao.xlsx`.
- Files are appended in the order received — no sorting.
