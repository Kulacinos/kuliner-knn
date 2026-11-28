"""Halaman Streamlit 'Evaluasi Pengguna': penilaian relevansi dan kuesioner SUS."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from kuliner.evaluasi import METODE
from kuliner.penilaian import (
    LABEL_RELEVANSI,
    METODE_BANDING_DEFAULT,
    PATH_HASIL_PENILAIAN,
    PATH_HASIL_SUS,
    SUMBER_CONTOH,
    kumpulan_item_penilaian,
    label_skenario,
    muat_penilaian,
    muat_skenario,
    muat_sus,
    seed_acak,
    simpan_penilaian,
    simpan_sus,
    validasi_kode_responden,
    waktu_sekarang,
)
from kuliner.sus import (
    AMBANG_ACCEPTABLE,
    LABEL_LIKERT,
    PERNYATAAN_SUS,
    ringkasan_skor,
    skor_sus,
)
from kuliner.ui_helpers import format_angka, teks_harga, teks_rating



def _baca_berkas_unduh(path) -> bytes | None:
    path = Path(path)
    if not path.is_file() or path.stat().st_size == 0:
        return None
    return path.read_bytes()


def _panel_unduh_jawaban() -> None:
    """Tombol unduh CSV agar jawaban sesi Cloud tidak hilang."""
    st.markdown("##### Unduh jawaban tersimpan")
    rel = _baca_berkas_unduh(PATH_HASIL_PENILAIAN)
    sus = _baca_berkas_unduh(PATH_HASIL_SUS)
    kiri, kanan = st.columns(2)
    with kiri:
        if rel:
            n = len(muat_penilaian(PATH_HASIL_PENILAIAN))
            st.download_button(
                label=f"Unduh penilaian relevansi ({n} baris)",
                data=rel,
                file_name="penilaian_relevansi.csv",
                mime="text/csv",
                key="unduh_penilaian",
            )
        else:
            st.caption("Belum ada penilaian relevansi pada sesi ini.")
    with kanan:
        if sus:
            n = len(muat_sus(PATH_HASIL_SUS))
            st.download_button(
                label=f"Unduh jawaban SUS ({n} responden)",
                data=sus,
                file_name="jawaban_sus.csv",
                mime="text/csv",
                key="unduh_sus",
            )
        else:
            st.caption("Belum ada jawaban SUS pada sesi ini.")


def tab_evaluasi_pengguna(data: pd.DataFrame) -> None:
    st.subheader("Evaluasi Pengguna")
    st.caption(
        "Halaman ini dipakai responden berusia 18–25 tahun untuk menilai "
        "relevansi hasil rekomendasi (skala 0/1/2) dan mengisi kuesioner "
        "kebergunaan SUS. Jawaban disimpan sebagai CSV (dan SQLite) pada "
        "mesin yang menjalankan aplikasi."
    )
    st.info(
        "Sebelum mengisi, selesaikan dulu tugas: mencari rekomendasi di tab "
        "**Rekomendasi** (atur lokasi dan preferensi, lihat daftar, peta, dan "
        "rincian skor), lalu coba tab **Cari Nama**. Setelah itu isi penilaian "
        "relevansi dan kuesioner SUS di bawah."
    )
    st.warning(
        "Jika aplikasi berjalan di Streamlit Community Cloud, berkas di server "
        "bersifat **sementara**: reboot atau deploy ulang dapat menghapus "
        "jawaban. Unduh salinan CSV setelah setiap sesi (tombol di bawah) "
        "dan simpan di komputer petugas."
    )
    _panel_unduh_jawaban()
    sub_rel, sub_sus = st.tabs(["Penilaian relevansi", "Kuesioner SUS"])
    with sub_rel:
        _form_relevansi(data)
    with sub_sus:
        _form_sus()


def _form_relevansi(data: pd.DataFrame) -> None:
    st.markdown(
        """
Nilai setiap tempat makan pada daftar di bawah tanpa melihat metode yang
menghasilkannya. Gabungan *Top-10* dari metode yang dibandingkan (bawaan:
jarak saja vs skor penuh) ditampilkan dalam urutan acak.

**Skala:** 0 = tidak relevan · 1 = cukup relevan · 2 = sangat relevan.
        """
    )
    try:
        skenario = muat_skenario()
    except FileNotFoundError:
        st.error("Berkas skenario tidak ditemukan (`data/evaluasi/skenario.csv`).")
        return

    kode = st.text_input(
        "Kode responden",
        value="",
        key="eval_kode",
        help="Misalnya R01. Jangan memakai kode yang diawali CONTOH (itu data tiruan).",
        max_chars=40,
    )
    label_map = {label_skenario(r): r.id for r in skenario.itertuples()}
    pilih = st.selectbox(
        "Skenario kueri",
        options=list(label_map.keys()),
        key="eval_skenario",
    )
    id_skenario = label_map[pilih]
    baris = skenario[skenario["id"] == id_skenario].iloc[0]

    opsi_metode = list(METODE.keys())
    default_m = [m for m in METODE_BANDING_DEFAULT if m in opsi_metode]
    metode = st.multiselect(
        "Metode yang dibandingkan (label metode disembunyikan pada daftar)",
        options=opsi_metode,
        default=default_m,
        format_func=lambda m: f"{m} — {METODE[m]['label']}",
        key="eval_metode",
    )

    st.caption(
        f"Lokasi acuan: {baris.kota} – {baris.kecamatan} "
        f"({float(baris.lat):.5f}, {float(baris.lon):.5f}). "
        f"Radius {int(baris.radius_km)} km, budget level {int(baris.budget_maks)}, "
        f"rating minimum {baris.rating_min}, kategori: "
        f"{(str(baris.kategori) or '').replace('|', ', ') or '(tidak dipilih)'}."
    )

    if st.button("Tampilkan daftar penilaian", type="primary", key="eval_tampilkan"):
        if not metode:
            st.warning("Pilih paling sedikit satu metode.")
        else:
            try:
                validasi_kode_responden(kode)
            except ValueError as exc:
                st.error(str(exc))
            else:
                st.session_state["eval_siap"] = {
                    "kode": kode.strip(),
                    "id_skenario": id_skenario,
                    "metode": list(metode),
                }

    siap = st.session_state.get("eval_siap")
    if not siap or siap.get("id_skenario") != id_skenario or siap.get("kode") != (kode or "").strip():
        st.caption("Isi kode responden, pilih skenario, lalu tekan tombol di atas.")
        return

    daftar = kumpulan_item_penilaian(
        data,
        baris,
        metode=siap["metode"],
        k=10,
        seed=seed_acak(siap["kode"], siap["id_skenario"]),
    )
    if daftar.empty:
        st.warning("Tidak ada hasil rekomendasi untuk skenario dan metode ini.")
        return

    st.write(f"**{len(daftar)} tempat makan** untuk dinilai (urutan acak).")
    nilai_baru: dict[str, int] = {}
    for rec in daftar.itertuples():
        with st.container(border=True):
            kiri, kanan = st.columns((2.2, 1.0))
            with kiri:
                st.markdown(f"**{int(rec.peringkat_tampil)}. {rec.nama}**")
                sudah = bool(getattr(rec, "sudah_dinilai", True))
                st.caption(
                    f"{rec.kota} – {rec.kecamatan} · "
                    f"{str(rec.kategori or '').replace('|', ', ') or '–'} · "
                    f"{teks_harga(int(rec.price_level))} · "
                    f"rating {teks_rating(rec.rating, sudah)} · "
                    f"{format_angka(float(rec.jarak_km), 2)} km"
                )
            with kanan:
                nilai_baru[str(rec.id_merchant)] = st.radio(
                    "Relevansi",
                    options=[0, 1, 2],
                    index=None,
                    format_func=lambda v: f"{v} — {LABEL_RELEVANSI[v]}",
                    key=f"eval_rel_{siap['kode']}_{siap['id_skenario']}_{rec.id_merchant}",
                    horizontal=True,
                    label_visibility="collapsed",
                )

    if st.button("Simpan penilaian", type="primary", key="eval_simpan"):
        kurang = [m for m, v in nilai_baru.items() if v is None]
        if kurang:
            st.error(f"Masih ada {len(kurang)} item yang belum dinilai. Lengkapi semua item.")
            return
        waktu = waktu_sekarang()
        baris_simpan = []
        for rec in daftar.itertuples():
            baris_simpan.append({
                "waktu_iso": waktu,
                "kode_responden": siap["kode"],
                "id_skenario": siap["id_skenario"],
                "id_merchant": str(rec.id_merchant),
                "nama": rec.nama,
                "peringkat_tampil": int(rec.peringkat_tampil),
                "nilai": int(nilai_baru[str(rec.id_merchant)]),
                "metode_sumber": rec.metode_sumber,
                "peringkat_per_metode": rec.peringkat_per_metode,
                "sumber": "responden",
            })
        simpan_penilaian(pd.DataFrame(baris_simpan))
        st.success(
            f"Penilaian {siap['kode']} untuk {siap['id_skenario']} tersimpan "
            f"({len(baris_simpan)} item). Pilih skenario lain atau isi kuesioner SUS."
        )
        st.session_state.pop("eval_siap", None)


def _form_sus() -> None:
    st.markdown(
        f"""
Kuesioner **System Usability Scale (SUS)** terdiri atas 10 pernyataan standar
(Brooke, 1996) dalam terjemahan Indonesia. Pilih 1 (sangat tidak setuju)
sampai 5 (sangat setuju) untuk setiap butir. Skor dihitung dengan Persamaan
(2.7): butir ganjil (sᵢ − 1), butir genap (5 − sᵢ), jumlah dikali 2,5
(rentang 0–100). Target NFR-02 adalah rata-rata kelompok ≥ {AMBANG_ACCEPTABLE:.0f}.
        """
    )
    kode = st.text_input(
        "Kode responden",
        value="",
        key="sus_kode",
        max_chars=40,
        help="Gunakan kode yang sama dengan penilaian relevansi, misalnya R01.",
    )
    jawaban: list[int | None] = []
    for i, teks in enumerate(PERNYATAAN_SUS, start=1):
        st.markdown(f"**{i}.** {teks}")
        jawaban.append(
            st.radio(
                f"Butir {i}",
                options=[1, 2, 3, 4, 5],
                index=None,
                format_func=lambda v: f"{v} — {LABEL_LIKERT[v]}",
                key=f"sus_s{i}",
                horizontal=True,
                label_visibility="collapsed",
            )
        )

    if st.button("Simpan jawaban SUS", type="primary", key="sus_simpan"):
        try:
            kode_ok = validasi_kode_responden(kode)
        except ValueError as exc:
            st.error(str(exc))
            return
        if any(v is None for v in jawaban):
            n = sum(1 for v in jawaban if v is None)
            st.error(f"Masih ada {n} butir yang belum dijawab.")
            return
        skor = skor_sus(jawaban)  # type: ignore[arg-type]
        info = ringkasan_skor(skor=skor)
        simpan_sus(pd.DataFrame([{
            "waktu_iso": waktu_sekarang(),
            "kode_responden": kode_ok,
            "s1": jawaban[0], "s2": jawaban[1], "s3": jawaban[2], "s4": jawaban[3],
            "s5": jawaban[4], "s6": jawaban[5], "s7": jawaban[6], "s8": jawaban[7],
            "s9": jawaban[8], "s10": jawaban[9],
            "skor": skor,
            "sumber": "responden",
        }]))
        st.success(
            f"Jawaban SUS {kode_ok} tersimpan. Skor Anda: **{skor:.1f}** "
            f"(huruf {info['huruf']}, {info['adjektiva_id']}, "
            f"{info['keberterimaan_id']})."
        )
        st.caption(
            "Interpretasi kelompok (rata-rata ≥ 70 = dapat diterima) baru dihitung "
            "setelah seluruh responden selesai, lewat `python scripts/hitung_sus.py`."
        )
