"""Pembersihan dataset GoFood, mereplikasi langkah pada notebook TK1.

Dari 10.372 baris mentah dihasilkan 10.261 baris bersih:

* 1 duplikat nama + koordinat dibuang;
* 110 merchant dengan ``price_level`` 0 dibuang (harga tidak tersedia);
* 521 merchant dengan rating 0 **tetap disimpan**, rating diubah menjadi
  kosong (NaN) dan ``sudah_dinilai`` bernilai False — rating 0 artinya
  *belum dinilai*, bukan rating buruk;
* 64 merchant tanpa kategori tetap disimpan (``n_kategori`` = 0).

Label kota/kecamatan dirapikan karena hasil *reverse geocoding* pada
data mentah tidak konsisten. Perhitungan jarak tetap memakai koordinat.
"""

from __future__ import annotations

import ast
from typing import Any

import numpy as np
import pandas as pd

from kuliner.config import (
    LAT_MAX,
    LAT_MIN,
    LON_MAX,
    LON_MIN,
    P_MAX,
    P_MIN,
    PATH_MENTAH,
    PEMISAH_KATEGORI,
)

# Provinsi yang dipakai sebagai jangkar saat membedah areaName.
_PROVINSI = (
    "Daerah Khusus Ibukota Jakarta",
    "Jawa Barat",
    "Banten",
)

# Label mentah yang sebenarnya merujuk ke Kota Depok.
_DEPOK = {
    "Depok",
    "Beji",
    "Pancoran Mas",
    "Cinere",
    "Limo",
    "Sawangan",
    "Cipayung",
    "Kecamatan Tapos",
    "Tapos",
    "Kelurahan Abadijaya",
    "Sukmajaya",
    "Cimanggis",
    "Bojongsari",
    "Cilodong",
}

# Kecamatan di Kota Bogor (bukan Kabupaten Bogor).
_KOTA_BOGOR = {
    "Bogor Tengah",
    "Bogor Timur",
    "Bogor Utara",
    "Bogor Barat",
    "Bogor Selatan",
    "Tanah Sareal",
}

# Kecamatan di Kota Tangerang Selatan; kadang muncul di posisi "kota".
_TANGSEL = {
    "Serpong Utara",
    "Pamulang",
    "Pondok Aren",
    "Ciputat Timur",
    "Serpong",
    "Ciputat",
    "Setu",
    "Pisangan",
}

_GANTI_KECAMATAN_DEPOK = {
    "Kecamatan Tapos": "Tapos",
    "Kelurahan Abadijaya": "Sukmajaya",
}


def parse_area(area: Any) -> tuple[str | None, str | None]:
    """Ambil pasangan (kota, kecamatan) mentah dari ``areaName``.

    ``areaName`` adalah hasil *reverse geocoding* yang dipisah koma.
    Kota dan kecamatan diambil sebagai dua ruas di kiri nama provinsi.
    """
    bagian = [x.strip() for x in str(area).split(",")]
    for i, teks in enumerate(bagian):
        if teks in _PROVINSI:
            kota = bagian[i - 1] if i >= 1 else None
            kecamatan = bagian[i - 2] if i >= 2 else None
            return kota, kecamatan
    return None, None


def rapihkan_wilayah(kota_mentah: Any, kecamatan_mentah: Any) -> tuple[str, str | None]:
    """Rapikan label kota dan kecamatan sesuai aturan pemetaan TK1."""
    k, c = kota_mentah, kecamatan_mentah
    if not isinstance(k, str):
        return "Jakarta Selatan", "Jagakarsa"
    if k.startswith("Jakarta "):
        return k, c
    if k == "Cilandak Timur":
        return "Jakarta Selatan", "Pasar Minggu"
    if k in ("Bogor", "Depok", "Jalan Cemara VI"):
        if k == "Jalan Cemara VI":
            return "Kota Depok", "Cinere"
        if c in _DEPOK or k == "Depok":
            c2 = _GANTI_KECAMATAN_DEPOK.get(c, c)
            return "Kota Depok", ("Beji" if k == "Depok" else c2)
        if c in _KOTA_BOGOR:
            return "Kota Bogor", c
        return "Kabupaten Bogor", c
    if k == "Tangerang":
        return "Kota Tangerang", c
    if k in _TANGSEL:
        return "Kota Tangerang Selatan", ("Ciputat Timur" if k == "Pisangan" else k)
    if k.startswith("Kel. "):
        return "Kota Bandung", c
    if k == "Sumedang":
        return "Kabupaten Sumedang", "Jatinangor"
    return k, c


def pecah_kategori(teks: Any) -> list[str]:
    """Ubah kolom kategori (teks dipisah ``|``) menjadi daftar nama."""
    if teks is None or (isinstance(teks, float) and np.isnan(teks)):
        return []
    teks = str(teks).strip()
    if not teks:
        return []
    return [x for x in teks.split(PEMISAH_KATEGORI) if x]


def _kategori_ke_teks(daftar: list[str]) -> float | str:
    if not daftar:
        return np.nan
    return PEMISAH_KATEGORI.join(daftar)


def bersihkan(mentah: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, int]]:
    """Bersihkan DataFrame mentah menjadi skema ``gofood_clean.csv``.

    Parameter
    ---------
    mentah:
        DataFrame hasil pembacaan CSV mentah (26 kolom asli).
        Objek ini tidak diubah.

    Keluaran
    --------
    df:
        16 kolom yang sama dengan ``data/processed/gofood_clean.csv``.
    log:
        Ringkasan jumlah baris pada setiap langkah pembersihan.
    """
    raw = mentah.copy()

    # Rating disimpan sebagai string kamus, misalnya {'average': 4.8, 'total': 0}.
    isi_rating = raw["ratings"].apply(ast.literal_eval)
    raw["rating"] = isi_rating.apply(lambda x: x.get("average"))

    # Hanya tag dengan taxonomy = 2 yang merupakan kategori kuliner.
    isi_tag = raw["tags"].apply(ast.literal_eval)
    raw["kategori"] = isi_tag.apply(
        lambda L: sorted({t["displayName"] for t in L if t.get("taxonomy") == 2})
    )

    wilayah = raw["areaName"].apply(parse_area)
    raw["kota_raw"] = [x[0] for x in wilayah]
    raw["kec_raw"] = [x[1] for x in wilayah]
    rapih = [
        rapihkan_wilayah(k, c) for k, c in zip(raw["kota_raw"], raw["kec_raw"])
    ]
    raw["kota"] = [x[0] for x in rapih]
    raw["kecamatan"] = [x[1] for x in rapih]
    # serviceArea.id = 2 adalah Bandung Raya; selain itu Jabodetabek.
    raw["region"] = np.where(raw["serviceArea.id"] == 2, "Bandung Raya", "Jabodetabek")

    df = pd.DataFrame(
        {
            "id": raw["uid"],
            "nama": raw["displayName"],
            "brand": raw["brand.displayName"],
            "alamat_area": raw["areaName"],
            "region": raw["region"],
            "kota": raw["kota"],
            "kecamatan": raw["kecamatan"],
            "latitude": raw["location.latitude"],
            "longitude": raw["location.longitude"],
            "price_level": raw["priceLevel"],
            "rating": raw["rating"],
            "kategori": raw["kategori"],
        }
    )

    log: dict[str, int] = {}
    log["awal"] = int(len(df))

    inti = ["id", "nama", "latitude", "longitude", "price_level", "rating"]
    log["missing_core"] = int(df[inti].isna().sum().sum())

    log["dup_id"] = int(df.duplicated("id").sum())
    log["dup_nama_koord"] = int(df.duplicated(["nama", "latitude", "longitude"]).sum())
    df = df.drop_duplicates("id").drop_duplicates(["nama", "latitude", "longitude"])

    nol = (df.latitude == 0) & (df.longitude == 0)
    dalam_kotak = df.latitude.between(LAT_MIN, LAT_MAX) & df.longitude.between(
        LON_MIN, LON_MAX
    )
    log["koord_nol"] = int(nol.sum())
    log["koord_luar_bbox"] = int((~dalam_kotak).sum())
    df = df[~nol & dalam_kotak]

    log["price_level_0"] = int((df.price_level == 0).sum())
    df = df[df.price_level.between(P_MIN, P_MAX)]

    # Rating 0 = belum dinilai: baris dipertahankan, nilai rating dikosongkan.
    df["sudah_dinilai"] = df.rating > 0
    log["rating_0"] = int((~df["sudah_dinilai"]).sum())
    df.loc[~df["sudah_dinilai"], "rating"] = np.nan

    df["n_kategori"] = df.kategori.apply(len)
    log["kategori_kosong"] = int((df.n_kategori == 0).sum())
    log["akhir"] = int(len(df))
    df = df.reset_index(drop=True)

    dinilai = df[df.sudah_dinilai]
    r_min = float(dinilai.rating.min())
    r_max = float(dinilai.rating.max())
    df["price_norm"] = (df.price_level - P_MIN) / (P_MAX - P_MIN)
    df["rating_gap"] = ((r_max - df.rating) / (r_max - r_min)).fillna(1.0)

    keluar = df.drop(columns=["kategori"]).assign(
        kategori=df.kategori.apply(_kategori_ke_teks)
    )
    # Urutan kolom diseragamkan dengan CSV bersih TK1.
    urutan = [
        "id",
        "nama",
        "brand",
        "alamat_area",
        "region",
        "kota",
        "kecamatan",
        "latitude",
        "longitude",
        "price_level",
        "rating",
        "sudah_dinilai",
        "n_kategori",
        "price_norm",
        "rating_gap",
        "kategori",
    ]
    return keluar[urutan], log


def baca_mentah(path=None) -> pd.DataFrame:
    """Baca CSV mentah GoFood."""
    return pd.read_csv(path if path is not None else PATH_MENTAH)


def bersihkan_berkas(path_mentah=None) -> tuple[pd.DataFrame, dict[str, int]]:
    """Baca CSV mentah lalu bersihkan."""
    return bersihkan(baca_mentah(path_mentah))
