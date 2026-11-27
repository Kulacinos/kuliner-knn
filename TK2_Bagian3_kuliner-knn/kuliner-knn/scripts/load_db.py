#!/usr/bin/env python3
"""Membangun (atau membangun ulang) basis data SQLite dari CSV merchant.

Contoh
------
Dari akar repositori::

    python scripts/load_db.py
    python scripts/load_db.py --csv data/processed/gofood_clean.csv --db data/kuliner.db
    python scripts/load_db.py --dari-mentah
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Agar paket kuliner dapat diimpor tanpa instalasi editable.
AKAR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AKAR / "src"))

from kuliner.config import PATH_BERSIH, PATH_DB, PATH_MENTAH  # noqa: E402
from kuliner.db import buat_mesin, hitung_isi, muat_dari_csv, muat_dari_dataframe  # noqa: E402
from kuliner.preprocessing import bersihkan_berkas  # noqa: E402


def parse_argumen() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Membangun basis data SQLite kuliner.db dari CSV (idempotent)."
    )
    p.add_argument(
        "--csv",
        type=Path,
        default=PATH_BERSIH,
        help="Jalur CSV bersih (default: data/processed/gofood_clean.csv).",
    )
    p.add_argument(
        "--db",
        type=Path,
        default=PATH_DB,
        help="Jalur berkas SQLite (default: data/kuliner.db).",
    )
    p.add_argument(
        "--dari-mentah",
        action="store_true",
        help="Bersihkan CSV mentah dulu, lalu muat hasilnya (tanpa menulis ulang CSV).",
    )
    p.add_argument(
        "--mentah",
        type=Path,
        default=PATH_MENTAH,
        help="Jalur CSV mentah, hanya dipakai bersama --dari-mentah.",
    )
    return p.parse_args()


def main() -> int:
    args = parse_argumen()
    args.db.parent.mkdir(parents=True, exist_ok=True)
    mesin = buat_mesin(path_db=args.db)

    if args.dari_mentah:
        print(f"Membersihkan {args.mentah} ...")
        df, log = bersihkan_berkas(args.mentah)
        print(
            "Log pembersihan: "
            f"awal={log['awal']}, "
            f"duplikat nama+koordinat={log['dup_nama_koord']}, "
            f"price_level 0={log['price_level_0']}, "
            f"rating 0 (dipertahankan)={log['rating_0']}, "
            f"akhir={log['akhir']}"
        )
        ringkas = muat_dari_dataframe(df, mesin, ulang=True)
    else:
        if not args.csv.is_file():
            print(f"Berkas CSV tidak ditemukan: {args.csv}", file=sys.stderr)
            return 1
        print(f"Memuat {args.csv} ke {args.db} ...")
        ringkas = muat_dari_csv(path_csv=args.csv, mesin=mesin, ulang=True)

    cek = hitung_isi(mesin)
    print("Selesai. Isi basis data:")
    print(f"  restoran           : {cek['restoran']}")
    print(f"  sudah dinilai      : {cek['sudah_dinilai']}")
    print(f"  belum dinilai      : {cek['restoran'] - cek['sudah_dinilai']}")
    print(f"  kota unik          : {cek['kota']}")
    print(f"  kategori unik      : {cek['kategori']}")
    print(f"  relasi restoran–kategori : {cek['restoran_kategori']}")
    print(f"Berkas: {args.db.resolve()}")
    # ringkas dipakai agar pemanggilan tidak dianggap sia-sia
    assert ringkas["restoran"] == cek["restoran"]
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
