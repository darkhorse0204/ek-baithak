"""KYC lab: run the full pipeline on the 12 specimen applicants (K01-K12)."""
from __future__ import annotations

from ..config import KYC_DIR
from ..data import leads
from . import verify

DOC_TYPES = ["gst_certificate", "udyam_certificate", "address_proof", "signatory_id"]


def applicant_ids() -> list[str]:
    return sorted({p.name[:3] for p in KYC_DIR.glob("K*_*.png")})


def applicant_docs(kid: str) -> list[dict]:
    out = []
    for t in DOC_TYPES:
        f = KYC_DIR / f"{kid}_{t}.png"
        if f.exists():
            out.append({"filename": f.name, "data": f.read_bytes()})
    return out


def crm_context(docs: list[dict]) -> dict:
    """Find the enquiry this applicant came from (who applied, which GSTIN they typed)."""
    bill = next((verify.read_document(d["data"], d["filename"]) for d in docs if "address_proof" in d["filename"]), None)
    if not bill or not bill.get("fields"):
        return {}
    name = bill["fields"].get("billed_to", "")
    addr = verify.key(bill["fields"].get("address", ""))
    L = leads()
    cand = L[L.business_name.map(verify.key) == verify.key(name)]
    cand = cand[cand.city.map(lambda c: verify.key(c) in addr)]
    if not len(cand):
        return {}
    r = cand.iloc[0]
    return {"lead_id": r.lead_id, "contact_name": r.contact_name, "contact_role": r.contact_role,
            "gstin": r.gstin if isinstance(r.gstin, str) else "", "udyam": r.udyam_number if isinstance(r.udyam_number, str) else "",
            "business_name": r.business_name}


def run(kid: str, use_ai: bool = True) -> dict:
    docs = applicant_docs(kid)
    ctx = crm_context(docs)
    res = verify.verify_applicant(docs, ctx, use_ai=use_ai)
    res["applicant"] = kid
    res["context"] = ctx
    res["files"] = [d["filename"] for d in docs]
    return res


# What a careful human reviewer should conclude (our own answer key, built by reading every document).
EXPECTED = {
    "K01": ("RESTRICTED", {"gstin_status"}), "K02": ("APPROVED", set()), "K03": ("APPROVED", set()),
    "K04": ("ACTION_NEEDED", {"quality_gst_certificate"}), "K05": ("ACTION_NEEDED", {"signatory_authority"}),
    "K06": ("REVIEW", {"gstin_checksum"}), "K07": ("REVIEW", {"gst_name_match"}), "K08": ("APPROVED", set()),
    "K09": ("APPROVED", set()), "K10": ("ACTION_NEEDED", {"signatory_contact"}), "K11": ("ACTION_NEEDED", {"bill_date"}),
    "K12": ("APPROVED", set()),
}
