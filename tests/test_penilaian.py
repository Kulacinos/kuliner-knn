"""Uji alat penilaian relevansi dan perhitungan metrik dari label manusia."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from kuliner.evaluasi import ndcg_at_k, precision_at_k
from kuliner.penilaian import (
    PATH_CONTOH_PENILAIAN,
    PATH_CONTOH_SUS,
    SUMBER_CONTOH,
    adalah_contoh,
    kumpulan_item_penilaian,
    metrik_dari_penilaian,
    muat_penilaian,
    muat_skenario,
    muat_sus,
    simpan_penilaian,
    simpan_sus,
    validasi_kode_responden,
)
from kuliner.recommender import muat_katalog

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def data():
    return muat_katalog()


@pytest.fixture(scope="module")
def skenario():
    return muat_skenario()


def test_validasi_kode():
    assert validasi_kode_responden("R01") == "R01"
    with pytest.raises(ValueError, match="wajib"):
        validasi_kode_responden("  ")
    with pytest.raises(ValueError, match="CONTOH"):
        validasi_kode_responden("CONTOH01")
    assert validasi_kode_responden("CONTOH01", izinkan_contoh=True) == "CONTOH01"
    with pytest.raises(ValueError, match="huruf"):
        validasi_kode_responden("R 01")


def test_adalah_contoh():
    assert adalah_contoh("CONTOH01") is True
    assert adalah_contoh(SUMBER_CONTOH) is True
    assert adalah_contoh("R01") is False


def test_kumpulan_acak_tanpa_duplikat(data, skenario):
    baris = skenario[skenario["id"] == "Q01"].iloc[0]
    a = kumpulan_item_penilaian(data, baris, metode=("S1_jarak", "S4_penuh"), k=10, seed=7)
    b = kumpulan_item_penilaian(data, baris, metode=("S1_jarak", "S4_penuh"), k=10, seed=7)
    c = kumpulan_item_penilaian(data, baris, metode=("S1_jarak", "S4_penuh"), k=10, seed=99)
    assert not a.empty
    assert a["id_merchant"].nunique() == len(a)
    assert len(a) <= 20  # gabungan dua Top-10
    assert list(a["id_merchant"]) == list(b["id_merchant"])
    # Biji berbeda → urutan (hampir pasti) berbeda, isi himpunan sama.
    assert set(a["id_merchant"]) == set(c["id_merchant"])
    if len(a) > 1:
        assert list(a["id_merchant"]) != list(c["id_merchant"])
    # Kolom metode ada untuk petugas, tidak wajib ditampilkan.
    assert "metode_sumber" in a.columns
    assert "peringkat_tampil" in a.columns


def test_simpan_dan_timpa(tmp_path, data, skenario):
    baris = skenario[skenario["id"] == "Q01"].iloc[0]
    daftar = kumpulan_item_penilaian(data, baris, metode=("S4_penuh",), k=3, seed=1)
    rec = daftar.iloc[0]
    csv = tmp_path / "p.csv"
    db = tmp_path / "p.db"
    frame = pd.DataFrame([{
        "waktu_iso": "2026-11-26T09:00:00+08:00",
        "kode_responden": "R01",
        "id_skenario": "Q01",
        "id_merchant": rec["id_merchant"],
        "nama": rec["nama"],
        "peringkat_tampil": 1,
        "nilai": 2,
        "metode_sumber": rec["metode_sumber"],
        "peringkat_per_metode": rec["peringkat_per_metode"],
        "sumber": "responden",
    }])
    simpan_penilaian(frame, path_csv=csv, path_db=db)
    frame2 = frame.copy()
    frame2["nilai"] = 1
    gabung = simpan_penilaian(frame2, path_csv=csv, path_db=db)
    assert len(gabung) == 1
    assert int(gabung.iloc[0]["nilai"]) == 1
    assert muat_penilaian(csv).iloc[0]["nilai"] == 1


def test_metrik_dari_nilai_dikenal(data, skenario):
    baris = skenario[skenario["id"] == "Q01"].iloc[0]
    dari_s4 = kumpulan_item_penilaian(data, baris, metode=("S4_penuh",), k=10, seed=1)
    # Semua item S4 dinilai 2 → P@10 = 1, NDCG@10 = 1.
    penilaian = pd.DataFrame({
        "kode_responden": ["R99"] * len(dari_s4),
        "id_skenario": ["Q01"] * len(dari_s4),
        "id_merchant": dari_s4["id_merchant"],
        "nilai": [2] * len(dari_s4),
        "metode_sumber": dari_s4["metode_sumber"],
        "peringkat_per_metode": dari_s4["peringkat_per_metode"],
        "sumber": ["responden"] * len(dari_s4),
    })
    hasil = metrik_dari_penilaian(penilaian, data, skenario, metode=("S4_penuh",), k=10)
    assert len(hasil) == 1
    assert hasil.iloc[0]["precision_at_k"] == pytest.approx(1.0)
    assert hasil.iloc[0]["ndcg_at_k"] == pytest.approx(1.0)


def test_precision_ndcg_fungsi_siap_nilai_manusia():
    # Sama dengan kontrak bagian 4 / 5: 1 dan 2 relevan untuk P@K.
    assert precision_at_k([2, 1, 0, 2, 0], k=5, ambang=1) == pytest.approx(0.6)
    assert 0 < ndcg_at_k([2, 1, 0, 2, 0], k=5) <= 1


def test_berkas_contoh_jelas_bukan_data_nyata():
    assert PATH_CONTOH_PENILAIAN.exists()
    assert PATH_CONTOH_SUS.exists()
    assert "contoh_" in PATH_CONTOH_PENILAIAN.name
    rel = muat_penilaian(PATH_CONTOH_PENILAIAN)
    sus = muat_sus(PATH_CONTOH_SUS)
    assert not rel.empty and not sus.empty
    assert rel["sumber"].eq(SUMBER_CONTOH).all()
    assert rel["kode_responden"].map(adalah_contoh).all()
    assert sus["sumber"].eq(SUMBER_CONTOH).all()
    assert sus["kode_responden"].map(adalah_contoh).all()
    # README di folder yang sama harus memperingatkan.
    baca = (ROOT / "data" / "evaluasi" / "README.md").read_text(encoding="utf-8")
    assert "BUKAN" in baca and "CONTOH" in baca.upper() or "contoh" in baca.lower()


def test_simpan_sus_timpa(tmp_path):
    csv = tmp_path / "sus.csv"
    db = tmp_path / "sus.db"
    baris = {
        "waktu_iso": "2026-11-26T09:00:00+08:00",
        "kode_responden": "R01",
        "s1": 5, "s2": 1, "s3": 5, "s4": 1, "s5": 5,
        "s6": 1, "s7": 5, "s8": 1, "s9": 5, "s10": 1,
        "skor": 100.0,
        "sumber": "responden",
    }
    simpan_sus(pd.DataFrame([baris]), path_csv=csv, path_db=db)
    baris["s1"] = 4
    baris["skor"] = 97.5
    gabung = simpan_sus(pd.DataFrame([baris]), path_csv=csv, path_db=db)
    assert len(gabung) == 1
    assert int(gabung.iloc[0]["s1"]) == 4
