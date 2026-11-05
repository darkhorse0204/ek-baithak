"""Rehearse the exact demo-video script in Chrome, timing each step. Usage: python scripts/rehearse_demo.py"""
import os
import time

from playwright.sync_api import sync_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "runtime", "rehearsal")
os.makedirs(OUT, exist_ok=True)
BASE = os.environ.get("BASE", "http://localhost:8000")
log, errors = [], []


def step(name, t0):
    dt = time.time() - t0
    log.append((name, round(dt, 1)))
    print(f"{dt:6.1f}s  {name}")
    return time.time()


def wait_bot(page, timeout=90):
    page.wait_for_timeout(300)
    page.wait_for_function("() => !document.querySelector('.typing')", timeout=timeout * 1000)


def last_bot(page):
    return page.locator(".msg:not(.me):not(.sys)").last.inner_text()


with sync_playwright() as p:
    b = p.chromium.launch(channel="chrome", headless=True)
    page = b.new_page(viewport={"width": 1600, "height": 900})
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(BASE + "/")
    page.wait_for_selector(".langs button")

    # Scene 2: Hindi
    t = time.time()
    page.locator(".langs button", has_text="हिन्दी").click()
    page.locator(".welcome .btn").click()
    page.wait_for_selector("#chatinput")
    page.fill("#chatinput", "मेरी जयपुर में मिठाई की दुकान है, 4 लोग काम करते हैं। UPI के लिए अच्छा इंटरनेट और CCTV चाहिए।")
    page.keyboard.press("Enter")
    wait_bot(page)
    t = step("Hindi: first reply (asks: " + last_bot(page)[-60:].replace("\n", " ") + ")", t)
    chips = [c.inner_text() for c in page.locator(".chips .chip").all()]
    print("        chips:", chips)
    if page.locator(".chips .chip").count():
        page.locator(".chips .chip").last.click()  # "I don't have GST"
        wait_bot(page)
        t = step("Hindi: tapped no-GST chip", t)
    if page.locator(".needs-card").count():
        page.locator(".needs-card .btn").click()
        wait_bot(page)
        t = step("Hindi: confirmed needs -> plan", t)
    page.locator("#phone").screenshot(path=os.path.join(OUT, "1_hindi_plan.png"))
    print("        plan:", page.locator(".plan-bubble .price").last.inner_text().replace("\n", " "))

    # Scene 3: English, Kochi clinic
    page.goto(BASE + "/")
    page.wait_for_selector(".langs button")
    t = time.time()
    page.locator(".langs button", has_text="English").click()
    page.locator(".welcome .btn").click()
    page.wait_for_selector("#chatinput")
    page.fill("#chatinput", "Dental clinic in Kochi, 12 staff. We want 1 Gbps internet and SMS reminders for patients.")
    page.keyboard.press("Enter")
    wait_bot(page)
    t = step("EN: first reply (" + last_bot(page)[-70:].replace("\n", " ") + ")", t)
    for _ in range(4):
        if page.locator(".needs-card").count():
            break
        chips = page.locator(".chips .chip")
        txt = [c.inner_text() for c in chips.all()]
        print("        chips:", txt)
        if any("GSTIN" in x for x in txt):
            page.locator(".chips .chip", has_text="GSTIN").click()
            page.fill("#chatinput", "32TTNXB7384T1ZW")
            page.keyboard.press("Enter")
            wait_bot(page)
            t = step("EN: typed GSTIN -> registry", t)
        elif txt:
            chips.first.click()
            wait_bot(page)
            t = step(f"EN: tapped chip {txt[0]}", t)
    page.locator(".needs-card .btn").click()
    wait_bot(page)
    t = step("EN: confirmed needs -> plan", t)
    page.locator("#phone").screenshot(path=os.path.join(OUT, "2_en_plan_chat.png"))
    print("        explanation:", last_bot(page)[:400].replace("\n", " | "))
    page.locator(".plan-bubble .btn").last.click()
    page.wait_for_selector(".price-hero")
    page.locator(".seg button").nth(1).click()
    page.wait_for_timeout(800)
    t = step("EN: quote screen, switched to 24 months", t)
    page.locator("#phone").screenshot(path=os.path.join(OUT, "3_quote.png"))
    page.locator(".sticky-foot .btn").click()
    page.wait_for_selector(".purpose")
    page.locator(".sticky-foot .btn").click()
    page.wait_for_selector(".samples")
    t = step("EN: consent accepted", t)
    for k in ("K06", "K02"):
        page.locator(".samples button", has_text=k).click()
        page.wait_for_selector(".verdict", timeout=90000)
        t = step(f"EN: KYC {k} -> " + page.locator(".verdict").inner_text().split("\n")[0], t)
        page.locator("#phone").screenshot(path=os.path.join(OUT, f"4_kyc_{k}.png"))
        if k == "K06":
            page.locator("text=Try other documents").click()
            page.wait_for_selector(".samples")
    page.locator(".sticky-foot .btn").click()
    page.wait_for_selector("#otp")
    page.locator(".pad .btn").first.click()
    page.wait_for_selector(".btn.green", timeout=30000)
    page.locator(".btn.green").click()
    page.wait_for_selector(".timeline")
    t = step("EN: signed + paid -> tracker", t)
    for _ in range(6):
        page.locator("text=Next day").click()
        page.wait_for_timeout(350)
    t = step("EN: tracker -> " + page.locator(".pad .row").first.inner_text().replace("\n", " "), t)
    page.locator("#phone").screenshot(path=os.path.join(OUT, "5_tracker.png"))
    for tab in ["Live journeys", "KYC lab", "Bundle audit", "Funnel & simulator"]:
        page.locator(".tabs button", has_text=tab).click()
        page.wait_for_timeout(1500)
    t = step("Control room tabs", t)
    page.screenshot(path=os.path.join(OUT, "6_control_room.png"))
    b.close()
print("TOTAL waiting time:", round(sum(x[1] for x in log), 1), "s; JS errors:", errors or "none")
