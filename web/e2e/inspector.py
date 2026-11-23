"""Prueba de punta a punta de la app del inspector con Chrome real.

Carga una junta (el portero detecta una foto puesta como radiografía y se mueve), espera el
análisis, revisa cada hallazgo, comprueba que la decisión esté bloqueada hasta revisar todo,
decide, arma el informe en PDF, carga la obra de ejemplo y verifica que todo quede guardado al
recargar.

Uso: con la app servida (npm run build && npx vite preview --port 4173),
     python e2e/inspector.py <ejemplos> <capturas>
     (<ejemplos> tiene radiografia_1.png y foto_cordon_1.jpg)
"""
import re
import sys
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

EJEMPLOS, CAPTURAS = Path(sys.argv[1]), Path(sys.argv[2])
CAPTURAS.mkdir(parents=True, exist_ok=True)
URL = "http://localhost:4173/"
ANALISIS = 240_000

with sync_playwright() as p:
    browser = p.chromium.launch(executable_path="/usr/bin/google-chrome", args=["--no-sandbox"])
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    page.add_init_script("window.print = () => { window.__impreso = (window.__impreso || 0) + 1; }")
    errores = []
    page.on("console", lambda m: m.type == "error" and errores.append(m.text))
    page.on("pageerror", lambda e: errores.append(str(e)))
    page.goto(URL)

    # 1. Bandeja vacía
    expect(page.locator("#bandeja-vacia")).to_be_visible()
    page.screenshot(path=CAPTURAS / "app-01-bandeja-vacia.png")

    # 2. Inspector y norma
    page.click("#btn-ajustes")
    page.fill("#aj-inspector", "Ana Inspectora")
    page.select_option("#aj-norma", "API 1104")
    page.click("#dlg-ajustes button[value=ok]")
    expect(page.locator("#ajustes-resumen")).to_have_text("Inspector: Ana Inspectora · API 1104")

    # 3. Cargar soldadura: guardar vacío muestra errores
    page.click("[data-nav=cargar]")
    page.click("button[data-then=revisar]")
    expect(page.locator("[data-err=obra]")).to_have_text("Indicá la obra.")
    expect(page.locator("[data-err=imagenes]")).to_contain_text("Subí")

    page.fill("input[name=obra]", "Gasoducto Norte")
    page.fill("input[name=tramo]", "Tramo 3 · Km 12–18")
    page.fill("input[name=numero]", "J-0001")
    page.fill("input[name=progresiva]", "12+100")
    page.select_option("#sel-union", "Caño–codo")
    page.fill("input[name=soldador]", "S-07")

    # foto puesta donde va la radiografía: el portero avisa y se mueve
    rx = page.locator(".slot[data-slot=radiografia]")
    foto = page.locator(".slot[data-slot=foto]")
    rx.locator("input[type=file]").set_input_files(EJEMPLOS / "foto_cordon_1.jpg")
    expect(rx.locator(".slot-note")).to_contain_text("parece una foto del cordón", timeout=60_000)
    page.screenshot(path=CAPTURAS / "app-02-portero-en-carga.png")
    rx.get_by_role("button", name="Moverla a foto del cordón").click()
    expect(foto.locator(".slot-note")).to_contain_text("Parece una foto del cordón", timeout=60_000)
    expect(rx.locator("img")).to_be_hidden()
    rx.locator("input[type=file]").set_input_files(EJEMPLOS / "radiografia_1.png")
    expect(rx.locator(".slot-note")).to_contain_text("Parece una radiografía", timeout=60_000)
    page.screenshot(path=CAPTURAS / "app-03-carga.png")
    page.click("button[data-then=revisar]")

    # 4. Revisión: espera el análisis de las dos imágenes
    expect(page).to_have_url(re.compile(r"#/junta/"))
    expect(page.locator("#r-titulo")).to_contain_text("J-0001")
    expect(page.locator("#r-estado")).to_contain_text("Para revisar", timeout=ANALISIS)
    expect(page.locator("#r-decidir")).to_be_disabled()
    pend = page.locator("#r-pend").inner_text()
    print("Hallazgos pendientes al abrir:", pend)
    page.screenshot(path=CAPTURAS / "app-04-revision.png")

    # el primero se cambia de tipo, el segundo se acepta, el resto se descarta. Después de cada
    # cambio la lista se vuelve a dibujar: se espera que baje la cuenta de pendientes.
    def pendientes():
        txt = page.locator("#r-pend").inner_text()
        return int(txt.split()[-1]) if txt else 0

    def hacer(accion):
        n = pendientes()
        accion()
        expect(page.locator("#r-pend")).to_have_text(f"· faltan {n - 1}" if n > 1 else "")

    total = pendientes()
    assert total >= 2, f"esperaba al menos 2 hallazgos, hay {total}"
    con_acciones = page.locator("[data-test^=aceptar-]")
    primero = page.locator("#r-hallazgos li[data-number]").filter(has=con_acciones).first
    opciones = primero.locator("select option:not([disabled]):not([value=''])")
    nuevo = opciones.first.get_attribute("value")
    hacer(lambda: primero.locator("select").select_option(nuevo))
    hacer(lambda: page.locator("[data-test^=aceptar-]").first.click())
    while pendientes():
        hacer(lambda: page.locator("[data-test^=descartar-]").first.click())
    expect(page.locator("#r-pend")).to_have_text("")
    expect(page.locator("#r-decidir")).to_be_enabled()

    # vista lado a lado
    page.click("#r-vistas button[data-vista=lado]")
    expect(page.locator("#r-viewers")).to_have_class(re.compile("lado"))
    page.locator("#r-hallazgos li[data-number]").first.click()
    page.screenshot(path=CAPTURAS / "app-05-lado-a-lado.png")

    # decisión: reparar sin motivo no se puede
    page.check("input[name=resultado][value=reparar]")
    page.click("#r-decidir")
    expect(page.locator("#r-dec-err")).to_contain_text("motivo")
    page.fill("#r-nota", "Porosidad agrupada en raíz: reparar y volver a radiografiar.")
    page.click("#r-decidir")
    expect(page.locator("#r-estado")).to_contain_text("Reparar")
    expect(page.locator("#r-estado")).to_contain_text("Ana Inspectora")
    expect(page.locator("[data-test^=aceptar-]")).to_have_count(0)
    historial = page.locator("#r-historial li").all_inner_texts()
    print("Historial:", len(historial), "eventos; último:", historial[0])
    assert any("cambió el hallazgo" in h for h in historial)
    assert any("decidió: reparar" in h for h in historial)
    assert any(h.startswith(tuple("0123456789")) and "IA" in h for h in historial)
    page.screenshot(path=CAPTURAS / "app-06-decidida.png")

    # 5. Informe: se arma y se imprime a PDF
    page.click("#r-informe")
    page.wait_for_function("window.__impreso === 1")
    page.emulate_media(media="print")
    page.pdf(path=str(CAPTURAS / "informe-J-0001.pdf"), format="A4", print_background=True)
    page.emulate_media(media="screen")
    assert page.locator("#informe img").count() == 2

    # 6. Bandeja con la obra de ejemplo
    page.click("[data-nav=bandeja]")
    expect(page.locator("#tabla-bandeja tbody tr")).to_have_count(1)
    expect(page.locator("#tabla-bandeja tbody tr").first).to_contain_text("Reparar")
    page.click("#btn-ejemplo-2")
    expect(page.locator("#tabla-bandeja tbody tr")).to_have_count(4)
    expect(page.locator("#tabla-bandeja")).not_to_contain_text("Analizando", timeout=ANALISIS)
    filas = page.locator("#tabla-bandeja tbody tr").all_inner_texts()
    print("Bandeja:")
    for f in filas:
        print("  ", " | ".join(x.strip().replace("\n", " ") for x in f.split("\t")))
    assert "Reparar" in filas[-1], "la junta decidida tiene que quedar al final"
    page.screenshot(path=CAPTURAS / "app-07-bandeja.png")

    # filtros
    page.select_option("#f-obra", "Gasoducto de ejemplo")
    expect(page.locator("#tabla-bandeja tbody tr")).to_have_count(3)
    page.select_option("#f-tramo", "Tramo 4 · Km 18–24")
    expect(page.locator("#tabla-bandeja tbody tr")).to_have_count(1)
    page.select_option("#f-obra", "")
    page.select_option("#f-tramo", "")

    # 7. Recargar: todo sigue guardado
    page.reload()
    expect(page.locator("#tabla-bandeja tbody tr")).to_have_count(4)
    page.locator("#tabla-bandeja tbody tr", has_text="J-0001").click()
    expect(page.locator("#r-estado")).to_contain_text("Reparar")

    # reabrir deja volver a revisar
    page.click("[data-test=reabrir]")
    expect(page.locator("#r-estado")).to_contain_text("Lista para decidir")
    expect(page.locator("#r-historial li").first).to_contain_text("reabrió")

    # 8. Analizar rápido sigue andando
    page.click("[data-nav=analizar]")
    page.set_input_files("#file", EJEMPLOS / "foto_cordon_1.jpg")
    expect(page.locator("#gate")).to_contain_text("parece", timeout=60_000)

    # 9. Celular
    page.set_viewport_size({"width": 390, "height": 844})
    page.click("[data-nav=bandeja]")
    page.screenshot(path=CAPTURAS / "app-08-celular.png", full_page=True)

    print("Errores de consola:", errores or "ninguno")
    assert not errores
    browser.close()
print("OK")
