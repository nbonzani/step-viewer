"""Test du viewer HTML sous file:// avec l'Edge installé (Playwright, channel msedge).

Usage : python tests/html_selftest.py [capture.png]
Vérifie : auto-test embarqué (#selftest), chargement de tests/sample.step via « Ouvrir… »,
arborescence et masquage sur tests/assembly.step, menu Vue.
"""
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
HTML = (ROOT / "html" / "dist" / "STEP_Viewer.html").as_uri()
SAMPLE = str(ROOT / "tests" / "sample.step")
ASSEMBLY = str(ROOT / "tests" / "assembly.step")


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

        # assemblage : arborescence tri-état et masquage en cascade
        page.goto(HTML)
        page.set_input_files("#file", ASSEMBLY)
        page.wait_for_function("document.getElementById('status').textContent.includes('corps')", timeout=60000)
        page.wait_for_timeout(300)
        names = page.evaluate("[...document.querySelectorAll('#tree .name')].map(n => n.textContent)")
        assert names == ["Ensemble", "Sous-ensemble", "Plaque", "Axe", "Axe"], names
        states = "[...document.querySelectorAll('#tree input')].map(c => c.indeterminate ? 'ind' : c.checked)"
        page.click("#tree .row >> nth=1 >> input")            # décoche Sous-ensemble
        assert page.evaluate(states) == ["ind", False, False, False, True], page.evaluate(states)
        hidden = page.evaluate("window.stepViewer.data.meshes.length")
        page.click("#tree .row >> nth=2 >> input")            # recoche Plaque → Sous-ensemble partiel
        assert page.evaluate(states) == ["ind", "ind", True, False, True], page.evaluate(states)
        page.click("#dd-view > button")
        page.click("#dd-view [data-view=top]")
        assert page.evaluate("document.getElementById('dd-view').classList.contains('open')") is False
        print(f"assembly.step — arborescence OK ({hidden} maillages)")

        # sélection multiple (clic, Ctrl, Maj), H / Ctrl+H, picking et menu contextuel dans la vue
        page.keyboard.press("0")
        page.wait_for_timeout(100)
        sel = lambda: page.evaluate("window.stepViewer.selection")
        hid = lambda: page.evaluate("window.stepViewer.hidden")
        rows = page.locator("#tree .row .name")
        rows.nth(2).click()
        assert sel() == ["Plaque"], sel()
        rows.nth(4).click(modifiers=["Control"])
        assert sel() == ["Plaque", "Axe"], sel()
        rows.nth(1).click()
        rows.nth(3).click(modifiers=["Shift"])
        assert sel() == ["Sous-ensemble", "Plaque", "Axe"], sel()
        page.keyboard.press("h")
        assert hid() == [0, 1], hid()
        page.keyboard.press("Control+h")
        assert hid() == [], hid()
        page.keyboard.press("Escape")
        page.mouse.click(600, 420)                             # la plaque, au centre en vue iso
        assert sel() == ["Plaque"], sel()
        page.mouse.click(600, 420, button="right")
        labels = page.evaluate("[...document.querySelectorAll('#ctxmenu button')].map(b => b.firstChild.textContent)")
        assert labels == ["Cacher", "Afficher", "Tout afficher", "Ajuster"], labels
        page.click("#ctxmenu button >> nth=0")
        page.wait_for_timeout(100)
        assert hid() == [0], hid()
        page.mouse.click(300, 600)                             # clic dans le vide : désélection
        assert sel() == [], sel()
        print("sélection / picking / menu contextuel OK")
        assert not errors, errors
        browser.close()
    print("OK")


if __name__ == "__main__":
    main()
