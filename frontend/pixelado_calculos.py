# Cálculos del PIXELADO del mundo (resolución interna reducida). Python puro: NO importa ursina ni panda3d; se
# prueba con pytest sin ventana. La parte gráfica (búfer offscreen + filtro NEAREST) está en frontend/pixelado.py.
#
# Vocabulario:
#   escala   número 0..1 que se guarda en los ajustes (`pixel_scale`): 0 = resolución nativa (sin pixelar), 1 = el máximo.
#            Es 0..1 porque así lo mueve el deslizador de la pantalla de Ajustes.
#   divisor  cuántas veces se reduce el mundo en cada eje (1 = nativo, 4 = un cuarto: ventana 1280x720 -> 320x180).
#            divisor = 1 + escala * (DIVISOR_MAX - 1).
#   preset   escala con nombre: Retro / Nítido / Normal; «personalizado» cuando el deslizador no coincide con ninguno.
#
# Solo el MUNDO se pixela: la interfaz (camera.ui) se dibuja siempre a la resolución nativa.

DIVISOR_MAX = 8.0
UMBRAL_NATIVA = 0.01              # escala por debajo de la cual no se monta ningún pase (coste cero)
TOLERANCIA_PRESET = 0.02          # cuánto puede alejarse el deslizador de un preset para seguir llamándose así
LADO_MINIMO_PX = 90               # el búfer interno nunca baja de este alto (ni de la proporción equivalente)
PRESET_PERSONALIZADO = "personalizado"
PRESET_POR_DEFECTO = "nitido"

# (clave, nombre visible, divisor). El orden es el del selector. «Nítido» es el estado de siempre (nativa, sin pase).
PRESETS = (
    ("retro", "Retro", 4.0),
    ("nitido", "Nítido", 1.0),
    ("normal", "Normal", 2.0),
)


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
    return [(nombre, clave) for clave, nombre, _ in PRESETS] + [("Personalizado", PRESET_PERSONALIZADO)]


# Escala de un preset; None si es «personalizado» o desconocido (no impone ninguna).
def escala_de_preset(clave):
    for c, _, divisor in PRESETS:
        if c == clave:
            return escala_de_divisor(divisor)
    return None


# Preset cuyo valor coincide (con tolerancia) con `escala`, o «personalizado».
def preset_de_escala(escala):
    escala = _acotar(escala)
    for clave, _, divisor in PRESETS:
        if abs(escala - escala_de_divisor(divisor)) <= TOLERANCIA_PRESET:
            return clave
    return PRESET_PERSONALIZADO


# Mantiene coherentes el preset y la escala tras un cambio. `cambiadas` = claves de ajustes que cambiaron.
# Reglas: si cambió la escala, manda ella (el preset se deduce); si solo cambió el preset, su escala se impone
# (salvo «personalizado», que conserva la escala). Devuelve (preset, escala) ya coherentes.
def reconciliar(preset, escala, cambiadas):
    escala = _acotar(escala)
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


# Texto del deslizador: nativa o «Píxel x4,0».
def formato_pixel(escala):
    if es_nativa(escala):
        return "Nativa"
    return f"Píxel x{divisor_de_escala(escala):.1f}".replace(".", ",")
