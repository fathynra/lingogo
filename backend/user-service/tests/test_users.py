import jwt
from tests.conftest import reg_login


def test_register_validation(client):
    ok = client.post("/auth/register", json={"name": "A", "email": "Z@Y.com", "password": "12345678"})
    assert ok.status_code == 201 and ok.json()["email"] == "z@y.com"
    assert "password" not in ok.text
    assert ok.json()["preferences"] == {"ui_language": "en", "pron_style": "en",
                                        "target_language": None, "default_destination": None}
    dup = client.post("/auth/register", json={"name": "A", "email": "z@y.com", "password": "12345678"})
    assert dup.status_code == 409
    assert client.post("/auth/register", json={"name": "A", "email": "z@y.com", "password": "pendek"}).status_code == 422
    assert client.post("/auth/register", json={"name": "A", "email": "bukan-email", "password": "12345678"}).status_code == 422


def test_login_and_me(client):
    r, h = reg_login(client)
    assert r.status_code == 200
    body = r.json()
    claims = jwt.decode(body["token"], "test-secret-test-secret-test-secret", algorithms=["HS256"], issuer="lingogo")
    assert claims["role"] == "user" and "jti" in claims
    assert client.get("/auth/me", headers=h).json()["email"] == "a@b.co"
    bad = client.post("/auth/login", json={"email": "a@b.co", "password": "salahsalah"})
    unk = client.post("/auth/login", json={"email": "tidak@ada.co", "password": "salahsalah"})
    assert bad.status_code == unk.status_code == 401 and bad.json() == unk.json()


def test_me_requires_token(client):
    assert client.get("/auth/me").status_code == 401
    assert client.get("/auth/me", headers={"Authorization": "Bearer ngawur"}).status_code == 401


def test_preferences(client):
    _, h = reg_login(client, "p@b.co")
    r = client.patch("/users/me/preferences", headers=h,
                     json={"ui_language": "id", "pron_style": "id", "target_language": "ja_JP",
                           "default_destination": "jp"})
    assert r.status_code == 200
    assert r.json() == {"ui_language": "id", "pron_style": "id", "target_language": "ja_JP",
                        "default_destination": "JP"}
    assert client.get("/users/me/preferences", headers=h).json()["ui_language"] == "id"
    part = client.patch("/users/me/preferences", headers=h, json={"pron_style": "en"}).json()
    assert part["pron_style"] == "en" and part["target_language"] == "ja_JP"
    cleared = client.patch("/users/me/preferences", headers=h, json={"target_language": ""}).json()
    assert cleared["target_language"] is None
    assert client.patch("/users/me/preferences", headers=h, json={"ui_language": "fr"}).status_code == 422
    assert client.patch("/users/me/preferences", headers=h, json={"target_language": "japan"}).status_code == 422
    assert client.patch("/users/me/preferences", headers=h, json={}).status_code == 422
    assert client.patch("/users/me/preferences", headers=h, json={"ui_language": None}).status_code == 422
    assert client.patch("/users/me/preferences", json={"ui_language": "en"}).status_code == 401


def test_logout_revokes_token(client):
    _, h = reg_login(client, "l@b.co")
    assert client.post("/auth/logout", headers=h).status_code == 204
    assert client.get("/auth/me", headers=h).status_code == 401


def test_admin_bootstrap(client):
    r = client.post("/auth/login", json={"email": "admin@lingogo.test", "password": "admin-pass-123"})
    assert r.status_code == 200 and r.json()["user"]["role"] == "admin"
