# Cálculos de los globos de texto de los NPC en PANTALLA (retoques 23-nov, Módulo 3). Python puro (sin ursina ni
# panda3d), con tests en tests/test_globos_pantalla.py. Lo usa frontend/globos_npc.py (CapaGlobos).
#
# Por qué en pantalla: el globo era un Text billboard del MUNDO con prueba de profundidad. Cables, postes y fachadas se
# pintaban encima, la niebla y el pase final lo teñían, de cerca crecía sin tope (pasaba bajo el HUD) y dos globos
# vecinos se mezclaban. Ahora cada globo es UI (camera.ui) colocado sobre la proyección de la cabeza del NPC:
#   - envolver(): el texto se parte en líneas (Text.text no reaplica el wordwrap de Ursina: salía en UNA línea);
#   - alto_linea(): alto de una línea según la distancia, ENTRE un mínimo legible y un tope (fracción del alto de la
#     ventana: igual de legible a 720p que a 1080p);
#   - colocar(): reparte los globos sin que se pisen entre sí ni con el HUD (apila hacia arriba; si no cabe, espera);
#   - IndiceOclusores.tapado(): ¿hay un edificio (o el terreno) entre la cámara y la cabeza? Entonces no hay globo
#     (sin prueba de profundidad, un globo tapado se vería a través de la pared);
#   - EstadoGlobo: un globo por NPC; si cambia el texto, el anterior se apaga en FUNDIDO_CAMBIO s y después entra el
#     nuevo (nunca dos textos superpuestos).

import math

AJUSTE_LINEA = 26                # caracteres por línea (= globos_npc.AJUSTE_LINEA)
MAX_LINEAS = 4                   # la frase más larga (90 caracteres) son 4 líneas

# Alto de UNA línea en unidades de camera.ui (1 = alto de la ventana). 0,026 = 18,7 px a 720p / 28 px a 1080p (las
# letras miden ~0,8 de la línea: ≥ 14 px a 720p y ≥ 18 px a 1080p); el tope, 0,036 = 26 px a 720p.
LINEA_MIN = 0.026
LINEA_MAX = 0.036
DISTANCIA_CERCA = 3.0            # m: a esta distancia o menos, el tope
DISTANCIA_LEJOS = 12.0           # m: a esta distancia o más, el mínimo

RELLENO_X = 0.6                  # en líneas: aire del texto al borde del globo
RELLENO_Y = 0.4
BORDE = 0.1                      # en líneas: grosor del contorno de tinta
COLA = 0.5                       # en líneas: alto de la colita que apunta a la cabeza
HOLGURA = 8 / 1080               # aire entre dos globos (y con el HUD): un paso de 8 px a 1080p
MAX_DESVIO_X = 0.4               # cuánto (unidades de camera.ui) se puede apartar un globo de su sitio natural: de lado
MAX_DESVIO_Y = 0.3               # y en vertical (de cerca, para bajar del HUD); si no hay hueco así, el globo espera

BAJAR_CUESTA = 3.0               # colocar(): un hueco por debajo del sitio natural cuenta el triple de lejos

FUNDIDO_CAMBIO = 0.15            # s: un texto que se cambia por otro se apaga en este tiempo
FUNDIDO_ENTRADA = 0.2            # s: entrada de un globo (si quien lo pide no trae su propio fundido)

CELDA = 8.0                      # m: celda del índice de oclusores
MARGEN_OCLUSOR = 0.25            # m que se encoge cada caja (un NPC pegado a la pared no queda «tapado»)
TRAMO_FINAL_LIBRE = 0.35         # m del final del rayo que no cuentan (la cabeza misma)
MUESTRAS_TERRENO = 6


def envolver(texto, ancho=AJUSTE_LINEA, max_lineas=MAX_LINEAS):
    """Texto partido en líneas de hasta `ancho` caracteres (por palabras; una palabra más larga va sola). Si sobran
    líneas, la última termina en «…»."""
    palabras = " ".join(str(texto or "").split()).split(" ")
    lineas, actual = [], ""
    for palabra in palabras:
        if not palabra:
            continue
        if actual and len(actual) + 1 + len(palabra) > ancho:
            lineas.append(actual)
            actual = palabra
        else:
            actual = f"{actual} {palabra}" if actual else palabra
    if actual:
        lineas.append(actual)
    if len(lineas) > max_lineas:
        lineas = lineas[:max_lineas]
        lineas[-1] = lineas[-1].rstrip(".…") + "…"
    return "\n".join(lineas)


def alto_linea(distancia, cerca=DISTANCIA_CERCA, lejos=DISTANCIA_LEJOS, minimo=LINEA_MIN, maximo=LINEA_MAX):
    """Alto de una línea (unidades de camera.ui) para un NPC a `distancia` m: el tope de cerca, el mínimo legible de
    lejos y lineal entre medias. Nunca sale del intervalo [minimo, maximo] (NaN o negativo = tope)."""
    if not isinstance(distancia, (int, float)) or distancia != distancia or distancia <= cerca:
        return maximo
    if distancia >= lejos:
        return minimo
    k = (distancia - cerca) / (lejos - cerca)
    return maximo + (minimo - maximo) * k


def medidas_globo(ancho_lineas, n_lineas, linea):
    """(ancho, alto del cuerpo, alto de la cola) del globo en unidades de camera.ui. `ancho_lineas`: ancho del texto
    medido en «alturas de línea» (Text.width / Text.size)."""
    ancho = (ancho_lineas + 2 * RELLENO_X + 2 * BORDE) * linea
    alto = (n_lineas + 2 * RELLENO_Y + 2 * BORDE) * linea
    return ancho, alto, COLA * linea


def film_a_ui(fx, fy, aspecto):
    """Coordenadas de film de la lente (-1..1) a camera.ui (x en ±aspecto/2, y en ±0,5)."""
    return fx * aspecto / 2.0, fy * 0.5


def _rect(r):
    """(x0, y0, x1, y1) de un rect (tupla u objeto con x0..y1)."""
    if isinstance(r, tuple):
        return r
    return (r.x0, r.y0, r.x1, r.y1)


def solapan(a, b, holgura=0.0):
    return not (a[2] + holgura <= b[0] or b[2] + holgura <= a[0] or a[3] + holgura <= b[1] or b[3] + holgura <= a[1])


def colocar(pedidos, obstaculos, zona, holgura=HOLGURA, max_x=MAX_DESVIO_X, max_y=MAX_DESVIO_Y, cabezas=None):
    """Sitio en pantalla de cada globo, sin pisarse entre ellos ni con el HUD.

    pedidos: [(clave, px, py, ancho, alto)] EN ORDEN DE PRIORIDAD (primero el que manda), con (px, py) la punta de la
      cola (justo encima de la cabeza) y alto = cuerpo + cola. obstaculos: rects del HUD. zona: rect de la zona segura.
    Cada globo va a su sitio natural (encima de la cabeza, metido en la zona segura); si ahí pisa algo, se prueban los
    huecos de al lado de lo que pisa (encima, debajo, a la izquierda, a la derecha) y se queda con el más cercano que
    esté libre, sin apartarse más de `max_x` / `max_y` del natural.
    cabezas: {clave: rect} de la cabeza de cada NPC con globo (segunda pasada, D6): el globo de un NPC no tapa la
      cabeza de OTRO que también habla (si no hay sitio sin taparla, se queda donde iría sin esa regla).
    Devuelve {clave: (x0, y0, x1, y1) | None}: el rect del globo (cola incluida, abajo) o None si no cabe (espera)."""
    zx0, zy0, zx1, zy1 = _rect(zona)
    hud = [_rect(o) for o in obstaculos]
    cabezas = {k: _rect(r) for k, r in (cabezas or {}).items()}
    puestos, salida = [], {}
    for clave, px, py, ancho, alto in pedidos:
        if ancho > zx1 - zx0 or alto > zy1 - zy0:
            salida[clave] = None
            continue
        ajenas = [r for k, r in cabezas.items() if k != clave]
        sitio = _sitio(px, py, ancho, alto, hud + puestos + ajenas, (zx0, zy0, zx1, zy1), holgura, max_x, max_y)
        if sitio is None and ajenas:
            sitio = _sitio(px, py, ancho, alto, hud + puestos, (zx0, zy0, zx1, zy1), holgura, max_x, max_y)
        salida[clave] = sitio
        if sitio is not None:
            puestos.append(sitio)
    return salida


def _sitio(px, py, ancho, alto, estorbos, zona, holgura, max_x, max_y):
    """El hueco libre más cercano al sitio natural del globo (ver colocar), o None."""
    zx0, zy0, zx1, zy1 = zona
    nx = min(max(px - ancho / 2, zx0), zx1 - ancho)
    ny = min(max(py, zy0), zy1 - alto)

    def libre(x0, y0):
        r = (x0, y0, x0 + ancho, y0 + alto)
        if x0 < zx0 - 1e-9 or r[2] > zx1 + 1e-9 or y0 < zy0 - 1e-9 or r[3] > zy1 + 1e-9:
            return None
        if abs(x0 - nx) > max_x + 1e-9 or abs(y0 - ny) > max_y + 1e-9:
            return None
        if any(solapan(r, o, holgura) for o in estorbos):
            return None
        return r

    sitio = libre(nx, ny)
    if sitio is None:
        opciones = []
        for o in estorbos:
            opciones += [(nx, o[3] + holgura), (nx, o[1] - holgura - alto),
                         (o[0] - holgura - ancho, ny), (o[2] + holgura, ny)]
        mejor = None
        for x0, y0 in opciones:
            x0 = min(max(x0, zx0), zx1 - ancho)
            y0 = min(max(y0, zy0), zy1 - alto)
            # bajar tapa al propio NPC: cuesta el triple que subir o apartarse de lado (D6: apilar hacia arriba)
            d = abs(x0 - nx) + (abs(y0 - ny) * (BAJAR_CUESTA if y0 < ny else 1.0))
            if mejor is not None and d >= mejor[0]:
                continue
            r = libre(x0, y0)
            if r is not None:
                mejor = (d, r)
        sitio = None if mejor is None else mejor[1]
    return sitio


def rect_cabeza(px, py, ancho=0.04, alto=0.05):
    """Rect (camera.ui) alrededor de la cabeza proyectada: (px, py) es el punto ALTURA m por encima del ancla."""
    return (px - ancho / 2, py - alto, px + ancho / 2, py)


def guia(rect, px, py, minimo=0.012):
    """Segmento ((x0, y0), (x1, y1)) del globo `rect` a la cabeza (px, py) cuando la colita no llega (globo apilado o
    apartado): sale del borde más cercano a la cabeza. None si la cabeza está pegada al globo."""
    x0, y0, x1, y1 = rect
    sx = min(max(px, x0 + 0.02), x1 - 0.02)
    if py < y0:
        inicio = (sx, y0)
    elif py > y1:
        inicio = (sx, y1)
    else:
        inicio = (x0 if px < x0 else x1, min(max(py, y0), y1))
    if math.hypot(px - inicio[0], py - inicio[1]) < minimo:
        return None
    return inicio, (px, py)


# -- Paneles abiertos (segunda pasada, D3) --

def globos_ocultos(en_pausa=False, cinematica=False, escena_activa=True, controles_bloqueados=False,
                   telefono_abierto=False, otros=()):
    """¿Se esconden TODOS los globos? Con pausa, cinemática, escena apagada, cualquier panel que congele los controles
    (EscenaMundo.controles_bloqueados: mapa grande, mochila, paneles registrados con registrar_bloqueador, trabajo,
    vendedor...), el teléfono abierto, u otro panel que no bloquea pero tapa (la leyenda de pulseras, B)."""
    return bool(en_pausa or cinematica or not escena_activa or controles_bloqueados or telefono_abierto
                or any(otros))


def buscar_atributo(obj, nombre, cadena=("vista", "respaldo", "_original"), profundidad=5):
    """El primer `obj.<cadena...>.nombre` que exista, siguiendo envoltorios (teléfono grande -> respaldo -> vista de
    rectificar -> vista de siempre). None si no hay."""
    vistos = set()
    pendientes = [(obj, 0)]
    while pendientes:
        actual, nivel = pendientes.pop(0)
        if actual is None or id(actual) in vistos or nivel > profundidad:
            continue
        vistos.add(id(actual))
        valor = actual.__dict__.get(nombre) if hasattr(actual, "__dict__") else None
        if valor is not None:
            return valor
        for a in cadena:
            siguiente = actual.__dict__.get(a) if hasattr(actual, "__dict__") else None
            if siguiente is not None:
                pendientes.append((siguiente, nivel + 1))
    return None


# -- Oclusores extra (segunda pasada, D6) --

def caja_arbol(cx, cz, suelo):
    """Caja de la copa de un árbol del mundo (ciudad_3d._arbol: esfera de 2,7 x 2,4 x 2,7 m a suelo + 2,75 y otra de
    1,7 m a + 3,75), algo por dentro de la esfera para no esconder de más. (x0, x1, y0, y1, z0, z1) en m."""
    return (cx - 1.15, cx + 1.15, suelo + 1.95, suelo + 4.2, cz - 1.15, cz + 1.15)


def caja_jugador(x, z, suelo, radio=0.28, alto=1.95):
    """Caja del personaje del jugador (modelo de 1,84 m + pelo/gorra): un NPC justo detrás de él no tiene globo
    (parecería que habla el jugador)."""
    return (x - radio, x + radio, suelo, suelo + alto, z - radio, z + radio)


# -- NPC de etapa (frontend/etapas_final_vista.py) --

def pedidos_etapa(cuerpos, prioridad):
    """Pedidos para la CapaGlobos de los NPC de etapa: [(npc, frase, 1.0, prioridad)] de los que hablan (`hablando` y
    `frase_actual`) y se ven (`npc.enabled`). Un NPC que calla o se oculta deja de pedir: la capa apaga su globo."""
    pedidos = []
    for c in cuerpos:
        npc = getattr(c, "npc", None)
        frase = getattr(c, "frase_actual", None)
        if npc is not None and frase and getattr(c, "hablando", False) and getattr(npc, "enabled", False):
            pedidos.append((npc, frase, 1.0, prioridad))
    return pedidos


# -- Oclusión: edificios y casas (cajas) y el terreno --

def _cruza_caja(o, d, caja, t_max):
    """¿El segmento o + t·d (0 < t < t_max) atraviesa la caja (x0, x1, y0, y1, z0, z1)? Método de las losas."""
    x0, x1, y0, y1, z0, z1 = caja
    t0, t1 = 0.0, t_max
    for oi, di, lo, hi in ((o[0], d[0], x0, x1), (o[1], d[1], y0, y1), (o[2], d[2], z0, z1)):
        if abs(di) < 1e-12:
            if oi < lo or oi > hi:
                return False
            continue
        a, b = (lo - oi) / di, (hi - oi) / di
        if a > b:
            a, b = b, a
        t0, t1 = max(t0, a), min(t1, b)
        if t0 > t1:
            return False
    return True


def _dentro(p, caja):
    x0, x1, y0, y1, z0, z1 = caja
    return x0 <= p[0] <= x1 and y0 <= p[1] <= y1 and z0 <= p[2] <= z1


class IndiceOclusores:
    """Cajas (x0, x1, y0, y1, z0, z1) en m del mundo, repartidas en celdas de `celda` m del plano XZ."""

    def __init__(self, cajas, celda=CELDA, margen=MARGEN_OCLUSOR, altura=None):
        self.celda = celda
        self.altura = altura                     # altura(x, z) del terreno, o None
        self.cajas = []
        self._celdas = {}
        for x0, x1, y0, y1, z0, z1 in cajas:
            if x1 - x0 <= 2 * margen or z1 - z0 <= 2 * margen or y1 <= y0:
                continue
            caja = (x0 + margen, x1 - margen, y0, y1, z0 + margen, z1 - margen)
            k = len(self.cajas)
            self.cajas.append(caja)
            for i in range(math.floor(caja[0] / celda), math.floor(caja[1] / celda) + 1):
                for j in range(math.floor(caja[4] / celda), math.floor(caja[5] / celda) + 1):
                    self._celdas.setdefault((i, j), []).append(k)

    def _cerca_del_segmento(self, a, b):
        c = self.celda
        vistos = set()
        for i in range(math.floor(min(a[0], b[0]) / c), math.floor(max(a[0], b[0]) / c) + 1):
            for j in range(math.floor(min(a[2], b[2]) / c), math.floor(max(a[2], b[2]) / c) + 1):
                for k in self._celdas.get((i, j), ()):
                    if k not in vistos:
                        vistos.add(k)
                        yield self.cajas[k]

    def tapado(self, ojo, punto, libre=TRAMO_FINAL_LIBRE, extras=()):
        """¿Hay una caja (o el terreno) entre `ojo` y `punto` (x, y, z)? El último `libre` m no cuenta, ni una caja que
        contenga al ojo (cámara metida en una pared: mejor ver el globo que perderlos todos). `extras`: cajas que no
        están en el índice (el personaje del jugador), sin encoger."""
        d = (punto[0] - ojo[0], punto[1] - ojo[1], punto[2] - ojo[2])
        largo = math.sqrt(d[0] * d[0] + d[1] * d[1] + d[2] * d[2])
        if largo <= libre:
            return False
        t_max = 1.0 - libre / largo
        for caja in list(self._cerca_del_segmento(ojo, punto)) + list(extras):
            if not _dentro(ojo, caja) and _cruza_caja(ojo, d, caja, t_max):
                return True
        if self.altura is not None:
            for s in range(1, MUESTRAS_TERRENO + 1):
                t = t_max * s / (MUESTRAS_TERRENO + 1)
                x, y, z = ojo[0] + d[0] * t, ojo[1] + d[1] * t, ojo[2] + d[2] * t
                try:
                    if self.altura(x, z) > y + 0.25:
                        return True
                except Exception:      # noqa: BLE001 — un terreno raro no esconde globos
                    return False
        return False


# -- Un globo por NPC: transición entre textos --

class EstadoGlobo:
    """Lo que se MUESTRA del globo de un NPC. `paso(dt, texto, alfa)` con lo que se PIDE (texto None = nada) devuelve
    (texto_mostrado, alfa_mostrado, cambio). Si el texto pedido cambia con el anterior aún a la vista, el anterior baja
    a 0 en FUNDIDO_CAMBIO s y solo entonces se cambia (`cambio` = True ese cuadro, con alfa 0). El alfa mostrado nunca
    pasa del pedido ni sube más rápido que FUNDIDO_ENTRADA."""

    __slots__ = ("texto", "alfa")

    def __init__(self):
        self.texto, self.alfa = None, 0.0

    def paso(self, dt, texto, alfa):
        dt = max(0.0, dt)
        alfa = max(0.0, min(1.0, alfa if texto else 0.0))
        cambio = False
        if texto != self.texto and self.texto is not None and self.alfa > 0.0:
            self.alfa = max(0.0, self.alfa - dt / FUNDIDO_CAMBIO)      # se apaga el anterior
            return self.texto, self.alfa, False
        if texto != self.texto:
            self.texto, self.alfa, cambio = texto, 0.0, True
            return self.texto, self.alfa, cambio
        if alfa < self.alfa:
            self.alfa = max(alfa, self.alfa - dt / FUNDIDO_CAMBIO)
        else:
            self.alfa = min(alfa, self.alfa + dt / FUNDIDO_ENTRADA)
        return self.texto, self.alfa, cambio
