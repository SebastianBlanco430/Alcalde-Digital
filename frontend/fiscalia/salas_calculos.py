# Planos de las tres salas de la Fiscalía (Python puro: NO importa ursina; tests en tests/test_fiscalia_escena_salas.py).
# Las tres viven en la misma escena, lejos una de otra (ORIGENES), y solo una se ve a la vez. Todo en METROS de mundo;
# rumbo en grados con la convención de Personaje.fijar_rumbo (0 = mira a +z, 90 = mira a +x).
#
#   oficina      despacho del fiscal: escritorio, el fiscal detrás (mira al sur) y el jugador enfrente (mira al norte).
#   laboratorio  dos terminales en la pared norte (uno por parkour del caso), puerta al sur; el jugador camina libre.
#   sala         sala de interrogatorio: mesa, interrogado al norte, jugador al sur, vidrio espejado en la pared oeste
#                con el fiscal detrás.

import math
from dataclasses import dataclass, field

OFICINA, LABORATORIO, SALA = "oficina", "laboratorio", "sala"
ESCENAS = (OFICINA, LABORATORIO, SALA)
ORIGENES = {OFICINA: (0.0, 0.0), LABORATORIO: (40.0, 0.0), SALA: (80.0, 0.0)}
ROTULOS = {OFICINA: "Despacho del fiscal", LABORATORIO: "Laboratorio forense", SALA: "Sala de interrogatorio"}

ALTURA_ASIENTO = 0.47
ALTURA_MESA = 0.76
CABEZA_SENTADO = 1.24         # m: centro de la cabeza de un adulto sentado (referencia de las tomas)
CABEZA_DE_PIE = 1.62
RADIO_JUGADOR = 0.28          # m: lo que ocupa el jugador al caminar por el laboratorio
RADIO_TERMINAL = 1.05         # m al punto de partida de la silla en que se ofrece «E — Sentarse»
RADIO_PUERTA_LAB = 1.25       # m a la puerta del laboratorio en que se ofrece «E — Pasar a la sala»


@dataclass(frozen=True)
class Asiento:
    x: float
    z: float
    rumbo: float

    @property
    def punto(self):
        return (self.x, self.z)

    def adelante(self, metros):
        r = math.radians(self.rumbo)
        return (self.x + math.sin(r) * metros, self.z + math.cos(r) * metros)

    def cabeza(self, alto=CABEZA_SENTADO):
        return (self.x, alto, self.z)


@dataclass(frozen=True)
class Terminal:
    nivel: str
    asiento: Asiento                 # silla del terminal (mira al monitor)
    mesa: tuple                      # (x, z, ancho, fondo) del tablero
    pantalla: dict                   # {"centro", "normal", "arriba", "alto", "ancho"} (mundo)
    acceso: tuple                    # (x, z): donde se para el jugador para pulsar E (detrás de la silla)


@dataclass(frozen=True)
class PlanoSala:
    nombre: str
    origen: tuple
    ancho: float
    fondo: float
    alto: float
    asientos: dict = field(default_factory=dict)      # «jugador», «hablante» -> Asiento
    mesas: tuple = ()                                 # (x, z, ancho, fondo, alto) en mundo
    terminales: tuple = ()
    puerta: tuple = (0.0, 0.0)                        # (x, z) de la puerta (en la pared)
    entrada: Asiento = None                           # dónde aparece el jugador de pie
    obstaculos: tuple = ()                            # (x0, z0, x1, z1): rectángulos que no se cruzan caminando
    de_pie: dict = field(default_factory=dict)        # personaje -> Asiento (de pie: el fiscal en el laboratorio)

    @property
    def centro(self):
        return self.origen

    def limites(self, margen=RADIO_JUGADOR + 0.1):
        ox, oz = self.origen
        return (ox - self.ancho / 2 + margen, oz - self.fondo / 2 + margen,
                ox + self.ancho / 2 - margen, oz + self.fondo / 2 - margen)


def _m(origen, x, z):
    return (origen[0] + x, origen[1] + z)


def _asiento(origen, x, z, rumbo):
    px, pz = _m(origen, x, z)
    return Asiento(px, pz, rumbo)


def _rect(origen, cx, cz, ancho, fondo, holgura=0.0):
    x, z = _m(origen, cx, cz)
    return (x - ancho / 2 - holgura, z - fondo / 2 - holgura, x + ancho / 2 + holgura, z + fondo / 2 + holgura)


def plano_oficina():
    o = ORIGENES[OFICINA]
    mesa = (*_m(o, 0.0, 0.55), 2.0, 0.9, ALTURA_MESA)
    return PlanoSala(OFICINA, o, 6.2, 5.2, 3.0,
                     asientos={"hablante": _asiento(o, 0.0, 1.42, 180.0), "jugador": _asiento(o, 0.0, -0.36, 0.0)},
                     mesas=(mesa,), puerta=_m(o, -1.9, -2.6), entrada=_asiento(o, -1.9, -2.0, 0.0))


# Laboratorio: terminales en la pared norte. El monitor mira al sur (a la silla), la silla mira al norte.
def _terminal(o, nivel, x):
    z_mesa = 2.2
    asiento = _asiento(o, x, z_mesa - 0.78, 0.0)
    cx, cz = _m(o, x, z_mesa + 0.12)
    pantalla = {"centro": (cx, 1.13, cz - 0.03), "normal": (0.0, 0.0, -1.0), "arriba": (0.0, 1.0, 0.0),
                "alto": 0.40, "ancho": 0.70}
    return Terminal(nivel, asiento, (*_m(o, x, z_mesa), 1.5, 0.75), pantalla, _m(o, x + (0.75 if x <= 0 else -0.75), z_mesa - 1.35))   # del lado del centro de la sala (lejos de los racks)


# pendientes-a (P8): el jugador aparece a 1,8 m de la puerta (fuera de RADIO_PUERTA_LAB) mirando a los terminales; antes
# aparecía a 0,75 m y la primera E abría «¿Pasar a la sala?».
def plano_laboratorio(niveles=("sector_1", "sector_2")):
    o = ORIGENES[LABORATORIO]
    xs = (-1.7, 1.7) if len(niveles) > 1 else (0.0,)
    terminales = tuple(_terminal(o, nivel, x) for nivel, x in zip(niveles, xs))
    obst = [_rect(o, t.mesa[0] - o[0], t.mesa[1] - o[1], t.mesa[2], t.mesa[3], 0.05) for t in terminales]
    obst.append(_rect(o, 3.05, 0.0, 0.7, 2.6, 0.05))           # racks de servidores (pared este)
    obst.append(_rect(o, -2.4, 0.2, 1.5, 0.8, 0.05))           # mesa de pruebas (oeste)
    return PlanoSala(LABORATORIO, o, 7.4, 6.4, 3.0, asientos={}, mesas=(),
                     terminales=terminales, puerta=_m(o, -3.7, -1.7), entrada=_asiento(o, -1.9, -1.7, 30.0),
                     obstaculos=tuple(obst), de_pie={"fiscal": _asiento(o, -2.7, -2.75, 30.0)})


def plano_sala():
    o = ORIGENES[SALA]
    mesa = (*_m(o, 0.0, 0.0), 1.5, 0.85, ALTURA_MESA)
    return PlanoSala(SALA, o, 5.2, 4.8, 2.9,
                     asientos={"hablante": _asiento(o, 0.0, 0.82, 180.0), "jugador": _asiento(o, 0.0, -0.82, 0.0)},
                     mesas=(mesa,), puerta=_m(o, 2.6, 1.6), entrada=_asiento(o, 2.0, 1.6, 270.0),
                     de_pie={"fiscal": _asiento(o, -3.4, -0.2, 90.0)})


def planos(niveles=("sector_1", "sector_2")):
    return {OFICINA: plano_oficina(), LABORATORIO: plano_laboratorio(niveles), SALA: plano_sala()}


# -- Caminar por el laboratorio --

def _choca(x, z, rect, radio):
    x0, z0, x1, z1 = rect
    cx, cz = min(max(x, x0), x1), min(max(z, z0), z1)
    return math.hypot(x - cx, z - cz) < radio


def mover(plano, x, z, dx, dz, radio=RADIO_JUGADOR):
    """(x, z) tras intentar moverse (dx, dz) dentro de los límites de la sala sin cruzar obstáculos (desliza por los ejes)."""
    lx0, lz0, lx1, lz1 = plano.limites(radio + 0.05)

    def libre(px, pz):
        if not (lx0 <= px <= lx1 and lz0 <= pz <= lz1):
            return False
        return not any(_choca(px, pz, r, radio) for r in plano.obstaculos)

    nx, nz = x + dx, z + dz
    if not libre(x, z):
        # Ya está dentro de un obstáculo o fuera de los límites (p. ej. al levantarse de la silla, pegado a la mesa):
        # se le deja salir en vez de dejarlo clavado; solo se respeta el borde de la sala.
        return min(max(nx, lx0), lx1), min(max(nz, lz0), lz1)
    if libre(nx, nz):
        return nx, nz
    if libre(nx, z):
        return nx, z
    if libre(x, nz):
        return x, nz
    return x, z


def terminal_cerca(plano, x, z, radio=RADIO_TERMINAL):
    """Nivel del terminal más cercano a menos de `radio` de su punto de acceso (o de su silla), o None."""
    mejor, mejor_d = None, None
    for t in plano.terminales:
        d = min(math.hypot(x - t.acceso[0], z - t.acceso[1]), math.hypot(x - t.asiento.x, z - t.asiento.z))
        if d <= radio and (mejor_d is None or d < mejor_d):
            mejor, mejor_d = t.nivel, d
    return mejor


def puerta_cerca(plano, x, z, radio=RADIO_PUERTA_LAB):
    return math.hypot(x - plano.puerta[0], z - plano.puerta[1]) <= radio


def terminal_de(plano, nivel):
    return next((t for t in plano.terminales if t.nivel == nivel), None)
