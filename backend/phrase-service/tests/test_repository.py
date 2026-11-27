"""Tes logika bisnis (tanpa HTTP): pencarian kota, phrasebook, kartu frasa."""
import pytest

from app import repository as repo, seed
from app.textutil import normalize, split_query


def test_normalize_and_split_query():
    assert normalize("  Yogyákarta!! ") == "yogyakarta"
    assert split_query("Kota Surabaya") == ("surabaya", "kota")
    assert split_query("kab. malang") == ("malang", "kabupaten")
    assert split_query("Kabupaten  Bogor") == ("bogor", "kabupaten")
    assert split_query("kota administrasi jakarta") == ("jakarta", "kota")
    assert split_query("bali") == ("bali", None)


def test_search_surabaya_returns_javanese(con):
    r = repo.search_cities(con, "id", q="surabaya")
    assert r.total == 1
    c = r.items[0]
    assert (c.code, c.name, c.type, c.province.name) == ("3578", "Surabaya", "kota", "Jawa Timur")
    assert [l.code for l in c.languages] == ["jv_ID"] and c.languages[0].name == "Jawa"


def test_search_is_case_accent_and_partial_insensitive(con):
    assert repo.search_cities(con, "id", q="SURABAYA").total == 1
    assert repo.search_cities(con, "id", q="yogya").items[0].code == "3471"
    assert {c.code for c in repo.search_cities(con, "id", q="ang").items} >= {"3507", "3573", "3374", "3671"}


def test_same_name_city_and_regency(con):
    r = repo.search_cities(con, "en", q="malang")
    assert {(c.code, c.type) for c in r.items} == {("3573", "kota"), ("3507", "kabupaten")}
    assert [c.code for c in repo.search_cities(con, "en", q="Kota Malang").items] == ["3573"]
    assert [c.code for c in repo.search_cities(con, "en", q="Kab. Malang").items] == ["3507"]
    assert [c.code for c in repo.search_cities(con, "en", q="malang", type="kabupaten").items] == ["3507"]


def test_search_ranking_exact_then_prefix_then_word_then_contains(con):
    con.executemany("INSERT INTO cities VALUES (?,?,?,?,?)", [
        ("3599", "Kemalang", "kemalang", "kabupaten", "35"),        # mengandung
        ("3598", "Malang Timur", "malang timur", "kabupaten", "35"),  # diawali
        ("3597", "Pulau Malang", "pulau malang", "kabupaten", "35"),  # awal kata ke-2
    ])
    con.executemany("INSERT INTO city_languages VALUES (?,?,?)", [(c, "jv_ID", 0) for c in ("3599", "3598", "3597")])
    try:
        r = repo.search_cities(con, "id", q="malang")
        assert [c.code for c in r.items] == ["3507", "3573", "3598", "3597", "3599"]
        assert [c.type for c in repo.search_cities(con, "id", q="bogor").items] == ["kabupaten", "kota"]
    finally:
        con.execute("DELETE FROM city_languages WHERE city_code IN ('3599','3598','3597')")
        con.execute("DELETE FROM cities WHERE code IN ('3599','3598','3597')")
        con.commit()


@pytest.mark.parametrize("q,ui,msg", [
    ("atlantis", "id", "Maaf, kota yang Anda cari tidak ada di database."),
    ("atlantis", "en", "Sorry, the city you are looking for is not in our database."),
    ("!!!", "id", "Maaf, kota yang Anda cari tidak ada di database."),
    ("Jawa Timur", "id", "Maaf, kota yang Anda cari tidak ada di database."),   # nama provinsi bukan kota
])
def test_search_not_found_message(con, q, ui, msg):
    with pytest.raises(repo.NotFound) as e:
        repo.search_cities(con, ui, q=q)
    assert str(e.value) == msg


def test_list_without_q_is_paged_and_filterable(con):
    allc = repo.search_cities(con, "id")
    assert allc.total == 17
    bali = repo.search_cities(con, "id", province="51")
    assert {c.name for c in bali.items} == {"Badung", "Gianyar", "Denpasar"}
    page = repo.search_cities(con, "id", limit=5, offset=5)
    assert len(page.items) == 5 and page.total == 17
    assert repo.search_cities(con, "id", province="99").total == 0     # tanpa q: kosong, bukan error


def test_multi_language_city_and_approximate_language(con):
    cirebon = repo.get_city(con, "3274", "id")
    assert [l.code for l in cirebon.languages] == ["jv_ID", "su_ID"]
    bwi = repo.get_city(con, "3510", "en")
    osing = bwi.languages[0]
    assert osing.code == "osi_ID" and osing.is_approximate and osing.closest_code == "jv_ID"
    assert not bwi.languages[1].is_approximate and bwi.languages[1].closest_code == "jv_ID"
    with pytest.raises(repo.NotFound):
        repo.get_city(con, "0000", "id")


def test_provinces(con):
    ps = repo.list_provinces(con, "en")
    assert [p.code for p in ps] == ["32", "33", "34", "35", "36", "51"]
    assert ps[3].name == "East Java" and ps[3].languages[0].name == "Javanese"
    assert repo.get_province(con, "51", "id").languages[0].native_name == "Basa Bali"
    with pytest.raises(repo.NotFound):
        repo.get_province(con, "00", "id")


def test_city_phrasebook_grouped_by_category(con):
    b = repo.city_phrasebook(con, "3578", None, "id", "id")
    assert b.city.name == "Surabaya" and b.language.code == "jv_ID"
    assert [c.code for c in b.categories] == ["greeting", "intro", "polite", "basic", "shopping", "help", "number"]
    assert sum(len(c.phrases) for c in b.categories) == 30
    assert all(c.phrase_count == len(c.phrases) for c in b.categories)
    assert b.categories[0].name == "Salam"
    card = b.categories[0].phrases[1]
    assert card.key == "greet_morning"
    assert card.text == "Sugeng enjing"                                   # istilah daerah
    assert card.pronunciation.style == "id" and card.pronunciation.guide == "SU-geng EN-jing"
    assert card.meaning.lang == "id" and card.meaning.text == "Selamat pagi"


def test_ui_and_pron_are_independent(con):
    b = repo.city_phrasebook(con, "5171", None, "en", "id")                # arti Inggris, pelafalan Indonesia
    card = b.categories[0].phrases[0]
    assert card.text == "Om Swastiastu" and card.meaning.text == "Hello" and card.pronunciation.style == "id"
    assert b.categories[0].name == "Greetings" and b.city.province.name == "Bali"
    e = repo.city_phrasebook(con, "5171", None, "id", "en").categories[0].phrases[0]
    assert e.meaning.text == "Halo" and e.pronunciation.guide == "ohm swah-stee-AH-stoo"


def test_multi_language_city_phrasebook_choice(con):
    d = repo.city_phrasebook(con, "3274", None, "id", "id")
    assert d.language.code == "jv_ID" and [l.code for l in d.available_languages] == ["jv_ID", "su_ID"]
    s = repo.city_phrasebook(con, "3274", "su_ID", "id", "id")
    assert s.language.code == "su_ID" and s.categories[0].phrases[0].text == "Halo"
    with pytest.raises(repo.NotFound):
        repo.city_phrasebook(con, "3274", "ban_ID", "id", "id")           # bukan bahasa kota ini


def test_approximate_language_has_complete_copy_no_empty(con):
    osi = repo.phrasebook(con, "osi_ID", "id", "id")
    jv = repo.phrasebook(con, "jv_ID", "id", "id")
    assert [p.text for c in osi.categories for p in c.phrases] == [p.text for c in jv.categories for p in c.phrases]
    assert osi.language.is_approximate


def test_no_null_or_empty_anywhere_in_database(con):
    for tbl, col in (("translations", "text"), ("pronunciations", "guide"), ("phrases", "meaning_id"),
                     ("phrases", "meaning_en"), ("cities", "name"), ("city_languages", "language_code")):
        assert con.execute(f"SELECT COUNT(*) FROM {tbl} WHERE {col} IS NULL OR TRIM({col})=''").fetchone()[0] == 0
    # setiap kota punya >= 1 bahasa
    assert con.execute("SELECT COUNT(*) FROM cities c WHERE NOT EXISTS "
                       "(SELECT 1 FROM city_languages x WHERE x.city_code=c.code)").fetchone()[0] == 0


def test_flat_phrase_list_get_and_search(con):
    r = repo.list_phrases(con, "jv_ID", "id", "id", category="number", limit=4)
    assert r.total == 10 and len(r.items) == 4 and r.items[0].key == "num_1" and r.items[0].text == "Siji"
    q = repo.list_phrases(con, "su_ID", "en", "en", q="terima")                 # cari di arti Indonesia
    assert any(i.key == "polite_thanks" for i in q.items)
    p = repo.get_phrase(con, "shop_how_much", "ban_ID", "en", "en")
    assert p.text == "Aji kuda niki?" and p.meaning.text == "How much is this?" and p.category.name == "Shopping"
    with pytest.raises(repo.NotFound):
        repo.get_phrase(con, "nope", "ban_ID", "en", "en")
    with pytest.raises(repo.NotFound):
        repo.list_phrases(con, "zz_ID", "en", "en")


def test_update_translation(con):
    repo.update_translation(con, "basic_yes", "jv_ID", pron_id="ING-gih!")
    assert repo.get_phrase(con, "basic_yes", "jv_ID", "id", "id").pronunciation.guide == "ING-gih!"
    repo.update_translation(con, "basic_yes", "jv_ID", pron_id="ING-gih")      # kembalikan
    with pytest.raises(repo.NotFound):
        repo.update_translation(con, "basic_yes", "xx_ID", text="x")


def test_emergency_numbers(con):
    e = {x.service: x for x in repo.emergency_numbers(con, "id")}
    assert e["police"].number == "110" and e["police"].name == "Polisi" and e["general"].number == "112"
    assert repo.emergency_numbers(con, "en")[0].name == "Police"


def test_reseed_only_when_csv_changes(fixture_copy, tmp_path, capsys):
    from app import db
    c = db.connect(tmp_path / "x.db")
    seed.ensure_seeded(c, fixture_copy)
    assert "diisi ulang" in capsys.readouterr().out
    seed.ensure_seeded(c, fixture_copy)
    assert "tidak diisi ulang" in capsys.readouterr().out
    p = fixture_copy / "emergency_numbers.csv"
    p.write_text(p.read_text(encoding="utf-8").replace("110", "111", 1), encoding="utf-8")
    seed.ensure_seeded(c, fixture_copy)
    assert "diisi ulang" in capsys.readouterr().out
    assert c.execute("SELECT number FROM emergency_numbers WHERE service='police'").fetchone()[0] == "111"


def test_invalid_csv_does_not_wipe_existing_data(fixture_copy, tmp_path):
    from app import dataset, db
    c = db.connect(tmp_path / "x.db")
    seed.ensure_seeded(c, fixture_copy)
    p = fixture_copy / "phrases.csv"
    p.write_text(p.read_text(encoding="utf-8").replace("Halo,Hello,Halo", "Halo,Hello,", 1), encoding="utf-8")
    with pytest.raises(dataset.DatasetError):
        seed.ensure_seeded(c, fixture_copy)
    assert c.execute("SELECT COUNT(*) FROM phrases").fetchone()[0] == 30


def test_old_world_database_is_rebuilt(tmp_path):
    """Database versi dunia (skema lama) dibuang & dibuat ulang, bukan menabrak."""
    from app import db
    c = db.connect(tmp_path / "old.db")
    c.executescript("CREATE TABLE languages (code TEXT PRIMARY KEY, name_en TEXT, name_id TEXT, "
                    "native_name TEXT, country_code TEXT, voice TEXT); CREATE TABLE destinations (code TEXT);")
    c.commit()
    from tests.conftest import FIXTURE_DB
    seed.ensure_seeded(c, FIXTURE_DB)
    assert c.execute("SELECT COUNT(*) FROM languages").fetchone()[0] == 4
    assert not c.execute("SELECT 1 FROM sqlite_master WHERE name='destinations'").fetchone()
