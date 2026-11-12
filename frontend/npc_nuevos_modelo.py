# Carga y pintura de los NPC NUEVOS (npc_hombre_01..03 y npc_mujer_01..02; datos en frontend/npc_nuevos_calculos.py).
# Esos .glb llegan sin animaciones, sin casco de tinta y con el color plano, así que al cargar cada uno (UNA vez; cada
# NPC es una copia, como los demás modelos) se le añade lo que falta para que sea un modelo más del juego:
#   - se quita la escala del nodo del esqueleto (queda en las medidas del periodista / la brasileña, con las que
#     trabajan el rostro, la mochila y la marcha) y esa escala pasa al Actor (plan["escala_base"]);
#   - clips: Idle, Hablar, Saludar, Caminar y Correr por código (frontend/npc_postura.py), los de la animación
#     humana (frontend/animacion_humana.py) y las variantes de postura;
#   - bandas de luz horneadas en el color de vértice y un casco de tinta (Geom extra con el material «Contorno»,
#     el mismo nombre que usan los otros .glb: la multitud lo reconoce y lo quita en sus figuras lejanas).
# Cada NPC recolorea su copia por zonas (piel, camiseta, pantalón, pelo, zapatos); el .glb no se toca.
# Si algo falla, `disponible()` avisa UNA vez por modelo y quien crea el NPC usa otro modelo (npc_modelo.crear_npc).

import sys

import gltf
from direct.actor.Actor import Actor
from panda3d.core import (Geom, GeomTriangles, GeomVertexData, GeomVertexReader, GeomVertexRewriter, GeomVertexWriter,
                          Material, MaterialAttrib, NodePath, RenderState)

from frontend import animacion_humana as ah
from frontend import npc_nuevos_calculos as nn
from frontend import npc_postura
from frontend import personaje_modelo as pm

CONTORNO = True                  # casco de tinta en los modelos nuevos (False = sin contorno, ~mitad de triángulos)
POSTURAS = True                  # hornear las variantes de postura (False = los nuevos solo tienen la postura neutra)

_zonas = {}                      # clave -> {(nodo, geom): [(grupo, brillo, color original)] por fila de vértices}
_fallidos = {}                   # clave -> motivo (no se reintenta en cada NPC)


def _avisar(clave, motivo):
    print(f"[assets] NPC nuevo {clave}: {motivo}. Se usa uno de los modelos de siempre.", file=sys.stderr)


# Grupo, brillo de la banda de luz y color original de cada fila de vértices de un Geom.
def _leer_zonas(datos, archivo):
    filas = []
    color, normal = GeomVertexReader(datos, "color"), GeomVertexReader(datos, "normal")
    while not color.isAtEnd():
        c, n = color.getData4(), normal.getData3()
        filas.append((nn.grupo_de_color(archivo, c), nn.banda_luz(n), (c[0], c[1], c[2])))
    return filas


# Escribe el color de cada fila: el del objetivo de su grupo (o el original) por el brillo de su banda.
def _pintar(datos, filas, objetivos):
    escritor = GeomVertexWriter(datos, "color")
    for grupo, brillo, original in filas:
        r, g, b = nn.color_con_banda(objetivos.get(grupo, original), brillo)
        escritor.setData4(r, g, b, 1.0)


# Casco de tinta de un Geom: los mismos vértices (mismo esqueleto) inflados por la normal SUAVIZADA (la media de
# las normales de los vértices que comparten posición: la malla es de caras planas y sin eso el casco se abriría por
# las aristas), en color tinta y con los triángulos al revés (solo se ve por el borde).
def _casco_tinta(origen):
    datos = GeomVertexData(origen.getVertexData())
    posicion, normal = GeomVertexReader(datos, "vertex"), GeomVertexReader(datos, "normal")
    puntos, suma = [], {}
    while not posicion.isAtEnd():
        p, n = posicion.getData3(), normal.getData3()
        clave = (round(p[0], 4), round(p[1], 4), round(p[2], 4))
        puntos.append((clave, (p[0], p[1], p[2])))
        s = suma.setdefault(clave, [0.0, 0.0, 0.0])
        s[0] += n[0]
        s[1] += n[1]
        s[2] += n[2]
    escritor, color = GeomVertexRewriter(datos, "vertex"), GeomVertexWriter(datos, "color")
    for clave, p in puntos:
        s = suma[clave]
        largo = (s[0] ** 2 + s[1] ** 2 + s[2] ** 2) ** 0.5 or 1.0
        k = nn.GROSOR_CONTORNO / largo
        escritor.setData3(p[0] + s[0] * k, p[1] + s[1] * k, p[2] + s[2] * k)
        color.setData4(*nn.COLOR_CONTORNO, 1.0)
    triangulos = GeomTriangles(Geom.UHStatic)
    for primitiva in origen.getPrimitives():
        primitiva = primitiva.decompose()
        vertices = [primitiva.getVertex(i) for i in range(primitiva.getNumVertices())]
        for t in range(0, len(vertices) - 2, 3):
            triangulos.addVertices(vertices[t], vertices[t + 2], vertices[t + 1])
    triangulos.closePrimitive()
    casco = Geom(datos)
    casco.addPrimitive(triangulos)
    return casco


# Deja el modelo recién cargado listo para ser la base de las copias (ver la cabecera). Lanza si no se puede.
def _preparar(modelo_np, archivo, clave):
    personaje = modelo_np.find("**/+Character")
    if personaje.isEmpty():
        raise ValueError("el modelo no tiene esqueleto")
    personaje.clearTransform()                       # la escala del .glb pasa al Actor (plan["escala_base"])
    zonas = {}
    estado_casco = RenderState.make(MaterialAttrib.make(Material("Contorno")))
    for nodo in modelo_np.findAllMatches("**/+GeomNode"):
        geom_node = nodo.node()
        for i in range(geom_node.getNumGeoms()):
            datos = geom_node.modifyGeom(i).modifyVertexData()
            if not (datos.hasColumn("color") and datos.hasColumn("normal")):
                continue
            filas = _leer_zonas(datos, archivo)
            zonas[(nodo.getName(), i)] = filas
            if CONTORNO:                             # antes de pintar: el casco se copia de los vértices originales
                geom_node.addGeom(_casco_tinta(geom_node.getGeom(i)), estado_casco)
            _pintar(datos, filas, {})                # la base ya lleva las bandas de luz con sus colores de origen
    if not zonas:
        raise ValueError("el modelo no tiene color de vértice")
    npc_postura.hornear_clips_basicos(modelo_np)
    if pm.ANIMACION_HUMANA:
        ah.hornear_clips(modelo_np, clave)
        if POSTURAS:
            npc_postura.hornear_posturas(modelo_np, clave)
    return zonas


# Actor base del modelo del plan (cargado y preparado una sola vez; va a la caché de personaje_modelo, como los demás).
def _base(plan):
    clave = plan["rol"]
    base = pm._bases.get(clave)
    if base is not None and clave in _zonas:
        return base
    if clave in _fallidos:
        raise RuntimeError(_fallidos[clave])
    try:
        ruta = pm.CARPETA_MODELOS / plan["archivo"]
        if not ruta.is_file():
            raise FileNotFoundError(f"no existe {ruta.name}")
        modelo = NodePath(gltf.load_model(str(ruta), gltf_settings=gltf.GltfSettings()))
        zonas = _preparar(modelo, plan["archivo"], clave)
        base = Actor(modelo)
        base.hide()
    except Exception as error:
        _fallidos[clave] = str(error)
        _avisar(clave, f"no se pudo cargar {plan['archivo']} ({error})")
        raise
    _zonas[clave] = zonas
    pm._bases[clave] = base
    return base


# ¿Se puede crear un NPC con el modelo de este plan? Carga la base si hace falta. Nunca lanza (el aviso sale una
# sola vez por modelo, desde _base).
def disponible(plan):
    try:
        _base(plan)
        return True
    except Exception:
        return False


# Copia del Actor del plan con la ropa, la piel y el pelo del NPC. Lanza si el modelo no carga.
def crear_actor(plan):
    actor = Actor(_base(plan))
    objetivos = nn.objetivos_nuevo(plan)
    zonas = _zonas[plan["rol"]]
    for nodo in actor.findAllMatches("**/+GeomNode"):
        geom_node = nodo.node()
        for i in range(geom_node.getNumGeoms()):
            filas = zonas.get((nodo.getName(), i))
            if filas is not None:                    # copia propia de los vértices: no altera a las demás copias
                _pintar(geom_node.modifyGeom(i).modifyVertexData(), filas, objetivos)
    return actor
