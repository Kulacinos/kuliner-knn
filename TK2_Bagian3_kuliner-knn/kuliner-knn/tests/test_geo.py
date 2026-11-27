"""Uji formula Haversine dan filter radius."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from kuliner.config import R_BUMI_KM
from kuliner.geo import haversine, saring_radius


def test_titik_yang_sama_berjarak_nol():
    assert haversine(-6.1754, 106.8272, -6.1754, 106.8272) == pytest.approx(0.0, abs=1e-12)


def test_satu_derajat_di_khatulistiwa():
    # Pada lintang 0, 1 derajat bujur = 1 derajat lintang = R * pi / 180.
    diharapkan = R_BUMI_KM * np.pi / 180.0
    assert haversine(0.0, 0.0, 0.0, 1.0) == pytest.approx(diharapkan, rel=1e-12)
    assert haversine(0.0, 0.0, 1.0, 0.0) == pytest.approx(diharapkan, rel=1e-12)


def test_simetris():
    a = haversine(-6.1754, 106.8272, -6.9214, 107.6071)
    b = haversine(-6.9214, 107.6071, -6.1754, 106.8272)
    assert a == pytest.approx(b, rel=1e-12)
    assert a > 100  # Monas ke pusat Bandung kira-kira 115–130 km
    assert a < 150


def test_antipodal():
    # (0, 0) ke (0, 180) adalah setengah keliling bumi.
    assert haversine(0.0, 0.0, 0.0, 180.0) == pytest.approx(np.pi * R_BUMI_KM, rel=1e-12)


def test_vektorized_bentuk_hasil():
    lat2 = np.array([-6.2, -6.3, -6.4])
    lon2 = np.array([106.8, 106.9, 107.0])
    jarak = haversine(-6.1754, 106.8272, lat2, lon2)
    assert isinstance(jarak, np.ndarray)
    assert jarak.shape == (3,)
    assert np.all(jarak > 0)


def test_filter_radius_inklusif_dan_keluar():
    # 1 derajat di khatulistiwa.
    satu_derajat = R_BUMI_KM * np.pi / 180.0
    data = pd.DataFrame(
        {
            "id": ["dalam", "batas", "luar"],
            "latitude": [0.0, 0.0, 0.0],
            "longitude": [0.5, 1.0, 1.1],
        }
    )
    dalam = saring_radius(0.0, 0.0, data, radius_km=satu_derajat)
    assert set(dalam["id"]) == {"dalam", "batas"}
    assert "jarak_km" in dalam.columns
    assert dalam.loc[dalam["id"] == "batas", "jarak_km"].iloc[0] == pytest.approx(
        satu_derajat, rel=1e-12
    )


def test_filter_radius_kosong():
    data = pd.DataFrame({"id": ["a"], "latitude": [10.0], "longitude": [10.0]})
    keluar = saring_radius(0.0, 0.0, data, radius_km=1.0)
    assert keluar.empty
    assert "jarak_km" in keluar.columns


def test_radius_negatif_ditolak():
    data = pd.DataFrame({"latitude": [0.0], "longitude": [0.0]})
    with pytest.raises(ValueError, match="negatif"):
        saring_radius(0.0, 0.0, data, radius_km=-1)
