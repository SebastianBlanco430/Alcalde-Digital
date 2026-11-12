# Pantalla final de la SEMANA (Ursina, en camera.ui). Variante nueva de frontend/panel_final.py (que no se toca): la
# muestra frontend/registro_reloj.py cuando la partida tiene reloj (FlujoConTiempo), termine por tiempo o por agotar las
# misiones. Pinta lo que da flujo.resumen_final() redactado por reloj_calculos.contenido_final_semana:
#   - título y párrafo del final (bueno / neutro / malo; backend/datos/finales_textos.py) y por qué terminó
#     («Se acabó la semana · Día 7 · 24:00» / «No quedan misiones · Día 4 · 10:15»);
#   - la confianza de los tres grupos (solo con GameState);
#   - CÓMO TERMINÓ LA CIUDAD: convivencia, confianza y desinformación en barras (en desinformación, alto = malo);
#   - el resumen (misiones acertadas y falladas, índice de la ciudad) y «Volver al menú».
# Solo pinta: qué final sale lo decide el backend. Sin reloj (ALCALDE_RELOJ=0) se usan los paneles de siempre.

from ursina import Entity, Text

from frontend import diseno_adaptable, estilo, reloj_calculos as rc, tipografia
from frontend.componentes import BarraIndicador, BotonPrimario, a_unidades, escala_fuente, panel_tinta, rgb
from frontend.hud import _medidor
from frontend.texto import envolver_texto

_TONOS = {"exito": estilo.ESTADO_EXITO, "aviso": estilo.ESTADO_AVISO, "error": estilo.ESTADO_ERROR}


class PanelFinalSemana(Entity):

    ANCHO, ALTO = 1.20, 0.94
    MARGEN = 0.06
    PX_TITULO, PX_SUBTITULO, PX_TEXTO, PX_RESUMEN = 36, 17, 18, 17
    LINEA = 1.3
    MAX_LINEAS_TEXTO = 6
    Y_TEXTO = 0.315           # borde superior del párrafo
    Y_GRUPOS = 0.105          # borde superior de la fila de confianza por grupo
    Y_CIUDAD = -0.02          # borde superior de la fila de indicadores de la ciudad
    Y_RESUMEN = -0.15

    def __init__(self, al_menu, **opciones):
        super().__init__(**opciones)
        self.z = -0.5                         # por delante del resto del HUD
        self.panel = panel_tinta(self, self.ANCHO, self.ALTO, tono=estilo.COLOR_FONDO)
        arriba = self.ALTO / 2
        self.titulo = Text("", parent=self, origin=(0, 0), position=(0, arriba - 0.07, -0.001),
                           scale=escala_fuente(self.PX_TITULO), color=rgb(estilo.COLOR_TEXTO), font=tipografia.FUENTE_TITULO)
        self.subtitulo = Text("", parent=self, origin=(0, 0), position=(0, arriba - 0.122, -0.001),
                              scale=escala_fuente(self.PX_SUBTITULO), color=rgb(estilo.COLOR_TEXTO_TENUE))
        self.texto = Text("", parent=self, origin=(-0.5, 0.5), position=(-self.ANCHO / 2 + self.MARGEN, self.Y_TEXTO, -0.001),
                          scale=escala_fuente(self.PX_TEXTO), color=rgb(estilo.COLOR_TEXTO))
        self.texto.line_height = self.LINEA
        util = self.ANCHO - 2 * self.MARGEN
        hueco = 0.05
        self.ancho_barra = (util - 2 * hueco) / 3
        xs = [-self.ANCHO / 2 + self.MARGEN + i * (self.ancho_barra + hueco) for i in range(3)]
        self.barras_grupos = [BarraIndicador("", self.ancho_barra, 0, parent=self, position=(x, self.Y_GRUPOS, -0.001))
                              for x in xs]
        self.barras_ciudad = [BarraIndicador("", self.ancho_barra, 0, parent=self, position=(x, self.Y_CIUDAD, -0.001))
                              for x in xs]
        self.resumen = Text("", parent=self, origin=(0, 0.5), position=(0, self.Y_RESUMEN, -0.001),
                            scale=escala_fuente(self.PX_RESUMEN), color=rgb(estilo.COLOR_TEXTO_TENUE))
        self.resumen.line_height = self.LINEA
        self.boton_menu = BotonPrimario("Volver al menú", al_clic=al_menu, ancho=0.36, alto=a_unidades(56),
                                        parent=self, position=(0, -self.ALTO / 2 + 0.07, -0.001))
        self.contenido = None
        self.enabled = False
        diseno_adaptable.ajustar_escala(self)      # ventanas más estrechas que el panel: se encoge entero

    # `contenido`: dict de reloj_calculos.contenido_final_semana. Llamarlo otra vez con lo mismo no repinta.
    def mostrar(self, contenido):
        if contenido != self.contenido:
            self.contenido = contenido
            self.titulo.text = contenido["titulo"]
            self.titulo.color = rgb(_TONOS[contenido["tono"]])
            self.subtitulo.text = contenido["subtitulo"]
            self._poner_parrafo(contenido["texto"])
            grupos, ciudad = contenido["barras_grupos"], contenido["barras_ciudad"]
            self._poner_fila(self.barras_grupos, [(n, v, True) for n, v in grupos], self.Y_GRUPOS)
            # Sin GameState no hay fila de grupos: la de la ciudad sube a su sitio.
            self._poner_fila(self.barras_ciudad, ciudad, self.Y_CIUDAD if grupos else self.Y_GRUPOS - 0.03)
            self.resumen.text = "\n".join(contenido["resumen"])
        self.enabled = True

    def ocultar(self):
        self.enabled = False

    def _poner_parrafo(self, cadena):
        self.texto.scale = escala_fuente(self.PX_TEXTO)
        lineas = envolver_texto(cadena, _medidor(self.texto), self.ANCHO - 2 * self.MARGEN)
        if len(lineas) > self.MAX_LINEAS_TEXTO:       # no debe pisar las barras: se encoge lo justo y se vuelve a partir
            factor = self.MAX_LINEAS_TEXTO / len(lineas)
            self.texto.scale = escala_fuente(self.PX_TEXTO) * factor
            lineas = envolver_texto(cadena, _medidor(self.texto), self.ANCHO - 2 * self.MARGEN)
        self.texto.text = "\n".join(lineas)

    @staticmethod
    def _poner_fila(barras, valores, y):
        for i, barra in enumerate(barras):
            if i >= len(valores):
                barra.enabled = False
                continue
            nombre, valor, mas_es_mejor = valores[i]
            barra.enabled = True
            barra.y = y
            barra.etiqueta = nombre
            barra.actualizar(valor)
            if not mas_es_mejor and barra.relleno.enabled:      # desinformación: mucho es MALO (color invertido)
                barra.rgb_relleno = estilo.rgb_por_valor(100 - valor)
                barra.relleno.color = rgb(barra.rgb_relleno)
