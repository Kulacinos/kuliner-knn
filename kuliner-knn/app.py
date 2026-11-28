#!/usr/bin/env python3
"""Aplikasi web Streamlit untuk sistem rekomendasi kuliner KNN.

Jalankan dari akar repositori::

    streamlit run app.py

Bagian 3 merampungkan FR-01 sampai FR-09 (lokasi, preferensi, pencarian,
hasil, detail skor, dan cari nama). Bagian 5 menambah tab Evaluasi Pengguna
(penilaian relevansi 0/1/2 dan kuesioner SUS). Bagian 6 menyiapkan
deployment ke Streamlit Community Cloud: basis data SQLite dibangun
otomatis dari CSV bersih jika `data/kuliner.db` belum ada. Fitur admin
(FR-10–12) menyusul.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Agar paket kuliner bisa diimpor tanpa instalasi editable
# (penting juga nanti di Streamlit Community Cloud).
AKAR = Path(__file__).resolve().parent
sys.path.insert(0, str(AKAR / "src"))

import pandas as pd
import streamlit as st
from streamlit_folium import st_folium

from kuliner.config import BOBOT_DEFAULT
from kuliner.halaman_evaluasi import tab_evaluasi_pengguna
from kuliner.recommender import muat_katalog, titik_pusat
from kuliner.ui_helpers import (
    KETERANGAN_HARGA,
    LABEL_HARGA,
    PILIHAN_RADIUS_KM,
    PILIHAN_RATING,
    bangun_peta,
    cari_nama,
    daftar_kategori,
    daftar_kecamatan,
    daftar_kota,
    format_angka,
    jalankan_pencarian,
    label_lokasi,
    pesan_di_luar_wilayah,
    ringkasan_preferensi,
    tabel_tampil,
    tautan_google_maps,
    teks_harga,
    teks_rating,
    teks_uraian,
    uraian_komponen,
)

st.set_page_config(
    page_title="Rekomendasi Kuliner — Jabodetabek & Bandung",
    page_icon="🍽️",
    layout="wide",
    initial_sidebar_state="expanded",
)


@st.cache_resource(show_spinner="Menyiapkan basis data… (dibangun dari CSV jika kuliner.db belum ada)")
def _pastikan_db() -> dict:
    """Pastikan SQLite tersedia (Cloud tidak mengunggah .db yang diabaikan Git)."""
    from kuliner.db import pastikan_basis_data
    from kuliner.recommender import bersihkan_cache

    info = pastikan_basis_data()
    # Katalog in-proses harus dibaca ulang setelah DB baru dibuat.
    bersihkan_cache()
    return info


@st.cache_data(show_spinner="Memuat katalog merchant…")
def _muat_katalog_cached() -> pd.DataFrame:
    """Bangun DB jika perlu, lalu baca katalog (SQLite, atau CSV sebagai cadangan)."""
    _pastikan_db()
    return muat_katalog(ulang=True)


def _init_sesi() -> None:
    awal = {
        "hasil": None,
        "meta": None,
        "sudah_cari": False,
        "lat_klik": None,
        "lon_klik": None,
    }
    for kunci, nilai in awal.items():
        if kunci not in st.session_state:
            st.session_state[kunci] = nilai


def _css() -> None:
    st.markdown(
        """
        <style>
        .block-container { padding-top: 1.2rem; }
        .stButton>button { font-weight: 600; }
        div[data-testid="stSidebar"] h1 { font-size: 1.25rem; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def sidebar_preferensi(data: pd.DataFrame) -> dict:
    """Gambar form preferensi di sidebar dan kembalikan nilainya."""
    st.sidebar.title("Rekomendasi Kuliner")
    st.sidebar.caption("Jabodetabek & Bandung")
    st.sidebar.header("Preferensi Anda")

    mode = st.sidebar.radio(
        "Cara menentukan lokasi",
        options=["Kota/kecamatan", "Titik peta / koordinat"],
        index=0,
        key="mode_lokasi",
        help="Lokasi manual memakai centroid kecamatan. Alternatif: isi koordinat atau klik peta.",
    )

    kota_opsi = daftar_kota(data)
    kota_default = "Kota Depok" if "Kota Depok" in kota_opsi else kota_opsi[0]
    lat = lon = None
    label = ""

    if mode == "Kota/kecamatan":
        kota = st.sidebar.selectbox(
            "Kota/Kabupaten",
            options=kota_opsi,
            index=kota_opsi.index(kota_default),
            key="kota",
        )
        kec_opsi = daftar_kecamatan(data, kota)
        kec_default = "Beji" if "Beji" in kec_opsi else (kec_opsi[0] if kec_opsi else "")
        kecamatan = st.sidebar.selectbox(
            "Kecamatan",
            options=kec_opsi,
            index=kec_opsi.index(kec_default) if kec_default in kec_opsi else 0,
            key="kecamatan",
            help="Hanya kecamatan dengan paling sedikit 5 merchant (aturan dropdown TK1).",
        )
        if kecamatan:
            lat, lon, n_loc = titik_pusat(kota, kecamatan, data=data)
            label = label_lokasi(kota, kecamatan)
            st.sidebar.caption(
                f"Titik acuan: centroid {n_loc} merchant di {kecamatan} "
                f"({lat:.5f}, {lon:.5f})."
            )
    else:
        # Proses klik peta dari rerun sebelumnya sebelum number_input dibuat.
        if st.session_state["lat_klik"] is not None:
            st.session_state["lat_manual"] = round(float(st.session_state["lat_klik"]), 6)
            st.session_state["lon_manual"] = round(float(st.session_state["lon_klik"]), 6)
            st.session_state["lat_klik"] = None
            st.session_state["lon_klik"] = None
        if "lat_manual" not in st.session_state:
            # Default: dekat Monas, Jakarta Pusat.
            st.session_state["lat_manual"] = -6.175392
            st.session_state["lon_manual"] = 106.827153
        lat = st.sidebar.number_input(
            "Latitude",
            min_value=-90.0,
            max_value=90.0,
            step=0.0001,
            format="%.6f",
            key="lat_manual",
        )
        lon = st.sidebar.number_input(
            "Longitude",
            min_value=-180.0,
            max_value=180.0,
            step=0.0001,
            format="%.6f",
            key="lon_manual",
        )
        label = f"Titik ({lat:.5f}, {lon:.5f})"
        st.sidebar.caption("Klik pada peta di panel kanan untuk mengisi koordinat, lalu tekan Cari.")

    radius_km = st.sidebar.select_slider(
        "Radius pencarian (km)",
        options=list(PILIHAN_RADIUS_KM),
        value=5,
        key="radius_km",
    )

    budget_maks = st.sidebar.selectbox(
        "Budget maksimum (harga rata-rata per menu)",
        options=[1, 2, 3, 4],
        index=1,
        format_func=lambda lv: f"Level {lv}  ·  {LABEL_HARGA[lv]}",
        key="budget_maks",
    )
    st.sidebar.caption(KETERANGAN_HARGA)

    label_rating = [p[0] for p in PILIHAN_RATING]
    pilih_rating = st.sidebar.radio(
        "Rating minimum",
        options=label_rating,
        index=2,
        key="label_rating",
        horizontal=True,
    )
    rating_min = dict(PILIHAN_RATING)[pilih_rating]

    sertakan = st.sidebar.checkbox(
        "Sertakan merchant yang belum dinilai",
        value=False,
        key="sertakan_belum",
        help=(
            "Rating 0 pada data mentah berarti belum dinilai, bukan rating buruk. "
            "Jika rating minimum dipasang, default-nya merchant ini dikeluarkan."
        ),
    )

    kategori_opsi = daftar_kategori(data)
    default_kat = ["Bakmie"] if "Bakmie" in kategori_opsi else []
    kategori = st.sidebar.multiselect(
        "Kategori kuliner (opsional, boleh lebih dari satu)",
        options=kategori_opsi,
        default=default_kat,
        key="kategori",
        help="Boleh dikosongkan. Default Bakmie mengikuti contoh kueri pada laporan TK1.",
    )

    k = st.sidebar.number_input(
        "Jumlah hasil (k)",
        min_value=1,
        max_value=30,
        value=10,
        step=1,
        key="k_hasil",
    )

    with st.sidebar.expander("Bobot lanjutan (opsional)"):
        st.caption(
            "Nilai akan dinormalisasi agar jumlahnya 1. "
            "Jika tidak ada kategori yang dipilih, bobot kategori di-nol-kan "
            "lalu dinormalisasi ulang (perilaku TK1)."
        )
        w_lok = st.slider("Lokasi (d/R)", 0.0, 1.0, float(BOBOT_DEFAULT["lokasi"]), 0.01, key="w_lokasi")
        w_kat = st.slider("Kategori (1 − Jaccard)", 0.0, 1.0, float(BOBOT_DEFAULT["kategori"]), 0.01, key="w_kategori")
        w_rat = st.slider("Rating (selisih ke terbaik)", 0.0, 1.0, float(BOBOT_DEFAULT["rating"]), 0.01, key="w_rating")
        w_har = st.slider("Harga ((p−1)/3)", 0.0, 1.0, float(BOBOT_DEFAULT["harga"]), 0.01, key="w_harga")
        total = w_lok + w_kat + w_rat + w_har
        if total <= 0:
            st.warning("Jumlah bobot harus lebih dari 0.")
            bobot = dict(BOBOT_DEFAULT)
        else:
            bobot = {
                "lokasi": w_lok / total,
                "kategori": w_kat / total,
                "rating": w_rat / total,
                "harga": w_har / total,
            }
            st.caption(
                "Setelah dinormalisasi: "
                f"lokasi {format_angka(bobot['lokasi'], 2)}, "
                f"kategori {format_angka(bobot['kategori'], 2)}, "
                f"rating {format_angka(bobot['rating'], 2)}, "
                f"harga {format_angka(bobot['harga'], 2)}."
            )
        if st.button("Kembalikan bobot default", key="reset_bobot"):
            st.session_state["w_lokasi"] = float(BOBOT_DEFAULT["lokasi"])
            st.session_state["w_kategori"] = float(BOBOT_DEFAULT["kategori"])
            st.session_state["w_rating"] = float(BOBOT_DEFAULT["rating"])
            st.session_state["w_harga"] = float(BOBOT_DEFAULT["harga"])
            st.rerun()

    cari = st.sidebar.button("Cari Rekomendasi", type="primary", key="btn_cari", width='stretch')
    return {
        "mode": mode,
        "lat": lat,
        "lon": lon,
        "label": label,
        "radius_km": float(radius_km),
        "budget_maks": int(budget_maks),
        "rating_min": float(rating_min),
        "kategori": kategori,
        "k": int(k),
        "bobot": bobot,
        "sertakan_belum_dinilai": True if sertakan else None,
        "cari": cari,
    }


def tampil_intro(data: pd.DataFrame) -> None:
    st.subheader("Temukan tempat makan yang dekat, sesuai budget, dan sesuai selera")
    st.write(
        "Sistem mencari tempat makan di sekitar titik lokasi Anda, menyaring "
        "yang berada di dalam radius, sesuai budget maksimum, dan memenuhi "
        "rating minimum, lalu mengurutkan kandidat dengan algoritma "
        "*K-Nearest Neighbor* berdasarkan jarak, kategori, rating, dan harga."
    )
    st.success(
        f"Data: {len(data):,} tempat makan GoFood di Jabodetabek dan Bandung "
        "(diambil Februari 2024). Rating dan harga dapat berubah sewaktu-waktu.".replace(",", ".")
    )
    st.markdown(
        """
**Cara memakai**

1. Pilih kota/kabupaten dan kecamatan, atau isi koordinat / klik peta.
2. Atur radius, budget maksimum, dan rating minimum.
3. Pilih satu atau beberapa kategori kuliner (opsional).
4. Tekan **Cari Rekomendasi**; sistem menampilkan *k* tempat teratas beserta peta dan skornya.
        """
    )
    st.caption(KETERANGAN_HARGA)


def tampil_hasil(pref: dict, data: pd.DataFrame) -> None:
    meta = st.session_state["meta"]
    hasil = st.session_state["hasil"]
    if meta is None:
        return

    if not meta["ok"]:
        st.error(meta["pesan"])
        _tampil_peta_lokasi(pref)
        return

    chip = " · ".join(
        ringkasan_preferensi(
            pref["label"],
            pref["radius_km"],
            pref["budget_maks"],
            pref["rating_min"],
            pref["kategori"],
        )
    )
    st.caption(chip)

    detik = meta["detik"]
    warna_waktu = "normal" if detik <= 2.0 else "inverse"
    st.metric(
        "Waktu respons pencarian",
        f"{format_angka(detik, 2)} s",
        delta="memenuhi NFR-01 (≤ 2 s)" if detik <= 2.0 else "melebihi batas NFR-01 (≤ 2 s)",
        delta_color="normal" if detik <= 2.0 else "inverse",
    )
    # delta_color disimpan di variabel agar mudah dibaca; Streamlit memakai argumen itu.
    _ = warna_waktu

    if hasil is None or hasil.empty:
        st.warning(meta["pesan"])
        _tampil_peta_lokasi(pref)
        return

    st.subheader(f"{len(hasil)} rekomendasi teratas")
    st.caption(meta["pesan"])

    kolom_kiri, kolom_kanan = st.columns((1.45, 1.0), gap="medium")
    with kolom_kiri:
        tampil = tabel_tampil(hasil).rename(
            columns={
                "peringkat": "#",
                "nama": "Nama",
                "kategori": "Kategori",
                "rating": "Rating",
                "harga": "Harga",
                "jarak_km": "Jarak (km)",
                "skor": "Skor",
            }
        )
        st.dataframe(tampil, width='stretch', hide_index=True, height=440)
    with kolom_kanan:
        st.markdown("**Peta hasil**")
        peta = bangun_peta(
            pref["lat"],
            pref["lon"],
            pref["radius_km"],
            hasil,
            judul_pengguna=pref["label"] or "Lokasi Anda",
        )
        peristiwa = st_folium(
            peta,
            height=480,
            width='stretch',
            returned_objects=["last_clicked"],
            key="peta_hasil",
        )
        _simpan_klik(pref, peristiwa)
        st.caption("Bintang merah = lokasi Anda · lingkaran putus-putus = radius · angka = peringkat.")

    _tampil_detail(hasil, meta["bobot"])


def _tampil_peta_lokasi(pref: dict) -> None:
    """Peta acuan (sebelum ada hasil, atau saat memilih titik)."""
    lat, lon = pref["lat"], pref["lon"]
    if lat is None or lon is None:
        # Peta default Jabodetabek agar pengguna bisa mengklik.
        lat, lon = -6.25, 106.83
    peta = bangun_peta(lat, lon, pref["radius_km"], hasil=None, judul_pengguna=pref["label"] or "Lokasi")
    peristiwa = st_folium(
        peta,
        height=420,
        width='stretch',
        returned_objects=["last_clicked"],
        key="peta_lokasi",
    )
    _simpan_klik(pref, peristiwa)
    st.caption("Klik peta untuk memilih titik, lalu tekan Cari Rekomendasi.")


def _simpan_klik(pref: dict, peristiwa: dict | None) -> None:
    if pref["mode"] != "Titik peta / koordinat":
        return
    if not peristiwa:
        return
    klik = peristiwa.get("last_clicked") if isinstance(peristiwa, dict) else None
    if klik and "lat" in klik and "lng" in klik:
        st.session_state["lat_klik"] = float(klik["lat"])
        st.session_state["lon_klik"] = float(klik["lng"])


def _tampil_detail(hasil: pd.DataFrame, bobot: dict) -> None:
    st.markdown("---")
    st.subheader("Mengapa direkomendasikan?")
    st.caption("Nilai komponen ternormalisasi (0 = ideal, 1 = terburuk) dan bobotnya.")
    opsi = [f"{int(r.peringkat)}. {r.nama}" for r in hasil.itertuples()]
    pilih = st.selectbox("Pilih hasil untuk melihat rincian skor", options=opsi, key="pilih_detail")
    idx = opsi.index(pilih)
    baris = hasil.iloc[idx]
    kiri, kanan = st.columns((1.1, 1.0), gap="large")
    with kiri:
        st.markdown(f"### {baris['nama']}")
        st.write(
            f"**Wilayah:** Kec. {baris.get('kecamatan') or '–'}, {baris.get('kota') or '–'}  \n"
            f"**Kategori:** {baris['kategori'] if pd.notna(baris['kategori']) else '–'}".replace("|", ", ")
        )
        sudah = bool(baris["sudah_dinilai"]) if "sudah_dinilai" in baris else None
        st.write(
            f"**Rating:** {teks_rating(baris['rating'], sudah)}"
            + (" / 5" if sudah is not False and pd.notna(baris["rating"]) else "")
            + f"  \n**Harga:** {teks_harga(int(baris['price_level']))} per menu  \n"
            f"**Jarak dari Anda:** {format_angka(float(baris['jarak_km']), 2)} km "
            "(Haversine, garis lurus)"
        )
        if "alamat_area" in baris and pd.notna(baris["alamat_area"]):
            st.caption(f"Alamat (area): {baris['alamat_area']}")
        tautan = tautan_google_maps(float(baris["latitude"]), float(baris["longitude"]))
        st.link_button("Buka di Google Maps", tautan)
        st.caption(tautan)
        st.write(teks_uraian(baris, bobot))
    with kanan:
        st.dataframe(uraian_komponen(baris, bobot), width='stretch', hide_index=True)
        st.metric("Skor D", format_angka(float(baris["skor"]), 3), help="Makin kecil makin sesuai.")


def tab_cari_nama(data: pd.DataFrame) -> None:
    st.subheader("Cari tempat makan berdasarkan nama")
    kol1, kol2, kol3 = st.columns((2.5, 1.5, 0.8))
    with kol1:
        kata = st.text_input("Nama mengandung kata ini", value="", key="cari_kata")
    with kol2:
        opsi_kota = ["Semua kota/kabupaten"] + daftar_kota(data)
        kota_pilih = st.selectbox("Filter kota (opsional)", options=opsi_kota, key="cari_kota")
    with kol3:
        halaman = st.number_input("Halaman", min_value=1, value=1, step=1, key="cari_halaman")
    kota = None if kota_pilih == "Semua kota/kabupaten" else kota_pilih
    if not kata.strip():
        st.info("Ketik sebagian nama, misalnya “gacoan”.")
        return
    potong, total = cari_nama(data, kata, kota=kota, halaman=int(halaman), per_halaman=10)
    if total == 0:
        st.warning("Tidak ada tempat makan yang namanya mengandung kata tersebut.")
        return
    awal = (int(halaman) - 1) * 10 + 1
    akhir = (int(halaman) - 1) * 10 + len(potong)
    st.caption(f"{total} tempat makan ditemukan • menampilkan {awal}–{akhir}.")
    tampil = pd.DataFrame(
        {
            "nama": potong["nama"],
            "kota": potong["kota"],
            "kecamatan": potong["kecamatan"],
            "kategori": potong["kategori"].fillna("").astype(str).str.replace("|", ", ", regex=False),
            "harga": [teks_harga(x) for x in potong["price_level"]],
            "rating": [
                teks_rating(r, s) for r, s in zip(potong["rating"], potong["sudah_dinilai"])
            ],
        }
    )
    st.dataframe(tampil, width='stretch', hide_index=True)


def tab_admin() -> None:
    st.subheader("Admin")
    st.info(
        "Login admin serta fitur menambah, mengubah, menghapus, dan mengimpor "
        "data (FR-10 sampai FR-12) akan dikerjakan pada bagian berikutnya. "
        "Halaman ini sengaja belum dapat diakses sebagai panel pengelolaan."
    )


def main() -> None:
    _css()
    _init_sesi()
    info_db = _pastikan_db()
    data = _muat_katalog_cached()
    if info_db.get("dibuat"):
        st.caption(info_db.get("pesan", "Basis data baru disiapkan dari CSV bersih."))
    pref = sidebar_preferensi(data)

    if pref["cari"]:
        ringkas = jalankan_pencarian(
            data,
            pref["lat"],
            pref["lon"],
            radius_km=pref["radius_km"],
            budget_maks=pref["budget_maks"],
            rating_min=pref["rating_min"],
            kategori_pilihan=pref["kategori"],
            k=pref["k"],
            bobot=pref["bobot"],
            sertakan_belum_dinilai=pref["sertakan_belum_dinilai"],
        )
        st.session_state["meta"] = ringkas
        st.session_state["hasil"] = ringkas["hasil"]
        st.session_state["sudah_cari"] = True
        st.session_state["label_terakhir"] = pref["label"]

    tab_rek, tab_nama, tab_eval, tab_adm = st.tabs(
        ["Rekomendasi", "Cari Nama", "Evaluasi Pengguna", "Admin"]
    )
    with tab_rek:
        if not st.session_state["sudah_cari"]:
            tampil_intro(data)
            if pref["mode"] == "Titik peta / koordinat":
                st.markdown("##### Pilih titik pada peta")
                _tampil_peta_lokasi(pref)
        else:
            # Pastikan label/titik yang dipakai hasil adalah yang baru (jika baru tekan Cari).
            tampil_hasil(pref, data)
    with tab_nama:
        tab_cari_nama(data)
    with tab_eval:
        tab_evaluasi_pengguna(data)
    with tab_adm:
        tab_admin()


if __name__ == "__main__":
    main()
