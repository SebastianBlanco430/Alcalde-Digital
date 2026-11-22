# Firma «la fuente» (M4): la fuente de la Praça da Sé muestra la salud de la ciudad. Python PURO (no importa ursina): de
# (salud, nivel) del Ambiente (frontend/ambiente_vivo.obtener()) saca la altura del chorro, el color y la opacidad del agua,
# si hay agua y qué extras se ven, y los acerca a ese objetivo poco a poco (~1 s) para que nada salte.
#
#   florece  chorro alto (2,2 m), agua cian viva, flores sobre el borde
#   sano     como siempre (chorro 1,4 m, agua AGUA_FUENTE)
#   tenso    chorro bajo (0,5 m), agua gris verdosa opaca
#   apagado  fuente SECA (sin agua ni chorro), basura en la pila y un cartelito de «sin conexión»
#
# La vista es frontend/fuente_firma.py (la instala frontend/registro_fuente_firma.py). Con la bandera encendida
# props_mundo.fuente deja SOLO la piedra en la malla única del decorado; el agua, el chorro y los extras son entidades
# pequeñas aparte. ALCALDE_FIRMA_FUENTE=0/false/no/off: la fuente queda exactamente como antes (agua en la malla, sin extras)
# y la ciudad viva tampoco prioriza la puerta del destino (ciudad_viva_calculos.elegir_sitios sin `foco`).

import os
from typing import NamedTuple

FIRMA_FUENTE = True

SEGUNDOS_TRANSICION = 1.0       # s de un cambio completo de estado (agua, chorro, color y extras)
PERIODO = 0.1                   # s entre dos actualizaciones de la vista
RADIO_FOCO = 12.0               # m alrededor de la puerta del destino en que basura y flores van primero

AGUA_SANA = (84, 168, 214)      # = props_mundo.AGUA_FUENTE
AGUA_VIVA = (96, 226, 255)
AGUA_TURBIA = (112, 128, 112)
MAXIMO_CHORRO = 2.2             # m (con escala 1)


class Estado(NamedTuple):
    chorro: float               # m de alto del chorro (con escala 1), 0 = sin chorro
    color: tuple                # RGB 0-255 del agua
    alfa: float                 # opacidad del agua 0..1
    agua: float                 # 0 = seca, 1 = llena
    flores: float               # 0..1 (fundido de escala)
    basura: float
    cartel: float


OBJETIVOS = {
    "florece": Estado(2.2, AGUA_VIVA, 0.82, 1.0, 1.0, 0.0, 0.0),
    "sano": Estado(1.4, AGUA_SANA, 0.9, 1.0, 0.0, 0.0, 0.0),
    "tenso": Estado(0.5, AGUA_TURBIA, 1.0, 1.0, 0.0, 0.0, 0.0),
    "apagado": Estado(0.0, AGUA_TURBIA, 1.0, 0.0, 0.0, 1.0, 1.0),
}
UMBRALES = (("florece", 0.75), ("sano", 0.5), ("tenso", 0.25))   # = ambiente_ciudad.UMBRALES_NIVEL


def _bandera(nombre, constante):
    valor = os.environ.get(nombre, "").strip().lower()
    if valor in ("1", "true", "si", "sí", "on"):
        return True
    if valor in ("0", "false", "no", "off"):
        return False
    return bool(constante)


def activo():
    return _bandera("ALCALDE_FIRMA_FUENTE", FIRMA_FUENTE)


def nivel_de(salud, nivel=None):
    """El nivel a mostrar: `nivel` si es uno conocido; si no, el que corresponde a `salud` (0..1)."""
    if nivel in OBJETIVOS:
        return nivel
    s = 0.5 if salud is None else float(salud)
    for nombre, umbral in UMBRALES:
        if s >= umbral:
            return nombre
    return "apagado"


def objetivo(salud, nivel=None):
    """Estado al que debe ir la fuente con ese Ambiente."""
    return OBJETIVOS[nivel_de(salud, nivel)]


def _acercar(a, b, paso):
    if abs(b - a) <= paso + 1e-9:          # sin restos de coma flotante: llega EXACTO a la meta
        return b
    return a + paso if b > a else a - paso


def avanzar(actual, meta, dt, segundos=SEGUNDOS_TRANSICION):
    """Un paso de `actual` hacia `meta`: cada valor recorre su rango completo en `segundos` (lineal, sin pasarse)."""
    if actual is None:
        return meta
    f = max(0.0, dt) / max(1e-6, segundos)
    color = tuple(_acercar(a, b, 255.0 * f) for a, b in zip(actual.color, meta.color))
    return Estado(_acercar(actual.chorro, meta.chorro, MAXIMO_CHORRO * f), color, _acercar(actual.alfa, meta.alfa, f),
                  _acercar(actual.agua, meta.agua, f), _acercar(actual.flores, meta.flores, f),
                  _acercar(actual.basura, meta.basura, f), _acercar(actual.cartel, meta.cartel, f))


def iguales(a, b, tolerancia=1e-4):
    if a is None or b is None:
        return a is b
    return (all(abs(x - y) <= tolerancia for x, y in zip(a[:1] + a[2:], b[:1] + b[2:]))
            and all(abs(x - y) <= tolerancia for x, y in zip(a.color, b.color)))


def escala_extra(f):
    """Escala de fundido de un extra (0..1 -> 0..1 con arranque y llegada suaves); 0 = oculto."""
    f = max(0.0, min(1.0, f))
    return f * f * (3.0 - 2.0 * f)


def alto_visible_chorro(estado):
    """m de chorro que se dibujan: el chorro también se recoge cuando la fuente se vacía."""
    return estado.chorro * estado.agua


def foco_de_mision(flujo, mundo):
    """(x, z) de la puerta del destino de la misión actual, o None (sin flujo, sin misión, sin destino o si algo falla)."""
    try:
        mision = flujo.mision_actual() if flujo is not None else None
        destino = getattr(mision, "destino", None)
        if destino is None or mundo is None:
            return None
        punto = mundo.punto_interaccion(destino)
        return None if punto is None else (float(punto[0]), float(punto[1]))
    except Exception:
        return None


# R3b/c (retoques): con el chorro y la corona translúcidos (sin escribir profundidad) el chorro alto de «florece» se leía
# como un haz de luz, la corona como una nube cian flotando y la tinta de pantalla se dibujaba a través de ellos; el agua
# de la pila, sin profundidad, dejaba ver los bordes del vaso como astillas oscuras. Con la bandera: chorro y corona
# opacos (agua de dibujo animado, como antes de M4) y el agua de pila y taza escribe profundidad.
# ALCALDE_FUENTE_OPACA=0 = como estaba.
FUENTE_OPACA = True
BLANCO_CHORRO = 0.6             # cuánto se acerca el color del chorro al blanco (0 = color del agua)


def fuente_opaca_activa():
    return _bandera("ALCALDE_FUENTE_OPACA", FUENTE_OPACA)


def colores_chorro(color, alfa, opaca):
    """((r, g, b, a) del chorro, (r, g, b, a) de la corona) en 0..1 a partir del color del agua (0-255) y su opacidad."""
    r, g, b = (c / 255 for c in color)
    if opaca:
        claro = tuple(c + (1 - c) * BLANCO_CHORRO for c in (r, g, b))
        corona = tuple(min(1.0, c + (1 - c) * 0.35) for c in claro)
        return (*claro, 1.0), (*corona, 1.0)
    claro = tuple(c + (1 - c) * 0.5 for c in (r, g, b))
    return (*claro, 0.55 + 0.35 * alfa), (*(min(1, c * 1.05) for c in claro), 0.85)
