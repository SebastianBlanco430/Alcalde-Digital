# Efecto glitch de entrada y salida del mundo digital (Ursina): bandas horizontales con los colores GLITCH_A y
# GLITCH_B de frontend/materiales.py y un velo oscuro que tapa la pantalla en el pico, para cambiar de escena sin que
# se vea el salto. Vive en camera.ui, FUERA de las escenas (como el destello del interior): sigue vivo aunque la
# escena que lo lanzó ya se haya desactivado. Está desactivado (sin update) mientras no se usa.
#
# Dos modos: `poner(intensidad)` lo fija a mano (lo usa la animación del computador, que ya tiene su línea de
# tiempo) y `subir(duracion, al_terminar)` / `desvanecer(duracion)` lo mueven solos con update().

from ursina import Entity, camera, color, time

from frontend import materiales
from frontend import mundo_digital_calculos as calc
from frontend.componentes import rgb

BANDAS = 14
CUADROS_POR_SEGUNDO = 24          # las bandas cambian a saltos, como un glitch de verdad
ANCHO_BANDA = 2.4


class GlitchOverlay(Entity):

    def __init__(self, **opciones):
        opciones.setdefault("parent", camera.ui)
        super().__init__(z=-95, enabled=False, **opciones)
        self.intensidad = 0.0
        self._modo = None                 # None | "subir" | "bajar"
        self._duracion = 0.0
        self._t = 0.0
        self._al_terminar = None
        self._cuadro = -1
        self._velo = Entity(parent=self, model="quad", scale=(4, 4), color=color.rgba32(*materiales.DIGITAL_FONDO, 0), z=0.01)
        self._bandas = [Entity(parent=self, model="quad", color=color.clear, scale=(ANCHO_BANDA, 0.02))
                        for _ in range(BANDAS)]
        self._colores = (rgb(materiales.GLITCH_A), rgb(materiales.GLITCH_B))

    # -- Control --

    def poner(self, intensidad):
        self._modo = None
        self.intensidad = max(0.0, min(1.0, intensidad))
        self._aplicar(forzar=True)

    # Sube de 0 a 1 en `duracion` s y llama a `al_terminar()` con la pantalla cubierta.
    def subir(self, duracion, al_terminar=None):
        self._arrancar("subir", duracion, 0.0, al_terminar)

    # Baja de la intensidad actual a 0 en `duracion` s y se apaga.
    def desvanecer(self, duracion=calc.DURACION_GLITCH_SALIDA):
        self._arrancar("bajar", duracion, self.intensidad, None)

    def _arrancar(self, modo, duracion, desde, al_terminar):
        self._modo, self._duracion, self._al_terminar = modo, max(duracion, 1e-3), al_terminar
        self.intensidad = desde
        self._t = 0.0
        self._aplicar(forzar=True)

    def cancelar(self):
        self._modo, self._al_terminar = None, None
        self.poner(0.0)

    @property
    def activo(self):
        return self.enabled

    # -- Frame --

    def update(self):
        self.avanzar(time.dt)

    def avanzar(self, dt):
        if self._modo is None:
            return
        self._t += max(0.0, dt)
        k = min(1.0, self._t / self._duracion)
        self.intensidad = k if self._modo == "subir" else max(0.0, self.intensidad - dt / self._duracion)
        self._aplicar()
        if self._modo == "subir" and k >= 1.0:
            callback, self._modo, self._al_terminar = self._al_terminar, None, None
            if callback is not None:
                callback()
        elif self._modo == "bajar" and self.intensidad <= 0.0:
            self._modo = None
            self._aplicar(forzar=True)

    def _aplicar(self, forzar=False):
        i = self.intensidad
        self.enabled = i > 0 or self._modo is not None
        if not self.enabled:
            return
        cuadro = int(self._t * CUADROS_POR_SEGUNDO) if self._modo else 0
        if cuadro == self._cuadro and not forzar:
            self._velo.color = color.rgba32(*materiales.DIGITAL_FONDO, int(255 * calc.velo_glitch(i)))
            return
        self._cuadro = cuadro
        # el cuadro también depende de la intensidad cuando se fija a mano (los cuadros de la línea de tiempo)
        semilla = cuadro if self._modo else int(i * 60)
        for banda, (y, alto, dx, c, alfa) in zip(self._bandas, calc.bandas_glitch(semilla, BANDAS, i)):
            banda.position = (dx, y)
            banda.scale = (ANCHO_BANDA, alto)
            base = self._colores[c]
            banda.color = color.rgba(base.r, base.g, base.b, alfa)
        self._velo.color = color.rgba32(*materiales.DIGITAL_FONDO, int(255 * calc.velo_glitch(i)))
