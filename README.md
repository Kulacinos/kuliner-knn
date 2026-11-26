# Sistem Rekomendasi Kuliner KNN Berbasis Lokasi, Harga, Rating, dan Kategori untuk Pengguna Dewasa Muda di Jabodetabek dan Bandung

Tugas Kelompok 2 (TK2) — Sains Data, Program Studi Informatika, Universitas Udayana.

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

## Rancangan yang sudah ditetapkan 

Rekomendasi bersifat *content-based nearest-neighbour retrieval* (bukan klasifikasi). Filter keras: radius Haversine, anggaran (`price_level` maksimum), dan rating minimum. Rating 0 pada data mentah berarti **belum dinilai**, bukan rating buruk. Jarak berbobot:

- lokasi \(d/R\), bobot 0,35
- kategori \(1 - \mathrm{Jaccard}\), bobot 0,30
- rating (selisih satu arah terhadap rating terbaik), bobot 0,20
- harga \((p-1)/3\), bobot 0,15

## Struktur folder

```
kuliner-knn/
  data/raw/                 CSV mentah
  data/processed/           CSV bersih
  src/kuliner/              paket Python
    config.py               jalur, URL SQLite, konstanta bobot
    preprocessing.py        pembersihan mentah → bersih (10.261 baris)
    db.py                   model SQLAlchemy + fungsi muat
  scripts/load_db.py        CLI membangun data/kuliner.db
  tests/                    uji pytest
```

Kategori disimpan dua cara: kolom teks `kategori` pada tabel `restoran` (dipisah `|`, sama seperti CSV) dan tabel normalisasi `kategori` + `restoran_kategori` untuk filter
