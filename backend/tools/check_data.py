#!/usr/bin/env python3
"""Cek CSV di database/ sebelum commit atau deploy.

    python tools/check_data.py [--database ../database]
"""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "phrase-service"))
from app import dataset  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--database", type=Path, default=ROOT.parent / "database")
    folder = ap.parse_args().database
    try:
        ds = dataset.load(folder)
    except dataset.DatasetError as e:
        for p in e.problems:
            print("ERROR", p)
        sys.exit(1)

    approx = [l for l in ds.languages if l["closest_code"] != l["code"]]
    print(f"provinsi {len(ds.provinces)} | kota/kabupaten {len(ds.cities)} | "
          f"bahasa {len(ds.languages)} ({len(ds.native)} punya data, {len(approx)} perkiraan) | "
          f"frasa {len(ds.phrases)}")
    for l in approx:
        print(f"  perkiraan: {l['code']} ({l['name_id']}) memakai data {l['closest_code']}")
    print("OK")


if __name__ == "__main__":
    main()
