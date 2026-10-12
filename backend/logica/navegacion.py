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
#  - En una calle (a, b): se elige el extremo con menos saltos hacia el destino
#    (empate: el más cercano en línea recta; luego el primero) y ese extremo es
#    la siguiente esquina, incluido en la lista.
#  - Fuera de la zona transitable: se trata como si estuviera en la plaza del
#    lugar más cercano.
# ValueError si el destino no existe.
def calcular_ruta_gps(mapa, x, z, destino):
    grafo = mapa.grafo
    lugar = mapa.lugar_en_plaza(x, z)
    if lugar is None:
        calle = mapa.calle_en(x, z)
        if calle is None:
            lugar = mapa.lugar_mas_cercano(x, z)
        else:
            return _ruta_desde_calle(mapa, x, z, calle, destino)
    return grafo.ruta_mas_corta(lugar, destino)[1:]


def _ruta_desde_calle(mapa, x, z, calle, destino):
    grafo = mapa.grafo
    mejor_ruta = None
    mejor_clave = None
    for extremo in calle:
        ruta = grafo.ruta_mas_corta(extremo, destino)
        if not ruta:
            continue  # sin camino desde ese extremo
        cx, cz = mapa.coordenada(extremo)
        clave = (len(ruta), math.hypot(x - cx, z - cz))
        if mejor_clave is None or clave < mejor_clave:
            mejor_ruta, mejor_clave = ruta, clave
    return mejor_ruta if mejor_ruta is not None else []


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
    escala = min(tamano[0] / (xmax - xmin), tamano[1] / (zmax - zmin))
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
