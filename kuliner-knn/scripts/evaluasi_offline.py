"""Menjalankan evaluasi offline (bagian 4) dan menulis laporan ke reports/.

Contoh:

    python scripts/evaluasi_offline.py

Katalog dibaca dari SQLite jika `data/kuliner.db` ada, selain itu dari CSV bersih.
Luaran: CSV/JSON metrik dan beberapa grafik PNG di `reports/evaluasi_offline/`.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from kuliner.config import PATH_BERSIH, PATH_DB  # noqa: E402
from kuliner.evaluasi import (  # noqa: E402
    METODE,
    cakupan_katalog,
    jalankan_kueri,
    pecah_kategori_skenario,
    uji_wilcoxon,
)
from kuliner.recommender import muat_katalog, rekomendasi  # noqa: E402

PATH_SKENARIO = ROOT / "data" / "evaluasi" / "skenario.csv"
DIR_LAPORAN = ROOT / "reports" / "evaluasi_offline"

WARNA = {
    "S1_jarak": "#6B7280",
    "S2_jarak_kategori": "#3B82F6",
    "S3_tanpa_harga": "#F59E0B",
    "S4_penuh": "#2E7D32",
    "S_rating": "#C2410C",
}
URUTAN_METODE = list(METODE.keys())
LABEL_METODE = {k: v["label"] for k, v in METODE.items()}

# Grid bobot S5 (langkah 0,05; jumlah 1; lokasi ≥ 0,20) dijalankan
# pada subset kueri agar runtime tetap nyaman di mesin mahasiswa.
N_S5_KUERI = 15
LANGKAH_BOBOT = 0.05
RADIUS_S6 = (1, 3, 5, 10)


def _muat_data():
    if PATH_DB.exists():
        return muat_katalog(sumber="sqlite", path_db=PATH_DB, ulang=True)
    return muat_katalog(sumber="csv", path_csv=PATH_BERSIH, ulang=True)


def _metrik_k(hasil, kategori, radius, budget, k, freq, n_katalog):
    from kuliner.evaluasi import metrik_daftar

    return metrik_daftar(hasil, kategori, radius, budget, k=k, frekuensi_merek=freq, n_katalog=n_katalog)


def jalankan_utama(data: pd.DataFrame, skenario: pd.DataFrame) -> pd.DataFrame:
    """Semua kueri × lima metode; daftar diambil 10 item, metrik @5 dan @10."""
    freq = data["brand"].value_counts().to_dict()
    n_katalog = len(data)
    baris = []
    for rec in skenario.itertuples():
        for metode in URUTAN_METODE:
            hasil, _ = jalankan_kueri(data, rec, metode=metode, k=10)
            ids = list(hasil["id"]) if len(hasil) else []
            m5 = _metrik_k(hasil.head(5), pecah_kategori_skenario(rec.kategori), rec.radius_km, rec.budget_maks, 5, freq, n_katalog)
            m10 = _metrik_k(hasil, pecah_kategori_skenario(rec.kategori), rec.radius_km, rec.budget_maks, 10, freq, n_katalog)
            baris.append({
                "id": rec.id,
                "kota": rec.kota,
                "kecamatan": rec.kecamatan,
                "metode": metode,
                "label_metode": LABEL_METODE[metode],
                "radius_km": rec.radius_km,
                "budget_maks": rec.budget_maks,
                "rating_min": rec.rating_min,
                "kategori": rec.kategori,
                "n_hasil": int(len(hasil)),
                "precision_at_5": m5["precision_at_k"],
                "ndcg_at_5": m5["ndcg_at_k"],
                "precision_at_10": m10["precision_at_k"],
                "ndcg_at_10": m10["ndcg_at_k"],
                "diversitas": m10["diversitas"],
                "jarak_rata": m10["jarak_rata"],
                "rating_rata": m10["rating_rata"],
                "proporsi_dinilai": m10["proporsi_dinilai"],
                "price_fit": m10["price_fit"],
                "keunikan_rata": m10["keunikan_rata"],
                "id_top": "|".join(str(x) for x in ids),
            })
    return pd.DataFrame(baris)


def ringkas(hasil: pd.DataFrame, n_katalog: int) -> pd.DataFrame:
    keluar = []
    for metode, potong in hasil.groupby("metode", sort=False):
        ids = [s.split("|") if s else [] for s in potong["id_top"].fillna("")]
        keluar.append({
            "metode": metode,
            "label_metode": LABEL_METODE[metode],
            "n_kueri": int(len(potong)),
            "n_kueri_kosong": int((potong["n_hasil"] == 0).sum()),
            "precision_at_5_rata": float(potong["precision_at_5"].mean()),
            "precision_at_10_rata": float(potong["precision_at_10"].mean()),
            "ndcg_at_5_rata": float(potong["ndcg_at_5"].mean()),
            "ndcg_at_10_rata": float(potong["ndcg_at_10"].mean()),
            "precision_at_10_median": float(potong["precision_at_10"].median()),
            "ndcg_at_10_median": float(potong["ndcg_at_10"].median()),
            "diversitas_rata": float(potong["diversitas"].mean()),
            "jarak_rata": float(np.nanmean(potong["jarak_rata"])),
            "rating_rata": float(np.nanmean(potong["rating_rata"])),
            "price_fit_rata": float(np.nanmean(potong["price_fit"])),
            "keunikan_rata": float(np.nanmean(potong["keunikan_rata"])),
            "cakupan_pct": cakupan_katalog(ids, n_katalog),
        })
    return pd.DataFrame(keluar)


def bangun_wilcoxon(hasil: pd.DataFrame) -> dict:
    def deret(metode, kolom):
        return hasil.loc[hasil["metode"] == metode].sort_values("id")[kolom].to_numpy()

    pasangan = [
        ("S4_penuh", "S1_jarak", "precision_at_10"),
        ("S4_penuh", "S1_jarak", "ndcg_at_10"),
        ("S4_penuh", "S_rating", "precision_at_10"),
        ("S4_penuh", "S_rating", "ndcg_at_10"),
        ("S4_penuh", "S2_jarak_kategori", "precision_at_10"),
        ("S4_penuh", "S3_tanpa_harga", "precision_at_10"),
    ]
    keluar = {}
    for a, b, kolom in pasangan:
        kunci = f"{a}_vs_{b}__{kolom}"
        uji = uji_wilcoxon(deret(a, kolom), deret(b, kolom))
        uji["metode_a"] = a
        uji["metode_b"] = b
        uji["metrik"] = kolom
        keluar[kunci] = uji
    return keluar


def jalankan_s6(data: pd.DataFrame, skenario: pd.DataFrame) -> pd.DataFrame:
    """Sensitivitas radius (S6): S4 pada R = 1, 3, 5, 10 km."""
    freq = data["brand"].value_counts().to_dict()
    n_katalog = len(data)
    baris = []
    for rec in skenario.itertuples():
        for radius in RADIUS_S6:
            # Salin skenario, ganti radius.
            rec2 = rec._replace(radius_km=radius)
            hasil, metrik = jalankan_kueri(data, rec2, metode="S4_penuh", k=10)
            baris.append({
                "id": rec.id,
                "kota": rec.kota,
                "radius_km": radius,
                "n_hasil": int(len(hasil)),
                "precision_at_10": metrik["precision_at_k"],
                "ndcg_at_10": metrik["ndcg_at_k"],
                "diversitas": metrik["diversitas"],
                "jarak_rata": metrik["jarak_rata"],
            })
    return pd.DataFrame(baris)


def _grid_bobot(langkah: float = LANGKAH_BOBOT, lokasi_min: float = 0.20):
    n = int(round(1.0 / langkah))
    kombinasi = []
    for i_l in range(int(round(lokasi_min / langkah)), n + 1):
        sisa = n - i_l
        for i_k in range(sisa + 1):
            for i_r in range(sisa - i_k + 1):
                i_h = sisa - i_k - i_r
                kombinasi.append({
                    "lokasi": round(i_l * langkah, 4),
                    "kategori": round(i_k * langkah, 4),
                    "rating": round(i_r * langkah, 4),
                    "harga": round(i_h * langkah, 4),
                })
    return kombinasi


def jalankan_s5(data: pd.DataFrame, skenario: pd.DataFrame, n_kueri: int = N_S5_KUERI) -> pd.DataFrame:
    """Grid bobot S5 pada subset kueri; pilih konfigurasi berdasar rata-rata NDCG@10 proksi."""
    subset = skenario.head(n_kueri)
    grid = _grid_bobot()
    freq = data["brand"].value_counts().to_dict()
    n_katalog = len(data)
    ringkas_grid = []
    for bobot in grid:
        p10, n10 = [], []
        for rec in subset.itertuples():
            hasil = rekomendasi(
                float(rec.lat), float(rec.lon),
                radius_km=float(rec.radius_km),
                budget_maks=int(rec.budget_maks),
                rating_min=float(rec.rating_min),
                kategori_pilihan=pecah_kategori_skenario(rec.kategori),
                k=10,
                bobot=bobot,
                data=data,
            )
            m = _metrik_k(hasil, pecah_kategori_skenario(rec.kategori), rec.radius_km, rec.budget_maks, 10, freq, n_katalog)
            p10.append(m["precision_at_k"])
            n10.append(m["ndcg_at_k"])
        ringkas_grid.append({
            **bobot,
            "n_kueri": int(len(subset)),
            "precision_at_10_rata": float(np.mean(p10)),
            "ndcg_at_10_rata": float(np.mean(n10)),
        })
    df = pd.DataFrame(ringkas_grid)
    df = df.sort_values(["ndcg_at_10_rata", "precision_at_10_rata"], ascending=False).reset_index(drop=True)
    df.insert(0, "peringkat", np.arange(1, len(df) + 1))
    return df


def _siapkan_gaya():
    plt.rcParams.update({
        "figure.dpi": 120,
        "savefig.dpi": 140,
        "font.size": 10,
        "axes.titlesize": 11,
        "axes.labelsize": 10,
        "axes.grid": True,
        "grid.alpha": 0.3,
        "axes.spines.top": False,
        "axes.spines.right": False,
    })


def _boxplot(ax, hasil: pd.DataFrame, kolom: str, judul: str, ylabel: str):
    data_plot, labels, colors = [], [], []
    for metode in URUTAN_METODE:
        data_plot.append(hasil.loc[hasil["metode"] == metode, kolom].dropna().to_numpy())
        labels.append(LABEL_METODE[metode].replace(" + ", "\n+ "))
        colors.append(WARNA[metode])
    bp = ax.boxplot(data_plot, tick_labels=labels, patch_artist=True, medianprops={"color": "black"})
    for patch, color in zip(bp["boxes"], colors):
        patch.set_facecolor(color)
        patch.set_alpha(0.75)
    ax.set_title(judul)
    ax.set_ylabel(ylabel)
    ax.tick_params(axis="x", labelsize=8)


def tulis_grafik(hasil: pd.DataFrame, ringkasan: pd.DataFrame, s6: pd.DataFrame, folder: Path) -> list[str]:
    _siapkan_gaya()
    jalur = []

    fig, axes = plt.subplots(1, 2, figsize=(11, 4.6))
    _boxplot(axes[0], hasil, "precision_at_10", "Precision@10 (relevansi proksi)", "Precision@10")
    _boxplot(axes[1], hasil, "ndcg_at_10", "NDCG@10 (relevansi proksi)", "NDCG@10")
    fig.tight_layout()
    p = folder / "p10_ndcg_boxplot.png"
    fig.savefig(p, bbox_inches="tight")
    plt.close(fig)
    jalur.append(str(p.relative_to(ROOT)))

    fig, axes = plt.subplots(1, 2, figsize=(11, 4.6))
    _boxplot(axes[0], hasil, "jarak_rata", "Jarak rata-rata Top-10", "km")
    _boxplot(axes[1], hasil, "diversitas", "Diversitas intra-daftar Top-10", "1 − Jaccard")
    fig.tight_layout()
    p = folder / "jarak_diversitas_boxplot.png"
    fig.savefig(p, bbox_inches="tight")
    plt.close(fig)
    jalur.append(str(p.relative_to(ROOT)))

    fig, ax = plt.subplots(figsize=(8, 4.2))
    x = np.arange(len(URUTAN_METODE))
    y = [float(ringkasan.loc[ringkasan["metode"] == m, "cakupan_pct"].iloc[0]) for m in URUTAN_METODE]
    bars = ax.bar(x, y, color=[WARNA[m] for m in URUTAN_METODE], edgecolor="none")
    ax.set_xticks(x)
    ax.set_xticklabels([LABEL_METODE[m].replace(" + ", "\n+ ") for m in URUTAN_METODE], fontsize=8)
    ax.set_ylabel("Cakupan katalog (%)")
    ax.set_title("Catalog coverage (Persamaan 3.7)")
    for b, v in zip(bars, y):
        ax.text(b.get_x() + b.get_width() / 2, b.get_height() + 0.15, f"{v:.2f}", ha="center", va="bottom", fontsize=8)
    fig.tight_layout()
    p = folder / "cakupan_katalog.png"
    fig.savefig(p, bbox_inches="tight")
    plt.close(fig)
    jalur.append(str(p.relative_to(ROOT)))

    fig, axes = plt.subplots(1, 2, figsize=(10, 4.2))
    agg = s6.groupby("radius_km", as_index=False).agg(
        precision_at_10=("precision_at_10", "mean"),
        ndcg_at_10=("ndcg_at_10", "mean"),
        jarak_rata=("jarak_rata", "mean"),
        n_hasil=("n_hasil", "mean"),
    )
    axes[0].plot(agg["radius_km"], agg["precision_at_10"], "o-", color=WARNA["S4_penuh"], label="P@10")
    axes[0].plot(agg["radius_km"], agg["ndcg_at_10"], "s--", color="#1B5E20", label="NDCG@10")
    axes[0].set_xlabel("Radius (km)")
    axes[0].set_ylabel("Rata-rata metrik proksi")
    axes[0].set_title("S6: sensitivitas radius (S4)")
    axes[0].legend()
    axes[1].plot(agg["radius_km"], agg["jarak_rata"], "o-", color="#1565C0", label="Jarak rata-rata")
    axes[1].set_xlabel("Radius (km)")
    axes[1].set_ylabel("km")
    axes[1].set_title("S6: jarak rata-rata Top-10")
    fig.tight_layout()
    p = folder / "sensitivitas_radius.png"
    fig.savefig(p, bbox_inches="tight")
    plt.close(fig)
    jalur.append(str(p.relative_to(ROOT)))

    return jalur


def main() -> int:
    DIR_LAPORAN.mkdir(parents=True, exist_ok=True)
    t0 = time.perf_counter()
    print("Memuat katalog...")
    data = _muat_data()
    skenario = pd.read_csv(PATH_SKENARIO)
    print(f"  {len(data):,} merchant, {len(skenario)} skenario.")

    print("Menjalankan S1–S4 dan baseline rating...")
    t1 = time.perf_counter()
    hasil = jalankan_utama(data, skenario)
    print(f"  selesai dalam {time.perf_counter() - t1:.1f} s.")

    ringkasan = ringkas(hasil, len(data))
    wilcox = bangun_wilcoxon(hasil)

    print("Menjalankan S6 (radius 1/3/5/10 km)...")
    t1 = time.perf_counter()
    s6 = jalankan_s6(data, skenario)
    print(f"  selesai dalam {time.perf_counter() - t1:.1f} s.")

    print(f"Menjalankan S5 (grid bobot langkah 0,05 pada {N_S5_KUERI} kueri pertama)...")
    t1 = time.perf_counter()
    s5 = jalankan_s5(data, skenario, n_kueri=N_S5_KUERI)
    print(f"  {len(s5)} kombinasi, selesai dalam {time.perf_counter() - t1:.1f} s.")

    hasil.to_csv(DIR_LAPORAN / "hasil_per_skenario.csv", index=False, float_format="%.6f")
    ringkasan.to_csv(DIR_LAPORAN / "ringkasan.csv", index=False, float_format="%.6f")
    s6.to_csv(DIR_LAPORAN / "sensitivitas_radius.csv", index=False, float_format="%.6f")
    s5.to_csv(DIR_LAPORAN / "grid_bobot.csv", index=False, float_format="%.6f")
    (DIR_LAPORAN / "wilcoxon.json").write_text(
        json.dumps(wilcox, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    grafik = tulis_grafik(hasil, ringkasan, s6, DIR_LAPORAN)

    meta = {
        "n_katalog": int(len(data)),
        "n_skenario": int(len(skenario)),
        "n_kota": int(skenario["kota"].nunique()),
        "metode": URUTAN_METODE,
        "peringatan_proksi": (
            "Precision@K dan NDCG@K memakai relevansi proksi Subbab 3.8.1, "
            "bukan penilaian responden. Aturan ini condong menguntungkan skor gabungan."
        ),
        "s5": {
            "n_kueri": N_S5_KUERI,
            "n_kombinasi": int(len(s5)),
            "langkah": LANGKAH_BOBOT,
            "lokasi_min": 0.20,
            "terbaik": s5.iloc[0][["lokasi", "kategori", "rating", "harga", "ndcg_at_10_rata", "precision_at_10_rata"]].to_dict(),
        },
        "durasi_detik": round(time.perf_counter() - t0, 2),
        "grafik": grafik,
    }
    (DIR_LAPORAN / "meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False, default=float) + "\n", encoding="utf-8")

    print("\nRingkasan (rata-rata, relevansi proksi):")
    tampil = ringkasan[["label_metode", "precision_at_10_rata", "ndcg_at_10_rata", "cakupan_pct", "diversitas_rata", "jarak_rata", "price_fit_rata"]]
    print(tampil.to_string(index=False, float_format=lambda x: f"{x:.4f}"))
    print("\nWilcoxon (berpasangan, α=0,05):")
    for kunci, uji in wilcox.items():
        p = uji["p_value"]
        p_txt = "n/a" if p != p else f"{p:.4g}"
        sig = "signifikan" if uji["signifikan"] else "tidak signifikan"
        print(f"  {kunci}: p={p_txt}, median selisih={uji['median_selisih']:.4f} ({sig})")
    print(f"\nLuaran tertulis di {DIR_LAPORAN.relative_to(ROOT)} ({time.perf_counter() - t0:.1f} s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
