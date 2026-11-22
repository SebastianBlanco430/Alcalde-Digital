# Pulseras visibles (M5): la parte pura (sin ursina ni panda3d). Tests en tests/test_pulseras_visibles.py.
#
#   M5.1  mini-pulseras: las 2 cintas (Convivencia y Confianza) en pequeño junto al chip del reloj. Al cambiar de NIVEL
#         una cinta, late (escala 1 -> 1.15 -> 1 en 300 ms) y enseña 30 s una flecha de tendencia (arriba = mejor).
#         Las posiciones salen de frontend/hud_esquinas_calculos.py; el dibujo, de frontend/pulseras_visibles_vista.py.
#   M5.2  pulseras de la muñeca del jugador más gruesas (escala) y con un realce del color del nivel (no un modelo nuevo).
#   M5.3  ajuste «Pulseras en el HUD: Siempre / Al cambiar» (campo `pulseras_hud` de backend/logica/ajustes.py). Con el
#         HUD en «Mínimo» se comportan como «Al cambiar».
#
# Bandera reversible: PULSERAS_VISIBLES / ALCALDE_PULSERAS_VISIBLES=0 deja todo exactamente como antes (sin minis, sin
# fila en Ajustes y las pulseras de la muñeca con su tamaño y color de siempre).

import math
import os

from backend.logica import manillas as mdl
from frontend import hud_contextual_calculos as hctx

PULSERAS_VISIBLES = True

SIEMPRE, AL_CAMBIAR = "siempre", "al_cambiar"
MODOS = (SIEMPRE, AL_CAMBIAR)
NOMBRES_MODO = {SIEMPRE: "Siempre", AL_CAMBIAR: "Al cambiar"}
CLAVE_AJUSTE = "pulseras_hud"

DURACION_FLECHA = 30.0               # s que la flecha de tendencia sigue a la vista tras un cambio de nivel
DURACION_PULSO = 0.3                 # s del latido (nada de UI dura más de 300 ms: regla de M3.6)
PULSO_MAX = 1.15
MEJOR, IGUAL, PEOR = 1, 0, -1

# M5.2: pulseras de la muñeca del jugador.
GROSOR_MUNECA = 1.6                  # el aro y la cola, 1.6 veces más anchos (solo escala; el radio no cambia)
REALCE_MUNECA = 0.45                 # cuánto se empuja el color hacia el del nivel (y por encima de 1: «emite»)


def _bandera(nombre, constante):
    valor = os.environ.get(nombre, "").strip().lower()
    if valor in ("1", "true", "si", "sí", "on"):
        return True
    if valor in ("0", "false", "no", "off"):
        return False
    return bool(constante)


def activo():
    return _bandera("ALCALDE_PULSERAS_VISIBLES", PULSERAS_VISIBLES)


def modo_valido(modo):
    return modo if modo in MODOS else SIEMPRE


def opciones_selector():
    """[(texto, valor)] para el selector de Ajustes."""
    return [(NOMBRES_MODO[m], m) for m in MODOS]


def siempre_visibles(modo_ajuste, hud_minimo):
    """¿Las minis están siempre a la vista? Con el HUD en «Mínimo» no: se portan como «Al cambiar»."""
    return modo_valido(modo_ajuste) == SIEMPRE and not hud_minimo


def direccion(nivel_previo, nivel_nuevo):
    """MEJOR si sube de nivel (mdl.NIVELES va de mejor a peor), PEOR si baja, IGUAL si no cambia o no se sabe."""
    if nivel_previo not in mdl.NIVELES or nivel_nuevo not in mdl.NIVELES:
        return IGUAL
    a, b = mdl.NIVELES.index(nivel_previo), mdl.NIVELES.index(nivel_nuevo)
    return MEJOR if b < a else PEOR if b > a else IGUAL


def escala_pulso(t):
    """Escala del latido a los `t` s de empezar: 1 -> PULSO_MAX (a la mitad) -> 1 en DURACION_PULSO. None = 1."""
    if t is None or t <= 0.0 or t >= DURACION_PULSO:
        return 1.0
    return 1.0 + (PULSO_MAX - 1.0) * math.sin(math.pi * t / DURACION_PULSO)


def color_realzado(rgb, k=REALCE_MUNECA):
    """Tinte (0..~1.45 por canal) de la cola texturizada: blanco empujado hacia el color del nivel y por encima de 1 en
    sus canales fuertes, para que se lea desde la cámara a 5 m (sin luz: es un «emisivo» barato)."""
    return tuple(1.0 + k * (c / 255.0) - k * 0.35 * (1.0 - c / 255.0) for c in rgb)


def color_aro_realzado(rgb, k=REALCE_MUNECA):
    """Color (0..~1.45) del aro liso: el del nivel, más brillante."""
    return tuple(min(1.0 + k, (c / 255.0) * (1.0 + k)) for c in rgb)


class EstadoMinis:
    """Qué enseña cada mini-pulsera: flecha (y cuánto le queda), latido y alfa del bloque entero."""

    def __init__(self, indicadores):
        self.indicadores = tuple(indicadores)
        self.niveles = {}
        self.flechas = {i: [IGUAL, 0.0] for i in self.indicadores}    # [dirección, s que le quedan]
        self.pulsos = {i: None for i in self.indicadores}             # s desde que empezó el latido, o None
        self.fundido = hctx.Fundido(alfa=0.0)

    def observar(self, niveles):
        """Nuevos niveles {indicador: nivel}. La primera lectura no cuenta como cambio. Devuelve los que cambiaron."""
        cambiados = []
        for i in self.indicadores:
            nuevo = (niveles or {}).get(i)
            if nuevo is None:
                continue
            previo = self.niveles.get(i)
            self.niveles[i] = nuevo
            if previo is None or previo == nuevo:
                continue
            self.flechas[i] = [direccion(previo, nuevo), DURACION_FLECHA]
            self.pulsos[i] = 0.0
            cambiados.append(i)
        return cambiados

    def avanzar(self, dt):
        for i in self.indicadores:
            f = self.flechas[i]
            if f[1] > 0.0:
                f[1] = max(0.0, f[1] - dt)
                if f[1] == 0.0:
                    f[0] = IGUAL
            if self.pulsos[i] is not None:
                self.pulsos[i] += dt
                if self.pulsos[i] >= DURACION_PULSO:
                    self.pulsos[i] = None

    def flecha(self, indicador):
        d, resto = self.flechas[indicador]
        return d if resto > 0.0 else IGUAL

    def escala(self, indicador):
        return escala_pulso(self.pulsos[indicador])

    def reciente(self):
        """¿Alguna cinta cambió de nivel hace menos de DURACION_FLECHA s?"""
        return any(resto > 0.0 for _d, resto in self.flechas.values())

    def alfa(self, visible, siempre, dt):
        """Alfa del bloque: 0 si el HUD está escondido (pausa, panel...); si no, 1 con «siempre» o, con «al cambiar»,
        a la vista solo mientras dure alguna flecha (entra y sale con el fundido de la regla de la UI)."""
        if not visible:
            self.fundido.fijar(0.0)
            return 0.0
        return self.fundido.avanzar(siempre or self.reciente(), dt)
