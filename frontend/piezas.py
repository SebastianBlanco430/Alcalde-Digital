# Piezas del mundo 3D (Ursina): Entity con el shader que recibe luz y sombras.
# Todo lo que se dibuja en `scene` en 3D real (ciudad, personajes, interior) se arma con
# estas primitivas (cubo, esfera, plano, círculo).

from ursina import Entity, Text, color
from ursina.shaders import lit_with_shadows_shader

from frontend import estilo
from frontend.componentes import rgb

# Ajustes del shader (se aplican a las piezas que se creen después): bias NEGATIVO (en Ursina el
# positivo agrega sombra) para que las
# capas planas del piso (calle/plaza/aro) no se auto-sombreen, y una sombra neutra (la de
# Ursina es azulada).
lit_with_shadows_shader.default_input["shadow_bias"] = -0.0008
lit_with_shadows_shader.default_input["shadow_color"] = color.rgba(0.30, 0.30, 0.38, 0.42)
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
COLOR_MARCADOR = color.rgb32(255, 220, 60)


# Etiqueta de texto que siempre mira a la cámara (billboard), centrada y sobre un fondo oscuro
# translúcido (se lee igual sobre fondos claros y oscuros).
def etiqueta(texto, **opciones):
    opciones.setdefault("scale", 18)
    opciones.setdefault("color", rgb(estilo.COLOR_TEXTO))
    texto_3d = Text(texto, billboard=True, origin=(0, 0), **opciones)
    texto_3d.create_background(padding=(0.03, 0.015), radius=0.3, color=color.rgba32(10, 12, 20, 170))
    return texto_3d
