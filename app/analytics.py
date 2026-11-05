"""Back-office analytics on last quarter's leads: funnel, lead scoring, rescue queue, simulator."""
from __future__ import annotations

from functools import lru_cache

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import StratifiedKFold, cross_val_predict
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from .data import gstin_registry, leads

STAGES = ["Lead", "Contacted", "Needs assessed", "Quote accepted", "KYC complete", "Activated"]
SEG_SHORT = {"Micro retail & services": "Micro retail", "Professional offices": "Professional",
             "Small multi-site businesses": "Multi-site", "Small manufacturers": "Manufacturers"}

# Each drop reason -> what our journey does about it, who acts, and a conservative recovery rate.
RESCUE = {
    "Quote too complex to understand": ("Send a one-tap WhatsApp quote with plain-language lines and a ₹/day price", "digital", 0.4),
    "Quote took too long to arrive": ("Instant quote from the advisor: no waiting", "digital", 0.4),
    "Found paperwork too long": ("Smart KYC link: GSTIN + Entity Locker fetch, 2 uploads at most", "digital", 0.45),
    "Missing GST or Udyam document": ("Fetch GST/Udyam from the registry; no upload needed", "digital", 0.45),
    "Document details did not match": ("Smart KYC shows exactly which field differs and how to fix it", "digital", 0.35),
    "Authorised signatory not available": ("Send the signatory a remote e-sign link on WhatsApp", "digital", 0.45),
    "Owner had no time for a visit": ("Self-serve advisor in their language: 7 minutes, no visit", "digital", 0.3),
    "Visit not scheduled by sales": ("Self-serve advisor link; partner joins only if asked", "digital", 0.3),
    "Price too high": ("Budget-fit bundle: 24-month price, fewer extras, setup spread over 6 months", "partner", 0.1),
    "Competitor offered cheaper plan": ("Show bundle value vs paying 4 vendors; partner match offer", "partner", 0.05),
    "Installation delayed beyond 21 days": ("Go live on 5G AirFiber in 2 days, move to fibre later", "digital", 0.35),
    "Site not feasible for fibre": ("5G AirFiber bridge: no fibre needed", "digital", 0.45),
    "First payment failed": ("One-time UPI pay link, AutoPay only from month 2", "digital", 0.45),
    "Customer cancelled before install": ("Partner call with live tracker; proactive install updates", "partner", 0.2),
    "Decided to wait": ("Nurture: reminder in 30 days with the saved quote", "digital", 0.1),
    "Only wanted a mobile plan": ("Sell the business postpaid line instantly in the app", "digital", 0.3),
    "Locked in with current provider": ("Remind 30 days before their contract ends", "digital", 0.0),
    "Unreachable after 3 attempts": ("WhatsApp-first reply within 5 minutes instead of calls", "digital", 0.1),
    "Not interested on first call": ("No action", "none", 0.0),
    "Wrong or invalid number": ("No action (validate numbers at capture)", "none", 0.0),
}
# Drops caused by friction in today's journey (slow/complex quote, paperwork, visits, install, payment).
FRICTION = {"Quote too complex to understand", "Quote took too long to arrive", "Found paperwork too long", "Missing GST or Udyam document",
            "Document details did not match", "Authorised signatory not available", "Owner had no time for a visit", "Visit not scheduled by sales",
            "Installation delayed beyond 21 days", "Site not feasible for fibre", "First payment failed"}
FEATURES_CAT = ["lead_source", "segment", "business_type", "city_tier", "preferred_language", "annual_turnover_band",
                "has_gstin", "has_udyam", "current_internet", "current_provider", "contact_role"]
FEATURES_NUM = ["log_employees", "num_sites", "log_spend", "n_interests"]


@lru_cache
def frame() -> pd.DataFrame:
    L = leads().copy()
    L["activated"] = (L.outcome == "Activated").astype(int)
    reg = gstin_registry()
    L["gst_status"] = L.gstin.map(lambda g: reg.loc[g].status if isinstance(g, str) and g in reg.index else "None")
    L["current_internet"] = L.current_internet.fillna("None")
    L["log_employees"] = np.log1p(L.employee_count)
    L["log_spend"] = np.log1p(L.monthly_telecom_spend_inr)
    L["n_interests"] = L.products_of_interest.fillna("").str.count(";") + L.products_of_interest.notna()
    L["city_tier"] = L.city_tier.astype(str)
    return L


def funnel() -> dict:
    L = frame()
    idx = {s: i for i, s in enumerate(STAGES)}
    reached = L.stage_reached.map(idx)
    counts = [int((reached >= i).sum()) for i in range(len(STAGES))]
    A = L[L.activated == 1]
    by_seg = []
    for seg, g in L.groupby("segment"):
        a = g[g.activated == 1]
        spend = g.acquisition_cost_inr.sum()
        by_seg.append({"segment": seg, "short": SEG_SHORT[seg], "leads": len(g), "activations": len(a),
                       "activation_rate": round(len(a) / len(g), 3), "churn_6m": round((a.churned_within_6_months == "Y").mean(), 3),
                       "median_mrr": float(a.monthly_bundle_value_inr.median()), "nps": round(a.nps_score.mean(), 1),
                       "cac_per_activation": round(spend / max(len(a), 1)),
                       "payback_months": round(spend / max(a.monthly_bundle_value_inr.sum(), 1), 1)})
    by_src = []
    for src, g in L.groupby("lead_source"):
        a = g[g.activated == 1]
        by_src.append({"source": src, "leads": len(g), "activations": len(a), "activation_rate": round(len(a) / len(g), 3),
                       "cac_per_activation": round(g.acquisition_cost_inr.sum() / max(len(a), 1)),
                       "churn_6m": round((a.churned_within_6_months == "Y").mean(), 3) if len(a) else None})
    drops = (L[L.outcome == "Dropped"].groupby(["stage_reached", "drop_reason"]).size().reset_index(name="n")
             .sort_values("n", ascending=False))
    drops["fix"] = drops.drop_reason.map(lambda r: RESCUE[r][0])
    drops["owner"] = drops.drop_reason.map(lambda r: RESCUE[r][1])
    calls = A.groupby("customer_follow_up_calls").agg(n=("lead_id", "size"), churn=("churned_within_6_months", lambda s: (s == "Y").mean()),
                                                      nps=("nps_score", "mean")).reset_index()
    return {
        "stages": [{"stage": s, "count": c, "pct_prev": None if i == 0 else round(c / counts[i - 1], 3)} for i, (s, c) in enumerate(zip(STAGES, counts))],
        "activation_rate": round(counts[-1] / counts[0], 3),
        "avg_days_to_activate": round(A.days_lead_to_activation.mean(), 1),
        "avg_follow_up_calls": round(A.customer_follow_up_calls.mean(), 1),
        "cac_per_activation": round(L.acquisition_cost_inr.sum() / counts[-1]),
        "churn_6m": round((A.churned_within_6_months == "Y").mean(), 3),
        "gstin_activation": {"with": round(L[L.has_gstin == "Y"].activated.mean(), 3), "without": round(L[L.has_gstin == "N"].activated.mean(), 3)},
        "by_segment": by_seg, "by_source": by_src,
        "drops": drops.to_dict("records"),
        "fixable_drops": int(drops[drops.drop_reason.isin(FRICTION)].n.sum()),
        "fixable_reasons": sorted(FRICTION),
        "calls_vs_churn": [{"calls": int(r.customer_follow_up_calls), "n": int(r.n), "churn": round(r.churn, 3), "nps": round(r.nps, 1)} for r in calls.itertuples()],
    }


@lru_cache
def model() -> dict:
    """Lead score: chance a lead activates, using only what we know when the lead arrives."""
    L = frame()
    X, y = L[FEATURES_CAT + FEATURES_NUM], L.activated
    pre = ColumnTransformer([("cat", OneHotEncoder(handle_unknown="ignore", min_frequency=10), FEATURES_CAT),
                             ("num", StandardScaler(), FEATURES_NUM)])
    pipe = Pipeline([("pre", pre), ("lr", LogisticRegression(C=0.5, max_iter=2000, class_weight="balanced"))])
    cv = StratifiedKFold(5, shuffle=True, random_state=7)
    oof = cross_val_predict(pipe, X, y, cv=cv, method="predict_proba")[:, 1]
    auc = roc_auc_score(y, oof)
    pipe.fit(X, y)
    # Lift: share of activations captured by calling the top 20% of leads.
    order = np.argsort(-oof)
    top = order[: len(order) // 5]
    lift = y.iloc[top].sum() / y.sum()
    names = pipe.named_steps["pre"].get_feature_names_out()
    coefs = pipe.named_steps["lr"].coef_[0]
    return {"pipe": pipe, "auc": round(float(auc), 3), "top20_capture": round(float(lift), 3),
            "oof": oof, "coef": dict(zip(names, coefs))}


def _reasons(row: pd.Series, k: int = 3) -> list[str]:
    m = model()
    pre = m["pipe"].named_steps["pre"]
    x = pre.transform(row[FEATURES_CAT + FEATURES_NUM].to_frame().T)
    x = x.toarray()[0] if hasattr(x, "toarray") else np.asarray(x)[0]
    contrib = x * np.array([m["coef"][n] for n in pre.get_feature_names_out()])
    names = pre.get_feature_names_out()
    order = np.argsort(-np.abs(contrib))[:k]
    out = []
    for i in order:
        out.append(("+ " if contrib[i] > 0 else "− ") + _friendly(names[i]))
    return out


def _friendly(feature: str) -> str:
    f = feature.replace("cat__", "").replace("num__", "")
    fixed = {"log_employees": "team size", "num_sites": "number of sites", "log_spend": "current telecom spend",
             "n_interests": "products asked about", "has_gstin_Y": "has GSTIN", "has_gstin_N": "no GSTIN",
             "has_udyam_Y": "Udyam registered", "has_udyam_N": "no Udyam"}
    if f in fixed:
        return fixed[f]
    for prefix, label in [("lead_source_", "came via "), ("business_type_", ""), ("segment_", ""), ("city_tier_", "tier-"),
                          ("preferred_language_", "speaks "), ("annual_turnover_band_", "turnover "), ("current_internet_", "today: "),
                          ("current_provider_", "provider: "), ("contact_role_", "contact is ")]:
        if f.startswith(prefix):
            v = f[len(prefix):].replace("infrequent_sklearn", "other")
            return label + v
    return f.replace("_", " ")


def scored_leads() -> pd.DataFrame:
    L = frame().copy()
    m = model()
    L["score"] = m["pipe"].predict_proba(L[FEATURES_CAT + FEATURES_NUM])[:, 1]
    seg_mrr = L[L.activated == 1].groupby("segment").monthly_bundle_value_inr.median()
    seg_churn = L[L.activated == 1].groupby("segment").churned_within_6_months.apply(lambda s: (s == "Y").mean())
    L["expected_mrr"] = L.segment.map(seg_mrr)
    L["priority_value"] = (L.score * L.expected_mrr * (1 - L.segment.map(seg_churn))).round()
    return L


def rescue_queue(limit: int = 200) -> dict:
    L = scored_leads()
    D = L[(L.outcome == "Dropped") & (L.drop_reason.map(lambda r: RESCUE.get(r, ("", "", 0))[2] > 0))].copy()
    D["action"] = D.drop_reason.map(lambda r: RESCUE[r][0])
    D["owner"] = D.drop_reason.map(lambda r: RESCUE[r][1])
    D["recovery_rate"] = D.drop_reason.map(lambda r: RESCUE[r][2])
    D.loc[D.drop_reason == "Only wanted a mobile plan", "expected_mrr"] = 1398  # two business postpaid lines
    D["rescue_value"] = (D.recovery_rate * D.expected_mrr).round()
    D = D.sort_values(["rescue_value", "score"], ascending=False)
    rows = []
    for _, r in D.head(limit).iterrows():
        rows.append({"lead_id": r.lead_id, "business": r.business_name, "type": r.business_type, "segment": SEG_SHORT[r.segment],
                     "city": r.city, "language": r.preferred_language, "source": r.lead_source, "stage": r.stage_reached,
                     "drop_reason": r.drop_reason, "action": r.action, "owner": r.owner, "score": round(float(r.score), 3),
                     "expected_mrr": int(r.expected_mrr), "rescue_value": int(r.rescue_value),
                     "contact": r.contact_name, "why": _reasons(r)})
    by_owner = D.groupby("owner").agg(leads=("lead_id", "size"), expected_recovered=("recovery_rate", "sum"),
                                      expected_mrr=("rescue_value", "sum")).round().reset_index().to_dict("records")
    return {"total": len(D), "rows": rows, "by_owner": by_owner,
            "expected_recovered": round(float(D.recovery_rate.sum())), "expected_mrr": int(D.rescue_value.sum())}


def open_leads(limit: int = 100) -> list[dict]:
    """Leads still worth calling, best first (stand-in for the live inbox)."""
    L = scored_leads()
    L = L.sort_values("priority_value", ascending=False).head(limit)
    return [{"lead_id": r.lead_id, "business": r.business_name, "segment": SEG_SHORT[r.segment], "city": r.city,
             "source": r.lead_source, "score": round(float(r.score), 3), "priority_value": int(r.priority_value),
             "why": _reasons(r)} for _, r in L.iterrows()]


DEFAULT_LEVERS = {k: v[2] for k, v in RESCUE.items()}


def simulate(levers: dict[str, float] | None = None, digital_share: float = 0.6) -> dict:
    """Re-run last quarter with the drop reasons we fix. Recovered leads still face every later stage."""
    L = frame()
    lv = {**DEFAULT_LEVERS, **(levers or {})}
    idx = {s: i for i, s in enumerate(STAGES)}
    reached = L.stage_reached.map(idx)
    base = [int((reached >= i).sum()) for i in range(len(STAGES))]
    dropped = L[L.outcome == "Dropped"]
    # Drops at each stage (dropped while sitting at stage i, i.e. failed to reach i+1)
    drops_at = {i: dropped[dropped.stage_reached == s] for i, s in enumerate(STAGES[:-1])}
    conv = []
    for i in range(len(STAGES) - 1):
        d = drops_at[i]
        recovered = sum(lv.get(r, 0) * n for r, n in d.drop_reason.value_counts().items())
        new_rate = (base[i + 1] + recovered) / base[i]
        conv.append(min(new_rate, 0.99))
    new = [base[0]]
    for c in conv:
        new.append(round(new[-1] * c))
    # Cost: digital journey cost per lead ~₹150 (cloud + messaging + KYC APIs); assisted leads keep today's cost.
    spend_base = float(L.acquisition_cost_inr.sum())
    spend_new = spend_base * (1 - digital_share) + base[0] * digital_share * 150 + (new[-1] * digital_share) * 1500  # ₹1,500 partner install fee
    days_base = float(L[L.activated == 1].days_lead_to_activation.mean())
    conservative = None
    if levers is None:
        conservative = simulate({k: v * 0.5 for k, v in DEFAULT_LEVERS.items()}, digital_share)["projected"]
    return {
        "levers": lv, "baseline": base, "projected": new, "conservative": conservative,
        "activation_rate": {"baseline": round(base[-1] / base[0], 3), "projected": round(new[-1] / new[0], 3)},
        "activations": {"baseline": base[-1], "projected": new[-1], "uplift": round(new[-1] / base[-1] - 1, 3)},
        "cac": {"baseline": round(spend_base / base[-1]), "projected": round(spend_new / new[-1])},
        "days_to_activate": {"baseline": round(days_base, 1), "projected_digital_products": 0, "projected_fibre": 6},
        "assumptions": {"digital_share": digital_share, "digital_cost_per_lead": 150, "partner_install_fee": 1500},
    }


def score_profile(p: dict, channel: str = "web") -> dict:
    """Score a live advisor session with the same model (for the 'leads the advisor could not close' queue)."""
    import pandas as pd

    from .catalogue import SEGMENT_NAMES

    seg = SEGMENT_NAMES.get(p.get("segment") or "", "Micro retail & services")
    emp = p.get("employees") or 3
    row = {
        "lead_source": "WhatsApp campaign" if channel == "whatsapp" else "Website form", "segment": seg,
        "business_type": p.get("business_type") or "Kirana store", "city_tier": str(p.get("tier") or 2),
        "preferred_language": "Hindi", "annual_turnover_band": "40 lakh - 1.5 cr",
        "has_gstin": "Y" if p.get("gstin") else "N", "has_udyam": "Y" if p.get("udyam") else "N",
        "current_internet": p.get("current_internet") or "None", "current_provider": "Local ISP",
        "contact_role": "Owner", "log_employees": np.log1p(emp), "num_sites": p.get("sites") or 1,
        "log_spend": np.log1p(p.get("current_spend") or 900), "n_interests": len(p.get("needs") or []) or 1,
    }
    X = pd.DataFrame([row])
    s = float(model()["pipe"].predict_proba(X[FEATURES_CAT + FEATURES_NUM])[:, 1][0])
    return {"score": round(s, 3), "why": _reasons(pd.Series(row))}
