# Mapa de la ciudad: añade coordenadas (plano XZ del mundo) a un GrafoCiudad.
# Zona transitable = unión de plazas (círculo de radio_plaza en cada lugar) y
# calles (cápsula de ancho_calle/2 alrededor de cada conexión). Lógica pura.

import math

from backend.grafos.grafo_ciudad import construir_grafo_ciudad_ejemplo

# Margen extra (además de radio_plaza) que limites() deja alrededor del mapa.
MARGEN_LIMITES = 1.5


class MapaCiudad:

    # coordenadas = {lugar: (x, z)}; debe cubrir exactamente los lugares del grafo.
    def __init__(self, grafo, coordenadas, ancho_calle=2.0, radio_plaza=2.5):
        faltan = [lugar for lugar in grafo.lugares() if lugar not in coordenadas]
        sobran = [lugar for lugar in coordenadas if lugar not in set(grafo.lugares())]
        if faltan:
            raise ValueError(f"Faltan coordenadas para: {faltan}")
        if sobran:
            raise ValueError(f"Coordenadas de lugares que no existen en el grafo: {sobran}")

        self._grafo = grafo
        self._coordenadas = {lugar: tuple(coordenadas[lugar]) for lugar in grafo.lugares()}
        self.ancho_calle = ancho_calle
        self.radio_plaza = radio_plaza

    @property
    def grafo(self):
        return self._grafo

    # Lanza ValueError si el lugar no existe.
    def coordenada(self, lugar):
        if lugar not in self._coordenadas:
            raise ValueError(f"Lugar inexistente en el mapa: {lugar!r}")
        return self._coordenadas[lugar]

    def lugares(self):
        return list(self._coordenadas.keys())

    # Una tupla (a, b) por conexión, sin duplicados, en orden de lugares/adyacencia.
    def segmentos(self):
        orden = {lugar: i for i, lugar in enumerate(self._coordenadas)}
        resultado = []
        for a in self._coordenadas:
            for b in self._grafo.vecinos(a):
                if orden[a] < orden[b]:
                    resultado.append((a, b))
        return resultado

    # El borde cuenta como transitable (<=).
    def es_transitable(self, x, z):
        return self.lugar_en_plaza(x, z) is not None or self.calle_en(x, z) is not None

    # Lugar cuyo centro es el más cercano; en empate gana el primero en el orden.
    def lugar_mas_cercano(self, x, z):
        mejor = None
        mejor_distancia = None
        for lugar, (cx, cz) in self._coordenadas.items():
            distancia = math.hypot(x - cx, z - cz)
            if mejor_distancia is None or distancia < mejor_distancia:
                mejor, mejor_distancia = lugar, distancia
        return mejor

    # Lugar cuya plaza contiene el punto (el más cercano si se solapan) o None.
    def lugar_en_plaza(self, x, z):
        lugar = self.lugar_mas_cercano(x, z)
        if lugar is None:
            return None
        cx, cz = self._coordenadas[lugar]
        if math.hypot(x - cx, z - cz) <= self.radio_plaza:
            return lugar
        return None

    # Calle de menor distancia entre las que contienen el punto, o None.
    def calle_en(self, x, z):
        mejor = None
        mejor_distancia = None
        semiancho = self.ancho_calle / 2
        for a, b in self.segmentos():
            distancia = _distancia_punto_segmento((x, z), self._coordenadas[a], self._coordenadas[b])
            if distancia <= semiancho and (mejor_distancia is None or distancia < mejor_distancia):
                mejor, mejor_distancia = (a, b), distancia
        return mejor

    # (xmin, xmax, zmin, zmax): caja de las coordenadas ampliada en radio_plaza + MARGEN_LIMITES.
    def limites(self):
        xs = [c[0] for c in self._coordenadas.values()]
        zs = [c[1] for c in self._coordenadas.values()]
        margen = self.radio_plaza + MARGEN_LIMITES
        return (min(xs) - margen, max(xs) + margen, min(zs) - margen, max(zs) + margen)

    # True si dos calles que no comparten extremo se intersectan (o se tocan).
    def segmentos_se_cruzan(self):
        segmentos = self.segmentos()
        for i, (a, b) in enumerate(segmentos):
            for c, d in segmentos[i + 1:]:
                if {a, b} & {c, d}:
                    continue
                if _segmentos_intersectan(
                    self._coordenadas[a], self._coordenadas[b],
                    self._coordenadas[c], self._coordenadas[d],
                ):
                    return True
        return False

    def __repr__(self):
        return f"MapaCiudad(lugares={len(self._coordenadas)}, calles={len(self.segmentos())})"


# t = clamp(((p-a)·(b-a)) / |b-a|², 0, 1); d = |p - (a + t·(b-a))|.
def _distancia_punto_segmento(p, a, b):
    abx, abz = b[0] - a[0], b[1] - a[1]
    largo2 = abx * abx + abz * abz
    if largo2 == 0:
        return math.hypot(p[0] - a[0], p[1] - a[1])
    t = ((p[0] - a[0]) * abx + (p[1] - a[1]) * abz) / largo2
    t = max(0.0, min(1.0, t))
    return math.hypot(p[0] - (a[0] + t * abx), p[1] - (a[1] + t * abz))


def _orientacion(p, q, r):
    valor = (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])
    return (valor > 0) - (valor < 0)


def _en_caja(p, q, r):
    return min(p[0], q[0]) <= r[0] <= max(p[0], q[0]) and min(p[1], q[1]) <= r[1] <= max(p[1], q[1])


def _segmentos_intersectan(p1, p2, p3, p4):
    o1, o2 = _orientacion(p1, p2, p3), _orientacion(p1, p2, p4)
    o3, o4 = _orientacion(p3, p4, p1), _orientacion(p3, p4, p2)
    if o1 != o2 and o3 != o4:
        return True
    # Casos colineales: un extremo cae sobre el otro segmento.
    return (
        (o1 == 0 and _en_caja(p1, p2, p3)) or (o2 == 0 and _en_caja(p1, p2, p4))
        or (o3 == 0 and _en_caja(p3, p4, p1)) or (o4 == 0 and _en_caja(p3, p4, p2))
    )


COORDENADAS_EJEMPLO = {
    "Alcaldía": (-8, 0),
    "Plaza Central": (0, 0),
    "Universidad de Ciudad Nova": (6, 7),
    "Parque Municipal": (14, 5),
    "Barrio Las Flores": (14, -4),
    "Terminal de Buses": (6, -7),
    "Hospital Las Flores": (21, -9),
}


def construir_mapa_ejemplo():
    return MapaCiudad(construir_grafo_ciudad_ejemplo(), COORDENADAS_EJEMPLO)
