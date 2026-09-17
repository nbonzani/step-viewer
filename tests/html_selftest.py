"""Test du viewer HTML sous file:// avec l'Edge installé (Playwright, channel msedge).

Usage : python tests/html_selftest.py [capture.png]
Vérifie : auto-test embarqué (#selftest) puis chargement de tests/sample.step via le bouton « Ouvrir… ».
"""
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
HTML = (ROOT / "html" / "dist" / "STEP_Viewer.html").as_uri()
SAMPLE = str(ROOT / "tests" / "sample.step")


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge", headless=True)
        page = browser.new_page(viewport={"width": 1000, "height": 700})
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))

        page.goto(HTML + "#selftest")
        page.wait_for_function("document.getElementById('status').textContent.startsWith('SELFTEST')", timeout=60000)
        status = page.text_content("#status")
        assert status.startswith("SELFTEST OK"), status
        print(status)

        page.goto(HTML)
        page.set_input_files("#file", SAMPLE)
        page.wait_for_function("document.getElementById('status').textContent.includes('corps')", timeout=60000)
        page.wait_for_timeout(300)
        status = page.text_content("#status")
        assert "2 corps" in status, status
        print(status)
        if len(sys.argv) > 1:
            page.screenshot(path=sys.argv[1])
        assert not errors, errors
        browser.close()
    print("OK")


if __name__ == "__main__":
    main()
