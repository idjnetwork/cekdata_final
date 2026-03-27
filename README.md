# CekData Engine

Mesin verifikasi klaim berbasis data statistik Indonesia. Dirancang untuk redaksi dan platform jurnalisme data yang ingin mengotomatisasi sebagian proses cek fakta terhadap data resmi (BPS dan sumber statistik sejenis).

Dikembangkan oleh [Indonesia Data Journalism Network (IDJN)](https://idjnetwork.org).

---

## Cara kerja

```
Pertanyaan pengguna
       │
       ▼
 intent_router.py    ← AI memahami niat, reformulasi, terjemahkan ke bahasa BPS
       │
       ├── off_topic? → tolak dengan penjelasan
       ├── clarify?   → balik tanya + contoh pertanyaan
       │
       ▼
 query_parser.py     ← rule-based: ekstrak indikator, wilayah, tahun, jenis query
       │              ← gabungkan hasil AI + rule → QueryProfile
       ▼
  retriever.py       ← cari kandidat data dari corpus (JSONL lokal atau Pinecone)
   + scorer.py       ← skor relevansi (38 bobot), diversifikasi, top 8
       │
       ▼
 data_gap_detector   ← skor terlalu rendah? indikator tidak cocok?
       │
       ├── ada gap → inference_reasoner.py (AI cari proxy data) → retrieve ulang
       │
       ▼
 ai_analyst.py       ← kirim kandidat ke GPT-4, terima analisis JSON terstruktur
       │
       ▼
  validator.py       ← validasi logis + editorial checks + followup prompt
       │
       ├── gap dari output AI? → reasoning + analisis ulang (max 1x)
       │
       ▼
  renderer.py        ← render teks final yang bisa dibaca pengguna
       │
       ▼
  engine.py          ← orkestrasi seluruh alur di atas
```

Setiap lapisan punya tanggung jawab tunggal dan bisa diuji secara terpisah.

---

## Fitur utama

### Penerjemahan konteks ke bahasa BPS

Intent Router (AI) menerjemahkan istilah populer dan klaim publik ke indikator dan dimensi BPS yang tepat:

- **Istilah demografis**: "Gen Z" → kelompok umur 15-24, "milenial" → 25-39, "lansia" → 60+
- **Program pemerintah**: "MBG tambah lapangan kerja" → bukan soal makan, tapi Jumlah Penduduk Bekerja + TPT
- **Ekonomi populer**: "daya beli turun" → Inflasi + Garis Kemiskinan, "PHK massal" → TPT + Jumlah Pengangguran
- **Kemiskinan spesifik**: "kemiskinan makin dalam" → Indeks Kedalaman (P1), "kemiskinan ekstrem" → P0 + garis internasional

### Peringatan editorial otomatis

Engine secara otomatis menambah `peringatan_editorial` untuk:

- **Klaim kausal**: "Program X berhasil menurunkan kemiskinan" → engine menurunkan penilaian dari "Benar" ke "Tidak dapat diverifikasi", memperingatkan bahwa korelasi bukan kausalitas, dan menyarankan 2-4 pertanyaan kritis konkret untuk follow-up jurnalistik.
- **Klaim pejabat/pemerintah**: Kata kunci seperti "prabowo mengklaim", "presiden mengatakan", "pemerintah menyebut" otomatis memicu skeptisisme editorial.
- **Data tidak cukup**: Jika AI memilih "Tidak dapat diverifikasi", peringatan editorial berisi saran langkah verifikasi spesifik — data apa yang dibutuhkan, ke mana mencarinya, pertanyaan apa untuk sumber klaim.
- **Indikator tidak ideal**: Jika query umum tapi AI memilih "Jumlah Penduduk Miskin" alih-alih "Persentase", engine menambah catatan editorial.

### Followup prompt

Jika data tidak tersedia dan pertanyaan bukan klaim eksplisit (misalnya jurnalis bertanya data teknis padahal sebenarnya mau verifikasi klaim), engine menampilkan ajakan: *"Apakah kamu sedang memverifikasi sebuah klaim? Coba sampaikan klaim lengkapnya supaya kami bisa membantu."* Ini mencegah jurnalis pulang dengan tangan kosong.

### Gap detection + inference reasoning

Jika data langsung tidak tersedia atau tidak relevan, engine tidak langsung menyerah:

1. **Gap Detector** mengecek skor kandidat dan kesesuaian indikator
2. **Inference Reasoner** (AI) berpikir tentang proxy data — misalnya klaim lapangan kerja MBG bisa diuji lewat data jumlah penduduk bekerja
3. Engine melakukan retrieve ulang dengan query alternatif
4. Jika setelah AI menjawab ternyata data tetap tidak ada, reasoning bisa dijalankan sekali lagi (max 1x untuk mencegah loop)

---

## Instalasi

```bash
pip install -e ".[dev]"
```

Dependensi:

| Package | Kapan dibutuhkan |
|---|---|
| `openai` | Analisis AI via GPT-4 (wajib untuk penilaian otomatis) |
| `pinecone-client` | Backend retrieval vector search (alternatif JSONL lokal) |
| `indicator_registry` | Lookup indikator kanonik (opsional — fallback built-in tersedia) |
| `breakdown_registry` | Deteksi breakdown usia/gender (opsional — fallback built-in tersedia) |

### Modul eksternal opsional

`indicator_registry` dan `breakdown_registry` adalah modul eksternal yang memperkaya deteksi indikator dan breakdown. Jika tidak tersedia, engine menggunakan fallback built-in yang mendeteksi indikator lewat keyword (kemiskinan, ketenagakerjaan, inflasi, PDRB) dan breakdown lewat keyword (generasi, gender, urban/rural). Pesan warning akan muncul di log saat startup.

---

## Konfigurasi environment

Buat file `.env` (lihat `.env.example`) atau set variabel berikut:

```bash
# ── Wajib ──
export CEKDATA_NEWDATA_JSONL=/path/ke/corpus.jsonl
export OPENAI_API_KEY=sk-...

# ── Engine (opsional) ──
export OPENAI_MODEL=gpt-4.1-mini-2025-04-14     # default
export RETRIEVAL_BACKEND=local                    # "local" atau "pinecone"

# ── Layer AI tambahan (opsional, default aktif) ──
export INTENT_ROUTER_ENABLED=true    # AI pemahaman niat + reformulasi
export REASONING_ENABLED=true        # AI reasoning proxy data
export GAP_SCORE_THRESHOLD=15.0      # threshold skor untuk deteksi gap
export INTENT_MODEL=gpt-4.1-mini-2025-04-14    # model untuk intent router
export REASONER_MODEL=gpt-4.1-mini-2025-04-14  # model untuk inference reasoner

# ── Keamanan (untuk API server) ──
export CORS_ORIGINS=http://localhost:3000,http://localhost:5173
export ADMIN_API_KEY=ganti-dengan-key-rahasia
# export CEKDATA_USERS_JSON=/path/to/users.json

# ── Pinecone (jika RETRIEVAL_BACKEND=pinecone) ──
# export PINECONE_API_KEY=...
# export PINECONE_INDEX_NAME=cekdata-index
# export OPENAI_EMBED_MODEL=text-embedding-3-small
```

---

## Format corpus JSONL

Setiap baris adalah satu JSON object dengan field berikut:

```jsonc
{
  "id": "unik per record",
  "doc_type": "atomic",          // "atomic" (satu titik data) atau "trend" (ringkasan tren)
  "series_label": "Persentase Penduduk Miskin",
  "area_name": "Jawa Timur",
  "area_level": "provinsi",      // "nasional" | "provinsi" | "kabupaten"
  "area_code": "35",
  "year": 2023,
  "year_start": null,            // untuk doc_type "trend"
  "year_end": null,
  "period": "Maret",             // "Maret" | "September" | "Triwulan I" | dst.
  "value": 10.35,
  "unit": "%",
  "breakdown_label": "",         // label dimensi breakdown, misal "Tipe Daerah"
  "breakdown_value": "",         // nilai breakdown, misal "Perdesaan"
  "subgroup_label": "",
  "subgroup_value": "",
  "title": "Persentase Penduduk Miskin Jawa Timur Maret 2023",
  "source": "BPS",
  "source_file": "kemiskinan_jatim_2023.xlsx",
  "download_url": "https://bps.go.id/...",
  "keywords": ["kemiskinan", "Jawa Timur"],
  "metadata": {}
}
```

Field yang tidak diisi cukup dihilangkan — `normalize_record()` akan mengisi nilai default yang aman.

---

## Penggunaan

### Python API

```python
from cekdata_engine import CekDataEngine

engine = CekDataEngine()
result = engine.answer_question("Benarkah kemiskinan di Jawa Timur turun di bawah rata-rata nasional?")

print(result["answer"])                          # teks siap tampil
print(result["parsed"]["penilaian"])             # "Benar" | "Salah" | "Sebagian benar" | "Tidak dapat diverifikasi"
print(result["parsed"]["peringatan_editorial"])  # catatan kritis jika ada
print(result["parsed"].get("followup_prompt"))   # ajakan konteks jika data tidak ada
print(result["effective_question"])              # pertanyaan setelah reformulasi AI
```

#### Shortcut untuk satu pertanyaan

```python
from cekdata_engine import answer_question

result = answer_question("Tren kemiskinan 5 tahun terakhir di Indonesia")
```

#### Pakai retriever kustom

```python
from cekdata_engine import CekDataEngine
from cekdata_engine.retriever import build_retriever

# Pakai Pinecone
engine = CekDataEngine(retriever=build_retriever("pinecone"))

# Atau injeksi retriever kustom (untuk testing)
engine = CekDataEngine(retriever=MyCustomRetriever())
```

#### Invalidate cache corpus

```python
from cekdata_engine import invalidate_corpus_cache

# Setelah file JSONL diperbarui, panggil ini agar reload di request berikutnya
invalidate_corpus_cache()
```

### CLI

```bash
cekdata "Benarkah kemiskinan di Papua masih di atas 20%?"

# Output: JSON lengkap ke stdout
```

### API Server

```bash
uvicorn api_server:app --host 0.0.0.0 --port 8001 --reload
```

Endpoints:

| Method | Path | Fungsi |
|---|---|---|
| `GET` | `/health` | Cek status server |
| `POST` | `/ask` | Verifikasi pertanyaan/klaim (rate-limited: 30/menit per IP) |
| `POST` | `/login` | Autentikasi user (password di-hash server-side) |
| `POST` | `/logout` | Hapus session |
| `POST` | `/feedback` | Kirim feedback pengguna |
| `POST` | `/refresh-corpus` | Reload corpus (dilindungi header `X-Admin-Key`) |

### Output structure

```python
{
    "question": str,               # pertanyaan asli
    "effective_question": str,     # setelah reformulasi oleh Intent Router
    "queries": list[str],          # generated queries untuk retrieval
    "query_profile": dict,         # QueryProfile sebagai dict
    "intent": dict | None,         # hasil Intent Router (status, reformulasi, confidence)
    "answer": str,                 # teks final siap tampil
    "parsed": {
        "claim": str,
        "indicator_used": str,
        "records_used": list[str], # candidate_id yang dipakai AI
        "temuan_data": str,
        "konteks_penting": str,
        "penilaian": str,          # "Benar" | "Salah" | "Sebagian benar" | "Tidak dapat diverifikasi"
        "alasan": str,
        "peringatan_editorial": str,   # catatan kritis untuk klaim kausal / data tidak cukup
        "followup_prompt": str,        # ajakan konteks jika data tidak ada + bukan klaim eksplisit
        "sumber": str,
        "unduh_data": str | list,
        "raw_answer": str,
    },
    "best_match": dict | None,     # record terbaik
    "best_score": float | None,
    "top_matches": list[dict],     # ringkasan semua kandidat teratas
    "reasoning": {                 # hanya ada jika inference reasoning dijalankan
        "found_proxy": bool,
        "alternative_queries": list[str],
        "proxy_rationale": str,
    } | None,
}
```

---

## Jenis query yang didukung

| Jenis | Contoh | Keterangan |
|---|---|---|
| `claim` | "Benarkah kemiskinan di NTT masih di atas 20%?" | Verifikasi klaim dengan data |
| `trend` | "Bagaimana tren kemiskinan 5 tahun terakhir di Indonesia?" | Analisis perubahan lintas waktu |
| `comparison` | "Bandingkan kemiskinan Jawa Barat dan Jawa Timur" | Perbandingan dua sisi |
| `latest` | "Berapa angka kemiskinan Indonesia terbaru?" | Ambil data paling mutakhir |

Engine juga menangani pertanyaan informal dan klaim implisit — Intent Router menerjemahkan ke jenis query yang tepat.

---

## Skala penilaian

| Penilaian | Kapan digunakan |
|---|---|
| **Benar** | Klaim didukung data yang relevan, sebanding, dan cukup jelas |
| **Salah** | Data yang tersedia langsung bertentangan dengan klaim |
| **Sebagian benar** | Klaim pakai sebagian data benar, tapi kesimpulan melompat lebih jauh |
| **Tidak dapat diverifikasi** | Data belum cukup: pembanding tidak lengkap, periode tidak setara, indikator tidak tepat, data belum ada, atau klaim mengandung hubungan sebab-akibat yang tidak bisa dibuktikan dari data statistik saja |

Penilaian hanya bisa diturunkan oleh Validator, tidak pernah dinaikkan. AI mengusulkan, Validator memverifikasi.

---

## Menjalankan test

```bash
# Semua test (tidak butuh API key atau corpus nyata)
pytest tests/ -v

# Satu file
pytest tests/test_validator.py -v

# Dengan coverage
pytest tests/ --cov=cekdata_engine --cov-report=term-missing
```

Test dirancang agar bisa berjalan sepenuhnya offline menggunakan stub retriever dan stub AI. Total: 251 test functions.

---

## Arsitektur modul

```
cekdata_engine/
├── constants.py          Konstanta domain (38 bobot scoring, alias wilayah, dsb.)
├── models.py             Dataclass: QueryProfile, Candidate, CorpusBundle, AnalysisResult
├── text_utils.py         Pure functions: normalize, tokenize, format angka, sort temporal
├── openai_client.py      Shared OpenAI client factory (satu singleton untuk semua layer AI)
├── query_parser.py       Parse pertanyaan → QueryProfile; fallback jika modul eksternal tidak ada
├── scorer.py             score_record(), diversify_candidates(), pack_candidates_for_ai()
├── retriever.py          RetrievalBackend ABC, JSONLRuleBasedRetriever, PineconeRetriever
├── intent_router.py      AI layer 1: pemahaman niat, reformulasi, terjemahan ke bahasa BPS
├── data_gap_detector.py  Deteksi gap data setelah retrieval dan setelah AI menjawab
├── inference_reasoner.py AI layer 2: reasoning proxy data jika data langsung tidak ada
├── ai_analyst.py         AI layer 3: prompt builder + analisis GPT-4 → JSON terstruktur
├── validator.py          Validasi output AI + editorial checks + followup prompt
├── renderer.py           render_answer(), build_top_matches(), pick_best_match()
├── engine.py             CekDataEngine — orkestrasi seluruh pipeline, tanpa logika domain
└── cli.py                Entry point CLI

tests/
├── test_text_utils.py          61 tests
├── test_query_parser.py        24 tests
├── test_scorer.py              22 tests
├── test_validator.py           22 tests
├── test_renderer.py            12 tests
├── test_data_gap_detector.py   23 tests
├── test_intent_router.py       30 tests
├── test_inference_reasoner.py  18 tests
└── test_engine_integration.py  39 tests
```

### Dependency antar layer

```
cli / api_server / frontend
           │
         engine              ← orkestrasi, tidak ada logika domain
           │
    ┌──────┼──────────────────────────┐
    │      │      │         │         │
 intent  retriever  ai_analyst  validator  renderer
 router    │                      │
    │   ┌──┤                      │
    │   │  scorer        data_gap_detector
    │   │                         │
    │   query_parser    inference_reasoner
    │       │
    └───────┤
            │
  openai_client + text_utils + constants + models
```

Layer bawah tidak pernah mengimpor layer atas. Dependency mengalir ke bawah.

---

## Menambah indikator baru

Jika `indicator_registry` tersedia: edit file registry tersebut.

Jika menggunakan fallback built-in: edit fungsi `_registry_candidates()` di `query_parser.py` — tambahkan keyword detection untuk indikator baru.

## Menambah wilayah baru

Edit `AREA_ALIASES` di `constants.py`:

```python
AREA_ALIASES["kalsel"] = "Kalimantan Selatan"
AREA_ALIASES["kalimantan selatan"] = "Kalimantan Selatan"
```

## Mengganti model AI

```bash
# Model untuk semua layer AI
export OPENAI_MODEL=gpt-4o-2024-11-20

# Atau model terpisah per layer (lebih hemat)
export INTENT_MODEL=gpt-4.1-mini-2025-04-14      # intent router (murah, cepat)
export REASONER_MODEL=gpt-4.1-mini-2025-04-14    # inference reasoner
export OPENAI_MODEL=gpt-4.1-2025-04-14           # AI analyst (perlu reasoning kuat)
```

## Mematikan layer AI tambahan

```bash
# Untuk hemat API call atau saat testing
export INTENT_ROUTER_ENABLED=false    # skip intent router, langsung ke parser
export REASONING_ENABLED=false        # skip gap detection + reasoning
```

---

## Lisensi

MIT
