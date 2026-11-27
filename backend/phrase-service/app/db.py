import sqlite3
from contextlib import contextmanager

from . import config

# Naikkan kalau skema berubah. Isi database ini turunan dari CSV, jadi aman dibuat ulang.
SCHEMA_VERSION = "3"

SCHEMA = """
CREATE TABLE languages (
  code TEXT PRIMARY KEY, name_id TEXT NOT NULL, name_en TEXT NOT NULL, native_name TEXT NOT NULL,
  closest_code TEXT NOT NULL, is_approximate INTEGER NOT NULL
);
CREATE TABLE provinces (code TEXT PRIMARY KEY, name_id TEXT NOT NULL, name_en TEXT NOT NULL);
CREATE TABLE province_languages (
  province_code TEXT NOT NULL REFERENCES provinces(code),
  language_code TEXT NOT NULL REFERENCES languages(code),
  position INTEGER NOT NULL,
  PRIMARY KEY (province_code, language_code)
);
CREATE TABLE cities (
  code TEXT PRIMARY KEY, name TEXT NOT NULL, name_norm TEXT NOT NULL,
  type TEXT NOT NULL, province_code TEXT NOT NULL REFERENCES provinces(code)
);
CREATE TABLE city_languages (
  city_code TEXT NOT NULL REFERENCES cities(code),
  language_code TEXT NOT NULL REFERENCES languages(code),
  position INTEGER NOT NULL,
  PRIMARY KEY (city_code, language_code)
);
CREATE TABLE categories (code TEXT PRIMARY KEY, name_en TEXT NOT NULL, name_id TEXT NOT NULL, sort_order INTEGER NOT NULL);
CREATE TABLE phrases (
  key TEXT PRIMARY KEY, category_code TEXT NOT NULL REFERENCES categories(code),
  meaning_id TEXT NOT NULL, meaning_en TEXT NOT NULL, sort_order INTEGER NOT NULL
);
CREATE TABLE translations (
  phrase_key TEXT NOT NULL REFERENCES phrases(key), lang TEXT NOT NULL REFERENCES languages(code),
  text TEXT NOT NULL, PRIMARY KEY (phrase_key, lang)
);
CREATE TABLE pronunciations (
  phrase_key TEXT NOT NULL REFERENCES phrases(key), lang TEXT NOT NULL REFERENCES languages(code),
  style TEXT NOT NULL, guide TEXT NOT NULL, PRIMARY KEY (phrase_key, lang, style)
);
CREATE TABLE emergency_numbers (service TEXT PRIMARY KEY, name_id TEXT NOT NULL, name_en TEXT NOT NULL, number TEXT NOT NULL);
CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE INDEX idx_cities_norm ON cities(name_norm);
CREATE INDEX idx_cities_prov ON cities(province_code);
CREATE INDEX idx_phrases_cat ON phrases(category_code);
"""


def connect(path=None):
    path = path or config.DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path, check_same_thread=False)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON")
    con.execute("PRAGMA journal_mode=WAL")
    return con


def init_schema(con):
    tables = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
    if "meta" in tables:
        row = con.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()
        if row and row[0] == SCHEMA_VERSION:
            return
    con.execute("PRAGMA foreign_keys=OFF")
    for t in tables:
        con.execute(f'DROP TABLE IF EXISTS "{t}"')
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
