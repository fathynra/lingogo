# Deploy LingoGo ke STB + Cloudflare Tunnel (K02: `lingogo.stei.site`)

Aturan STB: hanya container microservice, `mem_limit` & `cpus` di tiap container, rahasia di `.env`, jangan membuka port database, jangan menjalankan model AI / build mobile di STB.

## 0. Sekali saja, di laptop
1. **Pesan nama `lingogo`** di API Registry kelas (siapa cepat dia dapat). Hostname akhir: `lingogo.stei.site` (satu tingkat saja — jangan `api.lingogo...`).
2. Repo `lingogo` berisi `tts/` (sudah ada, termasuk `out/audio`) dan `backend/` (folder ini). Audio **tidak perlu disalin atau dikonversi**; backend membaca `tts/out/audio` langsung.
3. Cek data: `cd backend && python tools/check_data.py` → harus `OK` (1320/1320 audio).
4. Buat rahasia: `sh scripts/gen-secrets.sh` (simpan di password manager).
5. Push: `git add backend && git commit -m "Backend LingoGo" && git push` — pastikan `.env` **tidak** ikut (`git status`).

## 1. Cloudflare Tunnel (tugas anggota A)
1. Login dashboard Cloudflare dengan akun kelas (kredensial ada di slide dosen; **jangan di-commit / dibagikan**, logout setelah selesai, hanya ubah milik kelompok sendiri).
2. Networks → Tunnels → **Create a tunnel** → Cloudflared → nama `k02-lingogo`.
3. Salin **token** → akan dimasukkan ke `.env` sebagai `TUNNEL_TOKEN`.
4. Tab **Public Hostname → Add**: Subdomain `lingogo` · Domain `stei.site` · Type `HTTP` · URL `gateway:80`.
   (Nama menu bisa sedikit berbeda jika tampilan Cloudflare diperbarui.)

## 2. Di STB (SSH)
```bash
uname -m && docker --version && free -h        # cek arsitektur (arm64?), Docker, RAM
mkdir -p /www/apps && cd /www/apps
git clone --depth 1 https://github.com/USERNAME/lingogo.git && cd lingogo/backend   # repo ±120 MB karena tts/out
cp .env.example .env && nano .env              # isi JWT_SECRET, API_KEYS, password, TUNNEL_TOKEN
docker compose --profile tunnel up -d --build  # build pertama ±3-8 menit
docker compose ps
docker compose logs tunnel | tail -5           # harus ada "Registered tunnel connection"
curl localhost:8080/api/health                 # {"gateway":"ok"}
curl https://lingogo.stei.site/api/health      # dari mana saja
docker compose logs phrase-service | grep seed # "audio terdaftar: 1320"
```
Repo private? `git clone` meminta username + **Personal Access Token** GitHub (bukan password).

## 3. Uji dari laptop
```bash
BASE=https://lingogo.stei.site API_KEY=<key> DEMO_EMAIL=demo@lingogo.stei.site DEMO_PASSWORD=<pw> sh scripts/smoke-test.sh
```
Atau jalankan **Postman collection** (isi variabel `apiKey`, `demoPassword`, `adminPassword`) — semua request hijau. Simpan screenshot sebagai bukti.

## 4. Daftarkan ke API Registry — **sebelum akhir Minggu 14 (29 Nov 2026)**
Isi: kelompok `lingogo` · kelas K02 · tema Tourism · Base URL `https://lingogo.stei.site/api` · dokumentasi (link README / `/api/docs` / Postman) · auth `X-API-Key` + Bearer JWT · status `Online`.
Bagikan API key ke kelompok yang memintanya (satu key per kelompok di `API_KEYS`, lalu `docker compose --profile tunnel up -d`).

## 5. Operasional
| Tugas | Perintah |
|---|---|
| Update kode / data / audio | di laptop: commit + push → di STB (folder `backend/`): `sh scripts/deploy.sh` (data di-seed ulang otomatis jika `tts/` berubah) |
| Lihat log | `docker compose logs -f phrase-service` |
| Beban | `docker stats --no-stream` · `free -h` |
| Backup DB (berkala) | `sh scripts/backup.sh` → `backup-YYYYmmdd-HHMM/` (salin ke laptop dengan `scp`) |
| Paksa isi ulang data | `docker compose exec phrase-service python -m app.seed --reset` |
| Cabut API key | hapus dari `API_KEYS` di `.env` → `docker compose --profile tunnel up -d` |

## 6. Masalah umum
| Gejala | Solusi |
|---|---|
| Tunnel *Down / Inactive* | Token salah atau STB offline: cek `.env` & `docker compose logs tunnel` |
| `502 Bad Gateway` dari Cloudflare | URL tunnel salah (harus `gateway:80`) atau gateway mati: `docker compose ps` |
| `502 {"detail":"Service sedang tidak tersedia"}` | phrase/user-service sedang restart/mati: `docker compose logs <service>` |
| `401` di semua endpoint | `JWT_SECRET` beda antar service / `.env` belum terbaca → `docker compose up -d --force-recreate` |
| `audio_count` = 0 / audio 404 | `tts/out/audio` tidak ikut ter-clone/di-pull → `git pull`, cek `ls ../tts/out/audio`, lalu `docker compose restart phrase-service` |
| phrase-service gagal start: "Folder tts tidak ditemukan" | `backend/` harus bersaudara dengan `tts/` (mount `../tts`). Jalankan compose dari folder `backend/` |
| Container di-kill (OOM) | `docker stats`; naikkan `mem_limit` sedikit atau cek `free -h` |
| Subdomain sudah dipakai | Milik kelompok lain: cek API Registry, pilih nama lain (dan ganti di Cloudflare + README) |
