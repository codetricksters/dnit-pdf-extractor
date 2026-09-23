# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

`dnit-pdf-extractor` is a FastAPI web application for the DNIT "Resumo da Medição"
workflow. Users upload one or more PDFs; the app extracts their tabular data
(`pdfplumber`, or OCR for scanned files), persists the contract and the
measurement items in PostgreSQL, and combines them with the price índices the
users maintain (ANP weekly prices and IGP-DI) to compute the ΔP of art. 16.

The deliverable is an **Excel "Reequilíbrio" spreadsheet** generated from a
user-maintained template, with the calculation written as **live formulas** and
the memória de cálculo preserved as a native equation, so every number can be
audited. A Dash dashboard at `/dashboard` shows the same calculation on screen and
hosts the registration, índices, template and backup screens.

## Setup & Commands

This project uses [uv](https://docs.astral.sh/uv/) for dependency management. Python 3.12 is required (pinned in `.python-version`).

```bash
# Install dependencies (including dev)
uv sync

# Start PostgreSQL (required by the app and by the test suite, host port 5433)
docker compose up -d postgres

# Run the dev server (migrations are applied at startup)
uv run uvicorn main:app --reload --port 8000

# One-off initial load of the price índices
uv run python scripts/seed_indices.py

# Run tests
uv run pytest -v

# Add a runtime dependency
uv add <package>

# Add a dev-only dependency
uv add --dev <package>
```

Sample input PDFs go in `tmp/` (not committed to git).

## Rules

- [.claude/rules/architecture.md](.claude/rules/architecture.md) — app structure, data models, file layout
- [.claude/rules/backend.md](.claude/rules/backend.md) — extraction, persistence, ΔP rules, Excel generation, templates and backup
- [.claude/rules/frontend.md](.claude/rules/frontend.md) — templates, static assets, UI patterns
- [.claude/rules/deployment.md](.claude/rules/deployment.md) — dependencies, environment variables, running in production
