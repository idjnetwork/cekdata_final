"""
openai_client.py
================
Shared OpenAI client factory — satu client untuk semua layer AI.

Menggantikan tiga lazy singleton terpisah di ai_analyst.py, intent_router.py,
dan inference_reasoner.py. Menghemat koneksi dan memudahkan konfigurasi terpusat.
"""
from __future__ import annotations

import os


class OpenAIClientError(RuntimeError):
    """Gagal membuat OpenAI client."""


_shared_client = None


def get_openai_client():
    """
    Kembalikan shared OpenAI client. Lazy-initialized sekali saja.
    Melempar OpenAIClientError jika package atau API key tidak tersedia.
    """
    global _shared_client
    if _shared_client is None:
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise OpenAIClientError(
                "Package 'openai' belum terpasang. "
                "Install dengan: pip install openai"
            ) from exc
        api_key = os.getenv("OPENAI_API_KEY", "").strip()
        if not api_key:
            raise OpenAIClientError("OPENAI_API_KEY belum diset.")
        _shared_client = OpenAI(api_key=api_key)
    return _shared_client


def reset_client() -> None:
    """Reset shared client (untuk testing)."""
    global _shared_client
    _shared_client = None
