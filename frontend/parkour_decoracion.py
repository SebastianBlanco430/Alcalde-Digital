# Decoración del parkour (Ursina/Panda3D): cielo degradado (domo), rejillas del vacío a varias profundidades, bits de
# datos flotando y torres de servidores en la distancia. Todo son pocas mallas ESTÁTICAS con color por vértice (sin luces,
# sin niebla de Panda); lo único que se mueve es la posición de 6 nodos, que `sincronizar` fija una vez por frame (nada
# tiene update()). La matemática vive en parkour_visual_calculos.py. Hija de MundoParkour: se destruye con ella.

import math

from panda3d.core import (ColorBlendAttrib, Geom, GeomLines, GeomNode, GeomPoints, GeomTriangles, GeomVertexData,
                          GeomVertexFormat, GeomVertexWriter, NodePath)
from ursina import Entity

from frontend import parkour_visual_calculos as pvc
from frontend.piezas import silenciar

RADIO_DOMO = 260.0
MARGEN_REJILLA = 70.0
BITS_POR_CAPA = 55


# NodePath con color por vértice. vertices: [(x,y,z)]; colores: [(r,g,b[,a])] 0-255; indices: triángulos [(a,b,c)] o, con
# primitiva "lineas"/"puntos", la lista plana de vértices (en pares para líneas).
def nodo_malla(vertices, colores, indices=None, primitiva="triangulos", nombre="malla"):
    datos = GeomVertexData(nombre, GeomVertexFormat.get_v3c4(), Geom.UH_static)
    datos.set_num_rows(len(vertices))
    ev, ec = GeomVertexWriter(datos, "vertex"), GeomVertexWriter(datos, "color")
    for p, c in zip(vertices, colores):
        ev.add_data3(*p)
        ec.add_data4(c[0] / 255, c[1] / 255, c[2] / 255, (c[3] if len(c) > 3 else 255) / 255)
    if primitiva == "triangulos":
        prim = GeomTriangles(Geom.UH_static)
        for a, b, c in indices:
            prim.add_vertices(a, b, c)
    elif primitiva == "lineas":
        prim = GeomLines(Geom.UH_static)
        for i in range(0, len(vertices) - 1, 2):
            prim.add_vertices(i, i + 1)
    else:
        prim = GeomPoints(Geom.UH_static)
        for i in range(len(vertices)):
            prim.add_vertex(i)
    geom = Geom(datos)
    geom.add_primitive(prim)
    nodo = GeomNode(nombre)
    nodo.add_geom(geom)
    return NodePath(nodo)


def aditivo(nodo):
    nodo.setTransparency(1)
    nodo.setAttrib(ColorBlendAttrib.make(ColorBlendAttrib.M_add, ColorBlendAttrib.O_incoming_alpha, ColorBlendAttrib.O_one))
    nodo.setDepthWrite(False)
    nodo.setLightOff()
    nodo.setTwoSided(True)
    return nodo


class DecoracionParkour(Entity):

    def __init__(self, nivel, **opciones):
        super().__init__(**opciones)
        self.tema = pvc.tema_visual(nivel.tema)
        plataformas = list(nivel.plataformas.values())
        xs, zs, ys = [p.x for p in plataformas], [p.z for p in plataformas], [p.y for p in plataformas]
        self.cx, self.cz = (min(xs) + max(xs)) / 2, (min(zs) + max(zs)) / 2
        self.sx, self.sz = (max(xs) - min(xs)) / 2 + MARGEN_REJILLA, (max(zs) - min(zs)) / 2 + MARGEN_REJILLA
        self.y_abismo, self.y_alto = nivel.y_muerte, max(ys)
        self._capas = []                # (entidad, paso, velocidad, eje)
        self._bits = []                 # (entidad, alto, velocidad)
        self._construir_domo()
        self._construir_rejillas()
        self._construir_bits()
        self._construir_torres(nivel, [(p.x, p.z) for p in plataformas])
        silenciar(self)

    def _construir_domo(self):
        v, c, t = pvc.domo(RADIO_DOMO, self.tema)
        self.domo = Entity(parent=self)
        nodo = nodo_malla(v, c, t, nombre="domo")
        nodo.reparent_to(self.domo)
        nodo.setTwoSided(True)
        nodo.setBin("background", 0)
        nodo.setDepthWrite(False)
        nodo.setDepthTest(False)
        nodo.setLightOff()

    def _construir_rejillas(self):
        base = self.tema["rejilla"]
        for i, (dy, paso, brillo, vel) in enumerate(((1.0, 4.0, 1.0, 0.6), (-16.0, 8.0, 0.8, -0.9), (-42.0, 16.0, 0.6, 1.2))):
            v, c = pvc.rejilla_en_profundidad(self.cx, self.cz, self.sx, self.sz, self.y_abismo + dy, paso,
                                              pvc.escalar(base, brillo))
            capa = Entity(parent=self)
            nodo = nodo_malla(v, c, primitiva="lineas", nombre=f"rejilla{i}")
            nodo.reparent_to(capa)
            nodo.setRenderModeThickness(2.0 if i == 0 else 1.5)
            nodo.setLightOff()
            self._capas.append((capa, paso, vel))

    def _construir_bits(self):
        paleta = [self.tema["luz"], self.tema["luz"], self.tema["luz2"], (235, 245, 255)]
        alto = self.y_alto + 28 - self.y_abismo
        caja = ((self.cx - self.sx * 0.7, self.cx + self.sx * 0.7), (self.y_abismo, self.y_abismo + alto),
                (self.cz - self.sz * 0.7, self.cz + self.sz * 0.7))
        for i, (velocidad, grosor) in enumerate(((1.1, 3.0), (2.0, 2.0))):
            puntos = pvc.bits_de_datos(BITS_POR_CAPA, caja, 11 + i, paleta)
            v, c = [], []
            for k in (-1, 0):                                   # dos copias del patrón: la subida envuelve sin salto
                for x, y, z, col in puntos:
                    v.append((x, y + k * alto, z))
                    c.append(col)
            entidad = Entity(parent=self)
            nodo = nodo_malla(v, c, primitiva="puntos", nombre=f"bits{i}")
            nodo.reparent_to(entidad)
            nodo.setRenderModeThickness(grosor)
            nodo.setLightOff()
            self._bits.append((entidad, alto, velocidad))

    def _construir_torres(self, nivel, puntos):
        extension = max(self.sx, self.sz) - MARGEN_REJILLA
        n = max(14, min(34, 12 + int(extension / 4)))
        y_base = self.y_abismo - 75
        torres = pvc.colocar_torres(puntos, n, semilla=sum(map(ord, nivel.id)) + 5, y_base=y_base,
                                    y_alto=self.y_alto + 55)
        mallas = []
        for i, (x, z, ancho, fondo, techo) in enumerate(torres):
            d = min(math.hypot(x - px, z - pz) for px, pz in puntos)
            niebla = min(0.75, d / 150.0)
            mallas.append(pvc.malla_torre(x, z, ancho, fondo, y_base, techo, self.tema, 100 + i, niebla,
                                          cielo=self.tema["horizonte"]))
        if not mallas:
            return
        v, c, t = pvc.unir_mallas(mallas)
        self.torres = Entity(parent=self)
        nodo = nodo_malla(v, c, t, nombre="torres")
        nodo.reparent_to(self.torres)
        nodo.setTwoSided(True)
        nodo.setLightOff()
        self.n_torres = len(torres)

    # Una vez por frame: el domo acompaña al jugador; las rejillas derivan; los bits suben.
    def sincronizar(self, t, x, y, z):
        if not self.domo.is_empty():
            self.domo.position = (x, y, z)
        for i, (capa, paso, vel) in enumerate(self._capas):
            capa.x = pvc.deriva(t, abs(vel), paso) * (1 if vel > 0 else -1)
            capa.z = pvc.deriva(t, abs(vel) * 0.7, paso) * (1 if vel > 0 else -1)
        for entidad, alto, vel in self._bits:
            entidad.y = pvc.subida_bits(t, vel, alto)
