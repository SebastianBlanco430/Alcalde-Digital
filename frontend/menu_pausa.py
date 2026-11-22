# Menú de pausa del mundo (Ursina, en camera.ui): se abre con Escape. Reanudar / Volver al
# menú / Salir. Es solo vista: los tres callbacks los pone EscenaMundo (que además libera el
# ratón y congela los controles mientras está abierto).
# Visual (T9): velo de tinta, panel con borde de tinta (más un filo claro para que se vea sobre
# el velo), botón primario («Reanudar») y secundarios, y una guía de teclas. Teclado: flechas o
# Tab mueven el foco, Enter activa (Escape lo gestiona EscenaMundo).

from panda3d.core import ClockObject
from ursina import Entity, Text, camera, color, time

from frontend import estilo, tipografia, vehiculo_calculos
from frontend import menu_inicio_calculos as mic
from frontend.componentes import (
    BotonPrimario, BotonSecundario, a_unidades, escala_fuente, panel_tinta, rgb,
)
from frontend.fondo_menu import FocoTeclado, anadir_filo

ANCHO, ALTO = 1.22, 0.70        # VIS-005/006: más ancho para 3 columnas de teclas y la fila de ayuda (antes 0.74)
ALTO_CON_AJUSTES = 0.80      # (ya no se usan para el alto: lo calcula _medidas según botones y filas de teclas)
Z_FRENTE = -50
ALFA_VELO = 170
ALFA_VELO_AJUSTES = 245     # con «Ajustes» abierto el HUD del mundo no debe asomar por detrás
ANCHO_BOTON = 0.42
ALTO_BOTON = a_unidades(56)

# (tecla, acción) de la guía; dos columnas, en orden de lectura (izquierda, derecha, siguiente fila...). Con más
# de 2 filas el panel crece FILA_TECLAS por fila y todo su contenido sube la mitad, para seguir centrado.
# En vehículo: Shift = caballito, Ctrl = turbo, Espacio = freno de mano (frontend/vehiculo_mundo.py). Sin caballitos
# (vehiculo_calculos.CABALLITOS = False) Shift sigue siendo el turbo y no hay Ctrl.
if vehiculo_calculos.CABALLITOS:
    TECLAS = (("WASD", "mover"), ("Tab", "teléfono"), ("Shift", "correr / caballito"), ("M", "seguir misión"),
              ("Espacio", "saltar / frenar"), ("E", "entrar / montar"), ("Ctrl", "turbo"))
else:
    TECLAS = (("WASD", "mover"), ("Tab", "teléfono"), ("Shift", "correr / turbo"), ("M", "seguir misión"),
              ("Espacio", "saltar / frenar"), ("E", "entrar / montar"))
# VIS-006: también las de los paneles (las mismas que el README del repo).
TECLAS = TECLAS + (("L", "bandeja de Civitas"), ("K", "dilemas"), ("B", "pulseras"), ("N", "mapa"),
                   ("I", "mochila"))
FILA_TECLAS = 0.052
X_COLUMNAS = (-0.56, -0.15, 0.26)   # x de la tecla de cada columna (VIS-006: 3 columnas para que quepan todas)
PASO_BOTON = 0.1
CABECERA = 0.13                 # alto del título
FILA_EXTRA = 0.09              # fila de ayuda dentro del panel: «Cómo se juega» y «Avisos de Civitas» (VIS-005)
X_EXTRA = (-0.17, 0.17)         # x de cada hueco de la fila de ayuda
ANCHO_EXTRA = 0.30
SEPARACION_TECLAS = 0.035
PIE = 0.04


def _medidas(n_botones, n_teclas):
    """(alto del panel, [y de cada botón], y de la fila de ayuda, y de la primera fila de teclas); y relativas al centro."""
    filas = -(-n_teclas // len(X_COLUMNAS))
    alto = CABECERA + n_botones * PASO_BOTON + FILA_EXTRA + SEPARACION_TECLAS + filas * FILA_TECLAS + PIE
    arriba = alto / 2 - CABECERA
    ys = [arriba - PASO_BOTON * (i + 0.5) for i in range(n_botones)]
    y_extra = arriba - n_botones * PASO_BOTON - FILA_EXTRA / 2
    y_teclas = arriba - n_botones * PASO_BOTON - FILA_EXTRA - SEPARACION_TECLAS - FILA_TECLAS / 2
    return alto, ys, y_extra, y_teclas


# Tecla estilo teclado: papel con borde de tinta y base gruesa; devuelve la entidad.
def _tecla(padre, texto, x, y, ancho):
    alto = a_unidades(30)
    tecla = panel_tinta(padre, ancho, alto, estilo.PAPEL, estilo.RADIO_CHIP_PX, borde_px=2,
                        position=(x, y, -0.001))
    Text(texto, parent=tecla, origin=(0, 0), position=(0, a_unidades(1), -0.001),
         scale=escala_fuente(17), font=tipografia.FUENTE_TITULO, color=rgb(estilo.TINTA))
    return tecla


class MenuPausa(Entity):

    # con_ajustes: añade el botón «Ajustes» (por defecto, el de la bandera AJUSTES); False = menú de siempre.
    def __init__(self, al_reanudar, al_menu, al_salir, con_ajustes=None, **opciones):
        opciones.setdefault("parent", camera.ui)
        super().__init__(z=Z_FRENTE, enabled=False, **opciones)
        if con_ajustes is None:
            from backend.logica.ajustes import AJUSTES
            con_ajustes = AJUSTES
        self.con_ajustes = bool(con_ajustes)
        alto, ys_botones, self._y_extra, y0 = _medidas(4 if self.con_ajustes else 3, len(TECLAS))
        self.velo = Entity(parent=self, model="quad", color=color.rgba32(*estilo.TINTA, ALFA_VELO),
                           scale=(4, 4), z=0.01)
        self.panel = panel_tinta(self, ANCHO, alto, estilo.COLOR_PANEL, estilo.RADIO_PANEL_PX)
        anadir_filo(self.panel, ANCHO, alto, estilo.RADIO_PANEL_PX)
        self.texto_titulo = Text(
            "Pausa", parent=self, origin=(0, 0), position=(0, alto / 2 - 0.075, -0.001),
            scale=escala_fuente(40), font=tipografia.FUENTE_TITULO, color=rgb(estilo.COLOR_TEXTO))

        # Posiciones de los botones: 3 de siempre, o 4 (con «Ajustes» tras «Reanudar»).
        ys = tuple(ys_botones) if self.con_ajustes else (ys_botones[0], ys_botones[1], None, ys_botones[2])
        self.boton_reanudar = BotonPrimario(
            "Reanudar", al_clic=al_reanudar, ancho=ANCHO_BOTON, alto=ALTO_BOTON, tamano_fuente_px=24,
            parent=self, position=(0, ys[0], -0.001))
        self.boton_ajustes = None
        if self.con_ajustes:
            self.boton_ajustes = BotonSecundario(
                "Ajustes", al_clic=self.abrir_ajustes, ancho=ANCHO_BOTON, alto=ALTO_BOTON, tamano_fuente_px=22,
                parent=self, position=(0, ys[1], -0.001))
        self.boton_menu = BotonSecundario(
            "Volver al menú", al_clic=al_menu, ancho=ANCHO_BOTON, alto=ALTO_BOTON, tamano_fuente_px=22,
            parent=self, position=(0, ys[2] if self.con_ajustes else ys[1], -0.001))
        self._salir_del_juego = al_salir
        self.confirmacion = mic.Confirmacion()          # EST-011: «Salir» pregunta («No» con el foco; Esc = No)
        self.boton_salir = BotonSecundario(
            "Salir", al_clic=self._pedir_salir, ancho=ANCHO_BOTON, alto=ALTO_BOTON, tamano_fuente_px=22,
            parent=self, position=(0, ys[3], -0.001))
        self.botones = (self.boton_reanudar, self.boton_menu, self.boton_salir)
        if self.con_ajustes:
            self.botones = (self.boton_reanudar, self.boton_ajustes, self.boton_menu, self.boton_salir)
        self.pantalla_ajustes = None      # se crea al abrir «Ajustes» por primera vez
        self._frame_cierre_ajustes = -1   # frame en que se cerró «Ajustes» (para el Escape compartido)
        self._ocultos_por_ajustes = []

        # Guía de teclas: 3 columnas bajo la fila de ayuda.
        self.teclas = []
        for i, (tecla, accion) in enumerate(TECLAS):
            columna, fila = i % len(X_COLUMNAS), i // len(X_COLUMNAS)
            x = X_COLUMNAS[columna]
            y = y0 - fila * FILA_TECLAS
            ancho_t = a_unidades(34) + a_unidades(11) * len(tecla)
            self.teclas.append(_tecla(self, tecla, x + ancho_t / 2, y, ancho_t))
            Text(accion, parent=self, origin=(-0.5, 0), position=(x + ancho_t + 0.014, y, -0.001),
                 scale=escala_fuente(17), color=rgb(estilo.COLOR_TEXTO_TENUE))

        self.foco = FocoTeclado(lambda: self.botones, parent=self)
        self._crear_confirmacion()

    # VIS-005: hueco `i` (0 o 1) de la fila de ayuda, DENTRO del panel, para los botones que añaden otros módulos
    # («Cómo se juega», «Avisos de Civitas»). Devuelve (x, y, z) relativos al menú.
    def posicion_extra(self, i):
        return (X_EXTRA[min(max(int(i), 0), len(X_EXTRA) - 1)], self._y_extra, -0.001)

    # Al abrir, el foco vuelve al primer botón (Reanudar) y el anillo se oculta hasta usar el teclado.
    def on_enable(self):
        if getattr(self, "confirmacion", None) is not None:
            self._cerrar_confirmacion()
        foco = getattr(self, "foco", None)
        if foco is not None:
            foco.reiniciar()

    def on_disable(self):
        if getattr(self, "confirmacion", None) is not None:
            self._cerrar_confirmacion()

    # -- «¿Salir del juego?» (EST-011): mismo diálogo que el menú de inicio --

    def _crear_confirmacion(self):
        self.velo_confirmar = Entity(parent=self, model="quad", color=color.rgba32(*estilo.TINTA, 150),
                                     scale=(4, 4), z=-0.02, collider="box", enabled=False)
        self.dialogo = panel_tinta(self, 0.7, 0.26, estilo.COLOR_PANEL, position=(0, 0, -0.03), enabled=False)
        anadir_filo(self.dialogo, 0.7, 0.26, estilo.RADIO_PANEL_PX)
        self.texto_dialogo = Text(mic.SALIR[0], parent=self.dialogo, origin=(0, 0), position=(0, 0.05, -0.01),
                                  scale=escala_fuente(24), color=rgb(estilo.COLOR_TEXTO))
        self.boton_no = BotonPrimario(mic.TEXTO_NO, al_clic=lambda: self._responder(False), ancho=0.26,
                                      alto=ALTO_BOTON, tamano_fuente_px=22, parent=self.dialogo,
                                      position=(-0.15, -0.055, -0.01))
        self.boton_si = BotonSecundario(mic.SALIR[1], al_clic=lambda: self._responder(True), ancho=0.26,
                                        alto=ALTO_BOTON, tamano_fuente_px=22, parent=self.dialogo,
                                        position=(0.15, -0.055, -0.01))
        self._botones_menu = None

    def _pedir_salir(self):
        if self._salir_del_juego is None or self.confirmacion.abierta:
            return
        self.confirmacion.pedir(mic.SALIR, self._salir_del_juego)
        self.velo_confirmar.enabled = self.dialogo.enabled = True
        self._botones_menu, self._indice_menu = self.botones, self.foco.indice
        self.botones = (self.boton_no, self.boton_si)
        self.foco.indice = 0
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
        self.velo_confirmar.enabled = self.dialogo.enabled = False
        if self._botones_menu is not None:
            self.botones, self.foco.indice = self._botones_menu, self._indice_menu
            self._botones_menu = None
            self.foco._aplicar()

    def update(self):
        if self.confirmacion.abierta:
            self.confirmacion.avanzar(time.dt, self.foco.enfocado() is self.boton_si)

    def input(self, key):
        if self.confirmacion.tecla(key):             # Esc / B del mando = «No»; la pausa sigue abierta
            self._cerrar_confirmacion()
            self._frame_cierre_ajustes = ClockObject.get_global_clock().get_frame_count()

    # «Ajustes»: superpone la pantalla de ajustes (se crea la primera vez) y esconde lo demás del menú.
    def abrir_ajustes(self):
        from frontend.escenas.escena_ajustes import PantallaAjustes
        if self.pantalla_ajustes is None:
            self.pantalla_ajustes = PantallaAjustes(al_cerrar=lambda guardado: self.cerrar_ajustes(), parent=self,
                                                    z=-0.5)
        self._ocultos_por_ajustes = [e for e in self.children
                                     if e is not self.velo and e is not self.pantalla_ajustes and e.enabled]
        for entidad in self._ocultos_por_ajustes:
            entidad.enabled = False
        self.velo.color = color.rgba32(*estilo.TINTA, ALFA_VELO_AJUSTES)
        self.pantalla_ajustes.abrir()

    # ¿Escape pertenece a «Ajustes»? True si está abierta o se cerró en este mismo frame con ese Escape (el controlador
    # del mundo también recibe la misma tecla y no debe cerrar además la pausa).
    def escape_es_de_ajustes(self):
        if self.pantalla_ajustes is not None and self.pantalla_ajustes.enabled:
            return True
        if self.confirmacion.abierta:               # Escape responde «No» a «¿Salir del juego?» (ver input)
            return True
        return self._frame_cierre_ajustes == ClockObject.get_global_clock().get_frame_count()

    # Vuelve del submenú de ajustes al menú de pausa.
    def cerrar_ajustes(self):
        self._frame_cierre_ajustes = ClockObject.get_global_clock().get_frame_count()
        if self.pantalla_ajustes is not None:
            self.pantalla_ajustes.enabled = False
        for entidad in self._ocultos_por_ajustes:
            entidad.enabled = True
        self._ocultos_por_ajustes = []
        self.velo.color = color.rgba32(*estilo.TINTA, ALFA_VELO)
        foco = getattr(self, "foco", None)
        if foco is not None:
            foco.reiniciar()
