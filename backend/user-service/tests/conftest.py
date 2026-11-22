import os

import pytest

os.environ.update(JWT_SECRET="test-secret-test-secret-test-secret",
                  ADMIN_EMAIL="admin@lingogo.test", ADMIN_PASSWORD="admin-pass-123")


@pytest.fixture(scope="session")
def client(tmp_path_factory):
    os.environ["DB_PATH"] = str(tmp_path_factory.mktemp("u") / "u.db")
    from fastapi.testclient import TestClient
    from app.main import app
    with TestClient(app) as c:
        yield c


def reg_login(client, email="a@b.co", pw="password123", name="Bita"):
    client.post("/auth/register", json={"name": name, "email": email, "password": pw})
    r = client.post("/auth/login", json={"email": email, "password": pw})
    return r, {"Authorization": f"Bearer {r.json().get('token', '')}"}
