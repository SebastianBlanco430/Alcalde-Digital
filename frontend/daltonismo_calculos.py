# Matemática pura (sin ursina/panda3d) del FILTRO DE DALTONISMO: una transformación de color
#   salida = M · lineal(entrada) + d        (M matriz 3x3, d desplazamiento; todo en RGB LINEAL)
# que el shader de pantalla aplica a cada píxel (mundo 3D + interfaz). El shader convierte sRGB -> lineal
# antes y lineal -> sRGB después.
#
# Dos usos de las matrices de visión (Machado, Oliveira y Fernandes 2009, severidad 1.0, RGB lineal):
#   - SIMULACIÓN: cómo percibe la imagen alguien con ese tipo (para diseñar y para las muestras de Ajustes).
#   - DALTONIZACIÓN (lo que usa el jugador por defecto): se calcula el error e = c - simular(c) (lo que esa
#     persona NO ve) y se reparte en los canales que sí distingue: c' = c + R·e, con R el reparto de
#     Fidaner/Lindsey/Fidaner (2005). Es lineal, así que se funde en UNA matriz: M = I + R·(I - S).
# La `intensidad` (0..1) mezcla linealmente entre la identidad y la transformación completa.
# Acromatopsia: sin color no se corrige el tono; se pasa a luminancia con un poco de contraste para que
# las diferencias de brillo se noten. Alto contraste: más saturación y contraste (no es un tipo de visión).

import math

MODOS = ("ninguno", "protanopia", "deuteranopia", "tritanopia", "acromatopsia", "alto_contraste")

IDENTIDAD = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))
SIN_DESPLAZAMIENTO = (0.0, 0.0, 0.0)

# Luminancia Rec. 709 (RGB lineal).
LUMINANCIA = (0.2126, 0.7152, 0.0722)

# Matrices de SIMULACIÓN (Machado 2009, severidad 1.0), RGB lineal, por filas.
SIMULACION = {
    "protanopia": (
        (0.152286, 1.052583, -0.204868),
        (0.114503, 0.786281, 0.099216),
        (-0.003882, -0.048116, 1.051998),
    ),
    "deuteranopia": (
        (0.367322, 0.860646, -0.227968),
        (0.280085, 0.672501, 0.047413),
        (-0.011820, 0.042940, 0.968881),
    ),
    "tritanopia": (
        (1.255528, -0.076749, -0.178779),
        (-0.078411, 0.930809, 0.147602),
        (0.004733, 0.691367, 0.303900),
    ),
}

# Reparto del error (qué canales reciben lo que la persona no ve). Rojo/verde -> a verde y azul;
# azul-amarillo -> a rojo y verde.
REPARTO = {
    "protanopia": ((0.0, 0.0, 0.0), (0.7, 1.0, 0.0), (0.7, 0.0, 1.0)),
    "deuteranopia": ((0.0, 0.0, 0.0), (0.7, 1.0, 0.0), (0.7, 0.0, 1.0)),
    "tritanopia": ((1.0, 0.0, 0.7), (0.0, 1.0, 0.7), (0.0, 0.0, 0.0)),
}

# Acromatopsia (daltonización): luminancia y un contraste suave alrededor del gris medio.
CONTRASTE_ACROMATOPSIA = 1.15
# Alto contraste: saturación y contraste.
SATURACION_ALTO_CONTRASTE = 1.30
CONTRASTE_ALTO = 1.18
# Pivote del contraste en RGB lineal. Con 0.5 (gris medio lineal) las sombras por debajo de ~sRGB 70 salian negras
# (acromatopsia y alto contraste): con 0.02 las sombras se conservan (sRGB 40 queda en 40).
GRIS_MEDIO = 0.02


def _producto(a, b):
    return tuple(tuple(sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)) for i in range(3))


def _resta(a, b):
    return tuple(tuple(a[i][j] - b[i][j] for j in range(3)) for i in range(3))


def _suma(a, b):
    return tuple(tuple(a[i][j] + b[i][j] for j in range(3)) for i in range(3))


def _mezcla(a, b, t):
    return tuple(tuple(a[i][j] + (b[i][j] - a[i][j]) * t for j in range(3)) for i in range(3))


def _escala(m, k):
    return tuple(tuple(v * k for v in fila) for fila in m)


# Intensidad válida: número finito en [0, 1]; lo demás -> 1.0.
def _intensidad(valor):
    if isinstance(valor, bool) or not isinstance(valor, (int, float)) or not math.isfinite(valor):
        return 1.0
    return min(1.0, max(0.0, float(valor)))


# Matriz de daltonización PLENA (intensidad 1) de un modo.
def _matriz_correccion(modo):
    if modo in SIMULACION:
        s = SIMULACION[modo]
        return _suma(IDENTIDAD, _producto(REPARTO[modo], _resta(IDENTIDAD, s)))
    if modo == "acromatopsia":
        gris = (LUMINANCIA, LUMINANCIA, LUMINANCIA)
        return _escala(gris, CONTRASTE_ACROMATOPSIA)
    if modo == "alto_contraste":
        gris = (LUMINANCIA, LUMINANCIA, LUMINANCIA)
        saturada = _mezcla(gris, IDENTIDAD, SATURACION_ALTO_CONTRASTE)      # t > 1 extrapola: más saturación
        return _escala(saturada, CONTRASTE_ALTO)
    return IDENTIDAD


# Desplazamiento plano (contraste alrededor del gris medio) de un modo con intensidad 1.
def _desplazamiento_pleno(modo):
    if modo == "acromatopsia":
        d = GRIS_MEDIO * (1.0 - CONTRASTE_ACROMATOPSIA)
        return (d, d, d)
    if modo == "alto_contraste":
        d = GRIS_MEDIO * (1.0 - CONTRASTE_ALTO)
        return (d, d, d)
    return SIN_DESPLAZAMIENTO


def _modo_valido(modo):
    return modo if isinstance(modo, str) and modo in MODOS else "ninguno"


# Matriz 3x3 (tupla de 3 filas) del filtro de CORRECCIÓN para `modo` a `intensidad`. 'ninguno' o
# intensidad 0 -> identidad. Modos o intensidades inválidos se tratan como 'ninguno' / 1.0.
def matriz_3x3(modo, intensidad=1.0):
    modo = _modo_valido(modo)
    if modo == "ninguno":
        return IDENTIDAD
    return _mezcla(IDENTIDAD, _matriz_correccion(modo), _intensidad(intensidad))


# Desplazamiento (3 valores) que acompaña a la matriz (solo hay en acromatopsia y alto contraste).
def desplazamiento(modo, intensidad=1.0):
    modo = _modo_valido(modo)
    t = _intensidad(intensidad)
    return tuple(v * t for v in _desplazamiento_pleno(modo))


# Matriz 3x3 de SIMULACIÓN (cómo lo ve esa persona). Para acromatopsia, luminancia pura; para
# 'ninguno' y 'alto_contraste' (que no son tipos de visión), identidad.
def matriz_simulacion_3x3(modo, intensidad=1.0):
    modo = _modo_valido(modo)
    t = _intensidad(intensidad)
    if modo in SIMULACION:
        return _mezcla(IDENTIDAD, SIMULACION[modo], t)
    if modo == "acromatopsia":
        return _mezcla(IDENTIDAD, (LUMINANCIA, LUMINANCIA, LUMINANCIA), t)
    return IDENTIDAD


# Parámetros listos para el shader: (matriz 3x3, desplazamiento) según corrija o simule.
def parametros(modo, intensidad=1.0, simular=False):
    if simular:
        return matriz_simulacion_3x3(modo, intensidad), SIN_DESPLAZAMIENTO
    return matriz_3x3(modo, intensidad), desplazamiento(modo, intensidad)


# ¿El filtro no cambia nada (se puede apagar el pase de pantalla)?
def es_identidad(modo, intensidad=1.0, simular=False):
    matriz, d = parametros(modo, intensidad, simular)
    return all(abs(matriz[i][j] - IDENTIDAD[i][j]) < 1e-9 for i in range(3) for j in range(3)) \
        and all(abs(v) < 1e-9 for v in d)


# --- sRGB <-> lineal (el shader hace lo mismo con la fórmula exacta) ---

def srgb_a_lineal(v):
    return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4


def lineal_a_srgb(v):
    v = min(1.0, max(0.0, v))
    return v * 12.92 if v <= 0.0031308 else 1.055 * v ** (1 / 2.4) - 0.055


# Aplica el filtro a un color RGB (0-255) en el procesador; es lo mismo que hace el shader por píxel.
# Sirve para las muestras de color de Ajustes y para probar sin ventana.
def aplicar_a_color(rgb255, modo, intensidad=1.0, simular=False):
    matriz, d = parametros(modo, intensidad, simular)
    lineal = [srgb_a_lineal(c / 255.0) for c in rgb255[:3]]
    salida = []
    for i in range(3):
        v = sum(matriz[i][j] * lineal[j] for j in range(3)) + d[i]
        salida.append(int(round(lineal_a_srgb(v) * 255)))
    return tuple(salida)


# Muestras de color que se enseñan en Ajustes: pares que confunden las personas con daltonismo
# (rojo/verde, verde/marrón, azul/amarillo...) más los colores del propio juego.
MUESTRAS = (
    ("Rojo", (214, 62, 62)),
    ("Verde", (80, 190, 110)),
    ("Naranja", (235, 140, 60)),
    ("Azul", (66, 133, 244)),
    ("Amarillo", (255, 220, 60)),
    ("Cian", (70, 220, 255)),
    ("Rosa", (232, 84, 150)),
    ("Violeta", (140, 110, 200)),
)


# Diferencia perceptual aproximada entre dos colores 0-255 (distancia euclídea en sRGB ponderada, "redmean").
def distancia_color(a, b):
    rm = (a[0] + b[0]) / 2
    dr, dg, db = a[0] - b[0], a[1] - b[1], a[2] - b[2]
    return math.sqrt((2 + rm / 256) * dr * dr + 4 * dg * dg + (2 + (255 - rm) / 256) * db * db)
