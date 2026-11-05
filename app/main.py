"""Ek Baithak API + static web app.  Run:  python -m uvicorn app.main:app --port 8000"""
from __future__ import annotations

import logging
import threading
import time

import numpy as np
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import advisor, analytics, config, llm, orders, privacy, registry
from .config import ROOT
from .data import catalogue
from .i18n import LANGS, table
from .kyc import lab, verify
from .recommender import NEEDS, audit_historical_bundles

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
app = FastAPI(title="Ek Baithak · Accel Business onboarding", version="1.0")
KYC_RESULTS: dict[str, dict] = {}
LAB_CACHE: dict[str, dict] = {}


def clean(o):
    """numpy -> plain Python for JSON."""
    if isinstance(o, dict):
        return {str(k): clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple, set)):
        return [clean(v) for v in o]
    if isinstance(o, np.integer):
        return int(o)
    if isinstance(o, np.floating):
        return None if np.isnan(o) else float(o)
    if isinstance(o, float) and o != o:
        return None
    return o


def J(o):
    return JSONResponse(clean(o))


def _warm():
    """Train the lead model and OCR the specimen pack in the background so demos are instant."""
    try:
        analytics.model()
        for k in lab.applicant_ids():
            LAB_CACHE[k] = lab.run(k)
        logging.info("warm-up done")
    except Exception as e:
        logging.exception("warm-up failed: %s", e)


@app.on_event("startup")
def startup():
    threading.Thread(target=_warm, daemon=True).start()


# ---------------- meta ----------------
@app.get("/api/meta")
def meta():
    return J({"languages": LANGS, "i18n": table(), "needs": NEEDS, "llm": {"available": llm.available(), "offline_mode": config.OFFLINE_MODE,
              "stats": llm.STATS}, "today": str(config.TODAY)})


@app.get("/api/catalogue")
def get_catalogue():
    return J(catalogue().drop(columns=["tiers", "needs_one_of", "segments"]).to_dict("records"))


# ---------------- advisor ----------------
class StartReq(BaseModel):
    lang: str = "en"
    channel: str = "web"


class MsgReq(BaseModel):
    session: str
    text: str


class QuoteReq(BaseModel):
    session: str
    addons: dict[str, bool] | None = None
    term: int | None = None
    qty: dict[str, int] | None = None


@app.post("/api/advisor/start")
def advisor_start(r: StartReq):
    out = advisor.new_session(r.lang, r.channel)
    privacy.audit("system", "session.start", out["session"], f"lang={r.lang} channel={r.channel}")
    return J(out)


@app.post("/api/advisor/message")
def advisor_message(r: MsgReq):
    if r.session not in advisor.SESSIONS:
        raise HTTPException(404, "session not found")
    t = time.time()
    out = advisor.turn(r.session, r.text)
    out["latency_ms"] = int((time.time() - t) * 1000)
    return J(out)


@app.post("/api/advisor/voice")
async def advisor_voice(session: str = Form(...), audio: UploadFile = File(...)):
    s = advisor.SESSIONS.get(session)
    if not s:
        raise HTTPException(404, "session not found")
    data = await audio.read()
    try:
        text, model = llm.transcribe(data, audio.content_type or "audio/webm", LANGS[s["lang"]]["name"])
    except Exception as e:
        return J({"error": "Couldn't hear that clearly. Please type, or try again.", "detail": str(e)[:200]})
    out = advisor.turn(session, text.strip())
    out["transcript"] = text.strip()
    out["transcribe_model"] = model
    return J(out)


@app.post("/api/advisor/quote")
def advisor_quote(r: QuoteReq):
    if r.session not in advisor.SESSIONS:
        raise HTTPException(404, "session not found")
    return J(advisor.update_quote(r.session, r.addons, r.term, r.qty))


@app.get("/api/advisor/session/{sid}")
def advisor_session(sid: str):
    s = advisor.SESSIONS.get(sid)
    if not s:
        raise HTTPException(404)
    return J({k: v for k, v in s.items()})


# ---------------- registry (mock government APIs) ----------------
@app.get("/api/registry/gstin/{g}")
def reg_gstin(g: str):
    privacy.audit("system", "registry.gstin", g)
    return J(registry.lookup_gstin(g))


@app.get("/api/registry/udyam/{u}")
def reg_udyam(u: str):
    return J(registry.lookup_udyam(u))


@app.get("/api/registry/prefill/{g}")
def reg_prefill(g: str):
    return J(registry.prefill(g))


@app.get("/api/registry/feasibility/{pincode}")
def reg_feasible(pincode: str, tier: int = 2):
    return J(registry.fibre_feasible(pincode, tier))


# ---------------- consent ----------------
class ConsentReq(BaseModel):
    session: str
    purposes: dict[str, bool]


@app.get("/api/consent/notice")
def consent_notice():
    return J({"version": privacy.NOTICE_VERSION, "purposes": privacy.PURPOSES})


@app.post("/api/consent")
def consent(r: ConsentReq):
    s = advisor.SESSIONS.get(r.session)
    if not s:
        raise HTTPException(404)
    res = privacy.record_consent(r.session, r.purposes, s["lang"])
    if res["ok"]:
        s["consent_id"] = res["consent"]["id"]
        advisor._save()
    return J(res)


@app.post("/api/consent/{cid}/withdraw/{purpose}")
def consent_withdraw(cid: str, purpose: str):
    return J(privacy.withdraw(cid, purpose))


# ---------------- KYC ----------------
def _ctx(s: dict) -> dict:
    p = s["profile"]
    return {"gstin": p.get("gstin"), "udyam": p.get("udyam"), "business_name": p.get("business_name"),
            "contact_name": s.get("contact_name") or (s.get("registry") or {}).get("contact_name")}


def _need_consent(session: str) -> dict:
    s = advisor.SESSIONS.get(session)
    if not s:
        raise HTTPException(404, "session not found")
    if not s.get("consent_id"):
        raise HTTPException(403, "Consent is required before KYC")
    return s


def _kyc_result(session: str, res: dict, source: str) -> dict:
    s = advisor.SESSIONS[session]
    KYC_RESULTS[session] = res
    s["kyc_verdict"] = res["verdict"]
    s["stage"] = "kyc"
    advisor._save()
    privacy.audit("system", f"kyc.{source}", session, f"verdict={res['verdict']} issues={[c['id'] for c in res['issues']]}")
    # If GST is cancelled/suspended, show the owner the bundle they can buy today.
    if res["verdict"] == "RESTRICTED" and s.get("last_reco"):
        res["restricted_bundle"] = [l for l in s["last_reco"]["lines"] if catalogue().loc[l["product_id"]].requires_gstin != "Y"]
    return res


@app.post("/api/kyc/upload")
async def kyc_upload(session: str = Form(...), files: list[UploadFile] = File(...)):
    s = _need_consent(session)
    docs = [{"filename": f.filename, "data": await f.read()} for f in files]
    res = verify.verify_applicant(docs, _ctx(s))
    # Images were processed in memory only; drop the bytes now (retention: none).
    del docs
    return J(_kyc_result(session, res, "upload"))


@app.post("/api/kyc/sample/{kid}")
def kyc_sample(kid: str, session: str):
    s = _need_consent(session)
    docs = lab.applicant_docs(kid)
    if not docs:
        raise HTTPException(404)
    ctx = lab.crm_context(docs)
    # The demo session borrows the specimen applicant's identity.
    if ctx.get("gstin"):
        pre = registry.prefill(ctx["gstin"])
        if pre["ok"]:
            k = pre["known"]
            s["profile"].update(business_name=k["business_name"], gstin=k["gstin"], gstin_status=k["gstin_status"], city=k["city"],
                                constitution=k["constitution"], udyam=k["udyam"])
    s["contact_name"] = ctx.get("contact_name")
    res = verify.verify_applicant(docs, ctx)
    res["applicant"] = kid
    return J(_kyc_result(session, res, f"sample.{kid}"))


@app.post("/api/kyc/locker")
def kyc_locker(session: str):
    s = _need_consent(session)
    cons = privacy.CONSENTS.get(s["consent_id"], {})
    if not cons.get("purposes", {}).get("registry"):
        raise HTTPException(403, "Registry/Entity Locker consent not given")
    g = s["profile"].get("gstin")
    if not g:
        raise HTTPException(400, "Enter a GSTIN first")
    pull = registry.entity_locker_fetch(g)
    if not pull["ok"]:
        return J({"ok": False, "reason": pull["reason"]})
    rec = registry.lookup_gstin(g)["record"]
    status = rec["status"]
    checks = [verify._check("locker", "Documents fetched from Entity Locker", "pass", f"{len(pull['docs'])} issuer-verified documents (GST{', Udyam' if len(pull['docs']) > 1 else ''})."),
              verify._check("gstin_status", "GST registration is active", "pass" if status == "Active" else "restricted",
                            f"Registry status: {status}.", owner=None if status == "Active" else "Your GST shows as inactive; you can still buy non-GST products today.")]
    checks.append(verify._check("bill_present", "Address proof", "action", "Upload a utility bill from the last 90 days (Entity Locker has no utility bills).",
                                fix="Upload a recent bill.", owner="One photo left: an electricity or phone bill from the last 3 months."))
    checks.append(verify._check("id_present", "Signatory identity", "action", "Verify with Aadhaar e-KYC (OTP) at signing.",
                                fix="Aadhaar OTP at signing.", owner="We'll confirm your identity with an Aadhaar OTP when you sign. No ID photo needed."))
    res = verify._verdict(checks, {}, [{"type": d["type"], "source": "Entity Locker", "uri": d["uri"], "sha256": d["sha256"]} for d in pull["docs"]], rec)
    res["locker"] = pull
    return J(_kyc_result(session, res, "locker"))


@app.get("/api/kyc/lab")
def kyc_lab():
    out = []
    for k in lab.applicant_ids():
        r = LAB_CACHE.get(k) or lab.run(k)
        LAB_CACHE[k] = r
        exp = lab.EXPECTED.get(k, ("?", set()))
        out.append({"applicant": k, "verdict": r["verdict"], "headline": r["headline"], "expected": exp[0],
                    "match": r["verdict"] == exp[0] and exp[1] <= {c["id"] for c in r["issues"]},
                    "business": (r.get("business") or {}).get("trade_name") or r.get("context", {}).get("business_name"),
                    "issues": [{"id": c["id"], "status": c["status"], "label": c["label"], "detail": c["detail"], "owner": c["owner_message"]} for c in r["issues"]],
                    "auto": [c["detail"] for c in r["checks"] if c["status"] == "pass" and ("Straightened" in c["detail"] or "registry" in c["detail"].lower() and "fetched" in c["detail"].lower())]})
    return J({"results": out, "score": sum(x["match"] for x in out), "total": len(out)})


@app.get("/api/kyc/lab/{kid}")
def kyc_lab_one(kid: str):
    r = LAB_CACHE.get(kid) or lab.run(kid)
    LAB_CACHE[kid] = r
    return J(r)


@app.get("/api/kyc/doc/{name}")
def kyc_doc(name: str):
    f = config.KYC_DIR / name
    if not f.exists() or f.suffix != ".png":
        raise HTTPException(404)
    return FileResponse(f)


# ---------------- orders / tracker ----------------
class OrderReq(BaseModel):
    session: str


@app.post("/api/order")
def order_create(r: OrderReq):
    s = advisor.SESSIONS.get(r.session)
    if not s or not s.get("last_reco"):
        raise HTTPException(400, "No quote yet")
    kyc = KYC_RESULTS.get(r.session)
    if kyc and kyc["verdict"] == "REVIEW":
        raise HTTPException(409, "KYC is under review")
    o = orders.create(s, s["last_reco"], kyc, s.get("consent_id"))
    s["order_id"], s["status"], s["stage"] = o["id"], "won", "order"
    advisor._save()
    privacy.audit("system", "order.created", r.session, f"{o['id']} monthly={o['monthly']}")
    return J({**o, "eta": orders.eta(o)})


class SignReq(BaseModel):
    signer: str = "Owner"
    method: str = "aadhaar_otp"


@app.post("/api/order/{oid}/esign")
def order_esign(oid: str, r: SignReq):
    o = orders.esign(oid, r.signer, r.method)
    return J({**o, "eta": orders.eta(o)})


@app.post("/api/order/{oid}/pay")
def order_pay(oid: str):
    o = orders.pay(oid)
    return J({**o, "eta": orders.eta(o)})


@app.post("/api/order/{oid}/advance")
def order_advance(oid: str, days: int = 1):
    o = orders.advance(oid, days)
    return J({**o, "eta": orders.eta(o)})


@app.get("/api/order/{oid}")
def order_get(oid: str):
    o = orders.ORDERS.get(oid)
    if not o:
        raise HTTPException(404)
    return J({**o, "eta": orders.eta(o)})


# ---------------- back office ----------------
@app.get("/api/backoffice/funnel")
def bo_funnel():
    f = analytics.funnel()
    m = analytics.model()
    f["model"] = {"auc": m["auc"], "top20_capture": m["top20_capture"]}
    return J(f)


@app.get("/api/backoffice/sessions")
def bo_sessions():
    rows = []
    for s in sorted(advisor.SESSIONS.values(), key=lambda x: -x["updated"]):
        row = advisor.session_summary(s)
        if s["profile"].get("business_type") or s["profile"].get("employees"):
            sc = analytics.score_profile(s["profile"], s.get("channel", "web"))
            row.update(score=sc["score"], why=sc["why"])
        idle = time.time() - s["updated"]
        if row["status"] == "open" and idle > 600:
            row["status"] = "stalled"
        rows.append(row)
    return J({"sessions": rows})


@app.get("/api/backoffice/rescue")
def bo_rescue(limit: int = 100):
    return J(analytics.rescue_queue(limit))


@app.get("/api/backoffice/leads")
def bo_leads(limit: int = 50):
    return J({"leads": analytics.open_leads(limit), "model": {"auc": analytics.model()["auc"]}})


@app.get("/api/backoffice/audit")
def bo_audit():
    return J(audit_historical_bundles())


class SimReq(BaseModel):
    levers: dict[str, float] | None = None
    digital_share: float = 0.6


@app.post("/api/backoffice/simulate")
def bo_simulate(r: SimReq):
    return J(analytics.simulate(r.levers, r.digital_share))


@app.get("/api/backoffice/privacy-log")
def bo_privacy_log(limit: int = 50):
    return J({"audit": privacy.AUDIT[-limit:][::-1], "consents": len(privacy.CONSENTS)})


@app.get("/api/backoffice/live")
def bo_live():
    """Live KPIs from this running instance (sessions -> orders)."""
    ss = list(advisor.SESSIONS.values())
    os_ = list(orders.ORDERS.values())
    quoted = [s for s in ss if s.get("quote_monthly")]
    return J({"sessions": len(ss), "quoted": len(quoted), "orders": len(os_), "live": sum(o["status"] == "live" for o in os_),
              "handoffs": sum(s["status"] == "handoff" for s in ss),
              "avg_turns_to_quote": round(np.mean([sum(h["role"] == "user" for h in s["history"]) for s in quoted]), 1) if quoted else None,
              "support_calls": sum(o.get("calls_to_support", 0) for o in os_), "llm": llm.STATS})


# ---------------- my data (DPDP rights) ----------------
@app.get("/api/mydata/{sid}")
def mydata(sid: str):
    s = advisor.SESSIONS.get(sid)
    if not s:
        raise HTTPException(404)
    privacy.audit("owner", "data.access", sid)
    kyc = KYC_RESULTS.get(sid)
    return J({"profile": s["profile"], "consent": privacy.consent_for(sid),
              "kyc": kyc and {"verdict": kyc["verdict"], "verified_fields": {t: d["fields"] for t, d in kyc["documents"].items()},
                              "fetched": kyc["fetched_from_registry"], "images_stored": False},
              "order": orders.ORDERS.get(s.get("order_id") or ""), "chat": s["history"],
              "retention": {p: m["retention"] for p, m in privacy.PURPOSES.items()}})


@app.post("/api/mydata/{sid}/erase")
def mydata_erase(sid: str):
    s = advisor.SESSIONS.get(sid)
    if not s:
        raise HTTPException(404)
    kept = []
    if s.get("order_id"):
        kept.append("Verified KYC fields and signed application: telecom licence requires us to keep these while the connection is active.")
    s["history"] = [{"role": "system", "text": "[erased at owner's request]", "ts": time.time()}]
    if not s.get("order_id"):
        s["profile"] = {"language": s["lang"]}
        KYC_RESULTS.pop(sid, None)
    privacy.audit("owner", "data.erase", sid, "chat erased" + ("; KYC retained (legal)" if kept else "; all erased"))
    advisor._save()
    return J({"ok": True, "erased": ["chat history"] + ([] if s.get("order_id") else ["profile", "KYC results"]), "kept": kept})


# ---------------- WhatsApp Cloud API webhook (same advisor brain) ----------------
WA_SESSIONS: dict[str, str] = {}


@app.post("/webhook/whatsapp")
async def whatsapp(req: Request):
    """Accepts the WhatsApp Cloud API message payload. Replies are returned (in production, sent via the Graph API)."""
    body = await req.json()
    try:
        msg = body["entry"][0]["changes"][0]["value"]["messages"][0]
        wa_from = msg["from"]
        text = msg.get("text", {}).get("body", "")
    except (KeyError, IndexError):
        return J({"ok": True, "ignored": True})
    sid = WA_SESSIONS.get(wa_from)
    if not sid or sid not in advisor.SESSIONS:
        start = advisor.new_session("hi" if any("ऀ" <= ch <= "ॿ" for ch in text) else "en", "whatsapp")
        sid = WA_SESSIONS[wa_from] = start["session"]
        advisor.SESSIONS[sid]["wa_number"] = privacy.mask_text(wa_from)
    out = advisor.turn(sid, text)
    privacy.audit("system", "whatsapp.in", sid, f"from {wa_from}")
    reply = {"messaging_product": "whatsapp", "to": wa_from, "type": "text", "text": {"body": out.get("reply", "")}}
    if out.get("quick_replies"):
        reply = {"messaging_product": "whatsapp", "to": wa_from, "type": "interactive",
                 "interactive": {"type": "button", "body": {"text": out.get("reply", "")[:1000]},
                                 "action": {"buttons": [{"type": "reply", "reply": {"id": q["value"][:256], "title": q["label"][:20]}} for q in out["quick_replies"][:3]]}}}
    return J({"ok": True, "session": sid, "send": reply})


@app.get("/api/health")
def health():
    return J({"ok": True, "llm": llm.available(), "stats": llm.STATS, "lab_cached": len(LAB_CACHE)})


app.mount("/", StaticFiles(directory=ROOT / "web", html=True), name="web")
