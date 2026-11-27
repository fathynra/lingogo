"""Tes HTTP penuh (butuh fastapi + httpx; dilewati otomatis jika belum terpasang)."""
from tests.conftest import token


def test_health_public(client):
    j = client.get("/health").json()
    assert j["status"] == "ok" and j["phrases"] == 30 and j["cities"] == 17


def test_requires_auth(client):
    assert client.get("/provinces").status_code == 401
    assert client.get("/provinces", headers={"X-API-Key": "salah"}).status_code == 401
    bad = {"Authorization": "Bearer " + token(secret="lain-lain-lain-lain-lain-lain-lain")}
    assert client.get("/cities?q=surabaya", headers=bad).status_code == 401
    assert client.get("/cities?q=surabaya", headers={"Authorization": "Bearer " + token(exp=-10)}).status_code == 401


def test_search_city_flow(client, user):
    r = client.get("/cities", params={"q": "surabaya", "ui": "id"}, headers=user)
    assert r.status_code == 200
    c = r.json()["items"][0]
    assert c["name"] == "Surabaya" and c["province"]["name"] == "Jawa Timur" and c["languages"][0]["code"] == "jv_ID"


def test_city_not_found_message(client, user):
    r = client.get("/cities", params={"q": "atlantis", "ui": "id"}, headers=user)
    assert r.status_code == 404 and r.json() == {"detail": "Maaf, kota yang Anda cari tidak ada di database."}
    r = client.get("/cities", params={"q": "atlantis", "ui": "en"}, headers=user)
    assert r.json()["detail"] == "Sorry, the city you are looking for is not in our database."
    assert client.get("/cities/0000", headers=user).status_code == 404
    assert client.get("/cities", params={"q": "x", "type": "desa"}, headers=user).status_code == 422


def test_province_endpoints(client, key):
    assert len(client.get("/provinces", headers=key).json()) == 6
    assert len(client.get("/provinces/51/cities", headers=key).json()["items"]) == 3
    assert client.get("/provinces/00/cities", headers=key).status_code == 404


def test_city_phrasebook(client, key):
    j = client.get("/cities/3578/phrasebook", params={"ui": "id"}, headers=key).json()
    assert j["language"]["code"] == "jv_ID" and j["categories"][0]["name"] == "Salam"
    card = j["categories"][0]["phrases"][0]
    assert card["pronunciation"]["style"] == "id"                       # pron mengikuti ui
    en = client.get("/cities/3578/phrasebook", params={"ui": "en", "pron": "id"}, headers=key).json()
    assert en["categories"][0]["phrases"][0]["meaning"]["text"] == "Hello"
    assert en["categories"][0]["phrases"][0]["pronunciation"]["style"] == "id"
    assert client.get("/cities/3274/phrasebook", params={"lang": "su_ID"}, headers=key).json()["language"]["code"] == "su_ID"
    assert client.get("/cities/3274/phrasebook", params={"lang": "ban_ID"}, headers=key).status_code == 404
    assert client.get("/cities/3578/phrasebook", params={"ui": "fr"}, headers=key).status_code == 422


def test_flat_phrases_paging(client, key):
    r = client.get("/phrases", params={"lang": "jv_ID", "category": "number", "limit": 4}, headers=key).json()
    assert r["total"] == 10 and len(r["items"]) == 4
    assert client.get("/phrases", params={"lang": "zz_ID"}, headers=key).status_code == 404
    assert client.get("/phrases", headers=key).status_code == 422
    assert client.get("/phrases", params={"lang": "jv_ID", "limit": 999}, headers=key).status_code == 422
    one = client.get("/phrases/greet_hello", params={"lang": "ban_ID", "ui": "id", "pron": "en"}, headers=key).json()
    assert one["text"] == "Om Swastiastu" and one["pronunciation"]["guide"] == "ohm swah-stee-AH-stoo"


def test_languages_and_categories(client, key):
    ls = client.get("/languages", params={"ui": "id"}, headers=key).json()
    assert len(ls) == 4 and {l["code"] for l in ls if l["is_approximate"]} == {"osi_ID"}
    assert client.get("/languages/xx_ID", headers=key).status_code == 404
    cs = client.get("/categories", params={"ui": "id"}, headers=key).json()
    assert sum(c["phrase_count"] for c in cs) == 30


def test_admin_authorization(client, key, user, admin):
    url = "/phrases/basic_yes/translations/jv_ID"
    body = {"pronunciation_id": "YA-test"}
    assert client.put(url, json=body).status_code == 401
    assert client.put(url, json=body, headers=key).status_code == 403
    assert client.put(url, json=body, headers=user).status_code == 403
    assert client.put(url, json=body, headers=admin).status_code == 200
    got = client.get("/phrases/basic_yes", params={"lang": "jv_ID", "pron": "id"}, headers=key).json()
    assert got["pronunciation"]["guide"] == "YA-test"
    assert client.put(url, json={}, headers=admin).status_code == 422
    assert client.put("/phrases/nope/translations/jv_ID", json=body, headers=admin).status_code == 404


def test_emergency_numbers(client, key):
    e = {x["service"]: x for x in client.get("/emergency-numbers", params={"ui": "id"}, headers=key).json()}
    assert e["police"]["number"] == "110" and len(e) == 5
