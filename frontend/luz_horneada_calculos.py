# Cálculos puros de la LUZ HORNEADA del mundo (punto 4 del pulido; NO importa ursina ni panda3d).
#
# Problema (D2): el shader lit_with_shadows de Ursina multiplica el color por la luz y le SUMA N·L/π, así que todas las
# caras de una casa salen casi del mismo tono y la forma no se lee. Aquí se calcula, al CONSTRUIR el mundo, un factor
# por vértice que luego se multiplica en sus colores de vértice (costo cero en el loop):
#   - Orientación respecto al sol (`DIRECCION_SOL`, hacia donde apunta la luz): techo / cara hacia arriba x1.00, pared
#     de cara al sol x0.92, pared a la sombra x0.75 con un tinte frío leve (TINTE_SOMBRA). Las normales intermedias
#     mezclan suave según el coseno entre la pared y el sol; las caras hacia abajo van como sombra.
#   - Oclusión ambiental falsa: los primeros ALTO_AO m de cada pared sobre su base se oscurecen hasta x0.85 (gradiente).
# Los factores MULTIPLICAN el color (la noche de ciudad_viva y el tinte de cada piso se siguen aplicando encima).
#
# BANDERA: LUZ_HORNEADA = False o ALCALDE_LUZ_HORNEADA=0 dejan los colores exactamente como antes.

import math
import os

LUZ_HORNEADA = True
DIRECCION_SOL_POR_DEFECTO = (1.0, -1.1, 0.8)     # la de frontend/cielo.DIRECCION_SOL (el llamador pasa la real)

FACTOR_TECHO = 1.00
FACTOR_PARED_SOL = 0.92
FACTOR_PARED_SOMBRA = 0.75
TINTE_SOMBRA = (0.97, 0.98, 1.04)    # frío y sutil: solo en la parte a la sombra
ALTO_AO = 0.6                        # m sobre la base de la pieza
FACTOR_AO = 0.85                     # en la base misma
_EPS = 1e-9

# T4 del bloque T (ALCALDE_SOMBRA_CEL): sombra CEL con color. Dos tonos duros por cara (corte casi duro alrededor de la
# perpendicular al sol, banda BANDA_CEL de coseno) y la cara a la sombra cambia de MATIZ hacia el violeta azulado de la
# paleta (referencia RGB (88, 78, 140)) en vez de oscurecer en gris; razón de luminancia ~1,0 / 0,72. El matiz se mete en
# el factor multiplicativo (mezcla MEZCLA_MATIZ hacia el color de referencia normalizado) y se reescala a LUMA_SOMBRA_CEL;
# eso sube la saturación de los tonos cálidos en sombra (el +10 % del plan sale del propio matiz).
SOMBRA_CEL = True
COLOR_SOMBRA_CEL = (88, 78, 140)
MEZCLA_MATIZ = 0.38
LUMA_SOMBRA_CEL = 0.72
FACTOR_LUZ_CEL = 1.0
BANDA_CEL = 0.08
_NEUTRO = (1.0, 1.0, 1.0)


def _bandera(nombre, constante):
    valor = os.environ.get(nombre, "").strip().lower()
    if valor in ("1", "true", "si", "sí", "on"):
        return True
    if valor in ("0", "false", "no", "off"):
        return False
    return bool(constante)


def luz_horneada_activa():
    """¿Rige el punto 4? ALCALDE_LUZ_HORNEADA=1/0 manda sobre la constante."""
    return _bandera("ALCALDE_LUZ_HORNEADA", LUZ_HORNEADA)


def sombra_cel_activa():
    """¿T4? ALCALDE_SOMBRA_CEL=1/0 manda sobre la constante SOMBRA_CEL (solo cuenta con la luz horneada encendida)."""
    return _bandera("ALCALDE_SOMBRA_CEL", SOMBRA_CEL)


def _factor_sombra_cel():
    media = sum(COLOR_SOMBRA_CEL) / 3.0
    tinte = [1.0 + MEZCLA_MATIZ * (c / media - 1.0) for c in COLOR_SOMBRA_CEL]
    luma = 0.2126 * tinte[0] + 0.7152 * tinte[1] + 0.0722 * tinte[2]
    return tuple(t * LUMA_SOMBRA_CEL / luma for t in tinte)


FACTOR_SOMBRA_CEL = _factor_sombra_cel()


def factor_cel(normal, direccion_sol=DIRECCION_SOL_POR_DEFECTO):
    """T4: factor RGB de dos tonos duros. Arriba y de cara al sol: FACTOR_LUZ_CEL; a la sombra (o hacia abajo):
    FACTOR_SOMBRA_CEL (violeta azulado, luma 0,72). Normal degenerada -> neutro."""
    n = _unitario(normal)
    if n is None:
        return _NEUTRO
    sol = hacia_el_sol(direccion_sol)
    luz = n[0] * sol[0] + n[1] * sol[1] + n[2] * sol[2]
    if n[1] > 0.5:                     # techos y tapas: siempre a la luz (si no, las plazas se vuelven violetas)
        luz = max(luz, 1.0)
    t = _suave((luz + BANDA_CEL) / (2 * BANDA_CEL))
    return tuple(FACTOR_SOMBRA_CEL[i] + (FACTOR_LUZ_CEL - FACTOR_SOMBRA_CEL[i]) * t for i in range(3))


def _finito(*valores):
    try:
        return all(math.isfinite(float(v)) for v in valores)
    except (TypeError, ValueError):
        return False


def _suave(t):
    t = min(1.0, max(0.0, t))
    return t * t * (3.0 - 2.0 * t)


def _unitario(v):
    """Vector normalizado (tupla de 3) o None si es degenerado (largo ~0, NaN, infinito o mal formado)."""
    try:
        x, y, z = (float(c) for c in v[:3])
    except (TypeError, ValueError, IndexError):
        return None
    if not _finito(x, y, z):
        return None
    largo = math.sqrt(x * x + y * y + z * z)
    if largo < 1e-6:
        return None
    return (x / largo, y / largo, z / largo)


def hacia_el_sol(direccion_sol=DIRECCION_SOL_POR_DEFECTO):
    """Vector unitario desde la superficie HACIA el sol (el opuesto a la dirección de la luz)."""
    d = _unitario(direccion_sol) or _unitario(DIRECCION_SOL_POR_DEFECTO)
    return (-d[0], -d[1], -d[2])


def factor_direccional(normal, direccion_sol=DIRECCION_SOL_POR_DEFECTO):
    """Factor RGB (r, g, b) de una cara según su normal: 1 arriba, 0.92 pared al sol, 0.75 (y tinte frío) a la sombra.
    Normal degenerada -> neutro (1, 1, 1): nunca oscurece algo que no se sabe orientar."""
    if sombra_cel_activa():
        return factor_cel(normal, direccion_sol)
    n = _unitario(normal)
    if n is None:
        return _NEUTRO
    sol = hacia_el_sol(direccion_sol)
    # Pared: coseno entre la parte horizontal de la normal y la del sol (1 = de frente al sol, <= 0 = a la sombra).
    largo_h = math.hypot(n[0], n[2])
    largo_sol = math.hypot(sol[0], sol[2])
    if largo_h > 1e-6 and largo_sol > 1e-6:
        coseno = (n[0] * sol[0] + n[2] * sol[2]) / (largo_h * largo_sol)
    else:
        coseno = 0.0
    lit = _suave(coseno)                         # 0 a la sombra, 1 de frente al sol, suave entre medio
    pared = FACTOR_PARED_SOMBRA + (FACTOR_PARED_SOL - FACTOR_PARED_SOMBRA) * lit
    sombra = 1.0 - lit                           # cuánto tinte frío lleva la pared
    arriba = n[1]
    if arriba >= 0.0:
        valor = pared + (FACTOR_TECHO - pared) * arriba
        sombra *= (1.0 - arriba)
    else:
        w = -arriba                              # hacia abajo: como la sombra
        valor = pared + (FACTOR_PARED_SOMBRA - pared) * w
        sombra = sombra + (1.0 - sombra) * w
    return tuple(min(1.0, max(0.0, valor * (1.0 + (t - 1.0) * sombra))) for t in TINTE_SOMBRA)


def factor_ao(altura, alto=ALTO_AO, minimo=FACTOR_AO):
    """Oclusión falsa por la altura del vértice sobre la base de su pieza: `minimo` en la base (y por debajo), 1.0 desde
    `alto` m, gradiente suave entre medio. Altura None/NaN/infinita -> 1.0 (no oscurece)."""
    if altura is None or not _finito(altura):
        return 1.0
    if alto <= 0:
        return 1.0
    return minimo + (1.0 - minimo) * _suave(float(altura) / alto)


def factor_vertice(normal, altura=None, direccion_sol=DIRECCION_SOL_POR_DEFECTO):
    """Factor RGB total de un vértice: el direccional por la AO. La AO es de las PAREDES: en las caras hacia arriba
    (techos, tapas) se desvanece con la componente vertical de la normal."""
    f = factor_direccional(normal, direccion_sol)
    if altura is None:
        return f
    ao = factor_ao(altura)
    n = _unitario(normal)
    if n is not None and n[1] > 0.0:
        ao = ao + (1.0 - ao) * n[1]
    return (f[0] * ao, f[1] * ao, f[2] * ao)


def aplicar(color, factor):
    """Color RGBA 0-1 multiplicado por el factor RGB (alfa intacto), acotado a [0, 1]."""
    r, g, b = color[0], color[1], color[2]
    a = color[3] if len(color) > 3 else 1.0
    return (min(1.0, max(0.0, r * factor[0])), min(1.0, max(0.0, g * factor[1])),
            min(1.0, max(0.0, b * factor[2])), a)


def bases_por_pieza(alturas, conteos):
    """Base (la menor altura) de cada vértice según la pieza a la que pertenece. `alturas`: y de cada vértice de la
    malla combinada, en orden; `conteos`: vértices de cada pieza, en el mismo orden. Devuelve una lista paralela a
    `alturas`, o None si los conteos no cuadran con las alturas (entonces no se hace AO)."""
    if sum(conteos) != len(alturas) or any(c < 0 for c in conteos):
        return None
    salida, inicio = [], 0
    for c in conteos:
        tramo = alturas[inicio:inicio + c]
        finitos = [y for y in tramo if _finito(y)]
        base = min(finitos) if finitos else float("nan")
        salida.extend([base] * c)
        inicio += c
    return salida
