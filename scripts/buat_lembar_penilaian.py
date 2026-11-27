"""Buat lembar penilaian siap cetak / siap diunggah ke Google Sheets.

Setiap skenario mendapat gabungan Top-10 (S1 vs S4, atau metode yang dipilih)
dengan kolom nilai yang masih kosong. Berkas ini tidak berisi jawaban.

    python scripts/buat_lembar_penilaian.py
    python scripts/buat_lembar_penilaian.py --id Q01 --id Q19
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import pandas as pd

from kuliner.config import PATH_BERSIH, PATH_DB
from kuliner.penilaian import (
    METODE_BANDING_DEFAULT,
    kumpulan_item_penilaian,
    label_skenario,
    muat_skenario,
)
from kuliner.recommender import muat_katalog
from kuliner.sus import LABEL_LIKERT, PERNYATAAN_SUS

DIR_KELUAR = ROOT / "data" / "evaluasi" / "lembar"


def _data():
    if PATH_DB.exists():
        return muat_katalog(sumber="sqlite", path_db=PATH_DB, ulang=True)
    return muat_katalog(sumber="csv", path_csv=PATH_BERSIH, ulang=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--id", action="append", dest="ids", help="ID skenario (boleh diulang).")
    parser.add_argument("--semua", action="store_true", help="Buat lembar untuk 40 skenario.")
    args = parser.parse_args()

    skenario = muat_skenario()
    if args.semua:
        pilih = skenario
    elif args.ids:
        pilih = skenario[skenario["id"].isin(args.ids)]
    else:
        # Default: demonstrasi TK1 plus beberapa variasi, cukup untuk form cadangan.
        default_id = ["Q01", "Q19", "Q23", "Q27", "Q30"]
        pilih = skenario[skenario["id"].isin(default_id)]

    data = _data()
    DIR_KELUAR.mkdir(parents=True, exist_ok=True)
    gabung = []
    md = [
        "# Lembar penilaian relevansi (siap cetak / Google Sheets)",
        "",
        "Isi kode responden, lalu beri nilai 0 (tidak relevan), 1 (cukup relevan),",
        "atau 2 (sangat relevan) pada setiap tempat makan. Jangan mengisi kolom",
        "metode — kolom itu hanya untuk petugas yang mengolah hasil.",
        "",
        "Untuk uji resmi, utamakan tab **Evaluasi Pengguna** pada aplikasi",
        "(`streamlit run app.py`). Lembar ini adalah cadangan (kertas atau",
        "Google Form/Sheets).",
        "",
    ]
    for rec in pilih.itertuples():
        daftar = kumpulan_item_penilaian(
            data, rec, metode=METODE_BANDING_DEFAULT, k=10, seed=int(rec.id[1:]) * 17,
        )
        if daftar.empty:
            continue
        daftar = daftar.copy()
        daftar.insert(0, "kode_responden", "")
        daftar.insert(1, "id_skenario", rec.id)
        daftar["nilai_0_1_2"] = ""
        gabung.append(daftar)
        md.append(f"## {label_skenario(rec)}")
        md.append("")
        md.append("| No | Nama | Wilayah | Kategori | Harga | Rating | Jarak (km) | Nilai (0/1/2) |")
        md.append("| --- | --- | --- | --- | --- | --- | --- | --- |")
        for r in daftar.itertuples():
            kat = str(r.kategori or "").replace("|", ", ")
            md.append(
                f"| {int(r.peringkat_tampil)} | {r.nama} | {r.kota} – {r.kecamatan} | "
                f"{kat} | {int(r.price_level)} | {r.rating} | {float(r.jarak_km):.2f} | |"
            )
        md.append("")

    if gabung:
        csv = pd.concat(gabung, ignore_index=True)
        kolom = [
            "kode_responden", "id_skenario", "peringkat_tampil", "id_merchant",
            "nama", "kota", "kecamatan", "kategori", "price_level", "rating",
            "jarak_km", "nilai_0_1_2",
        ]
        csv[kolom].to_csv(DIR_KELUAR / "lembar_penilaian_relevansi.csv", index=False, float_format="%.4f")
    (DIR_KELUAR / "lembar_penilaian_relevansi.md").write_text("\n".join(md) + "\n", encoding="utf-8")

    # Templat SUS (satu baris per responden) — juga Google-Form-ready.
    sus_md = [
        "# Kuesioner SUS (siap cetak / Google Form)",
        "",
        "Skala Likert 1–5: 1 = sangat tidak setuju, 2 = tidak setuju, 3 = netral,",
        "4 = setuju, 5 = sangat setuju. Butir genap bersifat negatif.",
        "",
    ]
    for i, teks in enumerate(PERNYATAAN_SUS, start=1):
        opsi = " · ".join(f"{k} {v}" for k, v in LABEL_LIKERT.items())
        sus_md.append(f"{i}. {teks}")
        sus_md.append(f"   {opsi}")
        sus_md.append("")
    (DIR_KELUAR / "lembar_sus.md").write_text("\n".join(sus_md), encoding="utf-8")
    print(f"Lembar tertulis di {DIR_KELUAR.relative_to(ROOT)} ({len(pilih)} skenario).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
