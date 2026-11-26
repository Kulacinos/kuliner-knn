"""Perhitungan jarak geografis (Haversine) dan filter radius.

Latitude dan longitude adalah sudut, bukan koordinat bidang datar,
sehingga jarak Euclidean pada derajat tidak menggambarkan jarak
sebenarnya di permukaan bumi. Formula Haversine menghitung jarak
lingkaran besar (km) antara dua titik.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from kuliner.config import R_BUMI_KM


def haversine(lat1, lon1, lat2, lon2, r: float = R_BUMI_KM):
    """Jarak lingkaran besar dalam kilometer.

    Semua argumen boleh berupa skalar atau array NumPy/Pandas yang
    bisa disiarkan (broadcast) bersama. Jika seluruh masukan skalar,
    hasilnya ``float``; jika ada yang berbentuk array, hasilnya
    ``ndarray``.

    Rumus sama dengan notebook TK1, dengan radius bumi
    ``R_BUMI_KM = 6371.0088``.
    """
    phi1 = np.radians(np.asarray(lat1, dtype=float))
    lam1 = np.radians(np.asarray(lon1, dtype=float))
    phi2 = np.radians(np.asarray(lat2, dtype=float))
    lam2 = np.radians(np.asarray(lon2, dtype=float))
    dphi = phi2 - phi1
    dlam = lam2 - lam1
    a = np.sin(dphi / 2) ** 2 + np.cos(phi1) * np.cos(phi2) * np.sin(dlam / 2) ** 2
    # Cegah nilai di luar [0, 1] karena galat floating point.
    a = np.clip(a, 0.0, 1.0)
    jarak = 2.0 * r * np.arcsin(np.sqrt(a))
    if np.ndim(jarak) == 0:
        return float(jarak)
    return jarak


def saring_radius(
    lat: float,
    lon: float,
    data: pd.DataFrame,
    radius_km: float,
    kolom_lat: str = "latitude",
    kolom_lon: str = "longitude",
) -> pd.DataFrame:
    """Saring baris yang berada dalam radius (inklusif) dari titik kueri.

    Menambahkan kolom ``jarak_km``. Jika tidak ada yang lolos, DataFrame
    kosong tetap memiliki kolom tersebut.
    """
    if radius_km < 0:
        raise ValueError("radius_km tidak boleh negatif.")
    jarak = haversine(lat, lon, data[kolom_lat].to_numpy(), data[kolom_lon].to_numpy())
    jarak = np.asarray(jarak, dtype=float)
    if jarak.shape == ():
        jarak = np.full(len(data), float(jarak))
    mask = jarak <= radius_km
    keluar = data.loc[mask].copy()
    keluar["jarak_km"] = jarak[mask]
    return keluar
