# Terreno del mapa grande con niveles de detalle (la malla única del mundo chico, ciudad_3d._malla_terreno, sigue intacta).
#
#   LOD0   malla del chunk a 1 m (la grilla del Terreno), color por vértice como el suelo de la favela (pasto, tierra junto
#          a casas y calles, tierra de taludes); el color de la ladera se calcula cada 2 m y se interpola (4 veces menos
#          cuentas; el grano fino lo pone la textura del suelo). Con faldón (borde que cuelga) para tapar grietas con el vecino.
#   LOD1   malla del chunk a 4 m (17 x 17 vértices), 0,12 m más baja que la verdadera.
#   fondo  UNA malla de todo el mapa a 8 m más 160 m de margen, 0,6 m más baja que el terreno (se ve donde aún no hay chunks).
#
# Las normales del borde de cada chunk usan las alturas del vecino (Terreno.altura), así el sombreado no marca la unión.
# Los colores son una función de (x, z): dos chunks calculan lo mismo en sus nodos comunes y no hay costuras de color.
# Las funciones son generadores (ceden el control cada pocas filas) y su StopIteration.value es un DatosMalla.

import math
from collections import namedtuple

from backend.datos.terreno import PASO_GRILLA
from frontend import suelo_calculos as sc
from frontend.mapa_tierra_indexado import MapaTierraIndexado
from frontend.texturas_favela import METROS_GRANO

PENDIENTE_TIERRA = (25.0, 40.0)        # grados: de pasto a tierra en los taludes (igual que ciudad_3d)
FALDON = 1.5                           # m que cuelga el borde de cada malla
DESCENSO_LOD1 = 0.12                   # m más baja que el terreno real
DESCENSO_FONDO = 0.6                   # m más baja que el terreno real
PASO_LOD1 = 4                          # nodos (m) entre vértices del LOD1
PASO_FONDO = 8.0                       # m entre vértices del fondo
MARGEN_FONDO = 160.0                   # m que el fondo se extiende más allá del terreno
FILAS_POR_TANDA = 3                    # filas de vértices entre una cesión y otra

DatosMalla = namedtuple("DatosMalla", "vertices normales colores uvs triangulos")


def _tan_talud():
    return tuple(math.tan(math.radians(g)) for g in PENDIENTE_TIERRA)


def talud_de(gx, gz):
    """0 llano ... 1 muy empinado, a partir de la pendiente (gx, gz) en m/m."""
    desde, hasta = _tan_talud()
    return min(1.0, max(0.0, (math.hypot(gx, gz) - desde) / (hasta - desde)))


class CampoSuelo:
    """Color del suelo en (x, z): pasto, tierra junto a casas y calles y talud (suelo_calculos.color_ladera)."""

    def __init__(self, mundo):
        cajas = [e.caja() for e in mundo.edificios()]
        cajas += [(o.cx - o.ancho / 2, o.cx + o.ancho / 2, o.cz - o.fondo / 2, o.cz + o.fondo / 2)
                  for o in mundo.obstaculos() if o.tipo == "casa"]
        calles = [(mundo.coordenada(a), mundo.coordenada(b)) for a, b in mundo.segmentos()]
        plazas = [mundo.coordenada(lugar) for lugar in mundo.lugares()]
        self.mapa = MapaTierraIndexado(cajas, calles, plazas, mundo.radio_plaza + 0.9)
        self._talud = tuple(c * sc.BRILLO_SUELO / 255 for c in sc.COLOR_TALUD)

    # Color RGB 0-1 sin talud (llano).
    def base(self, x, z):
        return sc.color_ladera(x, z, self.mapa.peso_tierra(x, z), 0.0)

    # Mezcla el color base con la tierra del talud (talud 0-1): el mismo paso final de color_ladera.
    def con_talud(self, base, talud):
        if talud <= 0.0:
            return base
        s = sc._suave(talud)
        t = self._talud
        return (min(1.0, base[0] + (t[0] - base[0]) * s), min(1.0, base[1] + (t[1] - base[1]) * s),
                min(1.0, base[2] + (t[2] - base[2]) * s))

    def color(self, x, z, talud):
        return self.con_talud(self.base(x, z), talud)

    # Color del ladera en (x, z) para fundir el borde de las cintas de arena con el suelo (ciudad_3d._ladera_para_cintas).
    def ladera_para_cintas(self, x, z):
        return sc.color_ladera(x, z, self.mapa.peso_tierra(x, z), 0.0)


def _indices_muestreo(n, paso):
    idx = list(range(0, n, paso))
    if idx[-1] != n - 1:
        idx.append(n - 1)
    return idx


def _altura_en(filas, terreno, x0, z0, i, j, nx, nz):
    """Altura del nodo (i, j) del chunk; fuera del chunk, la del terreno completo (que pertenece al vecino)."""
    if 0 <= i < nx and 0 <= j < nz:
        return filas[j][i]
    return terreno.altura(x0 + i * PASO_GRILLA, z0 + j * PASO_GRILLA)


def malla_de_chunk(terreno, campo, ci, cj, paso=1, color_cada=2, descenso=0.0, faldon=FALDON, metros_uv=METROS_GRANO):
    """Generador: malla del chunk (ci, cj) con un vértice cada `paso` nodos (1 = 1 m, 4 = LOD1) y el color calculado cada
    `color_cada` nodos (interpolado entre medias). Devuelve DatosMalla (con uv y faldón)."""
    filas = terreno.grilla_de_chunk(ci, cj)
    x0, z0 = terreno.origen_chunk(ci, cj)
    nz, nx = len(filas), len(filas[0])
    ii, jj = _indices_muestreo(nx, paso), _indices_muestreo(nz, paso)
    colores_base = {}

    def base_en(i, j):
        clave = (i, j)
        c = colores_base.get(clave)
        if c is None:
            if color_cada <= 1 or (i % color_cada == 0 and j % color_cada == 0):
                c = campo.base(x0 + i * PASO_GRILLA, z0 + j * PASO_GRILLA)
            else:
                # i o j impares: media de los nodos pares vecinos que existen (los dos o los cuatro más cercanos)
                vi = [i] if i % color_cada == 0 else [k for k in (i - 1, i + 1) if 0 <= k < nx]
                vj = [j] if j % color_cada == 0 else [k for k in (j - 1, j + 1) if 0 <= k < nz]
                cs = [base_en(a, b) for a in vi for b in vj]
                c = tuple(sum(k[m] for k in cs) / len(cs) for m in range(3))
            colores_base[clave] = c
        return c

    vertices, normales, colores, uvs = [], [], [], []
    d = paso * PASO_GRILLA
    inv = 1.0 / (2 * d)
    inv_uv = 1.0 / metros_uv
    for n, j in enumerate(jj):
        fila = filas[j]
        interior_j = j - paso >= 0 and j + paso < nz
        z = z0 + j * PASO_GRILLA
        for i in ii:
            h = fila[i]
            if interior_j and i - paso >= 0 and i + paso < nx:          # camino rápido: todo dentro de la grilla del chunk
                gx = (fila[i + paso] - fila[i - paso]) * inv
                gz = (filas[j + paso][i] - filas[j - paso][i]) * inv
            else:
                gx = (_altura_en(filas, terreno, x0, z0, i + paso, j, nx, nz)
                      - _altura_en(filas, terreno, x0, z0, i - paso, j, nx, nz)) * inv
                gz = (_altura_en(filas, terreno, x0, z0, i, j + paso, nx, nz)
                      - _altura_en(filas, terreno, x0, z0, i, j - paso, nx, nz)) * inv
            largo = math.sqrt(gx * gx + 1 + gz * gz)
            x = x0 + i * PASO_GRILLA
            vertices.append((x, h - descenso, z))
            normales.append((-gx / largo, 1 / largo, -gz / largo))
            r, g, b = campo.con_talud(base_en(i, j), talud_de(gx, gz))
            colores.append((r, g, b, 1.0))
            uvs.append((x * inv_uv, z * inv_uv))
        if n % FILAS_POR_TANDA == FILAS_POR_TANDA - 1:
            yield
    sx, sz = len(ii), len(jj)
    triangulos = []
    for j in range(sz - 1):
        for i in range(sx - 1):
            v = j * sx + i
            triangulos.append((v, v + sx + 1, v + sx))
            triangulos.append((v, v + 1, v + sx + 1))
    if faldon > 0:
        bordes = ([j * sx for j in range(sz)], [j * sx + sx - 1 for j in range(sz)],
                  list(range(sx)), [(sz - 1) * sx + i for i in range(sx)])
        for borde in bordes:
            base = len(vertices)
            for v in borde:
                x, y, z = vertices[v]
                vertices.append((x, y, z))
                vertices.append((x, y - faldon, z))
                normales += [normales[v], normales[v]]
                colores += [colores[v], colores[v]]
                uvs += [uvs[v], uvs[v]]
            for k in range(len(borde) - 1):
                a = base + 2 * k
                triangulos.append((a, a + 1, a + 3))
                triangulos.append((a, a + 3, a + 2))
    return DatosMalla(vertices, normales, colores, uvs, triangulos)


def malla_lod0(terreno, campo, ci, cj):
    return (yield from malla_de_chunk(terreno, campo, ci, cj, paso=1, color_cada=2))


def malla_lod1(terreno, campo, ci, cj):
    return (yield from malla_de_chunk(terreno, campo, ci, cj, paso=PASO_LOD1, color_cada=1, descenso=DESCENSO_LOD1))


def malla_fondo(terreno, campo, margen=MARGEN_FONDO, paso=PASO_FONDO, descenso=DESCENSO_FONDO):
    """Generador: la malla de fondo de todo el mapa. Cada vértice toma la MENOR de 5 alturas (él y 4 puntos a medio paso)
    para quedar siempre bajo el terreno de los chunks, más `descenso`."""
    x0, x1, z0, z1 = terreno.extension
    x0, x1, z0, z1 = x0 - margen, x1 + margen, z0 - margen, z1 + margen
    nx, nz = int(math.ceil((x1 - x0) / paso)) + 1, int(math.ceil((z1 - z0) / paso)) + 1
    m = paso / 2
    alturas = []
    for j in range(nz):
        z = z0 + j * paso
        fila = []
        for i in range(nx):
            x = x0 + i * paso
            fila.append(min(terreno.altura(x, z), terreno.altura(x - m, z), terreno.altura(x + m, z),
                            terreno.altura(x, z - m), terreno.altura(x, z + m)) - descenso)
        alturas.append(fila)
        if j % FILAS_POR_TANDA == 0:
            yield
    vertices, normales, colores, uvs = [], [], [], []
    for j in range(nz):
        z = z0 + j * paso
        for i in range(nx):
            x = x0 + i * paso
            gx = (alturas[j][min(i + 1, nx - 1)] - alturas[j][max(i - 1, 0)]) / (2 * paso)
            gz = (alturas[min(j + 1, nz - 1)][i] - alturas[max(j - 1, 0)][i]) / (2 * paso)
            largo = math.sqrt(gx * gx + 1 + gz * gz)
            vertices.append((x, alturas[j][i], z))
            normales.append((-gx / largo, 1 / largo, -gz / largo))
            r, g, b = campo.color(x, z, talud_de(gx, gz))
            colores.append((r, g, b, 1.0))
            uvs.append((x / METROS_GRANO, z / METROS_GRANO))
        if j % FILAS_POR_TANDA == 0:
            yield
    triangulos = []
    for j in range(nz - 1):
        for i in range(nx - 1):
            v = j * nx + i
            triangulos.append((v, v + nx + 1, v + nx))
            triangulos.append((v, v + 1, v + nx + 1))
    return DatosMalla(vertices, normales, colores, uvs, triangulos)
