"""Membaca & memvalidasi folder database/ (CSV). Tidak bergantung pada FastAPI maupun SQLite.

Dipakai oleh seed.py (isi database saat service start) dan tools/check_data.py (cek sebelum deploy).
Aturan utama: TIDAK BOLEH ADA sel kosong. Bahasa yang belum punya data asli diisi salinan
bahasa terdekat (duplikat tidak apa-apa) dan ditandai status=approximate di languages.csv.

Berkas di database/:
  languages.csv                  code,name_id,name_en,native_name,closest_code,status
  provinces.csv                  code,name_id,name_en,languages          (languages: a;b;c, pertama = utama)
  cities.csv                     code,name,type,province_code,languages  (type: kota|kabupaten)
  categories.csv                 code,name_en,name_id,sort_order
  phrases.csv                    key,category,id_ID,en_US,<satu kolom per bahasa daerah>
  phrases_pronunciation_en.csv   key,category,<kolom bahasa daerah>   (dibaca pembicara Inggris)
  phrases_pronunciation_id.csv   key,category,<kolom bahasa daerah>   (dibaca pembicara Indonesia)
  emergency_numbers.csv          service,name_id,name_en,number
"""
import csv
import hashlib
from dataclasses import dataclass, field
from pathlib import Path

FILES = ("languages.csv", "provinces.csv", "cities.csv", "categories.csv", "phrases.csv",
         "phrases_pronunciation_en.csv", "phrases_pronunciation_id.csv", "emergency_numbers.csv")
MEANING_COLS = ("id_ID", "en_US")           # kolom arti di phrases.csv (bukan bahasa daerah)
CITY_TYPES = ("kota", "kabupaten")
LANG_STATUS = ("native", "approximate")
EXPECTED_PROVINCES = 38


class DatasetError(Exception):
    """Berisi daftar semua masalah data (bukan hanya yang pertama)."""

    def __init__(self, problems: list[str]):
        self.problems = problems
        super().__init__(f"{len(problems)} masalah data:\n  - " + "\n  - ".join(problems[:50])
                         + ("\n  - ..." if len(problems) > 50 else ""))


@dataclass
class Dataset:
    languages: list[dict] = field(default_factory=list)
    provinces: list[dict] = field(default_factory=list)   # languages: list[str]
    cities: list[dict] = field(default_factory=list)      # languages: list[str]
    categories: list[dict] = field(default_factory=list)
    phrases: list[dict] = field(default_factory=list)     # {key, category, meaning_id, meaning_en}
    translations: dict = field(default_factory=dict)      # (key, lang) -> text
    pronunciations: dict = field(default_factory=dict)    # (key, lang, style) -> guide
    emergency: list[dict] = field(default_factory=list)


def read_csv(path: Path) -> tuple[list[str], list[dict]]:
    with open(path, encoding="utf-8-sig", newline="") as f:
        r = csv.DictReader(f)
        return list(r.fieldnames or []), list(r)


def source_hash(database_dir: Path) -> str:
    h = hashlib.sha256()
    for n in FILES:
        h.update(n.encode())
        h.update((database_dir / n).read_bytes())
    return h.hexdigest()


def _split(v: str) -> list[str]:
    return [x.strip() for x in v.split(";") if x.strip()]


def load(database_dir: Path, full: bool = False) -> Dataset:
    """Muat semua CSV. Raise DatasetError (berisi semua masalah) bila tidak valid.

    full=True menambah syarat kelengkapan akhir: tepat 38 provinsi, tiap provinsi punya >=1 kota.
    """
    problems: list[str] = []
    ds = Dataset()
    raw: dict[str, tuple[list[str], list[dict]]] = {}
    for n in FILES:
        p = database_dir / n
        if not p.is_file():
            problems.append(f"{n}: berkas tidak ditemukan di {database_dir}")
            continue
        raw[n] = read_csv(p)
    if problems:
        raise DatasetError(problems)

    def need_cols(name, expected):
        miss = [c for c in expected if c not in raw[name][0]]
        if miss:
            problems.append(f"{name}: kolom wajib hilang: {', '.join(miss)}")
        return not miss

    def blank(name, row, cols, ident):
        for c in cols:
            if not (row.get(c) or "").strip():
                problems.append(f"{name}: {ident} kolom '{c}' kosong (tidak boleh ada null; isi dengan bahasa terdekat)")

    def unique(name, rows, col):
        seen = set()
        for r in rows:
            v = r[col]
            if v in seen:
                problems.append(f"{name}: {col} duplikat '{v}'")
            seen.add(v)

    # ---- languages
    if need_cols("languages.csv", ["code", "name_id", "name_en", "native_name", "closest_code", "status"]):
        for r in raw["languages.csv"][1]:
            blank("languages.csv", r, r.keys(), r.get("code"))
            if r["status"] not in LANG_STATUS:
                problems.append(f"languages.csv: {r['code']} status '{r['status']}' harus {'|'.join(LANG_STATUS)}")
        unique("languages.csv", raw["languages.csv"][1], "code")
        codes = {r["code"] for r in raw["languages.csv"][1]}
        for r in raw["languages.csv"][1]:
            if r["closest_code"] not in codes:
                problems.append(f"languages.csv: {r['code']} closest_code '{r['closest_code']}' tidak dikenal")
            if r["status"] == "native" and r["closest_code"] != r["code"]:
                problems.append(f"languages.csv: {r['code']} status native harus closest_code = kodenya sendiri")
            if r["status"] == "approximate" and r["closest_code"] == r["code"]:
                problems.append(f"languages.csv: {r['code']} status approximate harus menunjuk bahasa lain di closest_code")
        ds.languages = raw["languages.csv"][1]
    lang_codes = {r["code"] for r in ds.languages}

    # ---- categories
    if need_cols("categories.csv", ["code", "name_en", "name_id", "sort_order"]):
        for r in raw["categories.csv"][1]:
            blank("categories.csv", r, r.keys(), r.get("code"))
            if not r["sort_order"].strip().isdigit():
                problems.append(f"categories.csv: {r['code']} sort_order bukan angka")
        unique("categories.csv", raw["categories.csv"][1], "code")
        ds.categories = raw["categories.csv"][1]
    cat_codes = {r["code"] for r in ds.categories}

    # ---- provinces
    if need_cols("provinces.csv", ["code", "name_id", "name_en", "languages"]):
        for r in raw["provinces.csv"][1]:
            blank("provinces.csv", r, r.keys(), r.get("code"))
            r["languages"] = _split(r["languages"])
            for l in r["languages"]:
                if l not in lang_codes:
                    problems.append(f"provinces.csv: {r['code']} memakai bahasa tak dikenal '{l}'")
        unique("provinces.csv", raw["provinces.csv"][1], "code")
        ds.provinces = raw["provinces.csv"][1]
    prov_codes = {r["code"] for r in ds.provinces}

    # ---- cities
    if need_cols("cities.csv", ["code", "name", "type", "province_code", "languages"]):
        for r in raw["cities.csv"][1]:
            blank("cities.csv", r, r.keys(), r.get("code"))
            if r["type"] not in CITY_TYPES:
                problems.append(f"cities.csv: {r['code']} type '{r['type']}' harus {'|'.join(CITY_TYPES)}")
            if r["province_code"] not in prov_codes:
                problems.append(f"cities.csv: {r['code']} province_code '{r['province_code']}' tidak ada di provinces.csv")
            elif not r["code"].startswith(r["province_code"]):
                problems.append(f"cities.csv: kode {r['code']} tidak diawali kode provinsi {r['province_code']}")
            r["languages"] = _split(r["languages"])
            for l in r["languages"]:
                if l not in lang_codes:
                    problems.append(f"cities.csv: {r['code']} memakai bahasa tak dikenal '{l}'")
        unique("cities.csv", raw["cities.csv"][1], "code")
        seen = set()
        for r in raw["cities.csv"][1]:                     # 'Malang' boleh ada sbg kota dan kabupaten
            k = (r["name"].lower(), r["type"], r["province_code"])
            if k in seen:
                problems.append(f"cities.csv: {r['type']} {r['name']} ganda di provinsi {r['province_code']}")
            seen.add(k)
        ds.cities = raw["cities.csv"][1]

    # ---- phrases + pronunciations
    lang_cols: list[str] = []
    if need_cols("phrases.csv", ["key", "category", *MEANING_COLS]):
        header, rows = raw["phrases.csv"]
        lang_cols = [c for c in header if c not in ("key", "category", *MEANING_COLS)]
        if set(lang_cols) != lang_codes:
            problems.append(f"phrases.csv vs languages.csv: kolom bahasa berbeda: {sorted(set(lang_cols) ^ lang_codes)}")
        unique("phrases.csv", rows, "key")
        keys = [r["key"] for r in rows]
        for r in rows:
            blank("phrases.csv", r, header, r["key"])
            if r["category"] not in cat_codes:
                problems.append(f"phrases.csv: {r['key']} kategori '{r['category']}' tidak ada di categories.csv")
            ds.phrases.append({"key": r["key"], "category": r["category"],
                               "meaning_id": r["id_ID"].strip(), "meaning_en": r["en_US"].strip()})
            for l in lang_cols:
                ds.translations[(r["key"], l)] = (r[l] or "").strip()
        for style in ("en", "id"):
            name = f"phrases_pronunciation_{style}.csv"
            if not need_cols(name, ["key", "category"]):
                continue
            header_p, prow = raw[name]
            if [r["key"] for r in prow] != keys:
                problems.append(f"{name}: urutan/isi key berbeda dari phrases.csv")
            if [c for c in header_p if c not in ("key", "category")] != lang_cols:
                problems.append(f"{name}: kolom bahasa berbeda dari phrases.csv (harus sama & berurutan)")
            for r in prow:
                blank(name, r, header_p, r["key"])
                for l in lang_cols:
                    ds.pronunciations[(r["key"], l, style)] = (r.get(l) or "").strip()

    # ---- emergency numbers
    if need_cols("emergency_numbers.csv", ["service", "name_id", "name_en", "number"]):
        for r in raw["emergency_numbers.csv"][1]:
            blank("emergency_numbers.csv", r, r.keys(), r.get("service"))
            if not r["number"].strip().isdigit():
                problems.append(f"emergency_numbers.csv: {r['service']} nomor bukan angka: {r['number']!r}")
        unique("emergency_numbers.csv", raw["emergency_numbers.csv"][1], "service")
        ds.emergency = raw["emergency_numbers.csv"][1]

    # ---- lintas berkas
    for p in ds.provinces:
        if not p["languages"]:
            problems.append(f"provinces.csv: provinsi {p['code']} tidak punya bahasa")
    for c in ds.cities:
        if not c["languages"]:
            problems.append(f"cities.csv: kota {c['code']} tidak punya bahasa")
    if full:
        if len(ds.provinces) != EXPECTED_PROVINCES:
            problems.append(f"provinces.csv: harus {EXPECTED_PROVINCES} provinsi, ada {len(ds.provinces)}")
        with_city = {c["province_code"] for c in ds.cities}
        for p in ds.provinces:
            if p["code"] not in with_city:
                problems.append(f"cities.csv: provinsi {p['code']} ({p['name_id']}) belum punya kota")

    if problems:
        raise DatasetError(problems)
    return ds
