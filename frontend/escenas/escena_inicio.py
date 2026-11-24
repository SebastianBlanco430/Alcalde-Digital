# Escena de inicio (Ursina): wordmark, subtítulo y botones "Empezar" y "Salir".
# No conoce al gestor de escenas: recibe los callbacks `al_comenzar` y `al_salir`.
# Visual (T7): fondo de menú en capas con deriva lenta, wordmark dibujado por código y botones
# de tinta (primario amarillo / secundario). Teclado: flechas o Tab mueven el foco, Enter activa.
# Menú BOTW (sesión G, ALCALDE_MENU_BOTW, encendido por defecto): frontend/menu_botw.py pone encima una piel con el fondo
# del póster, logo y opciones en cursiva; estos botones siguen siendo los controles (mismos callbacks y confirmaciones).
# Con =0, sin recursos o si la piel falla, este menú se ve tal cual.

from ursina import Entity, Text, color, time

from frontend import diseno_adaptable, estilo
from frontend import menu_botw_calculos as mbc
from frontend import menu_inicio_calculos as mic
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

    def __init__(self, al_comenzar, al_salir=None, al_ajustes=None, al_online=None, **opciones):
        super().__init__(**opciones)
        self._al_comenzar = al_comenzar
        self._salir_del_juego = al_salir
        self.confirmacion = mic.Confirmacion()
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
        # el subtítulo casi llena la placa: con otra fuente o escala no debe salirse de ella
        diseno_adaptable.ajustar_texto(self.texto_subtitulo, ancho_sub - 0.04, escala_base=escala_fuente(21),
                                       escala_min=0.8, max_lineas=1)

        # Con «En línea» hay un botón más: se compacta la columna (alto y paso menores) para que Salir quepa.
        alto_b = self.ALTO_BOTON if al_online is None else a_unidades(50)
        paso = a_unidades(80) if al_online is None else a_unidades(62)
        self.boton_comenzar = BotonPrimario(
            "Empezar", al_clic=self._clic_comenzar, ancho=self.ANCHO_BOTON, alto=alto_b,
            tamano_fuente_px=26, parent=self, position=(0, self.Y_BOTON),
        )
        # Botón «Ajustes» (opcional: solo si main.py pasa `al_ajustes`): va entre Empezar y Salir y Salir baja
        # un puesto. Sin `al_ajustes` el menú queda exactamente como siempre.
        self.boton_ajustes = None
        y_salir = self.Y_BOTON - paso
        if al_ajustes is not None:
            self.boton_ajustes = BotonSecundario(
                "Ajustes", al_clic=al_ajustes, ancho=self.ANCHO_BOTON, alto=alto_b,
                tamano_fuente_px=24, parent=self, position=(0, y_salir),
            )
            y_salir = y_salir - paso
        # Botón «En línea» (opcional: solo si main.py pasa `al_online`, es decir con ONLINE=True): va tras Empezar.
        self.boton_online = None
        if al_online is not None:
            self.boton_online = BotonSecundario(
                "En línea", al_clic=al_online, ancho=self.ANCHO_BOTON, alto=alto_b,
                tamano_fuente_px=24, parent=self, position=(0, y_salir),
            )
            y_salir = y_salir - paso
        self.boton_salir = BotonSecundario(
            "Salir", al_clic=self._clic_salir, ancho=self.ANCHO_BOTON, alto=alto_b,
            tamano_fuente_px=24, parent=self, position=(0, y_salir),
        )
        self.botones = (self.boton_comenzar, self.boton_salir)
        if self.boton_ajustes is not None:
            self.botones = (self.boton_comenzar, self.boton_ajustes, self.boton_salir)
        if self.boton_online is not None:
            self.botones = tuple(b for b in self.botones if b is not self.boton_salir) + (
                self.boton_online, self.boton_salir)
        self.foco = FocoTeclado(lambda: self.botones, parent=self)
        # «Continuar» (guardado de partida): oculto hasta que frontend/registro_guardado.py lo ofrece y hay un guardado.
        self.boton_continuar = BotonPrimario(
            "Continuar", al_clic=self._clic_continuar, ancho=self.ANCHO_BOTON, alto=alto_b,
            tamano_fuente_px=26, parent=self, position=(-self.X_PAREJA, self.Y_BOTON), enabled=False)
        self.texto_continuar = Text(
            "", parent=self, origin=(0, 0), position=(-self.X_PAREJA, self.Y_BOTON + alto_b / 2 + a_unidades(16), -0.001),
            scale=escala_fuente(16), color=rgb(estilo.COLOR_TEXTO), enabled=False)
        self._botones_base = self.botones
        self._al_continuar = None
        self._resumen_guardado = None
        self._crear_confirmacion(alto_b)
        self.botw = None
        if mbc.activo():
            from frontend import menu_botw
            self.botw = menu_botw.crear(self)      # None si faltan recursos o falla: queda el menú de siempre

    X_PAREJA = a_unidades(140)          # con «Continuar» a la vista, él y «Partida nueva» van uno al lado del otro

    # Lo llama frontend/registro_guardado.py: `al_continuar()` carga la partida guardada y `resumen()` devuelve su texto
    # corto («2 jugadores · 5 misiones hechas») o "" si no hay guardado de este mundo.
    def ofrecer_continuar(self, al_continuar, resumen):
        self._al_continuar, self._resumen_guardado = al_continuar, resumen
        self._refrescar_continuar()

    def _clic_continuar(self):
        if self._al_continuar is not None:
            self._al_continuar()

    def _refrescar_continuar(self):
        texto = ""
        if self._resumen_guardado is not None:
            try:
                texto = self._resumen_guardado() or ""
            except Exception:
                texto = ""
        hay = bool(texto)
        self.boton_continuar.enabled = hay
        self.texto_continuar.enabled = hay
        self.texto_continuar.text = f"Partida guardada: {texto}" if hay else ""
        if hay:
            # cabe sobre la pareja de botones (de «Continuar» al centro de «Partida nueva»)
            diseno_adaptable.ajustar_texto(self.texto_continuar, 2 * self.X_PAREJA, escala_base=escala_fuente(16),
                                           escala_min=0.8, max_lineas=1)
        self.boton_comenzar.x = self.X_PAREJA if hay else 0
        self.boton_comenzar.text = "Partida nueva" if hay else "Empezar"
        self.botones = ((self.boton_continuar,) + self._botones_base) if hay else self._botones_base

    # -- Confirmaciones (EST-011 «Salir», BUG-005 «Partida nueva» con guardado): foco en «No», Esc/B = No --

    def _crear_confirmacion(self, alto_b):
        self.velo = Entity(parent=self, model="quad", scale=(4, 2), color=color.rgba(0, 0, 0, 0.55), z=-0.3,
                           collider="box", enabled=False)          # tapa el menú: el ratón no llega a lo de detrás
        self.dialogo = panel_tinta(self, 0.78, 0.3, estilo.COLOR_PANEL, position=(0, 0.02, -0.31), enabled=False)
        self.texto_dialogo = Text("", parent=self.dialogo, origin=(0, 0), position=(0, 0.06, -0.01),
                                  scale=escala_fuente(24), color=rgb(estilo.COLOR_TEXTO))
        self.boton_no = BotonPrimario(mic.TEXTO_NO, al_clic=lambda: self._responder(False), ancho=a_unidades(180),
                                      alto=alto_b, tamano_fuente_px=24, parent=self.dialogo,
                                      position=(-0.16, -0.07, -0.01))
        self.boton_si = BotonSecundario("Sí", al_clic=lambda: self._responder(True), ancho=a_unidades(180),
                                        alto=alto_b, tamano_fuente_px=24, parent=self.dialogo,
                                        position=(0.16, -0.07, -0.01))
        self._botones_menu = None

    def _pedir(self, contenido, al_si):
        if self.confirmacion.abierta:
            return
        self.confirmacion.pedir(contenido, al_si)
        self.texto_dialogo.text = self.confirmacion.pregunta
        self.boton_si.text = self.confirmacion.texto_si
        self.velo.enabled = self.dialogo.enabled = True
        self._botones_menu, self._indice_menu = self.botones, self.foco.indice
        self.botones = (self.boton_no, self.boton_si)
        self.foco.indice = 0                    # «No» con el anillo de foco a la vista
        self.foco.visible = True
        self.foco._hover_previo = None
        self.foco._aplicar()

    def _responder(self, si):
        if not self.confirmacion.abierta:
            return
        if si and not self.confirmacion.puede_si(por_teclado=self.foco.visible):
            return                                  # «Sí» demasiado pronto (aporreando el mando): no pasa nada
        accion = self.confirmacion.responder(si)
        self._cerrar_confirmacion()
        if accion is not None:
            accion()

    def _cerrar_confirmacion(self):
        self.confirmacion.responder(False)
        self.velo.enabled = self.dialogo.enabled = False
        if self._botones_menu is not None:
            self.botones, self.foco.indice = self._botones_menu, self._indice_menu
            self._botones_menu = None
            self.foco._aplicar()

    def _clic_salir(self):
        if self._salir_del_juego is not None:
            self._pedir(mic.SALIR, self._salir_del_juego)

    def _clic_comenzar(self):
        if self._al_comenzar is None:
            return
        if mic.necesita_confirmar_nueva(self.boton_continuar.enabled):
            self._pedir(mic.NUEVA, self._al_comenzar)
        else:
            self._al_comenzar()

    def input(self, key):
        if self.confirmacion.tecla(key):
            self._cerrar_confirmacion()

    def update(self):
        if self.confirmacion.abierta:
            self.confirmacion.avanzar(time.dt, self.foco.enfocado() is self.boton_si)

    def al_salir(self):
        self._cerrar_confirmacion()
        if self.botw is not None:
            self.botw.al_salir()

    def al_entrar(self, **datos):
        self._cerrar_confirmacion()
        self._refrescar_continuar()
        self.foco.reiniciar()
        self.fondo.t = 0.0
        if self.botw is not None:
            self.botw.al_entrar()
