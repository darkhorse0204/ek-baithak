"""Conversational advisor.

Per turn: (1) the LLM extracts facts from what the owner said and writes a one-line
acknowledgement in their language; (2) plain code merges the facts, decides the next
question, and (when ready) calls the recommender; (3) the LLM explains the bundle from the
recommender's structured reasons. If no model answers, a keyword extractor and translated
templates take over, so the journey never stalls.
"""
from __future__ import annotations

import json
import re
import threading
import time
import uuid

from . import llm, registry
from .catalogue import Profile
from .config import RUNTIME_DIR
from .data import CITY_TIER, business_type_segment, catalogue
from .i18n import LANGS, t
from .recommender import BUSINESS_NEEDS, NEEDS, default_needs, infer_segment, recommend

SESSIONS: dict[str, dict] = {}
_lock = threading.Lock()
SESSIONS_FILE = RUNTIME_DIR / "sessions.json"

BUSINESS_TYPES = sorted(business_type_segment())
PRODUCT_ALIASES = {
    "P03": ["1 gbps", "1gbps", "1 gb", "gigabit", "1000 mbps", "biz fibre 1g"], "P02": ["300 mbps"], "P01": ["100 mbps fibre"],
    "P04": ["airfiber", "air fiber", "5g fwa"], "P05": ["leased line", "ill", "dedicated line"], "P06": ["leased line 100", "100 mbps leased"],
    "P10": ["sd-wan", "sdwan", "sd wan"], "P11": ["static ip", "fixed ip"], "P12": ["cloud telephony", "ivr", "sip"],
    "P13": ["toll free", "toll-free", "1800"], "P14": ["sms"], "P15": ["whatsapp api", "whatsapp business api"],
    "P21": ["firewall"], "P24": ["machine monitoring", "iot"], "P25": ["fleet", "gps tracker"],
}
KEYWORD_TYPES = {
    "kirana": "Kirana store", "grocery": "Kirana store", "किराना": "Kirana store", "general store": "Kirana store",
    "pharmacy chain": "Pharmacy chain", "medical store": "Pharmacy", "chemist": "Pharmacy", "pharmacy": "Pharmacy", "दवा": "Pharmacy",
    "sweet": "Sweet shop", "mithai": "Sweet shop", "मिठाई": "Sweet shop", "bakery chain": "Bakery chain", "bakery": "Bakery", "बेकरी": "Bakery",
    "salon": "Salon", "parlour": "Salon", "parlor": "Salon", "सैलून": "Salon", "boutique": "Boutique", "optician": "Optician", "optical": "Optician",
    "mobile repair": "Mobile repair shop", "hardware": "Hardware store", "stationery": "Stationery shop",
    "dental": "Dental clinic", "dentist": "Dental clinic", "ca firm": "CA firm", "chartered accountant": "CA firm", "coaching": "Coaching centre",
    "tuition": "Coaching centre", "diagnostic": "Diagnostic lab", "pathology": "Diagnostic lab", "lab": "Diagnostic lab", "law": "Law office",
    "lawyer": "Law office", "advocate": "Law office", "physio": "Physiotherapy clinic", "clinic": "Physiotherapy clinic", "real estate": "Real estate agency",
    "property": "Real estate agency", "travel": "Travel agency", "insurance": "Insurance agency", "architect": "Architecture studio",
    "restaurant": "Restaurant chain", "cafe": "Restaurant chain", "gym": "Gym chain", "hotel": "Budget hotel group", "pre-school": "Pre-school chain",
    "preschool": "Pre-school chain", "play school": "Pre-school chain", "apparel": "Apparel retail chain", "clothing": "Apparel retail chain",
    "electronics": "Electronics retail chain", "auto parts": "Auto-parts unit", "auto-parts": "Auto-parts unit", "textile": "Textile unit",
    "food processing": "Food processing unit", "furniture": "Furniture workshop", "packaging": "Packaging unit", "plastic": "Plastic moulding unit",
    "printing": "Printing press", "factory": "Auto-parts unit",
}
NEED_KEYWORDS = {
    "cctv": ["cctv", "camera", "कैमरा"], "whatsapp": ["whatsapp", "व्हाट्सएप", "catalogue"], "billing": ["billing", "pos", "बिलिंग", "invoice"],
    "guest_wifi": ["guest wifi", "customer wifi", "wi-fi for customers", "wifi for customers"], "email": ["email", "ईमेल"],
    "website": ["website", "वेबसाइट"], "backup": ["backup"], "security": ["virus", "antivirus", "ransomware", "security"],
    "failover": ["backup internet", "failover", "never down", "uptime"], "phone_lines": ["ivr", "call recording", "phone lines", "telephony"],
    "sms": ["sms", "reminder"], "fleet": ["vehicle", "truck", "delivery van", "fleet"], "iot_machines": ["machine"],
    "upi_pos": ["upi", "card payment", "पेमेंट"], "static_ip": ["static ip", "remote access"], "tollfree": ["toll free", "1800"],
}

HINDI_CITIES = {
    "दिल्ली": "Delhi", "मुंबई": "Mumbai", "बेंगलुरु": "Bengaluru", "बंगलौर": "Bengaluru", "पुणे": "Pune", "चेन्नई": "Chennai",
    "हैदराबाद": "Hyderabad", "कोलकाता": "Kolkata", "अहमदाबाद": "Ahmedabad", "भोपाल": "Bhopal", "कोयंबटूर": "Coimbatore",
    "इंदौर": "Indore", "जयपुर": "Jaipur", "कोच्चि": "Kochi", "लखनऊ": "Lucknow", "लुधियाना": "Ludhiana", "मैसूर": "Mysuru",
    "नागपुर": "Nagpur", "नासिक": "Nashik", "पटना": "Patna", "सूरत": "Surat", "वडोदरा": "Vadodara", "विशाखापत्तनम": "Visakhapatnam",
}

SLOT_ORDER = ["business_type", "city", "employees", "sites", "gstin", "needs"]

EXTRACT_SYSTEM = """You are the listening part of a telecom sales advisor for Indian small businesses.
Read the owner's message and return ONLY JSON with this shape:
{"business_type": one of %s or null,
 "business_name": str|null, "city": str|null (English city name), "employees": int|null, "sites": int|null,
 "gstin": str|null, "no_gstin": bool (true only if they clearly say they have no GST registration),
 "needs_add": [tags], "needs_remove": [tags], "requested_products": [product ids they explicitly ask for],
 "removed_products": [product ids they want removed], "budget": int|null (monthly rupees),
 "counts": {"mobile_lines":int,"cameras":int,"counters":int,"email_users":int,"devices":int,"vehicles":int,"machines":int,"phone_channels":int} (only those stated),
 "current_spend": int|null, "wants_human": bool, "accepts_plan": bool, "question": str|null (the owner's question if they asked one),
 "ack": "one short warm sentence in %s acknowledging what they said (no question, no prices)"}
Need tags: %s.
Products: %s.
Map business descriptions to the closest business_type (e.g. 'medical shop' -> Pharmacy, 'CA practice' -> CA firm, '3 cafes' -> Restaurant chain).
Never invent facts the owner did not say. Hindi/Hinglish and other Indian languages are common: read them carefully."""

EXPLAIN_SYSTEM = """You explain a telecom bundle to an Indian small-business owner in plain %s, like a helpful shopkeeper.
Rules: 4-6 short lines. Start with the monthly price and the price per day. Then one line per key product saying why it
helps THIS business (use the reasons given). If some products were not offered, say why in one friendly line and give the
alternative or tip. No product codes. No jargon (say 'internet line' not 'FTTH'). Do not change any number or add products."""


def _now() -> float:
    return time.time()


def _save() -> None:
    try:
        with _lock:
            slim = {k: {kk: vv for kk, vv in v.items() if kk != "last_reco"} for k, v in SESSIONS.items()}
            SESSIONS_FILE.write_text(json.dumps(slim, default=str), encoding="utf-8")
    except Exception:
        pass


def _load() -> None:
    if SESSIONS_FILE.exists():
        try:
            SESSIONS.update(json.loads(SESSIONS_FILE.read_text(encoding="utf-8")))
        except Exception:
            pass


_load()


def new_session(lang: str = "en", channel: str = "web") -> dict:
    sid = uuid.uuid4().hex[:10]
    s = {"id": sid, "lang": lang if lang in LANGS else "en", "channel": channel, "created": _now(), "updated": _now(),
         "profile": Profile(language=lang).to_dict(), "history": [], "stage": "discover", "asked": [], "status": "open",
         "models": [], "events": [], "no_gstin": False}
    SESSIONS[sid] = s
    msg = t("greeting", s["lang"])
    s["history"].append({"role": "assistant", "text": msg, "ts": _now()})
    _save()
    return {"session": sid, "reply": msg, "quick_replies": quick_replies("business_type", s), "stage": s["stage"]}


def _profile(s: dict) -> Profile:
    d = {k: v for k, v in s["profile"].items() if k in Profile.__dataclass_fields__}
    return Profile(**d)


def _set_profile(s: dict, p: Profile) -> None:
    s["profile"] = p.to_dict()


# ---------- extraction ----------

def _keyword_extract(text: str) -> dict:
    low = text.lower()
    out: dict = {"needs_add": [], "requested_products": [], "counts": {}}
    for kw, bt in sorted(KEYWORD_TYPES.items(), key=lambda kv: -len(kv[0])):
        if kw in low:
            out["business_type"] = bt
            break
    for c in CITY_TIER:
        if c.lower() in low or (c == "Bengaluru" and "bangalore" in low) or (c == "Mumbai" and "bombay" in low):
            out["city"] = c
            break
    for hc, c in HINDI_CITIES.items():
        if hc in text:
            out["city"] = c
    m = re.search(r"(\d+)\s*(?:people|staff|employees|workers|log|लोग|कर्मचारी|members|persons|person|employee)", low)
    if m:
        out["employees"] = int(m.group(1))
    m = re.search(r"(\d+)\s*(?:sites?|branch(?:es)?|outlets?|stores?|shops?|locations?|ब्रांच|दुकानें|दुकान)", low)
    if m:
        out["sites"] = int(m.group(1))
    m = re.search(r"\b(\d{2}[A-Z]{5}\d{4}[A-Z][0-9A-Z]Z[0-9A-Z])\b", text.upper())
    if m:
        out["gstin"] = m.group(1)
    if re.search(r"\b(no gst|without gst|not registered|gst nahi|जीएसटी नहीं|no gstin)\b", low):
        out["no_gstin"] = True
    for tag, kws in NEED_KEYWORDS.items():
        if any(k in low for k in kws):
            out["needs_add"].append(tag)
    for pid, kws in PRODUCT_ALIASES.items():
        if any(re.search(r"(?<![a-z])" + re.escape(k) + r"(?![a-z])", low) for k in kws):
            out["requested_products"].append(pid)
    if "P06" in out["requested_products"] and "P05" in out["requested_products"]:
        out["requested_products"].remove("P05")
    for pat, key in [(r"(\d+)\s*(?:delivery\s+)?(?:vans?|vehicles?|trucks?|bikes?)", "vehicles"), (r"(\d+)\s*(?:cctv\s+)?cameras?", "cameras"),
                     (r"(\d+)\s*(?:machines?|looms?)", "machines"), (r"(\d+)\s*(?:billing\s+)?counters?", "counters"),
                     (r"email\s+(?:ids?\s+)?for\s+(?:all\s+)?(\d+)", "email_users"), (r"(\d+)\s*(?:sims?|mobile\s+lines?|phone\s+lines?)", "mobile_lines")]:
        m = re.search(pat, low)
        if m:
            out["counts"][key] = int(m.group(1))
    m = re.search(r"(?:budget|under|within|max|upto|up to|बजट)\D{0,12}(\d[\d,]{2,6})", low)
    if m:
        out["budget"] = int(m.group(1).replace(",", ""))
    if any(k in low for k in ["human", "call me", "agent", "salesperson", "talk to someone", "बात करनी"]):
        out["wants_human"] = True
    if any(k in low for k in ["buy", "go ahead", "proceed", "confirm", "ठीक है", "हाँ", "yes, book"]):
        out["accepts_plan"] = True
    if "?" in text:
        out["question"] = text
    return out


def _extract(s: dict, text: str) -> tuple[dict, str]:
    kw = _keyword_extract(text)
    if not llm.available():
        return kw, "offline"
    # A short answer that already fills the slot we asked (usually a tapped chip): no model needed.
    asked = s["asked"][-1] if s["asked"] else None
    if asked and len(text) <= 30 and kw.get({"business_type": "business_type", "city": "city", "employees": "employees",
                                               "sites": "sites", "gstin": "gstin"}.get(asked, "_")):
        return kw, "rules"
    if asked == "business_type" and text in business_type_segment():
        return {**kw, "business_type": text}, "rules"
    cat = "; ".join(f"{r.product_id}={r.product_name}" for r in catalogue().itertuples())
    system = EXTRACT_SYSTEM % (json.dumps(BUSINESS_TYPES), LANGS[s["lang"]]["name"], ", ".join(NEEDS), cat)
    hist = "\n".join(f"{h['role']}: {h['text']}" for h in s["history"][-6:])
    prompt = f"Known so far: {json.dumps({k: s['profile'].get(k) for k in ['business_type','city','employees','sites','gstin','needs','budget']}, ensure_ascii=False)}\nRecent chat:\n{hist}\n\nOwner's new message: {text}"
    try:
        data, model = llm.json_call(prompt, system=system, timeout=9)
        # Keep keyword hits the model missed (cheap safety net), e.g. an exact GSTIN.
        for k in ("gstin", "city", "business_type", "employees", "sites", "budget"):
            if not data.get(k) and kw.get(k):
                data[k] = kw[k]
        data["needs_add"] = list(set((data.get("needs_add") or []) + kw.get("needs_add", [])))
        data["requested_products"] = list(set((data.get("requested_products") or []) + kw.get("requested_products", [])))
        return data, model
    except Exception:
        return kw, "offline"


# ---------- dialogue policy ----------

def _missing(s: dict) -> list[str]:
    p = s["profile"]
    miss = []
    if not p.get("business_type"):
        miss.append("business_type")
    if not p.get("city"):
        miss.append("city")
    if not p.get("employees"):
        miss.append("employees")
    seg = infer_segment(_profile(s))
    if not p.get("sites") and (seg in ("multi", "mfg", "prof") or "chain" in (p.get("business_type") or "").lower()):
        miss.append("sites")
    if not p.get("gstin") and not s.get("no_gstin"):
        miss.append("gstin")
    if not p.get("needs_confirmed"):
        miss.append("needs")
    return miss


def quick_replies(slot: str, s: dict) -> list[dict]:
    lang = s["lang"]
    if slot == "business_type":
        return [{"label": t(f"bt_{k}", lang), "value": v} for k, v in
                [("kirana", "Kirana store"), ("clinic", "Dental clinic"), ("ca", "CA firm"), ("salon", "Salon"),
                 ("restaurant", "Restaurant chain"), ("factory", "Auto-parts unit"), ("coaching", "Coaching centre"), ("pharmacy", "Pharmacy")]]
    if slot == "city":
        return [{"label": c, "value": c} for c in ["Delhi", "Mumbai", "Bengaluru", "Pune", "Jaipur", "Lucknow", "Nagpur", "Kochi"]]
    if slot == "employees":
        return [{"label": x, "value": v} for x, v in [("1-3", "3 people"), ("4-9", "6 people"), ("10-25", "15 people"), ("26-100", "50 people"), ("100+", "120 people")]]
    if slot == "sites":
        return [{"label": x, "value": v} for x, v in [("1", "1 site"), ("2", "2 sites"), ("3-5", "4 sites"), ("6-12", "8 sites")]]
    if slot == "gstin":
        return [{"label": t("qr_type_gstin", lang), "value": "__type_gstin__"}, {"label": t("qr_no_gstin", lang), "value": "__no_gstin__"}]
    return []


def _needs_payload(s: dict) -> dict:
    p = _profile(s)
    seg = infer_segment(p)
    mentioned = set(p.needs or [])
    # Micro shops are the most price-sensitive: pre-tick only what they asked for + reliable internet and mobile.
    defaults = mentioned | ({"upi_pos", "mobile"} if seg == "micro" else set(default_needs(p)))
    pool = list(dict.fromkeys(list(defaults) + default_needs(p) + {"micro": ["cctv", "website", "guest_wifi", "billing"], "prof": ["backup", "failover", "website", "phone_lines"],
                                                  "multi": ["guest_wifi", "phone_lines", "tollfree", "firewall"], "mfg": ["iot_machines", "fleet", "cctv", "firewall"]}[seg]))
    li = 1 if s["lang"] == "hi" else 0
    return {"options": [{"tag": n, "label": NEEDS[n][li], "checked": n in defaults} for n in pool if n in NEEDS]}


def _ask(s: dict, slot: str) -> tuple[str, dict]:
    p = s["profile"]
    lang = s["lang"]
    if slot == "needs":
        bt = p.get("business_type") or ""
        return t("ask_needs", lang, business=bt.lower() or t("your_business", lang)), {"needs": _needs_payload(s)}
    return t(f"ask_{slot}", lang), {"quick_replies": quick_replies(slot, s)}


def _apply(s: dict, ex: dict) -> list[str]:
    """Merge extracted facts; returns notes about what changed (for the UI timeline)."""
    p = _profile(s)
    notes = []
    if ex.get("gstin"):
        pre = registry.prefill(ex["gstin"])
        if pre["ok"]:
            k = pre["known"]
            p.gstin, p.gstin_status = k["gstin"], k["gstin_status"]
            p.business_name = p.business_name or k["business_name"]
            p.constitution, p.udyam = k["constitution"], k["udyam"]
            if p.city and p.city != k["city"]:
                notes.append("city_differs")
                s["registered_city"] = k["city"]
            p.city = p.city or k["city"]
            p.state, p.pincode = k["state"], k["pincode"]
            p.tier = CITY_TIER.get(p.city)
            if k.get("business_type") and not p.business_type:
                p.business_type = k["business_type"]
            if k.get("employees") and not p.employees:
                p.employees, p.sites = k["employees"], k["sites"]
                p.current_internet, p.current_spend = k.get("current_internet") or "", k.get("current_spend")
            s["registry"] = k
            notes.append("registry_prefill")
        else:
            s["gstin_error"] = pre["gstin"]["format"]["problems"] or ["not found"]
            notes.append("gstin_not_found")
    if ex.get("no_gstin"):
        s["no_gstin"] = True
        p.gstin, p.gstin_status = "", ""
    bt = ex.get("business_type")
    if bt and bt in business_type_segment():
        p.business_type = bt
    if ex.get("business_name"):
        p.business_name = ex["business_name"]
    if ex.get("city"):
        c = str(ex["city"]).strip().title().replace("Bangalore", "Bengaluru").replace("Bombay", "Mumbai").replace("Gurgaon", "Delhi")
        p.city = c
        p.tier = CITY_TIER.get(c)
        if p.tier is None:
            p.tier = 2
            notes.append("city_unlisted")
    for k in ("employees", "sites", "budget", "current_spend"):
        v = ex.get(k)
        if isinstance(v, (int, float)) and v > 0:
            setattr(p, k, int(v))
    if p.business_type and not p.sites and infer_segment(p) == "micro":
        p.sites = 1
    needs = set(p.needs or [])
    if ex.get("needs_add"):
        needs |= {n for n in ex["needs_add"] if n in NEEDS}
    if ex.get("needs_remove"):
        needs -= set(ex["needs_remove"])
    if needs != set(p.needs or []):
        p.needs = sorted(needs)
    req = set(p.requested or [])
    req |= {x for x in ex.get("requested_products") or [] if x in catalogue().index}
    req -= set(ex.get("removed_products") or [])
    p.requested = sorted(req)
    if ex.get("removed_products"):
        s.setdefault("addons_off", [])
        s["addons_off"] = sorted(set(s["addons_off"]) | set(ex["removed_products"]))
    for k, v in (ex.get("counts") or {}).items():
        if isinstance(v, (int, float)) and v > 0:
            p.counts[k] = int(v)
    p.segment = infer_segment(p) if p.business_type or p.employees else ""
    _set_profile(s, p)
    return notes


def _feasibility(s: dict) -> None:
    p = _profile(s)
    if p.pincode:
        f = registry.fibre_feasible(p.pincode, p.tier)
        p.fibre_feasible = f["feasible"]
        s["feasibility"] = f
        _set_profile(s, p)


def build_reco(s: dict) -> dict:
    _feasibility(s)
    p = _profile(s)
    addons = {pid: True for pid in s.get("addons_on", [])}
    addons.update({pid: False for pid in s.get("addons_off", [])})
    reco = recommend(p, addons=addons, term=s.get("term", 12), qty_override=s.get("qty", {}))
    # Budget first: if the owner gave a budget and a lean plan fits it, lead with that plan
    # (extras stay one tap away as add-ons).
    bn = reco.get("budget_note")
    if bn and bn["fits"] and not s.get("budget_applied"):
        s["budget_applied"] = True
        s["term"] = 24
        lean = bn["items"]
        s["addons_off"] = sorted(set(s.get("addons_off", [])) | {l["product_id"] for l in reco["lines"] if l["product_id"] not in lean})
        s.setdefault("qty", {}).update({pid: q for pid, q in lean.items() if pid in ("P07", "P08")})
        addons = {pid: False for pid in s["addons_off"]}
        reco = recommend(_profile(s), addons=addons, term=24, qty_override=s["qty"])
        reco["budget_applied"] = True
    s["last_reco"] = reco
    s["quote_monthly"] = reco["monthly"]
    return reco


def _explain(s: dict, reco: dict) -> tuple[str, str]:
    lang = s["lang"]
    facts = {
        "monthly_price_inr": reco["monthly"], "price_per_day_inr": reco["per_day"], "one_time_setup_inr": reco["setup"],
        "contract_months": reco["contract_months"],
        "products": [{"name": l["name"], "qty": l["qty"], "why": l["why"]} for l in reco["lines"]],
        "not_offered": [{"name": e["name"], "why": e["reasons"], "alternative": e["alternative_name"], "tip": e["tip"]} for e in reco["excluded"]],
        "business": {k: s["profile"].get(k) for k in ("business_type", "city", "employees", "sites")},
        "budget_note": reco.get("budget_note") and {"budget": s["profile"].get("budget"), "lean_monthly": reco["budget_note"]["monthly"]},
    }
    if llm.available():
        try:
            txt, model = llm.text(json.dumps(facts, ensure_ascii=False), system=EXPLAIN_SYSTEM % LANGS[lang]["name"], timeout=12)
            return txt.strip(), model
        except Exception:
            pass
    lines = [t("reco_head", lang, monthly=f"{reco['monthly']:,}", per_day=reco["per_day"])]
    lines += [f"• {l['name']} ×{l['qty']}: {l['why']}" for l in reco["lines"][:5]]
    for e in reco["excluded"]:
        lines.append(f"• {e['name']}: {e['reasons'][0]}" + (f" → {e['alternative_name']}" if e["alternative_name"] else "") + (f" {e['tip']}" if e["tip"] else ""))
    return "\n".join(lines), "offline"


def _answer(s: dict, question: str) -> str | None:
    """Short factual answer grounded in the catalogue and the current quote."""
    if not llm.available():
        return None
    reco = s.get("last_reco")
    ctx = {"catalogue": [{"id": r.product_id, "name": r.product_name, "desc": r.description, "price_range": f"₹{r.price_min_inr_per_month}-{r.price_max_inr_per_month}",
                          "setup": r.one_time_setup_inr, "min_contract": r.min_contract_months, "install_days": r.typical_install_days,
                          "needs_gstin": r.requires_gstin} for r in catalogue().itertuples()],
           "current_quote": reco and {"monthly": reco["monthly"], "lines": [(l["name"], l["qty"], l["monthly"]) for l in reco["lines"]],
                                       "not_offered": [(e["name"], e["reasons"]) for e in reco["excluded"]]}}
    try:
        txt, _ = llm.text(f"Context: {json.dumps(ctx, ensure_ascii=False)}\n\nQuestion: {question}",
                          system=f"Answer the small-business owner's question in 1-3 short sentences in {LANGS[s['lang']]['name']}, using only the context. "
                                 "If it's not in the context, say a specialist will confirm. Never invent prices.", timeout=15)
        return txt.strip()
    except Exception:
        return None


def turn(sid: str, text: str) -> dict:
    s = SESSIONS.get(sid)
    if not s:
        return {"error": "unknown session"}
    text = (text or "").strip()
    s["updated"] = _now()
    lang = s["lang"]

    # Structured shortcuts from buttons
    if text == "__no_gstin__":
        s["no_gstin"] = True
        text_for_history = t("qr_no_gstin", lang)
        ex, model = {}, "ui"
    elif text.startswith("__needs__:"):
        tags = [x for x in text.split(":", 1)[1].split(",") if x in NEEDS]
        p = _profile(s)
        p.needs, p.needs_confirmed = tags, True
        _set_profile(s, p)
        text_for_history = ", ".join(NEEDS[x][1 if lang == "hi" else 0] for x in tags) or "—"
        ex, model = {}, "ui"
    else:
        text_for_history = text
        ex, model = _extract(s, text)
    s["history"].append({"role": "user", "text": text_for_history, "ts": _now()})
    s["models"].append(model)
    notes = _apply(s, ex)

    payload: dict = {"session": sid, "extracted": {k: v for k, v in ex.items() if v and k not in ("ack",)}, "model": model, "notes": notes}
    parts = []
    if ex.get("ack"):
        parts.append(ex["ack"])
    if "registry_prefill" in notes:
        k = s["registry"]
        parts.append(t("registry_found", lang, name=k["business_name"], city=k["city"], status=k["gstin_status"],
                       since=k["registered_since"][:4], btype=k.get("business_type") or "—"))
        if k["gstin_status"] != "Active":
            parts.append(t("gst_inactive", lang, status=k["gstin_status"].lower()))
        payload["registry"] = k
    if "gstin_not_found" in notes:
        parts.append(t("gstin_bad", lang, problem="; ".join(s.get("gstin_error", []))))
    if "city_differs" in notes:
        parts.append(f"Note: your GST address is in {s['registered_city']}. I'll plan for {s['profile'].get('city')} as you said; we confirm the installation address at KYC.")
    if "city_unlisted" in notes:
        parts.append(t("city_unlisted", lang))

    if ex.get("wants_human"):
        s["status"] = "handoff"
        s["handoff_reason"] = "Owner asked for a person"
        parts.append(t("handoff", lang))
        payload.update(reply="\n".join(parts), stage="handoff")
        _finish(s, payload)
        return payload

    if ex.get("question") and s.get("last_reco") and not any(ex.get(k) for k in ("needs_add", "requested_products", "removed_products", "budget", "employees", "sites", "city")):
        ans = _answer(s, ex["question"])
        if ans:
            parts.append(ans)
            payload.update(reply="\n\n".join(parts), stage=s["stage"], reco=s["last_reco"])
            _finish(s, payload)
            return payload

    missing = _missing(s)
    if missing:
        slot = missing[0]
        q, extra = _ask(s, slot)
        parts.append(q)
        s["stage"] = "needs" if slot == "needs" else "discover"
        s["asked"].append(slot)
        payload.update(reply="\n\n".join(p for p in parts if p), stage=s["stage"], ask=slot, **extra)
    else:
        reco = build_reco(s)
        expl, emodel = _explain(s, reco)
        s["models"].append(emodel)
        s["stage"] = "quote"
        parts.append(expl)
        if ex.get("accepts_plan"):
            parts.append(t("go_checkout", lang))
            payload["go"] = "checkout"
        payload.update(reply="\n\n".join(p for p in parts if p), stage="quote", reco=reco, explain_model=emodel)
    _finish(s, payload)
    return payload


def _finish(s: dict, payload: dict) -> None:
    s["history"].append({"role": "assistant", "text": payload.get("reply", ""), "ts": _now()})
    payload["profile"] = s["profile"]
    _save()


def update_quote(sid: str, addons: dict[str, bool] | None = None, term: int | None = None, qty: dict | None = None) -> dict:
    s = SESSIONS[sid]
    for pid, on in (addons or {}).items():
        on_l, off_l = set(s.get("addons_on", [])), set(s.get("addons_off", []))
        (on_l.add if on else on_l.discard)(pid)
        (off_l.discard if on else off_l.add)(pid)
        s["addons_on"], s["addons_off"] = sorted(on_l), sorted(off_l)
    if term:
        s["term"] = int(term)
    if qty:
        s.setdefault("qty", {}).update({k: int(v) for k, v in qty.items()})
    reco = build_reco(s)
    _save()
    return {"session": sid, "reco": reco}


def session_summary(s: dict) -> dict:
    p = s["profile"]
    return {"id": s["id"], "lang": s["lang"], "channel": s.get("channel", "web"), "status": s["status"], "stage": s["stage"],
            "business": p.get("business_name") or p.get("business_type") or "Unknown", "type": p.get("business_type"),
            "city": p.get("city"), "employees": p.get("employees"), "sites": p.get("sites"), "segment": p.get("segment"),
            "gst": p.get("gstin_status") or ("none" if s.get("no_gstin") else "?"), "quote": s.get("quote_monthly"),
            "turns": sum(1 for h in s["history"] if h["role"] == "user"), "updated": s["updated"],
            "handoff_reason": s.get("handoff_reason"), "order_id": s.get("order_id")}
