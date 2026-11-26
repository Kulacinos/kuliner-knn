#!/usr/bin/env python3
"""Contoh pemakaian mesin rekomendasi dari baris perintah.

Default: titik di dekat Monas, Jakarta Pusat, radius 5 km, 10 hasil.
Contoh lain (centroid Beji, Depok — sama dengan demo laporan TK1)::

    python scripts/demo_rekomendasi.py --contoh beji
    python scripts/demo_rekomendasi.py --lat -6.1754 --lon 106.8272 --budget 2 --rating-min 4.5 --kategori Bakmie
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

AKAR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AKAR / "src"))

from kuliner.recommender import (  # noqa: E402
    muat_katalog,
    rekomendasi,
    rekomendasi_dasar,
    titik_pusat,
)

# Monumen Nasional, Jakarta Pusat (perkiraan koordinat).
MONAS_LAT = -6.175392
MONAS_LON = 106.827153


def parse_argumen() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Demo rekomendasi kuliner KNN (bagian 2).")
    p.add_argument("--lat", type=float, default=None, help="Latitude pengguna.")
    p.add_argument("--lon", type=float, default=None, help="Longitude pengguna.")
    p.add_argument("--radius", type=float, default=5.0, help="Radius filter (km).")
    p.add_argument("--budget", type=int, default=4, help="price_level maksimum (1–4).")
    p.add_argument("--rating-min", type=float, default=0.0, help="Rating minimum (0 = tidak dibatasi).")
    p.add_argument(
        "--kategori",
        type=str,
        default="",
        help="Kategori dipisah koma, misalnya: Bakmie,Kopi.",
    )
    p.add_argument("-k", type=int, default=10, help="Jumlah hasil.")
    p.add_argument(
        "--contoh",
        choices=["monas", "beji"],
        default="monas",
        help="Titik siap pakai jika --lat/--lon tidak diisi (default: monas).",
    )
    p.add_argument(
        "--dasar",
        action="store_true",
        help="Cetak juga 10 besar baseline jarak-saja (filter yang sama).",
    )
    return p.parse_args()


def _cetak(judul: str, hasil) -> None:
    print(judul)
    if hasil.empty:
        print("  (tidak ada merchant yang lolos filter)")
        return
    kolom = [
        c
        for c in (
            "peringkat",
            "nama",
            "kecamatan",
            "kategori",
            "price_level",
            "rating",
            "jarak_km",
            "f_lokasi",
            "f_kategori",
            "f_rating",
            "f_harga",
            "skor",
        )
        if c in hasil.columns
    ]
    tampil = hasil[kolom].copy()
    for c in ("jarak_km", "f_lokasi", "f_kategori", "f_rating", "f_harga", "skor"):
        if c in tampil.columns:
            tampil[c] = tampil[c].map(lambda x: f"{x:.3f}")
    if "rating" in tampil.columns:
        tampil["rating"] = tampil["rating"].map(lambda x: "–" if pd_isna(x) else f"{x:.1f}")
    print(tampil.to_string(index=False))


def pd_isna(x) -> bool:
    try:
        import pandas as pd

        return bool(pd.isna(x))
    except Exception:
        return x is None


def main() -> int:
    args = parse_argumen()
    data = muat_katalog()  # DB jika ada, kalau tidak CSV
    print(f"Katalog: {len(data):,} merchant.".replace(",", "."))

    if args.lat is not None and args.lon is not None:
        lat, lon = args.lat, args.lon
        sumber = "koordinat manual"
    elif args.contoh == "beji":
        lat, lon, n = titik_pusat("Kota Depok", "Beji", data=data)
        sumber = f"centroid Kota Depok – Beji ({n} merchant)"
        # Jika pengguna tidak mengubah filter, ikuti contoh TK1.
        if args.budget == 4 and args.rating_min == 0.0 and not args.kategori:
            args.budget = 2
            args.rating_min = 4.5
            args.kategori = "Bakmie"
            print("Filter contoh Beji: budget ≤ 2, rating ≥ 4,5, kategori Bakmie.")
    else:
        lat, lon = MONAS_LAT, MONAS_LON
        sumber = "Monas, Jakarta Pusat"

    kategori = [s.strip() for s in args.kategori.split(",") if s.strip()]
    print(f"Lokasi: {sumber} ({lat:.6f}, {lon:.6f})")
    print(
        f"Filter: radius {args.radius:g} km, budget ≤ {args.budget}, "
        f"rating ≥ {args.rating_min:g}, kategori={kategori or '–'}, k={args.k}"
    )
    print()

    hasil = rekomendasi(
        lat,
        lon,
        radius_km=args.radius,
        budget_maks=args.budget,
        rating_min=args.rating_min,
        kategori_pilihan=kategori,
        k=args.k,
        data=data,
    )
    _cetak("Rekomendasi (jarak berbobot TK1):", hasil)

    if args.dasar:
        print()
        dasar = rekomendasi_dasar(
            lat,
            lon,
            radius_km=args.radius,
            budget_maks=args.budget,
            rating_min=args.rating_min,
            kategori_pilihan=kategori,
            k=args.k,
            acuan="jarak",
            data=data,
        )
        _cetak("Baseline jarak saja (filter sama):", dasar)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
