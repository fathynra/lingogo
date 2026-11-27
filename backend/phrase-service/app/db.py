import sqlite3
from contextlib import contextmanager

from . import config

# Naikkan angka ini setiap skema berubah: database turunan (dari CSV) akan dibuat ulang otomatis.
SCHEMA_VERSION = "2"

SCHEMA = """
CREATE TABLE languages (
  code TEXT PRIMARY KEY, name_id TEXT NOT NULL, name_en TEXT NOT NULL, native_name TEXT NOT NULL,
  closest_code TEXT NOT NULL, is_approximate INTEGER NOT NULL CHECK (is_approximate IN (0,1))
);
CREATE TABLE provinces (
  code TEXT PRIMARY KEY, name_id TEXT NOT NULL, name_en TEXT NOT NULL
);
CREATE TABLE province_languages (
  province_code TEXT NOT NULL REFERENCES provinces(code),
  language_code TEXT NOT NULL REFERENCES languages(code),
  position INTEGER NOT NULL,                       -- 0 = bahasa utama
  PRIMARY KEY (province_code, language_code)
);
CREATE TABLE cities (
  code TEXT PRIMARY KEY, name TEXT NOT NULL, name_norm TEXT NOT NULL,
  type TEXT NOT NULL CHECK (type IN ('kota','kabupaten')),
  province_code TEXT NOT NULL REFERENCES provinces(code)
);
CREATE TABLE city_languages (
  city_code TEXT NOT NULL REFERENCES cities(code),
  language_code TEXT NOT NULL REFERENCES languages(code),
  position INTEGER NOT NULL,
  PRIMARY KEY (city_code, language_code)
);
CREATE TABLE categories (
  code TEXT PRIMARY KEY, name_en TEXT NOT NULL, name_id TEXT NOT NULL, sort_order INTEGER NOT NULL
);
CREATE TABLE phrases (
  key TEXT PRIMARY KEY, category_code TEXT NOT NULL REFERENCES categories(code),
  meaning_id TEXT NOT NULL, meaning_en TEXT NOT NULL, sort_order INTEGER NOT NULL
);
CREATE TABLE translations (
  phrase_key TEXT NOT NULL REFERENCES phrases(key),
  lang TEXT NOT NULL REFERENCES languages(code),
  text TEXT NOT NULL,
  PRIMARY KEY (phrase_key, lang)
);
CREATE TABLE pronunciations (
  phrase_key TEXT NOT NULL REFERENCES phrases(key),
  lang TEXT NOT NULL REFERENCES languages(code),
  style TEXT NOT NULL CHECK (style IN ('en','id')),
  guide TEXT NOT NULL,
  PRIMARY KEY (phrase_key, lang, style)
);
CREATE TABLE emergency_numbers (
  service TEXT PRIMARY KEY, name_id TEXT NOT NULL, name_en TEXT NOT NULL, number TEXT NOT NULL
);
CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE INDEX idx_cities_norm ON cities(name_norm);
CREATE INDEX idx_cities_prov ON cities(province_code);
CREATE INDEX idx_phrases_cat ON phrases(category_code);
CREATE INDEX idx_trans_lang ON translations(lang);
"""


def connect(path=None) -> sqlite3.Connection:
    path = path or config.DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path, check_same_thread=False)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON")
    con.execute("PRAGMA journal_mode=WAL")
    return con


def init_schema(con: sqlite3.Connection) -> None:
    """Buat skema. Jika versi skema berbeda (mis. database lama dari versi dunia), hapus & buat ulang:
    isi database ini 100% turunan dari CSV sehingga aman diisi ulang."""
    names = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
    ok = False
    if "meta" in names:
        row = con.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()
        ok = bool(row) and row[0] == SCHEMA_VERSION
    if ok:
        return
    con.execute("PRAGMA foreign_keys=OFF")
    for n in names:
        con.execute(f'DROP TABLE IF EXISTS "{n}"')
    con.executescript(SCHEMA)
    con.execute("INSERT INTO meta VALUES ('schema_version', ?)", (SCHEMA_VERSION,))
    con.commit()
    con.execute("PRAGMA foreign_keys=ON")


@contextmanager
def get_db():
    con = connect()
    try:
        yield con
    finally:
        con.close()
