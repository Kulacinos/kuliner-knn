"""Uji mesin rekomendasi: filter, bobot, urutan, kasus tepi, dan replikasi TK1."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from kuliner.config import BOBOT_DEFAULT, PATH_BERSIH
from kuliner.db import buat_mesin, muat_dari_csv
from kuliner.recommender import (
    BOBOT_JARAK_SAJA,
    jaccard,
    muat_katalog,
    normalisasi_bobot,
    rekomendasi,
    rekomendasi_dasar,
    titik_pusat,
    bersihkan_cache,
)


# --- data sintetis kecil (tiga merchant di sekitar khatulistiwa) ---

def _sintetis() -> pd.DataFrame:
    # 1 derajat bujur di lintang 0 ≈ 111,2 km. Kita pakai lon 0.01 ≈ 1,11 km.
    return pd.DataFrame(
        {
            "id": ["A", "B", "C", "D", "E"],
            "nama": ["Dekat Bakmie", "Jauh Bakmie", "Dekat Sushi", "Murah belum dinilai", "Mahal rating rendah"],
            "kota": ["X"] * 5,
            "kecamatan": ["Y"] * 5,
            "latitude": [0.0, 0.0, 0.0, 0.0, 0.0],
            "longitude": [0.01, 0.03, 0.01, 0.012, 0.015],
            "price_level": [2, 2, 2, 1, 4],
            "rating": [4.8, 4.8, 4.8, np.nan, 3.0],
            "sudah_dinilai": [True, True, True, False, True],
            "kategori": ["Bakmie", "Bakmie", "Jepang", "Bakmie", "Bakmie"],
        }
    )


def test_bobot_default_jumlahnya_satu():
    assert sum(BOBOT_DEFAULT.values()) == pytest.approx(1.0)
    norm = normalisasi_bobot()
    assert sum(norm.values()) == pytest.approx(1.0)
    assert norm["lokasi"] == pytest.approx(0.35)
    assert norm["kategori"] == pytest.approx(0.30)
    assert norm["rating"] == pytest.approx(0.20)
    assert norm["harga"] == pytest.approx(0.15)


def test_bobot_tanpa_kategori_dinormalisasi_ulang():
    norm = normalisasi_bobot(pakai_kategori=False)
    assert norm["kategori"] == 0.0
    assert sum(norm.values()) == pytest.approx(1.0)
    # Sisa 0,70 dibagi proporsional.
    assert norm["lokasi"] == pytest.approx(0.35 / 0.70)
    assert norm["rating"] == pytest.approx(0.20 / 0.70)
    assert norm["harga"] == pytest.approx(0.15 / 0.70)


def test_jaccard_kasus_dasar():
    assert jaccard(["Bakmie"], ["Bakmie"]) == 1.0
    assert jaccard(["Bakmie"], ["Jepang"]) == 0.0
    assert jaccard(["Bakmie", "Kopi"], ["Bakmie"]) == pytest.approx(0.5)
    assert jaccard([], []) == 0.0


def test_filter_anggaran_dan_radius():
    df = _sintetis()
    # Radius kecil: lon 0.01 masuk, 0.03 (≈ 3,3 km) keluar jika R = 2 km.
    hasil = rekomendasi(0.0, 0.0, radius_km=2.0, budget_maks=4, rating_min=0, data=df, k=10)
    assert set(hasil["id"]) <= {"A", "C", "D", "E"}
    assert "B" not in set(hasil["id"])
    murah = rekomendasi(0.0, 0.0, radius_km=5.0, budget_maks=2, rating_min=0, data=df, k=10)
    assert "E" not in set(murah["id"])  # price_level 4
    assert set(murah["id"]) == {"A", "B", "C", "D"}


def test_rating_minimum_mengeluarkan_yang_belum_dinilai():
    df = _sintetis()
    # Perilaku TK1: rating_min > 0 → belum dinilai dan rating rendah keluar.
    hasil = rekomendasi(0.0, 0.0, radius_km=5.0, budget_maks=4, rating_min=4.5, data=df, k=10)
    assert set(hasil["id"]) == {"A", "B", "C"}
    # Tanpa batas rating, D (belum dinilai) ikut.
    semua = rekomendasi(0.0, 0.0, radius_km=5.0, budget_maks=4, rating_min=0, data=df, k=10)
    assert "D" in set(semua["id"])
    # Paksa keluarkan yang belum dinilai.
    ketat = rekomendasi(
        0.0, 0.0, radius_km=5.0, budget_maks=4, rating_min=0,
        sertakan_belum_dinilai=False, data=df, k=10,
    )
    assert "D" not in set(ketat["id"])
    # Paksa sertakan meski ada rating minimum.
    longgar = rekomendasi(
        0.0, 0.0, radius_km=5.0, budget_maks=4, rating_min=4.5,
        sertakan_belum_dinilai=True, data=df, k=10,
    )
    assert "D" in set(longgar["id"])
    assert "E" not in set(longgar["id"])


def test_kategori_kosong_tidak_memengaruhi_skor():
    df = _sintetis()
    hasil = rekomendasi(
        0.0, 0.0, radius_km=5.0, budget_maks=4, rating_min=0,
        kategori_pilihan=[], data=df, k=10,
    )
    assert (hasil["f_kategori"] == 0).all()
    # A dan C sama jarak dan harga-rating; tanpa kategori, skor harus sama.
    ac = hasil[hasil["id"].isin(["A", "C"])]
    assert ac["skor"].nunique() == 1


def test_kategori_mengubah_urutan():
    df = _sintetis()
    hasil = rekomendasi(
        0.0, 0.0, radius_km=5.0, budget_maks=2, rating_min=4.5,
        kategori_pilihan=["Bakmie"], data=df, k=10,
    )
    # A (Bakmie, dekat) harus di atas C (Jepang, dekat).
    assert list(hasil["id"])[0] == "A"
    assert hasil.loc[hasil["id"] == "A", "f_kategori"].iloc[0] == pytest.approx(0.0)
    assert hasil.loc[hasil["id"] == "C", "f_kategori"].iloc[0] == pytest.approx(1.0)


def test_urutan_skor_menaik_dan_peringkat():
    df = _sintetis()
    hasil = rekomendasi(0.0, 0.0, radius_km=5.0, budget_maks=4, data=df, k=10)
    assert list(hasil["peringkat"]) == list(range(1, len(hasil) + 1))
    assert hasil["skor"].is_monotonic_increasing
    assert set(hasil.columns) >= {"jarak_km", "f_lokasi", "f_kategori", "f_rating", "f_harga", "skor", "peringkat"}


def test_tie_break_deterministik():
    # Dua merchant identik kecuali id; urutan harus selalu id yang lebih awal.
    df = pd.DataFrame(
        {
            "id": ["b", "a"],
            "nama": ["B", "A"],
            "latitude": [0.0, 0.0],
            "longitude": [0.01, 0.01],
            "price_level": [1, 1],
            "rating": [5.0, 5.0],
            "sudah_dinilai": [True, True],
            "kategori": ["Bakmie", "Bakmie"],
        }
    )
    h1 = rekomendasi(0.0, 0.0, radius_km=5, data=df, k=2)
    h2 = rekomendasi(0.0, 0.0, radius_km=5, data=df, k=2)
    assert list(h1["id"]) == list(h2["id"]) == ["a", "b"]
    assert h1["skor"].iloc[0] == pytest.approx(h1["skor"].iloc[1])


def test_hasil_kosong_dan_k_lebih_besar():
    df = _sintetis()
    kosong = rekomendasi(
        0.0, 0.0, radius_km=0.01, budget_maks=1, rating_min=4.9,
        kategori_pilihan=["India"], data=df, k=10,
    )
    assert kosong.empty
    assert "skor" in kosong.columns
    # Hanya 5 baris, k=20 → semua yang lolos filter.
    semua = rekomendasi(0.0, 0.0, radius_km=10, budget_maks=4, data=df, k=20)
    assert len(semua) == 5


def test_k_tidak_valid():
    with pytest.raises(ValueError):
        rekomendasi(0.0, 0.0, k=0, data=_sintetis())


def test_normalisasi_harga_dan_lokasi():
    df = _sintetis()
    hasil = rekomendasi(0.0, 0.0, radius_km=5.0, budget_maks=4, data=df, k=10)
    # price_level 1 → (1-1)/3 = 0; level 4 → 1; level 2 → 1/3.
    baris_d = hasil.set_index("id")
    assert baris_d.loc["D", "f_harga"] == pytest.approx(0.0)
    assert baris_d.loc["E", "f_harga"] == pytest.approx(1.0)
    assert baris_d.loc["A", "f_harga"] == pytest.approx(1 / 3)
    assert (baris_d["f_lokasi"] == baris_d["jarak_km"] / 5.0).all()
    # Belum dinilai: f_rating = 1.
    assert baris_d.loc["D", "f_rating"] == pytest.approx(1.0)


def test_baseline_jarak_mengurutkan_menurut_jarak():
    df = _sintetis()
    dasar = rekomendasi_dasar(0.0, 0.0, radius_km=5, budget_maks=2, rating_min=4.5, data=df, acuan="jarak")
    # Setelah filter (tanpa E dan D): A dan C sama jarak, lalu B.
    assert dasar["jarak_km"].is_monotonic_increasing
    assert set(dasar["id"]) == {"A", "B", "C"}


# --- replikasi contoh Beji pada laporan TK1 ---

@pytest.fixture(scope="module")
def katalog_bersih():
    bersihkan_cache()
    return muat_katalog(sumber="csv", path_csv=PATH_BERSIH, ulang=True)


def test_titik_pusat_beji(katalog_bersih):
    lat, lon, n = titik_pusat("Kota Depok", "Beji", data=katalog_bersih)
    assert n == 130
    assert lat == pytest.approx(-6.374424323559896, rel=1e-9)
    assert lon == pytest.approx(106.82704588955647, rel=1e-9)


def test_replikasi_filter_dan_peringkat_beji(katalog_bersih):
    lat, lon, _ = titik_pusat("Kota Depok", "Beji", data=katalog_bersih)
    # Jumlah dalam radius 5 km, sebelum filter budget/rating.
    dari_semua = rekomendasi(
        lat, lon, radius_km=5, budget_maks=4, rating_min=0, data=katalog_bersih, k=10_000,
    )
    assert len(dari_semua) == 423
    hasil = rekomendasi(
        lat, lon, radius_km=5, budget_maks=2, rating_min=4.5,
        kategori_pilihan=["Bakmie"], k=10, data=katalog_bersih,
    )
    n_filter = rekomendasi(
        lat, lon, radius_km=5, budget_maks=2, rating_min=4.5,
        kategori_pilihan=["Bakmie"], k=10_000, data=katalog_bersih,
    )
    assert len(n_filter) == 186
    assert list(hasil["nama"]) == [
        "Bakmi Roxy, Depok",
        "Mie Ayam Bangka Koko, Kuliner Ceria",
        "Seblak Seuhah Peed Mamah Ebot, Beji",
        "Mie Aceh Jambo, Moch Kahfi 2",
        "Mie Gacoan Depok, Margonda",
        "Mie Ayam Purwodadi 17, Sukmajaya",
        "Laila Alkatiri Nasi Kuning Nusantara, Cimanggis",
        "Tegato, Pancoran Mas",
        "Warunk Upnormal, Margonda",
        "Ayam Bakar Bang Jali, Pd. Duta Raya",
    ]
    # Skor (D) dan jarak contoh baris pertama, sesuai notebook TK1.
    assert hasil.iloc[0]["skor"] == pytest.approx(0.2349, abs=5e-5)
    assert hasil.iloc[0]["jarak_km"] == pytest.approx(1.6041, abs=5e-5)
    assert hasil.iloc[0]["f_kategori"] == pytest.approx(0.0)
    assert hasil.iloc[2]["f_kategori"] == pytest.approx(0.5)


def test_replikasi_baseline_jarak_beji(katalog_bersih):
    lat, lon, _ = titik_pusat("Kota Depok", "Beji", data=katalog_bersih)
    dasar = rekomendasi_dasar(
        lat, lon, radius_km=5, budget_maks=2, rating_min=4.5,
        kategori_pilihan=["Bakmie"], k=10, acuan="jarak", data=katalog_bersih,
    )
    assert list(dasar["nama"]) == [
        "Pempek Lapan Duobelas, Beji",
        "Bebek Goreng H. Slamet, Margonda",
        "Gado Gado Ibu Siti, Beji",
        "Simpang Raya, Depok",
        "Roti Bakar Eddy, Margonda",
        "Burger King, Margo City",
        "Makaroni Ngehe, Echo Depok",
        "Michelle Bakery, Margonda",
        "Ayam Keprabon Express, Margonda",
        "Ayam Geprek Gold Chick, Depok",
    ]
    # Baseline jarak-saja TK1: tidak ada Bakmie di 10 besar (hanya jarak).
    assert all("Bakmie" not in str(x).split("|") for x in dasar["kategori"])
    # Pilihan kategori tidak mengubah urutan karena bobot kategori = 0.
    tanpa = rekomendasi_dasar(
        lat, lon, radius_km=5, budget_maks=2, rating_min=4.5,
        kategori_pilihan=None, k=10, acuan="jarak", data=katalog_bersih,
    )
    assert list(tanpa["nama"]) == list(dasar["nama"])


def test_kasus_kosong_india_beji(katalog_bersih):
    lat, lon, _ = titik_pusat("Kota Depok", "Beji", data=katalog_bersih)
    kosong = rekomendasi(
        lat, lon, radius_km=1, budget_maks=1, rating_min=4.9,
        kategori_pilihan=["India"], data=katalog_bersih, k=10,
    )
    assert kosong.empty


def test_muat_dari_csv_dan_dari_db(tmp_path, katalog_bersih):
    bersihkan_cache()
    dari_csv = muat_katalog(sumber="csv", path_csv=PATH_BERSIH, ulang=True)
    assert len(dari_csv) == 10261
    path_db = tmp_path / "kuliner.db"
    mesin = buat_mesin(path_db=path_db)
    muat_dari_csv(path_csv=PATH_BERSIH, mesin=mesin, ulang=True)
    bersihkan_cache()
    dari_db = muat_katalog(sumber="db", path_db=path_db, ulang=True)
    assert len(dari_db) == 10261
    assert set(dari_db["id"]) == set(dari_csv["id"])
    # Cache: pemanggilan kedua tidak wajib baca ulang (objek yang sama).
    lagi = muat_katalog()
    assert lagi is dari_db
