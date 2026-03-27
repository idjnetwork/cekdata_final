"""
tests/test_scorer.py
====================
Unit test untuk score_record(), diversify_candidates(), pack_candidates_for_ai().
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

from cekdata_engine.scorer import score_record, diversify_candidates, pack_candidates_for_ai
from cekdata_engine.models import Candidate, QueryProfile
from cekdata_engine.text_utils import normalize_record


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_record(**kwargs) -> dict:
    defaults = {
        "id": "r1", "doc_type": "atomic",
        "series_label": "persentase penduduk miskin",
        "area_name": "Indonesia", "breakdown_value": "",
        "subgroup_value": "", "year": 2023, "period": "",
        "text": "", "title": "",
    }
    defaults.update(kwargs)
    return normalize_record(defaults, 1)


def make_profile(**kwargs) -> QueryProfile:
    defaults = dict(
        raw_question="test",
        normalized_question="test",
        query_type="claim",
        needs_latest=False,
        needs_recent_range=False,
        requested_trend_years=None,
        explicit_years=[],
        periods=[],
        indicator_targets=["persentase penduduk miskin"],
        primary_indicator="persentase penduduk miskin",
        area_targets=["Indonesia"],
        comparison_targets=[],
        breakdown_targets=[],
        comparator_words=[],
        quantity_hint=False,
        ambiguous_indicator=False,
        generated_queries=["test"],
        keyword_targets=[],
        metadata_filters={},
    )
    defaults.update(kwargs)
    return QueryProfile(**defaults)


def make_candidate(**record_kwargs) -> Candidate:
    profile = make_profile()
    record = make_record(**record_kwargs)
    return score_record(record, profile)


# ---------------------------------------------------------------------------
# score_record: indikator
# ---------------------------------------------------------------------------

class TestScoreIndicator:
    def test_primary_indicator_match_highest(self):
        profile = make_profile(primary_indicator="persentase penduduk miskin")
        r_match = make_record(series_label="persentase penduduk miskin")
        r_other = make_record(series_label="garis kemiskinan")
        c_match = score_record(r_match, profile)
        c_other = score_record(r_other, profile)
        assert c_match.score > c_other.score

    def test_wrong_indicator_penalized(self):
        profile = make_profile(primary_indicator="persentase penduduk miskin")
        r_garis = make_record(series_label="garis kemiskinan")
        r_persen = make_record(series_label="persentase penduduk miskin")
        c_garis = score_record(r_garis, profile)
        c_persen = score_record(r_persen, profile)
        assert c_persen.score > c_garis.score

    def test_primary_indicator_note_added(self):
        profile = make_profile(primary_indicator="persentase penduduk miskin")
        r = make_record(series_label="persentase penduduk miskin")
        c = score_record(r, profile)
        assert "primary_indicator_match" in c.retrieval_notes

    def test_secondary_indicator_match(self):
        profile = make_profile(
            primary_indicator="persentase penduduk miskin",
            indicator_targets=["persentase penduduk miskin", "jumlah penduduk miskin"],
        )
        r = make_record(series_label="jumlah penduduk miskin")
        c = score_record(r, profile)
        assert "secondary_indicator_match" in c.retrieval_notes


# ---------------------------------------------------------------------------
# score_record: wilayah
# ---------------------------------------------------------------------------

class TestScoreArea:
    def test_area_match_bonus(self):
        profile = make_profile(area_targets=["Jawa Timur"])
        r_match = make_record(area_name="Jawa Timur")
        r_other = make_record(area_name="Aceh")
        c_match = score_record(r_match, profile)
        c_other = score_record(r_other, profile)
        assert c_match.score > c_other.score

    def test_non_target_area_penalized(self):
        profile = make_profile(area_targets=["Jawa Timur"])
        r = make_record(area_name="Papua")
        c = score_record(r, profile)
        assert "penalty_non_target_area" in c.retrieval_notes

    def test_no_area_target_indonesia_small_bonus(self):
        profile = make_profile(area_targets=[])
        r = make_record(area_name="Indonesia")
        c = score_record(r, profile)
        assert c.score > 0


# ---------------------------------------------------------------------------
# score_record: breakdown
# ---------------------------------------------------------------------------

class TestScoreBreakdown:
    def test_aggregate_breakdown_bonus(self):
        profile = make_profile(breakdown_targets=[])
        r = make_record(breakdown_value="")
        c = score_record(r, profile)
        assert "aggregate_breakdown_bonus" in c.retrieval_notes

    def test_detailed_breakdown_penalized_if_not_requested(self):
        profile = make_profile(breakdown_targets=[])
        r = make_record(breakdown_value="Laki-laki")
        c = score_record(r, profile)
        assert "penalty_unrequested_detailed_breakdown" in c.retrieval_notes

    def test_breakdown_match_bonus(self):
        profile = make_profile(breakdown_targets=["Perdesaan"])
        r_match = make_record(breakdown_value="Perdesaan")
        r_other = make_record(breakdown_value="Perkotaan")
        c_match = score_record(r_match, profile)
        c_other = score_record(r_other, profile)
        assert c_match.score > c_other.score


# ---------------------------------------------------------------------------
# score_record: temporal
# ---------------------------------------------------------------------------

class TestScoreTemporal:
    def test_explicit_year_bonus(self):
        profile = make_profile(explicit_years=[2022])
        r_match = make_record(year=2022)
        r_other = make_record(year=2019)
        c_match = score_record(r_match, profile)
        c_other = score_record(r_other, profile)
        assert c_match.score > c_other.score

    def test_latest_bias_newer_scores_higher(self):
        profile = make_profile(needs_latest=True, explicit_years=[])
        r_new = make_record(year=2023)
        r_old = make_record(year=2015)
        c_new = score_record(r_new, profile)
        c_old = score_record(r_old, profile)
        assert c_new.score > c_old.score

    def test_period_match_bonus(self):
        profile = make_profile(periods=["Maret"])
        r_match = make_record(period="Maret")
        r_other = make_record(period="September")
        c_match = score_record(r_match, profile)
        c_other = score_record(r_other, profile)
        assert c_match.score > c_other.score


# ---------------------------------------------------------------------------
# score_record: query_type trend
# ---------------------------------------------------------------------------

class TestScoreTrend:
    def test_atomic_prioritized_for_requested_years(self):
        profile = make_profile(
            query_type="trend", requested_trend_years=5,
            primary_indicator="persentase penduduk miskin",
        )
        r_atomic = make_record(doc_type="atomic", year=2023)
        r_trend = make_record(doc_type="trend", year=2023)
        c_atomic = score_record(r_atomic, profile)
        c_trend = score_record(r_trend, profile)
        assert c_atomic.score > c_trend.score

    def test_trend_doc_bonus_without_requested_years(self):
        profile = make_profile(
            query_type="trend", requested_trend_years=None,
            primary_indicator="persentase penduduk miskin",
        )
        r_trend = make_record(doc_type="trend", year_start=2018, year_end=2023)
        c = score_record(r_trend, profile)
        assert "trend_doc_type" in c.retrieval_notes


# ---------------------------------------------------------------------------
# diversify_candidates
# ---------------------------------------------------------------------------

class TestDiversifyCandidates:
    def _make_candidate(self, area, year, indicator="persentase penduduk miskin") -> Candidate:
        profile = make_profile(area_targets=[area])
        record = make_record(area_name=area, year=year, series_label=indicator)
        return score_record(record, profile)

    def test_returns_at_most_top_k(self):
        profile = make_profile(area_targets=["Indonesia"])
        candidates = [self._make_candidate("Indonesia", y) for y in range(2015, 2024)]
        result = diversify_candidates(candidates, profile, top_k=5)
        assert len(result) <= 5

    def test_empty_input(self):
        profile = make_profile()
        assert diversify_candidates([], profile, top_k=5) == []

    def test_comparison_includes_both_sides(self):
        profile = make_profile(
            query_type="comparison",
            area_targets=["Jawa Barat", "Jawa Timur"],
            comparison_targets=["Jawa Barat", "Jawa Timur"],
        )
        cands = [
            score_record(make_record(area_name="Jawa Barat", year=2023), profile),
            score_record(make_record(area_name="Jawa Timur", year=2023), profile),
            score_record(make_record(area_name="Aceh", year=2023), profile),
        ]
        result = diversify_candidates(cands, profile, top_k=5)
        areas = {c.record["area_name"] for c in result}
        assert "Jawa Barat" in areas
        assert "Jawa Timur" in areas

    def test_no_duplicates(self):
        profile = make_profile(area_targets=["Indonesia"])
        base_record = make_record(area_name="Indonesia", year=2023)
        # Buat Candidate yang sama dua kali dengan score berbeda
        c1 = Candidate(score=10, record=base_record, evidence_text="", retrieval_notes=[], keyword_hits=[], metadata_hits={})
        c2 = Candidate(score=8, record=base_record, evidence_text="", retrieval_notes=[], keyword_hits=[], metadata_hits={})
        result = diversify_candidates([c1, c2], profile, top_k=5)
        # c1 dan c2 adalah object berbeda, keduanya boleh masuk
        # yang penting tidak ada object yang sama persis dua kali
        seen_ids = set()
        for c in result:
            assert id(c) not in seen_ids
            seen_ids.add(id(c))


# ---------------------------------------------------------------------------
# pack_candidates_for_ai
# ---------------------------------------------------------------------------

class TestPackCandidatesForAi:
    def _cand(self, area, year, breakdown="") -> Candidate:
        profile = make_profile()
        r = make_record(area_name=area, year=year, breakdown_value=breakdown)
        return score_record(r, profile)

    def test_respects_top_k(self):
        profile = make_profile(query_type="claim")
        cands = [self._cand("Indonesia", y) for y in range(2010, 2020)]
        result = pack_candidates_for_ai(cands, profile, top_k=4)
        assert len(result) <= 4

    def test_trend_uses_pack_trend(self):
        profile = make_profile(
            query_type="trend",
            primary_indicator="persentase penduduk miskin",
            area_targets=["Indonesia"],
            requested_trend_years=3,
        )
        cands = [
            score_record(make_record(area_name="Indonesia", year=y, doc_type="atomic"), profile)
            for y in range(2018, 2024)
        ]
        result = pack_candidates_for_ai(cands, profile, top_k=8)
        assert len(result) >= 1

    def test_comparison_aligns_periods(self):
        profile = make_profile(
            query_type="comparison",
            area_targets=["Jawa Barat", "Jawa Timur"],
            comparison_targets=["Jawa Barat", "Jawa Timur"],
            primary_indicator="persentase penduduk miskin",
        )
        cands = [
            score_record(make_record(area_name="Jawa Barat", year=2023), profile),
            score_record(make_record(area_name="Jawa Timur", year=2023), profile),
        ]
        result = pack_candidates_for_ai(cands, profile, top_k=8)
        areas = {c.record["area_name"] for c in result}
        assert "Jawa Barat" in areas
        assert "Jawa Timur" in areas
