import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent

STORAGE_PATH = Path(os.getenv("STORAGE_PATH", str(PROJECT_ROOT / "data")))
DB_PATH = STORAGE_PATH / "extractor.db"

STORAGE_PATH.mkdir(parents=True, exist_ok=True)
(STORAGE_PATH / "jobs").mkdir(exist_ok=True)
