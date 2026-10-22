# Suelo de la favela (Ursina): mallas de las calles de arena con borde irregular, el asfalto gastado de la
# avenida con parches de arena, los discos pintados de las plazas y las texturas procedurales de la
# ladera. Los números (colores, pesos, columnas) salen de frontend/suelo_calculos.py y las imágenes de
# frontend/texturas_favela.py; aquí solo se arman Mesh y Texture.
#
# Todo es opcional y reversible desde ciudad_3d.py: con las banderas de suelo apagadas se vuelve al suelo
# de antes (asfalto en todas las calles, plazas de cemento gris, ladera verde).

import math

from ursina import Mesh, Texture

from frontend import suelo_calculos as sc
from frontend.azar_fijo import azar_de, ruido_suave
from frontend.texturas_favela import METROS_GRANO, textura_camino, textura_grano

# -- Asfalto de la avenida --
COLOR_ASFALTO_GASTADO = (50, 50, 62)       # RGB 0-255, base del asfalto (más claro y violeta que el de antes)
PARCHE_ARENA_ASFALTO = 0.62                # umbral del ruido de los parches de arena sobre el asfalto
PARCHE_BACHE = 0.70                        # umbral de los baches oscuros


# Textura de Ursina desde una imagen de PIL, con mipmaps para que no brille al alejarse.
def textura_de(imagen):
    return Texture(imagen, filtering="mipmap")


def textura_del_grano():
    return textura_de(textura_grano())


def textura_del_camino():
    return textura_de(textura_camino())


# Normal del suelo en (x, z) por diferencias centrales de `suelo` (igual que ciudad_3d._normal_suelo).
def _normal(suelo, x, z, h=0.5):
    nx = -(suelo(x + h, z) - suelo(x - h, z)) / (2 * h)
    nz = -(suelo(x, z + h) - suelo(x, z - h)) / (2 * h)
    largo = math.sqrt(nx * nx + 1 + nz * nz)
    return (nx / largo, 1 / largo, nz / largo)


# Una sola malla con TODAS las calles de arena de `tramos` [(a, b)] (puntos (x, z) de plaza a plaza):
# cintas de SEMIANCHO_CINTA m a cada lado del eje, con los bordes corridos por ruido (irregulares),
# `alto` m sobre el suelo, color por vértice (arena en el centro que se funde con la ladera al borde,
# `ladera(x, z)` -> RGB 0-1) y coordenadas de textura (u a lo ancho, v a lo largo cada
# LARGO_TEXTURA_CAMINO m) para la textura del camino. Con normales del suelo.
def malla_calles_arena(suelo, tramos, ladera, alto=0.06):
    vertices, colores, normales, uvs, triangulos = [], [], [], [], []
    for numero, (a, b) in enumerate(tramos):
        largo = math.dist(a, b)
        if largo < 1e-9:
            continue
        ux, uz = (b[0] - a[0]) / largo, (b[1] - a[1]) / largo
        nx, nz = -uz, ux
        pasos = max(1, math.ceil(largo / sc.PASO_CINTA))
        base = len(vertices)
        ancho = sc.COLUMNAS_CINTA + 1
        for k in range(pasos + 1):
            s = largo * k / pasos
            irregular_izq = sc.borde_irregular(s, numero, -1)
            irregular_der = sc.borde_irregular(s, numero, 1)
            for c, d in enumerate(sc.columnas_cinta(irregular_izq, irregular_der)):
                x, z = a[0] + ux * s + nx * d, a[1] + uz * s + nz * d
                t = min(1.0, abs(d) / sc.SEMIANCHO_CINTA)
                vertices.append((x, suelo(x, z) + alto, z))
                normales.append(_normal(suelo, x, z))
                r, g, bl = sc.color_cinta(x, z, t, ladera(x, z))
                colores.append((r, g, bl, 1.0))
                uvs.append((c / sc.COLUMNAS_CINTA, s / sc.LARGO_TEXTURA_CAMINO))
        for k in range(pasos):
            for c in range(sc.COLUMNAS_CINTA):
                i = base + k * ancho + c
                triangulos += [(i, i + 1, i + ancho + 1), (i, i + ancho + 1, i + ancho)]
    if not vertices:
        return None
    return Mesh(vertices=vertices, triangles=triangulos, colors=colores, uvs=uvs, normals=normales)


# Cinta de asfalto gastado (de s0 a s1 m desde `a` hacia `b`, de d0 a d1 m a la izquierda del eje, `alto` m
# sobre el suelo): como props_mundo.cinta_con_tono pero con parches de arena que invaden desde los bordes y
# baches oscuros, y con normales del suelo. Con `lados` > 0 agrega las paredes laterales.
def cinta_asfalto_gastado(suelo, a, b, s0, s1, d0, d1, alto, columnas=8, paso=1.0, lados=0.0):
    largo = math.dist(a, b)
    ux, uz = (b[0] - a[0]) / largo, (b[1] - a[1]) / largo
    nx, nz = -uz, ux
    pasos = max(1, math.ceil((s1 - s0) / paso))
    vertices, colores, normales, triangulos = [], [], [], []
    semiancho = max(abs(d0), abs(d1))
    for k in range(pasos + 1):
        s = s0 + (s1 - s0) * k / pasos
        for c in range(columnas + 1):
            d = d0 + (d1 - d0) * c / columnas
            x, z = a[0] + ux * s + nx * d, a[1] + uz * s + nz * d
            vertices.append((x, suelo(x, z) + alto, z))
            normales.append(_normal(suelo, x, z))
            colores.append(color_asfalto(x, z, abs(d) / semiancho))
    ancho = columnas + 1
    for k in range(pasos):
        for c in range(columnas):
            i = k * ancho + c
            triangulos += [(i, i + 1, i + ancho + 1), (i, i + ancho + 1, i + ancho)]
    if lados > 0:
        for columna in (0, columnas):
            base = len(vertices)
            for k in range(pasos + 1):
                x, y, z = vertices[k * ancho + columna]
                vertices += [(x, y, z), (x, y - lados - 0.05, z)]
                colores += [colores[k * ancho + columna]] * 2
                normales += [(0, 1, 0)] * 2
            for k in range(pasos):
                i = base + 2 * k
                triangulos += [(i, i + 2, i + 3), (i, i + 3, i + 1)] if columna else [(i, i + 3, i + 2), (i, i + 1, i + 3)]
    return Mesh(vertices=vertices, triangles=triangulos, colors=colores, normals=normales)


# Color RGBA 0-1 del asfalto en (x, z) a la fracción lateral `t` (0 eje, 1 borde): asfalto con manchas,
# más arena hacia los bordes y baches oscuros sueltos.
def color_asfalto(x, z, t):
    base = COLOR_ASFALTO_GASTADO
    mancha = ruido_suave(x, z, 5.0) - 0.5
    grano = azar_de(x * 1.9, z * 1.3) - 0.5
    f = 1.0 + 0.22 * mancha + 0.10 * grano
    asfalto = tuple(c * f for c in base)
    arena = sc.color_arena(x, z)
    umbral = PARCHE_ARENA_ASFALTO - 0.22 * t                # en los bordes hay más arena
    parche = sc._suave((ruido_suave(x + 5.0, z - 9.0, 3.4) - umbral) * 7.0)
    color = sc._mezclar(asfalto, tuple(c * 0.92 for c in arena), parche)
    bache = sc._suave((ruido_suave(x - 3.0, z + 4.0, 1.8) - PARCHE_BACHE) * 9.0) * 0.45
    color = sc._mezclar(color, (24, 24, 32), bache)
    return (min(1.0, color[0] / 255), min(1.0, color[1] / 255), min(1.0, color[2] / 255), 1.0)


# Malla del disco pintado de una plaza de `radio` m centrada en (cx, cz) a la altura `y` (la plaza es una
# terraza plana): franjas concéntricas de la paleta número `indice` que ondulan, un aro exterior de
# bordillo con rayas alternas y un círculo central. Vértices sueltos por celda (colores planos).
# Devuelve (vértices, triángulos, colores, normales) para un Mesh.
def datos_plaza_pintada(cx, cz, y, radio, indice):
    paleta = sc.paleta_de_plaza(indice)
    anillos, sectores = sc.ANILLOS_PLAZA, sc.SECTORES_PLAZA
    vertices, colores, triangulos = [], [], []

    def celda(r0, r1, th0, th1, tono, alto):
        base = len(vertices)
        for r, th in ((r0, th0), (r1, th0), (r1, th1), (r0, th1)):
            vertices.append((cx + r * math.cos(th), y + alto, cz + r * math.sin(th)))
            colores.append((*tono, 1.0))
        # el sentido de los triángulos se corrige más abajo con el de la normal (hacia +y)
        triangulos.extend(_hacia_arriba(vertices, base, base + 1, base + 2, base + 3))

    for k in range(anillos):
        r0, r1 = radio * k / anillos, radio * (k + 1) / anillos
        for m in range(sectores):
            th0, th1 = 2 * math.pi * m / sectores, 2 * math.pi * (m + 1) / sectores
            celda(r0, r1, th0, th1, sc.color_disco((r0 + r1) / 2 / radio, (th0 + th1) / 2, paleta, indice), 0.0)
    # aro exterior de bordillo (0,9 m): rayas alternas de dos colores de la paleta, un poco más abajo
    for m in range(sectores):
        th0, th1 = 2 * math.pi * m / sectores, 2 * math.pi * (m + 1) / sectores
        tono = paleta[3] if m % 2 == 0 else paleta[1]
        celda(radio - 0.02, radio + 0.9, th0, th1, tuple(min(1.0, c / 255 * sc.BRILLO_PLAZA) for c in tono), -0.02)
    return vertices, triangulos, colores, [(0.0, 1.0, 0.0)] * len(vertices)


# Dos triángulos del cuadrilátero (a, b, c, d) con el orden que deja la cara hacia +y (el suelo no es de doble cara).
def _hacia_arriba(vertices, a, b, c, d):
    va, vb, vc = vertices[a], vertices[b], vertices[c]
    ux, uz = vb[0] - va[0], vb[2] - va[2]
    wx, wz = vc[0] - va[0], vc[2] - va[2]
    # Panda: antihorario visto desde arriba (+y) con x a la derecha y z hacia arriba en pantalla es cara frontal.
    cruz = ux * wz - uz * wx
    if cruz > 0:
        return [(a, b, c), (a, c, d)]
    return [(a, c, b), (a, d, c)]


def malla_plaza_pintada(cx, cz, y, radio, indice):
    vertices, triangulos, colores, normales = datos_plaza_pintada(cx, cz, y, radio, indice)
    return Mesh(vertices=vertices, triangles=triangulos, colors=colores, normals=normales)
