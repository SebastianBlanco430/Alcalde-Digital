# Cálculos de las misiones visuales del parkour (frontend/parkour_extra.py, parkour_glitch.py y parkour_fantasma.py).
# Python puro, sin ursina, con tests en tests/test_parkour_extra.py. No toca las reglas (backend/logica/parkour_calculos.py).
#
#   - cámara lenta breve en los saltos largos (el doble salto): factor de tiempo que baja y vuelve, con enfriamiento;
#   - corredor fantasma: grabar la mejor carrera (posición y rumbo cada N pasos), interpolarla y decidir si se guarda;
#   - glitch de las plataformas que se rompen (desfase de color, cortes horizontales, fragmentos que caen);
#   - medallas: cuál se acaba de perder con el tiempo y cuál se ganó al llegar; el orbe de evidencia.

import bisect
import json
import math
import os
import random
from pathlib import Path

# -- Cámara lenta --

DUR_LENTA = 0.55             # s REALES que dura
FACTOR_MINIMO = 0.4          # lo más lento (40 % de la velocidad)
ENFRIAMIENTO = 2.5           # s reales entre dos cámaras lentas


def factor_tiempo(t, dur=DUR_LENTA, minimo=FACTOR_MINIMO, reducir=False):
    """Multiplicador del tiempo de la simulación `t` s después de empezar la cámara lenta (1 = normal)."""
    if reducir or t is None or t < 0 or t >= dur:
        return 1.0
    p = t / dur
    entrada, salida = 0.15, 0.45                     # baja rápido, aguanta y vuelve suave
    if p < entrada:
        k = p / entrada
    elif p > 1 - salida:
        k = (1 - p) / salida
    else:
        k = 1.0
    k = k * k * (3 - 2 * k)
    return 1.0 - (1.0 - minimo) * k


def dispara_lenta(eventos):
    """¿Algún evento de la simulación pide cámara lenta? El doble salto es el salto largo del parkour."""
    return "doble_salto" in eventos


# -- Corredor fantasma --

CADA_N_FRAMES = 4
MAX_MUESTRAS = 4000
VERSION_FANTASMA = 1


class Grabador:
    """Graba (t, x, y, z, rumbo) cada `cada` frames. `t` es el tiempo de la simulación."""

    def __init__(self, cada=CADA_N_FRAMES):
        self.cada = max(1, int(cada))
        self.muestras = []
        self._frame = 0

    def anotar(self, t, x, y, z, rumbo):
        if self.muestras and t < self.muestras[-1][0]:      # otra carrera (reinicio): se empieza de cero
            self.muestras, self._frame = [], 0
        if self._frame % self.cada == 0 and len(self.muestras) < MAX_MUESTRAS:
            self.muestras.append((round(t, 3), round(x, 3), round(y, 3), round(z, 3), round(rumbo, 1)))
        self._frame += 1

    def reiniciar(self):
        self.muestras, self._frame = [], 0


def interpolar(muestras, t):
    """(x, y, z, rumbo) del fantasma en `t` (interpolación lineal; el rumbo por el camino corto). None si no hay datos
    o la carrera grabada ya terminó."""
    if not muestras or t > muestras[-1][0]:
        return None
    tiempos = [m[0] for m in muestras]
    i = bisect.bisect_right(tiempos, t)
    if i <= 0:
        return tuple(muestras[0][1:])
    a, b = muestras[i - 1], muestras[min(i, len(muestras) - 1)]
    if b[0] <= a[0]:
        return tuple(a[1:])
    k = (t - a[0]) / (b[0] - a[0])
    giro = ((b[4] - a[4] + 180) % 360) - 180
    return (a[1] + (b[1] - a[1]) * k, a[2] + (b[2] - a[2]) * k, a[3] + (b[3] - a[3]) * k, a[4] + giro * k)


def velocidad_en(muestras, t):
    """m/s horizontales del fantasma en `t` (para su animación de carrera)."""
    p, q = interpolar(muestras, t), interpolar(muestras, t + 0.1)
    if p is None or q is None:
        return 0.0
    return math.hypot(q[0] - p[0], q[2] - p[2]) / 0.1


def es_mejor(tiempo_nuevo, guardado):
    """¿La carrera nueva (terminada en `tiempo_nuevo` s) mejora la guardada (dict o None)?"""
    if tiempo_nuevo is None or tiempo_nuevo <= 0:
        return False
    previo = (guardado or {}).get("tiempo_s")
    return previo is None or tiempo_nuevo < previo


def carpeta_fantasmas():
    elegido = os.environ.get("ALCALDE_AJUSTES_DIR")
    base = Path(elegido) if elegido else Path.home() / ".alcalde_digital"
    return base / "parkour_fantasmas"


def ruta_fantasma(nivel_id, carpeta=None):
    seguro = "".join(c for c in str(nivel_id) if c.isalnum() or c == "_") or "nivel"
    return Path(carpeta) / f"{seguro}.json" if carpeta is not None else carpeta_fantasmas() / f"{seguro}.json"


def cargar_fantasma(nivel_id, carpeta=None):
    """Mejor carrera guardada del nivel ({"tiempo_s", "muestras"}) o None (sin archivo o roto: sin fantasma).
    EST-002: un archivo roto (raíz que no es un objeto, números enormes o no finitos, JSON anidado sin fin) ya no
    tumba el controlador de los extras del nivel; se aparta como «<nivel>.json.dañado» y se juega sin fantasma."""
    ruta = ruta_fantasma(nivel_id, carpeta)
    try:
        with open(ruta, encoding="utf-8") as archivo:
            datos = json.load(archivo)
    except OSError:
        return None
    except (ValueError, RecursionError) as error:
        _apartar(ruta, type(error).__name__)
        return None
    try:
        if not isinstance(datos, dict) or not isinstance(datos.get("muestras", []), list):
            raise TypeError("formato desconocido")
        muestras = [tuple(float(v) for v in m) for m in datos.get("muestras", []) if isinstance(m, list) and len(m) == 5]
        muestras = [m for m in muestras if all(math.isfinite(v) for v in m)]
        tiempo = float(datos["tiempo_s"])
        if not muestras or not math.isfinite(tiempo):
            return None
        return {"tiempo_s": tiempo, "muestras": muestras}
    except (ValueError, KeyError, TypeError, AttributeError, OverflowError) as error:
        _apartar(ruta, type(error).__name__)
        return None


def _apartar(ruta, motivo):
    try:
        from backend.logica import ajustes
        ajustes.apartar_danado(ruta, motivo)
    except Exception:                    # noqa: BLE001
        pass


def guardar_fantasma(nivel_id, tiempo_s, muestras, carpeta=None):
    """Guarda la carrera (escritura atómica). True si se guardó."""
    ruta = ruta_fantasma(nivel_id, carpeta)
    try:
        ruta.parent.mkdir(parents=True, exist_ok=True)
        temporal = ruta.with_suffix(".tmp")
        with open(temporal, "w", encoding="utf-8") as archivo:
            json.dump({"version": VERSION_FANTASMA, "tiempo_s": float(tiempo_s), "muestras": [list(m) for m in muestras]},
                      archivo)
        os.replace(temporal, ruta)
        return True
    except OSError:
        return False


# -- Glitch de las plataformas que se rompen --

def desfase_color(t, semilla=0, amplitud=0.09, reducir=False):
    """(dx rojo, dx azul) en m: las dos copias de color tiemblan a los lados de la plataforma."""
    if reducir:
        return amplitud * 0.5, -amplitud * 0.5
    a = amplitud * (0.6 + 0.4 * math.sin(t * 37 + semilla))
    return a * math.sin(t * 23 + semilla * 1.7), -a * math.cos(t * 29 + semilla)


def cortes(t, semilla=0, n=3, reducir=False):
    """[(y relativa -0.5..0.5, desplazamiento x)] de las franjas horizontales que «cortan» la plataforma. Cambian ~12
    veces por segundo; con reducir quedan quietas."""
    paso = 0 if reducir else int(t * 12)
    azar = random.Random(semilla * 7919 + paso)
    return [(azar.uniform(-0.45, 0.45), 0.0 if reducir else azar.uniform(-0.12, 0.12)) for _ in range(n)]


def fragmentos(n, semilla=0):
    """[(dx, dz, vx, vy, vz, giro)] de los trozos que caen al romperse una plataforma (posición relativa en -0.5..0.5)."""
    azar = random.Random(semilla)
    salida = []
    for _ in range(n):
        salida.append((azar.uniform(-0.5, 0.5), azar.uniform(-0.5, 0.5), azar.uniform(-1.2, 1.2), azar.uniform(0.5, 2.2),
                       azar.uniform(-1.2, 1.2), azar.uniform(-360, 360)))
    return salida


def posicion_fragmento(t, vx, vy, vz, gravedad=-14.0):
    return vx * t, vy * t + 0.5 * gravedad * t * t, vz * t


# -- Medallas y orbe --

ORDEN = ("bronce", "plata", "oro")


def perdidas(antes, ahora):
    """Medallas que se acaban de perder al pasar la medalla alcanzable de `antes` a `ahora` (None = ninguna)."""
    rango = lambda m: ORDEN.index(m) + 1 if m in ORDEN else 0
    return [m for m in ORDEN if rango(ahora) < ORDEN.index(m) + 1 <= rango(antes)]


def posicion_orbe(t, base, altura=1.6, flotar=0.18):
    """(x, y, z) del orbe de evidencia que flota sobre la meta."""
    x, y, z = base
    return x, y + altura + flotar * math.sin(t * 2.2), z


def estela_orbe(t, base, n=12, radio=0.55, altura=1.6):
    """Puntos de la estela de partículas que giran alrededor del orbe (la más nueva primero)."""
    x, y, z = base
    salida = []
    for i in range(n):
        ang = t * 3.0 - i * 0.35
        salida.append((x + radio * math.cos(ang), y + altura + 0.25 * math.sin(ang * 1.5), z + radio * math.sin(ang)))
    return salida
