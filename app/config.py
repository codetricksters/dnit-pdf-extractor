import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent

STORAGE_PATH = Path(os.getenv("STORAGE_PATH", str(PROJECT_ROOT / "data")))

DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql://dnit:dnit@localhost:5432/dnit"
)

MIGRATIONS_PATH = PROJECT_ROOT / "migrations"

BACKUP_DIR = Path(os.getenv("BACKUP_DIR", str(STORAGE_PATH / "backups")))
BACKUP_RETENTION = int(os.getenv("BACKUP_RETENTION", "14"))
BACKUP_INTERVAL_HOURS = int(os.getenv("BACKUP_INTERVAL_HOURS", "24"))

STORAGE_PATH.mkdir(parents=True, exist_ok=True)
(STORAGE_PATH / "jobs").mkdir(exist_ok=True)
