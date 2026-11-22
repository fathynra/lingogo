import os
import time
from pathlib import Path

import jwt
import pytest

# backend/phrase-service/tests -> repo root / tts  (bisa di-override dengan env TTS_DIR)
TTS = Path(os.getenv("TTS_DIR", Path(__file__).resolve().parents[3] / "tts"))
if not (TTS / "phrases.csv").is_file():
    pytest.skip(f"folder tts tidak ditemukan di {TTS}", allow_module_level=True)

SECRET = "test-secret-test-secret-test-secret"


@pytest.fixture(scope="session")
def client(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("lingogo")
    audio = tmp / "audio" / "de_DE"
    audio.mkdir(parents=True)
    (audio / "greet_hello.mp3").write_bytes(b"x")
    (audio / "greet_hello.wav").write_bytes(b"x")   # mp3 harus diprioritaskan
    os.environ.update(TTS_DIR=str(TTS), DB_PATH=str(tmp / "p.db"), AUDIO_DIR=str(tmp / "audio"),
                      JWT_SECRET=SECRET, API_KEYS="kelompokx:key-x,kelompoky:key-y")
    from fastapi.testclient import TestClient
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
