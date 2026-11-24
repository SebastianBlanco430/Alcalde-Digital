# Anclas del final animado (PURO: no importa ursina; se prueba con pytest). Un ancla es un punto con nombre del mundo
# de la partida, con su rumbo: las cámaras (camaras.py) y la puesta en escena (puesta.py) se escriben RELATIVAS a un
# ancla, así que si un ancla se corre, cámara y actores se corren juntos y el encuadre no se rompe.
#
# Rumbo en grados como en el resto del juego: 0 = +z, 90 = +x (math.atan2(dx, dz)). El «frente» del ancla es hacia donde
# mira el sujeto del plano. Marco local: (derecha, alto, frente). `alto` se mide desde `ancla.y`.
#
#   anclas(mundo)                       -> {nombre: Ancla}
#   a_mundo(ancla, derecha, alto, frente) -> (x, y, z) en el mundo
#   en_suelo(mundo, ancla, derecha, frente, alto=0) -> (x, y, z) con y = suelo real de ese punto + alto
#   rumbo_hacia(desde, hasta)           -> grados
#
# Dueño de los valores: el módulo de decorado y actores (puede correr un ancla si choca con algo del mundo).

import math
from dataclasses import dataclass

LUGAR_PLAZA = "Praça da Sé"
LUGAR_PREFEITURA = "Prefeitura"
LUGAR_MORRO = "Morro da Esperança"
LUGAR_RADIO = "Rádio Comunitária"
LUGAR_CALLE = "Universidade de Ciudad Nova"     # la calle del plano «calle» va de la plaza a este lugar

# Desplazamientos (derecha, frente) en el marco de la PLAZA (rumbo 180: mirando al sur, con la fuente y la Lan House detrás).
PODIO_EN_PLAZA = (0.0, 6.5)           # borde sur de la plaza; el público queda más al sur, de espaldas a la cámara
URNA_EN_PLAZA = (-5.5, 4.0)           # al este del podio (derecha negativa = +x con rumbo 180)
DIRECTO_EN_PLAZA = (5.5, 3.5)         # al oeste: la influencer en vivo, con la fuente detrás
TARIMA_EN_PLAZA = (2.6, 7.4)          # junto al podio: el candidato antes de subir / al reconocer la derrota
# Entre el centro de la plaza de la Prefeitura y su puerta. Era 0,45 (a 6,6 m de la puerta): la cámara de m3_protesta
# (frente +9) quedaba DENTRO del edificio. Con 0,12 el ancla está a ~10,6 m de la puerta y todo el marco
# (derecha -6..+6, frente -6..+9) se puede pisar salvo un farol (decorado-actores, 23-nov).
FRACCION_PROTESTA = 0.12
FRACCION_CALLE = 0.45                 # a lo largo de la calle plaza -> universidad
NOMBRES = ("plaza", "podio", "urna", "directo", "tarima", "prefeitura", "protesta", "calle", "morro", "radio", "azotea")


@dataclass(frozen=True)
class Ancla:
    nombre: str
    x: float
    z: float
    y: float
    rumbo: float

    @property
    def frente(self):
        r = math.radians(self.rumbo)
        return (math.sin(r), math.cos(r))

    @property
    def derecha(self):
        r = math.radians(self.rumbo)
        return (math.cos(r), -math.sin(r))


def rumbo_hacia(desde, hasta):
    """Rumbo (grados, 0 = +z) para mirar de `desde` (x, z) a `hasta` (x, z)."""
    return math.degrees(math.atan2(hasta[0] - desde[0], hasta[1] - desde[1])) % 360.0


def a_mundo(ancla, derecha=0.0, alto=0.0, frente=0.0):
    """Punto del mundo a (derecha, alto, frente) del ancla, en su marco local."""
    fx, fz = ancla.frente
    dx, dz = ancla.derecha
    return (ancla.x + dx * derecha + fx * frente, ancla.y + alto, ancla.z + dz * derecha + fz * frente)


def en_suelo(mundo, ancla, derecha=0.0, frente=0.0, alto=0.0):
    """Como a_mundo, pero la altura es la del SUELO real de ese punto (+ alto): para lo que pisa la calle."""
    x, _, z = a_mundo(ancla, derecha, 0.0, frente)
    return (x, float(mundo.altura(x, z)) + alto, z)


def _valor(dato):
    return dato() if callable(dato) else dato


def _centro_plaza(mundo):
    """Centro de la fuente (el círculo «fuente» que la ciudad entrega al mundo) o, sin él, el de la plaza."""
    extra = getattr(mundo, "obstaculos_extra", None)
    if callable(extra):
        try:
            for obstaculo in extra("fuente"):
                if getattr(obstaculo, "es_circulo", False):
                    return (float(obstaculo.cx), float(obstaculo.cz))
        except Exception:
            pass
    x, z = mundo.coordenada(LUGAR_PLAZA)
    return (float(x), float(z))


def _ancla(mundo, nombre, x, z, rumbo, y=None):
    return Ancla(nombre, float(x), float(z), float(mundo.altura(x, z)) if y is None else float(y), float(rumbo) % 360.0)


def anclas(mundo):
    """Las anclas del final en ese mundo. Lanza (KeyError / AttributeError / ValueError) si al mundo le falta un lugar:
    el final animado cae entonces a las viñetas."""
    px, pz = _centro_plaza(mundo)
    plaza = _ancla(mundo, "plaza", px, pz, 180.0)
    out = {"plaza": plaza}
    for nombre, (derecha, frente) in (("podio", PODIO_EN_PLAZA), ("urna", URNA_EN_PLAZA), ("directo", DIRECTO_EN_PLAZA),
                                      ("tarima", TARIMA_EN_PLAZA)):
        x, _, z = a_mundo(plaza, derecha, 0.0, frente)
        out[nombre] = _ancla(mundo, nombre, x, z, 180.0)

    # Prefeitura: el sujeto sale por la puerta mirando hacia fuera (despacho del alcalde y sede del Partido de la Tradición).
    pref = mundo.edificio_de(LUGAR_PREFEITURA)
    puerta = pref.punto_entrada(1.2)
    hacia_fuera = (_valor(pref.rumbo_puerta) + 180.0) % 360.0
    out["prefeitura"] = _ancla(mundo, "prefeitura", puerta[0], puerta[1], hacia_fuera)
    # Protesta: en la plaza de la Prefeitura, mirando al edificio.
    cx, cz = mundo.coordenada(LUGAR_PREFEITURA)
    x, z = cx + (puerta[0] - cx) * FRACCION_PROTESTA, cz + (puerta[1] - cz) * FRACCION_PROTESTA
    out["protesta"] = _ancla(mundo, "protesta", x, z, rumbo_hacia((x, z), puerta))

    # Calle: sobre el eje plaza -> universidad, mirando calle abajo hacia la plaza (el sujeto camina hacia la cámara).
    ux, uz = mundo.coordenada(LUGAR_CALLE)
    qx, qz = mundo.coordenada(LUGAR_PLAZA)
    x, z = qx + (ux - qx) * FRACCION_CALLE, qz + (uz - qz) * FRACCION_CALLE
    out["calle"] = _ancla(mundo, "calle", x, z, rumbo_hacia((ux, uz), (qx, qz)))

    for nombre, lugar in (("morro", LUGAR_MORRO), ("radio", LUGAR_RADIO)):
        edificio = mundo.edificio_de(lugar)
        puerta = edificio.punto_entrada(1.2)
        out[nombre] = _ancla(mundo, nombre, puerta[0], puerta[1], (_valor(edificio.rumbo_puerta) + 180.0) % 360.0)

    # Azotea: el techo del edificio de la plaza (Lan House), mirando a la plaza y a la ciudad.
    lan = mundo.edificio_de(LUGAR_PLAZA)
    out["azotea"] = _ancla(mundo, "azotea", lan.cx, lan.cz, rumbo_hacia((lan.cx, lan.cz), (px, pz)),
                           y=float(lan.y) + float(lan.alto))
    return out
