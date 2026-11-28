"""Hitung Precision@10 dan NDCG@10 dari penilaian responden (skala 0/1/2).

Sumber utama: data/evaluasi/hasil/penilaian_relevansi.csv
(data nyata, tidak diunggah ke Git).

Untuk memeriksa skrip tanpa data responden, jalankan dengan --contoh.
Berkas contoh adalah DATA TIRUAN dan tidak boleh dilaporkan sebagai hasil uji.

    python scripts/hitung_relevansi.py
    python scripts/hitung_relevansi.py --contoh
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import pandas as pd

from kuliner.config import PATH_BERSIH, PATH_DB
from kuliner.penilaian import (
    PATH_CONTOH_PENILAIAN,
    PATH_HASIL_PENILAIAN,
    SUMBER_CONTOH,
    adalah_contoh,
    metrik_dari_penilaian,
    muat_penilaian,
    muat_skenario,
    ringkas_metrik_manusia,
    wilcoxon_manusia,
)
from kuliner.recommender import muat_katalog

DIR_LAPORAN = ROOT / "reports" / "evaluasi_pengguna"


def _muat_data():
    if PATH_DB.exists():
        return muat_katalog(sumber="sqlite", path_db=PATH_DB, ulang=True)
    return muat_katalog(sumber="csv", path_csv=PATH_BERSIH, ulang=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Metrik relevansi dari penilaian manusia.")
    parser.add_argument(
        "--contoh",
        action="store_true",
        help="Pakai berkas contoh (DATA TIRUAN, bukan responden nyata).",
    )
    parser.add_argument("--path", type=Path, default=None, help="Berkas CSV penilaian kustom.")
    args = parser.parse_args()

    if args.path:
        path = args.path
        pakai_contoh = args.contoh or SUMBER_CONTOH in path.name or "contoh_" in path.name
    elif args.contoh:
        path = PATH_CONTOH_PENILAIAN
        pakai_contoh = True
    else:
        path = PATH_HASIL_PENILAIAN
        pakai_contoh = False

    if not path.exists():
        print(f"Berkas penilaian tidak ditemukan: {path}", file=sys.stderr)
        if not pakai_contoh:
            print(
                "Belum ada data responden. Setelah uji pengguna, berkas akan "
                "tertulis di data/evaluasi/hasil/penilaian_relevansi.csv.\n"
                "Untuk merapikan skrip dengan data tiruan: python scripts/hitung_relevansi.py --contoh",
                file=sys.stderr,
            )
        return 1

    penilaian = muat_penilaian(path)
    if penilaian.empty:
        print("Berkas penilaian kosong.", file=sys.stderr)
        return 1

    if penilaian["kode_responden"].map(adalah_contoh).any() or (
        "sumber" in penilaian.columns and penilaian["sumber"].map(adalah_contoh).any()
    ):
        pakai_contoh = True

    if pakai_contoh:
        print("=" * 72)
        print("PERINGATAN: ini DATA TIRUAN / CONTOH, BUKAN penilaian responden nyata.")
        print("Jangan masukkan angka berikut ke laporan hasil evaluasi TK2.")
        print("=" * 72)

    data = _muat_data()
    skenario = muat_skenario()
    hasil = metrik_dari_penilaian(penilaian, data, skenario, k=10)
    ringkas = ringkas_metrik_manusia(hasil)
    uji_p = wilcoxon_manusia(hasil, "S4_penuh", "S1_jarak", "precision_at_k")
    uji_n = wilcoxon_manusia(hasil, "S4_penuh", "S1_jarak", "ndcg_at_k")

    DIR_LAPORAN.mkdir(parents=True, exist_ok=True)
    akhiran = "contoh" if pakai_contoh else "responden"
    hasil.to_csv(DIR_LAPORAN / f"metrik_per_pasangan_{akhiran}.csv", index=False, float_format="%.6f")
    ringkas.to_csv(DIR_LAPORAN / f"ringkasan_metrik_{akhiran}.csv", index=False, float_format="%.6f")
    meta = {
        "sumber_berkas": str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path),
        "adalah_contoh": pakai_contoh,
        "peringatan": (
            "DATA TIRUAN, bukan responden nyata." if pakai_contoh else "Penilaian responden."
        ),
        "n_baris_penilaian": int(len(penilaian)),
        "n_responden": int(penilaian["kode_responden"].nunique()),
        "wilcoxon_S4_vs_S1_precision_at_10": uji_p,
        "wilcoxon_S4_vs_S1_ndcg_at_10": uji_n,
    }
    (DIR_LAPORAN / f"meta_{akhiran}.json").write_text(
        json.dumps(meta, indent=2, ensure_ascii=False, default=float) + "\n",
        encoding="utf-8",
    )

    print("\nRingkasan Precision@10 dan NDCG@10:")
    print(ringkas.to_string(index=False, float_format=lambda x: f"{x:.4f}"))
    print(
        f"\nWilcoxon S4 vs S1 (P@10): p={uji_p['p_value']!r}, "
        f"median selisih={uji_p['median_selisih']}"
    )
    print(f"Luaran: {DIR_LAPORAN.relative_to(ROOT)}/*_{akhiran}.*")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
