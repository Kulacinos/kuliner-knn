"""Uji pembersihan data: hasil harus sama dengan CSV bersih TK1 (10.261 baris)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from kuliner.config import PATH_BERSIH, PATH_MENTAH
from kuliner.preprocessing import bersihkan, bersihkan_berkas, pecah_kategori

# Angka yang dicatat pada laporan / notebook TK1.
LOG_TK1 = {
    "awal": 10372,
    "missing_core": 0,
    "dup_id": 0,
    "dup_nama_koord": 1,
    "koord_nol": 0,
    "koord_luar_bbox": 0,
    "price_level_0": 110,
    "rating_0": 521,
    "kategori_kosong": 64,
    "akhir": 10261,
}


@pytest.fixture(scope="module")
def hasil():
    df, log = bersihkan_berkas(PATH_MENTAH)
    return df, log


@pytest.fixture(scope="module")
def acuan():
    return pd.read_csv(PATH_BERSIH)


def test_berkas_sumber_ada():
    assert PATH_MENTAH.is_file(), f"CSV mentah tidak ada: {PATH_MENTAH}"
    assert PATH_BERSIH.is_file(), f"CSV bersih tidak ada: {PATH_BERSIH}"


def test_jumlah_baris_dan_log(hasil):
    df, log = hasil
    assert log == LOG_TK1
    assert len(df) == 10261


def test_input_tidak_berubah():
    mentah = pd.read_csv(PATH_MENTAH)
    n_awal, kolom_awal = len(mentah), list(mentah.columns)
    _df, _log = bersihkan(mentah)
    assert len(mentah) == n_awal
    assert list(mentah.columns) == kolom_awal


def test_kolom_sama_dengan_acuan(hasil, acuan):
    df, _ = hasil
    assert list(df.columns) == list(acuan.columns)


def test_identitas_baris_sama_dengan_acuan(hasil, acuan):
    df, _ = hasil
    assert list(df["id"]) == list(acuan["id"])
    assert set(df["id"]) == set(acuan["id"])


def test_nilai_kategorikal_dan_numerik(hasil, acuan):
    df, _ = hasil
    for kolom in ("nama", "brand", "alamat_area", "region", "kota", "kecamatan", "kategori"):
        kiri = df[kolom].fillna("__KOSONG__").astype(str)
        kanan = acuan[kolom].fillna("__KOSONG__").astype(str)
        assert kiri.equals(kanan), f"Kolom {kolom} berbeda dari acuan TK1"

    assert df["sudah_dinilai"].astype(bool).equals(acuan["sudah_dinilai"].astype(bool))
    assert df["price_level"].astype(int).equals(acuan["price_level"].astype(int))
    assert df["n_kategori"].astype(int).equals(acuan["n_kategori"].astype(int))

    for kolom in ("latitude", "longitude", "rating", "price_norm", "rating_gap"):
        assert np.allclose(
            df[kolom].to_numpy(dtype=float),
            acuan[kolom].to_numpy(dtype=float),
            equal_nan=True,
            atol=1e-10,
            rtol=0,
        ), f"Kolom {kolom} tidak cukup dekat dengan acuan TK1"


def test_rating_nol_menjadi_belum_dinilai(hasil):
    df, log = hasil
    belum = df[~df["sudah_dinilai"]]
    assert len(belum) == 521
    assert log["rating_0"] == 521
    assert belum["rating"].isna().all()
    assert np.allclose(belum["rating_gap"].to_numpy(), 1.0)
    # Yang sudah dinilai tidak boleh kosong dan berada di rentang 1–5.
    dinilai = df[df["sudah_dinilai"]]
    assert dinilai["rating"].between(1, 5).all()
    assert dinilai["rating"].min() == pytest.approx(2.3)
    assert dinilai["rating"].max() == pytest.approx(5.0)


def test_price_level_hanya_satu_sampai_empat(hasil):
    df, _ = hasil
    assert set(df["price_level"].unique()) <= {1, 2, 3, 4}
    # Normalisasi (p - 1) / 3.
    assert np.allclose(df["price_norm"], (df["price_level"] - 1) / 3)


def test_ringkasan_wilayah_dan_kategori(hasil):
    df, _ = hasil
    assert df["kota"].nunique() == 18
    assert set(df["region"]) == {"Jabodetabek", "Bandung Raya"}
    assert (df["region"] == "Jabodetabek").sum() == 8631
    assert (df["region"] == "Bandung Raya").sum() == 1630
    # 21 nama kategori unik, sama dengan EDA TK1.
    nama = {n for teks in df["kategori"] for n in pecah_kategori(teks)}
    assert len(nama) == 21
    assert (df["n_kategori"] == 0).sum() == 64


def test_contoh_pemetaan_wilayah(hasil):
    df, _ = hasil
    # Aturan rapikan_wilayah: label "Depok" menjadi Kota Depok, Beji.
    # Cukup pastikan Kota Depok dan Kota Tangerang Selatan muncul.
    assert "Kota Depok" in set(df["kota"])
    assert "Kota Tangerang Selatan" in set(df["kota"])
    assert "Kota Bandung" in set(df["kota"])
    assert "Kabupaten Sumedang" in set(df["kota"])
