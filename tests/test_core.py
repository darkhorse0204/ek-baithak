"""Fast offline tests for the rules that must never break. Run: python -m pytest -q"""
import os
import tempfile

os.environ.setdefault("EK_STATE_DIR", os.path.join(tempfile.gettempdir(), "ek_test_state"))

os.environ["OFFLINE_MODE"] = "1"

from app import gstin as G  # noqa: E402
from app import registry  # noqa: E402
from app.catalogue import Profile, check, unit_price, validate_bundle  # noqa: E402
from app.privacy import mask_text, record_consent  # noqa: E402
from app.recommender import audit_historical_bundles, recommend  # noqa: E402


def ids(reco):
    return {l["product_id"] for l in reco["lines"]}


def excluded(reco, pid):
    return next((e for e in reco["excluded"] if e["product_id"] == pid), None)


# ---- GSTIN ----
def test_checksum_valid_registry_numbers():
    assert G.checksum_ok("27PZSXS1936O1ZH")
    assert G.checksum_ok("37IHKXV5167L1ZS")


def test_checksum_catches_tampered_digit():
    assert not G.checksum_ok("08YKZXS8189L1ZO")  # K06: 5 changed to 8
    near = registry.near_gstins("08YKZXS8189L1Z0")
    assert near and near[0]["gstin"] == "08YKZXS5189L1ZO"
    assert [d["position"] for d in near[0]["diffs"]] == [8]


def test_ocr_normalisation_fixes_letter_digit_confusion():
    assert G.normalise_ocr("19E0GXH4115Y1ZL") == "19EOGXH4115Y1ZL"  # K02: O read as 0 inside the PAN


def test_masking():
    s = mask_text("GSTIN 27PZSXS1936O1ZH phone 9876543210 UDYAM-MH-00-6131836")
    assert "27PZSXS1936O1ZH" not in s and "9876543210" not in s and "6131836" not in s


# ---- eligibility ----
def test_tier_rule_blocks_1g_in_tier2():
    p = Profile(city="Kochi", tier=2, employees=12, sites=1, gstin="x", gstin_status="Active")
    assert any(f["rule"] == "city_tier" for f in check("P03", p, {"P03"}))


def test_gstin_rule_uses_status_not_presence():
    p = Profile(tier=1, employees=5, sites=1, gstin="37IHKXV5167L1ZS", gstin_status="Cancelled")
    assert any(f["rule"] == "gstin" for f in check("P15", p, {"P15"}))


def test_dependency_rule():
    p = Profile(tier=1, employees=3, sites=1)
    assert validate_bundle({"P04": 1, "P11": 1}, p)  # static IP needs wired fibre
    assert not validate_bundle({"P01": 1, "P11": 1}, p)


def test_recommendations_are_always_eligible():
    cases = [Profile(business_type=b, city=c, employees=e, sites=s, gstin="x" if g else "", gstin_status="Active" if g else "")
             for b, c, e, s, g in [("Kirana store", "Patna", 2, 1, False), ("Restaurant chain", "Mumbai", 60, 6, True),
                                   ("Textile unit", "Surat", 120, 1, True), ("CA firm", "Nagpur", 9, 1, False),
                                   ("Gym chain", "Delhi", 20, 2, True), ("Auto-parts unit", "Pune", 8, 1, True)]]
    for p in cases:
        r = recommend(p)
        items = {l["product_id"]: l["qty"] for l in r["lines"]}
        assert not validate_bundle(items, p), (p.business_type, validate_bundle(items, p))


def test_requested_product_is_explained_not_dropped():
    r = recommend(Profile(business_type="Boutique", city="Delhi", employees=4, sites=1, requested=["P05"]))
    e = excluded(r, "P05")
    assert e and "min_employees" in e["rules"] and "P05" not in ids(r)


def test_sdwan_needs_three_sites():
    r = recommend(Profile(business_type="Gym chain", city="Delhi", employees=20, sites=2, gstin="x", gstin_status="Active", requested=["P10"]))
    assert "P10" not in ids(r) and "min_sites" in excluded(r, "P10")["rules"]


def test_no_gst_gets_tip():
    r = recommend(Profile(business_type="Kirana store", city="Lucknow", employees=3, sites=1, needs=["whatsapp"], needs_confirmed=True))
    e = excluded(r, "P15")
    assert e and e["tip"]


def test_pricing_rule():
    assert unit_price("P01", 24) == 999 and unit_price("P01", 12) == 1099 and unit_price("P01", 6) == 1199


def test_budget_lean_plan():
    r = recommend(Profile(business_type="Pharmacy", city="Indore", employees=3, sites=1, budget=1500))
    assert r["budget_note"]["fits"] and r["budget_note"]["monthly"] <= 1500


def test_audit_finds_historical_violations():
    a = audit_historical_bundles()
    assert a["bundles_affected"] > 40 and {"city_tier", "gstin"} <= set(a["by_rule"])


# ---- privacy ----
def test_consent_requires_mandatory_purposes():
    assert not record_consent("t1", {"kyc": True}, "en")["ok"]
    assert record_consent("t2", {"kyc": True, "partner": True}, "en")["ok"]
