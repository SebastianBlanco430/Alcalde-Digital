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


# -- Rastrear / Comparar (rediseño de papel y tinta) --

def grano_corcho(n, ancho, alto, cy=0.0, semilla=11):
    """Motitas finas del corcho: [(x, y, radio, oscuro, alfa)]. Muchas, pequeñas y repartidas (determinista)."""
    import random
    azar = random.Random(semilla)
    n = max(0, int(n))
    salida = []
    for _ in range(n):
        oscuro = azar.random() < 0.6
        salida.append((azar.uniform(-ancho / 2 + 0.008, ancho / 2 - 0.008),
                       cy + azar.uniform(-alto / 2 + 0.008, alto / 2 - 0.008),
                       azar.uniform(0.002, 0.0055) if oscuro else azar.uniform(0.002, 0.004),
                       oscuro, azar.uniform(0.35, 0.7)))
    return salida


def esquinas_oscuras(ancho, alto, cy=0.0, capas=3, lado=0.2, alfa=0.1):
    """Viñeta de las 4 esquinas del corcho: rectángulos [(cx, cy, w, h, alfa)] anidados que se apilan hacia la esquina."""
    capas = max(1, int(capas))
    salida = []
    for sx in (-1, 1):
        for sy in (-1, 1):
            for k in range(capas):
                w = lado * (1.0 - k / capas)
                h = lado * 0.6 * (1.0 - k / capas)
                salida.append((sx * (ancho / 2 - w / 2), cy + sy * (alto / 2 - h / 2), w, h, alfa))
    return salida


def alto_nota(n_lineas, reenviado=False, cabecera=0.05, renglon=0.03, minimo=0.15, maximo=0.34):
    """Alto de una nota candidata ajustado a su texto: cabecera + renglones + hueco (más si lleva sello de reenviado)."""
    n = max(1, int(n_lineas))
    alto = cabecera + 0.03 + n * renglon + (0.06 if reenviado else 0.0)
    return max(minimo, min(maximo, alto))


def subrayado_rotulador(ancho, semilla=0, tramos=12, amplitud=0.0012):
    """Dos trazos de rotulador (polilíneas [(x, y)]) con un temblor leve, para subrayar una línea de `ancho`."""
    import random
    azar = random.Random(semilla)
    trazos = []
    for k, dy in enumerate((0.0, -0.007)):
        tramos_k = max(2, int(tramos))
        extra = azar.uniform(-0.02, 0.0) if k else 0.0
        x0, x1 = -ancho / 2 + 0.01 + (0.03 if k else 0.0), ancho / 2 - 0.01 + extra
        puntos = []
        for i in range(tramos_k + 1):
            t = i / tramos_k
            puntos.append((x0 + (x1 - x0) * t, dy + azar.uniform(-amplitud, amplitud) + 0.002 * (t - 0.5)))
        trazos.append(puntos)
    return trazos


def cabeza_retrato(radio=0.036):
    """Pieza mínima de un retrato: (centro de la cabeza, radio, trapecio de hombros) en coordenadas de la foto."""
    hombros = [(-radio * 2.0, -0.062), (-radio * 1.25, -0.022), (radio * 1.25, -0.022), (radio * 2.0, -0.062)]
    return (0.0, 0.012), radio, hombros
