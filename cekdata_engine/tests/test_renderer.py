"""
tests/test_renderer.py
======================
Unit test untuk render_answer(), build_top_matches(), pick_best_match().
"""
import sys, os, types
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

indicator_registry = types.ModuleType("indicator_registry")
indicator_registry.INDICATOR_CANONICAL = {}
indicator_registry.canonical_indicator_candidates = lambda q: ([], "", False, False)
indicator_registry.normalize_indicator_label = lambda label, fn: fn(label)
sys.modules["indicator_registry"] = indicator_registry

breakdown_registry = types.ModuleType("breakdown_registry")
breakdown_registry.extract_breakdown_context = lambda q: {}
sys.modules["breakdown_registry"] = breakdown_registry

from cekdata_engine.renderer import render_answer, build_top_matches, pick_best_match
from cekdata_engine.models import Candidate, QueryProfile
from cekdata_engine.text_utils import normalize_record


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_parsed(**kwargs):
    base = {
        "claim": "", "indicator_used": "", "records_used": [],
        "temuan_data": "", "konteks_penting": "", "penilaian": "",
        "alasan": "", "peringatan_editorial": "", "sumber": "", "unduh_data": "",
    }
    base.update(kwargs)
    return base


def make_candidate(id="r1", area="Indonesia", year=2023, score=10.0) -> Candidate:
    r = normalize_record({"id": id, "area_name": area, "year": year, "title": f"Data {area}"}, 1)
    return Candidate(
        score=score, record=r, evidence_text="",
        retrieval_notes=["area_match"], keyword_hits=["kemiskinan"], metadata_hits={},
    )


def make_profile(query_type="claim") -> QueryProfile:
    return QueryProfile(
        raw_question="test", normalized_question="test",
        query_type=query_type, needs_latest=False, needs_recent_range=False,
        requested_trend_years=None, explicit_years=[], periods=[],
        indicator_targets=[], primary_indicator="", area_targets=[],
        comparison_targets=[], breakdown_targets=[], comparator_words=[],
        quantity_hint=False, ambiguous_indicator=False,
        generated_queries=[], keyword_targets=[], metadata_filters={},
    )


# ---------------------------------------------------------------------------
# render_answer
# ---------------------------------------------------------------------------

class TestRenderAnswer:
    def test_all_fields(self):
        parsed = make_parsed(
            claim="Klaim test",
            temuan_data="Kemiskinan turun",
            konteks_penting="Data Maret",
            penilaian="Benar",
            alasan="Ada penurunan.",
            peringatan_editorial="Perlu verifikasi lebih lanjut.",
            sumber="BPS 2023",
            unduh_data="https://bps.go.id/data.csv",
        )
        result = render_answer(parsed)
        assert "Klaim" in result
        assert "Temuan data" in result
        assert "Penilaian" in result
        assert "Benar" in result
        assert "Alasan" in result
        assert "Peringatan editorial" in result
        assert "Sumber: BPS 2023" in result
        assert "Unduh data: https://bps.go.id/data.csv" in result

    def test_empty_fields_skipped(self):
        parsed = make_parsed(claim="Klaim saja", penilaian="Salah")
        result = render_answer(parsed)
        assert "Klaim" in result
        assert "Penilaian" in result
        # Field kosong tidak muncul
        assert "Temuan data" not in result
        assert "Peringatan editorial" not in result

    def test_unduh_data_list_single(self):
        parsed = make_parsed(unduh_data=["https://a.com"])
        result = render_answer(parsed)
        assert "https://a.com" in result
        assert "Unduh data:" in result

    def test_unduh_data_list_multiple(self):
        parsed = make_parsed(unduh_data=["https://a.com", "https://b.com"])
        result = render_answer(parsed)
        assert "* https://a.com" in result
        assert "* https://b.com" in result

    def test_empty_parsed(self):
        result = render_answer(make_parsed())
        assert result == ""

    def test_sections_separated_by_double_newline(self):
        parsed = make_parsed(claim="Klaim", penilaian="Benar")
        result = render_answer(parsed)
        assert "\n\n" in result

    def test_no_empty_sections(self):
        parsed = make_parsed(penilaian="Salah", alasan="Karena data tidak mendukung.")
        result = render_answer(parsed)
        assert "\n\n\n" not in result  # tidak ada section kosong


# ---------------------------------------------------------------------------
# build_top_matches
# ---------------------------------------------------------------------------

class TestBuildTopMatches:
    def test_respects_top_k(self):
        cands = [make_candidate(id=f"r{i}", year=2020+i) for i in range(10)]
        result = build_top_matches(cands, top_k=3)
        assert len(result) == 3

    def test_rank_starts_at_1(self):
        cands = [make_candidate()]
        result = build_top_matches(cands, top_k=5)
        assert result[0]["rank"] == 1

    def test_includes_required_fields(self):
        cands = [make_candidate(id="r1", area="Bali", year=2023, score=7.5)]
        result = build_top_matches(cands, top_k=5)
        row = result[0]
        assert row["candidate_id"] == "r1"
        assert row["score"] == 7.5
        assert row["area_name"] == "Bali"
        assert row["year"] == 2023
        assert "retrieval_notes" in row
        assert "keyword_hits" in row

    def test_empty_candidates(self):
        assert build_top_matches([], top_k=5) == []


# ---------------------------------------------------------------------------
# pick_best_match
# ---------------------------------------------------------------------------

class TestPickBestMatch:
    def test_picks_from_records_used(self):
        cands = [make_candidate(id="r1"), make_candidate(id="r2")]
        parsed = make_parsed(records_used=["r2"])
        result = pick_best_match(parsed, cands)
        assert result["id"] == "r2"

    def test_fallback_to_first_if_no_records_used(self):
        cands = [make_candidate(id="r1"), make_candidate(id="r2")]
        parsed = make_parsed(records_used=[])
        result = pick_best_match(parsed, cands)
        assert result["id"] == "r1"

    def test_comparison_picks_first_candidate(self):
        cands = [make_candidate(id="r1"), make_candidate(id="r2")]
        parsed = make_parsed(records_used=["r2"])
        profile = make_profile(query_type="comparison")
        result = pick_best_match(parsed, cands, profile)
        assert result["id"] == "r1"  # comparison selalu ambil kandidat[0]

    def test_trend_picks_latest(self):
        c1 = make_candidate(id="r1", year=2021)
        c2 = make_candidate(id="r2", year=2023)
        c3 = make_candidate(id="r3", year=2019)
        parsed = make_parsed(records_used=[])
        profile = make_profile(query_type="trend")
        result = pick_best_match(parsed, [c1, c2, c3], profile)
        assert result["id"] == "r2"  # tahun paling baru

    def test_empty_candidates_returns_none(self):
        assert pick_best_match(make_parsed(), [], make_profile()) is None
