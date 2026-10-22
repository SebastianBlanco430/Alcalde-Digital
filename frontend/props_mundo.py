# Decorado del mundo 3D (Ursina): árboles variados, arbustos con flores, farolas, bancos, vallas,
# carteles, jardineras y una fuente en la Plaza Central; además cintas de calle con ruido de color.
#
# Todo es DECORADO PURO: ninguna pieza tiene colisión (el backend no los conoce y no se toca), por
# eso se colocan siempre FUERA de las calles, de las huellas de los edificios y de las casas, de las
# escaleras, de los muros y de los pasos plaza -> puerta, y a distancia de los obstáculos que ya
# existen. La fuente central, en cambio, ocupa el centro de la plaza y se puede atravesar.
#
# Rendimiento: ningún prop es una Entity. Cada pieza (cubo, esfera baja, prisma) es una plantilla de
# triángulos que se copia con su posición, escala, giro y color directamente en UNA malla con
# normales planas (sombreado «low poly» con luz) y colores por vértice (degradado abajo -> arriba y
# un poco de ruido). El mundo recibe dos mallas: la opaca (con luz y sombras) y la de luces (focos de
# las farolas, sin sombreado).
#
# El azar sale de frontend/azar_fijo.py (determinista): ningún prop cambia entre ejecuciones y no se
# toca el random del backend. Las funciones puras (plantillas, colocación) se prueban en
# tests/frontend_3d/test_props_mundo.py; solo `construir_props_mundo` y `cinta_con_tono` usan Mesh.

import math
from functools import lru_cache
from typing import NamedTuple

from frontend.azar_fijo import azar_de, ruido_suave

# -- Colocación -----------------------------------------------------------------------------------
PASO_CALLE = 7.5             # m entre puestos de decorado a lo largo de una calle
ACERA = 2.0                  # m de acera a cada lado del asfalto (igual que ciudad_3d)
SEPARACION_CALLE = 1.5       # m extra entre el borde de la acera y el decorado
ENTRADA_PLAZA = 1.2          # m de la plaza (aro) hacia dentro de la calle donde empieza el decorado de calle
MARGEN_OBSTACULO = 0.7       # m libres entre un prop y los obstáculos del backend
CORREDOR_PASO = 2.6          # m a cada lado del eje de un camino plaza -> puerta o calle -> plaza
DISTANCIA_PROPS = 0.5        # m libres entre dos props nuevos
PENDIENTE_MAXIMA = 0.42      # desnivel por metro (tan ~23 grados): más empinado no lleva props
RADIO_PROP = {"arbol": 1.15, "arbusto": 0.9, "banco": 1.0, "valla": 1.2, "cartel": 0.5, "caneca": 0.4,
              "jardinera": 0.9, "farola": 0.4, "fuente": 2.3}
PROPS_POR_PLAZA = 4
PROPS_EN_CORONA = 9            # árboles/arbustos/carteles por plaza, sobre el pasto alrededor del aro
RADIO_ANILLO_PLAZA = 7.3     # m del centro de la plaza a los props de su borde interior
PLAZA_DE_LA_FUENTE = "Plaza Central"

# Verdes de las copas, flores y maderas (RGB 0-255). Con luz, el lado al sol sube y el de sombra queda.
VERDES = ((44, 102, 50), (60, 116, 48), (34, 88, 58), (78, 116, 42), (48, 108, 72))
VERDES_PINO = ((30, 84, 62), (38, 98, 70), (46, 106, 60))
FLORES_ARBOL = ((226, 136, 176), (240, 176, 200), (150, 112, 204), (236, 196, 90))
FLORES_ARBUSTO = ((222, 64, 64), (248, 206, 56), (240, 240, 232), (214, 70, 160), (250, 140, 60))
MADERAS = ((136, 88, 54), (112, 74, 46), (60, 100, 82), (156, 62, 50), (176, 140, 90))
COLORES_CARTEL = ((36, 84, 168), (34, 122, 78), (236, 196, 40), (200, 56, 52))
CONCRETO = (150, 146, 138)
HIERRO = (54, 56, 64)
PIEDRA_FUENTE = (176, 170, 160)
AGUA_FUENTE = (84, 168, 214)
LUZ_FAROLA = (255, 232, 160)


class Prop(NamedTuple):
    tipo: str
    x: float
    y: float
    z: float
    giro: float
    tam: float
    variante: int


# -- Plantillas de sólidos (puras) ----------------------------------------------------------------


# Reorienta cada triángulo para que su normal (cross(c - a, b - a): la cara frontal en Ursina) apunte
# hacia donde pida `referencia(g)`, con g el centro del triángulo.
def _orientar(vertices, triangulos, referencia):
    resultado = []
    for a, b, c in triangulos:
        pa, pb, pc = vertices[a], vertices[b], vertices[c]
        u = tuple(pc[i] - pa[i] for i in range(3))
        v = tuple(pb[i] - pa[i] for i in range(3))
        n = (u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0])
        g = tuple((pa[i] + pb[i] + pc[i]) / 3 for i in range(3))
        d = referencia(g)
        resultado.append((a, b, c) if sum(n[i] * d[i] for i in range(3)) >= 0 else (a, c, b))
    return resultado


def _hacia_afuera(centro):
    return lambda g: (g[0] - centro[0], g[1] - centro[1], g[2] - centro[2])


# Cubo de lado 1 centrado en el origen: (vértices, triángulos).
@lru_cache(maxsize=None)
def caja():
    vertices = tuple((x, y, z) for x in (-0.5, 0.5) for y in (-0.5, 0.5) for z in (-0.5, 0.5))
    caras = ((0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3))
    triangulos = [t for a, b, c, d in caras for t in ((a, b, c), (a, c, d))]
    return vertices, tuple(_orientar(vertices, triangulos, _hacia_afuera((0, 0, 0))))


# Esfera baja de radio 0.5: subdivisiones 0 = icosaedro (12 vértices), 1 = 42 vértices.
@lru_cache(maxsize=None)
def icosfera(subdivisiones=1):
    t = (1 + math.sqrt(5)) / 2
    vertices = [(-1, t, 0), (1, t, 0), (-1, -t, 0), (1, -t, 0), (0, -1, t), (0, 1, t), (0, -1, -t), (0, 1, -t),
                (t, 0, -1), (t, 0, 1), (-t, 0, -1), (-t, 0, 1)]
    triangulos = [(0, 11, 5), (0, 5, 1), (0, 1, 7), (0, 7, 10), (0, 10, 11), (1, 5, 9), (5, 11, 4), (11, 10, 2),
                  (10, 7, 6), (7, 1, 8), (3, 9, 4), (3, 4, 2), (3, 2, 6), (3, 6, 8), (3, 8, 9), (4, 9, 5),
                  (2, 4, 11), (6, 2, 10), (8, 6, 7), (9, 8, 1)]

    def unitario(v):
        n = 2 * math.sqrt(v[0] ** 2 + v[1] ** 2 + v[2] ** 2)
        return (v[0] / n, v[1] / n, v[2] / n)

    vertices = [unitario(v) for v in vertices]
    for _ in range(subdivisiones):
        medios, nuevos = {}, []

        def medio(i, j):
            clave = (min(i, j), max(i, j))
            if clave not in medios:
                a, b = vertices[i], vertices[j]
                vertices.append(unitario(tuple((a[k] + b[k]) / 2 for k in range(3))))
                medios[clave] = len(vertices) - 1
            return medios[clave]

        for a, b, c in triangulos:
            ab, bc, ca = medio(a, b), medio(b, c), medio(c, a)
            nuevos += [(a, ab, ca), (b, bc, ab), (c, ca, bc), (ab, bc, ca)]
        triangulos = nuevos
    return tuple(vertices), tuple(_orientar(vertices, triangulos, _hacia_afuera((0, 0, 0))))


# Prisma (o cono si radio_tope = 0) de altura 1 con la base en y = 0, de `lados` lados y los radios
# dados (sin tapa inferior: nunca se ve desde abajo).
@lru_cache(maxsize=None)
def prisma(lados=8, radio_base=0.5, radio_tope=0.5):
    vertices = []
    for y, r in ((0.0, radio_base), (1.0, radio_tope)):
        vertices += [(r * math.cos(2 * math.pi * k / lados), y, r * math.sin(2 * math.pi * k / lados))
                     for k in range(lados)]
    vertices.append((0.0, 1.0, 0.0))                       # centro de la tapa superior
    triangulos = []
    for k in range(lados):
        k1 = (k + 1) % lados
        triangulos += [(k, k1, lados + k1), (k, lados + k1, lados + k)]
        if radio_tope > 0:
            triangulos.append((lados + k, lados + k1, 2 * lados))
    return tuple(vertices), tuple(_orientar(vertices, triangulos, _hacia_afuera((0, 0.5, 0))))


# Anillo hueco (pared exterior, interior y borde superior) de altura 1 con la base en y = 0.
@lru_cache(maxsize=None)
def anillo(lados=14, radio_exterior=0.5, radio_interior=0.4):
    vertices = []
    for r in (radio_exterior, radio_interior):
        for y in (0.0, 1.0):
            vertices += [(r * math.cos(2 * math.pi * k / lados), y, r * math.sin(2 * math.pi * k / lados))
                         for k in range(lados)]
    # índices: [exterior abajo | exterior arriba | interior abajo | interior arriba]
    ea, ee, ia, ii = 0, lados, 2 * lados, 3 * lados
    muro_ext, muro_int, tapa = [], [], []
    for k in range(lados):
        k1 = (k + 1) % lados
        muro_ext += [(ea + k, ea + k1, ee + k1), (ea + k, ee + k1, ee + k)]
        muro_int += [(ia + k, ia + k1, ii + k1), (ia + k, ii + k1, ii + k)]
        tapa += [(ee + k, ee + k1, ii + k1), (ee + k, ii + k1, ii + k)]
    triangulos = (_orientar(vertices, muro_ext, lambda g: (g[0], 0, g[2]))
                  + _orientar(vertices, muro_int, lambda g: (-g[0], 0, -g[2]))
                  + _orientar(vertices, tapa, lambda g: (0, 1, 0)))
    return tuple(vertices), tuple(triangulos)


# -- Acumulador de mallas -------------------------------------------------------------------------


class Malla:
    """Copias de plantillas con normales planas y colores por vértice, listas para un Mesh."""

    def __init__(self):
        self.vertices, self.normales, self.colores = [], [], []

    def __len__(self):
        return len(self.vertices) // 3          # triángulos

    # Copia `solido` ((vértices, triángulos)) en `posicion` con `escala` (x, y, z o un número) y
    # giro_y grados (convención de Ursina). El color (RGB 0-255) va de `degradado[0]` abajo a
    # `degradado[1]` arriba (multiplicadores) y `ruido` lo varía por vértice.
    # `inclinacion` (grados, opcional): inclina el sólido sobre su eje x (positivo = la parte alta va hacia +z local,
    # o sea hacia donde mira `giro`) DESPUÉS de escalarlo y ANTES de girarlo `giro` sobre y: sirve para hojas de palma, toldos y colas. Con 0 todo sale
    # exactamente como antes.
    def agregar(self, solido, posicion, escala=1.0, giro=0.0, color=(255, 255, 255), degradado=(0.8, 1.05),
                ruido=0.0, inclinacion=0.0):
        sv, st = solido
        if isinstance(escala, (int, float)):
            escala = (escala, escala, escala)
        seno, coseno = math.sin(math.radians(giro)), math.cos(math.radians(giro))
        sp, cp = math.sin(math.radians(inclinacion)), math.cos(math.radians(inclinacion))
        ys = [v[1] for v in sv]
        alto = max(ys) - min(ys) or 1.0
        base = min(ys)
        puestos = []
        for x, y, z in sv:
            x, y, z = x * escala[0], y * escala[1], z * escala[2]
            if inclinacion:
                y, z = y * cp - z * sp, y * sp + z * cp
            puestos.append((posicion[0] + x * coseno + z * seno, posicion[1] + y,
                            posicion[2] - x * seno + z * coseno))
        tonos = []
        for (x, y, z), (_, vy, _) in zip(puestos, sv):
            f = degradado[0] + (degradado[1] - degradado[0]) * (vy - base) / alto
            f *= 1 - ruido * azar_de(x * 9.7 + y, z * 5.3)
            tonos.append((min(1.5, color[0] / 255 * f), min(1.5, color[1] / 255 * f), min(1.5, color[2] / 255 * f), 1.0))
        for a, b, c in st:
            pa, pb, pc = puestos[a], puestos[b], puestos[c]
            u = (pc[0] - pa[0], pc[1] - pa[1], pc[2] - pa[2])
            v = (pb[0] - pa[0], pb[1] - pa[1], pb[2] - pa[2])
            n = (u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0])
            largo = math.sqrt(n[0] ** 2 + n[1] ** 2 + n[2] ** 2) or 1.0
            n = (n[0] / largo, n[1] / largo, n[2] / largo)
            for i in (a, b, c):
                self.vertices.append(puestos[i])
                self.normales.append(n)
                self.colores.append(tonos[i])

    def mesh(self):
        from ursina import Mesh
        if not self.vertices:
            return None
        return Mesh(vertices=self.vertices, triangles=[], normals=self.normales, colors=self.colores)


def _tono(color, factor):
    return tuple(min(255, int(c * factor)) for c in color)


# -- Piezas de decorado ---------------------------------------------------------------------------
# Cada una agrega a `m` (opaca) y, si tiene focos, a `luz`. (x, y, z) es el pie; `s` la escala general.


def _elegir(paleta, a, b):
    return paleta[int(azar_de(a, b) * len(paleta)) % len(paleta)]


def arbol_redondo(m, x, y, z, s, variante, flor=False):
    copa = _elegir(FLORES_ARBOL, x + 1.3, z) if flor else VERDES[variante % len(VERDES)]
    alto_tronco = 1.5 * s
    m.agregar(prisma(6, 0.5, 0.36), (x, y - 0.1, z), (0.36 * s, alto_tronco + 0.1, 0.36 * s), azar_de(x, z) * 360,
              (104, 74, 48), (0.7, 1.0), 0.1)
    for dx, dy, dz, d, claro in ((0, 1.25, 0, 2.7, 1.0), (0.55, 1.95, -0.25, 1.9, 1.12), (-0.6, 1.55, 0.45, 1.7, 1.04)):
        m.agregar(icosfera(1), (x + dx * s, y + alto_tronco + (dy - 0.4) * s, z + dz * s), (d * s, d * 0.88 * s, d * s),
                  azar_de(x + dx, z + dy) * 360, _tono(copa, claro), (0.62, 1.12), 0.12)


def arbol_pino(m, x, y, z, s, variante):
    verde = VERDES_PINO[variante % len(VERDES_PINO)]
    m.agregar(prisma(6, 0.5, 0.4), (x, y - 0.1, z), (0.3 * s, 1.1 * s, 0.3 * s), 0, (96, 68, 44), (0.7, 1.0))
    for k, (d, alto) in enumerate(((2.5, 2.2), (1.95, 2.0), (1.4, 1.8))):
        m.agregar(prisma(8, 0.5, 0.0), (x, y + (0.9 + 1.25 * k) * s, z), (d * s, alto * s, d * s), k * 22 + variante * 9,
                  _tono(verde, 1.0 + 0.08 * k), (0.62, 1.1), 0.1)


def arbol_cipres(m, x, y, z, s, variante):
    m.agregar(prisma(6, 0.5, 0.4), (x, y - 0.1, z), (0.22 * s, 0.8 * s, 0.22 * s), 0, (96, 68, 44), (0.7, 1.0))
    m.agregar(icosfera(1), (x, y + 2.5 * s, z), (1.15 * s, 4.4 * s, 1.15 * s), variante * 30,
              _tono(VERDES_PINO[(variante + 1) % 3], 1.05), (0.6, 1.1), 0.12)


def arbusto(m, x, y, z, s, variante, flores=False):
    verde = VERDES[variante % len(VERDES)]
    for k, (dx, dz, d) in enumerate(((0, 0, 1.25), (0.55, 0.2, 0.9), (-0.45, -0.3, 0.8))):
        m.agregar(icosfera(1), (x + dx * s, y + 0.3 * d * s, z + dz * s), (d * s, 0.85 * d * s, d * s), k * 40,
                  _tono(verde, 1.0 - 0.06 * k), (0.62, 1.1), 0.12)
    if flores:
        flor = _elegir(FLORES_ARBUSTO, x, z + 2.2)
        for k in range(6):
            a = azar_de(x + k, z) * 6.283
            r = (0.25 + 0.5 * azar_de(x, z + k)) * s
            m.agregar(icosfera(0), (x + r * math.cos(a), y + (0.62 + 0.25 * azar_de(k, x)) * s, z + r * math.sin(a)),
                      0.2 * s, 0, flor, (0.9, 1.1))


def farola(m, luz, x, y, z, s, variante):
    m.agregar(prisma(8, 0.5, 0.4), (x, y - 0.05, z), (0.36 * s, 0.35 * s, 0.36 * s), 0, HIERRO, (0.8, 1.1))
    m.agregar(prisma(8, 0.5, 0.36), (x, y + 0.3 * s, z), (0.13 * s, 3.1 * s, 0.13 * s), 0, HIERRO, (0.8, 1.1))
    m.agregar(caja(), (x, y + 3.55 * s, z), (0.34 * s, 0.46 * s, 0.34 * s), 0, (236, 220, 170), (0.8, 1.0))
    m.agregar(prisma(8, 0.65, 0.0), (x, y + 3.78 * s, z), (0.5 * s, 0.32 * s, 0.5 * s), 0, HIERRO, (0.8, 1.1))
    luz.agregar(icosfera(0), (x, y + 3.55 * s, z), 0.42 * s, 0, LUZ_FAROLA, (1.0, 1.0))


def banco(m, x, y, z, giro, s, variante):
    madera = MADERAS[variante % len(MADERAS)]
    for dz in (-0.17, 0.0, 0.17):
        m.agregar(caja(), _desplazar(x, z, 0, dz, giro, y + 0.5 * s), (1.7 * s, 0.07 * s, 0.14 * s), giro, madera, (0.8, 1.0))
    for dy in (0.72, 0.9):
        m.agregar(caja(), _desplazar(x, z, 0, 0.26, giro, y + dy * s), (1.7 * s, 0.13 * s, 0.05 * s), giro, madera, (0.8, 1.0))
    for dx in (-0.75, 0.75):
        m.agregar(caja(), _desplazar(x, z, dx * s, 0.0, giro, y + 0.25 * s), (0.08 * s, 0.5 * s, 0.5 * s), giro, HIERRO, (0.8, 1.0))
        m.agregar(caja(), _desplazar(x, z, dx * s, 0.26 * s, giro, y + 0.62 * s), (0.08 * s, 0.7 * s, 0.05 * s), giro, HIERRO, (0.8, 1.0))


# (x, z) desplazado (dx, dz) en el sistema local de un objeto girado `giro` grados, y la altura dada.
def _desplazar(x, z, dx, dz, giro, y):
    seno, coseno = math.sin(math.radians(giro)), math.cos(math.radians(giro))
    return (x + dx * coseno + dz * seno, y, z - dx * seno + dz * coseno)


def valla(m, x, y, z, giro, largo, variante, suelo=None):
    color = (232, 228, 214) if variante % 2 == 0 else MADERAS[variante % len(MADERAS)]
    piquetes = max(2, int(largo / 0.32))
    for k in range(piquetes + 1):
        d = -largo / 2 + largo * k / piquetes
        px, _, pz = _desplazar(x, z, d, 0, giro, 0)
        base = suelo(px, pz) if suelo else y
        m.agregar(caja(), (px, base + 0.4, pz), (0.07, 0.8, 0.03), giro, color, (0.8, 1.0), 0.05)
    for dy in (0.3, 0.62):
        m.agregar(caja(), _desplazar(x, z, 0, 0, giro, y + dy), (largo, 0.05, 0.05), giro, color, (0.75, 1.0))
    for d in (-largo / 2, 0.0, largo / 2):
        px, _, pz = _desplazar(x, z, d, 0, giro, 0)
        base = suelo(px, pz) if suelo else y
        m.agregar(caja(), (px, base + 0.45, pz), (0.1, 0.95, 0.1), giro, _tono(color, 0.85), (0.75, 1.0))


def cartel(m, x, y, z, giro, s, variante):
    panel = COLORES_CARTEL[variante % len(COLORES_CARTEL)]
    m.agregar(prisma(6, 0.5, 0.5), (x, y - 0.05, z), (0.08 * s, 2.4 * s, 0.08 * s), 0, HIERRO, (0.8, 1.1))
    m.agregar(caja(), _desplazar(x, z, 0, -0.04, giro, y + 2.15 * s), (1.0 * s, 0.62 * s, 0.05 * s), giro, panel, (0.85, 1.05))
    m.agregar(caja(), _desplazar(x, z, 0, -0.075, giro, y + 2.15 * s), (0.7 * s, 0.1 * s, 0.03 * s), giro, (238, 238, 232), (0.9, 1.0))
    m.agregar(caja(), _desplazar(x, z, 0, -0.075, giro, y + 2.0 * s), (0.45 * s, 0.07 * s, 0.03 * s), giro, (238, 238, 232), (0.9, 1.0))


def jardinera(m, x, y, z, giro, s, variante):
    m.agregar(caja(), _desplazar(x, z, 0, 0, giro, y + 0.27 * s), (1.5 * s, 0.54 * s, 0.7 * s), giro, CONCRETO, (0.75, 1.0), 0.05)
    m.agregar(caja(), _desplazar(x, z, 0, 0, giro, y + 0.56 * s), (1.3 * s, 0.06 * s, 0.5 * s), giro, (82, 58, 40), (1.0, 1.0))
    verde, flor = VERDES[(variante + 2) % len(VERDES)], _elegir(FLORES_ARBUSTO, x + variante, z)
    for k, dx in enumerate((-0.45, 0.0, 0.45)):
        px, _, pz = _desplazar(x, z, dx * s, 0, giro, 0)
        m.agregar(icosfera(1), (px, y + 0.82 * s, pz), (0.55 * s, 0.45 * s, 0.5 * s), k * 30, verde, (0.62, 1.1), 0.1)
        m.agregar(icosfera(0), (px + 0.05, y + 1.05 * s, pz), 0.17 * s, 0, flor, (0.9, 1.1))


def caneca(m, x, y, z, s, variante):
    cuerpo = ((66, 112, 84), (96, 100, 108), (176, 98, 52))[variante % 3]
    m.agregar(prisma(8, 0.5, 0.42), (x, y, z), (0.46 * s, 0.78 * s, 0.46 * s), 0, cuerpo, (0.8, 1.05))
    m.agregar(prisma(8, 0.5, 0.45), (x, y + 0.78 * s, z), (0.5 * s, 0.07 * s, 0.5 * s), 0, HIERRO, (0.9, 1.1))


# Fuente de tres niveles: borde de piedra hueco, agua, pedestal, taza y chorro. Atravesable.
def fuente(m, x, y, z, s=1.0):
    m.agregar(prisma(14, 0.5, 0.5), (x, y, z), (4.5 * s, 0.12 * s, 4.5 * s), 0, _tono(PIEDRA_FUENTE, 0.9), (0.8, 1.0))
    m.agregar(anillo(14, 0.5, 0.42), (x, y, z), (4.0 * s, 0.66 * s, 4.0 * s), 12, PIEDRA_FUENTE, (0.85, 1.1), 0.05)
    m.agregar(prisma(14, 0.5, 0.5), (x, y + 0.04 * s, z), (3.35 * s, 0.46 * s, 3.35 * s), 0, AGUA_FUENTE, (0.95, 1.1))
    m.agregar(prisma(10, 0.5, 0.3), (x, y, z), (0.9 * s, 1.15 * s, 0.9 * s), 0, PIEDRA_FUENTE, (0.8, 1.1))
    m.agregar(prisma(14, 0.28, 0.5), (x, y + 1.05 * s, z), (1.9 * s, 0.34 * s, 1.9 * s), 0, PIEDRA_FUENTE, (0.8, 1.1))
    m.agregar(prisma(14, 0.5, 0.5), (x, y + 1.2 * s, z), (1.5 * s, 0.1 * s, 1.5 * s), 0, AGUA_FUENTE, (1.0, 1.1))
    m.agregar(prisma(6, 0.5, 0.2), (x, y + 1.2 * s, z), (0.28 * s, 1.2 * s, 0.28 * s), 0, (176, 218, 244), (0.95, 1.15))
    m.agregar(icosfera(1), (x, y + 2.45 * s, z), (0.42 * s, 0.5 * s, 0.42 * s), 0, (196, 228, 248), (1.0, 1.15))
    for k in range(6):                         # gotas que caen a la taza
        a = k * math.pi / 3
        m.agregar(icosfera(0), (x + 0.5 * s * math.cos(a), y + (1.55 - 0.1 * (k % 2)) * s, z + 0.5 * s * math.sin(a)),
                  0.13 * s, 0, (190, 226, 248), (1.0, 1.1))


# -- Colocación (pura) ----------------------------------------------------------------------------


def _distancia_a_segmento(x, z, a, b):
    dx, dz = b[0] - a[0], b[1] - a[1]
    largo2 = dx * dx + dz * dz
    t = 0.0 if largo2 < 1e-12 else min(1.0, max(0.0, ((x - a[0]) * dx + (z - a[1]) * dz) / largo2))
    return math.hypot(x - (a[0] + dx * t), z - (a[1] + dz * t))


class Reserva:
    """Lo que el decorado no puede tapar: obstáculos, cajas, círculos y corredores (a, b, ancho)."""

    def __init__(self, mundo):
        self.obstaculos = list(mundo.obstaculos())
        self.cajas = [(e.caja(), 1.2) for e in mundo.edificios()]
        self.cajas += [(z.caja(), 1.5) for z in getattr(mundo, "zonas", lambda: [])()]    # cancha y mercadito
        self.circulos = [(m.cx, m.cz, m.largo / 2 + 0.8) for m in mundo.muros()]
        self.pasos = []                  # caminos que se recorren a pie: plaza -> puerta y escaleras
        for e in mundo.edificios():
            self.pasos.append((mundo.coordenada(e.lugar), e.punto_entrada(2.0), CORREDOR_PASO))
        for escalera in mundo.escaleras():
            self.pasos.append(((escalera.ax, escalera.az), (escalera.bx, escalera.bz), escalera.ancho / 2 + 1.2))
        self.calles = []                 # asfalto y aceras (ancho completo)
        self.ejes = []                   # eje de cada calle con un corredor estrecho: dentro de la plaza
        semiancho = mundo.ancho_calle / 2
        for a, b in mundo.segmentos():
            pa, pb = mundo.coordenada(a), mundo.coordenada(b)
            if math.dist(pa, pb) > 1e-9:
                self.calles.append((pa, pb, semiancho + ACERA + 0.6))
                self.ejes.append((pa, pb, CORREDOR_PASO))
        self.circulos_nuevos = []

    # ¿Cabe un prop de radio r en (x, z)? Sin chocar con lo existente ni con lo ya colocado. Con
    # `en_plaza`, las calles solo reservan su eje (el asfalto no llega al interior de la plaza).
    def cabe(self, x, z, r, en_plaza=False):
        for o in self.obstaculos:
            if o.choca(x, z, r + MARGEN_OBSTACULO):
                return False
        for (x0, x1, z0, z1), margen in self.cajas:
            if math.hypot(x - min(max(x, x0), x1), z - min(max(z, z0), z1)) < r + margen:
                return False
        for cx, cz, cr in self.circulos:
            if math.hypot(x - cx, z - cz) < cr + r:
                return False
        for a, b, ancho in self.pasos + (self.ejes if en_plaza else self.calles):
            if _distancia_a_segmento(x, z, a, b) < ancho + r:
                return False
        return all(math.hypot(x - cx, z - cz) >= cr + r + DISTANCIA_PROPS for cx, cz, cr in self.circulos_nuevos)

    def ocupar(self, x, z, r):
        self.circulos_nuevos.append((x, z, r))


# Desnivel por metro del suelo en (x, z).
def pendiente(suelo, x, z, h=1.0):
    return math.hypot(suelo(x + h, z) - suelo(x - h, z), suelo(x, z + h) - suelo(x, z - h)) / (2 * h)


# Tipo de decorado de calle para un puesto: elegido por azar con estos pesos.
PESOS_CALLE = (("arbol", 0.42), ("arbusto", 0.17), ("valla", 0.14), ("banco", 0.09), ("cartel", 0.06),
               ("jardinera", 0.07), ("caneca", 0.05))


def _tipo_por_azar(u, pesos):
    acumulado = 0.0
    for tipo, peso in pesos:
        acumulado += peso
        if u < acumulado:
            return tipo
    return pesos[-1][0]


# Lista de Prop del mundo: decorado a los lados de las calles, alrededor de cada plaza (dentro y
# fuera de su aro) y la fuente de la Plaza Central.
def colocar_props(mundo):
    suelo = mundo.altura
    reserva = Reserva(mundo)
    props = []
    plazas = {lugar: mundo.coordenada(lugar) for lugar in mundo.lugares()}
    radio_plaza = mundo.radio_plaza
    semiancho = mundo.ancho_calle / 2

    def poner(tipo, x, z, giro=0.0, tam=1.0, variante=0, y=None, en_plaza=False):
        r = RADIO_PROP[tipo] * (tam if tipo not in ("valla", "banco", "cartel", "jardinera") else 1.0)
        if tipo == "valla":
            r = 1.0
        if not reserva.cabe(x, z, r, en_plaza) or pendiente(suelo, x, z) > PENDIENTE_MAXIMA:
            return False
        reserva.ocupar(x, z, r)
        props.append(Prop(tipo, round(x, 3), round(suelo(x, z) if y is None else y, 3), round(z, 3), giro, tam, variante))
        return True

    # Fuente: el centro de la plaza, sin reserva (nada más cabe ahí).
    centro_fuente = plazas.get(PLAZA_DE_LA_FUENTE)
    if centro_fuente is not None:
        props.append(Prop("fuente", centro_fuente[0], round(suelo(*centro_fuente) + 0.16, 3), centro_fuente[1], 0.0, 1.0, 0))
        reserva.ocupar(centro_fuente[0], centro_fuente[1], RADIO_PROP["fuente"])

    def poner_de_calle(tipo, x, z, u, nx, nz, lado, a_lo_largo, indice):
        variante = int(azar_de(x, z) * 997)
        tam = 0.85 + 0.4 * azar_de(z, x + 3.3)
        hacia_la_calle = math.degrees(math.atan2(lado * nx, lado * nz))
        if tipo == "arbol":
            clase = ("redondo", "redondo", "pino", "cipres", "flor", "redondo")[variante % 6]
            return poner("arbol", x, z, 0.0, tam, variante * 10 + ("redondo", "pino", "cipres", "flor").index(clase))
        if tipo == "valla":
            return poner("valla", x, z, a_lo_largo, 3.0 + 3.0 * azar_de(x, z), variante)
        if tipo in ("banco", "cartel"):
            return poner(tipo, x, z, hacia_la_calle, 1.0, variante)
        if tipo == "jardinera":
            return poner("jardinera", x, z, a_lo_largo, 1.0, variante)
        return poner(tipo, x, z, 0.0, tam, variante)

    # Calles: puestos cada PASO_CALLE m, alternando lados, fuera de la acera. Si el puesto está
    # ocupado se prueba más lejos de la calle.
    indice = 0
    for a, b in mundo.segmentos():
        pa, pb = mundo.coordenada(a), mundo.coordenada(b)
        largo = math.dist(pa, pb)
        if largo < 1e-9:
            continue
        ux, uz = (pb[0] - pa[0]) / largo, (pb[1] - pa[1]) / largo
        nx, nz = -uz, ux
        a_lo_largo = math.degrees(math.atan2(-uz, ux))       # el eje x local del objeto sigue la calle
        s = radio_plaza + 0.9 + ENTRADA_PLAZA
        while s < largo - radio_plaza - 0.9 - ENTRADA_PLAZA + 1e-6:
            for lado in (-1, 1):
                indice += 1
                sx = s + (azar_de(indice, 1.7) - 0.5) * 2.6
                tipo = _tipo_por_azar(azar_de(indice * 0.37, 4.1), PESOS_CALLE)
                for extra in (0.0, 1.6, 3.4):
                    d = lado * (semiancho + ACERA + SEPARACION_CALLE + 0.5 * azar_de(indice, 2.9) + extra)
                    x, z = pa[0] + ux * sx + nx * d, pa[1] + uz * sx + nz * d
                    if poner_de_calle(tipo, x, z, 0.0, nx, nz, lado, a_lo_largo, indice):
                        break
            s += PASO_CALLE

    # Alrededor de cada plaza.
    for lugar, (cx, cz) in plazas.items():
        h = suelo(cx, cz) + 0.14
        arranque = 360 * azar_de(cx + 1.1, cz - 0.7)
        # Borde interior: jardineras, farolas bajas y canecas en los arcos libres.
        puestos = 0
        for k in range(16):
            if puestos >= PROPS_POR_PLAZA:
                break
            a = math.radians((arranque + k * 22.5) % 360)
            x, z = cx + RADIO_ANILLO_PLAZA * math.cos(a), cz + RADIO_ANILLO_PLAZA * math.sin(a)
            tipo = ("jardinera", "farola", "jardinera", "caneca", "farola")[puestos % 5]
            giro = math.degrees(math.atan2(-math.sin(a), math.cos(a)))   # su eje x local es tangente al círculo
            if poner(tipo, x, z, giro, 1.0, int(azar_de(x, z) * 997), y=h, en_plaza=True):
                puestos += 1
        # Corona exterior sobre el pasto, entre las calles: árboles, arbustos con flores, vallas y
        # algún cartel. Cada ángulo prueba tres radios.
        puestos = 0
        for k in range(40):
            if puestos >= PROPS_EN_CORONA:
                break
            a = math.radians((arranque + 13 + k * 9 + 7 * (k % 3)) % 360)
            u = azar_de(cx + k * 0.41, cz + k * 0.29)
            variante = int(azar_de(cx + k, cz - k) * 997)
            for extra in (0.0, 2.2, 4.4):
                r = radio_plaza + 2.6 + 3.0 * azar_de(cx + k, cz - k * 0.7) + extra
                x, z = cx + r * math.cos(a), cz + r * math.sin(a)
                tam = 0.9 + 0.35 * azar_de(z, x)
                if u < 0.55:
                    clase = ("redondo", "redondo", "pino", "cipres", "flor", "redondo")[variante % 6]
                    ok = poner("arbol", x, z, 0.0, tam, variante * 10 + ("redondo", "pino", "cipres", "flor").index(clase))
                elif u < 0.93:
                    ok = poner("arbusto", x, z, 0.0, tam, variante)
                elif u < 0.97:
                    ok = poner("valla", x, z, math.degrees(math.atan2(-math.sin(a), math.cos(a))),
                               3.0 + 3.0 * azar_de(x, z), variante)
                else:
                    ok = poner("cartel", x, z, math.degrees(math.atan2(cx - x, cz - z)), 1.0, variante)
                if ok:
                    puestos += 1
                    break
    return props


# -- Armado ---------------------------------------------------------------------------------------


# Dibuja un Prop en las mallas `m` (opaca) y `luz` (focos).
def dibujar(prop, m, luz, suelo=None):
    x, y, z, g, s, v = prop.x, prop.y, prop.z, prop.giro, prop.tam, prop.variante
    if prop.tipo == "arbol":
        clase = v % 10
        if clase == 1:
            arbol_pino(m, x, y, z, s, v // 10)
        elif clase == 2:
            arbol_cipres(m, x, y, z, s, v // 10)
        else:
            arbol_redondo(m, x, y, z, s, v // 10, flor=clase == 3)
    elif prop.tipo == "arbusto":
        arbusto(m, x, y, z, s, v, flores=v % 3 == 0)
    elif prop.tipo == "farola":
        farola(m, luz, x, y, z, 0.8 + 0.2 * s, v)
    elif prop.tipo == "banco":
        banco(m, x, y, z, g, 1.0, v)
    elif prop.tipo == "valla":
        valla(m, x, y, z, g, s, v, suelo)
    elif prop.tipo == "cartel":
        cartel(m, x, y, z, g, 1.0, v)
    elif prop.tipo == "jardinera":
        jardinera(m, x, y, z, g, 1.0, v)
    elif prop.tipo == "caneca":
        caneca(m, x, y, z, 1.0, v)
    elif prop.tipo == "fuente":
        fuente(m, x, y, z, s)


# Las dos mallas del decorado del mundo: (opaca, luces) como Mesh (None si no hay nada).
def construir_props_mundo(mundo):
    opaca, luz = Malla(), Malla()
    for prop in colocar_props(mundo):
        dibujar(prop, opaca, luz, mundo.altura)
    return opaca.mesh(), luz.mesh()


# -- Contorno de tinta de los props grandes (estilo cómic) --------------------------------------------

GROSOR_CONTORNO_PROPS = 0.09     # m que el casco asoma por cada lado de un árbol
CONTORNO_PROPS = ("arbol",)      # tipos de prop que llevan contorno de tinta (la fuente no: sus piezas apiladas dejan huecos negros)
TINTA_PROPS = (0, 0, 0)          # el shader sin luz aclara el casco (gamma): en pantalla sale ~ la tinta (18, 20, 32)


class MallaContorno(Malla):
    """Casco de tinta: cada sólido que se le agrega sale unos cm más grande (en cada eje) y de color tinta. Se dibuja
    con las caras delanteras ocultas, así solo asoma el borde por detrás de la silueta (ver docs/DISENO.md §7)."""

    def __init__(self, grosor=GROSOR_CONTORNO_PROPS):
        super().__init__()
        self.grosor = grosor

    def agregar(self, solido, posicion, escala=1.0, giro=0.0, color=(255, 255, 255), degradado=(0.8, 1.05),
                ruido=0.0, inclinacion=0.0):
        if isinstance(escala, (int, float)):
            escala = (escala, escala, escala)
        super().agregar(solido, posicion, tuple(e + 2 * self.grosor for e in escala), giro, TINTA_PROPS, (1.0, 1.0), 0.0,
                        inclinacion)


# Las tres mallas del decorado: (opaca, luces, contorno) como Mesh (None si no hay nada). La de contorno lleva el casco
# de tinta de los árboles; va en una Entity aparte que solo dibuja caras traseras.
def construir_props_y_contorno(mundo):
    opaca, luz, contorno = Malla(), Malla(), MallaContorno()
    for prop in colocar_props(mundo):
        dibujar(prop, opaca, luz, mundo.altura)
        if prop.tipo in CONTORNO_PROPS:
            dibujar(prop, contorno, Malla(), mundo.altura)
    return opaca.mesh(), luz.mesh(), contorno.mesh()


# -- Cintas de calle con ruido de color -----------------------------------------------------------


# Cinta como la de ciudad_3d._cinta (de s0 a s1 m desde `a` hacia `b`, de d0 a d1 m a la izquierda del
# eje, `alto` m sobre el suelo) pero con `columnas` vértices a lo ancho y un color por vértice: el
# color base `tono` (RGB 0-255) más manchas suaves y un poco de grano de amplitud `amplitud` (niveles
# 0-255). Va con color de entidad blanco: combine() multiplica y conserva los colores por vértice.
def cinta_con_tono(suelo, a, b, s0, s1, d0, d1, alto, tono, amplitud, columnas=4, paso=1.0, lados=0.0):
    from ursina import Mesh
    largo = math.dist(a, b)
    ux, uz = (b[0] - a[0]) / largo, (b[1] - a[1]) / largo
    nx, nz = -uz, ux
    pasos = max(1, math.ceil((s1 - s0) / paso))
    vertices, colores, triangulos = [], [], []
    for k in range(pasos + 1):
        s = s0 + (s1 - s0) * k / pasos
        for c in range(columnas + 1):
            d = d0 + (d1 - d0) * c / columnas
            x, z = a[0] + ux * s + nx * d, a[1] + uz * s + nz * d
            vertices.append((x, suelo(x, z) + alto, z))
            colores.append(color_con_ruido(tono, amplitud, x, z))
    ancho = columnas + 1
    for k in range(pasos):
        for c in range(columnas):
            i = k * ancho + c
            triangulos += [(i, i + 1, i + ancho + 1), (i, i + ancho + 1, i + ancho)]
    if lados > 0:
        for columna in (0, columnas):
            base = len(vertices)
            for k in range(pasos + 1):
                x, y, z = vertices[k * ancho + columna]
                vertices += [(x, y, z), (x, y - lados - 0.05, z)]
                colores += [colores[k * ancho + columna]] * 2
            for k in range(pasos):
                i = base + 2 * k
                triangulos += [(i, i + 2, i + 3), (i, i + 3, i + 1)] if columna else [(i, i + 3, i + 2), (i, i + 1, i + 3)]
    return Mesh(vertices=vertices, triangles=triangulos, colors=colores)


# Color RGBA (0-1) en (x, z): `tono` más manchas amplias, grano fino y un leve cambio de tinte.
def color_con_ruido(tono, amplitud, x, z):
    mancha = ruido_suave(x, z, 6.0) - 0.5
    grano = azar_de(x * 1.9, z * 1.3) - 0.5
    tinte = ruido_suave(x + 40, z - 17, 11.0) - 0.5
    delta = amplitud * (1.1 * mancha + 0.6 * grano)
    r = tono[0] + delta + amplitud * 0.5 * tinte
    g = tono[1] + delta
    b = tono[2] + delta - amplitud * 0.5 * tinte
    return (min(1.0, max(0.0, r / 255)), min(1.0, max(0.0, g / 255)), min(1.0, max(0.0, b / 255)), 1.0)
