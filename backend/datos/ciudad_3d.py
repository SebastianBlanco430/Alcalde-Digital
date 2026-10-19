# Ciudad Nova en 3D (datos puros): el mapa de ejemplo a escala real, los 7 edificios
# ubicados a mano y los obstáculos decorativos (árboles del parque, farolas, bancos).
#
# Escala: 1 unidad = 1 metro. Las coordenadas del grafo del ejemplo se multiplican por
# ESCALA_MUNDO (4); calles de 8 m y plazas de radio 9 m. Los spawns de los roles
# (roles.py guarda los del mapa pequeño) se escalan con la misma constante.
#
# Cada edificio queda en el lado LIBRE de su plaza (donde no sale ninguna calle), con su
# puerta mirando al centro de la plaza. MundoCiudad valida en su constructor que ninguno
# tape una plaza ni una calle. Los obstáculos decorativos se generan por reglas y se
# descartan si estorbarían: ninguno se acerca a menos de 1.2 m del eje de una calle, del
# camino plaza -> puerta ni de un spawn, así que los recorridos siempre están despejados.

import math
import random
from dataclasses import replace

from backend.datos.modelos_edificios import MODELOS, modelo_de
from backend.datos.terreno import Terreno
from backend.grafos.grafo_ciudad import construir_grafo_ciudad_ejemplo
from backend.grafos.mapa_ciudad import COORDENADAS_EJEMPLO, MapaCiudad, _distancia_punto_segmento
from backend.logica.mundo_ciudad import (
    _NORMAL_FUERA,
    CasaDecorativa,
    Edificio,
    Escalera,
    MundoCiudad,
    Obstaculo,
    _distancia_punto_caja,
    _distancia_segmento_caja,
)
from backend.logica.roles import ROLES

ESCALA_MUNDO = 4
ANCHO_CALLE = 8
RADIO_PLAZA = 9
MARGEN_EDIFICIOS = 4.0      # m de pasto transitable alrededor de los edificios del borde

ESPACIO_LIBRE = 1.2         # m mínimos entre un obstáculo y las líneas que deben quedar libres
ESPACIO_EDIFICIO = 1.0      # m mínimos entre un obstáculo decorativo y un edificio

ALTO_PUERTA_MAXIMO = 3.2   # m: tope de escala de los modelos, para que las puertas no sean gigantes

# Casas decorativas de la favela (ver _casas_favela).
CANTIDAD_CASAS = 150
SEMILLA_CASAS = 2026
CALLEJON = 1.2              # m mínimos entre dos casas: los callejones
DESPEJE_PLAZA = 2.5         # m libres alrededor del aro de cada plaza
DESPEJE_CALLE = 3.0         # m libres a cada lado del asfalto (aceras de 2 m y un poco más)
DESNIVEL_LOTE = 3.0         # m máximos de desnivel bajo la huella de una casa
PASO_CANDIDATOS = 2.0       # m entre posiciones candidatas
BORDE_LADERA = 6.0          # m que se dejan sin casas en el borde de la ladera
ESCALAS_CASA = (2.2, 2.7)
PISOS_CASA = (1, 1, 1, 2)
# Escaleras de la favela (ver _escaleras).
LARGO_ESCALERA = 14.0       # m desde el borde de la acera
ANCHO_ESCALERA = 1.6
DESNIVEL_ESCALERA = 1.5     # m mínimos que tiene que salvar una escalera
# Vegetación suelta en la ladera (ver _vegetacion).
CANTIDAD_VEGETACION = 70
SEPARACION_VEGETACION = 0.8 # m entre una planta y cualquier otra cosa         # sorteo: cada modelo ya tiene ~2 plantas; 2 copias = una casa de 4

# (lugar, cx, cz, ancho en x, fondo en z, alto, lado de la puerta, nombre del letrero, modelo 3D)
# Con modelo, (cx, cz, ancho, fondo) es el LOTE: el modelo se escala sin deformarse para caber
# en él y la caja del edificio pasa a ser la del modelo (ver _encajar_modelo); `alto` se ignora.
# Sin modelo (""), la caja es el edificio de cubos tal cual.
_EDIFICIOS = (
    ("Plaza Central", -3, 18, 12, 10, 7, "s", "Café Internet de la Plaza", "casa1"),
    ("Alcaldía", -32, 18, 14, 10, 9, "s", "", "casa4"),
    ("Universidad de Ciudad Nova", 24, 46, 14, 12, 10, "s", "", "casa1"),
    ("Parque Municipal", 74, 20, 12, 12, 6, "o", "Biblioteca del Parque", "casa2"),
    ("Barrio Las Flores", 40, -8.5, 12, 12, 6, "e", "", "casa3"),
    ("Terminal de Buses", 24, -46, 14, 12, 6, "n", "", "casa2"),
    ("Hospital Las Flores", 84, -18, 14, 12, 9, "s", "", "casa4"),
)


def _construir_mapa():
    coordenadas = {lugar: (x * ESCALA_MUNDO, z * ESCALA_MUNDO) for lugar, (x, z) in COORDENADAS_EJEMPLO.items()}
    return MapaCiudad(construir_grafo_ciudad_ejemplo(), coordenadas,
                      ancho_calle=ANCHO_CALLE, radio_plaza=RADIO_PLAZA)


def _construir_edificios():
    edificios = []
    for lugar, cx, cz, ancho, fondo, alto, lado, nombre, modelo in _EDIFICIOS:
        lote = Edificio(lugar, cx, cz, ancho, fondo, alto, lado, nombre)
        edificios.append(_encajar_modelo(lote, modelo) if modelo else lote)
    return edificios


# El edificio con `modelo` dentro del `lote`: escala uniforme lo más grande posible (sin pasarse
# del lote ni de ALTO_PUERTA_MAXIMO), con la fachada de la puerta sobre la del lote y centrada en
# ella. La caja nueva queda siempre DENTRO del lote, así que no tapa nada que el lote no tapara.
def _encajar_modelo(lote, modelo):
    m = modelo_de(modelo)
    fondo_lote = lote.fondo if lote.lado_puerta in ("n", "s") else lote.ancho
    s = min(lote.frente / m.frente, fondo_lote / m.fondo, ALTO_PUERTA_MAXIMO / m.puerta_alto)
    frente, fondo = m.frente * s, m.fondo * s
    nx, nz = _NORMAL_FUERA[lote.lado_puerta]
    fx, fz = lote.cx + nx * lote.ancho / 2, lote.cz + nz * lote.fondo / 2     # centro de la fachada
    ancho, fondo_z = (frente, fondo) if lote.lado_puerta in ("n", "s") else (fondo, frente)
    return Edificio(lote.lugar, round(fx - nx * ancho / 2, 3), round(fz - nz * fondo_z / 2, 3),
                    round(ancho, 3), round(fondo_z, 3), round(m.alto * s, 3), lote.lado_puerta,
                    lote.nombre, modelo=modelo, desfase_puerta=round(m.puerta_x * s, 3))


def _spawns():
    return {rol: (info.spawn_x * ESCALA_MUNDO, info.spawn_y * ESCALA_MUNDO) for rol, info in ROLES.items()}


# Casa decorativa con el modelo `modelo` centrado en (cx, cz): su caja es la huella del modelo
# escalado y girado `rumbo` grados (múltiplo de 90).
def casa_decorativa(modelo, cx, cz, rumbo=0, escala=1.0, variante=0, pisos=1):
    m = modelo_de(modelo)
    frente, fondo = m.frente * escala, m.fondo * escala
    ancho, fondo_z = (frente, fondo) if rumbo % 180 == 0 else (fondo, frente)
    return CasaDecorativa("casa", cx, cz, ancho=round(ancho, 3), fondo=round(fondo_z, 3),
                          modelo=modelo, rumbo=rumbo, escala=escala, variante=variante, pisos=pisos)


# -- Reglas de despeje ------------------------------------------------------------------------


def _lineas_libres(mapa, edificios):
    """Segmentos que deben poder recorrerse: ejes de calle y plaza -> entrada -> puerta."""
    lineas = [(mapa.coordenada(a), mapa.coordenada(b)) for a, b in mapa.segmentos()]
    for e in edificios:
        centro = mapa.coordenada(e.lugar)
        lineas.append((centro, e.punto_entrada()))
        lineas.append((e.punto_entrada(), e.puerta()))
    return lineas


def _distancia_a_segmento(obstaculo, a, b):
    if obstaculo.es_circulo:
        return _distancia_punto_segmento((obstaculo.cx, obstaculo.cz), a, b) - obstaculo.radio
    return _distancia_segmento_caja(a, b, _caja(obstaculo))


def _distancia_a_punto(obstaculo, x, z):
    if obstaculo.es_circulo:
        return math.hypot(x - obstaculo.cx, z - obstaculo.cz) - obstaculo.radio
    return _distancia_punto_caja(x, z, _caja(obstaculo))


def _caja(o):
    return (o.cx - o.ancho / 2, o.cx + o.ancho / 2, o.cz - o.fondo / 2, o.cz + o.fondo / 2)


class _Despeje:
    """Decide si un obstáculo decorativo estorba algún recorrido, un spawn o un edificio."""

    def __init__(self, mapa, edificios, spawns):
        self._lineas = _lineas_libres(mapa, edificios)
        self._spawns = list(spawns.values())
        self._edificios = [e.como_obstaculo() for e in edificios]

    # Otra línea que debe quedar libre (p. ej. el eje de una escalera).
    def agregar_linea(self, a, b):
        self._lineas.append((a, b))

    def permite(self, obstaculo):
        if any(_distancia_a_segmento(obstaculo, a, b) < ESPACIO_LIBRE for a, b in self._lineas):
            return False
        if any(_distancia_a_punto(obstaculo, x, z) < ESPACIO_LIBRE for x, z in self._spawns):
            return False
        return all(_separacion_con_edificio(obstaculo, e) >= ESPACIO_EDIFICIO
                   for e in self._edificios)


def _separacion_con_edificio(obstaculo, caja_edificio):
    """Distancia entre el borde de `obstaculo` y la caja de un edificio."""
    caja = _caja(caja_edificio)
    if obstaculo.es_circulo:
        return _distancia_punto_caja(obstaculo.cx, obstaculo.cz, caja) - obstaculo.radio
    # caja contra caja alineadas: separación en cada eje (0 si se solapan en ese eje)
    ox, oz = _caja(obstaculo)[:2], _caja(obstaculo)[2:]
    dx = max(caja[0] - ox[1], ox[0] - caja[1], 0)
    dz = max(caja[2] - oz[1], oz[0] - caja[3], 0)
    return math.hypot(dx, dz)


def _separacion(a, b):
    """Distancia entre los bordes de dos obstáculos cualesquiera (círculos o cajas)."""
    if b.es_caja:
        return _separacion_con_edificio(a, b)
    if a.es_caja:
        return _separacion_con_edificio(b, a)
    return math.hypot(a.cx - b.cx, a.cz - b.cz) - a.radio - b.radio


# -- Decoración ------------------------------------------------------------------------------------


def _bancos(mapa, despeje):
    """Dos bancos por plaza, a 6 m del centro, separados al menos 90 grados."""
    bancos = []
    for lugar in mapa.lugares():
        cx, cz = mapa.coordenada(lugar)
        elegidos = []
        for grados in range(15, 360, 30):
            if any(abs((grados - g + 180) % 360 - 180) < 90 for g in elegidos):
                continue
            a = math.radians(grados)
            banco = Obstaculo("banco", round(cx + 6 * math.cos(a), 3), round(cz + 6 * math.sin(a), 3),
                              ancho=1.8, fondo=0.7)
            if despeje.permite(banco):
                elegidos.append(grados)
                bancos.append(banco)
            if len(elegidos) == 2:
                break
    return bancos


def _arboles_parque(mapa, despeje):
    cx, cz = mapa.coordenada("Parque Municipal")
    arboles = []
    for radio_anillo in (12.5, 16.0):
        for grados in range(0, 360, 20):
            a = math.radians(grados + (10 if radio_anillo > 14 else 0))
            arbol = Obstaculo("arbol", round(cx + radio_anillo * math.cos(a), 3),
                              round(cz + radio_anillo * math.sin(a), 3), radio=0.6)
            if despeje.permite(arbol):
                arboles.append(arbol)
    return arboles


def _farolas(mapa, despeje):
    """Farolas a lo largo de cada calle, alternando lados, a 0.8 m del borde del asfalto."""
    farolas = []
    desfase = mapa.ancho_calle / 2 + 0.8
    margen = mapa.radio_plaza + 3
    for a, b in mapa.segmentos():
        (ax, az), (bx, bz) = mapa.coordenada(a), mapa.coordenada(b)
        largo = math.dist((ax, az), (bx, bz))
        if largo < 1e-9:
            continue  # lugares superpuestos: calle sin dirección, sin farolas
        ux, uz = (bx - ax) / largo, (bz - az) / largo
        lado = 1
        s = margen
        while s <= largo - margen:
            farola = Obstaculo("farola", round(ax + ux * s - uz * lado * desfase, 3),
                               round(az + uz * s + ux * lado * desfase, 3), radio=0.2)
            if despeje.permite(farola):
                farolas.append(farola)
            lado = -lado
            s += 8
    return farolas


# -- Escaleras -------------------------------------------------------------------------------------


def _escaleras(mapa, edificios, obstaculos, terreno):
    """Escaleras que salen de la acera, perpendiculares a la calle, hacia la ladera.

    Para cada lado de cada calle se prueban arranques en el tramo libre (entre plazas) y se
    queda la que más sube o baja, si salva al menos DESNIVEL_ESCALERA m. Una escalera no puede
    acercarse a plazas, otras calles, edificios, caminos plaza -> puerta ni obstáculos, ni salir
    de la ladera. Se calculan ANTES de las casas: _Despeje las suma a sus líneas libres, así las
    casas les dejan paso y cada escalera queda como un callejón.
    """
    calles = [(a, b, mapa.coordenada(a), mapa.coordenada(b)) for a, b in mapa.segmentos()]
    plazas = [mapa.coordenada(lugar) for lugar in mapa.lugares()]
    accesos = [(mapa.coordenada(e.lugar), e.puerta()) for e in edificios]
    cajas = [e.caja() for e in edificios]
    x0, x1, z0, z1 = terreno.extension
    arranque = mapa.ancho_calle / 2 + 2.0           # borde exterior de la acera
    escaleras = []
    for a, b, pa, pb in calles:
        largo = math.dist(pa, pb)
        ux, uz = (pb[0] - pa[0]) / largo, (pb[1] - pa[1]) / largo
        for lado in (-1, 1):
            nx, nz = -uz * lado, ux * lado
            mejor = None
            for t in (0.4, 0.5, 0.6):
                s = largo * t
                ax, az = pa[0] + ux * s + nx * arranque, pa[1] + uz * s + nz * arranque
                bx, bz = ax + nx * LARGO_ESCALERA, az + nz * LARGO_ESCALERA
                if not (x0 + BORDE_LADERA <= bx <= x1 - BORDE_LADERA and z0 + BORDE_LADERA <= bz <= z1 - BORDE_LADERA):
                    continue
                escalera = Escalera(round(ax, 2), round(az, 2), round(bx, 2), round(bz, 2), ANCHO_ESCALERA)
                desnivel = abs(terreno.altura(bx, bz) - terreno.altura(ax, az))
                if desnivel < DESNIVEL_ESCALERA or (mejor and desnivel <= mejor[0]):
                    continue
                if _escalera_libre(escalera, mapa, (a, b), calles, plazas, accesos, cajas, obstaculos, escaleras):
                    mejor = (desnivel, escalera)
            if mejor:
                escaleras.append(mejor[1])
    return escaleras


def _escalera_libre(escalera, mapa, propia, calles, plazas, accesos, cajas, obstaculos, otras):
    a, b = (escalera.ax, escalera.az), (escalera.bx, escalera.bz)
    holgura = escalera.ancho / 2 + 1.0
    if any(_distancia_punto_segmento(p, a, b) < mapa.radio_plaza + 0.9 + holgura for p in plazas):
        return False
    for ca, cb, pa, pb in calles:
        if (ca, cb) != propia and _distancia_entre_segmentos(a, b, pa, pb) < mapa.ancho_calle / 2 + 2.0 + holgura:
            return False
    if any(_distancia_entre_segmentos(a, b, p, q) < holgura + ESPACIO_LIBRE for p, q in accesos):
        return False
    if any(_distancia_segmento_caja(a, b, caja) < holgura for caja in cajas):
        return False
    if any(_distancia_a_segmento(o, a, b) < holgura for o in obstaculos):
        return False
    return all(_distancia_entre_segmentos(a, b, (e.ax, e.az), (e.bx, e.bz)) >= 2 * holgura for e in otras)


# Distancia mínima entre los segmentos p1-p2 y q1-q2 (0 si se cortan).
def _distancia_entre_segmentos(p1, p2, q1, q2):
    def orientacion(a, b, c):
        return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])

    d1, d2 = orientacion(q1, q2, p1), orientacion(q1, q2, p2)
    d3, d4 = orientacion(p1, p2, q1), orientacion(p1, p2, q2)
    if d1 * d2 < 0 and d3 * d4 < 0:
        return 0.0
    return min(_distancia_punto_segmento(p1, q1, q2), _distancia_punto_segmento(p2, q1, q2),
               _distancia_punto_segmento(q1, p1, p2), _distancia_punto_segmento(q2, p1, p2))


# -- Favela ---------------------------------------------------------------------------------------


def _casas_favela(mapa, despeje, obstaculos, terreno, cantidad=CANTIDAD_CASAS, semilla=SEMILLA_CASAS):
    """Hasta `cantidad` casas decorativas sobre la ladera, por reglas y con azar fijo.

    Pase greedy sobre una grilla de candidatos (cada PASO_CANDIDATOS m, con un poco de ruido),
    de más cerca a más lejos de la red de calles: así la favela se apiña junto a las calles y se
    ralea hacia el borde. Una casa entra si:
      - no pisa ninguna plaza (aro + DESPEJE_PLAZA) ni calle (asfalto + DESPEJE_CALLE);
      - cumple _Despeje (ejes de calle, caminos plaza -> puerta, spawns y edificios);
      - deja un callejón de CALLEJON m con las otras casas y con árboles, farolas y bancos;
      - el suelo bajo su huella no varía más de DESNIVEL_LOTE m.
    Mira hacia la calle o plaza más cercana (rumbo múltiplo de 90).
    """
    azar = random.Random(semilla)
    calles = [(mapa.coordenada(a), mapa.coordenada(b)) for a, b in mapa.segmentos()]
    plazas = [mapa.coordenada(lugar) for lugar in mapa.lugares()]
    radio_plaza = mapa.radio_plaza + 0.9 + DESPEJE_PLAZA
    semiancho_calle = mapa.ancho_calle / 2 + DESPEJE_CALLE
    modelos = sorted(MODELOS)

    x0, x1, z0, z1 = terreno.extension
    candidatos = []
    x = x0 + BORDE_LADERA
    while x <= x1 - BORDE_LADERA:
        z = z0 + BORDE_LADERA
        while z <= z1 - BORDE_LADERA:
            px, pz = x + azar.uniform(-0.6, 0.6), z + azar.uniform(-0.6, 0.6)
            candidatos.append((_distancia_a_la_red(px, pz, calles, plazas) + azar.uniform(0, 8), px, pz))
            z += PASO_CANDIDATOS
        x += PASO_CANDIDATOS
    candidatos.sort()

    celda = 12.0                     # grilla espacial para buscar vecinos sin recorrer todo
    vecinos = {}

    def cercanos(cx, cz):
        i, j = int(cx // celda), int(cz // celda)
        return [o for di in (-1, 0, 1) for dj in (-1, 0, 1) for o in vecinos.get((i + di, j + dj), ())]

    def ocupar(o):
        vecinos.setdefault((int(o.cx // celda), int(o.cz // celda)), []).append(o)

    for o in obstaculos:
        ocupar(o)
    casas = []
    for _, px, pz in candidatos:
        if len(casas) >= cantidad:
            break
        casa = casa_decorativa(azar.choice(modelos), round(px, 2), round(pz, 2),
                               rumbo=_rumbo_hacia_la_red(px, pz, calles, plazas),
                               escala=round(azar.uniform(*ESCALAS_CASA), 2), variante=azar.randrange(4),
                               pisos=azar.choice(PISOS_CASA))
        caja = _caja(casa)
        if any(_distancia_punto_caja(cx, cz, caja) < radio_plaza for cx, cz in plazas):
            continue
        if any(_distancia_segmento_caja(a, b, caja) < semiancho_calle for a, b in calles):
            continue
        if not despeje.permite(casa):
            continue
        if any(_separacion_con_edificio(o, casa) < CALLEJON for o in cercanos(casa.cx, casa.cz)):
            continue
        esquinas = [(casa.cx + sx * casa.ancho / 2, casa.cz + sz * casa.fondo / 2) for sx in (-1, 1) for sz in (-1, 1)]
        alturas = [terreno.altura(x, z) for x, z in esquinas + [(casa.cx, casa.cz)]]
        if max(alturas) - min(alturas) > DESNIVEL_LOTE:
            continue
        casas.append(casa)
        ocupar(casa)
    return casas


def _distancia_a_la_red(x, z, calles, plazas):
    return min(min(_distancia_punto_segmento((x, z), a, b) for a, b in calles),
               min(math.dist((x, z), p) for p in plazas))


# Rumbo (múltiplo de 90) que mira desde (x, z) hacia el punto más cercano de la red de calles.
def _rumbo_hacia_la_red(x, z, calles, plazas):
    puntos = list(plazas) + [_punto_mas_cercano((x, z), a, b) for a, b in calles]
    px, pz = min(puntos, key=lambda p: math.dist((x, z), p))
    rumbo = math.degrees(math.atan2(px - x, pz - z))          # adelante = (sin ψ, cos ψ)
    return (round(rumbo / 90) * 90) % 360


def _punto_mas_cercano(p, a, b):
    dx, dz = b[0] - a[0], b[1] - a[1]
    largo2 = dx * dx + dz * dz
    t = 0.0 if largo2 < 1e-12 else min(1.0, max(0.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dz) / largo2))
    return (a[0] + dx * t, a[1] + dz * t)


# -- Vegetación de la ladera -----------------------------------------------------------------------


def _vegetacion(mapa, despeje, ocupados, terreno, cantidad=CANTIDAD_VEGETACION, semilla=SEMILLA_CASAS + 1):
    """Árboles y arbustos sueltos en el pasto que dejó la favela, con las mismas reglas que las
    casas (fuera de plazas, calles, caminos y escaleras) y SEPARACION_VEGETACION m de todo lo demás."""
    azar = random.Random(semilla)
    calles = [(mapa.coordenada(a), mapa.coordenada(b)) for a, b in mapa.segmentos()]
    plazas = [mapa.coordenada(lugar) for lugar in mapa.lugares()]
    x0, x1, z0, z1 = terreno.extension
    plantas = []
    for _ in range(cantidad * 40):
        if len(plantas) >= cantidad:
            break
        x = round(azar.uniform(x0 + BORDE_LADERA, x1 - BORDE_LADERA), 2)
        z = round(azar.uniform(z0 + BORDE_LADERA, z1 - BORDE_LADERA), 2)
        planta = Obstaculo("arbol", x, z, radio=0.6) if azar.random() < 0.45 else Obstaculo("arbusto", x, z, radio=0.45)
        if any(math.dist((x, z), p) < mapa.radio_plaza + 0.9 + 1.0 + planta.radio for p in plazas):
            continue
        if any(_distancia_punto_segmento((x, z), a, b) < mapa.ancho_calle / 2 + 2.0 + 0.5 + planta.radio
               for a, b in calles):
            continue
        if not despeje.permite(planta):
            continue
        if any(_separacion(planta, o) < SEPARACION_VEGETACION for o in ocupados + plantas):
            continue
        plantas.append(planta)
    return plantas


# -- Fábrica ------------------------------------------------------------------------------------------


# ladera=False: el mundo plano de antes (y = 0 en todas partes, sin casas decorativas).
# casas: cuántas casas decorativas generar en la ladera (0 = ninguna).
def construir_mundo_3d(ladera=True, casas=CANTIDAD_CASAS):
    mapa = _construir_mapa()
    edificios = _construir_edificios()
    spawns = _spawns()
    despeje = _Despeje(mapa, edificios, spawns)
    obstaculos = _bancos(mapa, despeje) + _arboles_parque(mapa, despeje) + _farolas(mapa, despeje)
    plano = MundoCiudad(mapa, edificios, obstaculos, spawns=spawns, margen_edificios=MARGEN_EDIFICIOS)
    if not ladera:
        return plano
    # La ladera necesita los límites del mundo; luego cada edificio toma la altura de su plaza.
    terreno = Terreno(mapa, edificios, plano.limites())
    edificios = [replace(e, y=round(terreno.altura_plaza(e.lugar), 3)) for e in edificios]
    escaleras = _escaleras(mapa, edificios, obstaculos, terreno)
    for e in escaleras:
        despeje.agregar_linea((e.ax, e.az), (e.bx, e.bz))
    obstaculos = obstaculos + _casas_favela(mapa, despeje, obstaculos, terreno, cantidad=casas)
    obstaculos = obstaculos + _vegetacion(mapa, despeje, obstaculos, terreno)
    return MundoCiudad(mapa, edificios, obstaculos, spawns=spawns, margen_edificios=MARGEN_EDIFICIOS,
                       terreno=terreno, escaleras=escaleras)
