# Mallas de las piezas del TALLER 3D (frontend/taller3d_escena.py), hechas por código con los sólidos de props_mundo
# (caja, prisma, anillo, icosfera) en una sola Malla con color por vértice (una llamada de dibujo por pieza).
# Repertorio y variantes de material: backend/datos/piezas_taller.PIEZAS_TALLER_3D (mismo `id` que aquí).
#
# Cada pieza es una lista de PARTES en orden de forja: con el progreso del turno las primeras salen con su color y el
# resto en hierro en bruto (taller3d_calculos.SILUETA). La calidad decide el acabado (taller3d_calculos): prístina =
# colores limpios y brillo en las caras de arriba; mala = malla deformada (ruido suave), abolladuras por cada golpe malo
# y color oxidado. Coordenadas de la pieza: ~1 de lado, y = 0 sobre el banco, la cara de -z mira al personaje.
# Sin ursina al construir (la Malla es Python puro): se prueba en tests/test_taller3d_calculos.py.

import math

from frontend import taller3d_calculos as tc
from frontend.props_mundo import Malla, anillo, caja, icosfera, prisma

ACERO = (150, 156, 170)
ACERO_CLARO = (196, 202, 214)
OSCURO = (66, 68, 78)
GOMA = (38, 38, 44)
MADERA = (140, 96, 58)
CRISTAL = (252, 238, 176)
MAX_ABOLLADURAS = 12
DEGRADADO = (0.82, 1.06)


def _engranaje(t):
    p = [(anillo(24, 0.5, 0.22), (0, 0, 0), (0.8, 0.14, 0.8), 0, t, 0)]
    for k in range(12):
        a = 30.0 * k
        r = math.radians(a)
        p.append((caja(), (0.44 * math.sin(r), 0.07, 0.44 * math.cos(r)), (0.11, 0.14, 0.12), a, t, 0))
    p.append((prisma(12), (0, 0, 0), (0.3, 0.2, 0.3), 0, OSCURO, 0))
    p.append((prisma(10), (0, 0.01, 0), (0.12, 0.2, 0.12), 0, GOMA, 0))
    return p


def _llave(t):
    return [
        (caja(), (0, 0.03, -0.12), (0.13, 0.06, 0.62), 0, t, 0),
        (anillo(14, 0.5, 0.3), (0, 0, -0.47), (0.16, 0.06, 0.16), 0, t, 0),
        (caja(), (0.02, 0.035, 0.24), (0.3, 0.07, 0.16), 0, ACERO_CLARO, 0),
        (caja(), (-0.11, 0.035, 0.4), (0.08, 0.07, 0.2), 0, ACERO_CLARO, 0),
        (caja(), (0.1, 0.035, 0.37), (0.08, 0.07, 0.15), 0, ACERO_CLARO, 0),
        (prisma(10), (-0.08, 0.035, 0.2), (0.06, 0.16, 0.06), 90, OSCURO, 90),
    ]


def _tuerca(t):
    p = [(anillo(6, 0.5, 0.25), (0.24, 0, 0.12), (0.36, 0.16, 0.36), 0, t, 0),
         (anillo(16, 0.5, 0.3), (0.24, 0, -0.26), (0.3, 0.03, 0.3), 0, ACERO_CLARO, 0),
         (prisma(6), (-0.2, 0.14, -0.38), (0.28, 0.12, 0.28), 0, t, 90),
         (prisma(12), (-0.2, 0.14, -0.27), (0.14, 0.62, 0.14), 0, t, 90)]
    for k in range(6):
        p.append((anillo(12, 0.5, 0.38), (-0.2, 0.14, -0.15 + 0.08 * k), (0.17, 0.025, 0.17), 0, ACERO, 90))
    return p


def _piston(t):
    p = [(prisma(18), (0, 0, 0), (0.5, 0.44, 0.5), 0, t, 0)]
    for y in (0.3, 0.35, 0.4):
        p.append((anillo(18, 0.5, 0.47), (0, y, 0), (0.52, 0.03, 0.52), 0, OSCURO, 0))
    p += [(prisma(18, 0.5, 0.46), (0, 0.44, 0), (0.5, 0.06, 0.5), 0, t, 0),
          (prisma(10), (-0.29, 0.18, 0), (0.1, 0.58, 0.1), 90, ACERO_CLARO, 90),
          (caja(), (0, 0.025, -0.52), (0.12, 0.05, 0.42), 0, ACERO, 0),
          (anillo(14, 0.5, 0.3), (0, 0, -0.76), (0.26, 0.06, 0.26), 0, ACERO, 0)]
    return p


def _bisagra(t):
    p = [(caja(), (-0.21, 0.015, 0), (0.38, 0.03, 0.62), 0, t, 0),
         (caja(), (0.21, 0.015, 0), (0.38, 0.03, 0.62), 0, t, 0)]
    for k in range(3):
        p.append((prisma(12), (0, 0.045, -0.31 + 0.21 * k), (0.09, 0.19, 0.09), 0, t if k % 2 else ACERO, 90))
    p.append((prisma(8), (0, 0.045, -0.33), (0.035, 0.66, 0.035), 0, OSCURO, 90))
    for x in (-0.3, 0.3):
        for z in (-0.18, 0.0, 0.18):
            p.append((prisma(10, 0.5, 0.4), (x, 0.03, z), (0.07, 0.02, 0.07), 0, OSCURO, 0))
    return p


def _rueda(t):
    p = [(anillo(32, 0.5, 0.44), (0, 0, 0), (1.0, 0.07, 1.0), 0, GOMA, 0),
         (anillo(32, 0.5, 0.45), (0, 0.003, 0), (0.88, 0.075, 0.88), 0, t, 0),
         (prisma(12), (0, -0.02, 0), (0.1, 0.12, 0.1), 0, ACERO, 0)]
    for k in range(12):
        a = 30.0 * k + 15
        r = math.radians(a)
        p.append((caja(), (0.2 * math.sin(r), 0.04, 0.2 * math.cos(r)), (0.012, 0.012, 0.36), a, ACERO_CLARO, 0))
    p.append((caja(), (0.0, 0.05, -0.41), (0.02, 0.06, 0.05), 0, OSCURO, 0))
    return p


def _lampara(t):
    return [
        (prisma(16, 0.5, 0.45), (0, 0, 0), (0.42, 0.06, 0.42), 0, t, 0),
        (caja(), (0.12, 0.07, -0.08), (0.06, 0.03, 0.04), 0, OSCURO, 0),
        (caja(), (0, 0.26, 0), (0.04, 0.4, 0.04), 0, OSCURO, 0),
        (icosfera(0), (0, 0.46, 0), (0.07, 0.07, 0.07), 0, OSCURO, 0),
        (caja(), (0, 0.46, 0.12), (0.04, 0.04, 0.25), 0, OSCURO, 0),
        (icosfera(1), (0, 0.36, 0.26), (0.12, 0.12, 0.12), 0, CRISTAL, 0),
        (prisma(16, 0.5, 0.22), (0, 0.34, 0.26), (0.36, 0.2, 0.36), 0, t, 0),
    ]


def _radio(t):
    p = [(caja(), (0, 0.23, 0), (0.8, 0.46, 0.34), 0, t, 0),
         (prisma(18), (-0.18, 0.22, -0.17), (0.3, 0.02, 0.3), 0, OSCURO, -90),
         (caja(), (0.2, 0.31, -0.175), (0.24, 0.1, 0.02), 0, CRISTAL, 0)]
    for x in (0.14, 0.26):
        p.append((prisma(10), (x, 0.13, -0.17), (0.07, 0.03, 0.07), 0, OSCURO, -90))
    p += [(caja(), (0, 0.5, 0), (0.42, 0.03, 0.04), 0, OSCURO, 0),
          (caja(), (-0.2, 0.48, 0), (0.03, 0.06, 0.04), 0, OSCURO, 0),
          (caja(), (0.2, 0.48, 0), (0.03, 0.06, 0.04), 0, OSCURO, 0),
          (caja(), (0.32, 0.66, 0.08), (0.02, 0.42, 0.02), 0, ACERO_CLARO, -20)]
    return p


PARTES = {"engranaje": _engranaje, "llave": _llave, "tuerca": _tuerca, "piston": _piston, "bisagra": _bisagra,
          "rueda": _rueda, "lampara": _lampara, "radio": _radio}


def partes(pieza):
    """Partes de la pieza (lista de (sólido, posición, escala, giro, color, inclinación)). Id desconocido = engranaje."""
    return PARTES.get(getattr(pieza, "id", None), _engranaje)(tuple(getattr(pieza, "tono", ACERO)))


def construir(pieza, progreso=1.0, calidad=1.0, errores=0, semilla=0):
    """Malla de la pieza con `progreso` (0..1) forjado, el acabado de `calidad` y una abolladura por golpe malo."""
    lista = partes(pieza)
    hechas = tc.partes_hechas(progreso, len(lista))
    m = Malla()
    for i, (solido, pos, escala, giro, tono, inclinacion) in enumerate(lista):
        c = tc.tono_final(tono, calidad) if i < hechas else tc.SILUETA
        m.agregar(solido, pos, escala, giro, c, DEGRADADO, 0.0, inclinacion)
    centros = tc.abolladuras(min(MAX_ABOLLADURAS, errores), semilla)
    deformar(m, tc.grado_deformacion(calidad), centros, semilla)
    realzar(m, tc.brillo(calidad))
    return m


def deformar(m, grado, centros, semilla=0):
    """Mueve los vértices de `m` (ruido suave + abolladuras) y rehace sus normales planas. Nada que hacer = no toca."""
    if grado <= 0 and not centros:
        return m
    nuevos = []
    for x, y, z in m.vertices:
        dx, dy, dz = tc.desplazamiento(x, y, z, grado, semilla)
        dy += tc.hundimiento(x, y, z, centros)
        nuevos.append((x + dx, max(-0.02, y + dy), z + dz))
    m.vertices = nuevos
    normales = []
    for i in range(0, len(nuevos), 3):
        pa, pb, pc = nuevos[i], nuevos[i + 1], nuevos[i + 2]
        u = (pc[0] - pa[0], pc[1] - pa[1], pc[2] - pa[2])
        v = (pb[0] - pa[0], pb[1] - pa[1], pb[2] - pa[2])
        n = (u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0])
        largo = math.sqrt(n[0] ** 2 + n[1] ** 2 + n[2] ** 2) or 1.0
        normales += [(n[0] / largo, n[1] / largo, n[2] / largo)] * 3
    m.normales = normales
    return m


def realzar(m, brillo):
    """Brillo de pieza bien hecha: aclara las caras que miran arriba (reflejo de la bombilla del taller)."""
    if brillo <= 0:
        return m
    colores = []
    for (r, g, b, a), (_, ny, _) in zip(m.colores, m.normales):
        f = 1 + 0.45 * brillo * max(0.0, ny)
        colores.append((min(1.5, r * f), min(1.5, g * f), min(1.5, b * f), a))
    m.colores = colores
    return m


def medidas(m):
    """(centro (x, y, z), lado mayor) de la caja que envuelve la malla (para encuadrarla en el panel de resultado)."""
    if not m.vertices:
        return (0.0, 0.0, 0.0), 1.0
    xs, ys, zs = zip(*m.vertices)
    centro = ((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2, (min(zs) + max(zs)) / 2)
    return centro, max(max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs)) or 1.0
