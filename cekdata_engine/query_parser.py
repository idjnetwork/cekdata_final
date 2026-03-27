"""
query_parser.py
===============
Bertanggung jawab mengubah string pertanyaan mentah menjadi QueryProfile
yang terstruktur. Layer ini tidak tahu apa-apa tentang data corpus atau AI.

Dependensi eksternal (opsional — fallback tersedia):
  - indicator_registry  (canonical indicator lookup)
  - breakdown_registry  (age/gender/area breakdown detection)

Jika modul eksternal tidak tersedia, engine tetap bisa berjalan dengan
fallback berbasis keyword sederhana.
"""
from __future__ import annotations

import logging
from typing import List, Tuple

log = logging.getLogger(__name__)

try:
    from indicator_registry import (
        canonical_indicator_candidates as _registry_candidates,
        normalize_indicator_label as _registry_normalize,
    )
except ImportError:
    log.warning(
        "indicator_registry tidak ditemukan — menggunakan fallback built-in. "
        "Deteksi indikator akan terbatas pada keyword kemiskinan dan ketenagakerjaan."
    )

    def _registry_normalize(label, normalize_fn):  # type: ignore[misc]
        """Fallback: normalisasi label menggunakan normalize_fn saja."""
        return normalize_fn(label)

    def _registry_candidates(question_norm):  # type: ignore[misc]
        """
        Fallback sederhana: deteksi indikator dari keyword di pertanyaan.
        Return: (indicator_targets, primary_indicator, quantity_hint, ambiguous)
        """
        targets: list[str] = []
        primary = ""
        quantity_hint = False
        ambiguous = False

        # Kemiskinan
        quantity_keywords = ["jumlah penduduk miskin", "jumlah orang miskin", "berapa orang miskin"]
        if any(k in question_norm for k in quantity_keywords):
            targets.append("jumlah penduduk miskin")
            primary = "jumlah penduduk miskin"
            quantity_hint = True
        elif "garis kemiskinan" in question_norm:
            targets.append("garis kemiskinan")
            primary = "garis kemiskinan"
        elif any(k in question_norm for k in [
            "kemiskinan", "miskin", "penduduk miskin", "persentase penduduk miskin",
        ]):
            targets.append("persentase penduduk miskin")
            primary = "persentase penduduk miskin"
            if "jumlah" in question_norm:
                targets.append("jumlah penduduk miskin")
                ambiguous = True

        # Ketenagakerjaan
        if any(k in question_norm for k in ["pengangguran", "tpt", "tingkat pengangguran"]):
            targets.append("tingkat pengangguran terbuka")
            if not primary:
                primary = "tingkat pengangguran terbuka"
        if any(k in question_norm for k in ["penduduk bekerja", "orang bekerja", "lapangan kerja"]):
            targets.append("jumlah penduduk bekerja")
            if not primary:
                primary = "jumlah penduduk bekerja"

        # Ekonomi
        if any(k in question_norm for k in ["pdrb", "pertumbuhan ekonomi"]):
            targets.append("pdrb")
            if not primary:
                primary = "pdrb"
        if "inflasi" in question_norm:
            targets.append("inflasi")
            if not primary:
                primary = "inflasi"

        return (targets, primary, quantity_hint, ambiguous)

try:
    from breakdown_registry import extract_breakdown_context
except ImportError:
    log.warning(
        "breakdown_registry tidak ditemukan — menggunakan fallback built-in. "
        "Deteksi breakdown usia/gender/generasi akan terbatas."
    )

    def extract_breakdown_context(question):  # type: ignore[misc]
        """
        Fallback: deteksi breakdown dari keyword.
        Menangani: gender, area (urban/rural), generasi/kelompok usia,
        dan istilah demografis umum.
        """
        from .text_utils import normalize_text
        qn = normalize_text(question)

        gender_targets: list[str] = []
        area_breakdown_targets: list[str] = []
        explicit_age_buckets: list[str] = []
        inferred_age_buckets: list[str] = []
        generation_targets: list[str] = []

        # ── Gender ──
        if "laki laki" in qn or "laki-laki" in qn:
            gender_targets.append("Laki-laki")
        if "perempuan" in qn or "wanita" in qn:
            gender_targets.append("Perempuan")

        # ── Area ──
        if "perdesaan" in qn or "pedesaan" in qn or "desa" in qn:
            area_breakdown_targets.append("Perdesaan")
        if "perkotaan" in qn or "kota" in qn:
            area_breakdown_targets.append("Perkotaan")

        # ── Generasi → bucket usia BPS (Sakernas) ──
        # Definisi berdasarkan TAHUN LAHIR, bukan usia — otomatis benar
        # setiap tahun tanpa perlu update manual.
        # Bucket BPS: 15-19, 20-24, 25-29, 30-34, 35-39, 40-44, 45-49, 50-54, 55-59, 60+
        from datetime import date
        _current_year = date.today().year

        _BPS_BUCKETS = [
            ("15-19", 15, 19), ("20-24", 20, 24), ("25-29", 25, 29),
            ("30-34", 30, 34), ("35-39", 35, 39), ("40-44", 40, 44),
            ("45-49", 45, 49), ("50-54", 50, 54), ("55-59", 55, 59),
            ("60+", 60, 999),
        ]

        def _birth_years_to_buckets(birth_start: int, birth_end: int) -> list[str]:
            """Konversi rentang tahun lahir ke bucket usia BPS berdasarkan tahun sekarang."""
            age_min = _current_year - birth_end   # usia termuda
            age_max = _current_year - birth_start  # usia tertua
            buckets = []
            for label, bkt_lo, bkt_hi in _BPS_BUCKETS:
                if age_max >= bkt_lo and age_min <= bkt_hi:
                    buckets.append(label)
            return buckets

        # Definisi generasi berdasarkan tahun lahir (konsensus umum)
        _generation_births: dict[str, tuple[int, int]] = {
            "gen z": (1996, 2012),
            "generasi z": (1996, 2012),
            "milenial": (1981, 1995),
            "millenial": (1981, 1995),
            "generasi y": (1981, 1995),
            "gen x": (1965, 1980),
            "generasi x": (1965, 1980),
            "baby boomer": (1946, 1964),
            "boomer": (1946, 1964),
        }

        _generation_map = {
            label: _birth_years_to_buckets(start, end)
            for label, (start, end) in _generation_births.items()
        }

        for label, buckets in _generation_map.items():
            if label in qn:
                generation_targets.append(label)
                for b in buckets:
                    if b not in inferred_age_buckets:
                        inferred_age_buckets.append(b)

        # ── Istilah demografis umum ──
        _demographic_terms: dict[str, list[str]] = {
            "usia produktif": ["15-19", "20-24", "25-29", "30-34", "35-39",
                               "40-44", "45-49", "50-54", "55-59"],
            "usia muda": ["15-19", "20-24"],
            "pemuda": ["15-19", "20-24"],
            "anak muda": ["15-19", "20-24"],
            "remaja": ["15-19"],
            "lansia": ["60+"],
            "penduduk tua": ["60+"],
            "lanjut usia": ["60+"],
            "paruh baya": ["40-44", "45-49", "50-54"],
        }

        for term, buckets in _demographic_terms.items():
            if term in qn:
                for b in buckets:
                    if b not in inferred_age_buckets:
                        inferred_age_buckets.append(b)

        # ── Bucket usia eksplisit (deteksi "usia 20-24", "umur 15 19", dll) ──
        # normalize_text replaces dash with space, so match both forms
        import re
        age_patterns = re.findall(
            r"(?:usia|umur|kelompok)\s*(\d{2})\s*[\s\-–]\s*(\d{2}\+?)", qn
        )
        for start, end in age_patterns:
            bucket = f"{start}-{end}"
            if bucket not in explicit_age_buckets:
                explicit_age_buckets.append(bucket)

        return {
            "inferred_age_buckets": inferred_age_buckets,
            "explicit_age_buckets": explicit_age_buckets,
            "gender_targets": gender_targets,
            "generation_targets": generation_targets,
            "area_breakdown_targets": area_breakdown_targets,
        }

from .constants import AREA_ALIASES, QUESTION_CUES
from .models import QueryProfile
from .text_utils import (
    normalize_text,
    extract_years,
    extract_periods,
    extract_requested_trend_years,
    tokenize,
)


# ---------------------------------------------------------------------------
# Normalisasi label indikator (delegasi ke registry)
# ---------------------------------------------------------------------------

def normalize_indicator_label(label: str) -> str:
    return _registry_normalize(label, normalize_text)


def canonical_indicator_candidates(question_norm: str) -> Tuple[List[str], str, bool, bool]:
    return _registry_candidates(question_norm)


# ---------------------------------------------------------------------------
# Ekstraksi wilayah
# ---------------------------------------------------------------------------

def extract_area_targets(
    question_norm: str,
) -> Tuple[List[str], List[str], List[str]]:
    """
    Kembalikan (areas, comparison_targets, breakdown_targets) dari pertanyaan.

    - areas: semua wilayah yang disebut
    - comparison_targets: dua sisi perbandingan (jika ada)
    - breakdown_targets: wilayah yang berupa breakdown (Perdesaan/Perkotaan)
    """
    areas: List[str] = []
    comparisons: List[str] = []
    breakdowns: List[str] = []

    for alias, canonical in AREA_ALIASES.items():
        if alias in question_norm:
            if canonical in {"Perdesaan", "Perkotaan"}:
                if canonical not in breakdowns:
                    breakdowns.append(canonical)
            else:
                if canonical not in areas:
                    areas.append(canonical)

    # Pastikan Indonesia selalu masuk jika disebut
    if any(k in question_norm for k in ["rata rata nasional", "nasional", "indonesia"]):
        if "Indonesia" not in areas:
            areas.append("Indonesia")

    # Tentukan comparison_targets
    if len(areas) >= 2:
        comparisons = areas[:2]
    elif len(areas) == 1 and any(
        k in question_norm for k in ["rata rata nasional", "nasional", "dibanding nasional", "di atas nasional"]
    ):
        comparisons = [areas[0], "Indonesia"] if areas[0] != "Indonesia" else ["Indonesia"]

    return areas, comparisons, breakdowns


# ---------------------------------------------------------------------------
# Deteksi query terkait program kerja (klaim kausal)
# ---------------------------------------------------------------------------

def _has_program_job_cues(question_norm: str) -> bool:
    program_keywords = {"makan bergizi gratis", "mbg", "program", "prabowo"}
    job_keywords = {
        "lapangan kerja", "orang bekerja", "penduduk bekerja",
        "pengangguran", "pekerjaan", "tenaga kerja",
    }
    return (
        any(k in question_norm for k in program_keywords)
        and any(k in question_norm for k in job_keywords)
    )


# ---------------------------------------------------------------------------
# Fungsi utama
# ---------------------------------------------------------------------------

def make_query_profile(question: str) -> QueryProfile:
    """
    Parse pertanyaan mentah menjadi QueryProfile terstruktur.

    Ini adalah satu-satunya fungsi yang perlu dipanggil dari luar modul ini.
    """
    qn = normalize_text(question)

    # --- Indikator ---
    indicator_targets, primary_indicator, quantity_hint, ambiguous = canonical_indicator_candidates(qn)
    area_targets, comparison_targets, breakdown_targets = extract_area_targets(qn)

    # --- Temporal ---
    periods = extract_periods(question)
    explicit_years = extract_years(question)
    requested_trend_years = extract_requested_trend_years(question)

    # --- Breakdown kontekstual (usia, gender, generasi) ---
    breakdown_ctx = extract_breakdown_context(question)
    for item in (
        list(breakdown_ctx.get("explicit_age_buckets") or [])
        + list(breakdown_ctx.get("inferred_age_buckets") or [])
        + list(breakdown_ctx.get("gender_targets") or [])
        + [
            x for x in (breakdown_ctx.get("area_breakdown_targets") or [])
            if x and x != "Indonesia"
        ]
    ):
        if item and item not in breakdown_targets:
            breakdown_targets.append(item)

    # --- Cue program/pekerjaan → inject indikator ketenagakerjaan ---
    if _has_program_job_cues(qn) and not indicator_targets:
        for hint in ["jumlah penduduk bekerja", "jumlah pengangguran", "tingkat pengangguran terbuka"]:
            indicator_targets.append(hint)
        if not primary_indicator:
            primary_indicator = "jumlah penduduk bekerja"
        if "Indonesia" not in area_targets:
            area_targets.append("Indonesia")

    # --- Jenis query ---
    query_type = "claim"
    if requested_trend_years or any(k in qn for k in QUESTION_CUES["trend"]):
        query_type = "trend"
    elif "bandingkan" in qn or "perbandingan" in qn or any(k in qn for k in QUESTION_CUES["comparison"]):
        query_type = "comparison"

    needs_latest = any(k in qn for k in QUESTION_CUES["latest"])
    needs_recent_range = (
        bool(requested_trend_years)
        or any(k in qn for k in QUESTION_CUES["latest_trend"])
        or query_type == "trend"
    )
    comparator_words = [k for k in QUESTION_CUES["comparison"] if k in qn]

    # --- Keyword targets untuk overlap scoring ---
    keyword_targets: List[str] = list(dict.fromkeys(
        indicator_targets + area_targets + breakdown_targets + periods
        + (["terbaru"] if needs_latest else [])
        + (["tren"] if query_type == "trend" else [])
    ))

    # --- Generated queries untuk multi-query scoring ---
    generated_queries: List[str] = [question.strip()]
    q2_parts = [qn]
    if primary_indicator:
        q2_parts.append(primary_indicator)
    if query_type == "comparison":
        q2_parts.extend(comparison_targets or area_targets)
    if breakdown_targets:
        q2_parts.extend(breakdown_targets)
    if needs_latest:
        q2_parts.append("periode terbaru")
    if needs_recent_range:
        q2_parts.append("data terbaru")
    generated_queries.append(" ".join(dict.fromkeys(p for p in q2_parts if p)))

    if query_type == "trend":
        generated_queries.append(" ".join(dict.fromkeys([
            qn,
            primary_indicator or "persentase penduduk miskin",
            *(area_targets or ["Indonesia"]),
            "tren terbaru",
            "rentang tahun terbaru",
        ])))

    generation_targets = list(breakdown_ctx.get("generation_targets") or [])
    gender_targets = list(breakdown_ctx.get("gender_targets") or [])
    area_breakdown_targets = [
        x for x in (breakdown_ctx.get("area_breakdown_targets") or [])
        if x and x != "Indonesia"
    ]
    explicit_age_buckets = list(breakdown_ctx.get("explicit_age_buckets") or [])
    inferred_age_buckets = list(breakdown_ctx.get("inferred_age_buckets") or [])

    return QueryProfile(
        raw_question=question,
        normalized_question=qn,
        query_type=query_type,
        needs_latest=needs_latest,
        needs_recent_range=needs_recent_range,
        requested_trend_years=requested_trend_years,
        explicit_years=explicit_years,
        periods=periods,
        indicator_targets=indicator_targets,
        primary_indicator=primary_indicator,
        area_targets=area_targets,
        comparison_targets=comparison_targets,
        breakdown_targets=breakdown_targets,
        comparator_words=comparator_words,
        quantity_hint=quantity_hint,
        ambiguous_indicator=ambiguous,
        generated_queries=list(dict.fromkeys(q for q in generated_queries if q)),
        keyword_targets=keyword_targets,
        metadata_filters={
            "query_type": query_type,
            "needs_latest": needs_latest,
            "needs_recent_range": needs_recent_range,
            "requested_trend_years": requested_trend_years,
            "primary_indicator": primary_indicator,
            "area_targets": area_targets,
            "comparison_targets": comparison_targets,
            "breakdown_targets": breakdown_targets,
            "periods": periods,
            "explicit_years": explicit_years,
            "generation_targets": generation_targets,
            "gender_targets": gender_targets,
            "area_breakdown_targets": area_breakdown_targets,
            "explicit_age_buckets": explicit_age_buckets,
            "inferred_age_buckets": inferred_age_buckets,
        },
    )


# ---------------------------------------------------------------------------
# Deteksi pertanyaan vague
# ---------------------------------------------------------------------------

def is_vague_question(question: str, profile: QueryProfile) -> bool:
    """
    Return True jika pertanyaan terlalu pendek/umum untuk dijawab dengan data.

    Query yang sudah teridentifikasi sebagai trend atau comparison tidak
    pernah dianggap vague — parser sudah menemukan cukup sinyal untuk meneruskan.
    """
    # Jika parser sudah bisa tentukan jenis query non-trivial, tidak vague
    if profile.query_type in {"trend", "comparison"}:
        return False

    qn = normalize_text(question)
    toks = [t for t in tokenize(qn) if t and len(t) > 1]

    if len(toks) <= 2:
        return True

    has_specific_signal = bool(
        profile.primary_indicator
        or profile.area_targets
        or profile.breakdown_targets
        or profile.comparison_targets
        or profile.explicit_years
        or profile.periods
        or profile.comparator_words
    )

    has_question_word = any(w in qn for w in [
        "berapa", "benarkah", "apakah", "bagaimana", "bandingkan", "tren",
        "jumlah", "persentase", "garis kemiskinan", "penduduk", "kemiskinan",
        "pengangguran", "inflasi", "pdrb", "tahun", "september", "maret",
    ])

    if len(toks) <= 4 and not has_specific_signal and not has_question_word:
        return True

    return False
