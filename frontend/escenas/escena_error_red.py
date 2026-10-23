# Pantalla de ERROR de red del modo online (Ursina): título y explicación según el motivo (versión, sala llena, rol
# tomado, código incorrecto, mundo distinto, nombre inválido, expulsado, anfitrión desconectado, tiempo agotado...;
# catálogo en online_lobby_calculos.info_error) y dos botones: «Reintentar» (solo si el motivo se puede reintentar)
# y «Volver al menú». No conoce al gestor: callbacks `al_reintentar(pagina)` y `al_menu()`.

from ursina import Entity

from frontend import diseno_adaptable, estilo, tipografia
from frontend import online_lobby_calculos as lobby
from frontend.componentes import BotonPrimario, BotonSecundario, a_unidades, panel_tinta, rgb
from frontend.escenas.escena_base import Escena
from frontend.fondo_menu import FocoTeclado, FondoMenu, anadir_filo
from frontend.online_ui import crear_texto, fijar, texto_envuelto

ANCHO_PANEL, ALTO_PANEL = 1.0, 0.60


class EscenaErrorRed(Escena):

    def __init__(self, al_reintentar=None, al_menu=None, **opciones):
        super().__init__(**opciones)
        self._al_reintentar = al_reintentar
        self._al_menu = al_menu
        self.pagina = "unirse"
        self.info = lobby.info_error(None)
        self.fondo = FondoMenu(parent=self)
        self.raiz = Entity(parent=self)
        diseno_adaptable.ajustar_escala(self.raiz)
        self.panel = panel_tinta(self.raiz, ANCHO_PANEL, ALTO_PANEL, estilo.COLOR_PANEL, estilo.RADIO_PANEL_PX)
        anadir_filo(self.panel, ANCHO_PANEL, ALTO_PANEL, estilo.RADIO_PANEL_PX)
        self.franja = Entity(parent=self.raiz, model="quad", color=rgb(estilo.ESTADO_ERROR),
                             scale=(ANCHO_PANEL - 0.06, 0.008), position=(0, 0.17, -0.004))
        self.t_titulo = crear_texto(self.raiz, "Error", 0, 0.225, 32, origen=(0, 0), font=tipografia.FUENTE_TITULO)
        self.t_texto = crear_texto(self.raiz, " ", -ANCHO_PANEL / 2 + 0.07, 0.11, 21, estilo.COLOR_TEXTO, origen=(-0.5, 0.5))
        self.t_codigo = crear_texto(self.raiz, " ", -ANCHO_PANEL / 2 + 0.07, -0.13, 15, estilo.COLOR_TEXTO_TENUE)
        self.btn_reintentar = BotonPrimario("Reintentar", al_clic=self.reintentar, ancho=0.36, alto=a_unidades(54),
                                            tamano_fuente_px=24, parent=self.raiz, position=(0.22, -0.22, -0.003))
        self.btn_menu = BotonSecundario("Volver al menú", al_clic=self.volver, ancho=0.40, alto=a_unidades(54),
                                        tamano_fuente_px=22, parent=self.raiz, position=(-0.22, -0.22, -0.003))
        self.foco = FocoTeclado(lambda: [self.btn_menu, self.btn_reintentar], parent=self)

    def al_entrar(self, **datos):
        self.fondo.t = 0.0
        self.pagina = datos.get("pagina") or "unirse"
        self.mostrar(datos.get("motivo"))

    def mostrar(self, motivo):
        self.info = lobby.info_error(motivo)
        fijar(self.t_titulo, self.info.titulo)
        texto_envuelto(self.t_texto, self.info.texto, ANCHO_PANEL - 0.14, 21)
        self.t_texto.origin = (-0.5, 0.5)
        fijar(self.t_codigo, f"Código: {self.info.codigo}")
        self.btn_reintentar.fijar_habilitado(self.info.reintentable)
        self.foco.reiniciar()

    def input(self, key):
        if key == "escape" and self.enabled:
            self.volver()

    def reintentar(self):
        if self.info.reintentable and self._al_reintentar is not None:
            self._al_reintentar(self.pagina)

    def volver(self):
        if self._al_menu is not None:
            self._al_menu()
