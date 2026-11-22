# T2 del bloque T (ALCALDE_CASCO_PANTALLA): casco de tinta con grosor ~constante EN PANTALLA. Puro: sin ursina ni panda3d.
#
# Hoy el casco se infla un grosor fijo en metros (tinta_calculos.grosor, T1), así que la línea mide ≈ 1005·g/d px: gruesa
# de cerca y casi nula de lejos. Con la bandera, un vertex shader (frontend/casco_pantalla.py) mueve cada vértice del casco
# a lo largo de su normal suavizada lo justo para que el borde mida PX_720 px a 720 px de alto (escalado con la resolución:
# 3 px a 720p, 4,5 px a 1080p), acotado entre MINIMO y MAXIMO veces el grosor T1 para que ni de cerca ni de lejos se rompa.
#
# Fórmula (perspectiva; con cámara ortográfica w = 1 y sale igual de bien):
#   metros por px a profundidad w = 2·w / (alto_px · ky),  ky = 1 / tan(fov_vertical / 2)  (fila «y» de la proyección)
#   objetivo = PX_720·(alto_px/720) · 2·w / (alto_px · ky) = 2·PX_720·w / (720·ky)          (no depende del alto_px)
#   grosor   = clamp(objetivo, MINIMO·g, MAXIMO·g)
# El casco ya viene inflado g (en la CPU, como siempre); el shader solo añade (grosor - g) por la normal. Si el shader no
# compila, el casco queda exactamente como antes.
#
# Familias: solo los NPC nuevos (casco de vértices inflados por normal, dibujado con el shader de skinning del cuerpo).
# Piezas procedurales, rostro y vehículos quedan fuera (ver motivo en FAMILIAS_FUERA).
import math
import os

CASCO_PANTALLA = True            # ALCALDE_CASCO_PANTALLA=0/false/no/off: todo exactamente como antes
PX_720 = 3.0                     # px del borde a 720 px de alto (se escala con la resolución)
ALTO_REF = 720
MINIMO = 0.4                     # × grosor T1: de cerca no más fino que esto
MAXIMO = 2.0                     # × grosor T1: de lejos no más grueso que esto
FOV_HORIZONTAL = 65.0            # el del juego (contorno_calculos.FOV_JUEGO)
ASPECTO_REF = 1280 / 720

FAMILIAS = ("npc_nuevos",)
FAMILIAS_FUERA = {
    "personaje": "casco = copia escalada de cubos/esferas unida con combine() de Ursina: sin normales ni dirección de empuje",
    "rostro": "mismas mallas combine() sin normales que las piezas procedurales",
    "vehiculo": "triángulos sueltos por pieza sin normales; haría falta hornear la dirección de empuje al construir",
    "casa": "excluida por diseño (copia escalada)",
}


def activa():
    valor = os.environ.get("ALCALDE_CASCO_PANTALLA", "").strip().lower()
    if valor in ("1", "true", "si", "sí", "on"):
        return True
    if valor in ("0", "false", "no", "off"):
        return False
    return bool(CASCO_PANTALLA)


def px_objetivo(alto_px):
    """px del borde a esa altura de ventana (PX_720 a 720 px, proporcional)."""
    return PX_720 * alto_px / ALTO_REF


def ky_de_fov(fov_horizontal=FOV_HORIZONTAL, aspecto=ASPECTO_REF):
    """1 / tan(fov_vertical / 2) de una lente con ese FOV horizontal y aspecto (lo que el shader lee de la proyección)."""
    return aspecto / math.tan(math.radians(fov_horizontal) / 2.0)


def limites(grosor_t1):
    """(mínimo, máximo) en m del grosor del casco."""
    return MINIMO * grosor_t1, MAXIMO * grosor_t1


def grosor_pantalla(distancia, grosor_t1, ky=None):
    """m que asoma el casco a esa profundidad (referencia en Python del vertex shader)."""
    ky = ky_de_fov() if ky is None else ky
    objetivo = 2.0 * PX_720 * distancia / (ALTO_REF * ky)
    minimo, maximo = limites(grosor_t1)
    return min(max(objetivo, minimo), maximo)


def empuje(distancia, grosor_t1, ky=None):
    """m que el shader añade por la normal al casco ya inflado grosor_t1 en la CPU (negativo = más fino)."""
    return grosor_pantalla(distancia, grosor_t1, ky) - grosor_t1


def pixeles(grosor, distancia, alto_px=ALTO_REF, ky=None):
    """px que mide un borde de `grosor` m a `distancia` m con una ventana de `alto_px` de alto."""
    ky = ky_de_fov() if ky is None else ky
    if distancia <= 0:
        return math.inf
    return grosor * alto_px * ky / (2.0 * distancia)


def parametros(grosor_modelo):
    """vec4 del uniform casco_pantalla: (px a 720, mínimo ×, máximo ×, grosor horneado en unidades del modelo)."""
    return (PX_720, MINIMO, MAXIMO, float(grosor_modelo))
