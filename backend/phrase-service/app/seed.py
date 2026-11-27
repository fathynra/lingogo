"""Isi SQLite dari CSV. Diisi ulang otomatis kalau isi CSV berubah.

Paksa isi ulang: docker compose exec phrase-service python -m app.seed --reset
"""
import argparse

from . import config, dataset, db
from .textutil import normalize

TABLES = ("pronunciations", "translations", "phrases", "categories", "city_languages", "cities",
          "province_languages", "provinces", "emergency_numbers", "languages")


def seed(con, ds: dataset.Dataset):
    for t in TABLES:
        con.execute(f"DELETE FROM {t}")

    for l in ds.languages:
        con.execute("INSERT INTO languages VALUES (?,?,?,?,?,?)",
                    (l["code"], l["name_id"], l["name_en"], l["native_name"], l["closest_code"],
                     int(l["closest_code"] != l["code"])))
    for c in ds.categories:
        con.execute("INSERT INTO categories VALUES (?,?,?,?)",
                    (c["code"], c["name_en"], c["name_id"], int(c["sort_order"])))
    for p in ds.provinces:
        con.execute("INSERT INTO provinces VALUES (?,?,?)", (p["code"], p["name_id"], p["name_en"]))
        for i, l in enumerate(p["languages"]):
            con.execute("INSERT INTO province_languages VALUES (?,?,?)", (p["code"], l, i))
    for c in ds.cities:
        con.execute("INSERT INTO cities VALUES (?,?,?,?,?)",
                    (c["code"], c["name"], normalize(c["name"]), c["type"], c["province_code"]))
        for i, l in enumerate(c["languages"]):
            con.execute("INSERT INTO city_languages VALUES (?,?,?)", (c["code"], l, i))

    for i, p in enumerate(ds.phrases):
        key = p["key"]
        con.execute("INSERT INTO phrases VALUES (?,?,?,?,?)", (key, p["category"], p["id_ID"], p["en_US"], i))
        for l in ds.languages:
            src = l["closest_code"]          # bahasa perkiraan memakai isi bahasa terdekat
            con.execute("INSERT INTO translations VALUES (?,?,?)", (key, l["code"], p[src]))
            con.execute("INSERT INTO pronunciations VALUES (?,?,?,?)", (key, l["code"], "en", ds.pron_en[key][src]))
            con.execute("INSERT INTO pronunciations VALUES (?,?,?,?)", (key, l["code"], "id", ds.pron_id[key][src]))

    for e in ds.emergency:
        con.execute("INSERT INTO emergency_numbers VALUES (?,?,?,?)",
                    (e["service"], e["name_id"], e["name_en"], e["number"]))
    con.commit()
    return {"provinces": len(ds.provinces), "cities": len(ds.cities),
            "languages": len(ds.languages), "phrases": len(ds.phrases)}


def ensure_seeded(con, folder=None):
    folder = folder or config.DATABASE_DIR
    db.init_schema(con)
    if not (folder / "phrases.csv").is_file():
        raise RuntimeError(f"Folder database tidak ditemukan di {folder}")
    h = dataset.source_hash(folder)
    row = con.execute("SELECT value FROM meta WHERE key='source_hash'").fetchone()
    if row and row["value"] == h:
        print("[seed] data sudah sesuai CSV")
        return
    info = seed(con, dataset.load(folder))   # CSV tidak valid -> error, data lama tetap utuh
    con.execute("INSERT OR REPLACE INTO meta VALUES ('source_hash', ?)", (h,))
    con.commit()
    print(f"[seed] data diisi ulang dari CSV: {info}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--reset", action="store_true", help="paksa isi ulang walau CSV tidak berubah")
    args = ap.parse_args()
    c = db.connect()
    db.init_schema(c)
    if args.reset:
        c.execute("DELETE FROM meta WHERE key='source_hash'")
        c.commit()
    ensure_seeded(c)
