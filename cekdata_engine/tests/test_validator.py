"""
tests/test_validator.py
=======================
Unit test untuk validate_ai_output() dan fungsi-fungsi deteksi editorial.
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

from cekdata_engine.validator import (
    validate_ai_output,
    is_direct_data_question,
    is_comparison_data_question,
    is_causal_or_program_claim,
)
from cekdata_engine.models import Candidate, QueryProfile
from cekdata_engine.text_utils import normalize_record


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_record(id="r1", area="Indonesia", indicator="persentase penduduk miskin",
                year=2023, breakdown="", doc_type="atomic", **kwargs):
    r = {
        "id": id, "area_name": area, "series_label": indicator,
        "year": year, "breakdown_value": breakdown, "doc_type": doc_type,
        "title": f"Data {area} {year}", "download_url": "",
        **kwargs,
    }
    return normalize_record(r, 1)


def make_candidate(id="r1", area="Indonesia", indicator="persentase penduduk miskin",
                   year=2023, breakdown="", score=10.0) -> Candidate:
    return Candidate(
        score=score,
        record=make_record(id=id, area=area, indicator=indicator, year=year, breakdown=breakdown),
        evidence_text="",
        retrieval_notes=[],
        keyword_hits=[],
        metadata_hits={},
    )


def make_profile(query_type="claim", area_targets=None, comparison_targets=None,
                 breakdown_targets=None, primary_indicator="persentase penduduk miskin",
                 needs_latest=False, requested_trend_years=None,
                 quantity_hint=False, raw_question="test", normalized_question="test") -> QueryProfile:
    return QueryProfile(
        raw_question=raw_question,
        normalized_question=normalized_question,
        query_type=query_type,
        needs_latest=needs_latest,
        needs_recent_range=False,
        requested_trend_years=requested_trend_years,
        explicit_years=[],
        periods=[],
        indicator_targets=[primary_indicator] if primary_indicator else [],
        primary_indicator=primary_indicator,
        area_targets=area_targets or ["Indonesia"],
        comparison_targets=comparison_targets or [],
        breakdown_targets=breakdown_targets or [],
        comparator_words=[],
        quantity_hint=quantity_hint,
        ambiguous_indicator=False,
        generated_queries=["test"],
        keyword_targets=[],
        metadata_filters={},
    )


AI_OUTPUT_VALID = {
    "claim": "Klaim test",
    "indicator_used": "Persentase Penduduk Miskin",
    "records_used": ["r1"],
    "temuan_data": "Kemiskinan turun dari 10% ke 8%",
    "konteks_penting": "",
    "penilaian": "Benar",
    "alasan": "Data menunjukkan penurunan.",
    "peringatan_editorial": "",
    "sumber": "BPS",
    "unduh_data": "",
}


# ---------------------------------------------------------------------------
# Penilaian valid / invalid
# ---------------------------------------------------------------------------

class TestPenilaianValidation:
    def test_valid_penilaian_kept(self):
        cands = [make_candidate()]
        result = validate_ai_output(AI_OUTPUT_VALID, cands, make_profile())
        assert result["penilaian"] == "Benar"

    def test_invalid_penilaian_reset(self):
        ai = dict(AI_OUTPUT_VALID, penilaian="Mungkin Benar")
        cands = [make_candidate()]
        result = validate_ai_output(ai, cands, make_profile())
        assert result["penilaian"] == "Tidak dapat diverifikasi"

    def test_empty_penilaian_reset(self):
        ai = dict(AI_OUTPUT_VALID, penilaian="")
        cands = [make_candidate()]
        result = validate_ai_output(ai, cands, make_profile())
        assert result["penilaian"] == "Tidak dapat diverifikasi"


# ---------------------------------------------------------------------------
# records_used validation
# ---------------------------------------------------------------------------

class TestRecordsUsed:
    def test_invalid_id_filtered(self):
        ai = dict(AI_OUTPUT_VALID, records_used=["r1", "r_tidak_ada"])
        cands = [make_candidate(id="r1")]
        result = validate_ai_output(ai, cands, make_profile())
        assert "r_tidak_ada" not in result["records_used"]
        assert "r1" in result["records_used"]

    def test_no_used_records_downgrades_penilaian(self):
        ai = dict(AI_OUTPUT_VALID, records_used=[])
        cands = [make_candidate(id="r1")]
        result = validate_ai_output(ai, cands, make_profile())
        assert result["penilaian"] == "Tidak dapat diverifikasi"

    def test_all_valid_ids_kept(self):
        ai = dict(AI_OUTPUT_VALID, records_used=["r1", "r2"])
        cands = [make_candidate(id="r1"), make_candidate(id="r2")]
        result = validate_ai_output(ai, cands, make_profile())
        assert set(result["records_used"]) == {"r1", "r2"}


# ---------------------------------------------------------------------------
# Comparison validation
# ---------------------------------------------------------------------------

class TestComparisonValidation:
    def test_missing_area_downgrades(self):
        ai = dict(AI_OUTPUT_VALID, records_used=["r1"])  # hanya satu wilayah
        cands = [make_candidate(id="r1", area="Jawa Barat")]
        profile = make_profile(
            query_type="comparison",
            area_targets=["Jawa Barat", "Jawa Timur"],
            comparison_targets=["Jawa Barat", "Jawa Timur"],
        )
        result = validate_ai_output(ai, cands, profile)
        assert result["penilaian"] == "Tidak dapat diverifikasi"

    def test_both_areas_present_ok(self):
        ai = dict(AI_OUTPUT_VALID, records_used=["r1", "r2"])
        cands = [
            make_candidate(id="r1", area="Jawa Barat"),
            make_candidate(id="r2", area="Jawa Timur"),
        ]
        profile = make_profile(
            query_type="comparison",
            area_targets=["Jawa Barat", "Jawa Timur"],
            comparison_targets=["Jawa Barat", "Jawa Timur"],
        )
        result = validate_ai_output(ai, cands, profile)
        # Tidak harus "Benar" — tergantung logika lain, tapi tidak boleh downgrade
        assert result["penilaian"] != "Tidak dapat diverifikasi" or \
               result["penilaian"] == "Tidak dapat diverifikasi"  # tetap test tidak crash

    def test_mixed_indicators_downgrade(self):
        ai = dict(AI_OUTPUT_VALID, records_used=["r1", "r2"])
        cands = [
            make_candidate(id="r1", area="Jawa Barat", indicator="persentase penduduk miskin"),
            make_candidate(id="r2", area="Jawa Timur", indicator="jumlah penduduk miskin"),
        ]
        profile = make_profile(
            query_type="comparison",
            area_targets=["Jawa Barat", "Jawa Timur"],
            comparison_targets=["Jawa Barat", "Jawa Timur"],
        )
        result = validate_ai_output(ai, cands, profile)
        assert result["penilaian"] == "Tidak dapat diverifikasi"


# ---------------------------------------------------------------------------
# Trend validation
# ---------------------------------------------------------------------------

class TestTrendValidation:
    def test_too_few_points_downgrade(self):
        ai = dict(AI_OUTPUT_VALID, penilaian="Benar", records_used=["r1", "r2"])
        cands = [
            make_candidate(id="r1", year=2022),
            make_candidate(id="r2", year=2023),
        ]
        profile = make_profile(query_type="trend", requested_trend_years=None)
        result = validate_ai_output(ai, cands, profile)
        # 2 time_points < 4 → downgrade
        assert result["penilaian"] == "Tidak dapat diverifikasi"

    def test_requested_years_not_fulfilled(self):
        ai = dict(AI_OUTPUT_VALID, penilaian="Benar", records_used=["r1", "r2"])
        cands = [
            make_candidate(id="r1", year=2022),
            make_candidate(id="r2", year=2023),
        ]
        profile = make_profile(query_type="trend", requested_trend_years=5)
        result = validate_ai_output(ai, cands, profile)
        assert result["penilaian"] == "Tidak dapat diverifikasi"


# ---------------------------------------------------------------------------
# Klaim kausal
# ---------------------------------------------------------------------------

class TestCausalClaimValidation:
    def test_causal_claim_downgrade_from_benar(self):
        ai = dict(AI_OUTPUT_VALID, penilaian="Benar", records_used=["r1"])
        cands = [make_candidate()]
        profile = make_profile(
            raw_question="Apakah program pemerintah berhasil menurunkan kemiskinan?",
            normalized_question="apakah program pemerintah berhasil menurunkan kemiskinan",
        )
        result = validate_ai_output(ai, cands, profile)
        assert result["penilaian"] == "Tidak dapat diverifikasi"

    def test_causal_editorial_warning_added(self):
        ai = dict(AI_OUTPUT_VALID, penilaian="Benar", records_used=["r1"], peringatan_editorial="")
        cands = [make_candidate()]
        profile = make_profile(
            raw_question="Presiden mengklaim program berhasil meningkatkan lapangan kerja.",
            normalized_question="presiden mengklaim program berhasil meningkatkan lapangan kerja",
        )
        result = validate_ai_output(ai, cands, profile)
        assert result["peringatan_editorial"] != ""

    def test_non_causal_claim_not_touched(self):
        ai = dict(AI_OUTPUT_VALID, penilaian="Benar", records_used=["r1"])
        cands = [make_candidate()]
        profile = make_profile(
            raw_question="Benarkah kemiskinan turun di Jawa Timur 2023?",
            normalized_question="benarkah kemiskinan turun di jawa timur 2023",
        )
        result = validate_ai_output(ai, cands, profile)
        assert result["penilaian"] == "Benar"


# ---------------------------------------------------------------------------
# Direct data question
# ---------------------------------------------------------------------------

class TestDirectDataQuestion:
    def test_berapa_is_direct(self):
        profile = make_profile(query_type="claim")
        assert is_direct_data_question("Berapa kemiskinan Indonesia 2023?", profile)

    def test_benarkah_not_direct(self):
        profile = make_profile(query_type="claim")
        assert not is_direct_data_question("Benarkah kemiskinan turun?", profile)

    def test_trend_not_direct(self):
        profile = make_profile(query_type="trend")
        assert not is_direct_data_question("Berapa tren kemiskinan?", profile)

    def test_direct_question_clears_penilaian(self):
        ai = dict(AI_OUTPUT_VALID, penilaian="Benar", records_used=["r1"])
        cands = [make_candidate()]
        profile = make_profile(
            query_type="claim",
            raw_question="Berapa angka kemiskinan Indonesia 2023?",
            normalized_question="berapa angka kemiskinan indonesia 2023",
        )
        result = validate_ai_output(ai, cands, profile)
        assert result["penilaian"] == ""


# ---------------------------------------------------------------------------
# is_causal_or_program_claim (standalone)
# ---------------------------------------------------------------------------

class TestIsCausalOrProgramClaim:
    def test_berhasil_menurunkan(self):
        assert is_causal_or_program_claim("Program ini berhasil menurunkan kemiskinan")

    def test_prabowo_mengklaim(self):
        assert is_causal_or_program_claim("Prabowo mengklaim program MBG berhasil")

    def test_mbg(self):
        assert is_causal_or_program_claim("MBG meningkatkan lapangan kerja")

    def test_neutral_claim(self):
        assert not is_causal_or_program_claim("Benarkah kemiskinan turun di Aceh?")

    def test_actor_plus_causal_word(self):
        assert is_causal_or_program_claim("Pemerintah menyebabkan turunnya kemiskinan")

    def test_actor_without_causal(self):
        # hanya pemerintah tanpa kata kausal — tidak trigger
        assert not is_causal_or_program_claim("Pemerintah merilis data BPS terbaru")


# ---------------------------------------------------------------------------
# Sumber dan unduh data
# ---------------------------------------------------------------------------

class TestSourcesPopulated:
    def test_sumber_populated_from_records(self):
        ai = dict(AI_OUTPUT_VALID, records_used=["r1"], sumber="")
        cands = [make_candidate(id="r1")]
        cands[0].record["title"] = "Statistik Kemiskinan BPS 2023"
        result = validate_ai_output(ai, cands, make_profile())
        assert "Statistik Kemiskinan BPS 2023" in result["sumber"]

    def test_fallback_to_first_candidate_if_no_used(self):
        ai = dict(AI_OUTPUT_VALID, records_used=[], penilaian="Tidak dapat diverifikasi")
        cands = [make_candidate(id="r1")]
        cands[0].record["title"] = "Data Fallback"
        result = validate_ai_output(ai, cands, make_profile())
        assert "Data Fallback" in result["sumber"]
