# Vista de las piezas de la sesión E sobre MundoParkour (Ursina): flechas que corren sobre las cintas, color por altura y
# destello por pulso de las barras de ritmo (con un tic sonoro por pulso), contorno tenue de los clips ocultos y la pared
# de la purga. La matemática está en parkour_visual_calculos.py; aquí solo se colocan mallas. Sin update(): MundoParkour
# llama a `sincronizar(sim, dt)` una vez por frame. Un nivel sin piezas nuevas no crea nada.

import math
import sys

from panda3d.core import TransparencyAttrib
from ursina import Entity, color

from backend.logica.parkour_calculos import desplazamiento_ritmo, pulso_actual
from frontend.parkour_decoracion import nodo_malla
from frontend import parkour_visual_calculos as pvc

PASO_CHEVRON = 1.1
MARGEN_PARED = 5.0            # m que la pared de la purga sobresale por encima de la plataforma más alta
ALFA_PARED = 0.18             # tenue: con la cámara ya al otro lado de la pared todo se tiñe, sin tapar el nivel
ALFA_CONTORNO = 0.35          # clip oculto: contorno tenue para saber dónde va a volver


def _contorno(ancho, fondo, grosor=0.5):
    hx, hz = ancho / 2, fondo / 2
    esquinas = [(-hx, 0, -hz), (hx, 0, -hz), (hx, 0, hz), (-hx, 0, hz)]
    abajo = [(x, -grosor, z) for x, _, z in esquinas]
    v = []
    for i in range(4):
        v += [esquinas[i], esquinas[(i + 1) % 4], abajo[i], abajo[(i + 1) % 4], esquinas[i], abajo[i]]
    return v


def _lineas(padre, vertices, tono, grosor=2.5, alfa=1.0):
    entidad = Entity(parent=padre)
    nodo = nodo_malla(vertices, [tuple(tono)] * len(vertices), primitiva="lineas", nombre="lineas_tipos")
    nodo.reparent_to(entidad)
    nodo.setRenderModeThickness(grosor)
    nodo.setLightOff()
    if alfa < 1.0:
        entidad.setTransparency(TransparencyAttrib.M_alpha)
        entidad.setColorScale(1, 1, 1, alfa)
    return entidad


class PiezasNuevas(Entity):

    def __init__(self, nivel, dinamicas, **opciones):
        super().__init__(**opciones)
        self.nivel = nivel
        self._dinamicas = dinamicas            # id -> (entidad, _) de MundoParkour
        self._cintas = []                      # (plataforma, entidad de flechas, (ux, uz))
        self._ritmos = []                      # plataformas de ritmo
        self._contornos = {}                   # id de clip -> entidad del contorno
        self._pulso_previo = None
        self._sin_audio = False
        self._pared = None
        for p in nivel.plataformas.values():
            if p.tipo == "cinta" and p.arrastre:
                self._crear_cinta(p)
            elif p.tipo == "ritmo" and p.ritmo:
                self._ritmos.append(p)
            elif p.tipo == "clip":
                c = _lineas(self, _contorno(p.ancho, p.fondo), pvc.ESTILOS["clip"]["borde"], 2.0, ALFA_CONTORNO)
                c.position = (p.x, p.y, p.z)
                c.enabled = False
                self._contornos[p.id] = c
        if nivel.purga:
            self._crear_pared()

    def _crear_cinta(self, p):
        vx, vz = p.arrastre
        modulo = math.hypot(vx, vz)
        ux, uz = vx / modulo, vz / modulo
        # Flechas para un largo reducido en PASO_CHEVRON: al desplazarlas ±paso/2 nunca salen de la plataforma.
        segmentos = pvc.chevrones_cinta(p.ancho - abs(ux) * PASO_CHEVRON, p.fondo - abs(uz) * PASO_CHEVRON, p.arrastre,
                                        0.0, PASO_CHEVRON)
        if not segmentos:
            return
        v = [(a[0], 0.0, a[1]) for s in segmentos for a in s]
        flechas = _lineas(self, v, (235, 255, 245), 3.0)
        flechas.position = (p.x, p.y + 0.03, p.z)
        self._cintas.append((p, flechas, (ux, uz)))

    def _crear_pared(self):
        xs = [q.x for q in self.nivel.plataformas.values()]
        ancho = max(xs) - min(xs) + 30.0
        y0 = self.nivel.y_muerte
        alto = max(q.y for q in self.nivel.plataformas.values()) + MARGEN_PARED - y0
        self._pared = Entity(parent=self, model="cube", scale=(ancho, alto, 0.12),
                             position=((max(xs) + min(xs)) / 2, y0 + alto / 2, 0),
                             color=color.rgba32(*pvc.COLOR_PURGA, int(255 * ALFA_PARED)))
        self._pared.setTransparency(TransparencyAttrib.M_alpha)
        self._pared.setLightOff()
        self._pared.setTwoSided(True)
        self._filo = Entity(parent=self._pared, model="cube", scale=(1.0, 0.02, 1.4), position=(0, 0, 0),
                            color=color.rgb32(255, 200, 210))
        self._filo.setLightOff()
        self._pared.enabled = False

    # -- Frame --

    def sincronizar(self, sim, dt=0.0):
        for p, flechas, (ux, uz) in self._cintas:
            d = pvc.fase_cinta(sim.t, p.arrastre, PASO_CHEVRON) - PASO_CHEVRON / 2
            flechas.position = (p.x + ux * d, p.y + 0.03, p.z + uz * d)
            flechas.enabled = sim.activa(p)
        for p in self._ritmos:
            entidad = self._dinamicas.get(p.id, (None,))[0]
            if entidad is None or not entidad.enabled:
                continue
            _, f = pulso_actual(p, sim.t)
            k = pvc.altura_relativa_ritmo(desplazamiento_ritmo(p, sim.t), p.ritmo["patron"])
            r, g, b = pvc.color_ritmo(k)
            brillo = 1.0 + 1.4 * pvc.destello_pulso(f, p.ritmo["pulso_s"])
            entidad.setColorScale(r / 255 * 1.6 * brillo, g / 255 * 1.6 * brillo, b / 255 * 1.6 * brillo, 1)
        self._tic(sim)
        for id_p, contorno in self._contornos.items():
            contorno.enabled = sim.fase(self.nivel.plataformas[id_p]) == "oculta"
        if self._pared is not None:
            frente = sim.purga_frente()
            self._pared.enabled = frente is not None
            if frente is not None:
                self._pared.z = frente
                self._pared.setColorScale(1, 1, 1, 0.75 + 0.25 * math.sin(sim.t * 14.0))

    # Tic sonoro en cada cambio de pulso (el compás lo marca la primera barra del nivel). Sin audio: solo el destello.
    def _tic(self, sim):
        if not self._ritmos or sim.terminado:
            return
        indice = math.floor(sim.t / self._ritmos[0].ritmo["pulso_s"] + self._ritmos[0].ritmo.get("fase", 0.0))
        if self._pulso_previo is not None and indice != self._pulso_previo and not self._sin_audio:
            try:
                from frontend import audio
                gestor = audio.obtener()
                if gestor is not None and gestor.activo:
                    gestor.efecto("clic_ui", 0.45, 1.5 if indice % 2 == 0 else 1.2)
            except Exception as error:          # el audio nunca tumba el parkour
                print(f"[parkour] tic del ritmo sin audio ({error})", file=sys.stderr)
                self._sin_audio = True
        self._pulso_previo = indice
