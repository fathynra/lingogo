from pydantic import BaseModel, Field


class Language(BaseModel):
    code: str = Field(examples=["ja_JP"])
    name: str
    native_name: str
    country_code: str
    phrase_count: int
    audio_count: int


class Destination(BaseModel):
    code: str
    name: str
    languages: list[str]


class Category(BaseModel):
    code: str
    name: str
    phrase_count: int


class Pronunciation(BaseModel):
    style: str = Field(description="'en' = dibaca pembicara Inggris, 'id' = pembicara Indonesia")
    guide: str


class SourceText(BaseModel):
    lang: str
    text: str


class TargetText(BaseModel):
    lang: str
    text: str
    pronunciation: Pronunciation
    audio_url: str | None


class CategoryRef(BaseModel):
    code: str
    name: str


class PhraseOut(BaseModel):
    key: str
    category: CategoryRef
    source: SourceText
    target: TargetText


class PhraseList(BaseModel):
    items: list[PhraseOut]
    total: int
    limit: int
    offset: int


class TranslationUpdate(BaseModel):
    text: str | None = Field(default=None, min_length=1, max_length=300)
    pronunciation_en: str | None = Field(default=None, min_length=1, max_length=300)
    pronunciation_id: str | None = Field(default=None, min_length=1, max_length=300)


class EmergencyNumbers(BaseModel):
    police: str | None = None
    fire: str | None = None
    ambulance: str | None = None


class DestinationEmergency(BaseModel):
    destination: str = Field(examples=["DE"])
    name: str
    available: bool = Field(description="False jika data nomor darurat negara ini belum ada")
    numbers: EmergencyNumbers
