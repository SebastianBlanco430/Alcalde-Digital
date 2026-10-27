# Comercios sobre el mundo real (Ursina): para cada comercio del catálogo (backend/datos/comercios_semilla.py) un
# puesto visible (toldo de colores, mostrador, letrero con el nombre, producto expuesto) y un dependiente quieto con su
# nombre. Cada comercio es una Interaccion de frontend/economia_mundo.py: «E: Hablar con <dependiente> / comprar» abre
# el PanelTienda; los puestos de trabajo muestran «E: Trabajar en <nombre>». Seu Zé (vendedor_calle) lo pone
# frontend/vendedor_calle.py: aquí solo se le reserva el sitio.
#
# Rendimiento: ningún tornillo es una Entity. Todos los puestos se funden en UNA malla (props_mundo.Malla, normales
# planas y color por vértice, con luz y sombras) y solo hay un Text por letrero y un NPC por dependiente.
# Sin colisión nueva: el decorado no choca con nada; la colocación (frontend/comercios_calculos.py) evita que un
# puesto pise edificios, asfalto, escaleras u obstáculos con la huella de ~2,6 x 2,4 m (gira el puesto o lo corre
# unos metros desde su ancla si hace falta).

import math
import sys

from ursina import Text

from backend.datos.comercios_semilla import CATALOGO_COMERCIOS
from backend.logica.comercios import resolver_comercios
from backend.logica.perfil_economia import perfil_de
from frontend.comercios_calculos import Ocupacion, elegir_puesto, huellas_mercadito
from frontend.componentes import rgb
from frontend.props_mundo import Malla, anillo, caja, icosfera, prisma
from frontend.tienda_calculos import ControlTienda
from frontend.tienda_ui import PanelTienda

INDICE_NPC_BASE = 101            # plan_npc(101 + i): Seu Zé (vendedor_calle) usa el 100 y los peatones el 0-11
PRIORIDAD = 8
Y_ETIQUETA_DEPENDIENTE = 2.0     # m sobre los pies (la cabeza llega a ~1,8)
ESCALA_ETIQUETA_DEPENDIENTE = 5.0
RADIO_PUESTO = 2.4               # m del dependiente a los que se oye la E
RADIO_SEU_ZE = 1.4               # m que se le reservan a Seu Zé
RADIO_PUESTO_OCUPADO = 1.9       # m que un puesto ya colocado reserva a los siguientes
SEGUNDOS_MENSAJE = 2.5
DISTANCIA_CUERPO_ANIMADO = 10.0  # m de la cámara: más lejos el dependiente se queda quieto (el esqueleto cuesta ~0,4 ms)
DISTANCIA_VISIBLE = 35.0         # m de la cámara: más lejos el dependiente se oculta del todo (el puesto sigue a la vista)
INTERVALO_LOD = 0.3              # s entre revisiones de esa distancia
ANCHO_LETRERO = 2.3              # m del tablero (el texto se ajusta a 2,0 m)

# Aspecto de cada puesto: toldo (dos rayas), mostrador (cuerpo y tapa), fondo, tablero del letrero, color de las letras.
ESTILOS = {
    "supermercado": dict(toldo=((46, 160, 90), (250, 246, 232)), cuerpo=(222, 224, 230), tapa=(246, 246, 250),
                         fondo=(238, 232, 214), letrero=(28, 100, 60), letras=(255, 255, 255), piso=(196, 200, 192)),
    "panaderia": dict(toldo=((240, 140, 160), (252, 240, 222)), cuerpo=(190, 134, 88), tapa=(240, 214, 170),
                      fondo=(250, 236, 210), letrero=(150, 70, 60), letras=(255, 236, 200), piso=(214, 196, 170)),
    "lanchonete": dict(toldo=((226, 52, 60), (250, 210, 50)), cuerpo=(250, 196, 40), tapa=(240, 240, 236),
                       fondo=(255, 248, 230), letrero=(200, 40, 45), letras=(255, 232, 110), piso=(206, 192, 170)),
    "bar": dict(toldo=((110, 60, 160), (250, 200, 60)), cuerpo=(72, 46, 38), tapa=(120, 84, 56),
                fondo=(58, 46, 64), letrero=(40, 30, 60), letras=(250, 200, 60), piso=(150, 136, 130)),
    "taller": dict(toldo=((150, 156, 166), (116, 122, 134)), cuerpo=(84, 92, 108), tapa=(150, 154, 160),
                   fondo=(72, 76, 90), letrero=(240, 192, 40), letras=(30, 30, 38), piso=(128, 128, 132),
                   poste=(200, 50, 40)),
    "lan_house": dict(toldo=((50, 130, 230), (30, 40, 96)), cuerpo=(34, 38, 66), tapa=(56, 62, 96),
                      fondo=(26, 30, 54), letrero=(20, 24, 48), letras=(110, 232, 255), piso=(120, 124, 150)),
    "entregas": dict(toldo=((250, 200, 30), (34, 34, 40)), cuerpo=(64, 64, 72), tapa=(210, 210, 216),
                     fondo=(240, 236, 220), letrero=(250, 200, 30), letras=(34, 34, 40), piso=(150, 150, 154)),
    "feirante": dict(toldo=((250, 140, 40), (250, 246, 232)), cuerpo=(150, 104, 66), tapa=(196, 148, 96),
                     fondo=(204, 176, 126), letrero=(60, 120, 40), letras=(255, 255, 255), piso=(214, 190, 150)),
    "tienda_general": dict(toldo=((40, 150, 160), (250, 240, 214)), cuerpo=(122, 90, 62), tapa=(184, 142, 96),
                           fondo=(156, 116, 80), letrero=(96, 60, 40), letras=(250, 230, 170), piso=(190, 170, 140)),
}
ESTILO_POR_DEFECTO = ESTILOS["tienda_general"]
FRUTAS = ((240, 130, 40), (216, 50, 50), (110, 190, 60), (250, 210, 50), (170, 60, 150))
CAJAS_PRODUCTO = ((226, 70, 60), (60, 130, 220), (250, 200, 50), (80, 180, 110), (240, 140, 60), (150, 90, 200))


class _Local:
    """Pincel de un puesto: coordenadas locales (a lo largo del mostrador, altura, hacia el cliente) sobre una Malla."""

    def __init__(self, malla, x, y, z, rumbo):
        self.m, self.x, self.y, self.z, self.rumbo = malla, x, y, z, rumbo
        self.s, self.c = math.sin(math.radians(rumbo)), math.cos(math.radians(rumbo))

    def p(self, da, dy, df):
        return (self.x + self.c * da + self.s * df, self.y + dy, self.z - self.s * da + self.c * df)

    def caja(self, da, dy, df, ancho, alto, fondo, color, giro=0.0, incl=0.0, grad=(0.8, 1.05), ruido=0.0):
        self.m.agregar(caja(), self.p(da, dy, df), (ancho, alto, fondo), self.rumbo + giro, color, grad, ruido, incl)

    def cilindro(self, da, dy, df, diametro, alto, color, lados=8, tope=None, incl=0.0, giro=0.0):
        r = 0.5 if tope is None else 0.5 * tope
        self.m.agregar(prisma(lados, 0.5, r), self.p(da, dy, df), (diametro, alto, diametro), self.rumbo + giro, color,
                       (0.8, 1.05), 0.0, incl)

    def esfera(self, da, dy, df, sx, sy=None, sz=None, color=(255, 255, 255), fino=0, giro=0.0):
        self.m.agregar(icosfera(fino), self.p(da, dy, df), (sx, sx if sy is None else sy, sx if sz is None else sz),
                       self.rumbo + giro, color, (0.85, 1.1))

    def anillo(self, da, dy, df, diametro, alto, color, interior=0.28):
        self.m.agregar(anillo(12, 0.5, interior), self.p(da, dy, df), (diametro, alto, diametro), 0, color, (0.75, 1.0))


def _mezcla(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


# -- Estructura común --------------------------------------------------------------------------------


def _estructura(L, e, con_toldo=True, mostrador=(0.0, 2.5), estantes=True):
    # piso, postes, toldo a rayas con volante, fondo con estantes y mostrador; (da, ancho) del mostrador
    a, b = e["toldo"]
    poste = e.get("poste", (110, 80, 56))
    L.caja(0, 0.0, 0.1, 2.9, 0.3, 2.7, e["piso"], grad=(0.85, 1.0), ruido=0.1)                   # losa (tapa el desnivel)
    for da in (-1.25, 1.25):
        L.cilindro(da, -0.1, 1.22, 0.07, 2.8, poste, 6)
        L.cilindro(da, -0.1, -0.98, 0.07, 3.15, poste, 6)
    if con_toldo:
        for k in range(7):
            L.caja(-1.2 + k * 0.4, 2.88, 0.12, 0.4, 0.05, 2.58, (a, b)[k % 2], incl=8.0, grad=(0.9, 1.05))
        for k in range(7):                                                                         # volante en onda
            alto = 0.17 if k % 2 else 0.11
            L.caja(-1.2 + k * 0.4, 2.65 - alto / 2 + 0.06, 1.4, 0.4, alto, 0.03, (b, a)[k % 2])
    L.caja(0, 1.475, -1.02, 2.7, 3.15, 0.06, e["fondo"], grad=(0.9, 1.05))                            # pared del fondo
    if estantes:
        for y in (1.0, 1.5, 2.0):
            L.caja(0, y, -0.86, 2.5, 0.04, 0.3, _mezcla(e["cuerpo"], (255, 255, 255), 0.15))
    da_m, ancho_m = mostrador
    L.caja(da_m, 0.45, 0.85, ancho_m, 0.9, 0.62, e["cuerpo"])
    L.caja(da_m, 0.55, 1.16, ancho_m - 0.2, 0.5, 0.02, a)                                          # frente de color
    L.caja(da_m, 0.93, 0.85, ancho_m + 0.1, 0.06, 0.76, e["tapa"], grad=(0.9, 1.05))


def _letrero_malla(L, e):
    # tablero con dos soportes sobre el toldo; las letras van aparte (un Text)
    L.caja(0, 3.08, 1.33, ANCHO_LETRERO, 0.46, 0.06, e["letrero"], grad=(0.95, 1.0))
    L.caja(0, 3.08, 1.295, ANCHO_LETRERO + 0.1, 0.52, 0.03, (255, 255, 255), grad=(0.95, 1.0))      # marco claro
    for da in (-1.0, 1.0):
        L.cilindro(da, 2.68, 1.33, 0.04, 0.22, (90, 70, 52), 6)


def _estante(L, y, n, producto, ancho=2.2):
    for k in range(n):
        producto(L, -ancho / 2 + (k + 0.5) * ancho / n, y, k)


# -- Producto expuesto de cada puesto -----------------------------------------------------------------


def _surtido_supermercado(L, e):
    def caja_cereal(L, da, y, k):
        L.caja(da, y + 0.15, -0.86, 0.2, 0.28, 0.12, CAJAS_PRODUCTO[(k + int(y * 3)) % 6])
        L.caja(da, y + 0.19, -0.79, 0.15, 0.1, 0.01, (255, 255, 255))
    def lata(L, da, y, k):
        L.cilindro(da, y + 0.02, -0.86, 0.11, 0.17, CAJAS_PRODUCTO[(k * 2 + 1) % 6], 8)
        L.cilindro(da, y + 0.19, -0.86, 0.1, 0.012, (200, 204, 210), 8)
    _estante(L, 1.0, 8, caja_cereal)
    _estante(L, 1.5, 12, lata)
    _estante(L, 2.0, 8, caja_cereal)
    for da in (-0.55, 0.45):                                                                       # cestas rojas con fruta
        L.caja(da, 1.02, 0.85, 0.5, 0.16, 0.34, (214, 50, 50))
        for j in range(5):
            L.esfera(da - 0.16 + j * 0.08, 1.14, 0.85 + 0.06 * (j % 2), 0.11, color=FRUTAS[j % 5])
    L.caja(1.0, 1.08, 0.78, 0.34, 0.2, 0.28, (50, 54, 66))                                         # caja registradora
    L.caja(1.0, 1.22, 0.7, 0.26, 0.14, 0.02, (110, 220, 160), incl=-15)
    L.cilindro(-0.9, 1.04, 0.62, 0.3, 0.06, (230, 200, 70), 12)                                    # cartel de oferta


def _surtido_panaderia(L, e):
    pan = (196, 130, 66)
    def hogaza(L, da, y, k):
        L.esfera(da, y + 0.09, -0.86, 0.3, 0.17, 0.22, (pan[0] + 12 * (k % 3), pan[1] + 8 * (k % 2), pan[2]), 0)
    for y in (1.0, 1.5, 2.0):
        _estante(L, y, 6, hogaza)
    for k in range(5):                                                                             # hogazas en el mostrador
        L.esfera(-0.9 + k * 0.38, 1.04, 0.78 + 0.1 * (k % 2), 0.32, 0.17, 0.2, (pan[0] + 10 * k % 30, pan[1], pan[2]), 0)
    L.caja(0.8, 1.05, 0.9, 0.55, 0.26, 0.34, (150, 104, 66))                                       # cesta de baguettes
    for k in range(5):
        L.cilindro(0.62 + k * 0.09, 1.1, 0.88, 0.075, 0.7, (214, 160, 84), 6, incl=-18)
    for k in range(4):                                                                             # cruasanes
        L.esfera(-0.2 + k * 0.17, 1.0 + 0.04, 0.98, 0.16, 0.07, 0.1, (226, 170, 80), giro=20 * (k % 2))
    L.caja(-0.05, 1.12, 0.7, 0.8, 0.02, 0.2, (255, 255, 255), grad=(1.0, 1.0))                     # bandeja blanca


def _surtido_lanchonete(L, e):
    for k in range(3):                                                                             # hamburguesas
        da = -0.8 + k * 0.38
        L.esfera(da, 1.05, 0.85, 0.3, 0.12, 0.3, (214, 156, 80), 0)
        L.cilindro(da, 1.1, 0.85, 0.28, 0.05, (92, 50, 34), 12)
        L.caja(da, 1.155, 0.85, 0.31, 0.02, 0.31, (110, 190, 60))
        L.esfera(da, 1.2, 0.85, 0.3, 0.14, 0.3, (226, 170, 90), 0)
    for k in range(4):                                                                             # vasos
        L.cilindro(0.4 + k * 0.14, 0.96, 0.85, 0.1, 0.18, (240, 240, 240) if k % 2 else (226, 52, 60), 8, tope=0.8)
    L.caja(-0.95, 0.9, -0.65, 0.85, 1.8, 0.6, (140, 190, 240))                                     # nevera
    L.caja(-0.95, 1.82, -0.65, 0.88, 0.06, 0.62, (240, 244, 250))
    L.caja(-0.95, 1.1, -0.34, 0.5, 0.02, 0.01, (255, 255, 255))
    L.caja(0.35, 1.7, -0.98, 1.4, 0.7, 0.04, (34, 34, 40))                                          # pizarra del menú
    for k, (ancho, tono) in enumerate(((1.1, (255, 232, 110)), (0.9, (255, 255, 255)), (1.0, (255, 160, 90)))):
        L.caja(0.35 - (1.1 - ancho) / 2, 1.88 - k * 0.17, -0.95, ancho, 0.05, 0.01, tono)
    L.caja(0.9, 1.0, -0.72, 0.5, 0.1, 0.4, (70, 70, 76))                                            # plancha
    L.caja(0.9, 0.99, -0.72, 0.42, 0.02, 0.32, (24, 24, 28))


def _surtido_bar(L, e):
    def botella(L, da, y, k):
        tono = ((40, 120, 60), (170, 100, 30), (190, 220, 235), (130, 40, 50))[k % 4]
        L.cilindro(da, y + 0.02, -0.86, 0.09, 0.2, tono, 8)
        L.cilindro(da, y + 0.22, -0.86, 0.04, 0.12, tono, 8)
    for y in (1.0, 1.5, 2.0):
        _estante(L, y, 11, botella)
    for da in (-0.55, 0.55):                                                                       # taburetes
        L.cilindro(da, 0.0, 1.62, 0.07, 0.62, (60, 60, 68), 6)
        L.cilindro(da, 0.58, 1.62, 0.34, 0.07, (190, 50, 60), 12)
        L.cilindro(da, 0.0, 1.62, 0.3, 0.03, (60, 60, 68), 12)
    for k in range(4):                                                                             # vasos y jarra
        L.cilindro(-0.9 + k * 0.17, 0.96, 0.85, 0.1, 0.16, (230, 236, 240), 8, tope=0.85)
    L.cilindro(0.6, 0.96, 0.85, 0.24, 0.3, (240, 190, 60), 10)
    L.cilindro(0.6, 1.2, 0.85, 0.25, 0.06, (255, 255, 255), 10)
    L.caja(-0.1, 1.7, -0.98, 0.9, 0.5, 0.04, (24, 22, 30))                                          # espejo oscuro
    L.caja(-0.1, 1.7, -0.95, 0.78, 0.38, 0.01, (120, 160, 190))


def _surtido_taller(L, e):
    L.caja(0.1, 1.7, -0.98, 2.3, 1.3, 0.04, (60, 64, 76))                                           # tablero de herramientas
    for k in range(7):                                                                             # llaves colgadas
        da = -0.95 + k * 0.3
        L.caja(da, 1.75 - 0.06 * (k % 3), -0.94, 0.045, 0.34 + 0.05 * (k % 2), 0.02, (190, 196, 206), grad=(0.9, 1.1))
        L.cilindro(da, 1.9 - 0.06 * (k % 3), -0.94, 0.1, 0.02, (190, 196, 206), 8, incl=90)
    L.caja(0.15, 1.3, -0.94, 1.8, 0.02, 0.1, (150, 90, 40))
    for k in range(3):                                                                             # herramientas sobre el banco
        L.caja(0.45 + k * 0.4, 0.99, 0.8, 0.3, 0.03, 0.06, (190, 196, 206), giro=20 * k)
    L.caja(-0.1, 1.0, 0.95, 0.4, 0.2, 0.24, (214, 50, 40))                                          # caja de herramientas
    L.caja(-0.1, 1.13, 0.95, 0.22, 0.03, 0.04, (60, 60, 66))
    L.cilindro(0.95, 0.96, 0.7, 0.06, 0.22, (120, 70, 40), 6)                                       # martillo
    L.caja(0.95, 1.2, 0.7, 0.16, 0.07, 0.07, (80, 84, 92))
    for k in range(3):                                                                             # pila de neumáticos
        L.anillo(-1.0, 0.0 + 0.2 * k, 1.05, 0.7, 0.2, (28, 28, 32), 0.7)
    L.cilindro(-1.0, 0.0, 1.05, 0.34, 0.5, (150, 150, 158), 8)
    L.cilindro(1.0, 0.0, -0.35, 0.28, 0.4, (40, 80, 170), 8)                                        # bidón de aceite
    L.cilindro(1.0, 0.4, -0.35, 0.08, 0.06, (230, 200, 40), 8)


def _surtido_lan_house(L, e):
    for k in range(3):                                                                             # monitores
        da = -0.8 + k * 0.8
        L.caja(da, 1.28, 0.78, 0.5, 0.34, 0.04, (16, 18, 24))
        L.caja(da, 1.28, 0.8, 0.44, 0.28, 0.01, ((90, 200, 255), (255, 120, 190), (120, 255, 170))[k], grad=(1.0, 1.0))
        L.cilindro(da, 0.96, 0.78, 0.06, 0.15, (50, 54, 66), 6)
        L.caja(da, 0.97, 0.9, 0.2, 0.01, 0.1, (50, 54, 66))
        L.caja(da, 0.97, 1.06, 0.4, 0.025, 0.14, (30, 32, 40))                                      # teclado
        L.caja(da + 0.28, 0.975, 1.06, 0.06, 0.03, 0.1, (30, 32, 40))
    L.caja(0, 0.55, 1.19, 2.3, 0.06, 0.02, (110, 232, 255), grad=(1.0, 1.0))                        # neón del mostrador
    for k in range(6):                                                                             # routers y cajas en el estante
        L.caja(-0.95 + k * 0.38, 1.1, -0.86, 0.22, 0.12, 0.2, (40, 44, 58))
        L.caja(-0.95 + k * 0.38, 1.04, -0.75, 0.03, 0.03, 0.03, (120, 255, 150), grad=(1.0, 1.0))
        L.caja(-0.95 + k * 0.38, 1.62, -0.86, 0.24, 0.18, 0.18, CAJAS_PRODUCTO[k % 6])
    for k in range(4):                                                                             # audífonos colgados
        L.caja(-0.9 + k * 0.5, 1.92, -0.94, 0.2, 0.02, 0.02, (30, 30, 36))
        L.esfera(-1.0 + k * 0.5, 1.84, -0.94, 0.07, 0.1, 0.05, (30, 30, 36), 0)
        L.esfera(-0.8 + k * 0.5, 1.84, -0.94, 0.07, 0.1, 0.05, (30, 30, 36), 0)


def _moto(L, da, df, tono, giro=0.0):
    c = lambda a, y, f, *r, **k: L.caja(da + a * math.cos(math.radians(giro)) + f * math.sin(math.radians(giro)), y,
                                         df - a * math.sin(math.radians(giro)) + f * math.cos(math.radians(giro)), *r,
                                         giro=giro, **k)
    for f in (-0.5, 0.5):                                                                          # ruedas
        L.esfera(da + f * math.sin(math.radians(giro)), 0.3, df + f * math.cos(math.radians(giro)),
                 0.09, 0.6, 0.6, (24, 24, 28), giro=giro)
    c(0, 0.5, -0.05, 0.16, 0.2, 0.62, tono)                                                         # depósito y carenado
    c(0, 0.42, -0.35, 0.2, 0.1, 0.5, (30, 30, 36))                                                  # asiento
    c(0, 0.6, 0.38, 0.08, 0.44, 0.1, (150, 154, 162))                                               # horquilla
    c(0, 0.82, 0.42, 0.5, 0.04, 0.05, (30, 30, 36))                                                 # manillar
    c(0, 0.72, 0.5, 0.14, 0.12, 0.08, (255, 244, 180), grad=(1.0, 1.0))                             # faro
    c(0, 0.62, -0.55, 0.14, 0.1, 0.12, (214, 50, 40))
    c(0.15, 0.3, -0.3, 0.05, 0.14, 0.34, (170, 170, 176))                                           # escape


def _surtido_entregas(L, e):
    _moto(L, -0.85, 0.15, (214, 50, 40))
    _moto(L, 0.85, 0.15, (50, 110, 210), giro=8)
    L.esfera(0.1, 1.06, 0.8, 0.3, 0.26, 0.3, (250, 200, 30), 0)                                     # casco sobre el mostrador
    L.caja(0.1, 1.04, 0.95, 0.34, 0.04, 0.06, (34, 34, 40))
    L.caja(0.1, 1.15, -0.98, 1.0, 0.7, 0.03, (250, 246, 232))                                       # mapa en la pared
    for k in range(4):
        L.caja(-0.2 + k * 0.28, 1.15, -0.95, 0.04, 0.5, 0.01, ((214, 50, 40), (50, 110, 210))[k % 2])
    for k in range(3):                                                                             # paquetes
        L.caja(-0.9 + k * 0.15, 1.2 - 0.15, -0.85, 0.28, 0.2, 0.28, (190, 150, 100))


def _surtido_feirante(L, e):
    for k, da in enumerate((-0.85, 0.0, 0.85)):                                                    # cajones de fruta
        L.caja(da, 1.04, 0.85, 0.62, 0.16, 0.42, (160, 112, 70))
        for j in range(8):
            L.esfera(da - 0.22 + (j % 4) * 0.15, 1.17, 0.74 + (j // 4) * 0.2, 0.15, color=FRUTAS[(k + j) % 5])
    for k in range(3):                                                                             # racimos colgados
        for j in range(4):
            L.esfera(-0.7 + k * 0.7 + j * 0.05, 1.98 - j * 0.02, 1.2, 0.05, 0.2, 0.05, (250, 214, 60), 0, giro=10 * j)
    def verdura(L, da, y, k):
        L.esfera(da, y + 0.1, -0.86, 0.2, 0.2, 0.2, FRUTAS[(k + int(y * 2)) % 5], 0)
    for y in (1.0, 1.5):
        _estante(L, y, 8, verdura)
    L.caja(-1.0, 0.18, -0.55, 0.5, 0.36, 0.4, (170, 120, 70))                                      # cestos en el suelo
    for j in range(5):
        L.esfera(-1.1 + (j % 3) * 0.12, 0.4, -0.6 + (j % 2) * 0.12, 0.15, color=FRUTAS[(j + 2) % 5])
    L.caja(1.0, 0.18, -0.55, 0.5, 0.36, 0.4, (170, 120, 70))
    for j in range(5):
        L.esfera(0.9 + (j % 3) * 0.12, 0.4, -0.6 + (j % 2) * 0.12, 0.15, color=FRUTAS[(j + 4) % 5])


def _mochila(L, da, y, tono):
    oscuro = _mezcla(tono, (0, 0, 0), 0.35)
    L.caja(da, y, -0.9, 0.3, 0.4, 0.14, tono, grad=(0.85, 1.1))
    L.caja(da, y - 0.08, -0.82, 0.2, 0.16, 0.05, oscuro)
    L.caja(da, y + 0.21, -0.9, 0.12, 0.04, 0.05, oscuro)
    L.caja(da - 0.09, y + 0.0, -0.97, 0.03, 0.34, 0.02, oscuro)
    L.caja(da + 0.09, y + 0.0, -0.97, 0.03, 0.34, 0.02, oscuro)


def _surtido_tienda_general(L, e):
    for k, tono in enumerate(((220, 70, 60), (60, 120, 210), (240, 180, 50), (70, 160, 100), (150, 80, 190))):
        _mochila(L, -0.95 + k * 0.48, 1.62, tono)                                                  # mochilas colgadas
    for k, tono in enumerate(((60, 120, 210), (220, 70, 60), (70, 160, 100))):
        _mochila(L, -0.7 + k * 0.7, 1.05 + 0.0, tono)
    for da in (0.95, 1.25):                                                                        # botijones de gas
        L.cilindro(da, 0.0, -0.45, 0.34, 0.62, (232, 124, 40), 10)
        L.esfera(da, 0.62, -0.45, 0.33, 0.18, 0.33, (232, 124, 40), 0)
        L.cilindro(da, 0.7, -0.45, 0.07, 0.1, (60, 60, 66), 6)
    L.caja(-0.95, 0.2, -0.5, 0.5, 0.4, 0.42, (150, 104, 66))                                       # cesto con balones
    for j, tono in enumerate(((250, 250, 250), (240, 130, 40), (60, 120, 210))):
        L.esfera(-1.05 + j * 0.12, 0.5, -0.5 + 0.04 * (j % 2), 0.24, color=tono, fino=1)
    for k in range(3):                                                                             # linternas y libretas
        L.cilindro(-0.9 + k * 0.17, 0.96, 0.85, 0.07, 0.2, (240, 200, 40), 8, incl=90, giro=k * 14)
        L.caja(0.1 + k * 0.2, 0.99, 0.82, 0.16, 0.03, 0.22, ((60, 120, 210), (220, 70, 60), (70, 160, 100))[k])
    L.cilindro(0.95, 0.0, 0.7, 0.04, 1.4, (150, 104, 66), 6, incl=-8)                              # escoba y pala apoyadas
    L.caja(1.18, 0.25, 0.7, 0.14, 0.3, 0.02, (160, 160, 168))


SURTIDOS = {
    "supermercado": _surtido_supermercado, "panaderia": _surtido_panaderia, "lanchonete": _surtido_lanchonete,
    "bar": _surtido_bar, "taller": _surtido_taller, "lan_house": _surtido_lan_house,
    "entregas": _surtido_entregas, "feirante": _surtido_feirante, "tienda_general": _surtido_tienda_general,
}
# Ajustes de la estructura por puesto (toldo, mostrador (da, ancho), estantes).
ESTRUCTURA = {
    "taller": dict(mostrador=(0.45, 1.5), estantes=False),
    "entregas": dict(mostrador=(0.0, 0.9), estantes=False),
    "feirante": dict(mostrador=(0.0, 2.5), estantes=True),
}


# Dibuja un puesto en la malla: (x, z) es donde está de pie el dependiente y `rumbo` hacia donde mira (el cliente).
def dibujar_puesto(malla, comercio_id, x, y, z, rumbo):
    e = ESTILOS.get(comercio_id, ESTILO_POR_DEFECTO)
    L = _Local(malla, x, y, z, rumbo)
    _estructura(L, e, **ESTRUCTURA.get(comercio_id, {}))
    _letrero_malla(L, e)
    SURTIDOS.get(comercio_id, _surtido_tienda_general)(L, e)
    return L


# -- Letreros y dependiente -------------------------------------------------------------------------------


def _poner_letrero(escena, comercio, x, y, z, rumbo):
    e = ESTILOS.get(comercio.id, ESTILO_POR_DEFECTO)
    L = _Local(Malla(), x, y, z, rumbo)
    texto = Text(comercio.nombre, parent=escena, origin=(0, 0), position=L.p(0, 3.08, 1.37), rotation_y=rumbo + 180,
                 scale=6.0, color=rgb(e["letras"]))
    try:
        ancho = texto.width
        if ancho > 2.0:
            texto.scale = 6.0 * 2.0 / ancho                  # el nombre cabe siempre en el tablero
    except Exception:
        pass
    texto.ignore = True
    return texto


# Modelos con ropa cotidiana de barrio para un dependiente: «periodista» (camisa) y «brasilena» (top y short). Se
# descartan el smoking (traje de gala) y el «ciudadano» (torso al aire; su camiseta añadida se pega a la piel y
# sigue pareciendo torso desnudo).
MODELOS_DEPENDIENTE = ("periodista.glb", "brasilena.glb")
ARCHIVO_DEPENDIENTA = "brasilena.glb"        # el único modelo femenino


# ¿El nombre del dependiente es de mujer? («Dona X» en el catálogo); decide el modelo para que nombre y aspecto casen.
def es_dependienta(nombre):
    return str(nombre or "").strip().lower().startswith(("dona ", "dona\u00a0"))


# Índice de NPC >= `minimo` con ropa cotidiana (ver MODELOS_DEPENDIENTE). `mujer` True/False/None filtra el modelo
# por género (None = cualquiera de los dos). Determinista; `usados` evita repetir la cara entre comercios.
def indice_vestido(minimo, usados=(), mujer=None):
    from frontend import npc_calculos as nc
    from frontend.peatones import SEMILLA
    from frontend.peatones_calculos import aspecto_peaton
    indice = minimo
    while True:
        plan = nc.plan_npc(indice, SEMILLA, aspecto_peaton(indice, SEMILLA))
        archivo = plan["archivo"]
        if mujer is None:
            genero_ok = True
        else:
            genero_ok = (archivo == ARCHIVO_DEPENDIENTA) == bool(mujer)
        if indice not in usados and archivo in MODELOS_DEPENDIENTE and genero_ok:
            return indice
        indice += 1


def _crear_dependiente(escena, indice, nombre, x, z, rumbo, crear_npc=None):
    from frontend.npc_modelo import crear_npc as fabrica
    from frontend.peatones import ROPA, SEMILLA
    from frontend.peatones_calculos import aspecto_peaton, rasgos_peaton
    from frontend.componentes import destruir_arbol
    from frontend.piezas import etiqueta, silenciar
    fabrica = crear_npc or fabrica
    npc = fabrica(indice, SEMILLA, aspecto_peaton(indice, SEMILLA), rasgos_peaton(indice, SEMILLA),
                  ROPA[indice % len(ROPA)], parent=escena)
    npc.aro.enabled = False
    npc.nombre = nombre
    try:
        y = min(npc.etiqueta.y, Y_ETIQUETA_DEPENDIENTE)      # más baja y pequeña: no tapa el letrero ni el producto
        destruir_arbol(npc.etiqueta)
        npc.etiqueta = silenciar(etiqueta(nombre, parent=npc, y=y, scale=ESCALA_ETIQUETA_DEPENDIENTE))
    except Exception as error:
        print(f"[assets] comercio: no se pudo poner el nombre ({error})", file=sys.stderr)
    npc.suelo = escena._mundo.altura
    npc.automatico = False          # como los peatones: quieto y sin animar el cuerpo cada frame (rendimiento)
    npc.colocar(x, z)
    npc.fijar_rumbo(rumbo)
    return npc


# -- Interacción ----------------------------------------------------------------------------------------


class ComercioMundo:
    """Un comercio como Interaccion (frontend/economia_mundo.py): tienda -> abre el PanelTienda; puesto de trabajo -> trabajar."""

    prioridad = PRIORIDAD

    def __init__(self, escena, comercio, x, z, rumbo, npc=None, panel=None):
        self._escena = escena
        self.comercio = comercio
        self.x, self.z, self.rumbo = float(x), float(z), float(rumbo)
        self.npc = npc
        self.panel = panel
        self.nombre = comercio.npc or comercio.nombre
        self._mensaje = None
        self._t_mensaje = 0.0
        self._lejos = False
        self._t_lod = 0.0
        self._acotar_animacion()

    # El LOD del NPC (npc_calculos) anima el cuerpo hasta 45 m; un dependiente quieto no lo necesita tan lejos: con
    # varios puestos a la vista costaba más de 1 ms. Se envuelve su congelado: lejos queda quieto, cerca anima.
    def _acotar_animacion(self):
        original = getattr(self.npc, "_ajustar_cuerpo", None)
        if not callable(original):
            return
        self.npc._ajustar_cuerpo = lambda congelar: original(bool(congelar) or self._lejos)
        cara = getattr(self.npc, "_animar_rostro", None)
        if callable(cara):
            self.npc._animar_rostro = lambda: bool(cara()) and not self._lejos       # la cara también, lejos, quieta

    def _revisar_lod(self, dt):
        self._t_lod -= dt
        if self._t_lod > 0 or self.npc is None:
            return
        self._t_lod = INTERVALO_LOD
        try:
            from ursina import camera
            distancia = (camera.world_position - self.npc.world_position).length()
        except Exception:
            return
        lejos = distancia > DISTANCIA_CUERPO_ANIMADO
        if lejos != self._lejos:
            self._lejos = lejos
            if hasattr(self.npc, "_ajustar_cuerpo"):
                self.npc._ajustar_cuerpo(lejos)
        visible = distancia <= DISTANCIA_VISIBLE
        if bool(self.npc.enabled) != visible:        # idempotente: también corrige si la escena lo reactivó
            self.npc.enabled = visible

    def _cerca(self, x, z):
        return math.hypot(x - self.x, z - self.z) <= RADIO_PUESTO

    def texto_aviso(self):
        if self.comercio.tipo == "puesto_trabajo":
            return f"E: Trabajar en {self.comercio.nombre}"
        return f"E: Hablar con {self.nombre} / comprar"

    def aviso(self, jugador, x, z):
        if not self._cerca(x, z):
            return None
        return self._mensaje or self.texto_aviso()

    def usar(self, jugador, economia):
        if not self._cerca(jugador.x, jugador.z):
            return False
        if self.comercio.tipo == "puesto_trabajo":
            return self._trabajar(jugador, economia)
        perfil = perfil_de(jugador, economia.catalogo)
        control = ControlTienda(perfil, self.comercio, economia.catalogo)
        self.panel.comercio_actual = self
        if not economia.abrir_modal(self.panel, control):
            return False
        return True

    # El puesto lo lleva la economía de trabajos (frontend/trabajo_mundo.py): economia.al_trabajar(jugador, trabajo_id).
    def _trabajar(self, jugador, economia):
        al_trabajar = getattr(economia, "al_trabajar", None)
        if callable(al_trabajar) and self.comercio.trabajo_id:
            al_trabajar(jugador, self.comercio.trabajo_id)
            return True
        self._mensaje = "Aquí aún no hay turnos disponibles."
        self._t_mensaje = SEGUNDOS_MENSAJE
        return True

    def actualizar(self, dt):
        if self._mensaje:
            self._t_mensaje -= dt
            if self._t_mensaje <= 0:
                self._mensaje = None
        self._revisar_lod(dt)
        camara = getattr(self._escena, "camara", None)
        ignorar = getattr(camara, "ignorar", None)
        if self.npc is not None and isinstance(ignorar, list) and self.npc not in ignorar:
            ignorar.append(self.npc)                # la cámara no se acerca al dependiente

    def destruir(self):
        from frontend.componentes import destruir_arbol
        if self.npc is not None:
            destruir_arbol(self.npc)
            self.npc = None


# Coloca todos los comercios del catálogo (menos el vendedor de la calle, que lleva vendedor_calle.py) sobre el
# mundo real y los registra en la economía. Devuelve la lista de ComercioMundo.
def instalar(economia, comercios=None, crear_npc=None):
    escena = economia.escena
    mundo = escena._mundo
    resueltos = resolver_comercios(mundo, comercios if comercios is not None else CATALOGO_COMERCIOS)
    zona = next((z for z in mundo.zonas() if z.tipo == "mercado"), None)
    ocupacion = Ocupacion(mundo, cajas=huellas_mercadito(zona) if zona is not None else ())
    for comercio, (x, z, _rumbo) in resueltos:
        if comercio.tipo == "vendedor_calle":
            ocupacion.agregar_circulo(x, z, RADIO_SEU_ZE)
    panel = PanelTienda(None, titulo_fn=lambda: _titulo(panel), parent=escena.hud)
    panel.comercio_actual = None
    economia.modales.append(panel)
    malla = Malla()
    puestos = []
    suelo = mundo.altura
    for orden, (comercio, (x, z, rumbo)) in enumerate(resueltos):
        if comercio.tipo == "vendedor_calle":
            continue
        px, pz, prumbo, _v = elegir_puesto(ocupacion, x, z, rumbo)
        ocupacion.agregar_circulo(px, pz, RADIO_PUESTO_OCUPADO)
        puestos.append((orden, comercio, px, pz, prumbo))
    for orden, comercio, px, pz, prumbo in puestos:
        dibujar_puesto(malla, comercio.id, px, suelo(px, pz), pz, prumbo)
    registrados = []
    usados = {INDICE_NPC_BASE - 1}                      # el 100 es Seu Zé
    mesh = malla.mesh()
    if mesh is not None:
        from frontend.piezas import pieza
        economia.puestos_malla = pieza(parent=escena, model=mesh, name="comercios_puestos")
    for orden, comercio, px, pz, prumbo in puestos:
        _poner_letrero(escena, comercio, px, suelo(px, pz), pz, prumbo)
        indice = indice_vestido(INDICE_NPC_BASE + orden, usados, es_dependienta(comercio.npc))
        usados.add(indice)
        npc = _crear_dependiente(escena, indice, comercio.npc or comercio.nombre, px, pz, prumbo, crear_npc)
        registrados.append(economia.registrar(ComercioMundo(escena, comercio, px, pz, prumbo, npc, panel)))
    economia.comercios_mundo = registrados
    return registrados


def _titulo(panel):
    actual = getattr(panel, "comercio_actual", None)
    if actual is None:
        return ("", "")
    return (actual.comercio.nombre, actual.comercio.npc or "")
