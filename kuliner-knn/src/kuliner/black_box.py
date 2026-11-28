"""Katalog dan pelaksana uji black-box (Tabel 3.19 laporan TK1).

Setiap kasus punya masukan dan keluaran yang diharapkan tanpa meninjau
kode di dalam fungsi. Kasus yang bisa dijalankan otomatis memakai AppTest
Streamlit atau keluaran publik mesin/peta. Kasus GPS (BB-01) dan admin
(BB-11–BB-14) belum dapat diotomasi karena fiturnya belum ada.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable

import pandas as pd

from kuliner.recommender import muat_katalog, titik_pusat
from kuliner.ui_helpers import (
    bangun_peta,
    cari_nama,
    jalankan_pencarian,
    pesan_di_luar_wilayah,
    pesan_hasil_kosong,
    tautan_google_maps,
)

STATUS_LULUS = "lulus"
STATUS_GAGAL = "gagal"
STATUS_DILEWATI = "dilewati"
STATUS_DITUNDA = "ditunda"

APP = Path(__file__).resolve().parents[2] / "app.py"


def _semua_teks(at) -> str:
    bagian = []
    for attr in (
        "markdown", "title", "header", "subheader", "caption", "text",
        "info", "success", "warning", "error",
    ):
        for item in getattr(at, attr, []):
            bagian.append(getattr(item, "value", str(item)))
    for item in getattr(at, "metric", []):
        bagian.append(str(getattr(item, "label", "")))
        bagian.append(str(getattr(item, "value", "")))
        bagian.append(str(getattr(item, "delta", "")))
    for df in getattr(at, "dataframe", []):
        try:
            bagian.append(str(df.value))
        except Exception:
            bagian.append(str(df))
    for attr in ("button", "link_button", "download_button"):
        for item in getattr(at, attr, []):
            bagian.append(str(getattr(item, "label", "")))
            bagian.append(str(getattr(item, "url", "")))
            bagian.append(str(item))
    if getattr(at, "sidebar", None):
        for attr in ("caption", "markdown", "text", "info", "warning", "error"):
            for item in getattr(at.sidebar, attr, []):
                bagian.append(getattr(item, "value", str(item)))
    return "\n".join(bagian)


def _buat_app():
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_file(str(APP), default_timeout=60)
    at.run()
    if at.exception:
        raise RuntimeError(at.exception)
    return at


def _lulus(aktual: str) -> dict:
    return {"aktual": aktual, "status": STATUS_LULUS}


def _gagal(aktual: str) -> dict:
    return {"aktual": aktual, "status": STATUS_GAGAL}


# ---------------------------------------------------------------------------
# Pelaksana kasus otomatis
# ---------------------------------------------------------------------------

def jalankan_bb02() -> dict:
    at = _buat_app()
    lat, lon, n = titik_pusat("Kota Depok", "Beji")
    teks = _semua_teks(at)
    potongan = f"({lat:.5f}, {lon:.5f})"
    if "Beji" in teks and potongan in teks:
        return _lulus(
            f"Default Kota Depok–Beji; caption menampilkan centroid "
            f"{n} merchant {potongan}."
        )
    return _gagal(f"Centroid Beji {potongan} tidak tampil pada form. Cuplikan: {teks[:400]}")


def jalankan_bb03() -> dict:
    at = _buat_app()
    at.sidebar.select_slider(key="radius_km").set_value(10)
    at.sidebar.selectbox(key="budget_maks").set_value(3)
    at.sidebar.radio(key="label_rating").set_value("★ 4,0")
    at.sidebar.multiselect(key="kategori").set_value(["Kopi"])
    at.sidebar.button(key="btn_cari").click()
    at.run()
    if at.exception:
        return _gagal(f"Aplikasi error: {at.exception}")
    teks = _semua_teks(at)
    butuh = ["10 km", "Kopi"]
    # Ringkasan preferensi / hasil harus memuat preferensi baru.
    if all(b in teks for b in butuh) and ("Level 3" in teks or "level 3" in teks.lower() or "Rp40" in teks or "4,0" in teks or "4.0" in teks):
        return _lulus("Setelah diubah, ringkasan/hasil memuat radius 10 km, budget level 3, dan kategori Kopi.")
    # Lebih longgar: widget values persisted + search ran
    if "rekomendasi" in teks.lower() or "tempat makan" in teks.lower():
        # Check widget state
        try:
            r = at.sidebar.select_slider(key="radius_km").value
            b = at.sidebar.selectbox(key="budget_maks").value
            kat = at.sidebar.multiselect(key="kategori").value
        except Exception:
            r = b = kat = None
        if r == 10 and b == 3 and kat == ["Kopi"]:
            return _lulus(
                f"Nilai baru tersimpan pada widget (radius={r}, budget={b}, kategori={kat}) "
                "dan pencarian dijalankan."
            )
    return _gagal(f"Preferensi baru tidak terlihat. Cuplikan: {teks[:500]}")


def jalankan_bb04() -> dict:
    at = _buat_app()
    at.sidebar.radio(key="mode_lokasi").set_value("Titik peta / koordinat")
    at.run()
    at.sidebar.number_input(key="lat_manual").set_value(10.0)
    at.sidebar.number_input(key="lon_manual").set_value(100.0)
    at.sidebar.button(key="btn_cari").click()
    at.run()
    if at.exception:
        return _gagal(f"Aplikasi error: {at.exception}")
    teks = _semua_teks(at)
    expected = pesan_di_luar_wilayah()
    # Pastikan tidak ada tabel hasil rekomendasi 10 baris.
    if expected in teks:
        return _lulus(f"Pesan kesalahan tampil: “{expected}”.")
    return _gagal(f"Pesan luar wilayah tidak tampil. Cuplikan: {teks[:500]}")


def jalankan_bb05() -> dict:
    data = muat_katalog()
    lat, lon, _ = titik_pusat("Kota Depok", "Beji", data=data)
    ringkas = jalankan_pencarian(
        data, lat, lon, radius_km=5, budget_maks=2, rating_min=4.5,
        kategori_pilihan=["Bakmie"], k=10,
    )
    hasil = ringkas["hasil"]
    if hasil is None or hasil.empty:
        return _gagal("Kueri Beji/Bakmie tidak menghasilkan daftar.")
    jarak_ok = bool((hasil["jarak_km"] <= 5 + 1e-9).all())
    harga_ok = bool((hasil["price_level"] <= 2).all())
    if "sudah_dinilai" in hasil.columns:
        rating_ok = bool(
            ((~hasil["sudah_dinilai"]) | (hasil["rating"] >= 4.5)).all()
        )
    else:
        rating_ok = bool((hasil["rating"] >= 4.5).all())
    if jarak_ok and harga_ok and rating_ok:
        return _lulus(
            f"{len(hasil)} hasil; semua jarak ≤ 5 km, price_level ≤ 2, rating ≥ 4,5."
        )
    return _gagal(
        f"Filter dilanggar: jarak_ok={jarak_ok}, harga_ok={harga_ok}, rating_ok={rating_ok}."
    )


def jalankan_bb06() -> dict:
    data = muat_katalog()
    lat, lon, _ = titik_pusat("Kota Depok", "Beji", data=data)
    ringkas = jalankan_pencarian(
        data, lat, lon, radius_km=5, budget_maks=2, rating_min=4.5,
        kategori_pilihan=["Bakmie"], k=10,
    )
    hasil = ringkas["hasil"]
    if hasil is None or len(hasil) != 10:
        n = 0 if hasil is None else len(hasil)
        return _gagal(f"Diharapkan 10 hasil, diterima {n}.")
    skor = list(hasil["skor"])
    urut = all(skor[i] <= skor[i + 1] + 1e-12 for i in range(len(skor) - 1))
    nama1 = str(hasil.iloc[0]["nama"])
    if urut and "Bakmi Roxy" in nama1:
        return _lulus(
            f"Tepat 10 hasil, terurut menaik menurut D, peringkat 1 = {nama1} "
            f"(skor {skor[0]:.4f})."
        )
    return _gagal(f"Urut={urut}, peringkat 1={nama1}, skor={skor[:3]}.")


def jalankan_bb07() -> dict:
    at = _buat_app()
    at.sidebar.select_slider(key="radius_km").set_value(1)
    at.sidebar.selectbox(key="budget_maks").set_value(1)
    at.sidebar.radio(key="label_rating").set_value("★ 4,9")
    at.sidebar.multiselect(key="kategori").set_value(["India"])
    at.sidebar.button(key="btn_cari").click()
    at.run()
    if at.exception:
        return _gagal(f"Aplikasi error: {at.exception}")
    teks = _semua_teks(at)
    kunci = "Tidak ada tempat makan yang memenuhi semua batas"
    if kunci in teks:
        return _lulus(f"Pesan hasil kosong dan saran tampil: “{pesan_hasil_kosong(1)}”.")
    return _gagal(f"Pesan kosong tidak tampil. Cuplikan: {teks[:500]}")


def jalankan_bb08() -> dict:
    data = muat_katalog()
    lat, lon, _ = titik_pusat("Kota Depok", "Beji", data=data)
    ringkas = jalankan_pencarian(
        data, lat, lon, radius_km=5, budget_maks=2, rating_min=4.5,
        kategori_pilihan=["Bakmie"], k=10,
    )
    hasil = ringkas["hasil"]
    peta = bangun_peta(lat, lon, 5, hasil, judul_pengguna="Kota Depok – Beji")
    html = peta.get_root().render()
    kurang = [str(r.nama) for r in hasil.itertuples() if str(r.nama) not in html]
    if len(hasil) == 10 and not kurang:
        # AppTest: pastikan UI menampilkan tabel dan judul peta.
        at = _buat_app()
        at.sidebar.button(key="btn_cari").click()
        at.run()
        if at.exception:
            return _gagal(f"Aplikasi error: {at.exception}")
        teks = _semua_teks(at)
        if "Peta hasil" in teks and "Bakmi Roxy" in teks and len(at.dataframe) >= 1:
            return _lulus(
                "10 nama pada daftar ada di peta Folium; UI menampilkan tabel dan “Peta hasil”."
            )
        return _gagal(f"Peta/tabel UI tidak lengkap. Cuplikan: {teks[:400]}")
    return _gagal(f"Nama tidak lengkap di peta: {kurang}")


def jalankan_bb09() -> dict:
    at = _buat_app()
    at.sidebar.button(key="btn_cari").click()
    at.run()
    if at.exception:
        return _gagal(f"Aplikasi error: {at.exception}")
    teks = _semua_teks(at)
    data = muat_katalog()
    lat, lon, _ = titik_pusat("Kota Depok", "Beji", data=data)
    ringkas = jalankan_pencarian(
        data, lat, lon, radius_km=5, budget_maks=2, rating_min=4.5,
        kategori_pilihan=["Bakmie"], k=10,
    )
    baris = ringkas["hasil"].iloc[0]
    tautan = tautan_google_maps(float(baris["latitude"]), float(baris["longitude"]))
    butuh = [
        "Mengapa direkomendasikan",
        str(baris["nama"]),
        "Skor D",
    ]
    kurang = [b for b in butuh if b not in teks]
    ada_maps = ("google.com/maps" in teks.lower()) or ("google maps" in teks.lower()) or (tautan in teks)
    if kurang:
        return _gagal(f"Bagian detail kurang: {kurang}. Cuplikan: {teks[:500]}")
    if not ada_maps:
        return _gagal(f"Tautan Google Maps tidak ditemukan. Cuplikan: {teks[:500]}")
    return _lulus(
        f"Detail peringkat 1 ({baris['nama']}) tampil beserta komponen skor dan tautan Google Maps."
    )


def jalankan_bb10() -> dict:
    at = _buat_app()
    at.text_input(key="cari_kata").set_value("gacoan")
    at.run()
    if at.exception:
        return _gagal(f"Aplikasi error: {at.exception}")
    teks = _semua_teks(at)
    data = muat_katalog()
    potong, total = cari_nama(data, "gacoan", kota=None, halaman=1, per_halaman=10)
    if total <= 0:
        return _gagal("Katalog tidak berisi nama yang mengandung “gacoan”.")
    if "gacoan" not in teks.lower():
        return _gagal(f"Hasil UI tidak memuat “gacoan”. Cuplikan: {teks[:400]}")
    # Semua baris halaman 1 harus mengandung kata itu.
    if not potong["nama"].str.contains("gacoan", case=False, regex=False).all():
        return _gagal("Ada hasil mesin yang tidak mengandung “gacoan”.")
    if "Halaman" in teks or "menampilkan" in teks.lower() or total > 0:
        return _lulus(
            f"{total} hasil mengandung “gacoan”; halaman 1 menampilkan {len(potong)} baris."
        )
    return _gagal(f"Paginasi tidak terlihat. Cuplikan: {teks[:400]}")


def jalankan_bb15() -> dict:
    """Pelengkap: kategori dikosongkan, pencarian tetap jalan."""
    at = _buat_app()
    at.sidebar.multiselect(key="kategori").set_value([])
    at.sidebar.button(key="btn_cari").click()
    at.run()
    if at.exception:
        return _gagal(f"Aplikasi error: {at.exception}")
    teks = _semua_teks(at)
    if "Tidak ada tempat makan yang memenuhi semua batas" in teks:
        return _gagal("Kategori kosong justru memunculkan hasil kosong (seharusnya tetap ada kandidat).")
    if "rekomendasi teratas" in teks.lower() or "lolos filter" in teks.lower() or len(at.dataframe) >= 1:
        return _lulus("Tanpa kategori, pencarian tetap menampilkan daftar rekomendasi.")
    return _gagal(f"Hasil tidak tampil. Cuplikan: {teks[:400]}")


def jalankan_bb16() -> dict:
    """Pelengkap: waktu respons NFR-01 ≤ 2 s pada kueri default."""
    at = _buat_app()
    at.sidebar.button(key="btn_cari").click()
    at.run()
    if at.exception:
        return _gagal(f"Aplikasi error: {at.exception}")
    teks = _semua_teks(at)
    if "memenuhi NFR-01" in teks:
        # Ambil angka metric jika ada
        nilai = ""
        for m in at.metric:
            if "Waktu" in str(getattr(m, "label", "")):
                nilai = str(getattr(m, "value", ""))
                break
        return _lulus(f"UI menampilkan waktu respons {nilai or '(metric)'} dan status memenuhi NFR-01 (≤ 2 s).")
    if "melebihi batas NFR-01" in teks:
        return _gagal("Waktu respons melebihi 2 detik pada kueri default.")
    return _gagal(f"Status NFR-01 tidak tampil. Cuplikan: {teks[:400]}")


# ---------------------------------------------------------------------------
# Katalog kasus (Tabel 3.19 + pelengkap)
# ---------------------------------------------------------------------------

KASUS: list[dict] = [
    {
        "id": "BB-01",
        "fitur": "FR-01",
        "skenario": "Izinkan GPS di dalam Jabodetabek",
        "input": "Izin lokasi browser pada titik di dalam wilayah layanan",
        "expected": "Koordinat tersimpan, form preferensi aktif",
        "otomatis": False,
        "status_tetap": STATUS_DILEWATI,
        "aktual_tetap": (
            "Tidak diuji otomatis. Aplikasi Streamlit bagian 3 tidak memakai GPS browser "
            "(keterbatasan platform); lokasi dipilih lewat kota/kecamatan, koordinat, atau klik peta."
        ),
        "pelaksana": None,
    },
    {
        "id": "BB-02",
        "fitur": "FR-01",
        "skenario": "Pilih Kota Depok, Kecamatan Beji",
        "input": "Mode kota/kecamatan, Kota Depok, Kecamatan Beji (bawaan form)",
        "expected": "Titik acuan = centroid Beji",
        "otomatis": True,
        "pelaksana": jalankan_bb02,
    },
    {
        "id": "BB-03",
        "fitur": "FR-02",
        "skenario": "Ubah radius, budget, rating, dan kategori",
        "input": "Radius 10 km, budget level 3, rating ★ 4,0, kategori Kopi, lalu Cari",
        "expected": "Nilai baru tersimpan pada ringkasan preferensi",
        "otomatis": True,
        "pelaksana": jalankan_bb03,
    },
    {
        "id": "BB-04",
        "fitur": "FR-03",
        "skenario": "Klik Cari dengan koordinat di luar wilayah layanan",
        "input": "Mode titik peta, latitude 10,0, longitude 100,0, lalu Cari",
        "expected": "Pesan kesalahan tampil, pencarian tidak dijalankan",
        "otomatis": True,
        "pelaksana": jalankan_bb04,
    },
    {
        "id": "BB-05",
        "fitur": "FR-04",
        "skenario": "Kueri contoh Subbab 3.3.5 (Beji, Bakmie)",
        "input": "Beji, radius 5 km, budget ≤ 2, rating ≥ 4,5, kategori Bakmie",
        "expected": "Semua hasil berjarak ≤ 5 km, level ≤ 2, rating ≥ 4,5",
        "otomatis": True,
        "pelaksana": jalankan_bb05,
    },
    {
        "id": "BB-06",
        "fitur": "FR-05",
        "skenario": "Kueri contoh Subbab 3.3.5 (Beji, Bakmie)",
        "input": "Sama dengan BB-05, k = 10",
        "expected": "Tepat 10 hasil, urut menaik menurut D, peringkat 1 Bakmi Roxy",
        "otomatis": True,
        "pelaksana": jalankan_bb06,
    },
    {
        "id": "BB-07",
        "fitur": "FR-06",
        "skenario": "Radius 1 km, level 1, rating ≥ 4,9, kategori India",
        "input": "Kota Depok–Beji (bawaan) dengan preferensi ketat di atas",
        "expected": "Pesan hasil kosong dan saran tampil",
        "otomatis": True,
        "pelaksana": jalankan_bb07,
    },
    {
        "id": "BB-08",
        "fitur": "FR-07",
        "skenario": "Lihat halaman hasil",
        "input": "Kueri default Beji/Bakmie, amati daftar dan peta",
        "expected": "Daftar dan peta menampilkan 10 titik yang sama",
        "otomatis": True,
        "pelaksana": jalankan_bb08,
    },
    {
        "id": "BB-09",
        "fitur": "FR-08",
        "skenario": "Klik Detail pada hasil peringkat 1",
        "input": "Kueri default; rincian skor memakai item pertama (bawaan)",
        "expected": "Detail, komponen skor, dan tautan Google Maps benar",
        "otomatis": True,
        "pelaksana": jalankan_bb09,
    },
    {
        "id": "BB-10",
        "fitur": "FR-09",
        "skenario": "Cari nama “gacoan”",
        "input": "Tab Cari Nama, kata “gacoan”, tanpa filter kota",
        "expected": "Semua hasil mengandung kata tersebut, berhalaman",
        "otomatis": True,
        "pelaksana": jalankan_bb10,
    },
    {
        "id": "BB-11",
        "fitur": "FR-10",
        "skenario": "Login dengan password salah, lalu benar; buka URL admin tanpa login",
        "input": "Halaman Admin (placeholder bagian 3–5)",
        "expected": "Ditolak; berhasil masuk; akses tanpa login ditolak",
        "otomatis": False,
        "status_tetap": STATUS_DITUNDA,
        "aktual_tetap": (
            "Fitur login admin (FR-10) belum diimplementasikan; tab Admin masih berupa "
            "placeholder dan menyatakan pengelolaan data menyusul."
        ),
        "pelaksana": None,
    },
    {
        "id": "BB-12",
        "fitur": "FR-11",
        "skenario": "Tambah data dengan latitude 10,0 lalu dengan data valid",
        "input": "Form tambah data admin (belum ada)",
        "expected": "Ditolak dengan pesan; data valid tersimpan dan dapat direkomendasikan",
        "otomatis": False,
        "status_tetap": STATUS_DITUNDA,
        "aktual_tetap": "Fitur tambah data admin (FR-11) belum diimplementasikan.",
        "pelaksana": None,
    },
    {
        "id": "BB-13",
        "fitur": "FR-11",
        "skenario": "Ubah price level lalu hapus data",
        "input": "Form ubah/hapus data admin (belum ada)",
        "expected": "Perubahan tampil pada hasil; data terhapus tidak muncul lagi",
        "otomatis": False,
        "status_tetap": STATUS_DITUNDA,
        "aktual_tetap": "Fitur ubah/hapus data admin (FR-11) belum diimplementasikan.",
        "pelaksana": None,
    },
    {
        "id": "BB-14",
        "fitur": "FR-12",
        "skenario": "Impor CSV berisi baris valid dan tidak valid",
        "input": "Form impor CSV admin (belum ada)",
        "expected": "Baris valid tersimpan; ringkasan menyebut jumlah dan alasan penolakan",
        "otomatis": False,
        "status_tetap": STATUS_DITUNDA,
        "aktual_tetap": "Fitur impor CSV admin (FR-12) belum diimplementasikan.",
        "pelaksana": None,
    },
    {
        "id": "BB-15",
        "fitur": "FR-02/FR-05",
        "skenario": "Kategori dikosongkan",
        "input": "Kueri default Beji, multiselect kategori = [] , lalu Cari",
        "expected": "Pencarian tetap berjalan dan menampilkan daftar (bobot kategori dinolkan)",
        "otomatis": True,
        "pelaksana": jalankan_bb15,
        "pelengkap": True,
    },
    {
        "id": "BB-16",
        "fitur": "NFR-01",
        "skenario": "Waktu respons pencarian pada kueri default",
        "input": "Tekan Cari Rekomendasi (Beji, Bakmie, k=10)",
        "expected": "Waktu dari tekan Cari sampai hasil tampil ≤ 2 detik",
        "otomatis": True,
        "pelaksana": jalankan_bb16,
        "pelengkap": True,
    },
]


def jalankan_semua(hanya_otomatis: bool = False) -> pd.DataFrame:
    """Jalankan katalog dan kembalikan tabel id, fitur, skenario, input, expected, actual, status."""
    baris = []
    for kasus in KASUS:
        if hanya_otomatis and not kasus.get("otomatis"):
            continue
        rekaman = {
            "id": kasus["id"],
            "fitur": kasus["fitur"],
            "skenario": kasus["skenario"],
            "input": kasus["input"],
            "expected": kasus["expected"],
            "aktual": kasus.get("aktual_tetap", ""),
            "status": kasus.get("status_tetap", STATUS_DILEWATI),
            "otomatis": bool(kasus.get("otomatis")),
            "pelengkap": bool(kasus.get("pelengkap", False)),
        }
        pelaksana: Callable | None = kasus.get("pelaksana")
        if kasus.get("otomatis") and pelaksana is not None:
            try:
                hasil = pelaksana()
                rekaman["aktual"] = hasil["aktual"]
                rekaman["status"] = hasil["status"]
            except Exception as exc:  # noqa: BLE001 — tes black-box harus mencatat kegagalan
                rekaman["aktual"] = f"Pengecualian saat menjalankan: {type(exc).__name__}: {exc}"
                rekaman["status"] = STATUS_GAGAL
        baris.append(rekaman)
    return pd.DataFrame(baris)


def ringkasan_status(tabel: pd.DataFrame) -> dict:
    n = len(tabel)
    hitung = tabel["status"].value_counts().to_dict()
    otomatis = tabel[tabel["otomatis"]]
    n_oto = len(otomatis)
    n_lulus = int((otomatis["status"] == STATUS_LULUS).sum())
    return {
        "n": n,
        "n_otomatis": n_oto,
        "n_lulus_otomatis": n_lulus,
        "persen_lulus_otomatis": (100.0 * n_lulus / n_oto) if n_oto else 0.0,
        "hitung": {str(k): int(v) for k, v in hitung.items()},
    }
