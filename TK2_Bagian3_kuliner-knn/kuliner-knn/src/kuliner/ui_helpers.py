"""Pembantu antarmuka: label, validasi lokasi, peta, dan ringkasan hasil.

Fungsi di modul ini tidak bergantung pada Streamlit agar mudah diuji.
"""

from __future__ import annotations

from typing import Any, Sequence

import folium
import pandas as pd
from folium.features import DivIcon

from kuliner.config import (
    BOBOT_DEFAULT,
    LAT_MAX,
    LAT_MIN,
    LON_MAX,
    LON_MIN,
)
from kuliner.geo import saring_radius
from kuliner.recommender import (
    KUNCI_FITUR,
    normalisasi_bobot,
    rekomendasi,
    titik_pusat,
)

# Rentang rupiah mengikuti label GoFood pada laporan TK1.
# Level 1 dan 3 adalah perkiraan (disimpulkan), bukan tarif resmi.
LABEL_HARGA = {
    1: "< Rp16 rb",
    2: "Rp16–40 rb",
    3: "Rp40–100 rb",
    4: "> Rp100 rb",
}

KETERANGAN_HARGA = (
    "Keterangan harga (perkiraan harga rata-rata per menu, label GoFood): "
    "Level 1 < Rp16 rb • Level 2 Rp16–40 rb • Level 3 Rp40–100 rb • "
    "Level 4 > Rp100 rb. Rentang Level 1 dan 3 disimpulkan dari data, "
    "bukan tarif resmi."
)

PILIHAN_RADIUS_KM = (1, 3, 5, 10)
PILIHAN_RATING = (
    ("Semua", 0.0),
    ("★ 4,0", 4.0),
    ("★ 4,5", 4.5),
    ("★ 4,7", 4.7),
    ("★ 4,9", 4.9),  # dipakai pada contoh hasil kosong di laporan TK1
)

LABEL_KOMPONEN = {
    "lokasi": "Lokasi d/R",
    "kategori": "Kategori 1 − Jaccard",
    "rating": "Rating (selisih ke terbaik)",
    "harga": "Harga (p')",
}

MIN_MERCHANT_DROPDOWN = 5


def format_angka(nilai: float, nd: int = 1) -> str:
    """Format angka dengan koma desimal (gaya Indonesia)."""
    try:
        if pd.isna(nilai):
            return "–"
    except (TypeError, ValueError):
        pass
    return f"{float(nilai):.{nd}f}".replace(".", ",")


def label_harga(level: int) -> str:
    """Rentang rupiah untuk satu price level."""
    return LABEL_HARGA.get(int(level), f"Level {level}")


def teks_harga(level: int) -> str:
    """Label lengkap, misalnya 'Level 2 (Rp16–40 rb)'."""
    level = int(level)
    return f"Level {level} ({label_harga(level)})"


def teks_rating(nilai, sudah_dinilai: bool | None = None) -> str:
    """Tampilkan rating atau 'Belum dinilai'."""
    if sudah_dinilai is False:
        return "Belum dinilai"
    try:
        if nilai is None or pd.isna(nilai):
            return "Belum dinilai"
    except (TypeError, ValueError):
        return "Belum dinilai"
    if sudah_dinilai is None and float(nilai) <= 0:
        return "Belum dinilai"
    return format_angka(float(nilai), 1)


def format_kategori(nilai: Any) -> str:
    """Ubah pemisah '|' menjadi koma, atau '–' jika kosong."""
    if nilai is None:
        return "–"
    try:
        if pd.isna(nilai):
            return "–"
    except (TypeError, ValueError):
        pass
    if isinstance(nilai, (list, tuple, set)):
        bagian = [str(x) for x in nilai if str(x)]
    else:
        bagian = [s for s in str(nilai).split("|") if s]
    return ", ".join(bagian) if bagian else "–"


def tautan_google_maps(lat: float, lon: float) -> str:
    """Tautan Google Maps berdasarkan koordinat (bukan pencarian nama)."""
    return f"https://www.google.com/maps/search/?api=1&query={float(lat):.6f},{float(lon):.6f}"


def dalam_wilayah(lat: float, lon: float) -> bool:
    """True jika titik berada di kotak layanan Jabodetabek–Bandung."""
    try:
        la, lo = float(lat), float(lon)
    except (TypeError, ValueError):
        return False
    return (LAT_MIN <= la <= LAT_MAX) and (LON_MIN <= lo <= LON_MAX)


def pesan_lokasi_kosong() -> str:
    return (
        "Lokasi belum ditentukan. Pilih kota dan kecamatan, isi koordinat, "
        "atau klik titik pada peta."
    )


def pesan_di_luar_wilayah() -> str:
    return (
        "Koordinat berada di luar wilayah layanan (Jabodetabek dan Bandung)."
    )


def pesan_hasil_kosong(radius_km: float = 5) -> str:
    """Pesan ramah plus saran, sesuai mockup TK1 (FR-06)."""
    if radius_km < 3:
        saran_radius = "perluas radius menjadi 3 atau 5 km, "
    elif radius_km < 10:
        saran_radius = "perluas radius, "
    else:
        saran_radius = ""
    return (
        "Tidak ada tempat makan yang memenuhi semua batas. "
        f"Coba {saran_radius}naikkan budget maksimum, atau turunkan rating minimum."
    )


def daftar_kota(data: pd.DataFrame) -> list[str]:
    """Daftar kota/kabupaten, diurut abjad."""
    return sorted(str(x) for x in data["kota"].dropna().unique())


def daftar_kecamatan(
    data: pd.DataFrame,
    kota: str,
    min_merchant: int = MIN_MERCHANT_DROPDOWN,
) -> list[str]:
    """Kecamatan di satu kota untuk dropdown.

    Default hanya kecamatan dengan ≥ 5 merchant (aturan dropdown TK1).
    Jika tidak ada yang lolos, seluruh kecamatan di kota itu dikembalikan.
    """
    potong = data[data["kota"] == kota]
    hitung = potong.groupby("kecamatan", dropna=True).size()
    lolos = hitung[hitung >= min_merchant].sort_index()
    if lolos.empty:
        lolos = hitung.sort_index()
    return [str(x) for x in lolos.index]


def daftar_kategori(data: pd.DataFrame) -> list[str]:
    """21 kategori, diurut dari yang paling sering muncul (seperti mockup)."""
    pecah = (
        data["kategori"]
        .fillna("")
        .astype(str)
        .str.split("|")
        .explode()
    )
    pecah = pecah[pecah.str.len() > 0]
    return list(pecah.value_counts().index)


def label_lokasi(kota: str | None = None, kecamatan: str | None = None) -> str:
    if kecamatan and kota:
        return f"{kecamatan}, {kota}"
    if kota:
        return str(kota)
    return "Titik peta"


def ringkasan_preferensi(
    lokasi: str,
    radius_km: float,
    budget_maks: int,
    rating_min: float,
    kategori: Sequence[str] | None,
) -> list[str]:
    """Chip ringkas yang ditampilkan di atas hasil."""
    chip = [
        lokasi,
        f"Radius {format_angka(radius_km, 0)} km",
        f"Budget ≤ {teks_harga(budget_maks)}",
    ]
    if rating_min and rating_min > 0:
        chip.append(f"Rating ≥ {format_angka(rating_min, 1)}")
    else:
        chip.append("Rating: semua")
    if kategori:
        chip.extend(str(x) for x in kategori)
    else:
        chip.append("Semua kategori")
    return chip


def tabel_tampil(hasil: pd.DataFrame) -> pd.DataFrame:
    """Tabel hasil untuk UI: nama, kategori, rating, harga, jarak, skor."""
    if hasil is None or hasil.empty:
        return pd.DataFrame(
            columns=["peringkat", "nama", "kategori", "rating", "harga", "jarak_km", "skor"]
        )
    keluar = pd.DataFrame(
        {
            "peringkat": hasil["peringkat"].astype(int),
            "nama": hasil["nama"],
            "kategori": hasil["kategori"].map(format_kategori),
            "rating": [
                teks_rating(r, s)
                for r, s in zip(hasil["rating"], hasil.get("sudah_dinilai", [None] * len(hasil)))
            ],
            "harga": [teks_harga(x) for x in hasil["price_level"]],
            "jarak_km": [format_angka(x, 2) for x in hasil["jarak_km"]],
            "skor": [format_angka(x, 3) for x in hasil["skor"]],
        }
    )
    return keluar


def uraian_komponen(baris: pd.Series, bobot: dict[str, float] | None = None) -> pd.DataFrame:
    """Tabel nilai, bobot, dan kontribusi w·f² untuk satu hasil."""
    ww = dict(bobot) if bobot is not None else dict(BOBOT_DEFAULT)
    baris_tabel = []
    for kunci in KUNCI_FITUR:
        nilai = float(baris[f"f_{kunci}"])
        w = float(ww.get(kunci, BOBOT_DEFAULT[kunci]))
        baris_tabel.append(
            {
                "Komponen": LABEL_KOMPONEN[kunci],
                "Nilai": format_angka(nilai, 3),
                "Bobot": format_angka(w, 2),
                "Kontribusi w·f²": format_angka(w * nilai * nilai, 3),
            }
        )
    return pd.DataFrame(baris_tabel)


def teks_uraian(baris: pd.Series, bobot: dict[str, float] | None = None) -> str:
    """Paragraf singkat mengapa merchant ini direkomendasikan."""
    ww = normalisasi_bobot(bobot, pakai_kategori=True)
    nama = str(baris.get("nama", "Tempat ini"))
    skor = format_angka(float(baris["skor"]), 3)
    peringkat = int(baris.get("peringkat", 0) or 0)
    f_kat = float(baris.get("f_kategori", 0) or 0)
    if f_kat == 0 and ww.get("kategori", 0) > 0:
        ket_kat = "kategori merchant cocok penuh dengan pilihan Anda"
    elif ww.get("kategori", 0) == 0:
        ket_kat = "kategori tidak dipakai dalam skor (tidak ada pilihan kategori, bobot dinolkan)"
    else:
        ket_kat = f"kesamaan kategori (1 − Jaccard) bernilai {format_angka(f_kat, 3)}"
    return (
        f"Peringkat {peringkat} ({nama}) memiliki skor D = {skor} "
        f"(makin kecil makin sesuai). Nilai komponen sudah dinormalisasi ke 0–1 "
        f"(0 = ideal). Lokasi d/R = {format_angka(float(baris['f_lokasi']), 3)}, "
        f"{ket_kat}, rating (selisih ke terbaik) = "
        f"{format_angka(float(baris['f_rating']), 3)}, dan harga (p') = "
        f"{format_angka(float(baris['f_harga']), 3)}."
    )


def bangun_peta(
    lat: float,
    lon: float,
    radius_km: float,
    hasil: pd.DataFrame | None = None,
    judul_pengguna: str = "Lokasi Anda",
) -> folium.Map:
    """Peta Folium: titik pengguna, lingkaran radius, penanda bernomor."""
    peta = folium.Map(
        location=[float(lat), float(lon)],
        zoom_start=13,
        tiles="OpenStreetMap",
        control_scale=True,
    )
    folium.Circle(
        location=[float(lat), float(lon)],
        radius=float(radius_km) * 1000.0,
        color="#C62828",
        weight=2,
        dash_array="6, 4",
        fill=True,
        fill_color="#2E7D32",
        fill_opacity=0.06,
        tooltip=f"Radius {format_angka(radius_km, 0)} km",
    ).add_to(peta)
    folium.Marker(
        location=[float(lat), float(lon)],
        tooltip=judul_pengguna,
        popup=folium.Popup(
            f"<b>{judul_pengguna}</b><br>{float(lat):.6f}, {float(lon):.6f}",
            max_width=260,
        ),
        icon=DivIcon(
            icon_size=(22, 22),
            icon_anchor=(11, 14),
            html=(
                '<div style="color:#C62828;font-size:22px;line-height:22px;'
                'text-shadow:0 0 2px #fff">★</div>'
            ),
        ),
    ).add_to(peta)

    if hasil is not None and not hasil.empty:
        for rec in hasil.itertuples():
            peringkat = int(rec.peringkat)
            popup = (
                f"<b>{peringkat}. {rec.nama}</b><br>"
                f"{format_kategori(rec.kategori)}<br>"
                f"Rating: {teks_rating(rec.rating, getattr(rec, 'sudah_dinilai', None))}<br>"
                f"Harga: {teks_harga(rec.price_level)}<br>"
                f"Jarak: {format_angka(rec.jarak_km, 2)} km<br>"
                f"Skor D: {format_angka(rec.skor, 3)}"
            )
            folium.Marker(
                location=[float(rec.latitude), float(rec.longitude)],
                tooltip=f"{peringkat}. {rec.nama}",
                popup=folium.Popup(popup, max_width=280),
                icon=DivIcon(
                    icon_size=(24, 24),
                    icon_anchor=(12, 12),
                    html=(
                        f'<div style="background:#2E7D32;color:#fff;width:24px;height:24px;'
                        f'border-radius:12px;border:2px solid #fff;text-align:center;'
                        f'line-height:20px;font-size:12px;font-weight:bold;'
                        f'box-shadow:0 1px 3px rgba(0,0,0,.4)">{peringkat}</div>'
                    ),
                ),
            ).add_to(peta)
        # Sesuaikan bingkai agar titik dan lingkaran terlihat.
        delta = float(radius_km) / 110.0
        peta.fit_bounds(
            [[float(lat) - delta, float(lon) - delta], [float(lat) + delta, float(lon) + delta]]
        )
    return peta


def cari_nama(
    data: pd.DataFrame,
    kata: str,
    kota: str | None = None,
    halaman: int = 1,
    per_halaman: int = 10,
) -> tuple[pd.DataFrame, int]:
    """Cari merchant berdasarkan potongan nama (FR-09), hasil berhalaman."""
    q = str(kata or "").strip()
    if not q:
        return data.iloc[0:0].copy(), 0
    mask = data["nama"].astype(str).str.contains(q, case=False, na=False, regex=False)
    potong = data.loc[mask]
    if kota:
        potong = potong[potong["kota"] == kota]
    total = int(len(potong))
    halaman = max(1, int(halaman))
    awal = (halaman - 1) * per_halaman
    return potong.iloc[awal : awal + per_halaman].copy(), total


def jalankan_pencarian(
    data: pd.DataFrame,
    lat: float | None,
    lon: float | None,
    radius_km: float = 5,
    budget_maks: int = 4,
    rating_min: float = 0.0,
    kategori_pilihan: Sequence[str] | None = None,
    k: int = 10,
    bobot: dict[str, float] | None = None,
    sertakan_belum_dinilai: bool | None = None,
) -> dict[str, Any]:
    """Validasi lokasi, jalankan rekomender, dan kembalikan ringkasan.

    Pengukuran waktu mencakup filter + perhitungan skor (patokan NFR-01).
    """
    import time

    if lat is None or lon is None:
        return {
            "ok": False,
            "pesan": pesan_lokasi_kosong(),
            "hasil": pd.DataFrame(),
            "n_dalam_radius": 0,
            "n_lolos_filter": 0,
            "detik": 0.0,
            "bobot": normalisasi_bobot(bobot, pakai_kategori=bool(kategori_pilihan)),
        }
    if not dalam_wilayah(lat, lon):
        return {
            "ok": False,
            "pesan": pesan_di_luar_wilayah(),
            "hasil": pd.DataFrame(),
            "n_dalam_radius": 0,
            "n_lolos_filter": 0,
            "detik": 0.0,
            "bobot": normalisasi_bobot(bobot, pakai_kategori=bool(kategori_pilihan)),
        }

    t0 = time.perf_counter()
    dalam = saring_radius(float(lat), float(lon), data, float(radius_km))
    n_dalam = int(len(dalam))
    # Satu kali jalan dengan k besar: hitung yang lolos filter, lalu ambil k teratas.
    semua = rekomendasi(
        float(lat),
        float(lon),
        radius_km=float(radius_km),
        budget_maks=int(budget_maks),
        rating_min=float(rating_min),
        kategori_pilihan=kategori_pilihan,
        k=10_000,
        bobot=bobot,
        sertakan_belum_dinilai=sertakan_belum_dinilai,
        data=data,
    )
    n_lolos = int(len(semua))
    hasil = semua.head(max(int(k), 1)).copy()
    if not hasil.empty:
        hasil["peringkat"] = range(1, len(hasil) + 1)
    detik = time.perf_counter() - t0
    ww = normalisasi_bobot(bobot, pakai_kategori=bool(kategori_pilihan))

    if hasil.empty:
        return {
            "ok": True,
            "pesan": pesan_hasil_kosong(radius_km),
            "hasil": hasil,
            "n_dalam_radius": n_dalam,
            "n_lolos_filter": n_lolos,
            "detik": detik,
            "bobot": ww,
        }
    return {
        "ok": True,
        "pesan": (
            f"{n_lolos} dari {n_dalam} tempat makan dalam radius "
            f"{format_angka(radius_km, 0)} km lolos filter budget dan rating; "
            f"diurutkan menurut skor jarak berbobot D (makin kecil makin sesuai)."
        ),
        "hasil": hasil,
        "n_dalam_radius": n_dalam,
        "n_lolos_filter": n_lolos,
        "detik": detik,
        "bobot": ww,
    }


