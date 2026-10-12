# Mundo 3D de Ciudad Nova (modelo puro, sin ursina): el MapaCiudad (lugares, calles, GPS)
# más edificios con puerta y obstáculos. Es la fuente de verdad de "por dónde se puede
# caminar" en el mundo en tercera persona.
#
# Composición, no herencia: MundoCiudad guarda un MapaCiudad y delega en él todo lo que
# el GPS necesita (coordenada, grafo, lugar_en_plaza, calle_en...). Por eso las funciones
# de navegacion.py (que usan `es_transitable` por duck typing) funcionan igual con un
# mapa o con un mundo. La diferencia: aquí se camina LIBRE por toda la ciudad (calles,
# aceras, plazas, pasto) y solo estorban los obstáculos y el borde del mapa.
#
# Convención de ejes (Ursina): el plano es (x, z); con rotation_y = ψ "adelante" en el
# piso es (sin ψ, cos ψ). Lados de una fachada: 'n' = +z, 's' = -z, 'e' = +x, 'o' = -x.
#
# Colisión del jugador (círculo de radio r en p):
#   - contra una caja alineada: q = (clamp(x, xmin, xmax), clamp(z, zmin, zmax));
#     choca <=> |p - q| < r   (dentro de la caja q = p, distancia 0, choca)
#   - contra otro círculo (árbol, farola): choca <=> |p - c| < r + rc
# Tocar justo el borde (distancia == r) NO cuenta como choque.

import math
from dataclasses import dataclass

from backend.grafos.mapa_ciudad import _distancia_punto_segmento

RADIO_JUGADOR = 0.35
DISTANCIA_ENTRADA = 1.2          # m delante de la puerta donde se para el personaje
LADOS_PUERTA = ("n", "s", "e", "o")
# Rumbo (rotation_y, grados) con el que se ENTRA por cada cara: hacia dentro del edificio.
_RUMBO_ENTRADA = {"s": 0.0, "o": 90.0, "n": 180.0, "e": -90.0}
# Vector unitario hacia afuera de cada cara.
_NORMAL_FUERA = {"n": (0, 1), "s": (0, -1), "e": (1, 0), "o": (-1, 0)}


@dataclass(frozen=True)
class Obstaculo:
    """Algo que no se atraviesa. Caja alineada (cx, cz, ancho, fondo) o círculo (cx, cz, radio)."""

    tipo: str
    cx: float
    cz: float
    radio: float | None = None
    ancho: float | None = None
    fondo: float | None = None

    def __post_init__(self):
        es_circulo = self.radio is not None
        es_caja = self.ancho is not None or self.fondo is not None
        if es_circulo == es_caja:
            raise ValueError(f"Obstáculo {self.tipo!r}: indica un radio O ancho y fondo.")
        if es_circulo and self.radio <= 0:
            raise ValueError(f"Obstáculo {self.tipo!r}: el radio debe ser positivo.")
        if es_caja and (self.ancho is None or self.fondo is None or self.ancho <= 0 or self.fondo <= 0):
            raise ValueError(f"Obstáculo {self.tipo!r}: ancho y fondo deben ser positivos.")

    @property
    def es_circulo(self):
        return self.radio is not None

    @property
    def es_caja(self):
        return self.radio is None

    # True si un círculo de radio `r` centrado en (x, z) toca este obstáculo.
    def choca(self, x, z, r):
        if self.es_circulo:
            return math.hypot(x - self.cx, z - self.cz) < self.radio + r
        qx = min(max(x, self.cx - self.ancho / 2), self.cx + self.ancho / 2)
        qz = min(max(z, self.cz - self.fondo / 2), self.cz + self.fondo / 2)
        return math.hypot(x - qx, z - qz) < r


@dataclass(frozen=True)
class Edificio:
    """Un edificio por lugar: caja (cx, cz, ancho en x, fondo en z, alto) con UNA puerta."""

    lugar: str
    cx: float
    cz: float
    ancho: float
    fondo: float
    alto: float
    lado_puerta: str
    nombre: str = ""            # texto del letrero; vacío = el nombre del lugar

    def __post_init__(self):
        if self.lado_puerta not in LADOS_PUERTA:
            raise ValueError(f"lado_puerta debe ser uno de {LADOS_PUERTA}, no {self.lado_puerta!r}.")
        if self.ancho <= 0 or self.fondo <= 0 or self.alto <= 0:
            raise ValueError(f"El edificio de {self.lugar!r} necesita ancho, fondo y alto positivos.")

    @property
    def titulo(self):
        return self.nombre or self.lugar

    # Puerta: centro de la cara `lado_puerta`, sobre la fachada.
    def puerta(self):
        nx, nz = _NORMAL_FUERA[self.lado_puerta]
        return (self.cx + nx * self.ancho / 2, self.cz + nz * self.fondo / 2)

    # Punto de la calle `distancia` m delante de la puerta (donde se para el personaje).
    def punto_entrada(self, distancia=DISTANCIA_ENTRADA):
        nx, nz = _NORMAL_FUERA[self.lado_puerta]
        px, pz = self.puerta()
        return (px + nx * distancia, pz + nz * distancia)

    # Rumbo (rotation_y en grados) con el que se cruza la puerta hacia dentro.
    def rumbo_puerta(self):
        return _RUMBO_ENTRADA[self.lado_puerta]

    # (xmin, xmax, zmin, zmax) de la caja.
    def caja(self):
        return (self.cx - self.ancho / 2, self.cx + self.ancho / 2,
                self.cz - self.fondo / 2, self.cz + self.fondo / 2)

    def como_obstaculo(self):
        return Obstaculo("edificio", self.cx, self.cz, ancho=self.ancho, fondo=self.fondo)


class MundoCiudad:

    # `spawns` ({nombre: (x, z)}) es opcional: si se da, cada uno debe ser transitable.
    # `margen_edificios` ensancha los límites alrededor de los edificios que sobresalen del
    # mapa (0 = el borde pasa pegado a la pared).
    # ValueError si un edificio es de un lugar inexistente o repetido, tapa una plaza o una
    # calle, o si alguna puerta, punto de entrada o spawn no es transitable.
    def __init__(self, mapa, edificios, obstaculos, radio_jugador=RADIO_JUGADOR,
                 spawns=None, margen_edificios=0.0):
        if radio_jugador <= 0:
            raise ValueError("radio_jugador debe ser positivo.")
        self._mapa = mapa
        self._edificios = list(edificios)
        self._obstaculos = list(obstaculos)
        self.radio_jugador = radio_jugador
        self.spawns = dict(spawns) if spawns else {}
        self._por_lugar = {}

        for edificio in self._edificios:
            self._validar_edificio(edificio)
            self._por_lugar[edificio.lugar] = edificio

        self._fisicos = [e.como_obstaculo() for e in self._edificios] + self._obstaculos
        self._limites = self._calcular_limites(margen_edificios)

        for edificio in self._edificios:
            if not self._puerta_libre(edificio):
                raise ValueError(f"La puerta de {edificio.lugar!r} está bloqueada o fuera de los límites.")
            ex, ez = edificio.punto_entrada()
            if not self.es_transitable(ex, ez):
                raise ValueError(
                    f"El punto de entrada de {edificio.lugar!r} en ({ex:.2f}, {ez:.2f}) no es transitable.")
        for nombre, (x, z) in self.spawns.items():
            if not self.es_transitable(x, z):
                raise ValueError(f"El spawn {nombre!r} en ({x}, {z}) no es transitable.")

    # -- Delegación al mapa (lo que usa el GPS) --

    @property
    def mapa(self):
        return self._mapa

    @property
    def grafo(self):
        return self._mapa.grafo

    @property
    def ancho_calle(self):
        return self._mapa.ancho_calle

    @property
    def radio_plaza(self):
        return self._mapa.radio_plaza

    def coordenada(self, lugar):
        return self._mapa.coordenada(lugar)

    def lugares(self):
        return self._mapa.lugares()

    def segmentos(self):
        return self._mapa.segmentos()

    def lugar_en_plaza(self, x, z):
        return self._mapa.lugar_en_plaza(x, z)

    def calle_en(self, x, z):
        return self._mapa.calle_en(x, z)

    def lugar_mas_cercano(self, x, z):
        return self._mapa.lugar_mas_cercano(x, z)

    # -- Edificios y obstáculos --

    def edificios(self):
        return list(self._edificios)

    def obstaculos(self):
        return list(self._obstaculos)

    # ValueError si el lugar no tiene edificio.
    def edificio_de(self, lugar):
        if lugar not in self._por_lugar:
            raise ValueError(f"El lugar {lugar!r} no tiene edificio.")
        return self._por_lugar[lugar]

    # Donde se mide "llegué": la puerta del edificio; sin edificio, el centro del lugar
    # (así un mundo sin edificios se comporta como el mapa). ValueError si no existe.
    def punto_interaccion(self, lugar):
        if lugar in self._por_lugar:
            return self._por_lugar[lugar].puerta()
        return self._mapa.coordenada(lugar)

    # -- Movimiento --

    # (xmin, xmax, zmin, zmax): los límites del mapa ampliados para incluir los edificios.
    def limites(self):
        return self._limites

    # Transitable <=> dentro de los límites y el círculo del jugador no toca ningún obstáculo.
    def es_transitable(self, x, z):
        xmin, xmax, zmin, zmax = self._limites
        if not (xmin <= x <= xmax and zmin <= z <= zmax):
            return False
        return not any(o.choca(x, z, self.radio_jugador) for o in self._fisicos)

    # -- Internos --

    def _calcular_limites(self, margen):
        xmin, xmax, zmin, zmax = self._mapa.limites()
        for e in self._edificios:
            ex0, ex1, ez0, ez1 = e.caja()
            xmin, xmax = min(xmin, ex0 - margen), max(xmax, ex1 + margen)
            zmin, zmax = min(zmin, ez0 - margen), max(zmax, ez1 + margen)
        return (xmin, xmax, zmin, zmax)

    def _validar_edificio(self, edificio):
        mapa = self._mapa
        if edificio.lugar not in mapa.lugares():
            raise ValueError(f"Edificio de un lugar inexistente: {edificio.lugar!r}.")
        if edificio.lugar in self._por_lugar:
            raise ValueError(f"Hay dos edificios para {edificio.lugar!r} (lugar repetido).")
        caja = edificio.caja()
        for otro in self._por_lugar.values():
            if _cajas_se_solapan(caja, otro.caja()):
                raise ValueError(f"El edificio de {edificio.lugar!r} se solapa con el de {otro.lugar!r}.")
        for lugar in mapa.lugares():
            cx, cz = mapa.coordenada(lugar)
            if _distancia_punto_caja(cx, cz, caja) <= mapa.radio_plaza:
                raise ValueError(f"El edificio de {edificio.lugar!r} tapa la plaza de {lugar!r}.")
        semiancho = mapa.ancho_calle / 2
        for a, b in mapa.segmentos():
            if _distancia_segmento_caja(mapa.coordenada(a), mapa.coordenada(b), caja) <= semiancho:
                raise ValueError(f"El edificio de {edificio.lugar!r} tapa la calle {a!r} - {b!r}.")

    # La puerta está EN la fachada, así que su propio edificio siempre la "toca": no se le
    # exige ser transitable, solo estar dentro de los límites y que ningún OTRO obstáculo
    # la bloquee. Lo que sí es transitable es el punto de entrada, 1.2 m delante.
    def _puerta_libre(self, edificio):
        x, z = edificio.puerta()
        xmin, xmax, zmin, zmax = self._limites
        if not (xmin <= x <= xmax and zmin <= z <= zmax):
            return False
        propio = edificio.como_obstaculo()
        return not any(o.choca(x, z, self.radio_jugador) for o in self._fisicos if o != propio)

    def __repr__(self):
        return (f"MundoCiudad(lugares={len(self.lugares())}, edificios={len(self._edificios)}, "
                f"obstaculos={len(self._obstaculos)})")


# -- Geometría auxiliar ----------------------------------------------------------------


def _cajas_se_solapan(a, b):
    return a[0] < b[1] and b[0] < a[1] and a[2] < b[3] and b[2] < a[3]


# Distancia del punto a la caja (xmin, xmax, zmin, zmax); 0 si está dentro.
def _distancia_punto_caja(x, z, caja):
    xmin, xmax, zmin, zmax = caja
    return math.hypot(x - min(max(x, xmin), xmax), z - min(max(z, zmin), zmax))


# Distancia mínima entre el segmento a-b y la caja; 0 si se cortan o el segmento está dentro.
# Si no se cortan, el mínimo se da entre un extremo del segmento y la caja, o entre una
# esquina de la caja y el segmento (distancia entre polígonos convexos).
def _distancia_segmento_caja(a, b, caja):
    if _segmento_corta_caja(a, b, caja):
        return 0.0
    xmin, xmax, zmin, zmax = caja
    esquinas = [(xmin, zmin), (xmin, zmax), (xmax, zmin), (xmax, zmax)]
    return min(
        _distancia_punto_caja(a[0], a[1], caja),
        _distancia_punto_caja(b[0], b[1], caja),
        *(_distancia_punto_segmento(esquina, a, b) for esquina in esquinas),
    )


# Recorte de Liang-Barsky del segmento contra la caja.
def _segmento_corta_caja(a, b, caja):
    xmin, xmax, zmin, zmax = caja
    t0, t1 = 0.0, 1.0
    dx, dz = b[0] - a[0], b[1] - a[1]
    for p, q in ((-dx, a[0] - xmin), (dx, xmax - a[0]), (-dz, a[1] - zmin), (dz, zmax - a[1])):
        if p == 0:
            if q < 0:
                return False
            continue
        t = q / p
        if p < 0:
            t0 = max(t0, t)
        else:
            t1 = min(t1, t)
        if t0 > t1:
            return False
    return True
