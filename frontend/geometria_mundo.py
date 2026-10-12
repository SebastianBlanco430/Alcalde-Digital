# Utilidades de movimiento del mundo (Python puro: NO importa ursina, se prueba con pytest
# sin ventana): teclas -> ejes (y su inversa para los bots), suavizados independientes de los
# fps y rumbos.
#
# Convención de Ursina (fijada con tests/test_mundo_ventana.py):
#   - El plano del mundo es (x, z); la altura es y.
#   - Con camera.rotation = (pitch, yaw, 0), "adelante" de la cámara proyectado al
#     suelo es (sin yaw, cos yaw) y "derecha" es (cos yaw, -sin yaw).
#   - navegacion.mover_isometrico(h, v, yaw, ...) usa exactamente esas dos
#     direcciones, así que el yaw que se le pasa es el de la cámara orbital SIN
#     cambiar el signo: W (v=+1) avanza hacia donde mira la cámara y D (h=+1) va a su derecha.

import math





# -- Teclas -----------------------------------------------------------------

TECLAS_DERECHA = ("d", "right arrow")
TECLAS_IZQUIERDA = ("a", "left arrow")
TECLAS_ARRIBA = ("w", "up arrow")
TECLAS_ABAJO = ("s", "down arrow")


def _pulsada(teclas, nombres):
    return any(teclas.get(nombre, 0) for nombre in nombres)


# (h, v) con h, v en {-1, 0, 1} a partir de un mapa tecla -> valor (held_keys).
# D/flecha derecha = h +1; W/flecha arriba = v +1. Teclas opuestas se anulan.
def ejes_de_teclas(teclas):
    h = int(_pulsada(teclas, TECLAS_DERECHA)) - int(_pulsada(teclas, TECLAS_IZQUIERDA))
    v = int(_pulsada(teclas, TECLAS_ARRIBA)) - int(_pulsada(teclas, TECLAS_ABAJO))
    return (h, v)


# Inversa de mover_isometrico para un "bot": el (h, v) en {-1, 0, 1} cuya dirección
# en el mundo se parece más a (dx, dz). Cada eje se activa si su componente
# normalizada supera `umbral` (0.38 ~ sin 22.5 grados: reparte las 8 direcciones).
def ejes_hacia(dx, dz, yaw_grados, umbral=0.38):
    largo = math.hypot(dx, dz)
    if largo == 0:
        return (0, 0)
    theta = math.radians(yaw_grados)
    h = (dx * math.cos(theta) - dz * math.sin(theta)) / largo
    v = (dx * math.sin(theta) + dz * math.cos(theta)) / largo
    return (
        (h > umbral) - (h < -umbral),
        (v > umbral) - (v < -umbral),
    )


# -- Suavizados (independientes de los fps) ----------------------------------


# Acerca `actual` a `objetivo` con una exponencial: cubre 1 - e^(-rapidez·dt) de la
# distancia por frame, así que el resultado no depende de los fps.
def suavizar(actual, objetivo, rapidez, dt):
    return actual + (objetivo - actual) * (1 - math.exp(-rapidez * dt))


# Ángulo en grados en (-180, 180] equivalente a `angulo`.
def normalizar_angulo(angulo):
    angulo = (angulo + 180) % 360 - 180
    return 180 if angulo == -180 else angulo


# Como suavizar() pero por el camino angular más corto.
def suavizar_angulo(actual, objetivo, rapidez, dt):
    diferencia = normalizar_angulo(objetivo - actual)
    return actual + diferencia * (1 - math.exp(-rapidez * dt))


# Rumbo (rotation_y de Ursina, grados) de un vector (dx, dz): 0 = +z, 90 = +x.
def rumbo_de(dx, dz):
    return math.degrees(math.atan2(dx, dz))


