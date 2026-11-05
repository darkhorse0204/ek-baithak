"""Catalogue rules and pricing. This is the single source of truth for what can be sold.

The LLM never decides eligibility or price: it only talks. Everything here is plain code
so the same answer comes back every time and every rule can be explained.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .data import catalogue

SEGMENT_CODES = {
    "Micro retail & services": "micro",
    "Professional offices": "prof",
    "Small multi-site businesses": "multi",
    "Small manufacturers": "mfg",
}
SEGMENT_NAMES = {v: k for k, v in SEGMENT_CODES.items()}
FIXED_LINKS = ["P01", "P02", "P03", "P05", "P06"]  # wired / dedicated connectivity


@dataclass
class Profile:
    business_name: str = ""
    business_type: str = ""
    segment: str = ""  # micro | prof | multi | mfg
    city: str = ""
    tier: int | None = None
    state: str = ""
    employees: int | None = None
    sites: int | None = None
    gstin: str = ""
    gstin_status: str = ""  # Active | Cancelled | Suspended | "" (none)
    constitution: str = ""
    udyam: str = ""
    current_internet: str = ""
    current_spend: int | None = None
    needs: list[str] = field(default_factory=list)
    counts: dict = field(default_factory=dict)  # mobile_lines, email_users, devices, cameras, counters, vehicles, machines, phone_channels
    budget: int | None = None
    requested: list[str] = field(default_factory=list)  # product ids the owner asked for by name
    needs_confirmed: bool = False  # True once the owner ticked their needs
    fibre_feasible: bool = True
    pincode: str = ""
    language: str = "en"

    @property
    def gst_active(self) -> bool:
        return bool(self.gstin) and self.gstin_status == "Active"

    def to_dict(self) -> dict:
        d = self.__dict__.copy()
        d["gst_active"] = self.gst_active
        return d


def unit_price(pid: str, term_months: int) -> int:
    """Transparent price rule: 24-month term = list minimum, 12-month = middle of range,
    shorter terms = top of range. Rounded to end in 9 like a shop price."""
    p = catalogue().loc[pid]
    lo, hi = int(p.price_min_inr_per_month), int(p.price_max_inr_per_month)
    if term_months >= 24:
        return lo
    if term_months < 12:
        return hi
    mid = lo + (hi - lo) / 2
    return int(round(mid / 10)) * 10 - 1 if mid >= 100 else int(round(mid))


def check(pid: str, profile: Profile, bundle_ids: set[str]) -> list[dict]:
    """Return every rule this product breaks for this business (empty list = eligible)."""
    p = catalogue().loc[pid]
    fails = []
    if profile.tier and profile.tier not in p.tiers:
        fails.append({"rule": "city_tier", "text": f"{p.product_name} is only sold in tier-{'/'.join(map(str, sorted(p.tiers)))} cities"})
    if profile.employees is not None and profile.employees < p.min_employees:
        fails.append({"rule": "min_employees", "text": f"{p.product_name} needs at least {p.min_employees} employees"})
    if profile.sites is not None and profile.sites < p.min_sites:
        fails.append({"rule": "min_sites", "text": f"{p.product_name} needs at least {p.min_sites} sites"})
    if p.requires_gstin == "Y" and not profile.gst_active:
        why = "an active GSTIN" if not profile.gstin else f"an active GSTIN (yours is {profile.gstin_status or 'not verified'})"
        fails.append({"rule": "gstin", "text": f"{p.product_name} can only be sold with {why}"})
    if p.needs_one_of and not (set(p.needs_one_of) & bundle_ids):
        names = ", ".join(catalogue().loc[x].product_name for x in p.needs_one_of)
        fails.append({"rule": "dependency", "text": f"{p.product_name} works only with one of: {names}"})
    return fails


def validate_bundle(items: dict[str, int], profile: Profile) -> list[dict]:
    ids = set(items)
    out = []
    for pid in items:
        for f in check(pid, profile, ids):
            out.append({"product_id": pid, **f})
    return out


def min_term(items: dict[str, int]) -> int:
    cat = catalogue()
    return max([int(cat.loc[p].min_contract_months) for p in items] + [1])


def price_items(items: dict[str, int], term_months: int) -> dict:
    cat = catalogue()
    lines, monthly, setup, install = [], 0, 0, 0
    for pid, qty in sorted(items.items()):
        p = cat.loc[pid]
        term = max(term_months, int(p.min_contract_months))
        up = unit_price(pid, term)
        lines.append({
            "product_id": pid, "name": p.product_name, "category": p.category, "unit": p.unit, "qty": qty,
            "unit_price": up, "monthly": up * qty, "setup": int(p.one_time_setup_inr) * qty,
            "install_days": int(p.typical_install_days), "min_contract": int(p.min_contract_months),
            "description": p.description,
        })
        monthly += up * qty
        setup += int(p.one_time_setup_inr) * qty
        install = max(install, int(p.typical_install_days))
    return {"lines": lines, "monthly": monthly, "setup": setup, "install_days": install}
