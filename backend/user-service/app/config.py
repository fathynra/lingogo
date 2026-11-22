import os
from pathlib import Path

DB_PATH = Path(os.getenv("DB_PATH", "/data/users.db"))
JWT_SECRET = os.getenv("JWT_SECRET", "")
JWT_ISSUER = "lingogo"
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", str(60 * 24 * 7)))
# Admin awal (opsional): dibuat saat start jika belum ada
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "")
# Akun uji untuk kelompok lain & penilai (opsional)
DEMO_EMAIL = os.getenv("DEMO_EMAIL", "")
DEMO_PASSWORD = os.getenv("DEMO_PASSWORD", "")
