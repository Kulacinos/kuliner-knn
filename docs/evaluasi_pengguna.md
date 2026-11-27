# Panduan evaluasi pengguna (bagian 5)

Sasaran: responden berusia 18–25 tahun, sesuai laporan TK1. Ditargetkan paling sedikit 20 orang (NFR-02). Setiap orang mengisi satu atau dua skenario penilaian relevansi plus satu kuesioner SUS.

## Alur untuk responden

1. Buka aplikasi (`streamlit run app.py`), tab **Rekomendasi**.
2. Cari rekomendasi (pilih kota/kecamatan atau titik, atur radius/budget/rating/kategori, tekan **Cari Rekomendasi**). Lihat daftar, peta, dan rincian skor (“Mengapa direkomendasikan?”).
3. Coba tab **Cari Nama** (misalnya kata “gacoan”).
4. Buka tab **Evaluasi Pengguna**.
5. Isi **kode responden** yang diberikan petugas (misalnya `R01`). Jangan memakai kode yang diawali `CONTOH`.
6. Pada **Penilaian relevansi**, pilih skenario, tekan **Tampilkan daftar penilaian**, beri nilai 0/1/2 pada setiap tempat, lalu **Simpan penilaian**. Ulangi untuk skenario kedua jika diminta.
7. Pada **Kuesioner SUS**, jawab 10 pernyataan (skala 1–5) dengan kode yang sama, lalu simpan. Skor individu tampil setelah pengiriman; rata-rata kelompok dihitung kemudian.

Daftar penilaian adalah gabungan *Top-10* metode yang dibandingkan (bawaan: jarak saja vs skor penuh), diacak, tanpa label metode — sesuai Subbab 3.8.1.

Jawaban tersimpan di `data/evaluasi/hasil/` (CSV dan SQLite) pada komputer yang menjalankan aplikasi.

## Alur untuk petugas

Setelah sesi selesai:

```bash
python scripts/hitung_relevansi.py
python scripts/hitung_sus.py
```

Luaran ada di `reports/evaluasi_pengguna/`. Precision@10 menganggap nilai 1 dan 2 sebagai relevan; NDCG@10 memakai skala 0–2. Target SUS: rata-rata ≥ 70 (acceptable).

## Cadangan kertas / Google Form

Jika aplikasi tidak bisa dipakai di lokasi uji, buat lembar:

```bash
python scripts/buat_lembar_penilaian.py
```

Berkas di `data/evaluasi/lembar/` dapat dicetak atau diunggah ke Google Sheets. Kepala kolom kosong juga ada di `data/evaluasi/templat_*.csv`. Setelah diisi, salin ke `data/evaluasi/hasil/` dengan skema kolom yang sama, lalu jalankan skrip hitung.

## Peringatan penting

`data/evaluasi/contoh_penilaian_relevansi.csv` dan `contoh_jawaban_sus.csv` adalah **DATA TIRUAN** untuk menguji perangkat lunak. Skrip `hitung_*.py --contoh` akan menampilkan banner peringatan. Jangan memasukkan angkanya ke laporan hasil TK2.
