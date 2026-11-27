# Deploy LingoGo ke STB + Cloudflare Tunnel (K02: `lingogo.stei.site`)

Aturan STB: hanya container microservice, `mem_limit` & `cpus` di tiap container, rahasia di `.env`, jangan membuka port database, jangan menjalankan model AI / build mobile di STB.

## 0. Sekali saja, di laptop
1. **Pesan nama `lingogo`** di API Registry kelas. Hostname akhir: `lingogo.stei.site` (satu tingkat saja, jangan `api.lingogo...`).
2. Repo `lingogo` berisi `database/` (CSV provinsi, kota, bahasa daerah, frasa) dan `backend/` (folder ini). Tidak ada audio.
3. Cek data: `cd backend && python tools/check_data.py --full` → harus `OK` (38 provinsi, semua kota, tanpa sel kosong).
4. Buat dokumentasi API (butuh paket service terpasang): `pip install -r phrase-service/requirements.txt -r user-service/requirements.txt -r tools/requirements.txt && python tools/export_docs.py`, lalu commit `gateway/docs/openapi.yaml` dan `docs/LingoGo.postman_collection.json`.
5. Buat rahasia: `sh scripts/gen-secrets.sh` (simpan di password manager).
6. Push: `git add database backend && git commit -m "LingoGo" && git push`; pastikan `.env` **tidak** ikut (`git status`).

## 1. Cloudflare Tunnel (tugas anggota A)
Ikuti slide dosen (login akun kelas, jangan commit/bagikan kredensial). Buat tunnel `k02-lingogo`, salin **token** ke `.env` sebagai `TUNNEL_TOKEN`, lalu Public Hostname: Subdomain `lingogo` · Domain `stei.site` · Type `HTTP` · URL `gateway:80`.

## 2. Di STB (SSH)
```bash
uname -m && docker --version && free -h
mkdir -p /www/apps && cd /www/apps
git clone --depth 1 https://github.com/USERNAME/lingogo.git && cd lingogo/backend
cp .env.example .env && nano .env              # isi JWT_SECRET, API_KEYS, password, TUNNEL_TOKEN
docker compose --profile tunnel up -d --build
docker compose ps
docker compose logs tunnel | tail -5           # harus ada "Registered tunnel connection"
curl localhost:8080/api/health                 # {"gateway":"ok"}
docker compose logs phrase-service | grep seed # "[seed] data diisi ulang dari database/: {provinces..., cities...}"
```

## 3. Uji dari laptop
```bash
BASE=https://lingogo.stei.site API_KEY=<key> DEMO_EMAIL=demo@lingogo.stei.site DEMO_PASSWORD=<pw> sh scripts/smoke-test.sh
```

## 4. Daftarkan ke API Registry (sebelum akhir Minggu 14)
Kelompok `lingogo` · K02 · Tourism · Base URL `https://lingogo.stei.site/api` · dokumentasi (`/api/docs`, Postman) · auth `X-API-Key` + Bearer JWT · status `Online`.

## 5. Operasional
| Tugas | Perintah |
|---|---|
| Update kode / data CSV | laptop: commit + push → STB (folder `backend/`): `sh scripts/deploy.sh` (data di-seed ulang otomatis jika CSV berubah) |
| Lihat log | `docker compose logs -f phrase-service` |
| Backup DB (berkala) | `sh scripts/backup.sh` |
| Paksa isi ulang data | `docker compose exec phrase-service python -m app.seed --reset` |
| Cabut API key | hapus dari `API_KEYS` di `.env` → `docker compose --profile tunnel up -d` |

## 6. Masalah umum
| Gejala | Solusi |
|---|---|
| `502 Bad Gateway` dari Cloudflare | URL tunnel salah (harus `gateway:80`) atau gateway mati: `docker compose ps` |
| `401` di semua endpoint | `JWT_SECRET` beda antar service / `.env` belum terbaca → `docker compose up -d --force-recreate` |
| phrase-service gagal start: "N masalah data" | Ada sel kosong / referensi salah di CSV. Pesan menyebut berkas & barisnya; perbaiki lalu `python tools/check_data.py` |
| phrase-service gagal start: "Folder database tidak ditemukan" | `backend/` harus bersaudara dengan `database/` (mount `../database`). Jalankan compose dari folder `backend/` |
| `/api/docs` kosong | `gateway/docs/openapi.yaml` belum dibuat: jalankan `python tools/export_docs.py` lalu commit |
| Container di-kill (OOM) | `docker stats`; naikkan `mem_limit` sedikit atau cek `free -h` |
