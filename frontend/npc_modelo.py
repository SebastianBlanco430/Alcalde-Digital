# NPC (peatones) con el mismo modelo que los personajes principales: cada uno es una copia de uno de los 4 .glb
# (periodista, smoking, brasileña, ciudadano) con otra ropa, otro tono de piel, su cara por código (rasgos del
# peatón), a veces una mochila, y su propia escala y fase de animación. Es un PersonajeModelo (misma API que
# Personaje), así que frontend/peatones.py lo mueve igual que antes.
#
# No hay Blender instalado: la ropa se cambia en Panda3D reescribiendo el color de vértice de las piezas de la
# copia del Actor (frontend/npc_color.py); el .glb original y los personajes principales no cambian. El casco
# de tinta, el pelo del modelo y las bandas de luz se conservan. Cada modelo se carga UNA vez (caché de
# personaje_modelo._bases) y cada NPC es una copia.

import sys
import zlib

from ursina import camera, time
from panda3d.core import Mat4, Vec3, CS_zup_right, getDefaultCoordinateSystem

from frontend import modelo_calculos as mc
from frontend import npc_calculos as nc
from frontend import rostro_calculos as rc
from frontend.npc_color import agregar_camiseta, recolorear_actor
from frontend.personaje import Personaje
from frontend.personaje_modelo import PersonajeModelo, _cargar_actor
from frontend.rostro_modelo import _armar, colocar_rostro_animado_piezas

_avisados = set()


def _avisar(motivo):
    if motivo not in _avisados:
        _avisados.add(motivo)
        print(f"[assets] NPC: {motivo}.", file=sys.stderr)


# Piezas de una mochila (ejes del glb crudo, centradas en el origen): cuerpo, solapa, bolsillo y dos tirantes.
def piezas_mochila(color):
    oscuro = tuple(c * 0.7 for c in color)
    c = rc.GROSOR_CONTORNO
    return [rc._pieza("mochila_cuerpo", "caja", (0.0, 0.0, 0.0), (0.105, 0.065, 0.15), color, contorno=c),
            rc._pieza("mochila_solapa", "caja", (0.0, 0.004, 0.115), (0.108, 0.068, 0.045), oscuro, contorno=c),
            rc._pieza("mochila_bolsillo", "caja", (0.0, 0.07, -0.05), (0.07, 0.022, 0.07), oscuro, contorno=c),
            rc._pieza("tirante_-1", "caja", (-0.075, -0.075, 0.03), (0.018, 0.012, 0.12), oscuro),
            rc._pieza("tirante_1", "caja", (0.075, -0.075, 0.03), (0.018, 0.012, 0.12), oscuro)]


class PersonajeNPC(PersonajeModelo):

    def __init__(self, nombre, plan, aspecto, rasgos, **opciones):
        # Estos datos los usan los ganchos que PersonajeModelo.__init__ llama; van antes de crear la Entity.
        self._plan = plan
        self._aspecto = aspecto
        self._rasgos = nc.rasgos_para_modelo(plan["archivo"], rasgos)
        super().__init__(nombre, plan["rol"], **opciones)
        self._poner_mochila()
        self._congelado = False       # cuerpo congelado por estar lejos de la cámara
        self._cerca = True            # ¿está lo bastante cerca de la cámara para animarle la cara?
        self._t_lod = plan["fase"] * nc.INTERVALO_LOD

    # Copia del Actor del rol con la ropa y la piel del plan.
    def _crear_actor(self, rol):
        actor = _cargar_actor(rol)
        try:
            recolorear_actor(actor, nc.objetivos_recolor(self._plan))
            tipo = self._plan.get("camiseta_nueva")
            if tipo:
                agregar_camiseta(actor, self._plan["colores"]["camiseta"], nc.huesos_camiseta(tipo), nc.GROSOR_CAMISETA)
        except Exception as error:
            _avisar(f"no se pudo recolorear {self._plan['archivo']} ({error})")
        return actor

    def _escala_modelo(self, rol):
        return mc.escala_para_rol(rol) * self._plan["escala"]

    # Cara por código con los rasgos del peatón (peinado, gafas, gorra...), ajustada a la cabeza del modelo.
    def _poner_rostro(self, rol, nombre):
        descriptor = rc.descriptor_peaton(self._rasgos, self._aspecto["piel"], self._aspecto["pelo"])
        piezas = rc.piezas_rostro(descriptor)
        if rol in rc.AJUSTE_ROSTRO_POR_ROL:
            piezas = rc.ajustar_piezas(piezas, *rc.AJUSTE_ROSTRO_POR_ROL[rol])
        return colocar_rostro_animado_piezas(self.actor, rol, piezas, zlib.crc32(nombre.encode()))

    # Cada NPC arranca su ciclo en un punto distinto para no ir todos al compás.
    def _iniciar_loop(self, clip):
        self.actor.loop(clip)
        control = self.actor.getAnimControl(clip)
        if control is not None and control.getNumFrames() > 1:
            control.pose(int(self._plan["fase"] * control.getNumFrames()) % control.getNumFrames())
            control.loop(False)

    # Cada INTERVALO_LOD s mira la distancia a la cámara: lejos se apaga la cara y se congela el cuerpo.
    # Devuelve si la cara se anima este frame.
    def _animar_rostro(self):
        self._t_lod -= time.dt
        if self._t_lod <= 0:
            self._t_lod = nc.INTERVALO_LOD
            try:
                distancia = (camera.world_position - self.world_position).length()
            except Exception:
                distancia = 0.0
            self._cerca = nc.rostro_activo(distancia)
            self._ajustar_cuerpo(nc.cuerpo_congelado(distancia))
        return self._cerca

    # Congela (velocidad 0: el esqueleto no se recalcula) o reanuda la animación de los clips activos. Mientras está
    # congelado se repite cada revisión por si un cambio de clip la reanudó.
    def _ajustar_cuerpo(self, congelar):
        if self.actor is None or (not congelar and not self._congelado):
            return
        try:
            for clip in list(self._pesos):
                velocidad = 0.0 if congelar else ((self._rate or 1.0) if clip == self._clip else 1.0)
                self.actor.setPlayRate(velocidad, clip)
            self._congelado = congelar
        except Exception as error:
            _avisar(f"no se pudo ajustar la animación del cuerpo ({error})")

    # Mochila colgada del hueso de la espalda (si el plan trae una). Nunca lanza.
    def _poner_mochila(self):
        color = self._plan.get("mochila")
        if color is None:
            return
        try:
            hueso_nombre, centro = nc.ESPALDA_POR_ROL[self._plan["rol"]]
            hueso = self.actor.exposeJoint(None, "modelRoot", hueso_nombre)
            if hueso is None:
                return
            raiz = self.actor.attachNewNode("mochila")
            raiz.setMat(Mat4.translateMat(Vec3(*centro)) * Mat4.convertMat(CS_zup_right, getDefaultCoordinateSystem()))
            _armar(raiz, piezas_mochila(color), False)
            raiz.wrtReparentTo(hueso)
        except Exception as error:
            _avisar(f"no se pudo poner la mochila ({error})")


# Fábrica: PersonajeNPC del peatón `indice`; si algo falla devuelve el muñeco procedural de siempre.
# `color_ropa` solo lo usa el respaldo procedural.
def crear_npc(indice, semilla, aspecto, rasgos, color_ropa, **opciones):
    try:
        plan = nc.plan_npc(indice, semilla, aspecto)
        return PersonajeNPC(f"Peatón {indice}", plan, aspecto, rasgos, **opciones)
    except Exception as error:
        _avisar(f"peatón {indice}: no se pudo crear el modelo ({error}); se usa el muñeco procedural")
        return Personaje("", color_ropa, apariencia=dict(aspecto, rasgos=rasgos, piel_rgb=aspecto["piel"],
                                                          pelo_rgb=aspecto["pelo"]), **opciones)
