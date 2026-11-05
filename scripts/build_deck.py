"""Build the 10-slide business case on the official SYNC template. Numbers come from deck/data.json."""
import copy
import json
import os

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Emu, Inches, Pt

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TPL = os.path.join(ROOT, "..", "6ad9d4887d445_airtel_sync", "Submission Template_Sync.pptx")
OUT = os.path.join(ROOT, "deck", "Ek_Baithak_Business_Case.pptx")
D = json.load(open(os.path.join(ROOT, "deck", "data.json"), encoding="utf-8"))
SH = os.path.join(ROOT, "deck", "shots")
CH = os.path.join(ROOT, "deck", "charts")

RED, RED_D, RED_L = RGBColor(0xE1, 0x12, 0x1B), RGBColor(0xB1, 0x0C, 0x13), RGBColor(0xFD, 0xEC, 0xEC)
INK, INK2, MUTED = RGBColor(0x16, 0x18, 0x1D), RGBColor(0x4A, 0x4F, 0x59), RGBColor(0x8A, 0x90, 0x9C)
LIGHT, LINE, WHITE = RGBColor(0xF4, 0xF5, 0xF7), RGBColor(0xE2, 0xE4, 0xE8), RGBColor(0xFF, 0xFF, 0xFF)
GREEN, GREEN_L, AMBER, AMBER_L = RGBColor(0x13, 0x8A, 0x4B), RGBColor(0xE6, 0xF5, 0xEC), RGBColor(0xB8, 0x6E, 0x00), RGBColor(0xFF, 0xF4, 0xE0)
PURPLE, PURPLE_L, BLUE = RGBColor(0x6B, 0x3F, 0xB3), RGBColor(0xF1, 0xEB, 0xFA), RGBColor(0x2F, 0x6B, 0xC2)
FONT = "Calibri"

prs = Presentation(TPL)
cover, base = prs.slides[0], prs.slides[1]
bg_blob = base.shapes[0].image.blob
bg_path = os.path.join(ROOT, "deck", "_bg.jpg")
open(bg_path, "wb").write(bg_blob)
layout = base.slide_layout


def inr(n):
    s = f"{int(round(n)):,}"
    # Indian grouping
    n = int(round(n))
    s = str(n)
    if len(s) > 3:
        head, tail = s[:-3], s[-3:]
        parts = []
        while len(head) > 2:
            parts.insert(0, head[-2:])
            head = head[:-2]
        if head:
            parts.insert(0, head)
        s = ",".join(parts) + "," + tail
    return "₹" + s


def new_slide():
    s = prs.slides.add_slide(layout)
    for ph in list(s.placeholders):
        ph._element.getparent().remove(ph._element)
    pic = s.shapes.add_picture(bg_path, 0, 0, prs.slide_width, prs.slide_height)
    s.shapes._spTree.remove(pic._element)
    s.shapes._spTree.insert(2, pic._element)
    return s


def text(slide, x, y, w, h, content, size=12, color=INK, bold=False, align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP, font=FONT, spacing=1.0):
    """content: str or list of paragraphs; a paragraph is str or list of (text, {bold,color,size}) runs. '**x**' marks bold."""
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = Inches(0.02)
    tf.margin_top = tf.margin_bottom = Inches(0.01)
    tf.vertical_anchor = anchor
    paras = content if isinstance(content, list) else [content]
    for i, para in enumerate(paras):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        p.line_spacing = spacing
        runs = para if isinstance(para, list) else _md(para)
        for rt, st in runs:
            r = p.add_run()
            r.text = rt
            f = r.font
            f.name = font
            f.size = Pt(st.get("size", size))
            f.bold = st.get("bold", bold)
            f.color.rgb = st.get("color", color)
    return tb


def _md(s):
    parts = s.split("**")
    return [(t, {"bold": True} if i % 2 else {}) for i, t in enumerate(parts) if t]


def box(slide, x, y, w, h, fill=LIGHT, line=None, radius=True):
    shp = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE if radius else MSO_SHAPE.RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
    if radius:
        shp.adjustments[0] = 0.08
    shp.fill.solid()
    shp.fill.fore_color.rgb = fill
    if line:
        shp.line.color.rgb = line
        shp.line.width = Pt(1)
    else:
        shp.line.fill.background()
    shp.shadow.inherit = False
    return shp


def title(slide, t, kicker=None):
    text(slide, 0.45, 0.62, 9.1, 0.5, t, size=22, bold=True)
    if kicker:
        text(slide, 0.45, 1.08, 9.1, 0.32, kicker, size=11.5, color=INK2)


def tile(slide, x, y, w, h, big, label, accent=RED, fill=WHITE, big_size=22):
    box(slide, x, y, w, h, fill=fill, line=LINE)
    bar = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(x), Inches(y + 0.12), Inches(0.05), Inches(h - 0.24))
    bar.fill.solid(); bar.fill.fore_color.rgb = accent; bar.line.fill.background()
    text(slide, x + 0.15, y + 0.06, w - 0.22, 0.45, big, size=big_size, bold=True, color=INK)
    text(slide, x + 0.15, y + 0.06 + big_size / 52, w - 0.22, h - 0.5, label, size=9.5, color=INK2)


def table(slide, x, y, w, rows, widths, size=9, header_fill=INK, row_h=0.28, header_size=None, fills=None):
    shp = slide.shapes.add_table(len(rows), len(rows[0]), Inches(x), Inches(y), Inches(w), Inches(row_h * len(rows)))
    tbl = shp.table
    tbl.first_row = True
    for i, wd in enumerate(widths):
        tbl.columns[i].width = Inches(wd)
    for r, row in enumerate(rows):
        tbl.rows[r].height = Inches(row_h)
        for c, val in enumerate(row):
            cell = tbl.cell(r, c)
            cell.margin_left = cell.margin_right = Inches(0.06)
            cell.margin_top = cell.margin_bottom = Inches(0.03)
            cell.vertical_anchor = MSO_ANCHOR.MIDDLE
            tf = cell.text_frame
            tf.word_wrap = True
            runs = val if isinstance(val, list) else _md(str(val))
            p = tf.paragraphs[0]
            for rt, st in runs:
                run = p.add_run()
                run.text = rt
                run.font.name = FONT
                run.font.size = Pt(st.get("size", header_size or size + 0.5 if r == 0 else size))
                run.font.bold = True if r == 0 else st.get("bold", False)
                run.font.color.rgb = WHITE if r == 0 else st.get("color", INK)
            cell.fill.solid()
            cell.fill.fore_color.rgb = header_fill if r == 0 else ((fills or {}).get((r, c)) or (WHITE if r % 2 else LIGHT))
    return tbl


def pic(slide, path, x, y, w=None, h=None, border=False):
    kw = {}
    if w:
        kw["width"] = Inches(w)
    if h:
        kw["height"] = Inches(h)
    p = slide.shapes.add_picture(path, Inches(x), Inches(y), **kw)
    if border:
        p.line.color.rgb = LINE
        p.line.width = Pt(0.75)
    return p


def notes(slide, s):
    slide.notes_slide.notes_text_frame.text = s


def footer(slide, s, w=7.6):
    text(slide, 0.45, 5.13, w, 0.3, s, size=7.5, color=MUTED)


# ---------------------------------------------------------------- 1. cover
for shp in list(cover.placeholders):
    shp._element.getparent().remove(shp._element)
panel = box(cover, 0.42, 3.02, 4.75, 1.95, fill=RGBColor(0x14, 0x08, 0x0A), radius=True)
panel.fill.fore_color.brightness = 0
text(cover, 0.6, 3.1, 4.5, 0.6, "Ek Baithak", size=34, bold=True, color=WHITE)
text(cover, 0.6, 3.68, 4.5, 0.4, "Your business, live in one sitting", size=16, color=RGBColor(0xFF, 0xC9, 0xCB))
text(cover, 0.6, 4.1, 4.5, 0.75, ["Track A · Project Udyam Digital",
                                   "An AI helper that talks to shop owners in 10 Indian languages and gets them the right internet, mobile and digital tools: chosen, priced, verified and switched on in one sitting."],
     size=10.5, color=RGBColor(0xE6, 0xE7, 0xEA))
text(cover, 0.6, 4.98, 4.6, 0.3, "Team: <your name>  ·  Demo video and code: links in the submission", size=9, color=RGBColor(0xC9, 0xCC, 0xD3))
notes(cover, "Opening line: 7 of every 100 small businesses that talk to Accel become customers. We built a journey that gets that to about 16, at a third of the cost, without asking the owner to meet anyone. Replace <your name> with your team name.")

# ---------------------------------------------------------------- 2. problem
s = base
for shp in list(s.placeholders):
    shp._element.getparent().remove(shp._element)
title(s, "93 of 100 interested businesses never become customers",
      "Last quarter's 5,000 leads: the losses are mostly friction Accel controls, not lack of demand")
pic(s, os.path.join(CH, "funnel_today.png"), 0.4, 1.5, w=4.6)
text(s, 0.5, 4.3, 4.4, 0.5, [[("Biggest drop: needs → quote (44%). ", {"bold": True}), ("Quotes take 3–5 days and arrive as product codes.", {})]], size=10, color=INK2)
tw, tx = 1.38, 5.15
tile(s, tx, 1.5, tw, 0.95, "17.6", "days from lead to activation")
tile(s, tx + tw + 0.1, 1.5, tw, 0.95, "3 calls", "per customer chasing status")
tile(s, tx + 2 * (tw + 0.1), 1.5, tw, 0.95, inr(D["cac"]), "cost per activated SMB")
g = D["drop_groups"]
box(s, tx, 2.58, 3 * tw + 0.2, 1.22, fill=RED_L)
text(s, tx + 0.15, 2.64, 3 * tw - 0.1, 0.3, [[(f"{D['friction_total']:,} leads", {"bold": True, "color": RED_D}), (f" were lost to friction a digital journey removes:", {})]], size=11)
text(s, tx + 0.15, 2.95, 3 * tw - 0.1, 0.85, [
    f"**{g['No time for a visit']}** no time for a sales visit / visit never scheduled",
    f"**{g['Quote slow or confusing']}** quote too slow or too complex   ·   **{g['Paperwork & documents']}** paperwork, documents, signatory",
    f"**{g['Install, feasibility, payment']}** install delays, no fibre at site, first payment failed"], size=9.5, color=INK)
pic(s, os.path.join(CH, "churn_calls.png"), tx - 0.05, 3.86, w=2.25)
text(s, tx + 2.3, 3.92, 2.15, 1.15, [[("Status-chasing predicts churn. ", {"bold": True}), ("Customers who called 5 times churned at 28% vs 6% for 1 call.", {})],
                                     [("15% of bundles sold ", {"bold": True}), (f"({D['audit']['bundles_affected']} of {D['audit']['activated']}) broke the product rules, e.g. sold in a city where it isn't offered.", {})]], size=9.5, color=INK2)
footer(s, "Source: smb_leads.csv (Apr–Jun 2026, synthetic), our analysis. Bundle audit re-checks every sold bundle against catalogue rules and the GST registry.", w=4.55)
notes(s, "Three facts. 1) The funnel leaks most between needs and quote. 2) 1,652 drops are pure friction: no visit, slow/complex quote, paperwork, installation. 3) Status calls predict churn, and humans mis-sell: 56 of 368 bundles broke a catalogue rule (tier-1-only products in tier-2 cities, GST-only products with cancelled GSTINs).")

# ---------------------------------------------------------------- 3. segments & bundles
s = new_slide()
title(s, "Who first: go where digital pays back fastest", "Ranked by how many buy, how many stay, and how fast the sales cost is earned back (last quarter's data)")
seg = {x["segment"]: x for x in D["by_segment"]}
B = D["bundles"]
rows = [["Priority", "Segment (share of base)", "Today: buy · leave in 6 mo · earn back", "Bundle (12-month price unless noted)", "How we sell"]]
P, M, MU, MF = seg["Professional offices"], seg["Small multi-site businesses"], seg["Micro retail & services"], seg["Small manufacturers"]
rows.append(["**1 · Launch**", "Professional offices: clinics, CA firms, coaching (25%)", f"{P['activation_rate']:.0%} · {P['churn_6m']:.0%} · {P['payback_months']} mo",
             f"**Clinic & Office Pro** {inr(B['prof']['monthly'])}/mo: fibre 300, 2 lines, email ×9, backup, security, SMS, guest Wi-Fi", "Fully digital; partner installs"])
rows.append(["**1 · Launch**", "Small multi-site: chains, 3–10 outlets (15%)", f"{M['activation_rate']:.0%} · {M['churn_6m']:.0%} · {M['payback_months']} mo",
             f"**Multi-site One** {inr(B['multi']['monthly'])}/mo (5 sites, 24 mo): fibre + backup internet + one control screen for all branches; billing tablet and CCTV per site", "Digital quote + partner site survey"])
rows.append(["**2 · Scale**", "Micro retail & services: kirana, salon, pharmacy (55%)", f"{MU['activation_rate']:.0%} · {MU['churn_6m']:.0%} · {MU['payback_months']} mo",
             f"**Dukaan Starter** {inr(B['micro']['monthly'])}/mo (₹{round(B['micro']['monthly']/30)}/day): fibre 100 + 2 SIMs; add POS, CCTV, WhatsApp", "Only cheap channels: WhatsApp, referral, partner kiosk"])
rows.append(["**3 · Qualify**", "Small manufacturers (5%)", f"{MF['activation_rate']:.0%} · {MF['churn_6m']:.0%} · {MF['payback_months']} mo",
             f"**Factory Connect** {inr(B['mfg']['monthly'])}/mo (24 mo): leased line, firewall, machine IoT ×10, email, security", "Advisor pre-qualifies; field force closes"])
table(s, 0.45, 1.5, 9.1, rows, [0.95, 2.05, 1.75, 3.0, 1.35], size=8.6, row_h=0.5)
box(s, 0.45, 4.15, 4.45, 0.9, fill=GREEN_L)
text(s, 0.6, 4.2, 4.2, 0.85, [[("Why this order: ", {"bold": True}), ("professional offices buy instant products (email, security, backup) and need no survey; multi-site earns back its sales cost in under a month. Small shops are many, but 23% leave within 6 months: reach it only through cheap channels (WhatsApp, referrals, partners).", {})]], size=9.5)
box(s, 5.1, 4.15, 4.45, 0.9, fill=LIGHT)
src = sorted(D["by_source"], key=lambda r: r["cac_per_activation"])
ref = next(x for x in src if x["source"] == "Referral"); fs = next(x for x in src if x["source"] == "Field sales")
text(s, 5.25, 4.2, 4.2, 0.85, [[("Channels: ", {"bold": True}), (f"{ref['activation_rate']:.1%} of referred leads buy, at {inr(ref['cac_per_activation'])} each; for field sales it's {fs['activation_rate']:.1%} at {inr(fs['cac_per_activation'])}. Every new customer gets a one-tap referral link; the sales team moves to chains and factories.", {})]], size=9.5)
footer(s, "Prices come from our app: 12-month plan = middle of the catalogue price range, 24-month plan = lowest price. GST extra. 'Leave in 6 mo' = customers who left within 6 months.")
notes(s, "Answer to key question 1. Lead with professional offices (fast, digital-only products) and multi-site (highest value). Serve micro only through low-cost channels because churn is 23% and payback 8 months. Manufacturers need surveys, so the advisor qualifies and the field team closes.")

# ---------------------------------------------------------------- 4. journey
s = new_slide()
title(s, "The journey: discover, buy and go live in one sitting", "On the owner's phone, in their language. Tap, type or send a voice note. No visit, no PDF, no product codes.")
shots = [("hi_02_chat.png", "1 · Advisor (2 min)", "Asks 3–4 questions. A GSTIN pre-fills the rest from the registry. Hindi shown; 10 languages."),
         ("en_04_quote.png", "2 · One clear price (1 min)", "₹/month and ₹/day, 12 or 24 months, add-ons on/off, and why each item is there."),
         ("en_09_kyc_action.png", "3 · Smart KYC (2 min)", "Fetch documents from Entity Locker (government wallet) or take 4 photos. Problems come back as a one-tap fix."),
         ("en_15_tracker_live.png", "4 · Live + tracker", "eSIM, email, backup live on day 0; fibre in ~5 days. Every step pushed on WhatsApp.")]
for i, (f, h1, cap) in enumerate(shots):
    x = 0.45 + i * 2.3
    pic(s, os.path.join(SH, f), x + 0.32, 1.45, h=2.85)
    text(s, x, 4.36, 2.15, 0.25, h1, size=10.5, bold=True, color=RED_D)
    text(s, x, 4.6, 2.15, 0.5, cap, size=8.6, color=INK2)
footer(s, "Screens from the working prototype. The same helper also works on WhatsApp, with voice notes, and on a partner's phone for owners who want help.")
notes(s, "Walk the four screens. Emphasise: the owner never sees a product code; GSTIN pre-fills the profile; KYC failures come back as fixes; instant products go live before the owner puts the phone down.")

# ---------------------------------------------------------------- 5. how it works
s = new_slide()
title(s, "How it works: the AI talks, the rules decide", "AI understands and explains. Tested rules decide what is sold, at what price, and if documents pass.")
steps5 = [("1", "Listen", "Owner types, taps or sends a voice note in 10 languages. AI picks out the facts.", "AI"),
          ("2", "Look up", "GSTIN fills in name, address and business type from government records. No forms.", "Rules"),
          ("3", "Decide", "Rules pick only the products this business is allowed to buy, and price them.", "Rules"),
          ("4", "Explain", "AI explains each item in simple words, with the price per day.", "AI"),
          ("5", "Verify & switch on", "Documents read on our own server and checked by rules. e-Sign, UPI, live tracker.", "Rules")]
bw, gap, y0 = 1.66, 0.2, 1.62
for i, (n, h1, body, who) in enumerate(steps5):
    x = 0.45 + i * (bw + gap)
    box(s, x, y0, bw, 1.75, fill=WHITE, line=LINE)
    c = s.shapes.add_shape(MSO_SHAPE.OVAL, Inches(x + 0.12), Inches(y0 + 0.12), Inches(0.38), Inches(0.38))
    c.fill.solid(); c.fill.fore_color.rgb = RED; c.line.fill.background()
    c.text_frame.text = n
    for para in c.text_frame.paragraphs:
        para.alignment = PP_ALIGN.CENTER
        for r in para.runs:
            r.font.size = Pt(12); r.font.bold = True; r.font.color.rgb = WHITE; r.font.name = FONT
    box(s, x + bw - 0.68, y0 + 0.16, 0.56, 0.28, fill=RED_L if who == "AI" else GREEN_L)
    text(s, x + bw - 0.68, y0 + 0.18, 0.56, 0.26, who, size=8.5, bold=True, color=RED_D if who == "AI" else GREEN, align=PP_ALIGN.CENTER)
    text(s, x + 0.12, y0 + 0.58, bw - 0.22, 0.3, h1, size=12, bold=True)
    text(s, x + 0.12, y0 + 0.9, bw - 0.22, 0.85, body, size=9.2, color=INK2)
    if i < 4:
        a = s.shapes.add_shape(MSO_SHAPE.RIGHT_ARROW, Inches(x + bw + 0.02), Inches(y0 + 0.75), Inches(0.16), Inches(0.24))
        a.fill.solid(); a.fill.fore_color.rgb = MUTED; a.line.fill.background()
panels = [("Never stuck", "If one AI model is busy, it tries 3 more, then simple built-in rules. The app keeps working even with no AI.", GREEN_L),
          ("Can't be talked into mistakes", "Ask for 1 Gbps in a small city or a leased line for a 4-person shop: the rules say no and offer the right option.", RED_L),
          ("Tested", "15 of 15 test chats right (including Hindi and Tamil), 12 of 12 KYC files right, 29 automatic tests.", LIGHT)]
for i, (h1, body, f) in enumerate(panels):
    x = 0.45 + i * 3.08
    box(s, x, 3.62, 2.94, 1.18, fill=f)
    text(s, x + 0.14, 3.7, 2.7, 1.1, [[(h1, {"bold": True, "size": 11})], [(body, {"size": 9.3, "color": INK2})]])
footer(s, "Full technical diagram: Solution_Architecture.png. Built with Python (FastAPI), a phone web app, local OCR (RapidOCR), scikit-learn and the Gemini API.")
notes(s, "Simple message: the AI is the voice, the rules are the brain. That is why the advisor gets every judge-style trap right, and why it still works when the free AI is busy.")

# ---------------------------------------------------------------- 6. KYC
s = new_slide()
title(s, "Smart KYC: government records first, photos last", "All 12 sample applicants get the right result. Nobody is just rejected: they get a fix, a smaller plan, or a human check.")
V = {"APPROVED": ("Approved", GREEN_L), "ACTION_NEEDED": ("Fix in app", AMBER_L), "REVIEW": ("Human check", RED_L), "RESTRICTED": ("Non-GST plan", PURPLE_L)}
short = {"K01": "GSTIN cancelled in registry; Udyam number blank", "K02": "Scan tilted 7°: straightened automatically", "K03": "Clean",
         "K04": "GST certificate too blurry to read", "K05": "No Udyam upload: fetched from registry; LLP signatory needs partner authorisation",
         "K06": "GSTIN altered (8 vs registry 5): check digit fails", "K07": "Legal name differs from GST registry", "K08": "Clean", "K09": "Clean",
         "K10": "Signatory is not the person who applied", "K11": "Electricity bill 257 days old (limit 90)", "K12": "Clean"}
rows = [["", "Business", "What we caught", "Outcome"]]
fills = {}
for i, k in enumerate(D["kyc"], start=1):
    lab_, col = V[k["verdict"]]
    rows.append([k["id"], (k["business"] or "")[:30], short[k["id"]], lab_])
    fills[(i, 3)] = col
table(s, 0.45, 1.45, 5.6, rows, [0.42, 1.55, 2.6, 1.03], size=8, row_h=0.27, fills=fills)
x = 6.25
steps = [("1. Is the photo clear?", "Measures blur and tilt. Straightens tilted photos and removes watermarks automatically."),
         ("2. Read it on our own server", "Text reading (OCR) runs on our server. Documents are not sent to an AI to read."),
         ("3. Check with rules", "GST number check digit, GST and Udyam records, bill under 90 days old, right person signing."),
         ("4. Second opinion only if needed", "We tested Gemini on the blurred K04: it misread the GST number and said the photo was clear. So one reader is never enough.")]
y = 1.45
for h1, body in steps:
    box(s, x, y, 3.3, 0.7, fill=LIGHT)
    text(s, x + 0.12, y + 0.05, 3.1, 0.65, [[(h1, {"bold": True, "size": 10, "color": INK})], [(body, {"size": 8.5, "color": INK2})]])
    y += 0.78
box(s, x, y + 0.02, 3.3, 0.48, fill=GREEN_L)
text(s, x + 0.12, y + 0.06, 3.1, 0.45, "With Entity Locker (government document wallet): GST and Udyam come straight from the government; the owner adds 1 bill and signs with an Aadhaar OTP.", size=8.5)
footer(s, "Results from the prototype's KYC lab. 'Today' for date checks = 15 Jul 2026, as the case says. Signing rules follow telecom (DoT) KYC: owner, partner or director, or a signed authorisation.")
notes(s, "Answer to key question 3. Registry-first means most owners never photograph a GST or Udyam certificate. Our verdicts are four-way: approved, fix in app, non-GST bundle (K01 can still go live today with products that don't need GST), or compliance review for possible tampering (K06, K07). Mention the Gemini misread: it's why the code, not the model, decides.")

# ---------------------------------------------------------------- 7. partners
s = new_slide()
title(s, "Sales team and partners: the app does the routine work", "Partners earn on every app sale in their area, so the app helps them instead of competing with them")
roles = [("The app", "Discovery, quote, KYC, e-sign, payment, tracking for single-site offices and shops. Instant products live in the same sitting.", RED),
         ("Channel partners", f"Paid an install & assist fee (₹1,500) on every digital sale in their territory, so the app never takes their income. Get handoffs with the whole chat; do installs and assisted sign-ups.", BLUE),
         ("Field force", "Moves to chains and factories, where a site visit is really needed: surveys, leased lines, multi-branch networks.", INK2),
         ("Customers", "Get a one-tap referral link after going live. Referred leads buy twice as often, at 1/6 of the cost of a sales visit.", GREEN)]
y = 1.45
for h1, body, colr in roles:
    box(s, 0.45, y, 4.4, 0.8, fill=WHITE, line=LINE)
    b = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.45), Inches(y + 0.1), Inches(0.06), Inches(0.6)); b.fill.solid(); b.fill.fore_color.rgb = colr; b.line.fill.background()
    text(s, 0.62, y + 0.06, 4.15, 0.75, [[(h1, {"bold": True, "size": 10.5})], [(body, {"size": 8.8, "color": INK2})]])
    y += 0.88
r = D["rescue"]; m = D["model"]
tile(s, 5.05, 1.45, 2.2, 1.0, f"{r['total']:,}", "dropped leads last quarter had a reason we can now fix", accent=AMBER)
tile(s, 7.35, 1.45, 2.2, 1.0, f"~{r['expected_recovered']}", "expected to come back with the right next action", accent=GREEN)
tile(s, 5.05, 2.55, 2.2, 1.0, "2×", "better at picking who will buy than calling at random", accent=BLUE)
tile(s, 7.35, 2.55, 2.2, 1.0, f"{m['top20']:.0%}", "of all buyers are in the top 20% of leads our score picks", accent=BLUE)
pic(s, os.path.join(SH, "console_2_rescue_crop.png"), 5.05, 3.66, h=1.38, border=True)
footer(s, "Rescue list: each of the 20 reasons people dropped out has a next step and an owner (app or partner). Lead score: model trained on last quarter's 5,000 leads (AUC 0.69).")
notes(s, "Answer to key question 4. The conflict is about money, so we fix the money: partners earn on every digital sale in their area. The control room shows them stalled chats and the rescue queue, so their time goes to leads the app couldn't close.")

# ---------------------------------------------------------------- 8. business case
s = new_slide()
sim = D["sim"]
title(s, f"Same leads: about 2× the customers at about a third of the cost", "We replayed last quarter's 5,000 leads, winning back part of the people lost to friction (every assumption is a slider in the app)")
pic(s, os.path.join(CH, "funnel_projected.png"), 0.4, 1.45, w=5.15)
tiles = [(f"{sim['act_base']:.0%}", f"of leads become customers (today 7.4%; careful case {sim['act_cons']:.0%})", RED),
         (inr(sim['cac_base']), f"sales cost per new customer (today {inr(D['cac'])}; careful case {inr(sim['cac_cons'])})", RED),
         (f"+₹{D['arr_extra_base_cr']} Cr", f"extra revenue a year from the same 5,000 leads (careful case +₹{D['arr_extra_cons_cr']} Cr)", GREEN),
         ("Day 0 / ~6 days", "to go live: digital products / fibre (today 17.6 days)", GREEN)]
for i, (big, lab_, colr) in enumerate(tiles):
    xx = 5.7 + (i % 2) * 1.95
    yy = 1.45 + (i // 2) * 1.05
    tile(s, xx, yy, 1.85, 0.95, big, lab_, accent=colr, big_size=18)
box(s, 5.7, 3.6, 3.85, 1.45, fill=LIGHT)
text(s, 5.82, 3.65, 3.65, 1.4, [[("How we got these numbers", {"bold": True, "size": 10})],
                                  "We win back 30–45% of people lost to visits, slow quotes and paperwork; 10% of those lost on price; none of the 'not interested'. The careful case halves these.",
                                  "Revenue uses the typical bundle (₹6,900/month) and assumes 85% of customers stay. Cost: 60% of leads use the app at ₹150 each plus a ₹1,500 partner fee per sale; the rest cost what they cost today."], size=8.6, color=INK2)
footer(s, "All figures come from the app's simulator, using smb_leads.csv (synthetic data, Apr–Jun 2026).")
notes(s, "The business case in one chart: same marketing spend, same leads. Base case doubles activations; even the conservative case adds 50%. Cost per activation falls because the digital path costs about ₹150 a lead plus a partner fee, against ₹1,100 average spend per lead today.")

# ---------------------------------------------------------------- 9. metrics
s = new_slide()
title(s, "How we measure success: five numbers with targets", "Each number is counted automatically by the app, so nobody has to fill in a report")
rows = [["What we measure", "Today", "In 6 months", "In 12 months", "Why it matters"],
        ["**Leads who become customers**", "7.4%", "11%", "15%", "The whole journey in one number"],
        ["**Days from first chat to working service**", "17.6 days", "Same day (digital); fibre ≤ 7 days", "9 in 10 fibre installs ≤ 7 days", "Slow setup makes people give up"],
        ["**Sales cost per new customer**", inr(D["cac"]), "≤ ₹8,000", "≤ ₹5,000", "All sales, partner and app costs ÷ new customers"],
        ["**'Where is my order?' calls per customer**", "3.0", "≤ 1.0", "≤ 0.3", "More calls → more customers leave (6% → 28%)"],
        ["**Customers who leave within 6 months**", f"{D['churn']:.0%}", "≤ 13%", "≤ 10%", "Small shops tracked separately (23% today)"]]
table(s, 0.45, 1.45, 9.1, rows, [2.55, 0.95, 1.75, 1.6, 2.25], size=9.3, row_h=0.42)
gl = [("Zero", "plans that break product rules (15% today)"), ("≥ 85%", "KYC passed first time, no human"), ("≥ 8", "customer rating, NPS (6.9 today)"), ("< 2 h", "for a human document check")]
for i, (big, lab_) in enumerate(gl):
    tile(s, 0.45 + i * 2.3, 4.1, 2.2, 0.85, big, "Guardrail: " + lab_, accent=GREEN, big_size=17)
footer(s, "Targets sit between the careful and base cases of our simulator. Guardrails make sure we don't grow by mis-selling or weak checks.")
notes(s, "Answer to key question 5. Five metrics plus four guardrails. Status calls is our signature metric: the data shows it predicts churn, and the tracker is designed to drive it to near zero.")

# ---------------------------------------------------------------- 10. rollout & risks
s = new_slide()
title(s, "Rollout and risks", "Pilot small, prove the five numbers, then scale city by city")
phases = [("Weeks 0–6 · Pilot", "Pune (tier 1) + Jaipur (tier 2). Professional offices + micro via partners. Hindi, Marathi, English. Target: 11% activation in pilot cohorts."),
          ("Months 2–4 · Expand", "8 cities, WhatsApp channel live, multi-site with partner surveys, referral loop, 10 languages."),
          ("Months 5–12 · Scale", "All 22 cities; live links to GST, Udyam and Entity Locker systems; factories added with the field team.")]
y = 1.45
for h1, body in phases:
    box(s, 0.45, y, 4.2, 0.9, fill=LIGHT)
    text(s, 0.6, y + 0.06, 3.95, 0.85, [[(h1, {"bold": True, "size": 10.5, "color": RED_D})], [(body, {"size": 9, "color": INK2})]])
    y += 0.98
box(s, 0.45, y + 0.02, 4.2, 0.62, fill=RED)
text(s, 0.6, y + 0.07, 3.95, 0.55, [[("Our ask: ", {"bold": True, "color": WHITE}), ("a 6-week, two-city pilot, judged on the five metrics. The prototype already runs end to end, so the pilot is integration work, not research.", {"color": WHITE})]], size=9.5)
rows = [["Risk", "Mitigation"],
        ["AI sells the wrong thing or makes up a price", "Rules decide, AI only explains; 15 test chats run on every change"],
        ["Free AI is busy or down", "3 backup models, then built-in rules; paid AI plan in production"],
        ["Fake or edited documents", "Government records first, number checks, two readers, human check"],
        ["Partners see the app as a threat", "They earn on every app sale in their area and get ready-made leads"],
        ["Owners who can't read or type easily", "Voice notes, read-aloud, tap buttons, help from a partner"],
        ["Fibre not available", "Pincode check before quote; 5G AirFiber live in 2 days"],
        ["Privacy law (DPDP Act)", "Clear consent, no stored photos, hidden ID numbers, 'My data' page"]]
table(s, 4.85, 1.45, 4.7, rows, [1.85, 2.85], size=8.6, row_h=0.43)
footer(s, "Prototype, privacy note, architecture and data analysis in the repository. All data synthetic.")
notes(s, "Close: ask for a 6-week pilot in two cities, judged on the five metrics. The prototype already runs the full journey, so the pilot is integration work (GSTN, Udyam, Entity Locker, billing), not research.")

prs.core_properties.author = "darkhorse0204"
prs.core_properties.last_modified_by = "darkhorse0204"
prs.core_properties.title = "Ek Baithak · Business case"
prs.save(OUT)
os.remove(bg_path)
print("saved", OUT, "slides:", len(prs.slides))
