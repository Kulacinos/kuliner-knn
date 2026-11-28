# Skenario evaluasi offline

`skenario.csv` berisi 40 kueri sintetis yang dibangkitkan dengan biji acak 42. Setiap baris memakai centroid koordinat suatu kota–kecamatan (syarat ≥ 5 merchant, sama seperti antarmuka bagian 3). Ke-18 kota pada katalog terwakili.

Kolom:

| Kolom | Arti |
| --- | --- |
| `id` | Pengenal kueri (`Q01`–`Q40`) |
| `kota`, `kecamatan` | Lokasi acuan |
| `lat`, `lon` | Centroid merchant di kecamatan itu |
| `radius_km` | Radius filter keras |
| `budget_maks` | Level harga maksimum (1–4) |
| `rating_min` | Ambang rating (0 = tanpa filter rating) |
| `kategori` | Preferensi, dipisah `\|`; kosong = tidak memilih kategori |
| `k` | Ukuran daftar yang diminta pada skenario (metrik @5 dan @10 tetap dihitung untuk semua kueri) |
| `catatan` | Alasan skenario dimasukkan (demonstrasi TK1, radius ketat, kategori jarang, dsb.) |

`Q01` adalah kasus demonstrasi laporan TK1: Kota Depok – Beji, Bakmie, radius 5 km, budget 2, rating ≥ 4,5.

Hasil metrik **tidak** disimpan di folder ini; lihat `reports/evaluasi_offline/` setelah `python scripts/evaluasi_offline.py` dijalankan.

## Penilaian responden (bagian 5)

Penilaian manusia **tidak** ada di berkas contoh. Jawaban nyata tersimpan di `hasil/` (diabaikan Git) lewat tab **Evaluasi Pengguna** pada aplikasi.

| Berkas | Isi |
| --- | --- |
| `contoh_penilaian_relevansi.csv` | **DATA TIRUAN** untuk uji unit dan demonstrasi skrip. Bukan hasil responden. Setiap baris bertanda `sumber=CONTOH_BUKAN_DATA_NYATA` dan kode `CONTOH*`. |
| `contoh_jawaban_sus.csv` | **DATA TIRUAN** jawaban SUS. Kaidah yang sama. |
| `templat_penilaian_relevansi.csv` / `templat_sus.csv` | Kepala kolom siap diisi manual atau diunggah ke Google Sheets. |
| `lembar/` | Lembar cadangan siap cetak (dibuat `scripts/buat_lembar_penilaian.py`). |
| `hasil/` | Jawaban responden nyata (tidak di-commit). |

Menghitung metrik dari data tiruan (untuk memastikan skrip berjalan):

```bash
python scripts/hitung_relevansi.py --contoh
python scripts/hitung_sus.py --contoh
```

Tanpa `--contoh`, skrip hanya membaca `hasil/` dan menolak menganggap berkas `CONTOH_*` sebagai hasil resmi (tetap menampilkan peringatan jika terdeteksi).
