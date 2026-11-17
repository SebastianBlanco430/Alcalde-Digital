# Cálculos de los TRABAJOS visuales (frontend/trabajos_visual.py). Python puro, sin ursina, con tests en
# tests/test_trabajos_visual.py. Las reglas de los turnos (backend/logica/trabajos.py, entregas.py) no cambian:
# todo esto es solo decoración (paciencia, vuelos, cocción, humo, estela, «+R$»).

import math

SEGUNDOS_POR_UNIDAD = 4.0          # paciencia del cliente por unidad pedida (solo visual: no cambia el turno)
CRUDO = (232, 136, 146)
PERFECTO = (196, 128, 56)
QUEMADO = (58, 40, 34)
PLATOS = ("crudo", "perfecto", "quemado")


def _mezcla(a, b, k):
    k = max(0.0, min(1.0, k))
    return tuple(int(round(a[i] + (b[i] - a[i]) * k)) for i in range(3))


# -- Atender --

def paciencia(t, unidades, por_unidad=SEGUNDOS_POR_UNIDAD):
    """Fracción 1..0 de la barra de paciencia del cliente a los `t` s de esperar su pedido."""
    total = max(1.0, unidades * por_unidad)
    return max(0.0, 1.0 - t / total)


def color_paciencia(f):
    return _mezcla((230, 70, 60), (90, 200, 110), f)


def arco(t, desde, hasta, dur=0.45, alto=0.12):
    """(x, y, terminado) de un producto que vuela de la bandeja al cliente siguiendo una parábola."""
    p = 1.0 if dur <= 0 else max(0.0, min(1.0, t / dur))
    x = desde[0] + (hasta[0] - desde[0]) * p
    y = desde[1] + (hasta[1] - desde[1]) * p + alto * 4 * p * (1 - p)
    return x, y, p >= 1.0


def moneda_propina(t, i, n=3, dur=0.8):
    """(dx, dy, alfa) de la moneda `i` de la propina: saltan en abanico desde el cliente y se desvanecen."""
    p = max(0.0, min(1.0, t / dur))
    angulo = math.radians(-35 + 70 * (i / max(1, n - 1)))
    return math.sin(angulo) * 0.09 * p, 0.12 * p - 0.1 * p * p, 1.0 - p


# -- Secuencia (lan house) --

def ancho_monitor(n, lado=0.13, hueco=0.026, margen=0.08):
    return n * lado + max(0, n - 1) * hueco + margen


def pc_reparado(progreso_antes, progreso_ahora, largo, acierto):
    """True si esta acción completó la secuencia (el PC queda reparado y empieza otro)."""
    return bool(acierto) and progreso_antes == largo - 1 and progreso_ahora == 0


# -- Barra (lanchonete) --

def cercania(pos, zona):
    """1 dentro de la zona; baja a 0 a medida que la marca se aleja (0,5 de la barra = lejísimos)."""
    ini, fin = zona
    if ini <= pos <= fin:
        return 1.0
    distancia = ini - pos if pos < ini else pos - fin
    return max(0.0, 1.0 - distancia / 0.5)


def tono_coccion(pos, zona):
    """Color de la comida según dónde va la marca: cruda lejos, dorada en la zona, oscura si se pasa."""
    ini, fin = zona
    if pos > fin:
        return _mezcla(PERFECTO, QUEMADO, (pos - fin) / 0.35)
    return _mezcla(CRUDO, PERFECTO, cercania(pos, zona))


def plato_de(pos, zona, acierto):
    if acierto:
        return "perfecto"
    return "quemado" if pos > zona[1] else "crudo"


def humo(t, i, n=4, periodo=1.2):
    """(dx, dy, alfa, escala) de la bocanada `i` de humo (ciclo continuo)."""
    p = ((t / periodo) + i / n) % 1.0
    return 0.012 * math.sin(6.28 * p + i), 0.018 * p, 0.55 * (1.0 - p), 0.012 + 0.012 * p     # no sube a la línea del marcador


# -- Entregas --

def monto_entrega(pago_antes, pago_ahora):
    return max(0, int(pago_ahora) - int(pago_antes))


def flotar(t, dur=1.6, subida=0.08):
    """(dy, alfa) del «+R$» que sube y se desvanece."""
    p = max(0.0, min(1.0, t / dur))
    return subida * (1 - (1 - p) ** 2), 1.0 if p < 0.6 else max(0.0, 1.0 - (p - 0.6) / 0.4)


def deja_estela(velocidad, minimo=5.0):
    return velocidad >= minimo
