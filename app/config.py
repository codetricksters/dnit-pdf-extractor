import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).parent.parent

# Does not override variables already in the environment (e.g. the ones
# docker-compose.yml sets directly on the container), so this is safe in both
# the local run and the containerized one.
load_dotenv(PROJECT_ROOT / ".env")

STORAGE_PATH = Path(os.getenv("STORAGE_PATH", str(PROJECT_ROOT / "data")))

# Matches the local (non-Docker) run documented in the README: postgres on the
# host's port 5433. The full docker-compose stack does not use this default —
# it sets DATABASE_URL directly on the container's environment.
DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql://dnit:dnit@localhost:5433/dnit"
)

MIGRATIONS_PATH = PROJECT_ROOT / "migrations"

BACKUP_DIR = Path(os.getenv("BACKUP_DIR", str(STORAGE_PATH / "backups")))
BACKUP_RETENTION = int(os.getenv("BACKUP_RETENTION", "14"))
BACKUP_INTERVAL_HOURS = int(os.getenv("BACKUP_INTERVAL_HOURS", "24"))
# Directory holding pg_dump/pg_restore. Set it when the machine has several
# PostgreSQL client versions installed and the one on PATH does not match the
# server: a dump taken by a newer client cannot be restored into an older server.
PG_BIN = os.getenv("PG_BIN") or None

STORAGE_PATH.mkdir(parents=True, exist_ok=True)
(STORAGE_PATH / "jobs").mkdir(exist_ok=True)
