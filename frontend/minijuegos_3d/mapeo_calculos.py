# Matemática del mouse sobre superficies 3D (Python puro: NO importa ursina). La usa frontend/minijuegos_3d/raton.py.
#
# Sistemas de coordenadas (los mismos en todo el paquete):
#   - NDC de pantalla: (-1, -1) abajo a la izquierda, (1, 1) arriba a la derecha de la VENTANA.
#   - Local del quad: un quad de Ursina (model="quad") mide 1x1 en su espacio local, centrado: x, y en [-0.5, 0.5], normal +z
#     hacia atrás (la cara visible mira a -z local). Con scale=(ancho, alto) el local sigue siendo [-0.5, 0.5].
#   - UV: (0, 0) abajo a la izquierda, (1, 1) arriba a la derecha de la superficie.
#   - UI (camera.ui y la raíz de la textura): x en [-aspecto/2, aspecto/2], y en [-0.5, 0.5], centro (0, 0).
#   - NDC de la textura: como el de pantalla, pero de la cámara 2D fuera de pantalla.

import math

EPS = 1e-9


def pantalla_a_ndc(px, py, ancho, alto):
    """Píxel de ventana (origen arriba a la izquierda, como Panda get_pointer) -> NDC (-1..1, y hacia arriba)."""
    return (2.0 * px / ancho - 1.0, 1.0 - 2.0 * py / alto)


def mouse_ui_a_ndc(x, y, aspecto):
    """mouse.x / mouse.y de Ursina (espacio UI de la ventana) -> NDC de la ventana."""
    return (2.0 * x / aspecto, 2.0 * y)


def interseccion_rayo_plano(origen, direccion, punto, normal):
    """Punto donde el rayo origen + t·direccion (t >= 0) corta el plano (punto, normal); None si es paralelo o queda detrás."""
    den = sum(direccion[i] * normal[i] for i in range(3))
    if abs(den) < EPS:
        return None
    t = sum((punto[i] - origen[i]) * normal[i] for i in range(3)) / den
    if t < 0:
        return None
    return tuple(origen[i] + t * direccion[i] for i in range(3))


def rayo_en_local(cerca, lejos):
    """Con los dos extremos del rayo YA en el espacio local del quad, el punto local (x, y) en el plano z = 0, o None."""
    direccion = tuple(lejos[i] - cerca[i] for i in range(3))
    p = interseccion_rayo_plano(cerca, direccion, (0.0, 0.0, 0.0), (0.0, 0.0, 1.0))
    if p is None:
        return None
    return (p[0], p[1])


def local_a_uv(x, y):
    """Local del quad ([-0.5, 0.5]) -> UV ([0, 1]). Sin recortar."""
    return (x + 0.5, y + 0.5)


def uv_a_local(u, v):
    return (u - 0.5, v - 0.5)


def dentro(u, v, margen=0.0):
    """¿UV dentro de la superficie? `margen` > 0 encoge la zona válida (en fracción de lado)."""
    return margen <= u <= 1.0 - margen and margen <= v <= 1.0 - margen


def uv_a_ui(u, v, aspecto):
    """UV de la superficie -> coordenadas UI de la raíz 2D que se dibuja en ella (aspecto = ancho/alto de la textura)."""
    return ((u - 0.5) * aspecto, v - 0.5)


def ui_a_uv(x, y, aspecto):
    return (x / aspecto + 0.5, y + 0.5)


def uv_a_ndc(u, v):
    """UV -> NDC de la cámara 2D de la textura (la que mira la raíz 2D)."""
    return (2.0 * u - 1.0, 2.0 * v - 1.0)


def mapear(cerca_local, lejos_local, aspecto, margen=0.0):
    """Todo el camino de una vez: rayo del mouse (extremos en local del quad) -> (u, v, x_ui, y_ui) o None si el rayo no
    toca la superficie (fuera del monitor = sin hover y sin clic)."""
    local = rayo_en_local(cerca_local, lejos_local)
    if local is None:
        return None
    u, v = local_a_uv(*local)
    if not dentro(u, v, margen):
        return None
    x, y = uv_a_ui(u, v, aspecto)
    return (u, v, x, y)


# -- Legibilidad (alto de texto en píxeles de la ventana) --

def fov_vertical(fov_horizontal, aspecto):
    """Panda: Lens.set_fov(f) fija el FOV HORIZONTAL; el vertical sale del aspecto."""
    return math.degrees(2 * math.atan(math.tan(math.radians(fov_horizontal) / 2) / aspecto))


def altura_en_pantalla_px(altura_mundo, distancia, fov_v, alto_ventana_px):
    """Píxeles de alto que ocupa algo de `altura_mundo` m, de frente, a `distancia` m de una cámara con FOV vertical fov_v."""
    if distancia <= 0:
        return float("inf")
    return altura_mundo / (2 * distancia * math.tan(math.radians(fov_v) / 2)) * alto_ventana_px


def alto_linea_en_monitor_px(px_referencia, alto_monitor_en_pantalla_px, alto_referencia=600):
    """Alto de una línea de texto de la vista 2D (pedida en `px_referencia` píxeles de la referencia de 600 px de
    frontend/componentes.py) cuando la vista entera ocupa `alto_monitor_en_pantalla_px` píxeles de alto en la ventana."""
    return px_referencia / alto_referencia * alto_monitor_en_pantalla_px


def minimo_legible(alto_ventana_px):
    """Criterio del rework: >= 14 px a 720 y >= 18 px a 1080 (interpolado y acotado)."""
    if alto_ventana_px <= 720:
        return 14.0
    if alto_ventana_px >= 1080:
        return 18.0
    return 14.0 + (alto_ventana_px - 720) / (1080 - 720) * 4.0
