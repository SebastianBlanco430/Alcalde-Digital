# Vista de la recta final (backend/logica/recta_final.py): que el jugador SIENTA que el final de la partida pesa más.
#   - Chip de tensión arriba a la izquierda: «RECTA FINAL · decisiones ×1,4» con una barra de tensión (solo en la recta y
#     solo en el mundo: escenas_del_chip(); en las escenas de misión tapaba su encabezado).
#   - Aviso de entrada: cartel de unos segundos con el evento de entrada («Rumores acumulados»...) y un sonido (si la
#     recta empieza durante una misión, espera a que se vuelva al mundo).
#   - Pulso en cada decisión de la recta: el chip y las barras de indicadores de la escena de misión laten (más cuanto
#     mayor el multiplicador) y suena un clic más grave.
#   - Desenlace: al terminar la partida, una franja con «Ciudad unida / dividida / tomada» y las decisiones clave.
#   - titulo_resultado(): sufijo «· recta final ×1,4» en el título de la pantalla de resultado del grafo social.
#
# Un único vigía en camera.ui (instalar(gestor) desde main.py) que LEE cada PERIODO s; los .text solo cambian cuando el
# contenido cambia (no hay coste por frame más allá de un acumulador). En línea lee lo que mandó el anfitrión
# (FlujoEnLinea.ultimo_rf / desenlace_fin); en hot-seat, el controlador del flujo (FlujoConRectaFinal.recta_final).
#
# BANDERA. RECTA_FINAL_VISTA = False (o ALCALDE_SIN_RECTA_FINAL_VISTA=1, o ALCALDE_SIN_RECTA_FINAL=1): nada se instala.

import os
import sys

RECTA_FINAL_VISTA = True
PERIODO = 0.25              # s entre lecturas del estado
DURACION_AVISO = 4.0        # s del cartel de entrada
SONIDO_ENTRADA = "mensaje_civitas"
SONIDO_DECISION = "clic_ui"
FRANJA_Y = -0.292           # hueco libre de los paneles finales, sobre su botón
CHIP = (-0.64, 0.33)        # bajo el panel de turno (arriba a la derecha está el minimapa)
COLOR_TENSION = ((0.95, 0.75, 0.25), (0.98, 0.50, 0.15), (0.95, 0.25, 0.20))     # por nivel 1..3
COLOR_DESENLACE = {"unida": (0.35, 0.80, 0.45), "dividida": (0.95, 0.70, 0.25), "tomada": (0.90, 0.25, 0.25)}

_SI = ("1", "true", "si", "sí", "on")
_instalado = {"vigia": None}


def _variable(nombre):
    return os.environ.get(nombre, "").strip().lower() in _SI


def activo():
    from backend.logica import recta_final
    return bool(RECTA_FINAL_VISTA) and not _variable("ALCALDE_SIN_RECTA_FINAL_VISTA") and recta_final.activo()


# -- Textos (puros) --

def _mult(m):
    return f"×{float(m):.1f}".replace(".", ",")


def texto_chip(info):
    if not info or not info.get("en_recta"):
        return ""
    return f"RECTA FINAL · decisiones {_mult(info.get('mult', 1.0))}"


def titulo_resultado(titulo, estado):
    """Título de la pantalla de resultado con el sufijo de la recta final (el mismo título si no aplica)."""
    try:
        if not activo():
            return titulo
        ctrl = getattr(estado, "recta_final", None)
        if ctrl is None:
            return titulo
        info = ctrl.info()
        if not info["en_recta"]:
            return titulo
        eco = sum(info["eco"].values()) if info["eco"] else 0
        return f"{titulo} · recta final {_mult(info['mult'])}" + (f" · eco {eco:+d}" if eco else "")
    except Exception:
        return titulo


def lineas_desenlace(datos):
    """(título, [líneas]) de un desenlace: dict de recta_final.desenlace o {"clave", "claves"} del cooperativo."""
    from backend.logica import recta_final
    clave = datos.get("clave")
    if clave not in recta_final.DESENLACES:
        return None
    titulo, texto = recta_final.DESENLACES[clave]
    claves = datos.get("decisiones_clave")
    if claves is None:
        claves = recta_final.claves_de_texto(datos.get("claves", ""))
    return titulo, [texto] + [f"• {c}" for c in list(claves)[:recta_final.CLAVES_EN_PANTALLA]]


# -- Lectura del estado según el flujo --

def _escenas_de_partida():
    """Escenas donde se LEE el estado de la recta final: el mundo y las de misión (fuera de ellas, menú/rol/ajustes/red,
    nada). Leer no es pintar: el pulso, el sonido y el latido de las barras de la escena de juego siguen aquí; lo que
    se pinta (chip y aviso de entrada) lo decide escenas_del_chip()."""
    from frontend.flujo_constantes import INTERIOR, JUEGO, MUNDO, MUNDO_DIGITAL, PARKOUR, TRABAJO
    return {MUNDO, JUEGO, INTERIOR, TRABAJO, MUNDO_DIGITAL, PARKOUR, "minijuego"}


def escenas_del_chip():
    """Escenas donde se PINTAN el chip «RECTA FINAL» y el aviso de entrada: solo el mundo. En minijuegos, escena de
    juego, trabajo, parkour, mundo digital e interior tapaban el encabezado de la escena (retoques 2026-11-22, M1)."""
    from frontend.flujo_constantes import MUNDO
    return frozenset({MUNDO})


def chip_visible(escena, texto):
    """¿Se pinta el chip con `texto` en la escena `escena`? (puro)."""
    return bool(texto) and escena in escenas_del_chip()


def _leer(gestor):
    """(info | None, desenlace | None, terminada). Nunca lanza.

    Fuera de una escena de partida (BUG-001: el menú tras terminar) no hay nada que pintar; la franja del desenlace
    solo va en el mundo, donde está la pantalla final."""
    from frontend.flujo_constantes import MUNDO
    actual = gestor.nombre_actual()
    if actual not in _escenas_de_partida():
        return None, None, False
    escena = gestor._escenas.get(MUNDO)
    flujo = getattr(escena, "flujo", None) if escena is not None else None
    if flujo is None:
        return None, None, False
    terminada = bool(flujo.partida_terminada())
    ctrl = getattr(flujo, "recta_final", None)
    if ctrl is not None:                                       # hot-seat
        info = ctrl.info()
        leer = getattr(flujo, "desenlace_partida", None)
        return info, (leer() if terminada and callable(leer) and actual == MUNDO else None), terminada
    rf = getattr(flujo, "ultimo_rf", None)                     # en línea: lo que mandó el anfitrión
    info = None
    if rf is not None:
        nivel = int(rf.get("nivel", 0))
        info = {"en_recta": nivel > 0, "nivel": nivel, "mult": rf.get("mult", 1.0), "intensidad": nivel / 3.0,
                "decisiones": rf.get("n", 0), "eco": {}, "evento": None, "evento_titulo": None, "evento_texto": None}
    return info, (getattr(flujo, "desenlace_fin", None) if terminada and actual == MUNDO else None), terminada


def _cinematica_final_en_pantalla():
    try:
        from frontend.reloj_constantes import CINE_FINAL
        return CINE_FINAL.get("entidad") is not None
    except Exception:
        return False


def _vigia_cls():
    from ursina import Entity, Text, camera, color, curve, time

    class VigiaRectaFinal(Entity):

        def __init__(self, gestor):
            super().__init__(parent=camera.ui)
            self.gestor = gestor
            self._t = 0.0
            self._chip_txt = None
            self._decisiones = None
            self._entrada_vista = False
            self._flujo_visto = None
            self._aviso_t = 0.0
            self._desenlace_visto = None
            self.chip = Entity(parent=self, model="quad", color=color.rgba(0.08, 0.08, 0.1, 0.82),
                               position=CHIP, scale=(0.42, 0.05), enabled=False)
            self.chip_texto = Text("", parent=self, position=(CHIP[0], CHIP[1] + 0.007), origin=(0, 0), scale=0.85)
            self.barra = Entity(parent=self, model="quad", color=color.rgb(*COLOR_TENSION[0]),
                                position=(CHIP[0] - 0.21, CHIP[1] - 0.019), origin=(-0.5, 0), scale=(0.0, 0.008), enabled=False)
            self.aviso = Entity(parent=self, model="quad", color=color.rgba(0.05, 0.05, 0.07, 0.88),
                                position=(0, 0.26), scale=(0.95, 0.14), enabled=False)
            self.aviso_titulo = Text("", parent=self, position=(0, 0.285), origin=(0, 0), scale=1.6)
            self.aviso_texto = Text("", parent=self, position=(0, 0.235), origin=(0, 0), scale=0.9)
            # Franja del desenlace: en el hueco entre el texto de la pantalla final y su botón, siempre encima.
            self.franja = Entity(parent=self, model="quad", color=color.rgba(0.05, 0.05, 0.07, 0.94),
                                 position=(0, FRANJA_Y), scale=(1.18, 0.112), enabled=False, always_on_top=True)
            self.franja_titulo = Text("", parent=self, position=(0, FRANJA_Y + 0.036), origin=(0, 0), scale=1.05,
                                      always_on_top=True)
            self.franja_texto = Text("", parent=self, position=(-0.55, FRANJA_Y + 0.016), origin=(-0.5, 0.5),
                                     scale=0.74, always_on_top=True)
            self.chip_texto.enabled = self.aviso_titulo.enabled = self.aviso_texto.enabled = False
            self.franja_titulo.enabled = self.franja_texto.enabled = False

        def update(self):
            if self._aviso_t > 0:
                self._aviso_t -= time.dt
                if self._aviso_t <= 0:
                    self._mostrar_aviso(None)
            self._t += time.dt
            escena = self.gestor.nombre_actual()
            if self._t < PERIODO and escena == getattr(self, "_escena_vista", escena):
                return
            self._escena_vista = escena                 # cambio de escena: se relee ya (no queda 1 lectura encima)
            self._t = 0.0
            try:
                self._refrescar(*_leer(self.gestor))
            except Exception as error:      # la vista nunca debe tumbar la partida
                print(f"[recta_final_vista] {type(error).__name__}: {error}", file=sys.stderr)
                self._refrescar(None, None, False)

        def _refrescar(self, info, desenlace, terminada):
            flujo = getattr(self.gestor._escenas.get("mundo"), "flujo", None)
            if flujo is not self._flujo_visto:          # partida nueva o cargada: se reinicia lo visto
                self._flujo_visto = flujo
                self._decisiones = None
                self._entrada_vista = bool(info and info.get("en_recta"))
                self._desenlace_visto = None
            texto = "" if terminada else texto_chip(info)
            pintar = chip_visible(self.gestor.nombre_actual(), texto)
            if (texto, pintar) != self._chip_txt:
                self._chip_txt = (texto, pintar)
                self.chip_texto.text = texto
                for e in (self.chip, self.chip_texto, self.barra):
                    e.enabled = pintar
            if not pintar and self.aviso.enabled:          # se salió del mundo con el aviso puesto
                self._mostrar_aviso(None)
            if texto:
                nivel = max(1, min(3, int(info.get("nivel", 1))))
                self.barra.scale_x = 0.42 * max(0.05, float(info.get("intensidad", 0.0)))
                self.barra.color = color.rgb(*COLOR_TENSION[nivel - 1])
                if not self._entrada_vista and pintar:      # el aviso de entrada espera a volver al mundo
                    self._entrada_vista = True
                    titulo = info.get("evento_titulo") or "Recta final"
                    cuerpo = info.get("evento_texto") or "Desde ahora cada decisión pesa más."
                    self._mostrar_aviso((titulo, cuerpo))
                    self._sonar(SONIDO_ENTRADA, 0.9, 0.85)
                n = info.get("decisiones")
                if self._decisiones is not None and n != self._decisiones:
                    self._pulso(nivel, float(info.get("mult", 1.0)))
                self._decisiones = n
            elif info is not None:
                self._decisiones = info.get("decisiones")
            self._pintar_desenlace(desenlace if terminada else None)

        def _mostrar_aviso(self, contenido):
            visible = contenido is not None
            for e in (self.aviso, self.aviso_titulo, self.aviso_texto):
                e.enabled = visible
            if visible:
                self.aviso_titulo.text, self.aviso_texto.text = contenido
                self._aviso_t = DURACION_AVISO
                self.aviso.scale_x = 0.5
                self.aviso.animate_scale_x(0.95, duration=0.25, curve=curve.out_expo)

        def _pulso(self, nivel, mult):
            fuerza = 1.0 + 0.12 * nivel
            self.chip.scale = (0.42 * fuerza, 0.05 * fuerza)
            self.chip.animate_scale((0.42, 0.05), duration=0.35, curve=curve.out_expo)
            self.chip_texto.color = color.rgb(*COLOR_TENSION[nivel - 1])
            self.chip_texto.animate_color(color.white, duration=0.6)
            self._sonar(SONIDO_DECISION, min(1.0, 0.5 + 0.2 * nivel), max(0.6, 1.1 - 0.15 * nivel))
            self._latir_barras(mult)

        def _latir_barras(self, mult):
            from frontend.flujo_constantes import JUEGO
            if self.gestor.nombre_actual() != JUEGO:
                return
            barras = getattr(self.gestor._escenas.get(JUEGO), "barras", None) or {}
            for barra in barras.values():
                try:
                    base = barra.scale
                    barra.scale = base * (1.0 + 0.08 * (mult - 1.0) / 0.6 + 0.04)
                    barra.animate_scale(base, duration=0.4, curve=curve.out_expo)
                except Exception:
                    continue

        def _pintar_desenlace(self, desenlace):
            clave = (desenlace or {}).get("clave")
            estado = (clave, _cinematica_final_en_pantalla())
            if estado == self._desenlace_visto:
                return
            self._desenlace_visto = estado
            contenido = lineas_desenlace(desenlace) if desenlace else None
            visible = contenido is not None and not estado[1]      # la cinemática del final va primero
            for e in (self.franja, self.franja_titulo, self.franja_texto):
                e.enabled = visible
            if visible:
                self.franja_titulo.text = contenido[0]
                self.franja_titulo.color = color.rgb(*COLOR_DESENLACE.get(clave, (1, 1, 1)))
                claves = contenido[1][1:]
                self.franja_texto.text = "\n".join(claves if claves else contenido[1][:1])

        @staticmethod
        def _sonar(nombre, volumen, pitch):
            try:
                from frontend import audio
                audio.obtener().efecto(nombre, volumen=volumen, pitch=pitch)
            except Exception:
                pass

    return VigiaRectaFinal


def instalar(gestor):
    """Crea el vigía (una vez). Devuelve la entidad o None si la bandera está apagada o algo falla."""
    if not activo():
        return None
    if _instalado["vigia"] is not None:
        return _instalado["vigia"]
    try:
        _instalado["vigia"] = _vigia_cls()(gestor)
    except Exception as error:
        print(f"[recta_final_vista] no se pudo instalar ({type(error).__name__}: {error})", file=sys.stderr)
        return None
    return _instalado["vigia"]
