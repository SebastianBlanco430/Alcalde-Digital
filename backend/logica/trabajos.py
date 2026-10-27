# Trabajos (modelo puro): turnos de 60-90 s con un minijuego por puesto. Tres motores:
#   ATENDER   - pedido «2 pan + 1 café»; teclas 1-4 = las 4 opciones del puesto.
#   SECUENCIA - repetir una secuencia de direcciones (flechas / teclas).
#   BARRA     - detener una barra que va y viene dentro de la zona verde.
# TurnoTrabajo(trabajo, semilla) es determinista: avanzar(dt) mueve el reloj, accion(entrada) -> bool
# (True = acierto), terminado(), resultado() -> {aciertos, errores, rendimiento, pago, fatiga}.
# pago = round(pago_base + (pago_max - pago_base) * rendimiento). Sin ursina: la vista 2D vive en frontend/.

import math
import random
from dataclasses import dataclass

ATENDER, SECUENCIA, BARRA = "atender", "secuencia", "barra"
MOTORES = (ATENDER, SECUENCIA, BARRA)
FATIGA_AGOTADO = 100
MENSAJE_AGOTADO = "Estás agotado: come algo o espera tu turno"

# Segundos por acción que se espera de un buen jugador (define la meta de aciertos del turno).
RITMO_S = {ATENDER: 2.5, SECUENCIA: 1.2, BARRA: 5.0}
PENALIZA_ERROR = 0.5            # un error resta medio acierto
BARRA_VUELTAS_POR_S = 0.45      # viajes completos ida y vuelta por segundo
BARRA_ZONA = 0.22               # ancho de la zona verde (0..1)
LARGO_SECUENCIA = (4, 6)
PEDIDO_UNIDADES = (2, 4)


@dataclass(frozen=True)
class Trabajo:
    id: str
    nombre: str
    motor: str
    duracion_s: float
    pago_base: int
    pago_max: int
    fatiga: int
    opciones: tuple = ()        # ATENDER: 4 productos (teclas 1-4); SECUENCIA: las direcciones/teclas

    def __post_init__(self):
        if self.motor not in MOTORES:
            raise ValueError(f"Motor de trabajo inválido: {self.motor!r}")
        if not (self.duracion_s > 0 and 0 <= self.pago_base <= self.pago_max):
            raise ValueError(f"Trabajo {self.id!r}: duración o pagos inválidos.")
        if self.motor == ATENDER and len(self.opciones) != 4:
            raise ValueError(f"Trabajo {self.id!r}: ATENDER necesita 4 opciones.")
        if self.motor == SECUENCIA and len(self.opciones) < 2:
            raise ValueError(f"Trabajo {self.id!r}: SECUENCIA necesita al menos 2 opciones.")


def puede_trabajar(perfil):
    return perfil.fatiga < FATIGA_AGOTADO


class TurnoTrabajo:

    def __init__(self, trabajo, semilla=0):
        self.trabajo = trabajo
        self._rng = random.Random(semilla)
        self._t = 0.0
        self._aciertos = 0
        self._errores = 0
        self._pedido = {}
        self._entregado = {}
        self._secuencia = []
        self._indice = 0
        self._centro = 0.5
        if trabajo.motor == ATENDER:
            self._nuevo_pedido()
        elif trabajo.motor == SECUENCIA:
            self._nueva_secuencia()
        else:
            self._nueva_zona()

    # -- Reloj --

    def avanzar(self, dt):
        if isinstance(dt, bool) or not isinstance(dt, (int, float)) or not math.isfinite(dt) or dt <= 0:
            return
        self._t = min(self._t + dt, self.trabajo.duracion_s)

    def tiempo(self):
        return self._t

    def tiempo_restante(self):
        return max(0.0, self.trabajo.duracion_s - self._t)

    def terminado(self):
        return self._t >= self.trabajo.duracion_s

    # -- Entradas --

    # True = acierto. Entradas que no son del motor (o con el turno terminado) se ignoran: False sin penalizar.
    def accion(self, entrada):
        if self.terminado():
            return False
        motor = self.trabajo.motor
        if motor == ATENDER:
            return self._accion_atender(entrada)
        if motor == SECUENCIA:
            return self._accion_secuencia(entrada)
        return self._accion_barra()

    def _acierto(self):
        self._aciertos += 1
        return True

    def _error(self):
        self._errores += 1
        return False

    # -- ATENDER --

    def _nuevo_pedido(self):
        opciones = list(self.trabajo.opciones)
        total = self._rng.randint(*PEDIDO_UNIDADES)
        self._pedido = {}
        for _ in range(total):
            producto = self._rng.choice(opciones)
            self._pedido[producto] = self._pedido.get(producto, 0) + 1
        self._entregado = {}

    def _accion_atender(self, entrada):
        if isinstance(entrada, bool) or not isinstance(entrada, (int, str)):
            return False
        try:
            numero = int(entrada)
        except ValueError:
            return False
        if not 1 <= numero <= 4:
            return False
        producto = self.trabajo.opciones[numero - 1]
        if self._entregado.get(producto, 0) >= self._pedido.get(producto, 0):
            self._entregado = {}            # se pasó o pidió otra cosa: empieza de nuevo el pedido
            return self._error()
        self._entregado[producto] = self._entregado.get(producto, 0) + 1
        self._acierto()
        if self._entregado == self._pedido:
            self._nuevo_pedido()
        return True

    # Texto del pedido actual, p. ej. «2 pan + 1 café».
    def pedido_texto(self):
        return " + ".join(f"{n} {p}" for p, n in self._pedido.items())

    def pedido(self):
        return dict(self._pedido)

    def entregado(self):
        return dict(self._entregado)

    # -- SECUENCIA --

    def _nueva_secuencia(self):
        largo = self._rng.randint(*LARGO_SECUENCIA)
        self._secuencia = [self._rng.choice(self.trabajo.opciones) for _ in range(largo)]
        self._indice = 0

    def _accion_secuencia(self, entrada):
        if not isinstance(entrada, str) or entrada not in self.trabajo.opciones:
            return False
        if entrada != self._secuencia[self._indice]:
            self._indice = 0
            return self._error()
        self._indice += 1
        self._acierto()
        if self._indice >= len(self._secuencia):
            self._nueva_secuencia()
        return True

    def secuencia(self):
        return list(self._secuencia)

    def progreso(self):
        return self._indice

    # -- BARRA --

    def _nueva_zona(self):
        mitad = BARRA_ZONA / 2
        self._centro = self._rng.uniform(0.15 + mitad, 0.85 - mitad)

    # Posición de la barra (0..1), ida y vuelta según el reloj.
    def posicion_barra(self):
        fase = (self._t * BARRA_VUELTAS_POR_S * 2) % 2.0
        return fase if fase <= 1.0 else 2.0 - fase

    def zona_barra(self):
        return (self._centro - BARRA_ZONA / 2, self._centro + BARRA_ZONA / 2)

    def _accion_barra(self):
        ini, fin = self.zona_barra()
        dentro = ini <= self.posicion_barra() <= fin
        self._nueva_zona()
        return self._acierto() if dentro else self._error()

    # -- Resultado --

    def meta_aciertos(self):
        return max(1, round(self.trabajo.duracion_s / RITMO_S[self.trabajo.motor]))

    def rendimiento(self):
        puntos = self._aciertos - PENALIZA_ERROR * self._errores
        return max(0.0, min(1.0, puntos / self.meta_aciertos()))

    def resultado(self):
        t = self.trabajo
        rendimiento = self.rendimiento()
        return {
            "aciertos": self._aciertos,
            "errores": self._errores,
            "rendimiento": rendimiento,
            "pago": round(t.pago_base + (t.pago_max - t.pago_base) * rendimiento),
            "fatiga": t.fatiga,
        }
