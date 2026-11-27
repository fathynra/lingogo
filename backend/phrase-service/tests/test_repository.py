import pytest

from app import repository as repo, seed
from app.textutil import split_query

SORRY_ID = "Maaf, kota yang Anda cari tidak ada di database."


def test_split_query():
    assert split_query("Kota Surabaya") == ("surabaya", "kota")
    assert split_query("kab. malang") == ("malang", "kabupaten")
    assert split_query("BALI ") == ("bali", None)


def test_surabaya_uses_javanese(con):
    c = repo.search_cities(con, "id", q="surabaya").items[0]
    assert (c.code, c.name, c.province.name) == ("3578", "Surabaya", "Jawa Timur")
    assert c.languages[0].code == "jv_ID" and c.languages[0].name == "Jawa"


def test_every_province_is_searchable(con):
    for q, lang in [("padang", "min_ID"), ("medan", "bbc_ID"), ("banda aceh", "ace_ID"),
                    ("jayapura", "pmy_ID"), ("banjarmasin", "bjn_ID"), ("ambon", "abs_ID")]:
        assert repo.search_cities(con, "id", q=q).items[0].languages[0].code == lang


def test_search_ignores_case_and_matches_part(con):
    assert repo.search_cities(con, "id", q="SURABAYA").total == 1
    assert repo.search_cities(con, "id", q="yogya").items[0].code == "3471"


def test_kota_and_kabupaten_with_same_name(con):
    assert {c.type for c in repo.search_cities(con, "id", q="malang").items} == {"kota", "kabupaten"}
    assert [c.code for c in repo.search_cities(con, "id", q="Kota Malang").items] == ["3573"]
    assert repo.search_cities(con, "id", q="Kab. Malang").items[0].code == "3507"   # Pemalang ikut, tapi di bawah


@pytest.mark.parametrize("q", ["paris", "tokyo", "!!!", "Jawa Timur"])
def test_city_not_found(con, q):
    with pytest.raises(repo.NotFound) as e:
        repo.search_cities(con, "id", q=q)
    assert str(e.value) == SORRY_ID


def test_phrasebook_cards(con):
    b = repo.city_phrasebook(con, "3578", None, "id", "id")
    assert [c.code for c in b.categories] == ["greeting", "intro", "polite", "basic", "shopping", "help", "number"]
    card = b.categories[0].phrases[1]
    assert card.text == "Sugeng enjing"                       # istilah daerah
    assert card.pronunciation.guide == "SU-geng EN-jing"      # pelafalan
    assert card.meaning.text == "Selamat pagi"                # arti


def test_ui_and_pronunciation_language_are_separate(con):
    card = repo.city_phrasebook(con, "5171", None, "en", "id").categories[0].phrases[0]
    assert card.text == "Om Swastiastu" and card.meaning.text == "Hello" and card.pronunciation.style == "id"


def test_city_with_two_languages(con):
    b = repo.city_phrasebook(con, "3274", None, "id", "id")            # Kota Cirebon
    assert [l.code for l in b.available_languages] == ["jv_ID", "su_ID"]
    assert repo.city_phrasebook(con, "3274", "su_ID", "id", "id").language.code == "su_ID"
    with pytest.raises(repo.NotFound):
        repo.city_phrasebook(con, "3274", "ban_ID", "id", "id")


def test_approximate_language_uses_closest_data(con):
    mataram = repo.city_phrasebook(con, "5271", None, "id", "id")      # Sasak -> data Bali
    bali = repo.phrasebook(con, "ban_ID", "id", "id")
    assert mataram.language.is_approximate and mataram.language.closest_code == "ban_ID"
    assert mataram.categories[0].phrases[0].text == bali.categories[0].phrases[0].text


def test_new_language_data(con):
    p = repo.get_phrase(con, "polite_thanks", "min_ID", "en", "id")
    assert p.text == "Tarimo kasih" and p.meaning.text == "Thank you"


def test_update_translation(con):
    repo.update_translation(con, "basic_yes", "jv_ID", pron_id="ING-gih!")
    assert repo.get_phrase(con, "basic_yes", "jv_ID", "id", "id").pronunciation.guide == "ING-gih!"
    repo.update_translation(con, "basic_yes", "jv_ID", pron_id="ING-gih")


def test_reseed_only_when_csv_changes(db_copy, tmp_path, capsys):
    from app import db
    c = db.connect(tmp_path / "x.db")
    seed.ensure_seeded(c, db_copy)
    assert "diisi ulang" in capsys.readouterr().out
    seed.ensure_seeded(c, db_copy)
    assert "sudah sesuai" in capsys.readouterr().out
    p = db_copy / "emergency_numbers.csv"
    p.write_text(p.read_text(encoding="utf-8").replace("110", "111", 1), encoding="utf-8")
    seed.ensure_seeded(c, db_copy)
    assert c.execute("SELECT number FROM emergency_numbers WHERE service='police'").fetchone()[0] == "111"


def test_invalid_csv_keeps_old_data(db_copy, tmp_path):
    from app import dataset, db
    c = db.connect(tmp_path / "x.db")
    seed.ensure_seeded(c, db_copy)
    p = db_copy / "phrases.csv"
    p.write_text(p.read_text(encoding="utf-8").replace("Halo,Hello,Halo", "Halo,Hello,", 1), encoding="utf-8")
    with pytest.raises(dataset.DatasetError):
        seed.ensure_seeded(c, db_copy)
    assert c.execute("SELECT COUNT(*) FROM phrases").fetchone()[0] == 30
