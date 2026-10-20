# Escena de inicio (Ursina): wordmark, subtítulo y botones "Empezar" y "Salir".
# No conoce al gestor de escenas: recibe los callbacks `al_comenzar` y `al_salir`.
# Visual (T7): fondo de menú en capas con deriva lenta, wordmark dibujado por código y botones
# de tinta (primario amarillo / secundario). Teclado: flechas o Tab mueven el foco, Enter activa.

from ursina import Text

from frontend import estilo
from frontend.componentes import (
    BotonPrimario, BotonSecundario, a_unidades, escala_fuente, panel_tinta, rgb,
)
from frontend.escenas.escena_base import Escena
from frontend.fondo_menu import FocoTeclado, FondoMenu
from frontend.logo import crear_wordmark

TITULO = "Alcalde Digital"
SUBTITULO = "Campaña electoral en Ciudad Nova · Civitas"


# Pantalla de bienvenida; `al_comenzar` se invoca al pulsar "Empezar" y `al_salir`
# (opcional) al pulsar "Salir".
class EscenaInicio(Escena):

    # Posiciones verticales (camera.ui: 0 = centro, positivo = arriba).
    Y_TITULO = a_unidades(300 - 150)
    Y_SUBTITULO = a_unidades(300 - 262)
    Y_BOTON = a_unidades(300 - 360)
    Y_BOTON_SALIR = Y_BOTON - a_unidades(80)
    ANCHO_BOTON = a_unidades(260)
    ALTO_BOTON = a_unidades(60)

    def __init__(self, al_comenzar, al_salir=None, **opciones):
        super().__init__(**opciones)
        self.fondo = FondoMenu(parent=self)
        self.wordmark = crear_wordmark(self, position=(0, self.Y_TITULO))
        self.texto_titulo = self.wordmark.texto_principal

        # Subtítulo sobre una placa de tinta: se lee igual sobre cualquier parte del cielo.
        ancho_sub = 0.80
        alto_sub = a_unidades(40)
        self.placa_subtitulo = panel_tinta(
            self, ancho_sub, alto_sub, estilo.TINTA, estilo.RADIO_CHIP_PX,
            position=(0, self.Y_SUBTITULO), sombra=False)
        self.texto_subtitulo = Text(
            SUBTITULO, parent=self.placa_subtitulo, origin=(0, 0), position=(0, 0, -0.001),
            scale=escala_fuente(21), color=rgb(estilo.COLOR_TEXTO))

        self.boton_comenzar = BotonPrimario(
            "Empezar", al_clic=al_comenzar, ancho=self.ANCHO_BOTON, alto=self.ALTO_BOTON,
            tamano_fuente_px=26, parent=self, position=(0, self.Y_BOTON),
        )
        self.boton_salir = BotonSecundario(
            "Salir", al_clic=al_salir, ancho=self.ANCHO_BOTON, alto=self.ALTO_BOTON,
            tamano_fuente_px=24, parent=self, position=(0, self.Y_BOTON_SALIR),
        )
        self.botones = (self.boton_comenzar, self.boton_salir)
        self.foco = FocoTeclado(lambda: self.botones, parent=self)

    def al_entrar(self, **datos):
        self.foco.reiniciar()
        self.fondo.t = 0.0
