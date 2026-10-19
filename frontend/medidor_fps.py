# Medidor de FPS opcional (diagnóstico de rendimiento). Se activa con la variable de entorno
# ALCALDE_FPS al lanzar main.py:
#   ALCALDE_FPS=1      registra los FPS con el tope normal del juego (60).
#   ALCALDE_FPS=libre  además quita el tope, para ver cuánto margen hay por encima de 60.
#
# Cada INTERVALO segundos imprime una línea con los FPS medio, mínimo y "1 % bajo" (la media del
# 1 % de frames más lentos, que es lo que se nota como tirones). Al cerrar imprime el resumen
# de toda la sesión. Los frames de carga (dt > DT_DESCARTE) no cuentan.

import atexit
import os

from ursina import Entity, time

VARIABLE = "ALCALDE_FPS"
INTERVALO = 5.0          # s entre líneas del registro
DT_DESCARTE = 0.5        # s: frames más largos son cargas de escena, no rendimiento


def modo():
    # "" (apagado), "1" o "libre".
    return os.environ.get(VARIABLE, "").strip().lower()


# (media, mínimo, 1 % bajo) en FPS de una lista de dt en segundos.
def resumir(dts):
    if not dts:
        return 0.0, 0.0, 0.0
    lentos = sorted(dts, reverse=True)[:max(1, len(dts) // 100)]
    return len(dts) / sum(dts), 1 / max(dts), len(lentos) / sum(lentos)


def _linea(etiqueta, dts):
    media, minimo, bajo = resumir(dts)
    return f"[FPS] {etiqueta}: media {media:5.1f} | mínimo {minimo:5.1f} | 1 % bajo {bajo:5.1f} ({len(dts)} frames)"


class MedidorFps(Entity):

    def __init__(self, **opciones):
        super().__init__(ignore_paused=True, **opciones)
        self.todos = []
        self._tramo = []
        atexit.register(self.imprimir_resumen)

    def update(self):
        dt = time.dt
        if not 0 < dt <= DT_DESCARTE:
            return
        self.todos.append(dt)
        self._tramo.append(dt)
        if sum(self._tramo) >= INTERVALO:
            print(_linea("últimos 5 s", self._tramo), flush=True)
            self._tramo = []

    def imprimir_resumen(self):
        if self.todos:
            print(_linea("sesión", self.todos), flush=True)
            self.todos = []
