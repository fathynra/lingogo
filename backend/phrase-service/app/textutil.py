"""Normalisasi teks untuk pencarian kota."""
import re
import unicodedata

_PREFIX = re.compile(r"^(kota\s+administrasi|kota\s+adm\.?|kota|kabupaten|kab\.?)\s+", re.I)


def normalize(s: str) -> str:
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = re.sub(r"[^a-z0-9 ]+", " ", s.lower())
    return re.sub(r"\s+", " ", s).strip()


def split_query(q: str) -> tuple[str, str | None]:
    """'Kota Surabaya' -> ('surabaya', 'kota'); 'kab. malang' -> ('malang', 'kabupaten'); 'bali' -> ('bali', None)."""
    q = q.strip()
    m = _PREFIX.match(q)
    typ = None
    if m:
        typ = "kota" if m.group(1).lower().startswith("kota") else "kabupaten"
        q = q[m.end():]
    return normalize(q), typ
