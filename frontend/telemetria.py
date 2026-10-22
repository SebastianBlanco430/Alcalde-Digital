# Panel de telemetría (F3): FPS (medio, mínimo, 1 % bajo, ms por frame y gráfica de los últimos frames),
# uso de CPU (total y del juego), reloj de la CPU, RAM (total y del juego), y de la GPU NVIDIA: uso,
# temperatura, potencia, reloj y VRAM. Muestra también qué GPU está dibujando el juego (driver_renderer),
# para notar si Windows lo abrió en la integrada (ver frontend/gpu_dedicada.py).
#
# Rendimiento: las lecturas del sistema (psutil y nvidia-smi, que tarda ~50 ms) van en un hilo aparte que
# duerme mientras el panel está oculto; el texto se rehace cada INTERVALO_TEXTO s, no cada frame. Con el
# panel oculto solo se anota el dt de cada frame.
#
# F3 lo muestra u oculta en cualquier escena; ALCALDE_TELEMETRIA=1 lo abre al arrancar. TELEMETRIA = False
# lo quita del todo. Sin psutil (requirements.txt) muestra solo FPS y GPU. La lógica pura está en
# frontend/telemetria_calculos.py.

import os
import sys
import threading

from ursina import Entity, Mesh, Text, application, camera, color, time, window

from frontend import estilo
from frontend.componentes import escala_fuente, rgb
from frontend.telemetria_calculos import EstadisticasFps, leer_nvidia, lineas_panel

try:
    import psutil
except ImportError:          # opcional: sin él, el panel muestra FPS y GPU
    psutil = None

TELEMETRIA = True
TECLA = "f3"
INTERVALO_TEXTO = 0.5        # s entre refrescos del texto y la gráfica
INTERVALO_SISTEMA = 1.0      # s entre lecturas de CPU/RAM/GPU (hilo aparte)
FRAMES_GRAFICA = 90
ANCHO_PANEL = 0.50           # unidades de camera.ui
ALTO_GRAFICA = 0.06
MS_TOPE_GRAFICA = 66.0       # ms que llenan el alto de la gráfica (≈15 FPS)
COLOR_BUENO = (80, 190, 110)     # ≤ 16.7 ms (60 FPS)
COLOR_MEDIO = (215, 180, 60)     # ≤ 33.3 ms (30 FPS)
COLOR_MALO = (200, 70, 70)


class MuestreoSistema:
    """Hilo que lee CPU/RAM (psutil) y GPU (nvidia-smi) cada INTERVALO_SISTEMA s mientras `activo` esté puesto."""

    def __init__(self):
        self.datos = {}
        self.activo = threading.Event()
        self._proceso = psutil.Process() if psutil else None
        self._nucleos = (psutil.cpu_count() or 1) if psutil else 1
        self._nvidia = True                  # se apaga si nvidia-smi no responde
        hilo = threading.Thread(target=self._bucle, name="telemetria", daemon=True)
        hilo.start()

    def _leer(self):
        datos = {}
        if psutil:
            memoria = psutil.virtual_memory()
            frecuencia = psutil.cpu_freq()
            datos.update(cpu=psutil.cpu_percent(interval=None), nucleos=self._nucleos,
                         cpu_juego=self._proceso.cpu_percent(interval=None) / self._nucleos,
                         cpu_mhz=frecuencia.current if frecuencia else None,
                         ram_usada=(memoria.total - memoria.available) / 2**30, ram_total=memoria.total / 2**30,
                         ram_pct=memoria.percent, ram_juego=self._proceso.memory_info().rss / 2**20)
        if self._nvidia:
            gpu = leer_nvidia()
            if gpu is None:
                self._nvidia = False
            datos["gpu"] = gpu
        return datos

    def _bucle(self):
        while True:
            self.activo.wait()
            try:
                self.datos = self._leer()
            except Exception as error:      # noqa: BLE001 — la telemetría nunca debe tumbar el juego
                self.datos = {"error": str(error)}
            threading.Event().wait(INTERVALO_SISTEMA)


class PanelTelemetria(Entity):

    def __init__(self, visible=False, **opciones):
        super().__init__(parent=camera.ui, ignore_paused=True, z=-0.9, **opciones)
        self.fps = EstadisticasFps()
        self.muestreo = MuestreoSistema()
        self._t = 0.0
        try:
            self._renderer = application.base.win.gsg.driver_renderer
        except AttributeError:
            self._renderer = "desconocido"
        self.position = (-window.aspect_ratio / 2 + 0.015, 0.32)
        self.fondo = Entity(parent=self, model="quad", origin=(-0.5, 0.5), color=color.rgba32(*estilo.TINTA, 205),
                            z=0.01)
        self.texto = Text("", parent=self, origin=(-0.5, 0.5), position=(0.012, -0.01), scale=escala_fuente(13),
                          color=rgb(estilo.COLOR_TEXTO))
        self.grafica = Entity(parent=self, z=-0.001)
        self.linea_60 = Entity(parent=self.grafica, model="quad", origin=(-0.5, 0), color=color.rgba32(255, 255, 255, 60))
        self.mostrar(visible)

    def mostrar(self, visible):
        self.visible_panel = bool(visible)
        for hijo in (self.fondo, self.texto, self.grafica):
            hijo.enabled = self.visible_panel
        if self.visible_panel:
            self.muestreo.activo.set()
            self._t = INTERVALO_TEXTO        # refresca ya
        else:
            self.muestreo.activo.clear()

    def input(self, key):
        if key == TECLA:
            self.mostrar(not self.visible_panel)

    def update(self):
        self.fps.agregar(time.dt_unscaled if hasattr(time, "dt_unscaled") else time.dt)
        if not self.visible_panel:
            return
        self._t += time.dt_unscaled if hasattr(time, "dt_unscaled") else time.dt
        if self._t < INTERVALO_TEXTO:
            return
        self._t = 0.0
        self._refrescar()

    def _refrescar(self):
        self.texto.text = "\n".join(lineas_panel(self.fps.resumen(), self.muestreo.datos, self._renderer))
        alto_texto = self.texto.height + 0.02
        self.fondo.scale = (ANCHO_PANEL, alto_texto + ALTO_GRAFICA + 0.025)
        self.grafica.position = (0.012, -alto_texto - ALTO_GRAFICA - 0.008)
        self._dibujar_grafica()

    # Barras verticales de los últimos frames: alto proporcional a los ms, color por tramo de FPS.
    def _dibujar_grafica(self):
        dts = self.fps.ultimos(FRAMES_GRAFICA)
        ancho = (ANCHO_PANEL - 0.024) / FRAMES_GRAFICA
        vertices, colores = [], []
        for i, dt in enumerate(dts):
            ms = dt * 1000
            alto = min(1.0, ms / MS_TOPE_GRAFICA) * ALTO_GRAFICA
            x0, x1 = i * ancho, (i + 0.8) * ancho
            tono = rgb(COLOR_BUENO if ms <= 16.7 else COLOR_MEDIO if ms <= 33.4 else COLOR_MALO)
            vertices += [(x0, 0, 0), (x1, 0, 0), (x1, alto, 0), (x0, 0, 0), (x1, alto, 0), (x0, alto, 0)]
            colores += [tono] * 6
        self.grafica.model = Mesh(vertices=vertices, colors=colores) if vertices else None
        self.linea_60.scale = (ANCHO_PANEL - 0.024, 0.0015)
        self.linea_60.y = 16.7 / MS_TOPE_GRAFICA * ALTO_GRAFICA


def activo():
    return TELEMETRIA and os.environ.get("ALCALDE_SIN_TELEMETRIA", "").strip() != "1"


# Lo llama main.crear_aplicacion() con la ventana abierta. Devuelve el panel (o None si está apagado).
def instalar():
    if not activo():
        return None
    try:
        return PanelTelemetria(visible=os.environ.get("ALCALDE_TELEMETRIA", "").strip() == "1")
    except Exception as error:      # noqa: BLE001 — la telemetría nunca debe impedir jugar
        print(f"[telemetria] no se pudo crear el panel ({error}).", file=sys.stderr)
        return None
