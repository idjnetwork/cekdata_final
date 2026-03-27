"""
api_server.py
=============
FastAPI server yang menjembatani frontend (App.jsx) dengan cekdata_engine.

Jalankan:
    uvicorn api_server:app --host 0.0.0.0 --port 8001 --reload

Env var yang dibutuhkan (lihat README cekdata_engine):
    CEKDATA_NEWDATA_JSONL   path ke corpus JSONL
    OPENAI_API_KEY          API key OpenAI untuk analisis AI
    OPENAI_MODEL            (opsional) model yang dipakai, default gpt-4.1-mini-2025-04-14
    RETRIEVAL_BACKEND       "local" (default) atau "pinecone"

Layer baru (opsional):
    INTENT_ROUTER_ENABLED   "true" (default) | "false" — nonaktifkan intent router
    REASONING_ENABLED       "true" (default) | "false" — nonaktifkan inference reasoning
    GAP_SCORE_THRESHOLD     float, default 15.0 — threshold skor untuk deteksi gap
    INTENT_MODEL            model untuk intent router, default = OPENAI_MODEL
    REASONER_MODEL          model untuk inference reasoner, default = OPENAI_MODEL

Keamanan:
    CORS_ORIGINS            domain frontend, default "http://localhost:3000"
    ADMIN_API_KEY           API key untuk endpoint admin (/refresh-corpus)
    CEKDATA_USERS_JSON      path ke file JSON berisi user accounts (opsional)
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import secrets
import time
from collections import defaultdict
from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException, Request, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from cekdata_engine import answer_question, invalidate_corpus_cache
from cekdata_engine.retriever import CorpusConfigError, RetrievalError
from cekdata_engine.ai_analyst import AIAnalysisError

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)
log = logging.getLogger("api_server")

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = FastAPI(
    title="CekData AI API",
    description="API verifikasi klaim berbasis data statistik Indonesia.",
    version="0.3.0",
)

# CORS — default ke localhost, bukan wildcard
_default_origins = "http://localhost:3000,http://localhost:5173,http://127.0.0.1:3000"
ALLOWED_ORIGINS = [
    o.strip() for o in os.getenv("CORS_ORIGINS", _default_origins).split(",") if o.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Rate limiter sederhana (in-memory, per IP)
# ---------------------------------------------------------------------------

_RATE_LIMIT_WINDOW = 60       # detik
_RATE_LIMIT_MAX_REQUESTS = 30  # max request per window per IP

_rate_limiter: Dict[str, list] = defaultdict(list)


def _check_rate_limit(client_ip: str) -> bool:
    """Return True jika request diizinkan, False jika melebihi limit."""
    now = time.time()
    window_start = now - _RATE_LIMIT_WINDOW
    # Bersihkan entry lama
    _rate_limiter[client_ip] = [
        ts for ts in _rate_limiter[client_ip] if ts > window_start
    ]
    if len(_rate_limiter[client_ip]) >= _RATE_LIMIT_MAX_REQUESTS:
        return False
    _rate_limiter[client_ip].append(now)
    return True


# ---------------------------------------------------------------------------
# User management (simple file-based)
# ---------------------------------------------------------------------------

def _hash_password(password: str) -> str:
    """Hash password dengan SHA-256 + salt sederhana."""
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def _load_users() -> Dict[str, str]:
    """
    Muat user dari file JSON atau env var.
    Format: {"email": "hashed_password", ...}
    Jika CEKDATA_USERS_JSON tidak diset, gunakan default demo user.
    """
    users_path = os.getenv("CEKDATA_USERS_JSON", "").strip()
    if users_path and os.path.isfile(users_path):
        try:
            with open(users_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as exc:
            log.warning(f"Gagal membaca users file: {exc}. Menggunakan default.")

    # Default demo user — password di-hash, bukan plaintext
    return {
        "demo@cekdata.ai": _hash_password("cekdata2026"),
    }


_users = _load_users()

# Session tokens sederhana (in-memory)
_sessions: Dict[str, str] = {}   # token → email

# Admin API key
_ADMIN_API_KEY = os.getenv("ADMIN_API_KEY", "").strip()

# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class AskRequest(BaseModel):
    question: str = Field(..., min_length=3, max_length=2000,
                          description="Pertanyaan atau klaim yang ingin diverifikasi.")
    top_k: int    = Field(8, ge=1, le=20,
                          description="Jumlah kandidat data yang diambil (default 8).")


class LoginRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=200)
    password: str = Field(..., min_length=1, max_length=200)


class FeedbackRequest(BaseModel):
    conversation_id: str = Field(..., min_length=1, max_length=100)
    value: str = Field(..., pattern=r"^(membantu|kurang tepat|salah)$")
    question: str = Field("", max_length=2000)


class HealthResponse(BaseModel):
    status: str
    retrieval_backend: str
    corpus_path: Optional[str]


# ---------------------------------------------------------------------------
# Middleware: log waktu setiap request
# ---------------------------------------------------------------------------

@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    elapsed = (time.perf_counter() - start) * 1000
    log.info(f"{request.method} {request.url.path}  {response.status_code}  {elapsed:.0f}ms")
    return response


# ---------------------------------------------------------------------------
# Exception handlers — agar error backend tidak bocor sebagai 500 mentah
# ---------------------------------------------------------------------------

@app.exception_handler(CorpusConfigError)
async def corpus_config_error_handler(request: Request, exc: CorpusConfigError):
    log.error(f"Corpus config error: {exc}")
    return JSONResponse(status_code=503,
        content={"detail": "Corpus data belum dikonfigurasi. Hubungi admin.",
                 "error_type": "corpus_config"})


@app.exception_handler(RetrievalError)
async def retrieval_error_handler(request: Request, exc: RetrievalError):
    log.error(f"Retrieval error: {exc}")
    return JSONResponse(status_code=503,
        content={"detail": "Gagal mengakses sumber data. Coba lagi.",
                 "error_type": "retrieval"})


@app.exception_handler(AIAnalysisError)
async def ai_error_handler(request: Request, exc: AIAnalysisError):
    log.warning(f"AI analysis error (degraded mode): {exc}")
    return JSONResponse(status_code=503,
        content={"detail": "Analisis AI tidak tersedia saat ini. Coba lagi.",
                 "error_type": "ai_analysis"})


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/health", response_model=HealthResponse, tags=["infra"])
def health():
    """
    Cek status server dan konfigurasi aktif.
    Dipakai frontend untuk memastikan backend siap sebelum mengirim pertanyaan.
    """
    return {
        "status": "ok",
        "retrieval_backend": os.getenv("RETRIEVAL_BACKEND", "local"),
        "corpus_path": os.getenv("CEKDATA_NEWDATA_JSONL") or None,
    }


@app.post("/login", tags=["auth"])
def login(req: LoginRequest):
    """
    Autentikasi user. Mengembalikan session token jika berhasil.
    Password di-hash dan dibandingkan dengan database user.
    """
    hashed = _hash_password(req.password)
    stored_hash = _users.get(req.email)

    if stored_hash is None or stored_hash != hashed:
        raise HTTPException(status_code=401, detail="Email atau password salah.")

    token = secrets.token_urlsafe(32)
    _sessions[token] = req.email
    log.info(f"Login berhasil: {req.email}")
    return {"status": "ok", "token": token, "email": req.email}


@app.post("/logout", tags=["auth"])
def logout(authorization: str = Header(default="")):
    """Hapus session token."""
    token = authorization.replace("Bearer ", "").strip()
    if token in _sessions:
        email = _sessions.pop(token)
        log.info(f"Logout: {email}")
    return {"status": "ok"}


@app.post("/ask", tags=["core"])
def ask(req: AskRequest, request: Request) -> Dict[str, Any]:
    """
    Verifikasi satu pertanyaan atau klaim.
    Rate-limited: max 30 request per menit per IP.
    """
    client_ip = request.client.host if request.client else "unknown"

    if not _check_rate_limit(client_ip):
        raise HTTPException(
            status_code=429,
            detail="Terlalu banyak request. Coba lagi dalam 1 menit.",
        )

    log.info(f"POST /ask  question={req.question[:80]!r}  top_k={req.top_k}  ip={client_ip}")

    try:
        result = answer_question(req.question, top_k=req.top_k)
    except (CorpusConfigError, RetrievalError, AIAnalysisError):
        raise  # ditangani oleh exception handlers di atas
    except Exception as exc:
        log.exception(f"Unexpected error on /ask: {exc}")
        raise HTTPException(status_code=500,
            detail="Terjadi kesalahan internal. Hubungi admin.")

    return result


@app.post("/feedback", tags=["core"])
def feedback(req: FeedbackRequest):
    """
    Simpan feedback pengguna untuk satu jawaban.
    Saat ini di-log ke file — bisa diperluas ke database.
    """
    log.info(
        f"Feedback: conversation={req.conversation_id} "
        f"value={req.value} question={req.question[:60]!r}"
    )
    return {"status": "ok", "message": "Feedback diterima. Terima kasih."}


@app.post("/refresh-corpus", tags=["infra"])
def refresh_corpus(x_admin_key: str = Header(default="", alias="X-Admin-Key")):
    """
    Paksa reload corpus dari file JSONL tanpa restart server.
    Dilindungi dengan admin API key via header X-Admin-Key.
    """
    if _ADMIN_API_KEY and x_admin_key != _ADMIN_API_KEY:
        raise HTTPException(status_code=403, detail="Admin API key tidak valid.")

    invalidate_corpus_cache()
    log.info("Corpus cache invalidated via /refresh-corpus")
    return {"status": "ok", "message": "Corpus akan di-reload pada request berikutnya."}
