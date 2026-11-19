# Dibujos 2D del minijuego de trabajo (VISTA, Ursina): iconos de producto, flechas, marca de acierto y clientes.
# Salieron de escenas/escena_trabajo.py para que las vistas (trabajos_visual) no importen un controlador;
# la escena los reexporta con los mismos nombres.
import random

from ursina import Entity, Mesh, Text

from frontend import estilo, tipografia
from frontend.trabajo_constantes import ROTACION_FLECHA
from frontend.componentes import escala_fuente, modelo_redondeado, rgb

def _seguro(cadena):
    return str(cadena).replace("<", "(").replace(">", ")")


def _texto(padre, cadena, px, tono, pos, origen=(0, 0), negrita=False, z=-0.01):
    opciones = {"font": tipografia.FUENTE_TITULO} if negrita else {}
    return Text(_seguro(cadena), parent=padre, origin=origen, position=(pos[0], pos[1], z),
                scale=escala_fuente(px), color=rgb(tono), **opciones)


def _caja(padre, ancho, alto, tono, pos, radio=6, z=0.0):
    return Entity(parent=padre, model=modelo_redondeado(ancho, alto, radio),
                  color=rgb(tono) if isinstance(tono, tuple) else tono, scale=(ancho, alto),
                  position=(pos[0], pos[1], z))


PIEL = ((236, 196, 160), (205, 150, 108), (150, 100, 66), (104, 66, 44))
CAMISAS = ((214, 92, 80), (78, 150, 214), (96, 176, 110), (230, 170, 60), (160, 110, 200), (70, 190, 190))
PELO = ((40, 30, 28), (90, 56, 34), (200, 160, 80), (30, 30, 40))


def _triangulo():
    return Mesh(vertices=[(-0.5, -0.5, 0), (0.5, -0.5, 0), (0, 0.5, 0)], triangles=[(0, 1, 2)])


# Capa de dibujo: cada forma que se añade queda un pelo delante de la anterior (orden de pintado estable).
class Capa:

    def __init__(self, padre, z=-0.002):
        self.padre = padre
        self.z = z
        self.n = 0

    def forma(self, modelo, tono, escala, pos=(0, 0), rot=0):
        self.n += 1
        e = Entity(parent=self.padre, model=_triangulo() if modelo == "triangulo" else modelo,
                   color=rgb(tono) if isinstance(tono, tuple) else tono, scale=escala,
                   position=(pos[0], pos[1], self.z - 0.0004 * self.n))
        e.rotation_z = rot
        return e

    def elipse(self, tono, w, h, pos=(0, 0), rot=0):
        return self.forma("circle", tono, (w, h), pos, rot)

    def rect(self, tono, w, h, pos=(0, 0), rot=0):
        return self.forma("quad", tono, (w, h), pos, rot)


# ---------------------------------------------------------------------------
# Iconos de producto: dibujados con formas. `k` = lado aproximado del icono en unidades de camera.ui.
# ---------------------------------------------------------------------------

def _pan(c, k):
    c.elipse((205, 140, 70), k * 1.0, k * 0.62)
    c.elipse((226, 170, 96), k * 0.8, k * 0.4, (0, k * 0.06))
    for dx in (-0.2, 0.0, 0.2):
        c.rect((150, 96, 48), k * 0.05, k * 0.2, (dx * k, k * 0.07), rot=35)


def _cafe(c, k):
    c.elipse(estilo.PAPEL, k * 0.2, k * 0.22, (k * 0.36, -k * 0.02))
    c.elipse(estilo.COLOR_TARJETA, k * 0.1, k * 0.12, (k * 0.36, -k * 0.02))
    c.rect(estilo.PAPEL, k * 0.62, k * 0.52, (0, -k * 0.06))
    c.rect((90, 56, 34), k * 0.52, k * 0.09, (0, k * 0.15))
    for dx in (-0.12, 0.12):
        c.rect(estilo.COLOR_TEXTO_TENUE, k * 0.04, k * 0.2, (dx * k, k * 0.38), rot=12)


def _bollo(c, k):
    c.elipse((214, 160, 90), k * 0.92, k * 0.82)
    c.elipse((240, 150, 180), k * 0.7, k * 0.52, (0, k * 0.06))
    c.elipse(estilo.COLOR_TARJETA, k * 0.2, k * 0.17, (0, -k * 0.02))
    for dx, dy in ((-0.2, 0.15), (0.18, 0.17), (0.0, 0.26), (-0.28, 0.0), (0.26, 0.02)):
        c.rect(estilo.PAPEL, k * 0.04, k * 0.1, (dx * k, dy * k), rot=40)


def _leche(c, k):
    c.rect((245, 245, 250), k * 0.46, k * 0.62, (0, -k * 0.05))
    c.forma("triangulo", (225, 225, 235), (k * 0.46, k * 0.2), (0, k * 0.36))
    c.rect((80, 140, 214), k * 0.46, k * 0.18, (0, -k * 0.08))
    c.elipse(estilo.PAPEL, k * 0.16, k * 0.12, (0, -k * 0.08))


def _arroz(c, k):
    c.rect((236, 226, 186), k * 0.58, k * 0.74, (0, -k * 0.02))
    c.rect((200, 188, 140), k * 0.58, k * 0.1, (0, k * 0.33))
    c.elipse((70, 150, 90), k * 0.3, k * 0.22, (0, -k * 0.02))
    for dx, dy in ((-0.1, 0.1), (0.1, 0.06), (0.0, -0.15)):
        c.elipse(estilo.PAPEL, k * 0.05, k * 0.1, (dx * k, dy * k - 0.0), rot=30)


def _feijao(c, k):
    c.elipse(estilo.COLOR_PANEL, k * 0.95, k * 0.62, (0, -k * 0.12))
    for dx, dy, r in ((-0.26, -0.02, 20), (0.0, 0.04, -15), (0.25, 0.0, 30), (-0.12, -0.2, -25), (0.14, -0.2, 10)):
        c.elipse((120, 56, 40), k * 0.28, k * 0.18, (dx * k, dy * k), rot=r)
        c.elipse((160, 92, 64), k * 0.12, k * 0.06, (dx * k, (dy + 0.03) * k), rot=r)


def _jabon(c, k):
    c.forma(modelo_redondeado(k * 0.7, k * 0.44, 4), (120, 190, 235), (k * 0.7, k * 0.44), (0, -k * 0.1))
    c.rect(estilo.PAPEL, k * 0.4, k * 0.06, (0, -k * 0.1))
    for dx, dy, r in ((-0.22, 0.3, 0.2), (0.0, 0.4, 0.14), (0.24, 0.28, 0.16)):
        c.elipse((200, 235, 250), k * r, k * r, (dx * k, dy * k))


def _mango(c, k):
    c.elipse((240, 170, 50), k * 0.74, k * 0.82)
    c.elipse((226, 96, 60), k * 0.4, k * 0.5, (k * 0.14, -k * 0.06))
    c.elipse((80, 160, 70), k * 0.3, k * 0.12, (-k * 0.02, k * 0.42), rot=-30)


def _banana(c, k):
    for dx, dy, r in ((-0.16, -0.04, 25), (0.0, 0.0, 8), (0.16, -0.04, -10)):
        c.elipse((245, 214, 70), k * 0.2, k * 0.84, (dx * k, dy * k), rot=r)
        c.elipse((200, 160, 40), k * 0.06, k * 0.14, (dx * k - k * 0.02, (dy - 0.38) * k), rot=r)
    c.rect((110, 90, 40), k * 0.12, k * 0.08, (0, k * 0.4))


def _tomate(c, k):
    c.elipse((214, 54, 48), k * 0.82, k * 0.74, (0, -k * 0.04))
    c.elipse((236, 110, 96), k * 0.2, k * 0.12, (-k * 0.18, k * 0.08), rot=30)
    for r in (0, 72, 144):
        c.elipse((70, 160, 80), k * 0.4, k * 0.1, (0, k * 0.3), rot=r)


def _yuca(c, k):
    c.elipse((190, 150, 100), k * 0.3, k * 0.95, rot=-55)
    c.elipse((226, 200, 160), k * 0.14, k * 0.7, (k * 0.04, k * 0.02), rot=-55)
    c.rect((110, 74, 46), k * 0.07, k * 0.07, (-k * 0.36, -k * 0.2), rot=-55)


def _agua(c, k):
    c.rect((150, 205, 240), k * 0.36, k * 0.66, (0, -k * 0.08))
    c.rect((150, 205, 240), k * 0.2, k * 0.16, (0, k * 0.32))
    c.rect((60, 110, 200), k * 0.24, k * 0.1, (0, k * 0.42))
    c.rect(estilo.PAPEL, k * 0.3, k * 0.18, (0, -k * 0.06))
    c.rect((90, 160, 220), k * 0.28, k * 0.03, (0, -k * 0.2))


def _refresco(c, k):
    c.rect((206, 52, 52), k * 0.44, k * 0.7)
    c.rect((200, 205, 215), k * 0.44, k * 0.07, (0, k * 0.35))
    c.rect((200, 205, 215), k * 0.44, k * 0.07, (0, -k * 0.35))
    c.rect(estilo.PAPEL, k * 0.44, k * 0.16)
    c.rect(estilo.TINTA, k * 0.2, k * 0.05)


def _salgado(c, k):
    c.elipse((222, 160, 56), k * 0.94, k * 0.7)
    c.elipse((244, 196, 100), k * 0.72, k * 0.42, (0, k * 0.07))
    for dx, dy in ((-0.2, 0.0), (0.04, 0.12), (0.22, -0.02), (-0.04, -0.14)):
        c.elipse((180, 110, 40), k * 0.06, k * 0.06, (dx * k, dy * k))


def _generico(c, k):
    c.rect((190, 160, 110), k * 0.6, k * 0.5)
    c.rect((150, 120, 76), k * 0.6, k * 0.08, (0, k * 0.2))


ICONOS = {"pan": _pan, "café": _cafe, "cafe": _cafe, "bollo": _bollo, "leche": _leche, "arroz": _arroz,
          "feijão": _feijao, "jabón": _jabon, "mango": _mango, "banana": _banana, "tomate": _tomate,
          "yuca": _yuca, "agua": _agua, "refresco": _refresco, "salgado": _salgado}


# Dibuja el icono de `producto` centrado en `pos` dentro de `padre`.
def dibujar_icono(padre, producto, pos, k=0.1, z=-0.004):
    contenedor = Entity(parent=padre, position=(pos[0], pos[1], z))
    Capa(contenedor, z=0).elipse(estilo.COLOR_PANEL, k * 1.18, k * 1.18)
    ICONOS.get(producto, _generico)(Capa(contenedor, z=-0.002), k)
    return contenedor


# Flecha dibujada con formas, apuntando a `direccion`.
def dibujar_flecha(padre, direccion, tono, lado, pos=(0, 0), z=-0.004):
    contenedor = Entity(parent=padre, position=(pos[0], pos[1], z))
    contenedor.rotation_z = ROTACION_FLECHA[direccion]
    c = Capa(contenedor, z=0)
    c.rect(tono, lado * 0.2, lado * 0.46, (0, -lado * 0.14))
    c.forma("triangulo", tono, (lado * 0.62, lado * 0.46), (0, lado * 0.2))
    return contenedor


def dibujar_marca_ok(padre, tono, lado, pos, z=-0.006):
    contenedor = Entity(parent=padre, position=(pos[0], pos[1], z))
    c = Capa(contenedor, z=0)
    c.rect(tono, lado * 0.1, lado * 0.3, (-lado * 0.09, -lado * 0.03), rot=-45)
    c.rect(tono, lado * 0.1, lado * 0.52, (lado * 0.11, lado * 0.04), rot=45)
    return contenedor


def dibujar_cliente(padre, numero, pos, escala=1.0):
    azar = random.Random(numero * 7919 + 13)
    contenedor = Entity(parent=padre, position=(pos[0], pos[1], -0.004), scale=escala)
    c = Capa(contenedor, z=0)
    camisa, piel, pelo = azar.choice(CAMISAS), azar.choice(PIEL), azar.choice(PELO)
    c.forma(modelo_redondeado(0.15, 0.1, 8), camisa, (0.15, 0.1), (0, -0.045))
    c.rect(piel, 0.036, 0.03, (0, 0.012))
    c.elipse(piel, 0.1, 0.1, (0, 0.06))
    c.elipse(pelo, 0.108, 0.07, (0, 0.082))
    c.elipse(estilo.TINTA, 0.012, 0.014, (-0.02, 0.058))
    c.elipse(estilo.TINTA, 0.012, 0.014, (0.02, 0.058))
    c.rect(estilo.TINTA, 0.03, 0.006, (0, 0.036))
    return contenedor
