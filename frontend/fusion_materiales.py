# Rendimiento: menos draw calls en las casas decorativas de la favela (frontend/casas_decorativas.py).
#
# Perfilado (2026-11, recorrido de scripts/medir_fps.py, RTX 2050): las casas del barrio quedaban en UN GeomNode con
# 305 geoms (305 draw calls y cambios de estado por frame) porque cada geom lleva su propio ColorAttrib plano (la pintura
# del piso) y su MaterialAttrib del .glb, y flatten_strong no funde geoms con estados distintos. Sin color ni material
# quedaban solo 29 estados distintos (la textura).
#
# Aquí, ANTES de copiar y aplanar, el color plano de cada geom de la FUENTE se hornea en la columna de color de sus
# vértices (la columna se añade si el .glb no la trae), su ColorAttrib pasa a ser «de vértice» y se quita su MaterialAttrib.
# Hasta el 2026-11-15 la columna no se añadía y se quitaba el ColorAttrib: las casas de la favela salían blancas/grises.
# Con el shader de Ursina (lit_with_shadows:
# textura · p3d_ColorScale · p3d_Color, sin p3d_Material) el resultado en pantalla es el mismo: p3d_Color pasa de ser el
# color plano a ser el color de vértice con el mismo valor, y el tinte del piso (set_color_scale) se sigue multiplicando
# igual al aplanar. Los geoms sin color plano reciben blanco (lo que Panda daba por defecto sin columna de color) para
# que todos tengan el mismo formato de vértice y se puedan fundir.
#
# BANDERA. FUSION_MATERIALES = False, ALCALDE_SIN_FUSION_MATERIALES=1 o ALCALDE_SIN_RENDIMIENTO=1: las fuentes quedan
# como siempre.

import os
import sys

from panda3d.core import (ColorAttrib, Geom, GeomVertexArrayFormat, GeomVertexData, GeomVertexFormat, GeomVertexWriter,
                          LColor, MaterialAttrib)

FUSION_MATERIALES = True
_BLANCO = LColor(1, 1, 1, 1)


def activo():
    if os.environ.get("ALCALDE_SIN_RENDIMIENTO", "").strip() == "1":
        return False
    return FUSION_MATERIALES and os.environ.get("ALCALDE_SIN_FUSION_MATERIALES", "").strip() != "1"


# Hornea los colores planos de `fuente` (NodePath) en sus vértices y quita color plano y material de cada geom.
# Devuelve la misma fuente. Si algo falla, deja la fuente como estaba en ese geom y avisa una vez (nunca lanza).
def hornear_colores(fuente):
    if not activo():
        return fuente
    try:
        for camino in fuente.find_all_matches("**/+GeomNode"):
            nodo = camino.node()
            for i in range(nodo.get_num_geoms()):
                _hornear_geom(nodo, i)
    except Exception as error:
        print(f"[fusion_materiales] fuente sin fundir ({type(error).__name__}: {error})", file=sys.stderr)
    return fuente


# flatten_strong de `raiz` con el tope de vértices por GeomVertexData subido a MAX_VERTICES mientras dura (el de Panda,
# 65534, partía las casas en muchos geoms aunque tuvieran el mismo estado); al terminar se deja el valor de antes. Sin la
# bandera es el flatten_strong de siempre.
MAX_VERTICES = 1 << 20


def aplanar(raiz):
    if not activo():
        return raiz.flatten_strong()
    from panda3d.core import ConfigVariableInt
    variable = ConfigVariableInt("max-collect-vertices")
    antes = variable.get_value()
    variable.set_value(max(antes, MAX_VERTICES))
    try:
        return raiz.flatten_strong()
    finally:
        variable.set_value(antes)


# Copia de `datos` (GeomVertexData) con la columna «color» llena de `color`. GeomVertexData.set_color no añade la
# columna si falta (pasa con los .glb de las casas, sin COLOR_0): el color se perdía y las casas salían grises.
def _con_color(datos, color):
    if not datos.has_column("color"):
        formato = GeomVertexFormat(datos.get_format())
        formato.add_array(GeomVertexArrayFormat("color", 4, Geom.NT_uint8, Geom.C_color))
        datos = datos.convert_to(GeomVertexFormat.register_format(formato))
    # copia escribible (convert_to y get_vertex_data la devuelven de solo lectura)
    datos = GeomVertexData(datos)
    escritor = GeomVertexWriter(datos, "color")
    for _ in range(datos.get_num_rows()):
        escritor.set_data4(color)
    return datos


def _hornear_geom(nodo, i):
    estado = nodo.get_geom_state(i)
    atributo = estado.get_attrib(ColorAttrib)
    if atributo is not None and atributo.get_color_type() == ColorAttrib.T_vertex:
        nodo.set_geom_state(i, estado.remove_attrib(MaterialAttrib))     # ya usa sus colores de vértice
        return
    if atributo is not None and atributo.get_color_type() == ColorAttrib.T_flat:
        color = atributo.get_color()
    else:
        color = _BLANCO                  # sin ColorAttrib (o T_off): Panda usaba blanco
        if atributo is None and nodo.get_geom(i).get_vertex_data().has_column("color"):
            nodo.set_geom_state(i, estado.remove_attrib(MaterialAttrib))     # colores de vértice propios: se respetan
            return
    geom = nodo.modify_geom(i)
    geom.set_vertex_data(_con_color(geom.get_vertex_data(), color))
    # ColorAttrib de vértice (no quitarlo): sin él, un color plano heredado de un nodo padre pisaba el color horneado
    # y las casas de la favela salían grises (2026-11-15). Todos los geoms horneados llevan el mismo, así que se funden igual.
    nodo.set_geom_state(i, estado.set_attrib(ColorAttrib.make_vertex()).remove_attrib(MaterialAttrib))
