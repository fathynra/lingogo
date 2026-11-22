from tests.conftest import TTS, token


def test_health_public(client):
    r = client.get("/health")
    assert r.status_code == 200 and r.json()["phrases"] == 30


def test_requires_auth(client):
    assert client.get("/languages").status_code == 401
    assert client.get("/languages", headers={"X-API-Key": "salah"}).status_code == 401
    bad = {"Authorization": "Bearer " + token(secret="lain-lain-lain-lain-lain-lain-lain")}
    assert client.get("/languages", headers=bad).status_code == 401
    expired = {"Authorization": "Bearer " + token(exp=-10)}
    assert client.get("/languages", headers=expired).status_code == 401


def test_languages_and_ui_names(client, key):
    en = client.get("/languages", headers=key).json()
    assert len(en) == 44
    j = client.get("/languages/de_DE", headers=key).json()
    assert j["name"] == "German" and j["phrase_count"] == 30
    assert client.get("/languages/de_DE?ui=id", headers=key).json()["name"] == "Jerman"
    assert client.get("/languages/xx_XX", headers=key).status_code == 404


def test_destinations(client, user):
    d = {x["code"]: x for x in client.get("/destinations", headers=user).json()}
    assert d["CH"]["languages"] == ["de_DE", "fr_FR", "it_IT"]
    langs = client.get("/destinations/jp/languages", headers=user)
    assert langs.status_code == 404
    ok = client.get("/destinations/id/languages?ui=id", headers=user).json()
    assert {x["code"] for x in ok} == {"id_ID", "en_US"}


def test_phrases_source_and_pron(client, key):
    r = client.get("/phrases/greet_hello", params={"lang": "de_DE", "from": "id", "pron": "id"}, headers=key)
    j = r.json()
    assert r.status_code == 200
    assert j["source"] == {"lang": "id_ID", "text": "Halo"}
    assert j["target"]["text"] == "Hallo"
    assert j["target"]["pronunciation"] == {"style": "id", "guide": "HA-lo"}
    assert j["category"]["name"] == "Salam"
    e = client.get("/phrases/greet_hello", params={"lang": "de_DE", "from": "en", "pron": "en"}, headers=key).json()
    assert e["source"]["text"] == "Hello" and e["target"]["pronunciation"]["style"] == "en"
    assert e["category"]["name"] == "Greetings"


def test_phrase_list_filter_paging(client, key):
    r = client.get("/phrases", params={"lang": "fr_FR", "category": "number", "limit": 4}, headers=key).json()
    assert r["total"] == 10 and len(r["items"]) == 4
    q = client.get("/phrases", params={"lang": "fr_FR", "q": "merci"}, headers=key).json()
    assert q["total"] >= 1
    assert client.get("/phrases", params={"lang": "zz_ZZ"}, headers=key).status_code == 404
    assert client.get("/phrases", params={"lang": "fr_FR", "from": "jp"}, headers=key).status_code == 422
    assert client.get("/phrases", headers=key).status_code == 422
    assert client.get("/phrases", params={"lang": "fr_FR", "limit": 999}, headers=key).status_code == 422


def test_audio_url_prefers_mp3(client, key):
    j = client.get("/phrases/greet_hello", params={"lang": "de_DE"}, headers=key).json()
    assert j["target"]["audio_url"] == "/api/audio/de_DE/greet_hello.mp3"
    j = client.get("/phrases/greet_hello", params={"lang": "fr_FR"}, headers=key).json()
    assert j["target"]["audio_url"] is None
    assert client.get("/languages/de_DE", headers=key).json()["audio_count"] == 1


def test_categories(client, key):
    c = client.get("/categories?ui=id", headers=key).json()
    assert [x["code"] for x in c][:2] == ["greeting", "intro"] and c[0]["name"] == "Salam"
    assert sum(x["phrase_count"] for x in c) == 30


def test_admin_authorization(client, key, user, admin):
    url = "/phrases/basic_yes/translations/de_DE"
    body = {"pronunciation_id": "YA-test"}
    assert client.put(url, json=body).status_code == 401
    assert client.put(url, json=body, headers=key).status_code == 403
    assert client.put(url, json=body, headers=user).status_code == 403
    r = client.put(url, json=body, headers=admin)
    assert r.status_code == 200
    got = client.get("/phrases/basic_yes", params={"lang": "de_DE", "pron": "id"}, headers=key).json()
    assert got["target"]["pronunciation"]["guide"] == "YA-test"
    assert client.put(url, json={}, headers=admin).status_code == 422
    assert client.put("/phrases/nope/translations/de_DE", json=body, headers=admin).status_code == 404


def test_emergency_numbers_per_destination(client, key):
    de = client.get("/destinations/de/emergency-numbers", headers=key).json()
    assert de == {"destination": "DE", "name": "Germany", "available": True,
                  "numbers": {"police": "110", "fire": "112", "ambulance": "112"}}
    idn = client.get("/destinations/ID/emergency-numbers?ui=id", headers=key).json()
    assert idn["name"] == "Indonesia" and idn["numbers"]["police"] == "110"
    # GB dipakai dua bahasa (en_GB & cy_GB) -> satu set nomor
    assert client.get("/destinations/GB/emergency-numbers", headers=key).json()["numbers"]["police"] == "999"
    # ambulans Kongo kosong di CSV -> null, tapi negara tetap tersedia
    cd = client.get("/destinations/CD/emergency-numbers", headers=key).json()
    assert cd["available"] is True and cd["numbers"]["ambulance"] is None and cd["numbers"]["police"]
    # Swiss tak ada di emergency_numbers.csv (tak punya locale sendiri)
    ch = client.get("/destinations/CH/emergency-numbers", headers=key).json()
    assert ch["available"] is False and ch["numbers"] == {"police": None, "fire": None, "ambulance": None}
    assert client.get("/destinations/XX/emergency-numbers", headers=key).status_code == 404
    assert client.get("/destinations/DE/emergency-numbers").status_code == 401


def test_emergency_list(client, user):
    lst = client.get("/emergency-numbers?ui=id", headers=user).json()
    assert len(lst) == 42 and sum(x["available"] for x in lst) == 40


def test_reseed_only_when_sources_change(tmp_path, capsys):
    import shutil
    from app import config, db, seed
    src = tmp_path / "tts"
    shutil.copytree(TTS, src, ignore=shutil.ignore_patterns("out", "__pycache__"))
    con = db.connect(tmp_path / "x.db")
    seed.ensure_seeded(con, src, config.DATA_DIR)
    assert "diisi ulang" in capsys.readouterr().out
    seed.ensure_seeded(con, src, config.DATA_DIR)
    assert "tidak diisi ulang" in capsys.readouterr().out
    (src / "emergency_numbers.csv").write_text(
        (src / "emergency_numbers.csv").read_text(encoding="utf-8-sig").replace("112,110,100,999", "112,110,100,998", 1),
        encoding="utf-8")
    seed.ensure_seeded(con, src, config.DATA_DIR)
    assert "diisi ulang" in capsys.readouterr().out
    assert con.execute("SELECT COUNT(*) FROM phrases").fetchone()[0] == 30
