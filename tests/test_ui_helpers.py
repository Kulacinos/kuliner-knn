"""Uji pembantu antarmuka: label, validasi, pencarian, dan peta."""

from __future__ import annotations

import folium
import pandas as pd
import pytest

from kuliner.config import LAT_MAX, LAT_MIN, LON_MAX, LON_MIN, PATH_BERSIH
from kuliner.recommender import muat_katalog, titik_pusat
from kuliner.ui_helpers import (
    LABEL_HARGA,
    bangun_peta,
    cari_nama,
    daftar_kategori,
    daftar_kecamatan,
    daftar_kota,
    dalam_wilayah,
    format_angka,
    jalankan_pencarian,
    label_harga,
    label_lokasi,
    pesan_di_luar_wilayah,
    pesan_hasil_kosong,
    pesan_lokasi_kosong,
    ringkasan_preferensi,
    tabel_tampil,
    tautan_google_maps,
    teks_harga,
    teks_rating,
    teks_uraian,
    uraian_komponen,
)


@pytest.fixture(scope="module")
def data():
    return muat_katalog(sumber="csv", path_csv=PATH_BERSIH, ulang=True)


def test_format_angka_koma_desimal():
    assert format_angka(1.6041, 2) == "1,60"
    assert format_angka(0.2349, 3) == "0,235"


def test_label_harga_sesuai_tk1():
    assert label_harga(1) == "< Rp16 rb"
    assert label_harga(2) == "Rp16–40 rb"
    assert label_harga(3) == "Rp40–100 rb"
    assert label_harga(4) == "> Rp100 rb"
    assert "Level 2" in teks_harga(2)
    assert "Rp16–40" in teks_harga(2)
    assert set(LABEL_HARGA) == {1, 2, 3, 4}


def test_teks_rating_belum_dinilai():
    assert teks_rating(4.7, True) == "4,7"
    assert teks_rating(None, False) == "Belum dinilai"
    assert teks_rating(float("nan"), True) == "Belum dinilai"
    assert teks_rating(0, None) == "Belum dinilai"


def test_wilayah_layanan():
    # Monas dan Beji masuk; Medan dan (0,0) tidak.
    assert dalam_wilayah(-6.175392, 106.827153)
    assert dalam_wilayah(-6.37442, 106.82705)
    assert not dalam_wilayah(3.5952, 98.6722)
    assert not dalam_wilayah(0.0, 0.0)
    assert not dalam_wilayah(LAT_MAX + 0.1, 106.8)
    assert dalam_wilayah(LAT_MIN, LON_MIN)
    assert dalam_wilayah(LAT_MAX, LON_MAX)


def test_pesan_validasi_dan_kosong():
    assert "belum ditentukan" in pesan_lokasi_kosong().lower()
    assert "Jabodetabek" in pesan_di_luar_wilayah()
    teks = pesan_hasil_kosong(radius_km=1)
    assert "Tidak ada tempat makan yang memenuhi semua batas" in teks
    assert "perluas radius" in teks


def test_tautan_google_maps():
    url = tautan_google_maps(-6.388833, 106.826333)
    assert url.startswith("https://www.google.com/maps/search/?api=1&query=")
    assert "-6.388833,106.826333" in url


def test_daftar_preset(data):
    kota = daftar_kota(data)
    assert "Kota Depok" in kota
    assert "Kota Bandung" in kota
    assert len(kota) == 18
    kec = daftar_kecamatan(data, "Kota Depok")
    assert "Beji" in kec
    # Dropdown TK1: kecamatan dengan < 5 merchant tidak muncul,
    # kecuali suatu kota tidak punya yang lolos ambang.
    hitung = data[data["kota"] == "Kota Depok"].groupby("kecamatan").size()
    for nama in kec:
        assert hitung.loc[nama] >= 5
    kat = daftar_kategori(data)
    assert len(kat) == 21
    assert "Bakmie" in kat
    assert kat[0] == "Aneka nasi"  # paling sering pada EDA TK1


def test_label_dan_ringkasan():
    assert label_lokasi("Kota Depok", "Beji") == "Beji, Kota Depok"
    chip = ringkasan_preferensi("Beji, Kota Depok", 5, 2, 4.5, ["Bakmie"])
    assert "Beji, Kota Depok" in chip
    assert any("5 km" in c for c in chip)
    assert any("Level 2" in c for c in chip)
    assert any("4,5" in c for c in chip)
    assert "Bakmie" in chip


def test_jalankan_pencarian_validasi(data):
    kosong = jalankan_pencarian(data, None, None)
    assert kosong["ok"] is False
    assert "belum ditentukan" in kosong["pesan"].lower()
    luar = jalankan_pencarian(data, 0.0, 0.0, radius_km=5)
    assert luar["ok"] is False
    assert "luar wilayah" in luar["pesan"].lower()


def test_jalankan_pencarian_beji(data):
    lat, lon, n = titik_pusat("Kota Depok", "Beji", data=data)
    assert n == 130
    meta = jalankan_pencarian(
        data, lat, lon, radius_km=5, budget_maks=2, rating_min=4.5,
        kategori_pilihan=["Bakmie"], k=10,
    )
    assert meta["ok"] is True
    assert meta["n_dalam_radius"] == 423
    assert meta["n_lolos_filter"] == 186
    assert len(meta["hasil"]) == 10
    assert meta["hasil"].iloc[0]["nama"] == "Bakmi Roxy, Depok"
    assert meta["detik"] < 2.0
    tabel = tabel_tampil(meta["hasil"])
    assert list(tabel.columns) == [
        "peringkat", "nama", "kategori", "rating", "harga", "jarak_km", "skor",
    ]
    assert tabel.iloc[0]["nama"] == "Bakmi Roxy, Depok"
    uraian = uraian_komponen(meta["hasil"].iloc[0], meta["bobot"])
    assert set(uraian["Komponen"]) >= {
        "Lokasi d/R",
        "Kategori 1 − Jaccard",
        "Rating (selisih ke terbaik)",
        "Harga (p')",
    }
    teks = teks_uraian(meta["hasil"].iloc[0], meta["bobot"])
    assert "0,235" in teks or "Bakmi Roxy" in teks
    assert "skor" in teks.lower() or "D" in teks


def test_jalankan_pencarian_kosong_india(data):
    lat, lon, _ = titik_pusat("Kota Depok", "Beji", data=data)
    meta = jalankan_pencarian(
        data, lat, lon, radius_km=1, budget_maks=1, rating_min=4.9,
        kategori_pilihan=["India"], k=10,
    )
    assert meta["ok"] is True
    assert meta["hasil"].empty
    assert "Tidak ada tempat makan yang memenuhi semua batas" in meta["pesan"]


def test_bangun_peta_memuat_penanda(data):
    lat, lon, _ = titik_pusat("Kota Depok", "Beji", data=data)
    meta = jalankan_pencarian(
        data, lat, lon, radius_km=5, budget_maks=2, rating_min=4.5,
        kategori_pilihan=["Bakmie"], k=10,
    )
    peta = bangun_peta(lat, lon, 5, meta["hasil"], judul_pengguna="Beji, Kota Depok")
    assert isinstance(peta, folium.Map)
    html = peta.get_root().render()
    assert "Bakmi Roxy" in html
    assert "Beji, Kota Depok" in html
    assert "#C62828" in html  # lingkaran radius
    assert "dashArray" in html


def test_cari_nama_gacoan(data):
    halaman, total = cari_nama(data, "gacoan", halaman=1, per_halaman=8)
    assert total >= 1
    assert len(halaman) <= 8
    assert halaman["nama"].str.lower().str.contains("gacoan").all()
    kosong, n0 = cari_nama(data, "", halaman=1)
    assert n0 == 0
    tidak_ada, n1 = cari_nama(data, "xyzbukanmakanan123")
    assert n1 == 0
