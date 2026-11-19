# Cálculo puro (sin ursina) de las piezas de «Contrarreloj» visual: huecos de la cinta de noticias, relleno y tono del
# cronómetro, segmentos de la línea discontinua y trazos de los iconos. Lo usa piezas_contrarreloj.py.

import math

X_CINTA = 0.60
Y_CINTA_ARRIBA = 0.31
Y_LINEA_ROJA = -0.20
ALTO_TARJETA_MAX = 0.13
ALTO_TARJETA_MIN = 0.088
SEPARACION_TARJETAS = 8 / 720.0      # 8 px entre papeles: se ve el hueco entre notas y el sello FRENADA no las funde
FRACCION_ROJA = 0.25         # último cuarto del tiempo: el cronómetro se pone rojo


def huecos_cinta(n, y_arriba=Y_CINTA_ARRIBA, y_abajo=Y_LINEA_ROJA + 0.02, separacion=SEPARACION_TARJETAS):
    """(alto, [y_centro...]) de las n tarjetas de la cinta, apiladas de arriba abajo."""
    n = max(1, int(n))
    paso = (y_arriba - y_abajo) / n
    alto = max(ALTO_TARJETA_MIN, min(ALTO_TARJETA_MAX, paso - separacion))
    paso = min(paso, alto + separacion)
    return alto, [y_arriba - alto / 2 - i * paso for i in range(n)]


def fraccion_restante(t, duracion):
    """Cuánto queda del tiempo de la ronda (1 = todo, 0 = nada)."""
    return max(0.0, min(1.0, 1.0 - t / max(0.1, duracion)))


def es_rojo(restante):
    return restante <= FRACCION_ROJA


def segmentos_discontinuos(p0, p1, largo=0.014, hueco=0.010, maximo=40):
    """Trazos [(cx, cy, angulo_grados, largo)] de una línea discontinua entre p0 y p1."""
    dx, dy = p1[0] - p0[0], p1[1] - p0[1]
    dist = math.hypot(dx, dy)
    if dist < 1e-6:
        return []
    ang = math.degrees(math.atan2(dy, dx))
    salida, d = [], 0.0
    while d < dist and len(salida) < maximo:
        fin = min(dist, d + largo)
        medio = (d + fin) / 2
        salida.append((p0[0] + dx * medio / dist, p0[1] + dy * medio / dist, ang, fin - d))
        d += largo + hueco
    return salida


def trazos_aspa(tam):
    """Dos trazos (cx, cy, angulo, largo) que forman un aspa de lado `tam`."""
    return [(0.0, 0.0, 45.0, tam * 1.4), (0.0, 0.0, -45.0, tam * 1.4)]


def trazos_palomita(tam):
    """Dos trazos de una palomita: el corto baja y el largo sube."""
    return [(-tam * 0.22, -tam * 0.12, -45.0, tam * 0.55), (tam * 0.18, tam * 0.1, 55.0, tam * 1.0)]


def trazos_flecha(ancho):
    """Flecha hacia la derecha: eje + dos trazos de la punta (cx, cy, angulo, largo)."""
    return [(0.0, 0.0, 0.0, ancho), (ancho * 0.34, ancho * 0.16, -40.0, ancho * 0.38),
            (ancho * 0.34, -ancho * 0.16, 40.0, ancho * 0.38)]


def rectangulos_mano(tam):
    """Mano abierta: palma + 4 dedos + pulgar como rectángulos (cx, cy, ancho, alto, angulo)."""
    r = [(0.0, -tam * 0.18, tam * 0.62, tam * 0.5, 0.0)]
    for k in range(4):
        x = (k - 1.5) * tam * 0.15
        alto = tam * (0.46 if k in (1, 2) else 0.38)
        r.append((x, tam * 0.1 + alto / 2 - tam * 0.05, tam * 0.11, alto, 0.0))
    r.append((-tam * 0.36, -tam * 0.05, tam * 0.1, tam * 0.3, -50.0))
    return r
