# Becos del mapa grande (datos puros, sin ursina): pasajes peatonales de 2,5 a 3,5 m que salen de una calle y suben la
# ladera en polilínea (2 a 4 tramos), con Escalera en los tramos donde el suelo sube. Se generan ANTES de las casas y se
# agregan como líneas libres al despeje, así las casas les dejan paso. No añaden nodos al grafo de calles.
#
# Es determinista: mismo mapa, mismo terreno y misma semilla -> mismos becos (azar propio random.Random).

import math
import random
from dataclasses import dataclass

from backend.datos import terreno as _t
from backend.datos.ciudad_3d import BORDE_LADERA, _distancia_entre_segmentos
from backend.logica.mundo_ciudad import Escalera, _distancia_punto_caja, _distancia_segmento_caja

ANCHO_BECO = (2.5, 3.5)           # m
TRAMO_BECO = (10.0, 16.0)         # m de cada tramo de la polilínea
TRAMOS_BECO = (2, 4)
SEPARACION_BECOS = 34.0           # m medios entre becos a lo largo de una calle
DESNIVEL_ESCALERA_BECO = 1.0      # m: un tramo que sube al menos esto lleva escalera
PENDIENTE_MAXIMA_TRAMO = 0.9      # |desnivel| / largo máximo de un tramo (~42 grados)
GIRO_MAXIMO = math.radians(35)
LARGO_MINIMO = 12.0               # m: un beco más corto no se crea
DESPEJE_LATERAL = 1.2             # m libres que las casas dejan junto al eje (ver _Despeje)


@dataclass(frozen=True)
class Beco:
    """Pasaje peatonal: polilínea `puntos` ((x, z), ...), `ancho` libre en m y las Escalera de sus tramos."""

    puntos: tuple
    ancho: float
    escaleras: tuple = ()

    @property
    def largo(self):
        return sum(math.dist(a, b) for a, b in zip(self.puntos, self.puntos[1:]))

    def tramos(self):
        return list(zip(self.puntos, self.puntos[1:]))


def _unitario(v):
    n = math.hypot(*v)
    return (v[0] / n, v[1] / n)


def _girar(v, ang):
    c, s = math.cos(ang), math.sin(ang)
    return (v[0] * c - v[1] * s, v[0] * s + v[1] * c)


def _lineas_cercanas(despeje, a, b, m):
    idx = getattr(despeje, "_lineas_idx", None)
    if idx is None:
        return list(despeje.lineas())
    x0, x1 = min(a[0], b[0]) - m, max(a[0], b[0]) + m
    z0, z1 = min(a[1], b[1]) - m, max(a[1], b[1]) + m
    lineas = despeje._lineas
    return [lineas[k] for k in sorted(idx.cerca(x0, x1, z0, z1))]


def _cajas_cercanas(despeje, a, b, m):
    idx = getattr(despeje, "_edificios_idx", None)
    cajas = getattr(despeje, "_edificios", [])
    if idx is None:
        return [(o.cx - o.ancho / 2, o.cx + o.ancho / 2, o.cz - o.fondo / 2, o.cz + o.fondo / 2) for o in cajas]
    x0, x1 = min(a[0], b[0]) - m, max(a[0], b[0]) + m
    z0, z1 = min(a[1], b[1]) - m, max(a[1], b[1]) + m
    return [(o.cx - o.ancho / 2, o.cx + o.ancho / 2, o.cz - o.fondo / 2, o.cz + o.fondo / 2)
            for o in (cajas[k] for k in sorted(idx.cerca(x0, x1, z0, z1)))]


def _tramo_libre(a, b, h, mapa, despeje, calles, propia, primero, limites):
    x0, x1, z0, z1 = limites
    if not (x0 <= b[0] <= x1 and z0 <= b[1] <= z1):
        return False
    plaza = mapa.radio_plaza + 0.9 + h
    for lugar in mapa.lugares():
        if _punto_segmento(mapa.coordenada(lugar), a, b) < plaza:
            return False
    calle_min = mapa.ancho_calle / 2 + 2.0 + h
    es_calle = set(calles)
    for p, q in _lineas_cercanas(despeje, a, b, calle_min + 1.0):
        if (p, q) in es_calle:
            if (p, q) == propia and primero:
                continue
            minimo = calle_min if (p, q) != propia else calle_min + 0.5
        else:
            minimo = h + 1.5
        if _distancia_entre_segmentos(a, b, p, q) < minimo:
            return False
    for caja in _cajas_cercanas(despeje, a, b, h + 3.0):
        if _distancia_segmento_caja(a, b, caja) < h + 1.0:
            return False
    return True


def _tiene_talud(terreno, a, b, largo):
    """¿Algún punto (cada ~1 m) del tramo a-b tiene una pendiente no caminable (o casi)? Un tramo puede subir poco en
    total y aun así cruzar un escalón empinado: sin escalera ese punto cortaría el beco (F4)."""
    caminable = getattr(terreno, "caminable", None)
    if caminable is None:
        return False
    n = max(1, int(math.ceil(largo)))
    for k in range(n + 1):
        t = k / n
        x, z = a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t
        if not caminable(x, z) or not caminable(x + 0.5, z) or not caminable(x - 0.5, z) \
                or not caminable(x, z + 0.5) or not caminable(x, z - 0.5):
            return True
    return False


def _punto_segmento(p, a, b):
    dx, dz = b[0] - a[0], b[1] - a[1]
    l2 = dx * dx + dz * dz
    t = 0.0 if l2 < 1e-12 else min(1.0, max(0.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dz) / l2))
    return math.hypot(p[0] - (a[0] + dx * t), p[1] - (a[1] + dz * t))


def generar_becos(mapa, terreno, despeje, semilla, separacion=SEPARACION_BECOS):
    """Becos que salen de las calles del `mapa` y suben la ladera del `terreno` (necesita `altura` y `extension`).
    Cada beco aceptado se agrega a `despeje` (eje y, si es ancho, dos líneas laterales) para que las casas le dejen
    paso. Devuelve list[Beco] en un orden fijo (calle a calle, de un extremo al otro)."""
    azar = random.Random(semilla + 31337)
    calles = [(mapa.coordenada(a), mapa.coordenada(b)) for a, b in mapa.segmentos()]
    sube = _unitario(_t.DIRECCION_SUBIDA)
    ex0, ex1, ez0, ez1 = terreno.extension
    limites = (ex0 + BORDE_LADERA, ex1 - BORDE_LADERA, ez0 + BORDE_LADERA, ez1 - BORDE_LADERA)
    arranque = mapa.ancho_calle / 2 + 2.0
    margen = mapa.radio_plaza + 4.0
    becos = []
    for pa, pb in calles:
        largo = math.dist(pa, pb)
        if largo < 2 * margen + 8:
            continue
        u = ((pb[0] - pa[0]) / largo, (pb[1] - pa[1]) / largo)
        s = margen + azar.uniform(2.0, separacion * 0.6)
        alterna = azar.choice((-1, 1))
        while s <= largo - margen:
            lado = alterna
            alterna = -alterna
            n = (-u[1] * lado, u[0] * lado)
            if n[0] * sube[0] + n[1] * sube[1] < -0.15:
                lado, n = -lado, (-n[0], -n[1])          # sale por el lado cuesta arriba
            beco = _intentar_beco(azar, mapa, terreno, despeje, calles, (pa, pb), u, s, n, arranque, sube, limites)
            if beco is not None:
                becos.append(beco)
            s += separacion * azar.uniform(0.8, 1.3)
    return becos


def _intentar_beco(azar, mapa, terreno, despeje, calles, propia, u, s, n, arranque, sube, limites):
    pa = propia[0]
    ancho = round(azar.uniform(*ANCHO_BECO), 1)
    h = ancho / 2 + 1.0
    inicio = (round(pa[0] + u[0] * s + n[0] * arranque, 2), round(pa[1] + u[1] * s + n[1] * arranque, 2))
    direccion = n
    puntos, escaleras = [inicio], []
    tramos = azar.randint(*TRAMOS_BECO)
    for k in range(tramos):
        # el rumbo se corre hacia la subida y un giro al azar; el primer tramo sale perpendicular a la calle
        if k > 0:
            mezcla = _unitario((direccion[0] * 0.6 + sube[0] * 0.4, direccion[1] * 0.6 + sube[1] * 0.4))
            direccion = _girar(mezcla, azar.uniform(-GIRO_MAXIMO, GIRO_MAXIMO))
        largo = azar.uniform(*TRAMO_BECO)
        a = puntos[-1]
        b = (round(a[0] + direccion[0] * largo, 2), round(a[1] + direccion[1] * largo, 2))
        if not _tramo_libre(a, b, h, mapa, despeje, calles, propia, k == 0, limites):
            break
        ha, hb = terreno.altura(*a), terreno.altura(*b)
        if abs(hb - ha) / largo > PENDIENTE_MAXIMA_TRAMO:
            break
        puntos.append(b)
        if abs(hb - ha) >= DESNIVEL_ESCALERA_BECO or _tiene_talud(terreno, a, b, largo):
            e_ancho = round(max(0.9, min(1.4, ancho - 0.6)), 2)
            escaleras.append(Escalera(a[0], a[1], b[0], b[1], e_ancho))
    if len(puntos) < 2 or sum(math.dist(p, q) for p, q in zip(puntos, puntos[1:])) < LARGO_MINIMO:
        return None
    beco = Beco(tuple(puntos), ancho, tuple(escaleras))
    for a, b in beco.tramos():
        despeje.agregar_linea(a, b)
        lateral = ancho / 2 - DESPEJE_LATERAL
        if lateral > 0.05:
            l = math.dist(a, b)
            nx, nz = -(b[1] - a[1]) / l * lateral, (b[0] - a[0]) / l * lateral
            despeje.agregar_linea((round(a[0] + nx, 2), round(a[1] + nz, 2)), (round(b[0] + nx, 2), round(b[1] + nz, 2)))
            despeje.agregar_linea((round(a[0] - nx, 2), round(a[1] - nz, 2)), (round(b[0] - nx, 2), round(b[1] - nz, 2)))
    return beco
