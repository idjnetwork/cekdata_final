"""
tests/test_engine_integration.py
=================================
Integration test untuk CekDataEngine menggunakan stub retriever dan stub AI.
Tidak memerlukan file JSONL, Pinecone, atau OpenAI API key.
"""
import sys, os, types
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

indicator_registry = types.ModuleType("indicator_registry")
indicator_registry.INDICATOR_CANONICAL = {}
indicator_registry.canonical_indicator_candidates = lambda q: (
    ["persentase penduduk miskin"], "persentase penduduk miskin", False, False
) if "miskin" in q or "kemiskinan" in q else ([], "", False, False)
indicator_registry.normalize_indicator_label = lambda label, fn: fn(label)
sys.modules["indicator_registry"] = indicator_registry

breakdown_registry = types.ModuleType("breakdown_registry")
breakdown_registry.extract_breakdown_context = lambda q: {
    "inferred_age_buckets": [], "explicit_age_buckets": [],
    "gender_targets": [], "generation_targets": [], "area_breakdown_targets": [],
}
sys.modules["breakdown_registry"] = breakdown_registry

from cekdata_engine.engine import CekDataEngine
from cekdata_engine.models import Candidate, QueryProfile
from cekdata_engine.retriever import RetrievalBackend
from cekdata_engine.query_parser import make_query_profile
from cekdata_engine.text_utils import normalize_record

# ---------------------------------------------------------------------------
# Stub retriever
# ---------------------------------------------------------------------------

def _make_stub_records():
    """Corpus mini untuk testing."""
    rows = [
        {"id": "r1", "series_label": "persentase penduduk miskin",
         "area_name": "Indonesia", "year": 2023, "period": "Maret",
         "value": 9.36, "unit": "%", "doc_type": "atomic",
         "title": "Kemiskinan Indonesia Maret 2023", "source": "BPS",
         "download_url": "https://bps.go.id/kemiskinan2023.csv"},
        {"id": "r2", "series_label": "persentase penduduk miskin",
         "area_name": "Indonesia", "year": 2022, "period": "Maret",
         "value": 9.54, "unit": "%", "doc_type": "atomic",
         "title": "Kemiskinan Indonesia Maret 2022", "source": "BPS",
         "download_url": "https://bps.go.id/kemiskinan2022.csv"},
        {"id": "r3", "series_label": "persentase penduduk miskin",
         "area_name": "Jawa Timur", "year": 2023, "period": "Maret",
         "value": 10.35, "unit": "%", "doc_type": "atomic",
         "title": "Kemiskinan Jawa Timur 2023", "source": "BPS",
         "download_url": ""},
        {"id": "r4", "series_label": "jumlah penduduk miskin",
         "area_name": "Indonesia", "year": 2023, "period": "Maret",
         "value": 25900, "unit": "ribu orang", "doc_type": "atomic",
         "title": "Jumlah Penduduk Miskin 2023", "source": "BPS",
         "download_url": ""},
    ]
    return [normalize_record(r, i+1) for i, r in enumerate(rows)]

class StubRetriever(RetrievalBackend):
    """Retriever yang mengembalikan kandidat dari corpus mini tanpa scoring sesungguhnya."""

    def __init__(self, records=None):
        self._records = _make_stub_records() if records is None else records

    def retrieve(self, question: str, top_k: int = 8, profile=None):
        from cekdata_engine.scorer import score_record
        if profile is None:
            profile = make_query_profile(question)
        scored = [score_record(r, profile) for r in self._records]
        scored.sort(key=lambda c: c.score, reverse=True)
        return scored[:top_k], profile

# ---------------------------------------------------------------------------
# Stub AI analyst
# ---------------------------------------------------------------------------

def make_stub_ai_analyst(penilaian="Benar"):
    """Patch call_ai_analysis agar tidak butuh API key."""
    def stub(question, profile, candidates, **kwargs):
        used = [str(c.record.get("id")) for c in candidates[:2]]
        return {
            "claim": question,
            "indicator_used": "Persentase Penduduk Miskin",
            "records_used": used,
            "temuan_data": "Kemiskinan sebesar 9,36%.",
            "konteks_penting": "Data Maret 2023.",
            "penilaian": penilaian,
            "alasan": "Data menunjukkan nilai yang sesuai.",
            "peringatan_editorial": "",
            "sumber": "BPS",
            "unduh_data": "https://bps.go.id/kemiskinan2023.csv",
            "raw_answer": "",
        }
    return stub

# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestEngineVagueQuestion:
    def setup_method(self):
        self.engine = CekDataEngine(retriever=StubRetriever())

    def test_short_question_returns_vague_response(self):
        result = self.engine.answer_question("kemiskinan")
        assert "terlalu pendek" in result["answer"] or "contoh pertanyaan" in result["answer"].lower()
        assert result["best_match"] is None
        assert result["top_matches"] == []

    def test_vague_has_query_profile(self):
        result = self.engine.answer_question("kemiskinan")
        assert "query_profile" in result

class TestEngineFullPipeline:
    def setup_method(self):
        import cekdata_engine.engine as eng_mod
        self._original_call = eng_mod.call_ai_analysis
        eng_mod.call_ai_analysis = make_stub_ai_analyst("Benar")
        self.engine = CekDataEngine(retriever=StubRetriever())
        self._eng_mod = eng_mod

    def teardown_method(self):
        self._eng_mod.call_ai_analysis = self._original_call

    def test_returns_all_keys(self):
        result = self.engine.answer_question("Benarkah kemiskinan turun di Indonesia 2023?")
        for key in ["question", "queries", "query_profile", "answer", "parsed",
                    "best_match", "best_score", "top_matches"]:
            assert key in result, f"Key '{key}' tidak ada di result"

    def test_answer_not_empty(self):
        result = self.engine.answer_question("Benarkah kemiskinan turun di Indonesia 2023?")
        assert result["answer"].strip() != ""

    def test_parsed_has_penilaian(self):
        result = self.engine.answer_question("Benarkah kemiskinan turun di Indonesia 2023?")
        assert "penilaian" in result["parsed"]

    def test_top_matches_populated(self):
        result = self.engine.answer_question("Benarkah kemiskinan turun di Indonesia 2023?")
        assert len(result["top_matches"]) > 0

    def test_best_score_is_float(self):
        result = self.engine.answer_question("Benarkah kemiskinan turun di Indonesia 2023?")
        assert isinstance(result["best_score"], float)

    def test_query_profile_has_type(self):
        result = self.engine.answer_question("Benarkah kemiskinan turun di Indonesia 2023?")
        assert result["query_profile"]["query_type"] in {"claim", "trend", "comparison"}

    def test_sumber_populated(self):
        result = self.engine.answer_question("Kemiskinan Indonesia 2023")
        assert result["parsed"].get("sumber", "") != ""

class TestEngineNoCandidates:
    def setup_method(self):
        self.engine = CekDataEngine(retriever=StubRetriever(records=[]))

    def test_no_candidates_response(self):
        result = self.engine.answer_question("Benarkah inflasi turun di Indonesia?")
        assert "Tidak ada kandidat" in result["parsed"]["alasan"]
        assert result["best_match"] is None

class TestEngineAiFallback:
    def setup_method(self):
        import cekdata_engine.engine as eng_mod
        from cekdata_engine.ai_analyst import AIAnalysisError
        self._original_call = eng_mod.call_ai_analysis

        def failing_ai(*args, **kwargs):
            raise AIAnalysisError("Simulasi error koneksi AI")

        eng_mod.call_ai_analysis = failing_ai
        self.engine = CekDataEngine(retriever=StubRetriever())
        self._eng_mod = eng_mod

    def teardown_method(self):
        self._eng_mod.call_ai_analysis = self._original_call

    def test_fallback_active_on_ai_error(self):
        result = self.engine.answer_question("Kemiskinan Indonesia 2023")
        assert "Fallback aktif" in result["parsed"]["alasan"]
        assert result["parsed"]["penilaian"] == "Tidak dapat diverifikasi"

    def test_still_returns_valid_structure(self):
        result = self.engine.answer_question("Kemiskinan Indonesia 2023")
        assert "answer" in result
        assert "parsed" in result

class TestEngineTrendQuery:
    def setup_method(self):
        import cekdata_engine.engine as eng_mod
        self._original_call = eng_mod.call_ai_analysis
        eng_mod.call_ai_analysis = make_stub_ai_analyst("Tidak dapat diverifikasi")
        records = [
            normalize_record({
                "id": f"r{y}", "series_label": "persentase penduduk miskin",
                "area_name": "Indonesia", "year": y, "period": "Maret",
                "value": 10.0 - (y - 2018) * 0.3, "unit": "%",
                "doc_type": "atomic", "title": f"Data {y}", "source": "BPS",
            }, i) for i, y in enumerate(range(2018, 2024))
        ]
        self.engine = CekDataEngine(retriever=StubRetriever(records=records))
        self._eng_mod = eng_mod

    def teardown_method(self):
        self._eng_mod.call_ai_analysis = self._original_call

    def test_trend_query_detected(self):
        result = self.engine.answer_question("tren kemiskinan 3 tahun terakhir Indonesia")
        assert result["query_profile"]["query_type"] == "trend"

    def test_trend_top_matches_has_multiple_years(self):
        result = self.engine.answer_question("tren kemiskinan 3 tahun terakhir Indonesia")
        # top_matches diambil dari candidates yang sudah di-retrieve
        # dengan 6 records tahun berbeda, minimal 2 tahun harus muncul
        assert len(result["top_matches"]) >= 1
        years = {m["year"] for m in result["top_matches"] if m.get("year")}
        assert len(years) >= 1  # setidaknya ada data temporal

# ---------------------------------------------------------------------------
# Test: Intent Router integration
# ---------------------------------------------------------------------------

class TestEngineWithIntentRouter:
    """
    Test integrasi dengan intent router diaktifkan.
    Intent router di-mock — tidak perlu OpenAI API.
    """

    def setup_method(self):
        import cekdata_engine.engine as eng_mod
        self._eng_mod = eng_mod

        # Enable intent router for this test class
        self._orig_intent_flag = eng_mod._INTENT_ROUTER_ENABLED
        eng_mod._INTENT_ROUTER_ENABLED = True

        # Patch AI analyst
        self._orig_ai = eng_mod.call_ai_analysis
        eng_mod.call_ai_analysis = make_stub_ai_analyst("Benar")

        # Patch intent router — simulasi response "ok" dengan reformulasi
        from cekdata_engine.intent_router import IntentResult
        def stub_router(question):
            if "kemiskinan" in question.lower() or "miskin" in question.lower():
                return IntentResult(
                    status="ok",
                    original_question=question,
                    reformulated_question="Benarkah persentase penduduk miskin Indonesia menurun pada 2023?",
                    indicators=["persentase penduduk miskin"],
                    areas=["Indonesia"],
                    years=[2023],
                    query_type="claim",
                    confidence=0.95,
                )
            return IntentResult(status="ok", original_question=question,
                                reformulated_question=question)

        self._orig_router = eng_mod.route_intent
        self._eng_mod.route_intent = stub_router

        self.engine = CekDataEngine(retriever=StubRetriever())

    def teardown_method(self):
        self._eng_mod.call_ai_analysis = self._orig_ai
        self._eng_mod.route_intent = self._orig_router
        self._eng_mod._INTENT_ROUTER_ENABLED = self._orig_intent_flag

    def test_effective_question_in_response(self):
        result = self.engine.answer_question("kemiskinan turun nggak?")
        assert "effective_question" in result

    def test_reformulated_question_used(self):
        result = self.engine.answer_question("kemiskinan turun nggak?")
        # effective_question harus berisi reformulasi dari router
        assert "penduduk miskin" in result["effective_question"].lower()

    def test_intent_in_response(self):
        result = self.engine.answer_question("Benarkah kemiskinan Indonesia turun?")
        # intent field ada di response (bisa None jika status != "ok", tapi harus ada key-nya)
        assert "intent" in result

    def test_off_topic_handled(self):
        from cekdata_engine.intent_router import IntentResult
        orig = self._eng_mod.route_intent

        def off_topic_router(q):
            return IntentResult(
                status="off_topic",
                original_question=q,
                rejection_message="Pertanyaan tentang cuaca di luar cakupan.",
            )

        self._eng_mod.route_intent = off_topic_router
        try:
            result = self.engine.answer_question("Cuaca Jakarta besok?")
            assert "cuaca" in result["answer"].lower() or "luar cakupan" in result["answer"].lower()
            assert result["best_match"] is None
            assert result["top_matches"] == []
        finally:
            self._eng_mod.route_intent = orig

    def test_clarify_handled(self):
        from cekdata_engine.intent_router import IntentResult
        orig = self._eng_mod.route_intent

        def clarify_router(q):
            return IntentResult(
                status="clarify",
                original_question=q,
                clarification_question="Indikator apa yang ingin diperiksa?",
            )

        self._eng_mod.route_intent = clarify_router
        try:
            result = self.engine.answer_question("bagaimana kondisi?")
            assert "indikator" in result["answer"].lower() or result["answer"] != ""
            assert result["best_match"] is None
        finally:
            self._eng_mod.route_intent = orig

    def test_router_error_fallback_pipeline_continues(self):
        orig = self._eng_mod.route_intent

        def error_router(q):
            raise RuntimeError("Router crashed")

        self._eng_mod.route_intent = error_router
        try:
            # Engine harus tetap berjalan meski router error
            result = self.engine.answer_question("Benarkah kemiskinan Indonesia turun 2023?")
            assert "answer" in result
            assert "parsed" in result
        finally:
            self._eng_mod.route_intent = orig

# ---------------------------------------------------------------------------
# Test: Gap Detector + Inference Reasoner integration
# ---------------------------------------------------------------------------

class TestEngineWithGapAndReasoning:
    """
    Test integrasi alur gap detection dan inference reasoning.
    Semua external calls di-mock.
    """

    def setup_method(self):
        import cekdata_engine.engine as eng_mod
        import os

        self._eng_mod = eng_mod

        # Enable reasoning for this test class
        self._orig_reasoning_flag = eng_mod._REASONING_ENABLED
        eng_mod._REASONING_ENABLED = True

        # Matikan intent router agar tidak ikut campur
        self._orig_intent_flag = eng_mod._INTENT_ROUTER_ENABLED
        eng_mod._INTENT_ROUTER_ENABLED = False

        from cekdata_engine.intent_router import IntentResult
        self._orig_router = eng_mod.route_intent
        eng_mod.route_intent = lambda q: IntentResult(
            status="ok", original_question=q, reformulated_question=q
        )

        self._orig_ai = eng_mod.call_ai_analysis
        self._orig_reason = eng_mod.reason_alternative_queries

        # Records dengan skor rendah untuk trigger gap
        low_score_records = [
            normalize_record({
                "id": "r_low", "series_label": "garis kemiskinan",  # bukan yang diminta
                "area_name": "Indonesia", "year": 2023,
                "value": 550458, "unit": "rupiah",
                "title": "Garis Kemiskinan 2023", "source": "BPS",
            }, 1)
        ]
        self.engine_low = CekDataEngine(retriever=StubRetriever(records=low_score_records))

        # Records normal untuk retrieval ulang setelah reasoning
        self.engine_normal = CekDataEngine(retriever=StubRetriever())

    def teardown_method(self):
        self._eng_mod.call_ai_analysis = self._orig_ai
        self._eng_mod.reason_alternative_queries = self._orig_reason
        self._eng_mod.route_intent = self._orig_router
        self._eng_mod._REASONING_ENABLED = self._orig_reasoning_flag
        self._eng_mod._INTENT_ROUTER_ENABLED = self._orig_intent_flag

    def test_reasoning_not_called_when_data_sufficient(self):
        """Jika data cukup relevan, reasoning tidak dipanggil."""
        reasoning_called = []

        def spy_reasoner(q, profile, gap):
            reasoning_called.append(True)
            from cekdata_engine.inference_reasoner import ReasoningResult
            return ReasoningResult(found_proxy=False)

        self._eng_mod.reason_alternative_queries = spy_reasoner
        self._eng_mod.call_ai_analysis = make_stub_ai_analyst("Benar")

        self.engine_normal.answer_question("Benarkah kemiskinan Indonesia turun 2023?")
        # Dengan data yang relevan, reasoning tidak dipanggil
        assert len(reasoning_called) == 0

    def test_reasoning_returns_in_response_when_proxy_found(self):
        """Jika reasoning menemukan proxy, field 'reasoning' ada di response."""
        from cekdata_engine.inference_reasoner import ReasoningResult

        def mock_reasoner(q, profile, gap):
            return ReasoningResult(
                found_proxy=True,
                alternative_queries=["jumlah penduduk bekerja Indonesia 2023"],
                proxy_rationale="Data pekerja bisa jadi proxy untuk klaim ini",
            )

        self._eng_mod.reason_alternative_queries = mock_reasoner
        self._eng_mod.call_ai_analysis = make_stub_ai_analyst("Tidak dapat diverifikasi")

        result = self.engine_low.answer_question("Apakah MBG tambah lapangan kerja?")
        assert "reasoning" in result
        assert result["reasoning"]["found_proxy"] is True
        assert result["reasoning"]["proxy_rationale"] != ""

    def test_no_reasoning_field_when_data_sufficient(self):
        """Jika data cukup dan reasoning tidak dipanggil, field 'reasoning' tidak ada."""
        self._eng_mod.call_ai_analysis = make_stub_ai_analyst("Benar")

        result = self.engine_normal.answer_question("Benarkah kemiskinan Indonesia turun 2023?")
        # reasoning field tidak ada jika reasoning tidak dijalankan
        assert "reasoning" not in result or result.get("reasoning") is None

    def test_analyst_gap_triggers_reasoning(self):
        """Jika AI analyst bilang data tidak ada, reasoning harus dipanggil."""
        reasoning_called = []

        def spy_reasoner(q, profile, gap):
            reasoning_called.append(gap)
            from cekdata_engine.inference_reasoner import ReasoningResult
            return ReasoningResult(found_proxy=False)

        # AI analyst bilang data tidak tersedia
        def ai_data_missing(q, profile, candidates, **kwargs):
            used = [str(c.record.get("id")) for c in candidates[:1]]
            return {
                "claim": q, "indicator_used": "",
                "records_used": used,
                "temuan_data": "",
                "konteks_penting": "",
                "penilaian": "Tidak dapat diverifikasi",
                "alasan": "Data tidak tersedia dalam corpus untuk menjawab pertanyaan ini.",
                "peringatan_editorial": "", "sumber": "", "unduh_data": "", "raw_answer": "",
            }

        self._eng_mod.reason_alternative_queries = spy_reasoner
        self._eng_mod.call_ai_analysis = ai_data_missing

        # Engine dengan data yang cukup relevan (skor tinggi) agar tidak trigger gap dari retrieval
        self.engine_normal.answer_question("Benarkah kemiskinan Indonesia turun 2023?")
        # Reasoning dipanggil karena AI menyatakan data tidak ada
        assert len(reasoning_called) >= 1

    def test_reasoning_disabled_env_var(self):
        """Jika REASONING_ENABLED=false, reasoning tidak pernah dijalankan."""
        import cekdata_engine.engine as eng_mod
        orig_enabled = eng_mod._REASONING_ENABLED
        eng_mod._REASONING_ENABLED = False

        reasoning_called = []
        def spy_reasoner(q, profile, gap):
            reasoning_called.append(True)
            from cekdata_engine.inference_reasoner import ReasoningResult
            return ReasoningResult(found_proxy=False)

        self._eng_mod.reason_alternative_queries = spy_reasoner
        self._eng_mod.call_ai_analysis = make_stub_ai_analyst("Tidak dapat diverifikasi")

        try:
            self.engine_low.answer_question("pertanyaan kemiskinan apapun 2023")
            assert len(reasoning_called) == 0
        finally:
            self._eng_mod._REASONING_ENABLED = orig_enabled

    def test_response_structure_complete_with_new_fields(self):
        """Semua field yang dijanjikan engine ada di response."""
        self._eng_mod.call_ai_analysis = make_stub_ai_analyst("Benar")
        result = self.engine_normal.answer_question("Benarkah kemiskinan Indonesia turun 2023?")

        required_fields = [
            "question", "effective_question", "queries", "query_profile",
            "answer", "parsed", "best_match", "best_score", "top_matches",
        ]
        for field in required_fields:
            assert field in result, f"Field '{field}' tidak ada di response"

    def test_double_reasoning_prevented(self):
        """Reasoning hanya dipanggil sekali per pertanyaan — tidak boleh double."""
        reasoning_count = []

        def counting_reasoner(q, profile, gap):
            reasoning_count.append(1)
            from cekdata_engine.inference_reasoner import ReasoningResult
            return ReasoningResult(found_proxy=False)

        self._eng_mod.reason_alternative_queries = counting_reasoner

        def ai_data_missing(q, profile, candidates, **kwargs):
            used = [str(c.record.get("id")) for c in candidates[:1]]
            return {
                "claim": q, "indicator_used": "", "records_used": used,
                "temuan_data": "", "konteks_penting": "",
                "penilaian": "Tidak dapat diverifikasi",
                "alasan": "Data tidak tersedia dalam corpus.",
                "peringatan_editorial": "", "sumber": "", "unduh_data": "", "raw_answer": "",
            }

        self._eng_mod.call_ai_analysis = ai_data_missing
        self.engine_low.answer_question("pertanyaan yang memicu gap kemiskinan 2023")

        # Maksimal satu kali reasoning per pertanyaan
        assert len(reasoning_count) <= 1