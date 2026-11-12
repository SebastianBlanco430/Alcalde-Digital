# Minijuego «Ordenar la cadena de difusión» (lógica pura, sin ursina): mensajes barajados que el jugador ordena del primero al
# último. Mover sube o baja un mensaje un puesto; «Comprobar» cuenta cuántos quedaron en su puesto. Una sola comprobación.

import random

from backend.logica.minijuegos import CRONOLOGIA, ResultadoMinijuego


class PartidaOrden:

    def __init__(self, caso, azar=None):
        azar = azar if azar is not None else random.Random()
        self.caso = caso
        self.correcto = list(caso["items"])         # orden cronológico real
        n = len(self.correcto)
        indices = list(range(n))
        for _ in range(20):                         # nunca empieza resuelto
            azar.shuffle(indices)
            if indices != list(range(n)) and sum(1 for p, i in enumerate(indices) if p == i) <= max(0, n - 3):
                break
        self.orden = indices                        # orden[pos] = índice cronológico real del mensaje que está en pos
        self.comprobado = False

    @property
    def terminada(self):
        return self.comprobado

    def item(self, pos):
        return self.correcto[self.orden[pos]]

    def mover(self, pos, delta):
        """Mueve el mensaje de `pos` hacia arriba (delta=-1) o abajo (+1). Devuelve su nueva posición."""
        nuevo = pos + delta
        if self.comprobado or not (0 <= pos < len(self.orden)) or not (0 <= nuevo < len(self.orden)):
            return pos
        self.orden[pos], self.orden[nuevo] = self.orden[nuevo], self.orden[pos]
        return nuevo

    def en_su_puesto(self):
        return [self.orden[pos] == pos for pos in range(len(self.orden))]

    def comprobar(self):
        self.comprobado = True

    def resultado(self):
        bien = sum(self.en_su_puesto())
        total = len(self.orden)
        detalle = ("Pusiste toda la cadena en su orden." if bien == total
                   else f"{bien} de {total} mensajes quedaron en su puesto.")
        return ResultadoMinijuego(CRONOLOGIA, float(bien), float(total), self.comprobado, detalle)
