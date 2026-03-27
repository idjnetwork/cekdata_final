"""
constants.py
============
Semua konstanta domain yang dipakai di seluruh lapisan.
Tidak ada logika di sini — hanya data statis.
"""
from __future__ import annotations

# ---------------------------------------------------------------------------
# Penilaian yang diizinkan
# ---------------------------------------------------------------------------
ALLOWED_JUDGMENTS = frozenset({
    "Benar",
    "Salah",
    "Sebagian benar",
    "Tidak dapat diverifikasi",
})

# ---------------------------------------------------------------------------
# Bobot scoring — named constants agar mudah di-tune tanpa memburu magic number
# ---------------------------------------------------------------------------
SCORE_PRIMARY_INDICATOR_MATCH   =  18.0   # indikator utama persis cocok
SCORE_SECONDARY_INDICATOR_MATCH =  10.0   # indikator ada di target list
SCORE_AREA_MATCH                =  11.0   # wilayah cocok dengan target
SCORE_COMPARISON_AREA_MATCH     =   7.0   # wilayah cocok sebagai sisi pembanding
SCORE_BREAKDOWN_MATCH           =  12.0   # breakdown value cocok
SCORE_AGGREGATE_BREAKDOWN       =   7.5   # record adalah agregat (tidak dipecah)
SCORE_SUBGROUP_MATCH            =   8.0   # subgroup cocok
SCORE_AGGREGATE_SUBGROUP        =   3.5   # subgroup adalah agregat
SCORE_EXPLICIT_YEAR_MATCH       =   9.0   # tahun eksplisit cocok
SCORE_PERIOD_MATCH              =   7.0   # period (Maret/September/dsb) cocok
SCORE_NATIONAL_AREA_DEFAULT     =   2.0   # bonus kecil jika area Indonesia tanpa target
SCORE_TREND_DOC_TYPE            =   9.0   # doc_type=="trend" untuk query tren
SCORE_TREND_ATOMIC_PRIORITY     =  12.0   # atomic record untuk tren per-tahun
SCORE_COMPARISON_ATOMIC         =   5.0   # atomic untuk query perbandingan
SCORE_COMPARISON_COMBINED_BREAKDOWN =  6.5
SCORE_KEYWORD_HIT               =   1.8   # per keyword hit

PENALTY_WRONG_INDICATOR_MAIN    =  -8.0   # indikator salah untuk query utama
PENALTY_WRONG_INDICATOR_SOFT    =  -2.5   # indikator berbeda, tapi tidak kritis
PENALTY_JUMLAH_FOR_CLAIM        =  -2.0   # jumlah penduduk miskin untuk query claim umum
PENALTY_PERCENT_FOR_QUANTITY    =  -8.0   # persentase untuk query kuantitas
PENALTY_NON_TARGET_AREA         =  -6.0
PENALTY_WRONG_BREAKDOWN         =  -3.0
PENALTY_COMBINED_BREAKDOWN      =  -8.0   # gabungan perkotaan+perdesaan untuk query pair
PENALTY_UNREQUESTED_BREAKDOWN   =  -7.5
PENALTY_UNREQUESTED_OTHER_BREAK =  -3.0
PENALTY_UNREQUESTED_SUBGROUP    =  -6.5
PENALTY_UNREQUESTED_OTHER_SUB   =  -2.5
PENALTY_PERIOD_MISMATCH         =  -1.5
PENALTY_TREND_SUMMARY           =  -4.0   # trend summary untuk query yang minta per-tahun
PENALTY_PARTIAL_BREAKDOWN       =  -4.5
PENALTY_AVOID_GARIS             =  -7.0   # garis kemiskinan untuk query penilaian umum

# Bonus tambahan (sebelumnya hardcoded di scorer.py)
SCORE_TREND_POVERTY_PREF        =   4.0   # bonus persentase penduduk miskin di query tren
SCORE_TREND_SPAN_MAX            =   8.0   # batas atas bonus rentang tahun trend doc
SCORE_EXPLICIT_URBAN_RURAL      =   6.0   # bonus jika urban/rural disebut eksplisit

# Bias waktu (skala kecil — hanya tiebreaker)
BIAS_LATEST_YEAR   = 0.030
BIAS_LATEST_PERIOD = 0.003
BIAS_RECENT_YEAR   = 0.015
BIAS_RECENT_PERIOD = 0.001

# ---------------------------------------------------------------------------
# Urutan periode dalam setahun (untuk sort key)
# ---------------------------------------------------------------------------
PERIOD_ORDER: dict[str, int] = {
    "Januari": 1, "Februari": 2, "Maret": 3, "April": 4,
    "Mei": 5, "Juni": 6, "Juli": 7, "Agustus": 8,
    "September": 9, "Oktober": 10, "November": 11, "Desember": 12,
    "Triwulan I": 3, "Triwulan II": 6, "Triwulan III": 9, "Triwulan IV": 12,
    "Semester I": 6, "Semester II": 12,
    "Tahunan": 12, "Tahunan/Year": 12,
}

# ---------------------------------------------------------------------------
# Stopwords bahasa Indonesia + Inggris
# ---------------------------------------------------------------------------
STOPWORDS: frozenset[str] = frozenset({
    "yang", "dan", "di", "ke", "dari", "untuk", "dengan", "atau", "apakah",
    "benarkah", "berapa", "bagaimana", "tahun", "ini", "lebih", "daripada",
    "pada", "dalam", "antara", "masih", "rata", "vs", "tren", "beberapa",
    "terakhir", "apa", "jadi", "adalah", "sebuah", "suatu", "para",
    "the", "of", "to", "oleh", "agar", "karena", "bahwa", "itu",
})

# ---------------------------------------------------------------------------
# Alias wilayah → nama kanonik
# ---------------------------------------------------------------------------
AREA_ALIASES: dict[str, str] = {
    "nasional": "Indonesia", "indonesia": "Indonesia", "ri": "Indonesia",
    "aceh": "Aceh",
    "sumatera utara": "Sumatera Utara", "sumut": "Sumatera Utara",
    "sumatera barat": "Sumatera Barat", "sumbar": "Sumatera Barat",
    "sumatera selatan": "Sumatera Selatan", "sumsel": "Sumatera Selatan",
    "dki jakarta": "DKI Jakarta", "jakarta": "DKI Jakarta",
    "jawa barat": "Jawa Barat", "jabar": "Jawa Barat",
    "jawa tengah": "Jawa Tengah", "jateng": "Jawa Tengah",
    "jawa timur": "Jawa Timur", "jatim": "Jawa Timur",
    "banten": "Banten",
    "yogyakarta": "DI Yogyakarta", "diy": "DI Yogyakarta",
    "bali": "Bali",
    "ntb": "Nusa Tenggara Barat",
    "ntt": "Nusa Tenggara Timur",
    "kalimantan timur": "Kalimantan Timur", "kaltim": "Kalimantan Timur",
    "kalimantan barat": "Kalimantan Barat", "kalbar": "Kalimantan Barat",
    "sulawesi selatan": "Sulawesi Selatan", "sulsel": "Sulawesi Selatan",
    "papua": "Papua",
    "perdesaan": "Perdesaan", "pedesaan": "Perdesaan", "desa": "Perdesaan",
    "perkotaan": "Perkotaan", "kota": "Perkotaan",
}

# ---------------------------------------------------------------------------
# Cue kata untuk menentukan jenis query
# ---------------------------------------------------------------------------
QUESTION_CUES: dict[str, list[str]] = {
    "trend": [
        "tren", "trend", "perkembangan",
        "beberapa tahun terakhir", "dari tahun ke tahun",
    ],
    "comparison": [
        "bandingkan", "perbandingan", "dibanding", "vs", "versus",
        "lebih tinggi", "lebih rendah", "di atas", "di bawah",
        "lebih banyak", "lebih sedikit", "daripada", "rata rata nasional",
    ],
    "claim": ["benarkah", "apakah benar", "masih", "lebih baik", "membaik", "memburuk"],
    "latest": ["tahun ini", "terbaru", "saat ini", "sekarang"],
    "latest_trend": [
        "beberapa tahun terakhir", "dalam beberapa tahun terakhir", "akhir akhir ini",
    ],
}

# ---------------------------------------------------------------------------
# Pemetaan nama tampilan indikator
# ---------------------------------------------------------------------------
INDICATOR_DISPLAY_MAP: dict[str, str] = {
    "persentase penduduk miskin": "Persentase Penduduk Miskin",
    "jumlah penduduk miskin": "Jumlah Penduduk Miskin",
    "garis kemiskinan": "Garis Kemiskinan",
}

# ---------------------------------------------------------------------------
# Nilai breakdown/subgroup yang dianggap agregat (tidak butuh filter khusus)
# ---------------------------------------------------------------------------
AGGREGATE_BREAKDOWNS: frozenset[str] = frozenset({
    "", "Indonesia", "Perkotaan + Perdesaan", "Total", "TOTAL", "Nasional",
})

AGGREGATE_SUBGROUPS: frozenset[str] = frozenset({
    "", "Total", "TOTAL", "Jumlah Pengangguran", "Indonesia",
    "Semua", "Total/Laki-laki + Perempuan",
})

DETAILED_BREAKDOWN_LABELS: frozenset[str] = frozenset({
    "Laki-laki", "Perempuan", "Perkotaan", "Perdesaan",
    "15-19", "20-24", "25-29", "30-34", "35-39", "40-44",
    "45-49", "50-54", "55-59", "60+",
})

DETAILED_SUBGROUPS: frozenset[str] = frozenset({
    "Pernah Bekerja", "Tidak Pernah Bekerja",
    "Laki-laki", "Perempuan",
    "15-19", "20-24", "25-29", "30-34", "35-39", "40-44",
    "45-49", "50-54", "55-59", "60+",
})

# ---------------------------------------------------------------------------
# Output default jika semua jalur gagal
# ---------------------------------------------------------------------------
DEFAULT_OUTPUT: dict[str, object] = {
    "claim": "",
    "indicator_used": "",
    "records_used": [],
    "temuan_data": "",
    "konteks_penting": "",
    "penilaian": "Tidak dapat diverifikasi",
    "alasan": "Data yang ditemukan belum cukup kuat untuk mendukung penilaian otomatis.",
    "peringatan_editorial": "",
    "sumber": "",
    "unduh_data": "",
    "raw_answer": "",
}
