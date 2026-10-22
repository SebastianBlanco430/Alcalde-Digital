# Recolor del color de vértice de un Actor copiado de un .glb (Panda3D). Cada pieza del modelo (Camisa,
# Pantalon, Cuerpo...) es un Geom con color por vértice y las bandas de luz ya horneadas (dos o tres tonos
# del mismo color). Recolorear = poner el color objetivo en el tono más claro de la pieza y escalar los
# demás tonos con la misma proporción, así se conservan las bandas y el aspecto cómic.
# Solo toca los Geoms que se piden; el casco de tinta (negro) y los .glb originales no se tocan.

from panda3d.core import Geom, GeomTriangles, GeomVertexData, GeomVertexReader, GeomVertexRewriter

from frontend import npc_calculos as nc


# Pasa por las piezas del actor (GeomNode con nombre y su índice de Geom) y devuelve cuántas recoloreó.
# `objetivos`: {(nombre_de_nodo, indice_de_geom): (r, g, b) 0-1}.
def recolorear_actor(actor, objetivos):
    hechos = 0
    for nodo in actor.findAllMatches("**/+GeomNode"):
        geom_node = nodo.node()
        for i in range(geom_node.getNumGeoms()):
            objetivo = objetivos.get((nodo.getName(), i))
            if objetivo is None:
                continue
            datos = geom_node.modifyGeom(i).modifyVertexData()     # copia propia: no altera al resto de copias
            if not datos.hasColumn("color"):
                continue
            colores = []
            lector = GeomVertexReader(datos, "color")
            while not lector.isAtEnd():
                c = lector.getData4()
                colores.append((c[0], c[1], c[2], c[3]))
            nuevos = nc.recolorear_tonos(colores, objetivo)
            escritor = GeomVertexRewriter(datos, "color")
            for color in nuevos:
                escritor.setData4(*color)
            hechos += 1
    return hechos


# Peso (0 a 1) que los `huesos` dados tienen en cada fila de vértices de `datos` (None si el Geom no tiene esqueleto).
def _peso_en_huesos(datos, huesos):
    tabla = datos.getTransformBlendTable()
    if tabla is None or not datos.hasColumn("transform_blend"):
        return None
    por_mezcla = []
    for k in range(tabla.getNumBlends()):
        mezcla = tabla.getBlend(k)
        total = 0.0
        for t in range(mezcla.getNumTransforms()):
            junta = mezcla.getTransform(t).getJoint()
            if junta is not None and junta.getName() in huesos:
                total += mezcla.getWeight(t)
        por_mezcla.append(total)
    lector = GeomVertexReader(datos, "transform_blend")
    pesos = []
    while not lector.isAtEnd():
        pesos.append(por_mezcla[lector.getData1i()])
    return pesos


UMBRAL_PESO_CAMISETA = 0.3       # peso medio mínimo de los tres vértices de un triángulo sobre los huesos de la camiseta


# Añade una camiseta al torso desnudo: copia los triángulos de la piel (Cuerpo, Geom 0) cuyos tres vértices
# pesan sobre los `huesos` dados, con color `color`, un poco inflados a lo largo de la normal. Sigue al esqueleto
# porque comparte el esqueleto de la copia. Los vértices son propios, así que la piel no cambia.
# Devuelve el número de triángulos o 0 si no encontró la piel o su esqueleto.
def agregar_camiseta(actor, color, huesos, grosor):
    for nodo in actor.findAllMatches("**/+GeomNode"):
        if nodo.getName() != "Cuerpo":
            continue
        geom_node = nodo.node()
        origen = geom_node.getGeom(0)
        datos = GeomVertexData(origen.getVertexData())             # copia propia (mismo esqueleto)
        pesos = _peso_en_huesos(datos, huesos)
        if pesos is None:
            return 0
        triangulos = GeomTriangles(Geom.UHStatic)
        usados = set()
        for primitiva in origen.getPrimitives():
            primitiva = primitiva.decompose()
            vertices = [primitiva.getVertex(i) for i in range(primitiva.getNumVertices())]
            for t in range(0, len(vertices) - 2, 3):
                a, b, c = vertices[t], vertices[t + 1], vertices[t + 2]
                if (pesos[a] + pesos[b] + pesos[c]) / 3 >= UMBRAL_PESO_CAMISETA:
                    triangulos.addVertices(a, b, c)
                    usados.update((a, b, c))
        if not usados:
            return 0
        posicion, normal = GeomVertexRewriter(datos, "vertex"), GeomVertexReader(datos, "normal")
        colores = GeomVertexRewriter(datos, "color")
        for fila in range(datos.getNumRows()):
            posicion.setRow(fila)
            normal.setRow(fila)
            colores.setRow(fila)
            if fila in usados:
                p, n = posicion.getData3(), normal.getData3()
                posicion.setData3(p[0] + n[0] * grosor, p[1] + n[1] * grosor, p[2] + n[2] * grosor)
                luz = 0.8 + 0.2 * max(0.0, min(1.0, 0.5 + 0.5 * n[1]))     # más clara arriba: banda de luz simple
                colores.setData4(color[0] * luz, color[1] * luz, color[2] * luz, 1.0)
        triangulos.closePrimitive()
        nueva = Geom(datos)
        nueva.addPrimitive(triangulos)
        geom_node.addGeom(nueva, geom_node.getGeomState(0))
        return triangulos.getNumPrimitives()
    return 0
