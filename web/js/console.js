/* Back office ("control room") for Accel sales, partners and compliance. */
const C = { tab: "live", cache: {}, timer: null, labOpen: null, sim: null };
const TABS = [["live", "Live journeys"], ["calls", "Who to call"], ["rescue", "Rescue queue"], ["kyc", "KYC lab"],
  ["funnel", "Funnel & simulator"], ["segments", "Segments"], ["audit", "Bundle audit"], ["privacy", "Privacy log"]];

function cRender() {
  const root = $("#console");
  if (!root || getComputedStyle(root).display === "none") return;
  root.innerHTML = "";
  root.append(h("div", { class: "row between" },
    h("div", {}, h("h1", {}, "Accel Business · Control room"), h("div", { class: "sub" }, "What sales, partners and compliance see while the owner uses the phone on the left.")),
    h("span", { class: "pill-live" }, "live")));
  root.append(h("div", { class: "tabs" }, TABS.map(([k, label]) => h("button", { class: C.tab === k ? "on" : "", onclick: () => { C.tab = k; cRender(); } }, label))));
  const body = h("div", { id: "cbody" }, h("div", { class: "faint" }, "Loading…"));
  root.append(body);
  ({ live: cLive, calls: cCalls, rescue: cRescue, kyc: cKyc, funnel: cFunnel, segments: cSegments, audit: cAudit, privacy: cPrivacy }[C.tab])(body);
}

async function cached(key, path) {
  if (!C.cache[key]) C.cache[key] = await api(path);
  return C.cache[key];
}

/* ---------- live ---------- */
async function cLive(body) {
  const [live, ss] = await Promise.all([api("/api/backoffice/live"), api("/api/backoffice/sessions")]);
  body.innerHTML = "";
  body.append(h("div", { class: "kpis" },
    kpi(live.sessions, "Advisor conversations"), kpi(live.quoted, "Got a clear monthly price"), kpi(live.orders, "Orders placed"),
    kpi(live.live, "Fully live"), kpi(live.handoffs, "Asked for a person"), kpi(live.support_calls, "Calls to support (target 0)"),
    kpi(live.avg_turns_to_quote ?? "–", "Owner messages to reach a quote"),
    kpi(`${live.llm.ok}/${live.llm.calls}`, "AI calls answered (rest used fallback)")));
  const rows = ss.sessions;
  body.append(h("div", { class: "h2" }, "Leads the advisor hasn't closed (yet)"),
    h("div", { class: "faint", style: { marginBottom: "8px" } }, "Stalled for 10+ minutes, asked for a person, or under KYC review. Partners see the whole conversation, so the owner never repeats themselves. Score = chance to activate (model trained on last quarter's 5,000 leads)."));
  const tb = h("tbody");
  rows.forEach((r) => tb.append(h("tr", {},
    h("td", {}, h("b", {}, r.business), h("div", { class: "faint" }, [r.type, r.city, r.employees ? r.employees + " staff" : null, r.sites ? r.sites + (r.sites > 1 ? " sites" : " site") : null].filter(Boolean).join(" · "))),
    h("td", {}, h("span", { class: "tag " + ({ won: "green", handoff: "red", stalled: "amber", open: "blue" }[r.status] || "") }, r.status), h("div", { class: "faint" }, r.stage)),
    h("td", {}, r.score !== undefined ? h("span", { class: "score", style: scoreColor(r.score) }, Math.round(r.score * 100)) : "–", h("div", { class: "faint" }, (r.why || []).join(", "))),
    h("td", {}, r.quote ? inr(r.quote) + "/mo" : "–"),
    h("td", {}, r.lang.toUpperCase() + " · " + r.channel),
    h("td", {}, r.handoff_reason || (r.order_id ? "Order " + r.order_id : "")))));
  body.append(h("table", { class: "t" }, h("thead", {}, h("tr", {}, ["Business", "Status", "Score", "Quote", "Lang · channel", "Note"].map((x) => h("th", {}, x)))), tb));
  if (!rows.length) body.append(h("div", { class: "faint", style: { padding: "10px" } }, "Start a conversation on the phone to see it here."));
}

function kpi(v, label, delta) { return h("div", { class: "kpi" }, h("b", {}, v), h("span", {}, label), delta ? h("div", { class: "delta" }, delta) : null); }

/* ---------- who to call ---------- */
async function cCalls(body) {
  const d = await cached("leads", "/api/backoffice/leads?limit=40");
  body.innerHTML = "";
  body.append(h("div", { class: "muted", style: { marginBottom: "10px" } },
    `Ranked by expected value = chance to activate × typical bundle value × (1 − segment churn). Model AUC ${d.model.auc}; calling the top 20% of leads reaches ~39% of all activations (2× random).`));
  const tb = h("tbody");
  d.leads.forEach((r) => tb.append(h("tr", {}, h("td", {}, h("b", {}, r.business), h("div", { class: "faint" }, r.lead_id + " · " + r.city)),
    h("td", {}, r.segment), h("td", {}, r.source), h("td", {}, h("span", { class: "score", style: scoreColor(r.score) }, Math.round(r.score * 100))),
    h("td", {}, inr(r.priority_value)), h("td", { class: "faint" }, r.why.join(", ")))));
  body.append(h("table", { class: "t" }, h("thead", {}, h("tr", {}, ["Lead", "Segment", "Source", "Score", "Expected value/mo", "Why"].map((x) => h("th", {}, x)))), tb));
}

/* ---------- rescue ---------- */
async function cRescue(body) {
  const d = await cached("rescue", "/api/backoffice/rescue?limit=60");
  body.innerHTML = "";
  body.append(h("div", { class: "kpis" }, kpi(d.total.toLocaleString("en-IN"), "Dropped leads with a fixable reason"),
    kpi(d.expected_recovered, "Expected to recover"), kpi(inr(d.expected_mrr), "Expected monthly revenue recovered"),
    ...d.by_owner.map((o) => kpi(o.leads, o.owner === "digital" ? "Handled by the app (no visit)" : "Routed to partners"))));
  const tb = h("tbody");
  d.rows.forEach((r) => tb.append(h("tr", {}, h("td", {}, h("b", {}, r.business), h("div", { class: "faint" }, `${r.type} · ${r.city} · ${r.language}`)),
    h("td", {}, h("span", { class: "tag amber" }, r.drop_reason), h("div", { class: "faint" }, "stuck at: " + r.stage)),
    h("td", {}, r.action), h("td", {}, h("span", { class: "tag " + (r.owner === "digital" ? "blue" : "purple") }, r.owner)),
    h("td", {}, h("span", { class: "score", style: scoreColor(r.score) }, Math.round(r.score * 100))), h("td", {}, inr(r.rescue_value)))));
  body.append(h("table", { class: "t" }, h("thead", {}, h("tr", {}, ["Lead", "Why they dropped", "Next best action", "Owner", "Score", "Value"].map((x) => h("th", {}, x)))), tb));
}

/* ---------- KYC lab ---------- */
async function cKyc(body) {
  const d = await cached("lab", "/api/kyc/lab");
  body.innerHTML = "";
  body.append(h("div", { class: "kpis" }, kpi(`${d.score}/${d.total}`, "Applicants with the right verdict"),
    kpi(d.results.filter((r) => r.verdict === "APPROVED").length, "Approved with no human"),
    kpi(d.results.filter((r) => r.verdict === "ACTION_NEEDED").length, "Owner fixes in-app"),
    kpi(d.results.filter((r) => r.verdict === "REVIEW").length, "Sent to compliance"),
    kpi(d.results.filter((r) => r.verdict === "RESTRICTED").length, "Non-GST bundle only")));
  body.append(h("div", { class: "faint", style: { marginBottom: "10px" } }, "Pipeline: quality gate (blur/tilt) → auto-straighten → watermark removal → local OCR (RapidOCR, on our server) → field parser → GSTIN check digit → AI second reader only if the check fails → GST & Udyam registry → address-proof age (≤ 90 days) → who may sign (by constitution) → cross-document match."));
  const grid = h("div", { class: "lab" });
  d.results.forEach((r) => grid.append(h("div", { class: "labcard", onclick: () => { C.labOpen = r.applicant; cKycDetail(body, r.applicant); } },
    h("div", { class: "row between" }, h("b", {}, r.applicant), h("span", { class: "tag " + STATUS_TAG[r.verdict] }, r.verdict.replace("_", " "))),
    h("div", { style: { fontWeight: 600, marginTop: "4px" } }, r.business || ""),
    h("div", { class: "faint" }, r.issues.length ? r.issues.map((i) => "⚑ " + i.detail.split(/(?<=\.)\s/)[0].slice(0, 110)).join(String.fromCharCode(10)) : (r.auto.length ? "✓ " + r.auto.join("; ") : "✓ All checks passed")),
    h("div", { class: "faint", style: { marginTop: "4px" } }, r.match ? "✔ matches reviewer's expected verdict" : "✖ differs from expected (" + r.expected + ")"))));
  body.append(grid);
}

async function cKycDetail(body, kid) {
  const r = await api(`/api/kyc/lab/${kid}`);
  body.innerHTML = "";
  body.append(h("button", { class: "btn ghost sm", onclick: () => cRender() }, "← All applicants"));
  body.append(h("div", { class: "row between", style: { margin: "10px 0" } }, h("div", { class: "h2" }, `${kid} · ${(r.business || {}).trade_name || r.context.business_name || ""}`),
    h("span", { class: "tag " + STATUS_TAG[r.verdict] }, r.headline)));
  body.append(h("div", { class: "thumbs" }, r.files.map((f) => h("a", { href: `/api/kyc/doc/${f}`, target: "_blank" }, h("img", { src: `/api/kyc/doc/${f}`, alt: f })))));
  const tb = h("tbody");
  r.checks.forEach((c) => tb.append(h("tr", {}, h("td", {}, h("span", { class: "dot " + c.status, style: { display: "inline-grid", width: "20px", height: "20px", borderRadius: "50%", color: "#fff", placeItems: "center", fontSize: "11px" } }, STATUS_ICON[c.status])),
    h("td", {}, h("b", {}, c.label), h("div", { class: "faint" }, c.detail)), h("td", { class: "faint" }, c.fix || ""), h("td", { class: "faint" }, c.status === "pass" ? "" : c.owner_message || ""))));
  body.append(h("div", { style: { height: "10px" } }), h("table", { class: "t" }, h("thead", {}, h("tr", {}, ["", "Check", "Back-office action", "What the owner sees"].map((x) => h("th", {}, x)))), tb));
  const docs = h("div", { class: "grid2", style: { marginTop: "12px" } });
  Object.entries(r.documents).forEach(([tname, d]) => docs.append(h("div", { class: "card" }, h("b", {}, tname.replace("_", " ")),
    h("div", { class: "faint" }, `sharpness ${d.quality.sharpness} · tilt ${d.quality.skew_degrees}°` + (d.auto_fixes.length ? " · " + d.auto_fixes.join(", ") : "")),
    h("pre", { style: { whiteSpace: "pre-wrap", fontSize: "12px", margin: "6px 0 0" } }, Object.entries(d.fields).filter(([k]) => k !== "gstin_raw").map(([k, v]) => `${k}: ${v}`).join("\n") || "(unreadable)"))));
  body.append(docs);
}

/* ---------- funnel & simulator ---------- */
async function cFunnel(body) {
  const f = await cached("funnel", "/api/backoffice/funnel");
  if (!C.sim) C.sim = await api("/api/backoffice/simulate", { body: {} });
  body.innerHTML = "";
  const s = C.sim;
  body.append(h("div", { class: "kpis" },
    kpi(pct(s.activation_rate.baseline), "Lead → activation today", null),
    kpi(pct(s.activation_rate.projected), "Projected with Ek Baithak", `+${Math.round(s.activations.uplift * 100)}% activations`),
    kpi(inr(s.cac.baseline), "Cost per activation today"), kpi(inr(s.cac.projected), "Projected cost per activation"),
    kpi(f.avg_days_to_activate + " d", "Lead → activation today"), kpi("0 d / ~6 d", "Projected: digital products / fibre"),
    kpi(f.avg_follow_up_calls, "Status calls per customer today"), kpi("0", "Target with proactive tracker")));
  const fb = h("div", { class: "card" }, h("div", { class: "row between" }, h("b", {}, "Funnel: last quarter (grey) vs projected (red)"),
    h("span", { class: "faint" }, s.conservative ? `Conservative case (half the recovery): ${s.conservative[5]} activations` : "")));
  const max = s.baseline[0];
  ["Lead", "Contacted", "Needs assessed", "Quote accepted", "KYC complete", "Activated"].forEach((st, i) => fb.append(h("div", { style: { margin: "8px 0" } },
    h("div", { class: "row between faint" }, h("span", {}, st), h("span", {}, `${s.baseline[i].toLocaleString("en-IN")} → ${s.projected[i].toLocaleString("en-IN")}`)),
    h("div", { class: "bar" }, h("i", { class: "base", style: { width: (s.baseline[i] / max * 100) + "%" } }), h("i", { class: "proj", style: { width: (s.projected[i] / max * 100) + "%" } })))));
  const sl = h("div", { class: "card" }, h("b", {}, "What each fix recovers (drag to test assumptions)"),
    h("div", { class: "faint", style: { marginBottom: "6px" } }, "Share of leads lost to each reason that the new journey wins back. Defaults are deliberately conservative."));
  const drops = {}; f.drops.forEach((d) => { drops[d.drop_reason] = (drops[d.drop_reason] || 0) + d.n; });
  Object.entries(s.levers).sort((a, b) => (drops[b[0]] || 0) - (drops[a[0]] || 0)).forEach(([reason, v]) => {
    const out = h("span", { class: "faint" }, Math.round(v * 100) + "%");
    sl.append(h("div", { class: "slider-row" }, h("span", {}, `${reason} `, h("span", { class: "faint" }, `(${drops[reason] || 0})`)),
      h("input", { type: "range", min: 0, max: 0.9, step: 0.05, value: v, oninput: (e) => { out.textContent = Math.round(e.target.value * 100) + "%"; },
        onchange: async (e) => { C.sim = await api("/api/backoffice/simulate", { body: { levers: { ...C.sim.levers, [reason]: parseFloat(e.target.value) } } }); cFunnel(body); } }), out));
  });
  body.append(h("div", { class: "grid2" }, fb, sl));
  const calls = h("div", { class: "card" }, h("b", {}, "Why the tracker matters: churn rises with every status call"));
  f.calls_vs_churn.forEach((c) => calls.append(h("div", { style: { margin: "6px 0" } }, h("div", { class: "row between faint" }, h("span", {}, `${c.calls} call${c.calls > 1 ? "s" : ""} (${c.n} customers)`), h("span", {}, `6-month churn ${pct(c.churn, 0)} · NPS ${c.nps}`)),
    h("div", { class: "bar" }, h("i", { class: "base", style: { width: (c.churn / 0.3 * 100) + "%", background: "#e1121b", opacity: .7 } })))));
  const dr = h("tbody");
  f.drops.slice(0, 12).forEach((d) => dr.append(h("tr", {}, h("td", {}, d.drop_reason), h("td", {}, d.n), h("td", { class: "faint" }, d.fix))));
  body.append(h("div", { class: "grid2", style: { marginTop: "14px" } }, calls,
    h("table", { class: "t" }, h("thead", {}, h("tr", {}, ["Top drop reasons", "Leads", "Our fix"].map((x) => h("th", {}, x)))), dr)));
  body.append(h("div", { class: "faint", style: { marginTop: "8px" } }, `Cost model: ${Math.round(s.assumptions.digital_share * 100)}% of leads go digital at ₹${s.assumptions.digital_cost_per_lead}/lead (cloud, AI, messaging, registry APIs) + ₹${s.assumptions.partner_install_fee} partner fee per digital activation; the rest keep today's cost.`));
}

/* ---------- segments ---------- */
async function cSegments(body) {
  const f = await cached("funnel", "/api/backoffice/funnel");
  body.innerHTML = "";
  const plan = { "Professional offices": ["1 · Launch", "Fully digital: email, fibre, security are instant or 5-day installs", "Clinic & Office Pro ≈ ₹5–8k/mo, 12 months"],
    "Small multi-site businesses": ["1 · Launch (assisted)", "Digital quote + partner site survey; highest value, 0.5-month payback", "Multi-site One ≈ ₹10–40k/mo, 24 months"],
    "Micro retail & services": ["2 · Scale via cheap channels only", "Huge base but 23% churn and 8-month payback: WhatsApp, referral, partner kiosks", "Dukaan Starter ≈ ₹1.3–2.5k/mo, 12 months"],
    "Small manufacturers": ["3 · Pre-qualify digitally", "Leased lines need surveys (21–30 days); advisor qualifies, field team closes", "Factory Connect ≈ ₹12–40k/mo, 24 months"] };
  const tb = h("tbody");
  f.by_segment.sort((a, b) => a.payback_months - b.payback_months).forEach((s) => tb.append(h("tr", {}, h("td", {}, h("b", {}, s.segment)),
    h("td", {}, s.leads), h("td", {}, pct(s.activation_rate)), h("td", {}, pct(s.churn_6m, 0)), h("td", {}, inr(s.median_mrr)), h("td", {}, inr(s.cac_per_activation)),
    h("td", {}, s.payback_months + " mo"), h("td", {}, h("b", {}, plan[s.segment][0]), h("div", { class: "faint" }, plan[s.segment][1]), h("div", { class: "faint" }, plan[s.segment][2])))));
  body.append(h("table", { class: "t" }, h("thead", {}, h("tr", {}, ["Segment", "Leads", "Activation", "6-mo churn", "Median bundle", "Cost/activation", "Payback", "Our plan"].map((x) => h("th", {}, x)))), tb));
  const sb = h("tbody");
  f.by_source.sort((a, b) => a.cac_per_activation - b.cac_per_activation).forEach((s) => sb.append(h("tr", {}, h("td", {}, s.source), h("td", {}, pct(s.activation_rate)), h("td", {}, inr(s.cac_per_activation)), h("td", {}, pct(s.churn_6m, 0)))));
  body.append(h("div", { class: "h2", style: { marginTop: "16px" } }, "Channels: referrals convert 2× better at 1/6 the cost of field sales"),
    h("table", { class: "t" }, h("thead", {}, h("tr", {}, ["Source", "Activation", "Cost/activation", "6-mo churn"].map((x) => h("th", {}, x)))), sb));
}

/* ---------- audit ---------- */
async function cAudit(body) {
  const d = await cached("audit", "/api/backoffice/audit");
  body.innerHTML = "";
  body.append(h("div", { class: "kpis" }, kpi(d.bundles_affected, `of ${d.activated} bundles sold last quarter broke a catalogue rule`),
    ...Object.entries(d.by_rule).map(([k, v]) => kpi(v, { city_tier: "sold where not available", gstin: "GST-only products without an active GSTIN", min_employees: "below minimum size", dependency: "missing a required product" }[k] || k))));
  body.append(h("div", { class: "muted", style: { marginBottom: "10px" } }, "Re-checking every activated bundle against the same rules our advisor enforces. The advisor cannot make these mistakes: eligibility is code, not the AI's judgement."));
  const tb = h("tbody");
  d.violations.forEach((v) => tb.append(h("tr", {}, h("td", {}, v.lead_id), h("td", {}, v.business, h("div", { class: "faint" }, v.city)), h("td", {}, v.product), h("td", {}, v.problem), h("td", {}, v.lead_source))));
  body.append(h("table", { class: "t" }, h("thead", {}, h("tr", {}, ["Lead", "Business", "Product", "Rule broken", "Sold by"].map((x) => h("th", {}, x)))), tb));
}

/* ---------- privacy ---------- */
async function cPrivacy(body) {
  const d = await api("/api/backoffice/privacy-log?limit=80");
  body.innerHTML = "";
  body.append(h("div", { class: "kpis" }, kpi(d.consents, "Consent receipts"), kpi("0", "Document images stored"), kpi("masked", "IDs in logs and staff screens"), kpi("hash-chained", "Audit log (tamper-evident)")));
  const tb = h("tbody");
  d.audit.forEach((a) => tb.append(h("tr", {}, h("td", { class: "faint" }, new Date(a.ts * 1000).toLocaleTimeString()), h("td", {}, a.actor), h("td", {}, h("code", {}, a.action)), h("td", { class: "faint" }, a.subject), h("td", {}, a.detail), h("td", { class: "faint" }, a.hash))));
  body.append(h("table", { class: "t" }, h("thead", {}, h("tr", {}, ["Time", "Actor", "Action", "Session", "Detail (masked)", "Chain hash"].map((x) => h("th", {}, x)))), tb));
}

window.addEventListener("owner-update", () => { if (C.tab === "live" || C.tab === "privacy") cRender(); });
setInterval(() => { if (C.tab === "live") cRender(); }, 8000);
cRender();
