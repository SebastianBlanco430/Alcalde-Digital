# Navegación del overworld (funciones puras, sin ursina): movimiento relativo
# a la cámara, colisiones por zona transitable, GPS por BFS y minimapa.
#
# Convención de ejes: el plano del mundo es (x, z); en pantalla "arriba" es
# adelante (v = +1) y "derecha" es h = +1. `yaw_grados` es el giro de la cámara.
# Todas las fórmulas asumen esta convención; el signo real de yaw respecto a
# la cámara de Ursina se fija con un test de ventana (por eso es parámetro).

import math


# -- Movimiento -------------------------------------------------------------


# Desplazamiento (dx, dz) para la entrada (h, v) con h, v en {-1, 0, 1}:
#   dx = h·cosθ + v·sinθ ;  dz = -h·sinθ + v·cosθ
# La entrada se normaliza (la diagonal no es más rápida) y se multiplica por
# velocidad·dt. Sin entrada devuelve (0, 0).
def mover_isometrico(h, v, yaw_grados, velocidad, dt):
    if h == 0 and v == 0:
        return (0, 0)
    theta = math.radians(yaw_grados)
    dx = h * math.cos(theta) + v * math.sin(theta)
    dz = -h * math.sin(theta) + v * math.cos(theta)
    largo = math.hypot(dx, dz)
    if largo == 0:
        return (0, 0)
    factor = velocidad * dt / largo
    return (dx * factor, dz * factor)


PENDIENTE_FACTOR_MINIMO = 0.6   # multiplicador de velocidad más lento (subida muy empinada)
PENDIENTE_FACTOR_MAXIMO = 1.1   # multiplicador más rápido (bajada empinada)
PENDIENTE_COEF_SUBIDA = 0.9     # cuánto frena cada unidad de pendiente t subiendo
PENDIENTE_COEF_BAJADA = 0.3     # cuánto acelera cada unidad de pendiente |t| bajando
PENDIENTE_DISTANCIA_MIN = 1e-6  # m: por debajo se considera sin distancia (factor 1)


# Multiplicador de velocidad según la pendiente, con t = desnivel / distancia (m/m):
# subiendo (t > 0) max(0.6, 1 - 0.9·t) (≈ 0.76 a 15°); bajando (t < 0) min(1.1, 1 + 0.3·|t|);
# plano o distancia ~0 -> 1.
def factor_pendiente(desnivel, distancia):
    if distancia <= PENDIENTE_DISTANCIA_MIN:
        return 1.0
    t = desnivel / distancia
    if t > 0:
        return max(PENDIENTE_FACTOR_MINIMO, 1 - PENDIENTE_COEF_SUBIDA * t)
    return min(PENDIENTE_FACTOR_MAXIMO, 1 + PENDIENTE_COEF_BAJADA * abs(t))


# Colisión con deslizamiento: prueba (x+dx, z+dz), luego (x+dx, z), luego
# (x, z+dz); si ninguna es transitable se queda en (x, z).
def mover_con_colisiones(mapa, x, z, dx, dz):
    if mapa.es_transitable(x + dx, z + dz):
        return (x + dx, z + dz)
    if mapa.es_transitable(x + dx, z):
        return (x + dx, z)
    if mapa.es_transitable(x, z + dz):
        return (x, z + dz)
    return (x, z)


# -- GPS --------------------------------------------------------------------


# Lugares que faltan por recorrer, desde la siguiente esquina hasta el destino
# ([] si el jugador ya está en la plaza del destino o no hay camino).
#  - En la plaza de L: ruta_mas_corta(L, destino) sin L.
#  - En una calle (a, b): se elige el extremo con menos metros totales (tramo hasta
#    el extremo + ruta hacia el destino; empate: el más cercano en línea recta; luego el primero) y ese extremo es
#    la siguiente esquina, incluido en la lista.
#  - Fuera de la zona transitable: se trata como si estuviera en la plaza del
#    lugar más cercano.
# ValueError si el destino no existe.
def calcular_ruta_gps(mapa, x, z, destino):
    lugar = mapa.lugar_en_plaza(x, z)
    if lugar is None:
        calle = mapa.calle_en(x, z)
        if calle is None:
            lugar = mapa.lugar_mas_cercano(x, z)
            if lugar is None:
                return []
        else:
            return _ruta_desde_calle(mapa, x, z, calle, destino)
    return _ruta_entre(mapa, lugar, destino)[1:]


# Ruta [origen, ..., destino] por metros reales (Dijkstra) si el mapa la ofrece; si no
# hay camino o el mapa no tiene ruta_mas_corta_metros, usa BFS por saltos del grafo.
# [] si no hay camino. ValueError si algún lugar no existe.
def _ruta_entre(mapa, origen, destino):
    metros = getattr(mapa, "ruta_mas_corta_metros", None)
    if metros is not None:
        ruta, _ = metros(origen, destino)
        if ruta:
            return ruta
    return mapa.grafo.ruta_mas_corta(origen, destino)


def _metros_ruta(mapa, ruta):
    return sum(
        math.hypot(bx - ax, bz - az)
        for (ax, az), (bx, bz) in zip(map(mapa.coordenada, ruta), map(mapa.coordenada, ruta[1:]))
    )


def _ruta_desde_calle(mapa, x, z, calle, destino):
    mejor_ruta = None
    mejor_clave = None
    for extremo in calle:
        ruta = _ruta_entre(mapa, extremo, destino)
        if not ruta:
            continue  # sin camino desde ese extremo
        cx, cz = mapa.coordenada(extremo)
        recta = math.hypot(x - cx, z - cz)
        # Coste real: tramo hasta el extremo + metros de la ruta que se seguirá desde él.
        # Sin ruta_mas_corta_metros en el mapa se usan los saltos (comportamiento previo).
        if hasattr(mapa, "ruta_mas_corta_metros"):
            costo = recta + _metros_ruta(mapa, ruta)
        else:
            costo = len(ruta)
        clave = (costo, recta)
        if mejor_clave is None or clave < mejor_clave:
            mejor_ruta, mejor_clave = ruta, clave
    return mejor_ruta if mejor_ruta is not None else []


# Puntos (x, z) para DIBUJAR el camino hasta la puerta del destino: el centro de cada lugar
# de la ruta del GPS + el punto de entrada (1.2 m delante de la puerta) + la puerta. Estando
# ya en la plaza del destino son solo [entrada, puerta]. Con un mapa sin edificios (sin
# `edificio_de`) o un lugar sin edificio termina en el centro del destino.
# ValueError si el destino no existe.
def ruta_gps_hasta_puerta(mundo, x, z, destino):
    puntos = [mundo.coordenada(lugar) for lugar in calcular_ruta_gps(mundo, x, z, destino)]
    edificio_de = getattr(mundo, "edificio_de", None)
    try:
        edificio = edificio_de(destino) if edificio_de is not None else None
    except ValueError:
        edificio = None
    if edificio is None:
        return rodear_obstaculos(mundo, (x, z), puntos) or [mundo.coordenada(destino)]
    return rodear_obstaculos(mundo, (x, z), puntos + [edificio.punto_entrada()]) + [edificio.puerta()]


# Puntos (x, z) para DIBUJAR el camino hasta un punto exacto (delante de la puerta de la Fiscalía, el terminal de una
# misión digital) que queda en la plaza de `destino` o junto a ella. Sesión E (ruta-fiscalia): antes se dibujaba la ruta
# hasta la puerta del EDIFICIO del lugar (la Lan House da Praça, dentro de su muro) y de allí una recta al punto: la
# línea iba y volvía cruzando la plaza. Ahora: las esquinas del GPS SIN el centro de la plaza del destino (el punto está
# en su borde; pasar por el centro obliga a volver sobre los propios pasos) y el punto, con los rodeos de siempre. Si
# algún tramo sigue chocando, se repara con la rejilla (_reparar_tramos); si ni así, se pasa por el centro de la plaza.
# ValueError si el destino no existe.
def ruta_gps_hasta_punto(mundo, x, z, destino, punto, presupuesto=None):
    punto = (float(punto[0]), float(punto[1]))
    # Se pide en cada frame: caché por celda de CELDA_RUTA m del jugador (la línea se redibuja con PASO_FIRMA = 0,25 m).
    clave = (id(mundo), _version_mundo(mundo), destino, round(punto[0], 2), round(punto[1], 2),
             round(x / CELDA_RUTA), round(z / CELDA_RUTA))
    if clave in _CACHE_RUTAS_PUNTO:
        return list(_CACHE_RUTAS_PUNTO[clave])
    ruta, definitiva = _calcular_ruta_hasta_punto(mundo, x, z, destino, punto, presupuesto)
    if definitiva:
        if len(_CACHE_RUTAS_PUNTO) > _MAX_CACHE:
            _CACHE_RUTAS_PUNTO.clear()
        _CACHE_RUTAS_PUNTO[clave] = ruta
    return list(ruta)


CELDA_RUTA = 0.25
_CACHE_RUTAS_PUNTO = {}


def _version_mundo(mundo):
    """Cambia cuando el cliente agrega decorado con colisión (agregar_obstaculos): invalida las cachés de rutas."""
    return len(getattr(mundo, "_fisicos", ()) or ())


def _calcular_ruta_hasta_punto(mundo, x, z, destino, punto, presupuesto=None):
    """(ruta, definitiva): definitiva=False si la reparación quedó a medias por el presupuesto (ruta provisional)."""
    lugares = calcular_ruta_gps(mundo, x, z, destino)
    esquinas = [mundo.coordenada(lugar) for lugar in lugares]
    candidatas = [esquinas[:-1] + [punto]] if lugares and lugares[-1] == destino else []
    candidatas.append(esquinas + [punto])
    primera, reparada = None, None
    for puntos in candidatas:
        ruta = rodear_obstaculos(mundo, (x, z), puntos)
        if _polilinea_libre(mundo, [(x, z)] + ruta):
            return ruta, True
        if primera is None:
            primera = ruta
            try:
                reparada = _reparar_tramos(mundo, [(x, z)] + ruta, presupuesto)[1:]
            except _Pendiente:
                return ruta, False
            if _polilinea_libre(mundo, [(x, z)] + reparada):
                return reparada, True
    return reparada, True


def _polilinea_libre(mundo, puntos):
    if not callable(getattr(mundo, "es_transitable", None)):
        return True
    return all(_tramo_libre(mundo, a, b) for a, b in zip(puntos, puntos[1:]))


# Tramos que siguen chocando tras los rodeos (el rodeo de un solo punto lateral no basta, p. ej. entre la fuente y un
# banco): se cambian por el camino más corto en una rejilla de PASO_REJILLA m (8 vecinos, sin cortar esquinas) y luego se
# tensa (solo quedan los puntos sin línea de vista entre sí). La rejilla es un Dijkstra HACIA ATRÁS desde el extremo fijo
# del tramo (la esquina o la puerta) que se guarda y solo crece lo necesario: al caminar, el jugador cae casi siempre en
# celdas ya resueltas. Hasta RADIO_CAMPO m del extremo; más lejos (o sin camino) el tramo queda como estaba.
# `presupuesto` (celdas por llamada; None = sin tope): en el juego el campo crece a trozos, unos ms por frame, y mientras
# no llega al jugador la ruta es la de los rodeos (provisional; no se guarda en la caché).
PASO_REJILLA = 0.5
RADIO_CAMPO = 60.0
PRESUPUESTO_FRAME = 150            # celdas del campo que se resuelven por frame en el juego (unos ms)
_CAMPOS = {}
_MAX_CAMPOS = 16


class _Pendiente(Exception):
    """El campo aún no llega al jugador (presupuesto agotado)."""


def _reparar_tramos(mundo, puntos, presupuesto=None):
    salida = [puntos[0]]
    for a, b in zip(puntos, puntos[1:]):
        if not _tramo_libre(mundo, a, b):
            salida.extend(_camino_rejilla(mundo, a, b, presupuesto))
        salida.append(b)
    return salida


class _CampoHacia:
    """Dijkstra perezoso en rejilla hacia `meta` (x, z): distancia y siguiente celda hacia ella."""

    VECINOS = [(dx, dz, math.hypot(dx, dz)) for dx in (-1, 0, 1) for dz in (-1, 0, 1) if dx or dz]

    def __init__(self, mundo, meta):
        self.mundo, self.meta = mundo, meta
        self.fin = self.celda(meta)
        self.costo, self.siguiente, self.cerradas = {self.fin: 0.0}, {self.fin: None}, set()
        self.cola = [(0.0, self.fin)]
        self.libres = {self.fin: True}
        self.tope = RADIO_CAMPO / PASO_REJILLA
        self.vista = {}                # celda -> la celda más lejana del camino que se ve en línea recta desde ella

    @staticmethod
    def celda(p):
        return (round(p[0] / PASO_REJILLA), round(p[1] / PASO_REJILLA))

    @staticmethod
    def punto(c):
        return (c[0] * PASO_REJILLA, c[1] * PASO_REJILLA)

    def libre(self, c):
        if c not in self.libres:
            self.libres[c] = (math.hypot(c[0] - self.fin[0], c[1] - self.fin[1]) <= self.tope
                              and self.mundo.es_transitable(*self.punto(c)))
        return self.libres[c]

    def resolver(self, objetivo, presupuesto=None):
        """True si `objetivo` ya tiene camino; False si no lo habrá; _Pendiente si se agotó el presupuesto."""
        import heapq
        gastadas = 0
        while objetivo not in self.cerradas and self.cola:
            if presupuesto is not None and gastadas >= presupuesto:
                raise _Pendiente()
            g, c = heapq.heappop(self.cola)
            if c in self.cerradas:
                continue
            self.cerradas.add(c)
            gastadas += 1
            for dx, dz, w in self.VECINOS:
                n = (c[0] + dx, c[1] + dz)
                # la celda del jugador puede tocar un borde (está pegado a una pared): se acepta como origen
                if not (self.libre(n) or n == objetivo):
                    continue
                if dx and dz and not (self.libre((c[0] + dx, c[1])) and self.libre((c[0], c[1] + dz))):
                    continue                                    # en diagonal no se cortan esquinas
                if g + w < self.costo.get(n, math.inf):
                    self.costo[n], self.siguiente[n] = g + w, c
                    heapq.heappush(self.cola, (g + w, n))
        return objetivo in self.cerradas

    def _cadena(self, c):
        cadena = []
        while c is not None:
            cadena.append(c)
            c = self.siguiente[c]
        return cadena

    def _mas_lejana_visible(self, desde, cadena):
        """Índice en `cadena` de la celda más lejana que se ve en línea recta desde el punto `desde`."""
        if len(cadena) <= 1:
            return 0
        j = len(cadena) - 1
        while j > 1 and not _tramo_libre(self.mundo, desde, self.lugar(cadena[j])):
            j -= 1
        return j

    def lugar(self, c):
        """Punto de la celda; la de la meta es la meta exacta (el centro de su celda puede caer a 0,35 m)."""
        return self.meta if c == self.fin else self.punto(c)

    def tenso_desde(self, a):
        """Puntos intermedios tensos de `a` a la meta (sin `a` ni la meta)."""
        cadena = self._cadena(self.celda(a))
        if len(cadena) <= 1:
            return []
        intermedios = []
        c = cadena[self._mas_lejana_visible(a, cadena)]
        while c != self.fin:
            if c not in self.vista:
                resto = self._cadena(c)
                self.vista[c] = resto[self._mas_lejana_visible(self.lugar(c), resto)]
            intermedios.append(self.punto(c))
            c = self.vista[c]
        return intermedios


def _camino_rejilla(mundo, a, b, presupuesto=None):
    """Puntos intermedios (sin a ni b) de un camino libre de a a b; [] si no lo hay. _Pendiente con presupuesto agotado."""
    clave = (id(mundo), _version_mundo(mundo), round(b[0], 2), round(b[1], 2))
    campo = _CAMPOS.get(clave)
    if campo is None:
        if len(_CAMPOS) >= _MAX_CAMPOS:
            _CAMPOS.clear()
        campo = _CAMPOS[clave] = _CampoHacia(mundo, b)
    if not campo.resolver(campo.celda(a), presupuesto):
        return []
    return campo.tenso_desde(a)


# Polilínea completa que dibuja la ruta del piso (EscenaMundo._actualizar_ruta_piso): el jugador y los puntos hasta la
# puerta del destino; con `exacto` (x, z) —la puerta de la Fiscalía, el terminal de una misión digital— hasta ese punto.
# `presupuesto`: ver PRESUPUESTO_FRAME (el juego lo pasa; los tests calculan todo de una vez).
def puntos_ruta_piso(mundo, x, z, destino, exacto=None, presupuesto=None):
    if exacto is None:
        return [(x, z)] + list(ruta_gps_hasta_puerta(mundo, x, z, destino))
    try:
        return [(x, z)] + ruta_gps_hasta_punto(mundo, x, z, destino, exacto, presupuesto)
    except ValueError:
        raise                                   # destino inexistente: igual que ruta_gps_hasta_puerta
    except Exception:                           # noqa: BLE001 — red de seguridad: la composición de antes, sin caerse
        return [(x, z)] + list(ruta_gps_hasta_puerta(mundo, x, z, destino)) + [(float(exacto[0]), float(exacto[1]))]


# -- Rodeo de obstáculos (VIS-002 / EST-014 / REN-002) ---------------------------------------------------------------
# Los puntos del GPS son centros de plaza: el de la Praça da Sé cae DENTRO de la fuente y la recta de la plaza del
# Mercado cruza el toldo del puesto fijo de Seu Heitor. Con las colisiones reales del mundo (`es_transitable`):
#   1. un punto de paso dentro de un obstáculo se mueve al punto libre más cercano (el que menos alarga la ruta);
#   2. un tramo que cruza algo recibe un punto de desvío lateral (el menor que deja libres los dos tramos nuevos).
# El último tramo (entrada -> puerta) no se toca: la puerta está en la fachada. Un mapa sin `es_transitable` (los
# tests del mapa 2D) devuelve los puntos tal cual. Caché por tramo (los puntos de plaza no cambian) y del primer tramo
# por la posición del jugador redondeada a 1 m.
PASO_MUESTREO = 0.5                       # m entre muestras de un tramo
DESVIOS = tuple(0.75 * i for i in range(1, 15))     # distancias laterales que se prueban (hasta 10,5 m)
RADIOS_LIBRES = (0.6, 1.2, 1.8, 2.4, 3.0, 3.6, 4.5, 5.5, 7.0)
_CACHE_TRAMOS = {}
_CACHE_PUNTOS = {}
_MAX_CACHE = 512


def _transitable(mundo, p):
    return mundo.es_transitable(p[0], p[1])


def _tramo_libre(mundo, a, b):
    largo = math.hypot(b[0] - a[0], b[1] - a[1])
    n = max(1, int(largo / PASO_MUESTREO))
    return all(_transitable(mundo, (a[0] + (b[0] - a[0]) * i / n, a[1] + (b[1] - a[1]) * i / n)) for i in range(1, n))


def _anclas_del_bloqueo(a, b, mundo):
    """Puntos del tramo desde los que se prueba el desvío: centro, principio y final del trozo bloqueado."""
    largo = math.hypot(b[0] - a[0], b[1] - a[1])
    n = max(1, int(largo / PASO_MUESTREO))
    bloqueados = [i for i in range(1, n) if not _transitable(mundo, (a[0] + (b[0] - a[0]) * i / n,
                                                                    a[1] + (b[1] - a[1]) * i / n))]
    ts = ((bloqueados[0] + bloqueados[-1]) / 2 / n, bloqueados[0] / n, bloqueados[-1] / n)
    return [(a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t) for t in ts]


def _desvio(mundo, a, b):
    clave = (id(mundo), round(a[0], 1), round(a[1], 1), round(b[0], 1), round(b[1], 1))
    if clave in _CACHE_TRAMOS:
        return _CACHE_TRAMOS[clave]
    desvio = []
    if not _tramo_libre(mundo, a, b):
        largo = math.hypot(b[0] - a[0], b[1] - a[1]) or 1.0
        nx, nz = -(b[1] - a[1]) / largo, (b[0] - a[0]) / largo
        for mx, mz in _anclas_del_bloqueo(a, b, mundo):
            for d in DESVIOS:
                hallado = None
                for lado in (1.0, -1.0):
                    w = (mx + nx * d * lado, mz + nz * d * lado)
                    if _transitable(mundo, w) and _tramo_libre(mundo, a, w) and _tramo_libre(mundo, w, b):
                        hallado = w
                        break
                if hallado is not None:
                    desvio = [hallado]
                    break
            if desvio:
                break
    if len(_CACHE_TRAMOS) > _MAX_CACHE:
        _CACHE_TRAMOS.clear()
    _CACHE_TRAMOS[clave] = desvio
    return desvio


def _sacar_de_obstaculo(mundo, p, previo, siguiente):
    if _transitable(mundo, p):
        return p
    clave = (id(mundo), round(p[0], 1), round(p[1], 1), previo is None, siguiente is None)
    if clave in _CACHE_PUNTOS:
        return _CACHE_PUNTOS[clave]
    # El mejor punto libre alrededor: primero que deje libres los dos tramos que lo tocan, luego el que menos alarga.
    mejor, mejor_clave = p, None
    for r in RADIOS_LIBRES:
        for k in range(16):
            q = (p[0] + r * math.cos(k * math.pi / 8), p[1] + r * math.sin(k * math.pi / 8))
            if not _transitable(mundo, q):
                continue
            libres = sum(1 for o in (previo, siguiente) if o is None or _tramo_libre(mundo, o, q))
            costo = sum(math.hypot(q[0] - o[0], q[1] - o[1]) for o in (previo, siguiente) if o is not None)
            orden = (-libres, costo)
            if mejor_clave is None or orden < mejor_clave:
                mejor, mejor_clave = q, orden
        if mejor_clave is not None and mejor_clave[0] == -2:
            break                                # el anillo más cercano con los dos tramos libres
    if len(_CACHE_PUNTOS) > _MAX_CACHE:
        _CACHE_PUNTOS.clear()
    _CACHE_PUNTOS[clave] = mejor
    return mejor


def rodear_obstaculos(mundo, inicio, puntos):
    """`puntos` del GPS (sin el jugador) con los rodeos de arriba; `inicio` = (x, z) del jugador."""
    if not puntos or not callable(getattr(mundo, "es_transitable", None)):
        return list(puntos)
    try:
        fijos = list(puntos)
        for i in range(len(fijos) - 1):        # el último (punto de entrada / destino) no se mueve
            previo = fijos[i - 1] if i > 0 else inicio
            fijos[i] = _sacar_de_obstaculo(mundo, fijos[i], previo, fijos[i + 1])
        salida = []
        anterior = (round(inicio[0]), round(inicio[1]))
        for p in fijos:
            salida.extend(_desvio(mundo, anterior, p))
            salida.append(p)
            anterior = p
        return salida
    except Exception:                          # noqa: BLE001 — ante cualquier rareza del mundo, la ruta de siempre
        return list(puntos)


# Siguiente esquina del GPS, o None si ya llegó (o no hay camino).
def siguiente_esquina(mapa, x, z, destino):
    ruta = calcular_ruta_gps(mapa, x, z, destino)
    return ruta[0] if ruta else None


# -- Minimapa ---------------------------------------------------------------


# Punto del mundo (x, z) -> coordenadas (u, v) del minimapa.
# limites = (xmin, xmax, zmin, zmax); centro = (cx, cy) y tamano = (w, h) del
# rectángulo del minimapa. Escala uniforme s = min(w/ancho, h/alto) (no deforma).
# Decisión de Sam: el minimapa gira con el yaw de la cámara (estilo radar):
# el vector (x - xc, z - zc) se rota con la inversa de mover_isometrico
#   u' = dx·cosθ - dz·sinθ ;  v' = dx·sinθ + dz·cosθ
# de modo que "adelante" (W) siempre es "arriba" en el minimapa. Con yaw=0 es
# norte (+z) arriba y +x a la derecha.
def a_minimapa(x, z, limites, centro, tamano, yaw_grados=0):
    xmin, xmax, zmin, zmax = limites
    # límites degenerados (ancho o alto 0): sin división por cero, se ignora ese eje
    razones = [t / d for t, d in ((tamano[0], xmax - xmin), (tamano[1], zmax - zmin)) if d > 0]
    escala = min(razones) if razones else 1.0
    dx = x - (xmin + xmax) / 2
    dz = z - (zmin + zmax) / 2
    if yaw_grados:
        theta = math.radians(yaw_grados)
        dx, dz = (
            dx * math.cos(theta) - dz * math.sin(theta),
            dx * math.sin(theta) + dz * math.cos(theta),
        )
    return (centro[0] + escala * dx, centro[1] + escala * dz)


# Ángulo en grados de (u0, v0) hacia (u1, v1) medido desde "arriba" en sentido
# horario: 0 arriba, 90 derecha, 180 abajo, -90 izquierda. Mismo punto -> 0.
def angulo_hacia(u0, v0, u1, v1):
    return math.degrees(math.atan2(u1 - u0, v1 - v0))


# Punto (x, z) que el minimapa marca como destino: el exacto de la misión si lo hay (puerta de la Fiscalía, terminal),
# si no el centro del lugar. None sin destino.
def destino_en_minimapa(mapa, destino, exacto=None):
    if destino is None:
        return None
    if exacto is not None:
        return (float(exacto[0]), float(exacto[1]))
    return mapa.coordenada(destino)


# -- Distancia --------------------------------------------------------------


def distancia_xz(x1, z1, x2, z2):
    return math.hypot(x2 - x1, z2 - z1)
