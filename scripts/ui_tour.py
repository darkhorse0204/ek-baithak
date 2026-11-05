"""Drive the real UI in Chrome: full owner journey + every console tab. Saves screenshots to deck/shots/.
Usage: python scripts/ui_tour.py [lang] [first message]"""
import os
import sys
import time

from playwright.sync_api import sync_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "deck", "shots")
os.makedirs(OUT, exist_ok=True)
LANG = sys.argv[1] if len(sys.argv) > 1 else "en"
FIRST = sys.argv[2] if len(sys.argv) > 2 else "I run a dental clinic in Pune with 9 staff. Patients wait in reception, and we need appointment SMS reminders."
GSTIN = sys.argv[3] if len(sys.argv) > 3 else "27PZSXS1936O1ZH"
errors = []


def shot(page, name, phone_only=False):
    path = os.path.join(OUT, f"{LANG}_{name}.png")
    (page.locator("#phone") if phone_only else page).screenshot(path=path)
    print("shot", path)


def wait_idle(page, timeout=60):
    t = time.time()
    while time.time() - t < timeout:
        if page.locator(".typing").count() == 0:
            return
        time.sleep(0.3)


with sync_playwright() as p:
    b = p.chromium.launch(channel="chrome", headless=True)
    page = b.new_page(viewport={"width": 1500, "height": 920}, device_scale_factor=2)
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(os.environ.get("BASE", "http://localhost:8000") + "/")
    page.wait_for_selector(".langs button")
    page.locator(".langs button").nth(["en", "hi", "mr", "ta", "te", "bn", "gu", "kn", "ml", "pa"].index(LANG)).click()
    shot(page, "01_welcome", True)
    page.click("text=→")
    page.wait_for_selector("#chatinput")
    page.fill("#chatinput", FIRST)
    page.keyboard.press("Enter")
    time.sleep(0.5)
    wait_idle(page)
    for _ in range(6):
        wait_idle(page)
        if page.locator(".plan-bubble .btn").count():
            break
        if page.locator(".needs-card").count():
            shot(page, "03_needs", True)
            page.locator(".needs-card .btn").click()
            time.sleep(0.5)
            continue
        chips = page.locator(".chips .chip")
        if chips.count():
            txt = chips.first.inner_text()
            if page.locator(".chips .chip", has_text="GST").count() or "GSTIN" in page.locator(".msg").last.inner_text():
                page.fill("#chatinput", GSTIN)
                page.keyboard.press("Enter")
            else:
                chips.first.click()
            time.sleep(0.5)
            continue
        break
    wait_idle(page)
    shot(page, "02_chat", True)
    page.screenshot(path=os.path.join(OUT, f"{LANG}_00_desktop.png"))
    page.locator(".plan-bubble .btn").last.click()
    page.wait_for_selector(".price-hero")
    shot(page, "04_quote", True)
    page.locator(".screen").evaluate("e => e.scrollTo(0, 600)")
    shot(page, "05_quote_more", True)
    page.locator(".sticky-foot .btn").click()
    page.wait_for_selector(".purpose")
    shot(page, "06_consent", True)
    page.locator(".sticky-foot .btn").click()
    page.wait_for_selector(".samples")
    shot(page, "07_kyc_options", True)
    for k, name in [("K06", "08_kyc_review"), ("K11", "09_kyc_action"), ("K01", "10_kyc_restricted")]:
        page.locator(".samples button", has_text=k).click()
        page.wait_for_selector(".verdict", timeout=90000)
        shot(page, name, True)
        page.locator("text=Try other documents").click()
        page.wait_for_selector(".samples")
    if page.locator("text=Fetch from Entity Locker").count():
        page.locator("text=Fetch from Entity Locker").click()
        page.wait_for_selector(".verdict", timeout=60000)
        shot(page, "11_kyc_locker", True)
        page.locator("text=Try other documents").click()
        page.wait_for_selector(".samples")
    page.locator(".samples button", has_text="K02").click()
    page.wait_for_selector(".verdict", timeout=90000)
    shot(page, "12_kyc_approved", True)
    page.locator(".sticky-foot .btn").click()
    page.wait_for_selector("#otp")
    page.locator(".btn", has_text="Aadhaar").first.click() if LANG == "en" else page.locator(".pad .btn").first.click()
    page.wait_for_selector(".btn.green", timeout=30000)
    shot(page, "13_sign_pay", True)
    page.locator(".btn.green").click()
    page.wait_for_selector(".timeline")
    shot(page, "14_tracker_day0", True)
    for _ in range(6):
        page.locator("text=Next day").click()
        time.sleep(0.4)
    page.locator(".screen").evaluate("e => e.scrollTo(0, 0)")
    shot(page, "15_tracker_live", True)
    page.screenshot(path=os.path.join(OUT, f"{LANG}_16_desktop_tracker.png"))
    page.locator("button[title]", has_text="🔒").first.click() if page.locator("button[title]", has_text="🔒").count() else None
    time.sleep(1)
    shot(page, "17_mydata", True)
    # Console tabs
    for i, tab in enumerate(["Live journeys", "Who to call", "Rescue queue", "KYC lab", "Funnel & simulator", "Segments", "Bundle audit", "Privacy log"]):
        page.locator(".tabs button", has_text=tab).click()
        time.sleep(2.5)
        page.locator("#console").screenshot(path=os.path.join(OUT, f"console_{i}_{tab.split()[0].lower()}.png"))
    page.locator(".tabs button", has_text="KYC lab").click()
    time.sleep(1.5)
    page.locator(".labcard", has_text="K06").click()
    time.sleep(2)
    page.locator("#console").screenshot(path=os.path.join(OUT, "console_kyc_k06.png"))
    b.close()
print("JS errors:", errors or "none")
