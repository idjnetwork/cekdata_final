"""
renderer.py
===========
Bertanggung jawab mengubah hasil analisis terstruktur menjadi teks yang
dapat dibaca pengguna (plain text maupun terstruktur).

Layer ini murni presentasi — tidak ada logika bisnis, tidak ada validasi.
"""
from __future__ import annotations

from typing import Any, Dict, List


def render_answer(parsed: Dict[str, Any]) -> str:
    """
    Render dict hasil analisis menjadi teks yang siap ditampilkan ke pengguna.

    Urutan section: Klaim → Temuan data → Konteks penting → Penilaian → Alasan
                    → Peringatan editorial → Sumber + Unduh data
    """
    sections: List[str] = []

    for label, key in [
        ("Klaim", "claim"),
        ("Temuan data", "temuan_data"),
        ("Konteks penting", "konteks_penting"),
        ("Penilaian", "penilaian"),
        ("Alasan", "alasan"),
        ("Peringatan editorial", "peringatan_editorial"),
    ]:
        value = parsed.get(key)
        if value:
            sections.append(f"{label}\n{value}")

    footer: List[str] = []
    if parsed.get("sumber"):
        footer.append(f"Sumber: {parsed['sumber']}")

    unduh = parsed.get("unduh_data")
    if unduh:
        if isinstance(unduh, list):
            if len(unduh) == 1:
                footer.append(f"Unduh data: {unduh[0]}")
            else:
                footer.append("Unduh data:")
                footer.extend(f"* {item}" for item in unduh)
        else:
            footer.append(f"Unduh data: {unduh}")

    if footer:
        sections.append("\n".join(footer))

    # Followup prompt — ajakan untuk menyampaikan konteks klaim
    if parsed.get("followup_prompt"):
        sections.append(f"{parsed['followup_prompt']}")

    return "\n\n".join(s for s in sections if s).strip()


def build_top_matches(candidates, top_k: int) -> List[Dict[str, Any]]:
    """
    Bangun list ringkasan kandidat teratas untuk disertakan dalam response API.
    """
    result = []
    for rank, candidate in enumerate(candidates[:top_k], 1):
        record = candidate.record
        result.append({
            "rank": rank,
            "score": round(candidate.score, 4),
            "title": record.get("title", ""),
            "series_label": record.get("series_label", ""),
            "area_name": record.get("area_name", ""),
            "period": record.get("period", ""),
            "year": record.get("year", record.get("year_end", "")),
            "breakdown_value": record.get("breakdown_value", ""),
            "source_file": record.get("source_file", ""),
            "candidate_id": record.get("id"),
            "retrieval_notes": candidate.retrieval_notes,
            "keyword_hits": candidate.keyword_hits,
            "metadata_hits": candidate.metadata_hits,
        })
    return result


def pick_best_match(parsed: Dict[str, Any], candidates, profile=None) -> Any:
    """
    Pilih satu record terbaik sebagai 'best_match' untuk ditampilkan.
    Prioritas: record yang dipakai AI → latest untuk trend → kandidat[0].
    """
    if not candidates:
        return None

    from .text_utils import latest_sort_key

    if profile and profile.query_type == "comparison":
        return candidates[0].record

    if profile and profile.query_type == "trend":
        return max(candidates, key=lambda c: latest_sort_key(c.record)).record

    lookup = {str(c.record.get("id")): c.record for c in candidates}
    for cid in parsed.get("records_used") or []:
        cid = str(cid)
        if cid in lookup:
            return lookup[cid]

    return candidates[0].record
