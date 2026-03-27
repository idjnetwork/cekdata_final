"""
gdrive_resolver.py
==================
Resolve download URL lokal ke Google Drive URL menggunakan mapping
yang dihasilkan oleh scan_gdrive.py.

Mapping di-load sekali saat startup dan di-cache di memory.
Jika file mapping tidak ada, resolver tidak melakukan apa-apa
(URL tetap seperti aslinya).
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import unquote

log = logging.getLogger(__name__)

_mapping: Optional[Dict[str, Dict]] = None
_mapping_loaded = False


def _load_mapping() -> Dict[str, Dict]:
    """Load gdrive_mapping.json dari beberapa lokasi yang mungkin."""
    global _mapping, _mapping_loaded
    if _mapping_loaded:
        return _mapping or {}

    _mapping_loaded = True

    # Cari mapping file di beberapa lokasi
    candidates = [
        os.getenv("GDRIVE_MAPPING_FILE", ""),
        "gdrive_mapping.json",
        os.path.join(os.path.dirname(__file__), "..", "gdrive_mapping.json"),
    ]

    for path in candidates:
        if path and os.path.isfile(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    _mapping = json.load(f)
                log.info(f"Google Drive mapping loaded: {len(_mapping)} file dari {path}")
                return _mapping
            except Exception as exc:
                log.warning(f"Gagal membaca mapping {path}: {exc}")

    log.info("Google Drive mapping tidak ditemukan — download URL tetap seperti aslinya.")
    _mapping = {}
    return _mapping


def _extract_filename(url_or_path: str) -> str:
    """Ekstrak nama file dari URL atau path."""
    # URL-decode dulu
    decoded = unquote(url_or_path)
    # Ambil bagian terakhir setelah /
    filename = decoded.rsplit("/", 1)[-1] if "/" in decoded else decoded
    return filename.strip()


def resolve_url(url_or_path: str) -> str:
    """
    Resolve satu URL/path ke Google Drive URL jika ada di mapping.
    Jika tidak ada, kembalikan URL asli.
    Menambahkan &filename=NamaFile di URL supaya frontend bisa menampilkan
    nama file yang bermakna sebagai label link.
    """
    mapping = _load_mapping()
    if not mapping:
        return url_or_path

    filename = _extract_filename(url_or_path)
    matched_name = None

    # Coba lookup langsung
    if filename in mapping:
        matched_name = filename
    else:
        # Coba dengan ekstensi berbeda (csv → json atau sebaliknya)
        base = filename.rsplit(".", 1)[0] if "." in filename else filename
        for ext in [".csv", ".json", ".xlsx", ".html"]:
            alt = base + ext
            if alt in mapping:
                matched_name = alt
                break

    if matched_name:
        from urllib.parse import quote
        gdrive_url = mapping[matched_name]["url"]
        label = quote(matched_name, safe="")
        return f"{gdrive_url}&filename={label}"

    return url_or_path


def resolve_download_urls(parsed: Dict[str, Any]) -> Dict[str, Any]:
    """
    Resolve semua download URL dalam dict parsed result.
    Modifikasi in-place dan return dict yang sama.
    """
    # Resolve unduh_data
    unduh = parsed.get("unduh_data")
    if unduh:
        if isinstance(unduh, list):
            parsed["unduh_data"] = [resolve_url(u) for u in unduh]
        elif isinstance(unduh, str):
            parsed["unduh_data"] = resolve_url(unduh)

    return parsed


def resolve_record_urls(record: Dict[str, Any]) -> Dict[str, Any]:
    """Resolve download_url dalam satu record data."""
    if record.get("download_url"):
        record["download_url"] = resolve_url(record["download_url"])
    urls = record.get("download_urls")
    if isinstance(urls, list):
        record["download_urls"] = [resolve_url(u) for u in urls]
    return record


def invalidate_mapping() -> None:
    """Force reload mapping (misalnya setelah scan_gdrive.py dijalankan ulang)."""
    global _mapping, _mapping_loaded
    _mapping = None
    _mapping_loaded = False
