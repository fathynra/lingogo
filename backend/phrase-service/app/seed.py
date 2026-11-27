"""Isi database SQLite dari folder database/ (CSV = sumber kebenaran).

Saat service start: jika isi CSV berubah (hash), seluruh data diisi ulang otomatis.
Manual: docker compose exec phrase-service python -m app.seed --reset
"""
import argparse
from pathlib import Path

from . import config, dataset, db
from .textutil import normalize

TABLES = ("pronunciations", "translations", "phrases", "categories", "city_languages", "cities",
          "province_languages", "provinces", "emergency_numbers", "languages")


def seed(con, ds: dataset.Dataset) -> dict:
    for t in TABLES:
        con.execute(f"DELETE FROM {t}")
    for r in ds.languages:
        con.execute("INSERT INTO languages VALUES (?,?,?,?,?,?)",
                    (r["code"], r["name_id"], r["name_en"], r["native_name"], r["closest_code"],
                     1 if r["status"] == "approximate" else 0))
    for r in ds.categories:
        con.execute("INSERT INTO categories VALUES (?,?,?,?)",
                    (r["code"], r["name_en"], r["name_id"], int(r["sort_order"])))
    for r in ds.provinces:
        con.execute("INSERT INTO provinces VALUES (?,?,?)", (r["code"], r["name_id"], r["name_en"]))
        for i, l in enumerate(r["languages"]):
            con.execute("INSERT OR IGNORE INTO province_languages VALUES (?,?,?)", (r["code"], l, i))
    for r in ds.cities:
        con.execute("INSERT INTO cities VALUES (?,?,?,?,?)",
                    (r["code"], r["name"], normalize(r["name"]), r["type"], r["province_code"]))
        for i, l in enumerate(r["languages"]):
            con.execute("INSERT OR IGNORE INTO city_languages VALUES (?,?,?)", (r["code"], l, i))
    for i, p in enumerate(ds.phrases):
        con.execute("INSERT INTO phrases VALUES (?,?,?,?,?)",
                    (p["key"], p["category"], p["meaning_id"], p["meaning_en"], i))
    for (key, lang), text in ds.translations.items():
        con.execute("INSERT INTO translations VALUES (?,?,?)", (key, lang, text))
    for (key, lang, style), guide in ds.pronunciations.items():
        con.execute("INSERT INTO pronunciations VALUES (?,?,?,?)", (key, lang, style, guide))
    for r in ds.emergency:
        con.execute("INSERT INTO emergency_numbers VALUES (?,?,?,?)",
                    (r["service"], r["name_id"], r["name_en"], r["number"]))
    con.commit()
    return {"provinces": len(ds.provinces), "cities": len(ds.cities), "languages": len(ds.languages),
            "phrases": len(ds.phrases)}


def ensure_seeded(con, database_dir: Path = None) -> None:
    database_dir = database_dir or config.DATABASE_DIR
    db.init_schema(con)
    if not (database_dir / "phrases.csv").is_file():
        raise RuntimeError(f"Folder database tidak ditemukan di {database_dir} (mount ../database ke /database)")
    h = dataset.source_hash(database_dir)
    row = con.execute("SELECT value FROM meta WHERE key='source_hash'").fetchone()
    if row is None or row["value"] != h:
        ds = dataset.load(database_dir)          # raise DatasetError (daftar lengkap masalah) bila CSV tidak valid
        info = seed(con, ds)
        con.execute("INSERT OR REPLACE INTO meta VALUES ('source_hash', ?)", (h,))
        con.commit()
        print(f"[seed] data diisi ulang dari database/: {info}")
    else:
        print("[seed] data sudah sesuai database/ (tidak diisi ulang)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--reset", action="store_true", help="paksa isi ulang walau CSV tak berubah")
    args = ap.parse_args()
    c = db.connect()
    db.init_schema(c)
    if args.reset:
        c.execute("DELETE FROM meta WHERE key='source_hash'")
        c.commit()
    ensure_seeded(c)
