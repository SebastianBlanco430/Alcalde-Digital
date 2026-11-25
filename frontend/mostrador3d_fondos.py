# Fondos del MOSTRADOR 3D (frontend/mostrador3d_escena.py): lo que el jugador ve detrás del cliente, distinto en cada
# local. Cada local de backend/datos/mostrador3d_locales.json elige el suyo con la clave "fondo":
#   mercado      la calle de la feria: puestos con toldos de rayas, cajas de fruta, banderines y el cerro con casas
#   panaderia    interior: baldosas, azulejos, vitrina con panes, estante de canastas, pizarra con los precios del local,
#                puerta y ventana a la calle; luz cálida
#   supermercado interior: suelo blanco, góndolas con productos de colores, carteles de pasillo, otra caja con su cinta y
#                fluorescentes; luz fría
#   bar          boteco al atardecer: mesas y sillas de plástico, cajas de cerveza, tele con el partido, guirnalda de
#                bombillas y la calle por el portón
# Todo por código (props_mundo) en UNA malla con sombras por fondo; los carteles con texto y las bombillas van aparte
# (carteles()). Un fondo desconocido usa el mercado. exterior(nombre) dice si el puesto lleva toldo y postes (calle) o
# techo con lámparas (interior).

from frontend import mostrador3d_productos as mp
from frontend.azar_fijo import azar_de
from frontend.props_mundo import Malla, caja, icosfera, prisma

MADERA, MADERA_OSCURA = (150, 104, 64), (104, 70, 44)
TOLDOS = ((214, 70, 60), (60, 140, 200), (236, 190, 60), (70, 160, 100), (200, 110, 170))
CASAS = ((232, 196, 150), (196, 120, 96), (120, 170, 200), (236, 220, 120), (160, 200, 150), (214, 150, 120))
# Sala de los interiores (m): de pared a pared en x, de la cara del mostrador a la pared del fondo en z, alto del techo.
X_SALA, Z_FONDO, ALTO_SALA = 5.0, 5.6, 3.0
# pared de detrás del jugador (la sala queda cerrada aunque gire la cabeza: mirada libre del mostrador)
Z_ATRAS = -2.6
# Pizarra de la panadería y tele del bar, en la pared del fondo (centro, m)
PIZARRA = (-3.3, 1.62, Z_FONDO - 0.07)
TELE = (-3.5, 1.85, Z_FONDO - 0.07)
# panes de la vitrina y de las canastas (escala sobre los ~12 cm de mostrador3d_productos: se ven desde el mostrador)
ESCALA_PAN, ESCALA_PAN_CANASTA = 2.6, 1.6
# portón del bar y su letrero: por debajo de la cabecera 2D de la escena (que tapa lo que queda más alto) y a la
# izquierda del centro, donde no lo tapa la cabeza del cliente ni el cartel 2D de la derecha
ALTO_PORTON, X_LETRERO, Y_LETRERO, ANCHO_LETRERO = 1.75, -1.55, 1.98, 1.8
# Luz de cada fondo: (cielo, ambiente, sol) en RGB 0-255 y si es exterior.
LUZ = {
    "mercado": ((150, 200, 236), (140, 136, 132), (255, 250, 240), True),
    "panaderia": ((236, 214, 170), (122, 108, 94), (226, 196, 160), False),
    "supermercado": ((220, 226, 232), (150, 156, 166), (236, 244, 255), False),
    "bar": ((238, 150, 112), (128, 104, 100), (255, 196, 150), False),
}


def nombre_fondo(local):
    nombre = local.get("fondo", "mercado")
    return nombre if nombre in LUZ else "mercado"


def exterior(nombre):
    return LUZ.get(nombre, LUZ["mercado"])[3]


def luz(nombre):
    """(cielo, ambiente, sol) del fondo."""
    return LUZ.get(nombre, LUZ["mercado"])[:3]


def malla_fondo(nombre, local):
    """Malla del fondo `nombre` para el `local` (sin el puesto del jugador)."""
    m = Malla()
    FONDOS.get(nombre, _mercado)(m, local)
    return m


def _producto(m, producto, pos, escala=1.0, giro=0.0):
    """Copia la malla de un producto (mostrador3d_productos) dentro de `m`, en `pos`, escalada y girada sobre y."""
    import math
    sub = mp.malla_producto(producto)
    s, c = math.sin(math.radians(giro)), math.cos(math.radians(giro))
    for (x, y, z), n, col in zip(sub.vertices, sub.normales, sub.colores):
        x, y, z = x * escala, y * escala, z * escala
        m.vertices.append((pos[0] + x * c + z * s, pos[1] + y, pos[2] - x * s + z * c))
        m.normales.append((n[0] * c + n[2] * s, n[1], -n[0] * s + n[2] * c))
        m.colores.append(col)


# -- Calle del mercado --

def _mercado(m, local):
    m.agregar(caja(), (0, -0.05, 5.0), (24, 0.1, 16), 0, (128, 124, 118), (1, 1), 0.06)
    for k in range(-10, 11):
        m.agregar(caja(), (k * 1.1, 0.002, 2.4), (0.04, 0.004, 4.0), 0, (110, 106, 102), (1, 1))
    # puestos de enfrente con toldos de rayas, cajas de fruta y banderines
    for k, x in enumerate((-5.2, -2.6, 0.0, 2.6, 5.2)):
        tono = TOLDOS[k % len(TOLDOS)]
        m.agregar(caja(), (x, 0.45, 5.4), (2.2, 0.9, 0.7), 0, MADERA, (0.8, 1.05), 0.06)
        for j in range(6):
            m.agregar(caja(), (x - 1.0 + j * 0.4, 2.3, 5.2), (0.2, 0.04, 1.6), 0, tono if j % 2 else (244, 240, 230),
                      (1, 1), 0, -12)
        for dx in (-1.05, 1.05):
            m.agregar(caja(), (x + dx, 1.15, 5.75), (0.06, 2.3, 0.06), 0, MADERA_OSCURA)
        for j in range(4):
            fruta = TOLDOS[(k + j) % len(TOLDOS)]
            m.agregar(caja(), (x - 0.75 + j * 0.5, 0.97, 5.3), (0.42, 0.14, 0.4), 0, MADERA_OSCURA)
            m.agregar(caja(), (x - 0.75 + j * 0.5, 1.06, 5.3), (0.36, 0.06, 0.34), 0, fruta, (0.8, 1.1), 0.25)
    for k in range(18):
        m.agregar(prisma(3, 0.5, 0.0), (-6.0 + k * 0.7, 3.5, 4.2), (0.16, 0.2, 0.02), 0, TOLDOS[k % len(TOLDOS)],
                  (1, 1), 0, 180)
    _cerro(m, 9.0)


def _cerro(m, z0, filas=3):
    """Casas de la favela subiendo el cerro, al fondo (también se ven por las puertas de los interiores)."""
    for fila in range(filas):
        for k in range(9):
            x = -9.0 + k * 2.2 + fila * 0.9
            alto = 2.4 + (k * 7 + fila * 3) % 3 * 0.8
            z, y0 = z0 + fila * 3.0, fila * 2.2
            tono = CASAS[(k + fila * 2) % len(CASAS)]
            m.agregar(caja(), (x, y0 + alto / 2, z), (2.0, alto, 2.4), 0, tono, (0.8, 1.05), 0.05)
            for dx in (-0.4, 0.45):
                m.agregar(caja(), (x + dx, y0 + alto * 0.62, z - 1.21), (0.4, 0.45, 0.02), 0, (60, 64, 76), (1, 1))


# -- Sala común de los interiores --

def _sala(m, suelo_a, suelo_b, pared_baja, pared_alta, techo=(236, 232, 224), lado=0.5, hueco=None):
    """Suelo de baldosas en damero, paredes (zócalo de azulejos + pintura) y techo sobre todo, también sobre el puesto.
    hueco: (x0, x1, alto) abierto en la pared del fondo (puerta, portón), por donde se ve la calle."""
    n_x, n_z = int(2 * X_SALA / lado), int((Z_FONDO - Z_ATRAS) / lado) + 1
    for i in range(n_x):
        for j in range(n_z):
            tono = suelo_a if (i + j) % 2 == 0 else suelo_b
            m.agregar(caja(), (-X_SALA + (i + 0.5) * lado, -0.02, Z_ATRAS + (j + 0.5) * lado), (lado, 0.04, lado), 0, tono,
                      (1, 1))
    # pared del fondo (con el hueco, si lo hay) y paredes laterales
    tramos = [(-X_SALA, X_SALA)] if hueco is None else [(-X_SALA, hueco[0]), (hueco[1], X_SALA)]
    for x0, x1 in tramos:
        ancho, cx = x1 - x0, (x0 + x1) / 2
        m.agregar(caja(), (cx, 0.65, Z_FONDO), (ancho, 1.3, 0.1), 0, pared_baja, (0.9, 1.05))
        m.agregar(caja(), (cx, 1.3 + (ALTO_SALA - 1.3) / 2, Z_FONDO), (ancho, ALTO_SALA - 1.3, 0.1), 0, pared_alta,
                  (0.95, 1.05))
    if hueco is not None:
        x0, x1, alto = hueco
        m.agregar(caja(), ((x0 + x1) / 2, alto + (ALTO_SALA - alto) / 2, Z_FONDO), (x1 - x0, ALTO_SALA - alto, 0.1), 0,
                  pared_alta, (0.95, 1.05))
    for lado_x in (-1, 1):
        m.agregar(caja(), (lado_x * X_SALA, ALTO_SALA / 2, (Z_FONDO + Z_ATRAS) / 2), (0.1, ALTO_SALA, Z_FONDO - Z_ATRAS), 0,
                  pared_alta, (0.85, 1.05))
        m.agregar(caja(), (lado_x * (X_SALA - 0.06), 0.65, (Z_FONDO + Z_ATRAS) / 2), (0.02, 1.3, Z_FONDO - Z_ATRAS), 0,
                  pared_baja, (0.9, 1.05))
    # juntas de los azulejos del zócalo (pared del fondo)
    for k in range(1, 4):
        m.agregar(caja(), (0, 0.325 * k, Z_FONDO - 0.055), (2 * X_SALA, 0.012, 0.01), 0, (235, 235, 235), (1, 1))
    # pared de detrás del jugador (zócalo + pintura) y techo sobre toda la sala
    m.agregar(caja(), (0, 0.65, Z_ATRAS), (2 * X_SALA, 1.3, 0.1), 0, pared_baja, (0.9, 1.05))
    m.agregar(caja(), (0, 1.3 + (ALTO_SALA - 1.3) / 2, Z_ATRAS), (2 * X_SALA, ALTO_SALA - 1.3, 0.1), 0, pared_alta,
              (0.95, 1.05))
    m.agregar(caja(), (0, ALTO_SALA + 0.05, (Z_FONDO + Z_ATRAS) / 2), (2 * X_SALA, 0.1, Z_FONDO - Z_ATRAS), 0, techo,
              (1, 1))


# -- Panadería --

def _panaderia(m, local):
    _sala(m, (226, 210, 180), (186, 104, 72), (214, 226, 232), (222, 196, 150), hueco=(2.2, 3.4, 2.2))
    pan = next((p for p in local["productos"] if p["forma"] == "pan"), local["productos"][0])
    bollo = next((p for p in local["productos"] if p["forma"] == "bollo"), pan)
    # vitrina abierta a lo largo de la pared del fondo: base de madera, panes y bollos encima (a la vista) y un techo de
    # vidrio fino sobre cuatro postes
    m.agregar(caja(), (-1.0, 0.45, Z_FONDO - 0.45), (3.6, 0.9, 0.6), 0, MADERA, (0.8, 1.05), 0.05)
    m.agregar(caja(), (-1.0, 0.905, Z_FONDO - 0.45), (3.5, 0.01, 0.52), 0, (236, 228, 210), (1, 1))
    for dx in (-1.75, -0.6, 0.6, 1.75):
        m.agregar(caja(), (-1.0 + dx, 1.15, Z_FONDO - 0.2), (0.03, 0.5, 0.03), 0, MADERA_OSCURA)
    m.agregar(caja(), (-1.0, 1.41, Z_FONDO - 0.45), (3.64, 0.02, 0.64), 0, (196, 226, 232), (1, 1.05))
    for k in range(7):
        _producto(m, pan if k % 2 else bollo, (-2.5 + 0.5 * k, 0.91, Z_FONDO - 0.5), ESCALA_PAN, 30 * k)
    # estante con canastas de pan encima de la vitrina
    for fila in range(2):
        y = 1.6 + 0.45 * fila
        m.agregar(caja(), (-1.0, y, Z_FONDO - 0.18), (3.6, 0.04, 0.3), 0, MADERA_OSCURA)
        for k in range(5):
            x = -2.4 + 0.7 * k
            m.agregar(prisma(10, 0.5, 0.42), (x, y + 0.02, Z_FONDO - 0.2), (0.42, 0.14, 0.26), 0, (190, 150, 90),
                      (0.8, 1.05))
            for j in range(3):
                _producto(m, pan, (x - 0.1 + 0.1 * j, y + 0.1, Z_FONDO - 0.2), ESCALA_PAN_CANASTA, 70 + 20 * j)
    # puerta de la calle (marco) y la calle con el cerro detrás
    for dx in (2.15, 3.45):
        m.agregar(caja(), (dx, 1.1, Z_FONDO), (0.1, 2.2, 0.14), 0, MADERA_OSCURA)
    _cerro(m, Z_FONDO + 4.0, filas=2)
    # pizarra del cardápio en la pared del fondo, a la izquierda de la vitrina (el texto lo pone carteles())
    m.agregar(caja(), PIZARRA, (1.3, 1.0, 0.03), 0, (40, 52, 46), (1, 1))
    m.agregar(caja(), (PIZARRA[0], PIZARRA[1], PIZARRA[2] + 0.01), (1.38, 1.08, 0.03), 0, MADERA_OSCURA)
    _lamparas(m, (255, 236, 196))


def _lamparas(m, tono, filas=((-2.0, 2.0), (0.0, 2.0), (2.0, 2.0))):
    for x, z in filas:
        m.agregar(caja(), (x, ALTO_SALA - 0.25, z), (0.01, 0.5, 0.01), 0, (40, 40, 44), (1, 1))
        m.agregar(prisma(14, 0.5, 0.2), (x, ALTO_SALA - 0.68, z), (0.4, 0.18, 0.4), 0, (60, 62, 70), (1, 1))
        m.agregar(icosfera(1), (x, ALTO_SALA - 0.7, z), 0.12, 0, tono, (1.2, 1.3))


# -- Supermercado --

PRODUCTOS_GONDOLA = ((214, 60, 52), (60, 120, 200), (240, 200, 60), (80, 170, 100), (236, 236, 230), (200, 110, 170),
                     (240, 140, 60), (120, 80, 60))


def _supermercado(m, local):
    _sala(m, (236, 238, 240), (214, 218, 224), (204, 220, 232), (238, 240, 242), techo=(244, 244, 246), lado=0.6)
    # góndolas de frente al jugador, con pasillos entre ellas
    for fila, z in enumerate((3.0, 4.6)):
        for k, x in enumerate((-3.2, 0.0, 3.2)):
            _gondola(m, x + (0.8 if fila else 0.0), z, fila * 3 + k)
    # otra caja a la izquierda, con su cinta y su silla
    m.agregar(caja(), (-3.1, 0.45, 1.3), (1.6, 0.9, 0.6), 0, (176, 180, 188), (0.85, 1.05))
    m.agregar(caja(), (-3.1, 0.91, 1.3), (1.2, 0.03, 0.4), 0, (40, 40, 46), (1, 1))
    m.agregar(caja(), (-2.1, 1.0, 1.3), (0.3, 0.22, 0.3), 0, (70, 74, 84), (1, 1))
    # tubos fluorescentes en el techo
    for x in (-3.0, 0.0, 3.0):
        for z in (1.5, 3.5):
            m.agregar(caja(), (x, ALTO_SALA - 0.06, z), (1.6, 0.06, 0.16), 0, (250, 252, 255), (1.3, 1.3))


def _gondola(m, x, z, semilla):
    m.agregar(caja(), (x, 0.9, z + 0.18), (2.4, 1.8, 0.06), 0, (190, 194, 200), (0.9, 1.05))
    for dx in (-1.2, 1.2):
        m.agregar(caja(), (x + dx, 0.9, z), (0.05, 1.8, 0.4), 0, (150, 154, 162))
    for nivel in range(4):
        y = 0.15 + 0.45 * nivel
        m.agregar(caja(), (x, y, z), (2.4, 0.03, 0.4), 0, (170, 174, 182))
        for k in range(12):
            u = azar_de(semilla * 13 + nivel, k)
            tono = PRODUCTOS_GONDOLA[int(u * len(PRODUCTOS_GONDOLA)) % len(PRODUCTOS_GONDOLA)]
            alto = 0.16 + 0.14 * azar_de(k, semilla + nivel)
            m.agregar(caja(), (x - 1.08 + 0.196 * k, y + 0.015 + alto / 2, z - 0.05), (0.16, alto, 0.22), 0, tono,
                      (0.85, 1.1))


# -- Bar (boteco) --

def _bar(m, local):
    _sala(m, (176, 84, 62), (150, 70, 52), (60, 140, 100), (236, 214, 150), techo=(120, 84, 60), hueco=(-1.6, 1.6, ALTO_PORTON))
    # tabla del letrero sobre el portón (el texto lo pone carteles())
    m.agregar(caja(), (X_LETRERO, Y_LETRERO, Z_FONDO - 0.07), (ANCHO_LETRERO, 0.36, 0.04), 0, (120, 36, 34), (0.95, 1.05))
    m.agregar(caja(), (X_LETRERO, Y_LETRERO, Z_FONDO - 0.05), (ANCHO_LETRERO + 0.1, 0.44, 0.03), 0, MADERA_OSCURA)
    # la calle al atardecer por el portón: acera, una casa de enfrente y el cerro
    m.agregar(caja(), (0, -0.04, Z_FONDO + 3.0), (12, 0.06, 6.0), 0, (120, 112, 104), (1, 1))
    _cerro(m, Z_FONDO + 5.0, filas=2)
    # mesas y sillas de plástico rojas
    for k, (x, z) in enumerate(((-3.0, 2.2), (2.8, 2.5), (-0.4, 3.8))):
        tono = (206, 52, 46) if k % 2 == 0 else (236, 190, 50)
        m.agregar(caja(), (x, 0.72, z), (0.7, 0.04, 0.7), 0, tono, (0.9, 1.1))
        for dx in (-0.3, 0.3):
            for dz in (-0.3, 0.3):
                m.agregar(caja(), (x + dx, 0.36, z + dz), (0.04, 0.72, 0.04), 0, tono)
        for dx, dz, giro in ((-0.55, 0, 90), (0.55, 0, -90), (0, 0.55, 180)):
            m.agregar(caja(), (x + dx, 0.42, z + dz), (0.4, 0.04, 0.4), giro, tono, (0.9, 1.1))
            m.agregar(caja(), (x + dx * 1.35, 0.68, z + dz * 1.35), (0.4 if dz else 0.04, 0.5, 0.04 if dz else 0.4), 0,
                      tono, (0.9, 1.1))
            for ex in (-0.16, 0.16):
                m.agregar(caja(), (x + dx + (ex if dz else 0), 0.2, z + dz + (0 if dz else ex)), (0.03, 0.4, 0.03), 0,
                          tono)
        # botellas de cerveza sobre la mesa
        for j in range(2):
            m.agregar(prisma(8), (x - 0.1 + 0.2 * j, 0.74, z), (0.07, 0.24, 0.07), 0, (110, 70, 30), (0.9, 1.2))
    # cajas de cerveza apiladas contra la pared
    for k in range(6):
        x, y = 3.8 + 0.42 * (k % 2), 0.15 + 0.3 * (k // 2)
        m.agregar(caja(), (x, y, Z_FONDO - 0.5), (0.4, 0.28, 0.32), 0, (236, 196, 40), (0.85, 1.05))
    # tele en la pared del fondo, a la izquierda del portón, con el partido (cancha verde con sus líneas)
    x, y, z = TELE
    m.agregar(caja(), (x, y, z + 0.02), (1.15, 0.7, 0.08), 0, (24, 24, 28), (1, 1))
    m.agregar(caja(), (x, y, z - 0.03), (1.05, 0.6, 0.02), 0, (60, 150, 70), (1.1, 1.2))
    m.agregar(caja(), (x, y, z - 0.045), (0.015, 0.6, 0.01), 0, (240, 240, 240), (1, 1))


FONDOS = {"mercado": _mercado, "panaderia": _panaderia, "supermercado": _supermercado, "bar": _bar}


# -- Carteles con texto y luces (entidades aparte de la malla) --

def carteles(raiz, nombre, local):
    """Textos y bombillas del fondo: pizarra con precios (panadería), carteles de pasillo (supermercado), guirnalda y
    marcador (bar). Sin texto en el mercado."""
    from ursina import Entity, Text
    from ursina.shaders import unlit_shader
    from backend.logica.mostrador3d_dinero import formatear
    from frontend.componentes import rgb
    if nombre == "panaderia":
        x, y, z = PIZARRA
        Text(parent=raiz, text="CARDÁPIO", scale=3.4, origin=(0, 0), color=rgb((244, 240, 220)),
             position=(x, y + 0.36, z - 0.03))
        for k, p in enumerate(local["productos"]):
            Text(parent=raiz, text=f"{p['nombre']}  {formatear(p['precio'])}", scale=2.6, origin=(0, 0),
                 color=rgb((236, 232, 200)), position=(x, y + 0.12 - 0.17 * k, z - 0.03))
    elif nombre == "supermercado":
        for fila, z in enumerate((3.0, 4.6)):
            for k, (x, texto) in enumerate(((-3.2, "ARROZ E FEIJÃO"), (0.0, "LIMPEZA"), (3.2, "BEBIDAS"))):
                cx = x + (0.8 if fila else 0.0)
                if fila:
                    texto = ("MERCEARIA", "HIGIENE", "PADARIA")[k]
                Entity(parent=raiz, model="cube", color=rgb((40, 96, 176)), shader=unlit_shader,
                       position=(cx, 2.45, z - 0.3), scale=(1.5, 0.32, 0.03))
                Text(parent=raiz, text=texto, scale=3.0, origin=(0, 0), color=rgb((250, 250, 250)),
                     position=(cx, 2.45, z - 0.32))
    elif nombre == "bar":
        Text(parent=raiz, text="BRA 2 x 1 ARG", scale=2.0, origin=(0, 0), color=rgb((250, 250, 250)),
             position=(TELE[0], TELE[1] + 0.22, TELE[2] - 0.06))
        Text(parent=raiz, text="BAR DA ESQUINA", scale=5.5, origin=(0, 0), color=rgb((250, 220, 120)),
             position=(X_LETRERO, Y_LETRERO, Z_FONDO - 0.1))
        # guirnalda de bombillas de lado a lado del techo
        for k in range(14):
            x = -4.2 + 0.65 * k
            Entity(parent=raiz, model="sphere", color=rgb((255, 220, 140)), shader=unlit_shader, scale=0.07,
                   position=(x, ALTO_SALA - 0.35 - 0.12 * abs(((k % 7) - 3) / 3), 2.0 + 0.9 * (k // 7)))
