# Muros de contención por REGIÓN del mapa grande (datos puros, sin ursina).
#
# VERIFICADO en F4: no hace falta recalcular nada. MundoGrande.muros_de_chunk (mundo_grande.py) ya llama a
# muros.muros_de_contencion con una ventana de terreno recortada al chunk de 64 m (_VentanaTerreno cambia solo `extension`)
# y con las escaleras, cajas de edificios/casas y líneas libres (calles, becos, accesos) que tocan ese chunk; por dentro
# eso son _celdas_empinadas y _fusionar de muros.py, que solo recorren las celdas del recorte (sin barrer el mapa
# entero). Las celdas son de 1 m alineadas a la extensión y cada celda cae en un solo chunk, así que los muros no se
# repiten entre chunks. Por eso aquí NO se duplica ese cálculo: solo se añade
#
#   muros_de_region(mundo, caja)         muros de los chunks que toca la caja (xmin, xmax, zmin, zmax), sin repetidos.
#   muros_sobre_caminos(mundo, muros)    [(muro, motivo)]: muros que tapan una calle, un beco, una escalera o el tramo
#                                        puerta -> punto de entrada de un edificio. [] = ningún muro bloquea un camino.
#   caminos_libres(mundo)                [(nombre, a, b, paso)] de lo que ningún muro debe tapar: `paso` = semiancho exigido
#                                        (calles: la mitad de la calle; becos y escaleras: 1 m a cada lado del eje).

import math

from backend.datos.muros import _distancia_segmento

SEMIANCHO_ENTRADA = 0.6         # m: ancho de paso del jugador delante de una puerta
HOLGURA_MURO = 0.0              # m extra sobre el paso exigido (muros.py ya deja DISTANCIA_LIBRE = 1 m desde el eje a cada celda)
PASO_LIBRE_MINIMO = 1.0         # m a cada lado del eje que un muro nunca puede invadir (= muros.DISTANCIA_LIBRE)


def muros_de_region(mundo, caja):
    """Muros de los chunks que toca `caja`, en el orden de chunks (j, i), sin repetir ninguno."""
    xmin, xmax, zmin, zmax = caja
    ci0, cj0 = mundo.chunk_de(xmin, zmin)
    ci1, cj1 = mundo.chunk_de(xmax, zmax)
    vistos, salida = set(), []
    for cj in range(cj0, cj1 + 1):
        for ci in range(ci0, ci1 + 1):
            for m in mundo.muros_de_chunk(ci, cj):
                if m not in vistos:
                    vistos.add(m)
                    salida.append(m)
    return salida


def caminos_libres(mundo):
    """Lo que ningún muro debe tapar: [(nombre, (ax, az), (bx, bz), paso exigido a cada lado del eje)]."""
    caminos = []
    for a, b in mundo.segmentos():
        caminos.append((f"calle {a} - {b}", tuple(mundo.coordenada(a)), tuple(mundo.coordenada(b)), mundo.ancho_calle / 2))
    if hasattr(mundo, "becos"):
        for k, beco in enumerate(mundo.becos()):
            for p, q in beco.tramos():
                caminos.append((f"beco {k}", tuple(p), tuple(q), min(beco.ancho / 2, PASO_LIBRE_MINIMO)))
    for k, e in enumerate(mundo.escaleras()):
        caminos.append((f"escalera {k}", (e.ax, e.az), (e.bx, e.bz), min(e.ancho / 2, PASO_LIBRE_MINIMO)))
    for e in mundo.edificios():
        caminos.append((f"puerta de {e.lugar}", tuple(e.puerta()), tuple(e.punto_entrada()), SEMIANCHO_ENTRADA))
    return caminos


def _segmento_del_muro(m):
    rad = math.radians(m.rumbo)
    ux, uz = math.sin(rad), math.cos(rad)
    h = m.largo / 2
    return (m.cx - ux * h, m.cz - uz * h), (m.cx + ux * h, m.cz + uz * h)


def _distancia_entre_segmentos(a, b, c, d):
    # distancia mínima entre dos segmentos que no se cruzan (si se cruzan, los extremos dan > 0: se trata aparte)
    if _se_cruzan(a, b, c, d):
        return 0.0
    return min(_distancia_segmento(a[0], a[1], c, d), _distancia_segmento(b[0], b[1], c, d),
               _distancia_segmento(c[0], c[1], a, b), _distancia_segmento(d[0], d[1], a, b))


def _se_cruzan(a, b, c, d):
    def o(p, q, r):
        return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])
    return o(a, b, c) * o(a, b, d) < 0 and o(c, d, a) * o(c, d, b) < 0


def muros_sobre_caminos(mundo, muros=None, caminos=None):
    """[(muro, motivo)]: muros cuya losa queda a menos de (paso exigido + espesor) de un camino libre."""
    if muros is None:
        muros = mundo.muros()
    if caminos is None:
        caminos = caminos_libres(mundo)
    # índice mínimo por celdas de 32 m sobre los caminos
    celda = 32.0
    tabla = {}
    for k, (_, a, b, w) in enumerate(caminos):
        i0, i1 = int(math.floor((min(a[0], b[0]) - w) / celda)), int(math.floor((max(a[0], b[0]) + w) / celda))
        j0, j1 = int(math.floor((min(a[1], b[1]) - w) / celda)), int(math.floor((max(a[1], b[1]) + w) / celda))
        for i in range(i0, i1 + 1):
            for j in range(j0, j1 + 1):
                tabla.setdefault((i, j), []).append(k)
    malos = []
    for m in muros:
        p, q = _segmento_del_muro(m)
        i0, i1 = int(math.floor(min(p[0], q[0]) / celda)), int(math.floor(max(p[0], q[0]) / celda))
        j0, j1 = int(math.floor(min(p[1], q[1]) / celda)), int(math.floor(max(p[1], q[1]) / celda))
        ks = sorted({k for i in range(i0, i1 + 1) for j in range(j0, j1 + 1) for k in tabla.get((i, j), ())})
        for k in ks:
            nombre, a, b, w = caminos[k]
            if _distancia_entre_segmentos(p, q, a, b) < w + HOLGURA_MURO:
                malos.append((m, nombre))
                break
    return malos
