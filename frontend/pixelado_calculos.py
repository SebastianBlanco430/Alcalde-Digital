# Cálculos del PIXELADO del mundo (resolución interna reducida). Python puro: NO importa ursina ni panda3d; se
# prueba con pytest sin ventana. La parte gráfica (búfer offscreen + filtro NEAREST) está en frontend/pixelado.py.
#
# Vocabulario:
#   escala   número 0..1 que se guarda en los ajustes (`pixel_scale`): 0 = resolución nativa (sin pixelar), 1 = el máximo.
#            Es 0..1 porque así lo mueve el deslizador de la pantalla de Ajustes.
#   divisor  cuántas veces se reduce el mundo en cada eje (1 = nativo, 4 = un cuarto: ventana 1280x720 -> 320x180).
#            divisor = 1 + escala * (DIVISOR_MAX - 1).
#   preset   escala con nombre: Baja · retro / Media / Alta · nativa; «personalizada» cuando el deslizador no coincide.
#
# Solo el MUNDO se pixela: la interfaz (camera.ui) se dibuja siempre a la resolución nativa.
#
# NOMBRES (2026-11-13). Antes el selector decía Retro / Nítido / Normal en ese orden, y «Normal» (mitad de resolución)
# se veía peor que «Nítido» (nativa). Ahora va de menor a mayor calidad con nombres que lo dicen, y el deslizador solo
# da divisores enteros (x1,4 daba píxeles desiguales). Las CLAVES guardadas no cambian. ALCALDE_AJUSTES_V1=1 vuelve a
# los nombres, el orden y el deslizador continuo de antes.

import os

DIVISOR_MAX = 8.0
UMBRAL_NATIVA = 0.01              # escala por debajo de la cual no se monta ningún pase (coste cero)
TOLERANCIA_PRESET = 0.02          # cuánto puede alejarse el deslizador de un preset para seguir llamándose así
LADO_MINIMO_PX = 90               # el búfer interno nunca baja de este alto (ni de la proporción equivalente)
PRESET_PERSONALIZADO = "personalizado"
PRESET_POR_DEFECTO = "nitido"

# (clave, nombre visible, divisor), de menor a mayor calidad: es el orden del selector. «Alta · nativa» (nitido) es el
# estado de siempre (nativa, sin pase).
PRESETS = (
    ("retro", "Baja · retro", 4.0),
    ("normal", "Media", 2.0),
    ("nitido", "Alta · nativa", 1.0),
)
NOMBRE_PERSONALIZADO = "Personalizada"

# Lo que cambia cada valor, para la fila de ayuda bajo el selector.
DESCRIPCIONES = {
    "retro": "El mundo se dibuja a ¼ de resolución: píxeles grandes, estilo retro y el que más FPS da.",
    "normal": "El mundo se dibuja a la mitad de resolución: más FPS, bordes algo más gruesos.",
    "nitido": "El mundo se dibuja a resolución completa: lo más nítido. Los menús siempre van nítidos.",
    "personalizado": "Resolución elegida con el deslizador de pixelado (x2 = mitad, x4 = un cuarto).",
}

# Nombres y orden de antes (ALCALDE_AJUSTES_V1=1).
PRESETS_V1 = (
    ("retro", "Retro", 4.0),
    ("nitido", "Nítido", 1.0),
    ("normal", "Normal", 2.0),
)
NOMBRE_PERSONALIZADO_V1 = "Personalizado"


# ¿Se usan los nombres, el orden y el deslizador continuo de antes? (se lee en cada llamada)
def ajustes_v1():
    return os.environ.get("ALCALDE_AJUSTES_V1", "").strip().lower() in ("1", "true", "si", "sí", "on")


def _presets():
    return PRESETS_V1 if ajustes_v1() else PRESETS


def divisor_de_escala(escala):
    escala = _acotar(escala)
    return 1.0 + escala * (DIVISOR_MAX - 1.0)


def escala_de_divisor(divisor):
    try:
        divisor = float(divisor)
    except (TypeError, ValueError):
        return 0.0
    return _acotar((divisor - 1.0) / (DIVISOR_MAX - 1.0))


def _acotar(valor):
    if isinstance(valor, bool) or not isinstance(valor, (int, float)) or valor != valor:
        return 0.0
    return max(0.0, min(1.0, float(valor)))


# ¿Con esta escala no hace falta pase gráfico? (resolución nativa)
def es_nativa(escala):
    return _acotar(escala) < UMBRAL_NATIVA


def nombres_presets():
    personalizado = NOMBRE_PERSONALIZADO_V1 if ajustes_v1() else NOMBRE_PERSONALIZADO
    return [(nombre, clave) for clave, nombre, _ in _presets()] + [(personalizado, PRESET_PERSONALIZADO)]


# Texto corto de lo que hace un preset (vacío con los nombres de antes, que no lo tenían).
def descripcion_preset(clave):
    if ajustes_v1():
        return ""
    return DESCRIPCIONES.get(clave, DESCRIPCIONES[PRESET_PERSONALIZADO])


# Escala de un preset; None si es «personalizado» o desconocido (no impone ninguna).
def escala_de_preset(clave):
    for c, _, divisor in _presets():
        if c == clave:
            return escala_de_divisor(divisor)
    return None


# Preset cuyo valor coincide (con tolerancia) con `escala`, o «personalizado».
def preset_de_escala(escala):
    escala = _acotar(escala)
    for clave, _, divisor in _presets():
        if abs(escala - escala_de_divisor(divisor)) <= TOLERANCIA_PRESET:
            return clave
    return PRESET_PERSONALIZADO


# Escala del divisor ENTERO más cercano (x1..x8): los divisores con decimales dan píxeles de tamaños desiguales.
# Con ALCALDE_AJUSTES_V1=1 la escala queda como venga.
def ajustar_a_divisor_entero(escala):
    escala = _acotar(escala)
    if ajustes_v1():
        return escala
    return escala_de_divisor(round(divisor_de_escala(escala)))


# Lo que mueven las flechas en el deslizador de pixelado: un divisor entero por pulsación.
def paso_deslizador():
    return 1.0 / (DIVISOR_MAX - 1.0)


# Mantiene coherentes el preset y la escala tras un cambio. `cambiadas` = claves de ajustes que cambiaron.
# Reglas: si cambió la escala, manda ella (el preset se deduce); si solo cambió el preset, su escala se impone
# (salvo «personalizado», que conserva la escala). Devuelve (preset, escala) ya coherentes; la escala siempre cae
# en un divisor entero (un guardado viejo con x1,4 pasa a x1).
def reconciliar(preset, escala, cambiadas):
    escala = ajustar_a_divisor_entero(escala)
    if "pixel_scale" in cambiadas or "preset_grafico" not in cambiadas:
        return preset_de_escala(escala), escala
    impuesta = escala_de_preset(preset)
    if impuesta is None:
        return PRESET_PERSONALIZADO, escala
    return preset, impuesta


# Tamaño (ancho, alto) del búfer interno para una ventana y un divisor, sin bajar del mínimo y manteniendo la proporción.
def tamano_interno(ancho, alto, divisor):
    divisor = max(1.0, float(divisor))
    ancho, alto = max(1, int(ancho)), max(1, int(alto))
    piso = min(alto, LADO_MINIMO_PX)
    factor = max(1.0 / divisor, piso / alto)
    return (max(1, int(round(ancho * factor))), max(1, int(round(alto * factor))))


# Texto del deslizador: «Ninguno» o «x4 · 25 %» (cuánto se agranda el píxel y a qué resolución queda el mundo).
# Con ALCALDE_AJUSTES_V1=1, el de antes: nativa o «Píxel x4,0».
def formato_pixel(escala):
    if ajustes_v1():
        if es_nativa(escala):
            return "Nativa"
        return f"Píxel x{divisor_de_escala(escala):.1f}".replace(".", ",")
    divisor = round(divisor_de_escala(escala))
    if divisor <= 1:
        return "Ninguno"
    return f"x{divisor} · {round(100 / divisor)} %"
