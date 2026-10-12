# Geometría del mundo isométrico (Python puro: NO importa ursina, se prueba con
# pytest sin ventana). Reúne lo que EscenaMundo y ControladorJugador necesitan
# calcular: yaw de la cámara, teclas -> ejes, suavizados y colocación de edificios.
#
# Convención de Ursina (fijada con tests/test_mundo_ventana.py):
#   - El plano del mundo es (x, z); la altura es y.
#   - Con camera.rotation = (pitch, yaw, 0), "adelante" de la cámara proyectado al
#     suelo es (sin yaw, cos yaw) y "derecha" es (cos yaw, -sin yaw).
#   - navegacion.mover_isometrico(h, v, yaw, ...) usa exactamente esas dos
#     direcciones, así que el yaw que se le pasa es el rotation_y de la cámara
#     SIN cambiar el signo: W (v=+1) sube en pantalla y D (h=+1) va a la derecha.

import math

# Cámara de la demo (demos/ciudad_ursina.py): ortográfica, inclinada 35 grados y
# girada -45 grados.
ROTACION_CAMARA = (35, -45, 0)


# Yaw (grados) que se pasa a navegacion.mover_isometrico y a_minimapa. El
# minimapa de la Fase 4 debe usar ESTA misma función.
def yaw_de_camara():
    return ROTACION_CAMARA[1]


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


# Posición de la cámara para que mire a `foco` (x, y, z) con rotation=(pitch, yaw, 0)
# desde `distancia`. forward = (sin yaw·cos pitch, -sin pitch, cos yaw·cos pitch).
def posicion_camara(foco, pitch_grados, yaw_grados, distancia):
    pitch, yaw = math.radians(pitch_grados), math.radians(yaw_grados)
    adelante = (math.sin(yaw) * math.cos(pitch), -math.sin(pitch), math.cos(yaw) * math.cos(pitch))
    return tuple(foco[i] - adelante[i] * distancia for i in range(3))


# -- Edificios --------------------------------------------------------------

LADO_EDIFICIO = 3.0        # lado de la base cuadrada
MARGEN_EDIFICIO = 0.7      # holgura mínima entre la base y cualquier zona transitable
PASO_ANGULO = 15           # grados entre candidatos alrededor del lugar
PASO_DISTANCIA = 0.5
RECORRIDO_EXTRA = 5.0      # cuánto se aleja como máximo del borde de la plaza
FACTORES_LADO = (1.0, 0.75, 0.55)   # si no cabe, se intenta más pequeño


# Puntos que cubren la base cuadrada (lado `lado`, centro cx, cz) AMPLIADA en
# `margen`: perímetro cada ~0.5 más el centro. Si ninguno es transitable, ningún
# punto de la base lo es (las calles miden >= 2 de ancho).
def puntos_de_base(cx, cz, lado, margen):
    medio = lado / 2 + margen
    divisiones = max(2, math.ceil(2 * medio / 0.5))
    puntos = [(cx, cz)]
    for i in range(divisiones + 1):
        t = -medio + 2 * medio * i / divisiones
        puntos += [(cx + t, cz - medio), (cx + t, cz + medio),
                   (cx - medio, cz + t), (cx + medio, cz + t)]
    return puntos


# True si la base ampliada no toca zona transitable.
def base_libre(mapa, cx, cz, lado, margen=MARGEN_EDIFICIO):
    return not any(mapa.es_transitable(x, z) for x, z in puntos_de_base(cx, cz, lado, margen))


# Coloca el edificio del `lugar` FUERA de la zona transitable. Devuelve (x, z, lado)
# o None si no encontró sitio. Cómo se coloca:
#  1. Se prueban ángulos alrededor del lugar, empezando por la dirección "hacia
#     arriba en la pantalla" (así el edificio queda detrás de la plaza y no tapa
#     al jugador) y alternando a ambos lados de 15 en 15 grados.
#  2. Para cada ángulo se parte de la distancia mínima (radio de la plaza + media
#     diagonal + margen) y se aleja de a 0.5 hasta RECORRIDO_EXTRA.
#  3. Gana el primer candidato cuya base ampliada es libre (base_libre) y no choca
#     con los edificios ya colocados (`ocupados`: lista de (x, z, lado)).
#  4. Si no cabe, se repite con la base más pequeña (FACTORES_LADO).
def ubicar_edificio(mapa, lugar, yaw_grados, ocupados=(), lado=LADO_EDIFICIO):
    cx, cz = mapa.coordenada(lugar)
    preferido = math.radians(yaw_grados)   # (sin yaw, cos yaw) = adelante de la cámara
    for factor in FACTORES_LADO:
        lado_actual = lado * factor
        minimo = mapa.radio_plaza + lado_actual * math.sqrt(2) / 2 + MARGEN_EDIFICIO
        for desvio in _desvios_angulares():
            angulo = preferido + math.radians(desvio)
            distancia = minimo
            while distancia <= minimo + RECORRIDO_EXTRA:
                x = cx + math.sin(angulo) * distancia
                z = cz + math.cos(angulo) * distancia
                if base_libre(mapa, x, z, lado_actual) and not _choca(x, z, lado_actual, ocupados):
                    return (x, z, lado_actual)
                distancia += PASO_DISTANCIA
    return None


# 0, +15, -15, +30, -30 ... hasta 180.
def _desvios_angulares():
    yield 0
    for k in range(1, 180 // PASO_ANGULO + 1):
        yield k * PASO_ANGULO
        if k * PASO_ANGULO != 180:
            yield -k * PASO_ANGULO


# Choque entre bases cuadradas aproximado por sus círculos circunscritos más holgura.
def _choca(x, z, lado, ocupados):
    for ox, oz, olado in ocupados:
        minimo = (lado + olado) * math.sqrt(2) / 2 + 0.3
        if math.hypot(x - ox, z - oz) < minimo:
            return True
    return False


# {lugar: (x, z, lado)} para todos los lugares del mapa (se omiten los que no caben).
def ubicar_edificios(mapa, yaw_grados):
    colocados = {}
    for lugar in mapa.lugares():
        resultado = ubicar_edificio(mapa, lugar, yaw_grados, ocupados=list(colocados.values()))
        if resultado is not None:
            colocados[lugar] = resultado
    return colocados
