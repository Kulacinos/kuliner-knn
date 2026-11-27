# Sistem Rekomendasi Kuliner KNN Berbasis Lokasi, Harga, Rating, dan Kategori untuk Pengguna Dewasa Muda di Jabodetabek dan Bandung

Tugas Kelompok 2 (TK2) — Sains Data, Program Studi Informatika, Universitas Udayana.

**Status: bagian 5 dari 7** (struktur repositori, dataset, loader SQLite, mesin rekomendasi, antarmuka Streamlit + peta Folium, evaluasi offline, alat evaluasi pengguna, dan uji black-box).

## Anggota kelompok

| Nama | NIM |
| --- | --- |
| Ketut Indhira Ayu Maheswari | 2408561010 |
| Ida Ayu Prami Suari | 2408561040 |
| Kadek Ezra Mahanaim | 2408561052 |
| I Kadek Dillon Satria Prabawa | 2408561141 |

Dosen pengampu: I Made Satria Bimantara, S.Kom., M.Kom.

## Dataset

- Sumber: I. Narsa, *GoFood Merchant on Jabodetabek and Bandung*, Kaggle, diambil Februari 2024.
- Tautan: <https://www.kaggle.com/datasets/iannarsa/gofood-merchant-on-jabodetabek-and-bandung>
- Lisensi di halaman Kaggle: **Unknown** (tidak dicantumkan secara spesifik). Data hanya dipakai untuk keperluan akademik nonkomersial, sumbernya selalu disitasi, dan aplikasi tidak akan menyediakan unduhan massal.
- Isi folder: `data/raw/` (CSV mentah, 10.372 baris) dan `data/processed/` (hasil pembersihan TK1, 10.261 baris). File `data/kuliner.db` tidak diunggah ke Git; bangun sendiri dengan skrip di bawah.

## Menjalankan proyek

Python 3.10 atau lebih baru. Di folder ini:

```bash
python -m venv .venv
```

Windows (Command Prompt):

```bat
.venv\Scripts\activate
pip install -r requirements.txt
python scripts\load_db.py
python -m pytest
streamlit run app.py
```

Windows (PowerShell):

```powershell
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python scripts\load_db.py
python -m pytest
streamlit run app.py
```

Linux / macOS:

```bash
source .venv/bin/activate
pip install -r requirements.txt
python scripts/load_db.py
python -m pytest
streamlit run app.py
```

Setelah `streamlit run app.py`, buka alamat yang tampil di terminal (biasanya http://localhost:8501). Default form memakai contoh laporan TK1: Kota Depok – Beji, radius 5 km, budget level 2, rating ≥ 4,5, dan kategori Bakmie; tekan **Cari Rekomendasi** untuk melihat daftar dan peta. Waktu respons pencarian ditampilkan dan dibandingkan dengan batas NFR-01 (≤ 2 detik).

Skrip `scripts/load_db.py` bersifat idempotent: dijalankan berulang kali akan membangun ulang basis data yang sama (bukan menambah baris).

Demo mesin rekomendasi (bagian 2). Titik default di dekat Monas, Jakarta Pusat. Jika `kuliner.db` belum dibangun, katalog dibaca dari CSV bersih:

```bat
python scripts\demo_rekomendasi.py
python scripts\demo_rekomendasi.py --contoh beji
python scripts\demo_rekomendasi.py --lat -6.1754 --lon 106.8272 --budget 2 --rating-min 4.5 --kategori Bakmie
```

Atau dari Python:

```python
from kuliner.recommender import rekomendasi

hasil = rekomendasi(
    lat=-6.1754,
    lon=106.8272,
    radius_km=5,
    budget_maks=2,
    rating_min=4.5,
    kategori_pilihan=["Bakmie"],
    k=10,
)
print(hasil[["peringkat", "nama", "jarak_km", "skor"]])
```


Evaluasi offline (bagian 4). Skrip membaca 40 skenario di `data/evaluasi/skenario.csv`, membandingkan S1–S4 dan baseline rating, lalu menulis metrik serta grafik ke `reports/evaluasi_offline/`. Notebook `notebooks/TK2_Evaluasi_Offline.ipynb` menampilkan hasil yang sudah dijalankan.

```bat
python scripts\evaluasi_offline.py
```

```bash
python scripts/evaluasi_offline.py
```

Precision@K dan NDCG@K pada laporan ini memakai **relevansi proksi** (Subbab 3.8.1 TK1), bukan penilaian pengguna. Jangan dipakai sebagai klaim kualitas akhir; penilaian responden menyusul di bagian 5.


Evaluasi pengguna dan uji black-box (bagian 5). Tab **Evaluasi Pengguna** pada aplikasi menampilkan daftar gabungan Top-10 (urutan acak, tanpa label metode) untuk dinilai 0/1/2, plus kuesioner SUS 10 butir. Jawaban tersimpan di `data/evaluasi/hasil/` (tidak diunggah ke Git).

```bat
python scripts\hitung_relevansi.py
python scripts\hitung_sus.py
python scripts\uji_black_box.py
```

```bash
python scripts/hitung_relevansi.py
python scripts/hitung_sus.py
python scripts/uji_black_box.py
```

Berkas `data/evaluasi/contoh_*.csv` adalah **data tiruan** untuk menguji skrip (`--contoh`), bukan hasil responden. Panduan lengkap: `docs/evaluasi_pengguna.md`. Tabel black-box: `docs/black_box_testing.md`.

## Rancangan yang sudah ditetapkan (dari TK1)

Rekomendasi bersifat *content-based nearest-neighbour retrieval* (bukan klasifikasi). Filter keras: radius Haversine, anggaran (`price_level` maksimum), dan rating minimum. Rating 0 pada data mentah berarti **belum dinilai**, bukan rating buruk. Jarak berbobot (sudah diimplementasikan di `src/kuliner/recommender.py`):

- lokasi \(d/R\), bobot 0,35
- kategori \(1 - \mathrm{Jaccard}\), bobot 0,30
- rating (selisih satu arah terhadap rating terbaik), bobot 0,20
- harga \((p-1)/3\), bobot 0,15

Tumpukan: Python, Streamlit, folium, SQLAlchemy, SQLite; deployment ke Streamlit Community Cloud menyusul di bagian 6.

## Isi repositori saat ini

```
kuliner-knn/
  data/raw/                 CSV mentah
  data/processed/           CSV bersih
  data/evaluasi/            40 skenario kueri (biji 42)
  src/kuliner/              paket Python
    config.py               jalur, URL SQLite, konstanta bobot
    preprocessing.py        pembersihan mentah → bersih (10.261 baris)
    db.py                   model SQLAlchemy + fungsi muat
    geo.py                  Haversine dan filter radius
    recommender.py          filter keras + KNN jarak berbobot
    ui_helpers.py           label, validasi, peta Folium, ringkasan hasil
    evaluasi.py             Precision@K, NDCG@K, proksi, Wilcoxon
    sus.py                  10 butir SUS dan penskoran (Persamaan 2.7)
    penilaian.py            penilaian relevansi 0/1/2 dan metrik manusia
    halaman_evaluasi.py     tab Streamlit Evaluasi Pengguna
    black_box.py            katalog dan pelaksana uji black-box
  app.py                    antarmuka Streamlit (akar repo, siap Cloud)
  .streamlit/config.toml    tema hijau sesuai mockup TK1
  scripts/load_db.py        CLI membangun data/kuliner.db
  scripts/demo_rekomendasi.py  contoh kueri (Monas / Beji)
  scripts/evaluasi_offline.py  menjalankan evaluasi dan menulis laporan
  scripts/hitung_relevansi.py  P@10 dan NDCG@10 dari penilaian manusia
  scripts/hitung_sus.py        ringkasan skor SUS
  scripts/uji_black_box.py     menjalankan kasus black-box dan menulis tabel
  scripts/buat_lembar_penilaian.py  lembar cadangan (cetak / Sheets)
  notebooks/TK2_Evaluasi_Offline.ipynb  narasi evaluasi offline (bagian 4)
  reports/evaluasi_offline/ CSV, JSON, dan grafik metrik proksi
  reports/evaluasi_pengguna/  metrik dari penilaian manusia (setelah uji)
  reports/black_box/        hasil uji black-box
  docs/evaluasi_pengguna.md panduan responden dan petugas
  docs/black_box_testing.md tabel kasus (aktual dan status terisi)
  tests/                    uji pytest
```

Kategori disimpan dua cara: kolom teks `kategori` pada tabel `restoran` (dipisah `|`, sama seperti CSV) dan tabel normalisasi `kategori` + `restoran_kategori`. Mesin rekomendasi membaca katalog dari SQLite jika `data/kuliner.db` ada, dan jatuh ke CSV jika belum.
