"""Query ke SQLite -> objek schemas. Murni Python (tanpa FastAPI) supaya mudah diuji.

Konvensi parameter:
  ui   : 'en' | 'id'  bahasa antarmuka: nama kategori/provinsi/bahasa & ARTI frasa
  pron : 'en' | 'id'  gaya panduan pelafalan (default mengikuti ui)
"""
from . import schemas
from .textutil import split_query

NOT_FOUND_CITY = {
    "id": "Maaf, kota yang Anda cari tidak ada di database.",
    "en": "Sorry, the city you are looking for is not in our database.",
}


class NotFound(Exception):
    """Dipetakan ke HTTP 404 oleh main.py."""


def _n(row, ui, base="name"):
    return row[f"{base}_id"] if ui == "id" else row[f"{base}_en"]


# ---------- bahasa ----------
_LANG_SQL = """SELECT l.*, (SELECT COUNT(*) FROM translations t WHERE t.lang = l.code) AS pc FROM languages l"""


def _language(r, ui) -> schemas.Language:
    return schemas.Language(code=r["code"], name=_n(r, ui), native_name=r["native_name"],
                            is_approximate=bool(r["is_approximate"]), closest_code=r["closest_code"],
                            phrase_count=r["pc"])


def list_languages(con, ui) -> list[schemas.Language]:
    return [_language(r, ui) for r in con.execute(_LANG_SQL + " ORDER BY l.name_en")]


def get_language(con, code, ui) -> schemas.Language:
    r = con.execute(_LANG_SQL + " WHERE l.code=?", (code,)).fetchone()
    if not r:
        raise NotFound(f"Bahasa '{code}' tidak ditemukan")
    return _language(r, ui)


def _languages_of(con, table, fk, owner, ui) -> list[schemas.Language]:
    rows = con.execute(
        f"""{_LANG_SQL} JOIN {table} x ON x.language_code = l.code
            WHERE x.{fk} = ? ORDER BY x.position""", (owner,)).fetchall()
    return [_language(r, ui) for r in rows]


# ---------- provinsi ----------
def _province(con, r, ui) -> schemas.Province:
    return schemas.Province(code=r["code"], name=_n(r, ui),
                            languages=_languages_of(con, "province_languages", "province_code", r["code"], ui))


def list_provinces(con, ui) -> list[schemas.Province]:
    return [_province(con, r, ui) for r in con.execute("SELECT * FROM provinces ORDER BY code")]


def get_province(con, code, ui) -> schemas.Province:
    r = con.execute("SELECT * FROM provinces WHERE code=?", (code,)).fetchone()
    if not r:
        raise NotFound("Provinsi tidak ditemukan")
    return _province(con, r, ui)


# ---------- kota ----------
_CITY_SQL = """SELECT c.*, p.name_id AS p_id, p.name_en AS p_en FROM cities c
               JOIN provinces p ON p.code = c.province_code"""


def _city(con, r, ui) -> schemas.City:
    return schemas.City(
        code=r["code"], name=r["name"], type=r["type"],
        province=schemas.ProvinceRef(code=r["province_code"], name=r["p_id"] if ui == "id" else r["p_en"]),
        languages=_languages_of(con, "city_languages", "city_code", r["code"], ui))


def get_city(con, code, ui) -> schemas.City:
    r = con.execute(_CITY_SQL + " WHERE c.code=?", (code,)).fetchone()
    if not r:
        raise NotFound(NOT_FOUND_CITY[ui])
    return _city(con, r, ui)


def search_cities(con, ui, q=None, province=None, type=None, limit=20, offset=0) -> schemas.CityList:
    """Cari kota/kabupaten. Tanpa q = daftar (bisa difilter provinsi/type).
    Dengan q: cocok jika nama MENGANDUNG teks (tanpa huruf besar/aksen). Awalan 'Kota'/'Kab.' di q dipahami.
    q tidak ketemu sama sekali -> NotFound('Maaf, kota yang Anda cari tidak ada di database.')."""
    conds, params = [], {}
    order = "c.name_norm, c.type, c.code"
    if q is not None:
        nq, q_type = split_query(q)
        if not nq:
            raise NotFound(NOT_FOUND_CITY[ui])
        type = type or q_type
        conds.append("c.name_norm LIKE :contains")
        params["contains"] = f"%{nq}%"
        params["nq"], params["prefix"], params["word"] = nq, f"{nq}%", f"% {nq}%"
        # urutan: sama persis > diawali > awal kata > mengandung
        order = ("CASE WHEN c.name_norm = :nq THEN 0 WHEN c.name_norm LIKE :prefix THEN 1 "
                 "WHEN c.name_norm LIKE :word THEN 2 ELSE 3 END, " + order)
    if province:
        conds.append("c.province_code = :province")
        params["province"] = province
    if type:
        conds.append("c.type = :type")
        params["type"] = type
    where = (" WHERE " + " AND ".join(conds)) if conds else ""
    total = con.execute(f"SELECT COUNT(*) FROM cities c{where}", params).fetchone()[0]
    if q is not None and total == 0:
        raise NotFound(NOT_FOUND_CITY[ui])
    rows = con.execute(f"{_CITY_SQL}{where} ORDER BY {order} LIMIT :limit OFFSET :offset",
                       {**params, "limit": limit, "offset": offset}).fetchall()
    return schemas.CityList(items=[_city(con, r, ui) for r in rows], total=total, limit=limit, offset=offset)


# ---------- kategori & frasa ----------
def list_categories(con, ui) -> list[schemas.Category]:
    rows = con.execute("""SELECT c.*, (SELECT COUNT(*) FROM phrases p WHERE p.category_code = c.code) AS n
                          FROM categories c ORDER BY c.sort_order""")
    return [schemas.Category(code=r["code"], name=_n(r, ui), phrase_count=r["n"]) for r in rows]


_PHRASE_SQL = """
SELECT p.key, p.meaning_id, p.meaning_en, c.code AS cat_code, c.name_id AS cat_id, c.name_en AS cat_en,
       t.text AS text, pr.guide AS guide
FROM phrases p
JOIN categories c ON c.code = p.category_code
JOIN translations t ON t.phrase_key = p.key AND t.lang = :lang
JOIN pronunciations pr ON pr.phrase_key = p.key AND pr.lang = :lang AND pr.style = :pron
"""
_PHRASE_ORDER = " ORDER BY c.sort_order, p.sort_order"


def _card(r, ui, pron) -> dict:
    return dict(key=r["key"], text=r["text"],
                pronunciation=schemas.Pronunciation(style=pron, guide=r["guide"]),
                meaning=schemas.Meaning(lang=ui, text=r["meaning_id"] if ui == "id" else r["meaning_en"]))


def _check_lang(con, lang):
    if not con.execute("SELECT 1 FROM languages WHERE code=?", (lang,)).fetchone():
        raise NotFound(f"Bahasa '{lang}' tidak ditemukan")


def _phrase_out(r, ui, pron, lang) -> schemas.PhraseOut:
    return schemas.PhraseOut(
        lang=lang, category=schemas.CategoryRef(code=r["cat_code"], name=r["cat_id"] if ui == "id" else r["cat_en"]),
        **_card(r, ui, pron))


def list_phrases(con, lang, ui, pron, category=None, q=None, limit=50, offset=0) -> schemas.PhraseList:
    _check_lang(con, lang)
    params = {"lang": lang, "pron": pron}
    conds = []
    if category:
        conds.append("p.category_code = :cat")
        params["cat"] = category
    if q:
        conds.append("(t.text LIKE :q OR p.meaning_id LIKE :q OR p.meaning_en LIKE :q)")
        params["q"] = f"%{q}%"
    where = (" WHERE " + " AND ".join(conds)) if conds else ""
    total = con.execute("SELECT COUNT(*) FROM (" + _PHRASE_SQL + where + ")", params).fetchone()[0]
    rows = con.execute(_PHRASE_SQL + where + _PHRASE_ORDER + " LIMIT :limit OFFSET :offset",
                       {**params, "limit": limit, "offset": offset}).fetchall()
    return schemas.PhraseList(items=[_phrase_out(r, ui, pron, lang) for r in rows],
                              total=total, limit=limit, offset=offset)


def get_phrase(con, key, lang, ui, pron) -> schemas.PhraseOut:
    _check_lang(con, lang)
    r = con.execute(_PHRASE_SQL + " WHERE p.key = :key", {"key": key, "lang": lang, "pron": pron}).fetchone()
    if not r:
        raise NotFound("Frasa tidak ditemukan")
    return _phrase_out(r, ui, pron, lang)


def phrasebook(con, lang, ui, pron) -> schemas.Phrasebook:
    """Seluruh frasa satu bahasa, dikelompokkan per kategori (untuk daftar kategori yang bisa di-expand)."""
    language = get_language(con, lang, ui)
    rows = con.execute(_PHRASE_SQL + _PHRASE_ORDER, {"lang": lang, "pron": pron}).fetchall()
    cats = {c.code: schemas.PhrasebookCategory(**c.model_dump(), phrases=[]) for c in list_categories(con, ui)}
    for r in rows:
        cats[r["cat_code"]].phrases.append(schemas.PhraseCard(**_card(r, ui, pron)))
    return schemas.Phrasebook(language=language, categories=[c for c in cats.values() if c.phrases])


def city_phrasebook(con, city_code, lang, ui, pron) -> schemas.CityPhrasebook:
    """Alur utama aplikasi: kota -> bahasa daerahnya -> kategori + kartu frasa.
    lang kosong = bahasa utama kota (urutan pertama di cities.csv)."""
    city = get_city(con, city_code, ui)
    if lang is None:
        lang = city.languages[0].code
    elif lang not in {l.code for l in city.languages}:
        raise NotFound(f"Bahasa '{lang}' tidak dipakai di {city.name}")
    book = phrasebook(con, lang, ui, pron)
    return schemas.CityPhrasebook(city=city, available_languages=city.languages, **book.model_dump())


def update_translation(con, key, lang, text=None, pron_en=None, pron_id=None):
    if not con.execute("SELECT 1 FROM translations WHERE phrase_key=? AND lang=?", (key, lang)).fetchone():
        raise NotFound("Terjemahan tidak ditemukan")
    if text is not None:
        con.execute("UPDATE translations SET text=? WHERE phrase_key=? AND lang=?", (text, key, lang))
    for style, val in (("en", pron_en), ("id", pron_id)):
        if val is not None:
            con.execute("INSERT OR REPLACE INTO pronunciations VALUES (?,?,?,?)", (key, lang, style, val))
    con.commit()


# ---------- nomor darurat ----------
def emergency_numbers(con, ui) -> list[schemas.EmergencyNumber]:
    return [schemas.EmergencyNumber(service=r["service"], name=_n(r, ui), number=r["number"])
            for r in con.execute("SELECT * FROM emergency_numbers ORDER BY rowid")]
