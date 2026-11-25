# Animación 2D de la Rádio Comunitária: la parte PURA (no importa ursina). Lo que dibuja está en
# frontend/radio_emision.py; el hilo conductor en docs/HILO_CONDUCTOR.md. Paso intermedio antes de una emisión en 3D.
#
# Todo es función del tiempo `t` (s desde que empezó la emisión) y de `voz` (0..1, cuánto «habla» la locutora), así la
# vista no guarda estado de animación y las pruebas no necesitan ventana. Coordenadas relativas al centro de la viñeta
# (cinematica_final: 1,44 x 0,56 unidades de camera.ui).
#
#   voz(t, hablando)                -> 0..1: envolvente con sílabas cuando habla, en reposo cuando calla
#   ondas(t, voz)                   -> [(radio, alfa)] de las ondas que salen a cada lado de la radio
#   estrellas(semilla, n)           -> [(x, y, tamaño, fase)] fijas para una emisión
#   brillo_estrella(t, fase)        -> 0.35..1: centelleo
#   letras_visibles(t, total, cps)  -> cuántas letras del texto se ven (máquina de escribir)
#   cielo(momento)                  -> (bandas [(y, alto, color)], astro {tipo, x, y, r, color}, con_estrellas)
#   altura_sol(momento, y0, t)      -> el sol sube por la mañana y se pone el día 7

import math
import random

ANCHO, ALTO = 1.44 - 0.02, 0.56 - 0.02      # interior de la viñeta (el marco de papel queda a la vista)
LETRAS_POR_SEGUNDO = 45.0
ONDAS_POR_LADO = 3
PERIODO_ONDA = 1.6                          # s que tarda una onda en salir y apagarse
RADIO_ONDA_MIN, RADIO_ONDA_MAX = 0.06, 0.24
MOMENTOS = ("noche", "manana", "puente")

# Bandas de cielo de arriba abajo (la viñeta mide ALTO): noche azul profundo, amanecer naranja-rosa, atardecer violeta.
_CIELOS = {
    "noche": ((20, 24, 52), (28, 34, 72), (40, 46, 92)),
    "manana": ((122, 170, 214), (238, 168, 140), (250, 196, 120)),
    "puente": ((46, 30, 70), (98, 52, 92), (196, 98, 82)),
}
_ASTROS = {
    "noche": {"tipo": "luna", "x": 0.52, "y": 0.17, "r": 0.045, "color": (236, 232, 210)},
    "manana": {"tipo": "sol", "x": -0.5, "y": -0.13, "r": 0.075, "color": (255, 214, 102)},
    "puente": {"tipo": "sol", "x": 0.5, "y": -0.16, "r": 0.065, "color": (255, 150, 90)},
}


def voz(t, hablando):
    """Envolvente de voz: suma de senos que imitan sílabas (0,25..1) cuando habla; un respiro suave (0..0,12) si no."""
    if not hablando:
        return 0.06 + 0.06 * math.sin(t * 1.3)
    silabas = abs(math.sin(t * 8.7)) * 0.55 + abs(math.sin(t * 13.3 + 1.1)) * 0.3 + abs(math.sin(t * 3.1)) * 0.15
    return max(0.25, min(1.0, silabas))


def ondas(t, intensidad):
    """[(radio, alfa)] para ONDAS_POR_LADO ondas desfasadas: crecen de RADIO_ONDA_MIN a MAX y se apagan al salir.
    `intensidad` (0..1, la voz) escala el alfa: callada, las ondas casi no se ven."""
    salida = []
    for k in range(ONDAS_POR_LADO):
        fase = ((t / PERIODO_ONDA) + k / ONDAS_POR_LADO) % 1.0
        radio = RADIO_ONDA_MIN + (RADIO_ONDA_MAX - RADIO_ONDA_MIN) * fase
        alfa = (1.0 - fase) * (0.25 + 0.75 * max(0.0, min(1.0, intensidad)))
        salida.append((radio, alfa))
    return salida


def estrellas(semilla=7, n=16):
    """Estrellas fijas en la mitad de arriba, sin tapar la radio (centro) ni el astro. Deterministas por semilla."""
    azar = random.Random(semilla)
    salida = []
    while len(salida) < n:
        x = azar.uniform(-ANCHO / 2 + 0.04, ANCHO / 2 - 0.04)
        y = azar.uniform(0.0, ALTO / 2 - 0.03)
        if abs(x) < 0.3 and y < 0.2:            # hueco de la radio y del letrero
            continue
        salida.append((x, y, azar.uniform(0.006, 0.012), azar.uniform(0.0, math.tau)))
    return salida


def brillo_estrella(t, fase):
    return 0.35 + 0.65 * (0.5 + 0.5 * math.sin(t * 2.4 + fase))


def letras_visibles(t, total, cps=LETRAS_POR_SEGUNDO):
    return max(0, min(int(total), int(t * cps)))


BANDAS_CIELO = 6
SUBIDA_SOL = 0.012                          # unidades por segundo que sube el sol de la mañana (baja el del día 7)
RECORRIDO_SOL = 0.09                        # tope de ese movimiento


def _mezcla(a, b, f):
    return tuple(int(round(x + (y - x) * f)) for x, y in zip(a, b))


def degradado(tonos, n=BANDAS_CIELO):
    """n tonos interpolados entre los `tonos` de referencia (de arriba abajo). Pura."""
    if n <= 1 or len(tonos) == 1:
        return [tuple(tonos[0])] * max(1, n)
    salida = []
    for k in range(n):
        pos = k / (n - 1) * (len(tonos) - 1)
        i = min(int(pos), len(tonos) - 2)
        salida.append(_mezcla(tonos[i], tonos[i + 1], pos - i))
    return salida


def altura_sol(momento, y0, t):
    """y del sol en el instante t: la mañana sube, el día 7 se pone; la noche no tiene sol."""
    paso = min(RECORRIDO_SOL, SUBIDA_SOL * max(0.0, t))
    return y0 + paso if momento == "manana" else y0 - paso if momento == "puente" else y0


def cielo(momento):
    """(bandas, astro, con_estrellas) del momento; uno desconocido se pinta como la noche."""
    momento = momento if momento in MOMENTOS else "noche"
    tonos = degradado(_CIELOS[momento])
    alto = ALTO / len(tonos)
    bandas = [(ALTO / 2 - alto * (k + 0.5), alto, tono) for k, tono in enumerate(tonos)]
    return bandas, dict(_ASTROS[momento]), momento in ("noche", "puente")


def silueta(semilla=3, n=14):
    """Casas de la ladera al fondo: [(x, ancho, alto)] de izquierda a derecha cubriendo el ancho de la viñeta."""
    azar = random.Random(semilla)
    ancho = ANCHO / n
    return [(-ANCHO / 2 + ancho * (k + 0.5), ancho * azar.uniform(0.85, 1.05), azar.uniform(0.05, 0.13))
            for k in range(n)]
