import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

DB_PATH = Path(os.getenv("DB_PATH", "/data/phrases.db"))
# Folder CSV. Di Docker di-mount ke /database, saat dev lokal memakai ../../database
DATABASE_DIR = Path(os.getenv("DATABASE_DIR", str(BASE_DIR.parent.parent / "database")))

JWT_SECRET = os.getenv("JWT_SECRET", "")
JWT_ISSUER = "lingogo"
JWT_ALGORITHM = "HS256"

# Format: "kelompok1:kunci1,kelompok2:kunci2"
API_KEYS_RAW = os.getenv("API_KEYS", "")


def api_keys():
    """{kunci: nama_kelompok}"""
    keys = {}
    for item in API_KEYS_RAW.split(","):
        name, _, key = item.strip().partition(":")
        if name.strip() and key.strip():
            keys[key.strip()] = name.strip()
    return keys
