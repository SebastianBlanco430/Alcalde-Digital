# Fuegos sobre los tejados (cálculos puros: NO importa ursina ni panda3d). Lo dibuja frontend/fuego_tejado.py y lo
# engancha frontend/ciudad_viva.py en la capa «fuego» de las etapas malas del final.
#
# Antes: hogueras low-poly (conos de 5 lados y bolas de humo) sobre los puntos de basura de la ACERA, a ras de suelo.
# Ahora (FUEGO_TEJADO):
#   - el fuego arde SOBRE las casas: un sitio por casa decorativa, en el punto del tejado (o azotea) del piso de arriba;
#   - es más grande (ESCALA_FUEGO_TEJADO) y de formas suaves: lenguas de llama de silueta redondeada en láminas
#     cruzadas, con degradado de color y de transparencia (rojo -> naranja -> amarillo, opaco abajo y transparente en
#     la punta) y un borde de tinta, para no salir del estilo cómic del juego;
#   - más humo: BOCANADAS_HUMO bocanadas por fuego que suben, crecen, derivan con el viento y se desvanecen en bucle.
# Coste: la piscina de entidades de siempre (2 variantes x 5 fuegos, creadas una vez) y BOCANADAS_HUMO hijas por
# fuego, creadas también una vez; por frame solo se mueven/escalan (nada se crea).
# FUEGO_TEJADO = False (o ALCALDE_FUEGO_TEJADO=0) vuelve a las hogueras de la acera.

import math
import os

FUEGO_TEJADO = True
ESCALA_FUEGO_TEJADO = 2.4        # la llama mide ~1,5 m en la malla: arde a ~3,6 m sobre el tejado
BOCANADAS_HUMO = 4               # cada bocanada es un nodo (una llamada de dibujo): pocas y grandes
SUBIDA_HUMO = 8.5                # m que sube una bocanada en su vida
ALTURA_INICIO_HUMO = 2.2         # m sobre el tejado donde nace (encima de la llama, a escala 1 de la malla)
TAMANO_HUMO = (1.8, 6.2)         # m de diámetro al nacer y al desvanecerse
DERIVA_HUMO = (1.8, 0.6)         # m que el viento la lleva en x y z durante su vida
PERIODO_HUMO = 6.5               # s de vida de cada bocanada
ALFA_HUMO = 0.9
RADIO_FUEGO_TEJADO = 70.0        # m alrededor de la cámara en los que se encienden (son altos: se ven de lejos)
MARGEN_SOBRE_TEJADO = 0.05       # m que la base de la llama se hunde en el tejado (no flota)


def _bandera(nombre, constante):
    valor = os.environ.get(nombre, "").strip().lower()
    if valor in ("1", "true", "si", "sí", "on"):
        return True
    if valor in ("0", "false", "no", "off"):
        return False
    return bool(constante)


def activo():
    return _bandera("ALCALDE_FUEGO_TEJADO", FUEGO_TEJADO)


# Silueta de una lengua de llama (plano x-y, base en y=0): lista de (x, y) en orden antihorario. Base redondeada
# (media circunferencia de radio `ancho`/2), costados que se estrechan hasta la punta en `alto`, con una ondulación
# `curva` (desvío lateral de la punta, en fracciones del ancho). `n`: puntos por costado.
def silueta_llama(ancho, alto, curva=0.0, n=9):
    r = ancho / 2.0
    puntos = []
    for k in range(n + 1):                                       # base: media circunferencia de abajo
        a = math.pi + math.pi * k / n
        puntos.append((r * math.cos(a), r + r * math.sin(a)))
    for k in range(1, n):                                        # costado derecho hacia la punta
        s = k / n
        puntos.append((_mitad(r, s) + _desvio(ancho, curva, s), r + s * (alto - r)))
    puntos.append((_desvio(ancho, curva, 1.0), alto))           # punta
    for k in range(n - 1, 0, -1):                                # costado izquierdo de vuelta
        s = k / n
        puntos.append((-_mitad(r, s) + _desvio(ancho, curva, s), r + s * (alto - r)))
    return puntos


def _mitad(r, s):
    return r * (1.0 - s) ** 1.25 * (1.0 + 0.18 * math.sin(math.pi * s))


def _desvio(ancho, curva, s):
    return curva * ancho * math.sin(math.pi * s * 0.9) * s


# Alfa de un punto de la llama a altura relativa `s` (0 base, 1 punta): opaca abajo, transparente arriba.
def alfa_llama(s, abajo=0.95, arriba=0.05):
    s = max(0.0, min(1.0, s))
    return abajo + (arriba - abajo) * s ** 1.6


# Estado de la bocanada `j` (de `n`) del fuego de número fijo `u` en el instante `t`: (dx, dy, dz, diámetro, alfa,
# tono). dy sube; el diámetro crece; alfa nace rápido y se apaga despacio; tono 0 (oscuro, abajo) -> 1 (claro, arriba).
def ciclo_humo(t, u, j, n=BOCANADAS_HUMO, periodo=PERIODO_HUMO):
    fase = (t / periodo + j / n + u * 0.731) % 1.0
    dy = ALTURA_INICIO_HUMO + SUBIDA_HUMO * fase
    dx = DERIVA_HUMO[0] * fase * fase + 0.25 * math.sin(6.283 * (fase + u))
    dz = DERIVA_HUMO[1] * fase + 0.2 * math.cos(6.283 * (fase * 0.7 + u))
    diametro = TAMANO_HUMO[0] + (TAMANO_HUMO[1] - TAMANO_HUMO[0]) * fase ** 0.8
    alfa = ALFA_HUMO * min(1.0, fase * 7.0) * (1.0 - fase) ** 0.8
    return dx, dy, dz, diametro, alfa, fase


# Punto del tejado de un modelo (en su marco local, y arriba) a partir de una función `superficie(x, z)` -> altura de la
# cara de arriba más alta en (x, z) o None. Se busca en una rejilla dentro de la huella (`limites` = (x0, x1, z0, z1))
# el punto más alto cuyos vecinos a `paso` estén a la misma altura (±`tolerancia`): evita el canto fino de un antepecho.
# Devuelve (x, y, z) o None si no hay superficie.
def punto_de_tejado(superficie, limites, divisiones=7, paso=0.18, tolerancia=0.2):
    x0, x1, z0, z1 = limites
    mejor, respaldo = None, None
    for i in range(divisiones):
        for k in range(divisiones):
            x = x0 + (x1 - x0) * (0.15 + 0.7 * i / (divisiones - 1))
            z = z0 + (z1 - z0) * (0.15 + 0.7 * k / (divisiones - 1))
            y = superficie(x, z)
            if y is None:
                continue
            if respaldo is None or y > respaldo[1]:
                respaldo = (x, y, z)
            vecinos = [superficie(x + dx, z + dz) for dx, dz in ((paso, 0), (-paso, 0), (0, paso), (0, -paso))]
            if all(v is not None and abs(v - y) <= tolerancia for v in vecinos):
                # el más alto; a igual altura, el más cercano al centro de la huella
                centro = ((x - (x0 + x1) / 2) ** 2 + (z - (z0 + z1) / 2) ** 2)
                clave = (round(y, 2), -centro)
                if mejor is None or clave > mejor[0]:
                    mejor = (clave, (x, y, z))
    return mejor[1] if mejor is not None else respaldo


# Altura (y) de la cara de arriba más alta que cubre (x, z) entre `triangulos` [(a, b, c)] (vértices (x, y, z), y arriba)
# o None. Solo cuentan las caras con normal hacia arriba (|ny| > 0.35), sea cual sea el orden de sus vértices.
def superficie_en(triangulos, x, z):
    mejor = None
    for a, b, c in triangulos:
        if not _dentro_xz(x, z, a, b, c):
            continue
        ux, uy, uz = b[0] - a[0], b[1] - a[1], b[2] - a[2]
        vx, vy, vz = c[0] - a[0], c[1] - a[1], c[2] - a[2]
        nx, ny, nz = uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx
        largo = math.sqrt(nx * nx + ny * ny + nz * nz)
        if largo < 1e-12 or abs(ny) / largo < 0.35:
            continue
        y = a[1] - (nx * (x - a[0]) + nz * (z - a[2])) / ny
        if mejor is None or y > mejor:
            mejor = y
    return mejor


def _dentro_xz(x, z, a, b, c):
    def lado(p1, p2):
        return (x - p2[0]) * (p1[2] - p2[2]) - (p1[0] - p2[0]) * (z - p2[2])
    d1, d2, d3 = lado(a, b), lado(b, c), lado(c, a)
    negativo = d1 < 0 or d2 < 0 or d3 < 0
    positivo = d1 > 0 or d2 > 0 or d3 > 0
    return not (negativo and positivo)
