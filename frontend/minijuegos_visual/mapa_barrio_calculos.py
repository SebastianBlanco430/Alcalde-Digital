# Matemática del mapa del barrio del minijuego «Contrarreloj» visual (frontend/minijuegos_visual/contrarreloj_visual.py).
# Python puro, sin ursina, con tests en tests/test_mapa_barrio.py.
#
# Cada noticia es un foco (círculo) sobre una zona del mapa que crece con su difusión: la barra de difusión convertida en
# geografía. Frenar congela el círculo; dejar pasar lo expande hasta el borde con brillo verde. Al final se cuentan las zonas
# «contagiadas»: las que quedaron bajo el círculo de una noticia FALSA que no se frenó.
# Coordenadas del mapa normalizadas: x, y en [-0.5, 0.5] (la vista las escala al tamaño del panel).

import math

# Zonas del barrio (nombre, x, y). Nombres genéricos de Ciudad Nova.
ZONAS = (
    ("Morro", -0.30, 0.28),
    ("Feira", 0.05, 0.30),
    ("Escola", 0.32, 0.18),
    ("Praça", -0.05, 0.00),
    ("Igreja", -0.32, -0.20),
    ("Ponto", 0.28, -0.22),
    ("Campinho", 0.00, -0.32),
)

RADIO_MIN = 0.06
RADIO_MAX = 0.26
RADIO_LIBERADA = 0.30        # dejar pasar: se expande del todo
PITCH_BASE = 1.0
PITCH_MAX = 1.3
FRACCION_TENSA = 0.65        # a partir de esta fracción de tiempo gastado la música se acelera
SEGUNDOS_TICTAC = 5


def posicion_foco(i):
    """Centro (x, y) del foco de la noticia i: su zona con un pequeño desplazamiento para que no se tapen."""
    nombre, x, y = ZONAS[i % len(ZONAS)]
    vuelta = i // len(ZONAS)
    return x + 0.06 * vuelta, y - 0.05 * vuelta


def zona_de(i):
    return ZONAS[i % len(ZONAS)][0]


def radio_foco(propagacion):
    """Radio del círculo según cuánto se difundió (0..1)."""
    f = max(0.0, min(1.0, propagacion))
    return RADIO_MIN + (RADIO_MAX - RADIO_MIN) * f


def radio_objetivo(estado, propagacion, congelada=None):
    """Radio al que tiende el círculo según el estado de la noticia.
    pendiente: crece con la difusión; frenada: se queda donde se congeló; liberada / propagada: se expande del todo."""
    if estado == "frenada":
        return radio_foco(congelada if congelada is not None else 0.0)
    if estado in ("liberada", "propagada"):
        return RADIO_LIBERADA
    return radio_foco(propagacion)


def contagia(veraz, estado):
    """¿La noticia contagia el barrio? Solo una FALSA que se difundió (dejada pasar o sin juzgar)."""
    return (not veraz) and estado in ("liberada", "propagada")


def zonas_contagiadas(focos):
    """Índices de ZONAS bajo algún foco contagioso. `focos`: [(x, y, radio, contagia)]."""
    salida = set()
    for z, (_, zx, zy) in enumerate(ZONAS):
        for x, y, radio, contagioso in focos:
            if contagioso and math.hypot(zx - x, zy - y) <= radio:
                salida.add(z)
                break
    return salida


def texto_contagio(n, total=len(ZONAS)):
    """Mensaje del cierre (cabe en UNA línea de 17 px dentro de la cinta de noticias)."""
    if n == 0:
        return "Ninguna zona del barrio quedó contagiada."
    if n == 1:
        return "1 zona del barrio quedó contagiada."
    return f"{n} de {total} zonas quedaron contagiadas."


def pitch_musica(t, duracion):
    """Pitch de la música: normal hasta FRACCION_TENSA del tiempo y luego se acelera hasta PITCH_MAX."""
    if duracion <= 0:
        return PITCH_BASE
    f = max(0.0, min(1.0, t / duracion))
    if f <= FRACCION_TENSA:
        return PITCH_BASE
    return PITCH_BASE + (PITCH_MAX - PITCH_BASE) * (f - FRACCION_TENSA) / (1.0 - FRACCION_TENSA)


def tictac(restante_antes, restante_ahora, ultimos=SEGUNDOS_TICTAC):
    """¿Toca un tic-tac? Sí al cruzar un segundo entero dentro de los `ultimos` segundos."""
    if restante_ahora <= 0 or restante_ahora > ultimos:
        return False
    return math.ceil(restante_ahora) < math.ceil(restante_antes)


def brillo(t, frecuencia=1.6):
    """Pulso suave 0..1 para el halo del foco con el foco de teclado."""
    return 0.5 + 0.5 * math.sin(2 * math.pi * frecuencia * t)
