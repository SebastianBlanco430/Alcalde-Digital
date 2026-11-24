# Cálculos puros de la rueda de opciones del caso (sin ursina): su centro (FIJO: tercio derecho, altura del pecho), las
# cajas de los 4 huecos fijos (0 arriba, 1 derecha, 2 abajo, 3 izquierda) y la comprobación de que ninguna pisa la cara
# (círculo de radio 0,11 alrededor de un ancla) ni se sale de su franja de pantalla (contrato_ui.md §5).

SEMIANCHO_16_9 = 16 / 9 / 2      # camera.ui va de -0,889 a 0,889 en x a 16:9
RADIO_CARA = 0.11
CENTRO_FIJO = (0.48, -0.04)     # tercio derecho, altura del pecho, encima de los subtítulos (igual en toda toma)
CENTRO_SIN_ANCLA = CENTRO_FIJO   # nombre viejo (contrato_ui §5): ya no hay otro sitio
MARGEN_X = 0.02                  # aire con el borde de la pantalla
Y_MAX = 0.32                     # techo: el medidor ocupa y >= 0,41 y la ficha «Prueba nueva» baja hasta 0,33
Y_MIN = -0.25                    # suelo: los subtítulos ocupan y <= -0,32 y la frase del jugador llega a -0,27

RADIO_RELOJ = 0.05               # anillo del reloj en el centro (radio exterior)
SEPARACION = 0.022               # entre el anillo y las cajas

ANCHO_HUECO, ALTO_HUECO = 0.30, 0.075          # rueda de diálogo
ANCHO_FICHA, ALTO_FICHA = 0.30, 0.10           # acusación: ficha con retrato


def desplazamientos(ancho, alto, radio=RADIO_RELOJ, sep=SEPARACION):
    """(dx de los huecos laterales, dy de los huecos de arriba y abajo) respecto al centro."""
    return radio + sep + ancho / 2, radio + sep + alto / 2


def extension(ancho, alto, radio=RADIO_RELOJ, sep=SEPARACION):
    """Semiancho y semialto de toda la rueda (de borde a borde de sus cajas)."""
    dx, dy = desplazamientos(ancho, alto, radio, sep)
    return dx + ancho / 2, dy + alto / 2


def cajas(centro, ancho=ANCHO_HUECO, alto=ALTO_HUECO, radio=RADIO_RELOJ, sep=SEPARACION):
    """[(x, y, ancho, alto)] de los huecos 0..3 (centro de cada caja)."""
    cx, cy = centro
    dx, dy = desplazamientos(ancho, alto, radio, sep)
    return [(cx, cy + dy, ancho, alto), (cx + dx, cy, ancho, alto),
            (cx, cy - dy, ancho, alto), (cx - dx, cy, ancho, alto)]


def caja_pisa_circulo(caja, centro, radio):
    """¿La caja (x, y, ancho, alto) corta el círculo?"""
    x, y, w, h = caja
    px = min(max(centro[0], x - w / 2), x + w / 2)
    py = min(max(centro[1], y - h / 2), y + h / 2)
    return (px - centro[0]) ** 2 + (py - centro[1]) ** 2 < radio ** 2


def cajas_se_solapan(a, b):
    return abs(a[0] - b[0]) * 2 < a[2] + b[2] and abs(a[1] - b[1]) * 2 < a[3] + b[3]


def _encajar(centro, sw, sh, semiancho):
    x_min, x_max = -semiancho + MARGEN_X + sw, semiancho - MARGEN_X - sw
    y_min, y_max = Y_MIN + sh, Y_MAX - sh
    x = min(max(centro[0], x_min), x_max) if x_min <= x_max else 0.0
    y = min(max(centro[1], y_min), y_max) if y_min <= y_max else (Y_MIN + Y_MAX) / 2
    return x, y


def pisa_cara(centro, ancla, ancho=ANCHO_HUECO, alto=ALTO_HUECO):
    if ancla is None:
        return False
    return any(caja_pisa_circulo(c, ancla, RADIO_CARA) for c in cajas(centro, ancho, alto))


def colocar(ancla=None, ancho=ANCHO_HUECO, alto=ALTO_HUECO, semiancho=SEMIANCHO_16_9):
    """Centro de la rueda: SIEMPRE el mismo sitio (CENTRO_FIJO: tercio derecho, a la altura del pecho, encima de los
    subtítulos), sea cual sea la cara. `ancla` se acepta por compatibilidad y se ignora: antes la rueda iba al lado de la
    cara y cambiaba de lado cuando la cabeza cruzaba la mitad de la pantalla (al respirar), así que saltaba. Las tomas de
    la cámara (camaras_calculos.CARA_EN_PANTALLA) dejan la cara en el centro-izquierda, fuera de rectangulo()."""
    return _encajar(CENTRO_FIJO, *extension(ancho, alto), semiancho)


def rectangulo(ancho=ANCHO_HUECO, alto=ALTO_HUECO, semiancho=SEMIANCHO_16_9):
    """(x0, y0, x1, y1) en camera.ui que ocupa la rueda colocada (de borde a borde de sus cajas)."""
    cx, cy = colocar(None, ancho, alto, semiancho)
    sw, sh = extension(ancho, alto)
    return cx - sw, cy - sh, cx + sw, cy + sh


def dentro_de_franja(centro, ancho=ANCHO_HUECO, alto=ALTO_HUECO, semiancho=SEMIANCHO_16_9, tol=1e-9):
    """¿Todas las cajas quedan dentro de la pantalla y entre los subtítulos y el medidor?"""
    for x, y, w, h in cajas(centro, ancho, alto):
        if x - w / 2 < -semiancho - tol or x + w / 2 > semiancho + tol:
            return False
        if y + h / 2 > Y_MAX + tol or y - h / 2 < Y_MIN - tol:
            return False
    return True


def suavizar_centro(actual, objetivo, dt, velocidad=10.0, reducir=False, salto=0.25):
    """Sigue al ancla sin tirones: interpola hacia el objetivo; con reducir movimiento (o un salto grande) va directo."""
    if actual is None or reducir:
        return objetivo
    if abs(objetivo[0] - actual[0]) > salto or abs(objetivo[1] - actual[1]) > salto:
        return objetivo
    k = min(1.0, max(0.0, dt) * velocidad)
    return actual[0] + (objetivo[0] - actual[0]) * k, actual[1] + (objetivo[1] - actual[1]) * k
