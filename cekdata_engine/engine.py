"""
engine.py
=========
CekDataEngine: orkestrator utama yang menyatukan semua layer.

Alur lengkap:
  1.  Terima pertanyaan
  2.  IntentRouter — pahami niat, reformulasi, deteksi off-topic/ambigu
  3.  Parse → QueryProfile, perkaya dengan IntentResult
  4.  Retrieve putaran 1 → kandidat
  5.  GapDetector — apakah kandidat cukup relevan?
  6.  [Jika ada gap] InferenceReasoner → query alternatif
  7.  [Jika ada proxy] Retrieve putaran 2 → kandidat proxy
  8.  Pack kandidat untuk AI
  9.  Analyse via AI
  10. GapDetector lagi — apakah AI menyatakan data tidak ada?
  11. [Jika ada gap] InferenceReasoner lagi → query alternatif
  12. [Jika ada proxy] Retrieve putaran 3 → analisis ulang
  13. Validate output AI
  14. Enrich & render
  15. Return response terstruktur

Tidak ada logika domain di sini — semua delegasi ke layer yang tepat.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional, Tuple

from .ai_analyst import AIAnalysisError, call_ai_analysis
from .constants import DEFAULT_OUTPUT
from .data_gap_detector import GapAssessment, detect_analyst_gap, detect_retrieval_gap
from .inference_reasoner import ReasoningResult, reason_alternative_queries
from .intent_router import IntentResult, enrich_query_profile_from_intent, route_intent
from .models import Candidate, QueryProfile
from .query_parser import is_vague_question, make_query_profile
from .renderer import build_top_matches, pick_best_match, render_answer
from .retriever import RetrievalBackend, build_retriever
from .scorer import pack_candidates_for_ai
from .text_utils import (
    enrich_readable_numbers,
    normalize_editorial_labels,
    summarize_sources,
)
from .validator import validate_ai_output
from .gdrive_resolver import resolve_download_urls, resolve_record_urls

log = logging.getLogger(__name__)

_INTENT_ROUTER_ENABLED = os.getenv("INTENT_ROUTER_ENABLED", "true").lower() != "false"
_REASONING_ENABLED = os.getenv("REASONING_ENABLED", "true").lower() != "false"


class CekDataEngine:
    """
    Orkestrator mesin verifikasi data CekData AI.

    Cara pakai:
        engine = CekDataEngine()
        result = engine.answer_question("Benarkah kemiskinan turun di Jawa Timur?")

    Env var baru:
        INTENT_ROUTER_ENABLED  "true" (default) | "false"
        REASONING_ENABLED      "true" (default) | "false"
        GAP_SCORE_THRESHOLD    float, default 15.0
        INTENT_MODEL           model untuk intent router, default = OPENAI_MODEL
        REASONER_MODEL         model untuk inference reasoner, default = OPENAI_MODEL
    """

    def __init__(self, retriever: Optional[RetrievalBackend] = None) -> None:
        self._retriever = retriever

    @property
    def retriever(self) -> RetrievalBackend:
        if self._retriever is None:
            self._retriever = build_retriever()
        return self._retriever

    def answer_question(self, question: str, top_k: int = 8) -> Dict[str, Any]:
        # ── 1. Intent Router ────────────────────────────────────────────
        intent = self._run_intent_router(question)

        if intent.status == "off_topic":
            return self._off_topic_response(question, intent)
        if intent.status == "clarify":
            return self._clarify_response(question, intent)

        effective_question = (
            intent.reformulated_question
            if intent.status == "ok" and intent.reformulated_question
            else question
        )

        # ── 2. Parse & perkaya QueryProfile ─────────────────────────────
        profile = make_query_profile(effective_question)
        if intent.status == "ok":
            enrich_query_profile_from_intent(profile, intent)

        if is_vague_question(effective_question, profile):
            return self._vague_response(question, profile, intent)

        # ── 3. Retrieve putaran 1 ────────────────────────────────────────
        candidates, profile = self.retriever.retrieve(
            effective_question, top_k=top_k, profile=profile,
        )

        if is_vague_question(effective_question, profile):
            return self._vague_response(question, profile, intent)
        if not candidates:
            return self._no_candidates_response(question, profile, intent)

        # ── 4. Gap detection setelah retrieval ──────────────────────────
        reasoning_result: Optional[ReasoningResult] = None
        gap1 = detect_retrieval_gap(candidates, profile)

        if gap1.has_gap and _REASONING_ENABLED:
            log.info(f"Gap setelah retrieval-1: {gap1.reason}")
            candidates, reasoning_result = self._run_reasoning_and_retrieve(
                effective_question, profile, gap1, top_k, candidates
            )

        # ── 5. Analisis AI putaran 1 ─────────────────────────────────────
        packed = pack_candidates_for_ai(candidates, profile, top_k=top_k)
        try:
            ai_raw = call_ai_analysis(effective_question, profile, packed, original_question=question)
            parsed = validate_ai_output(ai_raw, packed, profile, original_question=question, is_claim=intent.is_claim)
        except AIAnalysisError as exc:
            parsed = self._ai_fallback(effective_question, packed, exc)

        # ── 6. Gap detection dari output AI (hanya jika belum reasoning) ─
        if _REASONING_ENABLED and reasoning_result is None:
            gap2 = detect_analyst_gap(parsed)
            if gap2.has_gap:
                log.info(f"Gap dari output AI: {gap2.reason}")
                new_cands, reasoning_result = self._run_reasoning_and_retrieve(
                    effective_question, profile, gap2, top_k, candidates
                )
                if reasoning_result and reasoning_result.found_proxy:
                    candidates = new_cands
                    packed = pack_candidates_for_ai(candidates, profile, top_k=top_k)
                    try:
                        ai_raw = call_ai_analysis(effective_question, profile, packed, original_question=question)
                        parsed = validate_ai_output(ai_raw, packed, profile, original_question=question, is_claim=intent.is_claim)
                    except AIAnalysisError as exc:
                        parsed = self._ai_fallback(effective_question, packed, exc)

        # ── 7. Enrich & render ───────────────────────────────────────────
        lookup = {str(c.record.get("id")): c.record for c in candidates}
        used_records = [
            lookup[cid] for cid in parsed.get("records_used", []) if cid in lookup
        ]
        for fname in ["claim", "temuan_data", "konteks_penting", "alasan", "peringatan_editorial", "sumber"]:
            if parsed.get(fname):
                val = enrich_readable_numbers(str(parsed[fname]), used_records)
                parsed[fname] = normalize_editorial_labels(val)

        final_answer = normalize_editorial_labels(
            enrich_readable_numbers(render_answer(parsed), used_records)
        )
        parsed["raw_answer"] = final_answer

        # ── 8. Resolve download URLs ke Google Drive ─────────────────────
        resolve_download_urls(parsed)

        # ── 9. Susun response ────────────────────────────────────────────
        best_match = pick_best_match(parsed, packed, profile)
        if best_match:
            resolve_record_urls(best_match)

        response: Dict[str, Any] = {
            "question": question,
            "effective_question": effective_question,
            "queries": profile.generated_queries,
            "area_code_filter": None,
            "query_profile": profile.__dict__,
            "intent": intent.to_dict() if intent.status == "ok" else None,
            "answer": final_answer,
            "parsed": parsed,
            "best_match": best_match,
            "best_score": round(candidates[0].score, 4) if candidates else None,
            "top_matches": build_top_matches(candidates, top_k),
        }

        if reasoning_result:
            response["reasoning"] = {
                "found_proxy": reasoning_result.found_proxy,
                "alternative_queries": reasoning_result.alternative_queries,
                "proxy_rationale": reasoning_result.proxy_rationale,
            }

        return response

    # ── Reasoning helper ──────────────────────────────────────────────────

    def _run_reasoning_and_retrieve(
        self,
        question: str,
        profile: QueryProfile,
        gap: GapAssessment,
        top_k: int,
        original_candidates: List[Candidate],
    ) -> Tuple[List[Candidate], ReasoningResult]:
        reasoning = reason_alternative_queries(question, profile, gap)

        if not reasoning.found_proxy:
            return original_candidates, reasoning

        all_new: List[Candidate] = []
        seen_ids: set = set()

        for alt_query in reasoning.alternative_queries:
            try:
                new_cands, _ = self.retriever.retrieve(alt_query, top_k=top_k)
                for c in new_cands:
                    cid = str(c.record.get("id") or id(c))
                    if cid not in seen_ids:
                        all_new.append(c)
                        seen_ids.add(cid)
            except Exception as exc:
                log.warning(f"Retrieval alternatif '{alt_query}' gagal: {exc}")

        if not all_new:
            return original_candidates, reasoning

        combined = all_new + [
            c for c in original_candidates
            if str(c.record.get("id") or id(c)) not in seen_ids
        ]
        log.info(f"Proxy retrieval: {len(all_new)} kandidat baru, total {len(combined)}.")
        return combined[: top_k * 2], reasoning

    # ── Intent router helper ──────────────────────────────────────────────

    def _run_intent_router(self, question: str) -> IntentResult:
        if not _INTENT_ROUTER_ENABLED:
            return IntentResult(status="ok", original_question=question,
                                reformulated_question=question)
        try:
            return route_intent(question)
        except Exception as exc:
            log.warning(f"IntentRouter error: {exc}. Melanjutkan tanpa routing.")
            return IntentResult(status="error", original_question=question,
                                reformulated_question=question)

    # ── Response builders ─────────────────────────────────────────────────

    def _off_topic_response(self, question: str, intent: IntentResult) -> Dict[str, Any]:
        msg = (intent.rejection_message
               or "Pertanyaan ini di luar cakupan CekData AI yang berfokus pada data statistik Indonesia.")
        return self._simple_response(question, msg, intent)

    def _clarify_response(self, question: str, intent: IntentResult) -> Dict[str, Any]:
        msg = (intent.clarification_question
               or "Tolong tuliskan pertanyaanmu dengan lebih spesifik — "
                  "sebutkan indikator, wilayah, atau periode yang ingin diperiksa.")
        return self._simple_response(question, msg, intent)

    def _vague_response(self, question: str, profile: QueryProfile,
                        intent: IntentResult) -> Dict[str, Any]:
        msg = (
            "Pertanyaanmu terlalu pendek atau umum untuk dijawab dengan data. "
            "Tolong tuliskan dengan lebih spesifik — sebutkan indikator, wilayah, atau periode.\n\n"
            "Contoh pertanyaan yang bisa dijawab:\n"
            "• \"Berapa persentase penduduk miskin Indonesia pada Maret 2023?\"\n"
            "• \"Bandingkan kemiskinan Jawa Timur dan Jawa Barat pada 2023\"\n"
            "• \"Bagaimana tren kemiskinan Indonesia dalam 5 tahun terakhir?\"\n"
            "• \"Benarkah pengangguran Gen Z paling tinggi?\"\n"
            "• \"Pemerintah klaim kemiskinan turun karena programnya. Benar?\""
        )
        parsed = dict(DEFAULT_OUTPUT)
        parsed.update(penilaian="", alasan="", raw_answer=msg)
        return {
            "question": question, "effective_question": question,
            "queries": profile.generated_queries, "area_code_filter": None,
            "query_profile": profile.__dict__,
            "intent": intent.to_dict() if intent.status == "ok" else None,
            "answer": msg, "parsed": parsed,
            "best_match": None, "best_score": None, "top_matches": [],
        }

    def _no_candidates_response(self, question: str, profile: QueryProfile,
                                intent: IntentResult) -> Dict[str, Any]:
        parsed = dict(DEFAULT_OUTPUT)
        parsed["claim"] = question
        parsed["alasan"] = "Tidak ada kandidat data yang ditemukan dari corpus aktif."
        parsed["raw_answer"] = render_answer(parsed)
        return {
            "question": question, "effective_question": question,
            "queries": profile.generated_queries, "area_code_filter": None,
            "query_profile": profile.__dict__,
            "intent": intent.to_dict() if intent.status == "ok" else None,
            "answer": parsed["raw_answer"], "parsed": parsed,
            "best_match": None, "best_score": None, "top_matches": [],
        }

    @staticmethod
    def _simple_response(question: str, message: str,
                         intent: IntentResult) -> Dict[str, Any]:
        parsed = dict(DEFAULT_OUTPUT)
        parsed.update(penilaian="", alasan="", raw_answer=message)
        return {
            "question": question, "effective_question": question,
            "queries": [], "area_code_filter": None, "query_profile": {},
            "intent": intent.to_dict(),
            "answer": message, "parsed": parsed,
            "best_match": None, "best_score": None, "top_matches": [],
        }

    @staticmethod
    def _ai_fallback(question: str, packed: List[Candidate],
                     exc: Exception) -> Dict[str, Any]:
        parsed = dict(DEFAULT_OUTPUT)
        parsed["claim"] = question
        parsed["temuan_data"] = "Sistem menemukan kandidat data, tetapi analisis AI gagal dijalankan."
        parsed["alasan"] = f"Fallback aktif karena error: {exc}"
        src, dl = summarize_sources([c.record for c in packed[:2]])
        parsed["sumber"] = src
        parsed["unduh_data"] = dl
        return parsed
