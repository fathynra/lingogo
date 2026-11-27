import os
import shutil
import time
from pathlib import Path

import jwt
import pytest

DATABASE = Path(__file__).resolve().parents[3] / "database"   # lingogo/database
SECRET = "test-secret-test-secret-test-secret"


@pytest.fixture
def db_copy(tmp_path):
    """Salinan CSV yang boleh diubah oleh tes."""
    dst = tmp_path / "database"
    shutil.copytree(DATABASE, dst)
    return dst


@pytest.fixture(scope="session")
def con(tmp_path_factory):
    from app import db, seed
    c = db.connect(tmp_path_factory.mktemp("repo") / "p.db")
    seed.ensure_seeded(c, DATABASE)
    yield c
    c.close()


@pytest.fixture(scope="session")
def client(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("api")
    os.environ.update(DATABASE_DIR=str(DATABASE), DB_PATH=str(tmp / "p.db"), JWT_SECRET=SECRET,
                      API_KEYS="kelompokx:key-x")
    from fastapi.testclient import TestClient
    from app import config
    config.JWT_SECRET, config.API_KEYS_RAW = SECRET, os.environ["API_KEYS"]
    config.DATABASE_DIR, config.DB_PATH = DATABASE, tmp / "p.db"
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
