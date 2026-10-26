# Árboles y arbustos de BAJA poligonización para el mapa grande.
#
# ANTES (ciudad_3d._arbol / _arbusto, que el mundo chico sigue usando): cada árbol = un tronco (cubo, 24 vértices) + dos
# esferas de Ursina (2880 vértices cada una) = 5784 vértices; cada arbusto = una esfera = 2880. Con las 135 árboles y 187
# arbustos del mapa grande serían 1,3 millones de vértices solo en vegetación de parque.
# AHORA (este módulo): mallas INDEXADAS con normales suaves (se ven como esferas de cómic, no facetadas):
#   árbol   tronco de 6 lados (13 vértices) + dos copas icosfera de 42  = 97 vértices   (LOD0)
#   árbol   tronco de 4 lados (9) + dos copas icosfera de 12            = 33 vértices   (LOD1, cajas lejanas)
#   arbusto una icosfera de 42 = 42 vértices (LOD0) / 12 (LOD1)
# Mismos colores, mismas proporciones y mismas posiciones que ciudad_3d (tronco 0,32 x 1,8 m; copa 2,7 x 2,4 m; segunda
# copa de 1,7 m desplazada; arbusto 1,3 x 1,0 m). Sin ursina: se prueba sin ventana (tests/test_arboles_lowpoly.py).

from frontend.geom_directa import icosfera_suave, prisma_suave

VERDES_ARBOL = ((58, 130, 62), (74, 148, 70), (46, 112, 70))
VERDES_ARBUSTO = ((70, 128, 60), (92, 140, 64), (60, 110, 76))
TRONCO = (98, 68, 44)
VERTICES_ANTES_ARBOL = 24 + 2 * 2880
VERTICES_ANTES_ARBUSTO = 2880

_PLANTILLAS = {}


def _plantilla(nombre, fabrica):
    p = _PLANTILLAS.get(nombre)
    if p is None:
        p = _PLANTILLAS[nombre] = fabrica()
    return p


def vertices_arbol(lejano=False):
    """Vértices de un árbol (tronco + 2 copas)."""
    if lejano:
        return len(_plantilla("tronco4", lambda: prisma_suave(4, 0.5, 0.36))[0]) + 2 * len(_plantilla("copa0", lambda: icosfera_suave(0))[0])
    return len(_plantilla("tronco6", lambda: prisma_suave(6, 0.5, 0.36))[0]) + 2 * len(_plantilla("copa1", lambda: icosfera_suave(1))[0])


def vertices_arbusto(lejano=False):
    return len(_plantilla("copa0" if lejano else "copa1", lambda: icosfera_suave(0 if lejano else 1))[0])


def color_arbol(cx, cz):
    return VERDES_ARBOL[int(abs(cx * 7 + cz * 13)) % 3]


def color_arbusto(cx, cz):
    return VERDES_ARBUSTO[int(abs(cx * 5 + cz * 11)) % 3]


# `y` = altura del suelo en (x, z). Las alturas relativas son las de ciudad_3d._arbol (que lo entierra 0,15 m).
def arbol_bajo(acum, x, y, z, lejano=False):
    verde = color_arbol(x, z)
    y = y - 0.15
    sub = 0 if lejano else 1
    tronco = _plantilla("tronco4", lambda: prisma_suave(4, 0.5, 0.36)) if lejano else _plantilla("tronco6", lambda: prisma_suave(6, 0.5, 0.36))
    copa = _plantilla(f"copa{sub}", lambda: icosfera_suave(sub))
    acum.solido(tronco, (x, y, z), (0.32, 1.8, 0.32), 0.0, TRONCO, (0.75, 1.0))
    acum.solido(copa, (x, y + 2.9, z), (2.7, 2.4, 2.7), 0.0, verde, (0.72, 1.1))
    acum.solido(copa, (x + 0.2, y + 3.9, z - 0.1), 1.7, 0.0, tuple(min(255, c + 14) for c in verde), (0.78, 1.12))


def arbusto_bajo(acum, x, y, z, lejano=False):
    sub = 0 if lejano else 1
    copa = _plantilla(f"copa{sub}", lambda: icosfera_suave(sub))
    acum.solido(copa, (x, y - 0.1 + 0.45, z), (1.3, 1.0, 1.3), 0.0, color_arbusto(x, z), (0.75, 1.1))
