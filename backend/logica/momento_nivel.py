# Momento de nivel: detector PURO de cruces de nivel del Ambiente de la ciudad (ambiente_ciudad.NIVELES). Sin ursina.
#
#   detector = DetectorNivel()
#   evento = detector.observar(nivel, dt, reinicio=False)   # EventoNivel | None, una vez por frame
#   titular(evento.desde, evento.hacia, cargar_titulares())  # texto corto para la vista, o None
#
# La primera observación (o cualquiera con reinicio=True: partida nueva, carga, salto de depuración) solo fija la
# referencia. Un cruce se anuncia cuando el nivel actual difiere del ÚLTIMO ANUNCIADO y ya pasó el enfriamiento
# (ENFRIAMIENTO_S desde el último evento). Un cruce durante el enfriamiento se aplaza: al terminar, si el nivel sigue
# distinto del anunciado, se anuncia una vez (desde = anunciado, hacia = actual); si volvió al anunciado, nada.

import json
from dataclasses import dataclass
from pathlib import Path

from backend.logica.ambiente_ciudad import NIVELES

ENFRIAMIENTO_S = 60.0
DURACION_ACELERACION_S = 3.0
TAU_ACELERADO_S = 1.0

RUTA_TITULARES = Path(__file__).resolve().parent.parent / "datos" / "titulares_nivel.json"


def _indice_nivel(nivel):
    if nivel not in NIVELES:
        raise ValueError(f"nivel inválido: {nivel!r}; se esperaba uno de {NIVELES}.")
    return NIVELES.index(nivel)


def direccion(desde, hacia):
    """"sube" si `hacia` es mejor que `desde`, "baja" si es peor, None si es el mismo. ValueError si alguno no existe."""
    a, b = _indice_nivel(desde), _indice_nivel(hacia)
    if a == b:
        return None
    return "sube" if b < a else "baja"          # NIVELES va de mejor a peor


@dataclass(frozen=True)
class EventoNivel:
    desde: str
    hacia: str
    direccion: str


class DetectorNivel:

    def __init__(self, enfriamiento=ENFRIAMIENTO_S):
        self._enfriamiento = float(enfriamiento)
        self._anunciado = None          # último nivel anunciado (o la referencia tras un reinicio)
        self._restante = 0.0            # s de enfriamiento que faltan

    def restante_enfriamiento(self):
        return self._restante

    def anunciado(self):
        return self._anunciado

    def observar(self, nivel, dt, reinicio=False):
        _indice_nivel(nivel)
        if reinicio or self._anunciado is None:
            self._anunciado = nivel
            self._restante = 0.0
            return None
        self._restante = max(0.0, self._restante - max(0.0, float(dt)))
        if nivel == self._anunciado or self._restante > 0.0:
            return None
        evento = EventoNivel(self._anunciado, nivel, direccion(self._anunciado, nivel))
        self._anunciado = nivel
        self._restante = self._enfriamiento
        return evento


def cargar_titulares(ruta=None):
    """Textos de titulares_nivel.json: {"version", "sube": {nivel: texto}, "baja": {nivel: texto}}."""
    with open(RUTA_TITULARES if ruta is None else ruta, encoding="utf-8") as archivo:
        return json.load(archivo)


def titular(desde, hacia, textos):
    """Titular del cruce desde → hacia (por nivel destino y dirección), o None si no hay cruce o falta el texto."""
    sentido = direccion(desde, hacia)
    if sentido is None:
        return None
    return (textos.get(sentido) or {}).get(hacia)
