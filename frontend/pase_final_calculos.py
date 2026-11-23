# Pase final único (T3 + M6): cálculos PUROS del post-proceso de pantalla completa que comparten el daltonismo, la TINTA de
# pantalla (contornos tipo cómic sacados de la profundidad) y el GRADING de salud (saturación + tinte según el Ambiente).
# Sin ursina ni panda3d: se prueba con pytest (tests/test_pase_final.py). El shader GLSL de frontend/daltonismo.py repite
# estas mismas fórmulas (linealizar, borde relativo, desvanecido); si se cambia una, cambiar la otra.
#
# Banderas (la variable de entorno manda sobre la constante):
#   TINTA_PANTALLA     / ALCALDE_TINTA_PANTALLA=0     sin tinta de pantalla (solo los contornos de casco de siempre)
#   SATURACION_SALUD   / ALCALDE_SATURACION_SALUD=0   sin grading de salud (ni saturación ni tinte)
# Con las dos apagadas el pase de pantalla es exactamente el de antes (sin FilterManager si no había daltonismo/pixelado).

import os

TINTA_PANTALLA = True
SATURACION_SALUD = True

# Ajuste del jugador «Tinta» (campo `tinta_pantalla` de backend/logica/ajustes.py): (texto, valor).
OPCIONES_TINTA = (("Contornos", "contornos"), ("Cómic", "comic"))

# --- Tinta -------------------------------------------------------------------------------------------------------------
COLOR_TINTA = (18 / 255.0, 20 / 255.0, 32 / 255.0)   # azul tinta casi negro
ALTO_REFERENCIA = 720.0          # a esta altura la línea mide 1 px; crece con la resolución
UMBRAL_BAJO = 0.25               # borde relativo (|Sobel(z)| / z) donde la línea empieza a aparecer...
UMBRAL_ALTO = 0.55               # ...y donde ya es tinta plena
FRACCION_CIELO = 0.6             # z >= 0,6 · far = cielo (la cúpula está a 0,8 · far): sin tinta
FIN_SIN_NIEBLA = 120.0           # m: rango del desvanecido cuando no hay niebla (interiores)
DESVANECE_INICIO = 0.30          # fracción del fin de niebla donde la tinta empieza a perder opacidad...
DESVANECE_FIN = 0.85             # ...y donde ya no se dibuja (lo lejano no se ensucia)
# Retoques M4 (rampas negras): la tinta de silueta solo se pinta donde hay SALTO de profundidad. En un plano 1/z es afín en
# pantalla: su segunda diferencia (relativa a 1/z del centro) es ~0 aunque el plano esté casi rasante, cuando |Sobel(z)|/z
# supera el umbral en cada píxel (con el trazo grueso, 3 px a 1080p) y una rampa que baja alejándose de la cámara se
# llenaba de negro. En un salto que ya pasaba el umbral del Sobel (|Δz|/z >= 0,0625) la segunda diferencia es >= 0,059,
# muy por encima de SALTO_ALTO: los contornos de siempre (personajes, casas, bordillos) quedan igual. Con 0,01-0,03 se perdía
# parte del contorno suave del borde de la plaza; con 0,0025-0,01 aparecían rayas de más (medido en el arnés).
SALTO_BAJO = 0.005
SALTO_ALTO = 0.02

# --- Grading de salud --------------------------------------------------------------------------------------------------
SATURACION_MIN = 0.72            # salud 0
SATURACION_MAX = 1.08            # salud 1
_SAT_LUZ_MIN, _SAT_LUZ_MAX = 0.55, 1.10      # rango de luz_ambiente(amb)["saturacion"]
PERIODO_UNIFORMES = 0.25         # s entre dos lecturas del Ambiente
NEUTRO = (1.0, (1.0, 1.0, 1.0))  # (saturación, tinte) fuera del mundo


def _bandera(nombre, constante, entorno=None):
    entorno = os.environ if entorno is None else entorno
    valor = str(entorno.get(nombre, "")).strip().lower()
    if valor in ("1", "true", "si", "sí", "on"):
        return True
    if valor in ("0", "false", "no", "off"):
        return False
    return bool(constante)


def tinta_activa(entorno=None):
    return _bandera("ALCALDE_TINTA_PANTALLA", TINTA_PANTALLA, entorno)


def saturacion_activa(entorno=None):
    return _bandera("ALCALDE_SATURACION_SALUD", SATURACION_SALUD, entorno)


# R2 (retoques): con la pausa (y sus Ajustes) abierta, el velo translúcido deja ver el mundo teñido y el menú entero
# «se ve tintado» aunque el UI no pase por el grading (medido: 0 % de píxeles distintos en el UI opaco). Con
# NEUTRO_EN_MENUS el pase va neutro (sin grading ni tinta) mientras haya un menú abierto. ALCALDE_PASE_NEUTRO_MENUS=0
# lo deja como antes.
NEUTRO_EN_MENUS = True


def neutro_en_menus_activo(entorno=None):
    return _bandera("ALCALDE_PASE_NEUTRO_MENUS", NEUTRO_EN_MENUS, entorno)


def interruptores_post(tinta, grading, con_profundidad, en_menu, neutro_menus=True):
    """(usar_tinta, usar_grading) del shader: lo pedido, salvo con un menú abierto y `neutro_menus` (todo apagado)."""
    if en_menu and neutro_menus:
        return 0.0, 0.0
    return (1.0 if (tinta and con_profundidad) else 0.0), (1.0 if grading else 0.0)


def tinta_en_pantalla(bandera, modo):
    """¿Se dibuja la tinta de pantalla? Hace falta la bandera Y el ajuste en «Cómic»."""
    return bool(bandera) and modo == "comic"


def opciones_selector():
    return list(OPCIONES_TINTA)


# --- Topología del pase ------------------------------------------------------------------------------------------------

def topologia(con_color, con_pixel, con_post):
    """Qué cadena de búferes hace falta:
      None      nada (sin FilterManager)
      "simple"  solo daltonismo: un búfer, la UI se re-apunta a él (lo de siempre)
      "post"    solo tinta/grading: un búfer, la UI se queda en la ventana (encima del cuadro: sin tinta ni grading)
      "etapa"   daltonismo + tinta/grading: mundo -> etapa nativa (tinta/grading + UI) -> ventana (matriz de color)
      "pixel"   pixelado (con o sin lo demás): mundo pequeño -> etapa nativa (+UI) -> ventana
    La UI nunca recibe tinta ni grading, pero sí el daltonismo."""
    if con_pixel:
        return "pixel"
    if con_color and con_post:
        return "etapa"
    if con_post:
        return "post"
    if con_color:
        return "simple"
    return None


# --- Tinta: fórmulas que repite el shader ------------------------------------------------------------------------------

def escala_texel(alto):
    """Ancho de la línea en texeles: 1 a 720 px de alto, proporcional por encima."""
    try:
        alto = float(alto)
    except (TypeError, ValueError):
        return 1.0
    if alto != alto:
        return 1.0
    return max(1.0, alto / ALTO_REFERENCIA)


def paso_texel(ancho, alto):
    """(du, dv) del vecino del Sobel en coordenadas de textura para un búfer de ancho x alto."""
    ancho, alto = max(1.0, float(ancho)), max(1.0, float(alto))
    k = escala_texel(alto)
    return (k / ancho, k / alto)


def linealizar(d, cerca, lejos, ortografica=False):
    """Profundidad de la textura (0..1, GL) -> distancia a la cámara en m."""
    if ortografica:
        return cerca + d * (lejos - cerca)
    return (cerca * lejos) / (lejos - d * (lejos - cerca))


def es_cielo(z, lejos):
    return z >= FRACCION_CIELO * lejos


def borde_relativo(vecinos):
    """|Sobel| / z del centro. `vecinos` = 3x3 de profundidades lineales, filas de arriba abajo."""
    (a, b, c), (d, e, f), (g, h, i) = vecinos
    gx = (c + 2 * f + i) - (a + 2 * d + g)
    gy = (g + 2 * h + i) - (a + 2 * b + c)
    return (gx * gx + gy * gy) ** 0.5 / max(e, 1e-6)


def _suave(a, b, x):
    t = min(1.0, max(0.0, (x - a) / (b - a)))
    return t * t * (3.0 - 2.0 * t)


def lado_cercano(vecinos):
    """1 si el centro es el lado CERCANO del borde (la línea va sobre el objeto de delante, 1 px), 0 si es el de atrás."""
    centro = vecinos[1][1]
    otros = [z for fila in vecinos for z in fila]
    return 1.0 if max(otros) - centro >= centro - min(otros) else 0.0


def salto_relativo(vecinos):
    """Mayor |2.ª diferencia de 1/z| / (1/z) del centro en las 4 direcciones del 3x3: ~0 en cualquier plano (también uno
    rasante), grande en un salto de profundidad o un pliegue."""
    (a, b, c), (d, e, f), (g, h, i) = vecinos
    w = lambda z: 1.0 / max(z, 1e-6)
    wc = w(e)
    s = max(abs(w(d) + w(f) - 2 * wc), abs(w(b) + w(h) - 2 * wc), abs(w(a) + w(i) - 2 * wc), abs(w(c) + w(g) - 2 * wc))
    return s / wc


def fuerza_tinta(vecinos, lejos):
    """Opacidad de la línea (0..1) antes del desvanecido por distancia. Solo donde hay salto (no en planos rasantes)."""
    if es_cielo(vecinos[1][1], lejos):
        return 0.0
    salto = _suave(SALTO_BAJO, SALTO_ALTO, salto_relativo(vecinos))
    return _suave(UMBRAL_BAJO, UMBRAL_ALTO, borde_relativo(vecinos)) * salto * lado_cercano(vecinos)


def niebla_de(fog_color, fog_density):
    """(rgb 0..1, fuerza 0..1, fin m) desde scene.fog_color (r, g, b, a) y scene.fog_density ((inicio, fin) o 0)."""
    try:
        r, g, b, a = (float(v) for v in tuple(fog_color)[:4])
    except (TypeError, ValueError):
        r = g = b = a = 0.0
    if isinstance(fog_density, (tuple, list)) and len(fog_density) >= 2:
        try:
            fin = float(fog_density[1])
        except (TypeError, ValueError):
            fin = 0.0
    else:
        fin, a = 0.0, 0.0
    if not fin > 0:
        return (r, g, b), 0.0, FIN_SIN_NIEBLA
    return (r, g, b), max(0.0, min(1.0, a)), fin


def desvanecido(z, fin, fuerza):
    """(opacidad, mezcla_niebla) de la tinta a `z` m: el color va hacia el de la niebla igual que el mundo, y la opacidad
    baja hasta 0 antes del fin de la niebla (lo lejano nunca queda sucio ni negro)."""
    fin = max(1.0, float(fin))
    mezcla = min(1.0, max(0.0, z / fin)) * fuerza
    opacidad = 1.0 - _suave(DESVANECE_INICIO * fin, DESVANECE_FIN * fin, z)
    return opacidad, mezcla


# --- Grading de salud --------------------------------------------------------------------------------------------------

def saturacion_de_salud(amb):
    """0,72 (salud 0) -> 1,08 (salud 1): mapa lineal de luz_ambiente(amb)["saturacion"] (0,55..1,10)."""
    from backend.logica import ambiente_ciudad as ac
    s = ac.luz_ambiente(amb)["saturacion"]
    t = min(1.0, max(0.0, (s - _SAT_LUZ_MIN) / (_SAT_LUZ_MAX - _SAT_LUZ_MIN)))
    return round(SATURACION_MIN + (SATURACION_MAX - SATURACION_MIN) * t, 4)


def uniformes_grading(amb, en_mundo, activo=True):
    """(saturación, tinte rgb) para el shader. Neutros (1, (1, 1, 1)) sin bandera, sin Ambiente o fuera del mundo."""
    if not activo or not en_mundo or amb is None:
        return NEUTRO
    from backend.logica import ciudad_viva_calculos as cv
    return saturacion_de_salud(amb), tuple(float(c) for c in cv.escala_color_mundo(amb))


def aplicar_grading(rgb, saturacion, tinte):
    """Lo que hace el shader con un píxel (0..1): saturación alrededor de la luma y luego el tinte multiplicativo."""
    y = 0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2]
    return tuple(min(1.0, max(0.0, (y + (rgb[i] - y) * saturacion) * tinte[i])) for i in range(3))


# --- R5 (retoques): tinta que se lea más a cómic ------------------------------------------------------------------------
# El verificador vio la tinta «parcial: líneas finas y suelos grandes sin tinta» y la sombra violeta «sutil de lejos».
#   TINTA_GRUESA      / ALCALDE_TINTA_GRUESA=0      el Sobel a 1 px a 720p (antes); con la bandera GROSOR_TINTA px
#   TINTA_PLIEGUES    / ALCALDE_TINTA_PLIEGUES=0    sin tinta de pliegues (antes). Con la bandera, el laplaciano de la
#       profundidad INVERSA (1/z es afín en pantalla sobre un plano: 0 en todo suelo plano, por grande que sea) entinta
#       bordillos, peldaños, losas con escalón y cambios de pendiente sin rayar el piso. Se desvanece como la otra tinta.
#   SOMBRA_LEJOS      / ALCALDE_SOMBRA_VIOLETA_LEJOS=0  como antes. Con la bandera, lo oscuro (sombras) gira hacia el
#       violeta de la sombra cel con la distancia, con la MISMA luma (no oscurece): de lejos la niebla ya no lo lava.
TINTA_GRUESA = True
TINTA_PLIEGUES = True
SOMBRA_LEJOS = False   # cierre (punto 1): apagada por defecto; ni con FUERZA_VIOLETA 0,6 el verificador vio efecto
GROSOR_TINTA = 2.0               # px a 720p con TINTA_GRUESA (crece con la resolución, como antes)
PLIEGUE_BAJO = 0.008             # |laplaciano(1/z)| / (1/z) donde empieza la línea de pliegue...
PLIEGUE_ALTO = 0.035             # ...y donde ya es plena
OPACIDAD_PLIEGUE = 0.8           # la de pliegue, algo más suave que la de silueta
VIOLETA_SOMBRA = (88 / 255.0, 78 / 255.0, 140 / 255.0)   # = luz_horneada_calculos.COLOR_SOMBRA_CEL
FUERZA_VIOLETA = 0.6             # mezcla máxima hacia el violeta (a la distancia del fin del desvanecido)
LUMA_SOMBRA = (0.15, 0.55)       # luma bajo la que un píxel cuenta como sombra (plena por debajo del primero)


def tinta_gruesa_activa(entorno=None):
    return _bandera("ALCALDE_TINTA_GRUESA", TINTA_GRUESA, entorno)


def pliegues_activos(entorno=None):
    return _bandera("ALCALDE_TINTA_PLIEGUES", TINTA_PLIEGUES, entorno)


def sombra_lejos_activa(entorno=None):
    return _bandera("ALCALDE_SOMBRA_VIOLETA_LEJOS", SOMBRA_LEJOS, entorno)


def grosor_tinta(gruesa):
    """Factor del paso del Sobel: GROSOR_TINTA con la bandera, 1 sin ella."""
    return GROSOR_TINTA if gruesa else 1.0


def paso_texel_con_grosor(ancho, alto, factor):
    """paso_texel multiplicado por `factor` (el grosor de la línea en px a 720p)."""
    du, dv = paso_texel(ancho, alto)
    return (du * factor, dv * factor)


def pliegue_relativo(vecinos):
    """|laplaciano de 1/z| / (1/z) del centro. `vecinos` = 3x3 de profundidades lineales (m). 0 en cualquier plano."""
    (_, b, _), (d, e, f), (_, h, _) = vecinos
    w = 1.0 / max(e, 1e-6)
    lap = (1.0 / max(b, 1e-6) + 1.0 / max(d, 1e-6) + 1.0 / max(f, 1e-6) + 1.0 / max(h, 1e-6)) - 4.0 * w
    return abs(lap) / w


def fuerza_pliegue(vecinos, lejos):
    if es_cielo(vecinos[1][1], lejos):
        return 0.0
    return OPACIDAD_PLIEGUE * _suave(PLIEGUE_BAJO, PLIEGUE_ALTO, pliegue_relativo(vecinos)) * lado_cercano(vecinos)


def violeta_lejos(rgb, z, fin, fuerza=FUERZA_VIOLETA):
    """Lo que hace el shader: un píxel oscuro (sombra) gira hacia VIOLETA_SOMBRA con la distancia, misma luma."""
    y = 0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2]
    yv = 0.2126 * VIOLETA_SOMBRA[0] + 0.7152 * VIOLETA_SOMBRA[1] + 0.0722 * VIOLETA_SOMBRA[2]
    objetivo = tuple(min(1.0, c * y / yv) for c in VIOLETA_SOMBRA)
    fin = max(1.0, float(fin))
    k = fuerza * (1.0 - _suave(LUMA_SOMBRA[0], LUMA_SOMBRA[1], y)) * _suave(0.05 * fin, DESVANECE_FIN * fin, z)
    return tuple(rgb[i] + (objetivo[i] - rgb[i]) * k for i in range(3))


def uniformes_r5(pliegues, sombra):
    """Entrada `extra` del shader: (pliegues 0/1, umbral bajo, umbral alto, fuerza del violeta lejano)."""
    return (1.0 if pliegues else 0.0, PLIEGUE_BAJO, PLIEGUE_ALTO, FUERZA_VIOLETA if sombra else 0.0)


# --- R2 (retoques, causa real): la niebla del mundo llegaba al UI ----------------------------------------------------------
# Las entidades del UI usan el shader por defecto de Ursina (unlit_with_fog_shader). ciudad_viva reparte fog_color/fog_end
# a TODAS las scene.entities (también las de camera.ui) y rendimiento.py da al UI la posición de la cámara del mundo: el UI
# se mezclaba con el color de la niebla según su «distancia» a esa cámara (~20 m), mucho más en «apagado» (niebla corta).
# Medido: botón «Reanudar» (255, 220, 60) -> (199, 190, 129) en apagado CON el pase apagado. Con UI_SIN_NIEBLA la raíz del
# UI fija fog_color con alfa 0 y prioridad alta (gana a lo que se ponga en cada entidad). ALCALDE_UI_SIN_NIEBLA=0 = antes.
UI_SIN_NIEBLA = True
PRIORIDAD_UI_SIN_NIEBLA = 1000
NIEBLA_NULA = (0.0, 0.0, 0.0, 0.0)


def ui_sin_niebla_activa(entorno=None):
    return _bandera("ALCALDE_UI_SIN_NIEBLA", UI_SIN_NIEBLA, entorno)


def mezcla_niebla(rgb, niebla_rgba, distancia, fin):
    """Lo que hace unlit_with_fog_shader con un píxel: mezcla hacia el color de la niebla t·alfa, t = distancia/fin."""
    t = min(1.0, max(0.0, distancia / max(1e-6, fin)))
    return tuple(rgb[i] + (niebla_rgba[i] - rgb[i]) * t * niebla_rgba[3] for i in range(3))


# --- Cierre (punto 5, ALCALDE_FUNDIDO_PAUSA): al cerrar la pausa con PASE_NEUTRO_MENUS el tinte y la tinta volvían DE GOLPE
# (los interruptores del shader son 0/1). Con la bandera, el shader mezcla lo procesado con el píxel sin procesar por
# `mezcla_post` (0..1) y al cerrar un menú esa mezcla sube de 0 a 1 en DURACION_FUNDIDO_PAUSA s (suave). Al abrir sigue
# siendo al instante (neutro en el mismo cuadro). La matriz de daltonismo va después: no se funde nunca. =0 como antes.
FUNDIDO_PAUSA = True
DURACION_FUNDIDO_PAUSA = 0.3


def fundido_pausa_activo(entorno=None):
    return _bandera("ALCALDE_FUNDIDO_PAUSA", FUNDIDO_PAUSA, entorno)


def mezcla_fundido(t, duracion=DURACION_FUNDIDO_PAUSA):
    """Mezcla del pase a los `t` s de cerrar el menú: 0 al cerrar, 1 a los `duracion` s (smoothstep: sin saltos)."""
    if duracion <= 0:
        return 1.0
    k = max(0.0, min(1.0, t / duracion))
    return k * k * (3.0 - 2.0 * k)


def aplicar_mezcla(original, procesado, mezcla):
    """Lo que hace el shader: mix(original, procesado, mezcla) por canal."""
    return tuple(o + (p - o) * mezcla for o, p in zip(original, procesado))
