# Pelo y piezas fijas del rostro deformados por el MISMO hueso y en el MISMO paso que el cráneo (skinning), en vez de
# colgados de un nodo de exposeJoint.
#
# Por qué (rework 3D, fase 1b; rework-3d/bug-pelo/informe.md): con «threading-model Cull/Draw» (frontend/rendimiento.py,
# HILOS_DE_DIBUJO) el cull y el dibujo van en hilos propios. El nodo de exposeJoint (del que colgaba el rostro) viaja por
# el pipeline con el cuadro N, pero el skinning por GPU (frontend/skinning_gpu.py) lee las matrices de hueso VIVAS en el
# hilo de dibujo, que el cull del cuadro N+1 ya puede haber reescrito. El pelo y el cráneo se dibujaban en cuadros
# distintos: al correr, saltar o subir escaleras el pelo se quedaba unos centímetros atrás y asomaba la calva.
# Arreglo: las dos mallas fijas del rostro (la fusionada «estaticas», con el pelo, nariz, orejas, barba, gafas..., y su
# casco de tinta «contorno») pasan a ser geometría ANIMADA del personaje, con peso 1 en el hueso de la cabeza: Panda
# las deforma con la misma matriz y en la misma llamada que la piel (GPU o CPU), así que nunca se separan.
# Las piezas con animación facial (ojos, párpados, cejas, boca) siguen colgadas del hueso como antes.
#
# Mismo aspecto: mismos vértices, colores, bins, caras, sin luz ni textura; el shader es el unlit de skinning_gpu (copia
# exacta del unlit de Ursina, el que ya pintaba estas piezas), con prioridad por encima de los que el Actor pone después.
# Bandera: ROSTRO_SKINNING o ALCALDE_ROSTRO_SKINNING=0/1 (0 = colgado de exposeJoint, como antes).
# skinear() NUNCA lanza: si algo falla avisa una vez y el rostro queda colgado del hueso como siempre.

import os
import sys

from panda3d.core import (BoundingSphere, Geom, GeomNode, GeomVertexAnimationSpec, GeomVertexArrayFormat, GeomVertexData,
                          GeomVertexFormat, InternalName, LPoint3, LVecBase2f, Mat4, SparseArray, TransformBlend,
                          TransformBlendTable)

ROSTRO_SKINNING = True
PRIORIDAD_SHADER = 20            # por encima de skinning_gpu/toon_duro (10), que el Actor aplica después
CENTRO_LIMITES = (0.0, -0.02, 0.15)   # centro de la cabeza en el marco del rostro (ejes del glb, metros)
RADIO_LIMITES = 0.75             # m (sin escala del Actor): cabeza + todo lo que se aleja del reposo al correr, saltar o agacharse
NOMBRES = ("estaticas", "contorno")

_avisados = set()


def activa():
    valor = os.environ.get("ALCALDE_ROSTRO_SKINNING", "").strip().lower()
    if valor in ("1", "true", "si", "sí", "on"):
        return True
    if valor in ("0", "false", "no", "off"):
        return False
    return bool(ROSTRO_SKINNING)


def _avisar(rol, motivo):
    if rol not in _avisados:
        _avisados.add(rol)
        print(f"[assets] {rol}: el rostro sigue colgado del hueso ({motivo}).", file=sys.stderr)


def _transformacion_cabeza(actor, hueso):
    # (JointVertexTransform del hueso, NodePath del GeomNode de piel que lo usa). Se reutiliza la transformación que ya
    # usa la piel: misma matriz, mismo índice en la tabla de huesos de la GPU.
    for camino in actor.findAllMatches("**/+GeomNode"):
        nodo = camino.node()
        for i in range(nodo.getNumGeoms()):
            tabla = nodo.getGeom(i).getVertexData().getTransformBlendTable()
            if tabla is None:
                continue
            for b in range(tabla.getNumBlends()):
                blend = tabla.getBlend(b)
                for k in range(blend.getNumTransforms()):
                    t = blend.getTransform(k)
                    junta = getattr(t, "getJoint", None)
                    if junta is not None and junta().getName() == hueso:
                        return t, camino
    return None, None


def _formato_animado(formato):
    nuevo = GeomVertexFormat(formato)
    arreglo = GeomVertexArrayFormat()
    arreglo.addColumn(InternalName.getTransformBlend(), 1, Geom.NT_uint16, Geom.C_index)
    nuevo.addArray(arreglo)
    spec = GeomVertexAnimationSpec()
    spec.setPanda()
    nuevo.setAnimation(spec)
    return GeomVertexFormat.registerFormat(nuevo)


def _geom_animada(geom, matriz, transformacion):
    # Copia de `geom` con los vértices llevados a `matriz` (espacio de la piel, en reposo) y todos en la mezcla 0 (peso
    # 1 en `transformacion`). Cada GeomVertexData lleva SU tabla con SUS filas: Panda anima las filas que dice la
    # tabla, y una tabla con más filas que los datos escribiría fuera de ellos.
    datos = geom.getVertexData()
    datos = GeomVertexData(datos.convertTo(_formato_animado(datos.getFormat())))   # columna nueva en 0: mezcla 0
    datos.transformVertices(matriz)
    tabla = TransformBlendTable()
    tabla.addBlend(TransformBlend(transformacion, 1.0))
    tabla.setRows(SparseArray.lowerOn(datos.getNumRows()))
    datos.setTransformBlendTable(tabla)
    copia = geom.makeCopy()
    copia.setVertexData(datos)
    return copia


def skinear(actor, raiz, rol, hueso, matriz_raiz):
    """Pasa las piezas fijas del rostro `raiz` (ya colgado del hueso) a geometría animada del Actor.
    `matriz_raiz`: posición de `raiz` respecto al Actor en reposo (la de rostro_modelo._matriz_cabeza).
    Devuelve cuántos nodos pasó (0 = como antes)."""
    if not activa() or actor is None or raiz is None:
        return 0
    try:
        if raiz.isEmpty():
            return 0
        transformacion, piel = _transformacion_cabeza(actor, hueso)
        if transformacion is None:
            return 0
        a_piel = Mat4(piel.getMat(actor))                 # piel -> Actor (fijo: el GeomNode de la piel no se anima)
        a_piel.invertInPlace()
        from frontend import skinning_gpu
        atributo = skinning_gpu.atributo_unlit() if skinning_gpu.activo() else None
        estado_raiz = raiz.getState()
        # Volumen FIJO alrededor de la cabeza en reposo: sin él Panda recalcula los límites de la malla animada cada vez
        # que el personaje se mueve (lo piden los raycasts del hilo principal): medido +0,25 ms por cuadro con 13 personajes.
        centro = (Mat4(matriz_raiz) * a_piel).xformPoint(LPoint3(*CENTRO_LIMITES))
        hechos = []
        for nombre in NOMBRES:                            # 1) se arma todo sin tocar el rostro
            viejo = raiz.find(nombre)
            if viejo.isEmpty():
                continue
            matriz = Mat4(viejo.getMat(raiz)) * Mat4(matriz_raiz) * a_piel   # pieza -> piel, en reposo
            nodo_viejo = viejo.node()
            nodo = GeomNode(nombre)
            nodo.setBounds(BoundingSphere(centro, RADIO_LIMITES))
            for i in range(nodo_viejo.getNumGeoms()):
                nodo.addGeom(_geom_animada(nodo_viejo.getGeom(i), matriz, transformacion), nodo_viejo.getGeomState(i))
            hechos.append((viejo, nodo, estado_raiz.compose(viejo.getState())))
        if not hechos:
            return 0
        # 2) y luego se cambia (nada aquí debería fallar). El shader va en un nodo PADRE con prioridad 20: skinning_gpu.aplicar
        # y toon_duro.aplicar_actor, que el Actor llama después, ponen el suyo (prioridad 10) en cada GeomNode animado, y
        # el del padre con más prioridad sigue mandando (el pelo no gana bandas de toon que antes no tenía).
        contenedor = piel.getParent().attachNewNode("rostro_skinning")
        contenedor.setMat(piel.getMat())                    # mismo espacio que la piel
        if atributo is not None:
            # las entradas van DENTRO del atributo: NodePath.setShaderInput lo rehace con prioridad 0 y perdería el 20
            atributo = (atributo.setShaderInput("texture_scale", LVecBase2f(1.0, 1.0))
                        .setShaderInput("texture_offset", LVecBase2f(0.0, 0.0)))
            contenedor.setAttrib(atributo, PRIORIDAD_SHADER)
        for viejo, nodo, estado in hechos:
            nuevo = contenedor.attachNewNode(nodo)
            nuevo.setState(estado)
            viejo.removeNode()
        return len(hechos)
    except Exception as error:      # noqa: BLE001 — colgado del hueso se ve como siempre (con el bug de los hilos)
        _avisar(rol, f"{type(error).__name__}: {error}")
        return 0


# --- Pelo DENTRO de la llamada de dibujo del cráneo (corrección tras el verificador: giros) ---
# Con el pelo en su propia malla animada aún eran DOS llamadas de dibujo (la piel en el bin opaco y el pelo en el bin
# «fixed», al final del cuadro), y cada una sube las matrices de hueso que lee en ese momento. Con los hilos de dibujo,
# el cull del cuadro siguiente puede actualizar el esqueleto ENTRE las dos: en los giros bruscos (la pose cambia mucho de
# un cuadro a otro) el pelo salía con la pose de otro cuadro y asomaba la coronilla. fusionar_con_piel() añade los
# triángulos del pelo como una primitiva más del MISMO Geom de la piel de la cabeza (y los del casco del pelo al Geom del
# casco del cuerpo): un Geom se prepara una sola vez por dibujo, así que pelo y cráneo usan exactamente las mismas matrices.
# Solo con el shader sin luz (protagonistas y NPC copia): con toon o toon duro el pelo cogería sus bandas, así que ahí
# se queda como malla aparte. Bandera: PELO_EN_PIEL o ALCALDE_PELO_EN_PIEL=0/1 (0 = malla aparte, como antes).
# Nunca lanza: si algo falla, el pelo sigue en su malla animada.

PELO_EN_PIEL = True


def fusion_activa():
    valor = os.environ.get("ALCALDE_PELO_EN_PIEL", "").strip().lower()
    if valor in ("1", "true", "si", "sí", "on"):
        return True
    if valor in ("0", "false", "no", "off"):
        return False
    return bool(PELO_EN_PIEL)


def _es_casco(estado):
    from panda3d.core import MaterialAttrib
    atributo = estado.getAttrib(MaterialAttrib)
    material = None if atributo is None else atributo.getMaterial()
    return material is not None and material.getName() == "Contorno"


def _hueso_de(datos):
    t = datos.getTransformBlendTable().getBlend(0).getTransform(0)
    return t.getJoint().getName()


def _cuenta_cabeza(tabla, nombre_hueso):
    cuenta = 0
    for b in range(tabla.getNumBlends()):
        blend = tabla.getBlend(b)
        for k in range(blend.getNumTransforms()):
            t = blend.getTransform(k)
            if getattr(t, "getJoint", None) is not None and t.getJoint().getName() == nombre_hueso \
                    and blend.getWeight(k) > 0.5:
                cuenta += 1
    return cuenta


def _destino(actor, contenedor, nombre_hueso, casco):
    # (NodePath del GeomNode, índice) de la malla de piel (o del casco) con más mezclas dominadas por la cabeza.
    mejor, cuenta_mejor = None, 0
    for camino in actor.findAllMatches("**/+GeomNode"):
        if camino.getParent() == contenedor:
            continue
        nodo = camino.node()
        for i in range(nodo.getNumGeoms()):
            tabla = nodo.getGeom(i).getVertexData().getTransformBlendTable()
            if tabla is None or _es_casco(nodo.getGeomState(i)) != casco:
                continue
            cuenta = _cuenta_cabeza(tabla, nombre_hueso)
            if cuenta > cuenta_mejor:
                mejor, cuenta_mejor = (camino, i), cuenta
    return mejor


def _fusionar(piel_np, i, pelo_np, nombre_hueso):
    from panda3d.core import GeomVertexReader, GeomVertexWriter, Thread
    hilo = Thread.getCurrentThread()
    nodo = piel_np.node()
    geom = nodo.getGeom(i)
    datos = geom.getVertexData()
    formato = datos.getFormat()
    tabla = TransformBlendTable(datos.getTransformBlendTable())
    cabeza, ref_blend = None, None          # la transformación de la cabeza de ESTA malla y una mezcla 100 % cabeza
    for b in range(tabla.getNumBlends()):
        blend = tabla.getBlend(b)
        for k in range(blend.getNumTransforms()):
            t = blend.getTransform(k)
            if getattr(t, "getJoint", None) is not None and t.getJoint().getName() == nombre_hueso:
                cabeza = t
                if blend.getNumTransforms() == 1 and ref_blend is None:
                    ref_blend = b
    if cabeza is None:
        return False
    indice = tabla.addBlend(TransformBlend(cabeza, 1.0))
    ref = None                              # fila de referencia para las columnas transform_index/weight del .glb
    if formato.hasColumn("transform_index"):
        if ref_blend is None:
            return False
        lector = GeomVertexReader(datos, "transform_blend")
        fila = 0
        while not lector.isAtEnd():
            if lector.getData1i() == ref_blend:
                ref = fila
                break
            fila += 1
        if ref is None:
            return False
    nuevos = GeomVertexData(datos)
    n0 = nuevos.getNumRows()
    a_piel = Mat4(pelo_np.getMat(piel_np))
    primitivas = []
    nodo_pelo = pelo_np.node()
    for g in range(nodo_pelo.getNumGeoms()):
        pelo = GeomVertexData(nodo_pelo.getGeom(g).getVertexData().convertTo(formato))
        pelo.transformVertices(a_piel)
        base = nuevos.getNumRows()
        nuevos.setNumRows(base + pelo.getNumRows())
        for r in range(pelo.getNumRows()):
            nuevos.copyRowFrom(base + r, pelo, r, hilo)
        for prim in nodo_pelo.getGeom(g).getPrimitives():
            p = prim.decompose().makeCopy()
            p.setIndexType(Geom.NT_uint32)
            p.offsetVertices(base)
            primitivas.append(p)
    total = nuevos.getNumRows()
    escritor = GeomVertexWriter(nuevos, "transform_blend")
    escritor.setRow(n0)
    for _ in range(total - n0):
        escritor.setData1i(indice)
    if ref is not None:
        idx_ref, peso_ref = GeomVertexReader(datos, "transform_index"), GeomVertexReader(datos, "transform_weight")
        idx_ref.setRow(ref)
        peso_ref.setRow(ref)
        vi, vw = idx_ref.getData4i(), peso_ref.getData4()
        wi, ww = GeomVertexWriter(nuevos, "transform_index"), GeomVertexWriter(nuevos, "transform_weight")
        wi.setRow(n0)
        ww.setRow(n0)
        for _ in range(total - n0):
            wi.setData4i(vi)
            ww.setData4(vw)
    tabla.setRows(SparseArray.lowerOn(total))
    nuevos.setTransformBlendTable(tabla)
    nuevo_geom = geom.makeCopy()
    nuevo_geom.setVertexData(nuevos)
    for p in primitivas:
        nuevo_geom.addPrimitive(p)
    nodo.setGeom(i, nuevo_geom)
    return True


def fusionar_con_piel(actor, rol=""):
    """Mete el pelo («estaticas») en el Geom de la piel de la cabeza y su casco («contorno») en el del casco del cuerpo.
    Llamar con los shaders del Actor ya puestos y solo si son los sin luz. Devuelve cuántas mallas fusionó."""
    if not activa() or not fusion_activa() or actor is None:
        return 0
    try:
        contenedor = actor.find("**/rostro_skinning")
        if contenedor.isEmpty():
            return 0
        planes = []                                       # 1) todo decidido antes de tocar nada
        for nombre, casco in (("estaticas", False), ("contorno", True)):
            pelo = contenedor.find(nombre)
            if pelo.isEmpty():
                continue
            hueso = _hueso_de(pelo.node().getGeom(0).getVertexData())
            destino = _destino(actor, contenedor, hueso, casco)
            if destino is not None:
                planes.append((pelo, destino, hueso))
        hechos = 0
        for pelo, (piel_np, i), hueso in planes:          # 2) cada fusión cambia el Geom de golpe (setGeom)
            if _fusionar(piel_np, i, pelo, hueso):
                pelo.removeNode()
                hechos += 1
        if contenedor.getNumChildren() == 0:
            contenedor.removeNode()
        return hechos
    except Exception as error:      # noqa: BLE001 — el pelo sigue en su malla animada (mismo aspecto)
        _avisar(rol, f"fusión con la piel: {type(error).__name__}: {error}")
        return 0
