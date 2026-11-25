# Sello de la Torre de la Tradición dibujado por código (Ursina): torre de reloj dentro de un sello redondo, solo con
# primitivas (quads, círculos y un triángulo), sin texturas, emojis ni caracteres especiales. La forma y las capas viven
# en frontend/sello_tradicion_calculos.py; qué mensaje lo lleva, en backend/logica/sello_rumores.py. Lo usan el banner
# y el panel del teléfono (frontend/hud.py), los minijuegos «Señales» y «Comparar» (marca de agua) y los carteles de
# campaña del día 5 (frontend/carteles_campana.py). Bandera: ALCALDE_HILO_SELLO (ver sello_rumores).
#
#   crear_sello(parent, lado, alfa=1.0, position=(0, 0, 0), plano=True) -> Entity (el sello; lado en unidades del padre)
#       plano=False: las piezas heredan el shader del padre (sobre el papel 3D de los minijuegos, con su luz)
#   crear_sello_capa(parent, capa, position)                  -> Entity con el lado y el alfa de la capa (camera.ui)

from ursina import Entity, Mesh, color

from frontend import sello_tradicion_calculos as calc
from frontend.componentes import a_unidades

_TRIANGULO = None


def _malla_triangulo():
    global _TRIANGULO
    if _TRIANGULO is None:
        # Triángulo de base 1 y alto 1 centrado en 0, con las dos caras (se ve igual desde los dos lados).
        _TRIANGULO = Mesh(vertices=[(-0.5, -0.5, 0), (0.5, -0.5, 0), (0, 0.5, 0)], triangles=[(0, 1, 2), (0, 2, 1)])
    return _TRIANGULO


def _tono(nombre, alfa):
    r, g, b = calc.tono_de(nombre)
    return color.rgba32(r, g, b, int(round(255 * max(0.0, min(1.0, alfa)))))


def crear_sello(parent, lado, alfa=1.0, position=(0, 0, 0), plano=True, **opciones):
    sello = Entity(parent=parent, position=position, scale=lado, **opciones)
    extra = {"shader": None} if plano else {}
    for k, pieza in enumerate(calc.piezas()):
        z = -0.001 * (k + 1)
        tono = _tono(pieza["tono"], alfa)
        if pieza["tipo"] == "disco":
            modelo = "circle"
        elif pieza["tipo"] == "tri":
            modelo = _malla_triangulo()
        else:
            modelo = "quad"
        Entity(parent=sello, model=modelo, color=tono, position=(pieza["x"], pieza["y"], z),
               scale=(pieza["ancho"], pieza["alto"]), rotation_z=pieza.get("giro", 0.0), **extra)
    return sello


def crear_sello_capa(parent, capa, position=(0, 0, 0)):
    lado_px, alfa, _sitio = calc.estilo_de_capa(capa)
    return crear_sello(parent, a_unidades(lado_px), alfa, position)
