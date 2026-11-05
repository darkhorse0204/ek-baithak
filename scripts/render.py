"""Render an HTML file (or element) to PNG/PDF with Chrome. Usage: render.py in.html out.png [selector] | out.pdf"""
import os, sys
from playwright.sync_api import sync_playwright
src, out = os.path.abspath(sys.argv[1]), os.path.abspath(sys.argv[2])
sel = sys.argv[3] if len(sys.argv) > 3 else None
with sync_playwright() as p:
    b = p.chromium.launch(channel="chrome", headless=True)
    pg = b.new_page(viewport={"width": 1600, "height": 900}, device_scale_factor=2)
    pg.goto("file:///" + src.replace("\\", "/"))
    pg.wait_for_timeout(400)
    if out.endswith(".pdf"):
        pg.pdf(path=out, format="A4", print_background=True, margin={"top": "0", "bottom": "0", "left": "0", "right": "0"})
    else:
        (pg.locator(sel) if sel else pg).screenshot(path=out)
    b.close()
print("wrote", out)
