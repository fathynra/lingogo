"""Validasi CSV: aturan 'tidak boleh ada sel kosong' & referensi antar berkas."""
import csv

import pytest

from app import dataset
from tests.conftest import FIXTURE_DB, REAL_DB


def _edit(path, fn):
    with open(path, encoding="utf-8", newline="") as f:
        rows = list(csv.reader(f))
    fn(rows)
    with open(path, "w", encoding="utf-8", newline="") as f:
        csv.writer(f, lineterminator="\n").writerows(rows)


def problems(db_dir, **kw):
    with pytest.raises(dataset.DatasetError) as e:
        dataset.load(db_dir, **kw)
    return e.value.problems


def test_fixture_and_real_database_are_valid():
    ds = dataset.load(FIXTURE_DB)
    assert len(ds.phrases) == 30 and len(ds.translations) == 30 * 4 and len(ds.pronunciations) == 30 * 4 * 2
    dataset.load(REAL_DB)          # data sungguhan harus selalu valid (mode longgar)


def test_empty_cell_is_rejected(fixture_copy):
    _edit(fixture_copy / "phrases.csv", lambda r: r[1].__setitem__(4, ""))        # greet_hello / jv_ID
    p = problems(fixture_copy)
    assert any("greet_hello" in x and "jv_ID" in x and "kosong" in x for x in p)


def test_empty_pronunciation_is_rejected(fixture_copy):
    _edit(fixture_copy / "phrases_pronunciation_id.csv", lambda r: r[5].__setitem__(3, ""))
    assert any("phrases_pronunciation_id.csv" in x and "kosong" in x for x in problems(fixture_copy))


def test_city_must_have_language_and_valid_references(fixture_copy):
    def f(r):
        r[1][4] = ""                       # kota pertama tanpa bahasa
        r[2][4] = "xx_ID"                  # bahasa tak dikenal
        r[3][3] = "99"                     # provinsi tak ada
    _edit(fixture_copy / "cities.csv", f)
    p = " | ".join(problems(fixture_copy))
    assert "kosong" in p and "bahasa tak dikenal 'xx_ID'" in p and "province_code '99'" in p


def test_language_columns_must_match_languages_csv(fixture_copy):
    _edit(fixture_copy / "languages.csv", lambda r: r.pop())                      # osi_ID dibuang
    assert any("kolom bahasa berbeda" in x for x in problems(fixture_copy))


def test_approximate_language_rules(fixture_copy):
    _edit(fixture_copy / "languages.csv", lambda r: r[4].__setitem__(4, "osi_ID"))  # approximate menunjuk dirinya
    assert any("approximate" in x for x in problems(fixture_copy))


def test_all_problems_reported_at_once(fixture_copy):
    _edit(fixture_copy / "phrases.csv", lambda r: [r[1].__setitem__(4, ""), r[2].__setitem__(5, "")])
    assert len(problems(fixture_copy)) >= 2


def test_full_mode_requires_38_provinces():
    p = problems(FIXTURE_DB, full=True)
    assert any("harus 38 provinsi" in x for x in p)


def test_missing_file(fixture_copy):
    (fixture_copy / "cities.csv").unlink()
    assert any("cities.csv: berkas tidak ditemukan" in x for x in problems(fixture_copy))
