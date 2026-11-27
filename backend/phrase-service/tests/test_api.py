from tests.conftest import token


def test_health(client):
    j = client.get("/health").json()
    assert j["status"] == "ok" and j["phrases"] == 30 and j["cities"] == 514


def test_auth_required(client):
    assert client.get("/provinces").status_code == 401
    assert client.get("/provinces", headers={"X-API-Key": "salah"}).status_code == 401
    expired = {"Authorization": "Bearer " + token(exp=-10)}
    assert client.get("/cities?q=surabaya", headers=expired).status_code == 401


def test_search_flow(client, user):
    r = client.get("/cities", params={"q": "surabaya", "ui": "id"}, headers=user)
    assert r.status_code == 200 and r.json()["items"][0]["languages"][0]["code"] == "jv_ID"
    r = client.get("/cities", params={"q": "singapura", "ui": "id"}, headers=user)
    assert r.status_code == 404 and r.json() == {"detail": "Maaf, kota yang Anda cari tidak ada di database."}
    r = client.get("/cities", params={"q": "singapura", "ui": "en"}, headers=user)
    assert r.json()["detail"] == "Sorry, the city you are looking for is not in our database."


def test_city_phrasebook(client, key):
    j = client.get("/cities/3578/phrasebook", params={"ui": "id"}, headers=key).json()
    card = j["categories"][0]["phrases"][0]
    assert j["language"]["code"] == "jv_ID" and j["categories"][0]["name"] == "Salam"
    assert set(card) == {"key", "text", "pronunciation", "meaning"}
    assert client.get("/cities/3578/phrasebook", params={"ui": "fr"}, headers=key).status_code == 422


def test_provinces_and_languages(client, key):
    assert len(client.get("/provinces", headers=key).json()) == 38
    langs = client.get("/languages", headers=key).json()
    assert {l["code"] for l in langs if not l["is_approximate"]} >= {"jv_ID", "min_ID", "bug_ID"}


def test_only_admin_can_edit(client, key, user, admin):
    url = "/phrases/basic_yes/translations/jv_ID"
    body = {"pronunciation_id": "YA"}
    assert client.put(url, json=body).status_code == 401
    assert client.put(url, json=body, headers=key).status_code == 403
    assert client.put(url, json=body, headers=user).status_code == 403
    assert client.put(url, json=body, headers=admin).status_code == 200


def test_emergency_numbers(client, key):
    e = {x["service"]: x["number"] for x in client.get("/emergency-numbers", headers=key).json()}
    assert e["police"] == "110" and e["general"] == "112"
