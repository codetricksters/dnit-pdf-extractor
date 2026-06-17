# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

`dnit-pdf-extractor` is a FastAPI web application that allows users to upload one or more DNIT "Resumo da Medição" PDF files, extracts their tabular data using `pdfplumber`, merges all content into a single DataFrame, and returns a downloadable Excel file.

## Setup & Commands

This project uses [uv](https://docs.astral.sh/uv/) for dependency management. Python 3.12 is required (pinned in `.python-version`).

```bash
# Install dependencies (including dev)
uv sync

# Run the dev server
uv run uvicorn main:app --reload --port 8000

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
- [.claude/rules/backend.md](.claude/rules/backend.md) — extraction logic, data cleaning, Excel generation
- [.claude/rules/frontend.md](.claude/rules/frontend.md) — templates, static assets, UI patterns
- [.claude/rules/deployment.md](.claude/rules/deployment.md) — dependencies, environment variables, running in production
