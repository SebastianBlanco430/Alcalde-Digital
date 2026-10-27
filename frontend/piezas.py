# Piezas del mundo 3D (Ursina): Entity con el shader que recibe luz y sombras.
# Todo lo que se dibuja en `scene` en 3D real (ciudad, personajes, interior) se arma con
# estas primitivas (cubo, esfera, plano, círculo).

from panda3d.core import (BitMask32, Geom, GeomLines, GeomNode, GeomVertexData, GeomVertexFormat,
                          GeomVertexWriter, NodePath)
from ursina import Entity, Text, color
from ursina.shaders import lit_with_shadows_shader

from frontend import estilo
from frontend.componentes import rgb

# Máscara de la cámara de sombras de DirectionalLight (camera mask 0b0001): `hide(MASCARA_LUZ)` saca
# una pieza del mapa de sombras. Definición única; la importan ciudad_3d y banderas.
MASCARA_LUZ = BitMask32.bit(0)

# Ajustes del shader (se aplican a las piezas que se creen después): bias NEGATIVO (en Ursina el
# positivo agrega sombra) para que las
# capas planas del piso (calle/plaza/aro) no se auto-sombreen, y una sombra neutra (la de
# Ursina es azulada).
lit_with_shadows_shader.default_input["shadow_bias"] = -0.0008
# Sombra azul-violeta y algo más suave (antes rgba(0.22, 0.24, 0.40, 0.50)): resta menos luz de la
# cuenta, sobre todo en el azul, así los colores vivos se ven aun a la sombra.
lit_with_shadows_shader.default_input["shadow_color"] = color.rgba(0.36, 0.30, 0.62, 0.36)
lit_with_shadows_shader.default_input["shadow_blur"] = 0.002


# Entity del mundo con sombreado y sombras (`shader` se puede pasar como None para algo
# brillante que no recibe luz: ventanas, baliza, ruta del GPS).
def pieza(**opciones):
    opciones.setdefault("shader", lit_with_shadows_shader)
    return Entity(**opciones)


# Marca la entidad y todos sus descendientes con ignore=True: Ursina los salta en su bucle de
# update()/input() (que recorre TODAS las entidades en Python cada frame, con un costo
# apreciable por entidad). Solo para lo pasivo: algo que sí necesite update() o recibir
# input (botones, el Sky que sigue a la cámara) no debe silenciarse.
def silenciar(entidad):
    entidad.ignore = True
    for hijo in entidad.children:
        silenciar(hijo)
    return entidad


# Une en UNA malla las piezas dadas ({model, color, position, scale}) colgadas de `padre`
# (menos entidades y menos llamadas de dibujo). Devuelve la Entity resultante.
def malla_unida(padre, piezas, **opciones):
    soporte = Entity(parent=padre, **opciones)
    for datos in piezas:
        Entity(parent=soporte, **datos)
    soporte.combine()
    soporte.shader = lit_with_shadows_shader
    return soporte


# Enciende o apaga una luz de ursina.lights (DirectionalLight, AmbientLight) a nivel de render.
# El shader lit_with_shadows solo usa la PRIMERA luz activa: por eso cada escena 3D (ciudad,
# interior) enciende la suya al entrar y la apaga al salir; si no, la de la escena oculta
# (con sombras calculadas para otra geometría) ensucia a la que está a la vista.
def encender_luz(luz, encendida):
    from ursina import application
    nodo = luz.find("**/+Light")
    if nodo.is_empty():
        return
    render = application.base.render
    if encendida:
        render.setLight(nodo)
    else:
        render.clearLight(nodo)


COLOR_PIEL = color.rgb32(235, 200, 170)
COLOR_MARCADOR = color.rgb32(*estilo.COLOR_DESTINO)


# Etiqueta de texto que siempre mira a la cámara (billboard), centrada y sobre un fondo oscuro
# translúcido (se lee igual sobre fondos claros y oscuros).
def etiqueta(texto, **opciones):
    opciones.setdefault("scale", 18)
    opciones.setdefault("color", rgb(estilo.COLOR_TEXTO))
    texto_3d = Text(texto, billboard=True, origin=(0, 0), **opciones)
    texto_3d.create_background(padding=(0.03, 0.015), radius=0.3, color=color.rgba32(10, 12, 20, 170))
    return texto_3d


# Acota el tamaño aparente de la etiqueta (frontend/etiqueta_calculos.py): cada frame, con la cámara cerca, la escala
# baja con la distancia para que en pantalla no pase de lo que mide a DISTANCIA_REFERENCIA. Nunca lanza. Lo llama el
# update() de cada personaje (la etiqueta está silenciada: no tiene el suyo).
def limitar_etiqueta(texto_3d):
    try:
        if not texto_3d.enabled:
            return
        from ursina import camera
        from frontend.etiqueta_calculos import escala_limitada
        base = getattr(texto_3d, "escala_base", None)
        if base is None:
            base = texto_3d.escala_base = texto_3d.scale_x
        distancia = (camera.world_position - texto_3d.world_position).length()
        nueva = escala_limitada(base, distancia)
        if abs(nueva - texto_3d.scale_x) > 1e-3:
            texto_3d.scale = nueva
    except Exception:
        pass


# Segmentos sueltos (vértices de a pares) en un solo Geom. Mesh(mode="line") de Ursina los uniría
# todos en una sola línea continua.
def lineas_sueltas(vertices):
    datos = GeomVertexData("lineas", GeomVertexFormat.get_v3(), Geom.UH_static)
    datos.set_num_rows(len(vertices))
    escritor = GeomVertexWriter(datos, "vertex")
    for v in vertices:
        escritor.add_data3(*v)
    lineas = GeomLines(Geom.UH_static)
    for i in range(0, len(vertices) - 1, 2):
        lineas.add_vertices(i, i + 1)
    geom = Geom(datos)
    geom.add_primitive(lineas)
    nodo = GeomNode("lineas")
    nodo.add_geom(geom)
    return NodePath(nodo)
