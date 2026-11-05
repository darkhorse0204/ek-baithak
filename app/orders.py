"""Orders and the tracker. The tracker pushes every status change to the owner (WhatsApp in
production) so they never need to call. Instant products go live in the same sitting; physical
installs are scheduled from each product's typical install time."""
from __future__ import annotations

import json
import random
import time
import uuid

from .config import RUNTIME_DIR
from .i18n import t

ORDERS: dict[str, dict] = {}
FILE = RUNTIME_DIR / "orders.json"
if FILE.exists():
    try:
        ORDERS.update(json.loads(FILE.read_text(encoding="utf-8")))
    except Exception:
        pass

# Products that can be switched on remotely the same day (eSIM, cloud services):
# everything the catalogue says installs within a day.
from .data import catalogue as _cat

INSTANT = set(_cat()[_cat().typical_install_days <= 1].product_id)
PARTNERS = {
    "Delhi": "Sharma Digital Point", "Mumbai": "Konkan Telecom Services", "Bengaluru": "Namma Net Solutions", "Pune": "Sahyadri Connect",
    "Chennai": "Marina Telelinks", "Hyderabad": "Charminar Comms", "Kolkata": "Howrah Net Care", "Ahmedabad": "Sabarmati Telecom",
    "Jaipur": "Pink City Connect", "Lucknow": "Awadh Telecom", "Nagpur": "Orange City Net", "Kochi": "Malabar Connect",
}


def _save():
    FILE.write_text(json.dumps(ORDERS, default=str), encoding="utf-8")


def _milestones(lines: list[dict]) -> list[dict]:
    instant = [l for l in lines if l["product_id"] in INSTANT]
    physical = [l for l in lines if l["product_id"] not in INSTANT]
    ms = [
        {"key": "placed", "label": "Order placed, KYC verified", "day": 0, "who": "Accel"},
        {"key": "paid", "label": "First payment received (UPI)", "day": 0, "who": "You"},
    ]
    if instant:
        ms.append({"key": "instant_live", "label": "Live now: " + ", ".join(l["name"] for l in instant), "day": 0, "who": "Accel",
                   "products": [l["product_id"] for l in instant]})
    if any(l["product_id"] in ("P07", "P08") for l in lines):
        ms.append({"key": "sim_kyc", "label": "SIM users finish 1-minute self-KYC", "day": 0, "who": "Your staff"})
    if physical:
        ms.append({"key": "slot", "label": "Installation slot booked", "day": 1, "who": "You"})
        groups: dict[int, list[dict]] = {}
        for l in physical:
            groups.setdefault(int(l["install_days"]), []).append(l)
        for d in sorted(groups):
            ms.append({"key": f"install_{d}", "label": "Installed: " + ", ".join(l["name"] for l in groups[d]), "day": d, "who": "Partner",
                       "products": [l["product_id"] for l in groups[d]]})
    last = max([m["day"] for m in ms])
    ms.append({"key": "all_live", "label": "Everything live, one bill, one support number", "day": last, "who": "Accel"})
    ms.append({"key": "first_bill", "label": "First combined bill (preview sent 3 days before AutoPay)", "day": 30, "who": "Accel"})
    for m in ms:
        m["done"] = False
        m["done_at"] = None
    return ms


def create(session: dict, reco: dict, kyc: dict | None, consent_id: str | None) -> dict:
    oid = "ACB-" + uuid.uuid4().hex[:6].upper()
    p = session["profile"]
    lines = reco["lines"]
    if kyc and kyc.get("verdict") == "RESTRICTED":
        from .data import catalogue
        lines = [l for l in lines if catalogue().loc[l["product_id"]].requires_gstin != "Y"]
    o = {
        "id": oid, "session": session["id"], "lang": session["lang"], "created": time.time(), "day": 0,
        "business": p.get("business_name") or p.get("business_type"), "city": p.get("city"), "segment": p.get("segment"),
        "lines": lines, "monthly": sum(l["monthly"] for l in lines), "setup": sum(l["setup"] for l in lines),
        "contract_months": reco["contract_months"], "kyc_verdict": (kyc or {}).get("verdict"), "consent_id": consent_id,
        "partner": {"name": PARTNERS.get(p.get("city") or "", "Accel Partner Network"), "role": "Installation & local support",
                    "credited": True, "fee_inr": 1500},
        "milestones": _milestones(lines), "notifications": [], "status": "awaiting_signature",
        "esign": {"status": "pending", "signer": None}, "payment": {"status": "pending"},
        "sim_users": [{"line": i + 1, "status": "link_sent"} for l in lines if l["product_id"] in ("P07", "P08") for i in range(l["qty"])],
        "calls_to_support": 0,
    }
    ORDERS[oid] = o
    _notify(o, t("ui_track_title", o["lang"]) + f" {oid}: " + "Order received. We'll message you at every step, no need to call.")
    _save()
    return o


def _notify(o: dict, text: str, kind: str = "update") -> None:
    o["notifications"].append({"ts": time.time(), "day": o["day"], "channel": "WhatsApp", "text": text, "kind": kind})


def _complete(o: dict, key: str) -> None:
    for m in o["milestones"]:
        if m["key"] == key and not m["done"]:
            m["done"], m["done_at"] = True, o["day"]
            _notify(o, f"✅ {m['label']}")


def esign(oid: str, signer: str, method: str = "aadhaar_otp") -> dict:
    o = ORDERS[oid]
    o["esign"] = {"status": "signed", "signer": signer, "method": method, "ts": time.time(),
                  "document": "Customer Application Form + authorisation", "hash": uuid.uuid4().hex[:16]}
    o["status"] = "awaiting_payment"
    _notify(o, f"✍️ Signed by {signer} with Aadhaar e-Sign. Copy of your signed form is in 'My data'.")
    _save()
    return o


def pay(oid: str) -> dict:
    o = ORDERS[oid]
    amount = o["monthly"] + o["setup"]
    o["payment"] = {"status": "paid", "amount": amount, "method": "UPI (one-time)", "ref": "UPI" + str(random.randint(10**9, 10**10 - 1)),
                    "autopay": "Mandate from month 2, reminder 24h before every debit"}
    o["status"] = "in_progress"
    _complete(o, "placed")
    _complete(o, "paid")
    _complete(o, "instant_live")
    _save()
    return o


def book_slot(oid: str, slot: str) -> dict:
    o = ORDERS[oid]
    o["slot"] = slot
    _complete(o, "slot")
    _notify(o, f"📅 Engineer from {o['partner']['name']} booked for {slot}. You'll get their name and photo 1 hour before.")
    _save()
    return o


def advance(oid: str, days: int = 1) -> dict:
    """Demo clock: move the order forward and fire the updates the owner would receive."""
    o = ORDERS[oid]
    for _ in range(days):
        o["day"] += 1
        for m in o["milestones"]:
            if m["key"] == "sim_kyc" and not m["done"]:
                for u in o["sim_users"]:
                    u["status"] = "verified"
                _complete(o, "sim_kyc")
            if m["key"] == "slot" and not m["done"] and o["day"] >= 1:
                book_slot(oid, "tomorrow 10:00-12:00")
            if m["key"].startswith("install_") and not m["done"]:
                if o["day"] == m["day"] - 1:
                    _notify(o, f"🔧 Tomorrow: engineer visit for {m['label'].replace('Installed: ', '')}. Reply 1 to confirm or 2 to reschedule.")
                if o["day"] >= m["day"]:
                    _complete(o, m["key"])
        if all(m["done"] for m in o["milestones"] if m["key"] not in ("all_live", "first_bill")):
            if not next(m for m in o["milestones"] if m["key"] == "all_live")["done"]:
                _complete(o, "all_live")
                o["status"] = "live"
                _notify(o, "🎉 Everything is live. One bill, one support number: 121 or reply here on WhatsApp.")
        if o["day"] >= 30:
            _complete(o, "first_bill")
    _save()
    return o


def eta(o: dict) -> dict:
    pending = [m for m in o["milestones"] if not m["done"] and m["key"] != "first_bill"]
    nxt = pending[0] if pending else None
    return {"next": nxt, "days_left": max(0, (max(m["day"] for m in pending) - o["day"])) if pending else 0,
            "progress": round(sum(m["done"] for m in o["milestones"] if m["key"] != "first_bill") / max(1, len(o["milestones"]) - 1), 2)}
