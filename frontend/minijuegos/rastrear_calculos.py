# Minijuego «Rastrear la fuente» (lógica pura, sin ursina): el jugador sigue la cadena de reenvíos hacia atrás, salto a salto,
# eligiendo en cada uno el mensaje MÁS ANTIGUO y que no es un reenvío. Cada error resta medio acierto; con MAX_ERRORES se pierde el
# rastro. Datos: backend/datos/minijuegos_casos.RASTREAR (ya preparados por backend.logica.minijuegos.preparar_caso).

import random

from backend.logica.minijuegos import RASTREAR, ResultadoMinijuego

MAX_ERRORES = 3
PENALIZACION_ERROR = 0.5


class PartidaRastreo:

    def __init__(self, caso, azar=None):
        azar = azar if azar is not None else random.Random()
        self.caso = caso
        self.saltos = []
        for salto in caso["hops"]:
            opciones = list(salto["opciones"])
            correcta = opciones[0]                     # en los datos la primera es la correcta
            azar.shuffle(opciones)
            indice = next(i for i, o in enumerate(opciones) if o is correcta)
            self.saltos.append({"pregunta": salto["pregunta"], "opciones": opciones, "correcta": indice,
                                "descartadas": set()})
        self.indice = 0
        self.errores = 0
        self.resueltos = 0

    @property
    def llegado(self):
        return self.resueltos >= len(self.saltos)

    @property
    def perdido(self):
        return self.errores >= MAX_ERRORES

    @property
    def terminada(self):
        return self.llegado or self.perdido

    def salto_actual(self):
        return None if self.terminada else self.saltos[self.indice]

    def origen(self):
        """Lo que se encuentra al final de la cadena (titulo/detalle); None si aún no se llegó."""
        return self.caso["origen"] if self.llegado else None

    # Elige la opción i del salto actual: "bien" (avanza), "error" (se descarta esa opción) o None (ya terminó / no válida).
    def elegir(self, i):
        salto = self.salto_actual()
        if salto is None or not 0 <= i < len(salto["opciones"]) or i in salto["descartadas"]:
            return None
        if i == salto["correcta"]:
            self.resueltos += 1
            self.indice += 1
            return "bien"
        salto["descartadas"].add(i)
        self.errores += 1
        return "error"

    def resultado(self):
        total = len(self.saltos)
        puntos = max(0.0, self.resueltos - PENALIZACION_ERROR * self.errores)
        if self.llegado:
            detalle = "Llegaste al origen del mensaje." if self.errores == 0 else "Llegaste al origen, con algún rodeo."
        else:
            detalle = "Perdiste el rastro antes de llegar al origen."
        return ResultadoMinijuego(RASTREAR, puntos, total, self.terminada, detalle)
