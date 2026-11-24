# Cálculos puros del diagrama de flujo del final del caso (sin ursina). El diagrama es un grafo dirigido acíclico ya
# ordenado por capas (casos_v2_tipos.Diagrama: cada NodoDiagrama trae `capa` y `fila`).
#
# disponer() (sesión E) es el que usa el juego: diseño por capas de Sugiyama sobre el grafo que ya llega reducido del
# backend (backend/logica/diagrama_caso.py): nodos ficticios en las aristas largas, orden por baricentro con el menor
# número de cruces, columnas con el mismo paso vertical, aristas como curvas suaves que solo van por los canales entre
# columnas (o por el hueco que deja un nodo ficticio), y los haces «todos con todos» de una rueda a la siguiente
# concentrados en un punto de unión. El algoritmo completo está explicado en docs/DIAGRAMA_FLUJO.md.
#
# distribuir() / segmento() / aristas() son el reparto ANTERIOR (sesión A): se conservan como referencia para medir el
# «antes» (cruces) en los tests y en el documento.

import math
from dataclasses import dataclass

from backend.logica import diagrama_caso as grafo_caso

# Zona del diagrama en camera.ui (16:9): debajo del título y del porcentaje, encima del botón «Salir».
AREA = (-0.84, 0.84, 0.27, -0.33)      # x0, x1, y_arriba, y_abajo
ANCHO_MAX, ALTO_MAX = 0.24, 0.105
OCUPA_COLUMNA = 0.86                    # fracción mínima del ancho de columna para el hueco de las flechas (0,14)
HUECO_FLECHAS = 0.06                    # hueco ideal entre columnas, mientras la caja no baje de ANCHO_LEGIBLE
ANCHO_LEGIBLE = 0.145                   # caja más estrecha en la que cabe un hito de 32 letras en 3 líneas
OCUPA_FILA = 0.86
ANCHO_LETRA = 0.53                      # ancho medio de una letra en «em» (Atkinson Hyperlegible, prudente)
INTERLINEA = 1.22
RELLENO = 0.006                         # margen interior de la caja


def area_para(semiancho):
    """Área del diagrama para una pantalla de semiancho dado (más estrecha que 16:9 = se estrecha el área)."""
    x0, x1, ya, yb = AREA
    m = min(-x0, max(0.3, semiancho - 0.045))
    return -m, m, ya, yb


def distribuir(nodos, capas=None, area=AREA):
    """{id: (x, y, ancho, alto)} con el centro de cada caja. `nodos`: objetos con .id .capa .fila."""
    nodos = list(nodos)
    if not nodos:
        return {}
    n_capas = max(int(capas or 0), 1 + max(int(n.capa) for n in nodos))
    por_capa = {}
    for n in nodos:
        por_capa.setdefault(int(n.capa), []).append(n)
    n_filas = max(len(v) for v in por_capa.values())
    x0, x1, ya, yb = area
    col = (x1 - x0) / n_capas
    fila = (ya - yb) / n_filas
    hueco = max(col * (1 - OCUPA_COLUMNA), min(HUECO_FLECHAS, col - ANCHO_LEGIBLE))
    w = min(ANCHO_MAX, col - hueco)
    h = min(ALTO_MAX, fila * OCUPA_FILA)
    medio = (ya + yb) / 2
    cajas = {}
    for capa, lista in por_capa.items():
        lista.sort(key=lambda n: (int(n.fila), str(n.id)))
        k = len(lista)
        for i, n in enumerate(lista):
            x = x0 + col * (capa + 0.5)
            y = medio + (k - 1) / 2 * fila - i * fila
            cajas[n.id] = (x, y, w, h)
    return cajas


def segmento(caja_a, caja_b):
    """Del borde derecho de `a` al borde izquierdo de `b`: (x1, y1, x2, y2)."""
    xa, ya, wa, _ = caja_a
    xb, yb, wb, _ = caja_b
    return xa + wa / 2, ya, xb - wb / 2, yb


def a_barra(x1, y1, x2, y2):
    """Centro, largo y ángulo (grados, como rotation_z de Ursina: positivo = horario) de una barra de x1,y1 a x2,y2."""
    dx, dy = x2 - x1, y2 - y1
    return (x1 + x2) / 2, (y1 + y2) / 2, math.hypot(dx, dy), -math.degrees(math.atan2(dy, dx))


def aristas(diagrama_aristas, cajas):
    """[(x1, y1, x2, y2, recorrida)] de las aristas cuyos dos extremos se dibujan."""
    salida = []
    for arista in diagrama_aristas or ():
        try:
            a, b, recorrida = arista[0], arista[1], bool(arista[2]) if len(arista) > 2 else False
        except (TypeError, IndexError):
            continue
        if a in cajas and b in cajas:
            salida.append((*segmento(cajas[a], cajas[b]), recorrida))
    return salida


def letras_por_linea(ancho_caja, px_ref):
    """Letras que caben (estimación prudente) en una línea de la caja con letra de `px_ref`."""
    alto_letra = px_ref / 600.0
    return max(1, int((ancho_caja - 2 * RELLENO) / (alto_letra * ANCHO_LETRA)))


def lineas_que_caben(alto_caja, px_ref):
    alto_letra = px_ref / 600.0
    return max(1, int((alto_caja - 2 * RELLENO) / (alto_letra * INTERLINEA)))


def partir(texto, por_linea, max_lineas):
    """Parte en líneas de como mucho `por_linea` letras; si sobra, la última acaba en «…»."""
    palabras = str(texto or "").split()
    lineas, actual = [], ""
    for p in palabras:
        while len(p) > por_linea:                  # palabra más larga que la línea: se corta
            if actual:
                lineas.append(actual)
                actual = ""
            lineas.append(p[:por_linea])
            p = p[por_linea:]
        if not actual:
            actual = p
        elif len(actual) + 1 + len(p) <= por_linea:
            actual += " " + p
        else:
            lineas.append(actual)
            actual = p
    if actual:
        lineas.append(actual)
    if len(lineas) > max_lineas:
        resto = " ".join(lineas[max_lineas - 1:])
        ultima = resto[: max(0, por_linea - 1)].rstrip() + "…"
        lineas = lineas[:max_lineas - 1] + [ultima]
    return lineas


def sin_solapes(cajas, separacion=0.0):
    """¿Ninguna pareja de cajas se toca (con `separacion` de aire)?"""
    lista = list(cajas.values())
    for i in range(len(lista)):
        for j in range(i + 1, len(lista)):
            a, b = lista[i], lista[j]
            if abs(a[0] - b[0]) * 2 < a[2] + b[2] + 2 * separacion and abs(a[1] - b[1]) * 2 < a[3] + b[3] + 2 * separacion:
                return False
    return True


def dentro(cajas, area=AREA):
    x0, x1, ya, yb = area
    return all(x - w / 2 >= x0 - 1e-9 and x + w / 2 <= x1 + 1e-9 and y + h / 2 <= ya + 1e-9 and y - h / 2 >= yb - 1e-9
               for x, y, w, h in cajas.values())


# -- Diseño por capas (Sugiyama) --------------------------------------------------------------------------------------

HUECO_CANAL = 0.075                     # canal ideal entre columnas, por donde van las curvas
ALTO_CAJA = 0.094                       # caja en la que caben 3 líneas de letra de 12 px
PASO_BASE = 0.122                       # paso vertical entre filas (5 filas = el alto del área)
SEP_LINEA = 0.016                       # separación entre líneas que pasan por un mismo hueco de columna
MUESTRAS_CURVA = 12                     # segmentos con que se aproxima cada curva


@dataclass(frozen=True)
class Trazo:
    """Un tramo dibujado: polilínea en camera.ui. `origen` / `destino` son ids de caja, o None si el extremo es un punto
    de unión o un nodo ficticio. `flecha`: termina en el borde izquierdo de una caja (lleva punta)."""
    puntos: tuple
    recorrida: bool
    origen: object = None
    destino: object = None
    flecha: bool = False


@dataclass(frozen=True)
class Union:
    """Punto de unión de un haz concentrado (varios orígenes -> el mismo grupo de destinos)."""
    x: float
    y: float
    recorrida: bool


@dataclass(frozen=True)
class Disposicion:
    cajas: dict                         # {id: (x, y, ancho, alto)} centro de cada caja
    trazos: tuple                       # Trazo
    uniones: tuple                      # Union
    aristas: tuple                      # (origen, destino, recorrida) que se dibujan: una por par
    escala: float = 1.0                 # < 1 si hubo que encoger todo para que quepa (la letra también)
    paso: float = 0.0                   # paso vertical entre filas (ya escalado)


def curva(p, q, muestras=MUESTRAS_CURVA):
    """Curva suave de p a q (Bézier cúbica con tangentes horizontales en los dos extremos). Su x avanza siempre de p.x a
    q.x, así que no sale del canal entre las dos columnas. Si están a la misma altura, un segmento recto."""
    (x1, y1), (x2, y2) = p, q
    if abs(y1 - y2) < 1e-9:
        return (tuple(p), tuple(q))
    xm = (x1 + x2) / 2
    puntos = []
    for i in range(muestras + 1):
        t = i / muestras
        a, b, c, d = (1 - t) ** 3, 3 * (1 - t) ** 2 * t, 3 * (1 - t) * t ** 2, t ** 3
        puntos.append((a * x1 + (b + c) * xm + d * x2, (a + b) * y1 + (c + d) * y2))
    return tuple(puntos)


def _aristas_validas(diagrama, capa):
    """{(u, v): recorrida} sin repetidas, sin lazos, solo entre cajas dibujadas y hacia la derecha (capa creciente)."""
    rec = {}
    for arista in getattr(diagrama, "aristas", None) or ():
        try:
            u, v, r = arista[0], arista[1], bool(arista[2]) if len(arista) > 2 else False
        except (TypeError, IndexError):
            continue
        if u in capa and v in capa and capa[u] < capa[v]:
            rec[(u, v)] = rec.get((u, v), False) or r
    return rec


def _alturas_locales(orden, alto, paso):
    """y de cada elemento de su capa, con 0 en la primera caja real. Las cajas van a paso fijo; los ficticios ocupan el
    hueco entre dos cajas (repartidos) o quedan por encima / por debajo, a SEP_LINEA."""
    local = {}
    for fila in orden:
        reales = [v for v in fila if not grafo_caso.es_ficticio(v)]
        for i, v in enumerate(reales):
            local[v] = -i * paso
        grupo, previa = [], -1
        tramos = []
        for v in fila:
            if grafo_caso.es_ficticio(v):
                grupo.append(v)
            else:
                if grupo:
                    tramos.append((previa, grupo))
                grupo, previa = [], previa + 1
        if grupo:
            tramos.append((previa, grupo))
        for k, grupo in tramos:
            m = len(grupo)
            for j, f in enumerate(grupo):
                if not reales:
                    local[f] = -j * SEP_LINEA
                elif k == -1:
                    local[f] = alto / 2 + (m - j) * SEP_LINEA
                elif k == len(reales) - 1:
                    local[f] = -(k * paso + alto / 2 + (j + 1) * SEP_LINEA)
                else:
                    local[f] = -(k * paso + alto / 2 + (j + 1) * (paso - alto) / (m + 1))
    return local


def _hueco_mayor(orden):
    """Máximo de ficticios entre dos cajas reales de una misma capa."""
    mayor = 0
    for fila in orden:
        cuenta, hubo_real = 0, False
        for v in fila:
            if grafo_caso.es_ficticio(v):
                cuenta += 1
            else:
                if hubo_real:
                    mayor = max(mayor, cuenta)
                cuenta, hubo_real = 0, True
    return mayor


def disponer(diagrama, area=AREA, concentrar=True):
    """Disposicion del diagrama (ver la cabecera). Pura y determinista; nunca lanza con un diagrama vacío o raro.
    `concentrar=False` dibuja cada arista suelta (sin puntos de unión): solo para medir en el documento."""
    nodos = list(getattr(diagrama, "nodos", None) or ())
    if not nodos:
        return Disposicion({}, (), (), ())
    declarado = {n.id: i for i, n in enumerate(nodos)}
    capa = {n.id: int(n.capa) for n in nodos}
    rec = _aristas_validas(diagrama, capa)
    grafo = {n.id: [] for n in nodos}
    for u, v in rec:
        grafo[u].append(v)
    # 1-2. Nodos ficticios y orden por baricentro (partiendo de las filas que ya trae el backend).
    propio, capa_p, cadenas = grafo_caso.insertar_ficticios(grafo, capa)
    n_capas = max(int(getattr(diagrama, "capas", 0) or 0), 1 + max(capa.values()))
    inicial = [[] for _ in range(n_capas)]
    for n in sorted(nodos, key=lambda n: (int(getattr(n, "fila", 0) or 0), declarado[n.id])):
        inicial[capa[n.id]].append(n.id)
    for f in propio:
        if grafo_caso.es_ficticio(f):
            inicial[capa_p[f]].append(f)
    orden = grafo_caso.ordenar_capas(propio, capa_p, inicial)
    # 3. Coordenadas: columnas de igual ancho; en cada capa, cajas a paso fijo (el mismo en todas).
    x0, x1, ya, yb = area
    col = (x1 - x0) / n_capas
    hueco = max(col * (1 - OCUPA_COLUMNA), min(HUECO_CANAL, col - ANCHO_LEGIBLE))
    w = min(ANCHO_MAX, col - hueco)
    h = ALTO_CAJA
    paso = max(PASO_BASE, h + (_hueco_mayor(orden) + 1) * SEP_LINEA)
    local = _alturas_locales(orden, h, paso)
    medio = (ya + yb) / 2
    # Capa centrada en vertical: su primera caja, (k - 1)/2 pasos por encima del medio (k = cajas reales de la capa).
    centrado = [medio + max(0, sum(1 for v in fila if not grafo_caso.es_ficticio(v)) - 1) / 2 * paso for fila in orden]
    desplazamiento = list(centrado)
    vecinos = {v: list(propio[v]) for v in propio}
    for u in propio:
        for v in propio[u]:
            vecinos[v].append(u)
    # Alineación: cada capa se mueve (en medios pasos) hacia la media de sus vecinos; 4 vueltas, determinista.
    for _ in range(4):
        for c, fila in enumerate(orden):
            difs = [desplazamiento[capa_p[w2]] + local[w2] - local[v] for v in fila for w2 in vecinos[v]]
            if difs:
                deseado = sum(difs) / len(difs)
                desplazamiento[c] = centrado[c] + round((deseado - centrado[c]) / (paso / 2)) * (paso / 2)
    y = {v: desplazamiento[capa_p[v]] + local[v] for v in propio}
    real = {v: not grafo_caso.es_ficticio(v) for v in propio}
    arriba = max(y[v] + (h / 2 if real[v] else 0) for v in propio)
    abajo = min(y[v] - (h / 2 if real[v] else 0) for v in propio)
    escala = min(1.0, (ya - yb) / (arriba - abajo)) if arriba > abajo else 1.0
    cx, cy = (x0 + x1) / 2, (arriba + abajo) / 2
    X = {v: cx + (x0 + col * (capa_p[v] + 0.5) - cx) * escala for v in propio}
    Y = {v: medio + (y[v] - cy) * escala for v in propio}
    w, h, paso = w * escala, h * escala, paso * escala
    cajas = {n.id: (X[n.id], Y[n.id], w, h) for n in nodos}
    # 4. Trazos: curvas del puerto de salida (borde derecho) al de entrada (borde izquierdo); un ficticio es un tramo
    # recto a su altura a través de su columna. Si varios orígenes van a los MISMOS destinos (todos con todos, como
    # las preguntas de una rueda que llevan a la rueda siguiente), el haz se concentra en un punto de unión.
    def salida(v):
        return (X[v] + w / 2, Y[v])

    def entrada(v):
        return (X[v] - w / 2, Y[v])

    def caja_o_nada(v):
        return v if real[v] else None

    rec_propia = {}
    for par, cadena in cadenas.items():
        for a, b in zip(cadena, cadena[1:]):
            rec_propia[(a, b)] = rec[par]
    trazos, uniones = [], []
    for fila in orden:
        for f in fila:
            if not real[f]:
                r = any(rec_propia.get((a, f), False) for a in vecinos[f])
                trazos.append(Trazo((entrada(f), salida(f)), r))
    for c in range(n_capas - 1):
        posicion = {v: i for i, v in enumerate(orden[c])}
        padres = {}
        for a in orden[c]:
            for b in propio[a]:
                padres.setdefault(b, []).append(a)
        grupos = {}
        for b in orden[c + 1]:
            if b in padres:
                grupos.setdefault(tuple(sorted(padres[b], key=posicion.get)), []).append(b)
        for origenes, destinos in grupos.items():
            if concentrar and len(origenes) >= 2 and len(destinos) >= 2:
                jx = (X[origenes[0]] + w / 2 + X[destinos[0]] - w / 2) / 2
                jy = (sum(Y[a] for a in origenes) / len(origenes) + sum(Y[b] for b in destinos) / len(destinos)) / 2
                for a in origenes:
                    r = any(rec_propia[(a, b)] for b in destinos)
                    trazos.append(Trazo(curva(salida(a), (jx, jy)), r, caja_o_nada(a), None))
                for b in destinos:
                    r = any(rec_propia[(a, b)] for a in origenes)
                    trazos.append(Trazo(curva((jx, jy), entrada(b)), r, None, caja_o_nada(b), real[b]))
                uniones.append(Union(jx, jy, any(rec_propia[(a, b)] for a in origenes for b in destinos)))
            else:
                for a in origenes:
                    for b in destinos:
                        trazos.append(Trazo(curva(salida(a), entrada(b)), rec_propia[(a, b)], caja_o_nada(a),
                                            caja_o_nada(b), real[b]))
    aristas = tuple((u, v, r) for (u, v), r in rec.items())
    return Disposicion(cajas, tuple(trazos), tuple(uniones), aristas, escala, paso)


def malla(trazos, uniones, grosor, flecha, union):
    """(vértices, triángulos) de UNA malla con todos los trazos (cada segmento, un rectángulo de `grosor`), las puntas
    de flecha (triángulo de lado `flecha` al final de los trazos con `flecha`) y los puntos de unión (rombos)."""
    vertices, triangulos = [], []
    for t in trazos:
        pts = t.puntos
        for p, q in zip(pts, pts[1:]):
            dx, dy = q[0] - p[0], q[1] - p[1]
            largo = math.hypot(dx, dy)
            if largo < 1e-12:
                continue
            nx, ny = -dy / largo * grosor / 2, dx / largo * grosor / 2
            i = len(vertices)
            vertices += [(p[0] + nx, p[1] + ny, 0), (p[0] - nx, p[1] - ny, 0),
                         (q[0] + nx, q[1] + ny, 0), (q[0] - nx, q[1] - ny, 0)]
            triangulos += [(i, i + 1, i + 2), (i + 1, i + 3, i + 2)]
        if t.flecha and len(pts) >= 2:
            (px, py), (qx, qy) = pts[-2], pts[-1]
            largo = math.hypot(qx - px, qy - py) or 1.0
            ux, uy = (qx - px) / largo, (qy - py) / largo
            bx, by = qx - ux * flecha, qy - uy * flecha
            i = len(vertices)
            vertices += [(qx, qy, 0), (bx - uy * flecha / 2, by + ux * flecha / 2, 0),
                         (bx + uy * flecha / 2, by - ux * flecha / 2, 0)]
            triangulos.append((i, i + 1, i + 2))
    for u in uniones:
        i = len(vertices)
        vertices += [(u.x, u.y + union, 0), (u.x + union, u.y, 0), (u.x, u.y - union, 0), (u.x - union, u.y, 0)]
        triangulos += [(i, i + 1, i + 2), (i, i + 2, i + 3)]
    return vertices, triangulos


# -- Geometría para medir un dibujo (la usan los tests y el informe) --------------------------------------------------

def _orientacion(a, b, c):
    v = (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
    return 0 if abs(v) < 1e-12 else (1 if v > 0 else -1)


def _punto_comun(p1, p2, q1, q2, eps=1e-12):
    """Punto donde se tocan dos segmentos (también en un extremo), o None. Si son colineales y se solapan, el centro
    del solape."""
    rx, ry = p2[0] - p1[0], p2[1] - p1[1]
    sx, sy = q2[0] - q1[0], q2[1] - q1[1]
    d = rx * sy - ry * sx
    wx, wy = q1[0] - p1[0], q1[1] - p1[1]
    if abs(d) < eps:
        if _orientacion(p1, p2, q1) != 0:
            return None                                   # paralelos
        rr = rx * rx + ry * ry
        if rr < eps:
            return None
        t0 = (wx * rx + wy * ry) / rr
        t1 = ((q2[0] - p1[0]) * rx + (q2[1] - p1[1]) * ry) / rr
        lo, hi = max(0.0, min(t0, t1)), min(1.0, max(t0, t1))
        if lo > hi + 1e-9:
            return None
        t = (lo + hi) / 2
        return p1[0] + t * rx, p1[1] + t * ry
    t = (wx * sy - wy * sx) / d
    u = (wx * ry - wy * rx) / d
    if -1e-9 <= t <= 1 + 1e-9 and -1e-9 <= u <= 1 + 1e-9:
        return p1[0] + t * rx, p1[1] + t * ry
    return None


def _clave(p):
    return round(p[0], 7), round(p[1], 7)


def _caja_de(puntos):
    xs, ys = [p[0] for p in puntos], [p[1] for p in puntos]
    return min(xs), max(xs), min(ys), max(ys)


def cruces(polilineas):
    """Número de cruces de un dibujo (cada arista o tramo es una polilínea [(x, y), ...]): para cada par de polilíneas,
    los puntos DISTINTOS donde se tocan, salvo los que son extremo de las dos (salir o llegar al mismo puerto o al
    mismo punto de unión no es un cruce). Un corte justo en un vértice de la polilínea cuenta una vez; que una arista
    toque otra por el medio, también. O(S²) en el número de segmentos, con descarte por rectángulo envolvente."""
    lineas = [list(p) for p in polilineas if p and len(p) >= 2]
    cajas = [_caja_de(p) for p in lineas]
    total = 0
    for i in range(len(lineas)):
        ax0, ax1, ay0, ay1 = cajas[i]
        for j in range(i + 1, len(lineas)):
            bx0, bx1, by0, by1 = cajas[j]
            if ax1 < bx0 - 1e-9 or bx1 < ax0 - 1e-9 or ay1 < by0 - 1e-9 or by1 < ay0 - 1e-9:
                continue
            a, b = lineas[i], lineas[j]
            extremos = {_clave(a[0]), _clave(a[-1])} & {_clave(b[0]), _clave(b[-1])}
            puntos = set()
            for k in range(len(a) - 1):
                for m in range(len(b) - 1):
                    p = _punto_comun(a[k], a[k + 1], b[m], b[m + 1])
                    if p is not None:
                        puntos.add(_clave(p))
            total += len(puntos - extremos)
    return total


def atraviesa(p, q, caja, holgura=1e-6):
    """¿El segmento p-q pasa por DENTRO de la caja (x, y, ancho, alto)? Recorte de Liang-Barsky contra el rectángulo
    (encogido `holgura` para que rozar el borde, como hace un puerto, no cuente)."""
    x, y, w, h = caja
    x0, x1 = x - w / 2 + holgura, x + w / 2 - holgura
    y0, y1 = y - h / 2 + holgura, y + h / 2 - holgura
    dx, dy = q[0] - p[0], q[1] - p[1]
    t0, t1 = 0.0, 1.0
    for d, lo, hi, v in ((dx, x0, x1, p[0]), (dy, y0, y1, p[1])):
        if abs(d) < 1e-15:
            if v <= lo or v >= hi:
                return False
            continue
        ta, tb = (lo - v) / d, (hi - v) / d
        if ta > tb:
            ta, tb = tb, ta
        t0, t1 = max(t0, ta), min(t1, tb)
        if t0 >= t1:
            return False
    return t1 - t0 > 1e-9
