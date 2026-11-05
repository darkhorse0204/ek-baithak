/* Tiny helpers: element builder, API client, formatting, i18n. No framework, no CDN: works offline. */
const $ = (sel, root = document) => root.querySelector(sel);

function h(tag, attrs, ...kids) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v === null || v === undefined || v === false) continue;
    if (k === "class") el.className = v;
    else if (k === "style" && typeof v === "object") Object.assign(el.style, v);
    else if (k.startsWith("on")) el.addEventListener(k.slice(2).toLowerCase(), v);
    else if (k === "html") el.innerHTML = v;
    else if (v === true) el.setAttribute(k, "");
    else el.setAttribute(k, v);
  }
  for (const kid of kids.flat(Infinity)) {
    if (kid === null || kid === undefined || kid === false) continue;
    el.append(kid instanceof Node ? kid : document.createTextNode(String(kid)));
  }
  return el;
}

async function api(path, opts = {}) {
  const init = { method: opts.method || (opts.body || opts.form ? "POST" : "GET"), headers: {} };
  if (opts.body) { init.headers["Content-Type"] = "application/json"; init.body = JSON.stringify(opts.body); }
  if (opts.form) init.body = opts.form;
  const r = await fetch(path, init);
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw Object.assign(new Error(data.detail || r.statusText), { status: r.status, data });
  return data;
}

const inr = (n) => "₹" + Math.round(n || 0).toLocaleString("en-IN");
const pct = (x, d = 1) => (x === null || x === undefined) ? "–" : (x * 100).toFixed(d) + "%";

const I18N = { table: {}, lang: "en" };
function t(key, vars = {}) {
  const s = (I18N.table[I18N.lang] || {})[key] || (I18N.table.en || {})[key] || key;
  return s.replace(/\{(\w+)\}/g, (_, k) => (vars[k] ?? `{${k}}`));
}

const ICONS = { P01: "🌐", P02: "🌐", P03: "🌐", P04: "📡", P05: "🔗", P06: "🔗", P07: "📱", P08: "📱", P09: "🔁", P10: "🧭",
  P11: "📍", P12: "☎️", P13: "📞", P14: "✉️", P15: "💬", P16: "📧", P17: "☁️", P18: "🌍", P19: "🧾", P20: "🛡️", P21: "🔥",
  P22: "📶", P23: "📷", P24: "⚙️", P25: "🚚" };

function toast(msg, root) {
  const el = h("div", { class: "toast" }, msg);
  (root || document.body).append(el);
  setTimeout(() => el.remove(), 2600);
}

function scoreColor(s) {
  if (s >= 0.6) return { background: "#e6f5ec", color: "#138a4b" };
  if (s >= 0.35) return { background: "#fff4e0", color: "#b86e00" };
  return { background: "#f1f2f4", color: "#4a4f59" };
}

const STATUS_TAG = { APPROVED: "green", ACTION_NEEDED: "amber", REVIEW: "red", RESTRICTED: "purple" };
const STATUS_ICON = { pass: "✓", fail: "!", action: "!", review: "⚑", restricted: "◐", info: "i" };
