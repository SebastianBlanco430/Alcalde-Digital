# Director de cinemáticas (Ursina): ejecuta una LineaDeTiempo (frontend/cinematica.py, pura y
# con tests) moviendo personaje, puerta y cámara cada frame. El director no sabe QUÉ se mueve:
# recibe un plan [(nombre, duracion)] (frontend/guion_cinematicas.py) y un dict
# {nombre_del_tramo: fn(t)} que la escena rellena; `fn(t)` recibe el avance LINEAL del tramo
# en [0, 1] (aplica ease_in_out si quiere suavizar) y se llama con t = 0 al empezar, cada frame
# y con t = 1 exacto al terminar (también al saltar), así el estado final siempre queda bien.
#
# Duración 0 (`escala=0`, los scripts de prueba): todo se resuelve dentro de reproducir(), sin
# esperar ningún frame. Saltar: una pulsación termina el tramo actual; una segunda dentro de
# SEGUNDOS_DOBLE_SALTO de reloj de cinemática termina TODO lo que falte.

from ursina import Entity, time

from frontend.cinematica import LineaDeTiempo, Tramo

SEGUNDOS_DOBLE_SALTO = 1.0


class DirectorCinematica(Entity):

    def __init__(self, **opciones):
        super().__init__(**opciones)
        self._linea = None
        self._animaciones = {}
        self._al_terminar = None
        self._reloj = 0.0
        self._ultimo_salto = None

    @property
    def activa(self):
        return self._linea is not None and not self._linea.terminada

    # plan: [(nombre, duracion)]; animaciones: {nombre: fn(t)}; escala multiplica las duraciones.
    def reproducir(self, plan, animaciones, al_terminar=None, escala=1.0):
        self._animaciones = animaciones
        self._al_terminar = al_terminar
        self._reloj = 0.0
        self._ultimo_salto = None
        tramos = []
        for nombre, duracion in plan:
            fn = animaciones.get(nombre)
            tramos.append(Tramo(
                nombre, duracion * escala,
                al_empezar=(lambda fn=fn: fn(0.0)) if fn else None,
                al_terminar=(lambda fn=fn: fn(1.0)) if fn else None))
        self._linea = LineaDeTiempo(tramos, al_terminar=self._terminar)
        self._linea.avanzar(0)               # arranca; los tramos de duración 0 se resuelven aquí

    def update(self):
        self.avanzar(time.dt)

    # Un paso de `dt` segundos (los tests y scripts lo llaman a mano).
    def avanzar(self, dt):
        if not self.activa:
            return
        self._reloj += max(0.0, dt)
        linea = self._linea
        linea.avanzar(dt)
        if self._linea is linea and not linea.terminada:
            tramo = linea.tramo_actual()
            fn = self._animaciones.get(tramo.nombre)
            if fn is not None:
                fn(linea.progreso_tramo())

    # Espacio / Enter: termina el tramo actual; dos seguidas, todo. Devuelve True si había
    # una cinemática en curso.
    def saltar(self):
        if not self.activa:
            return False
        doble = (self._ultimo_salto is not None
                 and self._reloj - self._ultimo_salto <= SEGUNDOS_DOBLE_SALTO)
        self._ultimo_salto = self._reloj
        if doble:
            self._linea.saltar_todo()
        else:
            self._linea.saltar()
        return True

    # Detiene sin disparar el callback final (al salir de la escena).
    def cancelar(self):
        self._linea = None
        self._al_terminar = None

    def _terminar(self):
        callback, self._al_terminar = self._al_terminar, None
        if callback is not None:
            callback()
