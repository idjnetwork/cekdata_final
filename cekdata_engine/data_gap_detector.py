"""
data_gap_detector.py
====================
Mendeteksi apakah kandidat dari retrieval cukup relevan untuk menjawab
pertanyaan, atau ada "gap" yang membutuhkan reasoning lebih lanjut.

Dipanggil di dua titik dalam engine:
  1. Setelah retrieval pertama — cek skor kandidat
  2. Setelah ai_analyst menjawab — cek apakah AI menyatakan data tidak ada

Tidak memanggil AI. Semua logika berbasis rule dan threshold.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import List, Optional

from .models import Candidate, QueryProfile
from .query_parser import normalize_indicator_label

log = logging.getLogger(__name__)

# Threshold skor minimum agar kandidat dianggap "relevan"
# Score > threshold ini → data cukup, tidak perlu reasoning
GAP_SCORE_THRESHOLD = float(__import__("os").getenv("GAP_SCORE_THRESHOLD", "15.0"))

# Frase dalam output AI yang menandakan data tidak tersedia
_DATA_NOT_FOUND_PHRASES = [
    "tidak tersedia",
    "tidak ditemukan",
    "tidak ada data",
    "data tidak ada",
    "belum tersedia",
    "tidak dapat ditemukan",
    "tidak memiliki data",
    "data yang dicari tidak",
    "tidak ada kandidat",
    "kandidat tidak relevan",
    "data yang relevan tidak",
    "tidak relevan dengan pertanyaan",
    "tidak relevan untuk",
    "kurang relevan",
]


@dataclass
class GapAssessment:
    """Hasil penilaian gap data."""

    has_gap: bool
    reason: str                        # penjelasan singkat mengapa ada gap
    best_score: float = 0.0
    top_candidate_indicator: str = ""  # indikator dari kandidat terbaik
    requested_indicator: str = ""      # indikator yang seharusnya ada


def detect_retrieval_gap(
    candidates: List[Candidate],
    profile: QueryProfile,
) -> GapAssessment:
    """
    Cek gap setelah retrieval pertama.

    Gap ada jika:
    - Tidak ada kandidat sama sekali
    - Skor kandidat terbaik di bawah threshold
    - Indikator kandidat terbaik tidak cocok dengan yang diminta
    """
    if not candidates:
        return GapAssessment(
            has_gap=True,
            reason="Tidak ada kandidat data yang ditemukan.",
            best_score=0.0,
        )

    best = candidates[0]
    best_score = best.score
    best_indicator = normalize_indicator_label(
        str(best.record.get("series_label") or "")
    )
    requested = profile.primary_indicator or ""

    # Skor terlalu rendah → data tidak relevan
    if best_score < GAP_SCORE_THRESHOLD:
        log.info(
            f"Gap terdeteksi: skor terbaik {best_score:.1f} < threshold {GAP_SCORE_THRESHOLD}"
        )
        return GapAssessment(
            has_gap=True,
            reason=f"Kandidat terbaik memiliki skor {best_score:.1f}, "
                   f"di bawah threshold {GAP_SCORE_THRESHOLD}. "
                   f"Data yang ditemukan mungkin tidak relevan.",
            best_score=best_score,
            top_candidate_indicator=best_indicator,
            requested_indicator=requested,
        )

    # Indikator tidak cocok dan punya target indikator spesifik
    if (
        requested
        and best_indicator
        and best_indicator != requested
        and best_indicator not in profile.indicator_targets
    ):
        log.info(
            f"Gap terdeteksi: indikator '{best_indicator}' != '{requested}'"
        )
        return GapAssessment(
            has_gap=True,
            reason=f"Kandidat terbaik memiliki indikator '{best_indicator}', "
                   f"bukan '{requested}' yang diminta.",
            best_score=best_score,
            top_candidate_indicator=best_indicator,
            requested_indicator=requested,
        )

    return GapAssessment(
        has_gap=False,
        reason="Kandidat cukup relevan.",
        best_score=best_score,
        top_candidate_indicator=best_indicator,
        requested_indicator=requested,
    )


def detect_analyst_gap(ai_parsed: dict) -> GapAssessment:
    """
    Cek gap dari output ai_analyst.

    Gap ada jika AI menyatakan penilaian "Tidak dapat diverifikasi"
    DAN alasannya mengandung frase yang menunjukkan data tidak ada —
    bukan karena logika tidak cukup, tapi karena data memang tidak tersedia.
    """
    penilaian = str(ai_parsed.get("penilaian") or "").lower()
    alasan = str(ai_parsed.get("alasan") or "").lower()
    temuan = str(ai_parsed.get("temuan_data") or "").lower()

    # Hanya trigger jika penilaian "tidak dapat diverifikasi"
    if "tidak dapat diverifikasi" not in penilaian:
        return GapAssessment(has_gap=False, reason="AI berhasil memberikan penilaian.")

    combined_text = alasan + " " + temuan
    data_missing = any(phrase in combined_text for phrase in _DATA_NOT_FOUND_PHRASES)

    if data_missing:
        log.info("Gap terdeteksi dari output AI: data tidak tersedia menurut analyst.")
        return GapAssessment(
            has_gap=True,
            reason="AI analyst menyatakan data yang dibutuhkan tidak tersedia dalam corpus.",
        )

    # "Tidak dapat diverifikasi" karena alasan lain (logika tidak cukup, dsb.)
    return GapAssessment(
        has_gap=False,
        reason="AI menyatakan tidak dapat diverifikasi, tapi bukan karena data tidak ada.",
    )
