# Pasa al hueso de la cabeza los pesos de los huesos faciales RAÍZ de un .glb recién cargado (antes de crear el Actor).
# Por qué y cómo: frontend/pesos_cabeza_calculos.py. Bandera: ALCALDE_PESOS_CABEZA=0 deja los pesos del .glb tal cual.
#
# Se reescribe solo la TransformBlendTable de cada GeomVertexData animada (los índices de mezcla de cada vértice no
# cambian): misma geometría, mismos huesos, y la copia del Actor (Actor(base)) hereda la tabla ya corregida.
# unificar() NUNCA lanza: ante cualquier fallo avisa una vez y el modelo queda como estaba.

import sys

from panda3d.core import CharacterJoint, JointVertexTransform, TransformBlend, TransformBlendTable

from frontend import animacion_humana as ah
from frontend import pesos_cabeza_calculos as pcc

_avisados = set()


def _avisar(rol, motivo):
    if rol not in _avisados:
        _avisados.add(rol)
        print(f"[assets] {rol}: no se pudieron unir los pesos de la cabeza ({motivo}); se usan los del .glb.",
              file=sys.stderr)


def _juntas(grupo, padre, salida):
    # nombre -> (CharacterJoint, nombre del hueso padre o None si es raíz)
    for i in range(grupo.getNumChildren()):
        hijo = grupo.getChild(i)
        if isinstance(hijo, CharacterJoint):
            salida[hijo.getName()] = (hijo, padre)
            _juntas(hijo, hijo.getName(), salida)
        else:
            _juntas(hijo, padre, salida)


def _nombre(transformacion):
    junta = getattr(transformacion, "getJoint", None)
    return junta().getName() if junta is not None else None


def _tabla_unificada(tabla, a_cabeza, cabeza, t_cabeza):
    # (tabla nueva, nº de mezclas cambiadas); (None, 0) si no hay nada que cambiar.
    for b in range(tabla.getNumBlends()):            # si la tabla ya trae la cabeza, se reutiliza esa transformación
        blend = tabla.getBlend(b)
        for k in range(blend.getNumTransforms()):
            if _nombre(blend.getTransform(k)) == cabeza:
                t_cabeza = blend.getTransform(k)
                break
        else:
            continue
        break
    nueva, cambiadas = None, 0
    for b in range(tabla.getNumBlends()):
        blend = tabla.getBlend(b)
        entradas = [(blend.getTransform(k), blend.getWeight(k)) for k in range(blend.getNumTransforms())]
        pesos = [(_nombre(t), w) for t, w in entradas]
        fusion = pcc.fusionar(pesos, a_cabeza, cabeza)
        if fusion is pesos:
            continue
        por_nombre = {n: t for (t, _), (n, _) in zip(entradas, pesos)}
        nuevo = TransformBlend()
        for n, w in fusion:
            nuevo.addTransform(t_cabeza if n == cabeza else por_nombre[n], w)
        if nueva is None:
            nueva = TransformBlendTable(tabla)
        nueva.setBlend(b, nuevo)
        cambiadas += 1
    return nueva, cambiadas


def unificar(modelo_np, rol=""):
    """Corrige los pesos del modelo (NodePath de gltf.load_model, antes del Actor). Devuelve cuántas mezclas cambió."""
    if not pcc.activa() or modelo_np is None:
        return 0
    try:
        personaje = modelo_np.find("**/+Character")
        if personaje.isEmpty():
            return 0
        juntas = {}
        for i in range(personaje.node().getNumBundles()):
            _juntas(personaje.node().getBundle(i), None, juntas)
        tipo = ah._tipo_esqueleto(set(juntas))
        if tipo is None:
            return 0
        cabeza = tipo["zonas"]["cabeza"][0]
        if cabeza not in juntas:
            return 0
        zonas = {h for huesos in tipo["zonas"].values() for h in huesos}
        explicitos = {plantilla % lado for plantilla in tipo["miembro"].values() for lado in "LR"}
        raices = [n for n, (_, padre) in juntas.items() if padre is None]
        a_cabeza = pcc.huesos_a_cabeza(raices, zonas, explicitos)
        if not a_cabeza:
            return 0
        t_cabeza = JointVertexTransform(juntas[cabeza][0])
        hechas = {}                                   # tabla original -> nueva (datos compartidos entre geoms)
        cambiadas = 0
        for camino in modelo_np.findAllMatches("**/+GeomNode"):
            nodo = camino.node()
            for i in range(nodo.getNumGeoms()):
                tabla = nodo.getGeom(i).getVertexData().getTransformBlendTable()
                if tabla is None:
                    continue
                clave = id(tabla)
                if clave not in hechas:
                    nueva, n = _tabla_unificada(tabla, a_cabeza, cabeza, t_cabeza)
                    hechas[clave] = (tabla, nueva)          # se guarda `tabla` para que id() no se reutilice
                    cambiadas += n
                nueva = hechas[clave][1]
                if nueva is not None:
                    nodo.modifyGeom(i).modifyVertexData().setTransformBlendTable(nueva)
        return cambiadas
    except Exception as error:      # noqa: BLE001 — los pesos del .glb siguen sirviendo (con el bug de siempre)
        _avisar(rol, f"{type(error).__name__}: {error}")
        return 0
