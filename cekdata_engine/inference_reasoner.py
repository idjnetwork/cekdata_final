"""
inference_reasoner.py
=====================
AI yang bertugas berpikir ketika data langsung tidak tersedia:
"Data ini tidak ada, tapi pertanyaan ini bisa didekati dengan proxy data apa?"

Contoh:
  Pertanyaan: "Apakah MBG berhasil menambah 1 juta lapangan kerja?"
  Data langsung: tidak ada (tidak ada dataset 'dampak MBG terhadap lapangan kerja')
  Reasoning: klaim ini bisa diuji dengan melihat perubahan jumlah penduduk bekerja
             atau TPT pada periode yang sama
  Output: query alternatif → "jumlah penduduk bekerja Indonesia 2024 2025"

Output layer ini HANYA berupa query alternatif (string).
Tidak ada konteks yang dikirim ke ai_analyst — ai_analyst akan menerima
kandidat baru dari retrieval ulang dan menganalisis seperti biasa.

Model dikonfigurasi via env var REASONER_MODEL.
Default: model yang sama dengan OPENAI_MODEL (GPT-4) karena reasoning
membutuhkan kemampuan penalaran yang cukup dalam.
"""
from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass, field
from typing import List, Optional

from .data_gap_detector import GapAssessment
from .models import QueryProfile

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class ReasonerError(RuntimeError):
    """Gagal mendapatkan reasoning yang valid."""


# ---------------------------------------------------------------------------
# Output model
# ---------------------------------------------------------------------------

@dataclass
class ReasoningResult:
    """
    Hasil reasoning dari inference_reasoner.

    Jika found_proxy=True, alternative_queries berisi query baru untuk
    dikirim ke retriever. Jika False, tidak ada yang bisa dilakukan.
    """
    found_proxy: bool
    alternative_queries: List[str] = field(default_factory=list)
    proxy_rationale: str = ""     # penjelasan singkat mengapa proxy ini relevan
    raw_response: str = ""


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """Kamu adalah sistem reasoning untuk mesin verifikasi data statistik Indonesia.

Tugasmu dipanggil ketika data yang persis sesuai pertanyaan tidak tersedia dalam corpus.
Kamu harus berpikir: apakah ada data proxy atau data pendekatan yang bisa digunakan
untuk menguji klaim atau menjawab pertanyaan secara tidak langsung?

CONTOH REASONING:
- Klaim "program X menambah 1 juta lapangan kerja" → tidak ada data 'dampak program X',
  tapi bisa diuji dengan: perubahan jumlah penduduk bekerja, perubahan TPT,
  perubahan TPAK pada periode yang sama
- Klaim "inflasi turunkan daya beli masyarakat miskin" → tidak ada data gabungan itu,
  tapi bisa dilihat dari: tren garis kemiskinan (komponen non-makanan), inflasi umum,
  persentase penduduk miskin
- Pertanyaan tentang "kesejahteraan" secara umum → bisa didekati dengan kemiskinan,
  pengangguran, PDRB per kapita

DATA YANG TERSEDIA DALAM CORPUS:
- Kemiskinan: persentase penduduk miskin (P0), jumlah penduduk miskin, garis kemiskinan
- Ketenagakerjaan: TPT (tingkat pengangguran terbuka), jumlah penduduk bekerja, TPAK
- Ekonomi: PDRB, laju pertumbuhan ekonomi
- Per wilayah: 34 provinsi + nasional, breakdown perkotaan/perdesaan
- Per periode: Maret/September (kemiskinan), Februari/Agustus (ketenagakerjaan)

ATURAN:
1. Jika ada proxy yang masuk akal secara logis → berikan query alternatif yang spesifik
2. Jika tidak ada proxy yang relevan sama sekali → nyatakan tidak bisa didekati
3. Query alternatif harus spesifik: sebutkan indikator + wilayah + rentang tahun
4. Maksimal 3 query alternatif — pilih yang paling relevan
5. Jangan membuat-buat hubungan yang tidak logis hanya agar ada jawabannya

OUTPUT wajib JSON valid (tidak ada teks lain):
{
  "found_proxy": true | false,
  "alternative_queries": [
    "jumlah penduduk bekerja Indonesia 2023 2024",
    "tingkat pengangguran terbuka Indonesia 2023 2024"
  ],
  "proxy_rationale": "Penjelasan singkat mengapa proxy ini relevan untuk menjawab klaim"
}

Jika found_proxy false, alternative_queries boleh array kosong dan
proxy_rationale berisi penjelasan singkat mengapa tidak bisa didekati.
"""


# ---------------------------------------------------------------------------
# OpenAI client — shared singleton via openai_client.py
# ---------------------------------------------------------------------------

def _get_client():
    from .openai_client import get_openai_client, OpenAIClientError
    try:
        return get_openai_client()
    except OpenAIClientError as exc:
        raise ReasonerError(str(exc)) from exc


# ---------------------------------------------------------------------------
# JSON extraction
# ---------------------------------------------------------------------------

def _extract_json(text: str) -> dict:
    text = (text or "").strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if not match:
        raise ReasonerError("Response reasoner bukan JSON valid.")
    return json.loads(match.group(0))


# ---------------------------------------------------------------------------
# Prompt builder
# ---------------------------------------------------------------------------

def _build_user_prompt(
    question: str,
    profile: QueryProfile,
    gap: GapAssessment,
) -> str:
    parts = [
        f"Pertanyaan asli: {question}",
        f"Gap yang terdeteksi: {gap.reason}",
    ]
    if profile.primary_indicator:
        parts.append(f"Indikator yang dicari: {profile.primary_indicator}")
    if profile.area_targets:
        parts.append(f"Wilayah: {', '.join(profile.area_targets)}")
    if profile.explicit_years:
        parts.append(f"Tahun: {', '.join(str(y) for y in profile.explicit_years)}")
    if gap.top_candidate_indicator:
        parts.append(f"Kandidat terbaik yang ditemukan: indikator '{gap.top_candidate_indicator}'")

    parts.append(
        "\nBerdasarkan informasi di atas, apakah ada data proxy yang bisa digunakan "
        "untuk menjawab atau menguji klaim ini secara tidak langsung?"
    )
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Fungsi utama
# ---------------------------------------------------------------------------

def reason_alternative_queries(
    question: str,
    profile: QueryProfile,
    gap: GapAssessment,
) -> ReasoningResult:
    """
    Minta AI berpikir: data proxy apa yang bisa menggantikan data langsung
    yang tidak tersedia?

    Mengembalikan ReasoningResult dengan alternative_queries siap dikirim
    ke retriever. Jika gagal atau tidak ada proxy, found_proxy=False.
    """
    model = os.getenv(
        "REASONER_MODEL",
        os.getenv("OPENAI_MODEL", "gpt-4.1-mini-2025-04-14"),
    ).strip()

    try:
        client = _get_client()
        response = client.chat.completions.create(
            model=model,
            temperature=0.2,      # sedikit lebih kreatif dari analyst (0)
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": _build_user_prompt(question, profile, gap)},
            ],
        )
        raw = response.choices[0].message.content or "{}"
        data = _extract_json(raw)

        found = bool(data.get("found_proxy", False))
        queries = [
            str(q).strip()
            for q in (data.get("alternative_queries") or [])
            if str(q).strip()
        ][:3]   # maksimal 3

        result = ReasoningResult(
            found_proxy=found and bool(queries),
            alternative_queries=queries,
            proxy_rationale=str(data.get("proxy_rationale") or ""),
            raw_response=raw,
        )

        if result.found_proxy:
            log.info(
                f"Reasoning berhasil: {len(queries)} query alternatif ditemukan. "
                f"Rationale: {result.proxy_rationale[:100]}"
            )
        else:
            log.info(
                f"Reasoning: tidak ada proxy yang relevan. "
                f"Alasan: {result.proxy_rationale[:100]}"
            )

        return result

    except Exception as exc:
        log.warning(f"inference_reasoner gagal: {exc}. Fallback ke tidak ada proxy.")
        return ReasoningResult(
            found_proxy=False,
            proxy_rationale=f"Reasoning gagal: {exc}",
        )
