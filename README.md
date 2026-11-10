# Tourist Phrases TTS

Generate audio frasa wisatawan (30 frasa, 44 locale) dengan Piper TTS.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Jalankan

```bash
python generate.py
python generate.py --langs en_US,id_ID,fr_FR
python generate.py --overwrite
```

Model suara diunduh otomatis ke `voices/` saat pertama kali dipakai.

## Hasil

- `out/audio/<locale>/<key>.wav`
- `out/phrases.db` (SQLite, tabel `phrases`: key, lang, category, text, audio)

## File

- `phrases.csv`: frasa. Satu kolom per locale, tambah baris atau kolom sesuai kebutuhan.
- `voices.json`: locale ke nama voice Piper. Daftar lengkap: https://huggingface.co/rhasspy/piper-voices

Cek lisensi tiap voice sebelum dipakai komersial.
