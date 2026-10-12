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

from frontend.geometria_mundo import normalizar_angulo

ALTURA_PIVOTE = 1.5


# Pivote (x, y, z) al que apunta la cámara: la cabeza del personaje en (x, z).
def pivote_del_jugador(x, z, altura=ALTURA_PIVOTE):
    return (x, altura, z)


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


# Rueda del ratón: rueda > 0 (hacia adelante) acerca, < 0 aleja. Cada "clic" mueve `paso` m.
def aplicar_zoom(distancia, rueda, dmin, dmax, paso=0.6):
    return min(dmax, max(dmin, distancia - rueda * paso))


# Distancia real de la cámara cuando un raycast desde el pivote hacia ella golpea algo a
# `distancia_impacto` (None = no golpeó nada): d = min(deseada, max(dmin, impacto − margen)).
def distancia_con_colision(deseada, distancia_impacto, margen, dmin=1.0):
    if distancia_impacto is None:
        return deseada
    return min(deseada, max(dmin, distancia_impacto - margen))


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
    t = min(1.0, max(0.0, (distancia - d0) / (d1 - d0)))
    return cerca + (lejos - cerca) * t * t * (3 - 2 * t)
