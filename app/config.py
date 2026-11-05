"""Settings. Secrets come from .env (never committed)."""
from __future__ import annotations

import datetime as dt
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
KYC_DIR = DATA_DIR / "kyc_documents"
CACHE_DIR = ROOT / "runtime"  # OCR cache: shared, content-addressed
CACHE_DIR.mkdir(exist_ok=True)
# Sessions, orders and consent records. Tests point this elsewhere so they never touch demo data.
RUNTIME_DIR = Path(os.environ.get("EK_STATE_DIR", str(CACHE_DIR)))
RUNTIME_DIR.mkdir(parents=True, exist_ok=True)


def _load_env() -> None:
    env = ROOT / ".env"
    if not env.exists():
        return
    for line in env.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"'))


_load_env()

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
OFFLINE_MODE = os.environ.get("OFFLINE_MODE", "0") == "1"

# Models are tried in order; the first that answers wins. Free tier models get busy,
# so the chain matters more than the choice of a single "best" model.
GEMINI_CHAT_MODELS = ["gemini-3.1-flash-lite", "gemini-3.5-flash-lite", "gemini-2.5-flash", "gemini-3.5-flash"]
GEMINI_SMART_MODELS = ["gemini-3.5-flash", "gemini-2.5-flash", "gemini-3.5-flash-lite", "gemini-3.1-flash-lite"]
GEMINI_VISION_MODELS = ["gemini-3.5-flash", "gemini-2.5-flash", "gemini-3.5-flash-lite", "gemini-3.1-flash-lite"]
GEMINI_AUDIO_MODELS = ["gemini-3.5-flash-lite", "gemini-2.5-flash", "gemini-3.5-flash", "gemini-3.1-flash-lite"]
GROQ_CHAT_MODELS = ["qwen/qwen3.8-27b", "openai/gpt-oss-120b", "openai/gpt-oss-20b"]

# The case says to use 2026-07-15 as "today" for date checks.
TODAY = dt.date(2026, 7, 15)
ADDRESS_PROOF_MAX_AGE_DAYS = 90
