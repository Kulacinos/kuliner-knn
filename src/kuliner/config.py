"""Konstanta dan jalur berkas proyek.

URL default basis data mengikuti bentuk relatif
``sqlite:///data/kuliner.db`` (diukur dari akar repositori).
Fungsi ``url_db()`` mengubahnya menjadi jalur absolut agar skrip
tetap benar meski dijalankan dari folder lain atau di Windows.
"""

from __future__ import annotations

from pathlib import Path

# Akar repositori: folder yang berisi requirements.txt dan data/.
def _cari_akar() -> Path:
    di_sini = Path(__file__).resolve()
    for folder in di_sini.parents:
        if (folder / "requirements.txt").is_file() and (folder / "data").is_dir():
            return folder
    return di_sini.parents[2]


AKAR_REPO = _cari_akar()
PATH_DATA = AKAR_REPO / "data"
PATH_MENTAH = PATH_DATA / "raw" / "gofood_Jabodetabek_bandung.csv"
PATH_BERSIH = PATH_DATA / "processed" / "gofood_clean.csv"
PATH_DB = PATH_DATA / "kuliner.db"

# Bentuk yang diminta sebagai default (relatif ke akar repo).
URL_DB_DEFAULT = "sqlite:///data/kuliner.db"


def url_db(path_db: Path | None = None) -> str:
    """Kembalikan URL SQLAlchemy SQLite dengan jalur absolut (aman di Windows)."""
    tujuan = Path(path_db) if path_db is not None else PATH_DB
    return "sqlite:///" + tujuan.resolve().as_posix()


# Bobot jarak berbobot (jumlah = 1). Dipakai mulai bagian 2.
BOBOT_DEFAULT = {
    "lokasi": 0.35,
    "kategori": 0.30,
    "rating": 0.20,
    "harga": 0.15,
}

# Normalisasi harga: (price_level - P_MIN) / (P_MAX - P_MIN) = (p - 1) / 3.
P_MIN = 1
P_MAX = 4

# Rentang rating merchant yang sudah dinilai pada data bersih TK1.
# rating_gap = (R_MAX - r) / (R_MAX - R_MIN); yang belum dinilai = 1,0.
R_MIN_DEFAULT = 2.3
R_MAX_DEFAULT = 5.0

# Radius bumi (km) untuk rumus Haversine, sama dengan notebook TK1.
R_BUMI_KM = 6371.0088

# Kotak wilayah layanan Jabodetabek–Bandung (filter koordinat).
LAT_MIN, LAT_MAX = -7.3, -5.9
LON_MIN, LON_MAX = 106.3, 108.0

RADIUS_DEFAULT_KM = 5.0

# Pemisah daftar kategori di CSV dan di kolom restoran.kategori.
PEMISAH_KATEGORI = "|"
