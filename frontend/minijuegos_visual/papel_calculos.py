# Cálculo puro (sin Ursina) de las piezas de papel de los minijuegos: giros deterministas, hojas con esquina doblada,
# renglones, cadenas, arcos, aros discontinuos de rotulador, ovillos y barridos de resaltador.

import hashlib
import math

PAPEL_VIEJO = (236, 224, 190)
PAPEL_SOMBRA = (214, 200, 168)
CORCHO = (150, 106, 66)
CORCHO_OSC = (118, 80, 48)


def giro_por_id(ident, maximo=1.5):
    """Giro determinista en [-maximo, maximo] a partir de `ident` (estable entre ejecuciones)."""
    resumen = hashlib.md5(str(ident).encode("utf-8")).digest()
    u = int.from_bytes(resumen[:4], "big") / 0xFFFFFFFF
    return (u * 2.0 - 1.0) * maximo


def esquina_doblada(ancho, alto, tam=0.05):
    """(poligono_hoja, triangulo_doblez) centrados en 0, con la esquina inferior derecha recortada."""
    w, h = ancho / 2.0, alto / 2.0
    t = max(0.0, min(tam, ancho, alto))
    hoja = [(-w, h), (w, h), (w, -h + t), (w - t, -h), (-w, -h)]
    doblez = [(w, -h + t), (w - t, -h), (w - t, -h + t)]
    return hoja, doblez


def renglones(n=6, y0=0.27, paso=0.105):
    return [y0 - paso * k for k in range(n)]


def pasarela(n=6, x=0.0, y0=0.27, paso=0.105):
    return [(x, y) for y in renglones(n, y0, paso)]


def posiciones_cadena(n, x_derecha=0.62, paso=0.25):
    return [x_derecha - paso * k for k in range(n)]


def arco(cx, cy, r, a0, a1, n=24):
    n = max(1, int(n))
    puntos = []
    for i in range(n + 1):
        a = math.radians(a0 + (a1 - a0) * i / n)
        puntos.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return puntos


def aro_discontinuo(rx, ry, segmentos=12, hueco=0.4):
    """Elipse de radios (rx, ry) partida en `segmentos` trazos; `hueco` es la fracción vacía de cada tramo."""
    segmentos = max(1, int(segmentos))
    hueco = max(0.0, min(0.95, hueco))
    tramo = 2 * math.pi / segmentos
    lleno = tramo * (1.0 - hueco)
    salida = []
    for k in range(segmentos):
        a0 = k * tramo
        a1 = a0 + lleno
        salida.append(((rx * math.cos(a0), ry * math.sin(a0)), (rx * math.cos(a1), ry * math.sin(a1))))
    return salida


def ovillos(total, restantes):
    total = max(0, int(total))
    restantes = max(0, min(total, int(restantes)))
    return [k < restantes for k in range(total)]


def progreso_barrido(t, dur=0.18, reducir=False):
    if reducir or dur <= 0:
        return 1.0
    return max(0.0, min(1.0, t / dur))
