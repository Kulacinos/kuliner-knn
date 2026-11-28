"""Alat penilaian relevansi oleh responden (skala 0/1/2).

Sesuai Subbab 3.8.1 laporan TK1: untuk setiap kueri, responden menilai
gabungan hasil Top-10 dari skenario yang dibandingkan, ditampilkan dalam
urutan acak tanpa keterangan metode, dengan skala 0 (tidak relevan),
1 (cukup relevan), dan 2 (sangat relevan).

Precision@10 menganggap nilai 1 dan 2 sebagai relevan; NDCG@10 memakai
nilai bertingkat 0–2 (fungsi di kuliner.evaluasi).

Berkas contoh di data/evaluasi/contoh_penilaian_relevansi.csv adalah
DATA TIRUAN untuk uji dan demonstrasi skrip, BUKAN hasil responden.
"""

from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Sequence

import numpy as np
import pandas as pd

from kuliner.config import AKAR_REPO, PATH_DATA
from kuliner.evaluasi import (
    METODE,
    jalankan_kueri,
    ndcg_at_k,
    pecah_kategori_skenario,
    precision_at_k,
    uji_wilcoxon,
)

LABEL_RELEVANSI: dict[int, str] = {
    0: "Tidak relevan",
    1: "Cukup relevan",
    2: "Sangat relevan",
}

SUMBER_CONTOH = "CONTOH_BUKAN_DATA_NYATA"
PREFIKS_CONTOH = "CONTOH"

PATH_SKENARIO = PATH_DATA / "evaluasi" / "skenario.csv"
PATH_CONTOH_PENILAIAN = PATH_DATA / "evaluasi" / "contoh_penilaian_relevansi.csv"
PATH_CONTOH_SUS = PATH_DATA / "evaluasi" / "contoh_jawaban_sus.csv"
DIR_HASIL = PATH_DATA / "evaluasi" / "hasil"
PATH_HASIL_PENILAIAN = DIR_HASIL / "penilaian_relevansi.csv"
PATH_HASIL_SUS = DIR_HASIL / "sus.csv"
PATH_DB_HASIL = DIR_HASIL / "evaluasi_pengguna.db"

METODE_BANDING_DEFAULT = ("S1_jarak", "S4_penuh")

_WIB = timezone(timedelta(hours=8))

KOL_PENILAIAN = [
    "waktu_iso",
    "kode_responden",
    "id_skenario",
    "id_merchant",
    "nama",
    "peringkat_tampil",
    "nilai",
    "metode_sumber",
    "peringkat_per_metode",
    "sumber",
]

KOL_SUS = [
    "waktu_iso",
    "kode_responden",
    "s1", "s2", "s3", "s4", "s5", "s6", "s7", "s8", "s9", "s10",
    "skor",
    "sumber",
]


def waktu_sekarang() -> str:
    """Stempel waktu ISO di zona Asia/Makassar (UTC+8)."""
    return datetime.now(_WIB).isoformat(timespec="seconds")


def adalah_contoh(kode_atau_sumber: str | None) -> bool:
    teks = str(kode_atau_sumber or "").strip()
    return teks.startswith(PREFIKS_CONTOH) or teks == SUMBER_CONTOH


def validasi_kode_responden(kode: str, *, izinkan_contoh: bool = False) -> str:
    kode = str(kode or "").strip()
    if not kode:
        raise ValueError("Kode responden wajib diisi.")
    if len(kode) > 40:
        raise ValueError("Kode responden terlalu panjang (maksimum 40 karakter).")
    if not re.fullmatch(r"[A-Za-z0-9_-]+", kode):
        raise ValueError("Kode responden hanya boleh huruf, angka, garis bawah, atau tanda hubung.")
    if adalah_contoh(kode) and not izinkan_contoh:
        raise ValueError(
            "Kode yang diawali 'CONTOH' dicadangkan untuk data tiruan. "
            "Pakai kode lain untuk responden nyata."
        )
    return kode


def muat_skenario(path: Path | None = None) -> pd.DataFrame:
    p = Path(path) if path else PATH_SKENARIO
    df = pd.read_csv(p)
    if "id" not in df.columns:
        raise ValueError(f"Berkas skenario tidak punya kolom id: {p}")
    return df


def label_skenario(baris) -> str:
    kats = str(getattr(baris, "kategori", "") or "")
    kats = kats.replace("|", ", ") or "(tanpa kategori)"
    return (
        f"{baris.id} · {baris.kota} – {baris.kecamatan} · "
        f"R={int(baris.radius_km)} km, budget {int(baris.budget_maks)}, "
        f"rating ≥ {baris.rating_min} · {kats}"
    )


def daftar_hasil_metode(
    data: pd.DataFrame,
    baris_skenario,
    metode: Sequence[str],
    k: int = 10,
) -> dict[str, pd.DataFrame]:
    """Top-k setiap metode untuk satu skenario (kunci = kode metode)."""
    keluar = {}
    for m in metode:
        if m not in METODE:
            raise ValueError(f"Metode tidak dikenal: {m}")
        hasil, _ = jalankan_kueri(data, baris_skenario, metode=m, k=k)
        keluar[m] = hasil
    return keluar


def kumpulan_item_penilaian(
    data: pd.DataFrame,
    baris_skenario,
    metode: Sequence[str] = METODE_BANDING_DEFAULT,
    k: int = 10,
    seed: int | str | None = None,
) -> pd.DataFrame:
    """Gabungan Top-k dari beberapa metode, diacak, tanpa label metode.

    Kolom ``metode_sumber`` dan ``peringkat_per_metode`` disimpan untuk
    perhitungan metrik, tetapi tidak boleh ditampilkan kepada responden.
    """
    per_metode = daftar_hasil_metode(data, baris_skenario, metode, k=k)
    peta: dict[str, dict] = {}
    for m, hasil in per_metode.items():
        if hasil is None or hasil.empty:
            continue
        for rec in hasil.itertuples():
            mid = str(rec.id)
            if mid not in peta:
                peta[mid] = {
                    "id_merchant": mid,
                    "nama": rec.nama,
                    "kota": getattr(rec, "kota", ""),
                    "kecamatan": getattr(rec, "kecamatan", ""),
                    "kategori": rec.kategori,
                    "rating": rec.rating,
                    "price_level": rec.price_level,
                    "jarak_km": rec.jarak_km,
                    "sudah_dinilai": getattr(rec, "sudah_dinilai", True),
                    "latitude": getattr(rec, "latitude", np.nan),
                    "longitude": getattr(rec, "longitude", np.nan),
                    "peringkat_metode": {},
                }
            peta[mid]["peringkat_metode"][m] = int(rec.peringkat)
    if not peta:
        return pd.DataFrame()

    baris = []
    for item in peta.values():
        pm = item.pop("peringkat_metode")
        item["metode_sumber"] = "|".join(sorted(pm))
        item["peringkat_per_metode"] = ";".join(f"{m}:{p}" for m, p in sorted(pm.items()))
        baris.append(item)
    df = pd.DataFrame(baris)
    if seed is None:
        urutan = np.arange(len(df))
        rng = np.random.RandomState(0)
        rng.shuffle(urutan)
        df = df.iloc[urutan].reset_index(drop=True)
    else:
        if isinstance(seed, str):
            seed_int = int(abs(hash(seed)) % (2**31 - 1))
        else:
            seed_int = int(seed)
        rng = np.random.RandomState(seed_int)
        df = df.sample(frac=1.0, random_state=rng).reset_index(drop=True)
    df.insert(0, "peringkat_tampil", np.arange(1, len(df) + 1))
    return df


def seed_acak(kode_responden: str, id_skenario: str) -> int:
    """Biji deterministik agar urutan tampil stabil untuk responden yang sama."""
    digest = hashlib.md5(f"{kode_responden}::{id_skenario}".encode("utf-8")).hexdigest()
    return int(digest[:8], 16)


def _baca_csv(path: Path, kolom: list[str]) -> pd.DataFrame:
    if not path.exists() or path.stat().st_size == 0:
        return pd.DataFrame(columns=kolom)
    df = pd.read_csv(path)
    for k in kolom:
        if k not in df.columns:
            df[k] = pd.NA
    return df[kolom]


def muat_penilaian(path: Path | None = None) -> pd.DataFrame:
    return _baca_csv(Path(path) if path else PATH_HASIL_PENILAIAN, KOL_PENILAIAN)


def muat_sus(path: Path | None = None) -> pd.DataFrame:
    return _baca_csv(Path(path) if path else PATH_HASIL_SUS, KOL_SUS)


def _tulis_sqlite(nama_tabel: str, df: pd.DataFrame, path_db: Path) -> None:
    import sqlite3

    path_db.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path_db) as kon:
        df.to_sql(nama_tabel, kon, if_exists="replace", index=False)


def simpan_penilaian(
    df_baru: pd.DataFrame,
    path_csv: Path | None = None,
    path_db: Path | None = None,
) -> pd.DataFrame:
    """Tambah/timpa penilaian (kunci: responden + skenario + merchant)."""
    path_csv = Path(path_csv) if path_csv else PATH_HASIL_PENILAIAN
    path_db = Path(path_db) if path_db else PATH_DB_HASIL
    path_csv.parent.mkdir(parents=True, exist_ok=True)
    lama = muat_penilaian(path_csv)
    baru = df_baru.copy()
    for k in KOL_PENILAIAN:
        if k not in baru.columns:
            baru[k] = pd.NA
    potongan = [lama, baru[KOL_PENILAIAN]] if not lama.empty else [baru[KOL_PENILAIAN]]
    gabung = pd.concat(potongan, ignore_index=True)
    gabung = gabung.drop_duplicates(["kode_responden", "id_skenario", "id_merchant"], keep="last")
    gabung.to_csv(path_csv, index=False)
    try:
        _tulis_sqlite("penilaian_relevansi", gabung, path_db)
    except Exception:
        # CSV tetap sumber utama jika SQLite gagal (berkas diabaikan git).
        pass
    return gabung


def simpan_sus(
    df_baru: pd.DataFrame,
    path_csv: Path | None = None,
    path_db: Path | None = None,
) -> pd.DataFrame:
    path_csv = Path(path_csv) if path_csv else PATH_HASIL_SUS
    path_db = Path(path_db) if path_db else PATH_DB_HASIL
    path_csv.parent.mkdir(parents=True, exist_ok=True)
    lama = muat_sus(path_csv)
    baru = df_baru.copy()
    for k in KOL_SUS:
        if k not in baru.columns:
            baru[k] = pd.NA
    potongan = [lama, baru[KOL_SUS]] if not lama.empty else [baru[KOL_SUS]]
    gabung = pd.concat(potongan, ignore_index=True)
    gabung = gabung.drop_duplicates(["kode_responden"], keep="last")
    gabung.to_csv(path_csv, index=False)
    try:
        _tulis_sqlite("sus", gabung, path_db)
    except Exception:
        pass
    return gabung


def _peringkat_dari_teks(teks: str, metode: str) -> int | None:
    if teks is None or (isinstance(teks, float) and pd.isna(teks)):
        return None
    for potong in str(teks).split(";"):
        if ":" not in potong:
            continue
        m, _, p = potong.partition(":")
        if m.strip() == metode:
            try:
                return int(p)
            except ValueError:
                return None
    return None


def metrik_dari_penilaian(
    penilaian: pd.DataFrame,
    data: pd.DataFrame,
    skenario: pd.DataFrame,
    metode: Sequence[str] | None = None,
    k: int = 10,
) -> pd.DataFrame:
    """Precision@K dan NDCG@K dari penilaian manusia, per responden–skenario–metode.

    Urutan item mengikuti perangkingan metode (bukan urutan tampilan acak).
    Item Top-k yang tidak dinilai dianggap tidak relevan (0).
    """
    if penilaian is None or penilaian.empty:
        return pd.DataFrame()
    metode = list(metode) if metode else list(METODE_BANDING_DEFAULT)
    skenario = skenario.set_index("id", drop=False)
    baris_keluar = []
    for (kode, sid), potong in penilaian.groupby(["kode_responden", "id_skenario"], sort=False):
        if sid not in skenario.index:
            continue
        rec = skenario.loc[sid]
        if isinstance(rec, pd.DataFrame):
            rec = rec.iloc[0]
        peta_nilai = {
            str(r.id_merchant): int(r.nilai)
            for r in potong.itertuples()
            if pd.notna(r.nilai)
        }
        # Metode yang muncul pada penilaian ini, plus daftar yang diminta.
        metode_ada = set(metode)
        for teks in potong["metode_sumber"].fillna(""):
            metode_ada.update(x for x in str(teks).split("|") if x)
        for m in metode:
            if m not in METODE:
                continue
            hasil, _ = jalankan_kueri(data, rec, metode=m, k=k)
            if hasil is None or hasil.empty:
                rel = [0] * k
            else:
                rel = [peta_nilai.get(str(i), 0) for i in hasil["id"].head(k)]
                if len(rel) < k:
                    rel = rel + [0] * (k - len(rel))
            baris_keluar.append({
                "kode_responden": kode,
                "id_skenario": sid,
                "metode": m,
                "label_metode": METODE[m]["label"],
                "n_dinilai": int(len(peta_nilai)),
                "precision_at_k": precision_at_k(rel, k=k, ambang=1),
                "ndcg_at_k": ndcg_at_k(rel, k=k),
                "sumber": potong["sumber"].iloc[0] if "sumber" in potong.columns else "",
                "adalah_contoh": bool(
                    adalah_contoh(kode)
                    or (len(potong) and adalah_contoh(str(potong["sumber"].iloc[0])))
                ),
            })
    return pd.DataFrame(baris_keluar)


def ringkas_metrik_manusia(hasil: pd.DataFrame) -> pd.DataFrame:
    if hasil is None or hasil.empty:
        return pd.DataFrame()
    keluar = []
    for metode, potong in hasil.groupby("metode", sort=False):
        keluar.append({
            "metode": metode,
            "label_metode": potong["label_metode"].iloc[0],
            "n_pasangan": int(len(potong)),
            "n_responden": int(potong["kode_responden"].nunique()),
            "n_skenario": int(potong["id_skenario"].nunique()),
            "precision_at_k_rata": float(potong["precision_at_k"].mean()),
            "ndcg_at_k_rata": float(potong["ndcg_at_k"].mean()),
            "adalah_contoh": bool(potong["adalah_contoh"].all()) if "adalah_contoh" in potong else False,
        })
    return pd.DataFrame(keluar)


def wilcoxon_manusia(hasil: pd.DataFrame, metode_a: str, metode_b: str, kolom: str = "precision_at_k") -> dict:
    """Uji berpasangan pada kueri yang dinilai responden yang sama."""
    if hasil is None or hasil.empty:
        return uji_wilcoxon([], [])
    a = hasil[hasil["metode"] == metode_a]
    b = hasil[hasil["metode"] == metode_b]
    gabung = a.merge(
        b,
        on=["kode_responden", "id_skenario"],
        suffixes=("_a", "_b"),
    )
    return uji_wilcoxon(gabung[f"{kolom}_a"], gabung[f"{kolom}_b"])
