from playwright.sync_api import sync_playwright
import sys, re
src, out = sys.argv[1], sys.argv[2]
head = open(src).read(400)
w, h = map(int, re.search(r'width="(\d+)" height="(\d+)"', head).groups())
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": w, "height": h}, device_scale_factor=2)
    pg.goto("file://" + src)
    pg.screenshot(path=out)
    b.close()
