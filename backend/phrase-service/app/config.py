import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

DB_PATH = Path(os.getenv("DB_PATH", "/data/phrases.db"))
# Folder database/ (CSV) milik repo: sumber kebenaran semua data bahasa, read-only.
# Di Docker di-mount ke /database; saat dev lokal otomatis menunjuk ke ../../database.
DATABASE_DIR = Path(os.getenv("DATABASE_DIR", str(BASE_DIR.parent.parent / "database")))

JWT_SECRET = os.getenv("JWT_SECRET", "")
JWT_ISSUER = "lingogo"
JWT_ALGORITHM = "HS256"

# Format: "namakelompok:kunci,kelompok2:kunci2"
API_KEYS_RAW = os.getenv("API_KEYS", "")


def api_keys() -> dict[str, str]:
    """Return {key: nama_kelompok}."""
    out = {}
    for item in API_KEYS_RAW.split(","):
        item = item.strip()
        if ":" in item:
            name, key = item.split(":", 1)
            if name.strip() and key.strip():
                out[key.strip()] = name.strip()
    return out
