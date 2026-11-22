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
    return texto_sin_tinta(texto_3d)


# R3a (retoques): la tinta de pantalla (Sobel sobre la profundidad) veía las letras de los textos del mundo como bordes
# y las erosionaba («Beto» se leía «Belo»). Con la tinta encendida, los textos del mundo no escriben profundidad (siguen
# ocultándose tras lo que tienen delante): el Sobel no los ve. ALCALDE_TINTA_PANTALLA=0 lo deja como antes. Nunca lanza.
def texto_sin_tinta(texto_3d):
    try:
        from frontend import pase_final_calculos
        if pase_final_calculos.tinta_activa():
            texto_3d.setDepthWrite(False)
            fondo = getattr(texto_3d, "background_entity", None)
            if fondo is not None:
                fondo.setDepthWrite(False)
    except Exception:
        pass
    return texto_3d


# Acota el tamaño aparente de la etiqueta (frontend/etiqueta_calculos.py): cada frame, con la cámara cerca, la escala
# baja con la distancia para que en pantalla no pase de lo que mide a DISTANCIA_REFERENCIA. Nunca lanza. Lo llama el
# update() de cada personaje (la etiqueta está silenciada: no tiene el suyo).
def limitar_etiqueta(texto_3d):
    try:
        if not texto_3d.enabled:
            return
        from ursina import camera
        from frontend.etiqueta_calculos import ESCALA_OTROS, alfa_por_distancia, escala_limitada
        base = getattr(texto_3d, "escala_base", None)
        if base is None:
            base = texto_3d.escala_base = texto_3d.scale_x
        distancia = (camera.world_position - texto_3d.world_position).length()
        atenuar = getattr(texto_3d, "atenuar_otro", False)     # M1.1: solo lo pone modo_etiqueta_jugador()
        if atenuar and texto_3d.isHidden():
            return
        nueva = escala_limitada(base * ESCALA_OTROS if atenuar else base, distancia)
        if abs(nueva - texto_3d.scale_x) > 1e-3:
            texto_3d.scale = nueva
        if atenuar:
            alfa, previo = alfa_por_distancia(distancia), getattr(texto_3d, "_alfa_etiqueta", 1.0)
            if alfa != previo and (abs(alfa - previo) > 1e-2 or alfa in (0.0, 1.0)):
                texto_3d._alfa_etiqueta = alfa
                texto_3d.setAlphaScale(alfa)       # afecta también al fondo (hijo); sin crear nada nuevo
    except Exception:
        pass


# M1.1 (D6): decide si la etiqueta de un avatar de jugador se ve (la del propio jugador no) y marca las de los demás
# para que limitar_etiqueta() las deje al 60 % y desvanecidas con la distancia. Lo llama resaltar() (no cada frame).
# Usa `visible` (hide/show), independiente del `enabled` que tocan cinemáticas e interiores. Con
# ALCALDE_ETIQUETA_JUGADOR=0 no hace nada: todo queda como antes.
def modo_etiqueta_jugador(texto_3d, es_activo):
    try:
        from frontend.etiqueta_calculos import etiqueta_jugador_activa, mostrar_etiqueta
        if not etiqueta_jugador_activa():
            return
        texto_3d.visible = mostrar_etiqueta(es_activo)
        texto_3d.atenuar_otro = not es_activo
        if not hasattr(texto_3d, "_alfa_etiqueta"):
            texto_3d._alfa_etiqueta = 1.0
            texto_3d.setTransparency(1)            # TransparencyAttrib.M_alpha, para setAlphaScale
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
