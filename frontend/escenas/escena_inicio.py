# Escena de inicio (Ursina): título, subtítulo y botones "Empezar" y "Salir".
# No conoce al gestor de escenas: recibe los callbacks `al_comenzar` y `al_salir`.

from ursina import Text

from frontend import estilo
from frontend.componentes import BotonAccion, a_unidades, escala_fuente, rgb
from frontend.escenas.escena_base import Escena

TITULO = "Alcalde Digital"
SUBTITULO = "Campaña electoral en Ciudad Nova · Civitas"


# Pantalla de bienvenida; `al_comenzar` se invoca al pulsar "Empezar" y `al_salir`
# (opcional) al pulsar "Salir".
class EscenaInicio(Escena):

    # Posiciones verticales de la versión pygame (800x600) convertidas a
    # camera.ui (0 = centro, positivo = arriba).
    Y_TITULO = a_unidades(300 - 240)
    Y_SUBTITULO = a_unidades(300 - 290)
    Y_BOTON = a_unidades(300 - 360)
    Y_BOTON_SALIR = Y_BOTON - a_unidades(76)

    def __init__(self, al_comenzar, al_salir=None, **opciones):
        super().__init__(**opciones)
        self.texto_titulo = Text(
            TITULO, parent=self, origin=(0, 0), position=(0, self.Y_TITULO),
            scale=escala_fuente(48), color=rgb(estilo.COLOR_TEXTO),
        )
        self.texto_subtitulo = Text(
            SUBTITULO, parent=self, origin=(0, 0), position=(0, self.Y_SUBTITULO),
            scale=escala_fuente(22), color=rgb(estilo.COLOR_TEXTO_TENUE),
        )
        self.boton_comenzar = BotonAccion(
            "Empezar", al_clic=al_comenzar, parent=self, position=(0, self.Y_BOTON),
        )
        self.boton_salir = BotonAccion(
            "Salir", al_clic=al_salir, parent=self, position=(0, self.Y_BOTON_SALIR),
        )
