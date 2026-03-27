"""
tests/test_inference_reasoner.py
=================================
Unit test untuk inference_reasoner.py.
Semua test menggunakan mock OpenAI — tidak ada panggilan API nyata.
"""
import sys, os, types, json
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

from cekdata_engine.inference_reasoner import (
    ReasoningResult, reason_alternative_queries
)
from cekdata_engine.data_gap_detector import GapAssessment
from cekdata_engine.models import QueryProfile


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _FakeMessage:
    def __init__(self, content): self.content = content

class _FakeChoice:
    def __init__(self, content): self.message = _FakeMessage(content)

class _FakeResponse:
    def __init__(self, content): self.choices = [_FakeChoice(content)]

class _FakeCompletion:
    def __init__(self, payload):
        self._payload = payload
    def create(self, **kwargs):
        return _FakeResponse(json.dumps(self._payload))

class _FakeClient:
    def __init__(self, payload):
        self.chat = types.SimpleNamespace(completions=_FakeCompletion(payload))


def _patch_reasoner(payload: dict):
    import cekdata_engine.openai_client as client_mod
    client_mod._shared_client = _FakeClient(payload)

def _restore_reasoner():
    import cekdata_engine.openai_client as client_mod
    client_mod._shared_client = None


def make_gap(has_gap=True, reason="Data tidak tersedia.",
             top_indicator="", requested="persentase penduduk miskin") -> GapAssessment:
    return GapAssessment(
        has_gap=has_gap, reason=reason,
        best_score=5.0, top_candidate_indicator=top_indicator,
        requested_indicator=requested,
    )


def make_profile(primary_indicator="persentase penduduk miskin",
                 area_targets=None, years=None) -> QueryProfile:
    return QueryProfile(
        raw_question="test", normalized_question="test",
        query_type="claim", needs_latest=False, needs_recent_range=False,
        requested_trend_years=None,
        explicit_years=years or [],
        periods=[], indicator_targets=[primary_indicator],
        primary_indicator=primary_indicator,
        area_targets=area_targets or ["Indonesia"],
        comparison_targets=[], breakdown_targets=[], comparator_words=[],
        quantity_hint=False, ambiguous_indicator=False,
        generated_queries=["test"], keyword_targets=[], metadata_filters={},
    )


# ---------------------------------------------------------------------------
# ReasoningResult dataclass
# ---------------------------------------------------------------------------

class TestReasoningResult:

    def test_default_not_found(self):
        r = ReasoningResult(found_proxy=False)
        assert r.found_proxy is False
        assert r.alternative_queries == []

    def test_found_with_queries(self):
        r = ReasoningResult(
            found_proxy=True,
            alternative_queries=["jumlah penduduk bekerja Indonesia 2023"],
            proxy_rationale="Proxy untuk klaim lapangan kerja",
        )
        assert r.found_proxy is True
        assert len(r.alternative_queries) == 1


# ---------------------------------------------------------------------------
# reason_alternative_queries — dengan mock
# ---------------------------------------------------------------------------

class TestReasonAlternativeQueries:

    def teardown_method(self):
        _restore_reasoner()

    def test_found_proxy_returns_queries(self):
        _patch_reasoner({
            "found_proxy": True,
            "alternative_queries": [
                "jumlah penduduk bekerja Indonesia 2024",
                "tingkat pengangguran terbuka Indonesia 2024",
            ],
            "proxy_rationale": "Klaim lapangan kerja bisa diuji dengan data ketenagakerjaan",
        })
        result = reason_alternative_queries(
            "Apakah MBG tambah 1 juta lapangan kerja?",
            make_profile("tingkat pengangguran terbuka"),
            make_gap(),
        )
        assert result.found_proxy is True
        assert len(result.alternative_queries) == 2
        assert "lapangan kerja" in result.proxy_rationale.lower() or result.proxy_rationale != ""

    def test_no_proxy_returns_not_found(self):
        _patch_reasoner({
            "found_proxy": False,
            "alternative_queries": [],
            "proxy_rationale": "Tidak ada data yang bisa mendekati pertanyaan ini.",
        })
        result = reason_alternative_queries(
            "Berapa banyak alien di Mars?",
            make_profile(),
            make_gap(),
        )
        assert result.found_proxy is False
        assert result.alternative_queries == []

    def test_max_three_queries_enforced(self):
        _patch_reasoner({
            "found_proxy": True,
            "alternative_queries": [
                "query 1", "query 2", "query 3", "query 4", "query 5",
            ],
            "proxy_rationale": "Banyak proxy tersedia",
        })
        result = reason_alternative_queries("q", make_profile(), make_gap())
        assert len(result.alternative_queries) <= 3

    def test_empty_queries_treated_as_not_found(self):
        # Model bilang found_proxy=True tapi queries kosong
        _patch_reasoner({
            "found_proxy": True,
            "alternative_queries": [],
            "proxy_rationale": "",
        })
        result = reason_alternative_queries("q", make_profile(), make_gap())
        assert result.found_proxy is False  # dikoreksi karena queries kosong

    def test_api_error_returns_not_found_gracefully(self):
        import cekdata_engine.openai_client as client_mod

        class _FailClient:
            chat = types.SimpleNamespace(
                completions=types.SimpleNamespace(
                    create=lambda **kwargs: (_ for _ in ()).throw(RuntimeError("API down"))
                )
            )
        client_mod._shared_client = _FailClient()

        result = reason_alternative_queries("q", make_profile(), make_gap())
        assert result.found_proxy is False
        assert "gagal" in result.proxy_rationale.lower()

    def test_invalid_json_returns_not_found(self):
        import cekdata_engine.openai_client as client_mod

        class _BadClient:
            class _BadCompletion:
                def create(self, **kwargs):
                    class _R:
                        choices = [type('C', (), {'message': type('M', (), {'content': 'bukan json sama sekali'})()})()]
                    return _R()
            chat = types.SimpleNamespace(completions=_BadCompletion())

        client_mod._shared_client = _BadClient()
        result = reason_alternative_queries("q", make_profile(), make_gap())
        assert result.found_proxy is False

    def test_queries_stripped_of_whitespace(self):
        _patch_reasoner({
            "found_proxy": True,
            "alternative_queries": ["  jumlah penduduk bekerja  ", " tpt indonesia "],
            "proxy_rationale": "proxy",
        })
        result = reason_alternative_queries("q", make_profile(), make_gap())
        for q in result.alternative_queries:
            assert q == q.strip()

    def test_empty_alternative_queries_filtered(self):
        _patch_reasoner({
            "found_proxy": True,
            "alternative_queries": ["query valid", "", "  "],
            "proxy_rationale": "proxy",
        })
        result = reason_alternative_queries("q", make_profile(), make_gap())
        assert all(q for q in result.alternative_queries)

    def test_proxy_rationale_preserved(self):
        rationale = "Data ketenagakerjaan BPS bisa jadi proxy untuk klaim program kerja."
        _patch_reasoner({
            "found_proxy": True,
            "alternative_queries": ["jumlah penduduk bekerja Indonesia 2023"],
            "proxy_rationale": rationale,
        })
        result = reason_alternative_queries("q", make_profile(), make_gap())
        assert result.proxy_rationale == rationale

    def test_gap_info_used_in_prompt(self):
        """Pastikan fungsi tidak crash dengan berbagai kombinasi gap info."""
        _patch_reasoner({
            "found_proxy": False,
            "alternative_queries": [],
            "proxy_rationale": "tidak ada proxy",
        })
        gaps = [
            make_gap(top_indicator="garis kemiskinan", requested="persentase penduduk miskin"),
            make_gap(top_indicator="", requested=""),
            GapAssessment(has_gap=True, reason="Skor rendah"),
        ]
        for gap in gaps:
            result = reason_alternative_queries("q", make_profile(), gap)
            assert isinstance(result, ReasoningResult)
