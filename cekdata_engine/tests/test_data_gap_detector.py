"""
tests/test_data_gap_detector.py
================================
Unit test untuk data_gap_detector.py.
Semua test berjalan tanpa corpus, AI, atau koneksi eksternal.
"""
import sys, os, types
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

indicator_registry = types.ModuleType("indicator_registry")
indicator_registry.INDICATOR_CANONICAL = {}
indicator_registry.canonical_indicator_candidates = lambda q: ([], "", False, False)
indicator_registry.normalize_indicator_label = lambda label, fn: fn(label)
sys.modules["indicator_registry"] = indicator_registry

breakdown_registry = types.ModuleType("breakdown_registry")
breakdown_registry.extract_breakdown_context = lambda q: {
    "inferred_age_buckets": [], "explicit_age_buckets": [],
    "gender_targets": [], "generation_targets": [], "area_breakdown_targets": [],
}
sys.modules["breakdown_registry"] = breakdown_registry

from cekdata_engine.data_gap_detector import (
    detect_retrieval_gap, detect_analyst_gap, GapAssessment
)
from cekdata_engine.models import Candidate, QueryProfile
from cekdata_engine.text_utils import normalize_record


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_candidate(score=50.0, series_label="persentase penduduk miskin",
                   area="Indonesia") -> Candidate:
    record = normalize_record({
        "id": "r1", "series_label": series_label,
        "area_name": area, "year": 2023,
    }, 1)
    return Candidate(score=score, record=record, evidence_text="",
                     retrieval_notes=[], keyword_hits=[], metadata_hits={})


def make_profile(primary_indicator="persentase penduduk miskin",
                 indicator_targets=None) -> QueryProfile:
    return QueryProfile(
        raw_question="test", normalized_question="test",
        primary_indicator=primary_indicator,
        indicator_targets=indicator_targets or [primary_indicator],
        area_targets=["Indonesia"], query_type="claim",
        needs_latest=False, needs_recent_range=False,
        requested_trend_years=None, explicit_years=[], periods=[],
        comparison_targets=[], breakdown_targets=[], comparator_words=[],
        quantity_hint=False, ambiguous_indicator=False,
        generated_queries=["test"], keyword_targets=[], metadata_filters={},
    )


# ---------------------------------------------------------------------------
# detect_retrieval_gap
# ---------------------------------------------------------------------------

class TestDetectRetrievalGap:

    def test_no_candidates_has_gap(self):
        profile = make_profile()
        result = detect_retrieval_gap([], profile)
        assert result.has_gap is True
        assert "tidak ada" in result.reason.lower()

    def test_high_score_no_gap(self):
        cands = [make_candidate(score=80.0)]
        profile = make_profile()
        result = detect_retrieval_gap(cands, profile)
        assert result.has_gap is False

    def test_low_score_has_gap(self):
        cands = [make_candidate(score=5.0)]
        profile = make_profile()
        result = detect_retrieval_gap(cands, profile)
        assert result.has_gap is True
        assert result.best_score == 5.0

    def test_wrong_indicator_has_gap(self):
        # Kandidat punya indikator berbeda dari yang diminta
        cands = [make_candidate(score=80.0, series_label="garis kemiskinan")]
        profile = make_profile(
            primary_indicator="persentase penduduk miskin",
            indicator_targets=["persentase penduduk miskin"],
        )
        result = detect_retrieval_gap(cands, profile)
        assert result.has_gap is True
        assert "garis kemiskinan" in result.reason

    def test_matching_indicator_no_gap(self):
        cands = [make_candidate(score=80.0, series_label="persentase penduduk miskin")]
        profile = make_profile(primary_indicator="persentase penduduk miskin")
        result = detect_retrieval_gap(cands, profile)
        assert result.has_gap is False

    def test_no_primary_indicator_only_checks_score(self):
        # Jika tidak ada primary_indicator, hanya skor yang dicek
        cands = [make_candidate(score=80.0, series_label="indikator acak")]
        profile = make_profile(primary_indicator="")
        result = detect_retrieval_gap(cands, profile)
        assert result.has_gap is False

    def test_gap_assessment_fields_populated(self):
        cands = [make_candidate(score=5.0, series_label="garis kemiskinan")]
        profile = make_profile(primary_indicator="persentase penduduk miskin")
        result = detect_retrieval_gap(cands, profile)
        assert isinstance(result.best_score, float)
        assert result.top_candidate_indicator != ""
        assert result.requested_indicator == "persentase penduduk miskin"

    def test_indicator_in_targets_no_gap(self):
        # Jika indikator ada di indicator_targets meski bukan primary, tidak ada gap
        cands = [make_candidate(score=80.0, series_label="jumlah penduduk miskin")]
        profile = make_profile(
            primary_indicator="persentase penduduk miskin",
            indicator_targets=["persentase penduduk miskin", "jumlah penduduk miskin"],
        )
        result = detect_retrieval_gap(cands, profile)
        assert result.has_gap is False

    def test_returns_gap_assessment_type(self):
        result = detect_retrieval_gap([], make_profile())
        assert isinstance(result, GapAssessment)


# ---------------------------------------------------------------------------
# detect_analyst_gap
# ---------------------------------------------------------------------------

class TestDetectAnalystGap:

    def test_benar_no_gap(self):
        result = detect_analyst_gap({"penilaian": "Benar", "alasan": "Data mendukung."})
        assert result.has_gap is False

    def test_salah_no_gap(self):
        result = detect_analyst_gap({"penilaian": "Salah", "alasan": "Data bertentangan."})
        assert result.has_gap is False

    def test_tidak_dapat_diverifikasi_with_data_missing_phrase_has_gap(self):
        result = detect_analyst_gap({
            "penilaian": "Tidak dapat diverifikasi",
            "alasan": "Data tidak tersedia dalam corpus untuk menjawab pertanyaan ini.",
        })
        assert result.has_gap is True

    def test_tidak_dapat_diverifikasi_without_data_missing_no_gap(self):
        # "Tidak dapat diverifikasi" karena logika tidak cukup, bukan data tidak ada
        result = detect_analyst_gap({
            "penilaian": "Tidak dapat diverifikasi",
            "alasan": "Perbandingan periode tidak setara sehingga penilaian tidak bisa ditegakkan.",
        })
        assert result.has_gap is False

    def test_data_missing_in_temuan_data(self):
        result = detect_analyst_gap({
            "penilaian": "Tidak dapat diverifikasi",
            "alasan": "Alasan lain.",
            "temuan_data": "Data yang ditemukan tidak relevan dengan pertanyaan.",
        })
        assert result.has_gap is True

    def test_empty_penilaian_no_gap(self):
        # Penilaian kosong (pertanyaan data langsung) — tidak trigger gap
        result = detect_analyst_gap({"penilaian": "", "alasan": ""})
        assert result.has_gap is False

    def test_sebagian_benar_no_gap(self):
        result = detect_analyst_gap({
            "penilaian": "Sebagian benar",
            "alasan": "Sebagian data mendukung.",
        })
        assert result.has_gap is False

    def test_various_not_found_phrases(self):
        phrases = [
            "tidak ditemukan",
            "tidak ada data",
            "belum tersedia",
            "tidak dapat ditemukan",
        ]
        for phrase in phrases:
            result = detect_analyst_gap({
                "penilaian": "Tidak dapat diverifikasi",
                "alasan": f"Data {phrase} dalam corpus.",
            })
            assert result.has_gap is True, f"Phrase '{phrase}' tidak terdeteksi"

    def test_returns_gap_assessment_type(self):
        result = detect_analyst_gap({"penilaian": "Benar"})
        assert isinstance(result, GapAssessment)
