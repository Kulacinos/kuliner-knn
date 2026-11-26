# Sistem Rekomendasi Kuliner KNN Berbasis Lokasi, Harga, Rating, dan Kategori untuk Pengguna Dewasa Muda di Jabodetabek dan Bandung

Tugas Kelompok 2 (TK2) — Sains Data, Program Studi Informatika, Universitas Udayana.

**Status: bagian 2 dari 7** (struktur repositori, dataset, loader SQLite, dan mesin rekomendasi).

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
```

Windows (PowerShell):

```powershell
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python scripts\load_db.py
python -m pytest
```

Linux / macOS:

```bash
source .venv/bin/activate
pip install -r requirements.txt
python scripts/load_db.py
python -m pytest
```

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
  src/kuliner/              paket Python
    config.py               jalur, URL SQLite, konstanta bobot
    preprocessing.py        pembersihan mentah → bersih (10.261 baris)
    db.py                   model SQLAlchemy + fungsi muat
    geo.py                  Haversine dan filter radius
    recommender.py          filter keras + KNN jarak berbobot
  scripts/load_db.py        CLI membangun data/kuliner.db
  scripts/demo_rekomendasi.py  contoh kueri (Monas / Beji)
  tests/                    uji pytest
```

Kategori disimpan dua cara: kolom teks `kategori` pada tabel `restoran` (dipisah `|`, sama seperti CSV) dan tabel normalisasi `kategori` + `restoran_kategori`. Mesin rekomendasi membaca katalog dari SQLite jika `data/kuliner.db` ada, dan jatuh ke CSV jika belum.
