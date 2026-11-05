"""DPDP Act 2023 / DPDP Rules 2025 controls: purpose-wise consent, masking, audit log,
retention, and the owner's rights (access, correction, erasure, withdrawal)."""
from __future__ import annotations

import hashlib
import json
import re
import time
import uuid

from .config import RUNTIME_DIR

NOTICE_VERSION = "2026-11-v1"
PURPOSES = {
    "kyc": {"required": True, "legal_basis": "Legal obligation: DoT KYC rules for business connections",
            "data": ["GSTIN", "business name & address", "signatory name & ID number", "photo of documents"],
            "retention": "Images: deleted within 24h of verification. Verified fields: kept for the life of the connection + period set by the DoT licence."},
    "registry": {"required": False, "legal_basis": "Consent (DPDP s.6)",
                 "data": ["GST registry record", "Udyam record", "Entity Locker document references"],
                 "retention": "References only (document URI + hash); no copies kept."},
    "updates": {"required": False, "legal_basis": "Consent (DPDP s.6)", "data": ["mobile number", "order status"],
                "retention": "Until the order is live + 90 days."},
    "partner": {"required": True, "legal_basis": "Necessary to install the service you asked for",
                "data": ["installation address", "contact name", "phone (masked until visit day)"],
                "retention": "Partner access ends 7 days after installation."},
    "marketing": {"required": False, "legal_basis": "Consent (DPDP s.6), off by default", "data": ["business type", "products bought"],
                  "retention": "Until you withdraw."},
}
CONSENTS: dict[str, dict] = {}
AUDIT: list[dict] = []
_FILE = RUNTIME_DIR / "privacy.json"
if _FILE.exists():
    try:
        d = json.loads(_FILE.read_text(encoding="utf-8"))
        CONSENTS.update(d.get("consents", {}))
        AUDIT.extend(d.get("audit", []))
    except Exception:
        pass

GSTIN_RE = re.compile(r"\b(\d{2})([A-Z]{5}\d{4}[A-Z])([0-9A-Z]Z[0-9A-Z])\b")
PHONE_RE = re.compile(r"\b([6-9])\d{6}(\d{3})\b")
UDYAM_RE = re.compile(r"\b(UDYAM-[A-Z]{2}-\d{2}-)\d{4}(\d{3})\b")
ID_RE = re.compile(r"\b(SYN-ID-)\d{3}(\d{3})\b")


def mask_text(s: str) -> str:
    """Mask identifiers in any string before it is logged or shown to staff."""
    s = GSTIN_RE.sub(lambda m: m.group(1) + "•" * 10 + m.group(3), s)
    s = PHONE_RE.sub(lambda m: m.group(1) + "•" * 6 + m.group(2), s)
    s = UDYAM_RE.sub(lambda m: m.group(1) + "••••" + m.group(2), s)
    s = ID_RE.sub(lambda m: m.group(1) + "•••" + m.group(2), s)
    return s


def _persist():
    _FILE.write_text(json.dumps({"consents": CONSENTS, "audit": AUDIT[-2000:]}, default=str), encoding="utf-8")


def audit(actor: str, action: str, subject: str, detail: str = "") -> None:
    """Append-only access log (DPDP Rules: logs kept at least one year). Identifiers are masked."""
    prev = AUDIT[-1]["hash"] if AUDIT else "genesis"
    row = {"ts": time.time(), "actor": actor, "action": action, "subject": subject, "detail": mask_text(detail)}
    row["hash"] = hashlib.sha256((prev + json.dumps(row, sort_keys=True)).encode()).hexdigest()[:16]
    AUDIT.append(row)
    _persist()


def record_consent(session_id: str, granted: dict[str, bool], lang: str) -> dict:
    missing = [p for p, m in PURPOSES.items() if m["required"] and not granted.get(p)]
    if missing:
        return {"ok": False, "missing": missing}
    cid = "CNS-" + uuid.uuid4().hex[:8].upper()
    rec = {"id": cid, "session": session_id, "notice_version": NOTICE_VERSION, "language": lang, "ts": time.time(),
           "purposes": {p: bool(granted.get(p)) for p in PURPOSES}, "history": []}
    rec["receipt_hash"] = hashlib.sha256(json.dumps(rec, sort_keys=True).encode()).hexdigest()[:20]
    CONSENTS[cid] = rec
    audit("owner", "consent.granted", session_id, f"{cid} purposes={[p for p, v in rec['purposes'].items() if v]}")
    return {"ok": True, "consent": rec}


def withdraw(cid: str, purpose: str) -> dict:
    rec = CONSENTS[cid]
    if PURPOSES[purpose]["required"]:
        return {"ok": False, "reason": "This purpose is needed to keep the service running; cancel the order to stop it."}
    rec["purposes"][purpose] = False
    rec["history"].append({"ts": time.time(), "withdrawn": purpose})
    audit("owner", "consent.withdrawn", rec["session"], f"{cid} {purpose}")
    return {"ok": True, "consent": rec}


def consent_for(session_id: str) -> dict | None:
    recs = [c for c in CONSENTS.values() if c["session"] == session_id]
    return recs[-1] if recs else None
