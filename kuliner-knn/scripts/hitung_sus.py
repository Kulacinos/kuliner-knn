"""Ringkas skor SUS dari jawaban responden.

    python scripts/hitung_sus.py
    python scripts/hitung_sus.py --contoh
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from kuliner.penilaian import (  # noqa: E402
    PATH_CONTOH_SUS,
    PATH_HASIL_SUS,
    SUMBER_CONTOH,
    adalah_contoh,
    muat_sus,
)
from kuliner.sus import AMBANG_ACCEPTABLE, ringkasan_kumpulan, ringkasan_skor, skor_sus  # noqa: E402

DIR_LAPORAN = ROOT / "reports" / "evaluasi_pengguna"


def main() -> int:
    parser = argparse.ArgumentParser(description="Ringkasan skor SUS.")
    parser.add_argument("--contoh", action="store_true", help="Pakai data tiruan (bukan responden).")
    parser.add_argument("--path", type=Path, default=None)
    args = parser.parse_args()

    if args.path:
        path = args.path
        pakai_contoh = args.contoh or "contoh_" in path.name
    elif args.contoh:
        path = PATH_CONTOH_SUS
        pakai_contoh = True
    else:
        path = PATH_HASIL_SUS
        pakai_contoh = False

    if not path.exists():
        print(f"Berkas SUS tidak ditemukan: {path}", file=sys.stderr)
        if not pakai_contoh:
            print(
                "Belum ada jawaban responden. Untuk uji skrip: python scripts/hitung_sus.py --contoh",
                file=sys.stderr,
            )
        return 1

    df = muat_sus(path)
    if df.empty:
        print("Berkas SUS kosong.", file=sys.stderr)
        return 1

    if df["kode_responden"].map(adalah_contoh).any() or (
        "sumber" in df.columns and df["sumber"].map(adalah_contoh).any()
    ):
        pakai_contoh = True

    if pakai_contoh:
        print("=" * 72)
        print("PERINGATAN: ini DATA TIRUAN / CONTOH, BUKAN jawaban responden nyata.")
        print("Jangan masukkan angka berikut ke laporan hasil kebergunaan TK2.")
        print("=" * 72)

    # Hitung ulang skor dari s1–s10 agar konsisten dengan Persamaan 2.7.
    skor = []
    for rec in df.itertuples():
        jawaban = [int(getattr(rec, f"s{i}")) for i in range(1, 11)]
        s = skor_sus(jawaban)
        skor.append(s)
    df = df.copy()
    df["skor"] = skor
    df["huruf"] = [ringkasan_skor(skor=s)["huruf"] for s in skor]
    df["adjektiva_id"] = [ringkasan_skor(skor=s)["adjektiva_id"] for s in skor]
    df["keberterimaan_id"] = [ringkasan_skor(skor=s)["keberterimaan_id"] for s in skor]

    ringkas = ringkasan_kumpulan(skor)
    DIR_LAPORAN.mkdir(parents=True, exist_ok=True)
    akhiran = "contoh" if pakai_contoh else "responden"
    tampil = df[["kode_responden", "skor", "huruf", "adjektiva_id", "keberterimaan_id", "sumber"]].copy()
    tampil.to_csv(DIR_LAPORAN / f"sus_per_responden_{akhiran}.csv", index=False, float_format="%.2f")
    (DIR_LAPORAN / f"sus_ringkasan_{akhiran}.json").write_text(
        json.dumps(
            {
                "adalah_contoh": pakai_contoh,
                "peringatan": "DATA TIRUAN, bukan responden nyata." if pakai_contoh else "Jawaban responden.",
                "ambang_nfr02": AMBANG_ACCEPTABLE,
                **{k: v for k, v in ringkas.items()},
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    print(
        f"\nn = {ringkas['n']}, rata-rata = {ringkas['rata']:.2f}, "
        f"median = {ringkas['median']:.2f}, min = {ringkas['min']:.1f}, "
        f"maks = {ringkas['maks']:.1f}"
    )
    print(
        f"Huruf (rata-rata): {ringkas['huruf']} · {ringkas['adjektiva_id']} · "
        f"{ringkas['keberterimaan_id']}"
    )
    print(
        f"Memenuhi NFR-02 (≥ {AMBANG_ACCEPTABLE:.0f}): "
        f"{ringkas['n_memenuhi_nfr02']}/{ringkas['n']} responden; "
        f"rata-rata {'memenuhi' if ringkas['memenuhi_nfr02'] else 'belum memenuhi'} ambang."
    )
    print(f"Luaran: {DIR_LAPORAN.relative_to(ROOT)}/*_{akhiran}.*")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
