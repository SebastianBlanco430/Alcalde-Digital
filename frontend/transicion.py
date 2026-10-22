# Transición entre escenas (Ursina): un quad negro que cubre toda camera.ui y hace un
# fundido (sale a negro, ejecuta el cambio de escena, vuelve a mostrar). La lógica del
# tiempo vive en frontend/fundido.py (pura, con tests); aquí solo se dibuja su alfa.
#
# Va al frente de todo: z muy negativo (más cerca de la cámara de camera.ui) y render_queue
# alto. Está desactivada mientras no hay fundido (no gasta nada). Se avanza sola en
# update() con time.dt; los scripts de prueba pueden llamar avanzar(dt) a mano o crearla
# con duraciones 0 (la acción corre al instante y nunca se ve el negro).
# Si la acción falla, el Fundido se libera y aquí se apaga el quad: nunca queda negro.
#
# Con `sostener` > 0 la pantalla se queda en negro total ese tiempo, y `ejecutar(accion, texto=...)`
# muestra el texto centrado mientras dura ese negro (el nombre del lugar al entrar a un edificio).

from panda3d.core import TransparencyAttrib
from ursina import Entity, Text, camera, color, time

from frontend import diseno_adaptable, estilo
from frontend.componentes import escala_fuente, rgb
from frontend.fundido import Fundido

Z_FRENTE = -100
COLA_DIBUJO = 100


class Transicion(Entity):

    def __init__(self, duracion_salida=0.25, duracion_entrada=0.25, sostener=0.0, **opciones):
        super().__init__(
            parent=camera.ui, model="quad", color=color.rgba(0, 0, 0, 0), scale=(4, 4),
            z=Z_FRENTE, enabled=False, **opciones)
        self.setTransparency(TransparencyAttrib.M_alpha)
        self.render_queue = COLA_DIBUJO
        self.fundido = Fundido(duracion_salida, duracion_entrada, sostener)
        # El texto es hijo del quad (escala 4): se contraescala para que mida lo de siempre.
        self.texto = Text("", parent=camera.ui, origin=(0, 0), z=Z_FRENTE - 1, enabled=False,
                          scale=escala_fuente(40), color=rgb(estilo.COLOR_TEXTO))
        self.texto.render_queue = COLA_DIBUJO + 1

    @property
    def ocupada(self):
        return self.fundido.ocupada

    @property
    def alfa(self):
        return self.fundido.alfa

    # Misma interfaz que Fundido.ejecutar (ConexionFlujo solo conoce `ocupada` y `ejecutar`).
    def ejecutar(self, accion, texto=None):
        self.enabled = True
        try:
            self.fundido.ejecutar(accion, texto=texto)
        finally:
            self._pintar()

    # Termina el fundido en curso al instante (ver Fundido.saltar).
    def saltar(self):
        try:
            return self.fundido.saltar()
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
        texto = self.fundido.texto
        self.texto.enabled = texto is not None
        if texto is not None:
            self.texto.text = texto
            self._ajustar_texto(texto)

    _texto_ajustado = None

    # El nombre del lugar nunca se sale de la ventana: se encoge (hasta la mitad) o se parte en
    # líneas según el aspecto actual. Solo se recalcula si cambia el texto; sin gestor no hace nada.
    def _ajustar_texto(self, texto):
        firma = (texto, round(diseno_adaptable.aspecto(), 3))
        if firma == self._texto_ajustado:
            return
        self._texto_ajustado = firma
        diseno_adaptable.ajustar_texto(self.texto, diseno_adaptable.aspecto() - 0.12,
                                       escala_base=escala_fuente(40), escala_min=0.5, max_lineas=3,
                                       cadena=texto)
