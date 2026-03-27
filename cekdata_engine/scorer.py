"""
scorer.py
=========
Bertanggung jawab atas:
  1. Memberi skor relevansi setiap record terhadap QueryProfile
  2. Mendiversifikasi kandidat agar tidak monoton
  3. Mempack kandidat yang optimal untuk dikirim ke AI (per query_type)

Layer ini murni komputasi — tidak ada I/O, tidak ada AI, tidak ada corpus loading.
"""
from __future__ import annotations

import math
from collections import Counter
from typing import Dict, List, Optional, Set, Tuple

from .constants import (
    AGGREGATE_BREAKDOWNS, AGGREGATE_SUBGROUPS,
    DETAILED_BREAKDOWN_LABELS, DETAILED_SUBGROUPS,
    BIAS_LATEST_PERIOD, BIAS_LATEST_YEAR, BIAS_RECENT_PERIOD, BIAS_RECENT_YEAR,
    PENALTY_AVOID_GARIS, PENALTY_COMBINED_BREAKDOWN, PENALTY_JUMLAH_FOR_CLAIM,
    PENALTY_NON_TARGET_AREA, PENALTY_PARTIAL_BREAKDOWN, PENALTY_PERCENT_FOR_QUANTITY,
    PENALTY_PERIOD_MISMATCH, PENALTY_TREND_SUMMARY, PENALTY_UNREQUESTED_BREAKDOWN,
    PENALTY_UNREQUESTED_OTHER_BREAK, PENALTY_UNREQUESTED_OTHER_SUB,
    PENALTY_UNREQUESTED_SUBGROUP, PENALTY_WRONG_BREAKDOWN,
    PENALTY_WRONG_INDICATOR_MAIN, PENALTY_WRONG_INDICATOR_SOFT,
    SCORE_AGGREGATE_BREAKDOWN, SCORE_AGGREGATE_SUBGROUP,
    SCORE_AREA_MATCH, SCORE_BREAKDOWN_MATCH,
    SCORE_COMPARISON_AREA_MATCH, SCORE_COMPARISON_ATOMIC,
    SCORE_COMPARISON_COMBINED_BREAKDOWN, SCORE_EXPLICIT_YEAR_MATCH,
    SCORE_KEYWORD_HIT, SCORE_NATIONAL_AREA_DEFAULT,
    SCORE_PERIOD_MATCH, SCORE_PRIMARY_INDICATOR_MATCH,
    SCORE_SECONDARY_INDICATOR_MATCH, SCORE_SUBGROUP_MATCH,
    SCORE_TREND_ATOMIC_PRIORITY, SCORE_TREND_DOC_TYPE,
    SCORE_TREND_POVERTY_PREF, SCORE_TREND_SPAN_MAX,
    SCORE_EXPLICIT_URBAN_RURAL,
)
from .models import Candidate, QueryProfile
from .query_parser import normalize_indicator_label
from .text_utils import build_record_text, latest_sort_key, normalize_text, tokenize


# ---------------------------------------------------------------------------
# Scoring dasar
# ---------------------------------------------------------------------------

def _overlap_score(query_tokens: List[str], text_tokens: List[str]) -> float:
    """TF-weighted overlap antara token query dan token teks record."""
    if not query_tokens or not text_tokens:
        return 0.0
    counter = Counter(text_tokens)
    score = 0.0
    for tok in query_tokens:
        if tok in counter:
            score += 1.0 + math.log(1 + counter[tok])
    return score


def score_record(record: Dict, profile: QueryProfile) -> Candidate:
    """
    Hitung skor relevansi satu record terhadap QueryProfile.
    Mengembalikan Candidate dengan score, notes, dan keyword_hits.
    """
    raw_text = build_record_text(record)
    text_norm = normalize_text(raw_text)
    text_tokens = tokenize(text_norm)

    score = 0.0
    notes: List[str] = []
    keyword_hits: List[str] = []
    metadata_hits: Dict = {}

    # --- Multi-query overlap ---
    for query in profile.generated_queries:
        score += _overlap_score(tokenize(query), text_tokens)

    # --- Indikator ---
    rec_indicator = normalize_indicator_label(str(record.get("series_label") or ""))
    if profile.primary_indicator:
        if rec_indicator == profile.primary_indicator:
            score += SCORE_PRIMARY_INDICATOR_MATCH
            notes.append("primary_indicator_match")
            metadata_hits["indicator_match"] = profile.primary_indicator
        elif rec_indicator in profile.indicator_targets:
            score += SCORE_SECONDARY_INDICATOR_MATCH
            notes.append("secondary_indicator_match")
            metadata_hits["indicator_match"] = rec_indicator
        else:
            if (
                profile.primary_indicator == "persentase penduduk miskin"
                and rec_indicator == "garis kemiskinan"
            ):
                score += PENALTY_WRONG_INDICATOR_MAIN
                notes.append("penalty_wrong_indicator")
            elif profile.primary_indicator and rec_indicator:
                score += PENALTY_WRONG_INDICATOR_SOFT

    # Penalti jumlah penduduk miskin untuk query claim umum (bukan quantity)
    if (
        profile.query_type == "claim"
        and not profile.quantity_hint
        and rec_indicator == "jumlah penduduk miskin"
    ):
        score += PENALTY_JUMLAH_FOR_CLAIM
        notes.append("soft_penalty_jumlah_for_general_claim")

    # Bonus/penalti jika query eksplisit soal kuantitas
    quantity_keywords = ["lebih banyak", "lebih sedikit", "jumlah", "orang miskin", "ribu orang", "juta orang"]
    if any(k in profile.normalized_question for k in quantity_keywords):
        if rec_indicator == "jumlah penduduk miskin":
            score += SCORE_PRIMARY_INDICATOR_MATCH  # setara primary match untuk query kuantitas
            notes.append("quantity_comparison_bonus")
        elif rec_indicator == "persentase penduduk miskin":
            score += PENALTY_PERCENT_FOR_QUANTITY
            notes.append("penalty_percent_for_quantity_comparison")

    # --- Wilayah ---
    rec_area = str(record.get("area_name") or "").strip()
    if profile.area_targets:
        if rec_area in profile.area_targets:
            score += SCORE_AREA_MATCH
            notes.append("area_match")
            keyword_hits.append(rec_area)
        elif rec_area == "Indonesia" and "Indonesia" in profile.comparison_targets:
            score += SCORE_COMPARISON_AREA_MATCH
            notes.append("comparison_area_match")
        else:
            score += PENALTY_NON_TARGET_AREA
            notes.append("penalty_non_target_area")
    else:
        if rec_area == "Indonesia":
            score += SCORE_NATIONAL_AREA_DEFAULT

    # --- Breakdown ---
    rec_break = str(record.get("breakdown_value") or "").strip()
    if profile.breakdown_targets:
        if rec_break in profile.breakdown_targets:
            score += SCORE_BREAKDOWN_MATCH
            notes.append("breakdown_match")
            keyword_hits.append(rec_break)
        else:
            score += PENALTY_WRONG_BREAKDOWN
            if rec_break == "Perkotaan + Perdesaan":
                score += PENALTY_COMBINED_BREAKDOWN
                notes.append("penalty_combined_breakdown_for_pair_query")
    else:
        if rec_break in AGGREGATE_BREAKDOWNS:
            score += SCORE_AGGREGATE_BREAKDOWN
            notes.append("aggregate_breakdown_bonus")
        elif rec_break in DETAILED_BREAKDOWN_LABELS:
            score += PENALTY_UNREQUESTED_BREAKDOWN
            notes.append("penalty_unrequested_detailed_breakdown")
        elif rec_break:
            score += PENALTY_UNREQUESTED_OTHER_BREAK
            notes.append("penalty_unrequested_other_breakdown")

    # --- Subgroup ---
    rec_subgroup = str(record.get("subgroup_value") or "").strip()
    if rec_subgroup:
        if rec_subgroup in profile.breakdown_targets:
            score += SCORE_SUBGROUP_MATCH
            notes.append("subgroup_match")
            keyword_hits.append(rec_subgroup)
        elif not profile.breakdown_targets:
            if rec_subgroup in AGGREGATE_SUBGROUPS:
                score += SCORE_AGGREGATE_SUBGROUP
                notes.append("aggregate_subgroup_bonus")
            elif rec_subgroup in DETAILED_SUBGROUPS:
                score += PENALTY_UNREQUESTED_SUBGROUP
                notes.append("penalty_unrequested_detailed_subgroup")
            else:
                score += PENALTY_UNREQUESTED_OTHER_SUB
                notes.append("penalty_unrequested_other_subgroup")

    # --- Temporal ---
    rec_year, rec_period_rank = latest_sort_key(record)
    if profile.explicit_years:
        if rec_year in profile.explicit_years:
            score += SCORE_EXPLICIT_YEAR_MATCH
            notes.append("explicit_year_match")
    elif profile.needs_latest:
        score += BIAS_LATEST_YEAR * rec_year + BIAS_LATEST_PERIOD * rec_period_rank
        notes.append("latest_bias")
    elif profile.needs_recent_range:
        score += BIAS_RECENT_YEAR * rec_year + BIAS_RECENT_PERIOD * rec_period_rank
        notes.append("recent_bias")

    rec_period = str(record.get("period") or "")
    if profile.periods:
        if rec_period in profile.periods:
            score += SCORE_PERIOD_MATCH
            notes.append("period_match")
        else:
            score += PENALTY_PERIOD_MISMATCH

    # --- Jenis query: trend ---
    if profile.query_type == "trend":
        if profile.requested_trend_years:
            if record.get("doc_type") == "atomic" and isinstance(record.get("year"), int):
                score += SCORE_TREND_ATOMIC_PRIORITY
                notes.append("trend_atomic_year_priority")
            elif record.get("doc_type") == "trend":
                score += PENALTY_TREND_SUMMARY
                notes.append("trend_summary_penalty_for_requested_years")
        else:
            if record.get("doc_type") == "trend":
                score += SCORE_TREND_DOC_TYPE
                notes.append("trend_doc_type")

        if rec_indicator == "persentase penduduk miskin":
            score += SCORE_TREND_POVERTY_PREF

        year_start = record.get("year_start") if isinstance(record.get("year_start"), int) else None
        year_end = record.get("year_end") if isinstance(record.get("year_end"), int) else None
        if year_start is not None and year_end is not None and not profile.requested_trend_years:
            score += min(SCORE_TREND_SPAN_MAX, max(0.0, year_end - year_start))
            notes.append("trend_span_bonus")

    # --- Jenis query: comparison ---
    elif profile.query_type == "comparison":
        if record.get("doc_type") == "atomic":
            score += SCORE_COMPARISON_ATOMIC
            notes.append("comparison_atomic_bonus")
        if profile.comparison_targets and not profile.breakdown_targets:
            if rec_break in {"Indonesia", "Perkotaan + Perdesaan", ""}:
                score += SCORE_COMPARISON_COMBINED_BREAKDOWN
                notes.append("comparison_combined_breakdown_bonus")
            elif rec_break in {"Perkotaan", "Perdesaan"}:
                score += PENALTY_PARTIAL_BREAKDOWN
                notes.append("penalty_partial_breakdown_for_area_comparison")

    # Bonus urban/rural jika disebut eksplisit
    if any(k in profile.normalized_question for k in ["perdesaan", "perkotaan", "desa", "kota"]):
        if rec_break in {"Perdesaan", "Perkotaan"}:
            score += SCORE_EXPLICIT_URBAN_RURAL

    # --- Keyword hits ---
    for key in profile.keyword_targets:
        if key and normalize_text(key) in text_norm:
            score += SCORE_KEYWORD_HIT
            keyword_hits.append(key)

    # Penalti garis kemiskinan untuk query evaluasi umum
    if rec_indicator == "garis kemiskinan" and any(
        k in profile.normalized_question
        for k in ["lebih baik", "membaik", "memburuk", "kondisi kemiskinan", "angka kemiskinan"]
    ):
        score += PENALTY_AVOID_GARIS
        notes.append("avoid_garis_for_general_assessment")

    return Candidate(
        score=score,
        record=record,
        evidence_text=raw_text[:1500],
        retrieval_notes=notes,
        keyword_hits=list(dict.fromkeys(keyword_hits)),
        metadata_hits=metadata_hits,
    )


# ---------------------------------------------------------------------------
# Helpers matching
# ---------------------------------------------------------------------------

def _matches_indicator(record: Dict, indicator: str) -> bool:
    if not indicator:
        return True
    return normalize_indicator_label(str(record.get("series_label") or "")) == indicator


def _matches_area(record: Dict, area: str) -> bool:
    return str(record.get("area_name") or "").strip() == area


def _matches_breakdown(record: Dict, breakdown: str) -> bool:
    return str(record.get("breakdown_value") or "").strip() == breakdown


def _sort_key(c: Candidate) -> Tuple:
    yr, pr = latest_sort_key(c.record)
    return (c.score, yr, pr)


def _choose_latest(candidates: List[Candidate]) -> Optional[Candidate]:
    if not candidates:
        return None
    return max(candidates, key=lambda c: latest_sort_key(c.record))


# ---------------------------------------------------------------------------
# Diversifikasi
# ---------------------------------------------------------------------------

def diversify_candidates(
    candidates: List[Candidate],
    profile: QueryProfile,
    top_k: int,
) -> List[Candidate]:
    """
    Pastikan kandidat terpilih mencakup semua sisi yang dibutuhkan
    (wilayah, breakdown, tahun) sebelum mengisi sisa slot dengan skor tertinggi.
    """
    if not candidates:
        return []

    selected: List[Candidate] = []
    selected_ids: Set[int] = set()

    def add_first(predicate) -> None:
        for cand in candidates:
            if id(cand) in selected_ids:
                continue
            if predicate(cand):
                selected.append(cand)
                selected_ids.add(id(cand))
                return

    # Comparison: pastikan setiap sisi perbandingan terwakili
    if profile.query_type == "comparison":
        if profile.comparison_targets:
            for target in profile.comparison_targets:
                add_first(lambda c, t=target: (
                    _matches_area(c.record, t)
                    and (
                        not profile.primary_indicator
                        or _matches_indicator(c.record, profile.primary_indicator)
                    )
                ))

        if profile.breakdown_targets:
            target_area = profile.area_targets[0] if profile.area_targets else "Indonesia"
            forced_indicator = (
                "jumlah penduduk miskin"
                if any(
                    k in profile.normalized_question
                    for k in ["lebih banyak", "lebih sedikit", "jumlah", "orang miskin", "ribu orang", "juta orang"]
                )
                else (profile.primary_indicator or "")
            )
            for target in profile.breakdown_targets:
                add_first(lambda c, t=target, a=target_area, ind=forced_indicator: (
                    _matches_area(c.record, a)
                    and _matches_breakdown(c.record, t)
                    and (not ind or _matches_indicator(c.record, ind))
                ))

    # Trend: ambil 6 data terbaru yang sesuai indikator+area
    if profile.query_type == "trend":
        preferred = [
            c for c in candidates
            if _matches_indicator(c.record, profile.primary_indicator or "persentase penduduk miskin")
            and str(c.record.get("area_name") or "").strip() in (profile.area_targets or ["Indonesia"])
            and str(c.record.get("breakdown_value") or "").strip() in AGGREGATE_BREAKDOWNS
        ]
        preferred.sort(key=lambda c: latest_sort_key(c.record))
        for c in preferred[-6:]:
            if id(c) not in selected_ids:
                selected.append(c)
                selected_ids.add(id(c))

    # Evaluative claim: pastikan tahun target dan tahun sebelumnya ada
    if _is_evaluative_claim(profile) and profile.explicit_years:
        target_year = max(profile.explicit_years)
        target_indicator = profile.primary_indicator or "persentase penduduk miskin"
        target_area = profile.area_targets[0] if profile.area_targets else "Indonesia"

        for yr in (target_year, target_year - 1):
            add_first(lambda c, y=yr, a=target_area, ind=target_indicator: (
                int(c.record.get("year") or 0) == y
                and _matches_area(c.record, a)
                and _matches_indicator(c.record, ind)
                and str(c.record.get("breakdown_value") or "").strip() in AGGREGATE_BREAKDOWNS
            ))

    # Isi sisa slot dengan skor tertinggi
    for cand in candidates:
        if id(cand) not in selected_ids:
            selected.append(cand)
            selected_ids.add(id(cand))
        if len(selected) >= top_k:
            break

    return selected[:top_k]


def _is_evaluative_claim(profile: QueryProfile) -> bool:
    return any(
        phrase in profile.normalized_question
        for phrase in [
            "membaik", "memburuk", "lebih baik", "lebih buruk",
            "masih tinggi", "masih rendah", "apakah membaik", "benarkah membaik",
        ]
    )


# ---------------------------------------------------------------------------
# Packing kandidat untuk AI (per query_type)
# ---------------------------------------------------------------------------

def pack_candidates_for_ai(
    candidates: List[Candidate],
    profile: QueryProfile,
    top_k: int,
) -> List[Candidate]:
    """Pilih dan urutkan kandidat yang paling berguna untuk dikirim ke AI."""
    if profile.query_type == "comparison":
        packed = _pack_comparison(candidates, profile)
    elif profile.query_type == "trend":
        packed = _pack_trend(candidates, profile)
    else:
        packed = list(candidates)
    return packed[:top_k]


def _pack_comparison(candidates: List[Candidate], profile: QueryProfile) -> List[Candidate]:
    packed: List[Candidate] = []
    seen_ids: Set[int] = set()

    def add(c: Candidate) -> None:
        if id(c) not in seen_ids:
            packed.append(c)
            seen_ids.add(id(c))

    if profile.breakdown_targets:
        target_area = profile.area_targets[0] if profile.area_targets else "Indonesia"
        indicator = (
            "jumlah penduduk miskin"
            if any(
                k in profile.normalized_question
                for k in ["lebih banyak", "lebih sedikit", "jumlah", "orang miskin", "ribu orang", "juta orang"]
            )
            else (profile.primary_indicator or "")
        )
        same_area = [
            c for c in candidates
            if _matches_area(c.record, target_area) and _matches_indicator(c.record, indicator)
        ]

        # Temukan latest_key dari breakdown yang diminta
        latest_key: Optional[Tuple[int, int]] = None
        for cand in same_area:
            if str(cand.record.get("breakdown_value") or "").strip() not in set(profile.breakdown_targets):
                continue
            lk = latest_sort_key(cand.record)
            if latest_key is None or lk > latest_key:
                latest_key = lk

        if latest_key is not None:
            for breakdown in profile.breakdown_targets:
                matched = [
                    c for c in same_area
                    if latest_sort_key(c.record) == latest_key and _matches_breakdown(c.record, breakdown)
                ]
                best = _choose_latest(matched)
                if best:
                    add(best)

    elif profile.comparison_targets:
        indicator = profile.primary_indicator or ""
        target_entities = list(dict.fromkeys(profile.comparison_targets))
        latest_pair: List[Candidate] = []

        for area in target_entities:
            matched = [
                c for c in candidates
                if _matches_area(c.record, area) and _matches_indicator(c.record, indicator)
            ]
            best = _choose_latest(matched)
            if best:
                latest_pair.append(best)

        if len(latest_pair) >= 2:
            # Align ke periode yang sama (ambil yang lebih tua)
            aligned_key = min(latest_sort_key(c.record) for c in latest_pair)
            aligned: List[Candidate] = []
            for area in target_entities:
                matched = [
                    c for c in candidates
                    if _matches_area(c.record, area)
                    and _matches_indicator(c.record, indicator)
                    and latest_sort_key(c.record) == aligned_key
                ]
                best = _choose_latest(matched)
                if best:
                    aligned.append(best)
            for c in (aligned if len(aligned) >= 2 else latest_pair):
                add(c)

    for cand in candidates:
        add(cand)
    return packed


def _pack_trend(candidates: List[Candidate], profile: QueryProfile) -> List[Candidate]:
    indicator = profile.primary_indicator or "persentase penduduk miskin"
    target_area = profile.area_targets[0] if profile.area_targets else "Indonesia"
    requested_years = profile.requested_trend_years or 6

    preferred = [
        c for c in candidates
        if _matches_indicator(c.record, indicator)
        and _matches_area(c.record, target_area)
        and str(c.record.get("breakdown_value") or "").strip() in AGGREGATE_BREAKDOWNS
    ]

    atomic = sorted(
        [c for c in preferred if c.record.get("doc_type") == "atomic" and isinstance(c.record.get("year"), int)],
        key=lambda c: latest_sort_key(c.record),
    )
    trend_docs = sorted(
        [c for c in preferred if c.record.get("doc_type") == "trend"],
        key=lambda c: latest_sort_key(c.record),
    )

    packed: List[Candidate] = []
    seen_ids: Set[int] = set()
    seen_years: Set[int] = set()

    def add(c: Candidate) -> None:
        if id(c) not in seen_ids:
            packed.append(c)
            seen_ids.add(id(c))

    # 1) Atomic per tahun unik (terbaru dulu)
    for cand in reversed(atomic):
        yr = cand.record.get("year")
        if not isinstance(yr, int):
            continue
        if yr not in seen_years:
            add(cand)
            seen_years.add(yr)
        if len(seen_years) >= requested_years:
            break

    # 2) Atomic tambahan jika masih kurang
    if len(seen_years) < requested_years:
        for cand in reversed(atomic):
            add(cand)
            atomic_years = {
                c.record.get("year") for c in packed
                if c.record.get("doc_type") == "atomic" and isinstance(c.record.get("year"), int)
            }
            if len(atomic_years) >= requested_years:
                break

    # 3) Trend summary sebagai pendukung
    for cand in reversed(trend_docs):
        add(cand)
        if len(packed) >= max(requested_years + 2, 6):
            break

    # 4) Fallback dari preferred
    for cand in reversed(preferred):
        add(cand)
        if len(packed) >= max(requested_years + 4, 8):
            break

    packed = list(reversed(packed))

    # Sisa kandidat lain di belakang
    for cand in candidates:
        add(cand)

    return packed
