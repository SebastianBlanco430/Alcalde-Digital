# Cálculos del edificio de la Fiscalía en el mundo (Python puro: NO importa ursina; tests en
# tests/test_fiscalia_escena_edificio.py). La Fiscalía es la casa decorativa más cercana a fiscalia_bandera.CASA_FISCALIA
# (decisiones.md): aquí se elige esa casa y se calculan su puerta, el punto de la calle delante de la puerta (baliza, E,
# salida al mundo), el cartel de la fachada y el radio en que se ofrece «E: entrar».
#
# Convención de giro (la de Ursina, igual que casas_decorativas: rotation_y = rumbo): un punto LOCAL (lx, lz) de la casa
# (lz hacia su frente, lx a su derecha según se la mira desde dentro) va al mundo con
#   x = cx + lx·cos(r) + lz·sin(r),   z = cz − lx·sin(r) + lz·cos(r).

import math
from dataclasses import dataclass

FUERA_PUERTA = 1.3            # m delante de la fachada donde se para el jugador (E, baliza, salida)
RADIO_PUERTA = 2.4            # m al punto de delante de la puerta en que se ofrece «E: entrar»
ALTO_CARTEL = 0.62            # m del cartel de la fachada
SOBRE_PUERTA = 0.45           # m entre el dintel y el borde de abajo del cartel
MARGEN_CARTEL = 0.5           # m que el cartel deja libres a cada lado de la fachada
SALIENTE_CARTEL = 0.09        # m que el cartel sobresale de la fachada


@dataclass(frozen=True)
class SitioFiscalia:
    cx: float
    cz: float
    rumbo: float              # grados: hacia donde mira la fachada con la puerta
    frente: float             # m de fachada
    fondo: float              # m de fondo
    alto_piso: float          # m de un piso
    pisos: int
    puerta: tuple             # (x, z) del centro de la puerta, en la fachada
    fuera: tuple              # (x, z) delante de la puerta, en la calle
    ancho_puerta: float
    alto_puerta: float
    cartel: tuple             # (x, z) del centro del cartel en la fachada
    ancho_cartel: float
    y_cartel: float           # m sobre el suelo de la casa (centro del cartel)

    @property
    def rumbo_salida(self):
        """Rumbo del jugador al salir (de espaldas a la puerta, mirando a la calle)."""
        return self.rumbo % 360.0

    @property
    def rumbo_entrada(self):
        """Rumbo del jugador mirando la puerta."""
        return (self.rumbo + 180.0) % 360.0


def local_a_mundo(cx, cz, rumbo, lx, lz):
    r = math.radians(rumbo)
    return (cx + lx * math.cos(r) + lz * math.sin(r), cz - lx * math.sin(r) + lz * math.cos(r))


def casa_mas_cercana(casas, punto):
    """La casa (CasaDecorativa: cx, cz) más cercana a `punto` (x, z), o None si no hay ninguna."""
    mejor, mejor_d = None, None
    for casa in casas or ():
        d = math.hypot(casa.cx - punto[0], casa.cz - punto[1])
        if mejor_d is None or d < mejor_d:
            mejor, mejor_d = casa, d
    return mejor


def sitio_de(casa, modelo):
    """SitioFiscalia de `casa` (CasaDecorativa) con las medidas de su `modelo` (ModeloEdificio: frente, fondo, alto,
    puerta_x, puerta_ancho, puerta_alto, en unidades del modelo)."""
    escala = float(casa.escala)
    est = float(getattr(casa, "estiramiento", 1.0) or 1.0)
    frente = modelo.frente * escala
    fondo = modelo.fondo * escala * est
    alto_piso = modelo.alto * escala
    px = float(getattr(modelo, "puerta_x", 0.0) or 0.0) * escala
    ancho_puerta = float(getattr(modelo, "puerta_ancho", 0.5) or 0.5) * escala
    alto_puerta = float(getattr(modelo, "puerta_alto", 1.0) or 1.0) * escala
    puerta = local_a_mundo(casa.cx, casa.cz, casa.rumbo, px, fondo / 2)
    fuera = local_a_mundo(casa.cx, casa.cz, casa.rumbo, px, fondo / 2 + FUERA_PUERTA)
    ancho_cartel = max(1.6, frente - 2 * MARGEN_CARTEL)
    cartel = local_a_mundo(casa.cx, casa.cz, casa.rumbo, 0.0, fondo / 2 + SALIENTE_CARTEL)
    y_cartel = min(alto_puerta + SOBRE_PUERTA + ALTO_CARTEL / 2, alto_piso - ALTO_CARTEL / 2 - 0.05)
    return SitioFiscalia(casa.cx, casa.cz, float(casa.rumbo) % 360.0, frente, fondo, alto_piso,
                         int(getattr(casa, "pisos", 1) or 1), puerta, fuera, ancho_puerta, alto_puerta, cartel,
                         ancho_cartel, y_cartel)


def cerca_de_puerta(sitio, x, z, radio=RADIO_PUERTA):
    return math.hypot(x - sitio.fuera[0], z - sitio.fuera[1]) <= radio


METRO_POR_LETRA = 0.0145      # m que mide una letra de un Text de Ursina a escala 1 en el mundo (medido en la fachada)


def escala_texto_cartel(texto, ancho, maximo=9.0):
    """Escala de un Text de Ursina para que `texto` quepa en `ancho` m."""
    letras = max(1, len(str(texto)))
    return max(0.8, min(maximo, ancho / (letras * METRO_POR_LETRA)))
