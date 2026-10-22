# Cálculos puros (sin ursina/panda3d, con tests) del diseño adaptable de la interfaz.
#
# Problema de partida: la UI se diseñó para 16:9 (camera.ui: alto fijo = 1, ancho = aspecto,
# x en ±0.889). Ursina solo reubica en x los hijos DIRECTOS de camera.ui al cambiar la ventana y
# los paneles calcularon sus anclajes una sola vez con el aspecto de entonces. Al pasar a pantalla
# completa del Mac (16:10, aspecto 1.54), a 4:3 o a ultra ancho, lo anclado a los bordes queda
# fuera de la pantalla (texto cortado) o flotando hacia dentro, y lo diseñado a 16:9 se recorta.
#
# Reglas (todas puras, `frontend/diseno_adaptable.py` las aplica a las entidades):
#   - Aspecto: ancho/alto de la ventana en píxeles.
#   - Ajuste «caber»: factor de escala <= 1 que mete un contenido de 16:9 en una ventana más
#     estrecha (nunca agranda: en una ventana más ancha el contenido queda centrado a su tamaño).
#   - Borde: lo anclado a la izquierda/derecha se desplaza (aspecto - aspecto_base) / 2 hacia el borde.
#   - Texto en un ancho máximo: primero se encoge (hasta `escala_min`), luego se parte en líneas y
#     solo como último recurso se recorta con elipsis.

from frontend.texto import envolver_texto

ASPECTO_DISENO = 16 / 9          # aspecto de la ventana por defecto (1280 x 720)
FACTOR_MIN = 0.4                 # el ajuste «caber» nunca baja de aquí (ventanas absurdamente estrechas)
TOLERANCIA_ASPECTO = 0.002       # cambios menores que esto no se consideran un cambio de tamaño
ELIPSIS = "…"

LADOS = ("izquierda", "derecha", "centro")


# Aspecto (ancho/alto) de una ventana de `ancho_px` x `alto_px`. Si algún lado no es positivo
# devuelve `por_defecto` (ventana minimizada o aún sin abrir).
def aspecto_de(ancho_px, alto_px, por_defecto=ASPECTO_DISENO):
    try:
        if ancho_px <= 0 or alto_px <= 0:
            return por_defecto
        return ancho_px / alto_px
    except TypeError:
        return por_defecto


# ¿Cambió el aspecto lo bastante como para reubicar la interfaz?
def aspecto_cambio(anterior, nuevo, tolerancia=TOLERANCIA_ASPECTO):
    if anterior is None:
        return True
    return abs(nuevo - anterior) > tolerancia


# Mitad del ancho de camera.ui para un aspecto (el alto siempre va de -0.5 a 0.5).
def semiancho(aspecto):
    return aspecto / 2


# Factor (0 < f <= 1) que reduce un contenido diseñado a `aspecto_diseno` para que quepa a lo
# ancho en una ventana de `aspecto`. En ventanas más anchas que el diseño vale 1.
def factor_ajuste(aspecto, aspecto_diseno=ASPECTO_DISENO, minimo=FACTOR_MIN):
    if aspecto <= 0 or aspecto_diseno <= 0:
        return 1.0
    return max(minimo, min(1.0, aspecto / aspecto_diseno))


# Desplazamiento en x de algo anclado a un borde cuando la ventana pasa de `aspecto_base` a
# `aspecto`: la izquierda se mueve -(delta)/2, la derecha +(delta)/2 y el centro no se mueve.
def desplazamiento_borde(lado, aspecto, aspecto_base):
    if lado not in LADOS:
        raise ValueError(f"lado desconocido: {lado!r} (use {LADOS})")
    delta = (aspecto - aspecto_base) / 2
    if lado == "izquierda":
        return -delta
    if lado == "derecha":
        return delta
    return 0.0


# Factor de escala para que algo de `ancho` unidades quepa en `ancho_max` (<= 1; nunca agranda).
def factor_para_ancho(ancho, ancho_max, minimo=FACTOR_MIN):
    if ancho <= 0 or ancho_max <= 0 or ancho <= ancho_max:
        return 1.0
    return max(minimo, ancho_max / ancho)


# Recorta `texto` con elipsis hasta que `medir(texto) <= ancho_max`. Si ni la elipsis cabe devuelve "".
def recortar_con_elipsis(texto, medir, ancho_max):
    if medir(texto) <= ancho_max:
        return texto
    if medir(ELIPSIS) > ancho_max:
        return ""
    resto = texto.rstrip()
    while resto and medir(resto + ELIPSIS) > ancho_max:
        resto = resto[:-1].rstrip()
    return resto + ELIPSIS


# Plan para pintar `texto` dentro de `ancho_max` (mismas unidades que devuelve `medir`, medido a escala 1):
#   {"escala": f, "lineas": [...], "recortado": bool}
# 1) si cabe en una línea: escala 1.
# 2) si encogiéndolo hasta `escala_min` cabe en una línea: esa escala.
# 3) si no, a `escala_min` se parte en líneas (envolver_texto); con `max_lineas` el excedente se
#    recorta con elipsis en la última línea (único caso con `recortado=True`).
def plan_texto_en_ancho(texto, medir, ancho_max, escala_min=0.7, max_lineas=None):
    texto = " ".join(str(texto).split())
    if ancho_max <= 0:
        return {"escala": escala_min, "lineas": [texto] if texto else [], "recortado": False}
    if not texto:
        return {"escala": 1.0, "lineas": [], "recortado": False}
    ancho = medir(texto)
    if ancho <= ancho_max:
        return {"escala": 1.0, "lineas": [texto], "recortado": False}
    if ancho * escala_min <= ancho_max:
        return {"escala": ancho_max / ancho, "lineas": [texto], "recortado": False}
    # A la escala mínima el ancho disponible, medido a escala 1, es ancho_max / escala_min.
    disponible = ancho_max / escala_min
    lineas = envolver_texto(texto, medir, disponible)
    recortado = False
    if max_lineas is not None and len(lineas) > max_lineas:
        recortado = True
        # La última línea conserva el resto del texto, recortado con elipsis.
        resto = " ".join(lineas[max_lineas - 1:])
        lineas = lineas[:max_lineas - 1] + [recortar_con_elipsis(resto, medir, disponible)]
    return {"escala": escala_min, "lineas": lineas, "recortado": recortado}
