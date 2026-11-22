from contextlib import asynccontextmanager
from typing import Literal

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from . import config, db, schemas, seed
from .security import Principal, get_principal, require_admin

SOURCE_LANG = {"en": "en_US", "id": "id_ID"}


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
    version="1.0.0",
    description=(
        "Layanan inti LingoGo: destinasi, bahasa, kategori, frasa, terjemahan, panduan "
        "pelafalan (pembicara Inggris/Indonesia) dan audio.\n\n"
        "**Auth:** `X-API-Key` (kelompok lain) atau `Authorization: Bearer <JWT>` (pengguna aplikasi)."),
    lifespan=lifespan,
)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET", "PUT"],
                   allow_headers=["*"])


def _name(row, ui: str) -> str:
    return row["name_id"] if ui == "id" else row["name_en"]


def _audio_url(path: str | None) -> str | None:
    return f"{config.PUBLIC_BASE_URL}{config.AUDIO_URL_PREFIX}/{path}" if path else None


def _norm_ui(v: str) -> str:
    v = v.lower()
    if v in ("en", "en_us"):
        return "en"
    if v in ("id", "id_id"):
        return "id"
    raise HTTPException(422, "from harus 'en' atau 'id'")


# ---------- health (tanpa auth) ----------
@app.get("/health", tags=["system"], summary="Cek service hidup")
def health():
    with db.get_db() as con:
        n = con.execute("SELECT COUNT(*) FROM phrases").fetchone()[0]
    return {"service": "phrase-service", "status": "ok", "phrases": n}


# ---------- Destination & Language Context ----------
@app.get("/languages", response_model=list[schemas.Language], tags=["destination-language"],
         summary="Daftar bahasa")
def list_languages(ui: Literal["en", "id"] = "en", _: Principal = Depends(get_principal)):
    with db.get_db() as con:
        rows = con.execute("""
          SELECT l.*, (SELECT COUNT(*) FROM translations t WHERE t.lang=l.code) AS pc,
                      (SELECT COUNT(*) FROM audio a WHERE a.lang=l.code) AS ac
          FROM languages l ORDER BY l.name_en""").fetchall()
    return [schemas.Language(code=r["code"], name=_name(r, ui), native_name=r["native_name"],
                             country_code=r["country_code"], phrase_count=r["pc"],
                             audio_count=r["ac"]) for r in rows]


@app.get("/languages/{code}", response_model=schemas.Language, tags=["destination-language"],
         summary="Detail satu bahasa")
def get_language(code: str, ui: Literal["en", "id"] = "en", _: Principal = Depends(get_principal)):
    with db.get_db() as con:
        r = con.execute("""
          SELECT l.*, (SELECT COUNT(*) FROM translations t WHERE t.lang=l.code) AS pc,
                      (SELECT COUNT(*) FROM audio a WHERE a.lang=l.code) AS ac
          FROM languages l WHERE l.code=?""", (code,)).fetchone()
    if not r:
        raise HTTPException(404, "Bahasa tidak ditemukan")
    return schemas.Language(code=r["code"], name=_name(r, ui), native_name=r["native_name"],
                            country_code=r["country_code"], phrase_count=r["pc"], audio_count=r["ac"])


def _destinations(con, ui, code=None):
    q = "SELECT * FROM destinations" + (" WHERE code=?" if code else "") + " ORDER BY name_en"
    out = []
    for d in con.execute(q, (code,) if code else ()).fetchall():
        langs = [x[0] for x in con.execute(
            "SELECT language_code FROM destination_languages WHERE destination_code=? "
            "ORDER BY language_code", (d["code"],))]
        out.append(schemas.Destination(code=d["code"], name=_name(d, ui), languages=langs))
    return out


@app.get("/destinations", response_model=list[schemas.Destination],
         tags=["destination-language"], summary="Daftar destinasi + kode bahasanya")
def list_destinations(ui: Literal["en", "id"] = "en", _: Principal = Depends(get_principal)):
    with db.get_db() as con:
        return _destinations(con, ui)


def _emergency(con, d, ui) -> schemas.DestinationEmergency:
    rows = {r["service"]: r["number"] for r in con.execute(
        "SELECT service, number FROM emergency_numbers WHERE country_code=?", (d["code"],))}
    return schemas.DestinationEmergency(
        destination=d["code"], name=_name(d, ui), available=bool(rows),
        numbers=schemas.EmergencyNumbers(**rows))


@app.get("/emergency-numbers", response_model=list[schemas.DestinationEmergency],
         tags=["destination-language"], summary="Nomor darurat (polisi, damkar, ambulans) semua destinasi")
def list_emergency(ui: Literal["en", "id"] = "en", _: Principal = Depends(get_principal)):
    with db.get_db() as con:
        return [_emergency(con, d, ui)
                for d in con.execute("SELECT * FROM destinations ORDER BY name_en").fetchall()]


@app.get("/destinations/{code}/emergency-numbers", response_model=schemas.DestinationEmergency,
         tags=["destination-language"], summary="Nomor darurat satu destinasi")
def destination_emergency(code: str, ui: Literal["en", "id"] = "en",
                          _: Principal = Depends(get_principal)):
    with db.get_db() as con:
        d = con.execute("SELECT * FROM destinations WHERE code=?", (code.upper(),)).fetchone()
        if not d:
            raise HTTPException(404, "Destinasi tidak ditemukan")
        return _emergency(con, d, ui)


@app.get("/destinations/{code}/languages", response_model=list[schemas.Language],
         tags=["destination-language"], summary="Bahasa yang dipakai di suatu destinasi")
def destination_languages(code: str, ui: Literal["en", "id"] = "en",
                          _: Principal = Depends(get_principal)):
    code = code.upper()
    with db.get_db() as con:
        d = _destinations(con, ui, code)
        if not d:
            raise HTTPException(404, "Destinasi tidak ditemukan")
        rows = con.execute("""
          SELECT l.*, (SELECT COUNT(*) FROM translations t WHERE t.lang=l.code) AS pc,
                      (SELECT COUNT(*) FROM audio a WHERE a.lang=l.code) AS ac
          FROM languages l WHERE l.code IN (SELECT language_code FROM destination_languages
          WHERE destination_code=?) ORDER BY l.name_en""", (code,)).fetchall()
    return [schemas.Language(code=r["code"], name=_name(r, ui), native_name=r["native_name"],
                             country_code=r["country_code"], phrase_count=r["pc"],
                             audio_count=r["ac"]) for r in rows]


# ---------- Phrasebook Context ----------
@app.get("/categories", response_model=list[schemas.Category], tags=["phrasebook"],
         summary="Daftar kategori frasa")
def list_categories(ui: Literal["en", "id"] = "en", _: Principal = Depends(get_principal)):
    with db.get_db() as con:
        rows = con.execute("""
          SELECT c.*, (SELECT COUNT(*) FROM phrases p WHERE p.category_code=c.code) AS n
          FROM categories c ORDER BY sort_order""").fetchall()
    return [schemas.Category(code=r["code"], name=_name(r, ui), phrase_count=r["n"]) for r in rows]


_PHRASE_SQL = """
SELECT p.key, c.code AS cat_code, c.name_en AS cat_en, c.name_id AS cat_id,
       s.text AS source_text, t.text AS target_text, pr.guide AS guide, a.path AS audio_path
FROM phrases p
JOIN categories c ON c.code = p.category_code
JOIN translations s ON s.phrase_key = p.key AND s.lang = :src
JOIN translations t ON t.phrase_key = p.key AND t.lang = :lang
LEFT JOIN pronunciations pr ON pr.phrase_key = p.key AND pr.lang = :lang AND pr.style = :pron
LEFT JOIN audio a ON a.phrase_key = p.key AND a.lang = :lang
"""


def _row_to_phrase(r, ui, src, lang, pron) -> schemas.PhraseOut:
    return schemas.PhraseOut(
        key=r["key"],
        category=schemas.CategoryRef(code=r["cat_code"], name=r["cat_id"] if ui == "id" else r["cat_en"]),
        source=schemas.SourceText(lang=src, text=r["source_text"]),
        target=schemas.TargetText(
            lang=lang, text=r["target_text"],
            pronunciation=schemas.Pronunciation(style=pron, guide=r["guide"] or ""),
            audio_url=_audio_url(r["audio_path"])))


def _check_lang(con, lang):
    if not con.execute("SELECT 1 FROM languages WHERE code=?", (lang,)).fetchone():
        raise HTTPException(404, f"Bahasa '{lang}' tidak ditemukan")


@app.get("/phrases", response_model=schemas.PhraseList, tags=["phrasebook"],
         summary="Daftar frasa dalam bahasa tujuan")
def list_phrases(
    lang: str = Query(description="Kode bahasa tujuan, mis. ja_JP / fr_FR"),
    source: str = Query("en", alias="from", description="Bahasa antarmuka: en | id"),
    pron: Literal["en", "id"] = Query("en", description="Panduan pelafalan untuk pembicara en | id"),
    category: str | None = Query(None, description="Filter kode kategori, mis. greeting"),
    q: str | None = Query(None, min_length=1, max_length=50, description="Cari di teks sumber/tujuan"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    _: Principal = Depends(get_principal),
):
    ui = _norm_ui(source)
    src = SOURCE_LANG[ui]
    where, params = "", {"src": src, "lang": lang, "pron": pron}
    conds = []
    if category:
        conds.append("p.category_code = :cat")
        params["cat"] = category
    if q:
        conds.append("(s.text LIKE :q OR t.text LIKE :q)")
        params["q"] = f"%{q}%"
    if conds:
        where = " WHERE " + " AND ".join(conds)
    with db.get_db() as con:
        _check_lang(con, lang)
        total = con.execute(
            "SELECT COUNT(*) FROM (" + _PHRASE_SQL + where + ")", params).fetchone()[0]
        rows = con.execute(
            _PHRASE_SQL + where + " ORDER BY c.sort_order, p.rowid LIMIT :limit OFFSET :offset",
            {**params, "limit": limit, "offset": offset}).fetchall()
    return schemas.PhraseList(items=[_row_to_phrase(r, ui, src, lang, pron) for r in rows],
                              total=total, limit=limit, offset=offset)


@app.get("/phrases/{key}", response_model=schemas.PhraseOut, tags=["phrasebook"],
         summary="Satu frasa dalam bahasa tujuan")
def get_phrase(
    key: str,
    lang: str = Query(description="Kode bahasa tujuan"),
    source: str = Query("en", alias="from"),
    pron: Literal["en", "id"] = "en",
    _: Principal = Depends(get_principal),
):
    ui = _norm_ui(source)
    src = SOURCE_LANG[ui]
    with db.get_db() as con:
        _check_lang(con, lang)
        r = con.execute(_PHRASE_SQL + " WHERE p.key = :key",
                        {"src": src, "lang": lang, "pron": pron, "key": key}).fetchone()
    if not r:
        raise HTTPException(404, "Frasa tidak ditemukan")
    return _row_to_phrase(r, ui, src, lang, pron)


@app.put("/phrases/{key}/translations/{lang}", response_model=schemas.PhraseOut,
         tags=["admin"], summary="[Admin] Ubah teks / pelafalan sebuah terjemahan")
def update_translation(key: str, lang: str, body: schemas.TranslationUpdate,
                       _: Principal = Depends(require_admin)):
    if body.text is None and body.pronunciation_en is None and body.pronunciation_id is None:
        raise HTTPException(422, "Minimal satu field harus diisi")
    with db.get_db() as con:
        if not con.execute("SELECT 1 FROM translations WHERE phrase_key=? AND lang=?",
                           (key, lang)).fetchone():
            raise HTTPException(404, "Terjemahan tidak ditemukan")
        if body.text is not None:
            con.execute("UPDATE translations SET text=? WHERE phrase_key=? AND lang=?",
                        (body.text, key, lang))
        for style, val in (("en", body.pronunciation_en), ("id", body.pronunciation_id)):
            if val is not None:
                con.execute("INSERT OR REPLACE INTO pronunciations VALUES (?,?,?,?)",
                            (key, lang, style, val))
        con.commit()
        r = con.execute(_PHRASE_SQL + " WHERE p.key = :key",
                        {"src": "en_US", "lang": lang, "pron": "en", "key": key}).fetchone()
    return _row_to_phrase(r, "en", "en_US", lang, "en")
