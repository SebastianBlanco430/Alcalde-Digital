# Menú de pausa del mundo (Ursina, en camera.ui): se abre con Escape. Reanudar / Volver al
# menú / Salir. Es solo vista: los tres callbacks los pone EscenaMundo (que además libera el
# ratón y congela los controles mientras está abierto).
# Visual (T9): velo de tinta, panel con borde de tinta (más un filo claro para que se vea sobre
# el velo), botón primario («Reanudar») y secundarios, y una guía de teclas. Teclado: flechas o
# Tab mueven el foco, Enter activa (Escape lo gestiona EscenaMundo).

from ursina import Entity, Text, camera, color

from frontend import estilo, tipografia
from frontend.componentes import (
    BotonPrimario, BotonSecundario, a_unidades, escala_fuente, panel_tinta, rgb,
)
from frontend.fondo_menu import FocoTeclado, anadir_filo

ANCHO, ALTO = 0.60, 0.70
Z_FRENTE = -50
ALFA_VELO = 170
ANCHO_BOTON = 0.42
ALTO_BOTON = a_unidades(56)

# (tecla, acción) de la guía; dos columnas.
TECLAS = (("WASD", "mover"), ("Shift", "correr"), ("E", "entrar"), ("Tab", "teléfono"))


# Tecla estilo teclado: papel con borde de tinta y base gruesa; devuelve la entidad.
def _tecla(padre, texto, x, y, ancho):
    alto = a_unidades(30)
    tecla = panel_tinta(padre, ancho, alto, estilo.PAPEL, estilo.RADIO_CHIP_PX, borde_px=2,
                        position=(x, y, -0.001))
    Text(texto, parent=tecla, origin=(0, 0), position=(0, a_unidades(1), -0.001),
         scale=escala_fuente(17), font=tipografia.FUENTE_TITULO, color=rgb(estilo.TINTA))
    return tecla


class MenuPausa(Entity):

    def __init__(self, al_reanudar, al_menu, al_salir, **opciones):
        opciones.setdefault("parent", camera.ui)
        super().__init__(z=Z_FRENTE, enabled=False, **opciones)
        self.velo = Entity(parent=self, model="quad", color=color.rgba32(*estilo.TINTA, ALFA_VELO),
                           scale=(4, 4), z=0.01)
        self.panel = panel_tinta(self, ANCHO, ALTO, estilo.COLOR_PANEL, estilo.RADIO_PANEL_PX)
        anadir_filo(self.panel, ANCHO, ALTO, estilo.RADIO_PANEL_PX)
        self.texto_titulo = Text(
            "Pausa", parent=self, origin=(0, 0), position=(0, ALTO / 2 - 0.075, -0.001),
            scale=escala_fuente(40), font=tipografia.FUENTE_TITULO, color=rgb(estilo.COLOR_TEXTO))

        self.boton_reanudar = BotonPrimario(
            "Reanudar", al_clic=al_reanudar, ancho=ANCHO_BOTON, alto=ALTO_BOTON, tamano_fuente_px=24,
            parent=self, position=(0, 0.125, -0.001))
        self.boton_menu = BotonSecundario(
            "Volver al menú", al_clic=al_menu, ancho=ANCHO_BOTON, alto=ALTO_BOTON, tamano_fuente_px=22,
            parent=self, position=(0, 0.125 - 0.115, -0.001))
        self.boton_salir = BotonSecundario(
            "Salir", al_clic=al_salir, ancho=ANCHO_BOTON, alto=ALTO_BOTON, tamano_fuente_px=22,
            parent=self, position=(0, 0.125 - 0.23, -0.001))
        self.botones = (self.boton_reanudar, self.boton_menu, self.boton_salir)

        # Guía de teclas: 2 columnas x 2 filas, con una línea fina encima.
        y0 = -0.235
        self.teclas = []
        for i, (tecla, accion) in enumerate(TECLAS):
            columna, fila = i % 2, i // 2
            x = -0.235 + columna * 0.245
            y = y0 - fila * 0.058
            ancho_t = a_unidades(34) + a_unidades(11) * len(tecla)
            self.teclas.append(_tecla(self, tecla, x + ancho_t / 2, y, ancho_t))
            Text(accion, parent=self, origin=(-0.5, 0), position=(x + ancho_t + 0.014, y, -0.001),
                 scale=escala_fuente(17), color=rgb(estilo.COLOR_TEXTO_TENUE))

        self.foco = FocoTeclado(lambda: self.botones, parent=self)

    # Al abrir, el foco vuelve al primer botón (Reanudar) y el anillo se oculta hasta usar el teclado.
    def on_enable(self):
        foco = getattr(self, "foco", None)
        if foco is not None:
            foco.reiniciar()
