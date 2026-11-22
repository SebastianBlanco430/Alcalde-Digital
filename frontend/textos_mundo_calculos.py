# M1.3 (D7) Textos flotantes que se pisan (puro, con tests). En el mundo, el globo de un NPC («Los niños a la escuela y
# yo a la f…») quedaba tapado por el cartel de la puerta «Prefeitura (Alcaldía)». Prioridad fija:
#
#   globo de NPC  >  cartel de puerta de edificio  >  cartel de puesto/tienda
#
# Si dos textos se solapan en pantalla (rectángulos con un pequeño margen), el de MENOS prioridad se desvanece en
# DURACION_FUNDIDO s y vuelve en otros DURACION_FUNDIDO s cuando deja de solaparse. Reglas decididas:
#   - Un texto OCULTO no oculta a otros (A > B > C, A tapa a B y B tocaba a C: C se queda visible si A no lo toca).
#   - Empates (misma prioridad) no se ocultan entre sí: se ven los dos (como antes).
#   - Bordes que solo se tocan NO cuentan como solape (el margen ya da la holgura).
# Rectángulos en unidades de pantalla de Ursina (y en [-0.5, 0.5], x en [-aspecto/2, aspecto/2]): (x0, y0, x1, y1).
# ALCALDE_TEXTOS_PRIORIDAD=0 apaga todo: los carteles quedan exactamente como antes.

import math
import os

TEXTOS_PRIORIDAD = True          # constante por defecto de la bandera

PRIORIDAD_GLOBO = 3
PRIORIDAD_PUERTA = 2
PRIORIDAD_PUESTO = 1

MARGEN = 0.006                   # unidades de pantalla que se agrandan los rectángulos por cada lado
DURACION_FUNDIDO = 0.15          # s de alfa 1 a 0 (y de 0 a 1)
PERIODO_SOLAPES = 0.1            # s entre dos recálculos de los solapes (el fundido avanza cada frame)
RADIO = 25.0                     # m de la cámara: más lejos no se consideran
_EPS = 1e-6


def _bandera(nombre, constante):
    valor = os.environ.get(nombre, "").strip().lower()
    if valor in ("1", "true", "si", "sí", "on"):
        return True
    if valor in ("0", "false", "no", "off"):
        return False
    return bool(constante)


def textos_prioridad_activa():
    return _bandera("ALCALDE_TEXTOS_PRIORIDAD", TEXTOS_PRIORIDAD)


# Rectángulo que encierra los puntos de pantalla (x, y), agrandado `margen` por lado. None si no hay puntos.
def rect_de_puntos(puntos, margen=MARGEN):
    puntos = list(puntos)
    if not puntos:
        return None
    xs = [p[0] for p in puntos]
    ys = [p[1] for p in puntos]
    return (min(xs) - margen, min(ys) - margen, max(xs) + margen, max(ys) + margen)


# Rectángulo centrado en (cx, cy) de semiancho `ax` y semialto `ay` (globos: siempre de frente a la cámara).
def rect_centrado(cx, cy, ax, ay, margen=MARGEN):
    ax, ay = abs(ax) + margen, abs(ay) + margen
    return (cx - ax, cy - ay, cx + ax, cy + ay)


# ¿Se solapan de verdad? (área común > 0; tocarse en un borde o una esquina no cuenta).
def se_solapan(a, b):
    if a is None or b is None:
        return False
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


# Pendiente de puestos (2026-11-22): a ras de ojos el letrero «Padaria Estrela» salía en blanco porque se solapaba en
# pantalla con el cartel de la puerta del Mercado, que está DETRÁS (el tablero del puesto lo tapa). Un cartel de puerta
# ya no oculta a un letrero de puesto que está más de DELANTE_M más cerca de la cámara. Los globos mandan siempre.
DELANTE_M = 1.0


def _no_oculta(p_alto, prof_alto, p_bajo, prof_bajo):
    return (p_alto == PRIORIDAD_PUERTA and p_bajo == PRIORIDAD_PUESTO and prof_alto is not None and prof_bajo is not None
            and prof_bajo < prof_alto - DELANTE_M)


# items: [(clave, prioridad, rect)] o [(clave, prioridad, rect, profundidad)] (z en espacio de cámara). Devuelve el
# conjunto de claves a ocultar. Se decide de mayor a menor prioridad: un texto se oculta si se solapa con alguno VISIBLE
# de prioridad estrictamente mayor (salvo el caso de _no_oculta). Los ocultos no ocultan.
def resolver_ocultos(items):
    visibles = []                                    # [(prioridad, rect, profundidad)] ya decididos visibles
    ocultos = set()
    for item in sorted(items, key=lambda it: -it[1]):
        clave, prioridad, rect = item[:3]
        prof = item[3] if len(item) > 3 else None
        if rect is None:
            continue
        if any(p > prioridad and se_solapan(rect, r) and not _no_oculta(p, pz, prioridad, prof)
               for p, r, pz in visibles):
            ocultos.add(clave)
        else:
            visibles.append((prioridad, rect, prof))
    return ocultos


# Un paso del fundido: acerca `alfa` a `objetivo` (0 o 1) a velocidad 1/duracion por segundo. Monótono, sin pasarse,
# y llega exactamente (con tolerancia de redondeo) tras `duracion` s acumulados.
def paso_alfa(alfa, objetivo, dt, duracion=DURACION_FUNDIDO):
    if dt <= 0 or alfa == objetivo:
        return alfa
    if duracion <= 0:
        return float(objetivo)
    paso = dt / duracion
    if objetivo > alfa:
        nuevo = alfa + paso
        return float(objetivo) if nuevo >= objetivo - _EPS else nuevo
    nuevo = alfa - paso
    return float(objetivo) if nuevo <= objetivo + _EPS else nuevo


# ¿Un punto en espacio de cámara está delante y a menos de `radio`? Ursina usa el sistema «y-up-left» de Panda
# (window.py): x a la derecha, y arriba, z hacia delante.
def cerca_y_delante(x, y, z, radio=RADIO):
    return z > 0.05 and math.sqrt(x * x + y * y + z * z) < radio


# De coordenadas de película de la lente (-1..1) a unidades de pantalla de Ursina.
def a_pantalla(fx, fy, aspecto):
    return fx * aspecto * 0.5, fy * 0.5


# -- M1.4 (D9) Letreros ilegibles --
# Un cartel estático del mundo (puerta + glosa, puesto, cartel pintado) cuyas letras miden en pantalla menos de
# ALTO_OCULTAR_PX píxeles es una mancha ilegible: se funde (los mismos 0.15 s). Vuelve cuando pasa de ALTO_MOSTRAR_PX
# (histéresis: entre los dos umbrales conserva lo que tenía, así no parpadea al caminar en el límite). Los globos de
# los NPC, las etiquetas de nombre y el cartel TRABAJO no entran. ALCALDE_LETREROS_MINIMO=0: como antes.

LETREROS_MINIMO = True           # constante por defecto de la bandera
# Qué se mide: el TAMAÑO DE LETRA en pantalla (el «em» de la fuente: alto de línea de las letras, sin el tablero ni la
# glosa), en px de la ventana, penalizado si el cartel se ve de lado (alto_efectivo). Calibrado con capturas reales a
# 1280x720 (medidas/m14_*): manchas ilegibles = BAR de lado a 13 m (9.2), AÇAÍ a 21 m (8.1), «Morro da Esperança» a
# 22 m y de lado (6.7); se leen = «Padaria Estrela» y «Supermercado do Bairro» a 14 m (10.7 / 10.9), «Mercado
# Municipal» a 18 m (15.4), «Prefeitura» a 11 m (21.4). Banda de histéresis estrecha (0.5 px, ~5 % de distancia):
# más ancha volvía a esconder los puestos a 14 m al llegar desde lejos.
ALTO_OCULTAR_PX = 10.0           # por debajo, ilegible: se oculta
ALTO_MOSTRAR_PX = 10.5           # por encima, legible: vuelve


def letreros_minimo_activa():
    return _bandera("ALCALDE_LETREROS_MINIMO", LETREROS_MINIMO)


# Alto en píxeles de algo de `alto_mundo` m a `profundidad` m delante de una cámara en perspectiva de campo vertical
# `fov_vertical` grados, en una ventana de `alto_ventana` px. None si no se puede (detrás de la cámara, datos malos).
def alto_en_pantalla_px(alto_mundo, profundidad, fov_vertical, alto_ventana):
    try:
        if alto_mundo is None or profundidad <= 0 or not 0 < fov_vertical < 180 or alto_ventana <= 0:
            return None
        return alto_mundo / (2.0 * profundidad * math.tan(math.radians(fov_vertical) / 2.0)) * alto_ventana
    except (TypeError, ValueError):
        return None


# ¿Se muestra? `antes`: si se mostraba en la pasada anterior. Sin medida (None) se queda como estaba.
def legible(alto_px, antes=True, ocultar=ALTO_OCULTAR_PX, mostrar=ALTO_MOSTRAR_PX):
    if alto_px is None or alto_px != alto_px:
        return antes
    return alto_px >= ocultar if antes else alto_px > mostrar


# Factor de alto_en_pantalla_px: alto_px = alto_mundo * factor / profundidad. None si la lente no es válida.
def factor_px(fov_vertical, alto_ventana):
    if not 0 < fov_vertical < 180 or alto_ventana <= 0:
        return None
    return alto_ventana / (2.0 * math.tan(math.radians(fov_vertical) / 2.0))


# Repaso de un tramo [desde, hasta) de carteles fijos, en un solo bucle (son ~280: llamar a Panda por cada uno costaba
# más que todo lo demás). `centros`: [(x, y, z)] en el mundo; `altos`: alto de las letras (m) o None; `matriz`: filas
# (4 x 4) de la matriz mundo -> cámara de Panda (punto fila por matriz: x' = x*m00 + y*m10 + z*m20 + m30); `factor`:
# factor_px(). Actualiza EN SU SITIO `legibles` (histéresis de legible()) y `cerca` (a menos de `radio` m) y devuelve
# los índices cuya legibilidad cambió. Sin `factor` (o minimo=False) la legibilidad no se toca.
def repasar_carteles(centros, altos, legibles, cerca, matriz, factor, desde, hasta, radio=RADIO, minimo=True,
                     ocultar=ALTO_OCULTAR_PX, mostrar=ALTO_MOSTRAR_PX, normales=None, diagnostico=None):
    (a0, a1, a2, _a3), (b0, b1, b2, _b3), (c0, c1, c2, _c3), (d0, d1, d2, _d3) = matriz
    radio2 = radio * radio
    medir = minimo and factor is not None
    cambiados = []
    for k in range(desde, min(hasta, len(centros))):
        centro = centros[k]
        if centro is None:
            cerca[k] = False
            continue
        x, y, z = centro
        cx = x * a0 + y * b0 + z * c0 + d0
        cy = x * a1 + y * b1 + z * c1 + d1
        cz = x * a2 + y * b2 + z * c2 + d2
        d2_ = cx * cx + cy * cy + cz * cz
        cerca[k] = d2_ < radio2
        if not medir or cz <= 0 or altos[k] is None:
            continue
        alto = altos[k] * factor / cz
        normal = normales[k] if normales is not None else None
        if normal is not None and d2_ > 0:
            nx, ny, nz = normal
            coseno = abs((nx * a0 + ny * b0 + nz * c0) * cx + (nx * a1 + ny * b1 + nz * c1) * cy
                         + (nx * a2 + ny * b2 + nz * c2) * cz) / math.sqrt(d2_)
            alto = alto_efectivo(alto, coseno)
        if diagnostico is not None:
            diagnostico[k] = alto
        antes = legibles[k]
        ahora = alto >= ocultar if antes else alto > mostrar
        if ahora != antes:
            legibles[k] = ahora
            cambiados.append(k)
    return cambiados


# Alto «efectivo» de las letras de un cartel visto de lado: `coseno` es el del ángulo entre la normal del cartel y la
# línea de vista (1 = de frente, 0 = de canto). De lado las letras se aplastan a lo ancho y se leen peor aunque
# conserven el alto: se penaliza con la raíz del coseno (a 60 grados, x0.71; a 75 grados, x0.51).
def alto_efectivo(alto_px, coseno):
    return alto_px * math.sqrt(min(1.0, max(0.0, coseno)))
