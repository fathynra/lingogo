import sqlite3
from contextlib import contextmanager

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS languages (
  code TEXT PRIMARY KEY, name_en TEXT NOT NULL, name_id TEXT NOT NULL,
  native_name TEXT NOT NULL, country_code TEXT NOT NULL, voice TEXT
);
CREATE TABLE IF NOT EXISTS destinations (
  code TEXT PRIMARY KEY, name_en TEXT NOT NULL, name_id TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS destination_languages (
  destination_code TEXT NOT NULL REFERENCES destinations(code),
  language_code TEXT NOT NULL REFERENCES languages(code),
  PRIMARY KEY (destination_code, language_code)
);
CREATE TABLE IF NOT EXISTS categories (
  code TEXT PRIMARY KEY, name_en TEXT NOT NULL, name_id TEXT NOT NULL,
  sort_order INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS phrases (
  key TEXT PRIMARY KEY, category_code TEXT NOT NULL REFERENCES categories(code)
);
CREATE TABLE IF NOT EXISTS translations (
  phrase_key TEXT NOT NULL REFERENCES phrases(key),
  lang TEXT NOT NULL REFERENCES languages(code),
  text TEXT NOT NULL,
  PRIMARY KEY (phrase_key, lang)
);
CREATE TABLE IF NOT EXISTS pronunciations (
  phrase_key TEXT NOT NULL REFERENCES phrases(key),
  lang TEXT NOT NULL REFERENCES languages(code),
  style TEXT NOT NULL CHECK (style IN ('en','id')),
  guide TEXT NOT NULL,
  PRIMARY KEY (phrase_key, lang, style)
);
CREATE TABLE IF NOT EXISTS audio (
  phrase_key TEXT NOT NULL REFERENCES phrases(key),
  lang TEXT NOT NULL REFERENCES languages(code),
  path TEXT NOT NULL,
  PRIMARY KEY (phrase_key, lang)
);
CREATE TABLE IF NOT EXISTS emergency_numbers (
  country_code TEXT NOT NULL,
  service TEXT NOT NULL CHECK (service IN ('police','fire','ambulance')),
  number TEXT NOT NULL,
  PRIMARY KEY (country_code, service)
);
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS idx_phrases_cat ON phrases(category_code);
CREATE INDEX IF NOT EXISTS idx_trans_lang ON translations(lang);
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
    con.executescript(SCHEMA)
    con.commit()


@contextmanager
def get_db():
    con = connect()
    try:
        yield con
    finally:
        con.close()
