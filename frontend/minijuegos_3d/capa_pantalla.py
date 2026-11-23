# Capa de UI EN PANTALLA de los minijuegos 3D (Ursina, camera.ui). camera.ui se dibuja en su propia región DESPUÉS del
# mundo y fuera del pase final (tinta, grading, pixelado): lo que se cuelga aquí se ve nítido y sin teñir, igual que el UI
# de hoy. Para: la línea de teclas de la vista 2D (que en el monitor queda pequeña), botones propios de una familia que no
# deban estar en el mundo, avisos. La raíz cuelga de camera.ui (no de la escena): no la escala el marco del PC.
#
#   capa = CapaPantalla(); capa.ayuda("Flechas: ...")
#   capa.boton("Linterna", al_clic, (x, y))  -> BotonPrimario de siempre (hover y clic del mouse real)
#   capa.texto("...", px=18, posicion=(x, y))
#   capa.destruir()

from ursina import Entity, camera, color

from frontend import estilo
from frontend.componentes import BotonPrimario, a_unidades, destruir_arbol, rgb
from frontend.minijuegos import ui as ui_2d

PX_AYUDA = 17


class CapaPantalla(Entity):

    def __init__(self, **opciones):
        opciones.setdefault("parent", camera.ui)
        super().__init__(z=-0.05, **opciones)
        self._ayuda = None
        self._franja = None

    def ayuda(self, texto):
        """La línea de teclas abajo, sobre una franja oscura translúcida (se lee sobre cualquier fondo 3D)."""
        for e in (self._ayuda, self._franja):
            if e is not None:
                destruir_arbol(e)
        self._ayuda = self._franja = None
        if not texto:
            return None
        ancho = 1.62
        lineas = max(1, len(ui_2d.lineas_de(texto, PX_AYUDA, ancho)))
        alto = ui_2d.alto_de(lineas, PX_AYUDA)
        margen = a_unidades(PX_AYUDA) * 0.45
        abajo = -0.5 + a_unidades(4)                    # la franja nunca se sale por abajo, aunque el texto ocupe 2 líneas
        self._franja = Entity(parent=self, model="quad", color=color.rgba32(14, 16, 26, 170),
                              scale=(4, alto + 2 * margen), y=abajo + alto / 2 + margen, z=0.01)
        self._ayuda = ui_2d.texto(self, texto, PX_AYUDA, ancho, estilo.COLOR_TEXTO, (-ancho / 2, abajo + margen + alto))
        return self._ayuda

    def texto(self, texto, px=18, posicion=(0, 0), ancho=1.0, tono=None):
        return ui_2d.texto(self, texto, px, ancho, tono or estilo.COLOR_TEXTO, posicion)

    def boton(self, texto, al_clic, posicion=(0, 0), ancho=0.26, alto=0.07):
        return BotonPrimario(texto, al_clic=al_clic, ancho=ancho, alto=alto, parent=self,
                             position=(posicion[0], posicion[1], -0.01), tamano_fuente_px=20)

    def avanzar(self, dt):
        pass

    def destruir(self):
        destruir_arbol(self)
        return True


def color_texto():
    return rgb(estilo.COLOR_TEXTO)
