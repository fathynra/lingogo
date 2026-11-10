import argparse
import csv
import json
import sqlite3
import subprocess
import sys
import wave
from pathlib import Path

from piper import PiperVoice, SynthesisConfig

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "out"
VOICES_DIR = ROOT / "voices"


def load_voice(name):
    model = VOICES_DIR / f"{name}.onnx"
    if not model.exists():
        VOICES_DIR.mkdir(exist_ok=True)
        subprocess.run(
            [sys.executable, "-m", "piper.download_voices", name],
            cwd=VOICES_DIR,
            check=True,
        )
    return PiperVoice.load(str(model))


def build_db(rows, langs):
    db = OUT / "phrases.db"
    db.unlink(missing_ok=True)
    con = sqlite3.connect(db)
    con.execute(
        "CREATE TABLE phrases (key TEXT, lang TEXT, category TEXT, text TEXT, audio BLOB, PRIMARY KEY (key, lang))"
    )
    for lang in langs:
        for row in rows:
            path = OUT / "audio" / lang / f"{row['key']}.wav"
            if path.exists():
                con.execute(
                    "INSERT INTO phrases VALUES (?, ?, ?, ?, ?)",
                    (row["key"], lang, row["category"], row[lang], path.read_bytes()),
                )
    con.commit()
    con.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--langs", help="contoh: en_US,id_ID,ja_JP (default: semua)")
    parser.add_argument("--length-scale", type=float, default=1.1, help="lebih besar = lebih lambat")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    voices = json.loads((ROOT / "voices.json").read_text(encoding="utf-8"))
    with open(ROOT / "phrases.csv", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))

    langs = args.langs.split(",") if args.langs else list(voices)
    config = SynthesisConfig(length_scale=args.length_scale)

    for lang in langs:
        try:
            voice = load_voice(voices[lang])
        except Exception as e:
            print(f"{lang}: gagal load voice {voices.get(lang)} ({e})")
            continue

        folder = OUT / "audio" / lang
        folder.mkdir(parents=True, exist_ok=True)
        for row in rows:
            path = folder / f"{row['key']}.wav"
            if path.exists() and not args.overwrite:
                continue
            try:
                with wave.open(str(path), "wb") as wav:
                    voice.synthesize_wav(row[lang], wav, syn_config=config)
            except Exception as e:
                path.unlink(missing_ok=True)
                print(f"{lang}/{row['key']}: gagal ({e})")
        print(f"{lang}: selesai")

    build_db(rows, list(voices))
    print("out/phrases.db dibuat")


if __name__ == "__main__":
    main()
