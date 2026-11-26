# Dónde va la flecha amarilla de la piel BOTW (la del ratón encima o el foco de teclado/mando) para que no se monte
# sobre lo que el control tiene al lado. Python PURO (sin ursina): la parte visual mide los rectángulos en camera.ui
# (frontend/componentes.py: colocar_flecha_botw) y aquí solo se elige.
#
# Orden de preferencia (el primero que no choca con nada y cabe en pantalla):
#   1. a la izquierda, tamaño normal (como siempre)       3. a la izquierda, más pequeña
#   2. a la derecha, tamaño normal (espejada)              4. a la derecha, más pequeña
#   5. si todo choca: SIN flecha (ANILLO). El control se marca con su anillo amarillo de foco, como las pestañas de BOTW:
#      una flecha metida dentro del botón tapaba su texto.
#
#   elegir(control, ancho, alto, hueco, obstaculos, limites) -> Colocacion(lado, escala, x, y, ancho, alto)
#   Rectángulos = (x0, y0, x1, y1) en unidades de camera.ui. `limites` = pantalla recortada al panel que lo contiene.

from collections import namedtuple

IZQUIERDA = "izquierda"
DERECHA = "derecha"
ANILLO = "anillo"
CANDIDATOS = ((IZQUIERDA, 1.0), (DERECHA, 1.0), (IZQUIERDA, 0.75), (DERECHA, 0.75))
MARGEN_CHOQUE = 0.002          # unidades de camera.ui: tocar el borde de otro control ya cuenta como choque

Colocacion = namedtuple("Colocacion", "lado escala x y ancho alto")


# Rectángulo de la flecha (ancho x alto a esa escala) en ese lado del control.
def rect_flecha(control, lado, ancho, alto, hueco, escala=1.0):
    x0, y0, x1, y1 = control
    w, h = ancho * escala, alto * escala
    cy = (y0 + y1) / 2
    if lado == IZQUIERDA:
        cx = x0 - hueco * escala - w / 2
    elif lado == DERECHA:
        cx = x1 + hueco * escala + w / 2
    else:
        cx = (x0 + x1) / 2
    return (cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2)


def se_cruzan(a, b, margen=MARGEN_CHOQUE):
    return a[0] < b[2] + margen and b[0] < a[2] + margen and a[1] < b[3] + margen and b[1] < a[3] + margen


def contiene(fuera, dentro):
    return fuera[0] <= dentro[0] and fuera[1] <= dentro[1] and fuera[2] >= dentro[2] and fuera[3] >= dentro[3]


# Obstáculos que cuentan: los que no envuelven al control (un panel que lo contiene no es «lo de al lado»).
def obstaculos_utiles(control, obstaculos):
    return [o for o in obstaculos if o is not None and not contiene(o, control)]


def elegir(control, ancho, alto, hueco, obstaculos=(), limites=None):
    """Primera colocación libre de CANDIDATOS; si ninguna lo está, ANILLO (sin flecha). `limites` = rectángulo donde
    debe caber la flecha (None = sin límite)."""
    otros = obstaculos_utiles(control, obstaculos)
    for lado, escala in CANDIDATOS:
        r = rect_flecha(control, lado, ancho, alto, hueco, escala)
        if limites is not None and not contiene(limites, r):
            continue
        if not any(se_cruzan(r, o) for o in otros):
            return _colocacion(lado, escala, r)
    return _colocacion(ANILLO, 0.0, rect_flecha(control, ANILLO, ancho, alto, hueco, 0.0))


# Intersección de dos rectángulos (None si alguno es None o no se tocan: entonces manda el otro).
def recortar(a, b):
    if a is None or b is None:
        return a if b is None else b
    r = (max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3]))
    return r if r[0] < r[2] and r[1] < r[3] else a


# El panel que contiene al control: el más pequeño de los fondos que lo envuelven, son claramente mayores (al menos el
# doble de área; un fondo del mismo tamaño que el botón no cuenta) y caben en `pantalla` (los decorados que se salen
# de la pantalla, como el paisaje del fondo, no son paneles). None si no hay.
def contenedor(control, fondos, pantalla=None):
    area = max(1e-9, (control[2] - control[0]) * (control[3] - control[1]))
    holgura = None if pantalla is None else (pantalla[0] - 0.01, pantalla[1] - 0.01, pantalla[2] + 0.01, pantalla[3] + 0.01)
    mejor = None
    for r in fondos:
        if r is None or not contiene(r, control) or (r[2] - r[0]) * (r[3] - r[1]) < 2 * area:
            continue
        if holgura is not None and not contiene(holgura, r):
            continue
        if mejor is None or (r[2] - r[0]) * (r[3] - r[1]) < (mejor[2] - mejor[0]) * (mejor[3] - mejor[1]):
            mejor = r
    return mejor


def _colocacion(lado, escala, r):
    return Colocacion(lado, escala, (r[0] + r[2]) / 2, (r[1] + r[3]) / 2, r[2] - r[0], r[3] - r[1])
