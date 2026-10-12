# Peatones que pasean por Ciudad Nova (Python puro: NO importa ursina). Cada Caminante va de
# lugar en lugar siguiendo las CALLES del mapa (por el eje, con un desvío lateral pequeño para
# que no vayan todos en fila), se detiene unos segundos en cada plaza y elige al azar el
# siguiente destino entre los lugares vecinos (sin volver atrás salvo en un callejón sin salida).
#
# Como solo recorren ejes de calle y centros de plaza, que el modelo garantiza despejados
# (ver backend/datos/ciudad_3d.py), nunca atraviesan edificios ni obstáculos. Son solo decoración:
# no tienen colisión con los jugadores ni afectan al modelo de la partida. El azar se inyecta
# (random.Random) para que sea determinista en los tests.

import math

VELOCIDAD = 1.5          # m/s
DESVIO_MAXIMO = 1.6      # m a un lado del eje de la calle (el asfalto mide 8 y las farolas están a 4.8)
PAUSA_MIN, PAUSA_MAX = 1.0, 5.0


class Caminante:

    def __init__(self, mundo, lugar, azar, velocidad=VELOCIDAD):
        self._mundo = mundo
        self._azar = azar
        self.velocidad = velocidad
        self.desvio = azar.uniform(-DESVIO_MAXIMO, DESVIO_MAXIMO)
        self._origen = lugar
        self._destino = None
        self._anterior = None
        self._espera = azar.uniform(0, PAUSA_MAX)
        cx, cz = mundo.coordenada(lugar)
        self.x, self.z = cx, cz
        self.rumbo = azar.uniform(-180, 180)
        self.en_movimiento = False

    # Avanza `dt` segundos: espera, o camina hacia el siguiente lugar.
    def avanzar(self, dt):
        if dt <= 0:
            return
        self.en_movimiento = False
        if self._espera > 0:
            self._espera -= dt
            return
        if self._destino is None:
            self._elegir_destino()
        tx, tz = self._objetivo()
        dx, dz = tx - self.x, tz - self.z
        distancia = math.hypot(dx, dz)
        paso = self.velocidad * dt
        if distancia <= paso:
            self.x, self.z = tx, tz
            self._anterior, self._origen, self._destino = self._origen, self._destino, None
            self._espera = self._azar.uniform(PAUSA_MIN, PAUSA_MAX)
            return
        self.x += dx / distancia * paso
        self.z += dz / distancia * paso
        self.rumbo = math.degrees(math.atan2(dx, dz))
        self.en_movimiento = True

    def _elegir_destino(self):
        vecinos = sorted(self._mundo.grafo.vecinos(self._origen))
        opciones = [v for v in vecinos if v != self._anterior] or vecinos
        self._destino = self._azar.choice(opciones)

    # Centro del lugar de destino desplazado `desvio` m a un lado de la calle origen -> destino.
    def _objetivo(self):
        ax, az = self._mundo.coordenada(self._origen)
        bx, bz = self._mundo.coordenada(self._destino)
        largo = math.hypot(bx - ax, bz - az)
        nx, nz = -(bz - az) / largo, (bx - ax) / largo
        return (bx + nx * self.desvio, bz + nz * self.desvio)


# `cantidad` caminantes repartidos por los lugares del mapa.
def crear_caminantes(mundo, cantidad, azar):
    lugares = mundo.lugares()
    return [Caminante(mundo, lugares[i % len(lugares)], azar) for i in range(cantidad)]
