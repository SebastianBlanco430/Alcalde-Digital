# Cámara orbital en tercera persona (Python puro: NO importa ursina, se prueba sin ventana).
# La CamaraTerceraPersona de Ursina solo lee el ratón, llama a estas funciones y coloca la
# cámara.
#
# Convención de Ursina (la misma de geometria_mundo): con camera.rotation = (φ, ψ, 0),
# "adelante" proyectado al piso es (sin ψ, cos ψ); φ positivo = mira hacia abajo.
# Pivote p = jugador + (0, 1.5, 0); yaw ψ; pitch φ; distancia d:
#
#     cam = p + d · ( -sin ψ · cos φ ,  sin φ ,  -cos ψ · cos φ )      rotation = (φ, ψ, 0)
#
# La cámara queda detrás (−adelante) y arriba del pivote y siempre lo mira de frente.

import math

from frontend.geometria_mundo import normalizar_angulo, suavizar

ALTURA_PIVOTE = 1.5


# Pivote (x, y, z) al que apunta la cámara: la cabeza del personaje parado en (x, suelo, z).
def pivote_del_jugador(x, z, altura=ALTURA_PIVOTE, suelo=0.0):
    return (x, suelo + altura, z)


# Posición de la cámara para el pivote, yaw y pitch (grados) y distancia dados.
def posicion_orbital(pivote, yaw, pitch, distancia):
    psi, phi = math.radians(yaw), math.radians(pitch)
    return (
        pivote[0] - distancia * math.sin(psi) * math.cos(phi),
        pivote[1] + distancia * math.sin(phi),
        pivote[2] - distancia * math.cos(psi) * math.cos(phi),
    )


# Movimiento del ratón (dx a la derecha, dy hacia arriba, como mouse.velocity):
#   ψ += sens·dx ;  φ = clamp(φ − sens·dy, φmin, φmax)
# El yaw se devuelve normalizado a (-180, 180]. Devuelve (yaw, pitch).
def aplicar_raton(yaw, pitch, dx, dy, sensibilidad, pitch_min, pitch_max):
    nuevo_yaw = normalizar_angulo(yaw + sensibilidad * dx)
    nuevo_pitch = min(pitch_max, max(pitch_min, pitch - sensibilidad * dy))
    return nuevo_yaw, nuevo_pitch


# mouse.velocity (dx, dy) menos el "reposo": dónde deja Ursina el cursor tras recentrarlo. En
# ventana normal es (0, 0); en la pantalla completa de macOS (F11 de Ursina) la ventana no mide lo
# pedido y el cursor queda desplazado, lo que sesga cada movimiento y clava el pitch en un extremo.
# Sin movimiento (0, 0) no se resta nada.
def quitar_reposo(velocidad, reposo):
    if velocidad[0] == 0 and velocidad[1] == 0:
        return (0.0, 0.0)
    return (velocidad[0] - reposo[0], velocidad[1] - reposo[1])


# Rueda del ratón: rueda > 0 (hacia adelante) acerca, < 0 aleja. Cada "clic" mueve `paso` m.
def aplicar_zoom(distancia, rueda, dmin, dmax, paso=0.6):
    return min(dmax, max(dmin, distancia - rueda * paso))


# Distancia real de la cámara cuando un raycast desde el pivote hacia ella golpea algo a
# `distancia_impacto` (None = no golpeó nada): d = min(deseada, max(dmin, impacto − margen)).
def distancia_con_colision(deseada, distancia_impacto, margen, dmin=1.0):
    if distancia_impacto is None:
        return deseada
    return min(deseada, max(dmin, distancia_impacto - margen))


# Distancia desde el pivote, hacia `posicion` (la cámara deseada), a la que el tramo pasa a menos
# de `margen` m por encima del suelo (`altura_suelo(x, z)`), o None si no lo toca. Se muestrea
# cada `paso` m: la ladera es suave a esa escala y no hace falta un raycast contra la malla.
def distancia_libre_de_suelo(pivote, posicion, altura_suelo, margen=0.4, paso=0.5):
    dx, dy, dz = (posicion[i] - pivote[i] for i in range(3))
    largo = math.sqrt(dx * dx + dy * dy + dz * dz)
    if largo < 1e-9:
        return None
    pasos = max(1, int(math.ceil(largo / paso)))
    for k in range(1, pasos + 1):
        t = k / pasos
        x, y, z = pivote[0] + dx * t, pivote[1] + dy * t, pivote[2] + dz * t
        if y < altura_suelo(x, z) + margen:
            return largo * (k - 1) / pasos
    return None


# Acerca `actual` a `objetivo` con una exponencial (independiente de los fps). Hacia
# adentro (objetivo < actual) con `rapidez_acercar`, hacia afuera con `rapidez_alejar`
# (más lenta): al pegarse a una pared la cámara se mete rápido y al salir no "salta".
def suavizar_distancia(actual, objetivo, dt, rapidez_acercar=20.0, rapidez_alejar=4.0):
    rapidez = rapidez_acercar if objetivo < actual else rapidez_alejar
    return actual + (objetivo - actual) * (1 - math.exp(-rapidez * max(0.0, dt)))


# (pitch, yaw) en grados con los que una cámara en `origen` mira a `objetivo` (ambos (x, y, z)):
# yaw = atan2(dx, dz) ; pitch = -atan2(dy, |(dx, dz)|)  (positivo = mira hacia abajo).
def rotacion_mirando(origen, objetivo):
    dx, dy, dz = (objetivo[i] - origen[i] for i in range(3))
    return (-math.degrees(math.atan2(dy, math.hypot(dx, dz))), math.degrees(math.atan2(dx, dz)))


# Un paso del seguimiento del pivote (x, z) hacia `objetivo`: exponencial como suavizar() y, si
# se da `vmax` (m/s), nunca más de vmax·dt por paso. El tope evita el tirón inicial al viajar de
# un jugador a otro (la exponencial arranca con rapidez·distancia: 150 m/s a 50 m); cerca del
# objetivo (caminando) el tope no interviene. No se pasa del objetivo.
def avanzar_pivote(actual, objetivo, dt, rapidez, vmax=None):
    dx, dz = objetivo[0] - actual[0], objetivo[1] - actual[1]
    distancia = math.hypot(dx, dz)
    if distancia == 0 or dt <= 0:
        return (actual[0], actual[1])
    paso = distancia * (1 - math.exp(-rapidez * dt))
    if vmax is not None:
        paso = min(paso, vmax * dt)
    paso = min(paso, distancia)
    return (actual[0] + dx / distancia * paso, actual[1] + dz / distancia * paso)


# Rapidez del suavizado según la distancia al objetivo: `cerca` (seguir al jugador caminando)
# hasta 2 m, `lejos` (viajar de un jugador a otro) desde 10 m y una transición suave (smoothstep)
# entre ambas. Al ser continua en la distancia, la cámara no cambia de golpe de "viajar" a "seguir".
def rapidez_de_seguimiento(distancia, cerca, lejos, d0=2.0, d1=10.0):
    if d1 <= d0:
        return lejos if distancia >= d1 else cerca
    t = min(1.0, max(0.0, (distancia - d0) / (d1 - d0)))
    return cerca + (lejos - cerca) * t * t * (3 - 2 * t)


# -- FOV dinámico al correr (T14) --

# ¿Corre el jugador? Por la velocidad real del objetivo (m/s): entre `umbral` (a medio camino entre
# caminar y correr) y `tope`. Por encima del tope no es correr sino un salto (cambio de turno,
# cinemática, teletransporte) y el FOV no se toca. Valores no finitos cuentan como "no corre".
def corriendo_por_velocidad(velocidad, umbral=6.5, tope=14.0):
    if not (velocidad == velocidad) or velocidad in (math.inf, -math.inf):
        return False
    return umbral <= velocidad <= tope


# Velocidad (m/s) del objetivo entre dos posiciones (x, z) separadas `dt` s (0 si dt <= 0).
def velocidad_del_objetivo(anterior, actual, dt):
    if dt <= 0 or anterior is None:
        return 0.0
    return math.hypot(actual[0] - anterior[0], actual[1] - anterior[1]) / dt


# Un paso del FOV hacia `base` (+ `extra` si corre) con la exponencial de geometria_mundo.suavizar,
# independiente de los fps. Sube con `rapidez_subir` (12 -> ~95% en 250 ms) y baja con `rapidez_bajar`
# (7,5 -> ~95% en 400 ms). Con dt <= 0 no cambia.
def fov_al_correr(actual, base, corriendo, dt, extra=4.0, rapidez_subir=12.0, rapidez_bajar=7.5):
    if dt <= 0:
        return actual
    objetivo = base + (extra if corriendo else 0.0)
    rapidez = rapidez_subir if objetivo > actual else rapidez_bajar
    return suavizar(actual, objetivo, rapidez, dt)


# -- Anillo de la baliza (T14) --

# Estado del anillo cian de la baliza en el instante `t` (s): (escala, alfa 0-1). Cada `periodo` s
# se expande de `desde` a `hasta` veces su radio (ease-out: arranca rápido y se frena) y se
# desvanece: sube en el primer 10% del ciclo (sin "pop") y baja a 0 al final, así el reinicio
# del ciclo es invisible. Continua en t y periódica.
def pulso_anillo(t, periodo=1.6, desde=1.0, hasta=1.6, alfa_max=0.85):
    if not (t == t) or periodo <= 0:
        return (desde, 0.0)
    fase = (t % periodo) / periodo
    avance = 1.0 - (1.0 - fase) ** 2
    entrada = min(1.0, fase / 0.10)
    salida = 1.0 - fase
    return (desde + (hasta - desde) * avance, alfa_max * entrada * salida)
