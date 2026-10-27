# Multitud del mapa grande (Python puro: NO importa ursina ni panda3d). Circuitos CÍCLICOS de peatones sobre el grafo
# de calles y becos del mundo grande, y la posición ANALÍTICA de cada agente en cada instante.
#
#   construir_grafo(mundo)                      grafo peatonal: lugares (plazas), cruces calle-beco y vértices de becos.
#   crear_poblacion(mundo, cantidad, semilla)   Poblacion(rutas, agentes): rutas validadas contra mundo.es_transitable.
#   posicion_en(t, ruta, semilla)               (x, z, rumbo, velocidad, en_movimiento, distancia): SIN ESTADO.
#   asignar_niveles(distancias, previos, ...)   niveles A (actor animado), B (figura sin esqueleto), C (solo simulado).
#   factor_horario(hora) / activo_a_la_hora     horario simple opcional (hora=None: sin horario).
#
# Cada ruta es un camino del grafo recorrido de ida y vuelta (un circuito cerrado): al final del camino el agente se para,
# cruza al otro lado de la calle y regresa; en las plazas intermedias hace paradas. Todo es función de (t, ruta, semilla):
# no hay estado, así que dos procesos o dos equipos que lean el mismo reloj ven al agente en el mismo sitio sin hablarse.
# `t` es el reloj compartido (segundos, p. ej. time.time()); la semilla del agente fija su velocidad, fase, lado de la calle
# y factor de paradas. Los agentes van por el eje de la calle con un desvío lateral (como peatones_calculos.Caminante),
# 1,6 m en calles de 8 m y 0,6 m en becos de 2,5 a 3,5 m; cada ruta se valida con es_transitable (casas, árboles, farolas,
# taludes sin escalera) en los extremos de ese desvío y, si no cabe, se estrecha el desvío o se descarta la ruta.
# Es determinista: mismo mundo y misma semilla -> mismas rutas y agentes (sin set/dict de strings en el orden).

import bisect
import math
import random

from backend.logica import escaleras_calculos as esc

POBLACION = 180                 # agentes simulados (la mayoría, solo posición: nivel C)
SEMILLA_MULTITUD = 2026
VARIANTES = 8                   # aspectos distintos (cada agente usa uno; el frontend crea un modelo por aspecto)
HOLGURA_CALLE = 1.6             # m a un lado del eje (el asfalto mide 8 m)
HOLGURA_BECO = 0.6              # m (un beco mide de 2,5 a 3,5 m y los muros dejan 1 m a cada lado del eje)
VELOCIDAD_MIN, VELOCIDAD_MAX = 1.0, 1.55      # m/s
LADO_PARTE_PAUSA = (0.2, 0.8)   # fracción de la parada de un extremo en la que cruzan al otro lado de la calle
PAUSA_EXTREMO = (7.0, 14.0)     # s parado al final del camino (cruza al otro lado y vuelve)
PAUSA_PLAZA = (3.0, 9.0)        # s en una plaza intermedia
PROBABILIDAD_PAUSA_PLAZA = 0.7
PAUSA_GIRO_BRUSCO = 5.0         # s mínimos si el camino da un giro de más de ~145 grados
LARGO_RUTA = (30.0, 150.0)      # m del camino (ida; el circuito mide el doble)
LARGO_MINIMO = 20.0
PASO_VALIDACION = 0.6           # m / s entre muestras al validar una ruta
RADIO_MAXIMO_CRUCE = 12.0       # m: distancia máxima de la entrada de un beco al eje de su calle

# Peso (densidad relativa) de cada lugar como origen de rutas: más gente en plazas, mercado, feria y estaciones.
PESO_LUGAR = {
    "Praça da Sé": 6.0, "Mercado Municipal": 5.0, "Feira da Ladeira": 5.0, "Estação do Teleférico": 4.0,
    "Estação Alto do Morro": 3.5, "Rodoviária": 4.0, "Parque do Povo": 4.0, "Escola de Samba": 3.0,
    "Supermercado Dois Irmãos": 3.0, "Padaria Pão Quente": 3.0, "Igreja Nossa Senhora da Esperança": 3.0,
    "Escola Municipal Paulo Freire": 3.0, "Campo de Várzea": 3.0, "Ponto de Mototáxi da Entrada": 2.5,
    "Hospital Santa Casa": 2.0, "Mirante do Alto": 1.5, "Morro da Esperança": 1.5, "Prefeitura": 2.5,
    "Universidade de Ciudad Nova": 2.0, "Rádio Comunitária": 2.0,
}
PESO_LUGAR_DEFECTO = 3.0
PESO_CRUCE_BECO = 0.04          # entrada de un beco en la calle
PESO_BECO_BASE = 0.12           # primer vértice de un beco a la altura de su calle
SUBIDA_BECO = 6.0               # m de subida sobre la calle que dividen a la mitad el peso (becos altos: menos gente)
EXPONENTE_PESO = 0.6            # suaviza el sesgo al elegir el siguiente nodo del camino

# Niveles de la multitud (ver frontend/multitud.py).
NIVEL_C, NIVEL_B, NIVEL_A = 0, 1, 2
RADIO_A, HISTERESIS_A = 25.0, 4.0
RADIO_B, HISTERESIS_B = 90.0, 8.0
MAXIMO_A, MAXIMO_B = 8, 32

_MASCARA = (1 << 64) - 1


def _u(semilla, k):
    """Número en [0, 1) determinista por (semilla, k) (mezcla tipo splitmix64; no usa hash() ni random)."""
    x = (semilla * 0x9E3779B97F4A7C15 + (k + 1) * 0xBF58476D1CE4E5B9) & _MASCARA
    x ^= x >> 30
    x = (x * 0xBF58476D1CE4E5B9) & _MASCARA
    x ^= x >> 27
    x = (x * 0x94D049BB133111EB) & _MASCARA
    x ^= x >> 31
    return (x >> 11) / float(1 << 53)


def _izquierda(ux, uz):
    return (-uz, ux)


def _rumbo(dx, dz):
    return math.degrees(math.atan2(dx, dz))


# -- Grafo peatonal -----------------------------------------------------------------------------------------------------


class Grafo:
    """Nodos con coordenadas, peso de densidad y si son plaza; aristas (vecino, holgura) en orden de creación."""

    def __init__(self):
        self.puntos, self.pesos, self.plaza, self.nombres, self.ady = [], [], [], [], []

    def nodo(self, x, z, peso, plaza=False, nombre=""):
        self.puntos.append((float(x), float(z)))
        self.pesos.append(float(peso))
        self.plaza.append(bool(plaza))
        self.nombres.append(nombre)
        self.ady.append([])
        return len(self.puntos) - 1

    def arista(self, i, j, holgura):
        self.ady[i].append((j, holgura))
        self.ady[j].append((i, holgura))


def _proyectar(p, a, b):
    dx, dz = b[0] - a[0], b[1] - a[1]
    l2 = dx * dx + dz * dz
    t = 0.0 if l2 < 1e-12 else min(1.0, max(0.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dz) / l2))
    q = (a[0] + dx * t, a[1] + dz * t)
    return math.hypot(p[0] - q[0], p[1] - q[1]), t, q


def construir_grafo(mundo):
    """Grafo de las calles (eje a eje de cada plaza) y los becos de `mundo`. Cada beco entra en su calle por un nodo de
    cruce (el punto del eje más cercano a su primer vértice); los becos más altos pesan menos."""
    graf = Grafo()
    lugar_nodo = {}
    for lugar in mundo.lugares():
        x, z = mundo.coordenada(lugar)
        lugar_nodo[lugar] = graf.nodo(x, z, PESO_LUGAR.get(lugar, PESO_LUGAR_DEFECTO), True, lugar)
    segmentos = [(lugar_nodo[a], lugar_nodo[b]) for a, b in mundo.mapa.segmentos()]
    cruces = [[] for _ in segmentos]                       # por segmento: [(t, nodo)]
    becos = list(mundo.becos()) if hasattr(mundo, "becos") else []
    for beco in becos:
        p0 = beco.puntos[0]
        mejor = None
        for s, (na, nb) in enumerate(segmentos):
            d, t, q = _proyectar(p0, graf.puntos[na], graf.puntos[nb])
            if mejor is None or d < mejor[0]:
                mejor = (d, s, t, q)
        if mejor is None or mejor[0] > RADIO_MAXIMO_CRUCE:
            continue
        _, s, t, q = mejor
        cruce = graf.nodo(q[0], q[1], PESO_CRUCE_BECO)
        cruces[s].append((t, cruce))
        h0 = mundo.altura(*q)
        previo = cruce
        for p in beco.puntos:
            sube = max(0.0, mundo.altura(*p) - h0)
            nodo = graf.nodo(p[0], p[1], PESO_BECO_BASE / (1.0 + sube / SUBIDA_BECO))
            graf.arista(previo, nodo, HOLGURA_BECO)
            previo = nodo
    for (na, nb), lista in zip(segmentos, cruces):
        previo = na
        for _, nodo in sorted(lista):
            graf.arista(previo, nodo, HOLGURA_CALLE)
            previo = nodo
        graf.arista(previo, nb, HOLGURA_CALLE)
    return graf


# -- Rutas --------------------------------------------------------------------------------------------------------------


class Ruta:
    """Circuito cerrado de 2n vértices: el camino de n tramos de ida y los mismos de vuelta. Por vértice k:
    `eje` (x, z), `n_ent` y `n_sal` (desvío lateral al llegar y al salir, ya con holgura y esquina) y `pausa` (s).
    `dist[k]` y `pausas[k]` son las sumas acumuladas (distancia y pausas antes del vértice k); `largos[k]`, el tramo k -> k+1."""

    __slots__ = ("clave", "eje", "n_ent", "n_sal", "pausa", "largos", "dir_ent", "dir_sal", "dist", "pausas",
                 "total_dist", "total_pausas", "escala", "origen", "_parametros")

    def __init__(self, clave, nodos_xz, holguras, pausas_ida, pausas_vuelta, origen=""):
        self.clave = clave
        self.origen = origen
        self.escala = 1.0
        self._parametros = {}
        n = len(nodos_xz) - 1
        m = 2 * n
        indice = [k if k <= n else m - k for k in range(m)]
        self.eje = tuple(nodos_xz[i] for i in indice)
        hol_nodo = []
        for i in range(n + 1):
            vecinas = ([holguras[i - 1]] if i > 0 else []) + ([holguras[i]] if i < n else [])
            hol_nodo.append(min(vecinas))
        self.largos = tuple(math.dist(self.eje[k], self.eje[(k + 1) % m]) for k in range(m))
        dirs = tuple(((self.eje[(k + 1) % m][0] - self.eje[k][0]) / self.largos[k],
                      (self.eje[(k + 1) % m][1] - self.eje[k][1]) / self.largos[k]) for k in range(m))
        self.dir_sal = dirs
        self.dir_ent = tuple(dirs[k - 1] for k in range(m))
        pausa = [0.0] * m
        for k in range(m):
            pausa[k] = pausas_ida[k] if k <= n else pausas_vuelta[m - k]
        n_ent, n_sal = [], []
        for k in range(m):
            h = hol_nodo[indice[k]]
            l1, l2 = _izquierda(*self.dir_ent[k]), _izquierda(*self.dir_sal[k])
            sx, sz = l1[0] + l2[0], l1[1] + l2[1]
            largo = math.hypot(sx, sz)
            if largo < 0.3:                                 # giro casi de vuelta: cada lado con su normal, y para
                n_ent.append((l1[0] * h, l1[1] * h))
                n_sal.append((l2[0] * h, l2[1] * h))
                pausa[k] = max(pausa[k], PAUSA_GIRO_BRUSCO + (3.0 if k in (0, n) else 0.0))
            else:
                mx, mz = sx / largo, sz / largo
                escala = min(2.0, 1.0 / max(0.5, mx * l1[0] + mz * l1[1]))
                n_ent.append((mx * h * escala, mz * h * escala))
                n_sal.append(n_ent[-1])
        self.n_ent, self.n_sal, self.pausa = tuple(n_ent), tuple(n_sal), tuple(pausa)
        d, p = [0.0], [0.0]
        for k in range(m):
            d.append(d[-1] + self.largos[k])
            p.append(p[-1] + pausa[k])
        self.dist, self.pausas = tuple(d), tuple(p)
        self.total_dist, self.total_pausas = d[-1], p[-1]

    def vertices(self):
        return len(self.eje)


def _parametros(ruta, semilla):
    """(velocidad m/s, factor de pausas, fase 0..1, desvío relativo 0.15..1) del agente `semilla` en `ruta`."""
    p = ruta._parametros.get(semilla)
    if p is None:
        p = (VELOCIDAD_MIN + (VELOCIDAD_MAX - VELOCIDAD_MIN) * _u(semilla, 0), 0.7 + 0.6 * _u(semilla, 1),
             _u(semilla, 2), 0.15 + 0.85 * _u(semilla, 3))
        ruta._parametros[semilla] = p
    return p


def duracion_ciclo(ruta, semilla):
    """Segundos que tarda el agente en dar una vuelta completa al circuito."""
    v, f, _, _ = _parametros(ruta, semilla)
    return ruta.total_dist / v + f * ruta.total_pausas


def _suave(x):
    x = 0.0 if x < 0.0 else 1.0 if x > 1.0 else x
    return x * x * (3.0 - 2.0 * x)


def _evaluar(ruta, u, v, f, d):
    """Estado en el instante `u` (s, ya dentro del ciclo) de un agente de velocidad `v`, factor de pausas `f` y desvío
    relativo `d`. (x, z, rumbo, velocidad, en_movimiento, distancia recorrida del circuito)."""
    dist, pausas = ruta.dist, ruta.pausas
    m = len(ruta.eje)
    k = bisect.bisect_right(range(m), u, key=lambda i: dist[i] / v + f * pausas[i]) - 1
    if k < 0:
        k = 0
    k_sig = k + 1 if k + 1 < m else 0
    inicio = dist[k] / v + f * pausas[k]
    espera = u - inicio
    duracion = f * ruta.pausa[k]
    esc = ruta.escala * d
    ax, az = ruta.eje[k]
    if espera < duracion:                                   # parado en el vértice (y quizá cruzando al otro lado)
        ni, ns = ruta.n_ent[k], ruta.n_sal[k]
        di, ds = ruta.dir_ent[k], ruta.dir_sal[k]
        if ni == ns:
            return (ax + ni[0] * esc, az + ni[1] * esc, _rumbo(*di), 0.0, False, dist[k])
        s = espera / duracion
        a, b = LADO_PARTE_PAUSA
        if s < a:
            return (ax + ni[0] * esc, az + ni[1] * esc, _rumbo(*di), 0.0, False, dist[k])
        if s >= b:
            return (ax + ns[0] * esc, az + ns[1] * esc, _rumbo(*ds), 0.0, False, dist[k])
        w = _suave((s - a) / (b - a))
        dx, dz = (ns[0] - ni[0]) * esc, (ns[1] - ni[1]) * esc
        vel = math.hypot(dx, dz) / (duracion * (b - a)) * 1.5
        return (ax + ni[0] * esc + dx * w, az + ni[1] * esc + dz * w, _rumbo(dx, dz), vel, True, dist[k])
    largo = ruta.largos[k]
    frac = (espera - duracion) * v / largo
    frac = 0.0 if frac < 0.0 else 1.0 if frac > 1.0 else frac
    bx, bz = ruta.eje[k_sig]
    ns, ne = ruta.n_sal[k], ruta.n_ent[k_sig]
    x0, z0 = ax + ns[0] * esc, az + ns[1] * esc
    x1, z1 = bx + ne[0] * esc, bz + ne[1] * esc
    dx, dz = ruta.dir_sal[k]
    return (x0 + (x1 - x0) * frac, z0 + (z1 - z0) * frac, _rumbo(dx, dz), v, True, dist[k] + frac * largo)


def posicion_en(t, ruta, semilla):
    """Posición del agente `semilla` en `ruta` en el instante `t` (s del reloj compartido): (x, z, rumbo en grados,
    velocidad m/s, en_movimiento, distancia recorrida en el circuito). Sin estado: misma entrada, misma salida."""
    v, f, fase, d = _parametros(ruta, semilla)
    ciclo = ruta.total_dist / v + f * ruta.total_pausas
    return _evaluar(ruta, (t + fase * ciclo) % ciclo, v, f, d)


def muestras_de_ruta(ruta, desvios=(0.15, 1.0), paso=PASO_VALIDACION):
    """[(x, z)] a lo largo de todo el circuito (incluido el cruce de los extremos) con cada desvío relativo de `desvios`."""
    ciclo = ruta.total_dist + ruta.total_pausas
    n = int(ciclo / paso) + 1
    return [_evaluar(ruta, ciclo * i / n, 1.0, 1.0, d)[:2] for d in desvios for i in range(n)]


def ruta_transitable(ruta, es_transitable):
    return all(es_transitable(x, z) for x, z in muestras_de_ruta(ruta))


# -- Población ----------------------------------------------------------------------------------------------------------


class Agente:
    __slots__ = ("indice", "ruta", "semilla", "variante", "umbral")

    def __init__(self, indice, ruta, semilla, variante, umbral):
        self.indice, self.ruta, self.semilla, self.variante, self.umbral = indice, ruta, semilla, variante, umbral


class Poblacion:
    def __init__(self, grafo, rutas, agentes):
        self.grafo, self.rutas, self.agentes = grafo, rutas, agentes


def _caminata(graf, inicio, azar, objetivo):
    camino, holguras, total, previo, actual = [inicio], [], 0.0, None, inicio
    while total < objetivo and len(camino) < 10:
        opciones = [(j, h) for j, h in graf.ady[actual] if j != previo and j not in camino]
        if not opciones:
            break
        pesos = [graf.pesos[j] ** EXPONENTE_PESO + 0.05 for j, _ in opciones]
        j, h = azar.choices(opciones, weights=pesos)[0]
        total += math.dist(graf.puntos[actual], graf.puntos[j])
        camino.append(j)
        holguras.append(h)
        previo, actual = actual, j
    return camino, holguras, total


def _pausas(graf, camino, azar):
    n = len(camino) - 1
    ida = [0.0] * (n + 1)
    for i, nodo in enumerate(camino):
        if i in (0, n):
            ida[i] = azar.uniform(*PAUSA_EXTREMO)
        elif graf.plaza[nodo] and azar.random() < PROBABILIDAD_PAUSA_PLAZA:
            ida[i] = azar.uniform(*PAUSA_PLAZA)
    vuelta = list(ida)
    for i, nodo in enumerate(camino):
        if 0 < i < n and graf.plaza[nodo]:
            vuelta[i] = azar.uniform(*PAUSA_PLAZA) if azar.random() < PROBABILIDAD_PAUSA_PLAZA else 0.0
    return ida, vuelta


def _ajustar_holgura(ruta, es_transitable):
    """Estrecha el desvío de la ruta hasta que todo el circuito sea transitable; False si ni sin desvío cabe."""
    for escala in (1.0, 0.6, 0.3, 0.0):
        ruta.escala = escala
        if ruta_transitable(ruta, es_transitable):
            return True
    return False


def _agentes_para(peso_inicio, azar):
    return 1 + (peso_inicio >= 2.0) + (peso_inicio >= 3.5) + azar.randint(0, 1)


def crear_poblacion(mundo, cantidad=POBLACION, semilla=SEMILLA_MULTITUD, validar=True, grafo=None):
    """Población de `cantidad` agentes en rutas del grafo del `mundo` (determinista por mundo y semilla). Con `validar`
    cada ruta se comprueba contra mundo.es_transitable. Los agentes de una misma ruta tienen variantes distintas
    consecutivas (que dos vecinos no vistan igual)."""
    azar = random.Random(semilla)
    graf = grafo if grafo is not None else construir_grafo(mundo)
    nodos = list(range(len(graf.puntos)))
    pesos = [graf.pesos[i] for i in nodos]
    rutas, agentes, intentos, descartadas = [], [], 0, 0
    while len(agentes) < cantidad and intentos < cantidad * 40:
        intentos += 1
        inicio = azar.choices(nodos, weights=pesos)[0]
        camino, holguras, total = _caminata(graf, inicio, azar, azar.uniform(*LARGO_RUTA))
        if len(camino) < 2 or total < LARGO_MINIMO:
            continue
        ida, vuelta = _pausas(graf, camino, azar)
        ruta = Ruta(len(rutas), [graf.puntos[i] for i in camino], holguras, ida, vuelta, graf.nombres[inicio])
        if validar and not _ajustar_holgura(ruta, mundo.es_transitable):
            descartadas += 1
            continue
        rutas.append(ruta)
        base = azar.randrange(VARIANTES)
        for slot in range(min(_agentes_para(graf.pesos[inicio], azar), cantidad - len(agentes))):
            sem = azar.getrandbits(48)
            agentes.append(Agente(len(agentes), ruta, sem, (base + slot * 3) % VARIANTES, _u(sem, 9)))
    poblacion = Poblacion(graf, rutas, agentes)
    poblacion.descartadas = descartadas
    return poblacion


# -- Niveles ------------------------------------------------------------------------------------------------------------


def asignar_niveles(distancias, previos=None, maximo_a=MAXIMO_A, maximo_b=MAXIMO_B, radio_a=RADIO_A, radio_b=RADIO_B,
                    histeresis_a=HISTERESIS_A, histeresis_b=HISTERESIS_B, activos=None):
    """Nivel de cada agente según su distancia (m) a la cámara: A (actor animado, hasta `maximo_a` a menos de `radio_a`),
    B (figura sin esqueleto, hasta `maximo_b` a menos de `radio_b`) y C (solo simulado). Los más cercanos mandan; el
    que ya tenía un nivel lo conserva `histeresis_*` m más allá del radio (sin parpadeo en el borde). `activos` (lista de
    bool, opcional) deja en C a los que no están activos por el horario."""
    n = len(distancias)
    niveles = [NIVEL_C] * n
    previos = previos if previos is not None else niveles
    candidatos = [i for i in range(n) if distancias[i] < radio_b + histeresis_b and (activos is None or activos[i])]
    candidatos.sort(key=distancias.__getitem__)
    na = nb = 0
    for i in candidatos:
        d, antes = distancias[i], previos[i]
        if na < maximo_a and d < radio_a + (histeresis_a if antes == NIVEL_A else 0.0):
            niveles[i] = NIVEL_A
            na += 1
        elif nb < maximo_b and d < radio_b + (histeresis_b if antes >= NIVEL_B else 0.0):
            niveles[i] = NIVEL_B
            nb += 1
    return niveles


class Asignador:
    """Reparte los recursos de dibujo (actores animados de nivel A y figuras de nivel B, ambos en piscinas FIJAS por
    variante) entre los agentes según su distancia. No crea ni destruye nada: solo presta y devuelve recursos, así que
    el frontend reutiliza las mismas instancias siempre. `actualizar` devuelve los eventos a aplicar:
    (agente, nivel_antes, recurso_antes, nivel_nuevo, recurso_nuevo) con recurso None en el nivel C.

    El A de una variante sale de su propia piscina (el aspecto de un agente no cambia al pasar de B a A) y, si no hay uno
    libre, el agente se queda en B. Los cambios A <-> B de un agente que se VE (`en_vista(i)`) se aplazan mientras no sean
    obligados (franja de 6 m junto al radio), para que el intercambio ocurra fuera de la vista."""

    def __init__(self, agentes, actores_por_variante=2, figuras_por_variante=12, maximo_a=MAXIMO_A, maximo_b=MAXIMO_B):
        self.agentes = agentes
        self.actores_por_variante, self.figuras_por_variante = actores_por_variante, figuras_por_variante
        self.maximo_a, self.maximo_b = maximo_a, maximo_b
        self.nivel = [NIVEL_C] * len(agentes)
        self.recurso = [None] * len(agentes)
        self._libres_a = [list(range((v + 1) * actores_por_variante - 1, v * actores_por_variante - 1, -1))
                          for v in range(VARIANTES)]
        self._libres_b = [list(range((v + 1) * figuras_por_variante - 1, v * figuras_por_variante - 1, -1))
                          for v in range(VARIANTES)]
        self.usados_a = self.usados_b = 0

    def total_a(self):
        return VARIANTES * self.actores_por_variante

    def total_b(self):
        return VARIANTES * self.figuras_por_variante

    def _tomar(self, nivel, variante):
        libres = (self._libres_a if nivel == NIVEL_A else self._libres_b)[variante]
        if not libres:
            return None
        if nivel == NIVEL_A:
            if self.usados_a >= self.maximo_a:
                return None
            self.usados_a += 1
        else:
            if self.usados_b >= self.maximo_b:
                return None
            self.usados_b += 1
        return libres.pop()

    def _devolver(self, nivel, variante, recurso):
        if nivel == NIVEL_A:
            self._libres_a[variante].append(recurso)
            self.usados_a -= 1
        elif nivel == NIVEL_B:
            self._libres_b[variante].append(recurso)
            self.usados_b -= 1

    def actualizar(self, distancias, activos=None, en_vista=None, max_promociones=12):
        deseado = asignar_niveles(distancias, self.nivel, activos=activos, maximo_a=self.maximo_a,
                                  maximo_b=self.maximo_b)
        eventos = []
        n = len(self.agentes)
        for i in range(n):                                      # bajar de nivel (siempre libera recursos)
            antes, quiere = self.nivel[i], deseado[i]
            if quiere >= antes:
                continue
            variante, d = self.agentes[i].variante, distancias[i]
            if antes == NIVEL_A and quiere == NIVEL_B and en_vista is not None and d < RADIO_A + HISTERESIS_A + 4.0 \
                    and en_vista(i):
                continue                                        # aplazado: se intercambia cuando salga de la vista
            nuevo = self._tomar(NIVEL_B, variante) if quiere == NIVEL_B else None
            if quiere == NIVEL_B and nuevo is None:
                quiere = NIVEL_C
            eventos.append((i, antes, self.recurso[i], quiere, nuevo))
            self._devolver(antes, variante, self.recurso[i])
            self.nivel[i], self.recurso[i] = quiere, nuevo
        subir = [i for i in range(n) if deseado[i] > self.nivel[i]]
        subir.sort(key=distancias.__getitem__)
        for i in subir[:max_promociones]:
            antes, quiere, variante = self.nivel[i], deseado[i], self.agentes[i].variante
            if quiere == NIVEL_A and antes == NIVEL_B and en_vista is not None and distancias[i] > RADIO_A - 6.0 \
                    and en_vista(i):
                continue
            nuevo = self._tomar(quiere, variante)
            if nuevo is None and quiere == NIVEL_A and antes == NIVEL_C:
                quiere = NIVEL_B
                nuevo = self._tomar(NIVEL_B, variante)
            if nuevo is None:
                continue
            eventos.append((i, antes, self.recurso[i], quiere, nuevo))
            self._devolver(antes, variante, self.recurso[i])
            self.nivel[i], self.recurso[i] = quiere, nuevo
        return eventos


# -- Altura de los pies ---------------------------------------------------------------------------------------------------

CELDA_ESCALERAS = 3.0           # m: celdas de la rejilla que guarda las escaleras cercanas


def indice_escaleras(mundo, celda=CELDA_ESCALERAS):
    """{(i, j): (perfil, ...)}: perfiles de peldaños (en el orden de mundo.perfiles_escaleras()) que tocan cada celda de
    `celda` m (con 1 m de margen). altura_con_escaleras recorre TODAS las escaleras (~175 us en el mapa grande); con este
    índice solo se miran las de la celda. {} si el mundo no tiene peldaños (mundo plano o ESCALERAS_PELDANOS apagado)."""
    if not esc.ESCALERAS_PELDANOS or not mundo.escaleras():
        return {}
    indice = {}
    for perfil in mundo.perfiles_escaleras():
        e = perfil.escalera
        m = e.ancho / 2 + 1.0
        for i in range(math.floor((min(e.ax, e.bx) - m) / celda), math.floor((max(e.ax, e.bx) + m) / celda) + 1):
            for j in range(math.floor((min(e.az, e.bz) - m) / celda), math.floor((max(e.az, e.bz) + m) / celda) + 1):
                indice.setdefault((i, j), []).append(perfil)
    return {k: tuple(v) for k, v in indice.items()}


def altura_pies(mundo, indice, x, z, celda=CELDA_ESCALERAS):
    """Altura que pisa un peatón en (x, z): lo mismo que mundo.altura_con_escaleras pero mirando solo las escaleras de su
    celda (con peldaños sobre las escaleras; la del terreno en el resto)."""
    perfiles = indice.get((math.floor(x / celda), math.floor(z / celda)))
    if perfiles is not None:
        h = esc.altura_sobre_escaleras(perfiles, x, z)
        if h is not None:
            return h
    return mundo.altura(x, z)


# -- Horario ------------------------------------------------------------------------------------------------------------

_HORARIO = ((0.0, 0.25), (5.0, 0.25), (7.0, 0.8), (9.0, 1.0), (18.0, 1.0), (21.0, 0.8), (22.5, 0.45), (24.0, 0.25))


def factor_horario(hora):
    """Fracción (0..1) de la población que está en la calle a la `hora` (0 a 24, reloj de juego). None = toda."""
    if hora is None:
        return 1.0
    hora = hora % 24.0
    for (h0, f0), (h1, f1) in zip(_HORARIO, _HORARIO[1:]):
        if h0 <= hora <= h1:
            return f0 + (f1 - f0) * (hora - h0) / (h1 - h0)
    return 1.0


def activo_a_la_hora(agente, hora):
    """¿Está el agente en la calle a esa hora? Cada uno tiene un umbral fijo: al subir la densidad aparecen, no se barajan."""
    return agente.umbral < factor_horario(hora)
