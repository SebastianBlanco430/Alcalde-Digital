# Matemática compartida de las vistas visuales de «Rastrear», «Comparar», «Señales» y «Cronología»
# (frontend/minijuegos_visual/*_visual.py). Python puro, sin ursina, con tests en tests/test_pistas_visuales.py.
#
#   - hilo rojo del tablero de corcho: curva que cuelga entre dos chinchetas y que se tensa; rodeo enredado al fallar;
#   - círculo rojo de rotulador que se dibuja con trazo (Señales) y barra de fosforito (Comparar);
#   - diferencia entre original y copia (la palabra alterada que «salta» al confirmar en Comparar);
#   - reloj gigante (ángulo de las agujas según la hora de la tarjeta) y balanceo de las tarjetas colgadas (Cronología);
#   - el rumor que crece con cada reenvío (mayúsculas, signos y añadidos).

import math
import re

# -- Hilo rojo (Rastrear) --

def catenaria(a, b, caida, n=16):
    """Puntos (x, y) de un hilo que cuelga de `a` a `b` con una caída máxima `caida` en el centro (parábola)."""
    (ax, ay), (bx, by) = a, b
    puntos = []
    for i in range(n + 1):
        t = i / n
        x = ax + (bx - ax) * t
        y = ay + (by - ay) * t - caida * 4 * t * (1 - t)
        puntos.append((x, y))
    return puntos


def caida_hilo(t, dur=0.45, floja=0.06, tensa=0.008, reducir=False):
    """Caída del hilo `t` s después de clavarlo: empieza flojo y se tensa (con un pequeño rebote)."""
    if reducir or t >= dur:
        return tensa
    if t <= 0:
        return floja
    p = t / dur
    return tensa + (floja - tensa) * (1 - p) * math.cos(p * math.pi * 1.5) ** 2


def enredo(a, b, vueltas=3, radio=0.018, n=40):
    """Puntos de un rodeo enredado entre `a` y `b` (bucles a lo largo del camino): un error en el rastro."""
    (ax, ay), (bx, by) = a, b
    puntos = []
    for i in range(n + 1):
        t = i / n
        x = ax + (bx - ax) * t
        y = ay + (by - ay) * t
        ang = t * vueltas * 2 * math.pi
        envolvente = math.sin(math.pi * t)
        puntos.append((x + radio * envolvente * math.sin(ang), y + radio * envolvente * (1 - math.cos(ang))))
    return puntos


def posiciones_rastro(n, x_derecha, paso, x_min):
    """x de cada nota del rastro: «Tú» a la derecha y cada fuente más antigua a su izquierda. Si no caben, se aprietan."""
    if n <= 0:
        return []
    paso_real = min(paso, (x_derecha - x_min) / max(1, n - 1)) if n > 1 else paso
    return [x_derecha - i * paso_real for i in range(n)]


def parcial(puntos, progreso):
    """Los puntos de una polilínea hasta `progreso` (0..1) de su recorrido (para «dibujar» un trazo)."""
    if not puntos:
        return []
    progreso = max(0.0, min(1.0, progreso))
    k = progreso * (len(puntos) - 1)
    entero = int(k)
    salida = list(puntos[:entero + 1])
    f = k - entero
    if entero < len(puntos) - 1 and f > 1e-9:
        (ax, ay), (bx, by) = puntos[entero], puntos[entero + 1]
        salida.append((ax + (bx - ax) * f, ay + (by - ay) * f))
    return salida


# -- Rotulador (Señales) y fosforito (Comparar) --

def circulo_rotulador(rx, ry, n=48, semilla=0, vuelta_extra=0.12):
    """Óvalo dibujado a mano: un poco irregular y que se pasa de la vuelta (como un círculo de rotulador)."""
    puntos = []
    total = 1.0 + vuelta_extra
    fase = (semilla % 17) * 0.3
    for i in range(n + 1):
        t = total * i / n
        ang = math.pi * 0.6 + 2 * math.pi * t
        temblor = 1.0 + 0.045 * math.sin(3 * ang + fase) + 0.03 * math.sin(7 * ang + fase * 2)
        crece = 1.0 + 0.06 * t
        puntos.append((rx * temblor * crece * math.cos(ang), ry * temblor * math.sin(ang)))
    return puntos


def avance_trazo(t, dur=0.35, reducir=False):
    """0..1: cuánto del trazo está dibujado."""
    if reducir:
        return 1.0
    return max(0.0, min(1.0, t / dur))


# -- Diferencia entre original y copia (Comparar) --

_PALABRA = re.compile(r"\S+")


def diferencia(original, copia):
    """(fragmento original, fragmento copia) del primer tramo de palabras que cambia. None si son iguales."""
    a, b = _PALABRA.findall(str(original or "")), _PALABRA.findall(str(copia or ""))
    if a == b:
        return None
    i = 0
    while i < min(len(a), len(b)) and a[i] == b[i]:
        i += 1
    j = 0
    while j < min(len(a), len(b)) - i and a[-1 - j] == b[-1 - j]:
        j += 1
    tramo_a = " ".join(a[i:len(a) - j]) or "(nada)"
    tramo_b = " ".join(b[i:len(b) - j]) or "(nada)"
    return tramo_a, tramo_b


def recortar(texto, largo=28):
    texto = str(texto)
    return texto if len(texto) <= largo else texto[:largo - 1].rstrip() + "…"


def texto_salto(original, copia):
    """Rótulo grande del momento estrella: «R$ 5 → R$ 50». None si no hay diferencia."""
    d = diferencia(original, copia)
    if d is None:
        return None
    return f"«{recortar(d[0])}»  pasó a  «{recortar(d[1])}»"


# -- Reloj gigante y tarjetas colgadas (Cronología) --

_HORA = re.compile(r"(\d{1,2})[:h](\d{2})")


def angulos_reloj(hora):
    """(ángulo de la aguja horaria, ángulo del minutero) en grados, en sentido horario desde las 12. None si no hay hora."""
    m = _HORA.search(str(hora or ""))
    if not m:
        return None
    h, mi = int(m.group(1)) % 24, int(m.group(2)) % 60
    return ((h % 12) * 30 + mi * 0.5, mi * 6.0)


def acercar_angulo(actual, objetivo, dt, tiempo=0.25):
    """Gira de `actual` a `objetivo` por el camino corto (grados), suave e independiente de los fps."""
    diferencia_ = ((objetivo - actual + 180) % 360) - 180
    if dt <= 0:
        return actual
    k = 1 - math.exp(-dt / max(1e-3, tiempo))
    return actual + diferencia_ * k


def balanceo(t, amplitud=3.0, frecuencia=1.6, amortiguacion=2.2, reducir=False):
    """Giro (grados) de una tarjeta colgada que se suelta: oscila y se apaga."""
    if reducir or t < 0:
        return 0.0
    return amplitud * math.exp(-amortiguacion * t) * math.sin(2 * math.pi * frecuencia * t)


# -- El rumor que crece con cada reenvío (Cronología) --

AGREGADOS = ("", " ¡Pásalo!", " ¡¡URGENTE!!", " ¡¡COMPARTE YA!!", " ¡¡¡TODOS DEBEN SABERLO!!!")


def exagerar(texto, nivel):
    """El mensaje tal como llega tras `nivel` reenvíos: más signos, más mayúsculas, más añadidos."""
    texto = str(texto or "").strip()
    nivel = max(0, int(nivel))
    if nivel == 0:
        return texto
    palabras = texto.split()
    cuantas = min(len(palabras), nivel * 2)
    palabras = [p.upper() if i < cuantas else p for i, p in enumerate(palabras)]
    resultado = " ".join(palabras).rstrip(".")
    resultado += "!" * min(3, nivel)
    return resultado + AGREGADOS[min(nivel, len(AGREGADOS) - 1)]


def escala_burbuja(nivel, maximo=4):
    """La burbuja engorda con cada reenvío (1.0 .. 1.45)."""
    return 1.0 + 0.45 * min(nivel, maximo) / maximo


def paso_reproduccion(t, n, dur_paso=0.9):
    """Qué mensaje (0..n-1) se ve a los `t` s de la reproducción, o None si ya terminó."""
    if t < 0:
        return 0
    k = int(t / dur_paso)
    return k if k < n else None
