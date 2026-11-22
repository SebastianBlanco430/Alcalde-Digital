# Globo de texto de las cinemáticas (Ursina, en camera.ui). Enseña UNA oración con el nombre de quien habla; no lleva
# reloj: lo enciende y lo apaga quien dirige (frontend/intro_cinematica.py, con el plan de frontend/intro_calculos.py).
#
#   mostrar(hablante, texto, estilo)   estilo "dialogo": bocadillo de papel abajo, con la etiqueta amarilla del hablante;
#                                      "bajo_titulo": texto blanco centrado, sin bocadillo, bajo el título sobre negro.
#   ocultar()
#
# El texto se parte midiendo su ancho real con la fuente (frontend/texto.envolver_texto), como las viñetas.

from ursina import Entity, Text, color

from frontend import estilo, tipografia
from frontend.componentes import a_unidades, destruir_arbol, escala_fuente, panel_tinta, rgb

ANCHO_DIALOGO = 1.0
Y_DIALOGO = -0.33               # centro del bocadillo en camera.ui
RELLENO = 0.03
PX_TEXTO = 22
PX_NOMBRE = 17
ALTO_ETIQUETA = 0.05
RELLENO_NOMBRE = 0.02
ANCHO_BAJO_TITULO = 1.1
Y_BAJO_TITULO = -0.07           # borde de arriba del texto bajo el título
PX_BAJO_TITULO = 22
MAX_LINEAS = 4

# M3.4 (ALCALDE_HUD_TAMANOS): subtítulos más grandes (el bocadillo ya es de papel opaco).
from frontend import hud_tamanos_calculos as _ht  # noqa: E402
if _ht.activo():
    PX_TEXTO, PX_BAJO_TITULO = _ht.PX_SUBTITULO, _ht.PX_SUBTITULO_BAJO_TITULO


def _partir(texto_entidad, cadena, ancho):
    from frontend import hud as hud_mod
    from frontend.texto import envolver_texto
    lineas = envolver_texto(hud_mod._seguro(str(cadena or "")), hud_mod._medidor(texto_entidad), ancho) or [""]
    if len(lineas) > MAX_LINEAS:
        lineas = lineas[:MAX_LINEAS]
        lineas[-1] = lineas[-1].rstrip() + "…"
    texto_entidad.text = "\n".join(lineas)
    return len(lineas)


class GloboDialogo(Entity):

    def __init__(self, **opciones):
        super().__init__(**opciones)
        self.fondo = None
        self.etiqueta = None
        self.hablante = None
        self.cadena = None
        self.texto = Text("", parent=self, origin=(-0.5, 0.5), z=-0.01, scale=escala_fuente(PX_TEXTO), color=rgb(estilo.TINTA))
        self.texto.line_height = 1.2
        self.nombre = Text("", parent=self, origin=(-0.5, 0), z=-0.03, scale=escala_fuente(PX_NOMBRE),
                           color=rgb(estilo.TINTA), font=tipografia.FUENTE_TITULO)
        self.enabled = False

    def _limpiar_paneles(self):
        for pieza in (self.fondo, self.etiqueta):
            if pieza is not None:
                destruir_arbol(pieza)
        self.fondo = self.etiqueta = None

    def mostrar(self, hablante, texto, estilo_globo="dialogo"):
        self.enabled = True
        self.hablante, self.cadena = hablante, texto
        self._limpiar_paneles()
        if estilo_globo == "bajo_titulo":
            self._bajo_titulo(texto)
        else:
            self._dialogo(hablante, texto)

    def ocultar(self):
        self.hablante = self.cadena = None
        self._limpiar_paneles()
        self.texto.text = ""
        self.nombre.text = ""
        self.enabled = False

    def _dialogo(self, hablante, texto):
        self.texto.origin = (-0.5, 0.5)
        self.texto.color = rgb(estilo.TINTA)
        self.texto.scale = escala_fuente(PX_TEXTO)
        ancho_texto = ANCHO_DIALOGO - 2 * RELLENO
        n = _partir(self.texto, texto, ancho_texto)
        alto = 2 * RELLENO + n * a_unidades(PX_TEXTO) * 1.2 + (0.012 if hablante else 0.0)
        self.fondo = panel_tinta(self, ANCHO_DIALOGO, alto, tono=estilo.PAPEL, radio_px=estilo.RADIO_TARJETA_PX,
                                 position=(0, Y_DIALOGO, 0.01))
        izquierda, arriba = -ANCHO_DIALOGO / 2 + RELLENO, Y_DIALOGO + alto / 2 - RELLENO - (0.012 if hablante else 0.0)
        self.texto.position = (izquierda, arriba, -0.01)
        self.nombre.text = hablante or ""
        if hablante:
            from frontend import hud as hud_mod
            ancho_nombre = hud_mod._medidor(self.nombre)(hablante) + 2 * RELLENO_NOMBRE
            y_etiqueta = Y_DIALOGO + alto / 2
            self.etiqueta = panel_tinta(self, ancho_nombre, ALTO_ETIQUETA, tono=estilo.ACENTO_PRIMARIO,
                                        radio_px=estilo.RADIO_TARJETA_PX, sombra=False,
                                        position=(izquierda + ancho_nombre / 2, y_etiqueta, -0.02))
            self.nombre.position = (izquierda + RELLENO_NOMBRE, y_etiqueta, -0.03)

    def _bajo_titulo(self, texto):
        self.nombre.text = ""
        self.texto.origin = (0, 0.5)
        self.texto.color = color.rgb32(236, 236, 240)
        self.texto.scale = escala_fuente(PX_BAJO_TITULO)
        _partir(self.texto, texto, ANCHO_BAJO_TITULO)
        self.texto.position = (0, Y_BAJO_TITULO, -0.01)
