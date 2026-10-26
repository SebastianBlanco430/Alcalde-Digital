# GPS del mundo en pantalla para el mapa grande (puro, sin ursina). navegacion.ruta_gps_hasta_puerta parte de una calle
# o de una plaza; dentro del barrio, lejos de la calle, la primera línea atravesaría casas. Aquí se antepone el tramo
# local (navegacion_local.ruta_gps_local: A* corto sobre la rejilla de conectividad) y se cachea, porque el A* cuesta
# 0,03-1,3 s y la escena pide la ruta cada frame.
#
#   ruta_gps_hasta_puerta_local(mundo, x, z, destino)  [(x, z), ...] SIN el punto de partida: tramo local + esquinas +
#                                                       punto de entrada + puerta (o el centro del lugar sin edificio).
#   CacheRutaGps                                        el mismo cálculo con caché (por destino y por distancia movida)
#                                                       y respaldo al GPS de siempre si algo falla.
#
# Con un mundo que no es grande (sin `contenido_de_chunk`) se llama a navegacion.ruta_gps_hasta_puerta: el mundo chico no
# cambia. navegacion.py y navegacion_local.py no se tocan.

import math
import time

from backend.logica import navegacion

DISTANCIA_RECALCULO = 5.0         # m que debe moverse el jugador para recalcular el tramo
SEGUNDOS_MINIMOS = 0.8            # s mínimos entre dos recálculos del mismo destino


def _final_del_destino(mundo, destino):
    edificio_de = getattr(mundo, "edificio_de", None)
    try:
        edificio = edificio_de(destino) if edificio_de is not None else None
    except ValueError:
        edificio = None
    if edificio is None:
        return None
    return [edificio.punto_entrada(), edificio.puerta()]


def ruta_gps_hasta_puerta_local(mundo, x, z, destino, radio_ventana=60.0):
    """Puntos (x, z) para DIBUJAR el camino del jugador (x, z) hasta la puerta de `destino`, sin incluir el punto de
    partida. ValueError si el destino no existe."""
    from backend.logica.navegacion_local import ruta_gps_local
    tramo, lugares = ruta_gps_local(mundo, x, z, destino, radio_ventana)
    puntos = [tuple(p) for p in tramo]
    if puntos and math.hypot(puntos[0][0] - x, puntos[0][1] - z) < 0.3:
        puntos = puntos[1:]                                  # el jugador ya es el primer punto
    puntos += [mundo.coordenada(lugar) for lugar in lugares]
    final = _final_del_destino(mundo, destino)
    if final is None:
        return puntos or [mundo.coordenada(destino)]
    return puntos + final


class CacheRutaGps:
    """ruta(mundo, x, z, destino) -> puntos sin el de partida. Solo recalcula si cambió el destino o el jugador se movió
    DISTANCIA_RECALCULO m (y han pasado SEGUNDOS_MINIMOS). Mundo sin chunks: el GPS de siempre, sin caché."""

    def __init__(self, reloj=time.monotonic):
        self._reloj = reloj
        self._clave = None
        self._origen = None
        self._t = -1e9
        self._puntos = []
        self.recalculos = 0

    def ruta(self, mundo, x, z, destino):
        if not hasattr(mundo, "contenido_de_chunk"):
            return navegacion.ruta_gps_hasta_puerta(mundo, x, z, destino)
        ahora = self._reloj()
        movido = math.inf if self._origen is None else math.hypot(x - self._origen[0], z - self._origen[1])
        if self._clave == destino and (movido < DISTANCIA_RECALCULO or ahora - self._t < SEGUNDOS_MINIMOS):
            return list(self._puntos)
        try:
            puntos = ruta_gps_hasta_puerta_local(mundo, x, z, destino)
        except (ValueError, ArithmeticError, IndexError):
            puntos = navegacion.ruta_gps_hasta_puerta(mundo, x, z, destino)
        self._clave, self._origen, self._t, self._puntos = destino, (x, z), ahora, puntos
        self.recalculos += 1
        return list(puntos)
