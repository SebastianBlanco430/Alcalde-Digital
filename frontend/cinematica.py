# Línea de tiempo de las cinemáticas (Python puro: NO importa ursina). Una LineaDeTiempo es
# una lista de Tramos que se recorren en orden; cada tramo tiene una duración y dos
# callbacks opcionales (al empezar y al terminar). El DirectorCinematica (Ursina) la avanza
# cada frame con `avanzar(dt)` y, mientras tanto, mueve personaje, puerta y cámara usando
# `progreso_tramo()` (0..1) con las interpolaciones de abajo.
#
# Garantías (probadas): cada callback se dispara UNA vez y en orden, aunque un dt enorme
# cruce varios tramos; un tramo de duración 0 es instantáneo (incluso con dt = 0), así que
# un script de prueba con todo en 0 termina en el primer avanzar; `saltar()` termina el
# tramo actual y `saltar_todo()` el resto. Si un callback lanza, la línea ya avanzó su
# estado: al reintentar no se vuelve a llamar.

from dataclasses import dataclass
from typing import Callable, Optional

from frontend.geometria_mundo import normalizar_angulo


@dataclass(frozen=True)
class Tramo:
    nombre: str
    duracion: float
    al_empezar: Optional[Callable[[], None]] = None
    al_terminar: Optional[Callable[[], None]] = None


class LineaDeTiempo:

    # `al_terminar` se llama una vez cuando acaba el último tramo. ValueError si algún
    # tramo tiene duración negativa.
    def __init__(self, tramos, al_terminar=None):
        self._tramos = list(tramos)
        if any(t.duracion < 0 for t in self._tramos):
            raise ValueError("La duración de un tramo no puede ser negativa.")
        self._al_terminar = al_terminar
        self._indice = 0
        self._tiempo = 0.0           # tiempo dentro del tramo actual
        self._empezado = False       # ¿ya se disparó el al_empezar del tramo actual?
        self._terminada = False

    # -- Consulta --

    @property
    def terminada(self):
        return self._terminada

    # Tramo en curso, o None si ya terminó.
    def tramo_actual(self):
        return None if self._terminada else self._tramos[self._indice]

    # Avance dentro del tramo actual en [0, 1] (1 si terminó o el tramo dura 0).
    def progreso_tramo(self):
        if self._terminada:
            return 1.0
        duracion = self._tramos[self._indice].duracion
        return 1.0 if duracion == 0 else min(1.0, self._tiempo / duracion)

    # -- Avance --

    # Avanza `dt` segundos (dt <= 0 solo procesa tramos de duración 0). Puede cruzar varios
    # tramos en una sola llamada.
    def avanzar(self, dt):
        restante = max(0.0, dt)
        self._cerrar_si_vacia()
        while not self._terminada:
            self._empezar()
            falta = self._tramos[self._indice].duracion - self._tiempo
            if restante < falta:
                self._tiempo += restante
                return
            restante -= falta
            self._terminar_tramo()

    # Termina el tramo actual (sus callbacks se disparan) y pasa al siguiente.
    def saltar(self):
        self._cerrar_si_vacia()
        if self._terminada:
            return
        self._empezar()
        self._terminar_tramo()
        if not self._terminada:
            self._empezar()

    # Termina todo lo que falte, en orden.
    def saltar_todo(self):
        while not self._terminada:
            self.saltar()

    # -- Internos --

    # Una línea sin tramos termina en el primer avance (y avisa una sola vez).
    def _cerrar_si_vacia(self):
        if not self._tramos and not self._terminada:
            self._terminada = True
            self._llamar(self._al_terminar)

    # Dispara el al_empezar del tramo actual (una sola vez).
    def _empezar(self):
        if self._empezado or self._terminada:
            return
        self._empezado = True
        self._llamar(self._tramos[self._indice].al_empezar)

    # Cierra el tramo actual: avanza el estado ANTES de llamar al callback.
    def _terminar_tramo(self):
        tramo = self._tramos[self._indice]
        self._indice += 1
        self._tiempo = 0.0
        self._empezado = False
        ultimo = self._indice >= len(self._tramos)
        if ultimo:
            self._terminada = True
            self._indice = max(0, len(self._tramos) - 1)
        self._llamar(tramo.al_terminar)
        if ultimo:
            self._llamar(self._al_terminar)

    @staticmethod
    def _llamar(callback):
        if callback is not None:
            callback()

    def __repr__(self):
        actual = self.tramo_actual()
        return f"LineaDeTiempo(tramo={actual.nombre if actual else None!r}, terminada={self._terminada})"


# -- Interpolaciones ---------------------------------------------------------------------------


# Suavizado de arranque y frenado: t²(3 − 2t), con t limitado a [0, 1].
def ease_in_out(t):
    t = min(1.0, max(0.0, t))
    return t * t * (3 - 2 * t)


# a + (b − a)·t (no limita t).
def lerp(a, b, t):
    return a + (b - a) * t


# Como lerp pero entre ángulos en grados, por el camino corto.
def lerp_angulo(a, b, t):
    return a + normalizar_angulo(b - a) * t


# lerp componente a componente de dos vectores de 3 valores.
def lerp_vec3(a, b, t):
    return tuple(lerp(a[i], b[i], t) for i in range(3))
