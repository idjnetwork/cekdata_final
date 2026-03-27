"""
tests/test_query_parser.py
==========================
Unit test untuk make_query_profile() dan is_vague_question().
Semua test berjalan tanpa corpus nyata atau koneksi AI.
"""
import sys, os, types
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Stub external dependencies
indicator_registry = types.ModuleType("indicator_registry")
indicator_registry.INDICATOR_CANONICAL = {}

def _mock_candidates(q):
    """Mock sederhana: deteksi kata kunci kemiskinan → kembalikan indikator."""
    if "kemiskinan" in q or "miskin" in q:
        return (
            ["persentase penduduk miskin"],
            "persentase penduduk miskin",
            False,
            False,
        )
    if "jumlah" in q and ("miskin" in q or "orang miskin" in q):
        return (
            ["jumlah penduduk miskin"],
            "jumlah penduduk miskin",
            True,
            False,
        )
    return ([], "", False, False)

indicator_registry.canonical_indicator_candidates = _mock_candidates
indicator_registry.normalize_indicator_label = lambda label, fn: fn(label)
sys.modules["indicator_registry"] = indicator_registry

breakdown_registry = types.ModuleType("breakdown_registry")
breakdown_registry.extract_breakdown_context = lambda q: {
    "inferred_age_buckets": [],
    "explicit_age_buckets": [],
    "gender_targets": [],
    "generation_targets": [],
    "area_breakdown_targets": [],
}
sys.modules["breakdown_registry"] = breakdown_registry

from cekdata_engine.query_parser import make_query_profile, is_vague_question


# ---------------------------------------------------------------------------
# Jenis query
# ---------------------------------------------------------------------------

class TestQueryType:
    def test_claim_default(self):
        p = make_query_profile("Benarkah kemiskinan menurun di Jawa Timur?")
        assert p.query_type == "claim"

    def test_trend_from_cue(self):
        p = make_query_profile("Bagaimana tren kemiskinan dalam beberapa tahun terakhir?")
        assert p.query_type == "trend"

    def test_trend_from_explicit_years(self):
        p = make_query_profile("Kemiskinan 5 tahun terakhir di Indonesia")
        assert p.query_type == "trend"
        assert p.requested_trend_years == 5

    def test_comparison_from_bandingkan(self):
        p = make_query_profile("Bandingkan kemiskinan Jawa Barat dan Jawa Timur")
        assert p.query_type == "comparison"

    def test_comparison_from_vs(self):
        p = make_query_profile("Kemiskinan Jawa Timur vs nasional")
        assert p.query_type == "comparison"


# ---------------------------------------------------------------------------
# Ekstraksi wilayah
# ---------------------------------------------------------------------------

class TestAreaExtraction:
    def test_province_alias(self):
        p = make_query_profile("kemiskinan jatim tahun 2023")
        assert "Jawa Timur" in p.area_targets

    def test_national_alias(self):
        p = make_query_profile("rata rata nasional kemiskinan")
        assert "Indonesia" in p.area_targets

    def test_multiple_provinces(self):
        p = make_query_profile("kemiskinan jabar vs jatim")
        assert "Jawa Barat" in p.area_targets
        assert "Jawa Timur" in p.area_targets

    def test_breakdown_perdesaan(self):
        p = make_query_profile("kemiskinan di perdesaan Indonesia")
        assert "Perdesaan" in p.breakdown_targets

    def test_breakdown_perkotaan(self):
        p = make_query_profile("kemiskinan di perkotaan")
        assert "Perkotaan" in p.breakdown_targets

    def test_comparison_targets_set(self):
        p = make_query_profile("kemiskinan jatim dibanding nasional")
        assert len(p.comparison_targets) >= 2

    def test_dki_alias(self):
        p = make_query_profile("kemiskinan jakarta")
        assert "DKI Jakarta" in p.area_targets


# ---------------------------------------------------------------------------
# Temporal
# ---------------------------------------------------------------------------

class TestTemporalExtraction:
    def test_explicit_year(self):
        p = make_query_profile("kemiskinan tahun 2022")
        assert 2022 in p.explicit_years

    def test_two_years(self):
        p = make_query_profile("perbandingan kemiskinan 2020 dan 2023")
        assert 2020 in p.explicit_years
        assert 2023 in p.explicit_years

    def test_period_maret(self):
        p = make_query_profile("kemiskinan Maret 2023")
        assert "Maret" in p.periods

    def test_period_september(self):
        p = make_query_profile("kemiskinan September 2022")
        assert "September" in p.periods

    def test_needs_latest(self):
        p = make_query_profile("kemiskinan terbaru Indonesia")
        assert p.needs_latest is True

    def test_needs_recent_range_for_trend(self):
        p = make_query_profile("tren kemiskinan beberapa tahun terakhir")
        assert p.needs_recent_range is True


# ---------------------------------------------------------------------------
# Requested trend years
# ---------------------------------------------------------------------------

class TestRequestedTrendYears:
    def test_digit(self):
        p = make_query_profile("kemiskinan 3 tahun terakhir")
        assert p.requested_trend_years == 3

    def test_word(self):
        p = make_query_profile("kemiskinan dua tahun terakhir")
        assert p.requested_trend_years == 2

    def test_none_if_not_present(self):
        p = make_query_profile("kemiskinan Indonesia 2023")
        assert p.requested_trend_years is None


# ---------------------------------------------------------------------------
# Indikator
# ---------------------------------------------------------------------------

class TestIndicatorExtraction:
    def test_primary_indicator_set(self):
        p = make_query_profile("benarkah kemiskinan turun di Indonesia?")
        assert p.primary_indicator == "persentase penduduk miskin"

    def test_quantity_hint_field_exists(self):
        # quantity_hint diisi registry — yang penting field-nya ada dan bertipe bool
        p = make_query_profile("berapa jumlah orang miskin di Indonesia?")
        assert isinstance(p.quantity_hint, bool)

    def test_no_indicator_for_unrelated(self):
        p = make_query_profile("cuaca di Jakarta hari ini")
        assert p.primary_indicator == ""


# ---------------------------------------------------------------------------
# Generated queries
# ---------------------------------------------------------------------------

class TestGeneratedQueries:
    def test_at_least_one_query(self):
        p = make_query_profile("kemiskinan Indonesia")
        assert len(p.generated_queries) >= 1

    def test_original_question_included(self):
        q = "Benarkah kemiskinan turun di Jawa Timur?"
        p = make_query_profile(q)
        assert q.strip() in p.generated_queries

    def test_trend_adds_extra_query(self):
        p = make_query_profile("tren kemiskinan 3 tahun terakhir")
        assert len(p.generated_queries) >= 2

    def test_no_duplicate_queries(self):
        p = make_query_profile("kemiskinan Indonesia terbaru")
        assert len(p.generated_queries) == len(set(p.generated_queries))


# ---------------------------------------------------------------------------
# is_vague_question
# ---------------------------------------------------------------------------

class TestIsVagueQuestion:
    def test_very_short_is_vague(self):
        p = make_query_profile("kemiskinan")
        assert is_vague_question("kemiskinan", p) is True

    def test_specific_question_not_vague(self):
        q = "Benarkah kemiskinan di Jawa Timur turun di bawah rata-rata nasional pada 2023?"
        p = make_query_profile(q)
        assert is_vague_question(q, p) is False

    def test_berapa_not_vague(self):
        q = "Berapa angka kemiskinan Indonesia 2023?"
        p = make_query_profile(q)
        assert is_vague_question(q, p) is False

    def test_has_area_not_vague(self):
        q = "kemiskinan jawa timur"
        p = make_query_profile(q)
        # ada area_targets → tidak vague meski pendek
        assert is_vague_question(q, p) is False

    def test_single_token_always_vague(self):
        p = make_query_profile("inflasi")
        assert is_vague_question("inflasi", p) is True


# ---------------------------------------------------------------------------
# Program/job cues
# ---------------------------------------------------------------------------

class TestProgramJobCues:
    def test_mbg_plus_kerja(self):
        q = "Apakah program makan bergizi gratis menciptakan lapangan kerja?"
        p = make_query_profile(q)
        # Harus inject indikator ketenagakerjaan
        assert any("pengangguran" in t or "bekerja" in t for t in p.indicator_targets)

    def test_no_cue_no_inject(self):
        q = "Benarkah kemiskinan turun di Aceh?"
        p = make_query_profile(q)
        assert not any("bekerja" in t for t in p.indicator_targets)


# ---------------------------------------------------------------------------
# Metadata filters
# ---------------------------------------------------------------------------

class TestMetadataFilters:
    def test_filters_populated(self):
        p = make_query_profile("kemiskinan jatim 2023")
        mf = p.metadata_filters
        assert "query_type" in mf
        assert "primary_indicator" in mf
        assert "area_targets" in mf

    def test_filters_match_profile(self):
        p = make_query_profile("tren kemiskinan jatim 5 tahun terakhir")
        mf = p.metadata_filters
        assert mf["query_type"] == p.query_type
        assert mf["requested_trend_years"] == p.requested_trend_years
