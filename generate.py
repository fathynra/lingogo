#!/usr/bin/env python3
"""
Tourist phrase audio generator.

Membaca phrases.csv, men-generate audio per bahasa dengan Piper TTS (offline)
atau edge-tts (online, tanpa API key), lalu menghasilkan:

  out/audio/<lang>/<key>.<format>   -> file audio
  out/manifest.json                 -> daftar semua frasa + path file
  out/phrases.db                    -> SQLite berisi teks + audio (BLOB)

Contoh:
  python generate.py                              # semua bahasa, Piper, wav
  python generate.py --langs en,es,fr --format mp3
  python generate.py --engine edge --langs id,en  # termasuk Indonesia
  python generate.py --list                       # lihat bahasa & suara
"""
import argparse
import asyncio
import csv
import json
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parent
NON_LANG_COLS = {"key", "category"}


# --------------------------------------------------------------------------
# Data
# --------------------------------------------------------------------------
def read_phrases(path: Path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        langs = [c for c in reader.fieldnames if c not in NON_LANG_COLS]
        rows = [r for r in reader if (r.get("key") or "").strip()]
    return langs, rows


def read_voices(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def convert(src: Path, dst: Path):
    if not shutil.which("ffmpeg"):
        sys.exit("ffmpeg tidak ditemukan. Install ffmpeg atau pakai --format wav (piper) / mp3 (edge).")
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-i", str(src), str(dst)],
        check=True,
    )


# --------------------------------------------------------------------------
# Backends
# --------------------------------------------------------------------------
class PiperBackend:
    native_ext = "wav"

    def __init__(self, voices_dir: Path, length_scale: float):
        self.voices_dir = voices_dir
        self.length_scale = length_scale
        self._cache = {}

    def _load(self, name: str):
        if name in self._cache:
            return self._cache[name]
        from piper import PiperVoice  # pip install piper-tts

        onnx = self.voices_dir / f"{name}.onnx"
        if not onnx.exists():
            self.voices_dir.mkdir(parents=True, exist_ok=True)
            print(f"  [download] voice {name}")
            subprocess.run(
                [sys.executable, "-m", "piper.download_voices", name],
                cwd=self.voices_dir,
                check=True,
            )
        voice = PiperVoice.load(str(onnx))
        self._cache = {name: voice}  # simpan 1 voice saja biar hemat RAM
        return voice

    def synth(self, voice_name: str, text: str, out_path: Path):
        voice = self._load(voice_name)
        kwargs = {}
        if self.length_scale != 1.0:
            try:
                from piper import SynthesisConfig

                kwargs["syn_config"] = SynthesisConfig(length_scale=self.length_scale)
            except ImportError:
                pass  # versi piper lama: abaikan
        with wave.open(str(out_path), "wb") as wf:
            if hasattr(voice, "synthesize_wav"):
                voice.synthesize_wav(text, wf, **kwargs)
            else:  # piper-tts < 1.3
                voice.synthesize(text, wf)


class EdgeBackend:
    native_ext = "mp3"

    def __init__(self, rate: str):
        self.rate = rate

    def synth(self, voice_name: str, text: str, out_path: Path):
        import edge_tts  # pip install edge-tts

        async def go():
            await edge_tts.Communicate(text, voice_name, rate=self.rate).save(str(out_path))

        asyncio.run(go())


# --------------------------------------------------------------------------
# Output
# --------------------------------------------------------------------------
def build_outputs(out: Path, fmt: str, engine: str, langs, rows, voices, write_db: bool):
    manifest = []
    con = None
    if write_db:
        db_path = out / "phrases.db"
        if db_path.exists():
            db_path.unlink()
        con = sqlite3.connect(db_path)
        con.execute(
            """CREATE TABLE phrases (
                   key TEXT NOT NULL, lang TEXT NOT NULL, category TEXT,
                   text TEXT NOT NULL, engine TEXT, voice TEXT,
                   format TEXT, file TEXT, audio BLOB,
                   PRIMARY KEY (key, lang))"""
        )
    for lang in langs:
        for row in rows:
            text = (row.get(lang) or "").strip()
            f = out / "audio" / lang / f"{row['key']}.{fmt}"
            if not text or not f.exists():
                continue
            rel = f.relative_to(out).as_posix()
            entry = {
                "key": row["key"], "lang": lang, "category": row.get("category", ""),
                "text": text, "engine": engine, "voice": voices.get(lang, ""),
                "format": fmt, "file": rel,
            }
            manifest.append(entry)
            if con:
                con.execute(
                    "INSERT INTO phrases VALUES (?,?,?,?,?,?,?,?,?)",
                    (entry["key"], lang, entry["category"], text, engine,
                     entry["voice"], fmt, rel, f.read_bytes()),
                )
    if con:
        con.commit()
        con.close()
    (out / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return len(manifest)


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------
def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--engine", choices=["piper", "edge"], default="piper")
    p.add_argument("--langs", help="kode bahasa dipisah koma, mis. en,es,fr (default: semua)")
    p.add_argument("--format", choices=["wav", "mp3", "ogg"], help="default: wav (piper) / mp3 (edge)")
    p.add_argument("--phrases", default=str(ROOT / "phrases.csv"))
    p.add_argument("--voices", default=str(ROOT / "voices.json"))
    p.add_argument("--voices-dir", default=str(ROOT / "voices"), help="tempat model Piper")
    p.add_argument("--out", default=str(ROOT / "out"))
    p.add_argument("--length-scale", type=float, default=1.1,
                   help="Piper: >1 lebih lambat/jelas (default 1.1)")
    p.add_argument("--edge-rate", default="-10%", help="edge-tts: kecepatan, mis. -10%%")
    p.add_argument("--overwrite", action="store_true", help="generate ulang file yang sudah ada")
    p.add_argument("--no-db", action="store_true", help="jangan buat SQLite")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--list", action="store_true", help="tampilkan bahasa & voice lalu keluar")
    args = p.parse_args()

    langs_all, rows = read_phrases(Path(args.phrases))
    voices = read_voices(Path(args.voices))[args.engine]

    if args.list:
        print(f"{len(rows)} frasa. Engine: {args.engine}")
        for l in langs_all:
            print(f"  {l:3s} -> {voices.get(l, '(tidak ada voice)')}")
        return

    langs = [l.strip() for l in args.langs.split(",")] if args.langs else langs_all
    unknown = [l for l in langs if l not in langs_all]
    if unknown:
        sys.exit(f"Bahasa tidak ada di phrases.csv: {unknown}")

    backend = (
        PiperBackend(Path(args.voices_dir), args.length_scale)
        if args.engine == "piper"
        else EdgeBackend(args.edge_rate)
    )
    fmt = args.format or backend.native_ext
    out = Path(args.out)

    failed = []
    for lang in langs:
        voice = voices.get(lang)
        if not voice:
            print(f"[skip] {lang}: tidak ada voice untuk engine '{args.engine}' di voices.json")
            continue
        print(f"[{lang}] voice={voice}")
        (out / "audio" / lang).mkdir(parents=True, exist_ok=True)
        for row in rows:
            text = (row.get(lang) or "").strip()
            if not text:
                continue
            dest = out / "audio" / lang / f"{row['key']}.{fmt}"
            if dest.exists() and not args.overwrite:
                continue
            if args.dry_run:
                print(f"  (dry) {row['key']}: {text}")
                continue
            try:
                with tempfile.TemporaryDirectory() as td:
                    raw = Path(td) / f"raw.{backend.native_ext}"
                    backend.synth(voice, text, raw)
                    if backend.native_ext == fmt:
                        shutil.copyfile(raw, dest)
                    else:
                        convert(raw, dest)
                print(f"  ok  {row['key']}: {text}")
            except Exception as e:  # noqa: BLE001
                failed.append((lang, row["key"], str(e)))
                print(f"  ERR {row['key']}: {e}")

    if args.dry_run:
        return
    n = build_outputs(out, fmt, args.engine, langs, rows, voices, not args.no_db)
    print(f"\nSelesai. {n} audio terdaftar di {out}/manifest.json" + ("" if args.no_db else " dan phrases.db"))
    if failed:
        print(f"{len(failed)} gagal:")
        for lang, key, err in failed:
            print(f"  {lang}/{key}: {err}")


if __name__ == "__main__":
    main()
