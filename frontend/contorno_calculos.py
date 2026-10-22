# Cálculos puros del contorno de tinta (casco invertido) y del realce de color de los personajes
# (NO importa ursina ni panda3d).
#
# Contorno: cada pieza del muñeco procedural se duplica un poco más grande, de color tinta y dibujada solo por
# sus caras traseras (sin shader): se ve únicamente el borde que sobresale, como el trazo grueso de un cómic.
# Como cada pieza se infla por su cuenta, el grosor es uniforme (cubos y esferas) y sigue la animación porque
# el casco cuelga del mismo pivote.

import colorsys
import math

from frontend import estilo

TINTA = estilo.TINTA                       # (18, 20, 32)
GROSOR_CUERPO = 0.018                      # m por cada lado: se lee a 8 m (≈ 2.7 px con FOV 65 y 720 px de alto)
GROSOR_DETALLE = 0.010                     # m: piezas pequeñas (zapatos, hebilla)
PIEZA_MINIMA = 0.06                        # m: bajo este tamaño usa el grosor fino
FOV_JUEGO = 65.0                           # grados (horizontal, como Ursina)
ANCHO_PANTALLA_REF = 1280                  # px de la captura de referencia


def inflar_escala(escala, grosor):
    # Escala (número o tupla) de una pieza inflada `grosor` por cada lado: se suma 2*grosor a cada medida.
    if isinstance(escala, (int, float)):
        return float(escala) + 2.0 * grosor
    return tuple(float(e) + 2.0 * grosor for e in escala)


def grosor_para(escala):
    # Grosor del casco según el tamaño de la pieza: las diminutas llevan un trazo más fino.
    dimensiones = (escala,) if isinstance(escala, (int, float)) else tuple(escala)
    return GROSOR_DETALLE if min(dimensiones) < PIEZA_MINIMA else GROSOR_CUERPO


def especificacion_contorno(especificacion, grosor=None):
    # Datos ({model, color, position, scale}, el formato de piezas.malla_unida) del casco de una pieza: la misma
    # pieza inflada y de color tinta. No modifica la original; devuelve ValueError si no trae escala ni forma.
    if "model" not in especificacion or "scale" not in especificacion:
        raise ValueError("la pieza necesita 'model' y 'scale'")
    g = grosor_para(especificacion["scale"]) if grosor is None else grosor
    datos = dict(especificacion)
    datos["scale"] = inflar_escala(especificacion["scale"], g)
    datos["color"] = TINTA
    return datos


def pixeles_contorno(grosor, distancia, ancho_px=ANCHO_PANTALLA_REF, fov_grados=FOV_JUEGO):
    # Grosor aparente del contorno en píxeles a `distancia` metros (FOV horizontal). Sirve para comprobar que a
    # 5-10 m el trazo aún se lee (≥ 2 px).
    if distancia <= 0:
        return math.inf
    ancho_mundo = 2.0 * distancia * math.tan(math.radians(fov_grados) / 2.0)
    return grosor * ancho_px / ancho_mundo


def realzar_color(color_rgb, saturacion=1.18, contraste=1.06):
    # Más saturación y algo de contraste en un color RGB 0-255 (tuplas de 3 enteros): ropa más viva, estilo cómic.
    r, g, b = (c / 255.0 for c in color_rgb[:3])
    h, s, v = colorsys.rgb_to_hsv(r, g, b)
    s = min(1.0, s * saturacion)
    v = min(1.0, max(0.0, (v - 0.5) * contraste + 0.5))
    r, g, b = colorsys.hsv_to_rgb(h, s, v)
    return (round(r * 255), round(g * 255), round(b * 255))
