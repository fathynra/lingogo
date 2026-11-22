import hmac

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer

from . import config

_api_key = APIKeyHeader(name="X-API-Key", auto_error=False, description="Untuk kelompok lain (server ke server)")
_bearer = HTTPBearer(auto_error=False, description="JWT dari POST /auth/login (untuk pengguna aplikasi)")


class Principal(dict):
    """kind: 'user' | 'group'; role: 'user' | 'admin' | 'partner'."""


def _unauthorized(msg: str):
    return HTTPException(401, msg, headers={"WWW-Authenticate": "Bearer"})


def get_principal(
    key: str | None = Depends(_api_key),
    cred: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> Principal:
    if key:
        for k, name in config.api_keys().items():
            if hmac.compare_digest(k, key):
                return Principal(kind="group", name=name, role="partner")
        raise _unauthorized("API key tidak valid")
    if cred:
        if not config.JWT_SECRET:
            raise HTTPException(500, "JWT_SECRET belum dikonfigurasi")
        try:
            data = jwt.decode(cred.credentials, config.JWT_SECRET,
                              algorithms=[config.JWT_ALGORITHM], issuer=config.JWT_ISSUER)
        except jwt.PyJWTError:
            raise _unauthorized("Token tidak valid atau kedaluwarsa")
        return Principal(kind="user", id=data.get("sub"), name=data.get("name"),
                         role=data.get("role", "user"))
    raise _unauthorized("Butuh header X-API-Key atau Authorization: Bearer <token>")


def require_admin(p: Principal = Depends(get_principal)) -> Principal:
    if p.get("role") != "admin":
        raise HTTPException(403, "Hanya admin yang boleh mengubah data")
    return p
