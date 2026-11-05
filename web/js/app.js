/* Owner app: welcome -> advisor chat -> plan -> consent -> KYC -> sign & pay -> tracker -> my data */
const S = { lang: "en", session: null, screen: "welcome", msgs: [], reco: null, profile: {}, kyc: null, order: null,
  consent: null, notice: null, meta: null, busy: false, signer: null, kycResolved: false, recorder: null };
const phone = () => $("#phone");
const STEP_OF = { chat: 1, quote: 2, consent: 3, kyc: 3, sign: 4, track: 5, mydata: 5 };

async function boot() {
  if (location.hash === "#owner") document.body.classList.add("owner-only");
  S.meta = await api("/api/meta");
  I18N.table = S.meta.i18n;
  render();
}

function go(screen) { S.screen = screen; render(); window.dispatchEvent(new Event("owner-update")); }

function header() {
  const step = STEP_OF[S.screen] || 0;
  return [
    h("div", { class: "app-head" },
      h("div", { class: "logo" }, "A"),
      h("div", { class: "t" }, h("b", {}, "Accel Business"), h("small", {}, S.screen === "chat" ? (S.busy ? "typing…" : "Advisor · online") : t("ui_tagline"))),
      S.session && S.screen === "chat" ? h("button", { class: "iconbtn", onclick: () => send("I want to talk to a person") }, "👤 " + t("ui_talk_human")) : null,
      S.session && S.screen !== "chat" && S.screen !== "mydata" ? h("button", { class: "iconbtn", onclick: () => go("chat") }, "💬") : null,
      S.session ? h("button", { class: "iconbtn", onclick: () => go("mydata"), title: t("ui_my_data") }, "🔒") : null),
    step ? h("div", { class: "steps" }, [1, 2, 3, 4, 5].map((i) => h("i", { class: i <= step ? "on" : "" }))) : null,
  ];
}

function render() {
  const p = phone();
  p.innerHTML = "";
  p.append(...header().filter(Boolean));
  const scr = h("div", { class: "screen", id: "screen" });
  p.append(scr);
  ({ welcome, chat, quote, consent, kyc, sign, track, mydata }[S.screen])(scr);
}

/* ---------------- welcome ---------------- */
function welcome(scr) {
  const langs = S.meta.languages;
  scr.append(h("div", { class: "welcome" },
    h("div", { class: "big" }, "1"),
    h("h1", {}, "Ek Baithak"),
    h("p", {}, (I18N.table[S.lang] || {}).ui_tagline || "Your business, live in one sitting"),
    h("div", { class: "faint", style: { marginBottom: "8px" } }, t("ui_choose_lang")),
    h("div", { class: "langs" }, Object.entries(langs).map(([code, m]) =>
      h("button", { class: S.lang === code ? "on" : "", onclick: () => { S.lang = code; I18N.lang = code; render(); } }, m.native, h("small", {}, m.name)))),
    h("div", { style: { height: "16px" } }),
    h("button", { class: "btn", onclick: start }, t("ui_start") + " →"),
    h("div", { class: "note" }, "🔒 We ask only what we need, in your language. Typing, tapping or a voice note: all work.")));
}

async function start() {
  I18N.lang = S.lang;
  const r = await api("/api/advisor/start", { body: { lang: S.lang, channel: "web" } });
  S.session = r.session;
  S.msgs = [{ role: "bot", text: r.reply, quick: r.quick_replies }];
  go("chat");
}

/* ---------------- chat ---------------- */
function chat(scr) {
  const box = h("div", { class: "chat", id: "chatbox" });
  const last = S.msgs.length - 1;
  S.msgs.forEach((m, i) => {
    if (m.role === "sys") { box.append(h("div", { class: "msg sys" }, m.text)); return; }
    box.append(h("div", { class: "msg " + (m.role === "me" ? "me" : "") }, m.text,
      m.role === "bot" && "speechSynthesis" in window ? h("span", { class: "meta", style: { cursor: "pointer" }, onclick: () => speak(m.text) }, "🔊") : null,
      m.voice ? h("span", { class: "meta" }, "🎤 voice note") : null));
    if (i === last && m.role === "bot") {
      if (m.quick && m.quick.length) box.append(h("div", { class: "chips" }, m.quick.map((q) =>
        h("button", { class: "chip", onclick: () => q.value === "__type_gstin__" ? askGstin() : send(q.value, q.label) }, q.label))));
      if (m.needs) box.append(needsCard(m.needs));
      if (m.reco) box.append(planBubble(m.reco));
    } else if (m.reco && m.role === "bot") box.append(planBubble(m.reco, true));
  });
  if (S.busy) box.append(h("div", { class: "typing" }, h("span"), h("span"), h("span")));
  scr.append(box);
  const input = h("input", { id: "chatinput", placeholder: t("ui_type_message"), autocomplete: "off",
    onkeydown: (e) => { if (e.key === "Enter" && input.value.trim()) { send(input.value.trim()); } } });
  const mic = h("button", { class: "round", title: "Hold to talk", id: "mic" }, "🎤");
  if (navigator.mediaDevices && window.MediaRecorder) {
    mic.addEventListener("pointerdown", startRec); mic.addEventListener("pointerup", stopRec); mic.addEventListener("pointerleave", stopRec);
  } else mic.classList.add("hide");
  const sendBtn = h("button", { class: "round", onclick: () => input.value.trim() && send(input.value.trim()) }, "➤");
  phone().append(h("div", { class: "composer" }, input, mic, sendBtn));
  scr.scrollTop = scr.scrollHeight;
  setTimeout(() => { scr.scrollTop = scr.scrollHeight; }, 30);
}

function askGstin() {
  S.msgs.push({ role: "sys", text: "Type your 15-character GSTIN. Demo GSTINs: 27PZSXS1936O1ZH (dental clinic, Nagpur) · 27XUIXG0767D1ZP (furniture unit) · 37IHKXV5167L1ZS (GST cancelled)" });
  render();
  const i = $("#chatinput"); i.placeholder = "e.g. 27PZSXS1936O1ZH"; i.focus();
}

function needsCard(n) {
  const card = h("div", { class: "needs-card" });
  n.options.forEach((o) => card.append(h("label", {}, h("input", { type: "checkbox", value: o.tag, checked: o.checked }), h("span", {}, o.label))));
  card.append(h("button", { class: "btn sm", style: { marginTop: "8px", width: "100%" }, onclick: () => {
    const tags = [...card.querySelectorAll("input:checked")].map((x) => x.value);
    send("__needs__:" + tags.join(","), [...card.querySelectorAll("input:checked")].map((x) => x.nextSibling.textContent).join(", "));
  } }, t("ui_confirm") + " ✓"));
  return card;
}

function planBubble(r, small) {
  return h("div", { class: "plan-bubble" },
    h("div", { class: "faint" }, t("ui_your_plan")),
    h("div", { class: "price" }, inr(r.monthly), h("small", {}, t("ui_per_month"))),
    h("div", { class: "faint" }, r.lines.map((l) => `${ICONS[l.product_id] || "•"} ${l.name}${l.qty > 1 ? " ×" + l.qty : ""}`).join("  ·  ")),
    small ? null : h("button", { class: "btn", style: { marginTop: "10px" }, onclick: () => go("quote") }, t("ui_see_plan") + " →"));
}

async function send(text, label) {
  if (S.busy) return;
  S.msgs.push({ role: "me", text: label || text });
  S.busy = true; render();
  try {
    const r = await api("/api/advisor/message", { body: { session: S.session, text } });
    handleReply(r);
  } catch (e) {
    S.msgs.push({ role: "sys", text: "Network issue, please try again." });
  }
  S.busy = false; render();
  window.dispatchEvent(new Event("owner-update"));
}

function handleReply(r) {
  if (r.error) { S.msgs.push({ role: "sys", text: r.error }); return; }
  S.profile = r.profile || S.profile;
  if (r.reco) S.reco = r.reco;
  S.msgs.push({ role: "bot", text: r.reply, quick: r.quick_replies, needs: r.needs, reco: r.reco });
  if (r.go === "checkout") setTimeout(() => go("quote"), 900);
}

function speak(text) {
  const u = new SpeechSynthesisUtterance(text.replace(/[•→]/g, ""));
  u.lang = S.meta.languages[S.lang].speech;
  speechSynthesis.cancel(); speechSynthesis.speak(u);
}

async function startRec(e) {
  e.preventDefault();
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    const rec = new MediaRecorder(stream);
    const chunks = [];
    rec.ondataavailable = (ev) => chunks.push(ev.data);
    rec.onstop = async () => {
      stream.getTracks().forEach((tr) => tr.stop());
      const blob = new Blob(chunks, { type: rec.mimeType || "audio/webm" });
      if (blob.size < 2000) return;
      const fd = new FormData(); fd.append("session", S.session); fd.append("audio", blob, "voice.webm");
      S.busy = true; S.msgs.push({ role: "me", text: "🎤 …", voice: true }); render();
      try {
        const r = await api("/api/advisor/voice", { form: fd });
        S.msgs[S.msgs.length - 1].text = r.transcript || "🎤";
        handleReply(r);
      } catch (err) { S.msgs.push({ role: "sys", text: "Couldn't hear that. Please type instead." }); }
      S.busy = false; render();
    };
    rec.start(); S.recorder = rec;
    $("#mic").classList.add("rec"); $("#chatinput").placeholder = t("ui_listening");
  } catch (err) { toast("Microphone not available", phone()); }
}
function stopRec() { if (S.recorder && S.recorder.state === "recording") { S.recorder.stop(); S.recorder = null; } }

/* ---------------- quote ---------------- */
function quote(scr) {
  const r = S.reco;
  if (!r) { go("chat"); return; }
  const instant = r.lines.filter((l) => l.install_days <= 1);
  const wrap = h("div", {});
  wrap.append(h("div", { class: "price-hero" },
    h("div", { class: "faint" }, t("ui_your_plan") + " · " + (S.profile.business_name || S.profile.business_type || "")),
    h("div", { class: "amt" }, inr(r.monthly), h("small", {}, t("ui_per_month"))),
    h("span", { class: "day" }, t("ui_per_day", { n: r.per_day })),
    r.vs_current ? h("div", { class: "faint", style: { marginTop: "6px" } }, t("ui_vs_today", { n: r.vs_current.current.toLocaleString("en-IN") })) : null,
    h("div", { class: "faint", style: { marginTop: "6px" } }, `${t("ui_setup")}: ${inr(r.setup)} · ${t("ui_contract")}: ${r.contract_months} ${t("ui_months")} · GST extra`)));
  const body = h("div", { class: "pad stack" });
  body.append(h("div", { class: "seg" },
    h("button", { class: r.contract_months < 24 ? "on" : "", onclick: () => requote({ term: 12 }) }, t("ui_term_12")),
    h("button", { class: r.contract_months >= 24 ? "on" : "", onclick: () => requote({ term: 24 }) }, t("ui_term_24"))));
  body.append(h("div", { class: "row", style: { gap: "6px", flexWrap: "wrap" } },
    instant.length ? h("span", { class: "tag green" }, "⚡ " + t("ui_live_today") + ": " + instant.map((l) => l.name.replace("Business ", "")).join(", ")) : null,
    r.install_days > 1 ? h("span", { class: "tag blue" }, "🔧 " + t("ui_installed_in", { n: r.install_days })) : null));
  const card = h("div", { class: "card" });
  r.lines.forEach((l) => card.append(lineRow(l, true)));
  body.append(card);
  if (r.optional && r.optional.length) {
    body.append(h("div", { class: "h2", style: { fontSize: "15px" } }, t("ui_addons")));
    const oc = h("div", { class: "card" });
    r.optional.forEach((l) => oc.append(lineRow(l, false)));
    body.append(oc);
  }
  if (r.excluded && r.excluded.length) {
    body.append(h("div", { class: "h2", style: { fontSize: "15px" } }, t("ui_not_offered")));
    r.excluded.forEach((e) => body.append(h("div", { class: "excl" }, h("b", {}, e.name), " · ", e.reasons.join("; "),
      e.alternative_name ? h("div", {}, "→ We added " + e.alternative_name + " instead.") : null, e.tip ? h("div", {}, "💡 " + e.tip) : null)));
  }
  if (r.budget_note) body.append(h("div", { class: "excl", style: { background: "#e8f0fc" } },
    h("b", { style: { color: "#1f5fbf" } }, `Budget option: ${inr(r.budget_note.monthly)}/month`), ` (${r.budget_note.contract_months} months): `,
    r.budget_note.lines.map((l) => `${l.name} ×${l.qty}`).join(", ")));
  body.append(h("div", { class: "faint" }, "Prices: 24-month plans use the lowest list price; 12-month the mid price. Same price for everyone, no haggling."));
  wrap.append(body);
  wrap.append(h("div", { class: "sticky-foot" }, h("button", { class: "btn", onclick: () => go("consent") }, t("ui_continue") + " · " + inr(r.monthly) + t("ui_per_month"))));
  scr.append(wrap);
}

function lineRow(l, core) {
  const fixed = ["P01", "P02", "P03", "P04", "P05", "P06"].includes(l.product_id) && core;
  const sw = h("label", { class: "switch" }, h("input", { type: "checkbox", checked: core, disabled: fixed,
    onchange: (e) => requote({ addons: { [l.product_id]: e.target.checked } }) }), h("span"));
  const qtyable = core && l.qty >= 1 && ["P07", "P08", "P16", "P20", "P23", "P19", "P12"].includes(l.product_id);
  return h("div", { class: "line" },
    h("div", { class: "ic" }, ICONS[l.product_id] || "•"),
    h("div", { class: "b" },
      h("div", { class: "nm" }, l.name, l.qty > 1 ? ` ×${l.qty}` : ""),
      h("div", { class: "why" }, l.why || l.description),
      qtyable ? h("div", { class: "row", style: { gap: "6px", marginTop: "4px" } },
        h("button", { class: "chip", onclick: () => requote({ qty: { [l.product_id]: Math.max(1, l.qty - 1) } }) }, "−"),
        h("span", { class: "faint" }, l.qty + " × " + inr(l.unit_price)),
        h("button", { class: "chip", onclick: () => requote({ qty: { [l.product_id]: l.qty + 1 } }) }, "+")) : null),
    h("div", { class: "amt" }, inr(l.monthly), h("small", {}, l.setup ? `+${inr(l.setup)} setup` : (l.install_days <= 1 ? "today" : `${l.install_days} days`))),
    fixed ? null : sw);
}

async function requote(body) {
  const r = await api("/api/advisor/quote", { body: { session: S.session, ...body } });
  S.reco = r.reco; render();
  window.dispatchEvent(new Event("owner-update"));
}

/* ---------------- consent ---------------- */
async function consent(scr) {
  if (!S.notice) S.notice = await api("/api/consent/notice");
  const chosen = S.consentChoice || Object.fromEntries(Object.entries(S.notice.purposes).map(([k, v]) => [k, k !== "marketing"]));
  S.consentChoice = chosen;
  const labels = { kyc: "ui_c_kyc", registry: "ui_c_registry", updates: "ui_c_updates", partner: "ui_c_partner", marketing: "ui_c_marketing" };
  const body = h("div", { class: "pad stack" },
    h("div", { class: "h2" }, "🔒 " + t("ui_consent_title")),
    h("div", { class: "muted" }, t("ui_consent_intro")));
  const card = h("div", { class: "card" });
  Object.entries(S.notice.purposes).forEach(([k, m]) => {
    card.append(h("div", { class: "purpose" },
      h("div", { style: { flex: 1 } },
        h("div", { style: { fontWeight: 600 } }, t(labels[k])),
        h("div", { class: "faint" }, m.required ? t("ui_required") : t("ui_optional"), " · ", m.data.join(", ")),
        h("div", { class: "faint" }, "⏱ " + m.retention)),
      h("label", { class: "switch" }, h("input", { type: "checkbox", checked: chosen[k], disabled: m.required,
        onchange: (e) => { chosen[k] = e.target.checked; } }), h("span"))));
  });
  body.append(card, h("div", { class: "faint" }, `Notice ${S.notice.version} · shown in ${S.meta.languages[S.lang].name} · DPDP Act 2023. Withdraw any optional item anytime from 🔒 My data.`),
    h("div", { class: "excl", style: { background: "#e6f5ec" } }, "🗑 " + t("ui_retention")));
  scr.append(body, h("div", { class: "sticky-foot" }, h("button", { class: "btn", onclick: async () => {
    const r = await api("/api/consent", { body: { session: S.session, purposes: chosen } });
    if (r.ok) { S.consent = r.consent; go("kyc"); } else toast("Required: " + r.missing.join(", "), phone());
  } }, t("ui_agree"))));
}

/* ---------------- KYC ---------------- */
function kyc(scr) {
  const body = h("div", { class: "pad stack" }, h("div", { class: "h2" }, "🪪 " + t("ui_kyc_title")));
  if (S.kycLoading) {
    body.append(h("div", { class: "card stack" }, h("div", {}, t("ui_checking")), h("div", { class: "scan" }, h("i")),
      h("div", { class: "faint" }, "Quality check → straighten → read on our server (documents never leave India) → GST & Udyam registry → signatory rules")));
    scr.append(body); return;
  }
  if (!S.kyc) {
    const g = S.profile.gstin;
    body.append(h("div", { class: "muted" }, g ? "Fastest: fetch your verified GST and Udyam documents from Entity Locker. Nothing to photograph." : "Upload your 4 documents, or fetch them from Entity Locker if you typed your GSTIN."));
    if (g && S.consent && S.consent.purposes.registry) body.append(h("button", { class: "btn green", onclick: () => runKyc("locker") }, "⚡ " + t("ui_fetch_locker")));
    const file = h("input", { type: "file", accept: "image/*", multiple: true, class: "hide", onchange: (e) => runKyc("upload", e.target.files) });
    body.append(file, h("button", { class: "btn ghost", onclick: () => file.click() }, "📷 " + t("ui_upload") + " (GST, Udyam, bill, ID)"));
    body.append(h("div", { class: "card stack" }, h("div", { style: { fontWeight: 600 } }, "🧪 " + t("ui_use_sample")),
      h("div", { class: "faint" }, "The 12 specimen applicants from the case pack. Some have planted problems."),
      h("div", { class: "samples" }, Array.from({ length: 12 }, (_, i) => "K" + String(i + 1).padStart(2, "0")).map((k) =>
        h("button", { onclick: () => runKyc("sample", k) }, k)))));
    scr.append(body); return;
  }
  const r = S.kyc;
  const nFix = r.checks.filter((c) => ["action", "fail"].includes(c.status)).length;
  const vt = { APPROVED: t("ui_all_good"), ACTION_NEEDED: (S.lang === "en" && nFix > 1) ? `Almost there: ${nFix} quick fixes` : t("ui_fix_needed"), REVIEW: t("ui_review"), RESTRICTED: t("ui_restricted") }[r.verdict];
  body.append(h("div", { class: "verdict " + r.verdict }, h("div", { style: { fontSize: "18px", fontWeight: 700 } },
    { APPROVED: "✅ ", ACTION_NEEDED: "✍️ ", REVIEW: "⏳ ", RESTRICTED: "◐ " }[r.verdict] + vt),
    r.business ? h("div", { style: { opacity: .9, fontSize: "13px" } }, `${r.business.trade_name} · ${r.business.constitution}`) : null));
  if (r.fetched_from_registry && r.fetched_from_registry.length) body.append(h("div", { class: "tag green" }, "⚡ Fetched, not uploaded: " + r.fetched_from_registry.map((f) => f.type.replace("_", " ")).join(", ")));
  const card = h("div", { class: "card" });
  const issues = r.checks.filter((c) => c.status !== "pass" && c.status !== "info");
  [...issues, ...r.checks.filter((c) => c.status === "pass" || c.status === "info")].forEach((c) => card.append(
    h("div", { class: "check" }, h("div", { class: "dot " + c.status }, STATUS_ICON[c.status]),
      h("div", { style: { flex: 1 } }, h("div", { style: { fontWeight: 600, fontSize: "13.5px" } }, c.label),
        h("div", { class: "faint", style: { fontSize: "12.5px", color: c.status === "pass" ? "" : "#4a4f59" } }, c.status === "pass" || c.status === "info" ? c.detail : (c.owner_message || c.detail)),
        fixButton(c)))));
  body.append(card);
  if (r.restricted_bundle) body.append(h("div", { class: "excl", style: { background: "#f1ebfa" } }, h("b", { style: { color: "#6b3fb3" } }, "You can go live today with: "),
    r.restricted_bundle.map((l) => l.name).join(", "), ". GST-only products are added automatically when your GST is active again."));
  const canGo = r.verdict === "APPROVED" || r.verdict === "RESTRICTED" || (r.verdict === "ACTION_NEEDED" && S.kycResolved);
  body.append(h("button", { class: "btn ghost sm", onclick: () => { S.kyc = null; S.kycResolved = false; render(); } }, "↺ Try other documents"));
  scr.append(body, h("div", { class: "sticky-foot" }, r.verdict === "REVIEW"
    ? h("div", { class: "faint", style: { textAlign: "center" } }, "We'll WhatsApp you within 2 hours. Nothing else to do now.")
    : h("button", { class: "btn", disabled: !canGo, onclick: () => go("sign") }, t("ui_continue"))));
}

function fixButton(c) {
  if (c.status === "pass" || c.status === "info") return null;
  const label = { signatory_authority: "📲 Send e-sign authorisation link", signatory_contact: "📲 Send one-tap confirmation",
    bill_date: "📷 Upload a recent bill", quality_gst_certificate: "⚡ Fetch from Entity Locker instead", udyam_number: "Skip: Udyam is optional",
    bill_present: "📷 Upload bill", id_present: "🔐 Use Aadhaar e-KYC at signing" }[c.id];
  if (!label) return null;
  return h("button", { class: "chip", style: { marginTop: "6px" }, onclick: () => {
    c.status = "pass"; c.detail = "Resolved: " + label.replace(/^[^ ]+ /, "");
    S.kycResolved = !S.kyc.checks.some((x) => ["action", "fail"].includes(x.status));
    toast("Done ✓", phone()); render();
  } }, label);
}

async function runKyc(kind, arg) {
  S.kycLoading = true; render();
  try {
    if (kind === "sample") S.kyc = await api(`/api/kyc/sample/${arg}?session=${S.session}`, { method: "POST" });
    else if (kind === "locker") S.kyc = await api(`/api/kyc/locker?session=${S.session}`, { method: "POST" });
    else { const fd = new FormData(); fd.append("session", S.session); [...arg].forEach((f) => fd.append("files", f)); S.kyc = await api("/api/kyc/upload", { form: fd }); }
    if (S.kyc.business) S.profile.business_name = S.kyc.business.trade_name;
    const sig = S.kyc.documents && S.kyc.documents.signatory_id;
    S.signer = (sig && sig.fields && sig.fields.name) || S.profile.proprietor || "Owner";
  } catch (e) { toast(e.message, phone()); }
  S.kycLoading = false; S.kycResolved = false; render();
  window.dispatchEvent(new Event("owner-update"));
}

/* ---------------- sign & pay ---------------- */
function sign(scr) {
  const r = S.reco;
  const lines = S.kyc && S.kyc.restricted_bundle ? S.kyc.restricted_bundle : r.lines;
  const monthly = lines.reduce((a, l) => a + l.monthly, 0), setup = lines.reduce((a, l) => a + l.setup, 0);
  const sims = lines.filter((l) => ["P07", "P08"].includes(l.product_id)).reduce((a, l) => a + l.qty, 0);
  const body = h("div", { class: "pad stack" }, h("div", { class: "h2" }, "✍️ " + t("ui_sign_title")));
  body.append(h("div", { class: "card" },
    h("div", { class: "row between" }, h("div", {}, h("div", { class: "faint" }, "Signatory"), h("b", {}, S.signer || "Owner")),
      S.signed ? h("span", { class: "tag green" }, "Signed ✓") : null),
    h("div", { class: "faint", style: { marginTop: "6px" } }, "Customer Application Form + authorisation, pre-filled from your verified details. Nothing to write.")));
  if (!S.signed) {
    body.append(h("div", { class: "otp", id: "otp" }, [0, 1, 2, 3, 4, 5].map(() => h("span", {}, ""))));
    body.append(h("button", { class: "btn", onclick: doSign }, "🔐 " + t("ui_esign")),
      h("button", { class: "btn ghost", onclick: () => toast("Link sent on WhatsApp to the authorised signatory", phone()) }, "📲 " + t("ui_send_link")));
  } else {
    if (sims) body.append(h("div", { class: "card" }, h("b", {}, `📱 ${sims} SIM user${sims > 1 ? "s" : ""}`), h("div", { class: "faint" }, t("ui_sim_users"))));
    body.append(h("div", { class: "card" },
      h("div", { class: "row between" }, h("span", {}, "First month"), h("b", {}, inr(monthly))),
      h("div", { class: "row between" }, h("span", {}, t("ui_setup")), h("b", {}, inr(setup))),
      h("div", { class: "row between", style: { borderTop: "1px solid #e7e8ec", marginTop: "6px", paddingTop: "6px" } }, h("b", {}, "Pay now"), h("b", {}, inr(monthly + setup))),
      h("div", { class: "faint", style: { marginTop: "6px" } }, "🔁 " + t("ui_autopay"))));
    body.append(h("button", { class: "btn green", onclick: doPay }, "UPI · " + t("ui_pay", { n: (monthly + setup).toLocaleString("en-IN") })));
  }
  scr.append(body);
}

async function doSign() {
  const boxes = [...document.querySelectorAll("#otp span")];
  const otp = "482916";
  for (let i = 0; i < 6; i++) { await new Promise((res) => setTimeout(res, 120)); boxes[i].textContent = otp[i]; }
  await new Promise((res) => setTimeout(res, 300));
  try {
    S.order = await api("/api/order", { body: { session: S.session } });
    S.order = await api(`/api/order/${S.order.id}/esign`, { body: { signer: S.signer || "Owner", method: "aadhaar_otp" } });
    S.signed = true; render();
  } catch (e) { toast(e.message, phone()); }
  window.dispatchEvent(new Event("owner-update"));
}

async function doPay() {
  S.order = await api(`/api/order/${S.order.id}/pay`, { method: "POST" });
  go("track");
}

/* ---------------- tracker ---------------- */
function track(scr) {
  const o = S.order;
  if (!o) { go("chat"); return; }
  const pctDone = Math.round((o.eta.progress || 0) * 100);
  const body = h("div", { class: "pad stack" });
  body.append(h("div", { class: "row" },
    h("div", { class: "ring", style: { background: `conic-gradient(#138a4b ${pctDone * 3.6}deg, #e7e8ec 0)` } },
      h("div", { style: { width: "60px", height: "60px", borderRadius: "50%", background: "#fff", display: "grid", placeItems: "center" } }, pctDone + "%")),
    h("div", {}, h("div", { class: "h2" }, t("ui_track_title")), h("div", { class: "faint" }, `${o.id} · Day ${o.day}`),
      o.status === "live" ? h("span", { class: "tag green" }, "🎉 Everything live") :
        h("div", { class: "faint" }, o.eta.next ? `${t("ui_next_step")}: ${o.eta.next.label}` : ""))));
  body.append(h("div", { class: "excl", style: { background: "#e6f5ec" } }, "💬 " + t("ui_whatsapp_updates")));
  const tl = h("div", { class: "timeline" });
  const nextKey = o.eta.next && o.eta.next.key;
  o.milestones.forEach((m) => tl.append(h("div", { class: "tl " + (m.done ? "done" : m.key === nextKey ? "next" : "") },
    h("b", {}, m.label), h("small", {}, (m.done ? `Done · day ${m.done_at}` : `Expected day ${m.day}`) + ` · ${m.who}`))));
  body.append(h("div", { class: "card" }, tl));
  body.append(h("div", { class: "card" }, h("div", { class: "faint" }, "Your local partner"), h("b", {}, o.partner.name), h("div", { class: "faint" }, o.partner.role)));
  const wa = h("div", { class: "wa" });
  o.notifications.slice().reverse().forEach((n) => wa.append(h("div", { class: "msg" }, n.text, h("span", { class: "meta" }, `day ${n.day} · WhatsApp`))));
  body.append(h("div", { style: { fontWeight: 600 } }, "Messages we sent you"), wa);
  body.append(h("div", { class: "row" },
    h("button", { class: "btn ghost sm", onclick: async () => { S.order = await api(`/api/order/${o.id}/advance?days=1`, { method: "POST" }); render(); window.dispatchEvent(new Event("owner-update")); } }, "⏩ Next day (demo)"),
    h("button", { class: "btn ghost sm", onclick: () => go("mydata") }, "🔒 " + t("ui_my_data"))));
  scr.append(body);
}

/* ---------------- my data ---------------- */
async function mydata(scr) {
  const d = await api(`/api/mydata/${S.session}`);
  const body = h("div", { class: "pad stack" }, h("div", { class: "h2" }, "🔒 " + t("ui_my_data")),
    h("div", { class: "faint" }, "Everything we hold about you, why, and for how long (DPDP Act 2023)."));
  const p = d.profile || {};
  body.append(h("div", { class: "card" }, h("b", {}, "Business"), h("div", { class: "faint" },
    [p.business_name, p.business_type, p.city, p.gstin ? "GSTIN " + p.gstin.slice(0, 2) + "••••••••••" + p.gstin.slice(-3) : null].filter(Boolean).join(" · "))));
  if (d.consent) {
    const cc = h("div", { class: "card" }, h("b", {}, `Consent ${d.consent.id}`), h("div", { class: "faint" }, `Receipt ${d.consent.receipt_hash} · notice ${d.consent.notice_version}`));
    Object.entries(d.consent.purposes).forEach(([k, v]) => cc.append(h("div", { class: "row between", style: { padding: "4px 0" } },
      h("span", {}, k), v && !["kyc", "partner"].includes(k) ? h("button", { class: "chip", onclick: async () => { await api(`/api/consent/${d.consent.id}/withdraw/${k}`, { method: "POST" }); toast("Withdrawn", phone()); render(); } }, t("ui_withdraw")) : h("span", { class: "tag " + (v ? "green" : "") }, v ? "on" : "off"))));
    body.append(cc);
  }
  if (d.kyc) body.append(h("div", { class: "card" }, h("b", {}, "KYC: " + d.kyc.verdict), h("div", { class: "faint" }, "Document images stored: " + (d.kyc.images_stored ? "yes" : "no, deleted after reading"))));
  body.append(h("div", { class: "card" }, h("b", {}, "How long we keep things"), ...Object.entries(d.retention).map(([k, v]) => h("div", { class: "faint" }, `${k}: ${v}`))));
  body.append(h("div", { class: "row" },
    h("button", { class: "btn ghost sm", onclick: () => { const a = h("a", { href: URL.createObjectURL(new Blob([JSON.stringify(d, null, 2)], { type: "application/json" })), download: "my-accel-data.json" }); a.click(); } }, "⬇ " + t("ui_download")),
    h("button", { class: "btn ghost sm", onclick: async () => { const r = await api(`/api/mydata/${S.session}/erase`, { method: "POST" }); toast("Erased: " + r.erased.join(", ") + (r.kept.length ? ". Kept (law): KYC record" : ""), phone()); } }, "🗑 " + t("ui_erase")),
    h("button", { class: "btn ghost sm", onclick: () => go(S.order ? "track" : "chat") }, t("ui_back"))));
  scr.append(body);
}

boot();
