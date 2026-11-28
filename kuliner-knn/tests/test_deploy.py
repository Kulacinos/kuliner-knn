"""Uji persiapan deployment: bangun DB otomatis dan tab unduhan."""

from __future__ import annotations

from pathlib import Path

import pytest

from kuliner.db import _basis_data_siap, hitung_isi, pastikan_basis_data
from kuliner.config import PATH_BERSIH


def test_pastikan_membangun_jika_belum_ada(tmp_path: Path):
    tujuan = tmp_path / "kuliner.db"
    assert not tujuan.exists()
    info = pastikan_basis_data(path_db=tujuan, path_csv=PATH_BERSIH)
    assert info["dibuat"] is True
    assert info["siap"] is True
    assert info["sumber"] == "sqlite"
    assert info["n_restoran"] == 10261
    assert tujuan.is_file()
    siap, n = _basis_data_siap(tujuan)
    assert siap and n == 10261


def test_pastikan_tidak_membangun_ulang_jika_sudah_valid(tmp_path: Path):
    tujuan = tmp_path / "kuliner.db"
    pertama = pastikan_basis_data(path_db=tujuan, path_csv=PATH_BERSIH)
    mtime = tujuan.stat().st_mtime
    ukuran = tujuan.stat().st_size
    kedua = pastikan_basis_data(path_db=tujuan, path_csv=PATH_BERSIH)
    assert pertama["dibuat"] is True
    assert kedua["dibuat"] is False
    assert kedua["siap"] is True
    assert kedua["n_restoran"] == 10261
    assert tujuan.stat().st_mtime == mtime
    assert tujuan.stat().st_size == ukuran


def test_pastikan_membangun_ulang_berkas_rusak(tmp_path: Path):
    tujuan = tmp_path / "kuliner.db"
    tujuan.write_bytes(b"ini bukan sqlite")
    info = pastikan_basis_data(path_db=tujuan, path_csv=PATH_BERSIH)
    assert info["dibuat"] is True
    assert info["siap"] is True
    assert info["n_restoran"] == 10261


def test_pastikan_csv_hilang(tmp_path: Path):
    info = pastikan_basis_data(
        path_db=tmp_path / "x.db",
        path_csv=tmp_path / "tidak-ada.csv",
    )
    assert info["siap"] is False
    assert info["dibuat"] is False
    assert "tidak ditemukan" in info["pesan"].lower() or "tidak ditemukan" in info["pesan"]


def test_versi_paket():
    from kuliner import __version__
    assert __version__ == "0.6.0"
