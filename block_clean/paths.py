from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
UPLOADS = DATA / "uploads"
DB_PATH = DATA / "db.json"
OUTBOX_PATH = DATA / "outbox.jsonl"
STATIC = ROOT / "static"


def ensure_dirs():
    DATA.mkdir(parents=True, exist_ok=True)
    UPLOADS.mkdir(parents=True, exist_ok=True)
