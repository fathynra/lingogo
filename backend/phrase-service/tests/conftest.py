import os
import shutil
import time
from pathlib import Path

import jwt
import pytest

HERE = Path(__file__).resolve().parent
FIXTURE_DB = HERE / "fixtures" / "database"      # data kecil & tetap khusus tes
REAL_DB = HERE.parents[2] / "database"           # lingogo/database (data sungguhan)
SECRET = "test-secret-test-secret-test-secret"


@pytest.fixture
def fixture_copy(tmp_path):
    """Salinan data tes yang boleh dirusak oleh tes."""
    dst = tmp_path / "database"
    shutil.copytree(FIXTURE_DB, dst)
    return dst


@pytest.fixture(scope="session")
def con(tmp_path_factory):
    """Koneksi SQLite yang sudah diisi dari data tes (untuk tes repository)."""
    from app import db, seed
    c = db.connect(tmp_path_factory.mktemp("repo") / "p.db")
    seed.ensure_seeded(c, FIXTURE_DB)
    yield c
    c.close()


@pytest.fixture(scope="session")
def client(tmp_path_factory):
    """Klien HTTP penuh. Dilewati otomatis bila fastapi/httpx belum terpasang."""
    pytest.importorskip("fastapi")
    pytest.importorskip("httpx")
    tmp = tmp_path_factory.mktemp("api")
    os.environ.update(DATABASE_DIR=str(FIXTURE_DB), DB_PATH=str(tmp / "p.db"), JWT_SECRET=SECRET,
                      API_KEYS="kelompokx:key-x,kelompoky:key-y")
    from fastapi.testclient import TestClient
    from app import config
    config.JWT_SECRET, config.API_KEYS_RAW = SECRET, os.environ["API_KEYS"]
    from app.main import app
    with TestClient(app) as c:
        yield c


def token(role="user", exp=3600, secret=SECRET):
    return jwt.encode({"sub": "1", "name": "Tes", "role": role, "iss": "lingogo",
                       "exp": int(time.time()) + exp}, secret, algorithm="HS256")


@pytest.fixture
def key():
    return {"X-API-Key": "key-x"}


@pytest.fixture
def user():
    return {"Authorization": f"Bearer {token()}"}


@pytest.fixture
def admin():
    return {"Authorization": f"Bearer {token('admin')}"}
