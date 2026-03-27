"""
retriever.py
============
Mendefinisikan antarmuka retrieval (ABC) dan dua implementasi:
  - JSONLRuleBasedRetriever  : corpus lokal dari file JSONL
  - PineconeRetriever        : vector search via Pinecone + OpenAI embeddings

Layer ini bertanggung jawab pada I/O data — bukan scoring, bukan AI analysis.
"""
from __future__ import annotations

import json
import os
from abc import ABC, abstractmethod
from functools import lru_cache
from pathlib import Path
from typing import List, Tuple

from .models import Candidate, CorpusBundle, QueryProfile
from .query_parser import make_query_profile
from .scorer import diversify_candidates, score_record
from .text_utils import build_record_text, latest_sort_key, normalize_record


# ---------------------------------------------------------------------------
# Custom exceptions
# ---------------------------------------------------------------------------

class CorpusConfigError(RuntimeError):
    """Corpus tidak ditemukan atau env var tidak diset."""


class RetrievalError(RuntimeError):
    """Error umum saat proses retrieval."""


# ---------------------------------------------------------------------------
# Corpus loader (JSONL lokal) — di-cache di level modul
# ---------------------------------------------------------------------------

class LocalJSONLCorpusLoader:
    """Memuat dan mem-parse file JSONL dari path yang diberikan oleh env var."""

    ENV_VAR = "CEKDATA_NEWDATA_JSONL"

    def __init__(self, env_var: str = ENV_VAR) -> None:
        self.env_var = env_var

    def resolve_path(self) -> Path:
        env_path = os.getenv(self.env_var, "").strip()
        if not env_path:
            raise CorpusConfigError(
                f"Env {self.env_var} belum diset. "
                "Engine sengaja tidak auto-discover corpus — sumber data harus eksplisit."
            )
        path = Path(os.path.expanduser(env_path)).resolve()
        if not path.exists() or not path.is_file():
            raise CorpusConfigError(f"Corpus JSONL tidak ditemukan: {path}")
        return path

    def load(self) -> CorpusBundle:
        path = self.resolve_path()
        records: list = []
        with path.open("r", encoding="utf-8") as handle:
            for line_no, line in enumerate(handle, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise ValueError(
                        f"Gagal parse JSONL pada baris {line_no}: {exc}"
                    ) from exc
                if isinstance(obj, dict):
                    records.append(normalize_record(obj, len(records) + 1))
        return CorpusBundle(records=records, source_path=path)


@lru_cache(maxsize=1)
def _load_corpus_cached() -> CorpusBundle:
    """Cache corpus di memory. Panggil invalidate_corpus_cache() untuk refresh."""
    return LocalJSONLCorpusLoader().load()


def invalidate_corpus_cache() -> None:
    """Paksa reload corpus pada request berikutnya (misal setelah file diperbarui)."""
    _load_corpus_cached.cache_clear()


def get_corpus() -> CorpusBundle:
    return _load_corpus_cached()


# ---------------------------------------------------------------------------
# Abstract base class
# ---------------------------------------------------------------------------

class RetrievalBackend(ABC):
    """
    Antarmuka yang harus diimplementasikan oleh setiap backend retrieval.

    Kontrak: menerima pertanyaan (dan opsional QueryProfile yang sudah diperkaya),
    mengembalikan (List[Candidate], QueryProfile).
    Jika profile diberikan, gunakan itu alih-alih membuat baru.
    """

    @abstractmethod
    def retrieve(
        self, question: str, top_k: int = 8,
        profile: QueryProfile | None = None,
    ) -> Tuple[List[Candidate], QueryProfile]:
        ...


# ---------------------------------------------------------------------------
# Implementasi 1: Rule-based JSONL
# ---------------------------------------------------------------------------

class JSONLRuleBasedRetriever(RetrievalBackend):
    """
    Retriever berbasis rule scoring lokal.
    Tidak memerlukan koneksi eksternal — hanya butuh file JSONL.
    """

    def __init__(self, corpus_loader=get_corpus) -> None:
        self.corpus_loader = corpus_loader

    def retrieve(
        self, question: str, top_k: int = 8,
        profile: QueryProfile | None = None,
    ) -> Tuple[List[Candidate], QueryProfile]:
        bundle = self.corpus_loader()
        if profile is None:
            profile = make_query_profile(question)

        scored = [score_record(r, profile) for r in bundle.records]
        scored.sort(
            key=lambda x: (x.score, latest_sort_key(x.record)[0], latest_sort_key(x.record)[1]),
            reverse=True,
        )

        top_pool = scored[: max(top_k * 8, 64)]
        diversified = diversify_candidates(top_pool, profile, top_k)
        diversified.sort(
            key=lambda x: (x.score, latest_sort_key(x.record)[0], latest_sort_key(x.record)[1]),
            reverse=True,
        )
        return diversified[:top_k], profile


# ---------------------------------------------------------------------------
# Implementasi 2: Pinecone vector search
# ---------------------------------------------------------------------------

class PineconeRetriever(RetrievalBackend):
    """
    Retriever berbasis vector similarity (Pinecone + OpenAI embeddings).
    Memerlukan: PINECONE_API_KEY, PINECONE_INDEX_NAME, OPENAI_API_KEY.
    """

    def __init__(self) -> None:
        try:
            from openai import OpenAI as _OpenAI
        except ImportError as exc:
            raise RetrievalError("Package 'openai' belum terpasang untuk PineconeRetriever.") from exc

        try:
            from pinecone import Pinecone as _Pinecone
        except ImportError as exc:
            raise RetrievalError("Package 'pinecone' belum terpasang untuk PineconeRetriever.") from exc

        self.index_name = _require_env("PINECONE_INDEX_NAME")
        openai_key = _require_env("OPENAI_API_KEY")
        pinecone_key = _require_env("PINECONE_API_KEY")
        self.embed_model = os.getenv("OPENAI_EMBED_MODEL", "text-embedding-3-small").strip()

        self._openai = _OpenAI(api_key=openai_key)
        self._index = _Pinecone(api_key=pinecone_key).Index(self.index_name)

    def _embed(self, text: str) -> list:
        resp = self._openai.embeddings.create(
            model=self.embed_model,
            input=[text if str(text).strip() else "."],
        )
        return resp.data[0].embedding

    def _match_to_record(self, match) -> dict:
        md = dict(getattr(match, "metadata", {}) or {})
        md["id"] = str(getattr(match, "id", "") or md.get("id") or "")
        md["text"] = build_record_text(md)
        return md

    def retrieve(
        self, question: str, top_k: int = 8,
        profile: QueryProfile | None = None,
    ) -> Tuple[List[Candidate], QueryProfile]:
        if profile is None:
            profile = make_query_profile(question)
        query_vec = self._embed(question)

        resp = self._index.query(
            vector=query_vec,
            top_k=max(top_k * 8, 64),
            include_values=False,
            include_metadata=True,
        )

        records = [self._match_to_record(m) for m in (getattr(resp, "matches", []) or [])]
        scored = [score_record(r, profile) for r in records]
        scored.sort(
            key=lambda x: (x.score, latest_sort_key(x.record)[0], latest_sort_key(x.record)[1]),
            reverse=True,
        )
        diversified = diversify_candidates(scored, profile, top_k)
        diversified.sort(
            key=lambda x: (x.score, latest_sort_key(x.record)[0], latest_sort_key(x.record)[1]),
            reverse=True,
        )
        return diversified[:top_k], profile


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def build_retriever(backend: str | None = None) -> RetrievalBackend:
    """
    Buat retriever sesuai konfigurasi.
    Jika backend=None, baca dari env var RETRIEVAL_BACKEND (default: 'local').
    """
    if backend is None:
        backend = os.getenv("RETRIEVAL_BACKEND", "local").strip().lower()

    if backend == "pinecone":
        return PineconeRetriever()
    return JSONLRuleBasedRetriever()


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _require_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RetrievalError(f"Env var {name} belum diset.")
    return value
