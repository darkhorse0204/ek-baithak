"""Bundle recommender: turns a business profile into an eligible, priced bundle.

Design rule: "the AI talks, the code decides". Every line has a plain-language reason,
and every product we could not offer comes back with the rule that blocked it and an
alternative, so the advisor can explain instead of silently dropping it.
"""
from __future__ import annotations

from .catalogue import FIXED_LINKS, Profile, check, min_term, price_items
from .data import CITY_STATE, CITY_TIER, business_type_segment, catalogue

# Needs the owner can tick. Labels are short so they fit on a phone chip.
NEEDS = {
    "upi_pos": ("Internet that never drops for UPI / card payments", "UPI/कार्ड पेमेंट के लिए भरोसेमंद इंटरनेट"),
    "billing": ("GST billing & stock on a tablet", "टैबलेट पर GST बिलिंग और स्टॉक"),
    "whatsapp": ("WhatsApp catalogue & customer messages", "WhatsApp कैटलॉग और ग्राहक मैसेज"),
    "sms": ("SMS reminders / offers to customers", "ग्राहकों को SMS रिमाइंडर/ऑफर"),
    "website": ("A simple website", "एक आसान वेबसाइट"),
    "email": ("Business email on your own name", "अपने नाम वाला बिज़नेस ईमेल"),
    "backup": ("Automatic backup of files", "फाइलों का ऑटो बैकअप"),
    "security": ("Protection from viruses & ransomware", "वायरस/रैनसमवेयर से सुरक्षा"),
    "firewall": ("Managed firewall for the office network", "ऑफिस नेटवर्क के लिए फ़ायरवॉल"),
    "cctv": ("CCTV you can watch on your phone", "फ़ोन पर दिखने वाला CCTV"),
    "guest_wifi": ("Separate Wi-Fi for customers", "ग्राहकों के लिए अलग Wi-Fi"),
    "failover": ("Backup internet when the main line is down", "मुख्य लाइन बंद हो तो बैकअप इंटरनेट"),
    "phone_lines": ("Office phone lines with IVR / call recording", "IVR/कॉल रिकॉर्डिंग वाली ऑफिस फ़ोन लाइन"),
    "tollfree": ("1800 toll-free number", "1800 टोल-फ्री नंबर"),
    "static_ip": ("Fixed IP for remote access / servers", "रिमोट एक्सेस के लिए फिक्स्ड IP"),
    "central_mgmt": ("Manage all branches' internet from one place", "सभी ब्रांच का इंटरनेट एक जगह से"),
    "iot_machines": ("Track machine uptime & power use", "मशीन अपटाइम और बिजली की निगरानी"),
    "fleet": ("GPS tracking for vehicles", "गाड़ियों की GPS ट्रैकिंग"),
    "high_bandwidth": ("Very fast internet for big files / many users", "बड़ी फाइलों/ज़्यादा लोगों के लिए तेज़ इंटरनेट"),
    "dedicated_line": ("Dedicated line with uptime guarantee (SLA)", "SLA वाली डेडिकेटेड लाइन"),
    "mobile": ("Business mobile numbers for staff", "स्टाफ के लिए बिज़नेस मोबाइल नंबर"),
}

BUSINESS_NEEDS = {
    "Kirana store": ["upi_pos", "billing", "whatsapp", "cctv", "mobile"],
    "Pharmacy": ["upi_pos", "billing", "cctv", "mobile"],
    "Sweet shop": ["upi_pos", "billing", "whatsapp", "cctv", "mobile"],
    "Bakery": ["upi_pos", "billing", "whatsapp", "mobile"],
    "Salon": ["upi_pos", "whatsapp", "guest_wifi", "mobile"],
    "Boutique": ["upi_pos", "whatsapp", "website", "mobile"],
    "Optician": ["upi_pos", "billing", "sms", "mobile"],
    "Mobile repair shop": ["upi_pos", "cctv", "whatsapp", "mobile"],
    "Hardware store": ["upi_pos", "billing", "cctv", "mobile"],
    "Stationery shop": ["upi_pos", "billing", "mobile"],
    "Dental clinic": ["email", "sms", "backup", "security", "guest_wifi", "mobile"],
    "CA firm": ["email", "backup", "security", "failover", "mobile"],
    "Coaching centre": ["guest_wifi", "website", "sms", "cctv", "mobile"],
    "Diagnostic lab": ["high_bandwidth", "email", "backup", "security", "failover", "sms", "mobile"],
    "Law office": ["email", "backup", "security", "mobile"],
    "Physiotherapy clinic": ["sms", "whatsapp", "email", "mobile"],
    "Real estate agency": ["whatsapp", "website", "email", "mobile"],
    "Travel agency": ["phone_lines", "whatsapp", "email", "mobile"],
    "Insurance agency": ["phone_lines", "email", "whatsapp", "mobile"],
    "Architecture studio": ["high_bandwidth", "backup", "email", "security", "mobile"],
    "Restaurant chain": ["billing", "cctv", "failover", "guest_wifi", "whatsapp", "central_mgmt", "mobile"],
    "Pharmacy chain": ["billing", "cctv", "failover", "central_mgmt", "mobile"],
    "Gym chain": ["guest_wifi", "cctv", "whatsapp", "mobile"],
    "Budget hotel group": ["guest_wifi", "cctv", "phone_lines", "failover", "mobile"],
    "Pre-school chain": ["cctv", "sms", "website", "mobile"],
    "Apparel retail chain": ["billing", "cctv", "whatsapp", "failover", "mobile"],
    "Electronics retail chain": ["billing", "cctv", "whatsapp", "failover", "mobile"],
    "Bakery chain": ["billing", "cctv", "whatsapp", "mobile"],
    "Auto-parts unit": ["dedicated_line", "iot_machines", "security", "email", "cctv", "mobile"],
    "Textile unit": ["dedicated_line", "iot_machines", "security", "email", "cctv", "mobile"],
    "Food processing unit": ["dedicated_line", "iot_machines", "email", "cctv", "fleet", "mobile"],
    "Furniture workshop": ["dedicated_line", "email", "cctv", "security", "mobile"],
    "Packaging unit": ["dedicated_line", "iot_machines", "email", "cctv", "mobile"],
    "Plastic moulding unit": ["dedicated_line", "iot_machines", "email", "security", "mobile"],
    "Printing press": ["high_bandwidth", "dedicated_line", "email", "security", "mobile"],
}
SEGMENT_NEEDS = {
    "micro": ["upi_pos", "whatsapp", "mobile"],
    "prof": ["email", "security", "mobile"],
    "multi": ["central_mgmt", "cctv", "failover", "billing", "mobile"],
    "mfg": ["dedicated_line", "security", "email", "mobile"],
}

# Friendly alternatives when a rule blocks a product.
ALTERNATIVES = {
    "P03": ["P02", "P01"], "P06": ["P05", "P03", "P02"], "P05": ["P03", "P02"],
    "P10": ["P09"], "P21": ["P20"], "P12": ["P08"], "P13": ["P08"], "P15": [], "P14": [],
    "P24": [], "P11": [], "P09": [], "P22": [], "P23": [],
}
NO_GST_TIPS = {
    "P15": "Start with the free WhatsApp Business app today. We switch you to the verified API channel the day your GSTIN is active.",
    "P14": "Use WhatsApp broadcast for now. Bulk SMS needs DLT registration, which needs a GSTIN.",
    "P12": "Business mobile lines with call forwarding cover this for now.",
    "P13": "A business mobile number can be your helpline until the GSTIN is active.",
    "P21": "Endpoint security on each device protects you until you qualify for a managed firewall.",
    "P24": "Machine monitoring needs an active GSTIN; we can add it later.",
}


def infer_segment(p: Profile) -> str:
    if p.segment in ("micro", "prof", "multi", "mfg"):
        return p.segment
    seg = business_type_segment().get(p.business_type)
    if seg:
        return {"Micro retail & services": "micro", "Professional offices": "prof",
                "Small multi-site businesses": "multi", "Small manufacturers": "mfg"}[seg]
    if (p.sites or 1) >= 3:
        return "multi"
    if (p.employees or 0) >= 7:
        return "prof"
    return "micro"


def default_needs(p: Profile) -> list[str]:
    return list(BUSINESS_NEEDS.get(p.business_type) or SEGMENT_NEEDS.get(infer_segment(p), []))


def fill_location(p: Profile) -> None:
    if p.city and not p.tier:
        p.tier = CITY_TIER.get(p.city.strip().title())
    if p.city and not p.state:
        p.state = CITY_STATE.get(p.city.strip().title(), "")


def _connectivity(p: Profile, seg: str, needs: set[str]) -> tuple[str, str]:
    emp, sites = p.employees or 1, p.sites or 1
    per_site_staff = emp / max(sites, 1)
    if not p.fibre_feasible and seg in ("micro", "prof", "multi"):
        return "P04", "Fibre can't reach your address yet, so we use 5G AirFiber: plug-and-play, installed in about 2 days."
    if seg == "mfg" or "dedicated_line" in needs:
        if emp >= 25 and ("high_bandwidth" in needs or emp >= 80):
            return "P06", "Machines and ERP need a line nobody else shares: 100 Mbps dedicated with a 99.9% uptime guarantee."
        return "P05", "A dedicated 1:1 line with a 99.5% uptime guarantee, so production systems never share bandwidth."
    if seg == "multi":
        if per_site_staff >= 10 or "high_bandwidth" in needs:
            return "P02", f"300 Mbps fibre at each of your {sites} sites, enough for billing, CCTV and staff together."
        return "P01", f"100 Mbps business fibre at each of your {sites} sites, one bill for all."
    if seg == "prof":
        if "high_bandwidth" in needs and emp >= 15 and p.tier == 1:
            return "P03", "1 Gbps fibre with priority support for heavy files and many users."
        if emp >= 8 or "high_bandwidth" in needs:
            return "P02", f"300 Mbps fibre comfortably serves {emp} people on calls, cloud files and email at once."
        return "P01", "100 Mbps business fibre with unlimited data: steady for a small office."
    return "P01", "Business fibre with unlimited data. It does not drop like a phone hotspot, so UPI and card payments go through first time."


def recommend(p: Profile, addons: dict[str, bool] | None = None, term: int = 12, qty_override: dict[str, int] | None = None) -> dict:
    """Build the recommended bundle. `addons` lets the owner switch optional lines on/off."""
    fill_location(p)
    seg = infer_segment(p)
    p.segment = seg
    needs = set(p.needs) if (p.needs and p.needs_confirmed) else set(p.needs or []) | set(default_needs(p))
    # Price-sensitive micro shops: guessed extras start switched off; owner-confirmed needs stay on.
    soft = {"whatsapp", "cctv", "website", "sms", "guest_wifi"} if (seg == "micro" and not p.needs_confirmed) else set()
    c = p.counts or {}
    emp, sites = max(p.employees or 1, 1), max(p.sites or 1, 1)

    core: dict[str, tuple[int, str]] = {}
    optional: dict[str, tuple[int, str]] = {}

    link, why = _connectivity(p, seg, needs)
    core[link] = (sites, why)

    # Mobile lines
    lines = int(c.get("mobile_lines") or {"micro": 2, "prof": 2, "multi": sites // 2 + 2, "mfg": 3}[seg])
    mob = "P07" if seg == "micro" else "P08"
    core[mob] = (lines, "Business mobile lines on one bill" + (" with roaming and priority care for staff who travel." if mob == "P08" else ", with 50 GB data each for UPI and WhatsApp on the go."))

    def want(tag: str) -> bool:
        return tag in needs

    if want("billing") or (seg == "micro" and want("upi_pos") and p.business_type in ("Kirana store", "Pharmacy", "Sweet shop", "Bakery", "Hardware store", "Stationery shop", "Optician")):
        n = int(c.get("counters") or (sites if seg == "multi" else 1))
        (core if want("billing") else optional)["P19"] = (n, "GST-ready billing, stock and UPI/card acceptance on a tablet at each counter.")
    if want("whatsapp"):
        (optional if "whatsapp" in soft else core)["P15"] = (1, "A verified WhatsApp channel with your catalogue and 1,000 customer conversations a month.")
    if want("sms"):
        (optional if "sms" in soft else core)["P14"] = (1, "10,000 SMS a month for appointment reminders and offers; we help with DLT registration.")
    if want("website"):
        (core if seg == "micro" and "website" not in soft else optional)["P18"] = (1, "Your own domain and a 5-page website so customers find you on Google.")
    if want("email") or seg in ("prof", "multi", "mfg"):
        n = int(c.get("email_users") or {"micro": 2, "prof": min(emp, 15), "multi": min(emp, sites + 2), "mfg": max(3, min(emp // 10, 20))}[seg])
        core["P16"] = (n, f"Email on your own business name for {n} people, plus shared documents and video meetings.")
    if want("backup"):
        core["P17"] = (1, "Every PC and phone backs up automatically, so a crash or theft never loses client files.")
    elif seg in ("prof", "mfg"):
        optional["P17"] = (1, "Automatic 1 TB backup of PCs and phones.")
    if want("security") or seg in ("prof", "mfg"):
        n = int(c.get("devices") or {"micro": 2, "prof": max(2, emp // 2), "multi": sites * 2, "mfg": max(5, emp // 10)}[seg])
        (core if want("security") else optional)["P20"] = (n, f"Antivirus and ransomware protection on {n} devices.")
    if want("firewall") or (seg in ("mfg", "multi") and emp >= 10) or (seg == "prof" and want("security") and emp >= 10):
        target = core if (want("firewall") or seg == "mfg") else optional
        target["P21"] = (sites, "A managed next-gen firewall watched by our security team, so client data stays inside.")
    if want("cctv"):
        n = int(c.get("cameras") or {"micro": 2, "prof": 2, "multi": sites * 2, "mfg": 4}[seg])
        (optional if "cctv" in soft else core)["P23"] = (n, f"{n} HD cameras with 30 days of cloud recording, viewable on your phone.")
    if want("guest_wifi"):
        (optional if "guest_wifi" in soft else core)["P22"] = (sites, "A separate Wi-Fi for customers, so they never touch your billing network.")
    if want("failover") or seg == "multi":
        (core if want("failover") else optional)["P09"] = (sites, "A backup 4G/5G router takes over automatically if the fibre goes down: no lost sales.")
    elif seg == "prof":
        optional["P09"] = (1, "Backup 4G/5G router that switches on by itself when fibre is down.")
    if want("phone_lines"):
        n = int(c.get("phone_channels") or max(2, min(4, emp // 5)))
        core["P12"] = (n, f"{n} cloud phone lines with IVR and call recording; staff answer from anywhere.")
    if want("tollfree"):
        core["P13"] = (1, "A 1800 toll-free number routed to your team.")
    if want("static_ip") or (want("cctv") and seg in ("prof", "mfg")):
        (core if want("static_ip") else optional)["P11"] = (1, "A fixed public IP for CCTV or remote access to your systems.")
    if want("central_mgmt") or (seg == "multi" and sites >= 3):
        core["P10"] = (sites, f"Manage the internet at all {sites} sites from one screen, with billing traffic given priority.")
    if want("iot_machines"):
        n = int(c.get("machines") or 5)
        core["P24"] = (n, f"Sensors on {n} machines show uptime and power use live on your phone.")
    if want("fleet"):
        n = int(c.get("vehicles") or 2)
        core["P25"] = (n, f"Live GPS tracking for {n} vehicles.")

    # Products the owner asked for by name go in as-is; the eligibility check below explains any block.
    per_site = {"P01", "P02", "P03", "P04", "P05", "P06", "P09", "P10", "P21", "P22"}
    for pid in p.requested or []:
        if pid in catalogue().index and pid not in core:
            if pid in optional:
                core[pid] = optional.pop(pid)
            else:
                core[pid] = (sites if pid in per_site else 1, f"You asked for {catalogue().loc[pid].product_name}: " + catalogue().loc[pid].description + ".")
            if pid in ("P01", "P02", "P03", "P04", "P05", "P06") and pid != link and link in core:
                core.pop(link)
                link = pid

    # Quantity overrides from the quote screen.
    for pid, q in (qty_override or {}).items():
        for d in (core, optional):
            if pid in d:
                d[pid] = (max(1, int(q)), d[pid][1])

    # Owner toggles: add-ons switched on move to core; core lines switched off move to optional.
    addons = addons or {}
    for pid, on in addons.items():
        if on and pid in optional:
            core[pid] = optional.pop(pid)
        elif not on and pid in core and pid != link:
            optional[pid] = core.pop(pid)

    excluded = []
    # Resolve eligibility. Re-run until stable because removing a line can break a dependency.
    for _ in range(4):
        changed = False
        ids = set(core)
        for pid in list(core):
            fails = check(pid, p, ids)
            if not fails:
                continue
            qty, why = core.pop(pid)
            changed = True
            alt_used = None
            for alt in ALTERNATIVES.get(pid, []):
                if alt not in core and not check(alt, p, set(core) | {alt}):
                    core[alt] = (qty, f"{catalogue().loc[alt].description}. {fails[0]['text']}, so we picked this instead.")
                    optional.pop(alt, None)
                    alt_used = alt
                    break
            excluded.append({
                "product_id": pid, "name": catalogue().loc[pid].product_name, "reasons": [f["text"] for f in fails],
                "rules": [f["rule"] for f in fails], "alternative": alt_used,
                "alternative_name": catalogue().loc[alt_used].product_name if alt_used else None,
                "tip": NO_GST_TIPS.get(pid) if any(f["rule"] == "gstin" for f in fails) else None,
            })
        if not changed:
            break
    for pid in list(optional):
        if check(pid, p, set(core) | {pid}):
            optional.pop(pid)

    items = {pid: q for pid, (q, _) in core.items()}
    contract = max(term, min_term(items) if any(catalogue().loc[x].min_contract_months >= 24 for x in items) else term)
    priced = price_items(items, contract)
    reasons = {pid: why for pid, (_, why) in core.items()}
    for ln in priced["lines"]:
        ln["why"] = reasons[ln["product_id"]]
    opt_priced = price_items({pid: q for pid, (q, _) in optional.items()}, contract)
    for ln in opt_priced["lines"]:
        ln["why"] = optional[ln["product_id"]][1]

    result = {
        "segment": seg, "needs": sorted(needs), "contract_months": contract,
        "lines": priced["lines"], "optional": opt_priced["lines"],
        "monthly": priced["monthly"], "setup": priced["setup"],
        "per_day": round(priced["monthly"] / 30), "install_days": priced["install_days"],
        "excluded": excluded,
        "instant": [ln["name"] for ln in priced["lines"] if ln["install_days"] <= 1],
        "profile": p.to_dict(),
    }
    if p.current_spend:
        result["vs_current"] = {"current": p.current_spend, "delta": priced["monthly"] - p.current_spend}
    if p.budget and priced["monthly"] > p.budget:
        result["budget_note"] = lean_version(p, items, contract)
    return result


def lean_version(p: Profile, items: dict[str, int], term: int) -> dict:
    """Cheapest version that keeps connectivity and the most-asked needs, for price-sensitive owners."""
    downgrade = {"P03": "P02", "P02": "P01", "P08": "P07", "P06": "P05"}
    lean = {}
    keep_order = ["P01", "P02", "P03", "P04", "P05", "P06", "P07", "P08", "P19", "P15", "P23", "P22", "P16", "P20", "P09"]
    for pid in keep_order:
        if pid in items:
            nid = downgrade.get(pid, pid)
            if not check(nid, p, set(lean) | {nid, *[x for x in items if x in FIXED_LINKS]}):
                lean[nid] = items[pid] if pid not in ("P07", "P08") else max(1, items[pid] - 1)
    while lean and price_items(lean, max(term, 24))["monthly"] > p.budget and len(lean) > 1:
        lean.pop(list(lean)[-1])
    priced = price_items(lean, max(term, 24))
    return {"items": lean, "monthly": priced["monthly"], "contract_months": max(term, 24),
            "fits": priced["monthly"] <= p.budget, "lines": priced["lines"]}


def audit_historical_bundles() -> dict:
    """Re-check every bundle sold last quarter against the catalogue rules."""
    from .data import gstin_registry, leads

    reg = gstin_registry()
    rows = []
    act = leads()[leads().outcome == "Activated"]
    for _, r in act.iterrows():
        items = {it.split("x")[0]: int(it.split("x")[1]) for it in str(r.bundle_products).split(";")}
        status = reg.loc[r.gstin].status if isinstance(r.gstin, str) and r.gstin in reg.index else ""
        prof = Profile(tier=int(r.city_tier), employees=int(r.employee_count), sites=int(r.num_sites),
                       gstin=r.gstin if isinstance(r.gstin, str) else "", gstin_status=status if r.has_gstin == "Y" else "")
        for pid in items:
            for f in check(pid, prof, set(items)):
                rows.append({"lead_id": r.lead_id, "business": r.business_name, "city": r.city, "product_id": pid,
                             "product": catalogue().loc[pid].product_name, "rule": f["rule"], "problem": f["text"],
                             "gstin_status": status or "none", "lead_source": r.lead_source})
    by_rule: dict[str, int] = {}
    for x in rows:
        by_rule[x["rule"]] = by_rule.get(x["rule"], 0) + 1
    return {"violations": rows, "count": len(rows), "bundles_affected": len({x["lead_id"] for x in rows}),
            "by_rule": by_rule, "activated": len(act)}
