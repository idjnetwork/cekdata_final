"""
cekdata_engine
==============
Mesin verifikasi klaim berbasis data statistik Indonesia.

Public API:
    from cekdata_engine import CekDataEngine, answer_question

Arsitektur (berlapis, bottom-up):
    constants.py    — semua konstanta domain
    models.py       — dataclass (QueryProfile, Candidate, CorpusBundle, AnalysisResult)
    text_utils.py   — fungsi teks murni (normalize, tokenize, format angka)
    query_parser.py — parse pertanyaan → QueryProfile
    scorer.py       — scoring, diversifikasi, dan packing kandidat
    retriever.py    — RetrievalBackend ABC + JSONLRetriever + PineconeRetriever
    ai_analyst.py   — prompt builder + OpenAI caller
    validator.py    — validasi output AI + editorial checks
    renderer.py     — render teks final
    engine.py       — CekDataEngine (orkestrator)
"""
from .engine import CekDataEngine
from .retriever import (
    CorpusConfigError,
    RetrievalError,
    build_retriever,
    get_corpus,
    invalidate_corpus_cache,
)
from .models import AnalysisResult, Candidate, CorpusBundle, QueryProfile
from .ai_analyst import AIAnalysisError
from .intent_router import IntentResult
from .inference_reasoner import ReasoningResult
from .data_gap_detector import GapAssessment

# Lazy singleton engine — tidak diinisialisasi sampai benar-benar dipakai
_engine: CekDataEngine | None = None


def _get_engine() -> CekDataEngine:
    global _engine
    if _engine is None:
        _engine = CekDataEngine()
    return _engine


def answer_question(question: str, top_k: int = 8) -> dict:
    """Shortcut: verifikasi satu pertanyaan menggunakan engine default."""
    return _get_engine().answer_question(question, top_k=top_k)


__all__ = [
    "CekDataEngine",
    "answer_question",
    "build_retriever",
    "get_corpus",
    "invalidate_corpus_cache",
    "QueryProfile",
    "Candidate",
    "CorpusBundle",
    "AnalysisResult",
    "AIAnalysisError",
    "CorpusConfigError",
    "RetrievalError",
    "IntentResult",
    "ReasoningResult",
    "GapAssessment",
]
