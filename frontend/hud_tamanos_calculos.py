# Tamaños y contraste del HUD (M3.4). Python puro (sin ursina ni panda3d); tests en tests/test_hud_tamanos.py.
#
#   - Texto del HUD >= 18 px a 1080p (proporcional: >= 12 px a 720p). Los «px» del código son los de
#     componentes.a_unidades (alto de referencia 600) y el bloque puede estar escalado (ESCALA_HUD 0,9, minimapa 0,72):
#     a 1080p un texto mide px * escala * 1080 / 600.
#   - Contraste WCAG >= 4,5:1 entre cada texto del HUD y su fondo (3:1 solo para >= 24 px en negrita).
#   - Globos de los NPC y subtítulos de las cinemáticas más grandes y con fondo OPACO.
#
# Bandera reversible: HUD_TAMANOS / ALCALDE_HUD_TAMANOS=0 deja tamaños y colores como estaban.

import math
import os

from frontend import estilo

HUD_TAMANOS = True

ALTO_REFERENCIA_PX = 600
PX_MIN_1080 = 18
PX_NEGRITA_GRANDE_1080 = 24          # desde aquí, en negrita, basta 3:1
CONTRASTE_MIN = 4.5
CONTRASTE_MIN_GRANDE = 3.0

# Tamaños nuevos (px de referencia) de lo que crece con la bandera.
PX_NOMBRE_CINTA = 13                 # «Conviv.», «Confianza» bajo las pulseras (antes 11)
PX_ROTULO_MINIMAPA = 12              # base; se asegura con px_asegurado() según la escala del minimapa
ESCALA_GLOBO_NPC = 9.0               # globos de los NPC (antes 7.0; los carteles de nombre de los NPC clave son 8)
FACTOR_ESCALA_GLOBO = ESCALA_GLOBO_NPC / 7.0
FONDO_GLOBO_NPC = (250, 248, 238, 255)       # opaco (antes alfa 235)
PX_SUBTITULO = 24                    # texto del bocadillo de las cinemáticas (antes 22)
PX_SUBTITULO_BAJO_TITULO = 24        # texto bajo el título sobre negro (antes 22)


def activo():
    """¿Tamaños y contraste nuevos? ALCALDE_HUD_TAMANOS=1/0 manda sobre la constante HUD_TAMANOS."""
    valor = os.environ.get("ALCALDE_HUD_TAMANOS", "").strip().lower()
    if valor in ("1", "true", "si", "sí", "on"):
        return True
    if valor in ("0", "false", "no", "off"):
        return False
    return bool(HUD_TAMANOS)


# -- Tamaños --------------------------------------------------------------------------------------------------------

def px_en_pantalla(px_ref, escala=1.0, alto_px=1080):
    """Alto en px de pantalla (ventana de alto_px) de un texto de px_ref (referencia 600) en un bloque a `escala`."""
    return px_ref * escala * alto_px / ALTO_REFERENCIA_PX


def px_minimo_ref(escala=1.0, minimo_1080=PX_MIN_1080):
    """El menor px de referencia (entero) que a esa escala mide >= minimo_1080 px a 1080p."""
    return math.ceil(round(minimo_1080 * ALTO_REFERENCIA_PX / 1080 / escala, 6))


def px_asegurado(px_ref, escala=1.0):
    """px_ref, subido lo justo para cumplir el mínimo a esa escala."""
    return max(px_ref, px_minimo_ref(escala))


# Textos del HUD del mundo con la bandera: nombre -> (px de referencia, escala del bloque). Mismos números que usa cada
# módulo; el test comprueba que todos llegan a 18 px a 1080p.
ESCALA_HUD = 0.9
ESCALA_MINIMAPA = 0.9 * 0.8
TEXTOS_HUD = {
    "mision": (19, ESCALA_HUD),
    "lugar": (20, ESCALA_MINIMAPA),
    "rotulo_minimapa": (px_asegurado(PX_ROTULO_MINIMAPA, ESCALA_MINIMAPA), ESCALA_MINIMAPA),
    "toast": (16, ESCALA_HUD),
    "contador_telefono": (16, ESCALA_HUD),
    "aviso_e": (22, ESCALA_HUD),
    "aviso": (22 * 0.75, ESCALA_HUD),          # el genérico se encoge como mucho al 75 %
    "franja_titulo": (13, 1.0),
    "franja_numero": (15, 1.0),
    "franja_etapa": (14, 1.0),
    "franja_desinfo": (12, 1.0),
    "reloj": (17, 1.0),
    "dinero": (17, 1.0),
    "chip_dilema": (13, 1.0),
    "chip_habito": (13, 1.0),
    "pulseras_titulo": (13, 1.0),
    "pulseras_nombre": (PX_NOMBRE_CINTA, 1.0),
    "pulseras_tooltip": (12, 1.0),
    "tarjeta_remitente": (14, ESCALA_HUD),
    "tarjeta_texto": (13, ESCALA_HUD),
    "subtitulo": (PX_SUBTITULO, 1.0),
    "subtitulo_nombre": (17, 1.0),
}


# -- Contraste ------------------------------------------------------------------------------------------------------

def contraste_minimo(px_ref, escala=1.0, negrita=False):
    grande = px_en_pantalla(px_ref, escala) >= PX_NEGRITA_GRANDE_1080
    return CONTRASTE_MIN_GRANDE if (negrita and grande) else CONTRASTE_MIN


def tono_legible_claro(tono, fondo, minimo=CONTRASTE_MIN):
    """El mismo tono, ACLARADO hacia el blanco lo justo para llegar a `minimo` sobre un fondo oscuro (el
    estilo.tono_legible oscurece: sirve sobre papel)."""
    tono = tuple(int(v) for v in tono[:3])
    if estilo.contraste(tono, fondo) >= minimo:
        return tono
    for paso in range(1, 41):
        k = paso * 0.025
        candidato = tuple(min(255, int(round(v + (255 - v) * k))) for v in tono)
        if estilo.contraste(candidato, fondo) >= minimo:
            return candidato
    return (255, 255, 255)


# Rojo de error para TEXTO sobre los fondos oscuros del HUD (el de las barras, ESTADO_ERROR, se queda igual).
ESTADO_ERROR_TEXTO = tono_legible_claro(estilo.ESTADO_ERROR, estilo.COLOR_TARJETA)


def tono_texto(tono, fondo=estilo.COLOR_FONDO):
    """Color con el que pintar un texto de `tono` sobre `fondo` con la bandera (aclarado si no llega a 4,5)."""
    return tono_legible_claro(tono, fondo)


# Pares texto/fondo del HUD: (nombre, texto, fondo, px de referencia, escala, negrita). Con la bandera.
FONDOS_HUD = (estilo.COLOR_FONDO, estilo.COLOR_PANEL)
PARES_HUD = [
    ("texto_fondo", estilo.COLOR_TEXTO, estilo.COLOR_FONDO, 12, 1.0, False),
    ("texto_panel", estilo.COLOR_TEXTO, estilo.COLOR_PANEL, 12, 1.0, False),
    ("tenue_fondo", estilo.COLOR_TEXTO_TENUE, estilo.COLOR_FONDO, 13, 1.0, False),
    ("tenue_panel", estilo.COLOR_TEXTO_TENUE, estilo.COLOR_PANEL, 13, 1.0, False),
    ("destino_fondo", estilo.COLOR_DESTINO, estilo.COLOR_FONDO, 19, ESCALA_HUD, False),
    ("acento_fondo", estilo.COLOR_ACENTO, estilo.COLOR_FONDO, 13, 1.0, True),
    ("cian_fondo", estilo.ACENTO_SECUNDARIO, estilo.COLOR_FONDO, 13, 1.0, True),
    ("etapa_exito", estilo.ESTADO_EXITO, estilo.COLOR_FONDO, 14, 1.0, True),
    ("etapa_aviso", estilo.ESTADO_AVISO, estilo.COLOR_FONDO, 14, 1.0, True),
    ("etapa_error", tono_texto(estilo.ESTADO_ERROR), estilo.COLOR_FONDO, 14, 1.0, True),
    ("remitente_error", tono_texto(estilo.ESTADO_ERROR), estilo.COLOR_FONDO, 14, ESCALA_HUD, True),
    ("remitente_exito", tono_texto(estilo.ESTADO_EXITO), estilo.COLOR_FONDO, 14, ESCALA_HUD, True),
    ("remitente_aviso", tono_texto(estilo.ESTADO_AVISO), estilo.COLOR_FONDO, 14, ESCALA_HUD, True),
    ("remitente_info", tono_texto(estilo.ESTADO_INFO), estilo.COLOR_FONDO, 14, ESCALA_HUD, True),
    ("boton_secundario", estilo.COLOR_BOTON_TEXTO, estilo.COLOR_BOTON, 22, 1.0, False),
    ("boton_resaltado", estilo.COLOR_BOTON_TEXTO, estilo.COLOR_BOTON_RESALTADO, 22, 1.0, False),
    ("boton_primario", estilo.COLOR_ACENTO_TEXTO, estilo.COLOR_ACENTO, 22, 1.0, False),
    ("subtitulo", estilo.TINTA, estilo.PAPEL, PX_SUBTITULO, 1.0, False),
    ("subtitulo_nombre", estilo.TINTA, estilo.ACENTO_PRIMARIO, 17, 1.0, True),
    ("subtitulo_bajo_titulo", (236, 236, 240), (0, 0, 0), PX_SUBTITULO_BAJO_TITULO, 1.0, False),
    ("globo_npc", (28, 30, 40), FONDO_GLOBO_NPC[:3], 14, 1.0, False),
]
