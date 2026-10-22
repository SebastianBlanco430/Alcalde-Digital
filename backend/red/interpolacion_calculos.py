# Interpolación de jugadores REMOTOS en el cliente (módulo PURO: sin red, sin ursina, sin panda3d).
# El anfitrión manda snapshots a ~20 Hz con su propio reloj `t` (s). Aquí se guardan los últimos 3-5 estados de
# cada jugador remoto y se dibuja el jugador RETARDO s en el pasado, para casi siempre tener un estado
# anterior y otro posterior entre los que interpolar:
#   - posición (x, z, y) con interpolación lineal; rumbo con `lerp_angulo` por el camino corto.
#   - sin estado posterior: se extrapola con la última velocidad hasta EXTRAPOLACION_MAX s y luego se queda quieto.
#   - más de INESTABLE_S s sin recibir nada: estado «inestable» (la UI avisa «Conexión inestable»).
#   - el reloj del anfitrión y el local no coinciden: el desfase (recibido_local - t) se estima con el MÍNIMO de
#     una ventana móvil (el paquete que menos tardó) y se suaviza para que el avatar no dé tirones.
#   - un salto de posición mayor que UMBRAL_TELEPORTE m es un teletransporte (reaparición): se vacía el búfer
#     y la muestra lo señala UNA vez para que la escena coloque el avatar sin deslizarlo.

import math
import time
from collections import deque
from dataclasses import dataclass

RETARDO = 0.100               # s que se dibuja en el pasado
CAPACIDAD_MIN = 3
CAPACIDAD_MAX = 5
EXTRAPOLACION_MAX = 0.200     # s máximos de extrapolación con la última velocidad
INESTABLE_S = 0.500           # s sin snapshot para declarar la conexión inestable
UMBRAL_TELEPORTE = 10.0       # m (horizontal) entre dos snapshots seguidos
UMBRAL_TELEPORTE_VERTICAL = 15.0   # m (vertical)
VENTANA_RELOJ = 64            # muestras de desfase de la ventana del mínimo móvil
SUAVIZADO_RELOJ = 0.10        # fracción por muestra con que el desfase suave persigue al mínimo

ESTADO_VACIO = "vacio"
ESTADO_NORMAL = "normal"
ESTADO_EXTRAPOLANDO = "extrapolando"
ESTADO_INESTABLE = "inestable"


# Diferencia más corta de ángulos en grados, en (-180, 180]: positiva = girar en sentido positivo.
def diferencia_angulo(a, b):
    d = (b - a) % 360.0
    return d - 360.0 if d > 180.0 else d


# Interpola el ángulo `a` hacia `b` (grados) una fracción t por el camino corto; resultado en [0, 360).
def lerp_angulo(a, b, t):
    return (a + diferencia_angulo(a, b) * t) % 360.0


def lerp(a, b, t):
    return a + (b - a) * t


@dataclass(frozen=True)
class Estado:
    t: float                  # reloj del anfitrión (s)
    x: float
    z: float
    y: float
    r: float = 0.0            # rumbo en grados (rotation_y de Ursina: adelante = (sin r, cos r))
    v: float = 0.0            # velocidad (m/s)
    f: int = 0                # banderas (en_aire, escalera, dentro, vehículo)


@dataclass(frozen=True)
class Muestra:
    x: float
    z: float
    y: float
    r: float
    v: float
    f: int
    estado: str               # ESTADO_*
    teletransporte: bool      # True una sola vez tras un salto grande: colocar sin deslizar


class InterpoladorRemoto:
    # `reloj`: función sin argumentos con segundos locales (time.monotonic por defecto, inyectable en tests).
    def __init__(self, reloj=time.monotonic, retardo=RETARDO, capacidad=CAPACIDAD_MAX,
                 umbral_teleporte=UMBRAL_TELEPORTE):
        self.reloj = reloj
        self.retardo = float(retardo)
        self.capacidad = max(CAPACIDAD_MIN, min(CAPACIDAD_MAX, int(capacidad)))
        self.umbral_teleporte = float(umbral_teleporte)
        self._estados = deque(maxlen=self.capacidad)
        self._desfases = deque(maxlen=VENTANA_RELOJ)
        self._desfase = None              # desfase suavizado (local - anfitrión)
        self._recibido = None             # reloj local del último snapshot aceptado
        self._tp_pendiente = False

    def __len__(self):
        return len(self._estados)

    # Desfase de reloj suavizado (local - anfitrión), None si aún no hay datos.
    @property
    def desfase(self):
        return self._desfase

    # Añade un snapshot con tiempo `t` del anfitrión. `recibido` = reloj local de la llegada (por defecto, ahora).
    # Devuelve True si se guardó; los duplicados y los que llegan tarde (t no creciente) se descartan.
    def agregar(self, t, x, z, y=0.0, r=0.0, v=0.0, f=0, recibido=None):
        valores = (t, x, z, y, r, v)
        if any(isinstance(a, bool) or not isinstance(a, (int, float)) or not math.isfinite(a) for a in valores):
            return False
        if self._estados and t <= self._estados[-1].t:
            return False
        ahora = self.reloj() if recibido is None else recibido
        self._actualizar_desfase(ahora - t)
        nuevo = Estado(float(t), float(x), float(z), float(y), float(r), float(v), int(f))
        if self._estados:
            ult = self._estados[-1]
            if (math.hypot(nuevo.x - ult.x, nuevo.z - ult.z) > self.umbral_teleporte
                    or abs(nuevo.y - ult.y) > UMBRAL_TELEPORTE_VERTICAL):
                self._estados.clear()
                self._tp_pendiente = True
        self._estados.append(nuevo)
        self._recibido = ahora
        return True

    # Segundos locales desde el último snapshot (None si nunca llegó uno).
    def silencio(self, ahora=None):
        if self._recibido is None:
            return None
        return (self.reloj() if ahora is None else ahora) - self._recibido

    def inestable(self, ahora=None):
        s = self.silencio(ahora)
        return s is not None and s > INESTABLE_S

    # Tiempo del anfitrión que toca dibujar ahora (ya con el retardo restado), None si no hay datos.
    def tiempo_de_dibujo(self, ahora=None):
        if self._desfase is None:
            return None
        return (self.reloj() if ahora is None else ahora) - self._desfase - self.retardo

    # Muestra a dibujar ahora. Sin snapshots devuelve None.
    def muestrear(self, ahora=None):
        if not self._estados:
            return None
        ahora = self.reloj() if ahora is None else ahora
        td = ahora - self._desfase - self.retardo
        estados = self._estados
        tp = self._tp_pendiente
        self._tp_pendiente = False
        inestable = self.inestable(ahora)
        primero, ultimo = estados[0], estados[-1]
        if td <= primero.t:
            return self._de_estado(primero, ESTADO_INESTABLE if inestable else ESTADO_NORMAL, tp)
        if td <= ultimo.t:
            a, b = primero, ultimo
            for e in estados:
                if e.t <= td:
                    a = e
                else:
                    b = e
                    break
            k = (td - a.t) / (b.t - a.t)
            return Muestra(lerp(a.x, b.x, k), lerp(a.z, b.z, k), lerp(a.y, b.y, k), lerp_angulo(a.r, b.r, k),
                           lerp(a.v, b.v, k), a.f, ESTADO_INESTABLE if inestable else ESTADO_NORMAL, tp)
        # Sin estado posterior: extrapolar con la última velocidad (limitado) y luego quedarse quieto.
        extra = min(td - ultimo.t, EXTRAPOLACION_MAX)
        vx, vz = self._velocidad_vectorial()
        estado = ESTADO_INESTABLE if inestable else ESTADO_EXTRAPOLANDO
        return Muestra(ultimo.x + vx * extra, ultimo.z + vz * extra, ultimo.y, ultimo.r, ultimo.v, ultimo.f,
                       estado, tp)

    # -- Internos --

    # Velocidad (m/s) del último tramo; con un solo estado, la derivada de (v, r).
    def _velocidad_vectorial(self):
        if len(self._estados) >= 2:
            a, b = self._estados[-2], self._estados[-1]
            dt = b.t - a.t
            if dt > 0:
                return ((b.x - a.x) / dt, (b.z - a.z) / dt)
        e = self._estados[-1]
        rad = math.radians(e.r)
        return (math.sin(rad) * e.v, math.cos(rad) * e.v)

    def _de_estado(self, e, estado, tp):
        return Muestra(e.x, e.z, e.y, e.r, e.v, e.f, estado, tp)

    # Mínimo móvil del desfase observado + suavizado exponencial hacia él.
    def _actualizar_desfase(self, observado):
        self._desfases.append(observado)
        minimo = min(self._desfases)
        if self._desfase is None:
            self._desfase = minimo
        else:
            self._desfase += (minimo - self._desfase) * SUAVIZADO_RELOJ
