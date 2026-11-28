"""Metrik evaluasi offline untuk sistem rekomendasi kuliner.

Bagian 4 menghitung metrik yang tidak membutuhkan penilaian manusia:
cakupan katalog, diversitas intra-daftar, jarak/rating rata-rata, dan
ketepatan proksi (Precision@K, NDCG@K). Fungsi Precision@K dan NDCG@K
sengaja menerima daftar nilai relevansi apa pun — termasuk penilaian
responden pada bagian 5.

PERINGATAN. Relevansi proksi pada modul ini merujuk Subbab 3.8.1 laporan
TK1 dan bersifat aturan otomatis, BUKAN penilaian pengguna. Aturan itu
memakai atribut yang sama dengan skor, sehingga cenderung menguntungkan
model gabungan (S4). Hasilnya hanya untuk analisis awal dan pemilihan
konfigurasi, bukan kesimpulan kualitas akhir sistem.
"""

from __future__ import annotations

from typing import Iterable, Sequence

import numpy as np
import pandas as pd
from scipy.stats import wilcoxon

from kuliner.config import BOBOT_DEFAULT
from kuliner.preprocessing import pecah_kategori
from kuliner.recommender import jaccard, rekomendasi, rekomendasi_dasar

# Ambang rating pada aturan proksi TK1 = median data (4,7).
PROXY_RATING_AMBANG = 4.7

# Konfigurasi eksperimen Tabel 3.18 (urutan: lokasi, kategori, rating, harga).
BOBOT_S1 = {"lokasi": 1.0, "kategori": 0.0, "rating": 0.0, "harga": 0.0}
BOBOT_S2 = {"lokasi": 0.50, "kategori": 0.50, "rating": 0.0, "harga": 0.0}
BOBOT_S3 = {"lokasi": 0.40, "kategori": 0.35, "rating": 0.25, "harga": 0.0}
BOBOT_S4 = dict(BOBOT_DEFAULT)  # (0,35; 0,30; 0,20; 0,15)
BOBOT_RATING = {"lokasi": 0.0, "kategori": 0.0, "rating": 1.0, "harga": 0.0}

METODE = {
    "S1_jarak": {"label": "S1 jarak saja", "bobot": BOBOT_S1, "dasar": "jarak"},
    "S2_jarak_kategori": {"label": "S2 jarak + kategori", "bobot": BOBOT_S2, "dasar": None},
    "S3_tanpa_harga": {"label": "S3 jarak + kategori + rating", "bobot": BOBOT_S3, "dasar": None},
    "S4_penuh": {"label": "S4 skor penuh (usulan)", "bobot": BOBOT_S4, "dasar": None},
    "S_rating": {"label": "Baseline rating saja", "bobot": BOBOT_RATING, "dasar": "rating"},
}


# ---------------------------------------------------------------------------
# Precision@K dan NDCG@K (Persamaan 2.4–2.6) — siap untuk label bagian 5
# ---------------------------------------------------------------------------

def _pangkas(relevansi: Sequence[float], k: int) -> list[float]:
    """Ambil k nilai pertama; jika lebih pendek, dilengkapi nol (item kosong = tidak relevan)."""
    nilai = [float(x) for x in list(relevansi)[:k]]
    if len(nilai) < k:
        nilai = nilai + [0.0] * (k - len(nilai))
    return nilai


def precision_at_k(relevansi: Sequence[float], k: int = 10, ambang: float = 1.0) -> float:
    """Precision@K (Persamaan 2.4).

    ``rel_i`` dijadikan biner: 1 jika nilai ≥ ``ambang``, selain itu 0.
    Untuk penilaian responden (0/1/2), ambang bawaan 1 berarti nilai 1 dan 2
    dianggap relevan, sesuai Subbab 3.8.1. Pembagi selalu K, bukan panjang daftar.
    """
    if k < 1:
        raise ValueError("k harus paling sedikit 1.")
    biner = [1.0 if r >= ambang else 0.0 for r in _pangkas(relevansi, k)]
    return float(sum(biner) / k)


def dcg_at_k(relevansi: Sequence[float], k: int = 10) -> float:
    """DCG@K (Persamaan 2.5): sum_i (2^{rel_i} − 1) / log2(i+1)."""
    if k < 1:
        raise ValueError("k harus paling sedikit 1.")
    total = 0.0
    for i, rel in enumerate(_pangkas(relevansi, k), start=1):
        total += (2.0 ** rel - 1.0) / np.log2(i + 1.0)
    return float(total)


def ndcg_at_k(relevansi: Sequence[float], k: int = 10) -> float:
    """NDCG@K (Persamaan 2.6): DCG@K / IDCG@K.

    IDCG dihitung dari nilai relevansi yang sama, diurutkan menurun
    (urutan ideal pada item yang dinilai). Jika semua nilai 0, hasilnya 0.
    """
    if k < 1:
        raise ValueError("k harus paling sedikit 1.")
    aktual = _pangkas(relevansi, k)
    dcg = dcg_at_k(aktual, k)
    idcg = dcg_at_k(sorted(aktual, reverse=True), k)
    if idcg == 0.0:
        return 0.0
    return float(dcg / idcg)


# ---------------------------------------------------------------------------
# Relevansi proksi (Subbab 3.8.1) — BUKAN penilaian pengguna
# ---------------------------------------------------------------------------

def relevansi_proksi(
    kategori_merchant,
    rating,
    jarak_km: float,
    kategori_pengguna: Sequence[str] | None,
    radius_km: float,
    rating_ambang: float = PROXY_RATING_AMBANG,
    sudah_dinilai: bool | None = None,
) -> int:
    """Nilai proksi 0/1/2 menurut aturan TK1.

    * 2 jika kategori beririsan, rating ≥ 4,7, dan jarak ≤ R/2;
    * 1 jika hanya kategori yang beririsan;
    * 0 untuk lainnya.

    Jika pengguna tidak memilih kategori, irisan tidak dapat dihitung.
    Dalam kasus itu (perluasan yang dicatat di dokumentasi): 2 jika rating
    dan jarak memenuhi, 1 jika salah satu memenuhi, 0 jika tidak.
    """
    pilihan = {str(x) for x in (kategori_pengguna or ()) if str(x).strip()}
    merchant = set(pecah_kategori(kategori_merchant)) if not isinstance(kategori_merchant, (set, list, tuple)) else {str(x) for x in kategori_merchant if str(x)}
    irisan = bool(pilihan & merchant)

    try:
        rating_ok = (sudah_dinilai is not False) and (rating is not None) and (not pd.isna(rating)) and (float(rating) >= rating_ambang)
    except (TypeError, ValueError):
        rating_ok = False
    dekat = (radius_km > 0) and (float(jarak_km) <= (float(radius_km) / 2.0))

    if not pilihan:
        if rating_ok and dekat:
            return 2
        if rating_ok or dekat:
            return 1
        return 0
    if irisan and rating_ok and dekat:
        return 2
    if irisan:
        return 1
    return 0


def nilai_proksi_daftar(
    hasil: pd.DataFrame,
    kategori_pengguna: Sequence[str] | None,
    radius_km: float,
    k: int = 10,
) -> list[int]:
    """Daftar nilai proksi sepanjang k untuk satu hasil rekomendasi."""
    nilai: list[int] = []
    if hasil is not None and not hasil.empty:
        for rec in hasil.head(k).itertuples():
            sudah = getattr(rec, "sudah_dinilai", None)
            nilai.append(
                relevansi_proksi(
                    rec.kategori,
                    rec.rating,
                    float(rec.jarak_km),
                    kategori_pengguna,
                    radius_km,
                    sudah_dinilai=None if sudah is None else bool(sudah),
                )
            )
    if len(nilai) < k:
        nilai = nilai + [0] * (k - len(nilai))
    return nilai


# ---------------------------------------------------------------------------
# Metrik pendukung tanpa label (Subbab 3.8.1, Persamaan 3.7)
# ---------------------------------------------------------------------------

def cakupan_katalog(daftar_id_per_kueri: Iterable[Iterable], n_katalog: int) -> float:
    """Catalog coverage (Persamaan 3.7) dalam persen: |gabungan Top-N| / |I| × 100."""
    if n_katalog <= 0:
        raise ValueError("n_katalog harus positif.")
    gabungan: set = set()
    for ids in daftar_id_per_kueri:
        gabungan.update(ids)
    return 100.0 * len(gabungan) / n_katalog


def diversitas_intra_daftar(kategori_daftar: Sequence) -> float:
    """Rata-rata 1 − Jaccard antarkategori semua pasangan dalam satu daftar.

    Jika daftar berisi kurang dari 2 item, dikembalikan 0 (tidak terdefinisi
    secara matematis; nol dipilih agar agregasi tidak pecah).
    """
    himpunan = []
    for nilai in kategori_daftar:
        if isinstance(nilai, (set, list, tuple)):
            himpunan.append({str(x) for x in nilai if str(x)})
        else:
            himpunan.append(set(pecah_kategori(nilai)))
    n = len(himpunan)
    if n < 2:
        return 0.0
    nilai = []
    for i in range(n):
        for j in range(i + 1, n):
            nilai.append(1.0 - jaccard(himpunan[i], himpunan[j]))
    return float(np.mean(nilai))


def keunikan_merek(brand: str, frekuensi_merek: dict[str, int], n_katalog: int) -> float:
    """Keunikan (novelty) satu merchant: −log2(frekuensi merek / |I|).

    Dataset tidak punya jumlah ulasan, jadi popularitas didekati frekuensi merek
    pada katalog. Semakin jarang mereknya, semakin tinggi keunikannya.
    """
    if n_katalog <= 0:
        return 0.0
    freq = max(int(frekuensi_merek.get(str(brand), 1)), 1)
    p = freq / n_katalog
    return float(-np.log2(p))


def metrik_daftar(
    hasil: pd.DataFrame,
    kategori_pengguna: Sequence[str] | None,
    radius_km: float,
    budget_maks: int,
    k: int = 10,
    frekuensi_merek: dict[str, int] | None = None,
    n_katalog: int | None = None,
) -> dict[str, float]:
    """Kumpulkan metrik untuk satu daftar Top-k (termasuk P@k dan NDCG@k proksi)."""
    k = int(k)
    n = 0 if hasil is None or hasil.empty else int(len(hasil))
    proksi = nilai_proksi_daftar(hasil if n else pd.DataFrame(), kategori_pengguna, radius_km, k)
    keluar: dict[str, float] = {
        "n_hasil": float(n),
        "precision_at_k": precision_at_k(proksi, k),
        "ndcg_at_k": ndcg_at_k(proksi, k),
        "diversitas": 0.0,
        "jarak_rata": float("nan"),
        "rating_rata": float("nan"),
        "proporsi_dinilai": float("nan"),
        "price_fit": float("nan"),
        "keunikan_rata": float("nan"),
    }
    if n == 0:
        return keluar
    keluar["diversitas"] = diversitas_intra_daftar(list(hasil["kategori"]))
    keluar["jarak_rata"] = float(hasil["jarak_km"].mean())
    dinilai = hasil["rating"].notna()
    if "sudah_dinilai" in hasil.columns:
        dinilai = hasil["sudah_dinilai"].astype(bool) & dinilai
    keluar["proporsi_dinilai"] = float(dinilai.mean())
    if dinilai.any():
        keluar["rating_rata"] = float(hasil.loc[dinilai, "rating"].mean())
    keluar["price_fit"] = float((hasil["price_level"] <= int(budget_maks)).mean())
    if frekuensi_merek is not None and n_katalog:
        keluar["keunikan_rata"] = float(
            np.mean([keunikan_merek(b, frekuensi_merek, n_katalog) for b in hasil["brand"]])
        )
    return keluar


# ---------------------------------------------------------------------------
# Uji Wilcoxon bertanda (berpasangan), taraf 0,05
# ---------------------------------------------------------------------------

def uji_wilcoxon(a: Sequence[float], b: Sequence[float], alpha: float = 0.05) -> dict:
    """Uji Wilcoxon bertanda berpasangan: apakah selisih (a − b) berpusat di 0.

    ``a`` biasanya metrik S4, ``b`` metrik baseline, pada kueri yang sama.
    Selisih nol dibuang (metode 'wilcox'). Jika semua selisih nol atau
    sampel terlalu kecil, p-value tidak dihitung.
    """
    x = np.asarray(list(a), dtype=float)
    y = np.asarray(list(b), dtype=float)
    if x.shape != y.shape:
        raise ValueError("Kedua deret harus sama panjang.")
    mask = np.isfinite(x) & np.isfinite(y)
    x, y = x[mask], y[mask]
    selisih = x - y
    n = int(len(selisih))
    n_nol = int(np.sum(selisih == 0))
    n_pakai = n - n_nol
    ringkas = {
        "n": n,
        "n_selisih_nol": n_nol,
        "n_dipakai": n_pakai,
        "median_selisih": float(np.median(selisih)) if n else float("nan"),
        "rata_selisih": float(np.mean(selisih)) if n else float("nan"),
        "statistik": float("nan"),
        "p_value": float("nan"),
        "signifikan": False,
        "alpha": alpha,
        "catatan": "",
    }
    if n_pakai < 1:
        ringkas["catatan"] = "Tidak bisa dihitung: semua selisih nol atau data kosong."
        return ringkas
    try:
        statistik, p = wilcoxon(x, y, zero_method="wilcox", alternative="two-sided")
        ringkas["statistik"] = float(statistik)
        ringkas["p_value"] = float(p)
        ringkas["signifikan"] = bool(p < alpha)
    except ValueError as exc:
        ringkas["catatan"] = str(exc)
    return ringkas


# ---------------------------------------------------------------------------
# Menjalankan satu kueri pada satu metode
# ---------------------------------------------------------------------------

def pecah_kategori_skenario(teks) -> list[str]:
    if teks is None or (isinstance(teks, float) and np.isnan(teks)):
        return []
    return [s.strip() for s in str(teks).replace(";", "|").split("|") if s.strip()]


def jalankan_kueri(
    data: pd.DataFrame,
    baris_skenario,
    metode: str = "S4_penuh",
    k: int | None = None,
) -> tuple[pd.DataFrame, dict[str, float]]:
    """Jalankan satu skenario + satu metode, kembalikan (hasil, metrik)."""
    if metode not in METODE:
        raise ValueError(f"Metode tidak dikenal: {metode}")
    info = METODE[metode]
    k = int(k if k is not None else baris_skenario.k if hasattr(baris_skenario, "k") else 10)
    kategori = pecah_kategori_skenario(getattr(baris_skenario, "kategori", ""))
    radius = float(baris_skenario.radius_km)
    budget = int(baris_skenario.budget_maks)
    rating_min = float(baris_skenario.rating_min)
    lat, lon = float(baris_skenario.lat), float(baris_skenario.lon)

    if info["dasar"] in ("jarak", "rating"):
        hasil = rekomendasi_dasar(
            lat, lon,
            radius_km=radius,
            budget_maks=budget,
            rating_min=rating_min,
            kategori_pilihan=kategori,
            k=k,
            acuan=info["dasar"],
            data=data,
        )
    else:
        hasil = rekomendasi(
            lat, lon,
            radius_km=radius,
            budget_maks=budget,
            rating_min=rating_min,
            kategori_pilihan=kategori,
            k=k,
            bobot=info["bobot"],
            data=data,
        )
    freq = data["brand"].value_counts().to_dict()
    metrik = metrik_daftar(
        hasil, kategori, radius, budget, k=k,
        frekuensi_merek=freq, n_katalog=len(data),
    )
    return hasil, metrik
