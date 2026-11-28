"""Uji metrik evaluasi offline: rumus, proksi, cakupan, Wilcoxon."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from kuliner.evaluasi import (
    PROXY_RATING_AMBANG,
    cakupan_katalog,
    dcg_at_k,
    diversitas_intra_daftar,
    keunikan_merek,
    metrik_daftar,
    ndcg_at_k,
    pecah_kategori_skenario,
    precision_at_k,
    relevansi_proksi,
    uji_wilcoxon,
    nilai_proksi_daftar,
)

ROOT = Path(__file__).resolve().parents[1]
PATH_SKENARIO = ROOT / "data" / "evaluasi" / "skenario.csv"


# ---------------------------------------------------------------------------
# Precision@K dan NDCG@K — contoh hitungan tangan
# ---------------------------------------------------------------------------

def test_precision_at_k_contoh_tangan():
    # Tiga relevan di lima posisi: 3/5 = 0,6. Jika K=10, tiga nol di belakang: 3/10.
    rel = [1, 0, 1, 0, 1]
    assert precision_at_k(rel, k=5) == pytest.approx(0.6)
    assert precision_at_k(rel, k=10) == pytest.approx(0.3)


def test_precision_ambang_graded():
    # Nilai 1 dan 2 relevan, 0 tidak — sesuai penilaian responden (bagian 5).
    rel = [2, 1, 0, 2, 0]
    assert precision_at_k(rel, k=5, ambang=1) == pytest.approx(0.6)
    assert precision_at_k(rel, k=5, ambang=2) == pytest.approx(0.4)


def test_precision_daftar_penuh_dan_kosong():
    assert precision_at_k([1] * 10, k=10) == 1.0
    assert precision_at_k([], k=10) == 0.0
    assert precision_at_k([0, 0, 0], k=3) == 0.0


def test_dcg_ndcg_contoh_tangan():
    # rel = [2, 1, 0, 2], K=4
    # DCG = 3/log2(2) + 1/log2(3) + 0/log2(4) + 3/log2(5)
    rel = [2, 1, 0, 2]
    dcg = (3 / np.log2(2) + 1 / np.log2(3) + 0 / np.log2(4) + 3 / np.log2(5))
    # IDCG dari [2, 2, 1, 0]
    idcg = (3 / np.log2(2) + 3 / np.log2(3) + 1 / np.log2(4) + 0 / np.log2(5))
    assert dcg_at_k(rel, k=4) == pytest.approx(dcg)
    assert ndcg_at_k(rel, k=4) == pytest.approx(dcg / idcg)


def test_ndcg_ideal_dan_nol():
    assert ndcg_at_k([2, 2, 1, 0], k=4) == pytest.approx(1.0)
    assert ndcg_at_k([0, 0, 0, 0], k=4) == 0.0
    assert ndcg_at_k([], k=10) == 0.0


def test_k_tidak_valid():
    with pytest.raises(ValueError):
        precision_at_k([1], k=0)
    with pytest.raises(ValueError):
        ndcg_at_k([1], k=0)


# ---------------------------------------------------------------------------
# Relevansi proksi Subbab 3.8.1
# ---------------------------------------------------------------------------

def test_proksi_nilai_dua():
    assert relevansi_proksi("Bakmie|Aneka nasi", 4.8, 2.0, ["Bakmie"], 5.0) == 2


def test_proksi_nilai_satu_hanya_kategori():
    # Rating di bawah median, atau jarak > R/2, tetapi kategori beririsan.
    assert relevansi_proksi("Bakmie", 4.5, 2.0, ["Bakmie"], 5.0) == 1
    assert relevansi_proksi("Bakmie", 4.8, 4.0, ["Bakmie"], 5.0) == 1


def test_proksi_nilai_nol_tanpa_irisan():
    assert relevansi_proksi("Chinese", 5.0, 1.0, ["Bakmie"], 5.0) == 0


def test_proksi_belum_dinilai_tidak_lolos_rating():
    assert relevansi_proksi("Bakmie", np.nan, 1.0, ["Bakmie"], 5.0, sudah_dinilai=False) == 1


def test_proksi_tanpa_pilihan_kategori():
    # Perluasan: tanpa kategori, 2 jika rating dan jarak, 1 jika salah satu.
    assert relevansi_proksi("Bakmie", 4.8, 1.0, [], 5.0) == 2
    assert relevansi_proksi("Bakmie", 4.8, 4.0, [], 5.0) == 1
    assert relevansi_proksi("Bakmie", 4.0, 1.0, [], 5.0) == 1
    assert relevansi_proksi("Bakmie", 4.0, 4.0, [], 5.0) == 0


def test_proksi_ambang_median_tk1():
    assert PROXY_RATING_AMBANG == pytest.approx(4.7)
    # Tepat di ambang: lolos syarat rating.
    assert relevansi_proksi("Bakmie", 4.7, 1.0, ["Bakmie"], 5.0) == 2
    assert relevansi_proksi("Bakmie", 4.69, 1.0, ["Bakmie"], 5.0) == 1


def test_nilai_proksi_daftar_dipotong_k():
    hasil = pd.DataFrame({
        "kategori": ["Bakmie", "Chinese", "Bakmie"],
        "rating": [4.9, 5.0, 4.2],
        "jarak_km": [1.0, 1.0, 1.0],
        "sudah_dinilai": [True, True, True],
    })
    nilai = nilai_proksi_daftar(hasil, ["Bakmie"], 5.0, k=5)
    assert nilai == [2, 0, 1, 0, 0]


# ---------------------------------------------------------------------------
# Cakupan, diversitas, keunikan, price-fit
# ---------------------------------------------------------------------------

def test_cakupan_katalog():
    assert cakupan_katalog([[1, 2, 3], [3, 4]], n_katalog=10) == pytest.approx(40.0)
    assert cakupan_katalog([[], []], n_katalog=10) == 0.0


def test_diversitas_pasangan_diketahui():
    # A|B dan A|C → Jaccard 1/3, 1 − Jaccard = 2/3.
    assert diversitas_intra_daftar(["A|B", "A|C"]) == pytest.approx(2 / 3)
    # Identik → diversitas 0.
    assert diversitas_intra_daftar(["Bakmie", "Bakmie"]) == pytest.approx(0.0)
    # Satu item → 0 (kesepakatan implementasi).
    assert diversitas_intra_daftar(["Bakmie"]) == 0.0


def test_keunikan_merek_lebih_tinggi_jika_jarang():
    freq = {"A": 100, "B": 1}
    n = 1000
    assert keunikan_merek("B", freq, n) > keunikan_merek("A", freq, n)
    # −log2(100/1000) = −log2(0,1) ≈ 3,3219
    assert keunikan_merek("A", freq, n) == pytest.approx(-np.log2(0.1))


def test_metrik_daftar_price_fit_dan_p10():
    hasil = pd.DataFrame({
        "id": [1, 2],
        "brand": ["X", "Y"],
        "kategori": ["Bakmie", "Bakmie"],
        "rating": [4.9, 4.2],
        "jarak_km": [1.0, 2.0],
        "price_level": [1, 3],
        "sudah_dinilai": [True, True],
    })
    m = metrik_daftar(hasil, ["Bakmie"], radius_km=5, budget_maks=2, k=2, frekuensi_merek={"X": 1, "Y": 1}, n_katalog=10)
    # Item kedua di atas budget → price_fit 0,5. Kedua beririsan kategori; pertama nilai 2, kedua nilai 1.
    assert m["price_fit"] == pytest.approx(0.5)
    assert m["precision_at_k"] == pytest.approx(1.0)
    assert m["n_hasil"] == 2


def test_pecah_kategori_skenario():
    assert pecah_kategori_skenario("Kopi|Sweets") == ["Kopi", "Sweets"]
    assert pecah_kategori_skenario("") == []
    assert pecah_kategori_skenario(None) == []


# ---------------------------------------------------------------------------
# Wilcoxon
# ---------------------------------------------------------------------------

def test_wilcoxon_identik():
    uji = uji_wilcoxon([1, 2, 3], [1, 2, 3])
    assert uji["n_selisih_nol"] == 3
    assert uji["p_value"] != uji["p_value"]  # NaN
    assert uji["signifikan"] is False
    assert "nol" in uji["catatan"].lower()


def test_wilcoxon_s4_lebih_tinggi():
    a = [0.8, 0.7, 0.9, 0.6, 0.75, 0.85]
    b = [0.4, 0.3, 0.5, 0.2, 0.35, 0.45]
    uji = uji_wilcoxon(a, b, alpha=0.05)
    assert uji["median_selisih"] > 0
    assert uji["p_value"] < 0.05
    assert uji["signifikan"] is True


# ---------------------------------------------------------------------------
# Berkas skenario
# ---------------------------------------------------------------------------

def test_skenario_empat_puluh_dan_delapan_belas_kota():
    df = pd.read_csv(PATH_SKENARIO)
    assert len(df) == 40
    assert df["id"].nunique() == 40
    assert df["kota"].nunique() == 18
    assert df.iloc[0]["id"] == "Q01"
    assert df.iloc[0]["kecamatan"] == "Beji"
    assert "Bakmie" in str(df.iloc[0]["kategori"])
    wajib = {"id", "kota", "kecamatan", "lat", "lon", "radius_km", "budget_maks", "rating_min", "kategori", "k"}
    assert wajib.issubset(set(df.columns))
