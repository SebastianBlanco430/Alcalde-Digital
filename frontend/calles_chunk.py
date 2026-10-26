# Calles del mapa grande, por chunk: las cintas de arena (con textura del camino y borde irregular), la avenida de asfalto
# gastado con sus aceras, línea central discontinua, líneas de borde y cebras, y los discos pintados de las plazas.
# Es el mismo dibujo que ciudad_3d._construir_calles/_construir_marcas/_construir_plazas y suelo_favela, escrito en listas
# (frontend/geom_directa.Acumulador) en vez de ursina.Mesh, y recortado a un chunk.
#
# Reparto sin repetir ni dejar huecos: la cinta de cada calle se corta en cuadriláteros de ~1 m a lo largo del eje y cada
# cuadrilátero lo dibuja el chunk que contiene el punto medio de su eje (aunque el ancho de la cinta asome por el vecino).
# Así dos chunks vecinos nunca dibujan lo mismo (nada de z-fighting) y, con los dos cargados, la calle queda continua.
# Las normales de la cinta salen de sus propios vértices (diferencias entre filas y columnas), no de más consultas al terreno.
#
# Todo es generador (cede cada pocas filas). Sin ursina: se prueba sin ventana.

import math
import zlib

from frontend import suelo_calculos as sc
from frontend.azar_fijo import azar_de
from frontend.props_mundo import color_con_ruido
from frontend.suelo_favela import color_asfalto

ALTO_ARENA = 0.06
ALTO_ASFALTO = 0.10
ALTO_LINEA = 0.12
ALTO_ACERA = 0.20
COLOR_LINEA = (200, 176, 92)
COLOR_MARCA_VIAL = (172, 172, 168)
COLOR_ACERA_AVENIDA = (176, 150, 128)
AMPLITUD_RUIDO_ACERA = 14
ACERA = 2.0
FILAS_POR_TANDA = 8
SEPARACION_LINEAS = 4.0

# Avenida de asfalto: las mismas calles de ciudad_3d.CALLES_ASFALTADAS (pares de lugares, en cualquier orden).
CALLES_ASFALTADAS = (("Prefeitura", "Praça da Sé"), ("Praça da Sé", "Universidade de Ciudad Nova"))


def es_asfalto(a, b):
    return (a, b) in CALLES_ASFALTADAS or (b, a) in CALLES_ASFALTADAS


def semilla_de_calle(a, b):
    """Número estable de una calle (el mismo en todos los chunks), para el borde irregular de su cinta."""
    return zlib.crc32(("%s|%s" % tuple(sorted((a, b)))).encode("utf-8")) % 997


def _filas_propias(mundo, clave, pa, pb, pasos):
    """Índices k (cuadriláteros k..k+1) de la cinta de pa a pb cuyo punto medio cae en el chunk `clave`."""
    propias = []
    for k in range(pasos):
        t = (k + 0.5) / pasos
        if mundo.chunk_de(pa[0] + (pb[0] - pa[0]) * t, pa[1] + (pb[1] - pa[1]) * t) == clave:
            propias.append(k)
    return propias


def cinta(acum, suelo, pa, pb, s_filas, d_columnas, alto, color_en, propias, uv=None, lados=0.0):
    """Generador: agrega a `acum` los cuadriláteros `propias` de la cinta (filas en `s_filas` m desde pa, columnas en
    `d_columnas` m a la izquierda del eje). `color_en(x, z, d_rel)` -> RGBA 0-1; `uv(c, s)` -> (u, v) o None. Con `lados` > 0
    agrega las paredes laterales. Cede el control cada FILAS_POR_TANDA filas."""
    if not propias:
        return
    largo = math.dist(pa, pb)
    ux, uz = (pb[0] - pa[0]) / largo, (pb[1] - pa[1]) / largo
    nx, nz = -uz, ux
    cols = len(d_columnas)
    necesarias = sorted({k for p in propias for k in (p, p + 1)})
    P = {}
    for n, k in enumerate(necesarias):
        s = s_filas[k]
        P[k] = [(pa[0] + ux * s + nx * d, suelo(pa[0] + ux * s + nx * d, pa[1] + uz * s + nz * d) + alto,
                 pa[1] + uz * s + nz * d) for d in d_columnas]
        if n % FILAS_POR_TANDA == FILAS_POR_TANDA - 1:
            yield
    semiancho = max(abs(d_columnas[0]), abs(d_columnas[-1])) or 1.0
    base = {}
    for n, k in enumerate(necesarias):
        base[k] = len(acum.vertices)
        antes, despues = P.get(k - 1, P[k]), P.get(k + 1, P[k])
        for c, d in enumerate(d_columnas):
            x, y, z = P[k][c]
            izq, der = P[k][max(c - 1, 0)], P[k][min(c + 1, cols - 1)]
            u = (despues[c][0] - antes[c][0], despues[c][1] - antes[c][1], despues[c][2] - antes[c][2])
            v = (der[0] - izq[0], der[1] - izq[1], der[2] - izq[2])
            nrm = (u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0])
            if nrm[1] < 0:
                nrm = (-nrm[0], -nrm[1], -nrm[2])
            ln = math.sqrt(nrm[0] ** 2 + nrm[1] ** 2 + nrm[2] ** 2)
            acum.vertices.append((x, y, z))
            acum.normales.append((nrm[0] / ln, nrm[1] / ln, nrm[2] / ln) if ln > 1e-9 else (0.0, 1.0, 0.0))
            acum.colores.append(color_en(x, z, abs(d) / semiancho))
            if uv is not None:
                acum.uvs.append(uv(c, s_filas[k]))
        if n % FILAS_POR_TANDA == FILAS_POR_TANDA - 1:
            yield
    for k in propias:
        for c in range(cols - 1):
            i, j = base[k] + c, base[k + 1] + c
            acum.triangulos += [(i, i + 1, j + 1), (i, j + 1, j)]
    if lados > 0:
        for c in (0, cols - 1):
            ids = {}
            for k in necesarias:
                x, y, z = P[k][c]
                ids[k] = len(acum.vertices)
                acum.vertices += [(x, y, z), (x, y - lados - 0.05, z)]
                acum.normales += [(0.0, 1.0, 0.0)] * 2
                acum.colores += [acum.colores[base[k] + c]] * 2
                if uv is not None:
                    acum.uvs += [acum.uvs[base[k] + c]] * 2
            for k in propias:
                i, j = ids[k], ids[k + 1]
                if c:
                    acum.triangulos += [(i, j, j + 1), (i, j + 1, i + 1)]
                else:
                    acum.triangulos += [(i, j + 1, j), (i, i + 1, j + 1)]


def _s_uniformes(largo, s0, s1, paso):
    pasos = max(1, math.ceil((s1 - s0) / paso))
    return [s0 + (s1 - s0) * k / pasos for k in range(pasos + 1)], pasos


def calle_de_arena(arena, mundo, campo, clave, a, b, pa, pb, texturado=True):
    """Generador: cinta de arena de la calle a-b (malla_calles_arena de suelo_favela, por cuadriláteros propios)."""
    largo = math.dist(pa, pb)
    if largo < 1e-9:
        return
    semilla = semilla_de_calle(a, b)
    s_filas, pasos = _s_uniformes(largo, 0.0, largo, sc.PASO_CINTA)
    propias = _filas_propias(mundo, clave, pa, pb, pasos)
    if not propias:
        return
    ux, uz = (pb[0] - pa[0]) / largo, (pb[1] - pa[1]) / largo
    columnas = sc.COLUMNAS_CINTA + 1
    # columnas irregulares: cada fila tiene su propio ancho (el borde se corre por ruido); aquí se usa la fila k para toda
    # la fila (d de cada columna), por eso la cinta se arma fila por fila con sus d.
    suelo = mundo.altura
    nx, nz = -uz, ux

    def d_de(k):
        s = s_filas[k]
        return sc.columnas_cinta(sc.borde_irregular(s, semilla, -1), sc.borde_irregular(s, semilla, 1))

    necesarias = sorted({k for p in propias for k in (p, p + 1)})
    filas = {}
    for n, k in enumerate(necesarias):
        s = s_filas[k]
        ds = d_de(k)
        pts, cols, uvs = [], [], []
        for c, d in enumerate(ds):
            x, z = pa[0] + ux * s + nx * d, pa[1] + uz * s + nz * d
            pts.append((x, suelo(x, z) + ALTO_ARENA, z))
            t = min(1.0, abs(d) / sc.SEMIANCHO_CINTA)
            f = sc._suave((t - sc.INICIO_FUNDIDO_BORDE) / (1.0 - sc.INICIO_FUNDIDO_BORDE))
            arena_c = tuple(min(1.0, v * sc.BRILLO_SUELO / 255) for v in sc.color_arena(x, z))
            if f > 0.0:
                r, g, bl = sc._mezclar(arena_c, campo.ladera_para_cintas(x, z), f)
            else:
                r, g, bl = arena_c
            cols.append((r, g, bl, 1.0))
            uvs.append((c / sc.COLUMNAS_CINTA, s / sc.LARGO_TEXTURA_CAMINO))
        filas[k] = (pts, cols, uvs)
        if n % FILAS_POR_TANDA == FILAS_POR_TANDA - 1:
            yield
    base = {}
    for k in necesarias:
        pts, cols, uvs = filas[k]
        base[k] = len(arena.vertices)
        antes = filas.get(k - 1, filas[k])[0]
        despues = filas.get(k + 1, filas[k])[0]
        for c in range(columnas):
            izq, der = pts[max(c - 1, 0)], pts[min(c + 1, columnas - 1)]
            u = (despues[c][0] - antes[c][0], despues[c][1] - antes[c][1], despues[c][2] - antes[c][2])
            if u == (0.0, 0.0, 0.0):
                u = (ux, 0.0, uz)
            v = (der[0] - izq[0], der[1] - izq[1], der[2] - izq[2])
            nrm = (u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0])
            if nrm[1] < 0:
                nrm = (-nrm[0], -nrm[1], -nrm[2])
            ln = math.sqrt(nrm[0] ** 2 + nrm[1] ** 2 + nrm[2] ** 2)
            arena.vertices.append(pts[c])
            arena.normales.append((nrm[0] / ln, nrm[1] / ln, nrm[2] / ln) if ln > 1e-9 else (0.0, 1.0, 0.0))
            arena.colores.append(cols[c])
            arena.uvs.append(uvs[c])
    for k in propias:
        for c in range(columnas - 1):
            i, j = base[k] + c, base[k + 1] + c
            arena.triangulos += [(i, i + 1, j + 1), (i, j + 1, j)]


def avenida(asfalto, mundo, clave, a, b, pa, pb, radio_plaza):
    """Generador: asfalto gastado, aceras, línea central, líneas de borde y cebras de la calle de asfalto a-b."""
    largo = math.dist(pa, pb)
    if largo < 1e-9:
        return
    suelo = mundo.altura
    semiancho = mundo.ancho_calle / 2
    borde = radio_plaza + 0.9
    s_filas, pasos = _s_uniformes(largo, 0.0, largo, 1.0)
    propias = _filas_propias(mundo, clave, pa, pb, pasos)
    if propias:
        d_cols = [-semiancho + 2 * semiancho * c / 8 for c in range(9)]
        yield from cinta(asfalto, suelo, pa, pb, s_filas, d_cols, ALTO_ASFALTO,
                         lambda x, z, t: color_asfalto(x, z, t), propias, lados=0.10)
    # aceras entre las plazas
    if largo - 2 * borde > 0:
        s_a, pasos_a = _s_uniformes(largo, borde, largo - borde, 1.0)
        # propias por el punto medio de cada cuadrilátero de la acera
        propias_a = [k for k in range(pasos_a)
                     if mundo.chunk_de(pa[0] + (pb[0] - pa[0]) * ((s_a[k] + s_a[k + 1]) / 2) / largo,
                                        pa[1] + (pb[1] - pa[1]) * ((s_a[k] + s_a[k + 1]) / 2) / largo) == clave]
        for lado in (-1, 1):
            d0, d1 = sorted((lado * semiancho, lado * (semiancho + ACERA)))
            yield from cinta(asfalto, suelo, pa, pb, s_a, [d0, (d0 + d1) / 2, d1], ALTO_ACERA,
                             lambda x, z, t: color_con_ruido(COLOR_ACERA_AVENIDA, AMPLITUD_RUIDO_ACERA, x, z), propias_a,
                             lados=0.20)
        # líneas de borde (continuas, algo hacia adentro del asfalto)
        for lado in (-1, 1):
            d = lado * (semiancho - 0.45)
            yield from cinta(asfalto, suelo, pa, pb, s_a, [d - 0.07, d + 0.07], ALTO_LINEA,
                             lambda x, z, t: _plano(COLOR_MARCA_VIAL), propias_a)
    # línea central discontinua
    s = mundo.radio_plaza + 2.0
    ux, uz = (pb[0] - pa[0]) / largo, (pb[1] - pa[1]) / largo
    while s + 1.0 <= largo - mundo.radio_plaza - 2.0:
        medio = s + 1.0
        if mundo.chunk_de(pa[0] + ux * medio, pa[1] + uz * medio) == clave:
            yield from cinta(asfalto, suelo, pa, pb, [s, s + 2.0], [-0.11, 0.11], ALTO_LINEA,
                             lambda x, z, t: _plano(COLOR_LINEA), [0])
        s += SEPARACION_LINEAS
    # cebras en cada entrada a una plaza
    if largo - 2 * borde > 0:
        largo_cebra = min(2.4, (largo - 2 * borde) / 2 - 0.4)
        if largo_cebra >= 1.2:
            for desde in (borde + 0.5, largo - borde - 0.5 - largo_cebra):
                medio = desde + largo_cebra / 2
                if mundo.chunk_de(pa[0] + ux * medio, pa[1] + uz * medio) != clave:
                    continue
                for k in range(-3, 4):
                    centro = 1.0 * k
                    if abs(centro) < 0.5:
                        continue
                    yield from cinta(asfalto, suelo, pa, pb, [desde, desde + largo_cebra], [centro - 0.25, centro + 0.25],
                                     ALTO_LINEA, lambda x, z, t: _plano(COLOR_MARCA_VIAL), [0])


def _plano(rgb255):
    return (rgb255[0] / 255, rgb255[1] / 255, rgb255[2] / 255, 1.0)


def calles_del_chunk(mundo, campo, vista, clave, arena, asfalto):
    """Generador: todas las calles del chunk (la arena en `arena`, con uv; el asfalto en `asfalto`)."""
    for a, b, pa, pb in vista.segmentos:
        if es_asfalto(a, b):
            yield from avenida(asfalto, mundo, clave, a, b, pa, pb, mundo.radio_plaza)
        else:
            yield from calle_de_arena(arena, mundo, campo, clave, a, b, pa, pb)
        yield


# -- Plazas ---------------------------------------------------------------------------------------------------------------


def plazas_globales(acum, mundo, y_plaza=0.14):
    """Generador: UN acumulador con todos los discos pintados de las plazas (suelo_favela.datos_plaza_pintada)."""
    from frontend.suelo_favela import datos_plaza_pintada
    for numero, lugar in enumerate(mundo.lugares()):
        cx, cz = mundo.coordenada(lugar)
        h = mundo.altura(cx, cz)
        vertices, triangulos, colores, normales = datos_plaza_pintada(cx, cz, h + y_plaza, mundo.radio_plaza, numero)
        i0 = len(acum.vertices)
        acum.vertices.extend(vertices)
        acum.normales.extend(normales)
        acum.colores.extend(colores)
        acum.triangulos.extend((a + i0, b + i0, c + i0) for a, b, c in triangulos)
        yield
