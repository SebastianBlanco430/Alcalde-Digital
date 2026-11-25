# Pantalla de finales (Ursina, en camera.ui): la muestra EscenaMundo al terminar la partida cuando hay consecuencias
# (FlujoConGameState.final_partida() no es None). Título y párrafo del final (bueno / neutro / malo), la confianza de
# los tres grupos en barras, el resumen de misiones y «Volver al menú». Sin consecuencias se sigue usando el
# PanelFinPartida de siempre (frontend/hud.py).
#
# Solo pinta: qué final sale y con qué textos lo decide el backend (confianza_misiones.evaluar_final,
# datos/finales_textos.py) y lo redacta frontend/veredicto_calculos.contenido_final. Perder es un final válido: no hay
# «game over», el panel es el mismo con otro tono.

from ursina import Entity, Text

from frontend import estilo, ui_botw_b
from frontend import veredicto_calculos as vc
from frontend.componentes import BarraIndicador, BotonPrimario, a_unidades, escala_fuente, panel_tinta, rgb
from frontend.hud import _medidor
from frontend.texto import envolver_texto

_TONOS = {"exito": estilo.ESTADO_EXITO, "aviso": estilo.ESTADO_AVISO, "error": estilo.ESTADO_ERROR}


class PanelFinal(Entity):

    ANCHO, ALTO = 1.20, 0.86
    MARGEN = 0.06
    PX_TITULO, PX_SUBTITULO, PX_TEXTO, PX_RESUMEN = 36, 17, 19, 18
    LINEA = 1.3
    SUBTITULO = "Fin de la campaña en Ciudad Nova"

    def __init__(self, al_menu, **opciones):
        super().__init__(**opciones)
        self.z = -0.5                         # por delante del resto del HUD
        # ALCALDE_FINALES_PULIDOS: el panel deja el mismo hueco que PanelFinalSemana entre el resumen y el botón; ahí va la
        # franja del desenlace de la recta final (frontend/recta_final_vista.FRANJA_Y), que antes tapaba la última línea
        # del resumen y medio botón «Volver al menú» (el panel final en línea y el del modo por turnos sin reloj).
        from frontend.final_animado import final_pulido_calculos as pulido
        if pulido.activo():
            alto, y_barras, y_resumen = pulido.PANEL_FINAL_ALTO, pulido.PANEL_FINAL_Y_BARRAS, pulido.PANEL_FINAL_Y_RESUMEN
        else:
            alto, y_barras, y_resumen = self.ALTO, -0.045, -0.175
        self.panel = panel_tinta(self, self.ANCHO, alto, tono=estilo.COLOR_FONDO)
        arriba = alto / 2
        self.titulo = Text("", parent=self, origin=(0, 0), position=(0, arriba - 0.075, -0.001),
                           scale=escala_fuente(self.PX_TITULO), color=rgb(estilo.COLOR_TEXTO))
        Text(self.SUBTITULO, parent=self, origin=(0, 0), position=(0, arriba - 0.13, -0.001),
             scale=escala_fuente(self.PX_SUBTITULO), color=rgb(estilo.COLOR_TEXTO_TENUE))
        self.texto = Text("", parent=self, origin=(-0.5, 0.5), position=(-self.ANCHO / 2 + self.MARGEN, arriba - 0.17, -0.001),
                          scale=escala_fuente(self.PX_TEXTO), color=rgb(estilo.COLOR_TEXTO))
        self.texto.line_height = self.LINEA
        # Tres barras de confianza, una por grupo, en fila.
        util = self.ANCHO - 2 * self.MARGEN
        hueco = 0.05
        self.ancho_barra = (util - 2 * hueco) / 3
        self.barras = []
        for i in range(3):
            x = -self.ANCHO / 2 + self.MARGEN + i * (self.ancho_barra + hueco)
            self.barras.append(BarraIndicador("", self.ancho_barra, 0, parent=self, position=(x, y_barras, -0.001)))
        self.resumen = Text("", parent=self, origin=(0, 0.5), position=(0, y_resumen, -0.001),
                            scale=escala_fuente(self.PX_RESUMEN), color=rgb(estilo.COLOR_TEXTO_TENUE))
        self.resumen.line_height = self.LINEA
        self.boton_menu = BotonPrimario("Volver al menú", al_clic=al_menu, ancho=0.36, alto=a_unidades(56),
                                        parent=self, position=(0, -alto / 2 + (0.07 if pulido.activo() else 0.075), -0.001))
        self.contenido = None
        # Piel BOTW (ALCALDE_UI_BOTW, frontend/ui_botw_b.py): título en cursiva con sombra de tinta, velo detrás del panel
        # y entrada desde la derecha al mostrarse. None = el panel de siempre.
        self.piel = ui_botw_b.vestir(self, titulos=(self.titulo,), piezas=(self,), velo=True)
        self.enabled = False

    # `final`: dict de confianza_misiones.evaluar_final. `indicadores`: los de la ciudad (opcional, van al resumen).
    def mostrar(self, final, indicadores=None):
        contenido = vc.contenido_final(final, indicadores)
        if contenido != self.contenido:
            self.contenido = contenido
            self.titulo.text = contenido["titulo"]
            self.titulo.color = rgb(_TONOS[contenido["tono"]])
            lineas = envolver_texto(contenido["texto"], _medidor(self.texto), self.ANCHO - 2 * self.MARGEN)
            self.texto.text = "\n".join(lineas)
            for barra, (nombre, valor) in zip(self.barras, contenido["barras"]):
                barra.etiqueta = nombre
                barra.actualizar(valor)
            self.resumen.text = "\n".join(contenido["resumen"])
        if not self.enabled and self.piel is not None:
            self.piel.reiniciar()
        self.enabled = True

    def ocultar(self):
        self.enabled = False
