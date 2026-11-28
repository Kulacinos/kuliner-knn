"""System Usability Scale (SUS) — Persamaan 2.7 laporan TK1.

Sepuluh butir standar Brooke (1996) disajikan dalam terjemahan Indonesia.
Jawaban memakai skala Likert 1 (sangat tidak setuju) sampai 5 (sangat setuju).
Butir ganjil bersifat positif (skor = s_i − 1), butir genap bersifat negatif
(skor = 5 − s_i). Jumlah dikali 2,5 sehingga rentang akhir 0–100.

Ambang NFR-02: rata-rata ≥ 70 digolongkan acceptable (dapat diterima)
menurut Bangor, Kortum, dan Miller (2008/2009).
"""

from __future__ import annotations

from typing import Sequence

# Terjemahan Indonesia dari 10 butir standar Brooke (1996).
PERNYATAAN_SUS: tuple[str, ...] = (
    "Saya pikir saya ingin menggunakan sistem ini secara rutin.",
    "Saya merasa sistem ini rumit secara tidak perlu.",
    "Saya pikir sistem ini mudah digunakan.",
    "Saya pikir saya membutuhkan dukungan dari orang teknis untuk dapat menggunakan sistem ini.",
    "Saya menemukan berbagai fungsi dalam sistem ini terintegrasi dengan baik.",
    "Saya pikir terlalu banyak ketidakkonsistenan dalam sistem ini.",
    "Saya membayangkan bahwa kebanyakan orang akan sangat cepat belajar menggunakan sistem ini.",
    "Saya merasa sistem ini sangat merepotkan untuk digunakan.",
    "Saya merasa sangat percaya diri menggunakan sistem ini.",
    "Saya perlu belajar banyak hal sebelum saya dapat menggunakan sistem ini dengan lancar.",
)

LABEL_LIKERT: dict[int, str] = {
    1: "Sangat tidak setuju",
    2: "Tidak setuju",
    3: "Netral",
    4: "Setuju",
    5: "Sangat setuju",
}

AMBANG_ACCEPTABLE = 70.0
AMBANG_MARGINAL = 50.0

# Titik tengah antar-rata-rata adjektiva Bangor, Kortum, & Miller (2009).
# Rata-rata yang dilaporkan: 12,5 / 20,3 / 35,7 / 50,9 / 71,4 / 85,5 / 90,9.
_AMBANG_ADJEKTIVA = (
    (88.2, "Best Imaginable", "Terbaik yang dibayangkan"),
    (78.45, "Excellent", "Unggul"),
    (61.15, "Good", "Baik"),
    (43.3, "OK", "Cukup"),
    (28.0, "Poor", "Kurang"),
    (16.4, "Awful", "Buruk"),
    (0.0, "Worst Imaginable", "Terburuk yang dibayangkan"),
)

# Skala huruf lengkung Sauro & Lewis (curved grading scale).
_AMBANG_HURUF = (
    (84.1, "A+"),
    (80.8, "A"),
    (78.9, "A-"),
    (77.2, "B+"),
    (74.1, "B"),
    (72.6, "B-"),
    (71.1, "C+"),
    (65.0, "C"),
    (62.7, "C-"),
    (51.7, "D"),
    (0.0, "F"),
)


def _bersihkan_jawaban(jawaban: Sequence[int | float]) -> list[int]:
    if jawaban is None or len(jawaban) != 10:
        raise ValueError("SUS memerlukan tepat 10 jawaban (butir 1 sampai 10).")
    bersih: list[int] = []
    for i, nilai in enumerate(jawaban, start=1):
        try:
            angka = int(nilai)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Jawaban butir {i} tidak valid: {nilai!r}.") from exc
        if angka != float(nilai):
            raise ValueError(f"Jawaban butir {i} harus bilangan bulat 1–5.")
        if angka < 1 or angka > 5:
            raise ValueError(f"Jawaban butir {i} harus antara 1 dan 5 (diterima {angka}).")
        bersih.append(angka)
    return bersih


def skor_sus(jawaban: Sequence[int | float]) -> float:
    """Hitung skor SUS 0–100 (Persamaan 2.7).

    Butir ganjil (1, 3, 5, 7, 9): s_i − 1.
    Butir genap (2, 4, 6, 8, 10): 5 − s_i.
    Jumlah kontribusi (0–40) dikalikan 2,5.
    """
    bersih = _bersihkan_jawaban(jawaban)
    total = 0
    for i, s in enumerate(bersih, start=1):
        if i % 2 == 1:
            total += s - 1
        else:
            total += 5 - s
    return float(total * 2.5)


def keberterimaan(skor: float) -> str:
    """Kategori acceptable / marginal / not acceptable (Bangor dkk.; NFR-02)."""
    if skor >= AMBANG_ACCEPTABLE:
        return "acceptable"
    if skor >= AMBANG_MARGINAL:
        return "marginal"
    return "not acceptable"


def label_keberterimaan(skor: float) -> str:
    peta = {
        "acceptable": "dapat diterima",
        "marginal": "marginal",
        "not acceptable": "tidak dapat diterima",
    }
    return peta[keberterimaan(skor)]


def adjektiva(skor: float) -> tuple[str, str]:
    """Kembalikan (label Inggris, label Indonesia) menurut skala adjektiva Bangor."""
    for ambang, en, idn in _AMBANG_ADJEKTIVA:
        if skor >= ambang:
            return en, idn
    return "Worst Imaginable", "Terburuk yang dibayangkan"


def huruf(skor: float) -> str:
    """Nilai huruf menurut curved grading scale Sauro & Lewis."""
    for ambang, label in _AMBANG_HURUF:
        if skor >= ambang:
            return label
    return "F"


def ringkasan_skor(jawaban: Sequence[int | float] | None = None, skor: float | None = None) -> dict:
    """Paket lengkap: skor, huruf, adjektiva, dan keberterimaan."""
    if skor is None:
        if jawaban is None:
            raise ValueError("Berikan jawaban atau skor.")
        skor = skor_sus(jawaban)
    en, idn = adjektiva(skor)
    return {
        "skor": float(skor),
        "huruf": huruf(skor),
        "adjektiva": en,
        "adjektiva_id": idn,
        "keberterimaan": keberterimaan(skor),
        "keberterimaan_id": label_keberterimaan(skor),
        "memenuhi_nfr02": bool(skor >= AMBANG_ACCEPTABLE),
    }


def ringkasan_kumpulan(daftar_skor: Sequence[float], ambang: float = AMBANG_ACCEPTABLE) -> dict:
    """Statistik deskriptif untuk kumpulan skor responden."""
    import numpy as np

    if not daftar_skor:
        raise ValueError("Daftar skor SUS kosong.")
    arr = np.asarray(list(daftar_skor), dtype=float)
    rata = float(arr.mean())
    info = ringkasan_skor(skor=rata)
    info.update(
        {
            "n": int(len(arr)),
            "rata": rata,
            "median": float(np.median(arr)),
            "min": float(arr.min()),
            "maks": float(arr.max()),
            "stdev": float(arr.std(ddof=1)) if len(arr) > 1 else 0.0,
            "n_memenuhi_nfr02": int((arr >= ambang).sum()),
            "ambang_nfr02": float(ambang),
        }
    )
    return info
