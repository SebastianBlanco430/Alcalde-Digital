# Detalle de la favela (Ursina): murales, carteles pintados, remiendos, grietas y manchas en las paredes,
# balcones, banderines que cruzan los callejones, bidones, macetas, motos, bicis, cajas de fruta y perros,
# palmeras y bananeros, la cancha de fútbol y el mercadito de toldos.
#
# Rendimiento: nada de esto es una Entity. Cada pieza se copia con su color por vértice a una de TRES
# mallas: la opaca (con luz y sombras: lo que está sobre las paredes y en el piso), la de tinta translúcida
# (manchas de humedad, sin luz) y la de banderines (sin luz, doble cara). Solo los carteles con letras llevan
# un Text cada uno (pocos). Las decisiones (qué pared, qué altura, qué objeto) salen de
# frontend/favela_calculos.py con azar fijo, así que todo sale igual en cada ejecución.
#
# Sin colisión: son decorado puro. Los objetos del piso solo se ponen pegados a paredes, en calles o pasillos
# de 2,2 m o más (ver favela_calculos.HUECO_OBJETO_MIN) y a distancia de los obstáculos redondos.

import math

from frontend import favela_calculos as fc
from frontend.azar_fijo import azar_de
from frontend.props_mundo import Malla, anillo, caja, icosfera, prisma

BRILLO_DECAL = 0.9                # factor de color de lo pintado en las paredes
TINTA = (24, 24, 36)              # bordes y trazos de los murales (la tinta de docs/DISENO.md §7, algo más clara)
CAPA = 0.006                      # m que se adelanta cada capa de un mural sobre la anterior (sin z-fighting)
MANCHA = (36, 24, 44)             # color de las manchas de humedad (se dibujan translúcidas)
ALFA_MANCHA = 0.34
FONDOS_CARTEL = ((214, 60, 60), (240, 190, 40), (40, 130, 200), (50, 160, 100), (36, 36, 48))
LETRAS_CARTEL = ((250, 246, 230), (30, 30, 40), (255, 240, 200), (255, 240, 200), (255, 220, 60))
COLORES_REMIENDO = ((226, 214, 188), (176, 98, 70), (196, 190, 180), (150, 196, 170), (232, 200, 120))
PINTURAS_OBJETO = ((60, 120, 220), (220, 60, 60), (240, 190, 40), (50, 160, 100), (240, 130, 40), (240, 240, 235))
PELAJES = ((196, 144, 84), (240, 236, 224), (60, 52, 50), (150, 100, 60), (214, 176, 120), (110, 100, 96))


# -- Primitivas planas ---------------------------------------------------------------------------


def _tono(color, factor=1.0, alfa=1.0):
    return (min(1.5, color[0] / 255 * factor), min(1.5, color[1] / 255 * factor), min(1.5, color[2] / 255 * factor), alfa)


# Polígono convexo plano: `puntos` son (u, v) en el plano de la pared (u a lo largo de la tangente, v hacia
# arriba), `origen` el punto (x, y, z) de la pared, `tang` y `norm` los vectores (x, z) a lo largo y hacia
# afuera. Se pinta con el color dado y la normal hacia afuera.
def _poligono(m, origen, tang, norm, puntos, color, fuera=0.0, alfa=1.0, factor=BRILLO_DECAL):
    normal = (norm[0], 0.0, norm[1])
    pts = [(origen[0] + tang[0] * u + norm[0] * fuera, origen[1] + v, origen[2] + tang[1] * u + norm[1] * fuera)
           for u, v in puntos]
    tono = _tono(color, factor, alfa)
    for k in range(1, len(pts) - 1):
        a, b, c = pts[0], pts[k], pts[k + 1]
        u_ = tuple(c[i] - a[i] for i in range(3))
        v_ = tuple(b[i] - a[i] for i in range(3))
        n = (u_[1] * v_[2] - u_[2] * v_[1], u_[2] * v_[0] - u_[0] * v_[2], u_[0] * v_[1] - u_[1] * v_[0])
        if sum(n[i] * normal[i] for i in range(3)) < 0:
            b, c = c, b
        for p in (a, b, c):
            m.vertices.append(p)
            m.normales.append(normal)
            m.colores.append(tono)


def _rect(cu, cv, ancho, alto, giro=0.0):
    a, c, s = math.radians(giro), math.cos(math.radians(giro)), math.sin(math.radians(giro))
    esquinas = ((-ancho / 2, -alto / 2), (ancho / 2, -alto / 2), (ancho / 2, alto / 2), (-ancho / 2, alto / 2))
    return [(cu + x * c - y * s, cv + x * s + y * c) for x, y in esquinas]


def _elipse(cu, cv, rx, ry, lados=14):
    return [(cu + rx * math.cos(2 * math.pi * k / lados), cv + ry * math.sin(2 * math.pi * k / lados)) for k in range(lados)]


def _estrella(cu, cv, radio, puntas=5):
    puntos = []
    for k in range(2 * puntas):
        r = radio if k % 2 == 0 else radio * 0.42
        a = math.pi / 2 + math.pi * k / puntas
        puntos.append((cu + r * math.cos(a), cv + r * math.sin(a)))
    return puntos


# Una estrella no es convexa: se pinta como un abanico de triángulos desde el centro.
def _poligono_estrella(m, origen, tang, norm, cu, cv, radio, color, fuera):
    puntos = _estrella(cu, cv, radio)
    for k in range(len(puntos)):
        _poligono(m, origen, tang, norm, [(cu, cv), puntos[k], puntos[(k + 1) % len(puntos)]], color, fuera)


# -- Murales y otras calcomanías ---------------------------------------------------------------------


# Dibuja una calcomanía en `m` (opaca) o `tinta` (translúcida). `base_y` = y de la planta baja de su casa.
def dibujar_calcomania(m, tinta, cal, base_y):
    cx, cz = cal.centro()
    nx, nz = fc.NORMAL[cal.lado]
    tang = fc.TANGENTE[cal.lado]
    # el origen es el centro de la base del dibujo; (u, v) = (0, 0) es ese punto
    origen = (cx, base_y + cal.y, cz)
    norm = (nx, nz)
    w, h, u = cal.ancho, cal.alto, cal.semilla
    if cal.tipo in ("sol", "bandera", "estrella", "corazon", "ola", "ojo"):
        _mural(m, origen, tang, norm, cal)
    elif cal.tipo == "cartel":
        fondo = FONDOS_CARTEL[int(u * len(FONDOS_CARTEL)) % len(FONDOS_CARTEL)]
        _poligono(m, origen, tang, norm, _rect(0, h / 2, w + 0.12, h + 0.12), TINTA, 0)
        _poligono(m, origen, tang, norm, _rect(0, h / 2, w, h), fondo, CAPA)
        for lado in (-1, 1):
            _poligono(m, origen, tang, norm, _rect(lado * (w / 2 - 0.1), h / 2, 0.08, h - 0.2), _aclarar(fondo, 1.3), 2 * CAPA)
    elif cal.tipo == "remiendo":
        color = COLORES_REMIENDO[int(u * len(COLORES_REMIENDO)) % len(COLORES_REMIENDO)]
        _poligono(m, origen, tang, norm, _rect(0, h / 2, w + 0.08, h + 0.08, giro=2 * (u - 0.5) * 6), _aclarar(color, 0.62), 0)
        _poligono(m, origen, tang, norm, _rect(0, h / 2, w, h, giro=2 * (u - 0.5) * 6), color, CAPA)
        for k in range(3):                     # ladrillos o líneas de la llana
            _poligono(m, origen, tang, norm, _rect(-w / 4 + k * w / 4, h / 2, 0.05, h * 0.7), _aclarar(color, 0.8), 2 * CAPA)
    elif cal.tipo == "grieta":
        _grieta(m, origen, tang, norm, cal)
    elif cal.tipo == "mancha":
        _mancha(tinta, origen, tang, norm, cal)
    elif cal.tipo == "balcon":
        _balcon(m, origen, tang, norm, cal)


def _aclarar(color, factor):
    return tuple(min(255, int(c * factor)) for c in color)


def _mural(m, origen, tang, norm, cal):
    w, h, u = cal.ancho, cal.alto, cal.semilla
    cy = h / 2
    _poligono(m, origen, tang, norm, _rect(0, cy, w + 0.14, h + 0.14), TINTA, 0)               # marco de tinta
    if cal.tipo == "sol":
        _poligono(m, origen, tang, norm, _rect(0, cy, w, h), (56, 168, 214), CAPA)
        for k in range(8):                                                                     # rayos
            a = k * 45
            rx, ry = 0.62 * math.cos(math.radians(a)), 0.62 * math.sin(math.radians(a))
            _poligono(m, origen, tang, norm, _rect(rx, cy + ry, 0.7, 0.14, giro=a), (255, 150, 40), 2 * CAPA)
        _poligono(m, origen, tang, norm, _elipse(0, cy, 0.42, 0.42, 16), TINTA, 3 * CAPA)
        _poligono(m, origen, tang, norm, _elipse(0, cy, 0.36, 0.36, 16), (255, 214, 60), 4 * CAPA)
    elif cal.tipo == "bandera":
        _poligono(m, origen, tang, norm, _rect(0, cy, w, h), (0, 156, 59), CAPA)
        _poligono(m, origen, tang, norm, _rect(0, cy, 1.55, 1.55, giro=45)[0:4], (255, 223, 0), 2 * CAPA)
        _poligono(m, origen, tang, norm, _elipse(0, cy, 0.52, 0.52, 18), (0, 39, 118), 3 * CAPA)
        _poligono(m, origen, tang, norm, _rect(0, cy, 0.95, 0.07, giro=-12), (250, 250, 250), 4 * CAPA)
    elif cal.tipo == "estrella":
        _poligono(m, origen, tang, norm, _rect(0, cy, w, h), (112, 58, 168), CAPA)
        _poligono_estrella(m, origen, tang, norm, 0, cy, 0.7, TINTA, 2 * CAPA)
        _poligono_estrella(m, origen, tang, norm, 0, cy, 0.6, (255, 220, 60), 3 * CAPA)
    elif cal.tipo == "corazon":
        _poligono(m, origen, tang, norm, _rect(0, cy, w, h), (250, 150, 190), CAPA)
        for lado in (-1, 1):
            _poligono(m, origen, tang, norm, _elipse(lado * 0.27, cy + 0.2, 0.32, 0.32, 14), (216, 40, 70), 2 * CAPA)
        _poligono(m, origen, tang, norm, _rect(0, cy + 0.02, 0.62, 0.62, giro=45), (216, 40, 70), 2 * CAPA)
    elif cal.tipo == "ola":
        _poligono(m, origen, tang, norm, _rect(0, cy, w, h), (90, 190, 230), CAPA)
        for fila in range(3):                                                                  # tres olas continuas
            color = (250, 250, 250) if fila % 2 == 0 else (30, 100, 180)
            y0 = cy - 0.5 + fila * 0.5
            pasos = 14
            for k in range(pasos):
                x0, x1 = -w / 2 + 0.1 + k * (w - 0.2) / pasos, -w / 2 + 0.1 + (k + 1) * (w - 0.2) / pasos
                ya, yb = y0 + 0.14 * math.sin(k * 0.9 + fila), y0 + 0.14 * math.sin((k + 1) * 0.9 + fila)
                _poligono(m, origen, tang, norm, [(x0, ya - 0.07), (x1, yb - 0.07), (x1, yb + 0.07), (x0, ya + 0.07)],
                          color, 2 * CAPA)
    else:                                                                                      # ojo
        _poligono(m, origen, tang, norm, _rect(0, cy, w, h), (255, 200, 60), CAPA)
        _poligono(m, origen, tang, norm, _elipse(0, cy, 0.95, 0.5, 20), TINTA, 2 * CAPA)
        _poligono(m, origen, tang, norm, _elipse(0, cy, 0.88, 0.44, 20), (250, 250, 246), 3 * CAPA)
        _poligono(m, origen, tang, norm, _elipse(0, cy, 0.34, 0.34, 14), (60, 150, 90), 4 * CAPA)
        _poligono(m, origen, tang, norm, _elipse(0, cy, 0.17, 0.17, 12), TINTA, 5 * CAPA)


# Grieta: una línea quebrada de tramos finos de tinta de abajo hacia arriba, con alguna rama.
def _grieta(m, origen, tang, norm, cal):
    u = cal.semilla
    x, y = 0.0, 0.0
    for k in range(7):
        dx = (azar_de(u * 7 + k, 1.3) - 0.5) * 0.5
        dy = 0.24 + 0.08 * azar_de(u, k)
        largo = math.hypot(dx, dy)
        giro = math.degrees(math.atan2(dx, dy))
        _poligono(m, origen, tang, norm, _rect(x + dx / 2, y + dy / 2, 0.045, largo, giro=-giro), TINTA, 2 * CAPA, factor=0.9)
        if k == 3:                                                                                # rama
            _poligono(m, origen, tang, norm, _rect(x + 0.14, y + dy / 2 + 0.05, 0.035, 0.34, giro=-55), TINTA, 2 * CAPA, factor=0.9)
        x, y = x + dx, y + dy


# Mancha de humedad: sube desde el piso, más oscura abajo; se dibuja translúcida y sin luz.
def _mancha(tinta, origen, tang, norm, cal):
    w, h = cal.ancho, cal.alto
    vertices = (( -w / 2, 0), (w / 2, 0), (w * 0.32, h * 0.62), (-w * 0.1, h), (-w * 0.4, h * 0.55))
    _poligono(tinta, origen, tang, norm, list(vertices), MANCHA, 0.0, alfa=ALFA_MANCHA, factor=1.0)
    _poligono(tinta, origen, tang, norm, [(-w / 2, 0), (w / 2, 0), (w * 0.3, h * 0.3), (-w * 0.3, h * 0.3)], MANCHA,
              CAPA, alfa=ALFA_MANCHA * 0.8, factor=1.0)


# Balcón: losa que sale de la pared con barandas de hierro y una maceta.
def _balcon(m, origen, tang, norm, cal):
    w, vol = cal.ancho, cal.alto
    nx, nz = norm
    tx, tz = tang
    def pos(u, fuera, y):
        return (origen[0] + tx * u + nx * fuera, origen[1] + y, origen[2] + tz * u + nz * fuera)
    rumbo = math.degrees(math.atan2(nx, nz))
    m.agregar(caja(), pos(0, vol / 2, 0.07), (w, 0.14, vol), rumbo, (196, 190, 182), (0.85, 1.0))
    for k in range(5):                                            # barrotes
        u = -w / 2 + 0.05 + k * (w - 0.1) / 4
        m.agregar(caja(), pos(u, vol - 0.04, 0.62), (0.04, 1.0, 0.04), rumbo, (40, 42, 52), (0.8, 1.0))
    m.agregar(caja(), pos(0, vol - 0.04, 1.12), (w, 0.05, 0.05), rumbo, (40, 42, 52), (0.8, 1.0))
    for lado in (-1, 1):
        m.agregar(caja(), pos(lado * (w / 2 - 0.04), vol / 2, 0.62), (0.04, 1.0, vol), rumbo, (40, 42, 52), (0.8, 1.0))
    verde = (60, 150, 70)
    m.agregar(prisma(8, 0.5, 0.36), pos(-w / 4, vol * 0.6, 0.14), (0.34, 0.3, 0.34), 0, (190, 96, 64), (0.8, 1.05))
    m.agregar(icosfera(1), pos(-w / 4, vol * 0.6, 0.5), (0.5, 0.42, 0.5), 0, verde, (0.7, 1.1), 0.1)


# -- Objetos de la calle -----------------------------------------------------------------------------


def dibujar_objeto(m, o, suelo):
    y = suelo(o.x, o.z)
    pintura = PINTURAS_OBJETO[o.variante % len(PINTURAS_OBJETO)]
    if o.tipo == "bidon":
        _bidon(m, o.x, y, o.z, pintura, o.variante)
    elif o.tipo == "maceta":
        _maceta(m, o.x, y, o.z, o.variante)
    elif o.tipo == "moto":
        _moto(m, o.x, y, o.z, o.rumbo, pintura)
    elif o.tipo == "bici":
        _bici(m, o.x, y, o.z, o.rumbo, pintura)
    elif o.tipo == "caja":
        _cajas_de_fruta(m, o.x, y, o.z, o.rumbo, o.variante)
    elif o.tipo == "perro":
        _perro(m, o.x, y, o.z, o.rumbo, o.variante)


def _bidon(m, x, y, z, pintura, variante):
    for k in range(1 + (variante % 2)):
        px, pz = x + 0.55 * k, z + 0.1 * k
        m.agregar(prisma(10, 0.5, 0.5), (px, y, pz), (0.56, 0.9, 0.56), variante * 31, pintura, (0.8, 1.05))
        for dy in (0.18, 0.7):
            m.agregar(prisma(10, 0.5, 0.5), (px, y + dy, pz), (0.585, 0.07, 0.585), variante * 31, _aclarar(pintura, 0.6), (0.9, 1.0))
        m.agregar(prisma(10, 0.5, 0.5), (px, y + 0.9, pz), (0.5, 0.04, 0.5), variante * 31, (40, 42, 52), (0.9, 1.0))


def _maceta(m, x, y, z, variante):
    m.agregar(prisma(8, 0.5, 0.36), (x, y, z), (0.5, 0.42, 0.5), 0, (200, 100, 64) if variante % 2 else (60, 130, 200), (0.8, 1.05))
    m.agregar(icosfera(1), (x, y + 0.62, z), (0.62, 0.5, 0.62), variante * 40, (54 + 20 * (variante % 3), 150, 62), (0.65, 1.1), 0.1)
    flor = ((240, 70, 110), (250, 210, 50), (250, 250, 240), (200, 90, 220))[variante % 4]
    for k in range(4):
        a = k * 1.7 + variante
        m.agregar(icosfera(0), (x + 0.2 * math.cos(a), y + 0.78 + 0.05 * (k % 2), z + 0.2 * math.sin(a)), 0.13, 0, flor, (1.0, 1.1))


# Moto de rumbo `rumbo` (su eje largo va a lo largo de rumbo + 90): ruedas, tanque de color, asiento oscuro y manillar.
def _moto(m, x, y, z, rumbo, pintura):
    s, c = math.sin(math.radians(rumbo)), math.cos(math.radians(rumbo))

    def p(d_largo, dy, d_ancho=0.0):
        return (x + s * d_largo + c * d_ancho, y + dy, z + c * d_largo - s * d_ancho)

    for d in (-0.62, 0.62):
        m.agregar(icosfera(1), p(d, 0.31), (0.16, 0.62, 0.62), rumbo, (28, 28, 34), (0.85, 1.05))
        m.agregar(icosfera(0), p(d, 0.31), (0.2, 0.2, 0.2), rumbo, (190, 190, 196), (0.9, 1.05))
    m.agregar(caja(), p(0.0, 0.5), (0.14, 0.12, 1.1), rumbo, (46, 48, 58), (0.8, 1.0))
    m.agregar(caja(), p(0.14, 0.72), (0.3, 0.26, 0.5), rumbo, pintura, (0.8, 1.05))
    m.agregar(caja(), p(-0.2, 0.7), (0.26, 0.1, 0.55), rumbo, (30, 30, 36), (0.8, 1.0))
    m.agregar(caja(), p(0.55, 0.88), (0.62, 0.05, 0.05), rumbo + 90, (60, 62, 70), (0.8, 1.0))
    m.agregar(icosfera(0), p(0.62, 0.8), 0.18, rumbo, (255, 236, 160), (1.0, 1.1))


def _bici(m, x, y, z, rumbo, pintura):
    s, c = math.sin(math.radians(rumbo)), math.cos(math.radians(rumbo))

    def p(d_largo, dy):
        return (x + s * d_largo, y + dy, z + c * d_largo)

    for d in (-0.5, 0.5):
        m.agregar(icosfera(1), p(d, 0.33), (0.05, 0.66, 0.66), rumbo, (36, 38, 44), (0.85, 1.05))
    m.agregar(caja(), p(0.0, 0.55), (0.04, 0.05, 1.0), rumbo, pintura, (0.8, 1.05))
    m.agregar(caja(), p(-0.15, 0.78), (0.1, 0.05, 0.3), rumbo, (30, 30, 36), (0.8, 1.0))
    m.agregar(caja(), p(0.5, 0.95), (0.5, 0.04, 0.04), rumbo + 90, (60, 62, 70), (0.8, 1.0))
    m.agregar(caja(), p(0.5, 0.65), (0.04, 0.6, 0.04), rumbo, (60, 62, 70), (0.8, 1.0))


def _cajas_de_fruta(m, x, y, z, rumbo, variante):
    madera = (176, 124, 76)
    frutas = ((240, 130, 40), (216, 50, 50), (110, 190, 60), (250, 210, 50))
    for k in range(2):
        px, pz = x + 0.62 * k * math.cos(math.radians(rumbo)), z - 0.62 * k * math.sin(math.radians(rumbo))
        m.agregar(caja(), (px, y + 0.17, pz), (0.55, 0.34, 0.4), rumbo, madera, (0.75, 1.0))
        fruta = frutas[(variante + k) % len(frutas)]
        for i in range(3):
            for j in range(2):
                m.agregar(icosfera(0), (px + (i - 1) * 0.15 * math.cos(math.radians(rumbo)), y + 0.36,
                                        pz + (j - 0.5) * 0.15), 0.17, 0, fruta, (0.9, 1.1))


# Perro callejero de pie, mirando hacia `rumbo`.
def _perro(m, x, y, z, rumbo, variante):
    pelo = PELAJES[variante % len(PELAJES)]
    manchas = PELAJES[(variante + 2) % len(PELAJES)]
    s, c = math.sin(math.radians(rumbo)), math.cos(math.radians(rumbo))

    def p(d_largo, dy, d_ancho=0.0):
        return (x + s * d_largo + c * d_ancho, y + dy, z + c * d_largo - s * d_ancho)

    m.agregar(caja(), p(0.0, 0.42), (0.26, 0.26, 0.62), rumbo, pelo, (0.8, 1.05))
    m.agregar(caja(), p(0.0, 0.44), (0.27, 0.12, 0.3), rumbo, manchas, (0.8, 1.0))
    m.agregar(caja(), p(0.42, 0.55), (0.2, 0.2, 0.22), rumbo, pelo, (0.8, 1.05))
    m.agregar(caja(), p(0.56, 0.5), (0.1, 0.09, 0.14), rumbo, _aclarar(pelo, 0.8), (0.8, 1.0))
    for lado in (-1, 1):
        m.agregar(caja(), p(0.4, 0.66, lado * 0.09), (0.05, 0.12, 0.07), rumbo, manchas, (0.8, 1.0))
        for d in (-0.22, 0.24):
            m.agregar(caja(), p(d, 0.17, lado * 0.09), (0.07, 0.34, 0.07), rumbo, pelo, (0.75, 1.0))
    m.agregar(caja(), p(-0.4, 0.6), (0.05, 0.05, 0.34), rumbo, pelo, (0.8, 1.0), 0.0, 48)


# -- Plantas: palmeras y bananeros -----------------------------------------------------------------------

VERDES_PALMA = ((44, 150, 70), (64, 168, 60), (36, 128, 78))
VERDES_BANANO = ((112, 192, 72), (94, 176, 70), (136, 204, 84))


# Hoja plana de `ancho` x `largo` m que sale de (x, y, z) hacia el rumbo `giro` y cae `caida` grados bajo la horizontal.
def _hoja(m, x, y, z, ancho, largo, giro, caida, color):
    c, sn = math.cos(math.radians(caida)), math.sin(math.radians(caida))
    dx, dz = math.sin(math.radians(giro)), math.cos(math.radians(giro))
    m.agregar(caja(), (x + dx * c * largo / 2, y - sn * largo / 2, z + dz * c * largo / 2), (ancho, 0.04, largo), giro,
              color, (0.7, 1.1), 0.08, caida)


def palmera(m, x, y, z, s=1.0, variante=0):
    inclina = (azar_de(x, z) - 0.5) * 0.16                                 # el tronco se curva un poco
    alto_total = 6.2 * s
    segmentos = 5
    tx, tz = x, z
    giro_inc = azar_de(z, x) * 360
    for k in range(segmentos):
        t = k / segmentos
        px = x + math.sin(math.radians(giro_inc)) * inclina * alto_total * t * t
        pz = z + math.cos(math.radians(giro_inc)) * inclina * alto_total * t * t
        m.agregar(prisma(7, 0.5, 0.42), (px, y + alto_total * t - 0.05, pz), (0.34 * s * (1 - 0.3 * t), alto_total / segmentos + 0.1, 0.34 * s * (1 - 0.3 * t)),
                  k * 25, (150, 112, 76) if k % 2 else (132, 96, 64), (0.7, 1.05), 0.1)
        tx, tz = px, pz
    cima = y + alto_total
    verde = VERDES_PALMA[variante % len(VERDES_PALMA)]
    for k in range(10):                                                      # hojas arqueadas: dos tramos que caen más
        giro = k * 36 + azar_de(x + k, z) * 18
        base = 8 + 22 * azar_de(k, x + z)
        color = _aclarar(verde, 0.8 + 0.3 * (k % 3) / 2)
        _hoja(m, tx, cima, tz, 0.5 * s, 1.5 * s, giro, base, color)
        dx, dz = math.sin(math.radians(giro)), math.cos(math.radians(giro))
        fin = 1.5 * s * math.cos(math.radians(base))
        _hoja(m, tx + dx * fin, cima - 1.5 * s * math.sin(math.radians(base)), tz + dz * fin, 0.34 * s, 1.3 * s, giro,
              base + 38, _aclarar(color, 1.12))
    for dx, dz in ((0.2, 0.0), (-0.12, 0.17), (-0.1, -0.15)):
        m.agregar(icosfera(0), (tx + dx * s, cima - 0.25 * s, tz + dz * s), 0.34 * s, 0, (110, 78, 46), (0.8, 1.05))


def bananero(m, x, y, z, s=1.0, variante=0):
    m.agregar(prisma(7, 0.5, 0.45), (x, y - 0.05, z), (0.26 * s, 2.3 * s, 0.26 * s), variante * 20, (150, 190, 100), (0.75, 1.05), 0.08)
    verde = VERDES_BANANO[variante % len(VERDES_BANANO)]
    for k in range(6):
        _hoja(m, x, y + 2.3 * s, z, 0.9 * s, 2.0 * s, k * 60 + azar_de(x, z + k) * 25, 15 + 40 * azar_de(z, x + k),
              _aclarar(verde, 0.9 + 0.2 * (k % 2)))
    for k in range(5):
        a = k * 1.25
        m.agregar(icosfera(0), (x + 0.28 * s * math.cos(a), y + 1.75 * s, z + 0.28 * s * math.sin(a)), (0.1 * s, 0.36 * s, 0.1 * s), 0,
                  (232, 204, 60), (0.9, 1.1))


# -- Cancha de fútbol ----------------------------------------------------------------------------------

COLOR_CESPED = ((82, 160, 66), (96, 174, 74))
COLOR_LINEA_CANCHA = (246, 246, 238)
GROSOR_LINEA = 0.14


# Cancha sobre la zona `zona` (cx, cz, ancho en x, fondo en z) a la altura `y`: franjas de césped, líneas
# blancas (borde, mitad, círculo central, áreas) y dos arcos. El eje largo es el mayor de la zona.
def cancha(m, zona, y):
    cx, cz, ancho, fondo = zona.cx, zona.cz, zona.ancho, zona.fondo
    largo_x = ancho >= fondo
    L, A = (ancho, fondo) if largo_x else (fondo, ancho)            # largo y ancho de la cancha
    alto = y + 0.05

    def punto(a, b):                                                # a a lo largo (-L/2..L/2), b a lo ancho
        return (cx + a, cz + b) if largo_x else (cx + b, cz + a)

    def losa(a0, a1, b0, b1, color, dy):
        esquinas = [punto(a0, b0), punto(a1, b0), punto(a1, b1), punto(a0, b1)]
        tono = _tono(color, 0.85)
        # la cara frontal debe mirar hacia arriba: si el orden da la normal hacia abajo, se invierte
        ux, uz = esquinas[2][0] - esquinas[0][0], esquinas[2][1] - esquinas[0][1]
        vx, vz = esquinas[1][0] - esquinas[0][0], esquinas[1][1] - esquinas[0][1]
        orden = ((0, 1, 2), (0, 2, 3)) if uz * vx - ux * vz >= 0 else ((0, 2, 1), (0, 3, 2))
        for (i, j, k) in orden:
            for q in (i, j, k):
                m.vertices.append((esquinas[q][0], alto + dy, esquinas[q][1]))
                m.normales.append((0.0, 1.0, 0.0))
                m.colores.append(tono)

    franjas = 8
    for k in range(franjas):
        losa(-L / 2 + L * k / franjas, -L / 2 + L * (k + 1) / franjas, -A / 2, A / 2, COLOR_CESPED[k % 2], 0.0)
    g = GROSOR_LINEA
    for a0, a1, b0, b1 in ((-L / 2, L / 2, -A / 2, -A / 2 + g), (-L / 2, L / 2, A / 2 - g, A / 2),
                           (-L / 2, -L / 2 + g, -A / 2, A / 2), (L / 2 - g, L / 2, -A / 2, A / 2),
                           (-g / 2, g / 2, -A / 2, A / 2)):
        losa(a0, a1, b0, b1, COLOR_LINEA_CANCHA, 0.012)
    for lado in (-1, 1):                                            # áreas grandes
        a_borde = lado * L / 2
        a_area = lado * (L / 2 - 4.2)
        losa(min(a_borde, a_area), max(a_borde, a_area), -3.6, -3.6 + g, COLOR_LINEA_CANCHA, 0.012)
        losa(min(a_borde, a_area), max(a_borde, a_area), 3.6 - g, 3.6, COLOR_LINEA_CANCHA, 0.012)
        losa(a_area - g / 2, a_area + g / 2, -3.6, 3.6, COLOR_LINEA_CANCHA, 0.012)
    for k in range(20):                                             # círculo central
        a0, a1 = 2 * math.pi * k / 20, 2 * math.pi * (k + 1) / 20
        r = 2.4
        p0, p1 = (r * math.cos(a0), r * math.sin(a0)), (r * math.cos(a1), r * math.sin(a1))
        losa(min(p0[0], p1[0]) - g / 2, max(p0[0], p1[0]) + g / 2, min(p0[1], p1[1]) - g / 2, max(p0[1], p1[1]) + g / 2,
             COLOR_LINEA_CANCHA, 0.012)
    for lado in (-1, 1):                                            # arcos: dos postes, travesaño y red
        a = lado * (L / 2 + 0.05)
        for b in (-1.8, 1.8):
            px, pz = punto(a, b)
            m.agregar(prisma(8, 0.5, 0.5), (px, alto, pz), (0.12, 2.2, 0.12), 0, (250, 250, 246), (0.9, 1.05))
        cxa, cza = punto(a, 0)
        m.agregar(caja(), (cxa, alto + 2.2, cza), (0.12, 0.12, 3.72) if largo_x else (3.72, 0.12, 0.12), 0, (250, 250, 246), (0.9, 1.05))
        for b in (-1.8, 1.8):                                       # fondo del arco
            px, pz = punto(a + lado * 1.1, b)
            m.agregar(prisma(6, 0.5, 0.5), (px, alto, pz), (0.07, 1.5, 0.07), 0, (232, 232, 226), (0.9, 1.05))
        cxb, czb = punto(a + lado * 1.1, 0)
        m.agregar(caja(), (cxb, alto + 1.5, czb), (0.06, 0.06, 3.7) if largo_x else (3.7, 0.06, 0.06), 0, (232, 232, 226), (0.9, 1.05))
    for a, b in ((-L / 2, -A / 2), (-L / 2, A / 2), (L / 2, -A / 2), (L / 2, A / 2)):           # banderines de córner
        px, pz = punto(a, b)
        m.agregar(prisma(6, 0.5, 0.5), (px, alto, pz), (0.05, 1.2, 0.05), 0, (240, 220, 60), (0.9, 1.05))
        m.agregar(caja(), (px + 0.14, alto + 1.1, pz), (0.28, 0.2, 0.02), 0, (230, 60, 60), (0.9, 1.05))


# -- Mercadito de toldos -------------------------------------------------------------------------------

TOLDOS = (((226, 52, 60), (250, 246, 232)), ((250, 200, 40), (60, 130, 220)), ((50, 170, 100), (250, 246, 232)),
          ((250, 130, 40), (250, 246, 232)), ((150, 80, 210), (250, 220, 90)))


# Puestos con toldo a rayas a lo largo del eje largo de la zona, en dos filas con pasillo en medio.
def mercadito(m, zona, y):
    cx, cz, ancho, fondo = zona.cx, zona.cz, zona.ancho, zona.fondo
    largo_x = ancho >= fondo
    L, A = (ancho, fondo) if largo_x else (fondo, ancho)
    alto = y + 0.05
    # suelo: losa de cemento claro
    esquinas = [(cx - ancho / 2, cz - fondo / 2), (cx + ancho / 2, cz - fondo / 2),
                (cx + ancho / 2, cz + fondo / 2), (cx - ancho / 2, cz + fondo / 2)]
    for tri in ((0, 1, 2), (0, 2, 3)):
        for q in tri:
            m.vertices.append((esquinas[q][0], alto, esquinas[q][1]))
            m.normales.append((0.0, 1.0, 0.0))
            m.colores.append(_tono((206, 188, 160), 0.85))
    puestos = max(2, int(L // 3.2))
    for fila in (-1, 1):
        for k in range(puestos):
            a = -L / 2 + (k + 0.5) * L / puestos
            b = fila * (A / 2 - 1.3)
            px, pz = (cx + a, cz + b) if largo_x else (cx + b, cz + a)
            rumbo = (0 if fila > 0 else 180) if largo_x else (90 if fila > 0 else 270)
            rumbo = (rumbo + 180) % 360                              # el frente mira al pasillo central
            _puesto(m, px, alto, pz, rumbo, TOLDOS[(k + (fila > 0)) % len(TOLDOS)], k + (fila > 0))


def _puesto(m, x, y, z, rumbo, toldo, variante):
    s, c = math.sin(math.radians(rumbo)), math.cos(math.radians(rumbo))

    def p(d_ancho, dy, d_fondo):                                     # d_fondo > 0 = hacia el frente del puesto
        return (x + c * d_ancho + s * d_fondo, y + dy, z - s * d_ancho + c * d_fondo)

    for da in (-1.05, 1.05):
        for df in (-0.7, 0.7):
            m.agregar(prisma(6, 0.5, 0.5), p(da, 0, df), (0.07, 2.2, 0.07), 0, (96, 70, 48), (0.8, 1.05))
    m.agregar(caja(), p(0, 0.85, 0.25), (2.2, 0.08, 0.9), rumbo, (176, 124, 76), (0.8, 1.0))          # mostrador
    m.agregar(caja(), p(0, 0.42, 0.25), (2.1, 0.8, 0.8), rumbo, (126, 94, 64), (0.75, 1.0))
    for k in range(6):                                               # toldo: 6 rayas inclinadas
        da = -1.0 + k * 0.4 + 0.2
        m.agregar(caja(), p(da, 2.3 + 0.0, 0.0), (0.4, 0.04, 1.95), rumbo, toldo[k % 2], (0.85, 1.05), 0.0, 16)
    for k in range(5):                                               # frutas y verduras sobre el mostrador
        fruta = ((240, 130, 40), (216, 50, 50), (110, 190, 60), (250, 210, 50), (170, 60, 150))[(k + variante) % 5]
        for j in range(3):
            m.agregar(icosfera(0), p(-0.85 + k * 0.42, 0.98, 0.1 + 0.2 * j), 0.2, 0, fruta, (0.9, 1.1))


# -- Rincones secretos (easter eggs) -----------------------------------------------------------------
# Dos puestos de broma (backend/datos/barrio_favela.py, bandera EASTER_EGGS), de juguete y sin marcas: un
# «expendio» de talco de bebé y dulces (brigadeiros y piruletas) y una «armería» de pistolas de agua de colores con
# la punta naranja y globos de agua. Mesa de feria, cartel de cartón (las letras van aparte: letreros_secretos) y
# todo dentro de la malla de objetos de la favela: 0 entidades nuevas salvo los dos Text del cartel.

CARTON = (196, 160, 110)
LETRAS_SECRETOS = {
    "puesto_talco": ("TALCO SUSPEITO", "só pra bebê ;)"),
    "armeria_juguete": ("ARSENAL DE BRINQUEDO", "só água!"),
}
COLORES_PISTOLA = ((120, 220, 60), (240, 70, 170), (40, 190, 230), (250, 210, 40))
NARANJA_PUNTA = (255, 120, 20)


# Rumbo (grados, múltiplo de 90) hacia donde mira el puesto: lo decide el backend (barrio_favela.orientar_secretos:
# hacia el lado por el que se llega), que también pone la mesa que choca con esa misma orientación.
def rumbo_secreto(zona, mundo=None):
    return zona.rumbo


# Punto local del puesto: (a lo largo de la mesa, altura, hacia el frente).
def _local(zona, y, rumbo):
    s, c = math.sin(math.radians(rumbo)), math.cos(math.radians(rumbo))
    return lambda da, dy, df: (zona.cx + c * da + s * df, y + dy, zona.cz - s * da + c * df)


def _mesa_de_feria(m, p, rumbo):
    largo, fondo = 2.4, 0.9                            # backend/datos/barrio_favela.MESA_SECRETA
    m.agregar(caja(), p(0, 0.78, 0), (largo, 0.06, fondo), rumbo, (232, 228, 214), (0.85, 1.0))      # tablero
    m.agregar(caja(), p(0, 0.6, 0.44), (largo, 0.36, 0.03), rumbo, (226, 52, 60), (0.85, 1.0))       # faldón rojo
    for da in (-1.1, 1.1):
        for df in (-0.38, 0.38):
            m.agregar(prisma(6, 0.5, 0.5), p(da, 0, df), (0.05, 0.76, 0.05), 0, (70, 70, 82), (0.8, 1.0))
    # Cartel de cartón detrás de la mesa, sobre dos palos (las letras: letreros_secretos).
    for da in (-0.85, 0.85):
        m.agregar(prisma(6, 0.5, 0.5), p(da, 0, -0.6), (0.05, 1.95, 0.05), 0, (120, 90, 60), (0.8, 1.0))
    m.agregar(caja(), p(0, 1.6, -0.6), (2.1, 0.8, 0.04), rumbo, CARTON, (0.9, 1.05), 0.08)


def puesto_talco(m, zona, y, rumbo):
    p = _local(zona, y, rumbo)
    _mesa_de_feria(m, p, rumbo)
    for k in range(6):                                 # frascos de talco: blancos con tapa rosa o celeste
        da, df = -0.95 + k * 0.32, 0.12 * (k % 2)
        m.agregar(prisma(10, 0.5, 0.42), p(da, 0.81, df), (0.14, 0.24, 0.14), 0, (246, 246, 240), (0.9, 1.05))
        tapa = (240, 140, 170) if k % 2 else (140, 190, 240)
        m.agregar(prisma(10, 0.5, 0.5), p(da, 1.05, df), (0.1, 0.05, 0.1), 0, tapa, (0.9, 1.05))
    for k in range(9):                                 # bandeja de brigadeiros
        m.agregar(icosfera(0), p(0.55 + (k % 3) * 0.1, 0.84, -0.15 + (k // 3) * 0.1), 0.08, 0, (88, 52, 34),
                  (0.8, 1.1))
    m.agregar(caja(), p(0.65, 0.81, -0.05), (0.42, 0.02, 0.38), rumbo, (210, 210, 220), (0.9, 1.0))
    for k, tono in enumerate(((250, 70, 120), (250, 210, 40), (60, 180, 240))):      # piruletas en un vaso
        m.agregar(prisma(6, 0.5, 0.5), p(-0.3 + k * 0.08, 0.81, -0.25), (0.015, 0.4, 0.015), 0, (245, 245, 245))
        m.agregar(prisma(14, 0.5, 0.5), p(-0.3 + k * 0.08, 1.2, -0.25), (0.14, 0.03, 0.14), rumbo, tono, (0.9, 1.1),
                  0.0, 90)


def armeria_juguete(m, zona, y, rumbo):
    p = _local(zona, y, rumbo)
    _mesa_de_feria(m, p, rumbo)
    for k in range(4):                                 # pistolas de agua tumbadas sobre la mesa
        da = -0.95 + k * 0.5
        tono = COLORES_PISTOLA[k % len(COLORES_PISTOLA)]
        m.agregar(caja(), p(da, 0.85, 0.05), (0.32, 0.09, 0.07), rumbo, tono, (0.9, 1.1))               # cuerpo
        m.agregar(caja(), p(da - 0.08, 0.83, -0.08), (0.08, 0.05, 0.16), rumbo, tono, (0.85, 1.05))      # mango
        m.agregar(icosfera(0), p(da + 0.02, 0.93, 0.05), (0.14, 0.09, 0.09), rumbo, (200, 235, 255), (0.9, 1.1))  # tanque
        m.agregar(caja(), p(da + 0.22, 0.85, 0.05), (0.12, 0.04, 0.04), rumbo, tono, (0.9, 1.1))         # cañón
        m.agregar(caja(), p(da + 0.3, 0.85, 0.05), (0.04, 0.05, 0.05), rumbo, NARANJA_PUNTA, (1.0, 1.1))  # punta naranja
    m.agregar(prisma(12, 0.5, 0.42), p(0.85, 0.81, -0.2), (0.34, 0.26, 0.34), 0, (60, 120, 220), (0.85, 1.05))   # balde
    for k, tono in enumerate(((240, 70, 170), (250, 210, 40), (120, 220, 60), (40, 190, 230), (250, 120, 40))):
        m.agregar(icosfera(0), p(0.78 + (k % 3) * 0.08, 1.08 + (k // 3) * 0.06, -0.24 + (k % 2) * 0.08), 0.12, 0,
                  tono, (0.9, 1.15))                  # globos de agua


# Letreros de los rincones secretos: [(texto, (x, y, z), rotation_y, escala)] (el primero grande, el segundo debajo).
# Van como Text sobre la cara del cartel de cartón que mira al frente.
def letreros_secretos(mundo):
    letreros = []
    for zona in mundo.zonas():
        if zona.tipo not in LETRAS_SECRETOS:
            continue
        rumbo = rumbo_secreto(zona, mundo)
        p = _local(zona, mundo.altura(zona.cx, zona.cz), rumbo)
        titulo, nota = LETRAS_SECRETOS[zona.tipo]
        letreros.append((titulo, p(0, 1.76, -0.57), rumbo + 180, 8.0 if len(titulo) <= 14 else 6.2))
        letreros.append((nota, p(0, 1.42, -0.57), rumbo + 180, 6.0))
    return letreros


# -- Pasadizos --------------------------------------------------------------------------------------


# Cuarto sobre un callejón: caja pintada con el color de una pared, losa oscura abajo y dos ventanas en cada cara
# abierta (las que dan al callejón: los extremos del cuarto).
def pasadizo(m, p):
    pintura = PASADIZO_PINTURAS[int(p.semilla * len(PASADIZO_PINTURAS)) % len(PASADIZO_PINTURAS)]
    y = p.y
    m.agregar(caja(), (p.cx, y - 0.1, p.cz), (p.ancho, 0.2, p.fondo), 0, (60, 58, 72), (0.9, 1.0))            # losa inferior
    m.agregar(caja(), (p.cx, y + p.alto / 2, p.cz), (p.ancho - 0.04, p.alto - 0.1, p.fondo - 0.04), 0, pintura, (0.8, 1.05))
    m.agregar(caja(), (p.cx, y + p.alto + 0.05, p.cz), (p.ancho + 0.2, 0.12, p.fondo + 0.2), 0, (130, 134, 150), (0.9, 1.0))  # techo
    a_lo_largo_x = p.ancho < p.fondo                               # el callejón corre a lo largo de x si el cuarto es angosto en x
    # ventanas en las dos caras que miran a lo largo del callejón
    for lado in (-1, 1):
        if a_lo_largo_x:
            pos = (p.cx, y + p.alto * 0.55, p.cz + lado * (p.fondo / 2 + 0.01))
            esc = (min(1.0, p.ancho * 0.5), 0.8, 0.04)
        else:
            pos = (p.cx + lado * (p.ancho / 2 + 0.01), y + p.alto * 0.55, p.cz)
            esc = (0.04, 0.8, min(1.0, p.fondo * 0.5))
        m.agregar(caja(), pos, esc, 0, (40, 54, 80), (1.0, 1.0))
        m.agregar(caja(), pos, (esc[0] + (0.1 if esc[0] > 0.1 else 0), esc[1] + 0.1, esc[2] + (0.1 if esc[2] > 0.1 else 0)), 0,
                  (232, 226, 210), (0.9, 1.0))


PASADIZO_PINTURAS = ((248, 120, 168), (255, 220, 84), (70, 214, 200), (255, 148, 58), (166, 224, 84), (82, 140, 244))


# -- Banderines -----------------------------------------------------------------------------------------


# Malla de banderines (vértices, colores, triángulos) para una lista de Cuerda: la cuerda es una línea de
# tramos finos y de ella cuelgan triángulos de colores.
def datos_banderines(cuerdas):
    vertices, colores, triangulos = [], [], []

    def tri(a, b, c, color):
        base = len(vertices)
        vertices.extend((a, b, c))
        colores.extend([_tono(color, 1.0)] * 3)
        triangulos.append((base, base + 1, base + 2))

    for cuerda in cuerdas:
        pasos = max(4, int(cuerda.largo * 3))
        for k in range(pasos):
            p, q = cuerda.punto(k / pasos), cuerda.punto((k + 1) / pasos)
            # cuerda: un cuadrilátero muy fino (dos triángulos) en tinta
            b = (p[0], p[1] - 0.015, p[2])
            d = (q[0], q[1] - 0.015, q[2])
            tri(p, q, d, (30, 28, 34))
            tri(p, d, b, (30, 28, 34))
        dx, dz = cuerda.b[0] - cuerda.a[0], cuerda.b[2] - cuerda.a[2]
        norma = math.hypot(dx, dz) or 1.0
        ux, uz = dx / norma, dz / norma
        for t, color in fc.banderas_de_cuerda(cuerda):
            c0 = cuerda.punto(t)
            mitad = fc.TAMANO_BANDERA / 2
            a = (c0[0] - ux * mitad, c0[1], c0[2] - uz * mitad)
            b = (c0[0] + ux * mitad, c0[1], c0[2] + uz * mitad)
            punta = (c0[0], c0[1] - fc.TAMANO_BANDERA * 1.15, c0[2])
            tri(a, b, punta, color)
    return vertices, triangulos, colores


# -- Reunión (usa ursina) ----------------------------------------------------------------------------


# Las mallas del detalle de la favela como Mesh (None si no hay nada):
# (objetos, pintura, tinta, banderines, textos). `objetos` lleva lo que tiene volumen (objetos del piso,
# balcones, plantas, cancha y mercado) y proyecta sombra; `pintura` lo pintado sobre las paredes (no proyecta);
# `tinta` las manchas translúcidas; `banderines` las cuerdas con banderas; `textos` los carteles que llevan letras.
# `casas`: CasaDecorativa; `bases`: y de la planta baja de cada una; `mundo`: MundoCiudad (zonas y obstáculos).
def construir_favela_detalles(mundo, casas, bases):
    from ursina import Mesh
    objetos, pintura, tinta = Malla(), Malla(), Malla()
    cuerdas = []
    textos = []
    if casas:
        caras = fc.caras_de_casas(casas)
        for cal in fc.calcomanias(casas, caras):
            destino = objetos if cal.tipo == "balcon" else pintura
            dibujar_calcomania(destino, tinta, cal, bases[cal.casa])
            if cal.tipo == "cartel":
                textos.append(cal)
        redondos = [o for o in mundo.obstaculos() if o.es_circulo]
        for o in fc.objetos_de_calle(casas, caras):
            if any(math.hypot(o.x - r.cx, o.z - r.cz) < r.radio + 0.9 for r in redondos):
                continue
            dibujar_objeto(objetos, o, mundo.altura)
        cuerdas = fc.banderines_de_callejones(casas, caras, bases)
        for p in fc.pasadizos_de_callejones(casas, caras, bases):
            pasadizo(objetos, p)
    for o in mundo.obstaculos():
        if o.tipo == "palmera":
            palmera(objetos, o.cx, mundo.altura(o.cx, o.cz) - 0.1, o.cz, 1.0 + 0.25 * azar_de(o.cx, o.cz),
                    int(azar_de(o.cz, o.cx) * 3))
        elif o.tipo == "bananero":
            bananero(objetos, o.cx, mundo.altura(o.cx, o.cz) - 0.1, o.cz, 1.0 + 0.2 * azar_de(o.cx, o.cz),
                     int(azar_de(o.cz, o.cx) * 3))
    for zona in mundo.zonas():
        h = mundo.altura(zona.cx, zona.cz)
        if zona.tipo == "cancha":
            cancha(objetos, zona, h)
        elif zona.tipo == "mercado":
            mercadito(objetos, zona, h)
        elif zona.tipo == "puesto_talco":
            puesto_talco(objetos, zona, h, rumbo_secreto(zona, mundo))
        elif zona.tipo == "armeria_juguete":
            armeria_juguete(objetos, zona, h, rumbo_secreto(zona, mundo))
    bandera_v, bandera_t, bandera_c = datos_banderines(cuerdas)
    malla_b = Mesh(vertices=bandera_v, triangles=bandera_t, colors=bandera_c) if bandera_v else None
    return objetos.mesh(), pintura.mesh(), tinta.mesh(), malla_b, textos
