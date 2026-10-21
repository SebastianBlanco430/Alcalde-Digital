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
import random

VELOCIDAD = 1.5          # m/s
DESVIO_MAXIMO = 1.6      # m a un lado del eje de la calle (el asfalto mide 8 y las farolas están a 4.8)
PAUSA_MIN, PAUSA_MAX = 1.0, 5.0

# Paletas de aspecto de los peatones (RGB), apagadas para no parecerse a los roles jugables.
PIELES = ((235, 200, 170), (224, 172, 130), (198, 134, 92), (141, 96, 66), (100, 66, 46), (245, 214, 190))
PELOS = ((48, 36, 30), (20, 18, 18), (92, 62, 38), (150, 108, 60), (196, 170, 110), (130, 130, 134))
PANTALONES = ((52, 58, 82), (70, 64, 58), (36, 40, 46), (96, 86, 70), (60, 78, 70), (110, 70, 80))


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
            if self._destino is None:             # lugar aislado: se queda quieto
                self._espera = PAUSA_MAX
                return
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
        if not vecinos:
            return
        opciones = [v for v in vecinos if v != self._anterior] or vecinos
        self._destino = self._azar.choice(opciones)

    # Centro del lugar de destino desplazado `desvio` m a un lado de la calle origen -> destino.
    def _objetivo(self):
        ax, az = self._mundo.coordenada(self._origen)
        bx, bz = self._mundo.coordenada(self._destino)
        largo = math.hypot(bx - ax, bz - az) or 1.0
        nx, nz = -(bz - az) / largo, (bx - ax) / largo
        return (bx + nx * self.desvio, bz + nz * self.desvio)


# `cantidad` caminantes repartidos por los lugares del mapa; `inicio` es el índice del primero (el lugar
# que le toca sale de ese índice).
def crear_caminantes(mundo, cantidad, azar, inicio=0):
    lugares = mundo.lugares()
    return [Caminante(mundo, lugares[i % len(lugares)], azar) for i in range(inicio, inicio + cantidad)]


# Los ORIGINALES primeros caminantes usan el azar de siempre (mismo recorrido que cuando eran solo
# esos); los que se añaden después usan otro generador aparte, para no alterar los originales.
ORIGINALES = 6


def crear_peatones(mundo, cantidad, semilla):
    primeros = min(cantidad, ORIGINALES)
    caminantes = crear_caminantes(mundo, primeros, random.Random(semilla))
    if cantidad > primeros:
        caminantes += crear_caminantes(mundo, cantidad - primeros, random.Random(semilla + 1), primeros)
    return caminantes


# Aspecto del peatón `indice` (pantalón, piel y pelo): determinista por semilla e índice, sin tocar
# el azar de los caminantes (así su recorrido no cambia al variar la ropa).
def aspecto_peaton(indice, semilla):
    azar = random.Random(semilla * 1000 + indice)
    return {"pantalon": azar.choice(PANTALONES), "piel": azar.choice(PIELES), "pelo": azar.choice(PELOS)}


# Rasgos de la cara del peatón `indice` (peinado, ojos, cejas, gafas, gorra, bigote, barba, arrugas): determinista por
# semilla e índice con su propio generador, así ni el recorrido ni el aspecto (pantalón, piel, pelo) cambian.
PEINADOS = ("corto", "corto", "largo", "afro", "mono", "calvo", "atras")
IRIS = ((0.20, 0.13, 0.07), (0.10, 0.30, 0.45), (0.12, 0.40, 0.25), (0.35, 0.22, 0.10), (0.06, 0.05, 0.05))
GORRAS = ((204, 70, 52), (52, 108, 186), (240, 190, 50), (70, 70, 80), (60, 150, 100))
BARBAS = ("incipiente", "chivo", "completa")


def rasgos_peaton(indice, semilla):
    azar = random.Random(semilla * 1000 + indice + 7919)
    gorra = azar.choice(GORRAS) if azar.random() < 0.3 else None
    peinado = azar.choice(PEINADOS)
    if gorra is not None and peinado in ("afro", "mono"):
        peinado = "corto"
    return {
        "peinado": peinado,
        "iris": azar.choice(IRIS),
        "cejas": (azar.uniform(0.022, 0.028), azar.uniform(0.005, 0.0075), 0.006),
        "inclinacion": azar.uniform(2.0, 11.0),
        "gorra": gorra,
        "gafas": azar.random() < 0.28,
        "bigote": azar.random() < 0.22,
        "barba": azar.choice(BARBAS) if azar.random() < 0.25 else None,
        "arrugas": azar.random() < 0.3,
    }
