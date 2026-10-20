# Gestos del rostro de los personajes con modelo .glb (NO importa ursina ni panda3d).
# Todo es determinista por tiempo y semilla (sin random ni estado): el mismo (t, semilla) da siempre
# el mismo valor, así que se puede probar y no hace falta guardar nada entre frames.
# frontend/rostro_modelo.py traduce estos números a la posición y escala de las piezas del rostro.
#
# Convenciones: parpadeo, apertura de boca, sonrisa, alza y fruncido de cejas van de 0 a 1;
# la mirada va de -1 a 1 (x: hacia la derecha del personaje, z: hacia arriba; 0 = centro).
# Clips: los mismos nombres que frontend/modelo_calculos.py (Idle, Caminar, Correr, Saludar, Hablar).

import math

IDLE, CAMINAR, CORRER, SALUDAR, HABLAR = "Idle", "Caminar", "Correr", "Saludar", "Hablar"

# -- Parpadeo --
RANURA_PARPADEO = 4.0            # s: una ranura por parpadeo; el inicio cae en sus primeros 2 s
DURACION_PARPADEO = 0.12         # s de cerrar y reabrir
SEPARACION_DOBLE = 0.26          # s entre los dos parpadeos de un doble
PROB_DOBLE = 0.2
# Con ranuras de 4 s e inicio en [0, 2) la separación entre parpadeos queda entre 2 y 6 s.

# -- Mirada --
RANURA_MIRADA = 1.0              # s: un punto de mira nuevo por ranura
TRANSICION_MIRADA = 0.07         # s que dura la sacada (salto rápido)

# -- Boca --
RANURA_SILABA = 0.21             # s por sílaba (~4.7 sílabas/s)
PROB_PAUSA = 0.14                # sílabas que se saltan (respiro entre palabras)

# Gesto base por clip: sonrisa, alza y fruncido de cejas, apertura de la boca, cierre parcial
# de párpados (entrecerrar al sonreír) y cuánto se mueve la mirada (1 = normal).
PERFIL_CLIP = {
    IDLE:    {"sonrisa": 0.30, "alza": 0.08, "frunce": 0.00, "boca": 0.00, "entorna": 0.00, "mirada": 1.0},
    CAMINAR: {"sonrisa": 0.30, "alza": 0.05, "frunce": 0.06, "boca": 0.02, "entorna": 0.00, "mirada": 0.6},
    CORRER:  {"sonrisa": 0.05, "alza": 0.00, "frunce": 0.38, "boca": 0.20, "entorna": 0.10, "mirada": 0.3},
    SALUDAR: {"sonrisa": 1.00, "alza": 0.70, "frunce": 0.00, "boca": 0.30, "entorna": 0.22, "mirada": 0.5},
    HABLAR:  {"sonrisa": 0.40, "alza": 0.15, "frunce": 0.00, "boca": 0.00, "entorna": 0.00, "mirada": 0.8},
}


def acotar(valor, minimo=0.0, maximo=1.0):
    # Total: un NaN o None se queda en el mínimo.
    try:
        if valor != valor:
            return minimo
        return max(minimo, min(maximo, float(valor)))
    except (TypeError, ValueError):
        return minimo


def _suave(x):
    x = acotar(x)
    return x * x * (3.0 - 2.0 * x)


def _azar(k, semilla, canal):
    # Hash entero -> número en [0, 1). Determinista y sin estado.
    x = (int(k) * 374761393 + int(semilla) * 668265263 + int(canal) * 2246822519 + 144665) & 0xFFFFFFFF
    x = ((x ^ (x >> 13)) * 1274126177) & 0xFFFFFFFF
    x = ((x ^ (x >> 16)) * 2246822519) & 0xFFFFFFFF
    return (x ^ (x >> 15)) / 4294967296.0


def _ruido(t, semilla, canal, periodo):
    # Ruido de valor continuo en [0, 1]: interpola con suavizado entre puntos al azar.
    u = t / periodo
    k = math.floor(u)
    f = _suave(u - k)
    return _azar(k, semilla, canal) * (1.0 - f) + _azar(k + 1, semilla, canal) * f


def _perfil(clip):
    return PERFIL_CLIP.get(clip) or PERFIL_CLIP[IDLE]


# -- Parpadeo --

def _pulso_parpadeo(dt):
    # Perfil de un parpadeo: cierra rápido (40 %) y reabre más despacio. 0 fuera de [0, duración].
    s = dt / DURACION_PARPADEO
    if s <= 0.0 or s >= 1.0:
        return 0.0
    if s < 0.4:
        return _suave(s / 0.4)
    return _suave(1.0 - (s - 0.4) / 0.6)


def parpadeo(t, semilla=0):
    # Cierre del párpado, 0 abierto y 1 cerrado del todo.
    t = acotar(t, 0.0, 1e9)
    k = math.floor(t / RANURA_PARPADEO)
    inicio = k * RANURA_PARPADEO + 2.0 * _azar(k, semilla, 1)
    cierre = _pulso_parpadeo(t - inicio)
    if _azar(k, semilla, 2) < PROB_DOBLE:
        cierre = max(cierre, _pulso_parpadeo(t - inicio - SEPARACION_DOBLE))
    return cierre


# -- Mirada --

def _punto_mira(k, semilla):
    # Punto de mira de la ranura k: a menudo el centro, a veces un poco a un lado o arriba/abajo.
    if _azar(k, semilla, 3) < 0.35:
        return 0.0, 0.0
    return (_azar(k, semilla, 4) * 2.0 - 1.0) * 0.45, (_azar(k, semilla, 5) * 2.0 - 1.0) * 0.25


def mirada(t, semilla=0, giro=0.0, escala=1.0):
    # (x, z) de -1 a 1. Sacadas rápidas entre puntos de mira; `giro` (-1..1, + hacia la derecha del
    # personaje) la arrastra hacia donde gira o camina; `escala` apaga las sacadas (correr).
    t = acotar(t, 0.0, 1e9)
    k = math.floor(t / RANURA_MIRADA)
    inicio = k * RANURA_MIRADA + 0.5 * _azar(k, semilla, 6)
    f = _suave((t - inicio) / TRANSICION_MIRADA)
    xa, za = _punto_mira(k - 1, semilla)
    xb, zb = _punto_mira(k, semilla)
    x = (xa + (xb - xa) * f) * acotar(escala, 0.0, 2.0) + 0.85 * acotar(giro, -1.0, 1.0)
    z = (za + (zb - za) * f) * acotar(escala, 0.0, 2.0)
    return acotar(x, -1.0, 1.0), acotar(z, -1.0, 1.0)


# -- Boca --

def apertura_silaba(t, semilla=0):
    # Apertura de la boca al pronunciar: una sílaba por ranura, con fuerza variable, algún
    # respiro y siempre cerrada entre sílabas. 0..1.
    t = acotar(t, 0.0, 1e9)
    k = math.floor(t / RANURA_SILABA)
    if _azar(k, semilla, 7) < PROB_PAUSA:
        return 0.0
    fuerza = 0.30 + 0.70 * _azar(k, semilla, 8)
    u = t / RANURA_SILABA - k
    return fuerza * math.sin(math.pi * u) ** 0.8


def jadeo(t, semilla=0):
    # Boca entreabierta que respira al correr: 0..1 alrededor de 0.5, ~2.7 Hz con algo de variación.
    t = acotar(t, 0.0, 1e9)
    fase = 2.0 * math.pi * 2.7 * t + 1.7 * _ruido(t, semilla, 9, 1.5)
    return 0.5 + 0.5 * math.sin(fase)


# -- Cejas --

def _enfasis(t, semilla):
    # Subidas de ceja al hablar: en la mitad de las ranuras de 1.1 s hay un énfasis de 0.45 s.
    ranura = 1.1
    k = math.floor(t / ranura)
    if _azar(k, semilla, 10) < 0.5:
        return 0.0
    inicio = k * ranura + 0.3 * _azar(k, semilla, 11)
    s = (t - inicio) / 0.45
    if s <= 0.0 or s >= 1.0:
        return 0.0
    return (0.45 + 0.55 * _azar(k, semilla, 12)) * math.sin(math.pi * s) ** 2


# -- Mezcla por clip --

def gesto(t, clip, semilla=0, giro=0.0):
    # Todo el gesto del instante t como una tupla de 7 números:
    # (cierre, mirada_x, mirada_z, alza, frunce, apertura, sonrisa). `entorna` ya va en cierre.
    # Total: un clip desconocido se trata como Idle y un tiempo inválido como 0.
    t = acotar(t, 0.0, 1e9)
    p = _perfil(clip)
    cierre = max(parpadeo(t, semilla), p["entorna"])
    mx, mz = mirada(t, semilla, giro, p["mirada"])
    alza = p["alza"] + 0.10 * _ruido(t, semilla, 13, 1.3)          # micro-movimiento de cejas
    frunce = p["frunce"]
    apertura = p["boca"]
    if clip == HABLAR:
        apertura = max(apertura, apertura_silaba(t, semilla))
        alza += 0.80 * _enfasis(t, semilla)
    elif clip == CORRER:
        apertura = 0.12 + 0.22 * jadeo(t, semilla)
        frunce += 0.10 * _ruido(t, semilla, 14, 0.8)
    elif clip == SALUDAR:
        apertura += 0.10 * _ruido(t, semilla, 15, 0.6)
    sonrisa = p["sonrisa"] + 0.08 * (_ruido(t, semilla, 16, 2.0) - 0.5)
    return (acotar(cierre), mx, mz, acotar(alza), acotar(frunce), acotar(apertura), acotar(sonrisa))


def suavizar(actual, objetivo, dt, tiempo=0.12):
    # Acerca `actual` a `objetivo` con una exponencial (tiempo = constante en s). Total.
    dt = acotar(dt, 0.0, 1.0)
    f = 1.0 - math.exp(-dt / max(1e-4, tiempo))
    return actual + (objetivo - actual) * f
