"""Baca dan cek CSV di folder database/.

Bahasa yang closest_code-nya bukan dirinya sendiri dianggap "perkiraan": tidak punya kolom
di phrases.csv, isinya diambil dari bahasa terdekat saat seed.
"""
import csv
import hashlib
from dataclasses import dataclass
from pathlib import Path

FILES = ("languages.csv", "provinces.csv", "cities.csv", "categories.csv", "phrases.csv",
         "phrases_pronunciation_en.csv", "phrases_pronunciation_id.csv", "emergency_numbers.csv")
PROVINCE_COUNT = 38


class DatasetError(Exception):
    def __init__(self, problems):
        self.problems = problems
        super().__init__(f"{len(problems)} masalah data:\n  - " + "\n  - ".join(problems[:30]))


@dataclass
class Dataset:
    languages: list
    provinces: list
    cities: list
    categories: list
    phrases: list
    pron_en: dict      # key -> row
    pron_id: dict
    emergency: list
    native: list       # bahasa yang punya data sendiri, urut sesuai kolom phrases.csv


def read(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        r = csv.DictReader(f)
        return list(r.fieldnames or []), list(r)


def source_hash(folder: Path) -> str:
    h = hashlib.sha256()
    for name in FILES:
        h.update(name.encode() + (folder / name).read_bytes())
    return h.hexdigest()


def load(folder: Path) -> Dataset:
    missing = [n for n in FILES if not (folder / n).is_file()]
    if missing:
        raise DatasetError([f"{n}: berkas tidak ditemukan di {folder}" for n in missing])

    data = {n: read(folder / n) for n in FILES}
    problems = []

    # tidak boleh ada sel kosong di berkas mana pun
    for name, (header, rows) in data.items():
        for i, row in enumerate(rows, start=2):
            for col in header:
                if not (row.get(col) or "").strip():
                    problems.append(f"{name} baris {i}: kolom '{col}' kosong")

    _, languages = data["languages.csv"]
    codes = {l["code"] for l in languages}
    native_set = {l["code"] for l in languages if l["closest_code"] == l["code"]}
    for l in languages:
        if l["closest_code"] not in native_set:
            problems.append(f"languages.csv: {l['code']} closest_code '{l['closest_code']}' "
                            "harus bahasa yang punya data sendiri")

    _, categories = data["categories.csv"]
    cat_codes = {c["code"] for c in categories}

    _, provinces = data["provinces.csv"]
    for p in provinces:
        p["languages"] = [x for x in p["languages"].split(";") if x]
        for l in p["languages"]:
            if l not in codes:
                problems.append(f"provinces.csv: {p['code']} memakai bahasa tak dikenal '{l}'")
    prov_codes = {p["code"] for p in provinces}
    if len(provinces) != PROVINCE_COUNT:
        problems.append(f"provinces.csv: harus {PROVINCE_COUNT} provinsi, ada {len(provinces)}")

    _, cities = data["cities.csv"]
    for c in cities:
        c["languages"] = [x for x in c["languages"].split(";") if x]
        if c["type"] not in ("kota", "kabupaten"):
            problems.append(f"cities.csv: {c['code']} type harus kota atau kabupaten")
        if c["province_code"] not in prov_codes:
            problems.append(f"cities.csv: {c['code']} province_code '{c['province_code']}' tidak ada")
        for l in c["languages"]:
            if l not in codes:
                problems.append(f"cities.csv: {c['code']} memakai bahasa tak dikenal '{l}'")
    missing_city = prov_codes - {c["province_code"] for c in cities}
    for p in sorted(missing_city):
        problems.append(f"cities.csv: provinsi {p} belum punya kota")

    header, phrases = data["phrases.csv"]
    native = [h for h in header if h not in ("key", "category", "id_ID", "en_US")]
    if set(native) != native_set:
        problems.append(f"phrases.csv: kolom bahasa harus sama dengan bahasa yang punya data sendiri "
                        f"(beda: {sorted(set(native) ^ native_set)})")
    for p in phrases:
        if p["category"] not in cat_codes:
            problems.append(f"phrases.csv: {p['key']} kategori '{p['category']}' tidak ada")

    keys = [p["key"] for p in phrases]
    pron = {}
    for style in ("en", "id"):
        name = f"phrases_pronunciation_{style}.csv"
        h, rows = data[name]
        if [r["key"] for r in rows] != keys:
            problems.append(f"{name}: daftar key harus sama dan berurutan dengan phrases.csv")
        if h[2:] != native:
            problems.append(f"{name}: kolom bahasa harus sama dengan phrases.csv")
        pron[style] = {r["key"]: r for r in rows}

    _, emergency = data["emergency_numbers.csv"]
    for e in emergency:
        if not e["number"].isdigit():
            problems.append(f"emergency_numbers.csv: nomor {e['service']} bukan angka")

    if problems:
        raise DatasetError(problems)
    return Dataset(languages, provinces, cities, categories, phrases,
                   pron["en"], pron["id"], emergency, native)
