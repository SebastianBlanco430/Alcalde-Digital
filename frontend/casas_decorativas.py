# Casas decorativas (no interactivas) dibujadas en lote, a partir de las CasaDecorativa del
# backend (backend/logica/mundo_ciudad.py).
#
# Rendimiento: cada modelo .glb tiene una pieza por material (7 a 12), así que 150 casas sueltas
# serían ~1500 llamadas de dibujo, y también ~1500 en la pasada de sombras. Aquí se copian todas
# bajo una raíz y se funden con flatten_strong(): Panda junta las piezas que comparten estado
# (textura y material) en una sola geometría y hornea en los vértices la posición, el giro, la
# escala y el tinte de cada copia. A diferencia de Entity.combine() (que pierde las texturas),
# conserva el estado de cada pieza: el lote queda en una llamada por material distinto.
#
# Lo fundido ya no se puede mover ni quitar por separado: solo sirve para lo estático.
#
# Pisos: una casa con `pisos` > 1 es el mismo modelo repetido hacia arriba (cada piso, el alto del
# modelo escalado) con el tinte siguiente, como las casas que crecen por encima en una favela.

from panda3d.core import ColorAttrib, MaterialAttrib, NodePath
from ursina import Entity, load_model
from ursina.shaders import lit_with_shadows_shader

from backend.datos.modelos_edificios import modelo_de
from frontend.componentes import rgb


# Entity con todas las `casas` fundidas, colgada de `padre`. `tintes`: lista de (r, g, b) que
# se elige con casa.variante. `alturas`: la y de apoyo de cada casa (None = todas en 0).
def construir_casas(padre, casas, tintes, alturas=None):
    lote = Entity(parent=padre, shader=lit_with_shadows_shader)
    raiz = NodePath("casas_decorativas")
    fuentes = {}
    for casa, y in zip(casas, alturas or [0.0] * len(casas)):
        if casa.modelo not in fuentes:
            fuentes[casa.modelo] = _fuente(casa.modelo)
        alto_piso = modelo_de(casa.modelo).alto * casa.escala
        for piso in range(getattr(casa, "pisos", 1)):
            copia = fuentes[casa.modelo].copy_to(raiz)
            # Mismo criterio que Entity (Ursina usa y arriba): hpr = (-rotation_y, -rotation_x, rotation_z).
            copia.set_pos(casa.cx, y + piso * alto_piso, casa.cz)
            copia.set_hpr(-casa.rumbo, 0, 0)
            copia.set_scale(casa.escala)
            copia.set_color_scale(rgb(tintes[(casa.variante + piso) % len(tintes)]))
    raiz.clear_model_nodes()     # el ModelRoot de cada .glb impide fundir las copias entre sí
    raiz.flatten_strong()
    raiz.reparent_to(lote)
    return lote


# El modelo cargado una vez, con el color base de sus materiales pasado a color plano.
def _fuente(nombre):
    fuente = load_model(modelo_de(nombre).archivo).copy_to(NodePath(nombre))
    color_base_como_color(fuente)
    return fuente


# lit_with_shadows_shader multiplica textura * color del vértice y no lee el material, así que el
# color base de los materiales glTF (las caras sin textura de los modelos) se perdería y se
# verían blancas. Se copia a un color plano por geom (en las caras con textura el factor es 1).
def color_base_como_color(nodo):
    for camino in nodo.find_all_matches("**/+GeomNode"):
        geom_node = camino.node()
        for i in range(geom_node.get_num_geoms()):
            estado = geom_node.get_geom_state(i)
            atributo = estado.get_attrib(MaterialAttrib)
            material = atributo.get_material() if atributo else None
            if material is not None and material.has_base_color():
                geom_node.set_geom_state(i, estado.set_attrib(ColorAttrib.make_flat(material.get_base_color())))
