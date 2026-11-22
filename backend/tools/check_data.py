#!/usr/bin/env python3
"""Periksa konsistensi folder tts/ dengan data master backend. Jalankan sebelum commit/deploy:

    python tools/check_data.py                # asumsi: backend/ dan tts/ bersaudara
    python tools/check_data.py --tts ../tts --audio ../tts/out/audio

Exit code 1 jika ada masalah (cocok untuk CI).
"""
import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def rows(p):
    with open(p, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tts", type=Path, default=ROOT.parent / "tts")
    ap.add_argument("--audio", type=Path, default=None, help="default: <tts>/out/audio")
    a = ap.parse_args()
    tts, audio = a.tts, a.audio or a.tts / "out" / "audio"
    data = ROOT / "phrase-service" / "data"
    errors, warns = [], []

    phrases = rows(tts / "phrases.csv")
    cols = [c for c in phrases[0] if c not in ("key", "category")]
    keys = [r["key"] for r in phrases]
    print(f"frasa: {len(keys)} | bahasa di phrases.csv: {len(cols)}")

    if len(set(keys)) != len(keys):
        errors.append("key frasa duplikat di phrases.csv")
    for r in phrases:
        for c in cols:
            if not r[c].strip():
                errors.append(f"phrases.csv: {r['key']}/{c} kosong")

    for name in ("phrases_pronunciation_en.csv", "phrases_pronunciation_id.csv"):
        pr = rows(tts / name)
        if [r["key"] for r in pr] != keys:
            errors.append(f"{name}: urutan/isi key berbeda dari phrases.csv")
        if [c for c in pr[0] if c not in ("key", "category")] != cols:
            errors.append(f"{name}: kolom bahasa berbeda dari phrases.csv")
        for r in pr:
            for c in cols:
                if not (r.get(c) or "").strip():
                    errors.append(f"{name}: {r['key']}/{c} kosong")

    voices = json.loads((tts / "voices.json").read_text(encoding="utf-8"))
    langs = rows(data / "languages.csv")
    lang_codes = {r["code"] for r in langs}
    if lang_codes != set(cols):
        errors.append(f"languages.csv vs phrases.csv: selisih {sorted(lang_codes ^ set(cols))}")
    if set(voices) != set(cols):
        errors.append(f"voices.json vs phrases.csv: selisih {sorted(set(voices) ^ set(cols))}")

    cats = {r["code"] for r in rows(data / "categories.csv")}
    for r in phrases:
        if r["category"] not in cats:
            errors.append(f"kategori '{r['category']}' ({r['key']}) tidak ada di categories.csv")
    for d in rows(data / "destinations.csv"):
        for l in d["languages"].split(";"):
            if l not in lang_codes:
                errors.append(f"destinations.csv: {d['code']} memakai bahasa tak dikenal {l}")

    # audio
    if not audio.is_dir():
        errors.append(f"folder audio tidak ada: {audio}")
    else:
        have = {(p.parent.name, p.stem) for p in audio.glob("*/*") if p.suffix in (".wav", ".mp3")}
        want = {(l, k) for l in cols for k in keys}
        missing, extra = sorted(want - have), sorted(have - want)
        print(f"audio: {len(have & want)}/{len(want)} tersedia")
        by_lang = {}
        for l, k in missing:
            by_lang.setdefault(l, []).append(k)
        for l, ks in by_lang.items():
            errors.append(f"audio {l}: kurang {len(ks)} ({', '.join(ks[:4])}{'...' if len(ks) > 4 else ''})")
        for l, k in extra[:10]:
            warns.append(f"audio tak dikenal: {l}/{k}")
        empty = [p for p in audio.glob("*/*.wav") if p.stat().st_size < 1000]
        for p in empty:
            errors.append(f"audio terlalu kecil/rusak: {p.parent.name}/{p.name} ({p.stat().st_size} B)")

    # nomor darurat
    em = rows(tts / "emergency_numbers.csv")
    country = {r["code"]: r["country_code"] for r in langs}
    seen = {}
    for r in em:
        for l in cols:
            v = (r.get(l) or "").strip()
            if not v:
                warns.append(f"emergency_numbers.csv: {r['key']}/{l} kosong")
                continue
            if not v.isdigit():
                errors.append(f"emergency_numbers.csv: {r['key']}/{l} bukan angka: {v!r}")
            prev = seen.setdefault((country[l], r["key"]), (v, l))
            if prev[0] != v:
                errors.append(f"nomor darurat {country[l]} {r['key']} konflik: {prev} vs {(v, l)}")
    dests = {d["code"] for d in rows(data / "destinations.csv")}
    no_num = sorted(dests - {c for c, _ in seen})
    if no_num:
        warns.append(f"destinasi tanpa nomor darurat: {', '.join(no_num)}")

    for w in warns:
        print("PERINGATAN", w)
    for e in errors:
        print("ERROR     ", e)
    print("OK" if not errors else f"{len(errors)} error")
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
