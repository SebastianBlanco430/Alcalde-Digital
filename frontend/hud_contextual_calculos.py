# HUD contextual (M3.2): las pulseras y el aviso de Civitas están CERRADOS por defecto y solo se asoman cuando pasa
# algo (cambia una pulsera, llega un mensaje) o cuando el jugador lo pide (B), y luego se desvanecen. Python puro (sin
# ursina ni panda3d): la máquina de estados de tiempos y la detección de «algo cambió»; frontend/registro_manillas.py
# y frontend/hud.py (TelefonoUI) solo aplican el alfa que sale de aquí. Tests: tests/test_hud_contextual.py.
#
# Los tiempos de las animaciones de UI viven en UN sitio (TIEMPOS): M3.6 los generalizará para el resto del HUD.
#
# Bandera reversible: HUD_CONTEXTUAL / ALCALDE_HUD_CONTEXTUAL=0 deja pulseras y banner de Civitas como estaban.

import math
import os

HUD_CONTEXTUAL = True


# Tiempos de las animaciones de UI (segundos). Un único sitio: M3.6 los reutiliza.
class TIEMPOS:
    ENTRADA = 0.18            # fundido de entrada (ease-out)
    SALIDA = 0.12             # fundido de salida
    REVELADO = 4.0            # lo que se queda a la vista un bloque contextual tras un cambio o una tecla
    TOAST = 2.75              # lo que dura el aviso corto de un mensaje junto al botón del teléfono
    DESLIZ_TOAST = 0.02       # unidades de camera.ui que el toast se desliza al entrar (hacia la izquierda)
    # M3.6 (ALCALDE_UI_ANIMACIONES): regla de la UI — entradas 150-200 ms ease-out, salidas 120 ms, nada > 300 ms,
    # sin ease-in. Tweens del HUD/UI llevados a la regla (antes -> ahora, ver ANTES):
    AVISO_ENTRADA = 0.18      # avisos «Presiona E» y genérico
    TARJETA_ENTRADA = 0.18    # tarjetas de notificación con el teléfono abierto (deslizan)
    TARJETA_SALIDA = 0.12     # y su fundido de salida
    BANNER_ENTRADA = 0.18     # banner largo del teléfono (sin HUD contextual)
    BANNER_SALIDA = 0.12
    TELEFONO_GRANDE_ENTRADA = 0.18   # el teléfono crece desde el icono del HUD
    TELEFONO_GRANDE_SALIDA = 0.12
    FEED_ENTRADA = 0.18       # publicación nueva del feed de Civitas
    CINTA_HUD = 0.3           # una cinta del brazalete se funde sobre la anterior (transición de contenido)
    BARRAS_FIN = 0.3          # barras del panel «Partida terminada»
    MAXIMO = 0.3              # ninguna animación de UI dura más
    RANGO_ENTRADA = (0.15, 0.20)


# Valores de antes (s) de cada tween cambiado, para documentar y para volver con ALCALDE_UI_ANIMACIONES=0.
ANTES = {
    "AVISO_ENTRADA": 0.12, "TARJETA_ENTRADA": 0.2, "TARJETA_SALIDA": 0.4, "BANNER_ENTRADA": 0.2, "BANNER_SALIDA": 0.2,
    "TELEFONO_GRANDE_ENTRADA": 0.25, "TELEFONO_GRANDE_SALIDA": 0.25, "FEED_ENTRADA": 0.2, "CINTA_HUD": 0.6,
    "BARRAS_FIN": 0.8,
}
ENTRADAS = ("ENTRADA", "AVISO_ENTRADA", "TARJETA_ENTRADA", "BANNER_ENTRADA", "TELEFONO_GRANDE_ENTRADA", "FEED_ENTRADA")
SALIDAS = ("SALIDA", "TARJETA_SALIDA", "BANNER_SALIDA", "TELEFONO_GRANDE_SALIDA")
TRANSICIONES = ("CINTA_HUD", "BARRAS_FIN")


def animaciones_activas():
    """¿Fundidos reales y regla de tiempos (M3.6)? ALCALDE_UI_ANIMACIONES=1/0 manda; por defecto, sí."""
    valor = os.environ.get("ALCALDE_UI_ANIMACIONES", "").strip().lower()
    if valor in ("0", "false", "no", "off"):
        return False
    return True


def tiempo(nombre):
    """Duración (s) de un tween de UI: la de TIEMPOS con la bandera, la de ANTES sin ella."""
    if not animaciones_activas() and nombre in ANTES:
        return ANTES[nombre]
    return getattr(TIEMPOS, nombre)


class Fundido:
    """Alfa de un bloque con la regla de la UI: entra con ease-out en `entrada` s y SALE también con ease-out (rápido al
    principio) en `salida` s; nunca ease-in. Al cambiar de sentido a medias sigue desde el alfa que tenía (continuo)."""

    def __init__(self, entrada=None, salida=None, alfa=0.0):
        self.entrada = TIEMPOS.ENTRADA if entrada is None else entrada
        self.salida = TIEMPOS.SALIDA if salida is None else salida
        self.alfa = float(alfa)
        self._sentido = 0
        self._t = 1.0

    def fijar(self, alfa):
        self.alfa, self._sentido, self._t = float(alfa), 0, 1.0

    def avanzar(self, visible, dt):
        sentido = 1 if visible else -1
        if sentido != self._sentido:
            self._sentido = sentido
            # tiempo equivalente (0..1) en la curva del nuevo sentido para el alfa actual
            self._t = 1.0 - math.sqrt(max(0.0, 1.0 - self.alfa)) if sentido == 1 else 1.0 - math.sqrt(max(0.0, self.alfa))
        duracion = self.entrada if sentido == 1 else self.salida
        self._t = 1.0 if duracion <= 0 else min(1.0, self._t + dt / duracion)
        self.alfa = ease_out(self._t) if sentido == 1 else 1.0 - ease_out(self._t)
        return self.alfa


OCULTO, ENTRANDO, VISIBLE, SALIENDO = "oculto", "entrando", "visible", "saliendo"


def activo():
    """¿HUD contextual? ALCALDE_HUD_CONTEXTUAL=1/0 manda sobre la constante HUD_CONTEXTUAL."""
    valor = os.environ.get("ALCALDE_HUD_CONTEXTUAL", "").strip().lower()
    if valor in ("1", "true", "si", "sí", "on"):
        return True
    if valor in ("0", "false", "no", "off"):
        return False
    return bool(HUD_CONTEXTUAL)


def ease_out(t):
    """Curva de salida cuadrática para t en [0, 1] (rápida al principio, suave al final)."""
    t = max(0.0, min(1.0, t))
    return 1.0 - (1.0 - t) * (1.0 - t)


def avanzar_fundido(progreso, objetivo_visible, dt, entrada=None, salida=None):
    """Progreso lineal en [0, 1] hacia 1 (entra en `entrada` s) o hacia 0 (sale en `salida` s)."""
    entrada = TIEMPOS.ENTRADA if entrada is None else entrada
    salida = TIEMPOS.SALIDA if salida is None else salida
    if objetivo_visible:
        return 1.0 if entrada <= 0 else min(1.0, progreso + dt / entrada)
    return 0.0 if salida <= 0 else max(0.0, progreso - dt / salida)


def alfa_de(progreso):
    """Alfa que se pinta para un progreso de fundido (la misma curva al entrar y al salir: es continua)."""
    return ease_out(progreso)


class Revelado:
    """Estado de un bloque contextual: oculto -> entrando -> visible (`duracion` s) -> saliendo -> oculto.

    revelar(): (re)abre el temporizador; si ya está a la vista solo lo alarga (no parpadea).
    mantener(True): forzado a la vista mientras dure (tutorial señalando, leyenda abierta); al soltarlo cuenta
    de nuevo `duracion` s antes de irse.
    avanzar(dt) -> alfa en [0, 1]."""

    def __init__(self, duracion=None, entrada=None, salida=None):
        self.duracion = TIEMPOS.REVELADO if duracion is None else duracion
        self.entrada = TIEMPOS.ENTRADA if entrada is None else entrada
        self.salida = TIEMPOS.SALIDA if salida is None else salida
        self.restante = 0.0
        self.progreso = 0.0
        self.forzado = False
        # M3.6: con la regla de animaciones, el alfa lo lleva un Fundido (sale con ease-out); progreso = alfa.
        self._fundido = Fundido(self.entrada, self.salida) if animaciones_activas() else None

    def fijar_alfa(self, alfa):
        """Pone el bloque en `alfa` ya (p. ej. al pasar a «mínimo»: sale desde 1 con su fundido)."""
        self.progreso = float(alfa)
        if self._fundido is not None:
            self._fundido.fijar(alfa)

    def revelar(self, segundos=None):
        self.restante = max(self.restante, self.duracion if segundos is None else segundos)

    def mantener(self, forzado):
        forzado = bool(forzado)
        if self.forzado and not forzado:
            self.revelar()                     # al soltarlo se queda su rato normal
        self.forzado = forzado

    def ocultar_ya(self):
        self.restante, self.progreso, self.forzado = 0.0, 0.0, False
        if self._fundido is not None:
            self._fundido.fijar(0.0)

    def quiere_verse(self):
        return self.forzado or self.restante > 0.0

    def avanzar(self, dt):
        if not self.forzado and self.restante > 0.0:
            self.restante = max(0.0, self.restante - dt)
        if self._fundido is not None:
            self.progreso = self._fundido.avanzar(self.quiere_verse(), dt)
            return self.progreso
        self.progreso = avanzar_fundido(self.progreso, self.quiere_verse(), dt, self.entrada, self.salida)
        return self.alfa

    @property
    def alfa(self):
        return self.progreso if self._fundido is not None else alfa_de(self.progreso)

    @property
    def visible(self):
        return self.progreso > 0.0

    @property
    def estado(self):
        if self.progreso <= 0.0:
            return OCULTO
        if self.quiere_verse():
            return VISIBLE if self.progreso >= 1.0 else ENTRANDO
        return SALIENDO


class DetectorCambios:
    """¿Cambió algo desde la última lectura? Compara un dict {clave: valor} con el anterior. La primera lectura (o tras
    reiniciar) NO cuenta como cambio: al entrar al mundo el bloque sigue cerrado. None = sin datos (no cambia nada)."""

    def __init__(self):
        self._anterior = None

    def reiniciar(self):
        self._anterior = None

    def cambio(self, valores):
        if valores is None:
            return False
        valores = dict(valores)
        anterior, self._anterior = self._anterior, valores
        if anterior is None:
            return False
        return any(anterior.get(k) != v for k, v in valores.items())


# -- Toast del mensaje ---------------------------------------------------------------------------------------------

ENCABEZADO_TOAST = "Civitas"


def primera_linea(texto):
    """El mensaje en una sola línea (sin saltos ni espacios dobles)."""
    return " ".join(str(texto or "").split())


def linea_toast(texto, medir, ancho_max, elipsis="…"):
    """«Civitas: <mensaje>» recortado con elipsis para caber en `ancho_max` (medido con `medir`)."""
    linea = f"{ENCABEZADO_TOAST}: {primera_linea(texto)}"
    if medir(linea) <= ancho_max:
        return linea
    resto = linea
    while len(resto) > len(ENCABEZADO_TOAST) + 2 and medir(resto.rstrip() + elipsis) > ancho_max:
        resto = resto[:-1]
    return resto.rstrip() + elipsis
