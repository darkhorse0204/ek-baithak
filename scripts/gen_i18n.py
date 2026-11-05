"""Generate web/i18n.json: translate every English string into 9 Indian languages with Gemini.
Run once; re-run only when strings change. Placeholders like {n} must survive translation."""
import json
import time
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app import llm  # noqa: E402
from app.config import ROOT  # noqa: E402
from app.i18n import EN, LANGS  # noqa: E402

OUT = ROOT / "web" / "i18n.json"
data = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}

SCRIPTS = {"hi": "Devanagari", "mr": "Devanagari", "ta": "Tamil", "te": "Telugu", "bn": "Bengali", "gu": "Gujarati", "kn": "Kannada", "ml": "Malayalam", "pa": "Gurmukhi"}
SYSTEM = ("You translate UI text for a telecom app used by Indian small-shop owners. Use simple, everyday spoken {lang} "
          "(the way a shopkeeper talks), keep common English tech words people actually use (WhatsApp, UPI, GST, GSTIN, Wi-Fi, "
          "CCTV, OTP, e-Sign, Entity Locker, Udyam) in English or transliterated. Keep every {{placeholder}} exactly. "
          "Write every value in {script} script, never in Latin letters (except those English tech words). Return JSON with exactly the same keys.")

for code, meta in LANGS.items():
    if code == "en":
        continue
    have = data.get(code, {})
    todo = {k: v for k, v in EN.items() if k not in have}
    if not todo:
        continue
    print("translating", code, len(todo))
    keys = list(todo)
    for i in range(0, len(keys), 20):
        chunk = {k: todo[k] for k in keys[i:i + 20]}
        for attempt in range(6):
            llm._cooldown.clear()
            try:
                res, model = llm.json_call(json.dumps(chunk, ensure_ascii=False), system=SYSTEM.format(lang=meta["name"], script=SCRIPTS[code]), smart=False, timeout=60)
                bad = [k for k in chunk if k not in res or set(re.findall(r"{\w+}", chunk[k])) != set(re.findall(r"{\w+}", str(res[k])))]
                if bad:
                    print("  placeholder/key problems", bad)
                    res = {k: v for k, v in res.items() if k not in bad}
                have.update({k: str(v) for k, v in res.items() if k in chunk})
                print("  ok", code, model, len(res))
                break
            except Exception as e:
                print("  retry", code, e)
                time.sleep(8)
    data[code] = have
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
print("done", {k: len(v) for k, v in data.items()})
