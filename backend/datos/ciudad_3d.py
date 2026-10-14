# Ciudad Nova en 3D (datos puros): el mapa de ejemplo a escala real, los 7 edificios
# ubicados a mano y los obstáculos decorativos (árboles del parque, farolas, bancos).
#
# Escala: 1 unidad = 1 metro. Las coordenadas del grafo del ejemplo se multiplican por
# ESCALA_MUNDO (4); calles de 8 m y plazas de radio 9 m. Los spawns de los roles
# (roles.py guarda los del mapa pequeño) se escalan con la misma constante.
#
# Cada edificio queda en el lado LIBRE de su plaza (donde no sale ninguna calle), con su
# puerta mirando al centro de la plaza. MundoCiudad valida en su constructor que ninguno
# tape una plaza ni una calle. Los obstáculos decorativos se generan por reglas y se
# descartan si estorbarían: ninguno se acerca a menos de 1.2 m del eje de una calle, del
# camino plaza -> puerta ni de un spawn, así que los recorridos siempre están despejados.

import math
from pathlib import Path

from backend.grafos.grafo_ciudad import construir_grafo_ciudad_ejemplo
from backend.grafos.mapa_ciudad import COORDENADAS_EJEMPLO, MapaCiudad, _distancia_punto_segmento
from backend.logica.mundo_ciudad import (
    Edificio,
    MundoCiudad,
    Obstaculo,
    _distancia_punto_caja,
    _distancia_segmento_caja,
    limites_con_edificios,
)
from backend.logica.roles import ROLES
from backend.logica.terreno import PENDIENTE_MAXIMA_CALLE, Terreno

ESCALA_MUNDO = 4
ANCHO_CALLE = 8
RADIO_PLAZA = 9
MARGEN_EDIFICIOS = 4.0      # m de pasto transitable alrededor de los edificios del borde

ESPACIO_LIBRE = 1.2         # m mínimos entre un obstáculo y las líneas que deben quedar libres
ESPACIO_EDIFICIO = 1.0      # m mínimos entre un obstáculo decorativo y un edificio

# -- Terreno ------------------------------------------------------------------------------------
# Ladera: la Alcaldía y la Plaza Central están abajo; el Barrio Las Flores y el Hospital, arriba.
# Cada lugar (su plaza y su edificio) queda sobre una plataforma plana a esta cota (metros sobre
# la Alcaldía). Las calles suben en rampa lineal entre las cotas de sus dos lugares: con ~12-17 m
# de rampa por calle, 2 m de desnivel ya son ~14 %. Si cambias una cota y una calle supera
# PENDIENTE_MAXIMA_CALLE, construir_mundo_3d() lanza ValueError con la calle y su pendiente.
ELEVACION_LUGAR = {
    "Alcaldía": 0.0,                      # abajo: el centro cívico, plaza lisa
    "Plaza Central": 1.5,                 # 12 % hasta la Alcaldía
    "Terminal de Buses": 3.0,             # 9 % desde la Plaza Central
    "Universidad de Ciudad Nova": 3.5,    # 12 % desde la Plaza Central
    "Parque Municipal": 5.0,              # 11 % desde la Universidad
    "Barrio Las Flores": 5.0,             # 14 % desde la Terminal; a nivel con el Parque
    "Hospital Las Flores": 7.0,           # 14 % desde Las Flores: lo más alto
}
TERRENO_ACTIVO = True                     # False: suelo plano de siempre (altura 0 en todas partes)
SEMILLA_TERRENO = 2026
AMPLITUD_ONDULACION = 0.6                 # m de ondulación suave de la ladera natural
# Si existe, este PNG en escala de grises reemplaza la ladera procedural: gris 0 -> primer valor,
# gris 255 -> segundo valor (metros). Calles, plazas y edificios siguen a ELEVACION_LUGAR.
RUTA_HEIGHTMAP = Path(__file__).resolve().parents[2] / "assets" / "terreno" / "heightmap.png"
HEIGHTMAP_METROS = (0.0, 10.0)

# (lugar, cx, cz, ancho en x, fondo en z, alto, lado de la puerta, nombre del letrero)
_EDIFICIOS = (
    ("Plaza Central", -3, 18, 12, 10, 7, "s", "Café Internet de la Plaza"),
    ("Alcaldía", -32, 18, 14, 10, 9, "s", ""),
    ("Universidad de Ciudad Nova", 24, 46, 14, 12, 10, "s", ""),
    ("Parque Municipal", 74, 20, 12, 12, 6, "o", "Biblioteca del Parque"),
    ("Barrio Las Flores", 40, -8.5, 12, 12, 6, "e", ""),
    ("Terminal de Buses", 24, -46, 14, 12, 6, "n", ""),
    ("Hospital Las Flores", 84, -18, 14, 12, 9, "s", ""),
)


def _construir_mapa():
    coordenadas = {lugar: (x * ESCALA_MUNDO, z * ESCALA_MUNDO) for lugar, (x, z) in COORDENADAS_EJEMPLO.items()}
    return MapaCiudad(construir_grafo_ciudad_ejemplo(), coordenadas,
                      ancho_calle=ANCHO_CALLE, radio_plaza=RADIO_PLAZA)


def _construir_edificios():
    return [Edificio(lugar, cx, cz, ancho, fondo, alto, lado, nombre)
            for lugar, cx, cz, ancho, fondo, alto, lado, nombre in _EDIFICIOS]


def _spawns():
    return {rol: (info.spawn_x * ESCALA_MUNDO, info.spawn_y * ESCALA_MUNDO) for rol, info in ROLES.items()}


# -- Reglas de despeje ------------------------------------------------------------------------


def _lineas_libres(mapa, edificios):
    """Segmentos que deben poder recorrerse: ejes de calle y plaza -> entrada -> puerta."""
    lineas = [(mapa.coordenada(a), mapa.coordenada(b)) for a, b in mapa.segmentos()]
    for e in edificios:
        centro = mapa.coordenada(e.lugar)
        lineas.append((centro, e.punto_entrada()))
        lineas.append((e.punto_entrada(), e.puerta()))
    return lineas


def _distancia_a_segmento(obstaculo, a, b):
    if obstaculo.es_circulo:
        return _distancia_punto_segmento((obstaculo.cx, obstaculo.cz), a, b) - obstaculo.radio
    return _distancia_segmento_caja(a, b, _caja(obstaculo))


def _distancia_a_punto(obstaculo, x, z):
    if obstaculo.es_circulo:
        return math.hypot(x - obstaculo.cx, z - obstaculo.cz) - obstaculo.radio
    return _distancia_punto_caja(x, z, _caja(obstaculo))


def _caja(o):
    return (o.cx - o.ancho / 2, o.cx + o.ancho / 2, o.cz - o.fondo / 2, o.cz + o.fondo / 2)


class _Despeje:
    """Decide si un obstáculo decorativo estorba algún recorrido, un spawn o un edificio."""

    def __init__(self, mapa, edificios, spawns):
        self._lineas = _lineas_libres(mapa, edificios)
        self._spawns = list(spawns.values())
        self._edificios = [e.como_obstaculo() for e in edificios]

    def permite(self, obstaculo):
        if any(_distancia_a_segmento(obstaculo, a, b) < ESPACIO_LIBRE for a, b in self._lineas):
            return False
        if any(_distancia_a_punto(obstaculo, x, z) < ESPACIO_LIBRE for x, z in self._spawns):
            return False
        return all(_separacion_con_edificio(obstaculo, e) >= ESPACIO_EDIFICIO
                   for e in self._edificios)


def _separacion_con_edificio(obstaculo, caja_edificio):
    """Distancia entre el borde de `obstaculo` y la caja de un edificio."""
    caja = _caja(caja_edificio)
    if obstaculo.es_circulo:
        return _distancia_punto_caja(obstaculo.cx, obstaculo.cz, caja) - obstaculo.radio
    # caja contra caja alineadas: separación en cada eje (0 si se solapan en ese eje)
    ox, oz = _caja(obstaculo)[:2], _caja(obstaculo)[2:]
    dx = max(caja[0] - ox[1], ox[0] - caja[1], 0)
    dz = max(caja[2] - oz[1], oz[0] - caja[3], 0)
    return math.hypot(dx, dz)


# -- Decoración ------------------------------------------------------------------------------------


def _bancos(mapa, despeje):
    """Dos bancos por plaza, a 6 m del centro, separados al menos 90 grados."""
    bancos = []
    for lugar in mapa.lugares():
        cx, cz = mapa.coordenada(lugar)
        elegidos = []
        for grados in range(15, 360, 30):
            if any(abs((grados - g + 180) % 360 - 180) < 90 for g in elegidos):
                continue
            a = math.radians(grados)
            banco = Obstaculo("banco", round(cx + 6 * math.cos(a), 3), round(cz + 6 * math.sin(a), 3),
                              ancho=1.8, fondo=0.7)
            if despeje.permite(banco):
                elegidos.append(grados)
                bancos.append(banco)
            if len(elegidos) == 2:
                break
    return bancos


def _arboles_parque(mapa, despeje):
    cx, cz = mapa.coordenada("Parque Municipal")
    arboles = []
    for radio_anillo in (12.5, 16.0):
        for grados in range(0, 360, 20):
            a = math.radians(grados + (10 if radio_anillo > 14 else 0))
            arbol = Obstaculo("arbol", round(cx + radio_anillo * math.cos(a), 3),
                              round(cz + radio_anillo * math.sin(a), 3), radio=0.6)
            if despeje.permite(arbol):
                arboles.append(arbol)
    return arboles


def _farolas(mapa, despeje):
    """Farolas a lo largo de cada calle, alternando lados, a 0.8 m del borde del asfalto."""
    farolas = []
    desfase = mapa.ancho_calle / 2 + 0.8
    margen = mapa.radio_plaza + 3
    for a, b in mapa.segmentos():
        (ax, az), (bx, bz) = mapa.coordenada(a), mapa.coordenada(b)
        largo = math.dist((ax, az), (bx, bz))
        ux, uz = (bx - ax) / largo, (bz - az) / largo
        lado = 1
        s = margen
        while s <= largo - margen:
            farola = Obstaculo("farola", round(ax + ux * s - uz * lado * desfase, 3),
                               round(az + uz * s + ux * lado * desfase, 3), radio=0.2)
            if despeje.permite(farola):
                farolas.append(farola)
            lado = -lado
            s += 8
    return farolas


# -- Fábrica ------------------------------------------------------------------------------------------


def construir_mundo_3d():
    mapa = _construir_mapa()
    edificios = _construir_edificios()
    spawns = _spawns()
    despeje = _Despeje(mapa, edificios, spawns)
    obstaculos = _bancos(mapa, despeje) + _arboles_parque(mapa, despeje) + _farolas(mapa, despeje)
    terreno = _construir_terreno(mapa, edificios) if TERRENO_ACTIVO else None
    return MundoCiudad(mapa, edificios, obstaculos, spawns=spawns, margen_edificios=MARGEN_EDIFICIOS,
                       terreno=terreno)


# Terreno de ladera del mapa. ValueError si alguna calle supera PENDIENTE_MAXIMA_CALLE.
def _construir_terreno(mapa, edificios):
    limites = limites_con_edificios(mapa, edificios, MARGEN_EDIFICIOS)
    heightmap = RUTA_HEIGHTMAP if RUTA_HEIGHTMAP.is_file() else None
    terreno = Terreno.desde_mundo(mapa, edificios, ELEVACION_LUGAR, limites, semilla=SEMILLA_TERRENO,
                                  amplitud=AMPLITUD_ONDULACION, ruta_heightmap=heightmap,
                                  heightmap_metros=HEIGHTMAP_METROS)
    terreno.validar_calles(PENDIENTE_MAXIMA_CALLE)
    return terreno
