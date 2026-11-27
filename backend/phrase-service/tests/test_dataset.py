import csv

import pytest

from app import dataset
from tests.conftest import DATABASE


def edit(path, fn):
    with open(path, encoding="utf-8", newline="") as f:
        rows = list(csv.reader(f))
    fn(rows)
    with open(path, "w", encoding="utf-8", newline="") as f:
        csv.writer(f, lineterminator="\n").writerows(rows)


def problems(folder):
    with pytest.raises(dataset.DatasetError) as e:
        dataset.load(folder)
    return " | ".join(e.value.problems)


def test_real_database_is_valid():
    ds = dataset.load(DATABASE)
    assert len(ds.provinces) == 38 and len(ds.cities) == 514 and len(ds.phrases) == 30


def test_empty_cell_rejected(db_copy):
    edit(db_copy / "phrases.csv", lambda r: r[1].__setitem__(4, ""))
    assert "kosong" in problems(db_copy)


def test_unknown_language_and_province_rejected(db_copy):
    def f(r):
        r[1][4] = "xx_ID"
        r[2][3] = "99"
    edit(db_copy / "cities.csv", f)
    p = problems(db_copy)
    assert "bahasa tak dikenal 'xx_ID'" in p and "province_code '99'" in p


def test_approximate_must_point_to_language_with_data(db_copy):
    def f(r):
        for row in r:
            if row[0] == "sas_ID":
                row[4] = "mak_ID"        # mak_ID sendiri juga perkiraan
    edit(db_copy / "languages.csv", f)
    assert "sas_ID closest_code 'mak_ID'" in problems(db_copy)


def test_missing_file(db_copy):
    (db_copy / "cities.csv").unlink()
    assert "cities.csv: berkas tidak ditemukan" in problems(db_copy)
