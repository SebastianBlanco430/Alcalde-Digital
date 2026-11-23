# Cielo por nivel (M7 del plan ambiente y pulseras; ALCALDE_CIELO_SALUD=0 = el cielo de siempre). Puro: sin ursina.
# Lo aplica frontend/ciudad_viva.py (dueño de luz, cielo y niebla) cada vez que repasa la atmósfera:
#   apagado  cielo CUBIERTO: una capa gris casi opaca dentro del domo y nubes más bajas, grandes y grises;
#   tenso    BRUMA: la misma capa, fina y parda;
#   sano / florece  despejado (capa invisible, nubes de siempre); en florece, algunos pájaros dando vueltas.
# Sin lluvia (partículas caras). Todo continuo en la salud: nada salta al cruzar un nivel.
import os

CIELO_SALUD = True

COLOR_CUBIERTO = (138, 142, 152)      # gris plomo
COLOR_BRUMA = (196, 182, 164)         # pardo claro
ALFA_CUBIERTO = 0.62
ALFA_BRUMA = 0.28
TONO_NUBE_GRIS = (0.62, 0.64, 0.70)   # factor de color de las nubes con la ciudad apagada
ESCALA_NUBES_MAX = 1.35               # nubes más grandes (y más bajas) apagado
BAJADA_NUBES = 0.06                   # fracción del radio del domo que bajan las nubes apagado
PAJAROS_MAX = 7


def activo():
    valor = os.environ.get("ALCALDE_CIELO_SALUD", "").strip().lower()
    if valor in ("1", "true", "si", "sí", "on"):
        return True
    if valor in ("0", "false", "no", "off"):
        return False
    return bool(CIELO_SALUD)


def _suave(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3.0 - 2.0 * t)


def _mezclar(a, b, t):
    return tuple(round(a[i] + (b[i] - a[i]) * t, 4) for i in range(len(a)))


def cielo_de_salud(salud):
    """{"capa_color" RGB 0-255, "capa_alfa" 0..1, "nubes_tono" (r, g, b) factor, "nubes_escala", "nubes_bajada",
    "pajaros" (entero)} para una salud 0..1. Con salud >= 0,5 el cielo es el de siempre (salvo pájaros en florece)."""
    s = max(0.0, min(1.0, float(salud)))
    cubierto = _suave((0.25 - s) / 0.2)         # 1 bien adentro de «apagado», 0 desde tenso
    bruma = _suave((0.5 - s) / 0.2)             # 1 desde la mitad de tenso hacia abajo, 0 en sano
    alfa = ALFA_BRUMA * bruma + (ALFA_CUBIERTO - ALFA_BRUMA) * cubierto
    color = _mezclar(COLOR_BRUMA, COLOR_CUBIERTO, cubierto)
    gris = max(cubierto, 0.4 * bruma)
    return {
        "capa_color": tuple(int(round(c)) for c in color),
        "capa_alfa": round(alfa, 4),
        "nubes_tono": _mezclar((1.0, 1.0, 1.0), TONO_NUBE_GRIS, gris),
        "nubes_escala": round(1.0 + (ESCALA_NUBES_MAX - 1.0) * cubierto, 4),
        "nubes_bajada": round(BAJADA_NUBES * cubierto, 4),
        "pajaros": int(round(PAJAROS_MAX * _suave((s - 0.75) / 0.15))),
    }


def posicion_pajaro(k, t, centro, radio=22.0, altura=16.0):
    """(x, y, z) del pájaro k a los t s: vueltas lentas y desfasadas sobre `centro` (x, z), con un leve sube y baja."""
    import math
    fase = k * 2.399963                         # ángulo áureo: se reparten sin amontonarse
    vel = 0.18 + 0.03 * (k % 3)
    a = fase + vel * t
    r = radio * (0.6 + 0.4 * ((k * 0.618) % 1.0))
    return (centro[0] + r * math.cos(a), altura + 1.5 * math.sin(0.7 * t + fase), centro[1] + r * math.sin(a))


# -- R4 (retoques): pájaros que se vean --------------------------------------------------------------------------------------
# posicion_pajaro los ponía a y = 16 m ABSOLUTOS, pero la ciudad está en ladera (plazas entre 7 y 17 m): en la Praça da Sé
# quedaban a 1,5 m del suelo, a 20 m, y se veían como «astillas» oscuras sobre el suelo; y con la cámara normal (pitch
# ~22°, FOV vertical ~39°) el borde de arriba de la pantalla queda bajo el horizonte: en el cielo nunca salían. Con la
# bandera vuelan en la franja de arriba de la vista: alrededor de un centro DELANTE de la cámara (que la sigue con retraso),
# como palomas que cruzan la plaza (con pitch 22° el borde de arriba queda ~4 m bajo la cámara a 30 m: más alto no se ve);
# a la altura que cae unos grados bajo el borde superior, y siempre al menos ALTURA_MIN_SUELO sobre el suelo.
# ALCALDE_PAJAROS_VISIBLES=0 = como antes.
PAJAROS_VISIBLES = True
DISTANCIA_PAJAROS = 12.0        # m delante de la cámara del centro de las vueltas
RADIO_PAJAROS = 3.5             # m de las vueltas (12 - 3,5 > 7 m de la cámara al jugador: nunca entre los dos)
GRADOS_BAJO_BORDE = 10.0        # grados bajo el borde de arriba de la pantalla (debajo de la barra del HUD)
ALTURA_MIN_SUELO = 2.2          # m sobre el suelo bajo el centro, como mínimo (palomas que cruzan la plaza)
ESCALA_PAJARO = 0.7             # m de envergadura
RAPIDEZ_CENTRO = 0.6            # 1/s: el centro sigue a la cámara sin pegarse (no giran con ella al instante)


def pajaros_visibles_activo():
    valor = os.environ.get("ALCALDE_PAJAROS_VISIBLES", "").strip().lower()
    if valor in ("1", "true", "si", "sí", "on"):
        return True
    if valor in ("0", "false", "no", "off"):
        return False
    return bool(PAJAROS_VISIBLES)


def fov_vertical(fov_horizontal, aspecto):
    """FOV vertical (grados) de una lente con FOV horizontal `fov_horizontal` y aspecto ancho/alto."""
    import math
    return math.degrees(2 * math.atan(math.tan(math.radians(fov_horizontal) / 2) / max(1e-6, aspecto)))


def centro_pajaros(camara, yaw, distancia=DISTANCIA_PAJAROS):
    """(x, z) del punto `distancia` m delante de la cámara (yaw en grados, convención de Ursina: adelante = (sin, cos))."""
    import math
    a = math.radians(yaw)
    return (camara[0] + distancia * math.sin(a), camara[2] + distancia * math.cos(a))


def seguir_centro(actual, objetivo, dt, rapidez=RAPIDEZ_CENTRO):
    """Un paso exponencial de `actual` (x, z) hacia `objetivo` (independiente de los fps). None = empieza en el objetivo."""
    import math
    if actual is None or dt <= 0:
        return objetivo if actual is None else actual
    f = 1 - math.exp(-rapidez * dt)
    return (actual[0] + (objetivo[0] - actual[0]) * f, actual[1] + (objetivo[1] - actual[1]) * f)


def altura_pajaros(camara_y, pitch, fov_v, suelo_centro, distancia=DISTANCIA_PAJAROS, bajo_borde=GRADOS_BAJO_BORDE,
                   minimo=ALTURA_MIN_SUELO):
    """y de las vueltas: la que a `distancia` m cae `bajo_borde` grados bajo el borde de arriba de la pantalla (pitch
    positivo = mirando abajo), pero nunca a menos de `minimo` m sobre el suelo del centro."""
    import math
    elevacion = -pitch + fov_v / 2 - bajo_borde
    return max(suelo_centro + minimo, camara_y + distancia * math.tan(math.radians(elevacion)))


def posicion_pajaro_visible(k, t, centro, altura, radio=RADIO_PAJAROS):
    """(x, y, z) del pájaro k: vueltas desfasadas de radio ~`radio` alrededor de `centro`, a `altura` ± 1 m."""
    x, y, z = posicion_pajaro(k, t, centro, radio=radio, altura=0.0)
    return (x, altura + y * (1.0 / 1.5), z)


def aleteo(k, t, frecuencia=8.0):
    """Factor de escala vertical del pájaro k a los t s: la V se abre y se cierra (alas arriba y abajo), desfasado.
    Nunca 0 (una escala nula deja la transformación singular en Panda): |factor| >= 0,2."""
    import math
    v = 1.6 * math.sin(frecuencia * t + k * 1.7)
    return v if abs(v) >= 0.2 else (0.2 if v >= 0 else -0.2)


# -- Cierre (punto 4, ALCALDE_PAJAROS_LIBRES): un pájaro quedó «sobre el respaldo de un banco». Las vueltas se calculan
# solo con el suelo bajo el CENTRO; con la ladera y los props del camino un pájaro podía quedar dentro de una copa o, visto
# desde la cámara, posado sobre un banco/farola/jardinera que tiene detrás. Con la bandera, a cada pájaro se le suma una
# SUBIDA (suave en el tiempo) que lo deja:
#   - al menos ALTURA_MIN_SUELO sobre el suelo bajo ÉL (no bajo el centro);
#   - fuera del volumen de cada prop (radio + MARGEN_DENTRO_XZ, alto + MARGEN_DENTRO_Y);
#   - sin que el rayo cámara→pájaro, más allá del pájaro, pase por un prop por debajo de su alto + MARGEN_VISUAL_Y (eso es
#     lo que se lee como «posado»): se resuelve exacto, la recta en xz no cambia al subirlo;
#   - a ≥ ANGULO_JUGADOR grados del personaje si está más cerca de la cámara que él (al girar no lo tapa).
# ALCALDE_PAJAROS_LIBRES=0 = como antes (R4).
PAJAROS_LIBRES = True
ALTO_PROP_PAJARO = {"banco": 1.0, "jardinera": 1.0, "caneca": 1.0, "valla": 1.1, "arbusto": 1.4, "cartel": 2.4,
                    "farola": 4.9, "arbol": 5.2, "fuente": 2.6}       # farola: 4,4 + 0,5 (2026-11-23, postes más altos)
RADIO_EXTRA_PROP = {"arbol": 1.6, "arbusto": 0.5, "farola": 0.2}   # copa/brazo más ancho que el cuerpo de colisión
MARGEN_DENTRO_XZ = 0.8
MARGEN_DENTRO_Y = 1.0
MARGEN_VISUAL_XZ = 0.5
MARGEN_VISUAL_Y = 0.5
ALCANCE_VISUAL = 18.0          # m detrás del pájaro en los que un prop aún «lo recoge»
ANGULO_JUGADOR = 9.0           # grados de aire entre el pájaro y el pecho del personaje
SUBIDA_MAX = 4.0               # m: más no hace falta (y lo sacaría de cuadro)
RAPIDEZ_SUBIDA = 3.0           # 1/s del suavizado de la subida


def pajaros_libres_activo(entorno=None):
    valor = (os.environ if entorno is None else entorno).get("ALCALDE_PAJAROS_LIBRES", "").strip().lower()
    if valor in ("1", "true", "si", "sí", "on"):
        return True
    if valor in ("0", "false", "no", "off"):
        return False
    return bool(PAJAROS_LIBRES)


def props_para_pajaros(obstaculos, suelo):
    """[(x, z, radio, y_tope)] de los obstáculos con alto conocido (círculos de props; las cajas usan su medio lado)."""
    salida = []
    for o in obstaculos:
        alto = ALTO_PROP_PAJARO.get(getattr(o, "tipo", None))
        if alto is None:
            continue
        r = o.radio if o.radio is not None else 0.5 * max(o.ancho or 0.0, o.fondo or 0.0)
        r += RADIO_EXTRA_PROP.get(o.tipo, 0.0)
        salida.append((o.cx, o.cz, r, suelo(o.cx, o.cz) + alto))
    return salida


def subida_por_props(p, camara, props, suelo_bajo=None):
    """m que hay que subir el pájaro en `p` (x, y, z) para que no quede dentro de un prop ni «posado» en uno de detrás."""
    import math
    x, y, z = p
    need = 0.0
    if suelo_bajo is not None:
        need = max(need, suelo_bajo + ALTURA_MIN_SUELO - y)
    cx, cy, cz = camara
    dx, dz = x - cx, z - cz
    db = math.hypot(dx, dz)
    for (px, pz, r, tope) in props:
        if math.hypot(x - px, z - pz) < r + MARGEN_DENTRO_XZ:
            need = max(need, tope + MARGEN_DENTRO_Y - y)
        if db < 1e-6:
            continue
        ux, uz = dx / db, dz / db
        d = (px - cx) * ux + (pz - cz) * uz                   # distancia horizontal de la cámara al punto más cercano
        if d <= db or d > db + ALCANCE_VISUAL:
            continue
        lateral = abs((px - cx) * uz - (pz - cz) * ux)
        if lateral >= r + MARGEN_VISUAL_XZ:
            continue
        h = cy + (y - cy) * d / db                            # altura del rayo cámara→pájaro sobre el prop
        if h < tope + MARGEN_VISUAL_Y:
            need = max(need, (tope + MARGEN_VISUAL_Y - h) * db / d)
    return max(0.0, min(SUBIDA_MAX, need))


def angulo_desde_camara(camara, a, b):
    """Grados entre las direcciones cámara→a y cámara→b."""
    import math
    va = [a[i] - camara[i] for i in range(3)]
    vb = [b[i] - camara[i] for i in range(3)]
    na, nb = math.sqrt(sum(c * c for c in va)), math.sqrt(sum(c * c for c in vb))
    if na < 1e-9 or nb < 1e-9:
        return 180.0
    cos = max(-1.0, min(1.0, sum(va[i] * vb[i] for i in range(3)) / (na * nb)))
    return math.degrees(math.acos(cos))


def subida_por_jugador(p, camara, pecho, angulo=ANGULO_JUGADOR, paso=0.1):
    """m que hay que subir el pájaro para quedar a ≥ `angulo` grados del pecho del personaje si está delante de él."""
    import math
    if pecho is None:
        return 0.0
    if math.dist(p, camara) >= math.dist(pecho, camara):
        return 0.0                                            # está detrás: lo tapa el personaje, no al revés
    subida = 0.0
    while subida < SUBIDA_MAX and angulo_desde_camara(camara, (p[0], p[1] + subida, p[2]), pecho) < angulo:
        subida += paso
    return min(subida, SUBIDA_MAX)


def suavizar_subida(actual, objetivo, dt, rapidez=RAPIDEZ_SUBIDA):
    """Sube al instante lo que falte para no meterse en un prop (nunca atraviesa) y baja suave."""
    import math
    if actual is None or objetivo >= actual or dt <= 0:
        return objetivo if (actual is None or objetivo >= actual) else actual
    return actual + (objetivo - actual) * (1 - math.exp(-rapidez * dt))


def subida_total(p, camara, props, suelo_bajo, pecho):
    """Subida de un pájaro: primero fuera de suelo y props; desde ahí, lo que falte para no tapar al personaje."""
    a = subida_por_props(p, camara, props, suelo_bajo)
    b = subida_por_jugador((p[0], p[1] + a, p[2]), camara, pecho)
    return min(SUBIDA_MAX, a + b)
