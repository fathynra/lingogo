import re
from typing import Literal

from pydantic import BaseModel, Field, field_validator

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
LANG_RE = re.compile(r"^[a-z]{2,3}_[A-Z]{2}$")


class RegisterIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    email: str = Field(max_length=150, examples=["bita@example.com"])
    password: str = Field(min_length=8, max_length=72)

    @field_validator("email")
    @classmethod
    def _email(cls, v):
        v = v.strip().lower()
        if not EMAIL_RE.match(v):
            raise ValueError("Format email tidak valid")
        return v


class LoginIn(BaseModel):
    email: str
    password: str

    @field_validator("email")
    @classmethod
    def _email(cls, v):
        return v.strip().lower()


class Preferences(BaseModel):
    ui_language: Literal["en", "id"] = "en"
    pron_style: Literal["en", "id"] = Field("en", description="Panduan pelafalan untuk pembicara en | id")
    target_language: str | None = Field(None, description="Bahasa daerah terakhir dipakai", examples=["jv_ID"])
    default_city: str | None = Field(None, description="Kode kota favorit/terakhir (4 digit)", examples=["3578"])


class PreferencesUpdate(BaseModel):
    ui_language: Literal["en", "id"] | None = None
    pron_style: Literal["en", "id"] | None = None
    target_language: str | None = Field(None, description="Kosongkan string '' untuk menghapus")
    default_city: str | None = Field(None, description="Kosongkan string '' untuk menghapus")

    @field_validator("target_language")
    @classmethod
    def _lang(cls, v):
        if v and not LANG_RE.match(v):
            raise ValueError("Format kode bahasa: xx_XX atau xxx_XX (mis. jv_ID, ban_ID)")
        return v

    @field_validator("default_city")
    @classmethod
    def _city(cls, v):
        if v and not re.match(r"^\d{4}$", v):
            raise ValueError("Kode kota 4 digit (mis. 3578)")
        return v


class UserOut(BaseModel):
    id: int
    name: str
    email: str
    role: str
    preferences: Preferences


class TokenOut(BaseModel):
    token: str
    token_type: str = "Bearer"
    expires_in: int
    user: UserOut
