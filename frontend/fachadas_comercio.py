# Fachadas de los edificios de comercio y servicio del mapa grande (F9): toldo a rayas, poste de barbero, cruz verde,
# campanario, mástil con bandera, pila de llantas, mesas y cajas. Sirve para que la Padaria, el Supermercado, la Oficina,
# el Bar, el Salão, el Posto, la Igreja, la Escola (y el Mototáxi) se distingan de las casas normales a distancia y de cerca.
#
# TODO va fundido en UNA malla (un solo Entity para todo el mapa; sin Entity por pieza), con color por vértice, y es solo
# decoración: sin colisión (todo queda pegado a la fachada, fuera del paso de 1,2 m delante de la puerta).
#
#   FACHADAS                    {lugar: Fachada}: qué lleva cada edificio (ver la tabla).
#   fachada_de(lugar)           la Fachada del lugar o None.
#   construir_fachadas(mundo)   Acumulador (frontend/geom_directa.py) con las de TODOS los edificios del mundo que tengan.
#   instalar(ciudad, mundo)     Entity con la malla, hija de la ciudad (la llama CiudadGrande; None si no hay nada).
#
# Parte pura (sin ursina): construir_fachadas. El mundo chico NO la usa (Ciudad3D no cambia).

import math

from backend.datos.modelos_edificios import escala_de, modelo_de
from backend.logica.mundo_ciudad import _NORMAL_FUERA, _TANGENTE
from frontend.geom_directa import Acumulador, prisma_suave

ALTO_TOLDO_PEGADO = 0.30       # m: lo que sube el toldo sobre el borde alto de la puerta (por debajo del letrero)
CAIDA_TOLDO = 0.25             # m que baja el borde exterior del toldo
FALDON_TOLDO = 0.15            # m del faldón vertical del borde exterior
SALIDA_TOLDO = 1.4             # m que sobresale hacia la calle
RAYAS_TOLDO = 8
MARGEN_PUERTA = 1.8            # m: lo suelto (mesas, cajas, llantas) se pone a esta distancia lateral de la puerta, no delante


class Fachada:
    __slots__ = ("toldo", "extras", "friso")

    def __init__(self, toldo=None, extras=(), friso=None):
        self.toldo = toldo          # (color A, color B) de las rayas del toldo, o None
        self.extras = tuple(extras)  # nombres de adornos: barbero, cruz, campanario, mastil, llantas, mesas, cajas, panes
        self.friso = friso          # RGB de una banda baja pintada a lo largo de la fachada, o None


FACHADAS = {
    "Padaria Pão Quente": Fachada(((236, 190, 70), (252, 244, 224)), ("panes",)),
    "Supermercado Dois Irmãos": Fachada(((204, 52, 52), (250, 250, 250)), ("cajas",)),
    "Oficina do Seu Zé": Fachada(((40, 40, 44), (240, 196, 40)), ("llantas",), friso=(240, 196, 40)),
    "Bar do Cabo": Fachada(((52, 140, 82), (248, 238, 214)), ("mesas",)),
    "Salão da Dona Lu": Fachada(((226, 100, 160), (252, 236, 244)), ("barbero",)),
    "Posto de Saúde Vila Nova": Fachada(((246, 250, 250), (46, 160, 130)), ("cruz",), friso=(46, 160, 130)),
    "Igreja Nossa Senhora da Esperança": Fachada(None, ("campanario",), friso=(120, 150, 200)),
    "Escola Municipal Paulo Freire": Fachada(((60, 130, 220), (250, 240, 200)), ("mastil",), friso=(60, 130, 220)),
    "Ponto de Mototáxi da Entrada": Fachada(((240, 150, 40), (36, 36, 40)), ("llantas",)),
}


def fachada_de(lugar):
    return FACHADAS.get(lugar)


class _Marco:
    """Coordenadas locales de una fachada -> mundo. x a lo largo de la cara (_TANGENTE), y hacia arriba desde el umbral,
    z hacia la calle (_NORMAL_FUERA); el origen es la puerta."""

    def __init__(self, edificio):
        self.px, self.pz = edificio.puerta()
        self.u = _TANGENTE[edificio.lado_puerta]
        self.n = _NORMAL_FUERA[edificio.lado_puerta]
        self.y0 = edificio.y
        # giro_y (grados, convención de Acumulador.caja) con que el eje x local queda sobre la cara
        self.giro = math.degrees(math.atan2(-self.u[1], self.u[0]))

    def punto(self, x, y, z):
        return (self.px + self.u[0] * x + self.n[0] * z, self.y0 + y, self.pz + self.u[1] * x + self.n[1] * z)


def _cuadrilatero(acum, a, b, c, d, color):
    """Cuadrilátero a-b-c-d (mundo) de doble cara, color RGB 0-255. Normal por producto cruz."""
    ux, uy, uz = b[0] - a[0], b[1] - a[1], b[2] - a[2]
    vx, vy, vz = d[0] - a[0], d[1] - a[1], d[2] - a[2]
    nx, ny, nz = uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx
    largo = math.sqrt(nx * nx + ny * ny + nz * nz) or 1.0
    nx, ny, nz = nx / largo, ny / largo, nz / largo
    rgb = (color[0] / 255, color[1] / 255, color[2] / 255, 1.0)
    for sentido, tri in ((1.0, ((0, 1, 2), (0, 2, 3))), (-1.0, ((0, 2, 1), (0, 3, 2)))):
        base = len(acum.vertices)
        for p in (a, b, c, d):
            acum.vertices.append(p)
            acum.normales.append((nx * sentido, ny * sentido, nz * sentido))
            acum.colores.append(rgb)
        acum.triangulos.extend((base + i, base + j, base + k) for i, j, k in tri)


def _caja(acum, marco, x, y, z, ancho, alto, fondo, color, tapa=None):
    """Caja centrada en el punto local (x, y, z) con `ancho` a lo largo de la cara y `fondo` hacia la calle."""
    wx, wy, wz = marco.punto(x, y, z)
    giro = marco.giro
    acum.caja(wx, wy, wz, ancho, alto, fondo, giro=giro, color=color, tapa=tapa)


def _toldo(acum, marco, ancho, y_borde, colores):
    """Toldo a rayas pegado a la pared: del borde alto (y_borde, pared) al bajo (y_borde - caída, SALIDA_TOLDO m afuera),
    con un faldón vertical del color de cada raya."""
    ancho_raya = ancho / RAYAS_TOLDO
    for k in range(RAYAS_TOLDO):
        x0 = -ancho / 2 + k * ancho_raya
        x1 = x0 + ancho_raya
        color = colores[k % 2]
        a, b = marco.punto(x0, y_borde, 0.12), marco.punto(x1, y_borde, 0.12)
        c, d = marco.punto(x1, y_borde - CAIDA_TOLDO, SALIDA_TOLDO), marco.punto(x0, y_borde - CAIDA_TOLDO, SALIDA_TOLDO)
        _cuadrilatero(acum, a, b, c, d, color)
        e, f = marco.punto(x1, y_borde - CAIDA_TOLDO - FALDON_TOLDO, SALIDA_TOLDO), marco.punto(x0, y_borde - CAIDA_TOLDO - FALDON_TOLDO, SALIDA_TOLDO)
        _cuadrilatero(acum, d, c, e, f, color)
    for lado in (-1, 1):                  # postes finos en las esquinas exteriores
        _caja(acum, marco, lado * (ancho / 2 - 0.1), (y_borde - CAIDA_TOLDO) / 2, SALIDA_TOLDO - 0.1, 0.07, y_borde - CAIDA_TOLDO,
              0.07, (70, 70, 76))


def _holguras(edificio):
    """(izquierda, derecha): metros de fachada que quedan a cada lado de la puerta (x < 0 y x > 0 del marco)."""
    return edificio.frente / 2 + edificio.desfase_puerta, edificio.frente / 2 - edificio.desfase_puerta


def _friso(acum, marco, edificio, color, hueco=1.1):
    """Banda pintada baja a lo largo de la cara de la puerta (a ~1,1 m del umbral), un poco saliente y con un hueco
    de `hueco` m a cada lado de la puerta."""
    izq, der = _holguras(edificio)
    for lado, room in ((-1, izq), (1, der)):
        largo = room - 0.15 - hueco
        if largo > 0.4:
            _caja(acum, marco, lado * (hueco + largo / 2), 1.1, 0.04, largo, 0.28, 0.08, color)


def _adorno_barbero(acum, marco, lado):
    x = lado * MARGEN_PUERTA
    plantilla = prisma_suave(8, 0.5, 0.5)
    for k, color in enumerate(((222, 46, 52), (250, 250, 250), (50, 90, 200), (250, 250, 250), (222, 46, 52))):
        px, py, pz = marco.punto(x, 0.9 + k * 0.22, 0.4)
        acum.solido(plantilla, (px, py, pz), escala=(0.26, 0.22, 0.26), color=color, degradado=(0.9, 1.0))
    _caja(acum, marco, x, 0.85, 0.4, 0.34, 0.1, 0.34, (60, 60, 66))
    _caja(acum, marco, x, 2.06, 0.4, 0.34, 0.1, 0.34, (60, 60, 66))


def _adorno_llantas(acum, marco, lado):
    plantilla = prisma_suave(10, 0.5, 0.5)
    x = lado * MARGEN_PUERTA
    for k in range(3):
        px, py, pz = marco.punto(x, k * 0.24, 0.6)
        acum.solido(plantilla, (px, py, pz), escala=(0.8, 0.24, 0.8), color=(36, 36, 40), degradado=(0.9, 1.0))


def _adorno_cajas(acum, marco, lado):
    x = lado * MARGEN_PUERTA
    colores = ((226, 120, 40), (120, 170, 60), (200, 60, 60))
    for k, color in enumerate(colores):
        _caja(acum, marco, x + (k - 1) * 0.5, 0.2, 0.55, 0.45, 0.4, 0.4, color)
    _caja(acum, marco, x, 0.58, 0.55, 0.45, 0.34, 0.4, colores[(0 + 1) % 3])


def _adorno_mesas(acum, marco, lado):
    x = lado * (MARGEN_PUERTA + 0.3)
    _caja(acum, marco, x, 0.72, 0.9, 0.9, 0.06, 0.9, (240, 240, 244))                 # mesa
    _caja(acum, marco, x, 0.36, 0.9, 0.08, 0.72, 0.08, (110, 110, 116))
    for dx in (-0.7, 0.7):
        _caja(acum, marco, x + dx, 0.22, 0.9, 0.34, 0.06, 0.34, (214, 60, 52))        # taburetes plásticos
        _caja(acum, marco, x + dx, 0.11, 0.9, 0.06, 0.22, 0.06, (180, 50, 44))


def _adorno_panes(acum, marco, lado):
    x = lado * MARGEN_PUERTA
    _caja(acum, marco, x, 0.5, 0.55, 1.1, 0.08, 0.6, (140, 96, 60))                   # mostrador exterior
    _caja(acum, marco, x - 0.4, 0.25, 0.55, 0.08, 0.5, 0.5, (110, 76, 48))
    _caja(acum, marco, x + 0.4, 0.25, 0.55, 0.08, 0.5, 0.5, (110, 76, 48))
    for k in range(4):
        _caja(acum, marco, x - 0.36 + k * 0.24, 0.6, 0.55, 0.2, 0.12, 0.4, (214, 160, 84))


def _adorno_cruz(acum, marco, edificio):
    y = min(edificio.alto - 1.0, 4.9)
    _caja(acum, marco, 0.0, y, 0.1, 1.5, 1.5, 0.1, (46, 160, 130))
    _caja(acum, marco, 0.0, y, 0.18, 1.0, 0.34, 0.06, (250, 250, 250))
    _caja(acum, marco, 0.0, y, 0.18, 0.34, 1.0, 0.06, (250, 250, 250))


def _adorno_campanario(acum, marco, edificio):
    """Torre cuadrada con aguja y cruz sobre el techo, y una cruz sobre la fachada."""
    cx, cz = edificio.cx, edificio.cz
    base = edificio.y + edificio.alto - 0.4            # hundida en el techo: así no flota si el modelo es algo más bajo
    ancho = min(edificio.ancho, edificio.fondo) * 0.3
    acum.caja(cx, base + 1.1, cz, ancho, 2.2, ancho, color=(236, 232, 220))
    acum.solido(prisma_suave(4, 0.7071, 0.0), (cx, base + 2.2, cz), escala=(ancho, 2.2, ancho), giro=45.0,
                color=(150, 70, 58), degradado=(0.85, 1.05))
    acum.caja(cx, base + 4.9, cz, 0.16, 1.2, 0.16, color=(240, 240, 244))
    acum.caja(cx, base + 5.1, cz, 0.7, 0.16, 0.16, color=(240, 240, 244))
    y = min(edificio.alto - 1.0, 5.8)
    _caja(acum, marco, 0.0, y, 0.1, 0.22, 1.5, 0.1, (240, 240, 244))
    _caja(acum, marco, 0.0, y + 0.3, 0.1, 0.8, 0.22, 0.1, (240, 240, 244))


def _adorno_mastil(acum, marco, edificio):
    """Mástil con la bandera de tres franjas en una esquina del techo (el lado de la puerta, fuera de la vista de la plaza)."""
    x = _holguras(edificio)[1] - 0.8
    techo = edificio.alto
    _caja(acum, marco, x, techo + 0.9, -0.8, 0.1, 3.0, 0.1, (200, 200, 206))
    for k, color in enumerate(((46, 160, 80), (250, 220, 60), (50, 90, 200))):
        _caja(acum, marco, x - 0.55, techo + 2.4 - k * 0.22, -0.8, 1.0, 0.2, 0.04, color)


_ADORNOS_LATERALES = {"barbero": _adorno_barbero, "llantas": _adorno_llantas, "cajas": _adorno_cajas,
                      "mesas": _adorno_mesas, "panes": _adorno_panes}
_ADORNOS_DE_PARED = {"cruz": _adorno_cruz, "campanario": _adorno_campanario, "mastil": _adorno_mastil}


def fachada_del_edificio(acum, edificio):
    """Añade a `acum` la fachada del edificio (si su lugar tiene una). Devuelve True si añadió algo."""
    ficha = fachada_de(edificio.lugar)
    if ficha is None:
        return False
    marco = _Marco(edificio)
    puerta_alto = 1.0
    if edificio.modelo:
        puerta_alto = modelo_de(edificio.modelo).puerta_alto * escala_de(edificio)
    if ficha.friso is not None:
        _friso(acum, marco, edificio, ficha.friso)
    if ficha.toldo is not None:
        izq, der = _holguras(edificio)
        ancho = 2 * max(1.2, min(3.25, izq - 0.4, der - 0.4))
        _toldo(acum, marco, ancho, puerta_alto + ALTO_TOLDO_PEGADO, ficha.toldo)
    izq, der = _holguras(edificio)
    lado = 1 if der >= izq else -1                           # hacia donde sobra más fachada
    for nombre in ficha.extras:
        if nombre in _ADORNOS_LATERALES:
            _ADORNOS_LATERALES[nombre](acum, marco, lado)
        elif nombre in _ADORNOS_DE_PARED:
            _ADORNOS_DE_PARED[nombre](acum, marco, edificio)
    return True


def construir_fachadas(mundo):
    """Acumulador con las fachadas de todos los edificios del mundo que tengan una (vacío si no hay ninguna)."""
    acum = Acumulador()
    for edificio in mundo.edificios():
        fachada_del_edificio(acum, edificio)
    return acum


def lugares_con_fachada(mundo):
    return [e.lugar for e in mundo.edificios() if e.lugar in FACHADAS]


def instalar(ciudad, mundo):
    """Entity con TODAS las fachadas fundidas en una malla, hija de `ciudad`. Devuelve el Entity o None si no hay nada."""
    from panda3d.core import NodePath
    from ursina import Entity
    from frontend.geom_directa import geom_completa
    from frontend.piezas import MASCARA_LUZ, silenciar
    from frontend.sombras_locales import shader_de_ciudad
    acum = construir_fachadas(mundo)
    if acum.vacio():
        return None
    nodo = geom_completa("fachadas_comercio", acum.vertices, acum.normales, acum.colores, acum.triangulos)
    if nodo is None:
        return None
    entidad = Entity(parent=ciudad, shader=shader_de_ciudad(), name="fachadas_comercio")
    n = NodePath(nodo)
    n.set_two_sided(True)
    n.hide(MASCARA_LUZ)
    n.reparent_to(entidad)
    silenciar(entidad)
    return entidad
