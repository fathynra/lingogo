import sqlite3
import time
import uuid
from contextlib import asynccontextmanager

import bcrypt
import jwt
from fastapi import Depends, FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from . import config, db, schemas

_bearer = HTTPBearer(auto_error=False, description="JWT dari POST /auth/login")


def _hash(pw: str) -> str:
    return bcrypt.hashpw(pw.encode()[:72], bcrypt.gensalt(rounds=10)).decode()


def _verify(pw: str, h: str) -> bool:
    try:
        return bcrypt.checkpw(pw.encode()[:72], h.encode())
    except ValueError:
        return False


def _bootstrap(con):
    for email, pw, role, name in ((config.ADMIN_EMAIL, config.ADMIN_PASSWORD, "admin", "Admin LingoGo"),
                                  (config.DEMO_EMAIL, config.DEMO_PASSWORD, "user", "Akun Uji")):
        if email and pw and not con.execute("SELECT 1 FROM users WHERE email=?",
                                            (email.lower(),)).fetchone():
            con.execute("INSERT INTO users (name,email,password_hash,role) VALUES (?,?,?,?)",
                        (name, email.lower(), _hash(pw), role))
    con.execute("DELETE FROM revoked_tokens WHERE expires_at < ?", (int(time.time()),))
    con.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    con = db.connect()
    try:
        db.init_schema(con)
        _bootstrap(con)
    finally:
        con.close()
    yield


app = FastAPI(
    title="LingoGo User Service",
    version="1.0.0",
    description="Registrasi, login/logout (JWT), dan preferensi pengguna LingoGo.",
    lifespan=lifespan,
)
app.add_middleware(CORSMiddleware, allow_origins=["*"],
                   allow_methods=["GET", "POST", "PATCH"], allow_headers=["*"])


def _user_out(r) -> schemas.UserOut:
    return schemas.UserOut(
        id=r["id"], name=r["name"], email=r["email"], role=r["role"],
        preferences=schemas.Preferences(
            ui_language=r["ui_language"], pron_style=r["pron_style"],
            target_language=r["target_language"], default_destination=r["default_destination"]))


def current_claims(cred: HTTPAuthorizationCredentials | None = Depends(_bearer)) -> dict:
    if not cred:
        raise HTTPException(401, "Butuh header Authorization: Bearer <token>",
                            headers={"WWW-Authenticate": "Bearer"})
    try:
        claims = jwt.decode(cred.credentials, config.JWT_SECRET, algorithms=[config.JWT_ALGORITHM],
                            issuer=config.JWT_ISSUER)
    except jwt.PyJWTError:
        raise HTTPException(401, "Token tidak valid atau kedaluwarsa",
                            headers={"WWW-Authenticate": "Bearer"})
    with db.get_db() as con:
        if con.execute("SELECT 1 FROM revoked_tokens WHERE jti=?", (claims.get("jti"),)).fetchone():
            raise HTTPException(401, "Token sudah logout", headers={"WWW-Authenticate": "Bearer"})
    return claims


def _load_user(claims) -> sqlite3.Row:
    with db.get_db() as con:
        r = con.execute("SELECT * FROM users WHERE id=?", (claims["sub"],)).fetchone()
    if not r:
        raise HTTPException(401, "Pengguna tidak ditemukan")
    return r


@app.get("/health", tags=["system"], summary="Cek service hidup")
def health():
    return {"service": "user-service", "status": "ok"}


@app.post("/auth/register", status_code=201, response_model=schemas.UserOut, tags=["auth"],
          summary="Daftar akun baru")
def register(body: schemas.RegisterIn):
    with db.get_db() as con:
        try:
            cur = con.execute("INSERT INTO users (name,email,password_hash) VALUES (?,?,?)",
                              (body.name.strip(), body.email, _hash(body.password)))
            con.commit()
        except sqlite3.IntegrityError:
            raise HTTPException(409, "Email sudah terdaftar")
        r = con.execute("SELECT * FROM users WHERE id=?", (cur.lastrowid,)).fetchone()
    return _user_out(r)


@app.post("/auth/login", response_model=schemas.TokenOut, tags=["auth"], summary="Masuk, dapat JWT")
def login(body: schemas.LoginIn):
    with db.get_db() as con:
        r = con.execute("SELECT * FROM users WHERE email=?", (body.email,)).fetchone()
    # pesan sama untuk email/password salah (tidak membocorkan mana yang salah)
    if not r or not _verify(body.password, r["password_hash"]):
        raise HTTPException(401, "Email atau password salah")
    now = int(time.time())
    exp = now + config.JWT_EXPIRE_MINUTES * 60
    token = jwt.encode({"sub": str(r["id"]), "name": r["name"], "role": r["role"],
                        "iss": config.JWT_ISSUER, "iat": now, "exp": exp,
                        "jti": uuid.uuid4().hex}, config.JWT_SECRET, algorithm=config.JWT_ALGORITHM)
    return schemas.TokenOut(token=token, expires_in=config.JWT_EXPIRE_MINUTES * 60, user=_user_out(r))


@app.post("/auth/logout", status_code=204, tags=["auth"], summary="Keluar (token dicabut)")
def logout(claims: dict = Depends(current_claims)):
    with db.get_db() as con:
        con.execute("INSERT OR IGNORE INTO revoked_tokens VALUES (?,?)",
                    (claims["jti"], int(claims["exp"])))
        con.commit()
    return Response(status_code=204)


@app.get("/auth/me", response_model=schemas.UserOut, tags=["auth"], summary="Data akun + preferensi")
def me(claims: dict = Depends(current_claims)):
    return _user_out(_load_user(claims))


@app.get("/users/me/preferences", response_model=schemas.Preferences, tags=["users"],
         summary="Lihat preferensi")
def get_prefs(claims: dict = Depends(current_claims)):
    return _user_out(_load_user(claims)).preferences


@app.patch("/users/me/preferences", response_model=schemas.Preferences, tags=["users"],
           summary="Ubah preferensi (bahasa UI, gaya pelafalan, bahasa tujuan, destinasi)")
def update_prefs(body: schemas.PreferencesUpdate, claims: dict = Depends(current_claims)):
    data = body.model_dump(exclude_unset=True)
    if not data:
        raise HTTPException(422, "Tidak ada field yang diubah")
    for k in ("ui_language", "pron_style"):
        if k in data and data[k] is None:
            raise HTTPException(422, f"{k} tidak boleh null")
    # '' -> NULL
    data = {k: (v or None) if k in ("target_language", "default_destination") else v
            for k, v in data.items()}
    sets = ", ".join(f"{k}=?" for k in data)  # kunci berasal dari skema, bukan input mentah
    with db.get_db() as con:
        con.execute(f"UPDATE users SET {sets} WHERE id=?", (*data.values(), claims["sub"]))
        con.commit()
        r = con.execute("SELECT * FROM users WHERE id=?", (claims["sub"],)).fetchone()
    return _user_out(r).preferences
