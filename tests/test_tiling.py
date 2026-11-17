import pytest

from revision_pipes.annotations import Box
from revision_pipes.tiling import boxes_in_window, merge, to_plate, windows

# --- Ventanas --------------------------------------------------------------------------

def test_imagen_casi_cuadrada_usa_una_sola_ventana():
    assert windows(640, 640) == [(0, 0, 640, 640)]
    assert windows(800, 600) == [(0, 0, 800, 600)]


def test_placa_ancha_se_corta_en_cuadrados_que_cubren_todo():
    ws = windows(3000, 600, overlap=0.25)
    assert all(x1 - x0 == 600 and y1 - y0 == 600 for x0, y0, x1, y1 in ws)
    assert ws[0][0] == 0
    assert ws[-1][2] == 3000
    # cada ventana pisa a la siguiente
    assert all(b[0] < a[2] for a, b in zip(ws, ws[1:], strict=False))


def test_placa_alta_se_corta_en_vertical():
    ws = windows(500, 2000)
    assert all(x0 == 0 and x1 == 500 and y1 - y0 == 500 for x0, y0, x1, y1 in ws)
    assert ws[-1][3] == 2000


def test_superposicion_invalida_da_error():
    with pytest.raises(ValueError):
        windows(3000, 600, overlap=1.0)


# --- Recuadros dentro de una ventana ---------------------------------------------------

def test_recuadro_adentro_pasa_a_coordenadas_de_la_ventana():
    (b,) = boxes_in_window([Box(700, 100, 750, 150, "poro")], (600, 0, 1200, 600))
    assert (b.x_min, b.y_min, b.x_max, b.y_max) == (100, 100, 150, 150)


def test_recuadro_cortado_se_conserva_solo_si_se_ve_lo_suficiente():
    window = (600, 0, 1200, 600)
    mostly_inside = Box(580, 0, 680, 10, "fisura")   # 80 % adentro
    mostly_outside = Box(500, 0, 620, 10, "fisura")  # 17 % adentro
    result = boxes_in_window([mostly_inside, mostly_outside], window, min_visible=0.4)
    assert len(result) == 1
    assert result[0].x_min == 0


def test_recuadro_fuera_de_la_ventana_se_descarta():
    assert boxes_in_window([Box(0, 0, 50, 50, "poro")], (600, 0, 1200, 600)) == []


# --- Volver a la placa y unir duplicados -----------------------------------------------

def test_ida_y_vuelta_conserva_las_coordenadas():
    original = Box(700, 100, 750, 150, "poro", 0.9)
    window = (600, 0, 1200, 600)
    assert to_plate(boxes_in_window([original], window), window) == [original]


def test_merge_une_duplicados_de_ventanas_que_se_pisan():
    a = Box(100, 100, 150, 150, "poro", 0.9)
    b = Box(102, 101, 151, 149, "poro", 0.7)
    c = Box(400, 100, 450, 150, "poro", 0.6)
    assert merge([b, a, c]) == [a, c]


def test_merge_no_une_clases_distintas():
    a = Box(100, 100, 150, 150, "poro", 0.9)
    b = Box(100, 100, 150, 150, "fisura", 0.8)
    assert len(merge([a, b])) == 2
