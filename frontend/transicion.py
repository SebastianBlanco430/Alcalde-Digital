# Transición entre escenas (Ursina): un quad negro que cubre toda camera.ui y hace un
# fundido (sale a negro, ejecuta el cambio de escena, vuelve a mostrar). La lógica del
# tiempo vive en frontend/fundido.py (pura, con tests); aquí solo se dibuja su alfa.
#
# Va al frente de todo: z muy negativo (más cerca de la cámara de camera.ui) y render_queue
# alto. Está desactivada mientras no hay fundido (no gasta nada). Se avanza sola en
# update() con time.dt; los scripts de prueba pueden llamar avanzar(dt) a mano o crearla
# con duraciones 0 (la acción corre al instante y nunca se ve el negro).
# Si la acción falla, el Fundido se libera y aquí se apaga el quad: nunca queda negro.

from panda3d.core import TransparencyAttrib
from ursina import Entity, camera, color, time

from frontend.fundido import Fundido

Z_FRENTE = -100
COLA_DIBUJO = 100


class Transicion(Entity):

    def __init__(self, duracion_salida=0.25, duracion_entrada=0.25, **opciones):
        super().__init__(
            parent=camera.ui, model="quad", color=color.rgba(0, 0, 0, 0), scale=(4, 4),
            z=Z_FRENTE, enabled=False, **opciones)
        self.setTransparency(TransparencyAttrib.M_alpha)
        self.render_queue = COLA_DIBUJO
        self.fundido = Fundido(duracion_salida, duracion_entrada)

    @property
    def ocupada(self):
        return self.fundido.ocupada

    @property
    def alfa(self):
        return self.fundido.alfa

    # Misma interfaz que Fundido.ejecutar (ConexionFlujo solo conoce `ocupada` y `ejecutar`).
    def ejecutar(self, accion):
        self.enabled = True
        try:
            self.fundido.ejecutar(accion)
        finally:
            self._pintar()

    def avanzar(self, dt):
        try:
            self.fundido.avanzar(dt)
        finally:
            self._pintar()

    def update(self):
        self.avanzar(time.dt)

    def _pintar(self):
        self.color = color.rgba(0, 0, 0, self.fundido.alfa)
        self.enabled = self.fundido.ocupada
