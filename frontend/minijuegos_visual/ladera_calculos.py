# Cálculo puro (sin ursina) del mapa de ladera de «Contrarreloj» visual: silueta con cresta escalonada, terrazas, casas
# distintas por zona (color por lugar), manchas de contagio con contorno irregular, línea de peligro rayada y reparto de la
# cinta de noticias. Todo se devuelve como polígonos convexos [(capa, puntos, rgba)] en unidades de pantalla con el origen
# en el centro del mapa, para que la vista los junte en UNA malla (un solo dibujo) en vez de cientos de entidades.
# Tests: tests/test_ladera_calculos.py.

import math
import random

from frontend import estilo
from frontend.minijuegos_visual import mapa_barrio_calculos as mapa

TINTA = estilo.TINTA
PAPEL = estilo.PAPEL
CIELO = (206, 224, 226)
SOL = (255, 226, 120)
TECHO_BASE = (176, 88, 62)
MARGEN = 0.012                      # marco de papel que queda alrededor del paisaje
FACTOR_RADIO = 0.6                  # las manchas son un 40 % más pequeñas que el radio lógico
PASO_RADIO = 0.003                  # el contorno de la mancha solo se regenera cuando el radio cambia este paso

# Altura de la cresta (fracción del alto, desde el centro) por columna: baja hacia la derecha como una ladera.
CRESTA = (0.40, 0.39, 0.38, 0.38, 0.32, 0.28)
LIMITES_TERRAZA = (-0.5, -0.30, -0.10, 0.10, 0.28)
TONOS_TERRAZA = ((205, 202, 142), (218, 198, 142), (226, 190, 138), (214, 178, 128), (200, 166, 118))

# Capas de dibujo: más alto = más cerca de la cámara. Las manchas de contagio van entre el terreno y las casas.
CAPA_TERRENO = 0
CAPA_ESCALERA_TINTA = 2
CAPA_ESCALERA = 3
CAPA_CASA_TINTA = 4
CAPA_PARED = 5
CAPA_TECHO_TINTA = 6
CAPA_TECHO = 7
CAPA_VANO_TINTA = 8
CAPA_VANO = 9
CAPA_DETALLE = 10
CAPA_ETIQUETA_TINTA = 16
CAPA_ETIQUETA = 17
Z_TERRENO = 0.0078
Z_MANCHA = 0.0063
Z_ARO = 0.0060
Z_CASAS = 0.0054
PASO_Z = 0.0003
PASO_Z_CASAS = 0.00025

LUGAR_DE_ZONA = {
    "Morro": "Morro da Esperança",
    "Feira": "Mercado",
    "Escola": "Escola de Samba",
    "Praça": "Praça da Sé",
    "Igreja": "Igreja Nossa Senhora da Esperança",
    "Ponto": "Ponto de Mototáxi da Entrada",
    "Campinho": "Parque",
}


def mezclar(a, b, t):
    """Mezcla RGB: t=0 da `a`, t=1 da `b`."""
    return tuple(int(round(a[k] + (b[k] - a[k]) * t)) for k in range(3))


def color_zona(nombre):
    """Color de identidad del lugar de la zona (estilo.COLORES_LUGAR); un beige neutro si no está."""
    return estilo.COLORES_LUGAR.get(LUGAR_DE_ZONA.get(nombre, ""), (200, 190, 160))


def z_capa(capa):
    """Profundidad de una capa (las capas ≥ CAPA_CASA_TINTA van delante de las manchas, las demás detrás)."""
    if capa < CAPA_CASA_TINTA:
        return Z_TERRENO - PASO_Z * capa
    return Z_CASAS - PASO_Z_CASAS * (capa - CAPA_CASA_TINTA)


def _rect(x0, y0, x1, y1):
    return ((x0, y0), (x1, y0), (x1, y1), (x0, y1))


def _octogono(cx, cy, r):
    return tuple((cx + r * math.cos(math.pi / 8 + k * math.pi / 4), cy + r * math.sin(math.pi / 8 + k * math.pi / 4))
                 for k in range(8))


def _poli(capa, puntos, tono, alfa=255):
    return (capa, tuple(puntos), (tono[0], tono[1], tono[2], alfa))


def _con_tinta(capa_tinta, capa, x0, y0, x1, y1, tono, borde=0.003):
    return [_poli(capa_tinta, _rect(x0 - borde, y0 - borde, x1 + borde, y1 + borde), TINTA),
            _poli(capa, _rect(x0, y0, x1, y1), tono)]


# -- Casas --

def posicion_zona(indice, ancho, alto):
    """Centro de la zona `indice` en unidades de pantalla (origen en el centro del mapa)."""
    _, x, y = mapa.ZONAS[indice % len(mapa.ZONAS)]
    return x * ancho, y * alto


def casas_de_zona(indice, cx, cy):
    """Cuatro casas escalonadas, distintas entre sí y deterministas: [{x, y, w, h, techo, pared, tejado}].
    (x, y) es el centro de la base; bajan hacia la derecha como en una ladera."""
    rng = random.Random(1009 * (indice + 1))
    base = color_zona(mapa.ZONAS[indice % len(mapa.ZONAS)][0])
    escalones = ((-0.112, 0.020), (-0.038, 0.008), (0.038, -0.006), (0.112, -0.018))
    mezclas = [0.62, 0.40, 0.72, 0.30]
    rng.shuffle(mezclas)
    tipos = ["dos_aguas", "plano", "lateral", "dos_aguas"]
    rng.shuffle(tipos)
    casas = []
    for k, (dx, dy) in enumerate(escalones):
        w = rng.choice((0.046, 0.052, 0.058))
        h = rng.choice((0.034, 0.040, 0.046, 0.054))
        pared = mezclar(base, PAPEL, mezclas[k])
        tejado = mezclar(base, TINTA, 0.30) if k % 2 else mezclar(TECHO_BASE, base, 0.25)
        casas.append({"x": cx + dx, "y": cy - 0.046 + dy, "w": w, "h": h, "techo": tipos[k], "pared": pared,
                      "tejado": tejado})
    nombre = mapa.ZONAS[indice % len(mapa.ZONAS)][0]
    if nombre == "Campinho":
        return casas[:2]                    # el resto del sitio es la cancha
    if nombre == "Praça":
        return [casas[0], casas[1], casas[3]]       # el hueco central es de la plaza (el árbol)
    return casas


def poligonos_casa(c):
    """Polígonos de una casa: contorno de tinta, pared, techo (dos aguas, plano o lateral), puerta y ventana."""
    x, y, w, h = c["x"], c["y"], c["w"], c["h"]
    x0, x1 = x - w / 2, x + w / 2
    polis = _con_tinta(CAPA_CASA_TINTA, CAPA_PARED, x0, y, x1, y + h, c["pared"])
    b = 0.003
    if c["techo"] == "dos_aguas":
        pico = (x, y + h + w * 0.42)
        polis.append(_poli(CAPA_TECHO_TINTA, ((x0 - 0.009, y + h - b), (x1 + 0.009, y + h - b), (pico[0], pico[1] + 0.005)), TINTA))
        polis.append(_poli(CAPA_TECHO, ((x0 - 0.006, y + h), (x1 + 0.006, y + h), pico), c["tejado"]))
    elif c["techo"] == "lateral":
        polis.append(_poli(CAPA_TECHO_TINTA, ((x0 - 0.009, y + h - b), (x1 + 0.009, y + h - b), (x1 + 0.009, y + h + w * 0.30)), TINTA))
        polis.append(_poli(CAPA_TECHO, ((x0 - 0.006, y + h), (x1 + 0.006, y + h), (x1 + 0.006, y + h + w * 0.26)), c["tejado"]))
    else:
        polis += _con_tinta(CAPA_TECHO_TINTA, CAPA_TECHO, x0 - 0.005, y + h, x1 + 0.005, y + h + 0.010, c["tejado"])
    pw = w * 0.22
    polis.append(_poli(CAPA_VANO, _rect(x1 - w * 0.36 - pw / 2, y, x1 - w * 0.36 + pw / 2, y + h * 0.5), TINTA))
    vx = x0 + w * 0.30
    vy = y + h * 0.58
    polis += _con_tinta(CAPA_VANO_TINTA, CAPA_VANO, vx - 0.006, vy - 0.006, vx + 0.006, vy + 0.006, (255, 236, 160), 0.002)
    return polis


def detalles_zona(indice, cx, cy, casas):
    """Un elemento propio de cada lugar: cruz (iglesia), bandera (escuela), toldo a rayas (feria, ponto), árbol (plaza)
    o cancha (campinho)."""
    nombre = mapa.ZONAS[indice % len(mapa.ZONAS)][0]
    base = color_zona(nombre)
    polis = []
    alta = max(casas, key=lambda c: c["h"])
    if nombre == "Igreja":
        tx, ty = alta["x"], alta["y"] + alta["h"] + alta["w"] * 0.42 + 0.004
        polis.append(_poli(CAPA_DETALLE, _rect(tx - 0.003, ty, tx + 0.003, ty + 0.026), TINTA))
        polis.append(_poli(CAPA_DETALLE, _rect(tx - 0.010, ty + 0.014, tx + 0.010, ty + 0.020), TINTA))
    elif nombre == "Escola":
        c = casas[0]
        tx, ty = c["x"] + 0.012, c["y"] + c["h"] + 0.004
        polis.append(_poli(CAPA_DETALLE, _rect(tx - 0.0022, ty, tx + 0.0022, ty + 0.040), TINTA))
        polis += _con_tinta(CAPA_DETALLE, CAPA_DETALLE + 1, tx + 0.002, ty + 0.022, tx + 0.026, ty + 0.038, base, 0.002)
    elif nombre in ("Feira", "Ponto"):
        c = casas[2]
        rayas = (base, PAPEL)
        n = 6
        ancho = c["w"] + 0.016
        for k in range(n):
            x0 = c["x"] - ancho / 2 + ancho * k / n
            polis.append(_poli(CAPA_DETALLE, _rect(x0, c["y"] + c["h"] * 0.52, x0 + ancho / n, c["y"] + c["h"] * 0.72), rayas[k % 2]))
        polis.append(_poli(CAPA_VANO_TINTA, _rect(c["x"] - ancho / 2 - 0.002, c["y"] + c["h"] * 0.50, c["x"] + ancho / 2 + 0.002,
                                                   c["y"] + c["h"] * 0.74), TINTA))
    elif nombre == "Praça":
        tx, ty = cx + 0.038, cy - 0.052
        polis.append(_poli(CAPA_DETALLE, _rect(tx - 0.003, ty, tx + 0.003, ty + 0.022), TINTA))
        polis.append(_poli(CAPA_DETALLE, _octogono(tx, ty + 0.034, 0.024), TINTA))
        polis.append(_poli(CAPA_DETALLE + 1, _octogono(tx, ty + 0.034, 0.020), (96, 160, 92)))
    elif nombre == "Campinho":
        polis += _con_tinta(CAPA_DETALLE, CAPA_DETALLE + 1, cx + 0.010, cy - 0.060, cx + 0.150, cy - 0.026, (128, 176, 96), 0.003)
        polis.append(_poli(CAPA_DETALLE + 2, _rect(cx + 0.078, cy - 0.060, cx + 0.082, cy - 0.026), PAPEL))
        polis.append(_poli(CAPA_DETALLE + 2, _octogono(cx + 0.080, cy - 0.043, 0.009), PAPEL))
        polis.append(_poli(CAPA_DETALLE + 3, _octogono(cx + 0.080, cy - 0.043, 0.006), (128, 176, 96)))
    return polis


# -- Escenario completo --

def _cresta_en(x, ancho, alto):
    """Altura (unidades de pantalla) de la cresta en la coordenada x."""
    k = int((x / ancho + 0.5) * len(CRESTA))
    return CRESTA[max(0, min(len(CRESTA) - 1, k))] * alto


def etiqueta_de_zona(indice, cx, cy):
    """Centro (x, y) de la chapa con el nombre de la zona."""
    return cx, cy + 0.066


def escenario(ancho, alto, anchos_etiqueta):
    """Todos los polígonos estáticos del mapa. `anchos_etiqueta`: ancho de cada nombre de zona (por índice de ZONAS)."""
    w2, h2 = ancho / 2 - MARGEN, alto / 2 - MARGEN
    polis = []
    # Cielo escalonado y sol.
    n = len(CRESTA)
    for k in range(n):
        x0 = -w2 + (2 * w2) * k / n
        x1 = -w2 + (2 * w2) * (k + 1) / n
        polis.append(_poli(CAPA_TERRENO, _rect(x0, CRESTA[k] * alto, x1, h2), CIELO))
        polis.append(_poli(CAPA_TERRENO, _rect(x0, CRESTA[k] * alto - 0.004, x1, CRESTA[k] * alto), TINTA))
    sx, sy = 0.40 * ancho, (CRESTA[-1] * alto + h2) / 2
    polis.append(_poli(CAPA_TERRENO + 1, _octogono(sx, sy, 0.034), TINTA))
    polis.append(_poli(CAPA_TERRENO + 2, _octogono(sx, sy, 0.028), SOL))
    # Terrazas: bandas de color con muro de tinta y una escalera por muro.
    limites = [l * alto for l in LIMITES_TERRAZA]
    for k, y0 in enumerate(limites):
        for j in range(n):
            x0 = -w2 + (2 * w2) * j / n
            x1 = -w2 + (2 * w2) * (j + 1) / n
            techo = limites[k + 1] if k + 1 < len(limites) else CRESTA[j] * alto - 0.004
            techo = min(techo, CRESTA[j] * alto - 0.004)
            if techo > y0:
                polis.append(_poli(CAPA_TERRENO, _rect(x0, max(y0, -h2), x1, techo), TONOS_TERRAZA[k]))
        if k:
            polis.append(_poli(CAPA_TERRENO + 1, _rect(-w2, y0 - 0.0035, w2, y0 + 0.0035), TINTA))
    escaleras_x = (-0.16, 0.13, 0.13, -0.12)
    for k, y0 in enumerate(limites[1:]):
        ex = escaleras_x[k % len(escaleras_x)] * ancho
        for paso in range(4):
            yy = y0 - 0.006 - paso * 0.0095
            polis += _con_tinta(CAPA_ESCALERA_TINTA, CAPA_ESCALERA, ex - 0.018 - paso * 0.003, yy - 0.0042,
                                ex + 0.018 + paso * 0.003, yy + 0.0042, PAPEL, 0.0022)
    # Casas, detalles y chapas de nombre.
    for i in range(len(mapa.ZONAS)):
        cx, cy = posicion_zona(i, ancho, alto)
        casas = casas_de_zona(i, cx, cy)
        for c in casas:
            polis += poligonos_casa(c)
        polis += detalles_zona(i, cx, cy, casas)
        ex, ey = etiqueta_de_zona(i, cx, cy)
        ew = anchos_etiqueta[i] if i < len(anchos_etiqueta) else 0.1
        polis += _con_tinta(CAPA_ETIQUETA_TINTA, CAPA_ETIQUETA, ex - ew / 2, ey - 0.0155, ex + ew / 2, ey + 0.0155, PAPEL, 0.003)
    return polis


def malla(polis):
    """(vértices[(x, y, z)], triángulos[(a, b, c)], colores[(r, g, b, a)]) para UNA sola Mesh con color por vértice."""
    vertices, triangulos, colores = [], [], []
    for capa, puntos, rgba in polis:
        z = z_capa(capa)
        base = len(vertices)
        for p in puntos:
            vertices.append((p[0], p[1], z))
            colores.append(rgba)
        for k in range(1, len(puntos) - 1):
            triangulos.append((base, base + k, base + k + 1))
    return vertices, triangulos, colores


# -- Manchas de contagio --

def radio_visible(radio, x, y, ancho, alto, tope=0.12):
    """Radio en pantalla de la mancha: un 40 % menor que antes y recortado para no salirse del mapa."""
    en_pantalla = radio * alto * FACTOR_RADIO
    margen_x = (0.5 - abs(x)) * ancho
    margen_y = (0.5 - abs(y)) * alto
    return max(0.008, min(en_pantalla, margen_x, margen_y, tope))


def cuantizar_radio(radio, paso=PASO_RADIO):
    return max(paso, round(radio / paso) * paso)


def contorno_mancha(radio, fase=0.0, n=26, irregular=0.06):
    """Contorno irregular (una mancha, no un círculo perfecto) de `n` puntos alrededor de (0, 0)."""
    puntos = []
    for k in range(n):
        a = 2 * math.pi * k / n
        r = radio * (1 + irregular * (0.7 * math.sin(3 * a + fase) + 0.3 * math.sin(5 * a + 2 * fase)))
        puntos.append((r * math.cos(a), r * math.sin(a)))
    return puntos


def malla_relleno(fase=0.0, n=26):
    """Abanico de la mancha de radio 1 (se escala al radio): (vértices, triángulos)."""
    contorno = contorno_mancha(1.0, fase, n)
    vertices = [(0.0, 0.0, 0.0)] + [(x, y, 0.0) for x, y in contorno]
    triangulos = [(0, 1 + k, 1 + (k + 1) % n) for k in range(n)]
    return vertices, triangulos


def malla_anillo(radio, grosor, fase=0.0, n=26):
    """Anillo de grosor constante con el mismo contorno que la mancha: (vértices, triángulos)."""
    exterior = contorno_mancha(radio, fase, n)
    interior = contorno_mancha(max(radio - grosor, 0.0001), fase, n)
    vertices = [(x, y, 0.0) for x, y in exterior] + [(x, y, 0.0) for x, y in interior]
    triangulos = []
    for k in range(n):
        j = (k + 1) % n
        triangulos.append((k, j, n + j))
        triangulos.append((k, n + j, n + k))
    return vertices, triangulos


# -- Línea de peligro rayada --

def franjas_peligro(ancho, alto, n=14, amarillo=(255, 214, 40)):
    """Polígonos [(puntos, rgba)] de una cinta amarilla con franjas negras inclinadas, centrada en (0, 0)."""
    polis = [(_rect(-ancho / 2, -alto / 2, ancho / 2, alto / 2), amarillo + (255,))]
    paso = ancho / n
    for k in range(n):
        x0 = -ancho / 2 + k * paso
        if k % 2 == 0:
            a, b = x0, x0 + paso * 0.55
            polis.append((((a, -alto / 2), (b, -alto / 2), (b + alto * 0.6, alto / 2), (a + alto * 0.6, alto / 2)), TINTA + (255,)))
    return [(_recortar_ancho(p, ancho), c) for p, c in polis]


def _recortar_ancho(puntos, ancho):
    """Recorta en x a ±ancho/2 (las franjas inclinadas se pasarían por la derecha)."""
    limite = ancho / 2
    return tuple((max(-limite, min(limite, x)), y) for x, y in puntos)
