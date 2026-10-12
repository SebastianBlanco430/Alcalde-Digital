# Menú de pausa del mundo (Ursina, en camera.ui): se abre con Escape. Reanudar / Volver al
# menú / Salir. Es solo vista: los tres callbacks los pone EscenaMundo (que además libera el
# ratón y congela los controles mientras está abierto).

from ursina import Entity, Text, camera, color

from frontend import estilo
from frontend.componentes import BotonAccion, escala_fuente, modelo_redondeado, rgb

ANCHO, ALTO = 0.5, 0.52
Z_FRENTE = -50


class MenuPausa(Entity):

    def __init__(self, al_reanudar, al_menu, al_salir, **opciones):
        opciones.setdefault("parent", camera.ui)
        super().__init__(z=Z_FRENTE, enabled=False, **opciones)
        Entity(parent=self, model="quad", color=color.rgba32(0, 0, 0, 150), scale=(4, 4), z=0.01)
        Entity(parent=self, model=modelo_redondeado(ANCHO, ALTO, 14), scale=(ANCHO, ALTO),
               color=color.rgba32(12, 14, 24, 245))
        Text("Pausa", parent=self, origin=(0, 0), position=(0, ALTO / 2 - 0.07, -0.001),
             scale=escala_fuente(32), color=rgb(estilo.COLOR_TEXTO))
        self.boton_reanudar = BotonAccion("Reanudar", al_clic=al_reanudar, ancho=0.34, parent=self,
                                          position=(0, 0.08, -0.001))
        self.boton_menu = BotonAccion("Volver al menú", al_clic=al_menu, ancho=0.34, parent=self,
                                      position=(0, -0.03, -0.001))
        self.boton_salir = BotonAccion("Salir", al_clic=al_salir, ancho=0.34, parent=self,
                                       position=(0, -0.14, -0.001))
        self.botones = (self.boton_reanudar, self.boton_menu, self.boton_salir)
