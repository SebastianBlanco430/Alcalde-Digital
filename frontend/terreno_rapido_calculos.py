# Color de la ladera, versión rápida (Python puro: NO importa ursina ni panda3d). Mismo resultado BIT A BIT que
# suelo_calculos.MapaTierra.peso_tierra + suelo_calculos.color_ladera (tests/test_cache_arranque.py lo compara en la
# rejilla entera del terreno y en puntos al azar).
#
# Por qué (M7.2): el terreno de la favela pide el color de ~56.000 vértices al arrancar (~2,2 s reales). Dos ahorros,
# ninguno cambia un solo número:
#   1. distancia a calles y plazas: en vez de medir los 13 ejes y 11 plazas en cada vértice, cada celda de 10 m tiene
#      la lista de los que pueden estar a menos de ALCANCE_CALLES. Si el más cercano está más lejos, el peso de las
#      calles es 0,0 exacto de todas formas (la distancia corrida por el ruido sigue por encima del final del fundido,
#      y _suave(>=1) = 1), así que el máximo con el de las casas no cambia.
#   2. color: las mismas operaciones de punto flotante en el mismo orden que color_ladera/color_arena/_mezclar, pero
#      escritas sin tuplas intermedias ni llamadas por componente.
# ALCALDE_TERRENO_RAPIDO=0 (o TERRENO_RAPIDO = False) usa las funciones de siempre.

import math
import os

from frontend import suelo_calculos as sc
from frontend.azar_fijo import azar_de

TERRENO_RAPIDO = True
# Más allá de esta distancia (m) a la calle/plaza el peso de calles es 0: fin del fundido + lo máximo que corre el ruido,
# más 1 m de holgura.
ALCANCE_CALLES = sc.TIERRA_JUNTO_A_CALLES[1] + sc.RUIDO_BORDE_TIERRA + 1.0


def terreno_rapido_activo(valor=None):
    valor = (os.environ.get("ALCALDE_TERRENO_RAPIDO", "") if valor is None else valor).strip().lower()
    if valor in ("1", "true", "si", "sí", "on"):
        return True
    if valor in ("0", "false", "no", "off"):
        return False
    return bool(TERRENO_RAPIDO)


class PesoTierraRapido:
    """peso_tierra(x, z) idéntico al de `mapa` (un suelo_calculos.MapaTierra), con calles y plazas por celdas."""

    def __init__(self, mapa):
        self.mapa = mapa
        self.celda = mapa.celda
        self._cerca = {}          # (i, j) -> (calles, plazas) que pueden quedar a menos de ALCANCE_CALLES de la celda
        self._medio_diagonal = self.celda * math.sqrt(2) / 2

    def _candidatos(self, i, j):
        clave = (i, j)
        hallado = self._cerca.get(clave)
        if hallado is None:
            cx, cz = (i + 0.5) * self.celda, (j + 0.5) * self.celda
            limite = ALCANCE_CALLES + self._medio_diagonal
            calles = [(a, b) for a, b in self.mapa.calles if sc.distancia_punto_segmento(cx, cz, a, b) <= limite]
            plazas = [(px, pz) for px, pz in self.mapa.plazas
                      if math.hypot(cx - px, cz - pz) - self.mapa.radio_plaza <= limite]
            hallado = (calles, plazas)
            self._cerca[clave] = hallado
        return hallado

    def distancia_a_calles(self, x, z):
        calles, plazas = self._candidatos(int(x // self.celda), int(z // self.celda))
        d = min((sc.distancia_punto_segmento(x, z, a, b) for a, b in calles), default=99.0)
        return min(d, min((math.hypot(x - px, z - pz) - self.mapa.radio_plaza for px, pz in plazas), default=99.0))

    def peso_tierra(self, x, z):
        corrimiento = (_ruido(x + 7.0, z + 3.0, 6.0) - 0.5) * 2 * sc.RUIDO_BORDE_TIERRA
        w_casas = sc.peso_por_distancia(self.mapa.distancia_a_casas(x, z) + corrimiento, *sc.TIERRA_JUNTO_A_CASAS)
        w_calles = sc.peso_por_distancia(self.distancia_a_calles(x, z) + corrimiento, *sc.TIERRA_JUNTO_A_CALLES)
        return max(w_casas, w_calles)


# ruido_suave(x, z, escala) con las 4 esquinas de cada celda guardadas: mismas operaciones, mismo número.
_esquinas = {}          # (escala, ix, iz) -> (a, b, c, d)
_floor = math.floor


def _ruido(x, z, escala):
    gx, gz = x / escala, z / escala
    ix, iz = _floor(gx), _floor(gz)
    fx, fz = gx - ix, gz - iz
    fx, fz = fx * fx * (3 - 2 * fx), fz * fz * (3 - 2 * fz)
    clave = (escala, ix, iz)
    e = _esquinas.get(clave)
    if e is None:
        if len(_esquinas) > 400_000:
            _esquinas.clear()
        e = (azar_de(ix + 0.37, iz + 0.71), azar_de(ix + 1.37, iz + 0.71),
             azar_de(ix + 0.37, iz + 1.71), azar_de(ix + 1.37, iz + 1.71))
        _esquinas[clave] = e
    a, b, c, d = e
    return (a + (b - a) * fx) * (1 - fz) + (c + (d - c) * fx) * fz


def _suave(t):
    t = min(1.0, max(0.0, t))
    return t * t * (3 - 2 * t)


_PF, _PS = sc.PASTO_FAVELA, sc.PASTO_SECO
_AC, _AM, _AR, _TO, _CT = sc.ARENA_CLARA, sc.ARENA_MEDIA, sc.ARENA_ROJIZA, sc.TIERRA_OSCURA, sc.COLOR_TALUD


def color_ladera(x, z, tierra, talud):
    """Igual que suelo_calculos.color_ladera (RGB 0-1 con brillo), operación por operación."""
    mancha = _ruido(x, z, 13.0) - 0.5
    t = _suave(_ruido(x - 9.0, z + 21.0, 15.0) * 1.5 - 0.3)
    p0 = _PF[0] + (_PS[0] - _PF[0]) * t
    p1 = _PF[1] + (_PS[1] - _PF[1]) * t
    p2 = _PF[2] + (_PS[2] - _PF[2]) * t
    f = (1 + 0.16 * mancha + 0.08 * (azar_de(x * 1.7, z * 2.3) - 0.5))
    p0, p1, p2 = p0 * f, p1 * f, p2 * f
    # color_arena(x, z)
    m = _ruido(x + 17.0, z - 5.0, 9.0)
    parche = _ruido(x - 31.0, z + 11.0, 3.2)
    grano = azar_de(x * 2.3, z * 1.7) - 0.5
    t = _suave(m * 1.6 - 0.1)
    b0 = _AC[0] + (_AM[0] - _AC[0]) * t
    b1 = _AC[1] + (_AM[1] - _AC[1]) * t
    b2 = _AC[2] + (_AM[2] - _AC[2]) * t
    t = _suave((parche - 0.55) * 3.0) * 0.8
    b0 = b0 + (_AR[0] - b0) * t
    b1 = b1 + (_AR[1] - b1) * t
    b2 = b2 + (_AR[2] - b2) * t
    g = 1.0 + 0.08 * grano
    b0, b1, b2 = b0 * g, b1 * g, b2 * g
    # mezcla con la tierra roja de la ladera
    t = sc.TIERRA_ROJA_LADERA
    b0 = b0 + (_AR[0] - b0) * t
    b1 = b1 + (_AR[1] - b1) * t
    b2 = b2 + (_AR[2] - b2) * t
    t = _suave(tierra * 1.15)
    s0 = p0 + (b0 - p0) * t
    s1 = p1 + (b1 - p1) * t
    s2 = p2 + (b2 - p2) * t
    t = _suave((_ruido(x + 2.0, z - 8.0, 2.6) - 0.6) * 3.5) * 0.35 * tierra
    s0 = s0 + (_TO[0] - s0) * t
    s1 = s1 + (_TO[1] - s1) * t
    s2 = s2 + (_TO[2] - s2) * t
    t = _suave(talud)
    s0 = s0 + (_CT[0] - s0) * t
    s1 = s1 + (_CT[1] - s1) * t
    s2 = s2 + (_CT[2] - s2) * t
    k = sc.BRILLO_SUELO
    return (min(1.0, s0 * k / 255), min(1.0, s1 * k / 255), min(1.0, s2 * k / 255))
