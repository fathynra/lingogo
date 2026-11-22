import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
URL = "https://huggingface.co/rhasspy/piper-voices/resolve/main/voices.json"
CATALOG = ROOT / "catalog.json"
QUALITY = {"medium": 0, "high": 1, "low": 2, "x_low": 3}

if not CATALOG.exists():
    subprocess.run(["curl", "-L", "--fail", "-sS", "-o", str(CATALOG), URL], check=True)

catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
by_locale = {}
for name, info in catalog.items():
    by_locale.setdefault(info["language"]["code"], []).append(name)

path = ROOT / "voices.json"
voices = json.loads(path.read_text(encoding="utf-8"))

for locale, name in voices.items():
    if name in catalog:
        continue
    options = by_locale.get(locale)
    if not options:
        print(f"{locale}: tidak ada voice Piper untuk locale ini")
        continue
    options.sort(key=lambda n: QUALITY.get(catalog[n]["quality"], 9))
    voices[locale] = options[0]
    print(f"{locale}: {name} -> {options[0]}")

path.write_text(json.dumps(voices, ensure_ascii=False, indent=2), encoding="utf-8")
print("selesai")
