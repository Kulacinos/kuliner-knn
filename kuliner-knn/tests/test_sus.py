"""Uji penskoran SUS (Persamaan 2.7) dan label interpretasi."""

from __future__ import annotations

import pytest

from kuliner.sus import (
    AMBANG_ACCEPTABLE,
    PERNYATAAN_SUS,
    adjektiva,
    huruf,
    keberterimaan,
    ringkasan_kumpulan,
    ringkasan_skor,
    skor_sus,
)


def test_sepuluh_pernyataan_bahasa_indonesia():
    assert len(PERNYATAAN_SUS) == 10
    assert all(s.endswith(".") for s in PERNYATAAN_SUS)
    # Butir genap harus bernada negatif.
    assert "rumit" in PERNYATAAN_SUS[1].lower() or "tidak perlu" in PERNYATAAN_SUS[1].lower()
    assert "merepotkan" in PERNYATAAN_SUS[7].lower()


def test_skor_sempurna_dan_terburuk():
    assert skor_sus([5, 1, 5, 1, 5, 1, 5, 1, 5, 1]) == 100.0
    assert skor_sus([1, 5, 1, 5, 1, 5, 1, 5, 1, 5]) == 0.0


def test_skor_netral_semua_tiga():
    # (3-1)*5 + (5-3)*5 = 20; 20*2,5 = 50
    assert skor_sus([3] * 10) == 50.0


def test_skor_contoh_empat_dua():
    # Setiap butir menyumbang 3; 30*2,5 = 75
    assert skor_sus([4, 2, 4, 2, 4, 2, 4, 2, 4, 2]) == 75.0


def test_semua_lima_bukan_seratus():
    # Setuju penuh pada butir negatif menurunkan skor: 50.
    assert skor_sus([5] * 10) == 50.0


def test_jawaban_tidak_valid():
    with pytest.raises(ValueError, match="tepat 10"):
        skor_sus([3, 3, 3])
    with pytest.raises(ValueError, match="antara 1 dan 5"):
        skor_sus([1, 2, 3, 4, 5, 1, 2, 3, 4, 6])
    with pytest.raises(ValueError, match="antara 1 dan 5"):
        skor_sus([0, 1, 1, 1, 1, 1, 1, 1, 1, 1])


def test_keberterimaan_nfr02():
    assert keberterimaan(70) == "acceptable"
    assert keberterimaan(69.9) == "marginal"
    assert keberterimaan(50) == "marginal"
    assert keberterimaan(49.9) == "not acceptable"
    assert AMBANG_ACCEPTABLE == 70.0


def test_huruf_dan_adjektiva():
    assert huruf(100) == "A+"
    assert huruf(84.1) == "A+"
    assert huruf(80.8) == "A"
    assert huruf(50) == "F" or huruf(50) == "D"  # 50 < 51.7 → F
    assert huruf(50) == "F"
    assert adjektiva(90)[0] == "Best Imaginable"
    assert adjektiva(80)[1] == "Unggul"
    assert adjektiva(70)[1] == "Baik"
    assert adjektiva(10)[0] == "Worst Imaginable"


def test_ringkasan_kumpulan():
    info = ringkasan_kumpulan([80.0, 70.0, 60.0])
    assert info["n"] == 3
    assert info["rata"] == pytest.approx(70.0)
    assert info["median"] == pytest.approx(70.0)
    assert info["n_memenuhi_nfr02"] == 2
    assert info["memenuhi_nfr02"] is True
    assert "huruf" in info


def test_ringkasan_kumpulan_kosong():
    with pytest.raises(ValueError):
        ringkasan_kumpulan([])
