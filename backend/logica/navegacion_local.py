# GPS local del mapa grande (funciones puras, sin ursina). navegacion.calcular_ruta_gps parte de una calle o de una plaza;
# dentro del barrio, lejos de la calle, solo sabe «ir a la plaza más cercana». Aquí se añade el tramo que falta: un A* corto
# sobre una VENTANA de la rejilla de conectividad (0,5 m, radio del jugador; conectividad_grande.construir_conectividad),
# sin tocar navegacion.py.
#
#   ruta_local(mundo, desde, hasta=None, radio_ventana=60.0)
#       [(x, z), ...] desde `desde` hasta `hasta` (un punto) o, con hasta=None, hasta la calle o plaza más cercana. La
#       ventana es el cuadrado de `radio_ventana` m de semilado centrado en `desde` (ampliado si `hasta` cae fuera y está
#       a menos de 2 ventanas). Si no se llega, termina en la celda alcanzada más cercana al objetivo; [] si `desde` no
#       tiene una celda libre a 1 m.
#   punto_de_calle_mas_cercano(mundo, x, z)  (x, z) del eje de calle/plaza más próximo.
#   ruta_gps_local(mundo, x, z, destino, radio_ventana=60.0)
#       (tramo_local, lugares): tramo_local = puntos hasta la calle (vacío si ya está en una calle o plaza) y `lugares` =
#       navegacion.calcular_ruta_gps desde ese punto de la calle. Dibujar: tramo_local + coordenadas de `lugares`.

import heapq
import math

from backend.datos.conectividad_grande import _VistaConectividad, construir_conectividad
from backend.logica import navegacion

RESOLUCION = 0.5
MARGEN_VENTANA = 6.0                  # m: lo que se amplía la caja de objetos respecto a la ventana
MAXIMO_NODOS = 400000
MAXIMO_SALTOS = 6                      # ventanas encadenadas por ruta_gps_local
_VECINOS = ((1, 0, 1.0), (-1, 0, 1.0), (0, 1, 1.0), (0, -1, 1.0),
            (1, 1, math.sqrt(2)), (1, -1, math.sqrt(2)), (-1, 1, math.sqrt(2)), (-1, -1, math.sqrt(2)))


def _en_caja(caja, c, m=0.0):
    return caja[0] - m <= c[1] and c[0] <= caja[1] + m and caja[2] - m <= c[3] and c[2] <= caja[3] + m


def _caja_obstaculo(o):
    r = o.radio if o.es_circulo else None
    if r is not None:
        return (o.cx - r, o.cx + r, o.cz - r, o.cz + r)
    return (o.cx - o.ancho / 2, o.cx + o.ancho / 2, o.cz - o.fondo / 2, o.cz + o.fondo / 2)


def _ventana(mundo, limites):
    """Conectividad de la ventana `limites` con solo los objetos que la tocan (la rejilla es de unos miles de celdas)."""
    m = MARGEN_VENTANA
    obstaculos = [o for o in mundo.obstaculos() if _en_caja(limites, _caja_obstaculo(o), m)]
    edificios = [e for e in mundo.edificios() if _en_caja(limites, e.caja(), m)]
    escaleras = [e for e in mundo.escaleras()
                 if _en_caja(limites, (min(e.ax, e.bx), max(e.ax, e.bx), min(e.az, e.bz), max(e.az, e.bz)), m + e.ancho)]
    vista = _VistaConectividad(mundo, obstaculos, edificios, escaleras, limites)
    return construir_conectividad(vista, limites=limites, resolucion=RESOLUCION)


def _distancia_a_segmento(x, z, a, b):
    dx, dz = b[0] - a[0], b[1] - a[1]
    l2 = dx * dx + dz * dz
    t = 0.0 if l2 < 1e-12 else min(1.0, max(0.0, ((x - a[0]) * dx + (z - a[1]) * dz) / l2))
    px, pz = a[0] + dx * t, a[1] + dz * t
    return math.hypot(x - px, z - pz), px, pz


def punto_de_calle_mas_cercano(mundo, x, z):
    """(px, pz) del eje de calle o centro de plaza más próximo a (x, z); None si el mapa no tiene calles ni lugares."""
    mejor = None
    for a, b in mundo.segmentos():
        d, px, pz = _distancia_a_segmento(x, z, mundo.coordenada(a), mundo.coordenada(b))
        if mejor is None or d < mejor[0]:
            mejor = (d, px, pz)
    for lugar in mundo.lugares():
        cx, cz = mundo.coordenada(lugar)
        d = math.hypot(x - cx, z - cz)
        if mejor is None or d < mejor[0]:
            mejor = (d, cx, cz)
    return None if mejor is None else (mejor[1], mejor[2])


def _en_red(mundo, x, z):
    return mundo.lugar_en_plaza(x, z) is not None or mundo.calle_en(x, z) is not None


class _Red:
    """Calles y plazas cercanas a una caja, para decidir rápido «¿esta celda es calle?» y «¿cuánto falta?»."""

    def __init__(self, mundo, caja, holgura=400.0):
        cerca = (caja[0] - holgura, caja[1] + holgura, caja[2] - holgura, caja[3] + holgura)
        self.semi = mundo.ancho_calle / 2
        self.radio = mundo.radio_plaza
        self.segmentos = []
        for a, b in mundo.segmentos():
            pa, pb = mundo.coordenada(a), mundo.coordenada(b)
            if _en_caja(cerca, (min(pa[0], pb[0]), max(pa[0], pb[0]), min(pa[1], pb[1]), max(pa[1], pb[1]))):
                self.segmentos.append((pa, pb))
        self.plazas = [mundo.coordenada(l) for l in mundo.lugares()
                       if cerca[0] <= mundo.coordenada(l)[0] <= cerca[1] and cerca[2] <= mundo.coordenada(l)[1] <= cerca[3]]
        self._falta = {}

    def falta(self, x, z):
        """Cota inferior (admisible) de los metros que faltan para pisar una calle o plaza."""
        clave = (round(x, 2), round(z, 2))
        v = self._falta.get(clave)
        if v is None:
            d = min([_distancia_a_segmento(x, z, a, b)[0] - self.semi for a, b in self.segmentos]
                    + [math.hypot(x - px, z - pz) - self.radio for px, pz in self.plazas] + [math.inf])
            v = self._falta[clave] = max(0.0, d) if d != math.inf else 0.0
        return v

    def es_red(self, x, z):
        return self.falta(x, z) <= 0.0


def ruta_local(mundo, desde, hasta=None, radio_ventana=60.0):
    """Ver el encabezado del módulo. `desde` y `hasta` son (x, z)."""
    x0, z0 = desde
    # Coordenadas no finitas (NaN/inf): sin ruta ([]), nunca una excepción ni un bucle.
    if not all(math.isfinite(v) for v in (x0, z0, radio_ventana)):
        return []
    if hasta is not None and not all(math.isfinite(v) for v in hasta):
        return []
    caja = [x0 - radio_ventana, x0 + radio_ventana, z0 - radio_ventana, z0 + radio_ventana]
    if hasta is not None and math.hypot(hasta[0] - x0, hasta[1] - z0) <= 2 * radio_ventana:
        caja = [min(caja[0], hasta[0] - 3), max(caja[1], hasta[0] + 3), min(caja[2], hasta[1] - 3), max(caja[3], hasta[1] + 3)]
    lim = mundo.limites_recorribles()
    caja = (max(caja[0], lim[0]), min(caja[1], lim[1]), max(caja[2], lim[2]), min(caja[3], lim[3]))
    if caja[0] >= caja[1] or caja[2] >= caja[3]:
        return []
    con = _ventana(mundo, caja)
    inicio = _celda_libre_cercana(con, x0, z0)
    if inicio is None:
        return []
    cx0, cz0 = con.limites[0], con.limites[2]

    def punto(c):
        return (cx0 + c[0] * RESOLUCION, cz0 + c[1] * RESOLUCION)

    if hasta is not None:
        meta = _celda_libre_cercana(con, *hasta)
        meta_punto = hasta

        def h(c):
            p = punto(c)
            return math.hypot(p[0] - meta_punto[0], p[1] - meta_punto[1])

        def es_meta(c):
            return meta is not None and c == meta
    else:
        red = _Red(mundo, caja)

        def h(c):
            return red.falta(*punto(c))

        def es_meta(c):
            return red.es_red(*punto(c))

    final = _astar(con, inicio, h, es_meta)
    cadena = _suavizar(con, final)
    puntos = [punto(c) for c in cadena]
    if puntos:
        puntos[0] = (x0, z0) if con.esta_libre(x0, z0) else puntos[0]
    return puntos


def _celda_libre_cercana(con, x, z, maximo=1.0):
    if not (math.isfinite(x) and math.isfinite(z)):
        return None                       # sin celda para coordenadas no finitas
    i0 = int(round((x - con.limites[0]) / con.paso))
    j0 = int(round((z - con.limites[2]) / con.paso))
    r = int(math.ceil(maximo / con.paso))
    mejor = None
    for dj in range(-r, r + 1):
        for di in range(-r, r + 1):
            if con.libre(i0 + di, j0 + dj):
                d = di * di + dj * dj
                if mejor is None or d < mejor[0]:
                    mejor = (d, (i0 + di, j0 + dj))
    return None if mejor is None else mejor[1]


def _astar(con, inicio, h, es_meta):
    """Celdas [inicio, ..., fin]: hasta la meta o, si no se alcanza, hasta la celda visitada con menor h."""
    g = {inicio: 0.0}
    padre = {}
    abiertos = [(h(inicio), 0, inicio)]
    cierre = set()
    mejor = (h(inicio), inicio)
    n = 0
    fin = None
    while abiertos and n < MAXIMO_NODOS:
        _, _, c = heapq.heappop(abiertos)
        if c in cierre:
            continue
        cierre.add(c)
        n += 1
        if es_meta(c):
            fin = c
            break
        hc = h(c)
        if hc < mejor[0]:
            mejor = (hc, c)
        i, j = c
        for di, dj, costo in _VECINOS:
            v = (i + di, j + dj)
            if v in cierre or not con.libre(*v):
                continue
            if di and dj and not (con.libre(i + di, j) and con.libre(i, j + dj)):
                continue
            nuevo = g[c] + costo * con.paso
            if nuevo < g.get(v, math.inf):
                g[v] = nuevo
                padre[v] = c
                heapq.heappush(abiertos, (nuevo + h(v), n, v))
    if fin is None:
        fin = mejor[1]
    cadena = [fin]
    while cadena[-1] in padre:
        cadena.append(padre[cadena[-1]])
    cadena.reverse()
    return cadena


def _linea_libre(con, a, b):
    """¿El segmento entre las celdas a y b pasa por celdas libres? En cada muestra (cada media celda) se exigen libres las
    cuatro celdas que rodean el punto, para no rozar esquinas entre dos celdas."""
    largo = math.hypot(b[0] - a[0], b[1] - a[1])
    if largo == 0:
        return True
    for k in range(1, int(largo * 2) + 1):
        t = min(1.0, k / (largo * 2))
        fi, fj = a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t
        i0, j0 = int(math.floor(fi)), int(math.floor(fj))
        i1, j1 = int(math.ceil(fi)), int(math.ceil(fj))
        if not (con.libre(i0, j0) and con.libre(i1, j0) and con.libre(i0, j1) and con.libre(i1, j1)):
            return False
    return True


def _suavizar(con, cadena):
    """Deja solo los puntos de giro: de cada punto se salta al más lejano visible en línea recta por celdas libres."""
    if len(cadena) <= 2:
        return cadena
    salida, k = [cadena[0]], 0
    while k < len(cadena) - 1:
        s = len(cadena) - 1
        while s > k + 1 and not _linea_libre(con, cadena[k], cadena[s]):
            s -= 1
        salida.append(cadena[s])
        k = s
    return salida


def ruta_gps_local(mundo, x, z, destino, radio_ventana=60.0):
    """(tramo_local, lugares). Ver el encabezado del módulo. ValueError si el destino no existe."""
    if destino not in mundo.lugares():
        raise ValueError(f"Lugar inexistente: {destino!r}")
    if _en_red(mundo, x, z):
        return [], navegacion.calcular_ruta_gps(mundo, x, z, destino)
    tramo = []
    for _ in range(MAXIMO_SALTOS):                      # si la calle queda más allá de la ventana, se encadenan ventanas
        parte = ruta_local(mundo, (x, z), None, radio_ventana)
        if len(parte) < 2:
            break
        tramo += parte if not tramo else parte[1:]
        x, z = parte[-1]
        if _en_red(mundo, x, z):
            break
    if not tramo:
        return [], navegacion.calcular_ruta_gps(mundo, x, z, destino)
    fx, fz = tramo[-1]
    return tramo, navegacion.calcular_ruta_gps(mundo, fx, fz, destino)
