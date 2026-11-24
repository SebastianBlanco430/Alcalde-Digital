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
# Elenco v2 (sesión F): los .glb v2 (plan["v2"]) entran por aquí igual; su plan trae la ruta y los grupos que se
# recolorean (ninguno, o la piel del NPC de etapa con capucha), y sus zonas se registran desde el propio .glb.

import sys
from pathlib import Path

import gltf
from direct.actor.Actor import Actor
from panda3d.core import (AnimBundle, AnimBundleNode, AnimChannelMatrixXfmTable, AnimGroup, CharacterJoint, Geom, GeomTriangles, GeomVertexData, GeomVertexReader,
                          GeomVertexRewriter, GeomVertexWriter, Material, MaterialAttrib, NodePath, RenderState)

from frontend import animacion_humana as ah
from frontend import casco_pantalla_calculos as cpc
from frontend import npc_nuevos_calculos as nn
from frontend import npc_postura
from frontend import personaje_modelo as pm
from frontend import pesos_cabeza

CONTORNO = True                  # casco de tinta en los modelos nuevos (False = sin contorno, ~mitad de triángulos)
POSTURAS = True                  # hornear las variantes de postura (False = los nuevos solo tienen la postura neutra)

_zonas = {}                      # clave -> {(nodo, geom): [(grupo, brillo, color original)] por fila de vértices}
_fallidos = {}                   # clave -> motivo (no se reintenta en cada NPC)
_clips = {}                      # clave -> (AnimBundles horneados, medidas de animacion_humana, {hueso: padre})
_reordenados = {}                # (clave de la referencia, orden de huesos del v2) -> AnimBundles en ese orden
REUSAR_CLIPS_V2 = True           # carga (sesión F): un .glb v2 usa los clips ya horneados de su referencia


def _avisar(clave, motivo):
    print(f"[assets] NPC nuevo {clave}: {motivo}. Se usa uno de los modelos de siempre.", file=sys.stderr)


# Grupo, brillo de la banda de luz y color original de cada fila de vértices de un Geom.
def _leer_zonas(datos, archivo):
    filas = []
    grupos = {}                  # carga: el grupo depende solo del color, y hay pocos colores distintos (uno por zona)
    color, normal = GeomVertexReader(datos, "color"), GeomVertexReader(datos, "normal")
    while not color.isAtEnd():
        c, n = color.getData4(), normal.getData3()
        rgb = (c[0], c[1], c[2])
        grupo = grupos.get(rgb, grupos)
        if grupo is grupos:
            grupo = grupos[rgb] = nn.grupo_de_color(archivo, c)
        filas.append((grupo, nn.banda_luz(n), rgb))
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
    # T2 (casco_pantalla_calculos): la normal del casco pasa a ser la suavizada, por la que su shader lo empuja
    normales = GeomVertexWriter(datos, "normal") if cpc.activa() else None
    for clave, p in puntos:
        s = suma[clave]
        largo = (s[0] ** 2 + s[1] ** 2 + s[2] ** 2) ** 0.5 or 1.0
        k = nn.GROSOR_CONTORNO / largo
        escritor.setData3(p[0] + s[0] * k, p[1] + s[1] * k, p[2] + s[2] * k)
        color.setData4(*nn.COLOR_CONTORNO, 1.0)
        if normales is not None:
            normales.setData3(s[0] / largo, s[1] / largo, s[2] / largo)
    # triángulos al revés: GeomPrimitive.reverse() (en C++) da los mismos triángulos con el orden invertido, igual que
    # el bucle de antes (v0, v2, v1) salvo por la rotación del primer vértice (carga, sesión F: ~10x más rápido)
    casco = Geom(datos)
    for primitiva in origen.getPrimitives():
        casco.addPrimitive(primitiva.decompose().reverse())
    return casco


# {hueso: padre} del esqueleto de un Character (para ver si dos modelos comparten esqueleto).
def _arbol(personaje):
    arbol = {}

    def rec(grupo, padre):
        for i in range(grupo.getNumChildren()):
            hijo = grupo.getChild(i)
            if isinstance(hijo, CharacterJoint):
                arbol[hijo.getName()] = padre
                rec(hijo, hijo.getName())
            else:
                rec(hijo, padre)
    rec(personaje.node().getBundle(0), None)
    return arbol


# Carga (sesión F): los .glb v2 copian el esqueleto de su referencia (npc_hombre_0X / npc_mujer_0X: mismos huesos,
# mismos padres, reposo igual a < 1e-4), así que sus clips horneados (básicos, humanos y de postura) son los de la
# referencia: se enlazan los mismos AnimBundles en vez de hornearlos otra vez (~85 % del coste de preparar un modelo).
# Medido: diferencia máxima entre hornear el v2 y reusar la referencia < 0,05 grados y < 0,002 mm en los 40 clips
# (sesiones-24nov/blender-1/elenco-en-juego/carga/comparar_clips.py). None si no se puede (se hornea como siempre).
def _clips_de_referencia(plan, personaje):
    if not (REUSAR_CLIPS_V2 and plan.get("v2")):
        return None
    try:
        referencia = nn.datos_de(plan["archivo"]).get("referencia")
        if referencia not in nn.DATOS:
            return None
        clave_ref = referencia[:-4]
        _base({"archivo": referencia, "rol": clave_ref})    # ya preparada casi siempre (los peatones la usan)
        bancos, medidas, arbol = _clips[clave_ref]
        propio = _arbol(personaje)
        if propio != arbol:                              # mismos huesos y mismos padres (el orden puede variar)
            return None
        orden = tuple(propio.items())
        if orden != tuple(arbol.items()):
            # Panda enlaza clip y esqueleto recorriendo los dos árboles en paralelo: con los hijos en otro orden el
            # enlace sale cruzado (huesos estirados a kilómetros). Se rearman los clips en el orden del v2, con las
            # mismas tablas (una vez por referencia y orden; los v2 de un mismo kit comparten orden).
            clave = (clave_ref, orden)
            if clave not in _reordenados:
                _reordenados[clave] = [_reordenar(banco, orden) for banco in bancos]
            bancos = _reordenados[clave]
        return bancos, medidas
    except Exception:      # noqa: BLE001 — sin referencia utilizable: se hornea
        return None


# AnimBundle con las mismas tablas que `banco` pero con los canales en el orden `orden` ((hueso, padre) en recorrido en
# profundidad del esqueleto destino). Lanza si a `banco` le falta algún hueso.
def _reordenar(banco, orden):
    tablas = {}

    def rec(grupo):
        for i in range(grupo.getNumChildren()):
            canal = grupo.getChild(i)
            if isinstance(canal, AnimChannelMatrixXfmTable):
                tablas[canal.getName()] = canal
            rec(canal)
    rec(banco)
    nuevo = AnimBundle(banco.getName(), banco.getBaseFrameRate(), banco.getNumFrames())
    raiz = AnimGroup(nuevo, "<skeleton>")
    canales = {}
    for nombre, padre in orden:
        origen = tablas[nombre]
        canal = AnimChannelMatrixXfmTable(raiz if padre is None else canales[padre], nombre)
        for k in "hprxyzijkabc":
            tabla = origen.getTable(k.encode())
            if len(tabla):
                canal.setTable(k.encode(), tabla)
        canales[nombre] = canal
    return nuevo


# Deja el modelo recién cargado listo para ser la base de las copias (ver la cabecera). Lanza si no se puede.
# `plan`: si es un v2 con referencia utilizable, sus clips salen de ella (_clips_de_referencia).
def _preparar(modelo_np, archivo, clave, plan=None):
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
    reuso = _clips_de_referencia(plan or {}, personaje)
    if reuso is not None:
        bancos, medidas = reuso
        for banco in bancos:
            personaje.attachNewNode(AnimBundleNode("rig", banco))
        if medidas is not None:
            ah._cache_medidas[clave] = medidas
    else:
        npc_postura.hornear_clips_basicos(modelo_np)
        if pm.ANIMACION_HUMANA:
            ah.hornear_clips(modelo_np, clave)
            if POSTURAS:
                npc_postura.hornear_posturas(modelo_np, clave)
    _clips[clave] = ([n.node().getBundle() for n in personaje.findAllMatches("**/+AnimBundleNode")],
                     ah._cache_medidas.get(clave), _arbol(personaje))
    pesos_cabeza.unificar(modelo_np, clave)           # bug-pelo: coronilla rígida con la cabeza al mezclar clips
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
        ruta = Path(plan["ruta"]) if plan.get("ruta") else pm.CARPETA_MODELOS / plan["archivo"]
        if not ruta.is_file():
            raise FileNotFoundError(f"no existe {ruta.name}")
        if plan.get("v2"):       # elenco v2: zonas, esqueleto y escala salen del propio .glb (asset.extras.alcalde)
            nn.registrar_v2(plan["archivo"], nn.datos_v2(nn.leer_gltf(ruta)))
        modelo = NodePath(gltf.load_model(str(ruta), gltf_settings=gltf.GltfSettings()))
        zonas = _preparar(modelo, plan["archivo"], clave, plan)
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
