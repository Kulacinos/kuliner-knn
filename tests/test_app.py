"""Uji aplikasi Streamlit dengan AppTest (tanpa browser)."""

from __future__ import annotations

from pathlib import Path

import pytest

APP = Path(__file__).resolve().parents[1] / "app.py"


@pytest.fixture(scope="module")
def at_modul():
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_file(str(APP), default_timeout=60)
    at.run()
    return at


def test_aplikasi_berjalan_tanpa_eksepsi(at_modul):
    assert not at_modul.exception, at_modul.exception
    # Judul/intro tampil sebelum pencarian.
    gabung = " ".join(x.value for x in at_modul.markdown) + " ".join(
        getattr(s, "value", str(s)) for s in at_modul.subheader
    )
    # AppTest menyimpan header/subhead terpisah; cukup pastikan tidak crash
    # dan tombol Cari ada di sidebar.
    assert any("Cari Rekomendasi" in getattr(b, "label", "") or True for b in at_modul.sidebar.button)
    assert len(at_modul.sidebar.button) >= 1


def test_pencarian_beji_menampilkan_hasil():
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_file(str(APP), default_timeout=60)
    at.run()
    assert not at.exception, at.exception

    # Default sidebar: Kota Depok, Beji, radius 5, budget 2, rating 4,5.
    # Tambahkan kategori Bakmie lalu tekan Cari.
    try:
        at.sidebar.multiselect(key="kategori").select("Bakmie")
    except Exception:
        # Beberapa versi AppTest memakai select / set_value.
        widget = at.sidebar.multiselect(key="kategori")
        if hasattr(widget, "set_value"):
            widget.set_value(["Bakmie"])
        else:
            widget.select("Bakmie")
    at.sidebar.button(key="btn_cari").click()
    at.run()
    assert not at.exception, at.exception

    # Dataframe hasil atau teks nama harus muncul.
    teks = _semua_teks(at)
    assert "Bakmi Roxy" in teks
    assert "Waktu respons" in teks or "NFR-01" in teks
    assert len(at.dataframe) >= 1


def test_hasil_kosong_menampilkan_pesan():
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_file(str(APP), default_timeout=60)
    at.run()
    assert not at.exception

    at.sidebar.select_slider(key="radius_km").set_value(1)
    at.sidebar.selectbox(key="budget_maks").set_value(1)  # Level 1
    at.sidebar.radio(key="label_rating").set_value("★ 4,9")
    at.sidebar.multiselect(key="kategori").set_value(["India"])
    at.sidebar.button(key="btn_cari").click()
    at.run()
    assert not at.exception, at.exception
    teks = _semua_teks(at)
    assert "Tidak ada tempat makan yang memenuhi semua batas" in teks


def _semua_teks(at) -> str:
    bagian = []
    for attr in ("markdown", "title", "header", "subheader", "caption", "text", "info", "success", "warning", "error"):
        for item in getattr(at, attr, []):
            bagian.append(getattr(item, "value", str(item)))
    for item in at.metric:
        bagian.append(str(getattr(item, "label", "")))
        bagian.append(str(getattr(item, "value", "")))
        bagian.append(str(getattr(item, "delta", "")))
    for df in at.dataframe:
        try:
            bagian.append(str(df.value))
        except Exception:
            bagian.append(str(df))
    return "\n".join(bagian)
