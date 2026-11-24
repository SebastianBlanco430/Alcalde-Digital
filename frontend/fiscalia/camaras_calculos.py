# Planos de cámara de la Fiscalía (Python puro: NO importa ursina; tests en tests/test_fiscalia_escena_camaras.py).
# Una TOMA es {"position": (x, y, z), "target": (x, y, z), "fov": grados} (la misma forma que
# frontend/minijuegos_3d/camaras_calculos y que la Toma del contrato de cinematica_silla).
#
#   general       abierta, desde detrás y a la derecha del jugador: él de espaldas, la mesa y quien habla.
#   pecho         de frente a quien habla, a la altura de los ojos, por encima del hombro del jugador (fuera de cuadro).
#   primer_plano  la cara de quien habla, cerca (reacciones).
#   contraplano   detrás del jugador, sobre su hombro derecho: su nuca asoma por el borde y quien habla enfrente.
# Toda toma deja la cara de quien habla en CARA_EN_PANTALLA (centro-izquierda; `encuadrar`): el tercio derecho es de la
# rueda de opciones, que no se mueve (rueda_calculos.CENTRO_FIJO).
# Elegir: el `plano` del nodo si viene; si no, `elegir_plano` (abre la sala en general; ruedas en pecho; respuestas a
# una elección en primer plano; el resto alterna pecho y contraplano).

import math

PLANOS = ("general", "pecho", "primer_plano", "contraplano")
FOV = {"general": 58.0, "pecho": 38.0, "primer_plano": 42.0, "contraplano": 46.0}
DURACION_CORTE = 0.55            # s de transición suave entre planos
DERIVA = 0.012                   # m: vaivén de la cámara al «respirar» (0 con reducir movimiento)
MIN_A_CABEZA = 0.38              # m: la cámara nunca entra más cerca de la cabeza
# Dónde cae la cara de quien habla en camera.ui (x de -0,889 a 0,889; y de -0,5 a 0,5): centro-izquierda y por encima
# de los subtítulos, lejos del rectángulo de la rueda (x >= 0,108). Con margen para que respire y gesticule.
CARA_EN_PANTALLA = {"general": (-0.10, 0.20), "pecho": (-0.22, 0.10), "primer_plano": (-0.26, 0.06),
                    "contraplano": (-0.20, 0.08)}
LATERAL_GENERAL, ATRAS_GENERAL, ALTO_GENERAL = 0.8, 2.0, 0.4     # m respecto al punto medio entre los dos
PECHO_LEJOS = 1.75               # m de la cámara de pecho a quien habla (si cabe)
PECHO_DELANTE = 0.22             # m que la cámara de pecho queda por delante de la cabeza del jugador (su hombro detrás)


def _sum(a, b):
    return tuple(a[i] + b[i] for i in range(3))


def _esc(a, k):
    return tuple(c * k for c in a)


def _horizontal(desde, hacia):
    """Vector unitario horizontal de `desde` a `hacia` (x, z) -> (dx, 0, dz)."""
    dx, dz = hacia[0] - desde[0], hacia[2] - desde[2]
    n = math.hypot(dx, dz) or 1.0
    return (dx / n, 0.0, dz / n)


def _derecha(adelante):
    """Derecha de quien mira hacia `adelante` (convención de rumbo: 0 = +z, 90 = +x)."""
    return (adelante[2], 0.0, -adelante[0])


def toma(plano, hablante, jugador, lateral=2.6):
    """Toma del `plano` con la cabeza de quien habla en `hablante` y la del jugador en `jugador` (x, y, z).
    Toda toma se ENCUADRA para que la cara de quien habla caiga en CARA_EN_PANTALLA[plano] (centro-izquierda): el tercio
    derecho queda libre para la rueda de opciones, que va siempre en el mismo sitio (rueda_calculos.CENTRO_FIJO)."""
    hacia_jugador = _horizontal(hablante, jugador)
    hacia_hablante = _esc(hacia_jugador, -1.0)
    der = _derecha(hacia_hablante)              # derecha del jugador (mirando a quien habla)
    medio = tuple((hablante[i] + jugador[i]) / 2 for i in range(3))
    if plano == "primer_plano":
        # algo baja: con la cabeza gacha (nervioso, triste) se sigue viendo el rostro, y la boca queda por encima de
        # la caja de subtítulos
        pos = _sum(_sum(_sum(hablante, _esc(hacia_jugador, 1.2)), _esc(der, 0.16)), (0.0, -0.14, 0.0))
    elif plano == "pecho":
        # La cámara nunca pasa del plano de la cabeza del jugador (queda PECHO_DELANTE por delante): en la sala los
        # asientos están a 1,64 m y con 1,75 fijos quedaba 11 cm DETRÁS de su cabeza, con el hombro pegado al objetivo
        # (un tercio del cuadro). Si se acerca, abre el fov en proporción: la cara sale del mismo tamaño.
        d_hj = math.hypot(jugador[0] - hablante[0], jugador[2] - hablante[2])
        lejos = max(MIN_A_CABEZA, min(PECHO_LEJOS, d_hj - PECHO_DELANTE))
        pos = _sum(_sum(_sum(hablante, _esc(hacia_jugador, lejos)), _esc(der, 0.34)), (0.0, 0.04, 0.0))
        fov = 2 * math.degrees(math.atan(math.tan(math.radians(FOV["pecho"] / 2)) * PECHO_LEJOS / lejos))
        base = {"position": pos, "target": hablante, "fov": fov}
        return encuadrar(base, hablante, CARA_EN_PANTALLA[plano])
    elif plano == "contraplano":
        # sobre el hombro derecho del jugador: su nuca asoma por el borde izquierdo (antes ocupaba un tercio)
        pos = _sum(_sum(_sum(jugador, _esc(hacia_hablante, -0.78)), _esc(der, 0.48)), (0.0, 0.18, 0.0))
    else:
        plano = "general"
        # abierta, desde detrás y a la derecha del jugador, algo alta: él de espaldas a la izquierda, la mesa y quien
        # habla en el centro-izquierda (antes era de lado y el jugador quedaba a la derecha, debajo de la rueda)
        pos = _sum(_sum(_sum(medio, _esc(der, min(lateral, LATERAL_GENERAL))), _esc(hacia_hablante, -ATRAS_GENERAL)),
                   (0.0, ALTO_GENERAL, 0.0))
    base = {"position": pos, "target": hablante, "fov": FOV[plano]}
    return encuadrar(base, hablante, CARA_EN_PANTALLA[plano])


def elegir_plano(tipo, plano_nodo, primero_en_sala, tras_eleccion, anterior=None):
    """Plano para un nodo: el del JSON si viene; si no, según el momento."""
    if plano_nodo in PLANOS:
        return plano_nodo
    if primero_en_sala:
        return "general"
    if tipo in ("rueda", "acusacion"):
        return "contraplano" if anterior == "primer_plano" else "pecho"     # al volver de una respuesta: sobre el hombro
    if tras_eleccion:
        return "primer_plano"
    return "contraplano" if anterior == "pecho" else "pecho"


def toma_laboratorio(origen, ancho, fondo):
    """Toma alta y abierta del laboratorio, en corte (la pared sur no se dibuja): desde fuera, por encima."""
    ox, oz = origen
    return {"position": (ox, 4.1, oz - fondo / 2 - 2.6), "target": (ox, 0.6, oz + 0.4), "fov": 60.0}


def toma_seguir(jugador, origen, fondo, alto=3.9, fuera=2.4):
    """Cámara del laboratorio que acompaña al jugador: alta, desde fuera de la pared sur (corte), mirándolo."""
    x, z = jugador
    ox, oz = origen
    return {"position": (x * 0.6 + ox * 0.4, alto, oz - fondo / 2 - fuera), "target": (x, 0.8, z + 0.5),
            "fov": 58.0}


def toma_terminal(pantalla, alejar=1.15):
    """Toma sobre el hombro del jugador sentado al terminal (mira el monitor)."""
    c, n = pantalla["centro"], pantalla["normal"]
    pos = (c[0] + n[0] * alejar + 0.32, c[1] + 0.16, c[2] + n[2] * alejar)
    return {"position": pos, "target": c, "fov": 44.0}


def toma_dentro_pantalla(pantalla):
    """La cámara pegada al monitor (lo llena: entrada al servidor)."""
    c, n = pantalla["centro"], pantalla["normal"]
    d = pantalla["alto"] / 2 / math.tan(math.radians(30.0 / 2)) * 0.62
    return {"position": (c[0] + n[0] * d, c[1], c[2] + n[2] * d), "target": c, "fov": 30.0}


def suave(k):
    k = min(1.0, max(0.0, k))
    return k * k * (3 - 2 * k)


def interpolar(a, b, k):
    return {"position": tuple(a["position"][i] + (b["position"][i] - a["position"][i]) * k for i in range(3)),
            "target": tuple(a["target"][i] + (b["target"][i] - a["target"][i]) * k for i in range(3)),
            "fov": a["fov"] + (b["fov"] - a["fov"]) * k}


SEGUIR_K = 2.5                   # 1/s: rapidez con que la cámara acompaña a la cara (llega al 90 % en ~0,9 s)


def seguir_paso(dt, rapidez=SEGUIR_K):
    """Fracción (0..1) que se acerca a la toma viva en `dt` segundos (amortiguado: igual a cualquier fps)."""
    return 1.0 - math.exp(-max(0.0, dt) * rapidez)


def con_deriva(t, toma_base, amplitud=DERIVA):
    """La toma con un vaivén lento (la cámara «respira»). amplitud 0 = igual."""
    if amplitud <= 0:
        return toma_base
    dx = math.sin(t * 0.53) * amplitud
    dy = math.sin(t * 0.37 + 1.3) * amplitud * 0.6
    p = toma_base["position"]
    return {"position": (p[0] + dx, p[1] + dy, p[2]), "target": toma_base["target"], "fov": toma_base["fov"]}


def distancia(a, b):
    return math.sqrt(sum((a[i] - b[i]) ** 2 for i in range(3)))


# -- Proyección y encuadre (misma convención que Ursina/Panda: fov HORIZONTAL, sin alabeo) --

ASPECTO = 16 / 9


def _base(posicion, objetivo):
    """(adelante, derecha, arriba) de una cámara en `posicion` que mira a `objetivo` (sin alabeo)."""
    pitch, yaw = rotacion_mirando(posicion, objetivo)
    return _base_angulos(pitch, yaw)


def _base_angulos(pitch, yaw):
    p, y = math.radians(pitch), math.radians(yaw)
    f = (math.sin(y) * math.cos(p), -math.sin(p), math.cos(y) * math.cos(p))
    r = (math.cos(y), 0.0, -math.sin(y))
    u = (f[1] * r[2] - f[2] * r[1], f[2] * r[0] - f[0] * r[2], f[0] * r[1] - f[1] * r[0])
    return f, r, u


def proyectar(t, punto, aspecto=ASPECTO):
    """(x, y) en camera.ui de un punto del mundo visto por la toma `t`, o None si queda detrás de la cámara.
    camera.ui va de -aspecto/2 a aspecto/2 en x y de -0,5 a 0,5 en y (como camaras.a_ui)."""
    f, r, u = _base(t["position"], t["target"])
    d = tuple(punto[i] - t["position"][i] for i in range(3))
    zc = sum(d[i] * f[i] for i in range(3))
    if zc <= 1e-6:
        return None
    th = math.tan(math.radians(t["fov"]) / 2)
    nx = sum(d[i] * r[i] for i in range(3)) / (zc * th)
    ny = sum(d[i] * u[i] for i in range(3)) / (zc * th / aspecto)
    return nx * aspecto / 2, ny / 2


def radio_en_pantalla(t, punto, radio_m, aspecto=ASPECTO):
    """Radio en unidades de camera.ui de una esfera de `radio_m` metros en `punto` (aprox. de lente fina)."""
    f, _, _ = _base(t["position"], t["target"])
    zc = sum((punto[i] - t["position"][i]) * f[i] for i in range(3))
    if zc <= 1e-6:
        return None
    th = math.tan(math.radians(t["fov"]) / 2)
    return radio_m / (zc * th) * aspecto / 2


def encuadrar(t, punto, objetivo_ui, aspecto=ASPECTO, iteraciones=10):
    """La toma `t` girada (misma posición y fov) para que `punto` caiga en `objetivo_ui` (x, y de camera.ui)."""
    pos = t["position"]
    pitch, yaw = rotacion_mirando(pos, punto)
    th = math.tan(math.radians(t["fov"]) / 2)
    tv = th / aspecto
    ox, oy = objetivo_ui[0] * 2 / aspecto, objetivo_ui[1] * 2       # en coordenadas normalizadas (-1..1)
    for _ in range(iteraciones):
        f, _, _ = _base_angulos(pitch, yaw)
        prueba = {"position": pos, "target": tuple(pos[i] + f[i] for i in range(3)), "fov": t["fov"]}
        p = proyectar(prueba, punto, aspecto)
        if p is None:
            break
        nx, ny = p[0] * 2 / aspecto, p[1] * 2
        if abs(nx - ox) < 1e-5 and abs(ny - oy) < 1e-5:
            break
        yaw += math.degrees(math.atan(nx * th) - math.atan(ox * th))
        pitch -= math.degrees(math.atan(ny * tv) - math.atan(oy * tv))
    f, _, _ = _base_angulos(pitch, yaw)
    lejos = max(1.0, distancia(pos, punto))
    return {"position": tuple(pos), "target": tuple(pos[i] + f[i] * lejos for i in range(3)), "fov": t["fov"]}


def rotacion_mirando(posicion, objetivo):
    dx, dy, dz = (objetivo[i] - posicion[i] for i in range(3))
    yaw = math.degrees(math.atan2(dx, dz))
    pitch = -math.degrees(math.atan2(dy, math.hypot(dx, dz)))
    return pitch, yaw
