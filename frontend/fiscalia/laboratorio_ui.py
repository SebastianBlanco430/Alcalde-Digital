# Interfaz del laboratorio forense del caso de Fiscalía v2 (Ursina, en camera.ui): una ficha (chip) por terminal con su
# nombre en la ficción, la prueba que guarda y su estado («Sin revisar» / palomita + «Prueba obtenida»), y abajo al centro,
# encima de los subtítulos, el aviso de la tecla E («Sentarse: Servidor fantasma», «Pasar a la sala»).
# La interfaz NO maneja E ni el movimiento (son de la escena): solo dibuja lo que la escena le dice.

from ursina import Entity, Text, destroy

from frontend import estilo, tipografia
from frontend.componentes import a_unidades, destruir_arbol, escala_fuente, panel_tinta, rgb, panel_piel
from frontend.fiscalia import ui_calculos as uc
from frontend.fiscalia.rueda import ajustar, ancho_real, palomita

X_CHIPS = -0.60
Y_PRIMER_CHIP = 0.29
ANCHO_CHIP, ALTO_CHIP = 0.50, 0.118
PASO_CHIP = 0.138
POS_AVISO = (0.0, -0.212)


class ChipTerminal(Entity):

    def __init__(self, **opciones):
        super().__init__(**opciones)
        self.panel = panel_piel(self, ANCHO_CHIP, ALTO_CHIP, tono=estilo.COLOR_PANEL, radio_px=estilo.RADIO_TARJETA_PX)
        x0 = -ANCHO_CHIP / 2 + 0.022
        self.nombre = Text("", parent=self, origin=(-0.5, 0), position=(x0, 0.033, -0.01),
                           scale=escala_fuente(uc.TAM["chip_titulo"]), font=tipografia.fuente_piel(titulo=True),
                           color=rgb(estilo.COLOR_TEXTO))
        self.prueba = Text("", parent=self, origin=(-0.5, 0), position=(x0, -0.003, -0.01),
                           scale=escala_fuente(uc.TAM["chip"]), color=rgb(estilo.COLOR_TEXTO_TENUE))
        self.estado = Text("", parent=self, origin=(-0.5, 0), position=(x0, -0.038, -0.01),
                           scale=escala_fuente(uc.TAM["chip"]), font=tipografia.fuente_piel(titulo=True),
                           color=rgb(estilo.COLOR_TEXTO_TENUE))
        self.marca = palomita(self, 0.026, position=(x0 + 0.012, -0.038, -0.01), enabled=False)
        self._x0 = x0

    def fijar(self, parkour, cerca):
        ajustar(self.nombre, parkour.nombre, ANCHO_CHIP - 0.05, uc.TAM["chip_titulo"])
        ajustar(self.prueba, f"Prueba: {parkour.nombre_evidencia}", ANCHO_CHIP - 0.05, uc.TAM["chip"])
        hecho = bool(parkour.completado)
        self.estado.text = uc.estado_parkour(hecho)
        self.estado.x = self._x0 + (0.032 if hecho else 0.0)
        self.estado.color = rgb((88, 214, 141) if hecho else estilo.COLOR_TEXTO_TENUE)
        self.marca.enabled = hecho
        self.panel.fondo.color = rgb(estilo.COLOR_SUPERFICIE_ALTA if cerca else estilo.COLOR_PANEL)
        self.panel.borde.color = rgb(estilo.COLOR_ACENTO if cerca else estilo.TINTA)


class LaboratorioUI(Entity):

    def __init__(self, **opciones):
        super().__init__(**opciones)
        self.titulo = Text("Terminales del laboratorio", parent=self, origin=(-0.5, 0),
                           position=(X_CHIPS - ANCHO_CHIP / 2, Y_PRIMER_CHIP + ALTO_CHIP / 2 + 0.03, -0.01),
                           scale=escala_fuente(uc.TAM["chip_titulo"]), font=tipografia.fuente_piel(titulo=True),
                           color=rgb(estilo.COLOR_ACENTO))
        self.chips = [ChipTerminal(parent=self, position=(X_CHIPS, Y_PRIMER_CHIP - i * PASO_CHIP, 0)) for i in range(2)]
        self.aviso = None
        self._aviso_actual = None
        self.enabled = False

    def _crear_aviso(self, texto):
        """Panel del aviso a la medida del texto (se rehace solo cuando el texto cambia)."""
        if self.aviso is not None:
            destruir_arbol(self.aviso)
            self.aviso = None
        self._aviso_actual = texto
        if not texto:
            return
        medida = Text("", parent=self, scale=escala_fuente(uc.TAM["aviso"]), font=tipografia.fuente_piel(titulo=True))
        ajustar(medida, texto, 0.62, uc.TAM["aviso"])
        ancho_txt, escala, cadena = ancho_real(medida), medida.scale, medida.text
        destroy(medida)
        tecla = a_unidades(30)
        ancho = ancho_txt + tecla + 0.065
        self.aviso = panel_piel(self, ancho, 0.062, tono=estilo.COLOR_PANEL, position=(*POS_AVISO, -0.01))
        x_tecla = -ancho / 2 + 0.02 + tecla / 2
        caja = panel_tinta(self.aviso, tecla, tecla, estilo.PAPEL, estilo.RADIO_CHIP_PX, borde_px=2,
                           position=(x_tecla, 0, -0.01))
        Text("E", parent=caja, origin=(0, 0), position=(0, a_unidades(1), -0.01), scale=escala_fuente(17),
             font=tipografia.FUENTE_TITULO, color=rgb(estilo.TINTA))
        self.aviso_txt = Text(cadena, parent=self.aviso, origin=(-0.5, 0), position=(x_tecla + tecla / 2 + 0.018, 0, -0.01),
                              scale=escala, font=tipografia.fuente_piel(titulo=True), color=rgb(estilo.COLOR_TEXTO))

    def mostrar(self, parkours, cerca=None, puerta=False):
        parkours = tuple(parkours or ())[:2]
        for i, chip in enumerate(self.chips):
            chip.enabled = i < len(parkours)
            if i < len(parkours):
                chip.fijar(parkours[i], cerca is not None and parkours[i].nivel == cerca)
        self.titulo.enabled = bool(parkours)
        aviso = uc.aviso_laboratorio(parkours, cerca, puerta)
        texto = aviso.split("—", 1)[-1].strip() if aviso else ""      # la «E» va en su tecla dibujada
        if texto != self._aviso_actual:
            self._crear_aviso(texto)
        self.enabled = True

    def ocultar(self):
        self.enabled = False
