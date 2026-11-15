# Entrada suave al computador de «La terminal» (cálculos puros: NO importa ursina). Lo aplica frontend/computador_mundo.py.
#
# Lo que se veía mal en la animación de siempre (mundo_digital_calculos.plan_sentarse):
#   - el paseo duraba siempre 0,6 s: de lejos el avatar «patinaba» a ~9 m/s con las piernas a ritmo de 3 m/s;
#   - el giro hacia la silla era instantáneo y la cámara se quedaba congelada mientras caminaba;
#   - la pose saltaba entre tramos (de media zancada a «parado», de «sentado» a «teclear»);
#   - la cámara iba en línea recta desde detrás del jugador al hombro (atravesándolo), se PARABA y volvía a arrancar
#     hacia el monitor, y el FOV saltaba a 65;
#   - el glitch subía en línea recta y cortaba de golpe.
# Ahora: giro previo con curva, paseo a velocidad de marcha con las piernas sincronizadas con la distancia, UNA sola
# trayectoria de cámara (curva de Catmull-Rom por la toma de partida, el hombro y el monitor, con el tiempo repartido
# por una curva de aceleración/frenado global: arranca y llega con velocidad cero y no se para a medio camino), la
# mirada pasa del avatar al monitor poco a poco, el FOV parte del actual, las poses se funden y el glitch entra con
# curva y se queda un instante a tope antes del cambio de escena.
# ENTRADA_TERMINAL_SUAVE = False (o ALCALDE_ENTRADA_TERMINAL_SUAVE=0) vuelve a la animación de siempre.

import math
import os

ENTRADA_TERMINAL_SUAVE = True
VELOCIDAD_MARCHA = 1.5           # m/s medios del paseo hasta la silla
DURACION_CAMINAR_MIN, DURACION_CAMINAR_MAX = 0.55, 2.6
GIRO_POR_SEGUNDO = 360.0         # grados/s del giro previo (con curva)
DURACION_GIRO_MIN, DURACION_GIRO_MAX = 0.0, 0.45
DURACION_SENTARSE = 0.9
DURACION_ACERCAR = 1.1
DURACION_GLITCH = 0.75
MESETA_GLITCH = 0.2              # fracción final del tramo con el glitch a tope
LARGO_ZANCADA = 1.3              # m por ciclo completo de piernas (dos pasos)
FUNDIDO_POSE = 0.3               # fracción del tramo en la que se funde la pose anterior con la nueva


def activa():
    valor = os.environ.get("ALCALDE_ENTRADA_TERMINAL_SUAVE", "").strip().lower()
    if valor in ("1", "true", "si", "sí", "on"):
        return True
    if valor in ("0", "false", "no", "off"):
        return False
    return bool(ENTRADA_TERMINAL_SUAVE)


def _acotar(t):
    return min(1.0, max(0.0, t))


# Curva de aceleración y frenado de orden 5: velocidad y aceleración cero en los extremos (más suave que smoothstep).
def suavizar(t):
    t = _acotar(t)
    return t * t * t * (t * (6 * t - 15) + 10)


def _normalizar(angulo):
    return (angulo + 180.0) % 360.0 - 180.0


def diferencia_angular(a, b):
    return _normalizar(b - a)


# Duraciones del plan para un paseo de `distancia` m y un giro de `giro` grados.
def duraciones(distancia, giro):
    caminar = min(DURACION_CAMINAR_MAX, max(DURACION_CAMINAR_MIN, distancia / VELOCIDAD_MARCHA))
    girar = min(DURACION_GIRO_MAX, max(DURACION_GIRO_MIN, abs(giro) / GIRO_POR_SEGUNDO))
    return {"girar": girar, "caminar": caminar, "sentarse": DURACION_SENTARSE, "acercar": DURACION_ACERCAR,
            "glitch": DURACION_GLITCH}


def plan(distancia, giro):
    d = duraciones(distancia, giro)
    return [(nombre, d[nombre]) for nombre in ("girar", "caminar", "sentarse", "acercar", "glitch")]


# Recorrido (0-1) del paseo en el instante t (0-1): arranca y frena con rampas cuadráticas en el 20 % de cada extremo
# y va a velocidad de marcha constante en el medio (continua en posición y velocidad; sin el pico de velocidad que daba
# un smoothstep puro a mitad de camino).
RAMPA_PASEO = 0.2


def avance_paseo(t, a=RAMPA_PASEO):
    t = _acotar(t)
    v = 1.0 / (1.0 - a)                      # velocidad de crucero para recorrer 1 en total
    if t < a:
        return 0.5 * v / a * t * t
    if t > 1.0 - a:
        r = 1.0 - t
        return 1.0 - 0.5 * v / a * r * r
    return 0.5 * v * a + v * (t - a)


# Velocidad relativa del paseo (0 parado, 1 crucero) en t: la misma forma de avance_paseo, para la intensidad de la marcha.
def velocidad_paseo(t, a=RAMPA_PASEO):
    t = _acotar(t)
    return min(1.0, t / a, (1.0 - t) / a)


# Fase de las piernas (radianes) tras recorrer `metros`: sincronizada con el suelo, sin patinar.
def fase_piernas(metros, fase_inicial=0.0):
    return (fase_inicial + 2 * math.pi * metros / LARGO_ZANCADA) % (2 * math.pi)


# Intensidad de la marcha (la de poses.pose_caminar) en t del paseo: sube y baja con la velocidad.
INTENSIDAD_MARCHA = 0.5


def intensidad_marcha(t):
    return INTENSIDAD_MARCHA * velocidad_paseo(t)


# Punto de una curva de Catmull-Rom CENTRÍPETA (alfa 0,5; algoritmo de Barry-Goldman) que pasa por `puntos` (lista
# de (x, y, z), al menos 2) en el parámetro global u (0-1), repartido por igual entre tramos. La centrípeta no hace
# picos ni bucles aunque los tramos midan muy distinto (la uniforme sí: la cámara daba un tirón cerca del hombro).
# Los extremos se prolongan con puntos fantasma.
def catmull_rom(puntos, u, alfa=0.5):
    puntos = [tuple(p) for p in puntos]
    if len(puntos) == 1:
        return puntos[0]
    n = len(puntos) - 1
    u = _acotar(u) * n
    i = min(n - 1, int(u))
    t = u - i
    p1, p2 = puntos[i], puntos[i + 1]
    p0 = puntos[i - 1] if i > 0 else tuple(2 * p1[k] - p2[k] for k in range(3))
    p3 = puntos[i + 2] if i + 2 <= n else tuple(2 * p2[k] - p1[k] for k in range(3))

    def nudo(ti, a, b):
        return ti + max(1e-6, math.dist(a, b)) ** alfa

    t0 = 0.0
    t1 = nudo(t0, p0, p1)
    t2 = nudo(t1, p1, p2)
    t3 = nudo(t2, p2, p3)
    x = t1 + (t2 - t1) * t

    def mezcla(a, b, ta, tb):
        f = (x - ta) / (tb - ta)
        return tuple(a[k] + (b[k] - a[k]) * f for k in range(3))

    a1, a2, a3 = mezcla(p0, p1, t0, t1), mezcla(p1, p2, t1, t2), mezcla(p2, p3, t2, t3)
    b1, b2 = mezcla(a1, a2, t0, t2), mezcla(a2, a3, t1, t3)
    return mezcla(b1, b2, t1, t2)


# Longitudes acumuladas (0-1) de la curva muestreada, para avanzar a velocidad uniforme por la distancia y no por el
# parámetro (los tramos de distinto largo no cambian de velocidad de golpe).
def tabla_longitud(puntos, muestras=256):
    previo = catmull_rom(puntos, 0.0)
    acumulado = [0.0]
    for k in range(1, muestras + 1):
        p = catmull_rom(puntos, k / muestras)
        acumulado.append(acumulado[-1] + math.dist(previo, p))
        previo = p
    total = acumulado[-1] or 1.0
    return [a / total for a in acumulado]


# Parámetro u de la curva para la fracción de longitud `s` (0-1), con la tabla de tabla_longitud.
def parametro_por_longitud(tabla, s):
    s = _acotar(s)
    muestras = len(tabla) - 1
    for k in range(1, len(tabla)):
        if tabla[k] >= s:
            tramo = tabla[k] - tabla[k - 1]
            f = 0.0 if tramo <= 0 else (s - tabla[k - 1]) / tramo
            return (k - 1 + f) / muestras
    return 1.0


# Toma intermedia de la cámara: entre la de partida y el hombro (a `fraccion` del camino), `alto` m más arriba. Así
# el polígono de control no hace ángulos agudos (ni retrocede si el jugador llega por el otro lado del escritorio) y la
# cámara pasa por encima del avatar en vez de atravesarlo.
def punto_acompanar(inicio, hombro, fraccion=0.35, alto=1.2):
    return (inicio[0] + (hombro[0] - inicio[0]) * fraccion, inicio[1] + (hombro[1] - inicio[1]) * fraccion + alto,
            inicio[2] + (hombro[2] - inicio[2]) * fraccion)


# Interpolación cúbica MONÓTONA (PCHIP, Fritsch-Carlson) de (xs, ys) en x, con pendiente cero en los extremos: pasa por
# todos los nudos, nunca retrocede y es C1 (sin tirones de velocidad). xs crecientes.
def pchip(xs, ys, x):
    n = len(xs)
    if x <= xs[0]:
        return ys[0]
    if x >= xs[-1]:
        return ys[-1]
    h = [xs[i + 1] - xs[i] for i in range(n - 1)]
    d = [(ys[i + 1] - ys[i]) / h[i] if h[i] > 0 else 0.0 for i in range(n - 1)]
    m = [0.0] * n
    for i in range(1, n - 1):
        if d[i - 1] * d[i] > 0:
            w1, w2 = 2 * h[i] + h[i - 1], h[i] + 2 * h[i - 1]
            m[i] = (w1 + w2) / (w1 / d[i - 1] + w2 / d[i])
    i = max(k for k in range(n - 1) if xs[k] <= x)
    t = (x - xs[i]) / h[i] if h[i] > 0 else 0.0
    t2, t3 = t * t, t * t * t
    return ((2 * t3 - 3 * t2 + 1) * ys[i] + (t3 - 2 * t2 + t) * h[i] * m[i]
            + (-2 * t3 + 3 * t2) * ys[i + 1] + (t3 - t2) * h[i] * m[i + 1])


class TrayectoriaCamara:
    """Cámara de la entrada: posición sobre la curva por `puntos`, avanzando por su LONGITUD. Sin `tiempos`, el tiempo
    total se reparte con suavizar(); con `tiempos` (instante en que la cámara pasa por cada punto, el primero 0 y el
    último `duracion_total`) el avance se interpola con pchip: la cámara llega a cada toma cuando toca (p. ej. al hombro
    solo cuando el avatar ya se sentó, así no le pasa rozando la espalda), arranca y llega parada y no da tirones.
    La mirada pasa de `mirar_inicio` a `mirar_fin` con otra curva."""

    def __init__(self, puntos, duracion_total, inicio_mirada=0.25, fin_mirada=0.7, tiempos=None):
        self.puntos = [tuple(p) for p in puntos]
        self.duracion = max(1e-6, duracion_total)
        self.tabla = tabla_longitud(self.puntos)
        self.inicio_mirada, self.fin_mirada = inicio_mirada, fin_mirada
        self.tiempos = None
        if tiempos is not None and len(tiempos) == len(self.puntos) and len(self.puntos) > 1:
            n, muestras = len(self.puntos) - 1, len(self.tabla) - 1
            self.tiempos = [float(t) for t in tiempos]
            self.longitudes = [self.tabla[round(k * muestras / n)] for k in range(n + 1)]

    def fraccion(self, tiempo):
        if self.tiempos is None:
            return suavizar(tiempo / self.duracion)
        return pchip(self.tiempos, self.longitudes, tiempo)

    def posicion(self, tiempo):
        return catmull_rom(self.puntos, parametro_por_longitud(self.tabla, self.fraccion(tiempo)))

    # Peso (0-1) del objetivo final en la mirada a la fracción de tiempo dada.
    def peso_mirada(self, tiempo):
        f = tiempo / self.duracion
        return suavizar((f - self.inicio_mirada) / max(1e-6, self.fin_mirada - self.inicio_mirada))

    def mirada(self, tiempo, mirar_inicio, mirar_fin):
        w = self.peso_mirada(tiempo)
        return tuple(mirar_inicio[k] + (mirar_fin[k] - mirar_inicio[k]) * w for k in range(3))


# FOV en la fracción `f` (0-1) del recorrido de cámara: se mantiene el actual y se cierra hacia el del monitor en la
# segunda mitad, con curva.
def fov(f, inicial, final):
    w = suavizar((f - 0.45) / 0.55)
    return inicial + (final - inicial) * w


# Intensidad del glitch en t (0-1) del tramo: entra con aceleración y se queda a tope en la meseta final.
def intensidad_glitch(t):
    subida = 1.0 - MESETA_GLITCH
    return 1.0 if t >= subida else suavizar(t / subida) ** 1.4
