# Barrio denso de la favela (datos puros, sin ursina): genera las casas apretadas de la ladera, los
# callejones peatonales entre ellas y las zonas abiertas (cancha y mercadito).
#
# Idea: las casas se alinean en FILAS paralelas al eje x (como las terrazas de una ladera) y dentro
# de cada fila se colocan de izquierda a derecha con un hueco de HUECO_CASA m entre una y otra. Entre
# filas queda un pasillo de HUECO_FILA m. Cada casa es un modelo de Blender (casa1-4) con su escala,
# su estiramiento en profundidad, su rumbo (múltiplo de 90) y de 1 a 3 pisos, y puede quedar pegada
# al frente, al fondo o centrada en su fila: así los pasillos no son rectas perfectas sino
# ensanchamientos y estrechamientos, con rincones y patios (un hueco ocasional de varios metros).
#
# Todo pasa por filtros duros, los mismos que usaban las casas sueltas de antes pero más estrictos:
#   - CALLEJON_MIN m (1,5) libres entre dos casas: por ahí cabe el jugador (diámetro 0,7 m) con holgura
#     y no hay dos casas "casi tocándose" por una rendija intransitable;
#   - fuera de plazas, calles (asfalto + acera + DESPEJE_CALLE), accesos a las puertas, escaleras,
#     spawns, edificios jugables (DESPEJE_EDIFICIO m) y de las zonas abiertas;
#   - el suelo bajo la huella no varía más de DESNIVEL_LOTE m.
# Al final una pasada con la rejilla de conectividad quita las casas que dejarían una bolsa de suelo
# libre aislada de las calles (no pasa casi nunca; es una red de seguridad).
#
# Es determinista: mismo mapa y misma semilla -> mismas casas. El azar es un random.Random propio.

import math
import random
from dataclasses import replace

from backend.datos.conectividad import Rejilla
from backend.datos.modelos_edificios import MODELOS, modelo_de
from backend.grafos.mapa_ciudad import _distancia_punto_segmento
from backend.logica.mundo_ciudad import (
    RADIO_JUGADOR,
    Callejon,
    CasaDecorativa,
    Obstaculo,
    Zona,
    _distancia_punto_caja,
    _distancia_segmento_caja,
)

# -- Cantidades y azar --
CANTIDAD_BARRIO = 900            # tope de casas del barrio denso (el relleno real es menor)
SEMILLA_BARRIO = 7               # semilla base de las filas (se suma a la semilla del mundo)
# -- Filas de casas --
BORDE_BARRIO = 5.0               # m sin casas en el borde de la ladera
PROFUNDIDAD_FILA = (7.0, 10.5)   # m de fondo disponible para cada fila de casas
HUECO_FILA = (1.7, 3.0)          # m del pasillo entre una fila y la siguiente
HUECO_CASA = (1.6, 2.8)          # m del callejón entre dos casas vecinas de la misma fila
ONDA_FILA = (1.2, 3.0)           # m de amplitud con la que una fila serpentea (como una curva de nivel)
LARGO_ONDA = (45.0, 90.0)        # m de longitud de onda de ese serpenteo
FASE_ENTRE_FILAS = 0.12          # rad que se desfasa cada fila respecto de la anterior (las vecinas casi paralelas)
AJUSTES_Z = (0.0, 0.6, -0.6, 1.2, -1.2)   # m que se prueba correr una casa en z si choca con la fila vecina
PROBABILIDAD_PATIO = 0.07        # fracción de huecos que son un patio abierto de 5 a 9 m
HUECO_PATIO = (5.0, 9.0)
# -- Casas --
ESCALA_BARRIO = (2.15, 2.9)      # escala del modelo (ancho y alto); 1 piso mide ~6-9 m de alto
ESTIRAMIENTO = (0.7, 1.55)       # factor de profundidad permitido
ANCHO_OBJETIVO = (5.5, 10.0)     # m de ancho deseado cuando el ancho se puede ajustar (casa de lado)
PISOS = (1,) * 14 + (2,) * 5 + (3,)      # reparto de pisos: 70 % uno, 25 % dos, 5 % tres
RUMBOS_FILA = (0, 180)           # fachada hacia el pasillo de la fila (mirando a +z o -z)
PROBABILIDAD_DE_LADO = 0.3       # fracción de casas que miran al callejón entre vecinas (±x)
DISTANCIA_MIRA_RED = 30.0        # m: más cerca que esto de una calle o plaza, la casa mira hacia ella
# -- Reglas de despeje --
CALLEJON_MIN = 1.5               # m mínimos entre dos casas (hay paso para el jugador)
DESPEJE_PLAZA = 1.2              # m libres alrededor del aro de cada plaza
DESPEJE_CALLE = 0.8              # m libres tras la acera (la acera mide 2 m y el asfalto 8 m)
ACERA_CALLE = 2.0                # m de acera a cada lado del asfalto
DESPEJE_EDIFICIO = 2.0           # m libres alrededor de los edificios jugables
DESPEJE_ZONA = 1.0               # m libres alrededor de la cancha y el mercadito
DESNIVEL_LOTE = 3.5              # m máximos de desnivel bajo la huella
ADELGAZAR_LEJOS = 40.0           # m de la red a partir de los cuales faltan casas (el barrio se ralea)
PROBABILIDAD_HUECO_LEJOS = 0.55  # fracción máxima de casas que faltan en el borde lejano


# -- Zonas abiertas --------------------------------------------------------------------------------

CANCHA = (24.0, 14.0)            # m (largo, ancho) de la cancha de fútbol de barrio
MERCADO = (16.0, 9.0)            # m del mercadito de toldos

# Rincones secretos (easter eggs, bandera EASTER_EGGS): dos puestos de broma escondidos en lo alto de la ladera,
# uno a cada lado (cuadrantes CUADRANTES_SECRETOS de los límites), lejos de calles y plazas: un «expendio» de talco
# y dulces y una «armería» de pistolas de agua. Son decorado (no cambian misiones ni indicadores, no salen en el
# minimapa ni en el GPS); lo único que choca es la mesa (mesas_secretas). Deterministas: mismo mapa, mismo sitio en
# todos los equipos. False = el barrio de antes (sin las zonas ni las mesas).
EASTER_EGGS = True
SECRETOS = ("puesto_talco", "armeria_juguete")
RINCON_SECRETO = (5.0, 4.0)      # m del rincón (largo, ancho)
LEJOS_SECRETO = 6.0              # m mínimos a calles y plazas: que no se vea desde ellas
MESA_SECRETA = (2.4, 0.9)        # m de la mesa del puesto (a lo largo del lado largo del rincón)
# (x0, x1, z0, z1) como fracción de los límites: arriba a la izquierda y arriba a la derecha.
CUADRANTES_SECRETOS = ((0.0, 0.45, 0.5, 1.0), (0.55, 1.0, 0.5, 1.0))


# Zona rectangular de `ancho` x `fondo` (en x, z) lo más plana posible dentro de `limites`, a más de
# `lejos` m de calles y plazas y de las cajas `ocupadas`; prueba las dos orientaciones. Usa la altura
# `suelo(x, z)` del terreno. Devuelve (cx, cz, ancho, fondo) o None. `cerca` (x, z) desempata hacia
# el punto más próximo entre los de igual desnivel redondeado a 0,25 m.
def buscar_zona_plana(mapa, ocupadas, suelo, limites, largo, ancho, lejos, cerca=None, evitar=(), paso=2.0):
    xmin, xmax, zmin, zmax = limites
    calles = [(mapa.coordenada(a), mapa.coordenada(b)) for a, b in mapa.segmentos()]
    plazas = [mapa.coordenada(lugar) for lugar in mapa.lugares()]
    mejor = None
    for ancho_x, fondo_z in ((largo, ancho), (ancho, largo)):
        x = xmin + ancho_x / 2 + 1
        while x <= xmax - ancho_x / 2 - 1:
            z = zmin + fondo_z / 2 + 1
            while z <= zmax - fondo_z / 2 - 1:
                caja = (x - ancho_x / 2, x + ancho_x / 2, z - fondo_z / 2, z + fondo_z / 2)
                if _caja_libre(caja, calles, plazas, mapa, ocupadas, evitar, lejos):
                    alturas = [suelo(px, pz) for px in (caja[0], x, caja[1]) for pz in (caja[2], z, caja[3])]
                    desnivel = round((max(alturas) - min(alturas)) * 4) / 4
                    cercania = math.dist((x, z), cerca) if cerca else 0.0
                    clave = (desnivel, cercania)
                    if mejor is None or clave < mejor[0]:
                        mejor = (clave, (x, z, ancho_x, fondo_z))
                z += paso
            x += paso
    return mejor[1] if mejor else None


def _caja_libre(caja, calles, plazas, mapa, ocupadas, evitar, lejos):
    if any(_distancia_punto_caja(px, pz, caja) < mapa.radio_plaza + 0.9 + lejos for px, pz in plazas):
        return False
    if any(_distancia_segmento_caja(a, b, caja) < mapa.ancho_calle / 2 + ACERA_CALLE + lejos for a, b in calles):
        return False
    if any(_cajas_cerca(caja, otra, lejos) for otra in list(ocupadas) + list(evitar)):
        return False
    return True


def _cajas_cerca(a, b, margen):
    return a[0] < b[1] + margen and b[0] < a[1] + margen and a[2] < b[3] + margen and b[2] < a[3] + margen


# -- Casas ---------------------------------------------------------------------------------------


def _caja(c):
    return (c.cx - c.ancho / 2, c.cx + c.ancho / 2, c.cz - c.fondo / 2, c.cz + c.fondo / 2)


# Huella (en x, en z) de un modelo con su escala, estiramiento y rumbo.
def huella(modelo, escala, estiramiento, rumbo):
    m = modelo_de(modelo)
    frente, fondo = m.frente * escala, m.fondo * escala * estiramiento
    return (frente, fondo) if rumbo % 180 == 0 else (fondo, frente)


def _punto_mas_cercano(p, a, b):
    dx, dz = b[0] - a[0], b[1] - a[1]
    largo2 = dx * dx + dz * dz
    t = 0.0 if largo2 < 1e-12 else min(1.0, max(0.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dz) / largo2))
    return (a[0] + dx * t, a[1] + dz * t)


class _Barrio:
    """Estado de la generación: reglas de despeje y rejilla de vecinos para no solaparse."""

    def __init__(self, mapa, edificios, despeje, previos, terreno, zonas, limites):
        self.mapa = mapa
        self.terreno = terreno
        self.despeje = despeje
        self.calles = [(mapa.coordenada(a), mapa.coordenada(b)) for a, b in mapa.segmentos()]
        self.plazas = [mapa.coordenada(lugar) for lugar in mapa.lugares()]
        self.cajas_edificios = [e.caja() for e in edificios]
        self.cajas_zonas = [z.caja() for z in zonas]
        self.radio_plaza = mapa.radio_plaza + 0.9 + DESPEJE_PLAZA
        self.semiancho_calle = mapa.ancho_calle / 2 + ACERA_CALLE + DESPEJE_CALLE
        self.limites = limites
        self.celda = 12.0
        self.vecinos = {}
        for o in previos:
            self.ocupar(o)

    def ocupar(self, o):
        self.vecinos.setdefault((int(o.cx // self.celda), int(o.cz // self.celda)), []).append(o)

    def cercanos(self, cx, cz):
        i, j = int(cx // self.celda), int(cz // self.celda)
        return [o for di in (-1, 0, 1) for dj in (-1, 0, 1) for o in self.vecinos.get((i + di, j + dj), ())]

    def distancia_a_la_red(self, x, z):
        return min(min(_distancia_punto_segmento((x, z), a, b) for a, b in self.calles),
                   min(math.dist((x, z), p) for p in self.plazas))

    # Rumbo (múltiplo de 90) hacia el punto más cercano de la red de calles y plazas.
    def rumbo_hacia_la_red(self, x, z):
        puntos = list(self.plazas) + [_punto_mas_cercano((x, z), a, b) for a, b in self.calles]
        px, pz = min(puntos, key=lambda p: math.dist((x, z), p))
        return (round(math.degrees(math.atan2(px - x, pz - z)) / 90) * 90) % 360

    # ¿Cabe la casa? Aplica todas las reglas duras.
    def permite(self, casa):
        caja = _caja(casa)
        xmin, xmax, zmin, zmax = self.limites
        if caja[0] < xmin or caja[1] > xmax or caja[2] < zmin or caja[3] > zmax:
            return False
        if any(_distancia_punto_caja(px, pz, caja) < self.radio_plaza for px, pz in self.plazas):
            return False
        if any(_distancia_segmento_caja(a, b, caja) < self.semiancho_calle for a, b in self.calles):
            return False
        if any(_cajas_cerca(caja, otra, DESPEJE_EDIFICIO) for otra in self.cajas_edificios):
            return False
        if any(_cajas_cerca(caja, otra, DESPEJE_ZONA) for otra in self.cajas_zonas):
            return False
        if not self.despeje.permite(casa):
            return False
        for o in self.cercanos(casa.cx, casa.cz):
            if _separacion(o, casa) < (CALLEJON_MIN if isinstance(o, CasaDecorativa) else 1.0):
                return False
        alturas = [self.terreno.altura(x, z) for x in (caja[0], casa.cx, caja[1]) for z in (caja[2], casa.cz, caja[3])]
        return max(alturas) - min(alturas) <= DESNIVEL_LOTE


# Distancia entre los bordes de dos obstáculos (círculos o cajas alineadas).
def _separacion(a, b):
    if a.es_circulo and b.es_circulo:
        return math.hypot(a.cx - b.cx, a.cz - b.cz) - a.radio - b.radio
    if a.es_circulo:
        return _distancia_punto_caja(a.cx, a.cz, _caja(b)) - a.radio
    if b.es_circulo:
        return _distancia_punto_caja(b.cx, b.cz, _caja(a)) - b.radio
    ca, cb = _caja(a), _caja(b)
    dx = max(cb[0] - ca[1], ca[0] - cb[1], 0)
    dz = max(cb[2] - ca[3], ca[2] - cb[3], 0)
    return math.hypot(dx, dz)


# La casa con esa huella: modelo, rumbo, escala y estiramiento, centrada en (cx, cz).
def _casa(modelo, cx, cz, rumbo, escala, estiramiento, pisos, variante):
    ancho, fondo = huella(modelo, escala, estiramiento, rumbo)
    return CasaDecorativa("casa", round(cx, 2), round(cz, 2), ancho=round(ancho, 3), fondo=round(fondo, 3),
                          modelo=modelo, rumbo=rumbo, escala=round(escala, 3), variante=variante, pisos=pisos,
                          estiramiento=round(estiramiento, 3))


# Una propuesta de casa de la fila que empieza en `x_izq` y tiene `prof` m de fondo desde `z_fila`.
# `reduccion` (1.0, 0.85...) encoge las dimensiones en los reintentos.
def _proponer(azar, barrio, x_izq, z_fila, prof, reduccion):
    modelos = sorted(MODELOS)
    modelo = azar.choice(modelos)
    escala = azar.uniform(*ESCALA_BARRIO) * min(1.0, reduccion + 0.1)
    pisos = azar.choice(PISOS)
    if pisos > 1:
        escala = min(escala, 2.45)            # las casas altas no son las más anchas
    m = modelo_de(modelo)
    # rumbo provisional con la posición aproximada para saber a qué lado mira
    x_prov, z_prov = x_izq + 4.0, z_fila + prof / 2
    if barrio.distancia_a_la_red(x_prov, z_prov) < DISTANCIA_MIRA_RED:
        rumbo = barrio.rumbo_hacia_la_red(x_prov, z_prov)
    elif azar.random() < PROBABILIDAD_DE_LADO:
        rumbo = azar.choice((90, 270))
    else:
        rumbo = azar.choice(RUMBOS_FILA)
    objetivo_z = prof * azar.uniform(0.82, 1.0) * reduccion
    if rumbo % 180 == 0:
        est = min(max(objetivo_z / (m.fondo * escala), ESTIRAMIENTO[0]), ESTIRAMIENTO[1])
    else:
        objetivo_x = azar.uniform(*ANCHO_OBJETIVO) * reduccion
        est = min(max(objetivo_x / (m.fondo * escala), ESTIRAMIENTO[0]), ESTIRAMIENTO[1])
    ancho, fondo = huella(modelo, escala, est, rumbo)
    if fondo > prof:                            # nunca más fondo que la fila: se achata la profundidad
        est = max(ESTIRAMIENTO[0] * 0.8, est * prof / fondo) if rumbo % 180 == 0 else est
        ancho, fondo = huella(modelo, escala, est, rumbo)
        if fondo > prof:
            return None
    anclaje = azar.random()                     # pegada al frente, al fondo o centrada en la fila
    if anclaje < 0.4:
        cz = z_fila + fondo / 2
    elif anclaje < 0.8:
        cz = z_fila + prof - fondo / 2
    else:
        cz = z_fila + prof / 2
    return _casa(modelo, x_izq + ancho / 2, cz, rumbo, escala, est, pisos, azar.randrange(4))


# Casas del barrio: filas de izquierda a derecha, con los filtros de la clase _Barrio. `cantidad`
# es el tope. `limites` es el rectángulo (xmin, xmax, zmin, zmax) donde puede haber casas. `fabrica_barrio` construye
# el estado de la generación (por defecto _Barrio; barrio_indexado._BarrioIndexado da el mismo resultado con índices).
def generar_casas(mapa, edificios, despeje, previos, terreno, zonas, limites, semilla, cantidad=CANTIDAD_BARRIO,
                   fabrica_barrio=_Barrio):
    azar = random.Random(semilla + SEMILLA_BARRIO)
    barrio = fabrica_barrio(mapa, edificios, despeje, previos, terreno, zonas, limites)
    x0, x1, z0, z1 = limites
    casas = []
    z_fila = z0
    numero_fila = 0
    amplitud, largo_onda = azar.uniform(*ONDA_FILA), azar.uniform(*LARGO_ONDA)
    fase = azar.uniform(0.0, 2 * math.pi)
    while z_fila < z1 and len(casas) < cantidad:
        prof = azar.uniform(*PROFUNDIDAD_FILA)
        x = x0 + azar.uniform(0.0, 3.0)
        fase_fila = fase + FASE_ENTRE_FILAS * numero_fila
        numero_fila += 1
        while x < x1 and len(casas) < cantidad:
            casa, falta = None, False
            for reduccion in (1.0, 0.85, 0.7):
                z_local = z_fila + amplitud * math.sin(2 * math.pi * (x + 4.0) / largo_onda + fase_fila)
                propuesta = _proponer(azar, barrio, x, z_local, prof, reduccion)
                if propuesta is None:
                    continue
                if reduccion == 1.0 and not _se_queda(azar, barrio, propuesta):
                    falta = True              # falta por azar (borde lejano): no se reintenta
                    break
                for dz in AJUSTES_Z:          # si choca con la fila vecina, se corre un poco
                    movida = propuesta if dz == 0 else replace(propuesta, cz=round(propuesta.cz + dz, 2))
                    if barrio.permite(movida):
                        casa = movida
                        break
                if casa is not None:
                    break
            if casa is None:
                x += azar.uniform(3.0, 6.0) if falta else 2.0     # sigue hasta el próximo sitio libre
                continue
            casas.append(casa)
            barrio.ocupar(casa)
            hueco = azar.uniform(*HUECO_PATIO) if azar.random() < PROBABILIDAD_PATIO else azar.uniform(*HUECO_CASA)
            x = _caja(casa)[1] + hueco
        z_fila += prof + azar.uniform(*HUECO_FILA)
    return casas


# ¿La casa se queda o es de las que faltan en el borde lejano? (azar decidido por posición, estable).
def _se_queda(azar, barrio, casa):
    lejos = barrio.distancia_a_la_red(casa.cx, casa.cz) - ADELGAZAR_LEJOS
    if lejos <= 0:
        return True
    return azar.random() >= min(PROBABILIDAD_HUECO_LEJOS, PROBABILIDAD_HUECO_LEJOS * lejos / 40.0)


# -- Bolsas aisladas ---------------------------------------------------------------------------------


# Quita las casas que encierran suelo libre sin salida: celdas libres del jugador, dentro de `limites`,
# que no se alcanzan desde `semilla_xz` (un punto de calle). Devuelve la lista sin esas casas.
def quitar_bolsas(casas, fijos, semilla_xz, limites, resolucion=0.5, maximo_vueltas=6):
    casas = list(casas)
    for _ in range(maximo_vueltas):
        rejilla = Rejilla(limites, resolucion)
        for caja in fijos:
            rejilla.bloquear_caja(caja, RADIO_JUGADOR)
        for c in casas:
            rejilla.bloquear_caja(_caja(c), RADIO_JUGADOR)
        vistas = rejilla.alcanzables(*semilla_xz)
        aisladas = [k for k in range(rejilla.nx * rejilla.nz) if rejilla.libre[k] and not vistas[k]]
        if not aisladas:
            return casas
        quitar = set()
        for k in aisladas:
            x, z = rejilla.centro(k % rejilla.nx, k // rejilla.nx)
            cercana = min(casas, key=lambda c: _distancia_punto_caja(x, z, _caja(c)), default=None)
            if cercana is not None and _distancia_punto_caja(x, z, _caja(cercana)) < 2.0:
                quitar.add(id(cercana))
        if not quitar:
            return casas
        casas = [c for c in casas if id(c) not in quitar]
    return casas


# -- Callejones --------------------------------------------------------------------------------------


# Pasillos entre casas: para cada par de casas enfrentadas por un lado (solape de >= SOLAPE_MIN m y
# una separación de CALLEJON_MIN a ANCHO_MAX_CALLEJON m) un Callejon sobre el eje del hueco.
ANCHO_MAX_CALLEJON = 3.4
SOLAPE_MIN = 1.5


def callejones_entre(casas):
    cajas = [_caja(c) for c in casas]
    celda = 14.0
    grilla = {}
    for k, caja in enumerate(cajas):
        for i in range(int(caja[0] // celda), int(caja[1] // celda) + 1):
            for j in range(int(caja[2] // celda), int(caja[3] // celda) + 1):
                grilla.setdefault((i, j), []).append(k)
    vistos, resultado = set(), []
    for k, a in enumerate(cajas):
        candidatos = set()
        for i in range(int((a[0] - ANCHO_MAX_CALLEJON) // celda), int((a[1] + ANCHO_MAX_CALLEJON) // celda) + 1):
            for j in range(int((a[2] - ANCHO_MAX_CALLEJON) // celda), int((a[3] + ANCHO_MAX_CALLEJON) // celda) + 1):
                candidatos.update(grilla.get((i, j), ()))
        for n in candidatos:
            if n <= k or (k, n) in vistos:
                continue
            b = cajas[n]
            solape_z = min(a[3], b[3]) - max(a[2], b[2])
            solape_x = min(a[1], b[1]) - max(a[0], b[0])
            hueco_x = max(b[0] - a[1], a[0] - b[1])
            hueco_z = max(b[2] - a[3], a[2] - b[3])
            if solape_z >= SOLAPE_MIN and CALLEJON_MIN - 1e-6 <= hueco_x <= ANCHO_MAX_CALLEJON:
                x = (a[1] + b[0]) / 2 if b[0] >= a[1] else (b[1] + a[0]) / 2
                z0, z1 = max(a[2], b[2]), min(a[3], b[3])
                resultado.append(Callejon(round(x, 2), round(z0, 2), round(x, 2), round(z1, 2), round(hueco_x, 2)))
                vistos.add((k, n))
            elif solape_x >= SOLAPE_MIN and CALLEJON_MIN - 1e-6 <= hueco_z <= ANCHO_MAX_CALLEJON:
                z = (a[3] + b[2]) / 2 if b[2] >= a[3] else (b[3] + a[2]) / 2
                x0, x1 = max(a[0], b[0]), min(a[1], b[1])
                resultado.append(Callejon(round(x0, 2), round(z, 2), round(x1, 2), round(z, 2), round(hueco_z, 2)))
                vistos.add((k, n))
    return resultado


# Las zonas abiertas del barrio (cancha, mercadito) sobre terreno `suelo` dentro de `limites`.
def zonas_abiertas(mapa, edificios, suelo, limites):
    ocupadas = [e.caja() for e in edificios]
    zonas = []
    cancha = buscar_zona_plana(mapa, ocupadas, suelo, limites, CANCHA[0], CANCHA[1], lejos=3.0,
                               cerca=mapa.coordenada("Praça da Sé") if "Praça da Sé" in mapa.lugares() else None)
    if cancha:
        zonas.append(Zona("cancha", round(cancha[0], 2), round(cancha[1], 2), cancha[2], cancha[3]))
    # El mercadito queda pegado a la acera de una calle, para que el paso hacia él sea la propia calle.
    mercado = _mercado_junto_a_calle(mapa, ocupadas + [z.caja() for z in zonas], suelo, limites)
    if mercado:
        zonas.append(mercado)
    if EASTER_EGGS:
        zonas += _rincones_secretos(mapa, ocupadas + [z.caja() for z in zonas], suelo, limites)
    return zonas


# Un rincón plano por tipo de SECRETOS, cada uno en su cuadrante de los límites (ver EASTER_EGGS).
def _rincones_secretos(mapa, ocupadas, suelo, limites):
    xmin, xmax, zmin, zmax = limites
    ancho, alto = xmax - xmin, zmax - zmin
    rincones = []
    for tipo, (fx0, fx1, fz0, fz1) in zip(SECRETOS, CUADRANTES_SECRETOS):
        cuadrante = (xmin + ancho * fx0, xmin + ancho * fx1, zmin + alto * fz0, zmin + alto * fz1)
        arriba = ((cuadrante[0] + cuadrante[1]) / 2, cuadrante[3])      # desempata hacia lo alto del cuadrante
        sitio = buscar_zona_plana(mapa, ocupadas + [r.caja() for r in rincones], suelo, cuadrante,
                                  RINCON_SECRETO[0], RINCON_SECRETO[1], lejos=LEJOS_SECRETO, cerca=arriba)
        if sitio:
            rincones.append(Zona(tipo, round(sitio[0], 2), round(sitio[1], 2), sitio[2], sitio[3]))
    return rincones


# Los rincones secretos ya orientados: cada uno mira (rumbo 0/90/180/270) hacia el lado por el que se llega, el que
# tiene más suelo libre de `cajas` (las casas ya colocadas) delante de su borde; si empatan, hacia la plaza más
# cercana. Las demás zonas se devuelven tal cual.
def orientar_secretos(zonas, cajas, mapa):
    plazas = [mapa.coordenada(lugar) for lugar in mapa.lugares()]
    resultado = []
    for z in zonas:
        if z.tipo not in SECRETOS:
            resultado.append(z)
            continue
        px, pz = min(plazas, key=lambda p: math.hypot(p[0] - z.cx, p[1] - z.cz))

        def puntaje(rumbo, z=z, px=px, pz=pz):
            fx, fz = round(math.sin(math.radians(rumbo))), round(math.cos(math.radians(rumbo)))
            borde = abs(fx) * z.ancho / 2 + abs(fz) * z.fondo / 2
            libres = 0
            for d in (0.8, 1.6, 2.4, 3.2):
                for lado in (-1.0, 0.0, 1.0):
                    x, y = z.cx + fx * (borde + d) + fz * lado, z.cz + fz * (borde + d) - fx * lado
                    libres += not any(c[0] - RADIO_JUGADOR <= x <= c[1] + RADIO_JUGADOR
                                      and c[2] - RADIO_JUGADOR <= y <= c[3] + RADIO_JUGADOR for c in cajas)
            return libres, (px - z.cx) * fx + (pz - z.cz) * fz

        resultado.append(replace(z, rumbo=max((0.0, 90.0, 180.0, 270.0), key=puntaje)))
    return resultado


# La mesa de cada rincón secreto como Obstaculo (lo único que choca): en el centro, a lo ancho del frente (su rumbo).
def mesas_secretas(zonas):
    mesas = []
    for z in zonas:
        if z.tipo in SECRETOS:
            largo, fondo = MESA_SECRETA
            frente_en_z = z.rumbo % 180 == 0              # mira a +z o -z: la mesa va a lo largo de x
            ancho, alto = (largo, fondo) if frente_en_z else (fondo, largo)
            mesas.append(Obstaculo("puesto_secreto", z.cx, z.cz, ancho=ancho, fondo=alto))
    return mesas


# Rectángulo de MERCADO a un lado de una calle, pegado a su acera, lo más plano posible.
def _mercado_junto_a_calle(mapa, ocupadas, suelo, limites):
    xmin, xmax, zmin, zmax = limites
    calles = [(mapa.coordenada(a), mapa.coordenada(b)) for a, b in mapa.segmentos()]
    plazas = [mapa.coordenada(lugar) for lugar in mapa.lugares()]
    mejor = None
    for a, b in calles:
        largo = math.dist(a, b)
        if largo < 1e-9:
            continue
        ux, uz = (b[0] - a[0]) / largo, (b[1] - a[1]) / largo
        for lado in (-1, 1):
            for t in (0.4, 0.5, 0.6):
                for ancho_x, fondo_z in ((MERCADO[0], MERCADO[1]), (MERCADO[1], MERCADO[0])):
                    # centro: sobre el eje a distancia (mitad de calle + acera + despeje + mitad del rectángulo)
                    mitad = ancho_x / 2 * abs(uz) + fondo_z / 2 * abs(ux)
                    d = mapa.ancho_calle / 2 + ACERA_CALLE + 1.0 + mitad
                    cx = a[0] + ux * largo * t - uz * lado * d
                    cz = a[1] + uz * largo * t + ux * lado * d
                    caja = (cx - ancho_x / 2, cx + ancho_x / 2, cz - fondo_z / 2, cz + fondo_z / 2)
                    if not (xmin + 1 <= caja[0] and caja[1] <= xmax - 1 and zmin + 1 <= caja[2] and caja[3] <= zmax - 1):
                        continue
                    if any(_distancia_punto_caja(px, pz, caja) < mapa.radio_plaza + 0.9 + 1.0 for px, pz in plazas):
                        continue
                    if any(_distancia_segmento_caja(p, q, caja) < mapa.ancho_calle / 2 + ACERA_CALLE + 0.5
                           for p, q in calles):
                        continue
                    if any(_cajas_cerca(caja, o, 1.5) for o in ocupadas):
                        continue
                    alturas = [suelo(x, z) for x in (caja[0], cx, caja[1]) for z in (caja[2], cz, caja[3])]
                    desnivel = max(alturas) - min(alturas)
                    if mejor is None or desnivel < mejor[0]:
                        mejor = (desnivel, Zona("mercado", round(cx, 2), round(cz, 2), ancho_x, fondo_z))
    return mejor[1] if mejor else None
