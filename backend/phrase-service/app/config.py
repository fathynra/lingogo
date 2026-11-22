import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

DB_PATH = Path(os.getenv("DB_PATH", "/data/phrases.db"))
# Data master milik backend (bahasa, destinasi, kategori) ikut di image
DATA_DIR = Path(os.getenv("DATA_DIR", str(BASE_DIR / "data")))
# Folder tts/ milik repo (phrases.csv, pelafalan, voices.json, emergency_numbers.csv): sumber kebenaran, read-only
TTS_DIR = Path(os.getenv("TTS_DIR", "/tts"))
# Audio hasil generate.py: <AUDIO_DIR>/<lang>/<key>.wav (atau .mp3 jika dikonversi)
AUDIO_DIR = Path(os.getenv("AUDIO_DIR", "/audio"))
# Prefix URL audio yang dikembalikan ke client. Kosong = path relatif (/api/audio/...).
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "").rstrip("/")
AUDIO_URL_PREFIX = "/api/audio"

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
