"""Lapisan HTTP phrase-service. Isinya hanya routing + validasi parameter; logika ada di repository.py."""
from contextlib import asynccontextmanager
from typing import Literal

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from . import db, repository as repo, schemas, seed
from .security import Principal, get_principal, require_admin

Ui = Literal["en", "id"]


@asynccontextmanager
async def lifespan(app: FastAPI):
    con = db.connect()
    try:
        seed.ensure_seeded(con)
    finally:
        con.close()
    yield


app = FastAPI(
    title="LingoGo Phrase Service",
    version="2.0.0",
    description=(
        "Layanan inti LingoGo untuk wisatawan di Indonesia: cari kota -> bahasa daerahnya -> "
        "kategori frasa -> kartu (istilah daerah, pelafalan Indonesia/Inggris, arti Indonesia/Inggris).\n\n"
        "`ui` = bahasa antarmuka (nama + arti): `id` | `en`. `pron` = gaya pelafalan `id` | `en` "
        "(default mengikuti `ui`).\n\n"
        "**Auth:** `X-API-Key` (kelompok lain) atau `Authorization: Bearer <JWT>` (pengguna aplikasi)."),
    lifespan=lifespan,
)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET", "PUT"], allow_headers=["*"])


def run(fn, *args, **kwargs):
    """Buka koneksi, jalankan fungsi repository, ubah NotFound -> HTTP 404."""
    with db.get_db() as con:
        try:
            return fn(con, *args, **kwargs)
        except repo.NotFound as e:
            raise HTTPException(404, str(e))


# ---------- health (tanpa auth) ----------
@app.get("/health", tags=["system"], summary="Cek service hidup")
def health():
    with db.get_db() as con:
        n = con.execute("SELECT COUNT(*) FROM phrases").fetchone()[0]
        c = con.execute("SELECT COUNT(*) FROM cities").fetchone()[0]
    return {"service": "phrase-service", "status": "ok", "phrases": n, "cities": c}


# ---------- Wilayah: provinsi & kota ----------
@app.get("/provinces", response_model=list[schemas.Province], tags=["region"],
         summary="Daftar provinsi + bahasa daerahnya")
def list_provinces(ui: Ui = "en", _: Principal = Depends(get_principal)):
    return run(repo.list_provinces, ui)


@app.get("/provinces/{code}", response_model=schemas.Province, tags=["region"], summary="Detail satu provinsi")
def get_province(code: str, ui: Ui = "en", _: Principal = Depends(get_principal)):
    return run(repo.get_province, code, ui)


@app.get("/cities", response_model=schemas.CityList, tags=["region"],
         summary="Cari kota/kabupaten (q) atau daftar semua",
         description=("Dengan `q`: cocok jika nama mengandung teks (tidak peka huruf besar/aksen; awalan "
                      "'Kota'/'Kab.' boleh dipakai). Jika tidak ada yang cocok -> **404** dengan pesan "
                      "'Maaf, kota yang Anda cari tidak ada di database.' (sesuai `ui`). Tanpa `q` = daftar berhalaman."))
def search_cities(
    q: str | None = Query(None, min_length=1, max_length=60, description="Teks pencarian, mis. 'surabaya'"),
    province: str | None = Query(None, description="Filter kode provinsi, mis. 35"),
    type: Literal["kota", "kabupaten"] | None = None,
    ui: Ui = "en",
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    _: Principal = Depends(get_principal),
):
    return run(repo.search_cities, ui, q=q, province=province, type=type, limit=limit, offset=offset)


@app.get("/provinces/{code}/cities", response_model=schemas.CityList, tags=["region"],
         summary="Kota/kabupaten di satu provinsi")
def province_cities(code: str, ui: Ui = "en", limit: int = Query(100, ge=1, le=100),
                    offset: int = Query(0, ge=0), _: Principal = Depends(get_principal)):
    def go(con):
        repo.get_province(con, code, ui)            # 404 jika provinsi tidak ada
        return repo.search_cities(con, ui, province=code, limit=limit, offset=offset)
    return run(go)


@app.get("/cities/{code}", response_model=schemas.City, tags=["region"],
         summary="Detail satu kota: provinsi + bahasa daerahnya")
def get_city(code: str, ui: Ui = "en", _: Principal = Depends(get_principal)):
    return run(repo.get_city, code, ui)


# ---------- Bahasa ----------
@app.get("/languages", response_model=list[schemas.Language], tags=["language"], summary="Daftar bahasa daerah")
def list_languages(ui: Ui = "en", _: Principal = Depends(get_principal)):
    return run(repo.list_languages, ui)


@app.get("/languages/{code}", response_model=schemas.Language, tags=["language"], summary="Detail satu bahasa")
def get_language(code: str, ui: Ui = "en", _: Principal = Depends(get_principal)):
    return run(repo.get_language, code, ui)


# ---------- Phrasebook ----------
@app.get("/cities/{code}/phrasebook", response_model=schemas.CityPhrasebook, tags=["phrasebook"],
         summary="Alur utama: kota -> frasa per kategori dalam bahasa daerahnya",
         description="`lang` opsional; kosong = bahasa utama kota. Untuk kota berbahasa ganda, "
                     "`available_languages` berisi pilihan lainnya.")
def city_phrasebook(code: str, lang: str | None = Query(None, description="Salah satu bahasa kota ini"),
                    ui: Ui = "en", pron: Ui | None = Query(None, description="Default = ui"),
                    _: Principal = Depends(get_principal)):
    return run(repo.city_phrasebook, code, lang, ui, pron or ui)


@app.get("/languages/{code}/phrasebook", response_model=schemas.Phrasebook, tags=["phrasebook"],
         summary="Seluruh frasa satu bahasa, dikelompokkan per kategori")
def language_phrasebook(code: str, ui: Ui = "en", pron: Ui | None = Query(None, description="Default = ui"),
                        _: Principal = Depends(get_principal)):
    return run(repo.phrasebook, code, ui, pron or ui)


@app.get("/categories", response_model=list[schemas.Category], tags=["phrasebook"], summary="Daftar kategori frasa")
def list_categories(ui: Ui = "en", _: Principal = Depends(get_principal)):
    return run(repo.list_categories, ui)


@app.get("/phrases", response_model=schemas.PhraseList, tags=["phrasebook"],
         summary="Daftar frasa (datar, berhalaman) dalam satu bahasa daerah")
def list_phrases(
    lang: str = Query(description="Kode bahasa daerah, mis. jv_ID"),
    ui: Ui = "en",
    pron: Ui | None = Query(None, description="Gaya pelafalan, default = ui"),
    category: str | None = Query(None, description="Filter kode kategori, mis. greeting"),
    q: str | None = Query(None, min_length=1, max_length=50, description="Cari di istilah daerah / arti"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    _: Principal = Depends(get_principal),
):
    return run(repo.list_phrases, lang, ui, pron or ui, category=category, q=q, limit=limit, offset=offset)


@app.get("/phrases/{key}", response_model=schemas.PhraseOut, tags=["phrasebook"], summary="Satu frasa")
def get_phrase(key: str, lang: str = Query(description="Kode bahasa daerah"), ui: Ui = "en",
               pron: Ui | None = Query(None, description="Default = ui"), _: Principal = Depends(get_principal)):
    return run(repo.get_phrase, key, lang, ui, pron or ui)


# ---------- Nomor darurat nasional ----------
@app.get("/emergency-numbers", response_model=list[schemas.EmergencyNumber], tags=["region"],
         summary="Nomor darurat nasional (polisi, damkar, ambulans, SAR, 112)")
def emergency_numbers(ui: Ui = "en", _: Principal = Depends(get_principal)):
    return run(repo.emergency_numbers, ui)


# ---------- Admin ----------
@app.put("/phrases/{key}/translations/{lang}", response_model=schemas.PhraseOut, tags=["admin"],
         summary="[Admin] Ubah teks / pelafalan sebuah terjemahan")
def update_translation(key: str, lang: str, body: schemas.TranslationUpdate, _: Principal = Depends(require_admin)):
    if body.text is None and body.pronunciation_en is None and body.pronunciation_id is None:
        raise HTTPException(422, "Minimal satu field harus diisi")

    def go(con):
        repo.update_translation(con, key, lang, body.text, body.pronunciation_en, body.pronunciation_id)
        return repo.get_phrase(con, key, lang, "en", "en")
    return run(go)
