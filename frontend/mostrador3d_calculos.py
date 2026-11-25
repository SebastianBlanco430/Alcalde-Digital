# Cálculos de la MIRADA LIBRE en primera persona del mostrador 3D (frontend/mostrador3d_escena.py). Python puro, sin
# ursina, con tests en tests/test_mostrador3d.py. El jugador sigue de pie detrás del puesto (la cámara no se desplaza):
# solo gira la cabeza, a izquierda y derecha y arriba y abajo, con topes para no mirarse la espalda ni el techo.
#   desvio = (giro, cabeceo) en grados respecto a la toma inicial; 0, 0 = mirando al cliente como antes.

import math

# topes del giro (izquierda/derecha) y del cabeceo (abajo/arriba), en grados respecto a la toma inicial
GIRO_MAX = 75.0
CABECEO_MIN, CABECEO_MAX = -40.0, 30.0
# grados por unidad de movimiento del ratón (mouse.velocity de Ursina) con el botón derecho apretado
SENSIBILIDAD_RATON = 160.0
# grados por segundo con las flechas del teclado
VELOCIDAD_TECLAS = 75.0
# 1/s: rapidez con que la vista vuelve al centro al pulsar C
VUELTA_CENTRO = 8.0


def angulos(posicion, objetivo):
    """(rumbo, cabeceo) en grados de la dirección posicion -> objetivo (rumbo 0 = hacia +z, positivo hacia +x)."""
    dx, dy, dz = (objetivo[i] - posicion[i] for i in range(3))
    return math.degrees(math.atan2(dx, dz)), math.degrees(math.atan2(dy, math.hypot(dx, dz)))


def limitar(giro, cabeceo):
    return max(-GIRO_MAX, min(GIRO_MAX, giro)), max(CABECEO_MIN, min(CABECEO_MAX, cabeceo))


def mover(desvio, raton=(0.0, 0.0), teclas=(0, 0), dt=0.0):
    """Nuevo desvío (giro, cabeceo) tras mover el ratón `raton` (dx, dy de la pantalla) y con las `teclas` apretadas
    (dx, dy en -1..1: izquierda/derecha, abajo/arriba) durante `dt` s. Siempre dentro de los topes."""
    giro = desvio[0] + raton[0] * SENSIBILIDAD_RATON + teclas[0] * VELOCIDAD_TECLAS * dt
    cabeceo = desvio[1] + raton[1] * SENSIBILIDAD_RATON + teclas[1] * VELOCIDAD_TECLAS * dt
    return limitar(giro, cabeceo)


def centrar(desvio, dt):
    """Un paso de la vuelta suave al centro (0, 0)."""
    k = min(1.0, VUELTA_CENTRO * dt)
    return desvio[0] * (1 - k), desvio[1] * (1 - k)


def toma_con_desvio(toma, desvio, distancia=2.0):
    """La toma (position, target, fov) girada `desvio` grados respecto a la inicial: misma posición, otro objetivo."""
    rumbo, cabeceo = angulos(toma["position"], toma["target"])
    r, c = math.radians(rumbo + desvio[0]), math.radians(cabeceo + desvio[1])
    x, y, z = toma["position"]
    objetivo = (x + distancia * math.sin(r) * math.cos(c), y + distancia * math.sin(c), z + distancia * math.cos(r) * math.cos(c))
    return {"position": tuple(toma["position"]), "target": objetivo, "fov": toma["fov"]}
