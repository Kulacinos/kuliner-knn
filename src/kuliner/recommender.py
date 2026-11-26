"""Mesin rekomendasi kuliner: filter keras + KNN jarak berbobot.

Alur (sama dengan prototipe TK1):

1. Filter keras: radius Haversine, anggaran (``price_level`` ≤ budget),
   dan rating minimum. Rating 0 / belum dinilai bukan rating buruk —
   baris itu hanya dikeluarkan jika pengguna memasang rating minimum
   (atau jika ``sertakan_belum_dinilai=False``).
2. Setiap kandidat diubah menjadi vektor fitur 0–1 (0 = ideal):
   lokasi ``d/R``, kategori ``1 − Jaccard``, rating (selisih satu arah
   terhadap rating terbaik), harga ``(p − 1)/3``.
3. Jarak berbobot ke titik ideal (0, 0, 0, 0):
   ``skor = sqrt(sum_i w_i * f_i^2)`` dengan ``w`` dinormalisasi
   agar jumlahnya 1. Ini sama dengan Euclidean KNN pada vektor
   ``f * sqrt(w)`` seperti di notebook TK1.
4. Ambil ``k`` skor terkecil. Jika skor seri, diurutkan menurut
   ``jarak_km`` lalu ``id`` (deterministik).

Jika pengguna tidak memilih kategori, bobot kategori di-nol-kan lalu
bobot sisanya dinormalisasi ulang (perilaku TK1).
"""

from __future__ import annotations

from typing import Iterable, Literal, Sequence

import numpy as np
import pandas as pd

from kuliner.config import (
    BOBOT_DEFAULT,
    P_MAX,
    P_MIN,
    PATH_BERSIH,
    PATH_DB,
    R_MAX_DEFAULT,
    R_MIN_DEFAULT,
    RADIUS_DEFAULT_KM,
)
from kuliner.geo import saring_radius
from kuliner.preprocessing import pecah_kategori

# Nama kolom fitur (0 = ideal) dan urutan yang dipakai saat menghitung skor.
KUNCI_FITUR = ("lokasi", "kategori", "rating", "harga")
KOLOM_FITUR = {k: f"f_{k}" for k in KUNCI_FITUR}
KOLOM_SKOR = ["jarak_km", "f_lokasi", "f_kategori", "f_rating", "f_harga", "skor", "peringkat"]

# Baseline untuk perbandingan di bagian 4 (uji Wilcoxon).
BOBOT_JARAK_SAJA = {"lokasi": 1.0, "kategori": 0.0, "rating": 0.0, "harga": 0.0}
BOBOT_RATING_SAJA = {"lokasi": 0.0, "kategori": 0.0, "rating": 1.0, "harga": 0.0}

# Cache katalog di memori (satu proses).
_KATALOG: pd.DataFrame | None = None


def jaccard(a: Iterable[str], b: Iterable[str]) -> float:
    """Koefisien Jaccard dua himpunan. Jika keduanya kosong, bernilai 0."""
    sa, sb = set(a), set(b)
    gabungan = sa | sb
    if not gabungan:
        return 0.0
    return len(sa & sb) / len(gabungan)


def normalisasi_bobot(
    bobot: dict[str, float] | None = None,
    pakai_kategori: bool = True,
) -> dict[str, float]:
    """Salin bobot, nol-kan kategori jika tidak dipakai, lalu normalkan ke jumlah 1."""
    ww = dict(BOBOT_DEFAULT if bobot is None else bobot)
    for kunci in KUNCI_FITUR:
        ww.setdefault(kunci, 0.0)
        ww[kunci] = float(ww[kunci])
    if not pakai_kategori:
        ww["kategori"] = 0.0
    total = sum(ww[k] for k in KUNCI_FITUR)
    if total <= 0:
        raise ValueError("Jumlah bobot harus positif (setelah kategori dinolkan jika perlu).")
    return {k: ww[k] / total for k in KUNCI_FITUR}


def _siapkan(data: pd.DataFrame) -> pd.DataFrame:
    """Salin DataFrame dan lengkapi kolom yang dibutuhkan mesin."""
    df = data.copy()
    wajib = {"id", "latitude", "longitude", "price_level"}
    kurang = wajib - set(df.columns)
    if kurang:
        raise ValueError(f"Data tidak lengkap, kolom hilang: {sorted(kurang)}")

    if "sudah_dinilai" not in df.columns:
        if "rating" in df.columns:
            df["sudah_dinilai"] = df["rating"].notna() & (df["rating"] > 0)
        else:
            df["sudah_dinilai"] = False
    df["sudah_dinilai"] = df["sudah_dinilai"].astype(bool)

    if "price_norm" not in df.columns:
        df["price_norm"] = (df["price_level"].astype(float) - P_MIN) / (P_MAX - P_MIN)

    if "rating_gap" not in df.columns:
        if "rating" in df.columns:
            df["rating_gap"] = (
                (R_MAX_DEFAULT - df["rating"].astype(float))
                / (R_MAX_DEFAULT - R_MIN_DEFAULT)
            ).where(df["sudah_dinilai"], 1.0)
        else:
            df["rating_gap"] = 1.0
        df["rating_gap"] = df["rating_gap"].fillna(1.0)

    if "kategori" not in df.columns:
        df["kategori"] = np.nan
    return df.reset_index(drop=True)


def muat_katalog(
    path_db=None,
    path_csv=None,
    ulang: bool = False,
    sumber: Literal["auto", "db", "csv"] = "auto",
) -> pd.DataFrame:
    """Muat katalog merchant ke memori (cache).

    Urutan ``auto``: basis data SQLite jika berkasnya ada, kalau tidak
    jatuh ke CSV bersih. Berguna untuk uji tanpa membangun ``kuliner.db``.
    """
    global _KATALOG
    if _KATALOG is not None and not ulang and sumber == "auto" and path_db is None and path_csv is None:
        return _KATALOG

    path_db = PATH_DB if path_db is None else path_db
    path_csv = PATH_BERSIH if path_csv is None else path_csv

    df = None
    if sumber in ("auto", "db"):
        from pathlib import Path as _Path

        if _Path(path_db).is_file():
            from kuliner.db import baca_restoran

            df = baca_restoran(path_db=path_db)
            if df is None or len(df) == 0:
                df = None

    if df is None:
        if sumber == "db":
            raise FileNotFoundError(f"Basis data tidak ditemukan atau kosong: {path_db}")
        df = pd.read_csv(path_csv)

    _KATALOG = _siapkan(df)
    return _KATALOG


def bersihkan_cache() -> None:
    """Buang cache katalog (misalnya setelah basis data dibangun ulang)."""
    global _KATALOG
    _KATALOG = None


def _katalog(data: pd.DataFrame | None) -> pd.DataFrame:
    if data is not None:
        return _siapkan(data)
    return muat_katalog()


def _himpunan_kategori(nilai) -> set[str]:
    if isinstance(nilai, (set, list, tuple)):
        return {str(x) for x in nilai if str(x)}
    return set(pecah_kategori(nilai))


def _lolos_rating(
    df: pd.DataFrame,
    rating_min: float,
    sertakan_belum_dinilai: bool | None,
) -> pd.Series:
    """Filter rating minimum, dengan aturan 'belum dinilai' sesuai TK1.

    Default (``sertakan_belum_dinilai is None``): merchant belum dinilai
    ikut serta hanya jika ``rating_min`` tidak dipasang (≤ 0).
    """
    if sertakan_belum_dinilai is None:
        sertakan_belum_dinilai = rating_min <= 0
    dinilai = df["sudah_dinilai"] & df["rating"].notna()
    lolos_nilai = dinilai & (df["rating"] >= rating_min)
    if sertakan_belum_dinilai:
        return lolos_nilai | (~df["sudah_dinilai"])
    return lolos_nilai


def _kerangka_kosong(df: pd.DataFrame) -> pd.DataFrame:
    kolom = list(df.columns) + [k for k in KOLOM_SKOR if k not in df.columns]
    return pd.DataFrame(columns=kolom)


def rekomendasi(
    lat: float,
    lon: float,
    radius_km: float = RADIUS_DEFAULT_KM,
    budget_maks: int = P_MAX,
    rating_min: float = 0.0,
    kategori_pilihan: Sequence[str] | None = None,
    k: int = 10,
    bobot: dict[str, float] | None = None,
    sertakan_belum_dinilai: bool | None = None,
    data: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Kembalikan hingga ``k`` merchant terdekat menurut jarak berbobot.

    Parameter
    ---------
    lat, lon:
        Lokasi pengguna (derajat).
    radius_km:
        Filter keras jarak Haversine (inklusif).
    budget_maks:
        ``price_level`` maksimum yang diterima (1–4).
    rating_min:
        Rating minimum. Nilai ≤ 0 berarti tidak ada batas.
    kategori_pilihan:
        Daftar kategori yang diinginkan, misalnya ``["Bakmie"]``.
        Kosong atau ``None`` berarti kategori tidak dipakai di skor.
    k:
        Jumlah hasil (nearest-neighbour retrieval, bukan klasifikasi).
    bobot:
        Kamus ``lokasi/kategori/rating/harga``. Default 0,35 / 0,30 /
        0,20 / 0,15. Akan dinormalisasi.
    sertakan_belum_dinilai:
        ``None`` mengikuti TK1 (ikut jika tidak ada rating minimum).
        ``True`` selalu menyertakan yang belum dinilai.
        ``False`` selalu mengeluarkannya.
    data:
        Katalog alternatif (untuk uji). Default: cache dari DB/CSV.

    Keluaran memuat ``jarak_km``, ``f_lokasi``, ``f_kategori``,
    ``f_rating``, ``f_harga``, ``skor`` (lebih kecil lebih baik),
    dan ``peringkat``.
    """
    if k < 1:
        raise ValueError("k harus paling sedikit 1.")
    if radius_km < 0:
        raise ValueError("radius_km tidak boleh negatif.")

    katalog = _katalog(data)
    kandidat = saring_radius(lat, lon, katalog, radius_km)
    if kandidat.empty:
        return _kerangka_kosong(katalog)

    kandidat = kandidat.loc[kandidat["price_level"] <= budget_maks]
    if kandidat.empty:
        return _kerangka_kosong(katalog)

    if rating_min > 0 or sertakan_belum_dinilai is False:
        kandidat = kandidat.loc[_lolos_rating(kandidat, rating_min, sertakan_belum_dinilai)]
    elif sertakan_belum_dinilai is True:
        # Tetap terapkan batas hanya pada yang sudah dinilai, yang belum tetap ikut.
        kandidat = kandidat.loc[_lolos_rating(kandidat, rating_min, True)]
    if kandidat.empty:
        return _kerangka_kosong(katalog)

    pilihan = [str(x) for x in (kategori_pilihan or ()) if str(x).strip()]
    pakai_kategori = len(pilihan) > 0
    ww = normalisasi_bobot(bobot, pakai_kategori=pakai_kategori)

    keluar = kandidat.copy()
    keluar["f_lokasi"] = keluar["jarak_km"] / radius_km if radius_km > 0 else 0.0
    keluar["f_harga"] = keluar["price_norm"].astype(float)
    keluar["f_rating"] = keluar["rating_gap"].astype(float)
    if pakai_kategori:
        himpunan = [_himpunan_kategori(x) for x in keluar["kategori"]]
        keluar["f_kategori"] = [1.0 - jaccard(pilihan, h) for h in himpunan]
    else:
        keluar["f_kategori"] = 0.0

    # skor = sqrt(sum w_i * f_i^2), setara Euclidean pada f * sqrt(w).
    akar_w = np.sqrt([ww[k] for k in KUNCI_FITUR])
    F = keluar[[KOLOM_FITUR[k] for k in KUNCI_FITUR]].to_numpy(dtype=float)
    keluar["skor"] = np.sqrt(((F * akar_w) ** 2).sum(axis=1))

    # Tie-break deterministik: skor, lalu jarak, lalu id.
    keluar = keluar.sort_values(
        by=["skor", "jarak_km", "id"],
        kind="mergesort",
        ignore_index=True,
    )
    keluar = keluar.head(int(k)).copy()
    keluar["peringkat"] = np.arange(1, len(keluar) + 1)
    # Rapikan urutan kolom: identitas, filter, lalu skor.
    depan = [c for c in keluar.columns if c not in KOLOM_SKOR]
    return keluar[depan + KOLOM_SKOR]


def rekomendasi_dasar(
    lat: float,
    lon: float,
    radius_km: float = RADIUS_DEFAULT_KM,
    budget_maks: int = P_MAX,
    rating_min: float = 0.0,
    kategori_pilihan: Sequence[str] | None = None,
    k: int = 10,
    acuan: Literal["jarak", "rating"] = "jarak",
    sertakan_belum_dinilai: bool | None = None,
    data: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Baseline sederhana dengan filter yang sama, untuk perbandingan nanti.

    * ``acuan="jarak"``: hanya jarak Haversine (bobot lokasi = 1).
      Ini baseline "jarak saja" pada laporan TK1.
    * ``acuan="rating"``: hanya selisih rating (bobot rating = 1).
    """
    if acuan == "jarak":
        bobot = BOBOT_JARAK_SAJA
    elif acuan == "rating":
        bobot = BOBOT_RATING_SAJA
    else:
        raise ValueError("acuan harus 'jarak' atau 'rating'.")
    return rekomendasi(
        lat,
        lon,
        radius_km=radius_km,
        budget_maks=budget_maks,
        rating_min=rating_min,
        kategori_pilihan=kategori_pilihan,
        k=k,
        bobot=bobot,
        sertakan_belum_dinilai=sertakan_belum_dinilai,
        data=data,
    )


def titik_pusat(
    kota: str,
    kecamatan: str,
    data: pd.DataFrame | None = None,
) -> tuple[float, float, int]:
    """Centroid (rata-rata koordinat) merchant di suatu kota–kecamatan.

    Mengembalikan ``(latitude, longitude, jumlah_merchant)``.
    """
    df = _katalog(data)
    potong = df[(df["kota"] == kota) & (df["kecamatan"] == kecamatan)]
    if potong.empty:
        raise ValueError(f"Tidak ada merchant di {kota} – {kecamatan}.")
    return float(potong.latitude.mean()), float(potong.longitude.mean()), int(len(potong))
