"""
validator.py
============
Bertanggung jawab atas:
  1. Validasi struktural output AI (penilaian valid, records_used ada di corpus)
  2. Validasi logis per query_type (comparison, trend, latest)
  3. Editorial checks: klaim kausal, indikator salah, peringatan editorial
  4. Post-processing label display

Layer ini tidak memanggil AI dan tidak membaca corpus secara langsung.
Semua informasi yang dibutuhkan sudah ada di dict hasil AI + kandidat.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from .constants import (
    ALLOWED_JUDGMENTS, DEFAULT_OUTPUT, INDICATOR_DISPLAY_MAP,
)
from .models import Candidate, QueryProfile
from .query_parser import normalize_indicator_label
from .text_utils import latest_sort_key, normalize_text, summarize_sources


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_lookup(candidates: List[Candidate]) -> Dict[str, Dict]:
    """Index kandidat by id untuk lookup O(1)."""
    return {str(c.record.get("id")): c.record for c in candidates}


# ---------------------------------------------------------------------------
# Deteksi jenis pertanyaan
# ---------------------------------------------------------------------------

def is_direct_data_question(question: str, profile: QueryProfile) -> bool:
    """Pertanyaan yang hanya meminta angka/data, bukan verifikasi klaim."""
    qn = normalize_text(question)
    direct_words = [
        "berapa", "jumlah berapa", "ada berapa", "berapa jumlah",
        "berapa persen", "berapa angka", "berapa nilai",
    ]
    claim_words = [
        "benarkah", "apakah benar", "lebih baik", "membaik", "memburuk",
        "lebih tinggi", "lebih rendah", "lebih banyak", "lebih sedikit",
        "di atas", "di bawah", "dibanding", "versus", "vs",
    ]
    if profile.query_type in {"trend", "comparison"}:
        return False
    return any(w in qn for w in direct_words) and not any(w in qn for w in claim_words)


def is_trend_data_question(question: str, profile: QueryProfile) -> bool:
    """Pertanyaan tren yang hanya meminta data perubahan, bukan verifikasi klaim."""
    qn = normalize_text(question)
    if profile.query_type != "trend":
        return False
    trend_words = [
        "bagaimana tren", "bagaimana perkembangan", "bagaimana perubahan",
        "tren kemiskinan", "tren pengangguran", "tren inflasi", "tren pertumbuhan",
        "perkembangan", "perubahan", "dari tahun ke tahun",
    ]
    claim_words = [
        "benarkah", "apakah benar", "membaik", "memburuk",
        "berhasil", "gagal", "efektif", "program", "kebijakan",
    ]
    return any(w in qn for w in trend_words) and not any(w in qn for w in claim_words)


def is_comparison_data_question(question: str, profile: QueryProfile) -> bool:
    """Pertanyaan perbandingan yang meminta data berdampingan, bukan penilaian."""
    qn = normalize_text(question)
    if profile.query_type != "comparison":
        return False
    compare_words = ["bandingkan", "perbandingan"]
    claim_words = [
        "benarkah", "apakah benar", "lebih baik", "membaik", "memburuk",
        "masih di atas", "lebih tinggi", "lebih rendah", "lebih banyak", "lebih sedikit",
    ]
    return any(w in qn for w in compare_words) and not any(w in qn for w in claim_words)


def is_causal_or_program_claim(question: str) -> bool:
    """Deteksi klaim kausal atau klaim keberhasilan program pemerintah."""
    qn = normalize_text(question)

    trigger_phrases = [
        "karena program", "disebabkan program", "berkat program", "akibat program",
        "hasil program", "program pemerintah berhasil", "kebijakan pemerintah berhasil",
        "berhasil menambah", "berhasil menurunkan", "berhasil meningkatkan",
        "berhasil mengurangi", "menciptakan", "menambah", "menurunkan",
        "meningkatkan", "mengurangi", "menyebabkan", "membuat",
        "berdampak pada", "dampak program", "klaim pemerintah", "klaim pejabat",
        "pemerintah menyebut", "pejabat mengatakan", "presiden mengatakan",
        "prabowo mengklaim", "mbg", "makan bergizi gratis", "efektif",
        "kesuksesan program", "keberhasilan program",
    ]
    actor_phrases = ["pemerintah", "pejabat", "presiden", "menteri", "prabowo", "otoritas"]
    causal_words = [
        "karena", "akibat", "berkat", "menyebabkan", "membuat",
        "bukti", "berhasil", "efektif",
    ]

    has_trigger = any(x in qn for x in trigger_phrases)
    has_actor_causal = (
        any(x in qn for x in actor_phrases)
        and any(x in qn for x in causal_words)
    )
    return has_trigger or has_actor_causal


def _fallback_editorial_warning() -> str:
    return (
        "Data yang tersedia hanya menunjukkan perubahan indikator, bukan bukti bahwa "
        "program atau kebijakan yang diklaim menjadi penyebab langsungnya. "
        "Pertanyaan lanjutan yang perlu diuji: bagaimana klaim itu dihitung; "
        "apakah ada data atribusi langsung; bagaimana kondisi indikator yang sama "
        "pada periode sebelum program berjalan; dan faktor lain apa yang mungkin "
        "ikut memengaruhi perubahan tersebut."
    )


# ---------------------------------------------------------------------------
# Validasi per query_type
# ---------------------------------------------------------------------------

def _validate_comparison(
    result: Dict[str, Any],
    used_records: List[Dict],
    profile: QueryProfile,
    flags: List[str],
) -> None:
    qn = normalize_text(profile.raw_question)

    if profile.breakdown_targets:
        needed = set(profile.breakdown_targets)
        used_breaks = {str(r.get("breakdown_value") or "").strip() for r in used_records if r.get("breakdown_value")}
        used_areas = {str(r.get("area_name") or "").strip() for r in used_records if r.get("area_name")}
        used_inds = {normalize_indicator_label(str(r.get("series_label") or "")) for r in used_records if r.get("series_label")}

        if len(used_breaks.intersection(needed)) < len(needed):
            result["penilaian"] = "Tidak dapat diverifikasi"
            flags.append("comparison_breakdown_incomplete")

        if len(used_areas) > 1:
            result["penilaian"] = "Tidak dapat diverifikasi"
            flags.append("comparison_breakdown_area_mismatch")

        if len(used_inds) > 1:
            result["penilaian"] = "Tidak dapat diverifikasi"
            flags.append("comparison_breakdown_indicator_mismatch")

        if any(k in qn for k in ["lebih banyak", "lebih sedikit", "jumlah", "orang miskin"]):
            used_ind = normalize_indicator_label(str(result.get("indicator_used") or ""))
            if used_ind != "jumlah penduduk miskin":
                result["penilaian"] = "Tidak dapat diverifikasi"
                flags.append("quantity_question_wrong_indicator")

    else:
        needed_areas = set(profile.comparison_targets or profile.area_targets)
        used_areas = {str(r.get("area_name") or "").strip() for r in used_records if r.get("area_name")}
        used_inds = {normalize_indicator_label(str(r.get("series_label") or "")) for r in used_records if r.get("series_label")}
        used_times = {latest_sort_key(r) for r in used_records}

        is_temporal = (
            not profile.comparison_targets
            and len(set(profile.area_targets or [])) <= 1
            and not profile.breakdown_targets
        )

        if not is_temporal:
            if len(used_areas.intersection(needed_areas)) < min(2, len(needed_areas) or 2):
                result["penilaian"] = "Tidak dapat diverifikasi"
                flags.append("comparison_area_incomplete")

        if len(used_inds) > 1:
            result["penilaian"] = "Tidak dapat diverifikasi"
            flags.append("comparison_indicator_mismatch")

        if not is_temporal and len(used_times) > 1:
            result["penilaian"] = "Tidak dapat diverifikasi"
            flags.append("comparison_time_mismatch")


def _validate_trend(
    result: Dict[str, Any],
    used_records: List[Dict],
    profile: QueryProfile,
    flags: List[str],
) -> None:
    time_points = {latest_sort_key(r) for r in used_records}
    year_points = {int(r.get("year")) for r in used_records if isinstance(r.get("year"), int)}
    atomic_years = {
        int(r.get("year")) for r in used_records
        if str(r.get("doc_type") or "").strip() == "atomic" and isinstance(r.get("year"), int)
    }
    requested = profile.requested_trend_years
    current = result["penilaian"]

    if current not in {"Benar", "Salah", "Sebagian benar"}:
        return  # sudah tidak perlu di-downgrade

    if requested:
        if len(atomic_years) < requested:
            result["penilaian"] = "Tidak dapat diverifikasi"
            flags.append("trend_requested_years_not_fulfilled")
    else:
        if len(time_points) < 4:
            result["penilaian"] = "Tidak dapat diverifikasi"
            flags.append("trend_too_few_points")
        elif len(year_points) < 2:
            result["penilaian"] = "Tidak dapat diverifikasi"
            flags.append("trend_year_span_too_short")


def _validate_latest(
    result: Dict[str, Any],
    used_records: List[Dict],
    candidates: List[Candidate],
    flags: List[str],
) -> None:
    if not used_records:
        return
    latest_used = max(latest_sort_key(r) for r in used_records)
    top_latest = max(latest_sort_key(c.record) for c in candidates)
    if latest_used < top_latest and result["penilaian"] in {"Benar", "Salah", "Sebagian benar"}:
        result["penilaian"] = "Tidak dapat diverifikasi"
        flags.append("latest_not_used")


# ---------------------------------------------------------------------------
# Fungsi utama
# ---------------------------------------------------------------------------

def validate_ai_output(
    ai_result: Dict[str, Any],
    candidates: List[Candidate],
    profile: QueryProfile,
    original_question: str = "",
    is_claim: bool = True,
) -> Dict[str, Any]:
    """
    Validasi dan perbaiki output mentah dari AI.

    Urutan:
    1. Merge ke DEFAULT_OUTPUT
    2. Pastikan penilaian valid
    3. Filter records_used ke yang benar-benar ada di kandidat
    4. Validasi logis per query_type
    5. Editorial checks (klaim kausal, indikator display, pertanyaan data murni)

    original_question: pertanyaan asli pengguna sebelum reformulasi.
    Digunakan untuk deteksi klaim kausal — karena reformulasi bisa
    menghilangkan keyword seperti 'prabowo', 'mengklaim', 'MBG'.
    """
    result: Dict[str, Any] = dict(DEFAULT_OUTPUT)
    result.update({k: v for k, v in ai_result.items() if v is not None})

    # Pastikan penilaian valid
    if result.get("penilaian") not in ALLOWED_JUDGMENTS:
        result["penilaian"] = "Tidak dapat diverifikasi"

    # Filter records_used
    lookup = _build_lookup(candidates)
    valid_ids: List[str] = [
        str(cid) for cid in (result.get("records_used") or [])
        if str(cid) in lookup
    ]
    result["records_used"] = valid_ids
    used_records = [lookup[cid] for cid in valid_ids]
    flags: List[str] = []

    # Tidak ada records → tidak bisa kasih penilaian tegas
    if not used_records and result["penilaian"] in {"Benar", "Salah", "Sebagian benar"}:
        result["penilaian"] = "Tidak dapat diverifikasi"
        flags.append("model_tidak_menunjuk_kandidat_yang_cukup_jelas")

    # Validasi per query_type
    if profile.query_type == "comparison":
        _validate_comparison(result, used_records, profile, flags)
    if profile.query_type == "trend":
        _validate_trend(result, used_records, profile, flags)
    if profile.needs_latest:
        _validate_latest(result, used_records, candidates, flags)

    # Sumber & unduh
    src_summary, dl_summary = summarize_sources(used_records or [c.record for c in candidates[:1]])
    result["sumber"] = src_summary
    if dl_summary:
        result["unduh_data"] = dl_summary

    # Standardisasi nama indikator
    if not result.get("indicator_used") and used_records:
        result["indicator_used"] = str(used_records[0].get("series_label") or "")

    if result.get("indicator_used"):
        norm = normalize_indicator_label(str(result["indicator_used"]))
        if norm in INDICATOR_DISPLAY_MAP:
            result["indicator_used"] = INDICATOR_DISPLAY_MAP[norm]

    # Peringatan editorial jika indikator tidak ideal
    if (
        profile.primary_indicator == "persentase penduduk miskin"
        and profile.query_type in {"claim", "comparison", "trend"}
        and not profile.quantity_hint
    ):
        used_ind = normalize_indicator_label(str(result.get("indicator_used") or ""))
        if used_ind == "jumlah penduduk miskin" and not result.get("peringatan_editorial"):
            result["peringatan_editorial"] = (
                "Pertanyaan bersifat umum; secara editorial indikator persentase "
                "biasanya lebih lazim untuk menilai kondisi kemiskinan."
            )

    # Isi alasan fallback jika flags ada dan belum ada alasan
    if not result.get("alasan") and flags:
        result["alasan"] = (
            "Data yang dipakai belum cukup konsisten atau belum cukup lengkap "
            "untuk mendukung penilaian tegas."
        )

    # Pertanyaan data murni → hapus penilaian dan alasan
    # Ditentukan oleh Intent Router (AI), bukan keyword matching
    _orig_q = original_question or profile.raw_question
    if not is_claim:
        result["penilaian"] = ""
        result["alasan"] = ""
        if not result.get("claim"):
            result["claim"] = _orig_q

    # Klaim kausal → turunkan penilaian dan isi peringatan
    # Cek kedua versi pertanyaan: asli (sebelum reformulasi) dan yang di profile
    # karena reformulasi bisa menghilangkan keyword kausal
    _is_causal = (
        is_causal_or_program_claim(original_question or profile.raw_question)
        or is_causal_or_program_claim(profile.raw_question)
    )

    if _is_causal:
        if result.get("penilaian") == "Benar":
            result["penilaian"] = "Tidak dapat diverifikasi"
        if not result.get("alasan"):
            result["alasan"] = (
                "Data yang tersedia menunjukkan perubahan indikator, tetapi belum cukup "
                "untuk membuktikan bahwa program atau kebijakan yang diklaim menjadi "
                "penyebab langsungnya."
            )
        if not result.get("peringatan_editorial"):
            result["peringatan_editorial"] = _fallback_editorial_warning()

    # ── Followup prompt: data tidak ada + bukan klaim eksplisit ──────────
    if (
        result.get("penilaian") == "Tidak dapat diverifikasi"
        and not _is_causal
        and not result.get("peringatan_editorial")
    ):
        result["followup_prompt"] = (
            "Data yang kamu cari belum tersedia dalam basis data kami. "
            "Apakah kamu sedang memverifikasi sebuah klaim? "
            "Jika iya, coba sampaikan klaim lengkapnya — misalnya siapa yang mengklaim, "
            "apa yang diklaim, dan konteksnya — supaya kami bisa membantu mencarikan data "
            "pendukung atau pendekatan verifikasi alternatif."
        )

    return result


def _normalize_starts_with(text: str, prefix: str) -> bool:
    return normalize_text(text).startswith(prefix)
