# Mapa de esquinas del HUD del mundo (M3.1, diagnóstico D5): como mucho UN bloque por esquina y UNA franja arriba
# al centro, con el mismo margen de seguridad y la misma escala de separaciones para todos. Python puro (sin ursina
# ni panda3d): lo usan frontend/hud.py, etapas_final_vista.py, registro_reloj.py, economia_mundo.py,
# registro_dilemas.py, registro_habitos.py y registro_manillas.py, y se prueba sin ventana (tests/test_hud_esquinas.py).
#
#   arriba-izquierda   misión actual en UNA línea («Misión: <título> · <rol>»; con varios jugadores, «· <nombre> · <rol>»)
#   arriba-centro      franja única: confianza de Ciudad Nova + desinformación
#   arriba-derecha     minimapa al 80 % del tamaño de antes + el chip del lugar debajo
#   abajo-izquierda    pila de chips: dinero, reloj (y los chips de dilemas/hábitos si salen)
#   abajo-derecha      botón del teléfono
#   izquierda-medio    pulseras (las vuelve contextuales el módulo siguiente; aquí solo se alinean al margen)
#
# Unidades: las de camera.ui (alto de la ventana = 1; x en [-aspecto/2, aspecto/2]). Como Ursina escala camera.ui con
# el alto de la ventana, un margen de 32 px a 1080p son 32/1080 unidades, y a 720p queda proporcional (~21 px).
#
# Bandera reversible: HUD_ESQUINAS / ALCALDE_HUD_ESQUINAS=0 deja el HUD exactamente como estaba.

import os
import re
from dataclasses import dataclass

from frontend import panel_unico_calculos
from frontend.reloj_constantes import ALTO_CHIP, ANCHO_CHIP

HUD_ESQUINAS = True                  # bandera (ALCALDE_HUD_ESQUINAS=1/0 manda sobre la constante)

ALTO_DISENO_PX = 1080
MARGEN = 32 / ALTO_DISENO_PX         # margen de seguridad a los bordes (32 px a 1080p)
PASO = 8 / ALTO_DISENO_PX            # escala de separaciones: múltiplos de 8 px a 1080p
ALTO_REFERENCIA_PX = 600             # = componentes.ALTO_REFERENCIA_PX (px de las fuentes -> unidades)

ESCALA_HUD = 0.9                     # = hud.ESCALA_HUD
ESCALA_MINIMAPA = 0.8                # el minimapa queda al 80 % de lo que medía

# Panel de misión (una línea). Medidas locales (antes de ESCALA_HUD).
PX_MISION = 19
RELLENO_MISION = 0.014
ESCALA_MIN_MISION = 0.85             # se encoge hasta aquí; si ni así cabe, el título se recorta con elipsis

# Minimapa: medidas locales de hud.Minimapa y del chip del lugar bajo él.
ANCHO_MINIMAPA_LOCAL, ALTO_MINIMAPA_LOCAL = 280 / 720, 200 / 720
PX_ETIQUETA_LUGAR = 20               # local: a ESCALA_HUD * ESCALA_MINIMAPA se lee como ~14 px
ALTO_ETIQUETA_FACTOR = 1.5           # alto del chip = px * 1.5

# Franja de arriba al centro (medidas de etapas_final_vista: ANCHO_MEDIDOR, ALTO_MEDIDOR; la fila de desinformación
# entra en el MISMO fondo, sin panel propio).
ANCHO_FRANJA = 0.60
ALTO_FILA_CONFIANZA = 0.088
ALTO_FILA_DESINFO = 0.040

# Teléfono (hud.TelefonoUI): icono local + la insignia roja que asoma arriba a la izquierda.
ANCHO_ICONO_TEL, ALTO_ICONO_TEL = 0.075, 0.12
INSIGNIA_ASOMA = 0.012               # local: la insignia sobresale del icono por arriba y por la izquierda

# Pulseras (registro_manillas): chip a media altura a la izquierda.
Y_CENTRO_PULSERAS = -0.07
TAMANO_PULSERAS = {2: (0.215, 0.226), 5: (0.355, 0.2)}
# Chip de la recta final (recta_final_vista.CHIP, tamaño (0.42, 0.05)): fijo, bajo el panel de misión.
CHIP_RECTA_FINAL = (-0.64, 0.33, 0.42, 0.05)

PILA_MAX = 4                         # chips abajo a la izquierda: dinero, reloj, dilema, hábito


def activo():
    """¿Mapa de esquinas? ALCALDE_HUD_ESQUINAS=1/0 manda sobre la constante HUD_ESQUINAS."""
    valor = os.environ.get("ALCALDE_HUD_ESQUINAS", "").strip().lower()
    if valor in ("1", "true", "si", "sí", "on"):
        return True
    if valor in ("0", "false", "no", "off"):
        return False
    return bool(HUD_ESQUINAS)


def a_unidades(px):
    return px / ALTO_REFERENCIA_PX


@dataclass(frozen=True)
class Rect:
    """Rectángulo en unidades de camera.ui (y hacia arriba)."""
    x0: float
    y0: float
    x1: float
    y1: float

    @property
    def ancho(self):
        return self.x1 - self.x0

    @property
    def alto(self):
        return self.y1 - self.y0

    @property
    def centro(self):
        return ((self.x0 + self.x1) / 2, (self.y0 + self.y1) / 2)

    def se_solapa(self, otro, holgura=0.0):
        """True si se tocan con menos de `holgura` de aire entre ellos."""
        return not (self.x1 + holgura <= otro.x0 or otro.x1 + holgura <= self.x0
                    or self.y1 + holgura <= otro.y0 or otro.y1 + holgura <= self.y0)

    def dentro_de(self, otro):
        eps = 1e-9
        return (self.x0 >= otro.x0 - eps and self.x1 <= otro.x1 + eps
                and self.y0 >= otro.y0 - eps and self.y1 <= otro.y1 + eps)

    def a_px(self, ancho_px, alto_px):
        """(x, y, ancho, alto) en píxeles de la ventana, origen arriba a la izquierda."""
        k = alto_px
        aspecto = ancho_px / alto_px
        return ((self.x0 + aspecto / 2) * k, (0.5 - self.y1) * k, self.ancho * k, self.alto * k)


def _rect_centro(cx, cy, ancho, alto):
    return Rect(cx - ancho / 2, cy - alto / 2, cx + ancho / 2, cy + alto / 2)


def factor_ajuste(aspecto, aspecto_diseno=16 / 9, minimo=0.4):
    """Mismo «caber» que diseno_adaptable_calculos.factor_ajuste (la franja lo usa al estrecharse la ventana)."""
    if aspecto <= 0:
        return 1.0
    return max(minimo, min(1.0, aspecto / aspecto_diseno))


# -- Medidas de cada bloque (pantalla, ya con sus escalas) ----------------------------------------------------------

def relleno_mision():
    """Relleno del panel de misión: el de la categoría «chip» con el estilo único (M3.3), si no el de antes."""
    return panel_unico_calculos.relleno("mision") if panel_unico_calculos.activo() else RELLENO_MISION


def alto_mision():
    return (a_unidades(PX_MISION) * 1.2 + 2 * relleno_mision()) * ESCALA_HUD


def escala_minimapa():
    return ESCALA_HUD * ESCALA_MINIMAPA


def medidas_minimapa():
    k = escala_minimapa()
    return ANCHO_MINIMAPA_LOCAL * k, ALTO_MINIMAPA_LOCAL * k


def hueco_etiqueta_local():
    """Hueco (local del minimapa) entre el mapa y el chip del lugar: un PASO en pantalla. Con el estilo único (M3.3)
    se suma lo que sobresalen la sombra del marco y el borde del chip, para que el aire visible siga siendo un PASO."""
    extra = 0.0
    if panel_unico_calculos.activo():
        extra = (panel_unico_calculos.extension_px("minimapa")["abajo"]
                 + panel_unico_calculos.extension_px("lugar")["arriba"]) / ALTO_REFERENCIA_PX
    return PASO / escala_minimapa() + extra


def alto_etiqueta_lugar():
    return a_unidades(PX_ETIQUETA_LUGAR) * ALTO_ETIQUETA_FACTOR * escala_minimapa()


def alto_franja(con_desinfo=True):
    return ALTO_FILA_CONFIANZA + (ALTO_FILA_DESINFO if con_desinfo else 0.0)


def medidas_telefono():
    return (ANCHO_ICONO_TEL + INSIGNIA_ASOMA) * ESCALA_HUD, (ALTO_ICONO_TEL + INSIGNIA_ASOMA) * ESCALA_HUD


# -- Posiciones -----------------------------------------------------------------------------------------------------

def y_franja(aspecto, con_desinfo=True):
    """y del centro de la FILA de confianza (origen del Medidor) para que la franja toque el margen de arriba.
    El Medidor se escala con factor_ajuste alrededor de ese origen."""
    f = factor_ajuste(aspecto)
    return 0.5 - MARGEN - f * ALTO_FILA_CONFIANZA / 2


def centro_minimapa(aspecto):
    ancho, alto = medidas_minimapa()
    return aspecto / 2 - MARGEN - ancho / 2, 0.5 - MARGEN - alto / 2


def origen_mision(aspecto):
    """Esquina superior izquierda del panel de misión (su origen)."""
    return -aspecto / 2 + MARGEN, 0.5 - MARGEN


def desplazamiento_telefono(aspecto_construccion, aspecto, margen_viejo):
    """(x, y) de TelefonoUI para que su icono quede en la esquina inferior derecha con MARGEN.

    TelefonoUI coloca sus hijos en coordenadas locales con x_derecho = aspecto_construccion/2 - margen_viejo e
    y_inferior = -0.5 + margen_viejo, y se escala ESCALA_HUD respecto a su origen."""
    x_derecho = aspecto_construccion / 2 - margen_viejo
    y_inferior = -0.5 + margen_viejo
    return (aspecto / 2 - MARGEN - ESCALA_HUD * x_derecho, -0.5 + MARGEN - ESCALA_HUD * y_inferior)


def centro_chip_pila(aspecto, indice, ancho=ANCHO_CHIP, alto=ALTO_CHIP):
    """Centro del chip `indice` (0 = el de abajo) de la pila de abajo a la izquierda, alineada a la izquierda."""
    return (-aspecto / 2 + MARGEN + ancho / 2, -0.5 + MARGEN + alto / 2 + indice * (alto + PASO))


def x_pulseras(aspecto, ancho):
    return -aspecto / 2 + MARGEN + ancho / 2


# -- Pulseras visibles (M5.1, ALCALDE_PULSERAS_VISIBLES): las 2 cintas en miniatura pegadas a la DERECHA del chip del
# reloj, en la misma fila de la pila de abajo a la izquierda (no es un bloque de esquina nuevo). Un chip del mismo alto
# que el del reloj, a un PASO de él; dentro, por cada cinta un hueco [cinta | flecha de tendencia].

ALTO_DISENO_MINI_PX = 720
ALTO_MINI_CINTA = 28 / ALTO_DISENO_MINI_PX            # ~28 px de alto a 720p (42 a 1080p: camera.ui escala con el alto)
ANCHO_MINI_CINTA = ALTO_MINI_CINTA * 0.5              # algo más ancha que la textura (64 x 160): en pequeño se lee mejor
LADO_FLECHA_MINI = 10 / ALTO_DISENO_MINI_PX
HUECO_FLECHA_MINI = 3 / ALTO_DISENO_MINI_PX            # aire entre la cinta y su flecha
RELLENO_MINI = 8 / ALTO_DISENO_MINI_PX                 # relleno lateral del chip y separación entre huecos


def ancho_mini_pulseras(n=2):
    hueco = ANCHO_MINI_CINTA + HUECO_FLECHA_MINI + LADO_FLECHA_MINI
    return 2 * RELLENO_MINI + n * hueco + (n - 1) * RELLENO_MINI


def centro_mini_pulseras_junto_a(cx_reloj, cy_reloj, n=2, ancho_reloj=ANCHO_CHIP):
    """Centro del chip de las mini-pulseras dado el centro del chip del reloj (pegado a su derecha, un PASO de aire)."""
    return cx_reloj + ancho_reloj / 2 + PASO + ancho_mini_pulseras(n) / 2, cy_reloj


def rect_mini_pulseras(aspecto, indice_reloj, n=2):
    """Rect del chip de las mini-pulseras con el reloj en el puesto `indice_reloj` de la pila (0 sin dinero, 1 con él)."""
    cx, cy = centro_mini_pulseras_junto_a(*centro_chip_pila(aspecto, indice_reloj), n=n)
    return _rect_centro(cx, cy, ancho_mini_pulseras(n), ALTO_CHIP)


def piezas_mini_pulseras(n=2):
    """[(x_cinta, x_flecha)] locales (respecto al centro del chip) de cada hueco, de izquierda a derecha; y = 0."""
    ancho = ancho_mini_pulseras(n)
    hueco = ANCHO_MINI_CINTA + HUECO_FLECHA_MINI + LADO_FLECHA_MINI
    salida = []
    for k in range(n):
        x0 = -ancho / 2 + RELLENO_MINI + k * (hueco + RELLENO_MINI)
        salida.append((x0 + ANCHO_MINI_CINTA / 2, x0 + ANCHO_MINI_CINTA + HUECO_FLECHA_MINI + LADO_FLECHA_MINI / 2))
    return salida


# -- Mapa completo --------------------------------------------------------------------------------------------------

def layout_esquinas(ancho_px, alto_px, con_desinfo=True, chips_pila=PILA_MAX, pulseras=2, mini_pulseras=None):
    """Rectángulos (unidades de camera.ui) de cada bloque del HUD para una ventana de ancho_px x alto_px.

    "mision" es el ancho MÁXIMO que puede ocupar el panel de misión (hasta la franja, con 2 pasos de aire).
    `mini_pulseras`: puesto del reloj en la pila (0 o 1) para añadir "mini_pulseras" (M5.1); None = no se añade."""
    aspecto = ancho_px / alto_px
    f = factor_ajuste(aspecto)
    r = {}
    top = 0.5 - MARGEN
    ancho_f, alto_f = ANCHO_FRANJA * f, alto_franja(con_desinfo) * f
    r["franja"] = Rect(-ancho_f / 2, top - alto_f, ancho_f / 2, top)
    ancho_m, alto_m = medidas_minimapa()
    cx, cy = centro_minimapa(aspecto)
    r["minimapa"] = _rect_centro(cx, cy, ancho_m, alto_m)
    y_lugar = r["minimapa"].y0 - hueco_etiqueta_local() * escala_minimapa()
    r["lugar"] = Rect(r["minimapa"].x0, y_lugar - alto_etiqueta_lugar(), r["minimapa"].x1, y_lugar)
    x0, _ = origen_mision(aspecto)
    r["mision"] = Rect(x0, top - alto_mision(), r["franja"].x0 - 2 * PASO, top)
    ancho_t, alto_t = medidas_telefono()
    r["telefono"] = Rect(aspecto / 2 - MARGEN - ancho_t, -0.5 + MARGEN, aspecto / 2 - MARGEN, -0.5 + MARGEN + alto_t)
    for k in range(chips_pila):
        r[f"pila{k}"] = _rect_centro(*centro_chip_pila(aspecto, k), ANCHO_CHIP, ALTO_CHIP)
    ancho_p, alto_p = TAMANO_PULSERAS[pulseras]
    r["pulseras"] = _rect_centro(x_pulseras(aspecto, ancho_p), Y_CENTRO_PULSERAS, ancho_p, alto_p)
    cx, cy, ancho_c, alto_c = CHIP_RECTA_FINAL
    r["recta_final"] = _rect_centro(cx, cy, ancho_c, alto_c)
    if mini_pulseras is not None:
        r["mini_pulseras"] = rect_mini_pulseras(aspecto, mini_pulseras)
    return r


def zona_segura(ancho_px, alto_px):
    aspecto = ancho_px / alto_px
    return Rect(-aspecto / 2 + MARGEN, -0.5 + MARGEN, aspecto / 2 - MARGEN, 0.5 - MARGEN)


def solapes(rects, holgura=0.0):
    """Pares (a, b) de bloques que se solapan (o quedan a menos de `holgura`)."""
    nombres = sorted(rects)
    return [(a, b) for i, a in enumerate(nombres) for b in nombres[i + 1:] if rects[a].se_solapa(rects[b], holgura)]


# -- Texto de la línea de misión ------------------------------------------------------------------------------------

_TURNO_LOCAL = re.compile(r"^Turno de (?P<nombre>.+) \((?P<rol>[^()]+)\)$")
_TURNO_ONLINE = re.compile(r"^(?P<nombre>.+) \((?P<rol>[^()]+)\)(?: · .*)?$")
SEPARADOR = " · "


def quien_juega(turno, varios_jugadores):
    """Lo corto que va tras el título: el rol (un jugador / en línea) o «nombre · rol» (hot-seat con varios)."""
    turno = " ".join(str(turno or "").split())
    m = _TURNO_LOCAL.match(turno)
    if m:
        return f"{m['nombre']}{SEPARADOR}{m['rol']}" if varios_jugadores else m["rol"]
    m = _TURNO_ONLINE.match(turno)
    if m:
        return m["rol"]
    return turno


def sufijo_mision(turno, varios_jugadores):
    quien = quien_juega(turno, varios_jugadores)
    return f"{SEPARADOR}{quien}" if quien else ""


_GLOSA_FINAL = re.compile(r"\s+\([^()]*\)\s*$")


def quitar_glosa(titulo):
    """Quita la glosa final entre paréntesis (la que añade glosar_texto); si no queda nada, deja el título igual."""
    corto = _GLOSA_FINAL.sub("", titulo)
    return corto if corto.strip() else titulo


def plan_linea_mision(cabeza, titulo, sufijo, medir, ancho_max, escala_min=ESCALA_MIN_MISION, elipsis="…"):
    """Cómo cabe «<cabeza><titulo><sufijo>» en una línea de `ancho_max` (medido a escala 1).

    Devuelve (escala, titulo): escala 1 si cabe; si encogiendo hasta escala_min cabe, esa escala; si no, escala_min y el
    título recortado con elipsis (cabeza y sufijo — «Misión:» y quién juega — no se recortan nunca). Antes de recortar
    se prueba sin la glosa final entre paréntesis («Concierto en la Praça (Plaza)» -> «Concierto en la Praça»)."""
    total = medir(cabeza + titulo + sufijo)
    if ancho_max <= 0 or total <= ancho_max:
        return 1.0, titulo
    if total * escala_min <= ancho_max:
        return ancho_max / total, titulo
    sin_glosa = quitar_glosa(titulo)
    if sin_glosa != titulo:
        return plan_linea_mision(cabeza, sin_glosa, sufijo, medir, ancho_max, escala_min, elipsis)
    disponible = ancho_max / escala_min
    recorte = titulo.rstrip()
    while recorte and medir(cabeza + recorte + elipsis + sufijo) > disponible:
        recorte = recorte[:-1].rstrip()
    return escala_min, (recorte + elipsis) if recorte else ""
