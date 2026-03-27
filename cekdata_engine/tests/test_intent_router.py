"""
tests/test_intent_router.py
============================
Unit test untuk intent_router.py.
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

from cekdata_engine.intent_router import (
    IntentResult, route_intent, enrich_query_profile_from_intent
)
from cekdata_engine.models import QueryProfile


# ---------------------------------------------------------------------------
# Helper: patch OpenAI
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
        self.chat = types.SimpleNamespace(
            completions=_FakeCompletion(payload)
        )


def _patch_client(payload: dict):
    """Patch shared OpenAI client agar intent_router menggunakan fake client."""
    import cekdata_engine.openai_client as client_mod
    client_mod._shared_client = _FakeClient(payload)
    return client_mod


def _restore_client():
    import cekdata_engine.openai_client as client_mod
    client_mod._shared_client = None


# ---------------------------------------------------------------------------
# IntentResult dataclass
# ---------------------------------------------------------------------------

class TestIntentResult:

    def test_default_status_ok(self):
        r = IntentResult(original_question="test")
        assert r.status == "ok"

    def test_to_dict_contains_all_required_fields(self):
        r = IntentResult(
            status="ok",
            original_question="q",
            reformulated_question="q reformulated",
            clarification_question="Wilayah mana?",
            rejection_message="",
        )
        d = r.to_dict()
        for field in [
            "status", "original_question", "reformulated_question",
            "indicators", "areas", "years", "query_type",
            "clarification_question", "rejection_message",
            "understood_topic", "confidence",
        ]:
            assert field in d, f"to_dict() missing field: {field}"

    def test_to_dict_clarification_question_included(self):
        r = IntentResult(clarification_question="Maksudnya provinsi mana?")
        d = r.to_dict()
        assert d["clarification_question"] == "Maksudnya provinsi mana?"

    def test_to_dict_rejection_message_included(self):
        r = IntentResult(rejection_message="Pertanyaan di luar cakupan.")
        d = r.to_dict()
        assert d["rejection_message"] == "Pertanyaan di luar cakupan."

    def test_confidence_default_one(self):
        r = IntentResult()
        assert r.confidence == 1.0


# ---------------------------------------------------------------------------
# route_intent — dengan mock
# ---------------------------------------------------------------------------

class TestRouteIntent:

    def teardown_method(self):
        _restore_client()

    def test_ok_status_returns_intent_result(self):
        _patch_client({
            "status": "ok",
            "reformulated_question": "Benarkah persentase penduduk miskin Indonesia turun?",
            "indicators": ["persentase penduduk miskin"],
            "areas": ["Indonesia"],
            "years": [2023],
            "periods": ["Maret"],
            "query_type": "claim",
            "requires_comparison": False,
            "comparison_entities": [],
            "requires_trend": False,
            "trend_years_requested": None,
            "understood_topic": "kemiskinan Indonesia",
            "confidence": 0.95,
            "clarification_question": "",
            "rejection_message": "",
        })
        result = route_intent("kemiskinan turun nggak?")
        assert result.status == "ok"
        assert "penduduk miskin" in result.reformulated_question
        assert "Indonesia" in result.areas
        assert 2023 in result.years
        assert result.confidence == 0.95

    def test_off_topic_returns_rejection(self):
        _patch_client({
            "status": "off_topic",
            "reformulated_question": "",
            "indicators": [],
            "areas": [],
            "years": [],
            "periods": [],
            "query_type": "claim",
            "requires_comparison": False,
            "comparison_entities": [],
            "requires_trend": False,
            "trend_years_requested": None,
            "understood_topic": "",
            "confidence": 0.99,
            "clarification_question": "",
            "rejection_message": "Pertanyaan tentang cuaca di luar cakupan CekData AI.",
        })
        result = route_intent("Cuaca Jakarta besok gimana?")
        assert result.status == "off_topic"
        assert "cuaca" in result.rejection_message.lower()

    def test_clarify_returns_question(self):
        _patch_client({
            "status": "clarify",
            "reformulated_question": "",
            "indicators": [],
            "areas": [],
            "years": [],
            "periods": [],
            "query_type": "claim",
            "requires_comparison": False,
            "comparison_entities": [],
            "requires_trend": False,
            "trend_years_requested": None,
            "understood_topic": "",
            "confidence": 0.5,
            "clarification_question": "Indikator apa yang ingin diperiksa?",
            "rejection_message": "",
        })
        result = route_intent("bagaimana kondisi Indonesia?")
        assert result.status == "clarify"
        assert result.clarification_question != ""

    def test_trend_query_parsed(self):
        _patch_client({
            "status": "ok",
            "reformulated_question": "Bagaimana tren kemiskinan Indonesia 5 tahun terakhir?",
            "indicators": ["persentase penduduk miskin"],
            "areas": ["Indonesia"],
            "years": [],
            "periods": [],
            "query_type": "trend",
            "requires_comparison": False,
            "comparison_entities": [],
            "requires_trend": True,
            "trend_years_requested": 5,
            "understood_topic": "tren kemiskinan",
            "confidence": 0.92,
            "clarification_question": "",
            "rejection_message": "",
        })
        result = route_intent("kemiskinan 5 tahun terakhir")
        assert result.query_type == "trend"
        assert result.requires_trend is True
        assert result.trend_years_requested == 5

    def test_comparison_query_parsed(self):
        _patch_client({
            "status": "ok",
            "reformulated_question": "Bandingkan kemiskinan Jawa Barat dan Jawa Timur 2023",
            "indicators": ["persentase penduduk miskin"],
            "areas": ["Jawa Barat", "Jawa Timur"],
            "years": [2023],
            "periods": [],
            "query_type": "comparison",
            "requires_comparison": True,
            "comparison_entities": ["Jawa Barat", "Jawa Timur"],
            "requires_trend": False,
            "trend_years_requested": None,
            "understood_topic": "perbandingan kemiskinan provinsi",
            "confidence": 0.97,
            "clarification_question": "",
            "rejection_message": "",
        })
        result = route_intent("jabar vs jatim kemiskinan 2023")
        assert result.query_type == "comparison"
        assert result.requires_comparison is True
        assert "Jawa Barat" in result.comparison_entities

    def test_invalid_status_normalized_to_ok(self):
        _patch_client({
            "status": "unknown_status",
            "reformulated_question": "q",
            "indicators": [],
            "areas": [],
            "years": [],
            "periods": [],
            "query_type": "claim",
            "requires_comparison": False,
            "comparison_entities": [],
            "requires_trend": False,
            "trend_years_requested": None,
            "understood_topic": "",
            "confidence": 1.0,
            "clarification_question": "",
            "rejection_message": "",
        })
        result = route_intent("pertanyaan apapun")
        assert result.status == "ok"

    def test_openai_error_returns_error_status(self):
        import cekdata_engine.intent_router as mod
        # Paksa error dengan client yang raise exception
        class _FailClient:
            chat = types.SimpleNamespace(
                completions=types.SimpleNamespace(
                    create=lambda **kwargs: (_ for _ in ()).throw(RuntimeError("Simulated API error"))
                )
            )
        mod._router_client = _FailClient()

        result = route_intent("pertanyaan apapun")
        assert result.status == "error"
        # Pipeline harus tetap bisa jalan — reformulated_question = pertanyaan asli
        assert result.reformulated_question != ""

    def test_empty_question_returns_clarify(self):
        result = route_intent("")
        assert result.status == "clarify"

    def test_whitespace_question_returns_clarify(self):
        result = route_intent("   ")
        assert result.status == "clarify"

    def test_years_parsed_as_int(self):
        _patch_client({
            "status": "ok",
            "reformulated_question": "q",
            "indicators": [],
            "areas": [],
            "years": ["2022", "2023"],  # string dari model
            "periods": [],
            "query_type": "claim",
            "requires_comparison": False,
            "comparison_entities": [],
            "requires_trend": False,
            "trend_years_requested": None,
            "understood_topic": "",
            "confidence": 1.0,
            "clarification_question": "",
            "rejection_message": "",
        })
        result = route_intent("kemiskinan 2022 dan 2023")
        assert all(isinstance(y, int) for y in result.years)


# ---------------------------------------------------------------------------
# enrich_query_profile_from_intent
# ---------------------------------------------------------------------------

class TestEnrichQueryProfile:

    def _make_empty_profile(self, question="test") -> QueryProfile:
        return QueryProfile(
            raw_question=question, normalized_question=question,
            query_type="claim", needs_latest=False, needs_recent_range=False,
            requested_trend_years=None, explicit_years=[], periods=[],
            indicator_targets=[], primary_indicator="",
            area_targets=[], comparison_targets=[], breakdown_targets=[],
            comparator_words=[], quantity_hint=False, ambiguous_indicator=False,
            generated_queries=[question], keyword_targets=[], metadata_filters={},
        )

    def test_fills_primary_indicator_if_empty(self):
        profile = self._make_empty_profile()
        intent = IntentResult(
            status="ok",
            indicators=["persentase penduduk miskin"],
            areas=[], years=[], periods=[],
        )
        enrich_query_profile_from_intent(profile, intent)
        assert profile.primary_indicator == "persentase penduduk miskin"

    def test_does_not_overwrite_existing_indicator(self):
        profile = self._make_empty_profile()
        profile.primary_indicator = "jumlah penduduk miskin"
        intent = IntentResult(
            status="ok",
            indicators=["persentase penduduk miskin"],
        )
        enrich_query_profile_from_intent(profile, intent)
        # primary_indicator yang sudah ada dipertahankan
        assert profile.primary_indicator == "jumlah penduduk miskin"

    def test_adds_new_areas(self):
        profile = self._make_empty_profile()
        intent = IntentResult(status="ok", areas=["Jawa Timur", "Indonesia"])
        enrich_query_profile_from_intent(profile, intent)
        assert "Jawa Timur" in profile.area_targets
        assert "Indonesia" in profile.area_targets

    def test_no_duplicate_areas(self):
        profile = self._make_empty_profile()
        profile.area_targets = ["Indonesia"]
        intent = IntentResult(status="ok", areas=["Indonesia", "Aceh"])
        enrich_query_profile_from_intent(profile, intent)
        assert profile.area_targets.count("Indonesia") == 1
        assert "Aceh" in profile.area_targets

    def test_adds_years(self):
        profile = self._make_empty_profile()
        intent = IntentResult(status="ok", years=[2022, 2023])
        enrich_query_profile_from_intent(profile, intent)
        assert 2022 in profile.explicit_years
        assert 2023 in profile.explicit_years

    def test_updates_query_type_from_claim_to_trend(self):
        profile = self._make_empty_profile()
        intent = IntentResult(status="ok", query_type="trend")
        enrich_query_profile_from_intent(profile, intent)
        assert profile.query_type == "trend"

    def test_does_not_override_non_default_query_type(self):
        profile = self._make_empty_profile()
        profile.query_type = "comparison"
        intent = IntentResult(status="ok", query_type="trend")
        enrich_query_profile_from_intent(profile, intent)
        # Jika query_parser sudah tentukan "comparison", intent tidak overwrite
        assert profile.query_type == "comparison"

    def test_sets_trend_years(self):
        profile = self._make_empty_profile()
        intent = IntentResult(status="ok", trend_years_requested=5)
        enrich_query_profile_from_intent(profile, intent)
        assert profile.requested_trend_years == 5

    def test_sets_comparison_targets(self):
        profile = self._make_empty_profile()
        intent = IntentResult(
            status="ok",
            requires_comparison=True,
            comparison_entities=["Jawa Barat", "Jawa Timur"],
        )
        enrich_query_profile_from_intent(profile, intent)
        assert "Jawa Barat" in profile.comparison_targets

    def test_reformulated_question_prepended_to_generated_queries(self):
        profile = self._make_empty_profile("pertanyaan asli")
        intent = IntentResult(
            status="ok",
            reformulated_question="Pertanyaan yang sudah direformulasi",
        )
        enrich_query_profile_from_intent(profile, intent)
        assert profile.generated_queries[0] == "Pertanyaan yang sudah direformulasi"

    def test_off_topic_status_does_nothing(self):
        profile = self._make_empty_profile()
        original_areas = list(profile.area_targets)
        intent = IntentResult(status="off_topic", areas=["Jakarta"])
        enrich_query_profile_from_intent(profile, intent)
        assert profile.area_targets == original_areas

    def test_error_status_does_nothing(self):
        profile = self._make_empty_profile()
        intent = IntentResult(status="error", areas=["Jakarta"])
        enrich_query_profile_from_intent(profile, intent)
        assert "Jakarta" not in profile.area_targets
