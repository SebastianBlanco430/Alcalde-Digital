# Matemática PURA (sin ursina ni panda3d) del traspaso de mano a mano del vendedor de la calle.
# Secuencia de 1,65 s en cinco fases: girar, estirar, volar, recibir y recoger. La compra ya está hecha cuando
# empieza: esto es solo presentación (la bolsita viaja de la mano del vendedor a la del jugador).

import math

FASES = (("girar", 0.30), ("estirar", 0.35), ("volar", 0.45), ("recibir", 0.20), ("recoger", 0.35))
DISTANCIA_TRASPASO = 1.0         # m máximos entre vendedor y jugador durante el traspaso
ARCO_BOLSITA = 0.06              # m que sube la bolsita en mitad del vuelo
GIRO_BOLSITA = 25.0              # grados de giro en mitad del vuelo


def duracion_total():
    return sum(d for _, d in FASES)


def _suave(x):
    x = max(0.0, min(1.0, x))
    return x * x * (3 - 2 * x)


# (nombre de la fase, avance 0..1 dentro de ella) para el instante t (segundos). Fuera de rango se acota.
def fase_en(t):
    try:
        t = float(t)
    except (TypeError, ValueError):
        t = 0.0
    if t != t or t <= 0.0:
        return FASES[0][0], 0.0
    acumulado = 0.0
    for nombre, duracion in FASES:
        if t < acumulado + duracion:
            return nombre, (t - acumulado) / duracion
        acumulado += duracion
    return FASES[-1][0], 1.0


# Peso (0..1) del gesto de los brazos: sube al estirar, se mantiene al volar y recibir y baja al recoger.
def peso_gesto(t):
    fase, k = fase_en(t)
    if fase == "girar":
        return 0.0
    if fase == "estirar":
        return _suave(k)
    if fase in ("volar", "recibir"):
        return 1.0
    return 1.0 - _suave(k)


# Posición de la bolsita en el vuelo (k 0..1): interpolación suave con un arco de `arco` m hacia arriba (eje y).
# k=0 es exactamente el origen y k=1 exactamente el destino.
def posicion_bolsita(k, origen, destino, arco=ARCO_BOLSITA):
    if k <= 0.0:
        return tuple(float(c) for c in origen)
    if k >= 1.0:
        return tuple(float(c) for c in destino)
    s = _suave(k)
    x, y, z = (origen[i] + (destino[i] - origen[i]) * s for i in range(3))
    return (x, y + arco * math.sin(math.pi * k), z)


# Giro (grados) de la bolsita en el vuelo: nulo al salir y al llegar.
def giro_bolsita(k):
    return GIRO_BOLSITA * math.sin(math.pi * max(0.0, min(1.0, k)))


# Escala de la bolsita: aparece al estirar, tamaño completo al volar y recibir, se encoge al recoger.
def escala_bolsita(fase, k):
    if fase == "girar":
        return 0.0
    if fase == "estirar":
        return _suave(k)
    if fase in ("volar", "recibir"):
        return 1.0
    return 1.0 - _suave(k)


# Posición final del jugador: se queda donde está si ya está a `distancia` o menos del vendedor; si no, se
# acerca por la línea por la que llegó hasta quedar a `distancia`.
def posicion_jugador(vendedor, jugador, distancia=DISTANCIA_TRASPASO):
    dx, dz = jugador[0] - vendedor[0], jugador[1] - vendedor[1]
    d = math.hypot(dx, dz)
    if d <= distancia or d < 1e-9:
        return (float(jugador[0]), float(jugador[1]))
    return (vendedor[0] + dx / d * distancia, vendedor[1] + dz / d * distancia)


# Rumbo (grados, convención del juego: atan2(dx, dz)) de `origen` hacia `destino`.
def rumbo_hacia(origen, destino):
    return math.degrees(math.atan2(destino[0] - origen[0], destino[1] - origen[1]))
