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
import threading
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

    # `en_hilo=True`: cuando el jugador está DENTRO del barrio (fuera de calles y plazas) el A* se calcula en un hilo
    # aparte y ruta() no espera por él: mientras llega devuelve la ruta anterior (o, con un destino nuevo, el GPS de
    # calles de siempre). Ahí el A* tarda de 0,3 a 3 s y, síncrono, congelaba el juego ese tiempo cada 5 m caminados.
    # En calle o plaza no hay A* (solo el GPS de calles, barato) y se calcula en el sitio: medido, mandarlo también al
    # hilo era peor (el hilo compite por el GIL: 59 -> 50 fps caminando). Sin `en_hilo` (por defecto) todo es síncrono.
    def __init__(self, reloj=time.monotonic, en_hilo=False):
        self._reloj = reloj
        self._clave = None
        self._origen = None
        self._t = -1e9
        self._puntos = []
        self.recalculos = 0
        self._en_hilo = en_hilo
        self._provisional = False         # la ruta guardada es el GPS de calles a la espera del tramo local
        self._pendiente = None            # (destino, origen, caja) del cálculo en curso; caja = [] hasta que termina

    def ruta(self, mundo, x, z, destino):
        if not hasattr(mundo, "contenido_de_chunk"):
            return navegacion.ruta_gps_hasta_puerta(mundo, x, z, destino)
        ahora = self._reloj()
        self._recoger(destino, ahora)
        movido = math.inf if self._origen is None else math.hypot(x - self._origen[0], z - self._origen[1])
        vigente = self._clave == destino and (movido < DISTANCIA_RECALCULO or ahora - self._t < SEGUNDOS_MINIMOS)
        if vigente and not self._provisional:       # una ruta provisional (GPS de calles) siempre pide el tramo local
            return list(self._puntos)
        if not self._en_hilo or (self._pendiente is None and _en_la_red(mundo, x, z)):
            puntos = _calcular(mundo, x, z, destino)
            self._provisional = False
            self._clave, self._origen, self._t, self._puntos = destino, (x, z), ahora, puntos
            self.recalculos += 1
            return list(puntos)
        if self._pendiente is None:
            caja = []
            self._pendiente = (destino, (x, z), caja)
            threading.Thread(target=lambda: caja.append(_calcular(mundo, x, z, destino)),
                             name="gps_local", daemon=True).start()
        if self._clave != destino:        # destino nuevo: el GPS de calles (barato) hasta que llegue el tramo local
            self._clave, self._origen, self._t = destino, (x, z), ahora
            self._puntos = navegacion.ruta_gps_hasta_puerta(mundo, x, z, destino)
            self._provisional = True
        return list(self._puntos)

    # Si el cálculo en curso terminó, lo adopta (salvo que ya se pida otro destino: ese resultado se descarta).
    def _recoger(self, destino, ahora):
        if self._pendiente is None or not self._pendiente[2]:
            return
        pedido, origen, caja = self._pendiente
        self._pendiente = None
        if pedido == destino:
            self._clave, self._origen, self._t, self._puntos = pedido, origen, ahora, caja[0]
            self._provisional = False
            self.recalculos += 1

    def calculando(self):
        return self._pendiente is not None and not self._pendiente[2]


# ¿(x, z) pisa una calle o una plaza? Ahí ruta_gps_local no necesita A*. Ante la duda, False (se calcula en el hilo).
def _en_la_red(mundo, x, z):
    try:
        return mundo.lugar_en_plaza(x, z) is not None or mundo.calle_en(x, z) is not None
    except Exception:      # noqa: BLE001
        return False


# El tramo local; si falla, el GPS de siempre. Nunca lanza por un fallo del A* (en el hilo dejaría la ruta colgada).
def _calcular(mundo, x, z, destino):
    try:
        return ruta_gps_hasta_puerta_local(mundo, x, z, destino)
    except Exception:      # noqa: BLE001 — antes solo ValueError/ArithmeticError/IndexError; en un hilo no puede escaparse nada
        return navegacion.ruta_gps_hasta_puerta(mundo, x, z, destino)
