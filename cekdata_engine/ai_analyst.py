"""
ai_analyst.py
=============
Bertanggung jawab atas komunikasi dengan model AI (OpenAI GPT-4).

Tanggung jawab layer ini:
  - Membangun system prompt dan user prompt
  - Memanggil OpenAI API
  - Mem-parse respons JSON mentah

Layer ini TIDAK memvalidasi kebenaran output — itu tanggung jawab validator.py.
Layer ini TIDAK tahu apa-apa tentang corpus atau scoring.
"""
from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List

from .constants import ALLOWED_JUDGMENTS
from .models import Candidate, QueryProfile
from .text_utils import choose_best_download, compact_json


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class AIAnalysisError(RuntimeError):
    """Gagal mendapatkan respons valid dari model AI."""


# ---------------------------------------------------------------------------
# OpenAI client — shared singleton via openai_client.py
# ---------------------------------------------------------------------------

def _get_openai_client():
    from .openai_client import get_openai_client, OpenAIClientError
    try:
        return get_openai_client()
    except OpenAIClientError as exc:
        raise AIAnalysisError(str(exc)) from exc


# ---------------------------------------------------------------------------
# Prompt builders
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = (
    "Anda adalah analis verifikasi data untuk CekData AI. "
    "Gunakan hanya kandidat data yang diberikan. Jangan memakai pengetahuan di luar kandidat. "
    "Jika bukti tidak cukup, pilih 'Tidak dapat diverifikasi'. "
    "Utamakan kesesuaian indikator, wilayah, periode, dan jenis pertanyaan. "

    "Aturan indikator: untuk frasa umum seperti 'kondisi kemiskinan', 'angka kemiskinan', "
    "'kemiskinan membaik', atau 'kemiskinan memburuk', utamakan indikator "
    "'Persentase Penduduk Miskin' atau padanannya seperti 'Persentase Penduduk Miskin (P0)'. "
    "Gunakan 'Jumlah Penduduk Miskin' hanya jika pertanyaan eksplisit tentang jumlah orang "
    "atau jika kandidat persentase tidak tersedia. "
    "Jangan gunakan 'Garis Kemiskinan' untuk menyimpulkan kondisi kemiskinan membaik atau "
    "memburuk kecuali pertanyaan memang eksplisit tentang garis kemiskinan. "

    "Untuk query 'tahun ini' atau 'terbaru', pilih periode paling mutakhir yang tersedia "
    "dan, jika perlu membandingkan, gunakan periode yang sebanding pada tahun sebelumnya. "
    "Untuk query 'beberapa tahun terakhir' atau tren, fokus ke rentang paling mutakhir "
    "yang tersedia, bukan rentang lama, kecuali data baru tidak tersedia. "
    "Untuk query komparatif seperti wilayah vs nasional, jangan beri penilaian tegas "
    "jika salah satu sisi pembanding tidak tersedia. "

    "Sangat penting: untuk klaim pemerintah, pejabat, atau aktor publik yang menyatakan "
    "sebuah program berhasil, efektif, menyebabkan, menambah, menurunkan, atau membuktikan "
    "sesuatu — Anda harus bersikap kritis. "
    "Kecocokan angka tidak otomatis membuktikan hubungan sebab akibat. "
    "Jika data hanya menunjukkan perubahan indikator agregat, isi peringatan_editorial "
    "secara substantif, bukan normatif. "
    "Peringatan editorial harus menjelaskan keterbatasan bukti, mempertanyakan lompatan "
    "logika klaim, dan mengajukan 2 sampai 4 pertanyaan kritis yang konkret untuk "
    "follow up jurnalistik. "
    "Jika kandidat data memungkinkan, gunakan pembanding periode sebelumnya untuk menguji "
    "apakah tren serupa sudah muncul sebelum program yang diklaim. "

    "Aturan KRITIS untuk peringatan_editorial saat data tidak cukup: "
    "Jika Anda memilih penilaian 'Tidak dapat diverifikasi' karena data yang dibutuhkan "
    "tidak tersedia atau tidak relevan, peringatan_editorial WAJIB diisi dengan saran "
    "langkah verifikasi yang spesifik dan kontekstual terhadap pertanyaan. "
    "Jangan hanya bilang 'data tidak ada'. Jelaskan: "
    "(1) data spesifik apa yang sebenarnya dibutuhkan untuk menjawab pertanyaan ini; "
    "(2) ke mana jurnalis bisa mencari data tersebut (BPS, kementerian terkait, dsb); "
    "(3) pertanyaan kritis apa yang bisa diajukan ke pihak yang mengklaim; "
    "(4) apakah ada pendekatan alternatif untuk menguji klaim ini secara tidak langsung. "
    "Semakin spesifik dan kontekstual saran Anda, semakin berguna bagi jurnalis. "

    "Field alasan harus singkat, natural, dan maksimal 4 kalimat. "
    "Field alasan harus menjelaskan mengapa bukti cukup atau tidak cukup, "
    "bukan mengulang aturan teknis internal sistem. "
    "Hindari frasa seperti 'perbandingan wilayah harus' atau 'indikator harus sama' "
    "kecuali benar-benar perlu; jika perlu, ubah menjadi penjelasan editorial yang "
    "mudah dipahami. "

    "Aturan penulisan angka: SELALU sertakan konversi yang mudah dibaca dalam kurung "
    "setelah angka asli. Pembaca non-teknis harus langsung paham skala angkanya. "
    "Panduan konversi: "
    "- Satuan 'ribu orang' atau 'ribu jiwa': konversi ke juta. "
    "  Contoh: '23.359,71 ribu orang (sekitar 23,36 juta jiwa)'. "
    "  Contoh: '1.200 ribu orang (sekitar 1,2 juta jiwa)'. "
    "- Satuan 'orang' atau 'jiwa' dengan angka besar: konversi ke juta atau ribu. "
    "  Contoh: '144.642.004 orang (sekitar 144,6 juta jiwa)'. "
    "  Contoh: '850.000 orang (sekitar 850 ribu jiwa)'. "
    "- Satuan 'rupiah/kapita/bulan' atau 'rupiah': konversi ke ribu, juta, atau miliar. "
    "  Contoh: '550.458 rupiah/kapita/bulan (sekitar Rp550,5 ribu)'. "
    "  Contoh: '2.500.000 rupiah (sekitar Rp2,5 juta)'. "
    "- Satuan 'miliar rupiah': konversi ke triliun jika besar. "
    "  Contoh: '15.200 miliar rupiah (sekitar Rp15,2 triliun)'. "
    "- Satuan 'ton': konversi ke ribu ton atau juta ton jika besar. "
    "  Contoh: '1.250.000 ton (sekitar 1,25 juta ton)'. "
    "- Satuan 'hektare' atau 'ha': konversi ke ribu atau juta hektare. "
    "  Contoh: '350.000 hektare (sekitar 350 ribu hektare)'. "
    "- Satuan 'unit' atau 'buah': konversi ke ribu atau juta. "
    "  Contoh: '25.000 unit (sekitar 25 ribu unit)'. "
    "- Persentase: tidak perlu konversi, tapi sertakan 'poin persentase' jika "
    "  menjelaskan selisih. Contoh: 'turun dari 9,36% ke 9,03% (turun 0,33 poin persentase)'. "
    "Prinsip umum: jika angka punya lebih dari 4 digit, PASTI butuh konversi. "
    "Gunakan 'sekitar' untuk pembulatan. Tulis dalam format Indonesia (titik untuk ribuan, "
    "koma untuk desimal). "

    "Output wajib berupa JSON valid saja."
)

OUTPUT_CONTRACT = {
    "claim": "Ringkas dan jelas. Untuk pertanyaan non klaim, boleh berupa ringkasan temuan utama.",
    "indicator_used": "Nama indikator utama yang benar benar dipakai.",
    "records_used": "Array candidate_id yang dipakai dalam analisis.",
    "temuan_data": (
        "Narasi angka dan pembanding utamanya. "
        "Untuk pertanyaan tren X tahun terakhir, paparkan tahun-tahun dalam rentang itu "
        "secara eksplisit, bukan hanya awal dan akhir."
    ),
    "konteks_penting": "Konteks pemilihan periode, indikator, atau keterbatasan data.",
    "penilaian": "Salah satu dari allowed_judgments.",
    "alasan": (
        "Alasan editorial singkat, natural, maksimal 4 kalimat, dan harus menjelaskan "
        "kenapa bukti cukup atau tidak cukup tanpa memakai bahasa teknis internal sistem."
    ),
    "peringatan_editorial": (
        "Kosongkan jika tidak perlu. Tetapi untuk klaim sebab akibat, klaim keberhasilan "
        "program, atau klaim pemerintah yang melompat dari data ke kesimpulan, "
        "field ini wajib diisi dengan catatan kritis dan pertanyaan follow up konkret. "
        "Juga isi jika penilaian 'Tidak dapat diverifikasi' — jelaskan data apa yang "
        "dibutuhkan dan langkah verifikasi apa yang bisa dilakukan jurnalis."
    ),
    "sumber": "Judul sumber paling relevan.",
    "unduh_data": "Satu link unduh paling relevan jika ada.",
}


def _candidate_for_prompt(candidate: Candidate, rank: int) -> Dict[str, Any]:
    """Serialisasi Candidate ke bentuk yang akan dikirim ke AI."""
    r = candidate.record
    return {
        "rank": rank,
        "candidate_id": r.get("id"),
        "score": round(candidate.score, 4),
        "doc_type": r.get("doc_type"),
        "title": r.get("title"),
        "dataset_id": r.get("dataset_id"),
        "topic_primary": r.get("topic_primary"),
        "topic_secondary": r.get("topic_secondary"),
        "area_level": r.get("area_level"),
        "area_name": r.get("area_name"),
        "area_code": r.get("area_code"),
        "year": r.get("year"),
        "year_start": r.get("year_start"),
        "year_end": r.get("year_end"),
        "period": r.get("period"),
        "periods": r.get("periods"),
        "series_label": r.get("series_label"),
        "breakdown_label": r.get("breakdown_label"),
        "breakdown_value": r.get("breakdown_value"),
        "subgroup_label": r.get("subgroup_label"),
        "subgroup_value": r.get("subgroup_value"),
        "unit": r.get("unit"),
        "value": r.get("value"),
        "source": r.get("source"),
        "source_file": r.get("source_file"),
        "source_files": r.get("source_files"),
        "download_url": choose_best_download(r),
        "download_urls": r.get("download_urls"),
        "keywords": r.get("keywords", []),
        "metadata": r.get("metadata", {}),
        "text": (r.get("text") or "")[:1600],
        "retrieval_notes": candidate.retrieval_notes,
        "keyword_hits": candidate.keyword_hits,
        "metadata_hits": candidate.metadata_hits,
    }


def build_user_prompt(
    question: str,
    profile: QueryProfile,
    candidates: List[Candidate],
    original_question: str = "",
) -> str:
    payload = {
        "question": question,
    }

    # Jika pertanyaan asli berbeda dari yang direformulasi, sertakan sebagai konteks
    # Ini penting agar AI tahu bahwa pertanyaan sebenarnya adalah klaim kausal,
    # bukan sekadar pertanyaan data
    if original_question and original_question.strip() != question.strip():
        payload["original_question"] = original_question
        payload["context_note"] = (
            "Pertanyaan asli pengguna (original_question) mungkin mengandung klaim kausal, "
            "klaim pejabat, atau konteks politik yang tidak ada di pertanyaan yang direformulasi. "
            "Gunakan original_question untuk memahami NIAT sebenarnya dan menjawab secara kritis "
            "jika ada klaim keberhasilan program atau hubungan sebab-akibat. "
            "Yang perlu diuji bukan hanya angkanya, tapi juga KLAIM di balik angka itu."
        )

    payload["query_profile"] = {
        "query_type": profile.query_type,
        "needs_latest": profile.needs_latest,
        "needs_recent_range": profile.needs_recent_range,
        "explicit_years": profile.explicit_years,
        "periods": profile.periods,
        "indicator_targets": profile.indicator_targets,
        "primary_indicator": profile.primary_indicator,
        "area_targets": profile.area_targets,
        "comparison_targets": profile.comparison_targets,
        "breakdown_targets": profile.breakdown_targets,
        "ambiguous_indicator": profile.ambiguous_indicator,
        "quantity_hint": profile.quantity_hint,
        "generated_queries": profile.generated_queries,
        "keyword_targets": profile.keyword_targets,
        "metadata_filters": profile.metadata_filters,
    }
    payload["editorial_rules"] = {
        "allowed_judgments": sorted(ALLOWED_JUDGMENTS),
        "required_output_fields": list(OUTPUT_CONTRACT.keys()),
        "special_guidance": {
            "claim_queries": "Jika pertanyaan berbentuk klaim, simpulkan apakah klaim didukung data.",
            "trend_queries": (
                "Untuk tren, fokus pada data paling mutakhir yang tersedia. "
                "WAJIB gunakan data dari tahun-tahun BERURUTAN — jangan lompat tahun. "
                "Jika data terbaru 2025, maka paparkan 2025, 2024, 2023, 2022, 2021 "
                "(minimal 3-5 titik data berurutan). "
                "Jika pertanyaan menyebut X tahun terakhir, gunakan record atomic dengan "
                "cakupan tahun unik sebanyak yang diminta. "
                "Paparkan SETIAP tahun dalam rentang secara eksplisit di temuan_data, "
                "jangan hanya menyebut titik awal dan akhir. "
                "Jangan mengandalkan trend summary saja — gunakan record atomic per tahun. "
                "Untuk pertanyaan tren tanpa klaim (seperti 'bagaimana tren X'), "
                "fokus pada penyajian data, bukan penilaian benar/salah."
            ),
            "comparison_queries": (
                "Untuk perbandingan, gunakan kandidat yang benar benar sebanding "
                "dalam indikator dan periode."
            ),
        },
    }
    payload["candidate_data"] = [_candidate_for_prompt(c, i) for i, c in enumerate(candidates, 1)]
    payload["output_contract"] = OUTPUT_CONTRACT
    return compact_json(payload)


# ---------------------------------------------------------------------------
# JSON extraction dari respons model
# ---------------------------------------------------------------------------

def _extract_json_block(text: str) -> Dict[str, Any]:
    text = (text or "").strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if not match:
        raise AIAnalysisError("Respons model bukan JSON valid.")
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError as exc:
        raise AIAnalysisError(f"Gagal parse JSON dari respons model: {exc}") from exc


# ---------------------------------------------------------------------------
# Fungsi utama
# ---------------------------------------------------------------------------

def call_ai_analysis(
    question: str,
    profile: QueryProfile,
    candidates: List[Candidate],
    original_question: str = "",
) -> Dict[str, Any]:
    """
    Kirim pertanyaan + kandidat ke GPT-4, kembalikan dict hasil parse JSON.
    Melempar AIAnalysisError jika gagal.
    """
    client = _get_openai_client()
    model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini-2025-04-14").strip()

    try:
        response = client.chat.completions.create(
            model=model,
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": build_user_prompt(question, profile, candidates, original_question)},
            ],
        )
    except Exception as exc:
        raise AIAnalysisError(f"OpenAI API error: {exc}") from exc

    content = response.choices[0].message.content or "{}"
    parsed = _extract_json_block(content)
    parsed["raw_answer"] = content
    return parsed
