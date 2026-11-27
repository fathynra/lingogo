from pydantic import BaseModel, Field


class Language(BaseModel):
    code: str = Field(examples=["jv_ID"])
    name: str = Field(description="Nama bahasa dalam bahasa antarmuka (ui)")
    native_name: str
    is_approximate: bool = Field(description="True = belum ada data asli, isinya memakai bahasa terdekat")
    closest_code: str = Field(description="Kode bahasa terdekat; sama dengan code jika data asli")
    phrase_count: int


class ProvinceRef(BaseModel):
    code: str = Field(examples=["35"])
    name: str


class Province(ProvinceRef):
    languages: list[Language] = Field(description="Bahasa daerah provinsi; yang pertama = utama")


class CityRef(BaseModel):
    code: str = Field(examples=["3578"])
    name: str = Field(examples=["Surabaya"])
    type: str = Field(description="kota | kabupaten")


class City(CityRef):
    province: ProvinceRef
    languages: list[Language] = Field(description="Bahasa daerah kota; yang pertama = utama")


class CityList(BaseModel):
    items: list[City]
    total: int
    limit: int
    offset: int


class Category(BaseModel):
    code: str
    name: str
    phrase_count: int


class CategoryRef(BaseModel):
    code: str
    name: str


class Pronunciation(BaseModel):
    style: str = Field(description="'en' = dibaca pembicara Inggris, 'id' = pembicara Indonesia")
    guide: str


class Meaning(BaseModel):
    lang: str = Field(description="'id' atau 'en'")
    text: str


class PhraseCard(BaseModel):
    """Satu kartu: istilah daerah (tebal, besar), pelafalan (kecil), arti (sedang)."""
    key: str
    text: str = Field(description="Istilah dalam bahasa daerah")
    pronunciation: Pronunciation
    meaning: Meaning


class PhraseOut(PhraseCard):
    lang: str
    category: CategoryRef


class PhraseList(BaseModel):
    items: list[PhraseOut]
    total: int
    limit: int
    offset: int


class PhrasebookCategory(Category):
    phrases: list[PhraseCard]


class Phrasebook(BaseModel):
    language: Language
    categories: list[PhrasebookCategory]


class CityPhrasebook(Phrasebook):
    city: City
    available_languages: list[Language] = Field(description="Semua bahasa kota ini (untuk pilihan ganti bahasa)")


class TranslationUpdate(BaseModel):
    text: str | None = Field(default=None, min_length=1, max_length=300)
    pronunciation_en: str | None = Field(default=None, min_length=1, max_length=300)
    pronunciation_id: str | None = Field(default=None, min_length=1, max_length=300)


class EmergencyNumber(BaseModel):
    service: str = Field(examples=["police"])
    name: str
    number: str
