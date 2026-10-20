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
        return puntos or [mundo.coordenada(destino)]
    return puntos + [edificio.punto_entrada(), edificio.puerta()]


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


# -- Distancia --------------------------------------------------------------


def distancia_xz(x1, z1, x2, z2):
    return math.hypot(x2 - x1, z2 - z1)
