# Menú de pausa del mundo (Ursina, en camera.ui): se abre con Escape. Reanudar / Volver al
# menú / Salir. Es solo vista: los tres callbacks los pone EscenaMundo (que además libera el
# ratón y congela los controles mientras está abierto).
# Visual (T9): velo de tinta, panel con borde de tinta (más un filo claro para que se vea sobre
# el velo), botón primario («Reanudar») y secundarios, y una guía de teclas. Teclado: flechas o
# Tab mueven el foco, Enter activa (Escape lo gestiona EscenaMundo).

from panda3d.core import ClockObject
from ursina import Entity, Text, camera, color

from frontend import estilo, tipografia, vehiculo_calculos
from frontend.componentes import (
    BotonPrimario, BotonSecundario, a_unidades, escala_fuente, panel_tinta, rgb,
)
from frontend.fondo_menu import FocoTeclado, anadir_filo

ANCHO, ALTO = 0.74, 0.70        # antes 0.60 de ancho: la guía de teclas creció (vehículos y «seguir misión»)
ALTO_CON_AJUSTES = 0.80      # con el botón «Ajustes» el panel crece (4 botones en vez de 3)
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
FILA_TECLAS = 0.058
X_COLUMNAS = (-0.33, 0.05)      # x de la tecla de cada columna


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
        extra = FILA_TECLAS * max(0, (len(TECLAS) + 1) // 2 - 2)     # filas de teclas de más (sobre 2)
        alto = (ALTO_CON_AJUSTES if self.con_ajustes else ALTO) + extra
        dy = extra / 2
        self.velo = Entity(parent=self, model="quad", color=color.rgba32(*estilo.TINTA, ALFA_VELO),
                           scale=(4, 4), z=0.01)
        self.panel = panel_tinta(self, ANCHO, alto, estilo.COLOR_PANEL, estilo.RADIO_PANEL_PX)
        anadir_filo(self.panel, ANCHO, alto, estilo.RADIO_PANEL_PX)
        self.texto_titulo = Text(
            "Pausa", parent=self, origin=(0, 0), position=(0, alto / 2 - 0.075, -0.001),
            scale=escala_fuente(40), font=tipografia.FUENTE_TITULO, color=rgb(estilo.COLOR_TEXTO))

        # Posiciones de los botones: 3 de siempre, o 4 (con «Ajustes» tras «Reanudar») un poco más juntos.
        if self.con_ajustes:
            ys = (0.19, 0.19 - 0.108, 0.19 - 0.216, 0.19 - 0.324)
        else:
            ys = (0.125, 0.125 - 0.115, None, 0.125 - 0.23)
        ys = tuple(None if y is None else y + dy for y in ys)
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
        self.boton_salir = BotonSecundario(
            "Salir", al_clic=al_salir, ancho=ANCHO_BOTON, alto=ALTO_BOTON, tamano_fuente_px=22,
            parent=self, position=(0, ys[3], -0.001))
        self.botones = (self.boton_reanudar, self.boton_menu, self.boton_salir)
        if self.con_ajustes:
            self.botones = (self.boton_reanudar, self.boton_ajustes, self.boton_menu, self.boton_salir)
        self.pantalla_ajustes = None      # se crea al abrir «Ajustes» por primera vez
        self._frame_cierre_ajustes = -1   # frame en que se cerró «Ajustes» (para el Escape compartido)
        self._ocultos_por_ajustes = []

        # Guía de teclas: 2 columnas, con una línea fina encima.
        y0 = (-0.255 if self.con_ajustes else -0.235) + dy
        self.teclas = []
        for i, (tecla, accion) in enumerate(TECLAS):
            columna, fila = i % 2, i // 2
            x = X_COLUMNAS[columna]
            y = y0 - fila * FILA_TECLAS
            ancho_t = a_unidades(34) + a_unidades(11) * len(tecla)
            self.teclas.append(_tecla(self, tecla, x + ancho_t / 2, y, ancho_t))
            Text(accion, parent=self, origin=(-0.5, 0), position=(x + ancho_t + 0.014, y, -0.001),
                 scale=escala_fuente(17), color=rgb(estilo.COLOR_TEXTO_TENUE))

        self.foco = FocoTeclado(lambda: self.botones, parent=self)

    # Al abrir, el foco vuelve al primer botón (Reanudar) y el anillo se oculta hasta usar el teclado.
    def on_enable(self):
        foco = getattr(self, "foco", None)
        if foco is not None:
            foco.reiniciar()

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
