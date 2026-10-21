# Cálculos puros (sin ursina ni panda3d) del detalle de la favela: qué paredes dan a un callejón o a
# la calle, dónde van murales, carteles, remiendos, grietas y manchas, dónde se cruzan banderines y
# dónde quedan los objetos de la calle (bidones, macetas, motos, bicis, perros). Lo dibuja
# frontend/favela_detalles.py; aquí solo hay geometría y azar fijo, así que se prueba sin ventana
# (tests/frontend_3d/test_favela_calculos.py).
#
# Convenciones: `casas` son CasaDecorativa (cx, cz, ancho en x, fondo en z, alto_total). Las caras de una
# casa se nombran por hacia dónde miran: 'n' = +z, 's' = -z, 'e' = +x, 'o' = -x (como los lados de las
# fachadas de MundoCiudad). El azar sale de azar_de (determinista): nada cambia entre ejecuciones y no se
# toca el random del backend.

import math
from dataclasses import dataclass

from frontend.azar_fijo import azar_de

LADOS = ("n", "s", "e", "o")
NORMAL = {"n": (0, 1), "s": (0, -1), "e": (1, 0), "o": (-1, 0)}       # hacia afuera de cada cara (x, z)
TANGENTE = {"n": (1, 0), "s": (1, 0), "e": (0, 1), "o": (0, 1)}       # a lo largo de la cara (x, z)

ALCANCE_VECINA = 6.0            # m: más lejos que esto, una cara "da a lo abierto" (calle, plaza, patio)
SOLAPE_MIN = 1.0                # m mínimos de pared enfrentada para que cuente como callejón
HUECO_CALLEJON = 3.4            # m máximos entre dos paredes para llamarlo callejón
SEPARACION_PARED = 0.07         # m que un mural, cartel o remiendo se despega de la pared (no hay z-fighting)

# -- Murales, carteles y manchas --
PROBABILIDAD_MURAL = 0.30       # fracción de caras de callejón (largas) con un mural
PROBABILIDAD_CARTEL = 0.38      # fracción de caras abiertas con un cartel pintado a mano
PROBABILIDAD_REMIENDO = 0.55    # fracción de caras con un remiendo de pintura o revoque distinto
PROBABILIDAD_GRIETA = 0.40
PROBABILIDAD_MANCHA = 0.65
PROBABILIDAD_BALCON = 0.22      # fracción de caras con un balcón (volado)
TIPOS_MURAL = ("sol", "bandera", "estrella", "corazon", "ola", "ojo")
TEXTOS_CARTEL = ("BAR", "LANCHES", "SALÃO", "MERCADO", "PADARIA", "AÇAÍ", "FUTEBOL", "PIZZA", "FARMÁCIA", "OFICINA")
ALTO_MURAL = 1.7
ANCHO_MURAL = 2.3
ALTO_CARTEL = 0.75
ANCHO_CARTEL = 2.2
VOLADO_BALCON = 0.9             # m que el balcón sobresale de la pared
ANCHO_BALCON = 2.0

# -- Banderines --
ALTURA_BANDERIN = (3.4, 6.6)    # m sobre la base de las casas
SEPARACION_BANDERAS = 0.5      # m entre bandera y bandera a lo largo de la cuerda
TAMANO_BANDERA = 0.42           # m de lado de cada triángulo
PROBABILIDAD_BANDERIN = 0.55    # fracción de los callejones con banderines
CALLEJON_MAXIMO_BANDERIN = 3.0  # m: en pasillos más anchos no se cruzan
CAIDA_BANDERIN = 0.045          # fracción del largo que cuelga la cuerda en el medio
COLORES_BANDERA = (
    (230, 60, 70), (250, 200, 40), (60, 140, 235), (60, 190, 110),
    (240, 120, 40), (190, 90, 220), (245, 245, 245), (40, 200, 200),
)


@dataclass(frozen=True)
class Cara:
    """Una pared de una casa: a qué lado mira, en qué plano está y qué tramo (t0, t1) tiene enfrente a
    otra casa a `hueco` m (callejón si hueco <= HUECO_CALLEJON). `vecina` es la casa de enfrente."""

    casa: int
    lado: str
    plano: float            # x (caras e/o) o z (caras n/s) de la pared
    t0: float               # inicio del tramo enfrentado, a lo largo de la pared (z en e/o, x en n/s)
    t1: float
    hueco: float            # distancia a la pared de enfrente (99 si no hay ninguna a ALCANCE_VECINA)
    vecina: int | None

    @property
    def largo(self):
        return self.t1 - self.t0

    @property
    def es_callejon(self):
        return self.vecina is not None and self.hueco <= HUECO_CALLEJON

    # Punto (x, z) de la pared a `t` a lo largo, `fuera` m hacia afuera.
    def punto(self, t, fuera=0.0):
        nx, nz = NORMAL[self.lado]
        if self.lado in ("e", "o"):
            return (self.plano + nx * fuera, t)
        return (t, self.plano + nz * fuera)


def _caja(c):
    return (c.cx - c.ancho / 2, c.cx + c.ancho / 2, c.cz - c.fondo / 2, c.cz + c.fondo / 2)


# Las cuatro caras de cada casa con su vecina de enfrente (la más próxima por ese lado dentro de ALCANCE_VECINA
# y con SOLAPE_MIN m de pared enfrentada). Sin vecina, el tramo es la pared entera.
def caras_de_casas(casas, alcance=ALCANCE_VECINA):
    cajas = [_caja(c) for c in casas]
    celda = 16.0
    grilla = {}
    for k, (x0, x1, z0, z1) in enumerate(cajas):
        for i in range(int(math.floor(x0 / celda)), int(math.floor(x1 / celda)) + 1):
            for j in range(int(math.floor(z0 / celda)), int(math.floor(z1 / celda)) + 1):
                grilla.setdefault((i, j), []).append(k)
    caras = []
    for k, (x0, x1, z0, z1) in enumerate(cajas):
        cercanas = set()
        for i in range(int(math.floor((x0 - alcance) / celda)), int(math.floor((x1 + alcance) / celda)) + 1):
            for j in range(int(math.floor((z0 - alcance) / celda)), int(math.floor((z1 + alcance) / celda)) + 1):
                cercanas.update(grilla.get((i, j), ()))
        cercanas.discard(k)
        for lado in LADOS:
            mejor = None
            for n in cercanas:
                b = cajas[n]
                if lado == "e":
                    hueco, solape = b[0] - x1, (max(z0, b[2]), min(z1, b[3]))
                elif lado == "o":
                    hueco, solape = x0 - b[1], (max(z0, b[2]), min(z1, b[3]))
                elif lado == "n":
                    hueco, solape = b[2] - z1, (max(x0, b[0]), min(x1, b[1]))
                else:
                    hueco, solape = z0 - b[3], (max(x0, b[0]), min(x1, b[1]))
                if hueco < -1e-6 or hueco > alcance or solape[1] - solape[0] < SOLAPE_MIN:
                    continue
                if mejor is None or hueco < mejor[0]:
                    mejor = (hueco, n, solape)
            if lado == "e":
                plano, entero = x1, (z0, z1)
            elif lado == "o":
                plano, entero = x0, (z0, z1)
            elif lado == "n":
                plano, entero = z1, (x0, x1)
            else:
                plano, entero = z0, (x0, x1)
            if mejor is None:
                caras.append(Cara(k, lado, round(plano, 3), round(entero[0], 3), round(entero[1], 3), 99.0, None))
            else:
                caras.append(Cara(k, lado, round(plano, 3), round(mejor[2][0], 3), round(mejor[2][1], 3),
                                  round(mejor[0], 3), mejor[1]))
    return caras


@dataclass(frozen=True)
class Calcomania:
    """Algo pintado o pegado en una pared: `tipo`, la cara, la posición `t` a lo largo, la altura `y` sobre la
    base de la casa (pie del dibujo), su tamaño y una semilla para variar colores y formas."""

    tipo: str
    casa: int
    lado: str
    plano: float
    t: float
    y: float
    ancho: float
    alto: float
    semilla: float
    texto: str = ""

    def centro(self):
        """(x, z) del centro de la calcomanía, despegada SEPARACION_PARED de la pared."""
        nx, nz = NORMAL[self.lado]
        if self.lado in ("e", "o"):
            return (self.plano + nx * SEPARACION_PARED, self.t)
        return (self.t, self.plano + nz * SEPARACION_PARED)

    @property
    def rumbo(self):
        """rotation_y (grados, convención de Ursina) de un plano cuya normal (+z local) mira hacia afuera."""
        nx, nz = NORMAL[self.lado]
        return math.degrees(math.atan2(nx, nz))


def _u(a, b):
    return azar_de(a, b)


# Calcomanías de las caras de `casas`: murales y remiendos y manchas en los callejones, carteles en las caras
# abiertas, balcones y grietas en todas. Cada una cabe en la altura de su casa (alto_total) y en el tramo
# de pared de la cara; las caras demasiado cortas no llevan nada.
def calcomanias(casas, caras):
    resultado = []
    for n, cara in enumerate(caras):
        casa = casas[cara.casa]
        s0 = casa.cx * 0.31 + casa.cz * 0.57 + n * 0.113
        largo = cara.largo
        altura = casa.alto_total
        if largo < 1.6:
            continue
        lado_vis = cara.es_callejon or cara.vecina is None or cara.hueco > HUECO_CALLEJON

        def posicion(u, ancho, margen=0.4):
            libre = max(0.0, largo - ancho - 2 * margen)
            return cara.t0 + margen + ancho / 2 + libre * u

        # Ancho que cabe en el tramo (con su margen): None si queda demasiado angosto para dibujarlo.
        def cabe(ancho, margen=0.3):
            a = min(ancho, largo - 2 * margen)
            return a if a >= 0.6 else None

        if cara.es_callejon and largo >= ANCHO_MURAL + 0.8 and _u(s0, 1.1) < PROBABILIDAD_MURAL:
            tipo = TIPOS_MURAL[int(_u(s0, 2.3) * len(TIPOS_MURAL)) % len(TIPOS_MURAL)]
            resultado.append(Calcomania(tipo, cara.casa, cara.lado, cara.plano, round(posicion(_u(s0, 3.7), ANCHO_MURAL), 2),
                                        0.5, ANCHO_MURAL, ALTO_MURAL, _u(s0, 4.1)))
        if not cara.es_callejon and largo >= ANCHO_CARTEL + 0.6 and _u(s0, 5.3) < PROBABILIDAD_CARTEL and altura > 4.0:
            texto = TEXTOS_CARTEL[int(_u(s0, 6.7) * len(TEXTOS_CARTEL)) % len(TEXTOS_CARTEL)]
            resultado.append(Calcomania("cartel", cara.casa, cara.lado, cara.plano,
                                        round(posicion(_u(s0, 7.9), ANCHO_CARTEL), 2), 2.3 + 0.6 * _u(s0, 8.8),
                                        ANCHO_CARTEL, ALTO_CARTEL, _u(s0, 9.2), texto))
        ancho = cabe(0.8 + 1.0 * _u(s0, 11.3))
        if _u(s0, 10.1) < PROBABILIDAD_REMIENDO and altura > 3.0 and ancho:
            alto = 0.7 + 0.9 * _u(s0, 12.7)
            resultado.append(Calcomania("remiendo", cara.casa, cara.lado, cara.plano,
                                        round(posicion(_u(s0, 13.1), ancho, 0.3), 2),
                                        round(0.6 + (altura - alto - 1.2) * _u(s0, 14.3), 2), ancho, alto, _u(s0, 15.9)))
        ancho = cabe(1.0)
        if _u(s0, 16.3) < PROBABILIDAD_GRIETA and altura > 3.0 and lado_vis and ancho:
            resultado.append(Calcomania("grieta", cara.casa, cara.lado, cara.plano,
                                        round(posicion(_u(s0, 17.7), ancho, 0.3), 2),
                                        round(1.2 + (altura - 3.2) * _u(s0, 18.1), 2), ancho, 1.8, _u(s0, 19.3)))
        ancho = cabe(1.2 + 1.6 * _u(s0, 21.3), 0.1)
        if _u(s0, 20.9) < PROBABILIDAD_MANCHA and ancho:
            resultado.append(Calcomania("mancha", cara.casa, cara.lado, cara.plano,
                                        round(posicion(_u(s0, 22.7), ancho, 0.1), 2), 0.0, ancho,
                                        1.0 + 1.2 * _u(s0, 23.1), _u(s0, 24.9)))
        if _u(s0, 25.7) < PROBABILIDAD_BALCON and altura > 6.0 and not cara.es_callejon and largo >= ANCHO_BALCON + 1.0:
            resultado.append(Calcomania("balcon", cara.casa, cara.lado, cara.plano,
                                        round(posicion(_u(s0, 26.3), ANCHO_BALCON, 0.5), 2),
                                        round(altura * (0.38 + 0.2 * _u(s0, 27.1)), 2), ANCHO_BALCON, VOLADO_BALCON,
                                        _u(s0, 28.5)))
    return resultado


@dataclass(frozen=True)
class Cuerda:
    """Una cuerda de banderines de `a` a `b` (x, y, z), con la comba `caida` m en el medio."""

    a: tuple
    b: tuple
    caida: float
    semilla: float

    @property
    def largo(self):
        return math.dist(self.a, self.b)

    # Punto a la fracción t de la cuerda (comba parabólica).
    def punto(self, t):
        return (self.a[0] + (self.b[0] - self.a[0]) * t,
                self.a[1] + (self.b[1] - self.a[1]) * t - self.caida * 4 * t * (1 - t),
                self.a[2] + (self.b[2] - self.a[2]) * t)


# Cuerdas de banderines atravesando los callejones: entre dos paredes enfrentadas a menos de
# CALLEJON_MAXIMO_BANDERIN m, a una altura que cabe bajo el techo más bajo de las dos casas. `bases` es la
# lista alineada con `casas` de la altura (y) de la planta baja; `suelo(x, z)` la altura del terreno.
def banderines_de_callejones(casas, caras, bases):
    cuerdas, vistos = [], set()
    for n, cara in enumerate(caras):
        if not cara.es_callejon or cara.hueco > CALLEJON_MAXIMO_BANDERIN or cara.lado not in ("e", "n"):
            continue
        j = cara.vecina
        clave = (min(cara.casa, j), max(cara.casa, j), cara.lado)
        if clave in vistos:
            continue
        vistos.add(clave)
        s0 = casas[cara.casa].cx * 0.43 + casas[cara.casa].cz * 0.29 + n * 0.071
        if _u(s0, 1.3) >= PROBABILIDAD_BANDERIN or cara.largo < 2.5:
            continue
        techo = min(bases[cara.casa] + casas[cara.casa].alto_total, bases[j] + casas[j].alto_total)
        base = max(bases[cara.casa], bases[j])
        alto_max = min(base + ALTURA_BANDERIN[1], techo - 0.8)
        alto_min = base + ALTURA_BANDERIN[0]
        if alto_max < alto_min:
            continue
        cantidad = 1 + int(cara.largo > 7.0) + int(cara.largo > 12.0)
        for k in range(cantidad):
            t = cara.t0 + cara.largo * (k + 0.5 + 0.35 * (_u(s0, 2.7 + k) - 0.5)) / cantidad
            y = alto_min + (alto_max - alto_min) * _u(s0, 3.9 + k)
            if cara.lado == "e":
                a, b = (cara.plano, y, t), (cara.plano + cara.hueco, y + 0.4 * (_u(s0, 5.1 + k) - 0.5), t)
            else:
                a, b = (t, y, cara.plano), (t, y + 0.4 * (_u(s0, 5.1 + k) - 0.5), cara.plano + cara.hueco)
            cuerdas.append(Cuerda(a, b, CAIDA_BANDERIN * math.dist(a, b) + 0.12, _u(s0, 6.3 + k)))
    return cuerdas


# Banderas de una cuerda: lista de (t, color) a lo largo (t en 0-1), alternando colores de la paleta.
def banderas_de_cuerda(cuerda, paleta=COLORES_BANDERA):
    cantidad = max(1, int(cuerda.largo / SEPARACION_BANDERAS))
    inicio = int(cuerda.semilla * len(paleta))
    return [((k + 0.5) / cantidad, paleta[(inicio + k) % len(paleta)]) for k in range(cantidad)]


# -- Objetos de la calle ---------------------------------------------------------------------------

TIPOS_OBJETO = ("bidon", "maceta", "moto", "bici", "caja", "perro")
SEPARACION_OBJETO = 0.40        # m de la pared al borde de un objeto del piso
HUECO_OBJETO_MIN = 2.2          # m: en pasillos más estrechos que esto no se ponen objetos en el piso
PROBABILIDAD_OBJETO = 0.50      # fracción de las caras abiertas o anchas con un objeto


@dataclass(frozen=True)
class Objeto:
    """Un objeto del piso pegado a una pared: `tipo`, posición (x, z), rumbo (rotation_y) y color/variante."""

    tipo: str
    x: float
    z: float
    rumbo: float
    variante: int
    casa: int


# Objetos del piso pegados a las paredes que dan a la calle o a pasillos de HUECO_OBJETO_MIN m o más.
def objetos_de_calle(casas, caras):
    objetos = []
    for n, cara in enumerate(caras):
        if cara.largo < 2.0 or (cara.es_callejon and cara.hueco < HUECO_OBJETO_MIN):
            continue
        casa = casas[cara.casa]
        s0 = casa.cx * 0.67 + casa.cz * 0.21 + n * 0.173
        if _u(s0, 1.7) >= PROBABILIDAD_OBJETO:
            continue
        tipo = TIPOS_OBJETO[int(_u(s0, 2.9) * len(TIPOS_OBJETO)) % len(TIPOS_OBJETO)]
        radio = {"bidon": 0.35, "maceta": 0.3, "moto": 0.55, "bici": 0.5, "caja": 0.4, "perro": 0.4}[tipo]
        t = cara.t0 + 0.5 + (cara.largo - 1.0) * _u(s0, 3.3)
        dist = SEPARACION_OBJETO + radio
        x, z = cara.punto(t, dist)
        rumbo = math.degrees(math.atan2(*NORMAL[cara.lado]))
        if tipo in ("moto", "bici"):
            rumbo = (rumbo + 90) % 360          # paralelas a la pared
        objetos.append(Objeto(tipo, round(x, 2), round(z, 2), round(rumbo, 1), int(_u(s0, 4.7) * 6), cara.casa))
    return objetos


# -- Pasadizos: cuartos que cruzan un callejón por encima ----------------------------------------------

PROBABILIDAD_PASADIZO = 0.09    # fracción de callejones estrechos con un cuarto que lo cruza por arriba
HUECO_PASADIZO_MAX = 2.7        # m: solo se tapan callejones angostos
ALTO_LIBRE_PASADIZO = 3.7       # m libres bajo el cuarto (de sobra para el jugador de 1,8 m)
ALTO_CUARTO = 2.5               # m de alto del cuarto
LARGO_CUARTO = 2.8              # m del cuarto a lo largo del callejón
ALTO_MINIMO_CASA = 8.5          # m: las dos casas deben ser más altas que esto (el cuarto cabe bajo sus techos)


@dataclass(frozen=True)
class Pasadizo:
    """Un cuarto construido sobre un callejón, apoyado en las paredes de las dos casas: caja alineada
    (cx, cz, ancho en x, fondo en z) desde `y` hasta `y + alto`."""

    cx: float
    cz: float
    ancho: float
    fondo: float
    y: float
    alto: float
    semilla: float


# Pasadizos de los callejones: cada uno cruza un hueco de 1,5-2,7 m entre dos paredes enfrentadas altas.
# `bases` es la lista alineada con `casas` de la altura (y) de la planta baja.
def pasadizos_de_callejones(casas, caras, bases):
    resultado, vistos = [], set()
    for n, cara in enumerate(caras):
        if not cara.es_callejon or cara.hueco > HUECO_PASADIZO_MAX or cara.lado not in ("e", "n") or cara.largo < LARGO_CUARTO + 1.2:
            continue
        j = cara.vecina
        clave = (min(cara.casa, j), max(cara.casa, j), cara.lado)
        if clave in vistos:
            continue
        vistos.add(clave)
        a, b = casas[cara.casa], casas[j]
        if min(a.alto_total, b.alto_total) < ALTO_MINIMO_CASA:
            continue
        s0 = a.cx * 0.59 + a.cz * 0.83 + n * 0.131
        if _u(s0, 1.9) >= PROBABILIDAD_PASADIZO:
            continue
        t = cara.t0 + 0.6 + LARGO_CUARTO / 2 + (cara.largo - LARGO_CUARTO - 1.2) * _u(s0, 2.3)
        y = max(bases[cara.casa], bases[j]) + ALTO_LIBRE_PASADIZO + 1.0 * _u(s0, 3.1)
        hueco = cara.hueco + 0.2                       # entra 0,1 m en cada pared
        if cara.lado == "e":
            resultado.append(Pasadizo(round(cara.plano + cara.hueco / 2, 3), round(t, 3), round(hueco, 3), LARGO_CUARTO, round(y, 2), ALTO_CUARTO, _u(s0, 4.3)))
        else:
            resultado.append(Pasadizo(round(t, 3), round(cara.plano + cara.hueco / 2, 3), LARGO_CUARTO, round(hueco, 3), round(y, 2), ALTO_CUARTO, _u(s0, 4.3)))
    return resultado
