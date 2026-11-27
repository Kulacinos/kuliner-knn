"""Jalankan kasus black-box dan tulis tabel hasil (aktual, status).

    python scripts/uji_black_box.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from kuliner.black_box import jalankan_semua, ringkasan_status  # noqa: E402

DIR_DOCS = ROOT / "docs"
DIR_LAPORAN = ROOT / "reports" / "black_box"


def _tabel_markdown(df) -> str:
    kolom = ["id", "fitur", "skenario", "input", "expected", "aktual", "status"]
    header = "| " + " | ".join(kolom) + " |"
    garis = "| " + " | ".join("---" for _ in kolom) + " |"
    baris = []
    for rec in df.itertuples(index=False):
        nilai = []
        for k in kolom:
            teks = str(getattr(rec, k, "")).replace("\n", " ").replace("|", "/")
            if len(teks) > 220:
                teks = teks[:217] + "..."
            nilai.append(teks)
        baris.append("| " + " | ".join(nilai) + " |")
    return "\n".join([header, garis, *baris])


def main() -> int:
    print("Menjalankan katalog black-box (AppTest + keluaran publik)...")
    tabel = jalankan_semua(hanya_otomatis=False)
    ringkas = ringkasan_status(tabel)
    DIR_DOCS.mkdir(parents=True, exist_ok=True)
    DIR_LAPORAN.mkdir(parents=True, exist_ok=True)
    tabel.to_csv(DIR_LAPORAN / "hasil_black_box.csv", index=False)
    tabel.to_csv(DIR_DOCS / "black_box_testing.csv", index=False)
    (DIR_LAPORAN / "ringkasan_black_box.json").write_text(
        json.dumps(ringkas, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    md = f"""# Uji black-box sistem rekomendasi kuliner

Tabel ini mengikuti rancangan Tabel 3.19 laporan TK1 (BB-01 sampai BB-14)
plus dua kasus pelengkap (BB-15 kategori kosong, BB-16 waktu respons NFR-01).
Sebuah kasus **lulus** jika keluaran sesuai hasil yang diharapkan.

Kolom `aktual` dan `status` diisi dari jalannya `python scripts/uji_black_box.py`
(atau `pytest tests/test_black_box.py`). Kasus otomatis memakai AppTest Streamlit
atau keluaran publik mesin/peta, tanpa membuka kode di dalam fungsi sebagai orakel.

## Ringkasan

- Jumlah kasus: **{ringkas['n']}**
- Diuji otomatis: **{ringkas['n_otomatis']}** (lulus {ringkas['n_lulus_otomatis']}, {ringkas['persen_lulus_otomatis']:.0f}%)
- Status keseluruhan: `{ringkas['hitung']}`

## Keterangan status

| Status | Arti |
| --- | --- |
| lulus | Keluaran sesuai yang diharapkan |
| gagal | Keluaran menyimpang; perlu perbaikan |
| dilewati | Tidak dapat diuji pada tumpukan saat ini (lihat aktual) |
| ditunda | Fitur terkait belum diimplementasikan (admin FR-10–12) |

BB-01 dilewati karena aplikasi tidak memakai GPS browser (keterbatasan Streamlit;
lokasi dipilih lewat kota/kecamatan, koordinat, atau klik peta). BB-11 sampai
BB-14 ditunda sampai fitur admin dikerjakan.

## Tabel kasus

{_tabel_markdown(tabel)}

## Mengulang

```bash
python scripts/uji_black_box.py
python -m pytest tests/test_black_box.py
```
"""
    (DIR_DOCS / "black_box_testing.md").write_text(md, encoding="utf-8")
    print(tabel[["id", "fitur", "status"]].to_string(index=False))
    print(
        f"\nOtomatis: {ringkas['n_lulus_otomatis']}/{ringkas['n_otomatis']} lulus "
        f"({ringkas['persen_lulus_otomatis']:.0f}%)."
    )
    print(f"Tabel: docs/black_box_testing.md dan reports/black_box/hasil_black_box.csv")
    gagal = tabel[(tabel["otomatis"]) & (tabel["status"] == "gagal")]
    return 1 if len(gagal) else 0


if __name__ == "__main__":
    raise SystemExit(main())
