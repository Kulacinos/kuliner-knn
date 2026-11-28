"""Uji model SQLAlchemy dan loader basis data (idempotent)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest
from sqlalchemy import inspect, select, text

from kuliner.config import PATH_BERSIH
from kuliner.db import (
    Kategori,
    Restoran,
    buat_mesin,
    hitung_isi,
    muat_dari_csv,
    restoran_kategori,
)
from kuliner.preprocessing import pecah_kategori


@pytest.fixture()
def mesin(tmp_path: Path):
    path_db = tmp_path / "kuliner.db"
    return buat_mesin(path_db=path_db)


@pytest.fixture()
def isi(mesin):
    return muat_dari_csv(path_csv=PATH_BERSIH, mesin=mesin, ulang=True)


def test_jumlah_baris_setelah_muat(isi):
    assert isi["restoran"] == 10261
    assert isi["sudah_dinilai"] == 9740
    assert isi["restoran"] - isi["sudah_dinilai"] == 521
    assert isi["kota"] == 18
    assert isi["kategori"] == 21


def test_jumlah_relasi_kategori(isi, mesin):
    acuan = pd.read_csv(PATH_BERSIH)
    n_relasi = int(acuan["n_kategori"].sum())
    assert isi["restoran_kategori"] == n_relasi
    # Cek satu merchant: jumlah relasi = n_kategori.
    with mesin.connect() as conn:
        baris = conn.execute(
            select(Restoran.id, Restoran.n_kategori, Restoran.kategori).limit(20)
        ).all()
    assert baris
    from sqlalchemy.orm import Session

    with Session(mesin) as sesi:
        for id_, n, teks in baris:
            objek = sesi.get(Restoran, id_)
            assert objek is not None
            assert len(objek.daftar_kategori) == n
            assert {k.nama for k in objek.daftar_kategori} == set(pecah_kategori(teks))


def test_rating_kosong_untuk_yang_belum_dinilai(mesin, isi):
    from sqlalchemy.orm import Session

    with Session(mesin) as sesi:
        belum = sesi.scalars(select(Restoran).where(Restoran.sudah_dinilai.is_(False))).all()
        assert len(belum) == 521
        assert all(r.rating is None for r in belum)
        assert all(r.rating_gap == pytest.approx(1.0) for r in belum)


def test_indeks_kota_kecamatan_dan_koordinat(mesin, isi):
    info = inspect(mesin)
    indeks = info.get_indexes("restoran")
    pasangan = {tuple(i["column_names"]) for i in indeks}
    assert ("kota", "kecamatan") in pasangan
    assert ("latitude", "longitude") in pasangan
    nama = {i["name"] for i in indeks}
    assert "ix_restoran_kota_kecamatan" in nama
    assert "ix_restoran_koordinat" in nama


def test_idempotent_tidak_menambah_baris(mesin):
    pertama = muat_dari_csv(path_csv=PATH_BERSIH, mesin=mesin, ulang=True)
    kedua = muat_dari_csv(path_csv=PATH_BERSIH, mesin=mesin, ulang=True)
    assert pertama == kedua
    assert hitung_isi(mesin) == kedua
    # Tidak ada id ganda.
    from sqlalchemy import func
    from sqlalchemy.orm import Session

    with Session(mesin) as sesi:
        n_id = sesi.scalar(select(func.count(func.distinct(Restoran.id))))
        n_semua = sesi.scalar(select(func.count()).select_from(Restoran))
    assert n_id == n_semua == 10261


def test_foreign_key_sqlite_aktif(mesin, isi):
    # Relasi merujuk ke restoran dan kategori yang ada.
    with mesin.connect() as conn:
        yatim = conn.execute(
            text(
                "SELECT COUNT(*) FROM restoran_kategori rk "
                "LEFT JOIN restoran r ON r.id = rk.restoran_id "
                "WHERE r.id IS NULL"
            )
        ).scalar_one()
        yatim_kat = conn.execute(
            text(
                "SELECT COUNT(*) FROM restoran_kategori rk "
                "LEFT JOIN kategori k ON k.id = rk.kategori_id "
                "WHERE k.id IS NULL"
            )
        ).scalar_one()
    assert yatim == 0
    assert yatim_kat == 0


def test_kecamatan_boleh_kosong(mesin, isi):
    from sqlalchemy.orm import Session

    acuan = pd.read_csv(PATH_BERSIH)
    n_kosong = int(acuan["kecamatan"].isna().sum())
    with Session(mesin) as sesi:
        n_db = len(sesi.scalars(select(Restoran).where(Restoran.kecamatan.is_(None))).all())
    assert n_db == n_kosong
    assert n_kosong == 10
