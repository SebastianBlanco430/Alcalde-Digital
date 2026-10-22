# Piezas geométricas puras de la bicicleta y la moto (NO importa ursina ni panda3d): cada vehículo es un
# conjunto de GRUPOS de piezas (cuadro, manubrio con la rueda delantera, rueda trasera, bielas, pedales, luz...)
# que frontend/vehiculo_modelo.py convierte en mallas de Panda3D y mueve por separado (ruedas que giran, manubrio
# que gira, pedales). Aquí solo hay datos y malla, así que se prueba con pytest sin ventana.
#
# Ejes (los del mundo): x a la derecha, y arriba, z hacia adelante. El origen está en el suelo, a mitad de la
# batalla. Cada grupo guarda sus piezas relativas a su `pivote`, que es donde el modelo lo cuelga y lo gira.
#
# Estética Borderlands: colores planos y saturados (las bandas de luz de malla_calculos van horneadas en el color
# de los vértices), tubos gruesos y un casco de tinta (la misma pieza inflada, dibujada por sus caras traseras)
# que vehiculo_modelo.py añade con el mismo método geométrico de contorno_calculos.py. Favela: pintura con parches
# de otro color, bici vieja de colores con cesta y caja de carga, moto de reparto / mototaxi con baúl.

import math
from dataclasses import dataclass, field

from frontend import contorno_calculos as cc
from frontend import malla_calculos as ml
from frontend import vehiculo_calculos as vc

# Luz horneada en las bandas (hacia donde está la luz, ejes del vehículo): arriba, delante y a la izquierda.
LUZ_VEHICULO = (-0.35, 0.80, 0.45)

TINTA = cc.TINTA
GROSOR_CONTORNO = 0.016          # m por lado en piezas grandes; en tubos finos se usa el fino
GROSOR_FINO = 0.009

NEUMATICO = (30, 31, 40)
CUBIERTA_TACOS = (74, 76, 92)
CROMO = (212, 216, 226)
ACERO = (150, 156, 172)
METAL_OSCURO = (58, 62, 78)
GOMA = (36, 36, 46)
LUZ_CALIDA = (255, 236, 150)
LUZ_ROJA = (255, 60, 50)
CUERO = (72, 52, 44)
MADERA = (176, 128, 74)


# -- Piezas ---------------------------------------------------------------------------------------------------


def _suma(a, b):
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def _resta(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


# Giro (grados, ejes x luego y) que lleva el eje z de una malla a la dirección p1 -> p2.
def giro_hacia(p1, p2):
    dx, dy, dz = _resta(p2, p1)
    largo = math.sqrt(dx * dx + dy * dy + dz * dz)
    if largo < 1e-9:
        return (0.0, 0.0, 0.0)
    a = -math.asin(max(-1.0, min(1.0, dy / largo)))
    b = math.atan2(dx, dz)
    return (math.degrees(a), math.degrees(b), 0.0)


def _pieza(forma, pos, escala, color, giro=(0.0, 0.0, 0.0), detalle=None, contorno=True, emisivo=False, **extra):
    datos = {"forma": forma, "pos": tuple(pos), "escala": tuple(escala), "giro": tuple(giro), "color": tuple(color),
             "contorno": contorno, "emisivo": emisivo}
    if detalle is not None:
        datos["detalle"] = detalle
    datos.update(extra)
    return datos


# Tubo (cilindro con tapas) de p1 a p2 y radio dado.
def tubo(p1, p2, radio, color, segmentos=6, contorno=True):
    largo = math.dist(p1, p2)
    centro = tuple((a + b) / 2 for a, b in zip(p1, p2))
    return _pieza("cilindro", centro, (radio, radio, largo / 2), color, giro_hacia(p1, p2), (segmentos,), contorno)


# Caja con semi-medidas (hx, hy, hz).
def caja(pos, semi, color, giro=(0.0, 0.0, 0.0), contorno=True, emisivo=False):
    return _pieza("caja", pos, semi, color, giro, None, contorno, emisivo)


# Elipsoide con semiejes.
def elipsoide(pos, semiejes, color, giro=(0.0, 0.0, 0.0), detalle=(10, 6), contorno=True, emisivo=False):
    return _pieza("esfera", pos, semiejes, color, giro, detalle, contorno, emisivo)


# Cilindro de eje x (para ejes de rueda, cubos, discos) de radio r y largo total `largo`.
def disco_x(pos, radio, largo, color, segmentos=12, contorno=True, emisivo=False):
    return _pieza("cilindro", pos, (radio, radio, largo / 2), color, (0.0, 90.0, 0.0), (segmentos,), contorno, emisivo)


# Toro de eje x (una rueda mirada de lado): `radio` al centro del tubo, `tubo_r` radio del neumático en el plano
# de la rueda y `tubo_w` el semiancho (a lo largo de x).
def toro_x(pos, radio, tubo_r, tubo_w, color, segmentos=20, lados=6, contorno=True, emisivo=False):
    return _pieza("toro", pos, (radio, tubo_r, tubo_w), color, (0.0, 0.0, 90.0), (segmentos, lados), contorno, emisivo)


def _toro_vertices(radio, tubo_r, tubo_w, segmentos, lados, extra=0.0):
    # Mismo trazado de índices que malla_calculos.anillo (el sentido de caras es el de todas las mallas del repo), pero
    # con el radio del tubo en el plano de la rueda y su semiancho por separado: el casco de tinta infla solo el tubo.
    vertices = []
    for i in range(segmentos):
        theta = 2 * math.pi * i / segmentos
        for j in range(lados):
            phi = 2 * math.pi * j / lados
            r = radio + (tubo_r + extra) * math.cos(phi)
            vertices.append((r * math.cos(theta), (tubo_w + extra) * math.sin(phi), r * math.sin(theta)))
    triangulos = []
    for i in range(segmentos):
        i2 = (i + 1) % segmentos
        for j in range(lados):
            j2 = (j + 1) % lados
            a, b = i * lados + j, i2 * lados + j
            c, d = i2 * lados + j2, i * lados + j2
            triangulos += [(a, b, c), (a, c, d)]
    return vertices, triangulos


# (vértices, triángulos) de una pieza colocada; `extra` infla cada lado (casco de tinta).
def malla_pieza(pieza, extra=0.0):
    if pieza["forma"] == "toro":
        radio, tubo_r, tubo_w = pieza["escala"]
        segmentos, lados = pieza.get("detalle", (20, 6))
        vertices, triangulos = _toro_vertices(radio, tubo_r, tubo_w, segmentos, lados, extra)
        return ml.colocar(vertices, (1.0, 1.0, 1.0), pieza["giro"], pieza["pos"]), triangulos
    return ml.pieza_a_malla(pieza, extra)


def _a_unidad(color):
    return tuple(c / 255.0 for c in color)


# Une piezas en una malla de triángulos sueltos con color por triángulo (0-1): bandas de luz horneadas salvo en las
# piezas emisivas y cuando se pide `casco` (todo del color de la tinta). Devuelve (vértices, colores, triángulos).
def unir(piezas, casco=False, extra=0.0):
    vertices, colores, triangulos = [], [], []
    for pieza in piezas:
        puntos, tris = malla_pieza(pieza, extra)
        base = _a_unidad(TINTA if casco else pieza["color"])
        for a, b, c in tris:
            pa, pb, pc = puntos[a], puntos[b], puntos[c]
            if casco or pieza.get("emisivo"):
                tono = base
            else:
                tono = ml.color_para_normal(base, ml.normal_triangulo(pa, pb, pc), LUZ_VEHICULO)
            n = len(vertices)
            vertices += [pa, pb, pc]
            colores += [tono, tono, tono]
            triangulos.append((n, n + 1, n + 2))
    return vertices, colores, triangulos


# Grosor del casco de tinta de una pieza: el de contorno_calculos.grosor_para según su tamaño (fino en piezas
# diminutas), pero acotado a los valores del vehículo.
def grosor_contorno(pieza):
    escala = pieza["escala"]
    if pieza["forma"] == "toro":
        menor = 2 * min(escala[1], escala[2])
    elif pieza["forma"] == "cilindro":
        menor = 2 * min(escala[0], escala[1])
    else:
        menor = 2 * min(escala)
    return GROSOR_FINO if menor < 0.07 else GROSOR_CONTORNO


# Cascos de tinta de las piezas que llevan contorno: (vértices, colores, triángulos) con cada pieza inflada con su
# grosor. Piezas sin contorno (radios, hardware diminuto) no entran.
def unir_cascos(piezas):
    vertices, colores, triangulos = [], [], []
    for pieza in piezas:
        if not pieza.get("contorno", True) or pieza.get("emisivo"):
            continue
        v, c, t = unir([pieza], casco=True, extra=grosor_contorno(pieza))
        base = len(vertices)
        vertices += v
        colores += c
        triangulos += [(a + base, b + base, d + base) for a, b, d in t]
    return vertices, colores, triangulos


# Caja que envuelve las piezas ((xmin, ymin, zmin), (xmax, ymax, zmax)).
def limites(piezas):
    minimo = [math.inf] * 3
    maximo = [-math.inf] * 3
    for pieza in piezas:
        puntos, _ = malla_pieza(pieza)
        for p in puntos:
            for i in range(3):
                minimo[i] = min(minimo[i], p[i])
                maximo[i] = max(maximo[i], p[i])
    return tuple(minimo), tuple(maximo)


# -- Modelo ---------------------------------------------------------------------------------------------------


@dataclass
class GrupoPiezas:
    nombre: str
    pivote: tuple                    # dónde se cuelga y gira el grupo (ABSOLUTO, respecto al origen del vehículo)
    piezas: list = field(default_factory=list)   # relativas al pivote
    padre: str = ""                  # grupo del que cuelga («manubrio» para la rueda delantera); vacío = el vehículo
    translucido: bool = False        # halo de luz: sin casco, con transparencia


@dataclass
class ModeloPiezas:
    tipo: str
    grupos: dict
    puntos: dict                     # puntos clave (ver cada constructor)

    def todas(self):
        return [p for g in self.grupos.values() for p in self._absolutas(g)]

    @staticmethod
    def _absolutas(grupo):
        return [dict(p, pos=_suma(p["pos"], grupo.pivote)) for p in grupo.piezas]


# Pone las piezas relativas a un pivote (resta el pivote a su posición).
def _relativas(piezas, pivote):
    return [dict(p, pos=_resta(p["pos"], pivote)) for p in piezas]


def _variante(paleta):
    cuerpo, acento, parche, caja_color = paleta
    return cuerpo, acento, parche, caja_color


def _oscurecer(color, f=0.72):
    return tuple(int(c * f) for c in color)


def _aclarar(color, f=0.35):
    return tuple(int(c + (255 - c) * f) for c in color)


# Parches de pintura: rectángulos de otro color pegados a una superficie plana (efecto «arreglado a mano»).
def _parche(pos, semi, color, giro=(0.0, 0.0, 0.0)):
    return caja(pos, semi, color, giro, contorno=False)


# -- Bicicleta ------------------------------------------------------------------------------------------------

RUEDA_B = 0.34                   # radio exterior (m)
EJE_TRAS_B = (0.0, RUEDA_B, -0.52)
EJE_DEL_B = (0.0, RUEDA_B, 0.52)
PEDALIER_B = (0.0, 0.30, -0.03)
BIELA = 0.17
PIVOTE_MANUBRIO_B = (0.0, 0.0, 0.40)       # eje de dirección (vertical) en el tubo de dirección


# Rueda de bicicleta con su eje en x: cubierta con tacos, llanta de color, radios, buje y reflectores. `n_radios`
# radios finos de cromo; los reflectores naranja y los tacos claros dan la referencia para ver que gira.
def rueda_bicicleta(acento, tacos=14, n_radios=10):
    piezas = [toro_x((0, 0, 0), RUEDA_B - 0.042, 0.042, 0.034, NEUMATICO, 20, 6)]
    for k in range(tacos):                                  # tacos de la cubierta (rayas claras)
        ang = 2 * math.pi * k / tacos
        piezas.append(caja((0, (RUEDA_B - 0.006) * math.sin(ang), (RUEDA_B - 0.006) * math.cos(ang)), (0.036, 0.013, 0.013),
                           CUBIERTA_TACOS, (math.degrees(-ang), 0, 0), contorno=False))
    piezas.append(toro_x((0, 0, 0), RUEDA_B - 0.10, 0.012, 0.022, acento, 18, 4, contorno=True))
    for k in range(n_radios):
        ang = 2 * math.pi * (k + 0.5) / n_radios
        punta = (0.0, (RUEDA_B - 0.11) * math.sin(ang), (RUEDA_B - 0.11) * math.cos(ang))
        piezas.append(tubo((0.0, 0.0, 0.0), punta, 0.0045, CROMO, 4, contorno=False))
    piezas.append(disco_x((0, 0, 0), 0.032, 0.12, ACERO, 8))
    for ang in (0.4, 0.4 + math.pi):                         # reflectores de la llanta
        piezas.append(caja((0, (RUEDA_B - 0.12) * math.sin(ang), (RUEDA_B - 0.12) * math.cos(ang)), (0.05, 0.026, 0.026),
                           (255, 150, 30), (math.degrees(-ang), 0, 0), contorno=False))
    return piezas


# Guardabarros: arco de cajas finas sobre la rueda entre dos ángulos (grados desde la parte alta, + hacia adelante).
def guardabarros(centro, desde, hasta, color, radio=RUEDA_B + 0.05, ancho=0.06, pasos=7):
    piezas = []
    for k in range(pasos):
        ang = math.radians(desde + (hasta - desde) * k / (pasos - 1))
        pos = (centro[0], centro[1] + radio * math.cos(ang), centro[2] + radio * math.sin(ang))
        piezas.append(caja(pos, (ancho, 0.008, 0.045), color, (math.degrees(ang), 0, 0), contorno=True))
    return piezas


def construir_bicicleta(paleta, indice=0):
    cuerpo, acento, parche, caja_color = _variante(paleta)
    cuerpo2 = _oscurecer(cuerpo, 0.8)
    r = 0.022                                                  # radio de los tubos del cuadro (grueso, de cómic)
    st = (0.0, 0.90, -0.20)                                    # remate del tubo del sillín
    ht = (0.0, 0.89, 0.355)                                    # arriba del tubo de dirección
    hb = (0.0, 0.73, 0.41)                                     # abajo del tubo de dirección
    cuadro = [
        tubo(PEDALIER_B, st, r, cuerpo),                                    # tubo del sillín
        tubo((0.0, 0.84, -0.19), (0.0, 0.85, 0.372), r, cuerpo),            # tubo superior
        tubo(PEDALIER_B, hb, r * 1.15, cuerpo),                             # tubo diagonal
        tubo(ht, hb, r * 1.3, cuerpo2),                                     # tubo de dirección
        tubo((0.0, 0.80, -0.19), (0.045, 0.37, -0.52), 0.014, acento),      # vainas del sillín
        tubo((0.0, 0.80, -0.19), (-0.045, 0.37, -0.52), 0.014, acento),
        tubo(PEDALIER_B, (0.05, 0.34, -0.52), 0.014, acento),                # vainas de la cadena
        tubo(PEDALIER_B, (-0.05, 0.34, -0.52), 0.014, acento),
        tubo(st, (0.0, 0.98, -0.215), 0.014, CROMO),                        # tija del sillín
        elipsoide((0.0, 0.995, -0.20), (0.075, 0.032, 0.14), CUERO, detalle=(8, 5)),    # sillín
        elipsoide((0.0, 0.985, -0.08), (0.04, 0.026, 0.06), CUERO, detalle=(8, 5)),     # pico del sillín
        elipsoide((0.0, 0.72, 0.0), (0.05, 0.05, 0.05), METAL_OSCURO, detalle=(6, 4), contorno=False),   # (relleno del cuadro)
        # parrilla de carga trasera
        caja((0.0, 0.76, -0.55), (0.085, 0.008, 0.13), METAL_OSCURO),
        tubo((0.06, 0.76, -0.46), (0.045, 0.37, -0.52), 0.007, METAL_OSCURO, 4, contorno=False),
        tubo((-0.06, 0.76, -0.46), (-0.045, 0.37, -0.52), 0.007, METAL_OSCURO, 4, contorno=False),
        caja((0.0, 0.725, -0.69), (0.03, 0.02, 0.012), LUZ_ROJA, emisivo=True),               # piloto trasero
        # parches de pintura del cuadro (arreglos con otra pintura)
        _parche((0.0235, 0.885, 0.1), (0.002, 0.02, 0.06), parche),
        _parche((-0.0235, 0.885, 0.1), (0.002, 0.02, 0.06), parche),
        _parche((0.0, 0.62, -0.015), (0.025, 0.05, 0.025), acento, (0, 0, 0)),
    ]
    cuadro += guardabarros(EJE_TRAS_B, -60, 20, acento, radio=RUEDA_B + 0.035, ancho=0.06)
    if indice % 2 == 1:                                         # bolsa / caja de carga en la parrilla trasera
        cuadro += [caja((0.0, 0.88, -0.58), (0.13, 0.11, 0.15), caja_color),
                   _parche((0.131, 0.88, -0.58), (0.002, 0.07, 0.09), _aclarar(caja_color, 0.7)),
                   _parche((-0.131, 0.88, -0.58), (0.002, 0.07, 0.09), _aclarar(caja_color, 0.7))]
    else:                                                       # pareja de alforjas
        cuadro += [caja((0.115, 0.84, -0.55), (0.04, 0.08, 0.11), caja_color),
                   caja((-0.115, 0.84, -0.55), (0.04, 0.08, 0.11), caja_color)]
    # cadena: dos tramos planos entre el plato y el piñón
    cuadro += [tubo((0.05, 0.385, -0.03), (0.05, 0.385, -0.52), 0.005, METAL_OSCURO, 4, contorno=False),
               tubo((0.05, 0.215, -0.03), (0.05, 0.295, -0.52), 0.005, METAL_OSCURO, 4, contorno=False)]

    # --- manubrio (gira con la dirección): horquilla, vástago, barra, puños y rueda delantera aparte
    p = PIVOTE_MANUBRIO_B
    manubrio = [
        tubo((0.045, 0.34, 0.52), (0.04, 0.745, 0.41), 0.014, ACERO),         # horquilla
        tubo((-0.045, 0.34, 0.52), (-0.04, 0.745, 0.41), 0.014, ACERO),
        tubo((-0.04, 0.745, 0.41), (0.04, 0.745, 0.41), 0.016, ACERO),         # corona
        tubo(ht, (0.0, 0.99, 0.335), 0.016, ACERO),                            # vástago
        tubo((0.0, 0.99, 0.335), (0.30, 1.01, 0.27), 0.014, ACERO),            # barra derecha
        tubo((0.0, 0.99, 0.335), (-0.30, 1.01, 0.27), 0.014, ACERO),
        tubo((0.28, 1.01, 0.275), (0.37, 1.01, 0.255), 0.020, GOMA),           # puños
        tubo((-0.28, 1.01, 0.275), (-0.37, 1.01, 0.255), 0.020, GOMA),
        tubo((0.22, 1.02, 0.30), (0.20, 1.035, 0.37), 0.006, METAL_OSCURO, 4, contorno=False),   # manetas de freno
        tubo((-0.22, 1.02, 0.30), (-0.20, 1.035, 0.37), 0.006, METAL_OSCURO, 4, contorno=False),
        # faro delantero (lente emisiva) sobre la corona
        disco_x((0.0, 0.88, 0.47), 0.05, 0.06, CROMO, 10),
        elipsoide((0.0, 0.88, 0.505), (0.04, 0.04, 0.012), LUZ_CALIDA, detalle=(8, 5), contorno=False, emisivo=True),
    ]
    manubrio += guardabarros(EJE_DEL_B, -20, 60, parche, radio=RUEDA_B + 0.035, ancho=0.055)
    if indice % 2 == 0:                                        # cesta delantera de listones (caja de fruta)
        manubrio += [caja((0.0, 0.93, 0.50), (0.17, 0.09, 0.12), MADERA),
                     caja((0.0, 0.93, 0.625), (0.175, 0.04, 0.004), _oscurecer(MADERA, 0.6), contorno=False),
                     caja((0.0, 0.90, 0.625), (0.175, 0.015, 0.004), caja_color, contorno=False),
                     caja((0.0, 0.99, 0.625), (0.175, 0.015, 0.004), caja_color, contorno=False)]
    manubrio = _relativas(manubrio, p)

    rueda_del = rueda_bicicleta(acento)
    rueda_tras = rueda_bicicleta(acento, n_radios=12)
    rueda_tras += [toro_x((0.05, 0, 0), 0.045, 0.006, 0.006, CROMO, 12, 4, contorno=False)]   # piñón

    biela = [
        toro_x((0.045, 0, 0), 0.085, 0.01, 0.012, CROMO, 14, 4),                    # plato
        tubo((0.075, 0.0, 0.0), (0.075, 0.0, BIELA), 0.014, ACERO),                  # biela derecha (fase 0: adelante)
        tubo((-0.075, 0.0, 0.0), (-0.075, 0.0, -BIELA), 0.014, ACERO),               # biela izquierda
        disco_x((0.0, 0.0, 0.0), 0.03, 0.2, METAL_OSCURO, 8),
    ]
    pedal_d = [caja((0.0, 0.0, 0.0), (0.06, 0.012, 0.055), METAL_OSCURO)]
    pedal_i = [caja((0.0, 0.0, 0.0), (0.06, 0.012, 0.055), METAL_OSCURO)]
    pata = [tubo((0.06, 0.34, -0.18), (0.075, 0.0, -0.22), 0.01, METAL_OSCURO, 5)]    # pata de cabra (aparcada)

    grupos = {
        "cuadro": GrupoPiezas("cuadro", (0.0, 0.0, 0.0), cuadro),
        "manubrio": GrupoPiezas("manubrio", p, manubrio),
        "rueda_del": GrupoPiezas("rueda_del", EJE_DEL_B, rueda_del, "manubrio"),
        "rueda_tras": GrupoPiezas("rueda_tras", EJE_TRAS_B, rueda_tras),
        "biela": GrupoPiezas("biela", PEDALIER_B, biela),
        "pedal_d": GrupoPiezas("pedal_d", (0.115, 0.30, -0.03 + BIELA), pedal_d),
        "pedal_i": GrupoPiezas("pedal_i", (-0.115, 0.30, -0.03 - BIELA), pedal_i),
        "pata": GrupoPiezas("pata", (0.0, 0.0, 0.0), pata),
    }
    puntos = {
        "sillin": (0.0, 0.975, -0.20),
        "pedalier": PEDALIER_B, "eje_pedal_x": 0.115,
        "agarre_d": (0.325, 1.02, 0.262), "agarre_i": (-0.325, 1.02, 0.262),
        "eje_del": EJE_DEL_B, "eje_tras": EJE_TRAS_B,
        "pivote_manubrio": p, "radio_rueda": RUEDA_B,
        "luz": (0.0, 0.88, 0.52),
    }
    return ModeloPiezas(vc.BICICLETA, grupos, puntos)


# -- Moto -----------------------------------------------------------------------------------------------------

RUEDA_M = 0.32
EJE_TRAS_M = (0.0, RUEDA_M, -0.65)
EJE_DEL_M = (0.0, RUEDA_M, 0.65)
PIVOTE_MANUBRIO_M = (0.0, 0.0, 0.50)


# Rueda de moto de aleación: cubierta ancha con tacos, llanta, 5 radios gruesos de color, buje y disco de freno.
def rueda_moto(acento, disco=True):
    piezas = [toro_x((0, 0, 0), RUEDA_M - 0.058, 0.058, 0.052, NEUMATICO, 22, 6)]
    for k in range(16):
        ang = 2 * math.pi * k / 16
        piezas.append(caja((0, (RUEDA_M - 0.004) * math.sin(ang), (RUEDA_M - 0.004) * math.cos(ang)), (0.052, 0.015, 0.016),
                           CUBIERTA_TACOS, (math.degrees(-ang), 0, 0), contorno=False))
    piezas.append(toro_x((0, 0, 0), RUEDA_M - 0.125, 0.018, 0.034, CROMO, 18, 4))
    for k in range(5):
        ang = 2 * math.pi * k / 5 + 0.3
        punta = (0.0, (RUEDA_M - 0.13) * math.sin(ang), (RUEDA_M - 0.13) * math.cos(ang))
        piezas.append(tubo((0.0, 0.0, 0.0), punta, 0.019, acento, 5, contorno=True))
    piezas.append(disco_x((0, 0, 0), 0.045, 0.14, ACERO, 10))
    if disco:
        piezas.append(disco_x((0.045, 0, 0), 0.11, 0.008, CROMO, 14, contorno=False))
    return piezas


def construir_moto(paleta, indice=0):
    cuerpo, acento, parche, caja_color = _variante(paleta)
    oscuro = _oscurecer(cuerpo, 0.62)
    tanque = [elipsoide((0.0, 0.78, 0.16), (0.155, 0.115, 0.23), cuerpo, detalle=(12, 7)),
              _parche((0.1555, 0.79, 0.14), (0.002, 0.05, 0.1), parche),
              _parche((-0.1555, 0.79, 0.14), (0.002, 0.05, 0.1), parche),
              caja((0.0, 0.8, 0.16), (0.005, 0.12, 0.2), acento, contorno=False)]       # franja de color por el eje
    cuadro = [
        # chasis de tubos y motor
        tubo((0.0, 0.84, 0.46), (0.0, 0.44, 0.20), 0.032, METAL_OSCURO),
        tubo((0.0, 0.64, -0.05), (0.0, 0.62, -0.55), 0.025, METAL_OSCURO),
        tubo((0.0, 0.64, -0.05), (0.0, 0.40, 0.04), 0.025, METAL_OSCURO),
        caja((0.0, 0.36, 0.06), (0.11, 0.15, 0.17), METAL_OSCURO),                       # bloque del motor
        tubo((0.0, 0.42, 0.10), (0.0, 0.56, 0.25), 0.075, ACERO, 8),                     # cilindro inclinado
        tubo((0.0, 0.36, 0.04), (0.0, 0.55, 0.23), 0.083, METAL_OSCURO, 8),
        caja((0.125, 0.36, 0.06), (0.018, 0.1, 0.12), ACERO),                            # tapa lateral del motor
        # asiento largo de taxi moto y guardabarros trasero con parche
        caja((0.0, 0.77, -0.18), (0.14, 0.045, 0.30), caja_color if indice % 2 else CUERO),
        elipsoide((0.0, 0.78, 0.05), (0.12, 0.05, 0.12), caja_color if indice % 2 else CUERO, detalle=(8, 5)),
        caja((0.0, 0.71, -0.62), (0.075, 0.02, 0.17), acento, (-10, 0, 0)),
        caja((0.0, 0.70, -0.64), (0.077, 0.004, 0.06), parche, (-10, 0, 0), contorno=False),
        caja((0.0, 0.66, -0.78), (0.05, 0.035, 0.012), (240, 240, 230), contorno=True),                # placa
        caja((0.0, 0.72, -0.80), (0.04, 0.02, 0.012), LUZ_ROJA, emisivo=True),                # luz trasera
        # parrilla de carga + baúl de reparto
        tubo((0.13, 0.78, -0.40), (0.13, 0.80, -0.78), 0.012, METAL_OSCURO, 5),
        tubo((-0.13, 0.78, -0.40), (-0.13, 0.80, -0.78), 0.012, METAL_OSCURO, 5),
        caja((0.0, 0.80, -0.60), (0.15, 0.01, 0.2), METAL_OSCURO),
        caja((0.0, 1.03, -0.62), (0.215, 0.215, 0.235), caja_color),                         # baúl
        caja((0.0, 1.245, -0.62), (0.225, 0.02, 0.245), _oscurecer(caja_color, 0.8)),        # tapa
        _parche((0.218, 1.04, -0.62), (0.002, 0.11, 0.14), parche),
        _parche((-0.218, 1.04, -0.62), (0.002, 0.11, 0.14), parche),
        _parche((0.0, 1.03, -0.857), (0.14, 0.1, 0.002), parche),
        # escape + silenciador (derecha)
        tubo((0.11, 0.30, 0.08), (0.17, 0.27, -0.30), 0.025, CROMO, 6),
        tubo((0.17, 0.30, -0.30), (0.17, 0.33, -0.76), 0.055, CROMO, 8),
        tubo((0.17, 0.33, -0.76), (0.17, 0.335, -0.80), 0.04, METAL_OSCURO, 8),
        # brazo oscilante, amortiguadores y pedales de apoyo
        tubo((0.10, 0.40, -0.06), (0.10, 0.32, -0.65), 0.02, METAL_OSCURO),
        tubo((-0.10, 0.40, -0.06), (-0.10, 0.32, -0.65), 0.02, METAL_OSCURO),
        tubo((0.10, 0.45, -0.55), (0.10, 0.70, -0.38), 0.022, acento, 6),
        tubo((-0.10, 0.45, -0.55), (-0.10, 0.70, -0.38), 0.022, acento, 6),
        caja((0.20, 0.30, -0.02), (0.075, 0.012, 0.03), METAL_OSCURO),                    # estribos del piloto
        caja((-0.20, 0.30, -0.02), (0.075, 0.012, 0.03), METAL_OSCURO),
        caja((0.20, 0.34, -0.38), (0.06, 0.012, 0.03), METAL_OSCURO),                     # estribos del pasajero
        caja((-0.20, 0.34, -0.38), (0.06, 0.012, 0.03), METAL_OSCURO),
    ] + tanque
    cuadro += guardabarros(EJE_TRAS_M, -95, -15, oscuro, radio=RUEDA_M + 0.07, ancho=0.085, pasos=4)

    p = PIVOTE_MANUBRIO_M
    manubrio = [
        tubo((0.08, 0.32, 0.65), (0.07, 0.90, 0.50), 0.022, CROMO, 8),                   # barras de la horquilla
        tubo((-0.08, 0.32, 0.65), (-0.07, 0.90, 0.50), 0.022, CROMO, 8),
        tubo((0.07, 0.62, 0.575), (0.075, 0.76, 0.54), 0.03, ACERO, 8),                  # fundas
        tubo((-0.07, 0.62, 0.575), (-0.075, 0.76, 0.54), 0.03, ACERO, 8),
        tubo((-0.08, 0.90, 0.50), (0.08, 0.90, 0.50), 0.03, METAL_OSCURO),               # tija
        tubo((0.0, 0.92, 0.48), (0.31, 1.00, 0.40), 0.016, METAL_OSCURO),                # manillar
        tubo((0.0, 0.92, 0.48), (-0.31, 1.00, 0.40), 0.016, METAL_OSCURO),
        tubo((0.28, 1.00, 0.41), (0.38, 1.00, 0.38), 0.025, GOMA),                       # puños
        tubo((-0.28, 1.00, 0.41), (-0.38, 1.00, 0.38), 0.025, GOMA),
        tubo((0.2, 1.04, 0.44), (0.2, 1.04, 0.52), 0.007, METAL_OSCURO, 4, contorno=False),   # manetas
        tubo((-0.2, 1.04, 0.44), (-0.2, 1.04, 0.52), 0.007, METAL_OSCURO, 4, contorno=False),
        # espejos
        tubo((0.30, 1.02, 0.40), (0.34, 1.20, 0.36), 0.007, METAL_OSCURO, 4, contorno=False),
        tubo((-0.30, 1.02, 0.40), (-0.34, 1.20, 0.36), 0.007, METAL_OSCURO, 4, contorno=False),
        elipsoide((0.34, 1.22, 0.36), (0.055, 0.04, 0.012), CROMO, detalle=(8, 5)),
        elipsoide((-0.34, 1.22, 0.36), (0.055, 0.04, 0.012), CROMO, detalle=(8, 5)),
        # faro: carcasa cromada y lente emisiva
        disco_x((0.0, 0.99, 0.62), 0.105, 0.1, cuerpo, 12),
        elipsoide((0.0, 0.99, 0.675), (0.085, 0.085, 0.018), LUZ_CALIDA, detalle=(10, 6), contorno=False, emisivo=True),
        # tablero
        caja((0.0, 1.03, 0.43), (0.06, 0.03, 0.04), METAL_OSCURO),
    ]
    manubrio += guardabarros(EJE_DEL_M, -15, 85, parche, radio=RUEDA_M + 0.07, ancho=0.08, pasos=5)
    manubrio = _relativas(manubrio, p)

    rueda_del = rueda_moto(acento, disco=True)
    rueda_tras = rueda_moto(acento, disco=False) + [toro_x((0.07, 0, 0), 0.085, 0.009, 0.012, ACERO, 14, 4, contorno=False)]
    pata = [tubo((-0.12, 0.35, -0.05), (-0.22, 0.0, -0.12), 0.012, METAL_OSCURO, 5)]
    halo = [elipsoide((0.0, 0.99, 0.74), (0.2, 0.2, 0.05), (255, 244, 170), detalle=(10, 6), contorno=False, emisivo=True)]

    grupos = {
        "cuadro": GrupoPiezas("cuadro", (0.0, 0.0, 0.0), cuadro),
        "manubrio": GrupoPiezas("manubrio", p, manubrio),
        "rueda_del": GrupoPiezas("rueda_del", EJE_DEL_M, rueda_del, "manubrio"),
        "rueda_tras": GrupoPiezas("rueda_tras", EJE_TRAS_M, rueda_tras),
        "pata": GrupoPiezas("pata", (0.0, 0.0, 0.0), pata),
        "halo": GrupoPiezas("halo", (0.0, 0.0, 0.0), halo, translucido=True),
    }
    puntos = {
        "sillin": (0.0, 0.815, -0.12),
        "estribo_d": (0.20, 0.33, -0.02), "estribo_i": (-0.20, 0.33, -0.02),
        "agarre_d": (0.34, 1.02, 0.395), "agarre_i": (-0.34, 1.02, 0.395),
        "eje_del": EJE_DEL_M, "eje_tras": EJE_TRAS_M,
        "pivote_manubrio": p, "radio_rueda": RUEDA_M,
        "escape": (0.17, 0.335, -0.82), "luz": (0.0, 0.99, 0.68),
    }
    return ModeloPiezas(vc.MOTO, grupos, puntos)


def construir(tipo, indice=0):
    paleta = vc.paleta_de(tipo, indice)
    if tipo == vc.BICICLETA:
        return construir_bicicleta(paleta, indice)
    if tipo == vc.MOTO:
        return construir_moto(paleta, indice)
    raise ValueError(f"tipo de vehículo desconocido: {tipo!r}")


# -- Pose del piloto ------------------------------------------------------------------------------------------

LARGO_MUSLO, LARGO_PANTORRILLA = 0.45, 0.41       # hasta el centro del zapato (ver Personaje: zapato en y = -0.41)
LARGO_BRAZO, LARGO_ANTEBRAZO = 0.30, 0.30         # codo a la mano (la esfera de la mano está a -0.28)
CADERA_X = 0.10
HOMBRO_X = 0.27
ALTURA_TORSO = 0.10                                # el pivote del torso está 0.1 sobre la pelvis
ALTURA_HOMBRO = 0.46                               # el hombro está 0.46 sobre el pivote del torso
ALTURA_CADERA = -0.05                              # la cadera está 0.05 bajo la pelvis


# Pose (dict en la convención de frontend/poses.py) del piloto sentado en `modelo` para la fase de pedal dada. Los
# pies siguen a los pedales (bici) o los estribos (moto) y las manos agarran el manubrio, todo por cinemática
# inversa. `giro_manubrio` (rad) mueve un poco las manos al girar. Devuelve (pose, pelvis_z) donde pelvis_z es dónde
# va el piloto (adelante/atrás) respecto al origen del vehículo; la pelvis siempre está en x = 0.
def pose_piloto(modelo, fase_pedal=0.0, giro_manubrio=0.0, torso=None):
    puntos = modelo.puntos
    sillin = puntos["sillin"]
    es_bici = modelo.tipo == vc.BICICLETA
    torso_grados = (32.0 if es_bici else 14.0) if torso is None else torso
    pelvis_y = sillin[1] + 0.09
    pelvis_z = sillin[2]
    t = math.radians(torso_grados)
    hombro = (pelvis_z + ALTURA_HOMBRO * math.sin(t), pelvis_y + ALTURA_TORSO + ALTURA_HOMBRO * math.cos(t))
    cadera = (pelvis_z, pelvis_y + ALTURA_CADERA)
    pose = {n: 0.0 for n in ("pelvis_y", "torso", "cabeza", "brazo_i", "brazo_d", "codo_i", "codo_d",
                              "muslo_i", "muslo_d", "rodilla_i", "rodilla_d")}
    pose["pelvis_y"] = pelvis_y
    pose["torso"] = torso_grados
    pose["cabeza"] = -torso_grados * 0.85               # mira al frente
    for lado, clave in ((1, "d"), (-1, "i")):
        if es_bici:
            pz, py = vc.posicion_pedal(fase_pedal, lado, BIELA)
            pie = (puntos["pedalier"][2] + pz + 0.04, puntos["pedalier"][1] + py + 0.07)
        else:
            e = puntos["estribo_d" if lado > 0 else "estribo_i"]
            pie = (e[2] + 0.02, e[1] + 0.07)
        muslo, rodilla = vc.ik_pierna((pie[0] - cadera[0], pie[1] - cadera[1]), LARGO_MUSLO, LARGO_PANTORRILLA)
        pose["muslo_" + clave], pose["rodilla_" + clave] = muslo, rodilla
        agarre = puntos["agarre_d" if lado > 0 else "agarre_i"]
        mano = (agarre[2] - hombro[0], agarre[1] - hombro[1])
        brazo, codo = vc.ik_brazo(mano, LARGO_BRAZO, LARGO_ANTEBRAZO)
        pose["brazo_" + clave], pose["codo_" + clave] = brazo, codo
    return pose, pelvis_z
