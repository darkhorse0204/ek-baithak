"""Mock government lookups backed by the provided CSVs.

In production these map to: GST public taxpayer search (or GSTN via the Account Aggregator
network, with consent), the Udyam verification API, and MeitY's Entity Locker for
consent-based document fetch. Same inputs and outputs, so swapping them is a config change.
"""
from __future__ import annotations

import difflib
import hashlib
import re

from . import gstin as G
from .data import CITY_TIER, business_type_segment, gstin_registry, leads, udyam_registry

ADDR_RE = re.compile(r"^(?P<street>.*),\s*(?P<city>[^,]+),\s*(?P<state>[^,]+?)\s*-\s*(?P<pin>\d{6})$")
PROP_RE = re.compile(r"^(?P<person>.+?)\s*\(Prop\.\s*(?P<trade>.+)\)$")


def parse_address(addr: str) -> dict:
    m = ADDR_RE.match((addr or "").strip())
    return m.groupdict() if m else {"street": addr, "city": "", "state": "", "pin": ""}


def proprietor_of(legal_name: str) -> str | None:
    m = PROP_RE.match(legal_name or "")
    return m.group("person").strip() if m else None


def lookup_gstin(gstin: str) -> dict:
    v = G.validate(gstin)
    out = {"query": v["gstin"], "format": v}
    reg = gstin_registry()
    if v["gstin"] in reg.index:
        r = reg.loc[v["gstin"]].to_dict()
        r["address"] = parse_address(r["principal_place_of_business"])
        r["proprietor"] = proprietor_of(r["legal_name"])
        out.update(found=True, record=r)
    else:
        out.update(found=False, record=None, near_matches=near_gstins(v["gstin"]))
    return out


def near_gstins(gstin: str, max_diff: int = 2) -> list[dict]:
    """Registry entries that differ by 1-2 characters: a typo, an OCR slip, or an edited number."""
    g = (gstin or "").upper()
    if len(g) != 15:
        # Lengths differ (OCR dropped a character): fall back to fuzzy ratio.
        cands = difflib.get_close_matches(g, gstin_registry().index.tolist(), n=3, cutoff=0.85)
        return [{"gstin": c, "diff_positions": [], "legal_name": gstin_registry().loc[c].legal_name} for c in cands]
    out = []
    same_state = gstin_registry()[gstin_registry().gstin.str[:2] == g[:2]]
    for cand in same_state.gstin:
        diffs = [i for i, (a, b) in enumerate(zip(g, cand)) if a != b and {a, b} not in ({"0", "O"}, {"1", "I"})]
        if 0 < len(diffs) <= max_diff:
            out.append({"gstin": cand, "diff_positions": diffs, "legal_name": same_state.loc[cand].legal_name,
                        "status": same_state.loc[cand].status,
                        "diffs": [{"position": i + 1, "document": g[i], "registry": cand[i]} for i in diffs]})
    return out


def search_gstin_by_name(name: str, state: str | None = None, limit: int = 5) -> list[dict]:
    reg = gstin_registry()
    pool = reg if not state else reg[reg.state.str.lower() == state.lower()]
    names = (pool.trade_name + " | " + pool.legal_name).tolist()
    hits = difflib.get_close_matches(name, pool.trade_name.tolist() + pool.legal_name.tolist(), n=limit * 2, cutoff=0.6)
    out, seen = [], set()
    for h in hits:
        for g in pool[(pool.trade_name == h) | (pool.legal_name == h)].gstin:
            if g not in seen:
                seen.add(g)
                r = pool.loc[g]
                out.append({"gstin": g, "legal_name": r.legal_name, "trade_name": r.trade_name, "state": r.state, "status": r.status})
    del names
    return out[:limit]


def lookup_udyam(number: str) -> dict:
    v = G.validate_udyam(number)
    reg = udyam_registry()
    if v["udyam"] in reg.index:
        return {"query": v["udyam"], "format": v, "found": True, "record": reg.loc[v["udyam"]].to_dict()}
    return {"query": v["udyam"], "format": v, "found": False, "record": None}


def find_udyam(enterprise_name: str, city: str | None = None) -> dict | None:
    reg = udyam_registry()
    m = reg[reg.enterprise_name.str.lower() == (enterprise_name or "").strip().lower()]
    if city:
        m = m[m.city.str.lower() == city.lower()]
        return m.iloc[0].to_dict() if len(m) else None
    return m.iloc[0].to_dict() if len(m) == 1 else None


def crm_lead(gstin: str) -> dict | None:
    """Existing enquiry in the CRM for this GSTIN (lets us pre-fill size and needs)."""
    m = leads()[leads().gstin == gstin]
    return m.sort_values("created_date").iloc[-1].to_dict() if len(m) else None


def prefill(gstin: str) -> dict:
    """Everything we can learn from a GSTIN before asking the owner anything."""
    g = lookup_gstin(gstin)
    if not g["found"]:
        return {"ok": False, "gstin": g}
    r = g["record"]
    city = r["address"]["city"]
    ud = find_udyam(r["trade_name"], city)
    btype = ud["nic_description"] if ud else ""
    seg_name = business_type_segment().get(btype, "")
    lead = crm_lead(r["gstin"])
    known = {
        "business_name": r["trade_name"], "legal_name": r["legal_name"], "constitution": r["constitution"],
        "city": city, "state": r["state"], "pincode": r["address"]["pin"], "tier": CITY_TIER.get(city),
        "gstin": r["gstin"], "gstin_status": r["status"], "registered_since": r["registration_date"],
        "proprietor": r["proprietor"], "udyam": ud["udyam_number"] if ud else "",
        "enterprise_size": ud["enterprise_type"] if ud else "", "business_type": btype, "segment_name": seg_name,
    }
    if lead:
        known.update(employees=int(lead["employee_count"]), sites=int(lead["num_sites"]),
                     current_internet=lead.get("current_internet") if isinstance(lead.get("current_internet"), str) else "",
                     current_spend=int(lead["monthly_telecom_spend_inr"]), crm_lead_id=lead["lead_id"],
                     contact_name=lead["contact_name"], contact_role=lead["contact_role"],
                     preferred_language=lead["preferred_language"])
    return {"ok": True, "known": known, "gstin": g, "udyam_record": ud}


def entity_locker_fetch(gstin: str) -> dict:
    """Mock of a consent-based pull from Entity Locker / DigiLocker: verified copies, no upload.
    We keep a reference (URI + hash), not a copy of the document."""
    g = lookup_gstin(gstin)
    if not g["found"]:
        return {"ok": False, "reason": "No entity found for this GSTIN in Entity Locker"}
    r = g["record"]
    docs = [{"type": "gst_certificate", "issuer": "GSTN", "uri": f"in.gov.gst-REGCT-{r['gstin']}",
             "fields": {"gstin": r["gstin"], "legal_name": r["legal_name"], "trade_name": r["trade_name"],
                        "constitution": r["constitution"], "address": r["principal_place_of_business"], "status": r["status"]}}]
    ud = find_udyam(r["trade_name"], r["address"]["city"])
    if ud:
        docs.append({"type": "udyam_certificate", "issuer": "Ministry of MSME", "uri": f"in.gov.msme-UDYAM-{ud['udyam_number']}",
                     "fields": {"udyam_number": ud["udyam_number"], "enterprise_name": ud["enterprise_name"],
                                "city": ud["city"], "state": ud["state"], "enterprise_type": ud["enterprise_type"]}})
    for d in docs:
        d["sha256"] = hashlib.sha256(repr(sorted(d["fields"].items())).encode()).hexdigest()[:16]
    return {"ok": True, "docs": docs, "note": "Fetched as issuer-verified digital documents. Stored as references, not copies."}


def fibre_feasible(pincode: str, tier: int | None) -> dict:
    """Mock serviceability check. Deterministic per pincode so demos repeat."""
    if not pincode:
        return {"feasible": True, "checked": False}
    h = int(hashlib.md5(pincode.encode()).hexdigest(), 16)
    miss_rate = 9 if tier == 2 else 14  # roughly 11% / 7% of pincodes without fibre
    feasible = h % miss_rate != 0
    return {"feasible": feasible, "checked": True, "airfiber": True,
            "eta_days": 5 if feasible else 2, "note": None if feasible else "Fibre not yet at this pincode. 5G AirFiber can be live in 2 days."}
