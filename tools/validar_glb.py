"""Validador de los .glb de personajes (fase Blender, contrato §2). Puro: solo json/struct/math (sin bpy ni ursina).

Uso:
    python tools/validar_glb.py <modelo.glb> [--esqueleto hombre|mujer|prota:<rol>] [--referencia <ref.glb>] [--json]

Código de salida 0 = válido (sin errores; los avisos no cuentan), 1 = con errores, 2 = no se pudo leer.

Qué comprueba (errores):
  - glTF 2.0 binario legible; sin Draco ni extensiones (`extensionsUsed`/`extensionsRequired` vacíos).
  - Huesos por primitiva <= 128: joints con peso > 0 en cada primitiva. Es lo que limita el skinning por GPU:
    panda3d-gltf hace un Geom (con su GeomVertexData y su TransformBlendTable) por primitiva, y el shader
    (frontend/skinning_gpu.py, p3d_TransformTable[MAX_HUESOS = 128]) indexa esa tabla; su tamaño es el número de
    joints distintos con peso > 0 en la primitiva (medido: 99 en npc_hombre_0X y en el cuerpo del ciudadano, el
    «hoy 99»). El tamaño de la skin (160 en el Rigify) NO limita: se informa.
  - Materiales <= 2.
  - Pies en y = 0 (tolerancia 1 cm), medidos en pose de reposo con la skin aplicada (matriz del nodo incluida).
    Con prota:<rol>, los pies se comparan con los de la referencia (± 1 cm): el smoking de hoy los tiene a -0,019 m.
  - asset.extras.alcalde con `autor`, `licencia` y `zonas` (lista de [[r, g, b] en 0-1, grupo]); cada color de
    zona tiene que existir en el COLOR_0 (tolerancia 2/255).
  - Con --esqueleto: mismos nombres de joints y mismos padres que el .glb de referencia (con prota:<rol>, un joint
    que en la referencia era raíz puede colgar de otro joint de la skin: se avisa, no falla); animaciones: ninguna para
    hombre/mujer (NPC v2: los clips los pone el código), los 5 clips (Idle, Caminar, Correr, Saludar, Hablar) para
    los protagonistas.
Avisos (no fallan): triángulos fuera de 2000-4000 en un NPC, altura fuera de ±3 % de la referencia, colores del
COLOR_0 sin zona, primitivas sin COLOR_0, unión de huesos de una malla > 128.
"""

import argparse
import json
import math
import struct
import sys
from pathlib import Path

MAX_HUESOS = 128                       # frontend/skinning_gpu.py: p3d_TransformTable[MAX_HUESOS]
MAX_MATERIALES = 2
TOL_PIES = 0.01                        # m
TOL_ALTURA_REF = 0.03                  # ±3 % de la referencia (aviso)
TOL_COLOR = 2.0 / 255.0
TRIANGULOS_NPC = (2000, 4000)          # contrato §4 (aviso)
CLIPS_PROTAGONISTA = ("Idle", "Caminar", "Correr", "Saludar", "Hablar")
CARPETA_PERSONAJES = Path(__file__).resolve().parent.parent / "assets" / "modelos" / "personajes"
REFERENCIAS = {
    "hombre": "npc_hombre_02.glb",
    "mujer": "npc_mujer_01.glb",
    "prota:ciudadano": "ciudadano.glb",
    "prota:periodista": "periodista.glb",
    "prota:candidato": "smoking.glb",
    "prota:smoking": "smoking.glb",
    "prota:influencer": "brasilena.glb",
    "prota:brasilena": "brasilena.glb",
}

_MAGIC, _JSON, _BIN = 0x46546C67, 0x4E4F534A, 0x004E4942
_COMP = {5120: ("b", 1, 127.0), 5121: ("B", 1, 255.0), 5122: ("h", 2, 32767.0), 5123: ("H", 2, 65535.0),
         5125: ("I", 4, None), 5126: ("f", 4, None)}
_N = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT2": 4, "MAT3": 9, "MAT4": 16}


# ---------------------------------------------------------------- lectura
def leer_glb(ruta_o_bytes):
    """(json, bin) de un .glb. Lanza ValueError si no es un GLB válido."""
    datos = ruta_o_bytes if isinstance(ruta_o_bytes, (bytes, bytearray)) else Path(ruta_o_bytes).read_bytes()
    if len(datos) < 20:
        raise ValueError("archivo demasiado corto para ser un .glb")
    magic, version, largo = struct.unpack_from("<III", datos, 0)
    if magic != _MAGIC:
        raise ValueError("no es un .glb (magic incorrecto)")
    if version != 2:
        raise ValueError(f"versión de contenedor {version} (se espera 2)")
    if largo > len(datos):
        raise ValueError(f"truncado: la cabecera dice {largo} bytes y hay {len(datos)}")
    pos, gltf, binario = 12, None, b""
    while pos + 8 <= largo:
        n, tipo = struct.unpack_from("<II", datos, pos)
        cuerpo = datos[pos + 8:pos + 8 + n]
        if len(cuerpo) != n:
            raise ValueError("chunk truncado")
        if gltf is None:
            if tipo != _JSON:
                raise ValueError("el primer chunk no es JSON")
            gltf = json.loads(bytes(cuerpo).decode("utf-8"))
        elif tipo == _BIN and not binario:
            binario = bytes(cuerpo)
        pos += 8 + n
    if gltf is None:
        raise ValueError("sin chunk JSON")
    return gltf, binario


def leer_accesor(gltf, binario, indice):
    acc = gltf["accessors"][indice]
    fmt, tam, maximo = _COMP[acc["componentType"]]
    n = _N[acc["type"]]
    if "bufferView" not in acc:
        return [(0,) * n] * acc["count"]
    vista = gltf["bufferViews"][acc["bufferView"]]
    inicio = vista.get("byteOffset", 0) + acc.get("byteOffset", 0)
    paso = vista.get("byteStride") or tam * n
    st = struct.Struct("<" + fmt * n)
    filas = [st.unpack_from(binario, inicio + i * paso) for i in range(acc["count"])]
    if acc.get("normalized") and maximo:
        filas = [tuple(max(v / maximo, -1.0) for v in f) for f in filas]
    return filas


# ---------------------------------------------------------------- matrices 4x4 (listas de filas)
def _mul(a, b):
    return [[sum(a[i][k] * b[k][j] for k in range(4)) for j in range(4)] for i in range(4)]


def _trs(nodo):
    if "matrix" in nodo:
        m = nodo["matrix"]                       # column-major
        return [[m[c * 4 + r] for c in range(4)] for r in range(4)]
    tx, ty, tz = nodo.get("translation", (0.0, 0.0, 0.0))
    x, y, z, w = nodo.get("rotation", (0.0, 0.0, 0.0, 1.0))
    sx, sy, sz = nodo.get("scale", (1.0, 1.0, 1.0))
    r = [[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
         [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
         [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]]
    return [[r[0][0] * sx, r[0][1] * sy, r[0][2] * sz, tx],
            [r[1][0] * sx, r[1][1] * sy, r[1][2] * sz, ty],
            [r[2][0] * sx, r[2][1] * sy, r[2][2] * sz, tz],
            [0.0, 0.0, 0.0, 1.0]]


def _punto(m, p):
    return tuple(m[i][0] * p[0] + m[i][1] * p[1] + m[i][2] * p[2] + m[i][3] for i in range(3))


def _padres(gltf):
    return {c: i for i, nd in enumerate(gltf.get("nodes", [])) for c in nd.get("children", [])}


def _mundos(gltf):
    padres, nodos, cache = _padres(gltf), gltf.get("nodes", []), {}

    def mundo(i):
        if i not in cache:
            local = _trs(nodos[i])
            cache[i] = _mul(mundo(padres[i]), local) if i in padres else local
        return cache[i]
    return [mundo(i) for i in range(len(nodos))]


# ---------------------------------------------------------------- medidas
def _pesos_normalizados(w):
    total = sum(abs(x) for x in w)
    return tuple(x / total for x in w) if total else tuple(w)


def huesos_por_primitiva(gltf, binario):
    """[{malla, primitiva, huesos: set(índices de joint con peso > 0)}] (como la TransformBlendTable de Panda)."""
    salida = []
    for mi, malla in enumerate(gltf.get("meshes", [])):
        for pi, prim in enumerate(malla.get("primitives", [])):
            atr = prim.get("attributes", {})
            usados = set()
            k = 0
            while f"JOINTS_{k}" in atr and f"WEIGHTS_{k}" in atr:
                js = leer_accesor(gltf, binario, atr[f"JOINTS_{k}"])
                ws = leer_accesor(gltf, binario, atr[f"WEIGHTS_{k}"])
                for j, w in zip(js, ws):             # normalizar no cambia qué pesos son 0
                    for ji, wi in zip(j, w):
                        if wi > 0.0:
                            usados.add(int(ji))
                k += 1
            salida.append({"malla": malla.get("name", f"malla{mi}"), "indice_malla": mi, "primitiva": pi,
                           "huesos": usados})
    return salida


def triangulos(gltf):
    total, por_malla = 0, {}
    for mi, malla in enumerate(gltf.get("meshes", [])):
        n = 0
        for prim in malla.get("primitives", []):
            modo = prim.get("mode", 4)
            if "indices" in prim:
                c = gltf["accessors"][prim["indices"]]["count"]
            else:
                c = gltf["accessors"][prim["attributes"]["POSITION"]]["count"]
            n += c // 3 if modo == 4 else max(c - 2, 0) if modo in (5, 6) else 0
        por_malla[malla.get("name", f"malla{mi}")] = por_malla.get(malla.get("name", f"malla{mi}"), 0) + n
        total += n
    return total, por_malla


def posiciones_reposo(gltf, binario):
    """Vértices en el mundo, pose de reposo, con la skin aplicada (sum w * mundo(joint) * IBM * v)."""
    mundos = _mundos(gltf)
    puntos = []
    for ni, nodo in enumerate(gltf.get("nodes", [])):
        if "mesh" not in nodo:
            continue
        skin = gltf["skins"][nodo["skin"]] if "skin" in nodo and gltf.get("skins") else None
        mats = None
        if skin is not None:
            if "inverseBindMatrices" in skin:
                ibm = [[[f[c * 4 + r] for c in range(4)] for r in range(4)]
                       for f in leer_accesor(gltf, binario, skin["inverseBindMatrices"])]
            else:
                ibm = [[[1.0 if r == c else 0.0 for c in range(4)] for r in range(4)] for _ in skin["joints"]]
            mats = [_mul(mundos[j], ibm[k]) for k, j in enumerate(skin["joints"])]
        for prim in gltf["meshes"][nodo["mesh"]].get("primitives", []):
            atr = prim["attributes"]
            pos = leer_accesor(gltf, binario, atr["POSITION"])
            if mats is None or "JOINTS_0" not in atr:
                puntos.extend(_punto(mundos[ni], p) for p in pos)
                continue
            js = leer_accesor(gltf, binario, atr["JOINTS_0"])
            ws = leer_accesor(gltf, binario, atr["WEIGHTS_0"])
            for p, j, w in zip(pos, js, ws):
                w = _pesos_normalizados(w)
                acc = [0.0, 0.0, 0.0]
                for ji, wi in zip(j, w):
                    if wi:
                        q = _punto(mats[int(ji)], p)
                        acc[0] += wi * q[0]; acc[1] += wi * q[1]; acc[2] += wi * q[2]
                puntos.append(tuple(acc))
    return puntos


def colores(gltf, binario):
    """Colores distintos del COLOR_0 (rgb 0-1, 4 decimales) y primitivas sin COLOR_0."""
    vistos, sin_color = set(), []
    for mi, malla in enumerate(gltf.get("meshes", [])):
        for pi, prim in enumerate(malla.get("primitives", [])):
            i = prim.get("attributes", {}).get("COLOR_0")
            if i is None:
                sin_color.append(f"{malla.get('name', mi)}[{pi}]")
                continue
            for c in leer_accesor(gltf, binario, i):
                vistos.add(tuple(round(float(x), 4) for x in c[:3]))
    return sorted(vistos), sin_color


def esqueleto(gltf):
    """{nombre del joint: nombre del padre o None}, nombres en orden de la skin, y el nodo del esqueleto."""
    if not gltf.get("skins"):
        return {}, [], None
    nodos, padres = gltf["nodes"], _padres(gltf)
    joints = gltf["skins"][0]["joints"]
    conj = set(joints)
    nombres = [nodos[j].get("name", f"nodo{j}") for j in joints]
    padre = {nodos[j].get("name", f"nodo{j}"): (nodos[padres[j]].get("name") if padres.get(j) in conj else None)
             for j in joints}
    raiz = None
    for j in joints:
        p = padres.get(j)
        if p is not None and p not in conj:
            raiz = p
            break
    return padre, nombres, raiz


def _frente(gltf, puntos, altura, pies):
    """+1 si el personaje mira a +z, -1 si a -z, 0 si no se sabe. Por el esqueleto (reposo): el joint del dedo del
    pie (`toe`) queda delante del joint del pie (`foot`; vale para el Rigify DEF-* y para Hips/.../toe.L). Sin esos
    joints, por la geometría: la punta del pie sobresale hacia adelante más que el talón hacia atrás."""
    if gltf.get("skins"):
        nodos, padres, mundos = gltf["nodes"], _padres(gltf), _mundos(gltf)
        dz = 0.0
        for j in gltf["skins"][0]["joints"]:
            p = padres.get(j)
            if p is not None and "toe" in nodos[j].get("name", "").lower() and "foot" in nodos[p].get("name", "").lower():
                dz += mundos[j][2][3] - mundos[p][2][3]
        if abs(dz) > 1e-4:
            return 1 if dz > 0 else -1
    bajos = [p[2] for p in puntos if p[1] < pies + 0.04 * altura]
    piernas = [p[2] for p in puntos if pies + 0.15 * altura < p[1] < pies + 0.45 * altura]
    if not bajos or not piernas:
        return 0
    d = (max(bajos) - max(piernas)) - (min(piernas) - min(bajos))
    return 0 if abs(d) < 1e-3 else (1 if d > 0 else -1)


# ---------------------------------------------------------------- validación
def _clave_referencia(esqueleto_arg):
    if esqueleto_arg is None:
        return None
    clave = esqueleto_arg.strip().lower()
    if clave not in REFERENCIAS:
        raise ValueError(f"--esqueleto desconocido: {esqueleto_arg!r} (use hombre, mujer o prota:<rol>; roles: "
                         "ciudadano, periodista, candidato, influencer)")
    return clave


def medir(ruta_o_bytes):
    gltf, binario = leer_glb(ruta_o_bytes)
    tri, tri_malla = triangulos(gltf)
    prims = huesos_por_primitiva(gltf, binario)
    union = {}
    for p in prims:
        union.setdefault(p["malla"], set()).update(p["huesos"])
    puntos = posiciones_reposo(gltf, binario)
    ys = [p[1] for p in puntos] or [0.0]
    altura, pies = max(ys) - min(ys), min(ys)
    padre, nombres, raiz = esqueleto(gltf)
    nodo_esq = gltf["nodes"][raiz] if raiz is not None else None
    cols, sin_color = colores(gltf, binario)
    mats = gltf.get("materials", [])
    return {
        "gltf": gltf,
        "triangulos": tri,
        "triangulos_por_malla": tri_malla,
        "skin_joints": len(nombres),
        "huesos_por_primitiva": [{"malla": p["malla"], "primitiva": p["primitiva"], "huesos": len(p["huesos"])}
                                 for p in prims],
        "huesos_max_primitiva": max((len(p["huesos"]) for p in prims), default=0),
        "huesos_union_por_malla": {k: len(v) for k, v in union.items()},
        "materiales": [m.get("name", f"material{i}") for i, m in enumerate(mats)],
        "altura": round(altura, 4),
        "pies_y": round(pies, 4),
        "frente_z": _frente(gltf, puntos, altura, pies) if puntos else 0,
        "nodo_esqueleto": None if nodo_esq is None else {
            "nombre": nodo_esq.get("name"), "escala": nodo_esq.get("scale", [1.0, 1.0, 1.0]),
            "traslacion": nodo_esq.get("translation", [0.0, 0.0, 0.0])},
        "joints_padre": padre,
        "animaciones": [a.get("name", f"anim{i}") for i, a in enumerate(gltf.get("animations", []))],
        "extensiones": sorted(set(gltf.get("extensionsUsed", [])) | set(gltf.get("extensionsRequired", []))),
        "colores": cols,
        "primitivas_sin_color": sin_color,
        "extras_alcalde": (gltf.get("asset", {}).get("extras") or {}).get("alcalde"),
        "generador": gltf.get("asset", {}).get("generator"),
    }


def _validar_extras(extras, cols, errores, avisos):
    if not isinstance(extras, dict):
        errores.append("falta asset.extras.alcalde (autor, licencia, zonas): inyectar con alcalde_blender.escribir_extras")
        return
    for k in ("autor", "licencia"):
        if not isinstance(extras.get(k), str) or not extras.get(k).strip():
            errores.append(f"asset.extras.alcalde.{k} falta o está vacío")
    zonas = extras.get("zonas")
    if not isinstance(zonas, list) or not zonas:
        errores.append("asset.extras.alcalde.zonas falta o está vacía (lista de [[r, g, b], grupo])")
        return
    cubiertos = set()
    for i, z in enumerate(zonas):
        ok = (isinstance(z, (list, tuple)) and len(z) == 2 and isinstance(z[1], str) and z[1]
              and isinstance(z[0], (list, tuple)) and len(z[0]) == 3
              and all(isinstance(x, (int, float)) and 0.0 <= x <= 1.0 for x in z[0]))
        if not ok:
            errores.append(f"zona {i} mal formada: {z!r} (se espera [[r, g, b] en 0-1, grupo])")
            continue
        cerca = [c for c in cols if max(abs(c[k] - z[0][k]) for k in range(3)) <= TOL_COLOR]
        if not cerca:
            errores.append(f"zona {z[1]!r} {list(z[0])}: ese color no está en el COLOR_0 (¿sRGB/lineal? ver "
                           "alcalde_blender.color)")
        cubiertos.update(cerca)
    sobran = [c for c in cols if c not in cubiertos]
    if sobran:
        avisos.append(f"{len(sobran)} colores del COLOR_0 sin zona: {sobran[:6]}{' ...' if len(sobran) > 6 else ''}")


def validar(ruta, esqueleto_arg=None, referencia=None):
    """Dict con 'valido', 'errores', 'avisos', 'medidas'. Lanza ValueError si el archivo no se puede leer."""
    clave = _clave_referencia(esqueleto_arg)
    m = medir(ruta)
    gltf = m.pop("gltf")
    errores, avisos = [], []
    if gltf.get("asset", {}).get("version") != "2.0":
        errores.append(f"asset.version = {gltf.get('asset', {}).get('version')!r} (se espera '2.0')")
    if m["extensiones"]:
        errores.append(f"usa extensiones {m['extensiones']} (sin Draco ni extensiones)")
    for malla in gltf.get("meshes", []):
        for prim in malla.get("primitives", []):
            if prim.get("extensions"):
                errores.append(f"primitiva de {malla.get('name')} con extensiones {sorted(prim['extensions'])}")
    for p in m["huesos_por_primitiva"]:
        if p["huesos"] > MAX_HUESOS:
            errores.append(f"{p['malla']}[{p['primitiva']}]: {p['huesos']} huesos con peso > 0 (tope del skinning "
                           f"por GPU: {MAX_HUESOS})")
    for malla, n in m["huesos_union_por_malla"].items():
        if n > MAX_HUESOS:
            avisos.append(f"{malla}: {n} huesos entre todas sus primitivas (cada primitiva cumple; si se fundieran, no)")
    if len(m["materiales"]) > MAX_MATERIALES:
        errores.append(f"{len(m['materiales'])} materiales (máximo {MAX_MATERIALES}): {m['materiales']}")
    if m["primitivas_sin_color"]:
        avisos.append(f"primitivas sin COLOR_0: {m['primitivas_sin_color']}")
    _validar_extras(m["extras_alcalde"], [tuple(c) for c in m["colores"]], errores, avisos)
    m["referencia"] = None
    es_prota = clave is not None and clave.startswith("prota:")
    pies_esperados, origen_pies = 0.0, "0"
    if clave is not None or referencia is not None:
        ruta_ref = Path(referencia) if referencia else CARPETA_PERSONAJES / REFERENCIAS[clave]
        ref = medir(ruta_ref)
        ref.pop("gltf")
        m["referencia"] = {"archivo": str(ruta_ref), "altura": ref["altura"], "pies_y": ref["pies_y"],
                           "frente_z": ref["frente_z"],
                           "nodo_esqueleto": ref["nodo_esqueleto"], "skin_joints": ref["skin_joints"]}
        faltan = sorted(set(ref["joints_padre"]) - set(m["joints_padre"]))
        sobran = sorted(set(m["joints_padre"]) - set(ref["joints_padre"]))
        if faltan:
            errores.append(f"faltan {len(faltan)} joints de {ruta_ref.name}: {faltan[:8]}{' ...' if len(faltan) > 8 else ''}")
        if sobran:
            errores.append(f"sobran {len(sobran)} joints que no tiene {ruta_ref.name}: {sobran[:8]}")
        malos = [(n, m["joints_padre"][n], p) for n, p in ref["joints_padre"].items()
                 if n in m["joints_padre"] and m["joints_padre"][n] != p]
        # Protagonistas (contrato §5, «su propio esqueleto»): un hueso que en la referencia era RAÍZ puede colgar de
        # otro hueso de la skin (el arreglo de protagonistas-raiz: el padre de Hornero._padre_virtual). Lo que ya
        # tenía padre tiene que conservarlo.
        if es_prota:
            nuevos = [(n, a, b) for n, a, b in malos if b is None and a is not None and a in m["joints_padre"]]
            malos = [x for x in malos if x not in nuevos]
            m["joints_reemparentados"] = len(nuevos)
            if nuevos:
                avisos.append(f"{len(nuevos)} joints raíz en {ruta_ref.name} cuelgan ahora de otro hueso (aceptado "
                              f"en protagonistas): " + ", ".join(f"{n} -> {a}" for n, a, _ in nuevos[:4])
                              + (" ..." if len(nuevos) > 4 else ""))
            # Pies: los de la referencia (el smoking de hoy los tiene a -0,019 m y subirlos movería la cabeza
            # respecto a rostro_calculos.REPOSO_CABEZA).
            pies_esperados, origen_pies = ref["pies_y"], f"los de {ruta_ref.name}"
        if malos:
            errores.append(f"{len(malos)} joints con otro padre que en {ruta_ref.name}: "
                           + ", ".join(f"{n}: {a} (ref {b})" for n, a, b in malos[:6]))
        if ref["frente_z"] and m["frente_z"] and ref["frente_z"] != m["frente_z"]:
            errores.append(f"mira hacia {'+' if m['frente_z'] > 0 else '-'}z y la referencia hacia "
                           f"{'+' if ref['frente_z'] > 0 else '-'}z")
        if ref["altura"] and abs(m["altura"] / ref["altura"] - 1.0) > TOL_ALTURA_REF:
            avisos.append(f"altura {m['altura']:.3f} m = {m['altura'] / ref['altura']:.3f} × la de {ruta_ref.name} "
                          f"({ref['altura']:.3f} m); el contrato pide ±3 % salvo diseño")
        if es_prota:
            faltan_c = [c for c in CLIPS_PROTAGONISTA if c not in m["animaciones"]]
            if faltan_c:
                errores.append(f"faltan clips de protagonista: {faltan_c}")
        elif clave in ("hombre", "mujer"):
            if m["animaciones"]:
                errores.append(f"un NPC v2 no lleva clips (los pone el código) y trae {m['animaciones']}")
            lo, hi = TRIANGULOS_NPC
            if not lo <= m["triangulos"] <= hi:
                avisos.append(f"{m['triangulos']} triángulos (el contrato pide {lo}-{hi} para el elenco)")
    if abs(m["pies_y"] - pies_esperados) > TOL_PIES:
        errores.append(f"pies en y = {m['pies_y']:+.3f} m (se espera {pies_esperados:+.3f} ± {TOL_PIES}, {origen_pies})")
    m.pop("joints_padre")
    return {"archivo": str(ruta), "esqueleto": clave, "valido": not errores, "errores": errores, "avisos": avisos,
            "medidas": m}


def informe_texto(r):
    m = r["medidas"]
    lineas = [f"{r['archivo']}: {'VÁLIDO' if r['valido'] else 'NO VÁLIDO'}"
              + (f" (esqueleto {r['esqueleto']})" if r["esqueleto"] else "")]
    lineas.append(f"  triángulos {m['triangulos']}  " + ", ".join(f"{k} {v}" for k, v in m["triangulos_por_malla"].items()))
    lineas.append(f"  skin {m['skin_joints']} joints; huesos con peso > 0: máx. {m['huesos_max_primitiva']} por "
                  f"primitiva (tope {MAX_HUESOS}); por malla " + ", ".join(f"{k} {v}" for k, v in m["huesos_union_por_malla"].items()))
    lineas.append(f"  materiales {len(m['materiales'])}: {m['materiales']}")
    ne = m["nodo_esqueleto"]
    lineas.append(f"  altura {m['altura']:.3f} m, pies y = {m['pies_y']:+.4f} m, frente {'+z' if m['frente_z'] > 0 else '-z' if m['frente_z'] < 0 else '?'}"
                  + (f"; nodo del esqueleto {ne['nombre']} escala {[round(x, 4) for x in ne['escala']]}" if ne else ""))
    lineas.append(f"  animaciones {m['animaciones']}; extensiones {m['extensiones'] or 'ninguna'}; "
                  f"{len(m['colores'])} colores en COLOR_0")
    if m.get("referencia"):
        ref = m["referencia"]
        lineas.append(f"  referencia {Path(ref['archivo']).name}: altura {ref['altura']:.3f} m, skin {ref['skin_joints']}")
    ex = m["extras_alcalde"]
    lineas.append(f"  extras.alcalde: {'no' if not ex else ', '.join(sorted(ex))}")
    lineas += [f"  ERROR: {e}" for e in r["errores"]]
    lineas += [f"  aviso: {a}" for a in r["avisos"]]
    return "\n".join(lineas)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Valida un .glb de personaje contra el contrato de la fase Blender.")
    ap.add_argument("glb")
    ap.add_argument("--esqueleto", help="hombre | mujer | prota:<ciudadano|periodista|candidato|influencer>")
    ap.add_argument("--referencia", help=".glb de referencia (por defecto, el del --esqueleto)")
    ap.add_argument("--json", action="store_true", help="salida JSON")
    a = ap.parse_args(argv)
    try:
        r = validar(a.glb, a.esqueleto, a.referencia)
    except (OSError, ValueError, KeyError, IndexError, struct.error, json.JSONDecodeError) as error:
        r = {"archivo": a.glb, "valido": False, "errores": [f"no se pudo leer: {type(error).__name__}: {error}"],
             "avisos": [], "medidas": None}
        if a.json:
            print(json.dumps(r, ensure_ascii=False, indent=1))
        else:
            print(f"{a.glb}: NO VÁLIDO\n  ERROR: {r['errores'][0]}")
        return 2
    if a.json:
        print(json.dumps(r, ensure_ascii=False, indent=1, default=list))
    else:
        print(informe_texto(r))
    return 0 if r["valido"] else 1


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
