# Marco de TELÉFONO en grande (Ursina, camera.ui): un celular en vertical con bisel de tinta, cámara frontal, botones
# laterales, barra de estado (hora, señal y batería) y una pantalla donde se cuelga el contenido (`self.pantalla`).
# Componente COMPARTIDO: lo usan la bandeja de Civitas y los dilemas de ciberacoso (frontend/registro_telefono_grande.py)
# y está pensado para que el reel 9:16 de la cinemática de intro lo reutilice (fase 2 de la intro).
#
#   MarcoTelefono(parent=camera.ui, al_ayuda=None)
#     .pantalla                 contenedor centrado en la pantalla del teléfono (coordenadas locales de camera.ui;
#                               ancho tgc.PANTALLA_ANCHO, alto tgc.PANTALLA_ALTO, sin escala propia)
#     .abrir(desde=None)        aparece; con `desde` = rect (x, y, ancho, alto) crece desde ahí (el icono del HUD)
#     .cerrar(al_terminar=None) se encoge hacia donde salió y se apaga; mientras se encoge no recibe clics
#     .fijar_hora(texto)        la hora de la barra de estado
#     .animando()               True durante la transición
# La transición dura tgc.DURACION_TRANSICION con ease_in_out y avanza con time.dt en update(): no traba el juego.
# Número de entidades fijo (≈ 20): se crea una vez y se reutiliza.
# Piel BOTW (docs/ESTILO_BOTW.md; ALCALDE_UI_BOTW=0 o Ajustes › Estilo «Clásico» la apagan): paneles, botones y
# títulos con la piel del menú de inicio (componentes.panel_piel / boton_piel_*, tipografia.fuente_piel).

from ursina import Entity, Text, camera, color, time

from frontend import estilo, tipografia
from frontend import hud_contextual_calculos as hctx
from frontend import telefono_grande_calculos as tgc
from frontend.componentes import a_unidades, escala_fuente, modelo_redondeado, rgb
from frontend.componentes import boton_piel_secundario

COLOR_CUERPO = (14, 15, 22)
COLOR_CANTO = (64, 68, 96)
COLOR_PANTALLA = (17, 19, 28)
RADIO_CUERPO_PX = 40
RADIO_PANTALLA_PX = 26


def _quad(padre, ancho, alto, tono, pos, radio_px=0, z=0.0):
    modelo = modelo_redondeado(ancho, alto, radio_px) if radio_px else "quad"
    tinte = rgb(tono) if isinstance(tono, tuple) and len(tono) == 3 else tono
    return Entity(parent=padre, model=modelo, scale=(ancho, alto), position=(pos[0], pos[1], z), color=tinte)


class MarcoTelefono(Entity):

    def __init__(self, al_ayuda=None, **opciones):
        opciones.setdefault("parent", camera.ui)
        super().__init__(enabled=False, **opciones)
        ancho, alto = tgc.TELEFONO_ANCHO, tgc.TELEFONO_ALTO
        borde = a_unidades(estilo.GROSOR_BORDE_PX)
        sx, sy = (a_unidades(v) for v in estilo.DESPLAZAMIENTO_SOMBRA_PX)
        # sombra plana, canto claro (se lee como un objeto) y cuerpo oscuro
        _quad(self, ancho + 2 * borde, alto + 2 * borde, color.rgba32(*estilo.TINTA, estilo.ALFA_SOMBRA),
              (sx * 2, sy * 2), RADIO_CUERPO_PX + 4, z=0.006)
        _quad(self, ancho + 2 * borde, alto + 2 * borde, estilo.TINTA, (0, 0), RADIO_CUERPO_PX + 4, z=0.005)
        _quad(self, ancho, alto, COLOR_CANTO, (0, 0), RADIO_CUERPO_PX, z=0.004)
        _quad(self, ancho - 0.008, alto - 0.008, COLOR_CUERPO, (0, 0), RADIO_CUERPO_PX - 2, z=0.0035)
        # botones laterales: volumen a la izquierda, encendido a la derecha
        for y, largo in ((0.22, 0.07), (0.13, 0.07)):
            _quad(self, 0.008, largo, COLOR_CANTO, (-ancho / 2 - 0.004, y), z=0.007)
        _quad(self, 0.008, 0.09, COLOR_CANTO, (ancho / 2 + 0.004, 0.18), z=0.007)
        # pantalla
        y_pantalla = tgc.PANTALLA_Y
        _quad(self, tgc.PANTALLA_ANCHO, tgc.PANTALLA_ALTO, COLOR_PANTALLA, (0, y_pantalla), RADIO_PANTALLA_PX, z=0.003)
        # cámara frontal en el bisel superior
        _quad(self, 0.07, 0.014, (6, 7, 12), (0, alto / 2 - tgc.BISEL_ARRIBA / 2), 7, z=0.002)
        Entity(parent=self, model="circle", color=rgb((40, 50, 80)), scale=0.009,
               position=(0.022, alto / 2 - tgc.BISEL_ARRIBA / 2, 0.001))
        # contenido (z negativo = delante de la pantalla)
        self.pantalla = Entity(parent=self, position=(0, y_pantalla, -0.002))
        # barra de estado: hora a la izquierda, señal y batería a la derecha
        arriba = tgc.PANTALLA_ALTO / 2 - tgc.ALTO_BARRA_ESTADO / 2
        izquierda = -tgc.PANTALLA_ANCHO / 2 + 0.03
        derecha = tgc.PANTALLA_ANCHO / 2 - 0.03
        self.hora = Text("", parent=self.pantalla, origin=(-0.5, 0), position=(izquierda, arriba, -0.01),
                         scale=escala_fuente(13), color=rgb(estilo.COLOR_TEXTO), font=tipografia.fuente_piel(titulo=True))
        for i in range(4):
            alto_barra = 0.006 + i * 0.003
            _quad(self.pantalla, 0.005, alto_barra, estilo.COLOR_TEXTO,
                  (derecha - 0.075 + i * 0.008, arriba - 0.008 + alto_barra / 2), z=-0.01)
        _quad(self.pantalla, 0.034, 0.016, estilo.COLOR_TEXTO, (derecha - 0.018, arriba), 3, z=-0.01)
        _quad(self.pantalla, 0.028, 0.011, COLOR_PANTALLA, (derecha - 0.018, arriba), 2, z=-0.011)
        _quad(self.pantalla, 0.018, 0.008, estilo.ESTADO_EXITO, (derecha - 0.022, arriba), z=-0.012)
        _quad(self.pantalla, 0.003, 0.007, estilo.COLOR_TEXTO, (derecha + 0.001, arriba), z=-0.01)
        # «?» para releer la explicación del tipo de aviso (solo si hay a quién llamar)
        self.boton_ayuda = None
        if al_ayuda is not None:
            self.boton_ayuda = boton_piel_secundario("?", al_clic=al_ayuda, ancho=0.05, alto=0.05, tamano_fuente_px=20,
                                                     parent=self, position=(ancho / 2 + 0.045, alto / 2 - 0.05, -0.01))
        self._desde = None
        self._t = 0.0
        self._sentido = 0              # 1 abriendo, -1 cerrando, 0 quieto
        self._al_terminar = None
        self._colocar(1.0)

    # -- Transición --

    def _rect_desde(self):
        return self._desde if self._desde is not None else (tgc.TELEFONO_X, -0.2, tgc.TELEFONO_ANCHO * 0.6,
                                                            tgc.TELEFONO_ALTO * 0.6)

    def _curva(self):
        """M3.6 (ALCALDE_UI_ANIMACIONES): ease-out al abrir y también al cerrar (rápido al principio); sin ease-in.
        None = el ease_in_out de antes."""
        if not hctx.animaciones_activas():
            return None
        if getattr(self, "_sentido", 0) < 0:
            return lambda p: 1.0 - hctx.ease_out(1.0 - p)
        return hctx.ease_out

    def _colocar(self, p):
        x, y, escala = tgc.escala_de_rect(tgc.rect_transicion(self._rect_desde(), tgc.rect_telefono(), p, self._curva()))
        self.position = (x, y, self.z)
        self.scale = escala

    def abrir(self, desde=None):
        if desde is not None:
            self._desde = desde
        self._al_terminar = None
        if not self.enabled:
            self._t = 0.0
        self.enabled = True
        self._sentido = 1
        self._colocar(self._t)

    def cerrar(self, al_terminar=None):
        if not self.enabled:
            if al_terminar is not None:
                al_terminar()
            return
        # mientras se encoge los clics no hacen nada: el control ya está cerrado (clic() sin fase no decide)
        self._sentido = -1
        self._al_terminar = al_terminar

    def cerrar_ya(self):
        self._sentido = 0
        self._t = 0.0
        self.enabled = False
        fin, self._al_terminar = self._al_terminar, None
        if fin is not None:
            fin()

    def animando(self):
        return self._sentido != 0

    def update(self):
        if self._sentido == 0:
            return
        # M3.6: abre en 0,18 s y cierra en 0,12 s (antes 0,25 s los dos)
        duracion = (hctx.tiempo("TELEFONO_GRANDE_ENTRADA") if self._sentido > 0 else hctx.tiempo("TELEFONO_GRANDE_SALIDA"))             if hctx.animaciones_activas() else tgc.DURACION_TRANSICION
        paso = time.dt / duracion
        self._t = max(0.0, min(1.0, self._t + paso * self._sentido))
        self._colocar(self._t)
        if self._sentido == 1 and self._t >= 1.0:
            self._sentido = 0
        elif self._sentido == -1 and self._t <= 0.0:
            self.cerrar_ya()

    # -- Contenido --

    def fijar_hora(self, texto):
        texto = texto or ""
        if self.hora.text != texto:
            self.hora.text = texto
