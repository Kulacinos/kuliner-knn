# Deployment ke Streamlit Community Cloud

Dokumen ini melengkapi bagian deployment di `README.md`. Aplikasi dirancang agar dapat dijalankan dari repositori GitHub [Kulacinos/kuliner-knn](https://github.com/Kulacinos/kuliner-knn) dengan berkas utama `app.py`.

## Prasyarat

- Repositori sudah diunggah ke GitHub dan berisi `app.py`, `requirements.txt`, paket `src/kuliner/`, `data/processed/gofood_clean.csv`, dan `.streamlit/config.toml`.
- Akun GitHub yang punya akses tulis ke repositori (atau repositori publik).
- `data/kuliner.db` **tidak** perlu diunggah (terdaftar di `.gitignore`). Aplikasi akan membangunnya dari CSV pada start pertama.
- Tidak ada rahasia yang wajib diisi: `.streamlit/secrets.toml` tidak dipakai pada versi ini.

## Langkah deploy

1. Buka <https://share.streamlit.io> dan masuk (*Sign in*) dengan GitHub. Izinkan Streamlit mengakses repositori jika diminta.
2. Di pojok kanan atas, klik **Create app**.
3. Ketika ditanya apakah aplikasi sudah ada, pilih **Yup, I have an app**.
4. Isi formulir:
   - *Repository:* `Kulacinos/kuliner-knn`
   - *Branch:* `main`
   - *Main file path:* `app.py`
   - *App URL* (opsional): subdomain, sehingga alamat menjadi `https://<subdomain>.streamlit.app`.
5. Klik **Advanced settings**:
   - *Python version:* pilih **3.13**. Ini versi yang dipakai saat dependensi diuji. **Jangan mengandalkan `runtime.txt`** — Streamlit Community Cloud mengatur versi Python dari menu ini, bukan dari berkas di repo. Default platform saat ini adalah 3.12; jika terlupa diganti, dependensi pin biasanya masih terpasang, tetapi 3.13 adalah pilihan yang disarankan.
   - *Secrets:* biarkan kosong (tidak diperlukan).
   - Simpan.
6. Klik **Deploy**. Tunggu instalasi paket (beberapa menit). Log di sisi kanan hanya terlihat oleh orang yang punya akses tulis ke repo.
7. Start pertama menampilkan spinner *Menyiapkan basis data…* sambil membangun `data/kuliner.db` dari CSV bersih. Start berikutnya memakai basis data yang sudah ada (selama instans tidak dihapus atau di-reboot ke filesystem kosong).
8. Uji cepat di URL publik: kueri default Kota Depok–Beji / Bakmie harus menampilkan Bakmi Roxy di peringkat 1, peta, dan waktu respons ≤ 2 detik.

Setelah berhasil, tambahkan URL itu ke README (bagian “URL aplikasi”).

## Perilaku khusus Cloud

- **Filesystem sementara.** Berkas yang ditulis aplikasi (termasuk `kuliner.db` dan `data/evaluasi/hasil/`) dapat hilang saat aplikasi di-reboot, di-deploy ulang, atau instans diganti. Katalog akan dibangun lagi otomatis dari CSV. **Jawaban evaluasi pengguna tidak dibangun ulang** — petugas harus mengunduh CSV lewat tab Evaluasi Pengguna setelah setiap sesi.
- **Resource.** Community Cloud punya batas memori dan waktu undur (*hibernation*) jika aplikasi sepi. Kunjungan pertama setelah tidur bisa lebih lama.
- **Tanpa GPS browser.** Lokasi tetap dipilih lewat kota/kecamatan, koordinat, atau klik peta.

## Mengubah versi Python setelah deploy

Versi Python tidak dapat diganti pada instans yang sudah berjalan. Catat subdomain, repo/branch/berkas utama, lalu hapus aplikasi dan deploy ulang dengan versi yang diinginkan di Advanced settings (lihat [dokumentasi resmi](https://docs.streamlit.io/deploy/streamlit-community-cloud/manage-your-app/upgrade-python)).

## Pemecahan masalah

| Gejala | Penyebab yang sering | Yang dicoba |
| --- | --- | --- |
| Deploy gagal saat `pip install` | Versi Python tidak cocok dengan pin di `requirements.txt`, atau jaringan/cache Cloud | Di Advanced settings pilih Python 3.13, lalu reboot atau hapus dan deploy ulang. Cek log untuk paket mana yang gagal. |
| Aplikasi boot lama / spinner basis data terus tampil | Start pertama sedang membangun SQLite dari 10.261 baris, atau CSV tidak ketemu | Tunggu 1–2 menit. Pastikan `data/processed/gofood_clean.csv` ada di repo (bukan hanya `data/raw/`). |
| Error `katalog` / `FileNotFoundError` untuk CSV | Jalur relatif salah atau folder `data/processed` tidak terunggah | Jalur dihitung dari akar repo (`requirements.txt` + folder `data/`). Jangan memindahkan `app.py` ke subfolder tanpa menyesuaikan struktur. |
| Jawaban SUS/relevansi hilang | Reboot/deploy Cloud menghapus `data/evaluasi/hasil/` | Unduh CSV segera setelah sesi. Simpan di komputer petugas, lalu salin kembali jika perlu. |
| Peta kosong / modul `streamlit_folium` | Dependensi tidak terpasang | Pastikan `folium` dan `streamlit-folium` ada di `requirements.txt` (sudah dipin). Reboot aplikasi. |
| Tema atau toolbar tidak seperti lokal | `config.toml` tidak terbaca | Berkas harus berada di `.streamlit/config.toml` (bukan di subfolder lain). |
| GitHub Actions merah | Uji gagal di PR | Jalankan `python -m pytest` secara lokal dengan Python 3.13 dan pin yang sama. |
| “App isn’t loading” / hibernasi | Instans tidur karena sepi | Muat ulang halaman; boot ulang bisa memakan waktu. |
| Hak akses repo | Streamlit tidak melihat repositori privat | Beri akses GitHub ke aplikasi Streamlit, atau buat repo publik untuk masa evaluasi. |

Dokumentasi resmi: [Deploy your app](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy).
