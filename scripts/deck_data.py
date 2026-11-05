"""Compute every number used in the deck from the data + engines -> deck/data.json"""
import json, os, sys, tempfile
os.environ.setdefault("EK_STATE_DIR", os.path.join(tempfile.gettempdir(), "ek_test_state"))
os.environ["OFFLINE_MODE"] = "1"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app import analytics as A
from app.catalogue import Profile
from app.recommender import recommend, audit_historical_bundles
from app.kyc import lab

L = A.frame(); act = L[L.activated == 1]; f = A.funnel()
groups = {"Quote slow or confusing": ["Quote too complex to understand", "Quote took too long to arrive"],
          "Paperwork & documents": ["Found paperwork too long", "Missing GST or Udyam document", "Document details did not match", "Authorised signatory not available"],
          "No time for a visit": ["Owner had no time for a visit", "Visit not scheduled by sales"],
          "Install, feasibility, payment": ["Installation delayed beyond 21 days", "Site not feasible for fibre", "First payment failed"]}
dr = L[L.outcome == "Dropped"].drop_reason.value_counts()
drop_groups = {g: int(sum(dr.get(r, 0) for r in rs)) for g, rs in groups.items()}

def bundle(name, prof, term=12):
    r = recommend(prof, term=term)
    return {"name": name, "monthly": r["monthly"], "setup": r["setup"], "contract": r["contract_months"],
            "lines": [f"{l['name']}{' ×' + str(l['qty']) if l['qty'] > 1 else ''}" for l in r["lines"]],
            "addons": [l["name"] for l in r["optional"]]}
G = dict(gstin="x", gstin_status="Active")
bundles = {
 "micro": bundle("Dukaan Starter", Profile(business_type="Kirana store", city="Pune", employees=3, sites=1, needs=["upi_pos", "mobile"], needs_confirmed=True)),
 "micro_plus": bundle("Dukaan Plus", Profile(business_type="Kirana store", city="Pune", employees=3, sites=1, needs=["upi_pos", "mobile", "billing", "cctv", "whatsapp"], needs_confirmed=True, **G)),
 "prof": bundle("Clinic & Office Pro", Profile(business_type="Dental clinic", city="Pune", employees=9, sites=1, needs=["email", "sms", "backup", "security", "mobile", "guest_wifi"], needs_confirmed=True, **G)),
 "multi": bundle("Multi-site One", Profile(business_type="Restaurant chain", city="Mumbai", employees=50, sites=5, needs=["billing", "cctv", "failover", "central_mgmt", "mobile", "guest_wifi"], needs_confirmed=True, **G), term=24),
 "mfg": bundle("Factory Connect", Profile(business_type="Auto-parts unit", city="Pune", employees=60, sites=1, needs=["dedicated_line", "iot_machines", "security", "email", "cctv", "mobile"], needs_confirmed=True, counts={"machines": 10}, **G), term=24),
}
s = A.simulate(); sc = A.simulate({k: v * 0.5 for k, v in A.DEFAULT_LEVERS.items()})
med = float(act.monthly_bundle_value_inr.median())
labr = [lab.run(k, use_ai=False) for k in lab.applicant_ids()]
out = {
 "funnel": [x["count"] for x in f["stages"]], "pct_prev": [x["pct_prev"] for x in f["stages"]],
 "days": f["avg_days_to_activate"], "calls": f["avg_follow_up_calls"], "cac": f["cac_per_activation"], "churn": f["churn_6m"],
 "gst": f["gstin_activation"], "calls_vs_churn": f["calls_vs_churn"], "by_segment": f["by_segment"], "by_source": f["by_source"],
 "drop_groups": drop_groups, "friction_total": sum(drop_groups.values()), "dropped_total": int((L.outcome == "Dropped").sum()),
 "audit": {k: v for k, v in audit_historical_bundles().items() if k != "violations"},
 "bundles": bundles, "median_mrr": med, "mean_mrr": float(act.monthly_bundle_value_inr.mean()),
 "sim": {"base": s["projected"], "cons": sc["projected"], "today": s["baseline"], "cac_base": s["cac"]["projected"], "cac_cons": sc["cac"]["projected"],
         "act_base": s["activation_rate"]["projected"], "act_cons": sc["activation_rate"]["projected"]},
 "arr_extra_base_cr": round((s["projected"][-1] - 368) * med * 12 * 0.85 / 1e7, 1),
 "arr_extra_cons_cr": round((sc["projected"][-1] - 368) * med * 12 * 0.85 / 1e7, 1),
 "model": {"auc": A.model()["auc"], "top20": A.model()["top20_capture"]},
 "rescue": {k: v for k, v in A.rescue_queue(1).items() if k != "rows"},
 "kyc": [{"id": r["applicant"], "verdict": r["verdict"], "business": (r.get("business") or {}).get("trade_name") or r["context"].get("business_name"),
          "issues": [c["detail"] for c in r["issues"]], "auto": [c["detail"] for c in r["checks"] if "Straightened" in c["detail"] or ("fetched" in c["detail"].lower())]} for r in labr],
}
os.makedirs("deck", exist_ok=True)
json.dump(out, open("deck/data.json", "w", encoding="utf-8"), indent=1, ensure_ascii=False, default=float)
print(json.dumps({k: out[k] for k in ["drop_groups", "friction_total", "dropped_total", "audit", "arr_extra_base_cr", "arr_extra_cons_cr", "sim"]}, indent=1, default=float))
for k, b in bundles.items(): print(k, b["name"], b["monthly"], b["setup"], b["contract"], b["lines"], "| addons", b["addons"])
