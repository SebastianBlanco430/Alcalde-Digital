# Figuras del nivel B de la multitud (frontend/multitud.py): el mismo personaje de los actores animados (mismo .glb,
# misma ropa, misma cara y mochila: el PersonajeNPC de npc_modelo.py) HORNEADO en una pose fija. Se deforma el esqueleto
# una sola vez en la CPU y se guarda la malla ya posada, con los Geoms que comparten estado unidos (un GeomNode, pocos
# draws), sin esqueleto ni animación: pintarla no cuesta nada en la CPU. Cada variante (aspecto) trae tres figuras:
# dos instantes de la marcha (las piernas cruzadas al revés) y la de pie; la multitud alterna las dos primeras por paso.
#
# Las variantes usan los índices de peatón INDICE_BASE..: iguales a las de los actores de nivel A, así que un agente
# conserva ropa, piel y cara al pasar de A a B. El .glb original y los demás personajes no se tocan.

import sys

from panda3d.core import GeomNode, GeomVertexFormat, NodePath, RenderState, Thread, MaterialAttrib
from ursina import camera, destroy, time

from backend.logica.multitud_calculos import VARIANTES
from frontend import npc_calculos as nc, skinning_gpu
from frontend.npc_modelo import PersonajeNPC, crear_npc
from frontend.peatones import ROPA, SEMILLA
from frontend.peatones_calculos import aspecto_peaton, rasgos_peaton

INDICE_BASE = 16                 # primer índice de peatón de las variantes (de 4 en 4: los cuatro modelos, dos veces)
POSES = (("Caminar", 0.10), ("Caminar", 0.60), ("Idle", 0.0))     # (clip, fracción del clip): paso A, paso B, de pie
FIGURA_PASO_A, FIGURA_PASO_B, FIGURA_PARADO = 0, 1, 2
SIN_CONTORNO = True              # las figuras (25-90 m) no llevan la cáscara de tinta: ~35 % menos triángulos (el borde mide <1 px)
# Hornear la malla de la pose exige el skinning por CPU (con la GPU la malla guarda el pose de reposo).


def indice_variante(variante):
    return INDICE_BASE + variante % VARIANTES


DISTANCIA_ROSTRO = 14.0          # m: más lejos de la cámara la cara del actor de nivel A no se anima (ahorra ~0,1 ms por actor)


class ActorMultitud(PersonajeNPC):
    """PersonajeNPC de la multitud: igual que el de los peatones, pero con la cara animada solo a menos de DISTANCIA_ROSTRO."""

    def _animar_rostro(self):
        self._t_lod -= time.dt
        if self._t_lod <= 0:
            self._t_lod = nc.INTERVALO_LOD
            try:
                distancia = (camera.world_position - self.world_position).length()
            except Exception:
                distancia = 0.0
            self._cerca = not (distancia > DISTANCIA_ROSTRO)
            self._ajustar_cuerpo(nc.cuerpo_congelado(distancia))
        return self._cerca


def crear_actor_variante(variante, **opciones):
    """PersonajeNPC de la variante (el mismo que se hornea); `opciones` van a la Entity (parent=...)."""
    i = indice_variante(variante)
    aspecto, rasgos = aspecto_peaton(i, SEMILLA), rasgos_peaton(i, SEMILLA)
    try:
        return ActorMultitud(f"Peatón {i}", nc.plan_npc(i, SEMILLA, aspecto), aspecto, rasgos, **opciones)
    except Exception as error:
        print(f"[multitud] actor {i}: {error}; se usa el de siempre", file=sys.stderr)
        return crear_npc(i, SEMILLA, aspecto, rasgos, ROPA[i % len(ROPA)], **opciones)


def _es_contorno(nodo, estado):
    """¿Es la cáscara de tinta invertida (el contorno negro) de una pieza? Material «Contorno» o nodo «contorno»."""
    if nodo.getName() == "contorno":
        return True
    atributo = estado.getAttrib(MaterialAttrib.getClassType())
    material = atributo.getMaterial() if atributo is not None else None
    return material is not None and material.getName() == "Contorno"


def _geometria_posada(personaje):
    """NodePath con una copia estática (vértices ya deformados) de todo lo visible del actor, en el sistema del cuerpo."""
    actor, cuerpo = personaje.actor, personaje.cuerpo
    actor.update()
    figura = NodePath("figura_multitud")
    for nodo in actor.findAllMatches("**/+GeomNode"):
        if nodo.isHidden() or nodo.node().getNumGeoms() == 0:
            continue
        origen = nodo.node()
        nuevo = GeomNode(nodo.getName())
        for k in range(origen.getNumGeoms()):
            if SIN_CONTORNO and _es_contorno(nodo, origen.getGeomState(k)):
                continue
            geom = origen.getGeom(k).makeCopy()
            datos = geom.getVertexData().animateVertices(True, Thread.getCurrentThread())
            if datos.getFormat().getNumArrays() > 1:       # sin los arrays de huesos: solo posición, normal y color
                formato = GeomVertexFormat()
                formato.addArray(datos.getFormat().getArray(0))
                datos = datos.convertTo(GeomVertexFormat.registerFormat(formato))
            geom.setVertexData(datos)
            estado = origen.getGeomState(k).removeAttrib(MaterialAttrib.getClassType())   # el material no se usa: se unen más Geoms
            nuevo.addGeom(geom, estado)
        destino = NodePath(nuevo)
        destino.reparentTo(figura)
        destino.setMat(nodo.getMat(cuerpo))
    figura.flattenStrong()
    return figura


def _poner_pose(personaje, clip, fraccion):
    actor = personaje.actor
    for nombre in actor.getAnimNames():
        actor.setControlEffect(nombre, 0.0)
    actor.setControlEffect(clip, 1.0)
    frames = max(1, actor.getNumFrames(clip))
    actor.pose(clip, int(fraccion * frames) % frames)


def hornear_variante(variante):
    """[figura de paso A, figura de paso B, figura de pie]: NodePath sueltos (sin padre), con los pies en y = 0 y mirando
    a +z como el cuerpo de un PersonajeNPC. Si algo falla devuelve None (la multitud se queda sin nivel B para esa variante)."""
    previo = skinning_gpu.SKINNING_GPU
    skinning_gpu.SKINNING_GPU = False
    personaje = None
    try:
        personaje = crear_actor_variante(variante)
        if not hasattr(personaje, "actor"):                # el muñeco procedural de respaldo no tiene Actor
            return None
        figuras = []
        for clip, fraccion in POSES:
            _poner_pose(personaje, clip, fraccion)
            figuras.append(_geometria_posada(personaje))
        return figuras
    except Exception as error:
        print(f"[multitud] no se pudo hornear la variante {variante}: {error}", file=sys.stderr)
        return None
    finally:
        skinning_gpu.SKINNING_GPU = previo
        if personaje is not None:
            destroy(personaje)
