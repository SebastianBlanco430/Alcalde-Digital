"""
Escena de inicio (Ursina): título, subtítulo y botón "Comenzar".

Replica el comportamiento y la paleta de la pantalla de inicio pygame original
(retirada en el Módulo 5). No conoce al gestor de escenas:
recibe el callback `al_comenzar` por constructor.
"""

from ursina import Text

from frontend import estilo
from frontend.componentes import BotonAccion, a_unidades, escala_fuente, rgb
from frontend.escenas.escena_base import Escena

TITULO = "Alcalde Digital"
SUBTITULO = "Campaña electoral en Ciudad Nova · Civitas"


class EscenaInicio(Escena):
    """Pantalla de bienvenida.

    Args:
        al_comenzar: callable sin argumentos que se invoca al pulsar "Comenzar".

    Atributos públicos: `texto_titulo`, `texto_subtitulo`, `boton_comenzar`
    (BotonAccion).
    """

    # Posiciones verticales de la versión pygame (800x600) convertidas a
    # camera.ui (0 = centro de la pantalla, positivo = arriba).
    Y_TITULO = a_unidades(300 - 240)
    Y_SUBTITULO = a_unidades(300 - 290)
    Y_BOTON = a_unidades(300 - 360)

    def __init__(self, al_comenzar, **kwargs):
        super().__init__(**kwargs)
        self.texto_titulo = Text(
            TITULO, parent=self, origin=(0, 0), position=(0, self.Y_TITULO),
            scale=escala_fuente(48), color=rgb(estilo.COLOR_TEXTO),
        )
        self.texto_subtitulo = Text(
            SUBTITULO, parent=self, origin=(0, 0), position=(0, self.Y_SUBTITULO),
            scale=escala_fuente(22), color=rgb(estilo.COLOR_TEXTO_TENUE),
        )
        self.boton_comenzar = BotonAccion(
            "Comenzar", on_click=al_comenzar, parent=self, position=(0, self.Y_BOTON),
        )
