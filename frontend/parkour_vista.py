# Vista 3D del parkour (Ursina): dibuja un Nivel (backend/logica/parkour_calculos.py) con la estética del tema
# «corrupto»/«digital» de materiales.py y la mantiene sincronizada con la Simulacion. No contiene reglas.
#
# Rendimiento: las plataformas FIJAS se unen en UNA malla (Entity.combine) y sus aristas en UN Geom de líneas;
# solo las que cambian (móviles, que desaparecen, ligadas a interruptor) son entidades propias. Nada tiene update():
# la escena llama a `sincronizar(sim)` una vez por frame. Todo es sin luz (neón plano), así que no necesita luces.

import math
import sys

from panda3d.core import TransparencyAttrib
from ursina import Entity, color

from backend.logica.parkour_calculos import VELOCIDAD, posicion_plataforma
from frontend import materiales as mat
from frontend.componentes import rgb
from frontend.parkour_decoracion import DecoracionParkour, nodo_malla
from frontend.parkour_efectos import EfectosParkour
from frontend.piezas import lineas_sueltas, silenciar
from frontend import parkour_skin_calculos as psc
from frontend import parkour_visual_calculos as pvc

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

    def __init__(self, nivel, jugador=None, **opciones):
        super().__init__(**opciones)
        self.nivel = nivel
        self.clave_skin = self.clave_pedida = psc.datos_de_skin(jugador) if psc.skin_activa() else None
        # clave_pedida la lee la escena para saber si hay que rehacer la skin (clave_skin pasa a None si la carga falla)
        self._skin = None           # personaje con skin .glb (None = muñeco de cubos)
        self._pos_previa = None     # (x, z) del frame anterior, para la velocidad real
        self.tema = mat.tema(nivel.tema)
        self.visual = pvc.visual_activo()          # ALCALDE_PARKOUR_VISUAL=0: aspecto anterior (cubos lisos + rejilla)
        self.decoracion = self.efectos = None
        self.acento = self.tema["acento"]
        self._dinamicas = {}        # id -> (entidad, color base RGB)
        self._interruptores = {}    # id -> entidad
        self._marcas_cp = {}        # id de plataforma -> entidad del rombo del checkpoint
        self._cp_activo = None
        self._construir_plataformas()
        self._construir_vacio()
        self._construir_interruptores()
        self._construir_hitos()
        self._construir_avatar_elegido()
        if self.visual:
            self._construir_visual()
        silenciar(self)
        if self._skin is not None:
            self._skin.ignore = False       # silenciar(self) lo apagó: el modelo necesita su update() (clips, rostro)

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
        if self.visual:
            return self._construir_plataformas_neon()
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
        if self.visual:
            return                                  # el vacío lo dibuja DecoracionParkour (_construir_visual)
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
        baliza.enabled = not self.visual            # con el aspecto nuevo la meta la marca EfectosParkour
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

    # Avatar con la skin .glb del jugador (misma fábrica que el mundo); con el interruptor apagado o si la carga
    # falla, el muñeco de cubos de siempre. La sombra circular de arriba se conserva (la del modelo se apaga).
    def _construir_avatar_elegido(self):
        if self.clave_skin is None:
            return self._construir_avatar()
        try:
            from backend.logica.roles import ROLES
            from frontend.personaje_modelo import crear_personaje
            nombre, rol = self.clave_skin
            personaje = crear_personaje(nombre, rol, ROLES[rol].color, parent=self)
        except Exception as error:
            print(f"[parkour] skin del jugador no disponible ({error}). Se usa el muñeco de cubos.", file=sys.stderr)
            self.clave_skin = None
            return self._construir_avatar()
        for parte in ("aro", "etiqueta"):                 # sin aro ni nombre flotante en el parkour
            if getattr(personaje, parte, None) is not None:
                getattr(personaje, parte).enabled = False
        if getattr(personaje, "sombra", None) is not None:
            personaje.sombra.enabled = False
        personaje.automatico = True
        self.avatar = self._skin = personaje
        self.sombra = Entity(parent=self, model="circle", rotation_x=90, scale=0.8,
                             color=color.rgba32(0, 0, 0, 120))
        self.sombra.setTransparency(TransparencyAttrib.M_alpha)
        self._yaw_avatar = 0.0

    # Pasa al modelo la velocidad real y el estado en el aire (elige Idle/Caminar/Correr/salto). Se llama tras mover el avatar.
    def _animar_skin(self, sim, dt):
        previa, self._pos_previa = self._pos_previa, (sim.x, sim.z)
        v = sim.vertical
        self._skin.fijar_estado_aire(v.en_aire, v.vy)
        if previa is None or dt <= 0:
            self._skin.fijar_velocidad(0.0)
            return
        arrastre = (0.0, 0.0)
        movil = self.nivel.plataformas.get(sim.sobre) if sim.sobre else None
        if movil is not None and movil.tipo == "movil" and not v.en_aire:
            ax, _, az = posicion_plataforma(movil, sim.t - dt)
            bx, _, bz = posicion_plataforma(movil, sim.t)
            arrastre = (bx - ax, bz - az)
        vel = psc.velocidad_horizontal(previa[0], previa[1], sim.x, sim.z, dt, arrastre)
        self._skin.fijar_velocidad(0.0 if vel > 3 * VELOCIDAD else vel)      # un salto de reaparición no es marcha

    # -- Frame --

    def marcar_checkpoint(self, id_plataforma):
        self._cp_activo = id_plataforma
        if self.efectos is not None:
            self.efectos.marcar_checkpoint(id_plataforma)
        for id_p, marca in self._marcas_cp.items():
            marca.color = rgb(mat.NEON_VERDE if id_p == id_plataforma else mat.WIREFRAME_TENUE)

    def sincronizar(self, sim, dt=0.0):
        for id_p, (caja, tono) in self._dinamicas.items():
            p = self.nivel.plataformas[id_p]
            x, y, z = posicion_plataforma(p, sim.t)
            caja.position = (x, y, z) if self.visual else (x, y - GROSOR / 2, z)
            self._estado_visual(caja, p, tono, sim)
        for id_i, base in self._interruptores.items():
            base.color = rgb(mat.NEON_VERDE if sim.interruptor_activo(id_i) else mat.NEON_MAGENTA)
        self.avatar.position = (sim.x, sim.y, sim.z)
        if self._skin is not None:
            self._animar_skin(sim, dt)
        _, alto = sim.soporte_actual()
        self.sombra.enabled = alto is not None
        if alto is not None:
            self.sombra.position = (sim.x, alto + 0.03, sim.z)
            self.sombra.scale = max(0.35, 0.8 - 0.12 * (sim.y - alto))
        self.baliza.alpha = 0.45 + 0.2 * math.sin(sim.t * 3.0)
        if self.visual:
            self._sincronizar_visual(sim, dt)

    def orientar_avatar(self, mx, mz, dt):
        if abs(mx) + abs(mz) < 1e-3:
            return
        meta = math.degrees(math.atan2(mx, mz))
        if self._skin is not None:
            self._skin.mirar_hacia(meta)            # el modelo gira suave solo (girar() en su update)
            return
        delta = (meta - self._yaw_avatar + 180) % 360 - 180
        self._yaw_avatar += delta * min(1.0, 14.0 * dt)
        self.avatar.rotation_y = self._yaw_avatar

    def _estado_visual(self, caja, p, tono, sim):
        if self.visual:
            return self._estado_visual_neon(caja, p, sim)
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


    # -- Aspecto cyber/neón (aditivo; ver parkour_visual_calculos / parkour_decoracion / parkour_efectos) --

    # Plataformas fijas: UNA malla con color por vértice (franja de aterrizaje + patrón por tipo). Móviles, que
    # desaparecen y ligadas a interruptor: una entidad con su propia caja neón (el estado se tiñe con el color de la entidad).
    def _construir_plataformas_neon(self):
        mallas, guias, gv, gc = [], [], [], []
        for p in self.nivel.plataformas.values():
            clave = pvc.clave_estilo(p.tipo, p.requiere, p.id == self.nivel.meta, p.checkpoint)
            caja = pvc.caja_neon(p.ancho, p.fondo, GROSOR + (0.15 if clave in ("meta", "checkpoint") else 0.0), clave)
            if p.tipo == "fija" and not p.requiere:
                v, c, t = caja
                mallas.append((pvc.desplazar(v, p.x, p.y, p.z), c, t))
            else:
                entidad = Entity(parent=self, position=(p.x, p.y, p.z))
                nodo_malla(*caja, nombre=f"plat_{p.id}").reparent_to(entidad)
                entidad.setTwoSided(True)
                self._dinamicas[p.id] = (entidad, None)
                if p.tipo == "movil" and p.movimiento:       # guía del recorrido: se ve hasta dónde llega la plataforma
                    ex, ey, ez = p.movimiento.get("eje", (0, 0, 0))
                    col = pvc.ESTILOS["movil"]["borde"]
                    gv += [(p.x - ex, p.y - ey + 0.02, p.z - ez), (p.x + ex, p.y + ey + 0.02, p.z + ez)]
                    gc += [pvc.escalar(col, 0.7)] * 2
        if mallas:
            v, c, t = pvc.unir_mallas(mallas)
            self.casco = Entity(parent=self)
            nodo = nodo_malla(v, c, t, nombre="plataformas")
            nodo.reparent_to(self.casco)
            nodo.setTwoSided(True)
        if gv:
            guia = Entity(parent=self)
            nodo = nodo_malla(gv, gc, primitiva="lineas", nombre="guias")
            nodo.reparent_to(guia)
            nodo.setRenderModeThickness(2.0)
            nodo.setLightOff()

    def _construir_visual(self):
        self.decoracion = DecoracionParkour(self.nivel, parent=self)
        self.efectos = EfectosParkour(self.nivel, parent=self)
        for pid in self._marcas_cp:
            self._marcas_cp[pid].scale = 0.4

    def _estado_visual_neon(self, caja, p, sim):
        if p.requiere is not None and not sim.activa(p):
            caja.enabled = True
            caja.setTransparency(TransparencyAttrib.M_alpha)
            caja.setColorScale(color.rgba(1, 1, 1, 0.3))
            return
        caja.setTransparency(TransparencyAttrib.M_none)
        if sim.fase(p) == "oculta":
            caja.enabled = False
            return
        caja.enabled = True
        brillo = sim.fase(p) == "aviso" and int(sim.t * PARPADEO_HZ * 2) % 2 == 0
        caja.setColorScale(color.rgba(2.6, 2.6, 2.6, 1) if brillo else color.white)

    def _sincronizar_visual(self, sim, dt):
        self.decoracion.sincronizar(sim.t, sim.x, sim.y, sim.z)
        self.efectos.sincronizar(sim, dt)
        for marca in self._marcas_cp.values():
            marca.rotation_y = sim.t * 90

    # Un evento de la simulación (texto de Simulacion.paso) -> efectos de juego. Sin efecto con el aspecto anterior.
    def reaccionar(self, evento, sim):
        if self.efectos is not None:
            self.efectos.reaccionar(evento, sim)
