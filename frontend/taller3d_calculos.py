# Cálculos del TALLER 3D (frontend/taller3d_escena.py y taller3d_piezas.py). Python puro, sin ursina, con tests en
# tests/test_taller3d_calculos.py. Las reglas del turno no cambian (backend/logica/taller_ritmo.py): la calidad sigue
# siendo aciertos / notas y el pago sale de ella como siempre. Aquí solo se decide cómo SE VE la pieza según esa calidad
# (prístina y con brillo, o deforme y rugosa, con grados intermedios) y la curva del martillazo del personaje.
#
# Banderas (la variable de entorno manda sobre la constante):
#   TALLER3D            / ALCALDE_TALLER3D=0             el taller 2D de antes (frontend/taller_vista.JuegoTaller)
#   TALLER3D_VELOCIDAD  / ALCALDE_TALLER3D_VELOCIDAD=1.0 rapidez de las flechas del taller 3D (1,2 = un 20 % más
#                                                        rápidas: cruzan el carril en 2,5 s en vez de 3,0 s)
#   TALLER3D_CADENCIA   / ALCALDE_TALLER3D_CADENCIA=1.0  cuán seguidas llegan las flechas (1,4 = un 40 % más juntas:
#                                                        de 1,5-1,05 s entre flechas a 1,07-0,75 s)

import math
import os

from backend.logica.azar_fijo import azar_de

TALLER3D = True
TALLER3D_VELOCIDAD = 1.2
VELOCIDAD_MIN, VELOCIDAD_MAX = 0.5, 2.5
TALLER3D_CADENCIA = 1.4

# Calidad (0..1) a partir de la cual la pieza sale sin ninguna deformación, y desde la que empieza a brillar.
CALIDAD_PRISTINA = 0.9
CALIDAD_BRILLO = 0.7
# desplazamiento máximo de un vértice (fracción del tamaño de la pieza) con calidad 0
DEFORMACION_MAX = 0.16
# cuánto hunde cada golpe malo los vértices cercanos
PROFUNDIDAD_ABOLLADURA = 0.09
RADIO_ABOLLADURA = 0.22
OXIDO = (92, 62, 46)
# hierro en bruto: las partes que aún no se han forjado
SILUETA = (58, 56, 62)
# Martillazo (s): bajar, quedarse sobre la pieza, volver arriba (como el del taller 2D).
T_BAJAR, T_QUIETO, T_SUBIR = 0.07, 0.09, 0.22


def _bandera(nombre, constante):
    valor = os.environ.get(nombre, "").strip().lower()
    if valor in ("1", "true", "si", "sí", "on"):
        return True
    if valor in ("0", "false", "no", "off"):
        return False
    return bool(constante)


def activo():
    return _bandera("ALCALDE_TALLER3D", TALLER3D)


def _numero(nombre, constante):
    """Número de la variable de entorno `nombre` (acepta coma decimal), acotado; un valor raro cae a la constante."""
    texto = os.environ.get(nombre, "").strip().replace(",", ".")
    try:
        valor = float(texto) if texto else constante
    except ValueError:
        valor = constante
    if not math.isfinite(valor):
        valor = constante
    return max(VELOCIDAD_MIN, min(VELOCIDAD_MAX, valor))


def velocidad_flechas():
    """Multiplicador de la rapidez de las flechas (TurnoRitmo(velocidad=...))."""
    return _numero("ALCALDE_TALLER3D_VELOCIDAD", TALLER3D_VELOCIDAD)


def cadencia_flechas():
    """Cuán seguidas llegan las flechas (TurnoRitmo(cadencia=...))."""
    return _numero("ALCALDE_TALLER3D_CADENCIA", TALLER3D_CADENCIA)


# -- Calidad -> aspecto --

def grado_deformacion(calidad):
    """0 = prístina (calidad >= CALIDAD_PRISTINA) .. 1 = chatarra (calidad 0), lineal entre medias."""
    calidad = max(0.0, min(1.0, float(calidad)))
    if calidad >= CALIDAD_PRISTINA:
        return 0.0
    return (CALIDAD_PRISTINA - calidad) / CALIDAD_PRISTINA


def brillo(calidad):
    """0 (sin brillo, por debajo de CALIDAD_BRILLO) .. 1 (calidad perfecta)."""
    calidad = max(0.0, min(1.0, float(calidad)))
    return max(0.0, (calidad - CALIDAD_BRILLO) / (1.0 - CALIDAD_BRILLO))


def mezcla(a, b, k):
    k = max(0.0, min(1.0, k))
    return tuple(int(round(a[i] + (b[i] - a[i]) * k)) for i in range(3))


def tono_final(tono, calidad):
    """Color del material terminado: más claro y limpio si brilla, más oscuro y oxidado cuanto más deforme."""
    g, b = grado_deformacion(calidad), brillo(calidad)
    sucio = mezcla(tono, OXIDO, 0.65 * g)
    return mezcla(sucio, (255, 255, 255), 0.22 * b)


def desplazamiento(x, y, z, grado, semilla=0):
    """(dx, dy, dz) de un vértice en (x, y, z) (coordenadas de la pieza, ~1 de lado). Ruido SUAVE que depende solo de la
    posición: dos vértices en el mismo punto se mueven igual y la malla no se abre. Con grado 0 no mueve nada."""
    if grado <= 0:
        return (0.0, 0.0, 0.0)
    a = DEFORMACION_MAX * grado
    s = semilla * 1.618
    dx = math.sin(x * 7.1 + y * 3.3 + s) * math.cos(z * 5.7 - s)
    dy = math.sin(y * 6.3 + z * 4.1 + 2 * s) * math.cos(x * 4.9 + s)
    dz = math.sin(z * 6.7 + x * 3.9 - s) * math.cos(y * 5.3 + 2 * s)
    # grano fino encima (rugosidad): solo se nota en las piezas muy malas
    grano = 0.35 * grado * (azar_de(round(x, 3) * 31.7 + round(y, 3), round(z, 3) * 17.3 + s) - 0.5)
    return (a * (dx + grano), a * 0.6 * (dy + grano), a * (dz + grano))


def abolladuras(n, semilla=0, radio=0.42):
    """`n` centros de abolladura (x, y, z) repartidos de forma determinista sobre la pieza (un golpe malo = una)."""
    centros = []
    for i in range(max(0, int(n))):
        ang = 2 * math.pi * azar_de(i + 0.3, semilla + 0.7)
        r = radio * (0.35 + 0.65 * azar_de(i + 1.9, semilla + 2.1))
        centros.append((r * math.cos(ang), 0.05 + 0.25 * azar_de(i + 4.2, semilla), r * math.sin(ang)))
    return centros


def hundimiento(x, y, z, centros):
    """dy (negativo) que dejan las abolladuras en el vértice (x, y, z): campana suave alrededor de cada centro."""
    total = 0.0
    for cx, cy, cz in centros:
        d = math.sqrt((x - cx) ** 2 + (y - cy) ** 2 + (z - cz) ** 2)
        if d < RADIO_ABOLLADURA:
            k = 1 - d / RADIO_ABOLLADURA
            total -= PROFUNDIDAD_ABOLLADURA * k * k
    return total


def partes_hechas(progreso, n):
    """Cuántas de las `n` partes de la pieza ya están forjadas con el `progreso` (0..1) del turno."""
    return max(0, min(n, int(math.floor(max(0.0, progreso) * n + 1e-6))))


# -- Martillazo --

def bajada_martillo(g, torcido=False):
    """0 = martillo en alto .. 1 = sobre la pieza, a los `g` s del golpe (None = reposo). Torcido: se queda a 0,7."""
    if g is None:
        return 0.0
    tope = 0.7 if torcido else 1.0
    if g < T_BAJAR:
        return tope * (g / T_BAJAR) ** 2
    if g < T_BAJAR + T_QUIETO:
        return tope
    if g < T_BAJAR + T_QUIETO + T_SUBIR:
        f = (g - T_BAJAR - T_QUIETO) / T_SUBIR
        return tope * (1 - f) ** 2
    return 0.0


def golpe_terminado(g):
    return g is None or g >= T_BAJAR + T_QUIETO + T_SUBIR
