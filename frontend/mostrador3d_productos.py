# Mallas de los productos y del dinero del MOSTRADOR 3D (frontend/mostrador3d_escena.py), por código con los sólidos de
# props_mundo en una Malla con color por vértice (sin ursina al construir: se prueba sin ventana). Cada producto mide
# unos 12 cm y se apoya en y = 0; `forma` y `color` salen de backend/datos/mostrador3d_locales.json.
# Billetes y monedas: rectángulos y discos de colores GENÉRICOS (no copian los diseños reales); el valor se escribe
# encima con texto en la escena («R$ 5», «R$ 0,25»).

import math

from frontend.props_mundo import Malla, anillo, caja, icosfera, prisma

BLANCO = (244, 242, 236)
TAPA = (60, 140, 220)
# Billetes: color de fondo por valor en centavos (paleta propia del juego).
COLOR_BILLETE = {200: (120, 196, 176), 500: (176, 150, 214), 1000: (226, 120, 104), 2000: (226, 196, 92),
                 5000: (232, 150, 84), 10000: (96, 150, 214), 20000: (170, 172, 180)}
PLATA, DORADO = (196, 200, 208), (214, 176, 84)
LARGO_BILLETE, ANCHO_BILLETE = 0.15, 0.072


def _pan(m, c):
    m.agregar(icosfera(1), (0, 0.035, 0), (0.15, 0.07, 0.07), 0, c, (0.8, 1.1))
    for dx in (-0.03, 0.01, 0.05):
        m.agregar(caja(), (dx, 0.068, 0), (0.008, 0.006, 0.05), 25, (238, 206, 140), (1, 1))


def _taza(m, c):
    m.agregar(prisma(14, 0.5, 0.56), (0, 0, 0), (0.08, 0.09, 0.08), 0, BLANCO)
    m.agregar(prisma(14), (0, 0.075, 0), (0.07, 0.01, 0.07), 0, c, (1, 1))
    m.agregar(anillo(10, 0.5, 0.32), (0.05, 0.02, 0), (0.05, 0.012, 0.05), 0, BLANCO, (1, 1), 0, 90)


def _bollo(m, c):
    m.agregar(icosfera(1), (0, 0.03, 0), (0.1, 0.065, 0.1), 0, c, (0.75, 1.1))
    m.agregar(icosfera(0), (0, 0.06, 0), (0.05, 0.015, 0.05), 0, BLANCO, (1, 1))


def _carton(m, c):
    m.agregar(caja(), (0, 0.08, 0), (0.07, 0.16, 0.07), 0, c, (0.85, 1.05))
    m.agregar(caja(), (0, 0.09, -0.036), (0.06, 0.06, 0.003), 0, TAPA, (1, 1))
    m.agregar(prisma(4, 0.5, 0.0), (0, 0.16, 0), (0.07, 0.03, 0.07), 45, c, (1, 1))


def _bolsa(m, c):
    m.agregar(caja(), (0, 0.06, 0), (0.1, 0.12, 0.05), 0, c, (0.85, 1.05), 0.06)
    m.agregar(caja(), (0, 0.07, -0.026), (0.07, 0.04, 0.003), 0, (214, 60, 52), (1, 1))


def _caja_producto(m, c):
    m.agregar(caja(), (0, 0.025, 0), (0.09, 0.05, 0.06), 0, c, (0.85, 1.05))
    m.agregar(caja(), (0, 0.03, -0.031), (0.05, 0.02, 0.003), 0, BLANCO, (1, 1))


def _fruta(m, c):
    m.agregar(icosfera(1), (0, 0.045, 0), (0.09, 0.085, 0.09), 0, c, (0.8, 1.1))
    m.agregar(caja(), (0, 0.092, 0), (0.008, 0.02, 0.008), 0, (90, 70, 40), (1, 1))
    m.agregar(icosfera(0), (0.015, 0.095, 0), (0.03, 0.008, 0.015), 0, (70, 150, 60), (1, 1))


def _banana(m, c):
    for k in range(4):
        a = math.radians(-30 + 20 * k)
        m.agregar(icosfera(1), (0.06 * math.sin(a), 0.03 + 0.012 * k, -0.02 * math.cos(a)),
                  (0.035, 0.035, 0.14), 20 * k - 30, c, (0.8, 1.1))
    m.agregar(caja(), (0, 0.06, 0.06), (0.03, 0.02, 0.03), 0, (110, 90, 50), (1, 1))


def _raiz(m, c):
    for k, dz in enumerate((-0.025, 0.025)):
        m.agregar(prisma(8, 0.5, 0.25), (0.08, 0.025 + 0.01 * k, dz), (0.05, 0.18, 0.05), -90, c, (0.8, 1.1), 0.1, 90)


def _botella(m, c):
    m.agregar(prisma(12), (0, 0, 0), (0.06, 0.13, 0.06), 0, c, (0.9, 1.15))
    m.agregar(prisma(12, 0.5, 0.25), (0, 0.13, 0), (0.06, 0.04, 0.06), 0, c, (1, 1.1))
    m.agregar(prisma(10), (0, 0.17, 0), (0.025, 0.02, 0.025), 0, TAPA, (1, 1))
    m.agregar(prisma(12), (0, 0.05, 0), (0.062, 0.04, 0.062), 0, BLANCO, (1, 1))


def _lata(m, c):
    m.agregar(prisma(14), (0, 0, 0), (0.065, 0.12, 0.065), 0, c, (0.85, 1.1))
    m.agregar(prisma(14), (0, 0.12, 0), (0.06, 0.006, 0.06), 0, PLATA, (1, 1))
    m.agregar(prisma(14), (0, 0.04, 0), (0.066, 0.025, 0.066), 0, BLANCO, (1, 1))


def _coxinha(m, c):
    m.agregar(icosfera(1), (0, 0.035, 0), (0.08, 0.07, 0.08), 0, c, (0.8, 1.05))
    m.agregar(prisma(10, 0.5, 0.0), (0, 0.05, 0), (0.07, 0.07, 0.07), 0, c, (0.9, 1.1))


FORMAS = {"pan": _pan, "taza": _taza, "bollo": _bollo, "carton": _carton, "bolsa": _bolsa, "caja": _caja_producto,
          "fruta": _fruta, "banana": _banana, "raiz": _raiz, "botella": _botella, "lata": _lata, "coxinha": _coxinha}


def malla_producto(producto):
    """Malla de un producto ({forma, color}); forma desconocida = una caja de su color."""
    m = Malla()
    FORMAS.get(producto.get("forma"), _caja_producto)(m, tuple(producto.get("color", BLANCO)))
    return m


def malla_cajon(madera=(150, 104, 64), ancho=0.3, fondo=0.22, alto=0.08):
    """Cajón de madera abierto donde se exponen los productos (listones con hueco)."""
    m = Malla()
    m.agregar(caja(), (0, 0.006, 0), (ancho, 0.012, fondo), 0, madera, (0.8, 1))
    for dz, sx, sz in ((-fondo / 2, ancho, 0.012), (fondo / 2, ancho, 0.012)):
        m.agregar(caja(), (0, alto / 2, dz), (sx, alto, sz), 0, madera, (0.8, 1.05), 0.08)
    for dx in (-ancho / 2, ancho / 2):
        m.agregar(caja(), (dx, alto / 2, 0), (0.012, alto, fondo), 0, madera, (0.8, 1.05), 0.08)
    return m


def malla_billete(valor):
    """Billete plano (x = largo, z = ancho, y = grosor) con marco claro y un óvalo en el centro."""
    c = COLOR_BILLETE.get(valor, (200, 200, 200))
    claro = tuple(min(255, int(v * 1.18)) for v in c)
    m = Malla()
    m.agregar(caja(), (0, 0.001, 0), (LARGO_BILLETE, 0.002, ANCHO_BILLETE), 0, claro, (1, 1))
    m.agregar(caja(), (0, 0.0022, 0), (LARGO_BILLETE - 0.012, 0.0012, ANCHO_BILLETE - 0.012), 0, c, (1, 1))
    m.agregar(prisma(14), (-0.042, 0.0026, 0), (0.034, 0.0012, 0.044), 0, claro, (1, 1))
    return m


def radio_moneda(valor):
    return {5: 0.011, 10: 0.0105, 25: 0.0125, 50: 0.0115, 100: 0.0135}.get(valor, 0.012)


def malla_moneda(valor):
    """Moneda: disco plateado (las de 1 real con anillo dorado; las de 0,05 y 0,25 doradas)."""
    r = radio_moneda(valor)
    m = Malla()
    cuerpo = DORADO if valor in (5, 25) else PLATA
    m.agregar(prisma(18), (0, 0, 0), (2 * r, 0.003, 2 * r), 0, cuerpo, (0.85, 1.15))
    if valor == 100:
        m.agregar(anillo(18, 0.5, 0.36), (0, 0.0005, 0), (2 * r + 0.001, 0.003, 2 * r + 0.001), 0, DORADO, (1, 1.1))
    return m
