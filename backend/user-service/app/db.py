import sqlite3
from contextlib import contextmanager

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  email TEXT NOT NULL UNIQUE,
  password_hash TEXT NOT NULL,
  role TEXT NOT NULL DEFAULT 'user' CHECK (role IN ('user','admin')),
  ui_language TEXT NOT NULL DEFAULT 'en' CHECK (ui_language IN ('en','id')),
  pron_style TEXT NOT NULL DEFAULT 'en' CHECK (pron_style IN ('en','id')),
  target_language TEXT,
  default_city TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS revoked_tokens (
  jti TEXT PRIMARY KEY, expires_at INTEGER NOT NULL
);
"""


def connect() -> sqlite3.Connection:
    config.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(config.DB_PATH, check_same_thread=False)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    return con


def init_schema(con):
    con.executescript(SCHEMA)
    con.commit()


@contextmanager
def get_db():
    con = connect()
    try:
        yield con
    finally:
        con.close()
