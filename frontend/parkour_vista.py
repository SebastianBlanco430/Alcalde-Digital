# Vista 3D del parkour (Ursina): dibuja un Nivel (backend/logica/parkour_calculos.py) con la estética del tema
# «corrupto»/«digital» de materiales.py y la mantiene sincronizada con la Simulacion. No contiene reglas.
#
# Rendimiento: las plataformas FIJAS se unen en UNA malla (Entity.combine) y sus aristas en UN Geom de líneas;
# solo las que cambian (móviles, que desaparecen, ligadas a interruptor) son entidades propias. Nada tiene update():
# la escena llama a `sincronizar(sim)` una vez por frame. Todo es sin luz (neón plano), así que no necesita luces.

import math

from panda3d.core import TransparencyAttrib
from ursina import Entity, color

from backend.logica.parkour_calculos import posicion_plataforma
from frontend import materiales as mat
from frontend.componentes import rgb
from frontend.piezas import lineas_sueltas, silenciar

GROSOR = 0.5                  # m de espesor de cada plataforma (la cara superior está en `y`)
ALTO_BALIZA = 9.0             # m de la columna de luz de la meta
MARGEN_REJILLA = 36.0         # m de rejilla del vacío más allá de las plataformas
PASO_REJILLA = 4.0
ALFA_FANTASMA = 0.16          # plataforma de interruptor aún sin activar: se ve, pero translúcida
PARPADEO_HZ = 7.0             # parpadeo de la plataforma que está a punto de desaparecer

_CUBO = [(-0.5, -0.5, -0.5), (0.5, -0.5, -0.5), (0.5, 0.5, -0.5), (-0.5, 0.5, -0.5),
         (-0.5, -0.5, 0.5), (0.5, -0.5, 0.5), (0.5, 0.5, 0.5), (-0.5, 0.5, 0.5)]
_ARISTAS_CUBO = [(0, 1), (1, 2), (2, 3), (3, 0), (4, 5), (5, 6), (6, 7), (7, 4), (0, 4), (1, 5), (2, 6), (3, 7)]


def _vertices_cubo(centro=(0, 0, 0), tam=(1, 1, 1)):
    v = []
    for a, b in _ARISTAS_CUBO:
        for i in (a, b):
            px, py, pz = _CUBO[i]
            v.append((centro[0] + px * tam[0], centro[1] + py * tam[1], centro[2] + pz * tam[2]))
    return v


# Lista de segmentos (pares de vértices) de la rejilla del vacío, en el plano y = `y`.
def vertices_rejilla(x0, x1, z0, z1, y, paso=PASO_REJILLA):
    v = []
    x = math.floor(x0 / paso) * paso
    while x <= x1:
        v += [(x, y, z0), (x, y, z1)]
        x += paso
    z = math.floor(z0 / paso) * paso
    while z <= z1:
        v += [(x0, y, z), (x1, y, z)]
        z += paso
    return v


def _lineas(padre, vertices, tono, grosor=2.0):
    entidad = Entity(parent=padre)
    nodo = lineas_sueltas(vertices)
    nodo.reparent_to(entidad)
    nodo.setColor(tono[0] / 255, tono[1] / 255, tono[2] / 255, 1)
    nodo.setLightOff()
    nodo.setRenderModeThickness(grosor)
    return silenciar(entidad)


class MundoParkour(Entity):

    def __init__(self, nivel, **opciones):
        super().__init__(**opciones)
        self.nivel = nivel
        self.tema = mat.tema(nivel.tema)
        self.acento = self.tema["acento"]
        self._dinamicas = {}        # id -> (entidad, color base RGB)
        self._interruptores = {}    # id -> entidad
        self._marcas_cp = {}        # id de plataforma -> entidad del rombo del checkpoint
        self._cp_activo = None
        self._construir_plataformas()
        self._construir_vacio()
        self._construir_interruptores()
        self._construir_hitos()
        self._construir_avatar()
        silenciar(self)

    # -- Construcción --

    def _color_base(self, p):
        if p.id == self.nivel.meta:
            return mat.NEON_AMARILLO
        if p.requiere:
            return mat.NEON_MAGENTA
        if p.tipo == "movil":
            return mat.mezclar(mat.CORRUPTO_PLATAFORMA, mat.NEON_AMARILLO, 0.55)
        if p.tipo == "desaparece":
            return mat.mezclar(mat.CORRUPTO_PLATAFORMA, mat.NEON_ROJO, 0.6)
        return mat.CORRUPTO_PLATAFORMA if self.nivel.tema == "corrupto" else mat.mezclar(
            mat.DIGITAL_FONDO, mat.NEON_CIAN, 0.45)

    def _construir_plataformas(self):
        estaticas, aristas = [], []
        for p in self.nivel.plataformas.values():
            tono = self._color_base(p)
            if p.tipo == "fija" and not p.requiere:
                estaticas.append(Entity(
                    parent=self, model="cube", color=rgb(tono),
                    position=(p.x, p.y - GROSOR / 2, p.z), scale=(p.ancho, GROSOR, p.fondo)))
                aristas += _vertices_cubo((p.x, p.y - GROSOR / 2, p.z), (p.ancho, GROSOR, p.fondo))
            else:
                caja = Entity(parent=self, model="cube", color=rgb(tono),
                              position=(p.x, p.y - GROSOR / 2, p.z), scale=(p.ancho, GROSOR, p.fondo))
                _lineas(caja, _vertices_cubo(), self.acento)
                self._dinamicas[p.id] = (caja, tono)
        if estaticas:
            soporte = Entity(parent=self)
            for caja in estaticas:
                caja.parent = soporte
            soporte.combine()
            self.casco = soporte
            _lineas(self, aristas, self.acento)

    def _construir_vacio(self):
        xs = [p.x for p in self.nivel.plataformas.values()]
        zs = [p.z for p in self.nivel.plataformas.values()]
        rejilla = vertices_rejilla(min(xs) - MARGEN_REJILLA, max(xs) + MARGEN_REJILLA,
                                   min(zs) - MARGEN_REJILLA, max(zs) + MARGEN_REJILLA, self.nivel.y_muerte + 1.0)
        _lineas(self, rejilla, self.tema["rejilla"], grosor=1.5)

    def _construir_interruptores(self):
        for sw in self.nivel.interruptores.values():
            base = Entity(parent=self, model="cube", color=rgb(mat.NEON_MAGENTA),
                          position=(sw.x, sw.y + 0.07, sw.z), scale=(sw.radio * 1.6, 0.14, sw.radio * 1.6))
            self._interruptores[sw.id] = base

    def _construir_hitos(self):
        for p in self.nivel.plataformas.values():
            if p.checkpoint:
                self._marcas_cp[p.id] = Entity(
                    parent=self, model="cube", color=rgb(mat.NEON_VERDE), rotation=(45, 45, 0),
                    position=(p.x - p.ancho / 2 + 0.5, p.y + 1.1, p.z - p.fondo / 2 + 0.5), scale=0.45)
        meta = self.nivel.plataformas[self.nivel.meta]
        baliza = Entity(parent=self, model="cube", position=(meta.x, meta.y + ALTO_BALIZA / 2, meta.z),
                        scale=(0.35, ALTO_BALIZA, 0.35), color=color.rgba32(*mat.NEON_AMARILLO, 150))
        baliza.setTransparency(TransparencyAttrib.M_alpha)
        self.baliza = baliza

    def _construir_avatar(self):
        self.avatar = Entity(parent=self)
        Entity(parent=self.avatar, model="cube", color=rgb(mat.AVATAR_CONTORNO), position=(0, 0.5, 0),
               scale=(0.55, 0.9, 0.4))
        Entity(parent=self.avatar, model="sphere", color=rgb(mat.AVATAR_NUCLEO), position=(0, 1.15, 0), scale=0.42)
        Entity(parent=self.avatar, model="cube", color=rgb(mat.NEON_MAGENTA), position=(0, 1.2, 0.17),
               scale=(0.3, 0.1, 0.12))                    # visor: marca el frente
        self.sombra = Entity(parent=self, model="circle", rotation_x=90, scale=0.8,
                             color=color.rgba32(0, 0, 0, 120))
        self.sombra.setTransparency(TransparencyAttrib.M_alpha)
        self._yaw_avatar = 0.0

    # -- Frame --

    def marcar_checkpoint(self, id_plataforma):
        self._cp_activo = id_plataforma
        for id_p, marca in self._marcas_cp.items():
            marca.color = rgb(mat.NEON_VERDE if id_p == id_plataforma else mat.WIREFRAME_TENUE)

    def sincronizar(self, sim, dt=0.0):
        for id_p, (caja, tono) in self._dinamicas.items():
            p = self.nivel.plataformas[id_p]
            x, y, z = posicion_plataforma(p, sim.t)
            caja.position = (x, y - GROSOR / 2, z)
            self._estado_visual(caja, p, tono, sim)
        for id_i, base in self._interruptores.items():
            base.color = rgb(mat.NEON_VERDE if sim.interruptor_activo(id_i) else mat.NEON_MAGENTA)
        self.avatar.position = (sim.x, sim.y, sim.z)
        _, alto = sim.soporte_actual()
        self.sombra.enabled = alto is not None
        if alto is not None:
            self.sombra.position = (sim.x, alto + 0.03, sim.z)
            self.sombra.scale = max(0.35, 0.8 - 0.12 * (sim.y - alto))
        self.baliza.alpha = 0.45 + 0.2 * math.sin(sim.t * 3.0)

    def orientar_avatar(self, mx, mz, dt):
        if abs(mx) + abs(mz) < 1e-3:
            return
        meta = math.degrees(math.atan2(mx, mz))
        delta = (meta - self._yaw_avatar + 180) % 360 - 180
        self._yaw_avatar += delta * min(1.0, 14.0 * dt)
        self.avatar.rotation_y = self._yaw_avatar

    def _estado_visual(self, caja, p, tono, sim):
        if p.requiere is not None and not sim.activa(p):
            caja.enabled = True
            caja.setTransparency(TransparencyAttrib.M_alpha)
            caja.color = color.rgba32(*tono, int(255 * ALFA_FANTASMA))
            return
        caja.setTransparency(TransparencyAttrib.M_none)
        fase = sim.fase(p)
        if fase == "oculta":
            caja.enabled = False
            return
        caja.enabled = True
        if fase == "aviso" and int(sim.t * PARPADEO_HZ * 2) % 2 == 0:
            caja.color = rgb((255, 255, 255))
        else:
            caja.color = rgb(tono)
