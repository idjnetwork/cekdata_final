"""
intent_router.py
================
Layer AI pertama yang menyambut pertanyaan sebelum masuk ke pipeline retrieval.

Tugas:
  1. Memahami niat, konteks, dan kebutuhan data dari pertanyaan natural
  2. Memutuskan indikator, wilayah, tahun, dan jenis query yang diperlukan
  3. Mereformulasi pertanyaan menjadi lebih presisi untuk retrieval
  4. Menolak pertanyaan yang sama sekali di luar topik data statistik Indonesia
  5. Balik tanya jika pertanyaan terlalu ambigu untuk dilanjutkan

Berbeda dari query_parser.py yang berbasis rule, layer ini menggunakan AI
sehingga bisa memahami konteks tersirat, bahasa tidak formal, dan klaim
yang membutuhkan inferensi untuk menentukan data apa yang relevan.

Model: dikonfigurasi via env var INTENT_MODEL
  Default: gpt-4o-mini (lebih cepat dan murah untuk routing)
"""
from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class IntentRouterError(RuntimeError):
    """Gagal mendapatkan IntentResult yang valid dari model."""


# ---------------------------------------------------------------------------
# Output model
# ---------------------------------------------------------------------------

@dataclass
class IntentResult:
    """
    Hasil pemahaman niat dari pertanyaan user.
    Dihasilkan oleh intent_router, dikonsumsi oleh query_parser dan engine.
    """

    # "ok" → lanjut pipeline
    # "clarify" → perlu balik tanya, isi clarification_question
    # "off_topic" → di luar topik, isi rejection_message
    # "error" → router gagal, fallback ke pipeline tanpa enrichment
    status: str = "ok"

    original_question: str = ""

    # Pertanyaan yang direformulasi — lebih presisi, siap untuk retrieval
    # "kemiskinan turun nggak?" → "Benarkah persentase penduduk miskin Indonesia menurun?"
    reformulated_question: str = ""

    # Metadata yang dipahami AI
    indicators: List[str] = field(default_factory=list)
    areas: List[str] = field(default_factory=list)
    years: List[int] = field(default_factory=list)
    periods: List[str] = field(default_factory=list)
    query_type: str = "claim"         # "claim" | "trend" | "comparison" | "latest"
    is_claim: bool = True             # AI menentukan: apakah ini klaim yang perlu penilaian?
    requires_comparison: bool = False
    comparison_entities: List[str] = field(default_factory=list)
    requires_trend: bool = False
    trend_years_requested: Optional[int] = None

    # Topik dalam bahasa natural — untuk logging dan debug
    understood_topic: str = ""

    # Tingkat kepercayaan AI (0.0–1.0)
    confidence: float = 1.0

    # Isi jika status == "clarify"
    clarification_question: str = ""

    # Isi jika status == "off_topic"
    rejection_message: str = ""

    # Breakdown demografis yang dipahami AI (usia, gender, pendidikan)
    demographic_filters: Dict[str, Any] = field(default_factory=dict)

    # Catatan penerjemahan konteks (untuk debug/transparansi)
    context_notes: str = ""

    raw_response: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "original_question": self.original_question,
            "reformulated_question": self.reformulated_question,
            "indicators": self.indicators,
            "areas": self.areas,
            "years": self.years,
            "periods": self.periods,
            "query_type": self.query_type,
            "is_claim": self.is_claim,
            "requires_comparison": self.requires_comparison,
            "comparison_entities": self.comparison_entities,
            "requires_trend": self.requires_trend,
            "trend_years_requested": self.trend_years_requested,
            "understood_topic": self.understood_topic,
            "confidence": self.confidence,
            "clarification_question": self.clarification_question,
            "rejection_message": self.rejection_message,
            "demographic_filters": self.demographic_filters,
            "context_notes": self.context_notes,
        }


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """Kamu adalah sistem routing untuk mesin verifikasi data statistik Indonesia bernama CekData AI.

Tugasmu adalah memahami pertanyaan atau klaim dari pengguna — termasuk yang tidak formal,
ambigu, atau implisit — lalu memutuskan data apa yang perlu dicari untuk menjawabnya.

═══ TAKSONOMI DATA BPS YANG TERSEDIA ═══

Kamu harus berpikir dalam kerangka bagaimana BPS mengorganisasi datanya.
Setiap indikator punya dimensi (breakdown) yang bisa dipanggil.

KEMISKINAN (periode: Maret dan September):
  Indikator utama:
  - "Persentase Penduduk Miskin" (P0) — ukuran paling umum, headcount ratio
  - "Indeks Kedalaman Kemiskinan" (P1) — seberapa jauh rata-rata pengeluaran miskin dari garis kemiskinan
  - "Indeks Keparahan Kemiskinan" (P2) — mengukur ketimpangan antar penduduk miskin
  - "Jumlah Penduduk Miskin" — angka absolut dalam ribuan
  - "Garis Kemiskinan" — batas pengeluaran per kapita per bulan (rupiah)
  Breakdown: perkotaan/perdesaan, provinsi, nasional
  Catatan: "kemiskinan menurun" secara umum → pakai P0. "Kemiskinan makin parah" → bisa P1 atau P2.
  "Masih banyak yang miskin" → Jumlah Penduduk Miskin. "Biaya hidup minimum" → Garis Kemiskinan.

KETENAGAKERJAAN (periode: Februari dan Agustus):
  Indikator utama:
  - "Tingkat Pengangguran Terbuka" (TPT) — persentase pengangguran dari angkatan kerja
  - "Jumlah Penduduk Bekerja" — angka absolut
  - "Jumlah Pengangguran" — angka absolut
  - "Tingkat Partisipasi Angkatan Kerja" (TPAK) — persentase angkatan kerja dari penduduk usia kerja
  Breakdown: perkotaan/perdesaan, provinsi, jenis kelamin, kelompok umur (15-19, 20-24, 25-29, 30-34, 35-39, 40-44, 45-49, 50-54, 55-59, 60+), pendidikan
  Catatan: "lapangan kerja bertambah" → Jumlah Penduduk Bekerja. "Pengangguran turun" → bisa TPT atau Jumlah Pengangguran.

EKONOMI:
  - PDRB (Produk Domestik Regional Bruto) — nilai ekonomi per wilayah
  - Laju Pertumbuhan Ekonomi — persentase pertumbuhan PDRB
  - Inflasi — perubahan harga konsumen

KEPENDUDUKAN:
  - Jumlah penduduk, kepadatan, rasio jenis kelamin, piramida penduduk

═══ ATURAN PENERJEMAHAN KONTEKS ═══

Tugasmu yang PALING PENTING: menerjemahkan bahasa sehari-hari, istilah populer, dan
klaim politik menjadi indikator dan dimensi BPS yang tepat. Kamu TIDAK boleh meneruskan
istilah populer apa adanya — kamu harus menerjemahkannya.

1. ISTILAH DEMOGRAFIS → breakdown usia BPS:
   Jangan pernah meneruskan label generasi sebagai indikator. Terjemahkan ke rentang usia
   berdasarkan TAHUN LAHIR, lalu hitung usia di tahun berjalan.
   - "Gen Z" → lahir 1996-2012 → hitung usia di tahun ini → cocokkan ke bucket BPS
   - "Milenial" / "Generasi Y" → lahir 1981-1995
   - "Gen X" → lahir 1965-1980
   - "Baby boomer" → lahir sebelum 1965
   - "Usia produktif" → kelompok umur 15-64 tahun
   - "Pemuda" / "anak muda" → kelompok umur 15-29 tahun
   - "Lansia" / "penduduk tua" → kelompok umur 60+
   - "Usia sekolah" → kelompok umur 7-18 tahun (konteks pendidikan)
   Bucket BPS (Sakernas): 15-19, 20-24, 25-29, 30-34, 35-39, 40-44, 45-49, 50-54, 55-59, 60+
   Jika pengguna bilang "Gen Z banyak yang nganggur", terjemahkan ke:
   indikator "Tingkat Pengangguran Terbuka", breakdown kelompok umur 15-29.
   PENTING: saat menerjemahkan istilah generasi, SELALU isi context_notes dengan
   rentang usia BPS yang digunakan. Contoh: "Gen Z diterjemahkan ke kelompok usia
   15-19, 20-24, 25-29 berdasarkan data BPS." Ini supaya pembaca tahu persis
   rentang usia mana yang dipakai dalam data.

2. ISTILAH PROGRAM/KEBIJAKAN → indikator dampak yang bisa diukur:
   Jangan cari data tentang programnya — cari data tentang indikator yang diklaim terdampak.
   - "Makan Bergizi Gratis" / "MBG" → BUKAN soal makanan. Lihat konteks klaimnya:
     * "MBG berhasil kurangi kemiskinan" → Persentase Penduduk Miskin
     * "MBG tambah lapangan kerja" → Jumlah Penduduk Bekerja + TPT
     * "MBG turunkan stunting" → (belum ada di corpus, tapi sebutkan di indicators)
   - "Kartu Prakerja" → TPT, Jumlah Penduduk Bekerja
   - "BLT" / "Bansos" / "PKH" → Persentase Penduduk Miskin, Jumlah Penduduk Miskin
   - "IKN" / "pemindahan ibu kota" → PDRB Kalimantan Timur, laju pertumbuhan
   - "Hilirisasi nikel" → PDRB, ekspor (jika ada)
   Prinsip: baca APA yang diklaim berubah, bukan NAMA programnya.

3. ISTILAH EKONOMI POPULER → indikator BPS:
   - "Daya beli" / "daya beli turun" → Inflasi, Garis Kemiskinan
   - "Harga-harga naik" → Inflasi
   - "Ekonomi lesu" / "resesi" → Laju Pertumbuhan Ekonomi
   - "Ketimpangan" → Rasio Gini (jika ada), atau Indeks Kedalaman Kemiskinan (P1)
   - "PHK massal" / "banyak yang di-PHK" → TPT, Jumlah Pengangguran
   - "Bonus demografi" → TPAK, penduduk usia produktif
   - "Kelas menengah menyusut" → (pendekatan: Garis Kemiskinan, distribusi pengeluaran)

4. ISTILAH KEMISKINAN SPESIFIK:
   - "Kemiskinan ekstrem" → Persentase Penduduk Miskin dengan garis kemiskinan internasional
   - "Kemiskinan makin dalam" / "makin parah" → Indeks Kedalaman (P1) atau Keparahan (P2)
   - "Keluar dari kemiskinan" / "turun kelas" → Persentase Penduduk Miskin (P0) tren
   - "Rentan miskin" / "hampir miskin" → (pendekatan: P0 + Garis Kemiskinan)

═══ ATURAN PEMAHAMAN KLAIM ═══

Ketika pengguna menyampaikan KLAIM (bukan pertanyaan data murni), tugasmu adalah:
1. Identifikasi SUBJEK klaim — siapa yang mengklaim (pejabat? media? publik?)
2. Identifikasi PROPOSISI klaim — apa yang diklaim berubah/terjadi
3. Terjemahkan PROPOSISI ke indikator BPS yang bisa mengujinya
4. Jangan terjebak oleh nama program — fokus pada indikator dampak

Contoh penerjemahan klaim:
- "Prabowo bilang programnya sukses tambah lapangan kerja"
  → Subjek: klaim pejabat. Proposisi: lapangan kerja bertambah.
  → indicators: ["Jumlah Penduduk Bekerja", "Tingkat Pengangguran Terbuka"]
  → reformulasi: "Benarkah jumlah penduduk bekerja Indonesia meningkat pada periode terbaru?"

- "Katanya kemiskinan turun tapi kok rasanya makin susah"
  → Proposisi ganda: P0 turun vs daya beli turun
  → indicators: ["Persentase Penduduk Miskin", "Garis Kemiskinan", "Indeks Kedalaman Kemiskinan"]
  → reformulasi: "Bagaimana tren persentase penduduk miskin dan garis kemiskinan Indonesia terbaru?"

- "Gen Z paling banyak nganggur"
  → Proposisi: pengangguran tertinggi di kelompok usia muda
  → indicators: ["Tingkat Pengangguran Terbuka"]
  → breakdown kelompok umur: 15-29
  → reformulasi: "Benarkah tingkat pengangguran terbuka kelompok usia 15-29 tahun paling tinggi?"

═══ ATURAN STATUS ═══

- "ok": pertanyaan jelas, ada indikator statistik yang bisa dicari
- "clarify": terlalu ambigu untuk tahu data apa yang dicari
  (contoh: "bagaimana kondisi Indonesia?" — tidak ada indikator spesifik)
  PENTING: saat clarify, berikan clarification_question yang menyebutkan contoh pertanyaan
  yang bisa dijawab, misalnya: "Apakah maksudmu tentang kemiskinan, pengangguran, atau
  pertumbuhan ekonomi? Contoh: 'Bagaimana tren kemiskinan Indonesia 5 tahun terakhir?'"
- "off_topic": tidak berkaitan dengan data statistik Indonesia sama sekali
  (cuaca, resep, opini politik murni, dll.)
  CATATAN: pertanyaan tentang klaim pejabat, program pemerintah, atau perbandingan
  wilayah tetap relevan selama ada indikator statistik yang bisa diuji.

SANGAT PENTING: Kamu TIDAK BOLEH menilai apakah data untuk periode tertentu sudah
tersedia atau belum. Itu bukan tugasmu. Basis data kami diperbarui secara berkala
dan mungkin sudah memiliki data yang menurut pengetahuanmu belum ada.
Jika pertanyaan menyebut indikator, wilayah, dan periode yang spesifik — statusnya
selalu "ok", MESKIPUN kamu berpikir data periode itu belum dipublikasikan.
Contoh: "Berapa jumlah penduduk miskin September 2025?" → status "ok", BUKAN "clarify".
Ketersediaan data akan diperiksa oleh komponen lain dalam sistem.

═══ ATURAN REFORMULASI ═══

- Pertahankan niat asli pengguna, jangan ubah substansinya
- WAJIB terjemahkan istilah populer ke istilah BPS (lihat aturan penerjemahan di atas)
- Sebutkan indikator BPS yang spesifik, wilayah, dan periode jika bisa diinferensikan
- Gunakan bahasa Indonesia formal
- Untuk klaim kausal ("program X menyebabkan Y"), reformulasi ke
  "Benarkah [indikator] berubah [arah] pada periode [X]?" — jangan tambahkan klaim kausal baru
- Jika pertanyaan menyebut breakdown demografis, sertakan kelompok umur spesifik

═══ ATURAN is_claim ═══

Field is_claim menentukan apakah pertanyaan ini KLAIM yang perlu penilaian benar/salah,
atau PERTANYAAN DATA yang hanya minta informasi.

is_claim = true jika pengguna:
- Membuat pernyataan yang bisa benar atau salah ("kemiskinan turun", "pengangguran naik")
- Menanyakan kebenaran suatu klaim ("benarkah...", "apakah benar...")
- Mengutip klaim pejabat/pihak lain ("Prabowo bilang...", "pemerintah klaim...")
- Membandingkan dengan kesimpulan ("lebih baik", "membaik", "memburuk", "lebih tinggi")
- Mengaitkan program/kebijakan dengan hasil ("MBG berhasil...", "program X menyebabkan Y")

is_claim = false jika pengguna:
- Hanya bertanya data ("berapa kemiskinan di Aceh?")
- Minta tren tanpa kesimpulan ("bagaimana tren kemiskinan 5 tahun terakhir?")
- Minta perbandingan tanpa kesimpulan ("bandingkan kemiskinan Jatim dan Jateng")
- Bertanya deskriptif ("apa indikator kemiskinan terbaru?")

Contoh:
- "Bagaimana tren kemiskinan Aceh?" → is_claim: false (minta data tren)
- "Benarkah tren kemiskinan Aceh turun?" → is_claim: true (ada klaim "turun")
- "Bandingkan kemiskinan Jatim dan Jateng" → is_claim: false (minta data)
- "Benarkah kemiskinan lebih baik dibanding tahun lalu?" → is_claim: true (ada klaim "lebih baik")
- "Berapa jumlah penduduk miskin?" → is_claim: false (minta angka)
- "Prabowo klaim MBG buka 1 juta lapangan kerja" → is_claim: true (klaim pejabat)

═══ OUTPUT ═══

Output wajib JSON valid (tidak ada teks lain):
{
  "status": "ok" | "clarify" | "off_topic",
  "reformulated_question": "...",
  "indicators": ["nama indikator BPS yang spesifik"],
  "areas": ["Nama Wilayah"],
  "years": [2023, 2024],
  "periods": ["Maret"],
  "query_type": "claim" | "trend" | "comparison" | "latest",
  "is_claim": true | false,
  "requires_comparison": true | false,
  "comparison_entities": [],
  "requires_trend": true | false,
  "trend_years_requested": null,
  "understood_topic": "penjelasan singkat topik yang dipahami",
  "confidence": 0.95,
  "clarification_question": "",
  "rejection_message": "",
  "demographic_filters": {
    "age_groups": [],
    "gender": "",
    "education_level": ""
  },
  "context_notes": "catatan penerjemahan konteks yang dilakukan"
}"""


# ---------------------------------------------------------------------------
# OpenAI client — shared singleton via openai_client.py
# ---------------------------------------------------------------------------

def _get_client():
    from .openai_client import get_openai_client, OpenAIClientError
    try:
        return get_openai_client()
    except OpenAIClientError as exc:
        raise IntentRouterError(str(exc)) from exc


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
        raise IntentRouterError("Response router bukan JSON valid.")
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError as exc:
        raise IntentRouterError(f"Gagal parse JSON dari router: {exc}") from exc


# ---------------------------------------------------------------------------
# Fungsi utama
# ---------------------------------------------------------------------------

def route_intent(question: str) -> IntentResult:
    """
    Kirim pertanyaan ke AI router, kembalikan IntentResult.

    Jika router gagal (network error, model error, dsb.), kembalikan
    IntentResult dengan status "error" — engine akan fallback ke pipeline
    biasa tanpa enrichment dari intent router.
    """
    if not question or not question.strip():
        return IntentResult(
            status="clarify",
            original_question=question,
            clarification_question="Pertanyaan tidak boleh kosong.",
        )

    model = os.getenv(
        "INTENT_MODEL",
        os.getenv("OPENAI_MODEL", "gpt-4.1-mini-2025-04-14"),
    ).strip()

    try:
        client = _get_client()
        response = client.chat.completions.create(
            model=model,
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": question.strip()},
            ],
        )
        raw = response.choices[0].message.content or "{}"
        data = _extract_json(raw)

        status = str(data.get("status", "ok")).lower()
        if status not in {"ok", "clarify", "off_topic"}:
            status = "ok"

        years_raw = data.get("years") or []
        years = [int(y) for y in years_raw if str(y).isdigit()]

        result = IntentResult(
            status=status,
            original_question=question,
            reformulated_question=str(data.get("reformulated_question") or question).strip(),
            indicators=[str(i).strip() for i in (data.get("indicators") or []) if i],
            areas=[str(a).strip() for a in (data.get("areas") or []) if a],
            years=years,
            periods=[str(p).strip() for p in (data.get("periods") or []) if p],
            query_type=str(data.get("query_type") or "claim"),
            is_claim=bool(data.get("is_claim", True)),
            requires_comparison=bool(data.get("requires_comparison", False)),
            comparison_entities=[
                str(e) for e in (data.get("comparison_entities") or []) if e
            ],
            requires_trend=bool(data.get("requires_trend", False)),
            trend_years_requested=(
                int(data["trend_years_requested"])
                if data.get("trend_years_requested")
                else None
            ),
            understood_topic=str(data.get("understood_topic") or ""),
            confidence=float(data.get("confidence") or 1.0),
            clarification_question=str(data.get("clarification_question") or ""),
            rejection_message=str(data.get("rejection_message") or ""),
            demographic_filters=data.get("demographic_filters") or {},
            context_notes=str(data.get("context_notes") or ""),
            raw_response=raw,
        )

        log.info(
            f"IntentRouter: status={result.status} "
            f"confidence={result.confidence:.2f} "
            f"topic={result.understood_topic[:60]!r}"
        )
        return result

    except Exception as exc:
        log.warning(
            f"IntentRouter gagal: {exc}. Fallback ke pipeline tanpa enrichment."
        )
        return IntentResult(
            status="error",
            original_question=question,
            reformulated_question=question,
        )


# ---------------------------------------------------------------------------
# Helper: enrichment QueryProfile dari IntentResult
# ---------------------------------------------------------------------------

def enrich_query_profile_from_intent(
    profile,
    intent: IntentResult,
) -> None:
    """
    Perkaya QueryProfile yang sudah ada dengan metadata dari IntentResult.
    Modifikasi in-place — hanya isi field yang belum terisi oleh query_parser.

    Dipanggil dari engine setelah make_query_profile() dan sebelum retrieval.
    """
    if intent.status != "ok":
        return

    # Indikator dari intent hanya ditambahkan jika query_parser belum menemukan
    if not profile.primary_indicator and intent.indicators:
        from .text_utils import normalize_text
        profile.primary_indicator = normalize_text(intent.indicators[0])
        profile.indicator_targets = [
            normalize_text(i) for i in intent.indicators
        ]

    # Area dari intent — tambahkan yang belum ada
    for area in intent.areas:
        if area and area not in profile.area_targets:
            profile.area_targets.append(area)

    # Tahun dari intent — tambahkan yang belum ada
    for year in intent.years:
        if year and year not in profile.explicit_years:
            profile.explicit_years.append(year)

    # Periode dari intent
    for period in intent.periods:
        if period and period not in profile.periods:
            profile.periods.append(period)

    # Query type dari intent jika parser menghasilkan "claim" (default)
    if profile.query_type == "claim" and intent.query_type != "claim":
        profile.query_type = intent.query_type

    # Trend years
    if not profile.requested_trend_years and intent.trend_years_requested:
        profile.requested_trend_years = intent.trend_years_requested

    # Comparison targets
    if not profile.comparison_targets and intent.comparison_entities:
        profile.comparison_targets = intent.comparison_entities

    # Breakdown demografis dari intent (usia, gender)
    demo = intent.demographic_filters or {}
    age_groups = demo.get("age_groups") or []
    gender = str(demo.get("gender") or "").strip()

    for ag in age_groups:
        ag_str = str(ag).strip()
        if ag_str and ag_str not in profile.breakdown_targets:
            profile.breakdown_targets.append(ag_str)

    if gender and gender not in profile.breakdown_targets:
        profile.breakdown_targets.append(gender)

    # Regenerasi generated_queries dengan reformulated question di depan
    if intent.reformulated_question and intent.reformulated_question != profile.raw_question:
        if intent.reformulated_question not in profile.generated_queries:
            profile.generated_queries.insert(0, intent.reformulated_question)
