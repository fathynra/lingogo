# Tourist Phrases TTS Generator

Generate audio frasa wisatawan (halo, terima kasih, berapa harga ini, angka 1-10, dst.)
untuk banyak bahasa, hasilnya berupa **file audio + manifest.json + database SQLite (audio BLOB)**.

Engine:
- **Piper** (default): offline, gratis, tanpa API key. Tidak punya suara Indonesia.
- **edge-tts** (opsional): online, gratis, tanpa API key, ada suara Indonesia.

## 1. Setup

```bash
# (opsional) fork & clone repo Piper kalau mau modifikasi sumbernya:
# git clone https://github.com/OHF-Voice/piper1-gpl.git
# lalu taruh folder ini di dalam repo itu (mis. piper1-gpl/tools/tourist-tts)

python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
# ffmpeg hanya perlu kalau mau output mp3/ogg dari Piper
# (Ubuntu: sudo apt install ffmpeg | macOS: brew install ffmpeg)
```

Kalau pakai fork Piper, install dari source: `pip install -e .` di root repo
(butuh compiler/cmake, lihat README repo), lalu skip `piper-tts` di requirements.
Cara paling gampang: pakai `pip install piper-tts` saja, script ini tidak perlu mengubah kode Piper.

## 2. Pakai

```bash
python generate.py --list                         # lihat bahasa & voice
python generate.py --dry-run                      # cek tanpa generate
python generate.py                                # semua bahasa (Piper, wav)
python generate.py --langs en,es,fr --format mp3  # sebagian bahasa, mp3
python generate.py --engine edge --langs id       # suara Indonesia via edge-tts
python generate.py --overwrite                    # generate ulang semua
```

Model suara Piper otomatis diunduh ke `voices/` saat pertama kali dipakai
(butuh internet sekali saja). Pakai `--length-scale 1.2` agar bicara lebih lambat/jelas.

## 3. Hasil

```
out/
  audio/en/greet_hello.wav
  audio/es/shop_how_much.wav
  ...
  manifest.json      # key, lang, text, voice, file
  phrases.db         # SQLite: tabel phrases (..., audio BLOB)
```

Contoh baca dari database:

```python
import sqlite3
con = sqlite3.connect("out/phrases.db")
text, audio = con.execute(
    "SELECT text, audio FROM phrases WHERE key=? AND lang=?",
    ("shop_how_much", "fr")).fetchone()
open("test.wav", "wb").write(audio)
```

## 4. Tambah frasa / bahasa

- **Frasa baru**: tambah baris di `phrases.csv` (kolom `key` harus unik, tanpa spasi).
- **Bahasa baru**: tambah kolom di `phrases.csv` (mis. `nl`) dan isi teksnya, lalu tambah
  voice-nya di `voices.json`. Daftar voice Piper: https://huggingface.co/rhasspy/piper-voices
  (nama voice = `<locale>-<speaker>-<quality>`, contoh `nl_NL-mls-medium`).
  Kalau satu bahasa kosong untuk suatu frasa, frasa itu dilewati.

## Catatan

- Terjemahan di `phrases.csv` ditulis manual, sebaiknya dicek penutur asli sebelum rilis.
  Beberapa frasa (mis. "Bonne matinée", "Bisa kurang?") bisa kamu sesuaikan.
- Nama voice di `voices.json` bisa berubah; kalau download gagal, cek nama persisnya
  di halaman piper-voices di atas.
- **Lisensi**: Piper sendiri GPL, dan tiap voice punya lisensi masing-masing (lihat MODEL_CARD
  tiap voice). Cek dulu sebelum audio dipakai di aplikasi komersial. edge-tts memakai layanan
  Microsoft yang tidak resmi, jadi kurang cocok untuk produk komersial.
