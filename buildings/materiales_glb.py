# Asigna un material a las primitivas de un .glb que no tienen ninguno (Python puro, sin Blender ni panda3d).
#
# Por qué: el cargador glTF de Panda3D (panda3d-gltf, gltf/_converter.py) avisa al arrancar con
#   «Warning: mesh Cube.023 has a primitive with no material, using an empty RenderState»
# por cada primitiva sin `material`. Pasaba con los NPC nuevos (npc_hombre_01..03: «Cube.023»; npc_mujer_01:
# «Cabello_Liso» y «Cylinder»; npc_mujer_02: «Cabello_Cola» y «Cylinder»), exportados sin materiales porque el color va
# en los vértices (COLOR_0).
#
# Qué hace: añade a cada malla con primitivas sin material un material propio con el nombre de la malla y la MISMA
# forma que los materiales de los .glb que ya se ven bien (periodista, brasilena...): {"pbrMetallicRoughness":
# {"metallicFactor": 0}}; sin color base (= blanco, no tiñe el color de vértice), sin textura y sin doubleSided (la
# primitiva conserva el culling que tenía con el RenderState vacío). No toca vértices, índices ni el buffer binario:
# solo reescribe el bloque JSON del .glb (con su relleno a 4 bytes) y la longitud total.
#
# Uso:  python buildings/materiales_glb.py assets/modelos/personajes/npc_*.glb [--copia DIRECTORIO] [--comprobar]
#   --comprobar  solo lista lo que cambiaría (no escribe).
#   --copia DIR  guarda el original en DIR antes de reescribir.

import json
import shutil
import struct
import sys
from pathlib import Path

MAGIA_GLB = 0x46546C67           # «glTF»
TIPO_JSON = 0x4E4F534A           # «JSON»


def leer_glb(datos):
    magia, version, _largo = struct.unpack_from("<III", datos, 0)
    if magia != MAGIA_GLB or version != 2:
        raise ValueError("no es un .glb versión 2")
    largo_json, tipo = struct.unpack_from("<II", datos, 12)
    if tipo != TIPO_JSON:
        raise ValueError("el primer bloque no es JSON")
    documento = json.loads(datos[20:20 + largo_json].decode("utf-8"))
    resto = datos[20 + largo_json:]              # bloques siguientes (BIN) tal cual
    return documento, resto


def escribir_glb(documento, resto):
    texto = json.dumps(documento, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    texto += b" " * ((4 - len(texto) % 4) % 4)  # el bloque JSON se rellena con espacios hasta múltiplo de 4
    largo_total = 12 + 8 + len(texto) + len(resto)
    return struct.pack("<III", MAGIA_GLB, 2, largo_total) + struct.pack("<II", len(texto), TIPO_JSON) + texto + resto


# Añade los materiales que faltan al documento (lo modifica). Retorna [(malla, nº de primitivas arregladas)].
def asignar_materiales(documento):
    materiales = documento.setdefault("materials", [])
    cambios = []
    for malla in documento.get("meshes", []):
        sin_material = [p for p in malla.get("primitives", []) if p.get("material") is None]
        if not sin_material:
            continue
        nombre = malla.get("name") or f"malla{len(cambios)}"
        materiales.append({"name": nombre, "pbrMetallicRoughness": {"metallicFactor": 0}})
        indice = len(materiales) - 1
        for primitiva in sin_material:
            primitiva["material"] = indice
        cambios.append((nombre, len(sin_material)))
    return cambios


def procesar(ruta, copia=None, comprobar=False):
    ruta = Path(ruta)
    datos = ruta.read_bytes()
    documento, resto = leer_glb(datos)
    cambios = asignar_materiales(documento)
    if not cambios or comprobar:
        return cambios
    if copia is not None:
        Path(copia).mkdir(parents=True, exist_ok=True)
        shutil.copy2(ruta, Path(copia) / ruta.name)
    ruta.write_bytes(escribir_glb(documento, resto))
    return cambios


def main(argumentos):
    comprobar = "--comprobar" in argumentos
    copia = None
    rutas = []
    i = 0
    while i < len(argumentos):
        if argumentos[i] == "--copia":
            copia = argumentos[i + 1]
            i += 2
            continue
        if not argumentos[i].startswith("--"):
            rutas.append(argumentos[i])
        i += 1
    for ruta in rutas:
        cambios = procesar(ruta, copia, comprobar)
        estado = "sin cambios" if not cambios else ("cambiaría" if comprobar else "arreglado")
        print(f"{ruta}: {estado} {cambios}")


if __name__ == "__main__":
    main(sys.argv[1:])
