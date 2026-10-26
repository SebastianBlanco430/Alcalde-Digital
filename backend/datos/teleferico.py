# Trazado del teleférico del mapa grande (datos PUROS, sin ursina): la polilínea del cable entre la Estação do
# Teleférico y la Estação Alto do Morro (~430 m), las torres, y el tiempo/posición de una cabina a lo largo del cable.
#
#   construir_trazado(mundo) -> Trazado   (determinista: depende solo de las alturas del mundo)
#   Trazado.posicion(u)      -> (x, y, z) del CABLE en la fracción u (0 = estación de abajo, 1 = Alto do Morro)
#   Trazado.rumbo(u)         -> rumbo (grados, convención de Ursina) del cable en u
#   avance(t)                -> fracción u de una cabina t segundos después de salir (arranque y frenada suaves)
#   fase_ambiente(t)         -> (u_a, u_b) de las dos cabinas decorativas que suben y bajan siempre
#
# Las torres suben lo justo para que el cable pase HOLGURA_M sobre el terreno (y las casas, que no pasan de ~12 m)
# en todo el vano; entre torres el cable cuelga un poco (comba parabólica). La cabina cuelga ALTO_PERCHA del cable.

import math

from backend.logica.viaje_rapido import ESTACIONES

TRAYECTO_S = 40.0            # s que dura el trayecto animado (se pidieron 25-45 s)
ESPERA_ESTACION_S = 8.0      # s que las cabinas decorativas esperan en cada estación
TRAMO_M = 62.0               # separación aproximada entre torres
HOLGURA_M = 24.0             # m mínimos del cable sobre el terreno (casas y muros incluidos)
ALTO_ESTACION = 11.2         # m: el techo de la estación (alto del edificio) donde amarra el cable
SOBRE_TECHO = 1.6            # m sobre el techo
ALTO_PERCHA = 3.0            # m que cuelga la cabina bajo el cable
COMBA_M = 0.9                # flecha máxima de la comba entre dos torres
PENDIENTE_MAX = 0.46         # tan(25°): tope de inclinación entre torres consecutivas
RADIO_MUESTRA = 9.0          # m: el terreno se mide alrededor de cada torre


class Trazado:
    """Polilínea del cable. `torres`: [(x, y, z)] de la estación de abajo a la de arriba (la primera y la última son las
    estaciones). Longitud acumulada para convertir una fracción u en distancia."""

    def __init__(self, torres):
        if len(torres) < 2:
            raise ValueError("El trazado necesita al menos dos torres.")
        self.torres = [tuple(float(c) for c in t) for t in torres]
        self._acum = [0.0]
        for a, b in zip(self.torres, self.torres[1:]):
            self._acum.append(self._acum[-1] + math.dist(a, b))
        self.largo = self._acum[-1]

    def _tramo(self, u):
        s = min(1.0, max(0.0, float(u))) * self.largo
        i = 1
        while i < len(self._acum) - 1 and self._acum[i] < s:
            i += 1
        a, b = self.torres[i - 1], self.torres[i]
        largo = self._acum[i] - self._acum[i - 1]
        k = 0.0 if largo <= 0 else (s - self._acum[i - 1]) / largo
        return a, b, k

    def posicion(self, u):
        a, b, k = self._tramo(u)
        x = a[0] + (b[0] - a[0]) * k
        z = a[2] + (b[2] - a[2]) * k
        y = a[1] + (b[1] - a[1]) * k - COMBA_M * 4.0 * k * (1.0 - k)       # cuelga entre torres, firme en ellas
        return x, y, z

    def rumbo(self, u):
        a, b, _ = self._tramo(u)
        return math.degrees(math.atan2(b[0] - a[0], b[2] - a[2]))


def _punto_de_estacion(mundo, estacion_id):
    lugar = ESTACIONES[estacion_id].lugar
    edificio = mundo.edificio_de(lugar)
    x0, x1, z0, z1 = edificio.caja()
    cx, cz = (x0 + x1) / 2, (z0 + z1) / 2                  # el cable amarra en el centro del edificio (no en la puerta)
    y = float(mundo.altura(cx, cz)) + max(ALTO_ESTACION, float(edificio.alto)) + SOBRE_TECHO
    return (cx, y, cz)


def _terreno_max(mundo, x, z, radio=RADIO_MUESTRA):
    m = float(mundo.altura(x, z))
    for k in range(8):
        a = k * math.pi / 4
        m = max(m, float(mundo.altura(x + math.cos(a) * radio, z + math.sin(a) * radio)))
    return m


def construir_trazado(mundo, de="tele_base", a="tele_alta"):
    """Trazado del cable de la estación `de` a la `a`. Las torres intermedias se alzan sobre el terreno."""
    (ax, ay, az), (bx, by, bz) = _punto_de_estacion(mundo, de), _punto_de_estacion(mundo, a)
    largo = math.hypot(bx - ax, bz - az)
    tramos = max(2, int(round(largo / TRAMO_M)))
    alturas = []
    puntos = []
    for i in range(tramos + 1):
        t = i / tramos
        x, z = ax + (bx - ax) * t, az + (bz - az) * t
        lineal = ay + (by - ay) * t
        alturas.append(max(lineal, _terreno_max(mundo, x, z) + HOLGURA_M))
        puntos.append((x, z))
    alturas[0], alturas[-1] = ay, by
    # Suavizado: ninguna torre queda por debajo de la media de sus vecinas menos un poco, y las pendientes se limitan
    # (así no hay picos feos): dos pasadas de «al menos la media de los vecinos» y luego el tope de pendiente.
    for _ in range(2):
        for i in range(1, tramos):
            alturas[i] = max(alturas[i], (alturas[i - 1] + alturas[i + 1]) / 2.0)
    paso = largo / tramos
    for i in range(1, tramos):                       # hacia delante y hacia atrás: |dy| <= PENDIENTE_MAX * paso
        alturas[i] = max(alturas[i], alturas[i - 1] - PENDIENTE_MAX * paso)
    for i in range(tramos - 1, 0, -1):
        alturas[i] = max(alturas[i], alturas[i + 1] - PENDIENTE_MAX * paso)
    return Trazado([(x, y, z) for (x, z), y in zip(puntos, alturas)])


def _suave(t):
    t = min(1.0, max(0.0, t))
    return t * t * (3.0 - 2.0 * t)


def avance(t, duracion=TRAYECTO_S):
    """Fracción (0..1) del recorrido que lleva una cabina t segundos después de salir: arranca y frena suavemente."""
    return _suave(float(t) / duracion)


def fase_ambiente(t):
    """(u_a, u_b) de las dos cabinas decorativas en el instante t del mundo: una sube mientras la otra baja, esperan
    ESPERA_ESTACION_S en cada estación y repiten. Determinista (sin sincronizar entre jugadores)."""
    ciclo = 2.0 * (TRAYECTO_S + ESPERA_ESTACION_S)
    r = float(t) % ciclo
    if r < ESPERA_ESTACION_S:
        u = 0.0
    elif r < ESPERA_ESTACION_S + TRAYECTO_S:
        u = avance(r - ESPERA_ESTACION_S)
    elif r < 2 * ESPERA_ESTACION_S + TRAYECTO_S:
        u = 1.0
    else:
        u = 1.0 - avance(r - 2 * ESPERA_ESTACION_S - TRAYECTO_S)
    return u, 1.0 - u
