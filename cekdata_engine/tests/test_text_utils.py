"""
tests/test_text_utils.py
========================
Unit test untuk fungsi-fungsi di text_utils.py.
Semua test bisa dijalankan tanpa koneksi eksternal atau corpus nyata.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Stub external dependencies sebelum import engine modules
import types

indicator_registry = types.ModuleType("indicator_registry")
indicator_registry.INDICATOR_CANONICAL = {}
indicator_registry.canonical_indicator_candidates = lambda q: ([], "", False, False)
indicator_registry.normalize_indicator_label = lambda label, fn: fn(label)
sys.modules["indicator_registry"] = indicator_registry

breakdown_registry = types.ModuleType("breakdown_registry")
breakdown_registry.extract_breakdown_context = lambda q: {}
sys.modules["breakdown_registry"] = breakdown_registry

from cekdata_engine.text_utils import (
    normalize_text,
    tokenize,
    extract_years,
    extract_periods,
    extract_requested_trend_years,
    latest_sort_key,
    format_id_number,
    humanize_unit_value,
    enrich_readable_numbers,
    normalize_editorial_labels,
    build_record_text,
    normalize_record,
    choose_best_download,
    summarize_sources,
)


# ---------------------------------------------------------------------------
# normalize_text
# ---------------------------------------------------------------------------

class TestNormalizeText:
    def test_lowercase(self):
        assert normalize_text("JAKARTA") == "jakarta"

    def test_strip_whitespace(self):
        assert normalize_text("  kemiskinan  ") == "kemiskinan"

    def test_slash_to_space(self):
        assert normalize_text("2023/2024") == "2023 2024"

    def test_dash_to_space(self):
        assert normalize_text("Jawa-Timur") == "jawa timur"

    def test_collapse_spaces(self):
        assert normalize_text("a   b   c") == "a b c"

    def test_none_returns_empty(self):
        assert normalize_text(None) == ""

    def test_number_passthrough(self):
        assert normalize_text(42) == "42"

    def test_percent_kept(self):
        assert "%" in normalize_text("10%")


# ---------------------------------------------------------------------------
# tokenize
# ---------------------------------------------------------------------------

class TestTokenize:
    def test_removes_stopwords(self):
        tokens = tokenize("kemiskinan di indonesia")
        assert "di" not in tokens
        assert "kemiskinan" in tokens

    def test_removes_short_tokens(self):
        tokens = tokenize("a b kemiskinan")
        assert "a" not in tokens
        assert "b" not in tokens

    def test_returns_list(self):
        assert isinstance(tokenize("kemiskinan"), list)

    def test_empty_string(self):
        assert tokenize("") == []


# ---------------------------------------------------------------------------
# extract_years
# ---------------------------------------------------------------------------

class TestExtractYears:
    def test_single_year(self):
        assert extract_years("data tahun 2023") == [2023]

    def test_multiple_years(self):
        result = extract_years("dari 2020 sampai 2023")
        assert 2020 in result
        assert 2023 in result

    def test_no_year(self):
        assert extract_years("kemiskinan menurun") == []

    def test_ignore_short_numbers(self):
        assert extract_years("nilai 99 persen") == []

    def test_year_boundary(self):
        assert extract_years("tahun 1900") == [1900]
        assert extract_years("tahun 2099") == [2099]
        assert extract_years("tahun 2100") == []


# ---------------------------------------------------------------------------
# extract_periods
# ---------------------------------------------------------------------------

class TestExtractPeriods:
    def test_maret(self):
        assert "Maret" in extract_periods("kemiskinan Maret 2023")

    def test_september(self):
        assert "September" in extract_periods("data September")

    def test_triwulan(self):
        assert "Triwulan II" in extract_periods("Triwulan II 2022")

    def test_semester(self):
        assert "Semester I" in extract_periods("Semester I 2021")

    def test_no_period(self):
        assert extract_periods("kemiskinan turun") == []

    def test_case_insensitive(self):
        # normalize_text sudah lowercase sebelum compare
        assert "Maret" in extract_periods("maret 2023")


# ---------------------------------------------------------------------------
# extract_requested_trend_years
# ---------------------------------------------------------------------------

class TestExtractRequestedTrendYears:
    def test_digit(self):
        assert extract_requested_trend_years("5 tahun terakhir") == 5

    def test_word(self):
        assert extract_requested_trend_years("tiga tahun terakhir") == 3

    def test_selama(self):
        assert extract_requested_trend_years("selama 4 tahun terakhir") == 4

    def test_no_match(self):
        assert extract_requested_trend_years("kemiskinan menurun") is None

    def test_all_words(self):
        words = {
            "satu": 1, "dua": 2, "lima": 5, "sepuluh": 10,
        }
        for word, num in words.items():
            assert extract_requested_trend_years(f"{word} tahun terakhir") == num


# ---------------------------------------------------------------------------
# latest_sort_key
# ---------------------------------------------------------------------------

class TestLatestSortKey:
    def test_basic(self):
        record = {"year": 2023, "period": "Maret"}
        year, period_rank = latest_sort_key(record)
        assert year == 2023
        assert period_rank == 3  # Maret = 3

    def test_fallback_to_year_end(self):
        record = {"year_end": 2022}
        year, _ = latest_sort_key(record)
        assert year == 2022

    def test_fallback_to_year_start(self):
        record = {"year_start": 2021}
        year, _ = latest_sort_key(record)
        assert year == 2021

    def test_missing_year(self):
        year, period = latest_sort_key({})
        assert year == 0
        assert period == 0

    def test_unknown_period(self):
        record = {"year": 2023, "period": "PeriodeTidakDikenal"}
        _, rank = latest_sort_key(record)
        assert rank == 0

    def test_sorting_works(self):
        r1 = {"year": 2022, "period": "Maret"}
        r2 = {"year": 2022, "period": "September"}
        r3 = {"year": 2023, "period": "Maret"}
        keys = [latest_sort_key(r) for r in [r1, r2, r3]]
        assert sorted(keys) == keys  # sudah ascending


# ---------------------------------------------------------------------------
# format_id_number
# ---------------------------------------------------------------------------

class TestFormatIdNumber:
    def test_basic(self):
        assert format_id_number(1234567.89) == "1.234.567,89"

    def test_zero_decimals(self):
        assert format_id_number(1000.0, 0) == "1.000"

    def test_small_number(self):
        assert format_id_number(9.5) == "9,50"


# ---------------------------------------------------------------------------
# humanize_unit_value
# ---------------------------------------------------------------------------

class TestHumanizeUnitValue:
    def test_ribu_orang_to_juta(self):
        result = humanize_unit_value(25000, "ribu orang")
        assert "juta" in result
        assert "25" in result

    def test_orang_jutaan(self):
        result = humanize_unit_value(2_500_000, "orang")
        assert "juta" in result

    def test_orang_ribuan(self):
        result = humanize_unit_value(500_000, "orang")
        assert "ribu" in result

    def test_rupiah_triliun(self):
        result = humanize_unit_value(5_000_000_000_000, "rupiah")
        assert "triliun" in result

    def test_rupiah_miliar(self):
        result = humanize_unit_value(3_000_000_000, "rupiah")
        assert "miliar" in result

    def test_rupiah_juta(self):
        result = humanize_unit_value(2_000_000, "rupiah")
        assert "juta" in result

    def test_unknown_unit_returns_empty(self):
        assert humanize_unit_value(100, "unit_tidak_dikenal") == ""

    def test_invalid_value(self):
        assert humanize_unit_value("bukan angka", "orang") == ""

    def test_hektare(self):
        result = humanize_unit_value(2_000_000, "hektare")
        assert "juta hektare" in result


# ---------------------------------------------------------------------------
# enrich_readable_numbers
# ---------------------------------------------------------------------------

class TestEnrichReadableNumbers:
    def test_enrich_single_record(self):
        text = "kemiskinan mencapai 25000.0 ribu orang di Jawa Timur"
        records = [{"value": 25000.0, "unit": "ribu orang"}]
        result = enrich_readable_numbers(text, records)
        assert "juta" in result

    def test_no_match_no_change(self):
        text = "kemiskinan menurun signifikan"
        records = [{"value": 5.0, "unit": "%"}]
        result = enrich_readable_numbers(text, records)
        assert result == text

    def test_none_value_skipped(self):
        text = "teks biasa"
        records = [{"value": None, "unit": "orang"}]
        assert enrich_readable_numbers(text, records) == text

    def test_empty_unit_skipped(self):
        text = "teks biasa"
        records = [{"value": 1000, "unit": ""}]
        assert enrich_readable_numbers(text, records) == text


# ---------------------------------------------------------------------------
# normalize_editorial_labels
# ---------------------------------------------------------------------------

class TestNormalizeEditorialLabels:
    def test_p0_removed(self):
        text = "Persentase Penduduk Miskin (P0) menurun"
        result = normalize_editorial_labels(text)
        assert "(P0)" not in result
        assert "Persentase Penduduk Miskin" in result

    def test_lowercase_p0_removed(self):
        text = "persentase penduduk miskin (p0)"
        result = normalize_editorial_labels(text)
        assert "(p0)" not in result

    def test_no_change_if_clean(self):
        text = "Persentase Penduduk Miskin menurun"
        assert normalize_editorial_labels(text) == text


# ---------------------------------------------------------------------------
# build_record_text
# ---------------------------------------------------------------------------

class TestBuildRecordText:
    def test_includes_key_fields(self):
        record = {
            "title": "Kemiskinan Jawa Timur",
            "area_name": "Jawa Timur",
            "series_label": "Persentase Penduduk Miskin",
            "year": 2023,
        }
        text = build_record_text(record)
        assert "Jawa Timur" in text
        assert "2023" in text
        assert "Persentase Penduduk Miskin" in text

    def test_empty_record(self):
        assert isinstance(build_record_text({}), str)

    def test_list_fields_included(self):
        record = {"keywords": ["kemiskinan", "BPS"]}
        text = build_record_text(record)
        assert "kemiskinan" in text
        assert "BPS" in text

    def test_metadata_dict_included(self):
        record = {"metadata": {"catatan": "data revisi"}}
        text = build_record_text(record)
        assert "data revisi" in text


# ---------------------------------------------------------------------------
# normalize_record
# ---------------------------------------------------------------------------

class TestNormalizeRecord:
    def test_sets_defaults(self):
        record = normalize_record({}, 1)
        assert record["id"] == "row_1"
        assert record["doc_type"] == "atomic"
        assert isinstance(record["keywords"], list)
        assert isinstance(record["metadata"], dict)

    def test_existing_values_preserved(self):
        record = normalize_record({"area_name": "Bali", "year": 2022}, 5)
        assert record["area_name"] == "Bali"
        assert record["year"] == 2022

    def test_id_not_overwritten_if_exists(self):
        record = normalize_record({"id": "custom_id"}, 99)
        assert record["id"] == "custom_id"


# ---------------------------------------------------------------------------
# choose_best_download
# ---------------------------------------------------------------------------

class TestChooseBestDownload:
    def test_prefers_download_url(self):
        record = {"download_url": "https://a.com", "download_urls": ["https://b.com"]}
        assert choose_best_download(record) == "https://a.com"

    def test_falls_back_to_last_url(self):
        record = {"download_urls": ["https://a.com", "https://b.com"]}
        assert choose_best_download(record) == "https://b.com"

    def test_empty_returns_empty(self):
        assert choose_best_download({}) == ""


# ---------------------------------------------------------------------------
# summarize_sources
# ---------------------------------------------------------------------------

class TestSummarizeSources:
    def test_collects_unique_titles(self):
        records = [
            {"title": "Statistik BPS 2023", "download_url": ""},
            {"title": "Statistik BPS 2023", "download_url": ""},  # duplikat
            {"title": "Data Kemiskinan", "download_url": ""},
        ]
        titles, _ = summarize_sources(records)
        assert titles.count("Statistik BPS 2023") == 1
        assert "Data Kemiskinan" in titles

    def test_collects_unique_downloads(self):
        records = [
            {"title": "", "download_url": "https://a.com"},
            {"title": "", "download_url": "https://a.com"},  # duplikat
            {"title": "", "download_url": "https://b.com"},
        ]
        _, downloads = summarize_sources(records)
        assert downloads.count("https://a.com") == 1
        assert "https://b.com" in downloads

    def test_empty_records(self):
        titles, downloads = summarize_sources([])
        assert titles == ""
        assert downloads == []
