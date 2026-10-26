# Generación del barrio con índices espaciales (datos puros, sin ursina): las MISMAS reglas y el MISMO azar que
# barrio_favela.py y ciudad_3d.py, pero cada consulta mira solo los vecinos cercanos en vez de recorrer todas las
# calles, plazas, cajas y líneas. Con ~5000 casas los recorridos lineales de antes se vuelven el cuello de botella.
#
# Todo esto es ADITIVO: nada del código existente cambia salvo el parámetro `fabrica_barrio` de
# barrio_favela.generar_casas. Con estas clases el mundo chico sale IDÉNTICO (mismas casas en el mismo orden, mismos
# obstáculos, callejones y escaleras): lo comprueba tests/test_barrio_indexado.py.
#
#   _BarrioIndexado(_Barrio)   permite / distancia_a_la_red / rumbo_hacia_la_red con índice (pasar como fabrica_barrio).
#   _DespejeIndexado(_Despeje) permite con índice de líneas libres, spawns y edificios (pasar como `despeje`).
#   vegetacion_indexada        = ciudad_3d._vegetacion_barrio sin listas nuevas por intento.
#   escaleras_callejon_indexadas = ciudad_3d._escaleras_de_callejones con índice y tope configurable.
#   quitar_bolsas_por_chunk    = barrio_favela.quitar_bolsas sin rejilla global de 0,5 m: barrido por bandas de
#                                chunk con tramos libres por fila y unión de tramos (no hay 2,7 M de celdas).
#   zonas_por_anclaje          = barrio_favela.zonas_abiertas con búsqueda indexada y, opcional, en torno a anclajes.
#   generar_barrio_indexado    = la parte «denso» de construir_mundo_3d con todo lo anterior.
#
# La evaluación de la altura del terreno es lo más caro que queda: se hace SOLO por Terreno.altura(x, z) (así otra
# clase de terreno más rápida entra sin tocar nada de aquí).

import math
from bisect import bisect_right
from dataclasses import dataclass, replace

from backend.datos import barrio_favela
from backend.datos._rejilla_barrio import RejillaBarrio
from backend.datos.barrio_favela import (
    ACERA_CALLE,
    CALLEJON_MIN,
    DESNIVEL_LOTE,
    DESPEJE_EDIFICIO,
    DESPEJE_ZONA,
    EASTER_EGGS,
    MERCADO,
    RINCON_SECRETO,
    SECRETOS,
    CUADRANTES_SECRETOS,
    CANCHA,
    LEJOS_SECRETO,
    _Barrio,
    _caja,
    _cajas_cerca,
    _punto_mas_cercano,
    _separacion,
)
from backend.datos.ciudad_3d import (
    ESCALERAS_CALLEJON,
    DESNIVEL_ESCALERA_CALLEJON,
    ESPACIO_EDIFICIO,
    ESPACIO_LIBRE,
    BORDE_LADERA,
    TIPOS_VEGETACION_BARRIO,
    CANTIDAD_VEGETACION_BARRIO,
    SEMILLA_CASAS,
    _Despeje,
    _caja as _caja_obstaculo,
    _distancia_a_punto,
    _distancia_a_segmento,
    _distancia_entre_segmentos,
    _separacion as _separacion_obstaculos,
    _separacion_con_edificio,
)
from backend.grafos.mapa_ciudad import _distancia_punto_segmento
from backend.logica.mundo_ciudad import (
    RADIO_JUGADOR,
    CasaDecorativa,
    Escalera,
    Obstaculo,
    Zona,
    _distancia_punto_caja,
    _distancia_segmento_caja,
)
import random

# -- Cantidades del barrio grande --
CANTIDAD_BARRIO_GRANDE = 5200      # tope de casas del barrio grande (900 x 650 m); el relleno real queda en 3500-5200
ESCALERAS_CALLEJON_GRANDE = 200    # tope de escaleras de callejón del barrio grande (22 en el mundo chico)
CELDA_INDICE = 16.0                # m de lado de las celdas de los índices
RADIO_INICIAL = 24.0               # m del primer anillo de la búsqueda del más cercano (se duplica hasta acertar)
MAX_CELDAS_ANILLO = 4096           # si un anillo toca más celdas que esto, se recorre todo (red pequeña o punto lejano)
CHUNK = 64.0                       # m de alto de cada banda del barrido de bolsas
RADIO_ANCLAJE = 120.0              # m de la ventana de búsqueda alrededor de un anclaje (zonas_por_anclaje)


def _bbox_obstaculo(o):
    if o.es_circulo:
        return (o.cx - o.radio, o.cx + o.radio, o.cz - o.radio, o.cz + o.radio)
    return _caja_obstaculo(o)


def _ensanchar(caja, m):
    return (caja[0] - m, caja[1] + m, caja[2] - m, caja[3] + m)


# -- Barrio ------------------------------------------------------------------------------------------


class _BarrioIndexado(_Barrio):
    """_Barrio con la red de calles y plazas, los edificios y las zonas en índices espaciales. Mismas decisiones."""

    def __init__(self, mapa, edificios, despeje, previos, terreno, zonas, limites):
        super().__init__(mapa, edificios, despeje, previos, terreno, zonas, limites)
        # plazas e índices 0..P-1, calles P..P+C-1 (el orden de _Barrio.rumbo_hacia_la_red: plazas primero)
        self._n_plazas = len(self.plazas)
        self._red = RejillaBarrio(CELDA_INDICE)
        self._plazas_idx = RejillaBarrio(CELDA_INDICE)
        self._calles_idx = RejillaBarrio(CELDA_INDICE)
        for k, (px, pz) in enumerate(self.plazas):
            self._red.insertar_punto(k, px, pz)
            self._plazas_idx.insertar_punto(k, px, pz)
        for k, (a, b) in enumerate(self.calles):
            self._red.insertar_segmento(self._n_plazas + k, a, b)
            self._calles_idx.insertar_segmento(k, a, b)
        self._edificios_idx = RejillaBarrio(CELDA_INDICE)
        for k, caja in enumerate(self.cajas_edificios):
            self._edificios_idx.insertar_caja(k, caja)
        self._zonas_idx = RejillaBarrio(CELDA_INDICE)
        for k, caja in enumerate(self.cajas_zonas):
            self._zonas_idx.insertar_caja(k, caja)

    # El elemento de la red más cercano a (x, z) según `medida(k)`; los empates los gana el de menor índice (como
    # min() sobre la lista plazas + calles). Anillos que se duplican: con el elemento más cercano a distancia <= r,
    # ninguno fuera del anillo puede ser mejor, así que el resultado es exacto.
    def _mas_cercano_red(self, x, z, medida):
        r = RADIO_INICIAL
        while True:
            if self._red.numero_de_celdas(x - r, x + r, z - r, z + r) > MAX_CELDAS_ANILLO:
                ids = range(self._n_plazas + len(self.calles))
                ultimo = True
            else:
                ids = sorted(self._red.cerca(x - r, x + r, z - r, z + r))
                ultimo = False
            mejor, mejor_id = math.inf, None
            for k in ids:
                d = medida(k)
                if d < mejor:
                    mejor, mejor_id = d, k
            if mejor_id is not None and (mejor <= r or ultimo):
                return mejor_id, mejor
            if ultimo:
                return None, math.inf
            r *= 2

    def distancia_a_la_red(self, x, z):
        p = (x, z)
        plazas, calles, n = self.plazas, self.calles, self._n_plazas

        def medida(k):
            if k < n:
                return math.dist(p, plazas[k])
            a, b = calles[k - n]
            return _distancia_punto_segmento(p, a, b)

        return self._mas_cercano_red(x, z, medida)[1]

    def rumbo_hacia_la_red(self, x, z):
        p = (x, z)
        plazas, calles, n = self.plazas, self.calles, self._n_plazas

        def punto(k):
            return plazas[k] if k < n else _punto_mas_cercano(p, *calles[k - n])

        k, _ = self._mas_cercano_red(x, z, lambda k: math.dist(p, punto(k)))
        px, pz = punto(k)
        return (round(math.degrees(math.atan2(px - x, pz - z)) / 90) * 90) % 360

    def permite(self, casa):
        caja = _caja(casa)
        xmin, xmax, zmin, zmax = self.limites
        if caja[0] < xmin or caja[1] > xmax or caja[2] < zmin or caja[3] > zmax:
            return False
        m = self.radio_plaza
        for k in self._plazas_idx.cerca(caja[0] - m, caja[1] + m, caja[2] - m, caja[3] + m):
            px, pz = self.plazas[k]
            if _distancia_punto_caja(px, pz, caja) < m:
                return False
        m = self.semiancho_calle
        for k in self._calles_idx.cerca(caja[0] - m, caja[1] + m, caja[2] - m, caja[3] + m):
            a, b = self.calles[k]
            if _distancia_segmento_caja(a, b, caja) < m:
                return False
        m = DESPEJE_EDIFICIO
        for k in self._edificios_idx.cerca(caja[0] - m, caja[1] + m, caja[2] - m, caja[3] + m):
            if _cajas_cerca(caja, self.cajas_edificios[k], m):
                return False
        m = DESPEJE_ZONA
        for k in self._zonas_idx.cerca(caja[0] - m, caja[1] + m, caja[2] - m, caja[3] + m):
            if _cajas_cerca(caja, self.cajas_zonas[k], m):
                return False
        if not self.despeje.permite(casa):
            return False
        for o in self.cercanos(casa.cx, casa.cz):
            if _separacion(o, casa) < (CALLEJON_MIN if isinstance(o, CasaDecorativa) else 1.0):
                return False
        alturas = [self.terreno.altura(x, z) for x in (caja[0], casa.cx, caja[1]) for z in (caja[2], casa.cz, caja[3])]
        return max(alturas) - min(alturas) <= DESNIVEL_LOTE


# -- Despeje -------------------------------------------------------------------------------------------


class _DespejeIndexado(_Despeje):
    """_Despeje con índices de líneas libres, spawns y edificios. agregar_linea actualiza el índice."""

    def __init__(self, mapa, edificios, spawns):
        super().__init__(mapa, edificios, spawns)
        self._lineas_idx = RejillaBarrio(CELDA_INDICE)
        for k, (a, b) in enumerate(self._lineas):
            self._lineas_idx.insertar_segmento(k, a, b)
        self._spawns_idx = RejillaBarrio(CELDA_INDICE)
        for k, (x, z) in enumerate(self._spawns):
            self._spawns_idx.insertar_punto(k, x, z)
        self._edificios_idx = RejillaBarrio(CELDA_INDICE)
        for k, e in enumerate(self._edificios):
            self._edificios_idx.insertar_caja(k, _caja_obstaculo(e))

    def agregar_linea(self, a, b):
        super().agregar_linea(a, b)
        self._lineas_idx.insertar_segmento(len(self._lineas) - 1, a, b)

    def permite(self, obstaculo):
        x0, x1, z0, z1 = _bbox_obstaculo(obstaculo)
        m = ESPACIO_LIBRE + 1e-6
        for k in self._lineas_idx.cerca(x0 - m, x1 + m, z0 - m, z1 + m):
            a, b = self._lineas[k]
            if _distancia_a_segmento(obstaculo, a, b) < ESPACIO_LIBRE:
                return False
        for k in self._spawns_idx.cerca(x0 - m, x1 + m, z0 - m, z1 + m):
            x, z = self._spawns[k]
            if _distancia_a_punto(obstaculo, x, z) < ESPACIO_LIBRE:
                return False
        m = ESPACIO_EDIFICIO + 1e-6
        for k in self._edificios_idx.cerca(x0 - m, x1 + m, z0 - m, z1 + m):
            if _separacion_con_edificio(obstaculo, self._edificios[k]) < ESPACIO_EDIFICIO:
                return False
        return True


# -- Vegetación ----------------------------------------------------------------------------------------


def vegetacion_indexada(mapa, despeje, ocupados, terreno, cantidad=CANTIDAD_VEGETACION_BARRIO,
                        semilla=SEMILLA_CASAS + 1, zonas=()):
    """Igual que ciudad_3d._vegetacion_barrio (mismo azar y mismas reglas), con índices para las plazas, las calles,
    las zonas y lo ya ocupado (más las plantas nuevas): sin construir `ocupados + plantas` en cada intento."""
    azar = random.Random(semilla)
    calles = [(mapa.coordenada(a), mapa.coordenada(b)) for a, b in mapa.segmentos()]
    plazas = [mapa.coordenada(lugar) for lugar in mapa.lugares()]
    x0, x1, z0, z1 = terreno.extension
    idx_plazas, idx_calles = RejillaBarrio(CELDA_INDICE), RejillaBarrio(CELDA_INDICE)
    for k, (px, pz) in enumerate(plazas):
        idx_plazas.insertar_punto(k, px, pz)
    for k, (a, b) in enumerate(calles):
        idx_calles.insertar_segmento(k, a, b)
    cajas_zonas = [z.caja() for z in zonas]
    idx_zonas = RejillaBarrio(CELDA_INDICE)
    for k, caja in enumerate(cajas_zonas):
        idx_zonas.insertar_caja(k, caja)
    todos = list(ocupados)                # ocupados + plantas aceptadas, en ese orden
    idx_todos = RejillaBarrio(CELDA_INDICE)
    for k, o in enumerate(todos):
        idx_todos.insertar_caja(k, _bbox_obstaculo(o))
    plantas = []
    for _ in range(cantidad * 60):
        if len(plantas) >= cantidad:
            break
        x = round(azar.uniform(x0 + BORDE_LADERA, x1 - BORDE_LADERA), 2)
        z = round(azar.uniform(z0 + BORDE_LADERA, z1 - BORDE_LADERA), 2)
        u, acumulado = azar.random(), 0.0
        tipo, radio = TIPOS_VEGETACION_BARRIO[-1][0], TIPOS_VEGETACION_BARRIO[-1][2]
        for nombre, proporcion, r in TIPOS_VEGETACION_BARRIO:
            acumulado += proporcion
            if u < acumulado:
                tipo, radio = nombre, r
                break
        planta = Obstaculo(tipo, x, z, radio=radio)
        m = mapa.radio_plaza + 0.9 + 1.0 + planta.radio
        if any(math.dist((x, z), plazas[k]) < m for k in idx_plazas.cerca(x - m, x + m, z - m, z + m)):
            continue
        m = mapa.ancho_calle / 2 + 2.0 + 0.5 + planta.radio
        if any(_distancia_punto_segmento((x, z), *calles[k]) < m for k in idx_calles.cerca(x - m, x + m, z - m, z + m)):
            continue
        if not despeje.permite(planta):
            continue
        m = planta.radio + 1.0
        if any(_distancia_punto_caja(x, z, cajas_zonas[k]) < m for k in idx_zonas.cerca(x - m, x + m, z - m, z + m)):
            continue
        m = 1.6
        caja = _bbox_obstaculo(planta)
        if any(_separacion_obstaculos(planta, todos[k]) < m
               for k in idx_todos.cerca(caja[0] - m, caja[1] + m, caja[2] - m, caja[3] + m)):
            continue
        plantas.append(planta)
        idx_todos.insertar_caja(len(todos), caja)
        todos.append(planta)
    return plantas


# -- Escaleras de los callejones -----------------------------------------------------------------------


def escaleras_callejon_indexadas(callejones, escaleras, terreno, maximo=ESCALERAS_CALLEJON):
    """Igual que ciudad_3d._escaleras_de_callejones (mismo orden y mismas reglas) pero la separación con las demás
    escaleras (2,5 m) se consulta en un índice: O(candidatas) en vez de O(candidatas x nuevas). `maximo` es el tope
    (ESCALERAS_CALLEJON_GRANDE = 200 en el barrio grande)."""
    candidatas = []
    for c in callejones:
        if c.largo < 5.0 or c.ancho > 3.0:
            continue
        desnivel = abs(terreno.altura(c.bx, c.bz) - terreno.altura(c.ax, c.az))
        if desnivel >= DESNIVEL_ESCALERA_CALLEJON:
            candidatas.append((desnivel, c))
    candidatas.sort(key=lambda t: -t[0])
    todas = list(escaleras)
    idx = RejillaBarrio(CELDA_INDICE)
    for k, e in enumerate(todas):
        idx.insertar_segmento(k, (e.ax, e.az), (e.bx, e.bz))
    nuevas = []
    m = 2.5
    for _, c in candidatas:
        ux, uz = (c.bx - c.ax) / c.largo, (c.bz - c.az) / c.largo
        mx, mz = (c.ax + c.bx) / 2, (c.az + c.bz) / 2
        largo = min(c.largo - 1.0, 7.0)
        if terreno.altura(c.bx, c.bz) < terreno.altura(c.ax, c.az):
            ux, uz = -ux, -uz
        a = (round(mx - ux * largo / 2, 2), round(mz - uz * largo / 2, 2))
        b = (round(mx + ux * largo / 2, 2), round(mz + uz * largo / 2, 2))
        ancho = round(max(0.9, min(1.4, c.ancho - 0.6)), 2)
        x0, x1 = min(a[0], b[0]) - m, max(a[0], b[0]) + m
        z0, z1 = min(a[1], b[1]) - m, max(a[1], b[1]) + m
        if any(_distancia_entre_segmentos(a, b, (todas[k].ax, todas[k].az), (todas[k].bx, todas[k].bz)) < m
               for k in idx.cerca(x0, x1, z0, z1)):
            continue
        nueva = Escalera(a[0], a[1], b[0], b[1], ancho)
        idx.insertar_segmento(len(todas), a, b)
        todas.append(nueva)
        nuevas.append(nueva)
        if len(nuevas) >= maximo:
            break
    return nuevas


# -- Bolsas aisladas ------------------------------------------------------------------------------------


class _Tramos:
    """Tramos libres por fila de la rejilla virtual (sin crear la rejilla) y unión de tramos vecinos."""

    def __init__(self, nx, nz):
        self.nx, self.nz = nx, nz
        self.inicios = [None] * nz        # por fila: columnas donde empieza cada tramo libre
        self.fines = [None] * nz
        self.ids = [None] * nz
        self.padre = []

    def raiz(self, k):
        p = self.padre
        while p[k] != k:
            p[k] = p[p[k]]
            k = p[k]
        return k

    def unir(self, a, b):
        ra, rb = self.raiz(a), self.raiz(b)
        if ra != rb:
            self.padre[max(ra, rb)] = min(ra, rb)

    def libre(self, i, j):
        if not (0 <= i < self.nx and 0 <= j < self.nz):
            return False
        ini = self.inicios[j]
        t = bisect_right(ini, i) - 1
        return t >= 0 and i <= self.fines[j][t]

    def tramo_en(self, i, j):
        ini = self.inicios[j]
        t = bisect_right(ini, i) - 1
        return self.ids[j][t]


def _intervalo_bloqueado(caja, radio, x0, paso, i_min, i_max, z):
    # columnas [lo, hi] de la fila `z` con distancia a la caja < radio (la condición exacta de Rejilla.bloquear_caja)
    dz = max(caja[2] - z, 0.0, z - caja[3])
    if dz >= radio:
        return None
    hx = math.sqrt(max(0.0, radio * radio - dz * dz))
    lo = max(i_min, int(math.ceil((caja[0] - hx - x0) / paso)) - 1)
    hi = min(i_max, int(math.floor((caja[1] + hx - x0) / paso)) + 1)
    while lo <= hi and not _distancia_punto_caja(x0 + lo * paso, z, caja) < radio:
        lo += 1
    while hi >= lo and not _distancia_punto_caja(x0 + hi * paso, z, caja) < radio:
        hi -= 1
    return (lo, hi) if lo <= hi else None


def _tramos_libres(cajas, limites, resolucion, radio, chunk):
    """Las celdas libres de Rejilla(limites, resolucion) tras bloquear cada caja con `radio`, como tramos por fila.
    Se barre por bandas de `chunk` m consultando solo las cajas de cada banda; nunca existe la rejilla completa."""
    xmin, xmax, zmin, zmax = limites
    nx = int(math.floor((xmax - xmin) / resolucion)) + 1
    nz = int(math.floor((zmax - zmin) / resolucion)) + 1
    tramos = _Tramos(nx, nz)
    indice = RejillaBarrio(CELDA_INDICE)
    for k, caja in enumerate(cajas):
        indice.insertar_caja(k, caja)
    filas_banda = max(1, int(chunk / resolucion))
    previa = None                                     # (inicios, fines, ids) de la fila anterior
    for j0 in range(0, nz, filas_banda):
        j1 = min(nz - 1, j0 + filas_banda - 1)
        z_a, z_b = zmin + j0 * resolucion - radio, zmin + j1 * resolucion + radio
        intervalos = {}
        for k in indice.cerca(xmin - radio, xmax + radio, z_a, z_b):
            caja = cajas[k]
            fa = max(j0, 0, int(math.ceil((caja[2] - radio - zmin) / resolucion)))
            fb = min(j1, nz - 1, int(math.floor((caja[3] + radio - zmin) / resolucion)))
            ia = max(0, int(math.ceil((caja[0] - radio - xmin) / resolucion)))
            ib = min(nx - 1, int(math.floor((caja[1] + radio - xmin) / resolucion)))
            if ia > ib:
                continue
            for j in range(fa, fb + 1):
                z = zmin + j * resolucion
                iv = _intervalo_bloqueado(caja, radio, xmin, resolucion, ia, ib, z)
                if iv is not None:
                    intervalos.setdefault(j, []).append(iv)
        for j in range(j0, j1 + 1):
            libres = _invertir(sorted(intervalos.get(j, ())), nx)
            ini = [t[0] for t in libres]
            fin = [t[1] for t in libres]
            ids = list(range(len(tramos.padre), len(tramos.padre) + len(libres)))
            tramos.padre.extend(ids)
            tramos.inicios[j], tramos.fines[j], tramos.ids[j] = ini, fin, ids
            if previa is not None:
                _unir_filas(tramos, previa, (ini, fin, ids))
            previa = (ini, fin, ids)
    return tramos


def _invertir(bloqueados, nx):
    libres, desde = [], 0
    for lo, hi in bloqueados:
        if lo > desde:
            libres.append((desde, lo - 1))
        if hi + 1 > desde:
            desde = hi + 1
    if desde <= nx - 1:
        libres.append((desde, nx - 1))
    return libres


# Vecindad de 4: la diagonal solo vale si sus dos celdas laterales están libres, así que no añade conexiones.
def _unir_filas(tramos, previa, actual):
    pi, pf, pid = previa
    ci, cf, cid = actual
    a = b = 0
    while a < len(pi) and b < len(ci):
        if pf[a] < ci[b]:
            a += 1
        elif cf[b] < pi[a]:
            b += 1
        else:
            tramos.unir(pid[a], cid[b])
            if pf[a] <= cf[b]:
                a += 1
            else:
                b += 1


def quitar_bolsas_por_chunk(casas, fijos, semilla_xz, limites, resolucion=0.5, maximo_vueltas=6, chunk=CHUNK):
    """Igual que barrio_favela.quitar_bolsas (mismo resultado) sin la rejilla global: las celdas libres se agrupan
    en tramos por fila, barridos por bandas de `chunk` m con las cajas de cada banda sacadas de un índice, y los
    tramos se unen entre filas. Las celdas libres que no se alcanzan desde `semilla_xz` quitan la casa más cercana
    si está a menos de 2 m (se vuelve a barrer, hasta `maximo_vueltas`)."""
    casas = list(casas)
    xmin, xmax, zmin, zmax = limites
    for _ in range(maximo_vueltas):
        cajas = list(fijos) + [_caja(c) for c in casas]
        tramos = _tramos_libres(cajas, limites, resolucion, RADIO_JUGADOR, chunk)
        raiz_semilla = _raiz_de_la_semilla(tramos, semilla_xz, limites, resolucion)
        indice = RejillaBarrio(CELDA_INDICE)
        for k, c in enumerate(casas):
            indice.insertar_caja(k, _caja(c))
        quitar, hay_aisladas = set(), False
        for j in range(tramos.nz):
            z = zmin + j * resolucion
            for ini, fin, ident in zip(tramos.inicios[j], tramos.fines[j], tramos.ids[j]):
                if raiz_semilla is not None and tramos.raiz(ident) == raiz_semilla:
                    continue
                hay_aisladas = True
                for i in range(ini, fin + 1):
                    x = xmin + i * resolucion
                    mejor, mejor_k = math.inf, None
                    for k in sorted(indice.cerca(x - 2.0, x + 2.0, z - 2.0, z + 2.0)):
                        d = _distancia_punto_caja(x, z, _caja(casas[k]))
                        if d < mejor:
                            mejor, mejor_k = d, k
                    if mejor_k is not None and mejor < 2.0:
                        quitar.add(mejor_k)
        if not hay_aisladas:
            return casas
        if not quitar:
            return casas
        casas = [c for k, c in enumerate(casas) if k not in quitar]
    return casas


# Raíz del tramo de la celda libre más cercana a la semilla (como Rejilla._libre_cercana con maximo = 1 m).
def _raiz_de_la_semilla(tramos, semilla_xz, limites, resolucion):
    i = int(round((semilla_xz[0] - limites[0]) / resolucion))
    j = int(round((semilla_xz[1] - limites[2]) / resolucion))
    if not (0 <= i < tramos.nx and 0 <= j < tramos.nz):
        return None
    radio = int(math.ceil(1.0 / resolucion))
    mejor = None
    for dj in range(-radio, radio + 1):
        for di in range(-radio, radio + 1):
            if tramos.libre(i + di, j + dj):
                d = di * di + dj * dj
                if mejor is None or d < mejor[0]:
                    mejor = (d, i + di, j + dj)
    if mejor is None:
        return None
    return tramos.raiz(tramos.tramo_en(mejor[1], mejor[2]))


# -- Zonas abiertas por anclaje ---------------------------------------------------------------------------


class _RedIndexada:
    """Calles, plazas y cajas ocupadas en índices para las pruebas de «caja libre» de las zonas."""

    def __init__(self, mapa, ocupadas):
        self.mapa = mapa
        self.calles = [(mapa.coordenada(a), mapa.coordenada(b)) for a, b in mapa.segmentos()]
        self.plazas = [mapa.coordenada(lugar) for lugar in mapa.lugares()]
        self.ocupadas = list(ocupadas)
        self.i_calles, self.i_plazas, self.i_ocupadas = (RejillaBarrio(CELDA_INDICE) for _ in range(3))
        for k, (a, b) in enumerate(self.calles):
            self.i_calles.insertar_segmento(k, a, b)
        for k, (px, pz) in enumerate(self.plazas):
            self.i_plazas.insertar_punto(k, px, pz)
        for k, caja in enumerate(self.ocupadas):
            self.i_ocupadas.insertar_caja(k, caja)

    def caja_libre(self, caja, lejos):
        m = self.mapa.radio_plaza + 0.9 + lejos
        for k in self.i_plazas.cerca(caja[0] - m, caja[1] + m, caja[2] - m, caja[3] + m):
            if _distancia_punto_caja(*self.plazas[k], caja) < m:
                return False
        m = self.mapa.ancho_calle / 2 + ACERA_CALLE + lejos
        for k in self.i_calles.cerca(caja[0] - m, caja[1] + m, caja[2] - m, caja[3] + m):
            if _distancia_segmento_caja(*self.calles[k], caja) < m:
                return False
        m = lejos
        for k in self.i_ocupadas.cerca(caja[0] - m, caja[1] + m, caja[2] - m, caja[3] + m):
            if _cajas_cerca(caja, self.ocupadas[k], lejos):
                return False
        return True

    def cerca_de_calle(self, caja, margen):
        m = margen
        return any(_distancia_segmento_caja(*self.calles[k], caja) < m
                   for k in self.i_calles.cerca(caja[0] - m, caja[1] + m, caja[2] - m, caja[3] + m))

    def cerca_de_plaza(self, caja, margen):
        m = margen
        return any(_distancia_punto_caja(*self.plazas[k], caja) < m
                   for k in self.i_plazas.cerca(caja[0] - m, caja[1] + m, caja[2] - m, caja[3] + m))

    def cerca_de_ocupada(self, caja, margen):
        m = margen
        return any(_cajas_cerca(caja, self.ocupadas[k], m)
                   for k in self.i_ocupadas.cerca(caja[0] - m, caja[1] + m, caja[2] - m, caja[3] + m))


# Igual que barrio_favela.buscar_zona_plana (mismas posiciones, mismo desempate) con la prueba de caja libre
# indexada. `ventana` (x0, x1, z0, z1) opcional: solo se evalúan los centros dentro de ella.
def buscar_zona_plana_indexada(mapa, ocupadas, suelo, limites, largo, ancho, lejos, cerca=None, evitar=(),
                               paso=2.0, ventana=None, red=None):
    xmin, xmax, zmin, zmax = limites
    red = red or _RedIndexada(mapa, list(ocupadas) + list(evitar))
    mejor = None
    for ancho_x, fondo_z in ((largo, ancho), (ancho, largo)):
        x = xmin + ancho_x / 2 + 1
        while x <= xmax - ancho_x / 2 - 1:
            if ventana is None or ventana[0] <= x <= ventana[1]:
                z = zmin + fondo_z / 2 + 1
                while z <= zmax - fondo_z / 2 - 1:
                    if ventana is None or ventana[2] <= z <= ventana[3]:
                        caja = (x - ancho_x / 2, x + ancho_x / 2, z - fondo_z / 2, z + fondo_z / 2)
                        if red.caja_libre(caja, lejos):
                            alturas = [suelo(px, pz) for px in (caja[0], x, caja[1]) for pz in (caja[2], z, caja[3])]
                            desnivel = round((max(alturas) - min(alturas)) * 4) / 4
                            cercania = math.dist((x, z), cerca) if cerca else 0.0
                            clave = (desnivel, cercania)
                            if mejor is None or clave < mejor[0]:
                                mejor = (clave, (x, z, ancho_x, fondo_z))
                    z += paso
            x += paso
    return mejor[1] if mejor else None


def _ventana(centro, radio, limites):
    return (max(limites[0], centro[0] - radio), min(limites[1], centro[0] + radio),
            max(limites[2], centro[1] - radio), min(limites[3], centro[1] + radio))


def _mercado_indexado(mapa, red, suelo, limites, ancla=None, radio=None):
    # barrio_favela._mercado_junto_a_calle con las pruebas indexadas; con `ancla` y `radio`, solo prueba las calles
    # cuyo punto medio queda a menos de `radio` del anclaje (el orden de las calles se conserva).
    xmin, xmax, zmin, zmax = limites
    mejor = None
    for a, b in red.calles:
        if ancla is not None and radio is not None and math.dist(ancla, ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)) > radio:
            continue
        largo = math.dist(a, b)
        if largo < 1e-9:
            continue
        ux, uz = (b[0] - a[0]) / largo, (b[1] - a[1]) / largo
        for lado in (-1, 1):
            for t in (0.4, 0.5, 0.6):
                for ancho_x, fondo_z in ((MERCADO[0], MERCADO[1]), (MERCADO[1], MERCADO[0])):
                    mitad = ancho_x / 2 * abs(uz) + fondo_z / 2 * abs(ux)
                    d = mapa.ancho_calle / 2 + ACERA_CALLE + 1.0 + mitad
                    cx = a[0] + ux * largo * t - uz * lado * d
                    cz = a[1] + uz * largo * t + ux * lado * d
                    caja = (cx - ancho_x / 2, cx + ancho_x / 2, cz - fondo_z / 2, cz + fondo_z / 2)
                    if not (xmin + 1 <= caja[0] and caja[1] <= xmax - 1 and zmin + 1 <= caja[2] and caja[3] <= zmax - 1):
                        continue
                    if red.cerca_de_plaza(caja, mapa.radio_plaza + 0.9 + 1.0):
                        continue
                    if red.cerca_de_calle(caja, mapa.ancho_calle / 2 + ACERA_CALLE + 0.5):
                        continue
                    if red.cerca_de_ocupada(caja, 1.5):
                        continue
                    alturas = [suelo(x, z) for x in (caja[0], cx, caja[1]) for z in (caja[2], cz, caja[3])]
                    desnivel = max(alturas) - min(alturas)
                    if mejor is None or desnivel < mejor[0]:
                        mejor = (desnivel, Zona("mercado", round(cx, 2), round(cz, 2), ancho_x, fondo_z))
    return mejor[1] if mejor else None


def zonas_por_anclaje(mapa, edificios, suelo, limites, anclajes=None, radio=RADIO_ANCLAJE):
    """Las zonas abiertas del barrio (cancha, mercadito y, con EASTER_EGGS, los rincones secretos), con la prueba de
    «sitio libre» indexada. Sin `anclajes` da EXACTAMENTE lo mismo que barrio_favela.zonas_abiertas. `anclajes` es
    {tipo: (x, z)} con tipo en 'cancha', 'mercado', 'puesto_talco', 'armeria_juguete': esa zona se busca solo en una
    ventana de `radio` m alrededor de su anclaje (y se desempata hacia él); si allí no cabe, se busca en todo el
    mapa. Sin ventana, el barrido de 2 m sobre 900 x 650 m sería el cuello de botella."""
    anclajes = anclajes or {}
    ocupadas = [e.caja() for e in edificios]
    zonas = []

    def buscar(tipo, largo, ancho, lejos, cerca_defecto, ocupadas_ahora, limites_busqueda):
        red = _RedIndexada(mapa, ocupadas_ahora)
        ancla = anclajes.get(tipo)
        if ancla is not None:
            ventana = _ventana(ancla, radio, limites)
            sitio = buscar_zona_plana_indexada(mapa, ocupadas_ahora, suelo, limites, largo, ancho, lejos,
                                               cerca=ancla, ventana=ventana, red=red)
            if sitio:
                return sitio
        return buscar_zona_plana_indexada(mapa, ocupadas_ahora, suelo, limites_busqueda, largo, ancho, lejos,
                                          cerca=cerca_defecto, red=red)

    praza = mapa.coordenada("Praça da Sé") if "Praça da Sé" in mapa.lugares() else None
    cancha = buscar("cancha", CANCHA[0], CANCHA[1], 3.0, praza, ocupadas, limites)
    if cancha:
        zonas.append(Zona("cancha", round(cancha[0], 2), round(cancha[1], 2), cancha[2], cancha[3]))
    ocupadas2 = ocupadas + [z.caja() for z in zonas]
    red_mercado = _RedIndexada(mapa, ocupadas2)
    mercado = _mercado_indexado(mapa, red_mercado, suelo, limites, anclajes.get("mercado"), radio)
    if mercado is None and anclajes.get("mercado") is not None:
        mercado = _mercado_indexado(mapa, red_mercado, suelo, limites)
    if mercado:
        zonas.append(mercado)
    if EASTER_EGGS:
        xmin, xmax, zmin, zmax = limites
        ancho_l, alto_l = xmax - xmin, zmax - zmin
        rincones = []
        for tipo, (fx0, fx1, fz0, fz1) in zip(SECRETOS, CUADRANTES_SECRETOS):
            cuadrante = (xmin + ancho_l * fx0, xmin + ancho_l * fx1, zmin + alto_l * fz0, zmin + alto_l * fz1)
            arriba = ((cuadrante[0] + cuadrante[1]) / 2, cuadrante[3])
            ocupadas_ahora = ocupadas + [z.caja() for z in zonas] + [r.caja() for r in rincones]
            red = _RedIndexada(mapa, ocupadas_ahora)
            sitio = None
            ancla = anclajes.get(tipo)
            if ancla is not None:
                sitio = buscar_zona_plana_indexada(mapa, ocupadas_ahora, suelo, limites, *RINCON_SECRETO,
                                                   lejos=LEJOS_SECRETO, cerca=ancla,
                                                   ventana=_ventana(ancla, radio, limites), red=red)
            if sitio is None:
                sitio = buscar_zona_plana_indexada(mapa, ocupadas_ahora, suelo, cuadrante, *RINCON_SECRETO,
                                                   lejos=LEJOS_SECRETO, cerca=arriba, red=red)
            if sitio:
                rincones.append(Zona(tipo, round(sitio[0], 2), round(sitio[1], 2), sitio[2], sitio[3]))
        zonas += rincones
    return zonas


# -- La parte «denso» de construir_mundo_3d --------------------------------------------------------------


@dataclass
class BarrioGenerado:
    casas: list
    obstaculos: list        # los obstáculos de entrada + mesas secretas + casas + vegetación (el orden de construir_mundo_3d)
    zonas: list             # ya orientadas
    callejones: list
    escaleras: list         # las de entrada + las de callejón


def generar_barrio_indexado(mapa, edificios, despeje, obstaculos, terreno, zonas, escaleras, limites_plano, semilla,
                            cantidad=None, maximo_escaleras=ESCALERAS_CALLEJON, vegetacion=CANTIDAD_VEGETACION_BARRIO,
                            semilla_calle=None):
    """Lo que hace construir_mundo_3d con denso=True desde generar_casas hasta la vegetación, con las versiones
    indexadas. `despeje` debería ser un _DespejeIndexado. Con los valores por defecto da el mismo barrio que la
    versión lineal. cantidad=None usa barrio_favela.CANTIDAD_BARRIO; para el barrio grande pasar
    CANTIDAD_BARRIO_GRANDE, maximo_escaleras=ESCALERAS_CALLEJON_GRANDE y vegetacion mayor."""
    x0, x1, z0, z1 = terreno.extension
    region = (x0 + barrio_favela.BORDE_BARRIO, x1 - barrio_favela.BORDE_BARRIO,
              z0 + barrio_favela.BORDE_BARRIO, z1 - barrio_favela.BORDE_BARRIO)
    tope = barrio_favela.CANTIDAD_BARRIO if cantidad is None else cantidad
    nuevas = barrio_favela.generar_casas(mapa, edificios, despeje, obstaculos, terreno, zonas, region, semilla,
                                         cantidad=tope, fabrica_barrio=_BarrioIndexado)
    zonas = barrio_favela.orientar_secretos(zonas, [_caja_obstaculo(c) for c in nuevas], mapa)
    obstaculos = obstaculos + barrio_favela.mesas_secretas(zonas)
    fijos = [e.caja() for e in edificios] + [_caja_obstaculo(o) for o in obstaculos if o.es_caja]
    fijos += [(o.cx - o.radio, o.cx + o.radio, o.cz - o.radio, o.cz + o.radio) for o in obstaculos if o.es_circulo]
    if semilla_calle is None:      # un punto de calle: la Praça da Sé o, si el mapa no la tiene, el primer lugar
        semilla_calle = mapa.coordenada("Praça da Sé" if "Praça da Sé" in mapa.lugares() else mapa.lugares()[0])
    casas = quitar_bolsas_por_chunk(nuevas, fijos, semilla_calle, limites_plano)
    obstaculos = obstaculos + casas
    callejones = barrio_favela.callejones_entre(casas)
    todas_escaleras = list(escaleras) + escaleras_callejon_indexadas(callejones, escaleras, terreno, maximo_escaleras)
    obstaculos = obstaculos + vegetacion_indexada(mapa, despeje, obstaculos, terreno, cantidad=vegetacion,
                                                  semilla=semilla + 1, zonas=zonas)
    return BarrioGenerado(casas, obstaculos, zonas, callejones, todas_escaleras)
