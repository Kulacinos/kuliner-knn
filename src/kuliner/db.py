"""Model SQLAlchemy dan fungsi untuk membangun basis data merchant.

Skema
-----
restoran
    Satu baris per merchant. Kolom ``kategori`` menyimpan daftar nama
    yang dipisah ``|`` (sama seperti CSV) agar mudah dibaca ulang.
    Indeks gabungan: (kota, kecamatan) untuk pilihan lokasi manual, dan
    (latitude, longitude) untuk kueri spasial kasar.

kategori
    Daftar unik nama kategori kuliner (21 nama pada data TK1).

restoran_kategori
    Tabel penghubung many-to-many. Dipakai nanti untuk filter kategori
    dan perhitungan Jaccard tanpa harus memecah string berulang kali.

Muat data bersifat idempotent: setiap pemanggilan menghapus isi lama
lalu mengisi ulang dari DataFrame/CSV, sehingga hasilnya selalu sama.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import pandas as pd
from sqlalchemy import (
    Boolean,
    Column,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Table,
    Text,
    create_engine,
    event,
    insert,
    select,
)
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship, sessionmaker

from kuliner.config import PATH_BERSIH, PEMISAH_KATEGORI, url_db
from kuliner.preprocessing import pecah_kategori


class Base(DeclarativeBase):
    """Kelas dasar model."""


restoran_kategori = Table(
    "restoran_kategori",
    Base.metadata,
    Column(
        "restoran_id",
        String(64),
        ForeignKey("restoran.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "kategori_id",
        Integer,
        ForeignKey("kategori.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Index("ix_restoran_kategori_kategori_id", "kategori_id"),
)


class Restoran(Base):
    """Merchant kuliner hasil pembersihan."""

    __tablename__ = "restoran"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    nama: Mapped[str] = mapped_column(String(255), nullable=False)
    brand: Mapped[str] = mapped_column(String(255), nullable=False)
    alamat_area: Mapped[str] = mapped_column(Text, nullable=False)
    region: Mapped[str] = mapped_column(String(32), nullable=False)
    kota: Mapped[str] = mapped_column(String(64), nullable=False)
    kecamatan: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    price_level: Mapped[int] = mapped_column(Integer, nullable=False)
    # None = belum dinilai (asalnya rating 0 pada data mentah).
    rating: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    sudah_dinilai: Mapped[bool] = mapped_column(Boolean, nullable=False)
    n_kategori: Mapped[int] = mapped_column(Integer, nullable=False)
    price_norm: Mapped[float] = mapped_column(Float, nullable=False)
    rating_gap: Mapped[float] = mapped_column(Float, nullable=False)
    # Salinan teks dipisah "|", memudahkan ekspor dan pemeriksaan cepat.
    kategori: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    daftar_kategori: Mapped[list["Kategori"]] = relationship(
        secondary=restoran_kategori,
        back_populates="daftar_restoran",
    )

    __table_args__ = (
        Index("ix_restoran_kota_kecamatan", "kota", "kecamatan"),
        Index("ix_restoran_koordinat", "latitude", "longitude"),
    )


class Kategori(Base):
    """Nama kategori kuliner (misalnya Bakmie, Aneka nasi)."""

    __tablename__ = "kategori"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nama: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)

    daftar_restoran: Mapped[list[Restoran]] = relationship(
        secondary=restoran_kategori,
        back_populates="daftar_kategori",
    )


def buat_mesin(url: str | None = None, path_db: Path | None = None) -> Engine:
    """Buat engine SQLAlchemy dan aktifkan foreign key pada SQLite."""
    if url is None:
        url = url_db(path_db)
    mesin = create_engine(url, future=True)

    if url.startswith("sqlite"):

        @event.listens_for(mesin, "connect")
        def _aktifkan_fk(dbapi_conn, _rekaman):  # noqa: ANN001
            kursor = dbapi_conn.cursor()
            kursor.execute("PRAGMA foreign_keys=ON")
            kursor.close()

    return mesin


def siapkan_skema(mesin: Engine, ulang: bool = True) -> None:
    """Buat tabel. Jika ``ulang``, hapus skema lama terlebih dahulu."""
    if ulang:
        Base.metadata.drop_all(mesin)
    Base.metadata.create_all(mesin)


def _nilai_kosong(nilai):
    """Ubah NaN/NaT pandas menjadi None untuk SQL."""
    if nilai is None:
        return None
    try:
        if pd.isna(nilai):
            return None
    except (TypeError, ValueError):
        pass
    return nilai


def muat_dari_dataframe(df: pd.DataFrame, mesin: Engine, ulang: bool = True) -> dict[str, int]:
    """Isi basis data dari DataFrame bersih. Mengembalikan jumlah baris."""
    siapkan_skema(mesin, ulang=ulang)

    nama_kategori: set[str] = set()
    for teks in df["kategori"].tolist():
        nama_kategori.update(pecah_kategori(teks))

    with Session(mesin) as sesi:
        peta: dict[str, Kategori] = {
            nama: Kategori(nama=nama) for nama in sorted(nama_kategori)
        }
        sesi.add_all(peta.values())
        sesi.flush()

        kolom = [
            "id",
            "nama",
            "brand",
            "alamat_area",
            "region",
            "kota",
            "kecamatan",
            "latitude",
            "longitude",
            "price_level",
            "rating",
            "sudah_dinilai",
            "n_kategori",
            "price_norm",
            "rating_gap",
            "kategori",
        ]
        baris_restoran: list[dict] = []
        penghubung: list[dict] = []
        for rekaman in df.itertuples(index=False):
            data = {k: _nilai_kosong(getattr(rekaman, k)) for k in kolom}
            data["sudah_dinilai"] = bool(rekaman.sudah_dinilai)
            data["n_kategori"] = int(rekaman.n_kategori)
            data["price_level"] = int(rekaman.price_level)
            baris_restoran.append(data)
            for nama in pecah_kategori(rekaman.kategori):
                penghubung.append(
                    {
                        "restoran_id": rekaman.id,
                        "kategori_id": peta[nama].id,
                    }
                )

        sesi.bulk_insert_mappings(Restoran, baris_restoran)
        if penghubung:
            sesi.execute(insert(restoran_kategori), penghubung)
        sesi.commit()

    return hitung_isi(mesin)


def hitung_isi(mesin: Engine) -> dict[str, int]:
    """Hitung isi ketiga tabel."""
    from sqlalchemy import func

    with Session(mesin) as sesi:
        n_restoran = sesi.scalar(select(func.count()).select_from(Restoran)) or 0
        n_kategori = sesi.scalar(select(func.count()).select_from(Kategori)) or 0
        n_penghubung = sesi.scalar(select(func.count()).select_from(restoran_kategori)) or 0
        n_dinilai = sesi.scalar(
            select(func.count()).select_from(Restoran).where(Restoran.sudah_dinilai.is_(True))
        ) or 0
        n_kota = sesi.scalar(select(func.count(func.distinct(Restoran.kota)))) or 0
    return {
        "restoran": int(n_restoran),
        "kategori": int(n_kategori),
        "restoran_kategori": int(n_penghubung),
        "sudah_dinilai": int(n_dinilai),
        "kota": int(n_kota),
    }


def muat_dari_csv(
    path_csv: Path | None = None,
    mesin: Engine | None = None,
    path_db: Path | None = None,
    ulang: bool = True,
) -> dict[str, int]:
    """Baca CSV bersih lalu muat ke SQLite."""
    path = Path(path_csv) if path_csv is not None else PATH_BERSIH
    if mesin is None:
        mesin = buat_mesin(path_db=path_db)
        # Pastikan folder tujuan ada.
        if path_db is not None:
            Path(path_db).parent.mkdir(parents=True, exist_ok=True)
        else:
            from kuliner.config import PATH_DB

            PATH_DB.parent.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(path)
    return muat_dari_dataframe(df, mesin, ulang=ulang)


def buat_sesi(mesin: Engine) -> sessionmaker[Session]:
    """Pabrik sesi untuk pemakaian di bagian berikutnya."""
    return sessionmaker(bind=mesin, future=True, expire_on_commit=False)
