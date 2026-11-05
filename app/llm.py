"""Thin LLM client: Gemini first, Groq as a second provider, then the caller's offline path.

Free-tier models get busy (we saw 503s during testing), so every call walks a chain of
models and gives up quickly. Callers must always have a non-LLM fallback.
"""
from __future__ import annotations

import base64
import json
import logging
import time
import urllib.error
import urllib.request

from . import config

log = logging.getLogger("llm")
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

# Models that failed recently are skipped for a short while.
_cooldown: dict[str, float] = {}
STATS = {"calls": 0, "ok": 0, "failed": 0, "by_model": {}}


class LLMUnavailable(Exception):
    pass


def available() -> bool:
    return not config.OFFLINE_MODE and bool(config.GEMINI_API_KEY or config.GROQ_API_KEY)


def _post(url: str, body: dict, headers: dict, timeout: float) -> dict:
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json", **headers})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def _gemini(model: str, parts: list, system: str | None, json_mode: bool, temperature: float, timeout: float) -> str:
    body: dict = {"contents": [{"role": "user", "parts": parts}], "generationConfig": {"temperature": temperature}}
    if system:
        body["systemInstruction"] = {"parts": [{"text": system}]}
    if json_mode:
        body["generationConfig"]["responseMimeType"] = "application/json"
    data = _post(GEMINI_URL.format(model=model), body, {"x-goog-api-key": config.GEMINI_API_KEY}, timeout)
    cand = data.get("candidates") or []
    if not cand or "content" not in cand[0]:
        raise LLMUnavailable(f"{model}: empty response ({cand[0].get('finishReason') if cand else 'no candidates'})")
    return "".join(p.get("text", "") for p in cand[0]["content"].get("parts", []) if not p.get("thought"))


def _groq(model: str, prompt: str, system: str | None, json_mode: bool, temperature: float, timeout: float) -> str:
    msgs = ([{"role": "system", "content": system}] if system else []) + [{"role": "user", "content": prompt}]
    body = {"model": model, "messages": msgs, "temperature": temperature}
    if json_mode:
        body["response_format"] = {"type": "json_object"}
    data = _post(GROQ_URL, body, {"Authorization": f"Bearer {config.GROQ_API_KEY}"}, timeout)
    return data["choices"][0]["message"]["content"]


def _run_chain(chain: list[tuple[str, str]], call) -> tuple[str, str]:
    if config.OFFLINE_MODE:
        raise LLMUnavailable("offline mode")
    errors = []
    now = time.time()
    for provider, model in chain:
        key = f"{provider}:{model}"
        if _cooldown.get(key, 0) > now:
            continue
        STATS["calls"] += 1
        t = time.time()
        try:
            text = call(provider, model)
            STATS["ok"] += 1
            STATS["by_model"][key] = STATS["by_model"].get(key, 0) + 1
            log.info("llm ok %s in %.1fs", key, time.time() - t)
            return text, key
        except urllib.error.HTTPError as e:
            STATS["failed"] += 1
            code = e.code
            errors.append(f"{key}: HTTP {code}")
            # Busy or rate-limited: skip this model for a minute. Bad request: don't retry it either.
            _cooldown[key] = time.time() + (20 if code in (429, 500, 503) else 600)
        except Exception as e:  # timeouts, parse errors
            STATS["failed"] += 1
            errors.append(f"{key}: {type(e).__name__}")
            _cooldown[key] = time.time() + 15
    raise LLMUnavailable("; ".join(errors) or "no model configured")


def text(prompt: str, system: str | None = None, json_mode: bool = False, smart: bool = False,
         temperature: float = 0.3, timeout: float = 25) -> tuple[str, str]:
    """Returns (text, model_used). Raises LLMUnavailable if every model failed."""
    chain = []
    if config.GEMINI_API_KEY:
        chain += [("gemini", m) for m in (config.GEMINI_SMART_MODELS if smart else config.GEMINI_CHAT_MODELS)]
    if config.GROQ_API_KEY:
        chain += [("groq", m) for m in config.GROQ_CHAT_MODELS]

    def call(provider, model):
        if provider == "gemini":
            return _gemini(model, [{"text": prompt}], system, json_mode, temperature, timeout)
        return _groq(model, prompt, system, json_mode, temperature, timeout)

    return _run_chain(chain, call)


def json_call(prompt: str, system: str | None = None, smart: bool = False, timeout: float = 25) -> tuple[dict, str]:
    raw, model = text(prompt, system, json_mode=True, smart=smart, temperature=0.2, timeout=timeout)
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.strip("`").split("\n", 1)[1].rsplit("```", 1)[0]
    return json.loads(raw), model


def vision_json(prompt: str, image: bytes, mime: str = "image/png", timeout: float = 40) -> tuple[dict, str]:
    if not config.GEMINI_API_KEY:
        raise LLMUnavailable("no Gemini key")
    parts = [{"text": prompt}, {"inline_data": {"mime_type": mime, "data": base64.b64encode(image).decode()}}]
    chain = [("gemini", m) for m in config.GEMINI_VISION_MODELS]
    raw, model = _run_chain(chain, lambda _p, m: _gemini(m, parts, None, True, 0, timeout))
    return json.loads(raw), model


def transcribe(audio: bytes, mime: str, language_hint: str = "") -> tuple[str, str]:
    """Voice note -> text in the speaker's own language and script."""
    if not config.GEMINI_API_KEY:
        raise LLMUnavailable("no Gemini key")
    prompt = ("Transcribe this voice note exactly, in the language and script it was spoken in "
              f"(likely {language_hint}). Return only the transcript." if language_hint else
              "Transcribe this voice note exactly, in the language and script it was spoken in. Return only the transcript.")
    parts = [{"text": prompt}, {"inline_data": {"mime_type": mime, "data": base64.b64encode(audio).decode()}}]
    chain = [("gemini", m) for m in config.GEMINI_AUDIO_MODELS]
    return _run_chain(chain, lambda _p, m: _gemini(m, parts, None, False, 0, 40))
