"""
text_utils.py
=============
Fungsi-fungsi utilitas teks murni (pure functions).
Tidak ada state, tidak ada side effect, tidak ada dependency ke layer lain.
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, Iterable, List, Tuple

from .constants import PERIOD_ORDER, STOPWORDS


# ---------------------------------------------------------------------------
# Normalisasi & tokenisasi
# ---------------------------------------------------------------------------

def normalize_text(text: Any) -> str:
    """Lowercase, strip, ganti karakter non-standar jadi spasi."""
    if text is None:
        return ""
    text = str(text).strip().lower()
    text = text.replace("/", " ").replace("-", " ")
    text = re.sub(r"[^\w\s%.,()]", " ", text, flags=re.UNICODE)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def tokenize(text: Any) -> List[str]:
    """Tokenisasi dan buang stopwords."""
    return [
        t for t in normalize_text(text).split()
        if t and t not in STOPWORDS and len(t) > 1
    ]


# ---------------------------------------------------------------------------
# Ekstraksi dari teks pertanyaan
# ---------------------------------------------------------------------------

def extract_years(text: str) -> List[int]:
    """Ekstrak semua tahun (1900–2099) dari teks."""
    return [int(y) for y in re.findall(r"\b(19\d{2}|20\d{2})\b", text)]


def extract_periods(text: str) -> List[str]:
    """Ekstrak periode semester/triwulan/bulan dari teks."""
    low = normalize_text(text)
    periods: List[str] = []
    candidates = [
        "Maret", "September",
        "Triwulan I", "Triwulan II", "Triwulan III", "Triwulan IV",
        "Semester I", "Semester II",
    ]
    for p in candidates:
        if normalize_text(p) in low:
            periods.append(p)
    return periods


def extract_requested_trend_years(question: str) -> int | None:
    """
    Ekstrak jumlah tahun yang diminta untuk analisis tren.
    Contoh: '5 tahun terakhir' → 5, 'tiga tahun terakhir' → 3.
    """
    word_to_num = {
        "satu": 1, "dua": 2, "tiga": 3, "empat": 4, "lima": 5,
        "enam": 6, "tujuh": 7, "delapan": 8, "sembilan": 9, "sepuluh": 10,
    }
    qn = normalize_text(question)

    m = re.search(r"\b(\d+)\s+tahun\s+terakhir\b", qn)
    if m:
        try:
            return int(m.group(1))
        except ValueError:
            pass

    for word, num in word_to_num.items():
        if f"{word} tahun terakhir" in qn:
            return num

    m2 = re.search(r"\bselama\s+(\d+)\s+tahun\s+terakhir\b", qn)
    if m2:
        try:
            return int(m2.group(1))
        except ValueError:
            pass

    return None


# ---------------------------------------------------------------------------
# Sort key temporal
# ---------------------------------------------------------------------------

def latest_sort_key(record: Dict) -> Tuple[int, int]:
    """
    Kembalikan (tahun, rank_periode) untuk sorting temporal.
    Record dengan data lebih baru → tuple lebih besar.
    """
    year = record.get("year")
    if not isinstance(year, int):
        if isinstance(record.get("year_end"), int):
            year = record["year_end"]
        elif isinstance(record.get("year_start"), int):
            year = record["year_start"]
        else:
            year = 0
    period = str(record.get("period") or "").strip()
    period_rank = PERIOD_ORDER.get(period, 0)
    return int(year or 0), int(period_rank)


# ---------------------------------------------------------------------------
# Penomoran & format angka
# ---------------------------------------------------------------------------

def format_id_number(value: float, decimals: int = 2) -> str:
    """Format angka dengan pemisah ribuan gaya Indonesia (titik = ribuan, koma = desimal)."""
    s = f"{value:,.{decimals}f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def humanize_unit_value(value: Any, unit: str) -> str:
    """
    Konversi nilai numerik + satuan ke teks yang lebih mudah dibaca.
    Contoh: 25000.0 + 'ribu orang' → '(sekitar 25,00 juta orang)'
    """
    try:
        num = float(value)
    except (TypeError, ValueError):
        return ""

    unit_norm = str(unit or "").strip().lower()

    if "ribu orang" in unit_norm:
        return f"(sekitar {format_id_number(num / 1_000.0, 2)} juta orang)"

    if unit_norm == "orang":
        if num >= 1_000_000:
            return f"(sekitar {format_id_number(num / 1_000_000.0, 2)} juta orang)"
        if num >= 1_000:
            return f"(sekitar {format_id_number(num / 1_000.0, 2)} ribu orang)"

    if "rupiah" in unit_norm:
        if num >= 1_000_000_000_000:
            return f"(sekitar Rp{format_id_number(num / 1_000_000_000_000.0, 2)} triliun)"
        if num >= 1_000_000_000:
            return f"(sekitar Rp{format_id_number(num / 1_000_000_000.0, 2)} miliar)"
        if num >= 1_000_000:
            return f"(sekitar Rp{format_id_number(num / 1_000_000.0, 2)} juta)"

    if "hektare" in unit_norm or "hektar" in unit_norm:
        if num >= 1_000_000:
            return f"(sekitar {format_id_number(num / 1_000_000.0, 2)} juta hektare)"
        if num >= 1_000:
            return f"(sekitar {format_id_number(num / 1_000.0, 2)} ribu hektare)"

    return ""


def enrich_readable_numbers(text: str, records: Iterable[Dict]) -> str:
    """
    Sebelumnya: sisipkan teks humanized di belakang angka+satuan.
    Sekarang: dinonaktifkan karena AI Analyst sudah diberi instruksi
    untuk menulis konversi langsung dalam jawabannya.
    Fungsi ini dipertahankan agar tidak perlu mengubah caller.
    """
    return text


def normalize_editorial_labels(text: str) -> str:
    """Standarisasi label indikator dalam teks output."""
    out = text.replace("Persentase Penduduk Miskin (P0)", "Persentase Penduduk Miskin")
    out = out.replace("persentase penduduk miskin (p0)", "persentase penduduk miskin")
    return out


# ---------------------------------------------------------------------------
# Utilitas record
# ---------------------------------------------------------------------------

def build_record_text(record: Dict) -> str:
    """Gabungkan semua field record menjadi satu string teks untuk indexing/scoring."""
    parts: List[str] = []

    scalar_keys = [
        "text", "title", "dataset_id", "topic_primary", "topic_secondary",
        "area_name", "area_level", "area_code", "series_label",
        "breakdown_label", "breakdown_value", "subgroup_label", "subgroup_value",
        "unit", "source", "source_file", "period",
    ]
    for key in scalar_keys:
        value = record.get(key)
        if value not in (None, ""):
            parts.append(str(value))

    for key in ["source_files", "download_urls", "periods", "keywords"]:
        value = record.get(key)
        if isinstance(value, list):
            parts.extend(str(v) for v in value if v not in (None, ""))

    metadata = record.get("metadata") or {}
    if isinstance(metadata, dict):
        for k, v in metadata.items():
            if v not in (None, "", []):
                parts.append(f"{k} {v}")

    if record.get("value") is not None:
        parts.append(str(record["value"]))

    for key in ["year", "year_start", "year_end"]:
        value = record.get(key)
        if value not in (None, ""):
            parts.append(str(value))

    return " ".join(parts)


def normalize_record(record: Dict, idx: int) -> Dict:
    """Pastikan semua field wajib ada dengan nilai default yang aman."""
    obj = dict(record)
    defaults = {
        "id": f"row_{idx}",
        "doc_type": "atomic",
        "text": "", "title": "", "dataset_id": "",
        "topic_primary": "", "topic_secondary": "",
        "area_level": "", "area_name": "", "area_code": "",
        "series_label": "", "breakdown_label": "", "breakdown_value": "",
        "subgroup_label": "", "subgroup_value": "",
        "unit": "", "source": "", "source_file": "",
        "source_files": [], "download_url": "", "download_urls": [],
        "period": "", "periods": [], "keywords": [], "metadata": {},
    }
    for key, default in defaults.items():
        obj.setdefault(key, default)
    return obj


def choose_best_download(record: Dict) -> str:
    """Pilih satu URL download terbaik dari record."""
    if record.get("download_url"):
        return str(record["download_url"])
    urls = record.get("download_urls") or []
    return str(urls[-1]) if urls else ""


def summarize_sources(records: Iterable[Dict]) -> Tuple[str, List[str]]:
    """Kumpulkan judul dan URL download unik dari daftar record."""
    titles: List[str] = []
    downloads: List[str] = []
    for record in records:
        title = str(record.get("title") or "").strip()
        if title and title not in titles:
            titles.append(title)
        dl = choose_best_download(record)
        if dl and dl not in downloads:
            downloads.append(dl)
    return "; ".join(titles), downloads


def compact_json(data: Any) -> str:
    """Serialisasi JSON kompak untuk dikirim ke AI."""
    return json.dumps(data, ensure_ascii=False, separators=(",", ":"))
