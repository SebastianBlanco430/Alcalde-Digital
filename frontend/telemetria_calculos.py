# Lógica pura de la telemetría (sin Ursina ni ventana): estadísticas de FPS, lectura de la GPU con
# nvidia-smi y textos del panel. La vista está en frontend/telemetria.py.

import collections
import shutil
import subprocess
import sys

VENTANA_FPS = 2.0            # s de frames que entran en las estadísticas del panel
CONSULTA_NVIDIA = ("name,utilization.gpu,memory.used,memory.total,temperature.gpu,power.draw,clocks.gr")


class EstadisticasFps:
    """Frame times de los últimos `ventana` segundos: FPS medio, mínimo, 1 % bajo y ms por frame."""

    def __init__(self, ventana=VENTANA_FPS):
        self.ventana = ventana
        self._dts = collections.deque()
        self._suma = 0.0

    def agregar(self, dt):
        if not 0 < dt <= 0.5:         # cargas de escena y pausas: no son rendimiento (como medidor_fps)
            return
        self._dts.append(dt)
        self._suma += dt
        while self._suma > self.ventana and len(self._dts) > 1:
            self._suma -= self._dts.popleft()

    def ultimos(self, cantidad):
        return list(self._dts)[-cantidad:]

    # (fps medio, fps mínimo, fps 1 % bajo, ms medio por frame); ceros sin datos.
    def resumen(self):
        if not self._dts:
            return 0.0, 0.0, 0.0, 0.0
        n = len(self._dts)
        lentos = sorted(self._dts, reverse=True)[:max(1, n // 100)]
        return n / self._suma, 1 / max(self._dts), len(lentos) / sum(lentos), 1000 * self._suma / n


# Lectura de la GPU NVIDIA: dict con nombre, uso, vram_usada, vram_total, temperatura, potencia y reloj
# (None si no hay nvidia-smi o falla). Una consulta tarda ~50 ms: se llama desde un hilo aparte.
def leer_nvidia(ejecutable=None):
    ejecutable = ejecutable or shutil.which("nvidia-smi")
    if not ejecutable:
        return None
    opciones = {"creationflags": subprocess.CREATE_NO_WINDOW} if sys.platform == "win32" else {}
    try:
        salida = subprocess.run([ejecutable, f"--query-gpu={CONSULTA_NVIDIA}", "--format=csv,noheader,nounits"],
                                capture_output=True, text=True, timeout=2, **opciones).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    return interpretar_nvidia(salida)


def _numero(texto):
    try:
        return float(texto)
    except (TypeError, ValueError):
        return None


# Primera línea de la salida CSV de nvidia-smi -> dict (campos ilegibles = None). None si está vacía.
def interpretar_nvidia(salida):
    lineas = [l for l in (salida or "").strip().splitlines() if l.strip()]
    if not lineas:
        return None
    campos = [c.strip() for c in lineas[0].split(",")]
    if len(campos) < 7:
        return None
    return {"nombre": campos[0], "uso": _numero(campos[1]), "vram_usada": _numero(campos[2]),
            "vram_total": _numero(campos[3]), "temperatura": _numero(campos[4]),
            "potencia": _numero(campos[5]), "reloj": _numero(campos[6])}


def _fmt(valor, formato, sufijo=""):
    return "n/d" if valor is None else f"{valor:{formato}}{sufijo}"


# Líneas del panel. `fps` = EstadisticasFps.resumen(); `sistema` = dict del muestreo (ver telemetria.py).
def lineas_panel(fps, sistema, renderer):
    media, minimo, bajo, ms = fps
    s = sistema or {}
    lineas = [f"FPS {media:5.1f}   {ms:5.1f} ms/frame",
              f"mín {minimo:5.1f}   1% bajo {bajo:5.1f}"]
    if s.get("cpu") is not None:
        lineas.append(f"CPU {s['cpu']:5.1f} %   juego {_fmt(s.get('cpu_juego'), '5.1f', ' %')}"
                      f"   {s.get('nucleos', '?')} hilos")
        if s.get("cpu_mhz"):
            lineas.append(f"CPU reloj {s['cpu_mhz']:.0f} MHz")
        lineas.append(f"RAM {_fmt(s.get('ram_usada'), '.1f')}/{_fmt(s.get('ram_total'), '.1f')} GB"
                      f" ({_fmt(s.get('ram_pct'), '.0f', ' %')})   juego {_fmt(s.get('ram_juego'), '.0f', ' MB')}")
    else:
        lineas.append("CPU/RAM: instala psutil (pip install -r requirements.txt)")
    gpu = s.get("gpu")
    if gpu:
        lineas.append(f"GPU {_fmt(gpu.get('uso'), '.0f', ' %')}   {_fmt(gpu.get('temperatura'), '.0f', ' °C')}"
                      f"   {_fmt(gpu.get('potencia'), '.1f', ' W')}   {_fmt(gpu.get('reloj'), '.0f', ' MHz')}")
        lineas.append(f"VRAM {_fmt(gpu.get('vram_usada'), '.0f')}/{_fmt(gpu.get('vram_total'), '.0f')} MB")
    else:
        lineas.append("GPU uso: n/d (solo NVIDIA, con nvidia-smi)")
    lineas.append(f"Render: {renderer}")
    return lineas
