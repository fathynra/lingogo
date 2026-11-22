"""Isi database dari folder tts/ (sumber kebenaran) + data master backend, lalu pindai audio.

Sumber:
  TTS_DIR  (../tts)   : phrases.csv, phrases_pronunciation_en.csv, phrases_pronunciation_id.csv,
                        voices.json, emergency_numbers.csv
  DATA_DIR (data/)    : languages.csv, destinations.csv, categories.csv  (milik backend)
  AUDIO_DIR           : <lang>/<key>.wav|mp3  (tts/out/audio)

Saat service start: jika isi sumber berubah (hash), data diisi ulang otomatis.
Manual: docker compose exec phrase-service python -m app.seed --reset
"""
import argparse
import csv
import hashlib
import json
from pathlib import Path

from . import config, db

AUDIO_EXTS = (".mp3", ".opus", ".ogg", ".wav")  # urutan preferensi
TTS_FILES = ("phrases.csv", "phrases_pronunciation_en.csv", "phrases_pronunciation_id.csv",
             "voices.json", "emergency_numbers.csv")
LOCAL_FILES = ("languages.csv", "destinations.csv", "categories.csv")


def _csv(path: Path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def source_hash(tts_dir: Path, data_dir: Path) -> str:
    h = hashlib.sha256()
    for d, names in ((tts_dir, TTS_FILES), (data_dir, LOCAL_FILES)):
        for n in names:
            h.update(n.encode())
            h.update((d / n).read_bytes())
    return h.hexdigest()


def seed(con, tts_dir: Path = None, data_dir: Path = None, reset: bool = True) -> dict:
    tts_dir = tts_dir or config.TTS_DIR
    data_dir = data_dir or config.DATA_DIR
    if reset:
        for t in ("audio", "emergency_numbers", "pronunciations", "translations", "phrases",
                  "destination_languages", "destinations", "categories", "languages"):
            con.execute(f"DELETE FROM {t}")
    voices = json.loads((tts_dir / "voices.json").read_text(encoding="utf-8"))

    langs_rows = _csv(data_dir / "languages.csv")
    country_of = {r["code"]: r["country_code"] for r in langs_rows}
    for r in langs_rows:
        con.execute("INSERT OR REPLACE INTO languages VALUES (?,?,?,?,?,?)",
                    (r["code"], r["name_en"], r["name_id"], r["native_name"],
                     r["country_code"], voices.get(r["code"])))
    for r in _csv(data_dir / "categories.csv"):
        con.execute("INSERT OR REPLACE INTO categories VALUES (?,?,?,?)",
                    (r["code"], r["name_en"], r["name_id"], int(r["sort_order"])))
    for r in _csv(data_dir / "destinations.csv"):
        con.execute("INSERT OR REPLACE INTO destinations VALUES (?,?,?)",
                    (r["code"], r["name_en"], r["name_id"]))
        for lang in r["languages"].split(";"):
            con.execute("INSERT OR REPLACE INTO destination_languages VALUES (?,?)",
                        (r["code"], lang))

    rows = _csv(tts_dir / "phrases.csv")
    pron = {"en": {r["key"]: r for r in _csv(tts_dir / "phrases_pronunciation_en.csv")},
            "id": {r["key"]: r for r in _csv(tts_dir / "phrases_pronunciation_id.csv")}}
    langs = [c for c in rows[0] if c not in ("key", "category")]
    for r in rows:
        con.execute("INSERT OR REPLACE INTO phrases VALUES (?,?)", (r["key"], r["category"]))
        for lang in langs:
            con.execute("INSERT OR REPLACE INTO translations VALUES (?,?,?)",
                        (r["key"], lang, r[lang].strip()))
            for style in ("en", "id"):
                con.execute("INSERT OR REPLACE INTO pronunciations VALUES (?,?,?,?)",
                            (r["key"], lang, style, pron[style][r["key"]][lang].strip()))

    # Nomor darurat: kolom per bahasa -> disimpan per negara (country_code bahasa itu)
    n_em = 0
    for r in _csv(tts_dir / "emergency_numbers.csv"):
        service = r["key"].removeprefix("emergency_")
        for lang, cc in country_of.items():
            val = (r.get(lang) or "").strip()
            if val:
                cur = con.execute("INSERT OR IGNORE INTO emergency_numbers VALUES (?,?,?)",
                                  (cc, service, val))
                n_em += cur.rowcount
    con.commit()
    return {"phrases": len(rows), "languages": len(langs), "emergency_numbers": n_em}


def refresh_audio(con, audio_dir: Path = None) -> int:
    """Pindai <audio_dir>/<lang>/<key>.<ext> dan simpan path relatif ke tabel audio."""
    audio_dir = audio_dir or config.AUDIO_DIR
    con.execute("DELETE FROM audio")
    n = 0
    if audio_dir.is_dir():
        known = {r["key"] for r in con.execute("SELECT key FROM phrases")}
        langs = {r["code"] for r in con.execute("SELECT code FROM languages")}
        for lang_dir in sorted(p for p in audio_dir.iterdir() if p.is_dir() and p.name in langs):
            found = {}
            for f in lang_dir.iterdir():
                if f.suffix in AUDIO_EXTS and f.stem in known:
                    best = found.get(f.stem)
                    if best is None or AUDIO_EXTS.index(f.suffix) < AUDIO_EXTS.index(best.suffix):
                        found[f.stem] = f
            for key, f in found.items():
                con.execute("INSERT INTO audio VALUES (?,?,?)",
                            (key, lang_dir.name, f"{lang_dir.name}/{f.name}"))
                n += 1
    con.commit()
    return n


def ensure_seeded(con, tts_dir: Path = None, data_dir: Path = None) -> None:
    tts_dir = tts_dir or config.TTS_DIR
    data_dir = data_dir or config.DATA_DIR
    db.init_schema(con)
    if not (tts_dir / "phrases.csv").is_file():
        raise RuntimeError(f"Folder tts tidak ditemukan di {tts_dir} (mount ../tts ke /tts)")
    h = source_hash(tts_dir, data_dir)
    row = con.execute("SELECT value FROM meta WHERE key='source_hash'").fetchone()
    if row is None or row["value"] != h:
        info = seed(con, tts_dir, data_dir, reset=True)
        con.execute("INSERT OR REPLACE INTO meta VALUES ('source_hash', ?)", (h,))
        con.commit()
        print(f"[seed] data diisi ulang dari tts/: {info}")
    else:
        print("[seed] data sudah sesuai tts/ (tidak diisi ulang)")
    print(f"[seed] audio terdaftar: {refresh_audio(con)}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--reset", action="store_true", help="paksa isi ulang walau sumber tak berubah")
    args = ap.parse_args()
    c = db.connect()
    if args.reset:
        db.init_schema(c)
        c.execute("DELETE FROM meta")
        c.commit()
    ensure_seeded(c)
