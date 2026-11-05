"""Turn OCR lines into labelled fields for the four document types."""
from __future__ import annotations

import re

from .. import gstin as G


def key(s: str | None) -> str:
    """Comparison key: lowercase letters and digits only (OCR often drops spaces)."""
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


DOC_LABELS = {
    "gst_certificate": {
        "gstin": "gstin", "legalname": "legal_name", "tradename": "trade_name", "constitution": "constitution",
        "addressofprincipal": "address", "placeofbusiness": "address_cont", "dateofliability": "date_of_liability",
        "typeofregistration": "registration_type",
    },
    "udyam_certificate": {
        "udyamregnumber": "udyam_number", "enterprisename": "enterprise_name", "majoractivity": "major_activity",
        "city": "city", "state": "state", "dateofregistration": "date_of_registration",
    },
    "address_proof": {
        "consumerno": "consumer_no", "billedto": "billed_to", "supplyaddress": "address", "billdate": "bill_date",
        "unitsconsumed": "units", "amountdueinr": "amount_due",
    },
    "signatory_id": {
        "name": "name", "designation": "designation", "forbusiness": "for_business", "idno": "id_no", "validtill": "valid_till",
    },
}


def classify(lines: list[dict]) -> str:
    head = " ".join(l["text"] for l in sorted(lines, key=lambda l: l["y"])[:4]).lower().replace(" ", "")
    if "gstregistration" in head:
        return "gst_certificate"
    if "udyam" in head:
        return "udyam_certificate"
    if "electricity" in head or "bill" in head or "addressproof" in head:
        return "address_proof"
    if "signatory" in head or "identity" in head:
        return "signatory_id"
    return "unknown"


def _join(parts: list[str]) -> str:
    """Re-join a value that wrapped onto the next line. Wraps happen mid-word, so a lowercase
    or digit-after-digit continuation joins without a space."""
    out = ""
    for p in parts:
        p = p.strip()
        if not out:
            out = p
        elif p[:1].islower() or (out[-1:].isdigit() and p[:1].isdigit()):
            out += p
        else:
            out += " " + p
    return re.sub(r"\s+", " ", out)


def _rows(lines: list[dict], labels: dict[str, str]) -> dict[str, str]:
    label_lines = []
    for l in lines:
        k = key(l["text"])
        if k in labels:
            label_lines.append((labels[k], l))
    fields: dict[str, list[str]] = {}
    used = set()
    for name, lab in label_lines:
        vals = [v for i, v in enumerate(lines) if i not in used and v is not lab and v["x"] > lab["x2"] + 40
                and abs(v["y"] - lab["y"]) <= 24 and key(v["text"]) not in labels]
        for v in vals:
            used.add(lines.index(v))
        fields[name] = [v["text"] for v in sorted(vals, key=lambda v: v["x"])]
    # Bill address wraps onto an unlabelled row just below "Supply address".
    if "address" in fields and "address_cont" not in labels.values():
        lab = next(l for n, l in label_lines if n == "address")
        below = [v for i, v in enumerate(lines) if i not in used and v["x"] > lab["x2"] + 40 and 30 < v["y"] - lab["y"] <= 85
                 and key(v["text"]) not in labels]
        fields["address"] += [v["text"] for v in below]
    out = {k: _join(v) for k, v in fields.items()}
    if "address_cont" in out:
        out["address"] = _join([out.get("address", ""), out.pop("address_cont")])
    return out


def _id_card(lines: list[dict]) -> dict[str, str]:
    labels = DOC_LABELS["signatory_id"]
    ordered = sorted(lines, key=lambda l: l["y"])
    out = {}
    for i, l in enumerate(ordered):
        k = key(l["text"])
        if k in labels and i + 1 < len(ordered):
            nxt = ordered[i + 1]
            if key(nxt["text"]) not in labels and abs(nxt["x"] - l["x"]) < 60:
                out[labels[k]] = nxt["text"].strip()
    return out


def extract(lines: list[dict]) -> dict:
    doc_type = classify(lines)
    if doc_type == "unknown":
        return {"doc_type": doc_type, "fields": {}}
    fields = _id_card(lines) if doc_type == "signatory_id" else _rows(lines, DOC_LABELS[doc_type])
    if doc_type == "gst_certificate" and fields.get("gstin"):
        fields["gstin_raw"] = fields["gstin"]
        fields["gstin"] = G.normalise_ocr(fields["gstin"])
    if doc_type == "udyam_certificate" and fields.get("udyam_number"):
        fields["udyam_number"] = re.sub(r"\s+", "", fields["udyam_number"]).upper().replace("UDYAM", "UDYAM")
    for d in ("date_of_liability", "date_of_registration", "bill_date", "valid_till"):
        if fields.get(d):
            m = re.search(r"(\d{4})\s*-\s*(\d{2})\s*-\s*(\d{2})", fields[d])
            fields[d] = f"{m.group(1)}-{m.group(2)}-{m.group(3)}" if m else fields[d]
    return {"doc_type": doc_type, "fields": fields}
