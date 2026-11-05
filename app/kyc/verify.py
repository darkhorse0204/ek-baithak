"""Smart KYC: registry first, documents second, and the code (not the AI) decides.

Pipeline per document: quality gate -> auto-straighten -> local OCR (no data leaves the
server) -> field parse -> AI second reader only when the first read fails a hard check.
Then applicant-level checks against the GST / Udyam registries, dates, and the telecom
rule on who may sign. Every failed check carries a plain-language fix for the owner.
"""
from __future__ import annotations

import datetime as dt
import difflib
import hashlib
import json
import threading

from .. import gstin as G
from .. import llm, registry
from ..config import ADDRESS_PROOF_MAX_AGE_DAYS, CACHE_DIR, TODAY
from . import imaging, parse
from .parse import key

CACHE_FILE = CACHE_DIR / "ocr_cache.json"
# Results of reading the 12 specimen applicants, shipped with the repo so a fresh copy starts in seconds.
SEED_FILE = CACHE_DIR.parent / "data" / "ocr_cache_seed.json"
_cache_lock = threading.Lock()
_CACHE = {}
for _f in (SEED_FILE, CACHE_FILE):
    try:
        if _f.exists():
            _CACHE.update(json.loads(_f.read_text(encoding="utf-8")))
    except Exception:
        pass

DOC_NAMES = {"gst_certificate": "GST certificate", "udyam_certificate": "Udyam certificate",
             "address_proof": "Address proof", "signatory_id": "Signatory ID"}
AUTHORISED_DESIGNATIONS = {
    "Proprietorship": None,  # proprietor in person, checked by name
    "Limited Liability Partnership": {"partner", "designatedpartner"},
    "Private Limited Company": {"director", "manageddirector", "managingdirector", "wholetimedirector"},
}
AUTH_DOC = {
    "Proprietorship": "a signed authorisation letter from the proprietor",
    "Limited Liability Partnership": "an authorisation letter signed by a designated partner",
    "Private Limited Company": "a board resolution naming this person as authorised signatory",
}


def _save_cache() -> None:
    with _cache_lock:
        CACHE_FILE.write_text(json.dumps(_CACHE), encoding="utf-8")


def similar(a: str | None, b: str | None) -> float:
    ka, kb = key(a), key(b)
    if not ka or not kb:
        return 0.0
    return difflib.SequenceMatcher(None, ka, kb).ratio()


def read_document(data: bytes, filename: str = "") -> dict:
    """Quality gate + OCR + parse for one image. Cached by content hash."""
    h = hashlib.sha256(data).hexdigest()
    if h in _CACHE:
        return {**_CACHE[h], "cached": True}
    im = imaging.load(data)
    q = imaging.quality(im)
    out = {"sha256": h[:16], "filename": filename, "quality": q, "auto_fixes": []}
    if q["blurry"]:
        out.update(doc_type=_guess_type(filename), fields={}, readable=False)
    else:
        if q["skewed"]:
            im = imaging.deskew(im, q["skew_degrees"])
            out["auto_fixes"].append(f"Straightened a {abs(q['skew_degrees']):.0f}° tilt")
        lines = imaging.ocr(im)
        ex = parse.extract(lines)
        if ex["doc_type"] == "unknown":
            ex["doc_type"] = _guess_type(filename)
        out.update(doc_type=ex["doc_type"], fields=ex["fields"], readable=bool(ex["fields"]),
                   ocr_confidence=round(sum(l["conf"] for l in lines) / max(len(lines), 1), 3))
    _CACHE[h] = out
    _save_cache()
    return out


def _guess_type(filename: str) -> str:
    f = (filename or "").lower()
    for t in DOC_NAMES:
        if t.split("_")[0] in f:
            return t
    return "unknown"


def second_reader_gstin(data: bytes) -> dict:
    """Ask the AI to read the GSTIN independently. Used only when our read fails the checksum."""
    h = "ai:" + hashlib.sha256(data).hexdigest()
    if h in _CACHE:
        return _CACHE[h]
    try:
        res, model = llm.vision_json(
            'Read the GSTIN printed on this GST certificate exactly as printed. Return JSON {"gstin": "...", "confident": true|false}. '
            "Do not correct it and do not guess unreadable characters.", data, timeout=35)
        out = {"ok": True, "gstin": G.normalise_ocr(str(res.get("gstin", ""))), "confident": bool(res.get("confident")), "model": model}
    except Exception as e:
        out = {"ok": False, "error": str(e)[:200]}
    if out.get("ok"):
        _CACHE[h] = out
        _save_cache()
    return out


def _check(cid, label, status, detail, fix=None, owner=None, evidence=None):
    return {"id": cid, "label": label, "status": status, "detail": detail, "fix": fix, "owner_message": owner or fix,
            "evidence": evidence or {}}


def verify_applicant(docs: list[dict], context: dict | None = None, use_ai: bool = True) -> dict:
    """docs: [{"filename", "data"(bytes) or "reading"(dict)}]. context: {gstin, contact_name, udyam, ...}."""
    context = context or {}
    readings = {}
    raw = {}
    for d in docs:
        r = d.get("reading") or read_document(d["data"], d.get("filename", ""))
        readings[r["doc_type"]] = r
        if "data" in d:
            raw[r["doc_type"]] = d["data"]

    checks = []
    fetched = []
    gst = readings.get("gst_certificate")
    ud = readings.get("udyam_certificate")
    bill = readings.get("address_proof")
    sid = readings.get("signatory_id")

    # 1. Image quality per document
    for t, r in readings.items():
        q = r["quality"]
        if not r.get("readable", True) or q["blurry"]:
            checks.append(_check(f"quality_{t}", f"{DOC_NAMES.get(t, t)} is readable", "fail",
                                 f"Image is too blurry to read (sharpness {q['sharpness']}, needs ≥ {imaging.BLUR_THRESHOLD:.0f}).",
                                 fix="Retake the photo flat, in good light, or fetch it from Entity Locker in one tap.",
                                 owner=f"Your {DOC_NAMES.get(t, t)} photo is blurry. Please retake it in good light, or tap 'Fetch from Entity Locker' and skip the upload."))
        elif r.get("auto_fixes"):
            checks.append(_check(f"quality_{t}", f"{DOC_NAMES.get(t, t)} is readable", "pass",
                                 "; ".join(r["auto_fixes"]) + " automatically before reading."))
        else:
            checks.append(_check(f"quality_{t}", f"{DOC_NAMES.get(t, t)} is readable", "pass", f"Sharp and straight (sharpness {q['sharpness']})."))

    # 2. GSTIN: format, checksum, second reader, registry
    reg_rec = None
    gstin_value = None
    if gst and gst.get("readable"):
        g = gst["fields"].get("gstin", "")
        v = G.validate(g)
        if not v["valid"]:
            cands = G.ocr_candidates(g)
            if len(cands) == 1:
                g, v = cands[0], G.validate(cands[0])
                checks.append(_check("gstin_checksum", "GSTIN check digit", "pass", f"Read {G.mask(gst['fields'].get('gstin_raw'))}; one O/0 reading passes the check digit."))
            else:
                second = second_reader_gstin(raw["gst_certificate"]) if (use_ai and "gst_certificate" in raw) else {"ok": False}
                agree = second.get("ok") and second.get("gstin") == g
                near = registry.near_gstins(g)
                detail = f"GSTIN on the certificate ({g}) fails the check digit: it was mistyped or edited."
                if second.get("ok"):
                    detail += f" AI second reader ({second['model']}) read {second['gstin']} — " + ("same as our read, so it's the document, not the OCR." if agree else "different from our read.")
                if near:
                    n = near[0]
                    pos = "; ".join(f"position {d['position']}: certificate '{d['document']}', registry '{d['registry']}'" for d in n.get("diffs", []))
                    detail += f" Registry has {n['gstin']} ({n['legal_name']}), {pos or 'similar number'}."
                checks.append(_check("gstin_checksum", "GSTIN check digit", "review", detail,
                                     fix="Send to back-office review. Do not activate GST-dependent products.",
                                     owner="The GST number on your certificate doesn't match government records. Please type your GSTIN, or fetch your certificate from Entity Locker, and we'll recheck instantly.",
                                     evidence={"read": g, "second_reader": second, "near_matches": near}))
        else:
            checks.append(_check("gstin_checksum", "GSTIN check digit", "pass", f"{G.mask(g, 2, 3)} has a valid check digit (state: {v['state']})."))
        gstin_value = g
        typed = (context.get("gstin") or "").upper()
        if typed and G.validate(typed)["valid"] and typed != g and not any(c["status"] == "review" for c in checks if c["id"] == "gstin_checksum"):
            checks.append(_check("gstin_matches_entered", "Certificate GSTIN matches the one entered", "review",
                                 f"Certificate shows {g}, but the owner entered {typed}.", fix="Back-office review.",
                                 owner="The GSTIN on your certificate is different from the one you typed. Please check which is right."))
        if typed and G.validate(typed)["valid"] and typed != g:
            gstin_value = typed
    elif context.get("gstin"):
        gstin_value = context["gstin"]

    if gstin_value:
        look = registry.lookup_gstin(gstin_value)
        if look["found"]:
            reg_rec = look["record"]
            st = reg_rec["status"]
            if st == "Active":
                checks.append(_check("gstin_status", "GST registration is active", "pass", f"Active since {reg_rec['registration_date']}."))
            else:
                checks.append(_check("gstin_status", "GST registration is active", "restricted",
                                     f"The GST registry shows this GSTIN as {st.upper()}.",
                                     fix="Sell only products that don't need a GSTIN; offer an upgrade when GST is restored.",
                                     owner=f"Your GST registration shows as {st.lower()} in government records. You can still go live today with products that don't need GST; we'll add the rest when it's active again."))
        elif not any(c["id"] == "gstin_checksum" and c["status"] == "review" for c in checks):
            checks.append(_check("gstin_status", "GSTIN found in registry", "review", "Valid format but not found in the GST registry.",
                                 fix="Back-office review.", owner="We couldn't find this GSTIN in government records. Please check the number."))
    elif not gst:
        checks.append(_check("gst_present", "GST certificate provided", "action", "No GST certificate uploaded.",
                             fix="Upload the GST certificate or type the GSTIN.", owner="Please add your GST certificate, or type your GSTIN and we'll fetch it."))

    if reg_rec and gst and gst.get("readable"):
        f = gst["fields"]
        s_legal = similar(f.get("legal_name"), reg_rec["legal_name"])
        s_trade = similar(f.get("trade_name"), reg_rec["trade_name"])
        if s_legal >= 0.92 and s_trade >= 0.92:
            checks.append(_check("gst_name_match", "Names on certificate match the registry", "pass", f"Legal and trade name match ({reg_rec['legal_name']})."))
        else:
            which = "legal name" if s_legal < 0.92 else "trade name"
            got = f.get("legal_name") if s_legal < 0.92 else f.get("trade_name")
            want = reg_rec["legal_name"] if s_legal < 0.92 else reg_rec["trade_name"]
            checks.append(_check("gst_name_match", "Names on certificate match the registry", "review",
                                 f"Certificate {which} '{got}' differs from the registry '{want}'.",
                                 fix="Back-office review: possible edited certificate or outdated copy.",
                                 owner="The name on your GST certificate is different from government records. If you changed your business name, upload the amended certificate."))
        if similar(f.get("address"), reg_rec["principal_place_of_business"]) >= 0.9:
            checks.append(_check("gst_address_match", "Address on certificate matches the registry", "pass", "Principal place of business matches."))
        else:
            checks.append(_check("gst_address_match", "Address on certificate matches the registry", "review",
                                 f"Certificate address '{f.get('address')}' differs from registry.", fix="Back-office review."))

    # 3. Udyam: certificate number, or registry-first fallback
    trade = (reg_rec or {}).get("trade_name") or (gst or {}).get("fields", {}).get("trade_name") or context.get("business_name")
    city = (reg_rec or {}).get("address", {}).get("city") if reg_rec else None
    if ud and ud.get("readable"):
        num = ud["fields"].get("udyam_number", "")
        if not num:
            found = registry.find_udyam(trade, city) if trade else None
            if found:
                fetched.append({"type": "udyam_certificate", "source": "Udyam registry", "number": found["udyam_number"]})
                checks.append(_check("udyam_number", "Udyam number present", "pass",
                                     f"Number is blank on the certificate; found {found['udyam_number']} in the Udyam registry by name.",
                                     owner="Your Udyam certificate had no number on it, so we looked it up in the Udyam registry for you."))
            else:
                checks.append(_check("udyam_number", "Udyam number present", "action",
                                     "The registration number is blank on the Udyam certificate and no registry record matches.",
                                     fix="Ask for the full certificate (Udyam is optional for connectivity; needed for MSME pricing).",
                                     owner="The Udyam number is missing on your certificate. Please upload the full certificate, or skip: Udyam is optional for your plan."))
        else:
            uv = registry.lookup_udyam(num)
            if not uv["format"]["valid"]:
                checks.append(_check("udyam_number", "Udyam number valid", "action", uv["format"]["problems"][0], fix="Re-upload the certificate."))
            elif not uv["found"]:
                checks.append(_check("udyam_number", "Udyam number in registry", "review", f"{num} not found in the Udyam registry.", fix="Back-office review."))
            else:
                rec = uv["record"]
                ok_name = similar(rec["enterprise_name"], trade) >= 0.9 if trade else True
                ok_state = (not reg_rec) or key(rec["state"]) == key(reg_rec["state"])
                if ok_name and ok_state:
                    checks.append(_check("udyam_number", "Udyam matches the business", "pass", f"{num}: {rec['enterprise_name']}, {rec['enterprise_type']} enterprise, {rec['city']}."))
                else:
                    checks.append(_check("udyam_number", "Udyam matches the business", "review",
                                         f"Udyam {num} is registered to {rec['enterprise_name']} ({rec['state']}), not this business.", fix="Back-office review."))
    else:
        num = context.get("udyam")
        found = registry.lookup_udyam(num)["record"] if num else (registry.find_udyam(trade, city) if trade else None)
        if found:
            fetched.append({"type": "udyam_certificate", "source": "Udyam registry", "number": found["udyam_number"]})
            checks.append(_check("udyam_number", "Udyam certificate", "pass",
                                 f"Not uploaded; fetched {found['udyam_number']} ({found['enterprise_name']}) from the Udyam registry instead.",
                                 owner="No need to upload your Udyam certificate: we fetched it from the Udyam registry."))
        else:
            checks.append(_check("udyam_number", "Udyam certificate", "info", "No Udyam certificate and no registry record. Udyam is optional for connectivity.",
                                 owner="No Udyam registration found. That's fine for your plan; registering is free at udyamregistration.gov.in."))

    # 4. Address proof
    if bill and bill.get("readable"):
        f = bill["fields"]
        try:
            bd = dt.date.fromisoformat(f.get("bill_date", ""))
            age = (TODAY - bd).days
        except ValueError:
            bd, age = None, None
        if age is None:
            checks.append(_check("bill_date", "Address proof is recent", "action", "Could not read the bill date.", fix="Re-upload."))
        elif age < 0:
            checks.append(_check("bill_date", "Address proof is recent", "review", f"Bill date {bd} is in the future.", fix="Back-office review."))
        elif age > ADDRESS_PROOF_MAX_AGE_DAYS:
            checks.append(_check("bill_date", "Address proof is recent", "action",
                                 f"Bill dated {bd} is {age} days old (limit {ADDRESS_PROOF_MAX_AGE_DAYS}).",
                                 fix="Ask for a bill from the last 90 days.",
                                 owner=f"Your electricity bill is from {bd:%d %b %Y}, more than 3 months old. Please upload a bill from after {(TODAY - dt.timedelta(days=ADDRESS_PROOF_MAX_AGE_DAYS)):%d %b %Y}."))
        else:
            checks.append(_check("bill_date", "Address proof is recent", "pass", f"Bill dated {bd} ({age} days old)."))
        ref_addr = (reg_rec or {}).get("principal_place_of_business") or (gst or {}).get("fields", {}).get("address")
        if ref_addr:
            s = similar(f.get("address"), ref_addr)
            checks.append(_check("bill_address", "Bill address matches GST address", "pass" if s >= 0.9 else "action",
                                 f"Supply address {'matches' if s >= 0.9 else 'does not match'} the GST principal place of business ({s:.0%}).",
                                 fix=None if s >= 0.9 else "Ask for a bill for the registered premises, or add the site as an additional place of business."))
        names = [n for n in [(reg_rec or {}).get("trade_name"), (reg_rec or {}).get("legal_name"), trade] if n]
        if names and max(similar(f.get("billed_to"), n) for n in names) < 0.9:
            checks.append(_check("bill_name", "Bill is in the business's name", "action", f"Billed to '{f.get('billed_to')}'.",
                                 fix="Ask for a rent agreement or NOC if the bill is in the landlord's name."))
    else:
        checks.append(_check("bill_present", "Address proof provided", "action", "No readable address proof.", fix="Upload a utility bill from the last 90 days."))

    # 5. Signatory: valid ID, right business, authority to sign (DoT: authorisation letter / board resolution)
    if sid and sid.get("readable"):
        f = sid["fields"]
        try:
            vt = dt.date.fromisoformat(f.get("valid_till", ""))
            checks.append(_check("id_valid", "Signatory ID is valid", "pass" if vt >= TODAY else "action",
                                 f"Valid till {vt}." if vt >= TODAY else f"ID expired on {vt}.", fix=None if vt >= TODAY else "Upload a current ID."))
        except ValueError:
            checks.append(_check("id_valid", "Signatory ID is valid", "action", "Could not read the validity date.", fix="Re-upload."))
        if trade and similar(f.get("for_business"), trade) < 0.9:
            checks.append(_check("id_business", "ID is for this business", "review", f"ID is for '{f.get('for_business')}'.", fix="Back-office review."))
        constitution = (reg_rec or {}).get("constitution") or (gst or {}).get("fields", {}).get("constitution", "")
        name = f.get("name", "")
        prop = (reg_rec or {}).get("proprietor") or registry.proprietor_of((gst or {}).get("fields", {}).get("legal_name", ""))
        if constitution == "Proprietorship":
            if prop and similar(name, prop) >= 0.9:
                checks.append(_check("signatory_authority", "Signatory can sign for the business", "pass", f"{name} is the proprietor."))
            else:
                checks.append(_check("signatory_authority", "Signatory can sign for the business", "action",
                                     f"{name} is not the proprietor ({prop}).", fix=f"Needs {AUTH_DOC[constitution]}.",
                                     owner=f"{name} isn't the proprietor on record. We'll send {prop} a WhatsApp link to e-sign an authorisation in 1 minute."))
        elif constitution in AUTHORISED_DESIGNATIONS:
            if key(f.get("designation")) in AUTHORISED_DESIGNATIONS[constitution]:
                checks.append(_check("signatory_authority", "Signatory can sign for the business", "pass", f"{name} is a {f.get('designation')} of the {constitution}."))
            else:
                checks.append(_check("signatory_authority", "Signatory can sign for the business", "action",
                                     f"For a {constitution} the signatory must be authorised by the firm; ID shows designation '{f.get('designation')}'.",
                                     fix=f"Needs {AUTH_DOC[constitution]} (telecom rules require it for business connections).",
                                     owner=f"For a {constitution.lower()}, telecom rules need {AUTH_DOC[constitution]}. We'll send a ready-made e-sign link to the right person on WhatsApp."))
        contact = context.get("contact_name")
        if contact and similar(contact, name) < 0.9:
            checks.append(_check("signatory_contact", "Signatory is the person who applied", "action",
                                 f"The application came from {contact}, but the signatory ID is for {name}.",
                                 fix="Confirm with an OTP to the registered mobile, or get the authorisation e-signed.",
                                 owner=f"This application was started by {contact}, but the ID is for {name}. We'll send {name} a one-tap confirmation on WhatsApp."))
    else:
        checks.append(_check("id_present", "Signatory ID provided", "action", "No readable signatory ID.", fix="Upload the signatory's ID, or use Aadhaar e-KYC."))

    # 6. Cross-document consistency of the business name
    names = {DOC_NAMES[t]: n for t, n in [("udyam_certificate", (ud or {}).get("fields", {}).get("enterprise_name")),
                                           ("address_proof", (bill or {}).get("fields", {}).get("billed_to")),
                                           ("signatory_id", (sid or {}).get("fields", {}).get("for_business"))] if n}
    if trade and names:
        off = {k: v for k, v in names.items() if similar(v, trade) < 0.9}
        checks.append(_check("cross_doc", "Same business on every document", "pass" if not off else "review",
                             "All documents name the same business." if not off else f"Different names: {off}.",
                             fix=None if not off else "Back-office review."))

    return _verdict(checks, readings, fetched, reg_rec)


def _verdict(checks, readings, fetched, reg_rec) -> dict:
    statuses = [c["status"] for c in checks]
    if "review" in statuses:
        verdict, headline = "REVIEW", "Sent to back-office review"
    elif "restricted" in statuses:
        verdict, headline = "RESTRICTED", "Approved for non-GST products only"
    elif any(s in ("action", "fail") for s in statuses):
        verdict, headline = "ACTION_NEEDED", "Owner can fix this in the app"
    else:
        verdict, headline = "APPROVED", "KYC approved"
    issues = [c for c in checks if c["status"] not in ("pass", "info")]
    return {
        "verdict": verdict, "headline": headline, "checks": checks, "issues": issues,
        "auto_fixed": [c for c in checks if c["status"] == "pass" and ("Straightened" in c["detail"] or "fetched" in c["detail"].lower() or "found" in c["detail"].lower() and "registry" in c["detail"])],
        "fetched_from_registry": fetched,
        "documents": {t: {"quality": r["quality"], "fields": r.get("fields", {}), "auto_fixes": r.get("auto_fixes", []),
                          "readable": r.get("readable", True)} for t, r in readings.items()},
        "business": {"gstin": reg_rec["gstin"], "legal_name": reg_rec["legal_name"], "trade_name": reg_rec["trade_name"],
                     "constitution": reg_rec["constitution"], "status": reg_rec["status"]} if reg_rec else None,
    }
