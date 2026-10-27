# Pantalla de carga con barra de progreso para las construcciones largas del mapa grande (arranque de la ciudad y anillo
# inicial de chunks). Dibuja entre paso y paso con base.graphicsEngine.render_frame(): el bucle de Ursina no corre mientras
# el código construye de forma síncrona, así que sin esto la ventana se quedaría congelada 5-10 s.
# Mientras está abierta apaga el dibujo del mundo 3D (la cámara del mundo): solo se pinta la UI y cada actualización cuesta ~1 ms.

import time

from ursina import Entity, Text, camera, color, application

from frontend import estilo
from frontend.componentes import rgb

ANCHO = 0.9               # unidades de camera.ui (la pantalla mide 1.78 x 1)
ALTO = 0.035
INTERVALO = 1 / 30        # s mínimos entre dos dibujos


class BarraCarga:

    def __init__(self, titulo="Cargando el barrio..."):
        self._cierre = []
        self._t = 0.0
        self._cam_activa = None
        self.fondo = Entity(parent=camera.ui, model="quad", color=rgb(estilo.COLOR_FONDO), scale=(3, 2), z=-5)
        self.marco = Entity(parent=camera.ui, model="quad", color=rgb(estilo.COLOR_PANEL), scale=(ANCHO + 0.02, ALTO + 0.02), z=-6)
        self.relleno = Entity(parent=camera.ui, model="quad", color=rgb(estilo.COLOR_ACENTO), origin=(-0.5, 0),
                              position=(-ANCHO / 2, 0), scale=(0.0001, ALTO), z=-7)
        self.titulo = Text(titulo, parent=camera.ui, origin=(0, 0), position=(0, 0.09), scale=1.6,
                           color=rgb(estilo.COLOR_TEXTO), z=-8)
        self.detalle = Text("", parent=camera.ui, origin=(0, 0), position=(0, -0.07), scale=1.0,
                            color=rgb(estilo.COLOR_TEXTO), z=-8)
        self._entidades = [self.fondo, self.marco, self.relleno, self.titulo, self.detalle]
        base = application.base
        try:
            self._cam_activa = base.cam.node().is_active()
            base.cam.node().set_active(False)
        except Exception:                                   # noqa: BLE001 — sin esto solo se dibuja también el mundo
            self._cam_activa = None
        self.actualizar(0.0, "", forzar=True)

    def actualizar(self, fraccion, texto="", forzar=False):
        ahora = time.perf_counter()
        if not forzar and ahora - self._t < INTERVALO and fraccion < 1.0:
            return
        self._t = ahora
        self.relleno.scale_x = max(0.0001, ANCHO * min(1.0, max(0.0, fraccion)))
        self.detalle.text = texto
        try:
            application.base.graphicsEngine.render_frame()
        except Exception:                                   # noqa: BLE001
            pass

    def cerrar(self):
        from ursina import destroy
        for e in self._entidades:
            destroy(e)
        self._entidades = []
        if self._cam_activa is not None:
            application.base.cam.node().set_active(self._cam_activa)
