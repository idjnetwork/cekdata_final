"""
models.py
=========
Dataclass yang dipakai di seluruh lapisan.
Tidak ada logika bisnis di sini — hanya struktur data.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class QueryProfile:
    """Representasi terstruktur dari pertanyaan pengguna setelah di-parse."""

    raw_question: str
    normalized_question: str
    query_type: str = "claim"          # "claim" | "trend" | "comparison" | "latest"
    needs_latest: bool = False
    needs_recent_range: bool = False
    requested_trend_years: Optional[int] = None
    explicit_years: List[int] = field(default_factory=list)
    periods: List[str] = field(default_factory=list)
    indicator_targets: List[str] = field(default_factory=list)
    primary_indicator: str = ""
    area_targets: List[str] = field(default_factory=list)
    comparison_targets: List[str] = field(default_factory=list)
    breakdown_targets: List[str] = field(default_factory=list)
    comparator_words: List[str] = field(default_factory=list)
    quantity_hint: bool = False
    ambiguous_indicator: bool = False
    generated_queries: List[str] = field(default_factory=list)
    keyword_targets: List[str] = field(default_factory=list)
    metadata_filters: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Candidate:
    """Satu record data beserta skor relevansi dan metadata retrieval-nya."""

    score: float
    record: Dict[str, Any]
    evidence_text: str
    retrieval_notes: List[str]
    keyword_hits: List[str]
    metadata_hits: Dict[str, Any]


@dataclass
class CorpusBundle:
    """Kumpulan record yang sudah di-load dari sumber data."""

    records: List[Dict[str, Any]]
    source_path: Path


@dataclass
class AnalysisResult:
    """
    Hasil akhir dari satu siklus analisis.
    Dibuat oleh validator dan di-render oleh renderer.
    """

    claim: str = ""
    indicator_used: str = ""
    records_used: List[str] = field(default_factory=list)   # list candidate_id
    temuan_data: str = ""
    konteks_penting: str = ""
    penilaian: str = "Tidak dapat diverifikasi"
    alasan: str = "Data yang ditemukan belum cukup kuat untuk mendukung penilaian otomatis."
    peringatan_editorial: str = ""
    sumber: str = ""
    unduh_data: str | List[str] = ""
    raw_answer: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "claim": self.claim,
            "indicator_used": self.indicator_used,
            "records_used": self.records_used,
            "temuan_data": self.temuan_data,
            "konteks_penting": self.konteks_penting,
            "penilaian": self.penilaian,
            "alasan": self.alasan,
            "peringatan_editorial": self.peringatan_editorial,
            "sumber": self.sumber,
            "unduh_data": self.unduh_data,
            "raw_answer": self.raw_answer,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "AnalysisResult":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})
