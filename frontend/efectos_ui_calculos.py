# Curvas y tiempos de la capa común de efectos de interfaz (frontend/efectos_ui.py). Python puro, sin ursina, con tests en
# tests/test_efectos_ui.py. Aquí solo hay matemática: cuánto se agranda una tarjeta, cuánto tiembla, cómo cae un sello,
# cuántas estrellas vale un resultado... La vista solo aplica estos números.
#
# REDUCIR MOVIMIENTO: todas las funciones con movimiento aceptan `reducir`. Con reducir=True no hay rebotes, temblores,
# destellos ni partículas: la curva queda plana (el estado final directamente) o un fundido suave.

import math
import random

# -- Duraciones (s) --
DUR_REBOTE = 0.38
DUR_PULSO = 0.22
DUR_TEMBLOR = 0.42
DUR_DESTELLO = 0.45
DUR_SELLO = 0.34
DUR_PARTICULA = 0.7

ESCALA_FOCO = 1.035          # cuánto crece una tarjeta con el foco
ESCALA_ENTRADA = 0.82        # desde qué tamaño entra una tarjeta
HUNDIDO_PULSO = 0.09         # cuánto se encoge al elegirla
AMPLITUD_TEMBLOR = 0.014     # unidades de camera.ui
FRECUENCIA_TEMBLOR = 11.0    # Hz
ESCALA_SELLO_INICIAL = 2.6
TONO_MAX_RACHA = 8           # a partir de aquí el tono deja de subir
PASO_TONO = 0.07
GRAVEDAD_PARTICULA = -1.6    # unidades/s²


def _progreso(t, dur):
    if dur <= 0:
        return 1.0
    return max(0.0, min(1.0, t / dur))


def salida_atras(p):
    """easeOutBack: de 0 a 1 pasándose un poco (el «rebote»)."""
    c1 = 1.70158
    c3 = c1 + 1
    q = p - 1
    return 1 + c3 * q ** 3 + c1 * q ** 2


def rebote(t, dur=DUR_REBOTE, desde=ESCALA_ENTRADA, reducir=False):
    """Multiplicador de escala de una tarjeta que entra: de `desde` a 1 con un pequeño rebote. t<0 = aún no entra."""
    if reducir:
        return 1.0
    if t < 0:
        return desde
    return desde + (1.0 - desde) * salida_atras(_progreso(t, dur))


def pulso_eleccion(t, dur=DUR_PULSO, reducir=False):
    """Multiplicador al elegir una tarjeta: se encoge y vuelve (1 -> 1-HUNDIDO -> 1)."""
    if reducir or t < 0 or t >= dur:
        return 1.0
    return 1.0 - HUNDIDO_PULSO * math.sin(math.pi * _progreso(t, dur))


def acercar(actual, objetivo, dt, tiempo=0.09):
    """Aproximación exponencial de `actual` a `objetivo` (suave e independiente de los fps)."""
    if tiempo <= 0 or dt <= 0:
        return objetivo if dt > 0 or tiempo <= 0 else actual
    k = 1.0 - math.exp(-dt / tiempo)
    return actual + (objetivo - actual) * k


def escala_foco(enfocado, reducir=False):
    """Escala objetivo de una tarjeta según tenga el foco (con reducir: sin cambio de tamaño, basta el borde)."""
    return ESCALA_FOCO if enfocado and not reducir else 1.0


def temblor(t, dur=DUR_TEMBLOR, amplitud=AMPLITUD_TEMBLOR, semilla=0, reducir=False):
    """Desplazamiento horizontal de una tarjeta que «dice que no»: oscila y se apaga. 0 fuera de tiempo o con reducir."""
    if reducir or t < 0 or t >= dur:
        return 0.0
    p = _progreso(t, dur)
    fase = (semilla % 7) * 0.37
    return amplitud * (1.0 - p) * math.sin(2 * math.pi * FRECUENCIA_TEMBLOR * t + fase)


def destello(t, dur=DUR_DESTELLO, reducir=False):
    """Opacidad (0..1) de un destello sobre una tarjeta. Con reducir: un tinte tenue que se va, sin fogonazo."""
    if t < 0 or t >= dur:
        return 0.0
    p = _progreso(t, dur)
    if reducir:
        return 0.22 * (1.0 - p)
    return (1.0 - p) ** 2


def velocidades_particulas(n, semilla=0, rapidez=(0.25, 0.55)):
    """Velocidades iniciales (vx, vy) de `n` partículas en abanico hacia arriba. Deterministas por semilla."""
    azar = random.Random(semilla)
    salida = []
    for i in range(max(0, n)):
        angulo = math.radians(20 + 140 * (i + azar.random() * 0.6) / max(1, n))
        v = azar.uniform(*rapidez)
        salida.append((math.cos(angulo) * v, math.sin(angulo) * v))
    return salida


def particula(t, vx, vy, dur=DUR_PARTICULA, gravedad=GRAVEDAD_PARTICULA):
    """Posición relativa (x, y) y opacidad de una partícula a los `t` s. Opacidad 0 al acabar."""
    if t < 0:
        return 0.0, 0.0, 0.0
    x = vx * t
    y = vy * t + 0.5 * gravedad * t * t
    alfa = max(0.0, 1.0 - _progreso(t, dur))
    return x, y, alfa


def caida_sello(t, dur=DUR_SELLO, reducir=False, inicial=ESCALA_SELLO_INICIAL):
    """(escala, opacidad, golpeó) de un sello que cae desde grande (`inicial`) hasta su sitio. `golpeó` se vuelve True al
    llegar. `inicial` lo baja ajustar_sello solo cuando el sello no cabría entero en su panel durante la caída."""
    if t < 0:
        return (1.0 if reducir else inicial), 0.0, False
    p = _progreso(t, dur)
    if reducir:
        return 1.0, p, p >= 1.0
    escala = inicial + (1.0 - inicial) * (p * p)      # acelera al caer
    return escala, min(1.0, p * 2.2), p >= 1.0


GIRO_SELLO = -9.0           # grados (rotation_z del sello)
MARGEN_SELLO = 0.012        # unidades del panel que quedan libres entre el sello y su borde


def medio_sello(ancho, alto, escala, giro=GIRO_SELLO):
    """(medio ancho, medio alto) de la caja alineada que ocupa el sello girado `giro` grados a escala `escala`."""
    c, s = abs(math.cos(math.radians(giro))), abs(math.sin(math.radians(giro)))
    return (ancho * c + alto * s) / 2 * escala, (ancho * s + alto * c) / 2 * escala


def _meter(valor, medio, minimo, maximo):
    """`valor` movido lo justo para que [valor - medio, valor + medio] quede dentro de [minimo, maximo]."""
    if 2 * medio >= maximo - minimo:
        return (minimo + maximo) / 2
    return min(max(valor, minimo + medio), maximo - medio)


def ajustar_sello(posicion, ancho, alto, escala, limites, inicial=ESCALA_SELLO_INICIAL, giro=GIRO_SELLO,
                  margen=MARGEN_SELLO):
    """(final, inicio, escala_inicial) para que el sello quede ENTERO dentro de `limites` (xmin, xmax, ymin, ymax, en las
    coordenadas del padre del sello) al final y durante TODA la caída. `final` es `posicion` metida dentro del panel si
    hacía falta. La caída sigue empezando a `inicial` (2,6 veces): si a esa escala no cabe sobre `final` (un sello junto al
    borde), arranca desde `inicio`, un punto más adentro, y se desliza a su sitio mientras encoge. Solo si el panel entero
    es más pequeño que el sello a esa escala, se reduce la escala de partida. Sin límites: lo de siempre."""
    x, y = float(posicion[0]), float(posicion[1])
    if limites is None:
        return (x, y), (x, y), inicial
    xmin, xmax, ymin, ymax = (limites[0] + margen, limites[1] - margen, limites[2] + margen, limites[3] - margen)
    hx, hy = medio_sello(ancho, alto, escala, giro)
    final = (_meter(x, hx, xmin, xmax), _meter(y, hy, ymin, ymax))
    cabe = min((xmax - xmin) / (2 * hx) if hx > 0 else inicial, (ymax - ymin) / (2 * hy) if hy > 0 else inicial)
    k = max(1.0, min(float(inicial), cabe))
    inicio = (_meter(final[0], hx * k, xmin, xmax), _meter(final[1], hy * k, ymin, ymax))
    return final, inicio, k


def posicion_caida(inicio, final, escala, inicial):
    """Punto del sello cuando su escala va por `escala` (de `inicial` a 1): mismo avance que la escala."""
    f = 1.0 if inicial <= 1.0 else max(0.0, min(1.0, (inicial - escala) / (inicial - 1.0)))
    return inicio[0] + (final[0] - inicio[0]) * f, inicio[1] + (final[1] - inicio[1]) * f


def tono_racha(racha):
    """Tono (pitch) del sonido de acierto: sube con cada acierto encadenado, con tope."""
    n = max(1, min(int(racha), TONO_MAX_RACHA))
    return 1.0 + PASO_TONO * (n - 1)


def texto_racha(racha):
    """Rótulo del multiplicador visible («x3»). Vacío por debajo de 2 aciertos seguidos."""
    return f"x{int(racha)}" if racha >= 2 else ""


def estrellas(fraccion, bien, completado=True):
    """De 0 a 3 estrellas: 3 perfecto, 2 bien, 1 algo acertado, 0 nada o abandonado."""
    if not completado:
        return 0
    if fraccion >= 1.0 - 1e-9:
        return 3
    if bien:
        return 2
    if fraccion >= 0.34:
        return 1
    return 0


def puntos_estrella(radio_ext=1.0, radio_int=0.45, puntas=5):
    """Vértices (x, y) del contorno de una estrella, empezando por la punta de arriba."""
    puntos = []
    for i in range(puntas * 2):
        radio = radio_ext if i % 2 == 0 else radio_int
        angulo = math.pi / 2 + math.pi * i / puntas
        puntos.append((radio * math.cos(angulo), radio * math.sin(angulo)))
    return puntos


def triangulos_estrella(puntas=5):
    """Triángulos (en abanico desde el centro, índice 0) para una malla de estrella con el centro + contorno."""
    n = puntas * 2
    return [(0, 1 + i, 1 + (i + 1) % n) for i in range(n)]


def retardos_escalonados(n, paso=0.06, tope=0.6):
    """Retardo de entrada de cada una de `n` tarjetas (en cascada, sin pasar de `tope`)."""
    if n <= 0:
        return []
    paso_real = min(paso, tope / max(1, n - 1)) if n > 1 else 0.0
    return [i * paso_real for i in range(n)]


ESTADOS_ACIERTO = ("correcta", "encontrada")
ESTADOS_ERROR = ("incorrecta", "perdida", "falsa_alarma", "propagada")


def veredicto_de_estado(estado):
    """'acierto', 'error' o None según el estado de revisión de una tarjeta (frontend/minijuegos/ui.Tarjeta)."""
    if estado in ESTADOS_ACIERTO:
        return "acierto"
    if estado in ESTADOS_ERROR:
        return "error"
    return None


def texto_sello(es_verdadera):
    """Texto del sello final según el veredicto real del rumor (None = sin veredicto: no hay sello)."""
    if es_verdadera is None:
        return None
    return "VERIFICADO" if es_verdadera else "BULO"


def texto_sello_resultado(es_verdadera, bien):
    """Sello del final de un minijuego: el veredicto del rumor SOLO si se verificó bien. Con «Se te escapó algo» no se
    estampa nada (un «VERIFICADO» ahí contradice el resultado; retoques 2026-11-22, M3)."""
    return texto_sello(es_verdadera) if bien else None
