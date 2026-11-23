# Cálculos PUROS (sin ursina/panda3d) de la familia «mesa» del rework 3D: Comparar dos versiones (linterna en el cuarto
# oscuro) y Señales de edición (plumón rojo con la lámpara encendida). Los usan comparar_3d.py, senales_3d.py y
# mesa_piezas.py; se prueban en tests/test_rework3d_mesa_calculos.py.
#
# Coordenadas: LOCALES del ancla «mesa» del set cuarto_mesa (metros; +x a lo ancho hacia la derecha, +y hacia el fondo,
# la cara visible hacia -z = hacia arriba) salvo donde se diga «mundo».
#
#   toma_mesa(objetivo, inclinacion, rumbo, distancia, fov, techo)  -> toma de cámara (dict de camaras_calculos)
#   proyectar(toma, punto, aspecto)                                  -> (x_ndc, y_ndc, profundidad) o None
#   filas_comparar(lineas, n_lineas_de, ...)                         -> reparto de las filas sobre las dos hojas
#   radio_haz(anchos)                                                -> radio del haz de la linterna (m)
#   Haz                                                              -> dónde está el haz: ratón / mando / teclado
#   mano_linterna(hombro, punto, ...)                                -> dónde va la mano que sostiene el celular
#   elipse(cx, cy, rx, ry, progreso)                                 -> puntos del trazo de plumón (a mano alzada)

import math

# -- Composición (salió de rework-3d/familia-mesa/busqueda_toma2.py: el cuerpo no tapa los papeles y el texto es el más
#    grande posible; la manda la legibilidad) --
PIE_MESA = (-0.75, -0.05, 45.0)      # (x, z, rumbo) MUNDO: de pie en la esquina cercana izquierda, mirando a los papeles
TOMA_COMPARAR = {"objetivo": (-0.15, -0.16), "inclinacion": 64.0, "rumbo": 0.0, "distancia": 2.1, "fov": 45.0}
TOMA_SENALES = {"objetivo": (-0.05, -0.20), "inclinacion": 64.0, "rumbo": 0.0, "distancia": 1.85, "fov": 45.0}
TECHO_MARGEN = 0.15                  # m: la cámara nunca a menos de esto del techo

# -- Hojas de Comparar --
ANCHO_HOJA = 0.51
SEPARACION_HOJAS = 0.23              # entre las hojas: las etiquetas de las filas marcadas de la copia («MARCADA»...)
Y_HOJAS = -0.06                      # centro (y local) de las dos hojas
ALTO_LINEA = 0.032                   # m (alto de letra de papel_3d.texto_en_papel); se mide en px con el arnés
LINEA = 1.32                         # = frontend.minijuegos.ui.LINEA (separación de renglones)
MARGEN_FILA = 0.012                  # m arriba y abajo de cada fila
MARGEN_HOJA = 0.04                   # m entre el borde de la hoja y la primera/última fila
ALTO_CABECERA = 0.07                 # m de la cabecera («ORIGINAL» / «COPIA QUE CIRCULA»)

# -- Haz de linterna --
RADIO_MIN, RADIO_MAX = 0.15, 0.34    # m (el tope deja caber la línea más larga de UNA hoja, nunca las dos)
FACTOR_RADIO = 0.65                  # radio = FACTOR · ancho de la línea de texto más larga (diámetro ~1,3 líneas)
BORDE_HAZ = 0.035                    # m de borde suave (fuera del radio menos esto, la luz cae a la penumbra)
SEGUIR_RATON = 30.0                  # 1/s: el haz sigue al puntero casi en el acto
SEGUIR_TECLADO = 7.0                 # 1/s: con el teclado se desliza
QUIETO_TECLADO = 1.6                 # s quieto en cada versión (copia, original, copia...) con el teclado
DISTANCIA_MANO = 0.40                # m del hombro a la mano que sostiene el celular, hacia el haz
ALTURA_MANO_MIN = 0.30               # m sobre la mesa como mínimo
MANO_PECHO = (0.18, -0.28, 0.04)     # celular a la altura del pecho: (adelante, abajo, hacia el haz) m desde el hombro

# -- Plumón --
DURACION_TRAZO = 0.4                 # s que tarda la mano en dibujar el círculo
GROSOR_TRAZO = 0.006                 # m
SOLAPE_TRAZO = 0.08                  # fracción de vuelta de más (el trazo a mano se cierra pasándose un poco)


def _sum(a, b):
    return tuple(a[i] + b[i] for i in range(len(a)))


def _res(a, b):
    return tuple(a[i] - b[i] for i in range(len(a)))


def _esc(a, k):
    return tuple(c * k for c in a)


def _largo(a):
    return math.sqrt(sum(c * c for c in a))


def _unit(a):
    n = _largo(a) or 1.0
    return _esc(a, 1.0 / n)


def _cruz(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def finito(p):
    """¿Todas las coordenadas son números finitos? (un hueso recién creado o una IK degenerada pueden dar NaN, y Panda
    aborta con «!mat.is_nan()» si se le pasa una posición así)."""
    try:
        return p is not None and all(math.isfinite(float(c)) for c in p)
    except (TypeError, ValueError):
        return False


# -- Cámara --

def toma_mesa(objetivo_mundo, inclinacion, rumbo, distancia, fov, techo=None):
    """Toma desde el lado cercano de la mesa (z menor), mirando `objetivo_mundo` desde `inclinacion` grados sobre la
    horizontal, girada `rumbo` grados alrededor de la vertical. Si la cámara tocaría el `techo`, se acerca (nunca sube)."""
    p, r = math.radians(inclinacion), math.radians(rumbo)
    d = distancia
    while True:
        pos = (objetivo_mundo[0] - d * math.cos(p) * math.sin(r), objetivo_mundo[1] + d * math.sin(p),
               objetivo_mundo[2] - d * math.cos(p) * math.cos(r))
        if techo is None or pos[1] <= techo - TECHO_MARGEN or d < 0.6:
            break
        d -= 0.02
    return {"position": pos, "target": tuple(objetivo_mundo), "fov": float(fov)}


def proyectar(toma, punto, aspecto=16 / 9):
    """Punto de MUNDO -> (x_ndc, y_ndc, profundidad) con la toma (FOV horizontal, mano izquierda como Ursina). None si
    queda detrás de la cámara."""
    pos, tgt = toma["position"], toma["target"]
    f = _unit(_res(tgt, pos))
    r = _unit(_cruz((0.0, 1.0, 0.0), f))
    u = _cruz(f, r)
    d = _res(punto, pos)
    z = sum(d[i] * f[i] for i in range(3))
    if z <= 1e-4:
        return None
    th = math.tan(math.radians(toma["fov"]) / 2)
    return (sum(d[i] * r[i] for i in range(3)) / (z * th), sum(d[i] * u[i] for i in range(3)) / (z * th / aspecto), z)


# -- Hojas de Comparar --

def filas_comparar(lineas, n_lineas_de, ancho_texto, alto_linea=ALTO_LINEA, alto_cabecera=ALTO_CABECERA):
    """Reparte las filas sobre las dos hojas (las dos versiones de la fila k a la MISMA altura). `lineas` son los dicts
    de la partida (etiqueta, original, copia); `n_lineas_de(cadena, alto_linea, ancho)` cuenta renglones (lo da la vista
    con la misma regla de ajuste que el texto). Devuelve {"textos": [(texto_original, texto_copia)], "altos": [m],
    "centros": [y relativa a la parte de arriba de la zona de filas, negativa], "alto_hoja": m}."""
    textos, altos = [], []
    for l in lineas:
        a = f"{l['etiqueta']}: {l['original']}"
        b = f"{l['etiqueta']}: {l['copia']}"
        n = max(n_lineas_de(a, alto_linea, ancho_texto), n_lineas_de(b, alto_linea, ancho_texto), 1)
        textos.append((a, b))
        altos.append(n * alto_linea * LINEA + 2 * MARGEN_FILA)
    centros, y = [], 0.0
    for h in altos:
        centros.append(y - h / 2)
        y -= h
    alto_hoja = alto_cabecera + sum(altos) + 2 * MARGEN_HOJA
    return {"textos": textos, "altos": altos, "centros": centros, "alto_hoja": alto_hoja}


def x_hojas(ancho=ANCHO_HOJA, separacion=SEPARACION_HOJAS):
    """(x del centro de la hoja ORIGINAL, x del centro de la COPIA): a izquierda y derecha del centro de la mesa."""
    d = (ancho + separacion) / 2
    return (-d, d)


def radio_haz(anchos_linea):
    """Radio (m) del haz: la línea de texto más larga cabe ENTERA y bien iluminada (diámetro ~1,3 líneas, más el borde
    suave, que ya no se lee), acotado para que haya que explorar."""
    anchos = [a for a in anchos_linea if a > 0]
    if not anchos:
        return RADIO_MIN
    return min(RADIO_MAX, max(RADIO_MIN, FACTOR_RADIO * max(anchos) + BORDE_HAZ))


def dentro_del_haz(punto, centro, radio):
    """¿Se lee `punto` (x, y)? (dentro del radio, sin contar el borde suave)."""
    return math.hypot(punto[0] - centro[0], punto[1] - centro[1]) <= radio - BORDE_HAZ


def _acercar(actual, destino, dt, rapidez):
    k = 1.0 - math.exp(-max(0.0, dt) * rapidez)
    return actual + (destino - actual) * k


class Haz:
    """Dónde apunta la linterna (x, y locales de la mesa). Tres modos, como el jugador juegue:
    - «libre»: el punto del puntero (ratón) o del cursor del palo derecho (mando) sobre la mesa; el haz lo sigue;
    - «teclado»: con las flechas/Enter el haz va SOLO a la fila con el foco: primero a la copia y, quieto un momento en
      cada una, alterna con el original (así se pueden comparar sin ratón).
    El modo cambia con lo último que hizo el jugador: mover el puntero/palo -> libre; una tecla -> teclado."""

    def __init__(self, inicio=(0.0, 0.0), limites=(-0.85, 0.85, -0.5, 0.5)):
        self.x, self.y = inicio
        self.destino = tuple(inicio)
        self.limites = limites
        self.modo = "libre"
        self._puntos = []
        self._t = 0.0

    def teclado(self, puntos):
        """El foco cambió con el teclado: `puntos` = [(x, y) de la copia, (x, y) del original] de esa fila (o [] si el
        foco está en un botón: el haz se queda donde está)."""
        if not puntos:
            return
        self.modo = "teclado"
        self._puntos = [tuple(p) for p in puntos]
        self._t = 0.0

    def avanzar(self, dt, libre=None):
        """`libre` = (x, y) del puntero/palo SI SE MOVIÓ este frame (None si no). Devuelve (x, y) del haz."""
        if libre is not None and not finito(libre):
            libre = None                                 # un rayo degenerado no mueve el haz
        if libre is not None:
            self.modo = "libre"
            self.destino = self._acotar(libre)
        elif self.modo == "teclado" and self._puntos:
            self._t += dt
            ciclo = QUIETO_TECLADO * len(self._puntos)
            i = int((self._t % ciclo) // QUIETO_TECLADO) if ciclo > 0 else 0
            self.destino = self._acotar(self._puntos[i])
        rapidez = SEGUIR_RATON if self.modo == "libre" else SEGUIR_TECLADO
        self.x = _acercar(self.x, self.destino[0], dt, rapidez)
        self.y = _acercar(self.y, self.destino[1], dt, rapidez)
        return (self.x, self.y)

    def _acotar(self, p):
        x0, x1, y0, y1 = self.limites
        return (min(max(p[0], x0), x1), min(max(p[1], y0), y1))


def se_movio(a, b, umbral=1e-4):
    """¿Cambió el punto del puntero/cursor entre dos frames? (None = sin puntero)."""
    if a is None or b is None:
        return a is not b
    return abs(a[0] - b[0]) > umbral or abs(a[1] - b[1]) > umbral


# -- Mano con el celular --

def mano_linterna(hombro, punto, altura_mesa, distancia=DISTANCIA_MANO, altura_min=ALTURA_MANO_MIN):
    """Mano (MUNDO) que sostiene el celular apuntando a `punto` (mundo, sobre la mesa): a `distancia` m del hombro en la
    dirección del punto, nunca a menos de `altura_min` m sobre la mesa (no la atraviesa y el haz cae desde arriba)."""
    d = _unit(_res(punto, hombro))
    mano = _sum(hombro, _esc(d, distancia))
    y_min = altura_mesa + altura_min
    if mano[1] < y_min:
        mano = (mano[0], y_min, mano[2])
    return mano


def mano_pecho(hombro, rumbo, punto, altura_mesa, ajuste=MANO_PECHO, altura_min=ALTURA_MANO_MIN):
    """Mano (MUNDO) que sostiene el celular junto al pecho (no se mete entre la cámara y los papeles): `ajuste[0]` m
    delante del hombro, `ajuste[1]` m más abajo y `ajuste[2]` m hacia el punto que alumbra (en horizontal); nunca a menos
    de `altura_min` m sobre la mesa."""
    r = math.radians(rumbo)
    adelante = (math.sin(r), 0.0, math.cos(r))
    hacia = _unit((punto[0] - hombro[0], 0.0, punto[2] - hombro[2]))
    mano = _sum(_sum(_sum(hombro, _esc(adelante, ajuste[0])), (0.0, ajuste[1], 0.0)), _esc(hacia, ajuste[2]))
    if mano[1] < altura_mesa + altura_min:
        mano = (mano[0], altura_mesa + altura_min, mano[2])
    return mano


def hombro_estimado(base, rumbo, lado="d", alto=1.40, ancho=0.19):
    """Hombro (mundo) de un personaje de pie en `base` (x, y, z) mirando a `rumbo` (grados; 0 = +z, Ursina)."""
    r = math.radians(rumbo)
    derecha = (math.cos(r), 0.0, -math.sin(r))
    s = 1.0 if lado == "d" else -1.0
    return (base[0] + derecha[0] * ancho * s, base[1] + alto, base[2] + derecha[2] * ancho * s)


# -- Plumón --

def elipse(cx, cy, rx, ry, progreso=1.0, n=48, inicio=100.0, solape=SOLAPE_TRAZO, temblor=0.06):
    """Puntos (x, y) de una elipse trazada a mano: empieza en `inicio` grados, va en sentido horario y da 1 + `solape`
    vueltas (se pasa un poco al cerrarse); `temblor` deforma el radio (fracción) con una onda fija (determinista).
    `progreso` (0..1) recorta el trazo: lo que la mano lleva dibujado."""
    progreso = min(1.0, max(0.0, progreso))
    total = 1.0 + solape
    pasos = max(2, int(round(n * total * progreso)) + 1)
    pts = []
    for k in range(pasos):
        f = total * progreso * k / (pasos - 1)
        a = math.radians(inicio) - 2 * math.pi * f
        onda = 1.0 + temblor * math.sin(3 * a + 0.7) * (0.6 + 0.4 * f)
        crece = 1.0 + 0.05 * f                       # la vuelta de más queda un poco por fuera
        pts.append((cx + rx * onda * crece * math.cos(a), cy + ry * onda * crece * math.sin(a)))
    return pts


def cinta(puntos, grosor=GROSOR_TRAZO):
    """Triángulos de una cinta de `grosor` m a lo largo de la polilínea `puntos` (x, y): lista de vértices (x, y) en
    grupos de 3 (para un Mesh de triángulos)."""
    if len(puntos) < 2:
        return []
    bordes = []
    for i, p in enumerate(puntos):
        a = puntos[max(0, i - 1)]
        b = puntos[min(len(puntos) - 1, i + 1)]
        dx, dy = b[0] - a[0], b[1] - a[1]
        n = math.hypot(dx, dy) or 1.0
        nx, ny = -dy / n * grosor / 2, dx / n * grosor / 2
        bordes.append(((p[0] + nx, p[1] + ny), (p[0] - nx, p[1] - ny)))
    tris = []
    for i in range(len(bordes) - 1):
        (a1, a2), (b1, b2) = bordes[i], bordes[i + 1]
        tris += [a1, a2, b1, b1, a2, b2]
    return tris


def progreso_trazo(t, duracion=DURACION_TRAZO):
    """Progreso suave (ease in-out) del trazo a los `t` s."""
    k = min(1.0, max(0.0, t / duracion if duracion > 0 else 1.0))
    return k * k * (3 - 2 * k)
