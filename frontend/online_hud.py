# HUD del modo ONLINE (Ursina, en camera.ui): pastilla de ping con TEXTO («42 ms»), un aviso arriba (conexión
# inestable, «Reconectando… (n s)», lo que decidió otro jugador, saludos rápidos, «Esperando a tus compañeros»),
# el menú de saludos rápidos (tecla G), el resumen de fin de partida bajo el panel de indicadores y la pantalla
# de «sala cerrada / conexión perdida» con el botón de volver al menú.
#
# Solo dibuja: qué texto toca lo decide frontend/online_mundo_calculos.py y quien llama es IntegracionOnline
# (frontend/online_mundo.py). Se crea como hijo del HudMundo, así que se activa y desactiva con él. El aviso es una
# segunda instancia del AvisoGenerico de hud.py colocada arriba, para no pisar el aviso de abajo («E: montar bici»,
# que usa hud.mostrar_aviso). Todo texto de red llega ya saneado (sanear_texto_visible) y aquí además pasa por
# _seguro() de hud.py.

from ursina import Entity, Text, color

from frontend import estilo
from frontend import online_lobby_calculos as lobby
from frontend import online_mundo_calculos as omc
from frontend.componentes import BotonPrimario, a_unidades, escala_fuente, modelo_redondeado, panel_tinta, rgb
from frontend.hud import MARGEN, AvisoGenerico, _fondo, _medidor, _seguro

Y_AVISO = 0.5 - MARGEN - 0.115          # centro del aviso superior (bajo la pastilla de ping)
COLOR_NIVEL = {
    lobby.NIVEL_BUENO: estilo.ESTADO_EXITO,
    lobby.NIVEL_ACEPTABLE: estilo.ESTADO_AVISO,
    lobby.NIVEL_ALTO: estilo.ESTADO_ERROR,
    lobby.NIVEL_SIN_DATO: estilo.COLOR_TEXTO_TENUE,
}


class HudOnline(Entity):

    ALTO_PASTILLA = 0.046

    def __init__(self, hud, al_menu=None, **opciones):
        opciones.setdefault("parent", hud)
        super().__init__(**opciones)
        self._hud = hud
        self._al_menu = al_menu

        # Pastilla de ping (arriba al centro): texto «42 ms»; el color acompaña pero no es la única señal.
        self.pastilla = Entity(parent=self, position=(0, 0.5 - MARGEN - self.ALTO_PASTILLA / 2, 0))
        self.pastilla_fondo = _fondo(self.pastilla, 0.2, self.ALTO_PASTILLA, color.rgba32(12, 14, 24, 235), 12, z=0.001)
        self.pastilla_texto = Text("— ms", parent=self.pastilla, origin=(0, 0), position=(0, 0, -0.001),
                                   scale=escala_fuente(18), color=rgb(estilo.COLOR_TEXTO))
        self._texto_pastilla = None
        self._nivel = None

        # Aviso superior (segunda instancia del AvisoGenerico de hud.py).
        self.aviso = AvisoGenerico(parent=self)
        self.aviso.y_base = Y_AVISO
        self.aviso.y = Y_AVISO
        self._texto_aviso = None

        # Menú de saludos rápidos (se abre con G): lista fija, sin chat libre.
        self.menu_saludos = Entity(parent=self, position=(-0.55, 0.05, 0), enabled=False)
        alto = 0.05 * (len(omc.SALUDOS) + 1) + 0.03
        self._fondo_saludos = _fondo(self.menu_saludos, 0.40, alto, color.rgba32(12, 14, 24, 240), 12, z=0.001)
        self._fondo_saludos.position = (0.20, -alto / 2 + 0.03)
        Text("Saludo rápido (G para cerrar)", parent=self.menu_saludos, origin=(-0.5, 0.5),
             position=(0.02, 0.0, -0.001), scale=escala_fuente(15), color=rgb(estilo.COLOR_TEXTO_TENUE))
        self.lineas_saludos = []
        for i, frase in enumerate(omc.SALUDOS):
            linea = Text(f"{i + 1}  {_seguro(frase)}", parent=self.menu_saludos, origin=(-0.5, 0.5),
                         position=(0.02, -0.05 * (i + 1), -0.001), scale=escala_fuente(19),
                         color=rgb(estilo.COLOR_TEXTO))
            self.lineas_saludos.append(linea)

        # Resumen de la partida (debajo del panel «Partida terminada»).
        self.resumen = Text(" ", parent=self, origin=(0, 0), position=(0, -0.40, -0.01),
                            scale=escala_fuente(18), color=rgb(estilo.COLOR_TEXTO_TENUE), enabled=False)

        # Pantalla de sala cerrada / conexión perdida (sobre todo lo demás).
        self.cierre = Entity(parent=self, position=(0, 0, -0.05), enabled=False)
        self.cierre_fondo = Entity(parent=self.cierre, model="quad", color=color.rgba32(8, 9, 16, 190),
                                   scale=(4, 2), z=0.01)
        self.cierre_panel = panel_tinta(self.cierre, 0.90, 0.46, estilo.COLOR_PANEL, estilo.RADIO_PANEL_PX)
        Entity(parent=self.cierre, model="quad", color=rgb(estilo.ESTADO_ERROR), scale=(0.84, 0.008),
               position=(0, 0.14, -0.002))
        self.cierre_titulo = Text("Conexión perdida", parent=self.cierre, origin=(0, 0), position=(0, 0.095, -0.003),
                                  scale=escala_fuente(30), color=rgb(estilo.COLOR_TEXTO))
        self.cierre_texto = Text(" ", parent=self.cierre, origin=(0, 0.5), position=(0, 0.04, -0.003),
                                 scale=escala_fuente(19), color=rgb(estilo.COLOR_TEXTO))
        self.cierre_texto.line_height = 1.25
        self.cierre_boton = BotonPrimario("Volver al menú", al_clic=self._volver, ancho=0.40, alto=a_unidades(54),
                                          tamano_fuente_px=22, parent=self.cierre, position=(0, -0.15, -0.004))

    # -- Pastilla de ping --

    def fijar_ping(self, ms, visible=True):
        self.pastilla.enabled = bool(visible)
        if not visible:
            return
        texto = omc.texto_ping(ms)
        nivel = lobby.nivel_ping(ms)
        if texto == self._texto_pastilla and nivel == self._nivel:
            return
        self._texto_pastilla, self._nivel = texto, nivel
        self.pastilla_texto.text = texto
        self.pastilla_texto.color = rgb(COLOR_NIVEL[nivel])
        ancho = max(0.14, _medidor(self.pastilla_texto)(texto) + 0.06)
        self.pastilla_fondo.model = modelo_redondeado(ancho, self.ALTO_PASTILLA, 12)
        self.pastilla_fondo.scale = (ancho, self.ALTO_PASTILLA)

    # -- Aviso superior --

    def fijar_aviso(self, texto):
        if texto == self._texto_aviso:
            return
        self._texto_aviso = texto
        if texto:
            self.aviso.mostrar(texto)
        else:
            self.aviso.ocultar()

    def avanzar(self, dt):
        self.aviso.avanzar(dt)

    # -- Saludos rápidos --

    def mostrar_saludos(self, abierto):
        self.menu_saludos.enabled = bool(abierto)

    @property
    def saludos_abierto(self):
        return bool(self.menu_saludos.enabled)

    # -- Fin de partida --

    def fijar_resumen(self, texto):
        if texto:
            self.resumen.text = _seguro(_partir(str(texto), 70))
            self.resumen.enabled = True
        else:
            self.resumen.enabled = False

    # -- Sala cerrada / conexión perdida --

    def mostrar_cierre(self, motivo):
        info = lobby.info_error(motivo)
        self.cierre_titulo.text = _seguro(info.titulo)
        self.cierre_texto.text = _seguro(_partir(info.texto, 62))
        self.cierre.enabled = True

    def ocultar_cierre(self):
        self.cierre.enabled = False

    @property
    def cierre_visible(self):
        return bool(self.cierre.enabled)

    def _volver(self):
        if self._al_menu is not None:
            self._al_menu()


# Parte `texto` en líneas de hasta `ancho` caracteres (aproximado; el panel es fijo).
def _partir(texto, ancho):
    lineas, actual = [], ""
    for palabra in texto.split():
        if actual and len(actual) + 1 + len(palabra) > ancho:
            lineas.append(actual)
            actual = palabra
        else:
            actual = f"{actual} {palabra}".strip()
    if actual:
        lineas.append(actual)
    return "\n".join(lineas)
