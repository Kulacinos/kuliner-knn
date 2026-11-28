"""Uji black-box otomatis (Tabel 3.19 + pelengkap)."""

from __future__ import annotations

import pytest

from kuliner.black_box import KASUS, STATUS_LULUS


KASUS_OTOMATIS = [k for k in KASUS if k.get("otomatis")]


@pytest.mark.parametrize("kasus", KASUS_OTOMATIS, ids=lambda k: k["id"])
def test_kasus_otomatis_lulus(kasus):
    pelaksana = kasus["pelaksana"]
    hasil = pelaksana()
    assert hasil["status"] == STATUS_LULUS, f"{kasus['id']}: {hasil['aktual']}"


def test_katalog_memuat_tabel_319():
    ids = [k["id"] for k in KASUS]
    for i in range(1, 15):
        assert f"BB-{i:02d}" in ids
    # GPS dan admin tidak otomatis.
    peta = {k["id"]: k for k in KASUS}
    assert peta["BB-01"]["otomatis"] is False
    for i in range(11, 15):
        assert peta[f"BB-{i:02d}"]["otomatis"] is False


def test_kasus_non_otomatis_punya_aktual():
    from kuliner.black_box import KASUS
    non = [k for k in KASUS if not k.get("otomatis")]
    assert len(non) >= 5  # BB-01, BB-11..BB-14
    for k in non:
        assert k.get("aktual_tetap"), k["id"]
        assert k.get("status_tetap"), k["id"]
        assert k.get("fitur") and k.get("expected")
