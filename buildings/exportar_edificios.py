# Exporta una casa de Blender (.blend de esta carpeta) a un .glb listo para el juego.
#
# Uso (Blender en modo background, una vez por casa):
#   blender -b buildings/casa1fav.blend --python buildings/exportar_edificios.py -- casa1
#
# Qué hace (el .blend original NO se guarda):
#   1. Borra cámaras y luces, une todos los meshes en uno y reenlaza las texturas por nombre a buildings/textures/ (las que
#      faltan se reemplazan por SUSTITUTOS) y las reduce a TAMANO_TEXTURA px como máximo.
#   2. Aplica rotación y escala y mueve la geometría para que el origen quede en el centro de la
#      HUELLA de planta baja y a la altura del umbral de la puerta (el suelo del juego).
#   3. Busca la puerta de entrada: polígonos con textura de puerta en la fachada +Y (el frente
#      de todas las casas), lo más abajo posible; a igual altura, una puerta antes que un
#      garaje y la más centrada.
#   4. Exporta assets/modelos/edificios/<nombre>.glb y la textura de la puerta como
#      <nombre>_puerta.jpg, e imprime la entrada para backend/datos/modelos_edificios.py.
#
# Convención: Blender +Y (frente) -> +z de Ursina, Blender +Z (arriba) -> +y de Ursina.

import os
import sys

import bpy

CARPETA = os.path.dirname(os.path.abspath(__file__))
TEXTURAS = os.path.join(CARPETA, "textures")
SALIDA = os.path.join(os.path.dirname(CARPETA), "assets", "modelos", "edificios")

TAMANO_TEXTURA = 1024
# Texturas que referencian los .blend pero no están en textures/: se usa una parecida.
SUSTITUTOS = {
    "Concrete-3012.jpg": "Concrete-2767.jpg",
    "WoodDoor-2044.jpg": "Door-8850.jpg",
    "Picsart_23-07-21_09-24-44-403.jpg": "janela01.jpg",
    "Picsart_23-07-21_09-23-07-056.jpg": "janela01.jpg",
}
PALABRA_PUERTA = "door"           # en el nombre de la imagen (Door-*, WoodDoor-*, GarageDoor-*)
FRANJA_FRENTE = 0.25              # fracción del fondo: qué tan cerca del frente debe estar la puerta
TOLERANCIA_ALTURA = 0.1           # puertas cuyo umbral difiere menos que esto cuentan como igual de bajas
ESCALON = 0.03                    # el suelo queda apenas por debajo del umbral


def _nombre_salida():
    argumentos = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    if not argumentos:
        raise SystemExit("Falta el nombre de salida: ... --python exportar_edificios.py -- casa1")
    return argumentos[0]


def _reenlazar_texturas():
    for imagen in bpy.data.images:
        if not imagen.filepath:
            continue
        nombre = imagen.name
        ruta = os.path.join(TEXTURAS, nombre)
        if not os.path.exists(ruta):
            # Imágenes duplicadas ("x.jpg.001"): se busca por el nombre del archivo.
            nombre = bpy.path.basename(imagen.filepath.replace("\\", "/"))
            ruta = os.path.join(TEXTURAS, nombre)
        if not os.path.exists(ruta) and nombre in SUSTITUTOS:
            print(f"AVISO: falta {nombre}; se usa {SUSTITUTOS[nombre]}")
            ruta = os.path.join(TEXTURAS, SUSTITUTOS[nombre])
        if not os.path.exists(ruta):
            print(f"AVISO: falta {nombre} y no tiene sustituto")
            continue
        imagen.filepath = ruta
        imagen.reload()
        ancho, alto = imagen.size
        if max(ancho, alto) > TAMANO_TEXTURA:
            k = TAMANO_TEXTURA / max(ancho, alto)
            imagen.scale(max(1, round(ancho * k)), max(1, round(alto * k)))
        imagen.pack()


def _imagen_de(objeto, poligono):
    material = objeto.material_slots[poligono.material_index].material
    if material and material.node_tree:
        for nodo in material.node_tree.nodes:
            if nodo.type == "TEX_IMAGE" and nodo.image:
                return nodo.image
    return None


def _caja(puntos):
    xs, ys, zs = zip(*puntos)
    return min(xs), max(xs), min(ys), max(ys), min(zs), max(zs)


# Puerta de entrada: entre los polígonos con textura de puerta que miran a +Y y están en la
# franja delantera, el más bajo (entre los igual de bajos, no garaje y el más centrado). Devuelve la caja
# (x0, x1, z0, z1) de esa puerta (sumando los polígonos apilados en la misma columna) y su imagen.
def _buscar_puerta(objeto):
    malla = objeto.data
    x0, x1, y0, y1, _, _ = _caja([v.co for v in malla.vertices])
    centro_x = (x0 + x1) / 2
    candidatos = []
    for p in malla.polygons:
        imagen = _imagen_de(objeto, p)
        if imagen is None or PALABRA_PUERTA not in imagen.name.lower() or p.normal.y < 0.9:
            continue
        caja = _caja([malla.vertices[i].co for i in p.vertices])
        if caja[2] < y1 - FRANJA_FRENTE * (y1 - y0):
            continue
        candidatos.append((caja, imagen))
    if not candidatos:
        raise SystemExit("No se encontró ninguna puerta en la fachada +Y.")
    mas_baja = min(c[4] for c, _ in candidatos)
    a_ras = [(c, im) for c, im in candidatos if c[4] <= mas_baja + TOLERANCIA_ALTURA]
    caja, imagen = min(a_ras, key=lambda c: ("garage" in c[1].name.lower(),
                                             abs((c[0][0] + c[0][1]) / 2 - centro_x)))
    columna = [c for c, im in candidatos
               if im == imagen and abs(c[0] - caja[0]) < 1e-3 and abs(c[1] - caja[1]) < 1e-3]
    return (caja[0], caja[1], min(c[4] for c in columna), max(c[5] for c in columna)), imagen


def main():
    nombre = _nombre_salida()
    os.makedirs(SALIDA, exist_ok=True)
    for objeto in list(bpy.data.objects):
        if objeto.type in ("CAMERA", "LIGHT"):
            bpy.data.objects.remove(objeto)
    mallas = [o for o in bpy.data.objects if o.type == "MESH"]
    if not mallas:
        raise SystemExit("No hay ningún objeto mesh.")
    _reenlazar_texturas()

    # Si la casa tiene varias piezas, se unen en una sola (la de más polígonos queda activa).
    objeto = max(mallas, key=lambda o: len(o.data.polygons))
    bpy.ops.object.select_all(action="DESELECT")
    for malla_extra in mallas:
        malla_extra.select_set(True)
    bpy.context.view_layer.objects.active = objeto
    if len(mallas) > 1:
        bpy.ops.object.join()
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    malla = objeto.data

    (px0, px1, pz0, pz1), imagen_puerta = _buscar_puerta(objeto)
    suelo = pz0 - ESCALON
    # Huella: solo la planta baja (de suelo a la altura de la puerta), sin aleros ni balcones.
    planta = [v.co for v in malla.vertices if suelo - 1e-3 <= v.co.z <= pz1]
    x0, x1, y0, y1, _, _ = _caja(planta)
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    for v in malla.vertices:
        v.co.x -= cx
        v.co.y -= cy
        v.co.z -= suelo
    malla.update()
    alto = max(v.co.z for v in malla.vertices)

    ruta_glb = os.path.join(SALIDA, f"{nombre}.glb")
    bpy.ops.export_scene.gltf(filepath=ruta_glb, export_format="GLB", export_yup=True,
                              export_image_format="JPEG", export_cameras=False, export_lights=False,
                              use_selection=False)

    archivo_puerta = f"{nombre}_puerta.jpg"
    bpy.context.scene.render.image_settings.file_format = "JPEG"
    imagen_puerta.save_render(os.path.join(SALIDA, archivo_puerta))

    print(f'MODELO     "{nombre}": ModeloEdificio("{nombre}", frente={x1 - x0:.3f}, fondo={y1 - y0:.3f}, '
          f'alto={alto:.3f}, puerta_x={(px0 + px1) / 2 - cx:.3f}, puerta_ancho={px1 - px0:.3f}, '
          f'puerta_alto={pz1 - pz0:.3f}, textura_puerta="{archivo_puerta}"),')
    print(f"EXPORTADO  {ruta_glb}  (puerta: {imagen_puerta.name})")


main()
