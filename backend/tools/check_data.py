#!/usr/bin/env python3
"""Periksa folder database/ (CSV). Jalankan sebelum commit/deploy:

    python tools/check_data.py                    # asumsi: backend/ dan database/ bersaudara
    python tools/check_data.py --database ../database --full

Aturan: tidak boleh ada sel kosong, semua referensi (bahasa, provinsi, kategori) harus valid.
--full : syarat kelengkapan akhir (tepat 38 provinsi & tiap provinsi punya kota). Exit code 1 jika ada masalah.
"""
import argparse
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "phrase-service"))
from app import dataset  # noqa: E402  (dataset.py hanya memakai pustaka standar)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--database", type=Path, default=ROOT.parent / "database")
    ap.add_argument("--full", action="store_true", help="wajib 38 provinsi & tiap provinsi punya kota")
    a = ap.parse_args()
    try:
        ds = dataset.load(a.database, full=a.full)
    except dataset.DatasetError as e:
        for p in e.problems:
            print("ERROR     ", p)
        print(f"{len(e.problems)} error")
        sys.exit(1)

    warns = []
    langs = {l["code"]: l for l in ds.languages}
    approx = [c for c, l in langs.items() if l["status"] == "approximate"]
    print(f"provinsi: {len(ds.provinces)} | kota/kabupaten: {len(ds.cities)} | bahasa: {len(langs)} "
          f"({len(langs) - len(approx)} asli, {len(approx)} terdekat) | frasa: {len(ds.phrases)} "
          f"| kategori: {len(ds.categories)}")
    for c in approx:
        print(f"  bahasa terdekat: {c} -> {langs[c]['closest_code']}")

    used = {l for p in ds.provinces for l in p["languages"]} | {l for c in ds.cities for l in c["languages"]}
    for c in langs:
        if c not in used:
            warns.append(f"bahasa {c} tidak dipakai provinsi/kota mana pun")
    per_prov = Counter(c["province_code"] for c in ds.cities)
    for p in ds.provinces:
        if not per_prov[p["code"]]:
            warns.append(f"provinsi {p['code']} {p['name_id']} belum punya kota")
    if not a.full:
        warns.append(f"mode longgar: {len(ds.provinces)}/{dataset.EXPECTED_PROVINCES} provinsi (pakai --full untuk syarat akhir)"
                     if len(ds.provinces) != dataset.EXPECTED_PROVINCES else "")
    for w in filter(None, warns):
        print("PERINGATAN", w)
    print("OK")


if __name__ == "__main__":
    main()
