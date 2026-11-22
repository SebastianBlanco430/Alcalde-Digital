# Ajuste «HUD: Completo / Mínimo» (M3.5). Python puro (sin ursina ni panda3d); tests en tests/test_hud_modo.py.
#
#   completo  todo el HUD a la vista, como siempre.
#   minimo    solo la línea de misión y el reloj. La franja de confianza, el minimapa (con su chip), el chip de dinero y
#             el botón del teléfono aparecen BAJO DEMANDA 4 s (la máquina Revelado de M3.2): cuando cambia su valor,
#             con su tecla (M/N el minimapa, Tab el teléfono) o mientras haga falta (mapa grande o teléfono abiertos,
#             toast a la vista, tutorial señalando el HUD). Las pulseras ya son contextuales (M3.2).
#
# El ajuste vive en backend/logica/ajustes.py (`hud_modo`). Bandera reversible: HUD_MINIMO_AJUSTE /
# ALCALDE_HUD_MINIMO_AJUSTE=0: ni fila en Ajustes ni efecto (el HUD queda como antes, aunque el JSON diga «minimo»).

import os

from frontend import hud_contextual_calculos as hctx

HUD_MINIMO_AJUSTE = True

COMPLETO, MINIMO = "completo", "minimo"
MODOS = (COMPLETO, MINIMO)
NOMBRES_MODO = {COMPLETO: "Completo", MINIMO: "Mínimo"}

SIEMPRE = ("mision", "reloj")                              # visibles también en «mínimo»
BAJO_DEMANDA = ("franja", "minimapa", "dinero", "telefono")
TECLAS = {"m": ("minimapa",), "n": ("minimapa",), "tab": ("telefono",)}


def activo():
    """¿Existe y se aplica el ajuste? ALCALDE_HUD_MINIMO_AJUSTE=1/0 manda sobre la constante HUD_MINIMO_AJUSTE."""
    valor = os.environ.get("ALCALDE_HUD_MINIMO_AJUSTE", "").strip().lower()
    if valor in ("1", "true", "si", "sí", "on"):
        return True
    if valor in ("0", "false", "no", "off"):
        return False
    return bool(HUD_MINIMO_AJUSTE)


def modo_valido(modo):
    return modo if modo in MODOS else COMPLETO


def opciones_selector():
    """[(texto, valor)] para el selector de Ajustes."""
    return [(NOMBRES_MODO[m], m) for m in MODOS]


class ControlHudModo:
    """Alfa de cada bloque bajo demanda según el modo. En «completo» todos valen 1 y no se cuenta nada."""

    def __init__(self, modo=COMPLETO, bloques=BAJO_DEMANDA):
        self.bloques = tuple(bloques)
        self.revelados = {b: hctx.Revelado() for b in self.bloques}
        self.detectores = {b: hctx.DetectorCambios() for b in self.bloques}
        self.modo = COMPLETO
        self.fijar_modo(modo)

    @property
    def minimo(self):
        return self.modo == MINIMO

    def fijar_modo(self, modo):
        """Cambia de modo en vivo. Al pasar a «mínimo» los bloques salen con su fundido (no de golpe)."""
        modo = modo_valido(modo)
        if modo == self.modo:
            return
        self.modo = modo
        for rev in self.revelados.values():
            rev.ocultar_ya()
            rev.fijar_alfa(1.0 if modo == MINIMO else 0.0)
        for det in self.detectores.values():
            det.reiniciar()

    def revelar(self, bloque):
        if bloque in self.revelados:
            self.revelados[bloque].revelar()

    def mantener(self, bloque, forzado):
        if bloque in self.revelados:
            self.revelados[bloque].mantener(forzado)

    def observar(self, bloque, valor):
        """Nuevo valor del bloque (p. ej. índice de confianza, destino): si cambió, se asoma. La 1.ª lectura no cuenta."""
        if valor is None:                    # sin dato aún: ni cuenta como primera lectura
            return
        if bloque in self.detectores and self.detectores[bloque].cambio({"valor": valor}) and self.minimo:
            self.revelar(bloque)

    def tecla(self, key):
        for bloque in TECLAS.get(key, ()):
            self.revelar(bloque)

    def avanzar(self, dt):
        """{bloque: alfa}. En «completo», 1 para todos."""
        if not self.minimo:
            return {b: 1.0 for b in self.bloques}
        return {b: rev.avanzar(dt) for b, rev in self.revelados.items()}

    def alfa(self, bloque):
        if not self.minimo or bloque not in self.revelados:
            return 1.0
        return self.revelados[bloque].alfa
