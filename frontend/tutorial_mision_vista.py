# Reproductor GENÉRICO del tutorial breve de cada tipo de misión (Ursina). Recibe un guion (backend/datos/tutoriales_mision.json,
# validado por backend/logica/tutorial_mision.py) y un ADAPTADOR que sabe construir la vista REAL de ese tipo de misión con un
# caso de demo y señalar sus elementos. Pone encima: el oscurecido con hueco sobre el elemento señalado, una mano fantasma que se
# desliza y «pulsa», el bocadillo (como mucho 2 líneas), la barra de progreso («Tutorial 2 de 3: Ahora tú») y «Saltar tutorial».
#
# TRES PARTES. «Mira» (la mano hace el recorrido y se equivoca una vez a propósito), «Ahora tú» (UN paso: el jugador hace la acción
# con el elemento correcto resaltado; si se equivoca no pasa nada, el bocadillo le explica por qué y reintenta, sin temporizador)
# y «De verdad» (cartel breve y empieza la misión real: lo hace quien lo abrió con `al_terminar`).
#
# CONTROLES. Espacio, Enter o clic avanzan un bocadillo; Escape salta TODO (cuenta como visto); dos saltos seguidos en menos de
# SEGUNDOS_DOBLE_SALTO también saltan todo (igual que DirectorCinematica). La tecla con la que se entró a la misión no salta el
# primer bocadillo (DEMORA_CONTINUAR de escena_minijuego). En «Ahora tú» las teclas van a la vista real.
#
# SIN CONSECUENCIAS. Aquí no se llama al `al_terminar` real de nada: el adaptador entrega a la vista un callback propio. El
# tutorial no sabe de GameState, billetera, logros ni reloj; la vista de demo lleva `es_tutorial = True` para que la capa de
# efectos no registre estrellas ni medallas.
#
# GUARDIÁN. Un fallo al construirse o en un frame avisa UNA vez por stderr (banderas_visuales.avisar_una_vez), el tutorial se
# cierra sin dejar nada en pantalla y se llama a `al_terminar(fallo=True)`: la misión sigue como hoy.
#
# REDUCIR MOVIMIENTO: la mano salta de un punto a otro (no se desliza) y no hay temblores.
#
# Rendimiento: pocas entidades (4 paneles del oscurecido + bloqueador, mano, bocadillo, 2 textos, 1 botón), creadas al abrir y
# destruidas al cerrar; un solo update() que llama a avanzar(dt).
# Piel BOTW (docs/ESTILO_BOTW.md; ALCALDE_UI_BOTW=0 o Ajustes › Estilo «Clásico» la apagan): paneles, botones y
# títulos con la piel del menú de inicio (componentes.panel_piel / boton_piel_*, tipografia.fuente_piel).

import time as _reloj_real

from ursina import Entity, Text, color, time

from backend.logica import tutorial_mision as logica
from frontend.cinematica import LineaDeTiempo, Tramo


def construir_linea(pasos, ejecutor, al_terminar=None):
    """LineaDeTiempo (frontend/cinematica) con un tramo por paso. `ejecutor` implementa, por acción, un método con su nombre
    (bocadillo(paso, i), mover(paso, i), tecla(paso, i), esperar(paso, i), error_demo(paso, i), turno_jugador(paso, i),
    camara(paso, i)) que se llama al EMPEZAR el tramo. El turno del jugador dura «infinito»: se cierra con linea.saltar().
    (Antes en backend/logica/tutorial_mision.py; movida aquí por ARQ-004.)"""
    tramos = []
    for i, paso in enumerate(pasos):
        metodo = getattr(ejecutor, paso["accion"])
        tramos.append(Tramo(f"{i}:{paso['accion']}", logica.duracion_paso(paso),
                            al_empezar=lambda m=metodo, p=paso, n=i: m(p, n)))
    return LineaDeTiempo(tramos, al_terminar=al_terminar)
from frontend import banderas_visuales as bv
from frontend import estilo, tipografia
from frontend.cinematica import ease_in_out, lerp
from frontend.componentes import a_unidades, destruir_arbol, escala_fuente, rgb
from frontend.componentes import panel_piel
from frontend.minijuegos import ui

Z_TUTORIAL = -0.5
Z_OSCURO, Z_BURBUJA, Z_MANO, Z_ROTULO, Z_BOTON = -0.2, -0.25, -0.3, -0.26, -0.27     # delante de la vista de demo
EXTENSION = 4.0                 # mitad del lado de los paneles de oscurecido (cubren cualquier ventana)
MARGEN_HUECO = 0.012
ALFA_OSCURO = 0.62
ANCHO_BOCADILLO = 0.86
PX_BOCADILLO = 20
SEGUNDOS_DOBLE_SALTO = 1.0
DEMORA_PRIMER_SALTO = 0.5       # = frontend.escenas.escena_minijuego.DEMORA_CONTINUAR
TONO_MANO = (255, 255, 255)
TONO_MANO_PULSO = (255, 214, 10)
RADIO_MANO = 0.026


def _rgba(tono, alfa):
    return color.rgba32(int(tono[0]), int(tono[1]), int(tono[2]), int(max(0.0, min(1.0, alfa)) * 255))


class TutorialMision(Entity):

    def __init__(self, id_, guion, adaptador, al_terminar, **opciones):
        super().__init__(**opciones)
        self.z = Z_TUTORIAL
        self.id = id_
        self.guion = guion
        self.pasos = guion["pasos"]
        self.adaptador = adaptador
        self._al_terminar = al_terminar
        self.cerrado = False
        self.vista = None
        self.reloj = 0.0
        self.ultimo_salto = None
        self.indice = -1
        self.paso = None
        self.en_turno = False
        self.turno_hecho = False
        self.mano_de = (0.0, 0.0)
        self.mano_a = (0.0, 0.0)
        self.mano_visible = False
        self._avanza_pendiente = 0.0
        self._avanza_total = 0.0
        self._duracion_paso = 1.0
        self._pulso = 0.0
        self.hueco = None
        try:
            self.vista = adaptador.crear_vista(self, self._vista_termino)
            self._montar_capas()
            self.linea = construir_linea(self.pasos, self, al_terminar=self._fin_de_la_linea)
            self.linea.avanzar(0.0)             # arranca el primer paso (los de duración 0 ya se ejecutan)
        except Exception:
            self._limpiar()
            raise

    # ------------------------------------------------------------ montaje

    def _montar_capas(self):
        self.oscuros = []
        for _ in range(4):
            self.oscuros.append(Entity(parent=self, model="quad", color=_rgba((8, 10, 16), ALFA_OSCURO), z=Z_OSCURO,
                                       collider="box"))
        # Sobre el hueco: durante «Mira» las manos del jugador no tocan la vista; en «Ahora tú» se quita.
        self.bloqueo = Entity(parent=self, model="quad", color=color.rgba(0, 0, 0, 0), z=Z_OSCURO, collider="box")
        self.mano = Entity(parent=self, model="circle", color=rgb(TONO_MANO), scale=(RADIO_MANO, RADIO_MANO), z=Z_MANO)
        self.mano_centro = Entity(parent=self.mano, model="circle", color=rgb(estilo.TINTA), scale=(0.55, 0.55), z=-0.01)
        self.mano.enabled = False
        self.burbuja = Entity(parent=self, z=Z_BURBUJA)
        self.rotulo_progreso = Text("", parent=self, origin=(-0.5, 0.5), position=(-0.81, 0.497, Z_ROTULO),
                                    scale=escala_fuente(13), color=rgb(estilo.COLOR_TEXTO_TENUE), font=tipografia.FUENTE_TEXTO)
        self.boton_saltar = ui.Boton("Saltar tutorial", self.saltar_todo, 0.3, 0.05, 15, parent=self,
                                     position=(0.66, 0.482, Z_BOTON))
        self._poner_hueco(None)

    # ------------------------------------------------------------ hueco, mano y bocadillo

    def _rect_de(self, elemento):
        """(cx, cy, ancho, alto) del elemento en coordenadas de este tutorial; None si no se puede medir."""
        if elemento is None:
            return None
        try:
            limites = elemento.getTightBounds(self)
            if limites:
                minimo, maximo = limites
                if maximo.x > minimo.x and maximo.y > minimo.y:
                    return ((minimo.x + maximo.x) / 2, (minimo.y + maximo.y) / 2, maximo.x - minimo.x, maximo.y - minimo.y)
            posicion = elemento.get_position(self)
            return (posicion.x, posicion.y, 0.1, 0.1)
        except Exception:                       # noqa: BLE001  sin medida: se oscurece todo y la mano va al centro
            return None

    def _poner_hueco(self, rect):
        """Oscurece toda la pantalla salvo `rect`; con None (sin elemento) cubre todo."""
        self.hueco = rect
        ext = EXTENSION
        if not self.guion.get("oscuro", True):         # tutoriales sobre el mundo 3D: no se oscurece lo que hay que mirar
            for panel in self.oscuros:
                panel.enabled = False
            self.bloqueo.enabled = False
            return
        if rect is None:
            self.oscuros[0].position, self.oscuros[0].scale = (0, 0, Z_OSCURO), (ext * 2, ext * 2)
            for panel in self.oscuros[1:]:
                panel.enabled = False
            self.oscuros[0].enabled = True
            self.bloqueo.enabled = False
            return
        cx, cy, ancho, alto = rect
        x0, x1 = cx - ancho / 2 - MARGEN_HUECO, cx + ancho / 2 + MARGEN_HUECO
        y0, y1 = cy - alto / 2 - MARGEN_HUECO, cy + alto / 2 + MARGEN_HUECO
        trozos = [
            ((-ext + x0) / 2, 0.0, x0 + ext, ext * 2),                 # izquierda
            ((x1 + ext) / 2, 0.0, ext - x1, ext * 2),                  # derecha
            ((x0 + x1) / 2, (y1 + ext) / 2, x1 - x0, ext - y1),        # arriba
            ((x0 + x1) / 2, (-ext + y0) / 2, x1 - x0, y0 + ext),       # abajo
        ]
        for panel, (px, py, sx, sy) in zip(self.oscuros, trozos):
            panel.enabled = sx > 0 and sy > 0
            panel.position, panel.scale = (px, py, Z_OSCURO), (max(sx, 0.0001), max(sy, 0.0001))
        self.bloqueo.position, self.bloqueo.scale = ((x0 + x1) / 2, (y0 + y1) / 2, Z_OSCURO), (x1 - x0, y1 - y0)
        self.bloqueo.enabled = not self.en_turno

    def _poner_burbuja(self, texto, tono=None):
        for hijo in list(self.burbuja.children):
            destruir_arbol(hijo)
        if not texto:
            return
        lineas = ui.lineas_de(texto, PX_BOCADILLO, ANCHO_BOCADILLO - 0.06)
        alto = ui.alto_de(len(lineas), PX_BOCADILLO) + 0.07
        # Debajo del elemento señalado si este está en la mitad de arriba; si no, encima.
        cy = self.hueco[1] if self.hueco else 0.0
        medio = self.hueco[3] / 2 if self.hueco else 0.0
        y = cy - medio - MARGEN_HUECO - alto / 2 - 0.03 if cy > -0.05 else cy + medio + MARGEN_HUECO + alto / 2 + 0.03
        y = max(-0.40 + alto / 2, min(0.40 - alto / 2, y))
        x = max(-0.9 + ANCHO_BOCADILLO / 2, min(0.9 - ANCHO_BOCADILLO / 2, self.hueco[0] if self.hueco else 0.0))
        panel_piel(self.burbuja, ANCHO_BOCADILLO, alto, tono=estilo.COLOR_PANEL, position=(x, y, 0))
        ui.texto(self.burbuja, texto, PX_BOCADILLO, ANCHO_BOCADILLO - 0.06, tono or estilo.COLOR_TEXTO,
                 (x - ANCHO_BOCADILLO / 2 + 0.03, y + alto / 2 - 0.035))
        if not self.en_turno:
            ui.texto(self.burbuja, "Espacio, Enter o clic: seguir", 12, 0.5, estilo.COLOR_TEXTO_TENUE,
                     (x - ANCHO_BOCADILLO / 2 + 0.03, y - alto / 2 + 0.03))

    def _mover_mano_a(self, rect):
        centro = (rect[0], rect[1]) if rect else (0.0, 0.0)
        self.mano_de = self.mano_a if self.mano_visible else centro
        self.mano_a = centro
        self.mano_visible = True
        self.mano.enabled = True
        if bv.reducir_movimiento():
            self.mano_de = self.mano_a            # salta de un punto a otro: sin deslizarse
            self._colocar_mano(1.0)

    def _colocar_mano(self, fraccion):
        f = ease_in_out(fraccion)
        self.mano.x = lerp(self.mano_de[0], self.mano_a[0], f)
        self.mano.y = lerp(self.mano_de[1], self.mano_a[1], f)

    # ------------------------------------------------------------ pasos (los llama la LineaDeTiempo al empezar cada tramo)

    def _empezar_paso(self, paso, indice):
        self._vaciar_avance()
        self.indice, self.paso = indice, paso
        self.en_turno = False
        self._duracion_paso = max(0.05, logica.duracion_paso(paso))
        self._avanza_pendiente = self._avanza_total = float(paso.get("avanza", 0.0))
        etapa = paso.get("etapa") or logica.etapa_de(self.pasos, indice)     # «etapa»: fuerza el rótulo de un paso
        self.rotulo_progreso.text = self.guion.get("rotulo") or logica.rotulo_progreso(etapa)
        self.boton_saltar.enabled = True
        # Gancho opcional del adaptador al empezar el paso: puede devolver cuántos segundos de juego hay que avanzar en él
        # (p. ej. hasta que la barra salga de la zona o llegue la nota); None = lo que diga el guion.
        al_paso = getattr(self.adaptador, "al_paso", None)
        if al_paso is not None:
            avance = al_paso(self.vista, paso)
            if avance is not None:
                self._avanza_pendiente = self._avanza_total = float(avance)

    def _elemento(self, foco):
        return self.adaptador.elemento(self.vista, foco)

    def bocadillo(self, paso, indice):
        self._empezar_paso(paso, indice)
        rect = self._rect_de(self._elemento(paso["foco"])) if "foco" in paso else None
        self._poner_hueco(rect)
        self._poner_burbuja(paso["texto"])
        if rect is not None and self.mano_visible:
            self.mano_de = self.mano_a = (self.mano.x, self.mano.y)

    def mover(self, paso, indice):
        self._empezar_paso(paso, indice)
        rect = self._rect_de(self._elemento(paso["foco"]))
        self._poner_hueco(rect)
        self._mover_mano_a(rect)
        self.adaptador.poner_foco(self.vista, paso["foco"])

    def tecla(self, paso, indice):
        self._empezar_paso(paso, indice)
        self._pulso = 0.35
        boton = self.adaptador.elemento_tecla(self.vista, paso["k"])
        if boton is not None:
            rect = self._rect_de(boton)
            self._poner_hueco(rect)
            self._mover_mano_a(rect)
            self.mano_de = self.mano_a
            self._colocar_mano(1.0)
        self.adaptador.enviar_tecla(self.vista, paso["k"])

    def esperar(self, paso, indice):
        self._empezar_paso(paso, indice)
        self._poner_burbuja("")

    def error_demo(self, paso, indice):
        self._empezar_paso(paso, indice)
        rect = self._rect_de(self._elemento(paso["foco"]))
        self._poner_hueco(rect)
        self._mover_mano_a(rect)
        self.adaptador.poner_foco(self.vista, paso["foco"])
        self.adaptador.error(self.vista, paso)          # el error a propósito (si el tipo de misión lo hace con una acción)
        self._poner_burbuja(paso["texto"], tono=estilo.ESTADO_AVISO)

    def camara(self, paso, indice):
        self._empezar_paso(paso, indice)
        self.adaptador.camara(self.vista, paso)

    def turno_jugador(self, paso, indice):
        self._empezar_paso(paso, indice)
        self.en_turno = True
        self.turno_hecho = False
        self.mano.enabled = False
        self.mano_visible = False
        rect = self._rect_de(self._elemento(paso["foco"]))
        self._poner_hueco(rect)
        self.adaptador.poner_foco(self.vista, paso["foco"])
        self._poner_burbuja(paso["texto"], tono=estilo.COLOR_ACENTO)
        self.adaptador.armar_turno(self.vista, paso, self._turno_acertado, self._turno_fallo)

    def _turno_acertado(self):
        self.turno_hecho = True

    def _turno_fallo(self, texto=None, bueno=False):
        """Mensaje durante «Ahora tú»: por defecto el «si_falla» del paso; un adaptador puede pasar otro texto (p. ej. el
        siguiente paso de la práctica, con bueno=True)."""
        if self.paso is not None and self.paso.get("accion") == "turno_jugador":
            self._poner_burbuja(texto or self.paso["si_falla"], tono=estilo.COLOR_ACENTO if bueno else estilo.ESTADO_AVISO)

    # ------------------------------------------------------------ avance

    def _vaciar_avance(self):
        """Lo que quedó por avanzar del juego de demo en el paso anterior se aplica de golpe (no se pierde por un dt grande)."""
        resto, self._avanza_pendiente = self._avanza_pendiente, 0.0
        if resto > 0 and self.vista is not None:
            self.adaptador.avanzar_juego(self.vista, resto)

    def avanzar(self, dt):
        if self.cerrado:
            return
        self.reloj += dt
        if self.vista is not None:
            self.adaptador.avanzar_visual(self.vista, dt)
        if self.paso is not None and self._avanza_pendiente > 0:
            cuanto = min(self._avanza_pendiente, self._avanza_total * dt / self._duracion_paso)
            self._avanza_pendiente -= cuanto
            self.adaptador.avanzar_juego(self.vista, cuanto)
        if self.en_turno:
            if self.turno_hecho:
                self.en_turno = False
                self.linea.saltar()              # el siguiente paso (el cartel «De verdad») empieza ya
            return
        self.linea.avanzar(dt)
        if not self.cerrado and self.mano_visible and self.paso is not None and self.paso["accion"] in ("mover", "error_demo"):
            self._colocar_mano(min(1.0, self.linea.progreso_tramo() * 1.4))
        if self._pulso > 0:
            self._pulso = max(0.0, self._pulso - dt)
            self.mano.color = rgb(TONO_MANO_PULSO if self._pulso > 0 else TONO_MANO)
            if not bv.reducir_movimiento():
                self.mano.scale = (RADIO_MANO * (1 + self._pulso), RADIO_MANO * (1 + self._pulso))

    def update(self):
        if self.cerrado:
            return
        try:
            self.avanzar(time.dt)
        except Exception as error:               # noqa: BLE001  guardián: un frame roto cierra el tutorial, no el juego
            self._fallo(error)

    # ------------------------------------------------------------ entrada

    def input(self, key):
        if self.cerrado:
            return
        try:
            self._entrada(key)
        except Exception as error:               # noqa: BLE001
            self._fallo(error)

    def _entrada(self, key):
        if key == "escape":
            self.saltar_todo()
            return
        if self.en_turno:
            if key.startswith("left mouse") or key.endswith(" up") or key.startswith("mouse"):
                return
            self.adaptador.enviar_tecla(self.vista, key)          # la vista real; si es la tecla mala, la puerta la frena
            return
        if key in ("space", "enter", "return") or (key == "left mouse down" and not self.boton_saltar.golpe.hovered):
            self._saltar_bocadillo()

    def _saltar_bocadillo(self):
        if self.reloj < DEMORA_PRIMER_SALTO or self.paso is None or self.paso["accion"] not in ("bocadillo", "camara", "esperar"):
            return
        doble = self.ultimo_salto is not None and self.reloj - self.ultimo_salto <= SEGUNDOS_DOBLE_SALTO
        self.ultimo_salto = self.reloj
        if doble:
            self.saltar_todo()
        else:
            self.linea.saltar()

    def saltar_todo(self):
        """Escape, «Saltar tutorial» o doble pulsación: termina todo (cuenta como visto)."""
        self._cerrar(saltado=True)

    # ------------------------------------------------------------ cierre

    def _vista_termino(self, resultado):
        """Callback PROPIO que recibe la vista de demo en lugar del `al_terminar` real: no hace nada."""

    def _fin_de_la_linea(self):
        self._cerrar(saltado=False)

    def _fallo(self, error):
        bv.avisar_una_vez(f"tutorial_{self.id}", error)
        self._cerrar(saltado=True, fallo=True)

    def _cerrar(self, saltado, fallo=False):
        if self.cerrado:
            return
        self.cerrado = True
        self.enabled = False
        try:
            self.adaptador.cerrar(self.vista)
        except Exception:                        # noqa: BLE001  limpieza de mejor esfuerzo
            pass
        callback, self._al_terminar = self._al_terminar, None
        if callback is not None:
            try:
                callback(saltado, fallo)
            except Exception as error:           # noqa: BLE001  un fallo de quien sigue no tumba el juego
                bv.avisar_una_vez(f"tutorial_{self.id}_cierre", error)

    def _limpiar(self):
        """Fallo al construirse: no queda nada en pantalla (ni oscurecido, ni botón, ni vista de demo)."""
        self.cerrado = True
        try:
            self.adaptador.cerrar(self.vista)
        except Exception:                        # noqa: BLE001
            pass
        try:
            self.enabled = False
            destruir_arbol(self)
        except Exception:                        # noqa: BLE001
            pass
