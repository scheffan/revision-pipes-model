"""Prueba de punta a punta de la pantalla "Analizar" con Chrome real.

Uso: con la app servida (npm run build && npx vite preview --port 4173),
     python e2e/analizar.py <ejemplos> <capturas>
     (<ejemplos> tiene radiografia_1.png y foto_cordon_1.jpg)
"""
import sys
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

EJEMPLOS, CAPTURAS = Path(sys.argv[1]), Path(sys.argv[2])
CAPTURAS.mkdir(parents=True, exist_ok=True)
URL = "http://localhost:4173/"

with sync_playwright() as p:
    browser = p.chromium.launch(executable_path="/usr/bin/google-chrome", args=["--no-sandbox"])
    page = browser.new_page(viewport={"width": 1440, "height": 860})
    logs = []
    page.on("console", lambda m: logs.append(f"{m.type}: {m.text}"))
    page.goto(URL)
    expect(page.locator("#drop-title")).to_have_text("Arrastrá una radiografía acá")
    page.screenshot(path=CAPTURAS / "web-01-inicio.png")

    # 1. Radiografía en la pestaña de radiografías: analiza directo
    page.set_input_files("#file", EJEMPLOS / "radiografia_1.png")
    expect(page.locator("#verdict")).to_contain_text("defecto", timeout=180_000)
    hallazgos = page.locator("#findings li").count()
    print("Radiografía:", page.locator("#verdict").inner_text(), "·", hallazgos, "hallazgos")
    page.screenshot(path=CAPTURAS / "web-02-radiografia.png")

    # 2. Zoom sobre el primer hallazgo
    page.locator("#findings li").first.click()
    page.screenshot(path=CAPTURAS / "web-03-zoom-hallazgo.png")

    # 3. Foto de cordón en la pestaña de radiografías: el portero avisa
    page.set_input_files("#file2", EJEMPLOS / "foto_cordon_1.jpg")
    expect(page.locator("#gate")).to_contain_text("parece", timeout=60_000)
    print("Portero:", page.locator("#gate").inner_text().splitlines()[0])
    page.screenshot(path=CAPTURAS / "web-04-portero-avisa.png")

    # 4. Cambiar de pestaña desde el aviso
    page.get_by_role("button", name="Cambiar a foto del cordón").click()
    expect(page.locator("#tab-cordones")).to_have_attribute("aria-selected", "true")
    expect(page.locator("#verdict")).not_to_have_text("Analizando…", timeout=180_000)
    hallazgos = page.locator("#findings li").count()
    print("Foto:", page.locator("#verdict").inner_text(), "·", hallazgos, "hallazgos")
    page.screenshot(path=CAPTURAS / "web-05-foto-cordon.png")

    errors = [line for line in logs if line.startswith("error")]
    print("Errores de consola:", errors or "ninguno")
    browser.close()
