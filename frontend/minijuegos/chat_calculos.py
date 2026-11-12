# Minijuego «Chat del barrio» (lógica pura, sin ursina): el grupo presiona y hay poco tiempo para responder. Cada respuesta vale
# 2 (protege a tu amigo y ayuda), 1 (a medias) o 0 (cedes un dato de otra persona). Si se acaba el tiempo «te quedas en visto»
# (vale 1). La presión que se ve en pantalla es la fracción de tiempo gastada (en palabras, nunca en números).

import random

from backend.logica.minijuegos import CHAT, ResultadoMinijuego

TIEMPO_POR_DEFECTO = 20.0
VALOR_EN_VISTO = 1
TEXTO_EN_VISTO = "Te quedaste en visto: el chat siguió sin ti."


class PartidaChat:

    def __init__(self, caso, azar=None):
        azar = azar if azar is not None else random.Random()
        self.caso = caso
        self.turnos = []
        for turno in caso["turnos"]:
            opciones = list(turno["opciones"])
            azar.shuffle(opciones)
            self.turnos.append({"de": turno["de"], "texto": turno["texto"], "opciones": opciones,
                                "segundos": float(turno.get("segundos", TIEMPO_POR_DEFECTO))})
        self.indice = 0
        self.restante = self.turnos[0]["segundos"] if self.turnos else 0.0
        self.respuestas = []         # [{"valor", "reaccion", "elegida"}]

    @property
    def terminada(self):
        return self.indice >= len(self.turnos)

    def turno_actual(self):
        return None if self.terminada else self.turnos[self.indice]

    def presion(self):
        """0 (recién llegó el mensaje) .. 1 (se acaba el tiempo)."""
        turno = self.turno_actual()
        if turno is None or turno["segundos"] <= 0:
            return 1.0
        return max(0.0, min(1.0, 1.0 - self.restante / turno["segundos"]))

    def _siguiente(self):
        self.indice += 1
        if not self.terminada:
            self.restante = self.turnos[self.indice]["segundos"]

    def responder(self, i):
        """Responde con la opción i; devuelve la reacción del chat (str) o None si no es válida."""
        turno = self.turno_actual()
        if turno is None or not 0 <= i < len(turno["opciones"]):
            return None
        opcion = turno["opciones"][i]
        self.respuestas.append({"valor": opcion["valor"], "reaccion": opcion.get("reaccion", ""), "elegida": opcion["texto"]})
        self._siguiente()
        return opcion.get("reaccion", "")

    def avanzar(self, dt):
        """Pasa `dt` segundos; si el tiempo del turno se acaba, el jugador se queda en visto. Devuelve la reacción o None."""
        if self.terminada:
            return None
        self.restante -= dt
        if self.restante > 0:
            return None
        self.respuestas.append({"valor": VALOR_EN_VISTO, "reaccion": TEXTO_EN_VISTO, "elegida": None})
        self._siguiente()
        return TEXTO_EN_VISTO

    def datos_cedidos(self):
        return sum(1 for r in self.respuestas if r["valor"] == 0)

    def resultado(self):
        total = 2.0 * len(self.turnos)
        puntos = float(sum(r["valor"] for r in self.respuestas))
        cedidos = self.datos_cedidos()
        detalle = ("Protegiste los datos de tu amigo." if cedidos == 0
                   else "Cediste datos de otra persona para salir del apuro." if cedidos == 1
                   else "Cediste datos de otras personas bajo presión.")
        return ResultadoMinijuego(CHAT, puntos, total, self.terminada, detalle)
