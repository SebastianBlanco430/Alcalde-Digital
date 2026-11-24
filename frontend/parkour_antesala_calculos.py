# Antesala del PARKOUR: el «terminal del servidor» donde el protagonista se sienta y entra en la pantalla antes del nivel
# (sesión B, Módulo 4). Python PURO (no importa ursina): geometría del cuartito, descriptores de la silla, la mesa y la
# pantalla para frontend/cinematica_silla.py, y las tomas de cámara. La vista está en frontend/parkour_antesala.py.
#
# Coordenadas: metros. Todo se define en LOCAL (el suelo del cuarto en y = 0, el centro del cuarto en x = z = 0, el
# sentado mira a +z) y se pasa a MUNDO sumando ORIGEN (la antesala cuelga de la escena del parkour, que está en el
# origen sin rotar; el nivel se oculta mientras se ve la antesala y el cuarto está bajo el nivel por si acaso).
#
# Reglas que comprueban los tests (tests/test_parkour_antesala_calculos.py):
#   - la silla acomodada no toca la mesa (ni el tablero ni las patas) y su frente no pasa de Mesa.borde;
#   - con la silla retirada (`retiro`) el respaldo no atraviesa la pared de atrás y el punto de partida está dentro;
#   - la toma de la sala encuadra silla, mesa, monitor y el punto de partida y está dentro del cuarto con margen;
#   - la toma de la pantalla hace que el monitor llene TODA la vista (para cualquier aspecto razonable).

import math

ORIGEN = (0.0, -60.0, 0.0)        # el cuarto, en mundo (bajo cualquier nivel: el nivel se oculta de todas formas)

ANCHO, FONDO, ALTO = 4.0, 4.8, 2.7       # x en [-2.0, 2.0], z en [-2.4, 2.4]
GROSOR_PARED = 0.1
MARGEN_CAMARA = 0.15                     # m de las paredes (guion.md: cámara dentro de la sala con 0,15 m)

MESA_ALTURA = 0.75                       # y de la cara de arriba del tablero
MESA_TABLERO = (1.3, 0.9)                # ancho (x) y fondo (z): mesa honda, el monitor al fondo (ver PANTALLA_CENTRO)
MESA_GROSOR = 0.04
MESA_Z = FONDO / 2 - 0.06 - MESA_TABLERO[1] / 2     # centro del tablero (pegada a la pared del fondo)
PATA = 0.05

SILLA_POS = (0.0, MESA_Z - MESA_TABLERO[1] / 2 - 0.35)   # centro del asiento acomodada (x, z): 0,35 m del canto
SILLA_RUMBO = 0.0
SILLA_ASIENTO = 0.45
SILLA_RESPALDO = 0.95
SILLA_RETIRO = 0.45
SILLA_LADO = "i"
SILLA_MEDIO = 0.23                       # m: medio ancho/fondo del asiento (la silla estándar de crear_silla)

# Pantalla de 0,48 m al fondo de la mesa: a ~1,1 m de la cabeza del sentado, cinematica_silla la llena con fov ~41 (con un
# monitor más grande o más cerca abre el fov hasta 75 para no meter la cámara en la cabeza).
PANTALLA_ANCHO, PANTALLA_ALTO = 0.48, 0.27
PANTALLA_CENTRO = (0.0, 1.13, MESA_Z + 0.33)      # cara de la pantalla (mira a -z, hacia la silla)
TECLADO = (0.0, MESA_ALTURA + 0.012, MESA_Z - MESA_TABLERO[1] / 2 + 0.17)
TECLADO_ESCALA = (0.44, 0.02, 0.14)
MANOS_Y = MESA_ALTURA + 0.04             # nunca por debajo del tablero + 2 cm (guion.md)

FOV_SALA = 60.0
FOV_PANTALLA = 40.0                      # guion.md: la cámara entra en la pantalla con fov -> 40
LLENADO = 0.94                           # < 1: la pantalla sobra un 6 % por cada lado (llena aunque redondee)


# -- Utilidades --

def mundo(p):
    """Punto local (x, y, z) -> mundo."""
    return (p[0] + ORIGEN[0], p[1] + ORIGEN[1], p[2] + ORIGEN[2])


def mundo_xz(p):
    return (p[0] + ORIGEN[0], p[1] + ORIGEN[2])


def suelo_y():
    return ORIGEN[1]


def limites():
    """(x_min, x_max, z_min, z_max) INTERIORES del cuarto en mundo."""
    return (ORIGEN[0] - ANCHO / 2, ORIGEN[0] + ANCHO / 2, ORIGEN[2] - FONDO / 2, ORIGEN[2] + FONDO / 2)


def _resta(a, b):
    return tuple(a[i] - b[i] for i in range(3))


def _punto(a, b):
    return sum(a[i] * b[i] for i in range(3))


def _cruz(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _norm(a):
    n = math.sqrt(_punto(a, a)) or 1.0
    return tuple(c / n for c in a)


def fov_vertical(fov_h, aspecto):
    return math.degrees(2 * math.atan(math.tan(math.radians(fov_h) / 2) / aspecto))


# -- Descriptores para cinematica_silla (kwargs de Silla / Mesa; la vista los convierte) --

def datos_silla():
    return {"posicion": mundo_xz(SILLA_POS), "rumbo": SILLA_RUMBO, "altura_asiento": SILLA_ASIENTO,
            "altura_respaldo": SILLA_RESPALDO, "retiro": SILLA_RETIRO, "lado": SILLA_LADO, "suelo_y": suelo_y()}


def borde_mesa():
    """m desde el centro del asiento (acomodada) hasta el canto cercano del tablero, a lo largo del rumbo (+z)."""
    return (MESA_Z - MESA_TABLERO[1] / 2) - SILLA_POS[1]


def datos_mesa():
    x, _, z = TECLADO
    manos = {"i": mundo((x - 0.13, MANOS_Y, z)), "d": mundo((x + 0.13, MANOS_Y, z))}
    return {"altura": MESA_ALTURA + ORIGEN[1], "borde": borde_mesa(), "manos": manos}


def pantalla():
    """{"centro", "normal", "arriba", "alto", "ancho"} en mundo (como Ancla.datos_toma())."""
    return {"centro": mundo(PANTALLA_CENTRO), "normal": (0.0, 0.0, -1.0), "arriba": (0.0, 1.0, 0.0),
            "frente": (0.0, -1.0, 0.0), "alto": PANTALLA_ALTO, "ancho": PANTALLA_ANCHO}


def punto_de_partida():
    """(x, z, rumbo) en mundo: 1,2 m detrás y 0,55 m al lado (`lado`) del asiento, mirando hacia el respaldo
    (guion.md). Respaldo de cinematica_silla.punto_de_partida si el módulo no responde."""
    lado = -1.0 if SILLA_LADO == "i" else 1.0          # rumbo 0: la izquierda del sentado es -x
    x, z = SILLA_POS[0] + 0.55 * lado, SILLA_POS[1] - 1.2
    rumbo = math.degrees(math.atan2(SILLA_POS[0] - x, SILLA_POS[1] - z))
    return (x + ORIGEN[0], z + ORIGEN[2], rumbo)


# -- Piezas (cajas) del cuarto en LOCAL: (nombre, centro, escala, color RGB, propia_luz) --
# propia_luz = True: neón sin iluminación (como las plataformas del parkour).

PARED = (30, 34, 60)
SUELO = (20, 20, 38)
TECHO = (14, 14, 28)
MESA = (40, 44, 62)
PATAS = (24, 26, 38)
MONITOR = (14, 15, 22)
TECLADO_COLOR = (30, 32, 44)
SILLA_COLOR = (52, 56, 74)
CIAN = (70, 230, 255)
MAGENTA = (255, 70, 200)
PANTALLA_FONDO = (8, 20, 34)


def piezas_cuarto():
    a, f, h, g = ANCHO, FONDO, ALTO, GROSOR_PARED
    p = [
        ("suelo", (0, -0.05, 0), (a + 2 * g, 0.1, f + 2 * g), SUELO, False),
        ("techo", (0, h + 0.05, 0), (a + 2 * g, 0.1, f + 2 * g), TECHO, False),
        ("pared_fondo", (0, h / 2, f / 2 + g / 2), (a + 2 * g, h, g), PARED, False),
        ("pared_atras", (0, h / 2, -f / 2 - g / 2), (a + 2 * g, h, g), PARED, False),
        ("pared_izq", (-a / 2 - g / 2, h / 2, 0), (g, h, f), PARED, False),
        ("pared_der", (a / 2 + g / 2, h / 2, 0), (g, h, f), PARED, False),
    ]
    # Franjas de neón (zócalo cian y línea magenta alta) en las cuatro paredes: la estética del sector.
    for nombre, y, alto_franja, tono in (("zocalo", 0.06, 0.03, CIAN), ("friso", 2.1, 0.02, MAGENTA)):
        p += [(f"{nombre}_fondo", (0, y, f / 2 - 0.006), (a, alto_franja, 0.01), tono, True),
              (f"{nombre}_atras", (0, y, -f / 2 + 0.006), (a, alto_franja, 0.01), tono, True),
              (f"{nombre}_izq", (-a / 2 + 0.006, y, 0), (0.01, alto_franja, f), tono, True),
              (f"{nombre}_der", (a / 2 - 0.006, y, 0), (0.01, alto_franja, f), tono, True)]
    return p


def piezas_mesa():
    ancho, fondo = MESA_TABLERO
    y = MESA_ALTURA
    p = [("tablero", (0, y - MESA_GROSOR / 2, MESA_Z), (ancho, MESA_GROSOR, fondo), MESA, False),
         ("canto", (0, y - MESA_GROSOR - 0.005, MESA_Z - fondo / 2 + 0.005), (ancho, 0.01, 0.01), CIAN, True)]
    alto_pata = y - MESA_GROSOR
    for dx in (-ancho / 2 + PATA, ancho / 2 - PATA):
        for dz in (-fondo / 2 + PATA, fondo / 2 - PATA):
            p.append(("pata", (dx, alto_pata / 2, MESA_Z + dz), (PATA, alto_pata, PATA), PATAS, False))
    cx, cy, cz = PANTALLA_CENTRO
    p += [("monitor", (cx, cy, cz + 0.025), (PANTALLA_ANCHO + 0.05, PANTALLA_ALTO + 0.05, 0.04), MONITOR, False),
          ("pie_monitor", (cx, (y + cy - PANTALLA_ALTO / 2) / 2, cz + 0.06), (0.05, cy - PANTALLA_ALTO / 2 - y, 0.04),
           MONITOR, False),
          ("base_monitor", (cx, y + 0.008, cz + 0.06), (0.24, 0.016, 0.16), MONITOR, False),
          ("teclado", TECLADO, TECLADO_ESCALA, TECLADO_COLOR, False)]
    return p


def partes_silla(posicion_local=SILLA_POS):
    """Cajas de la silla estándar (respaldo de la silla propia si cinematica_silla.crear_silla no está): asiento,
    respaldo (detrás del asiento, contra el rumbo) y 4 patas. Relativas al suelo bajo el centro del asiento."""
    m = SILLA_MEDIO
    a = SILLA_ASIENTO
    partes = [("asiento", (0, a - 0.03, 0), (2 * m, 0.06, 2 * m)),
              ("respaldo", (0, (a + SILLA_RESPALDO) / 2, -m + 0.02), (2 * m, SILLA_RESPALDO - a, 0.04))]
    for dx in (-m + 0.03, m - 0.03):
        for dz in (-m + 0.03, m - 0.03):
            partes.append(("pata", (dx, (a - 0.06) / 2, dz), (0.035, a - 0.06, 0.035)))
    x, z = posicion_local
    return [(n, (c[0] + x, c[1], c[2] + z), e) for n, c, e in partes]


def caja(centro, escala):
    """AABB ((x0, y0, z0), (x1, y1, z1))."""
    return (tuple(centro[i] - escala[i] / 2 for i in range(3)), tuple(centro[i] + escala[i] / 2 for i in range(3)))


def se_tocan(a, b):
    return all(a[0][i] < b[1][i] and b[0][i] < a[1][i] for i in range(3))


# -- Tomas (dicts de camaras_calculos: {"position", "target", "fov" horizontal}) --

def toma_sala():
    """Toma abierta de tres cuartos desde la esquina de atrás a la derecha: encuadra la silla, la mesa, el monitor y
    el punto de partida. Es la toma de llegada (antes de sentarse) y la de salida (tras levantarse)."""
    return {"position": mundo((1.7, 1.75, -2.2)), "target": mundo((-0.25, 0.85, 1.0)), "fov": FOV_SALA}


CABEZA_SENTADO = 1.22            # m: y aproximada del centro de la cabeza sentado (para la distancia mínima de cámara)


def cabeza_sentado():
    return mundo((SILLA_POS[0], CABEZA_SENTADO, SILLA_POS[1] - 0.05))


HOMBRO_LATERAL = {"influencer": 0.85}    # brasilena.glb: el afro (~0,28 m de radio) tapaba media toma con 0,55
RADIO_CABEZA = {"influencer": 0.30}


def toma_hombro(rol=None):
    """Sobre el hombro derecho del sentado, mirando el monitor: donde termina salir_de_pantalla (aún sentado)."""
    lateral = HOMBRO_LATERAL.get(rol, 0.55)
    return {"position": mundo((lateral, 1.55, SILLA_POS[1] - 0.95)), "target": centro_pantalla(), "fov": 52.0}


def distancia_rayo_cabeza(toma):
    """Distancia mínima del rayo cámara -> objetivo al centro de la cabeza del sentado (¿la cabeza tapa el centro?)."""
    p0, p1, c = toma["position"], toma["target"], cabeza_sentado()
    d = _resta(p1, p0)
    t = max(0.0, min(1.0, _punto(_resta(c, p0), d) / (_punto(d, d) or 1.0)))
    cerca = tuple(p0[i] + d[i] * t for i in range(3))
    return math.dist(cerca, c)


def centro_pantalla():
    return mundo(PANTALLA_CENTRO)


def distancia_llenado(fov_h, aspecto, ancho=PANTALLA_ANCHO, alto=PANTALLA_ALTO, llenado=LLENADO):
    """Distancia a la que la pantalla (ancho x alto) cubre TODA la vista (horizontal y vertical) con `llenado` de margen."""
    th = math.tan(math.radians(fov_h) / 2)
    tv = math.tan(math.radians(fov_vertical(fov_h, aspecto)) / 2)
    return llenado * min((ancho / 2) / th, (alto / 2) / tv)


def toma_pantalla(aspecto, fov=FOV_PANTALLA):
    """Cámara de frente a la pantalla, a la distancia en que la llena entera (el «dentro del servidor»)."""
    p = pantalla()
    d = distancia_llenado(fov, aspecto)
    c, n = p["centro"], p["normal"]
    return {"position": tuple(c[i] + n[i] * d for i in range(3)), "target": c, "fov": fov}


def ejes(toma):
    """(adelante, derecha, arriba) unitarios de una toma (sin alabeo, arriba del mundo = +y; Ursina: x derecha)."""
    f = _norm(_resta(toma["target"], toma["position"]))
    r = _norm(_cruz((0.0, 1.0, 0.0), f))
    u = _cruz(f, r)
    return f, r, u


def proyectar(toma, punto, aspecto):
    """(x, y) normalizados en [-1, 1] si `punto` cae dentro de la vista; None si está detrás de la cámara."""
    f, r, u = ejes(toma)
    v = _resta(punto, toma["position"])
    prof = _punto(v, f)
    if prof <= 1e-6:
        return None
    th = math.tan(math.radians(toma["fov"]) / 2)
    tv = math.tan(math.radians(fov_vertical(toma["fov"], aspecto)) / 2)
    return (_punto(v, r) / (prof * th), _punto(v, u) / (prof * tv))


def en_cuadro(toma, punto, aspecto, margen=0.95):
    p = proyectar(toma, punto, aspecto)
    return p is not None and abs(p[0]) <= margen and abs(p[1]) <= margen


def dentro_del_cuarto(punto, margen=MARGEN_CAMARA):
    x0, x1, z0, z1 = limites()
    y0, y1 = ORIGEN[1], ORIGEN[1] + ALTO
    return (x0 + margen <= punto[0] <= x1 - margen and z0 + margen <= punto[2] <= z1 - margen
            and y0 + margen <= punto[1] <= y1 - margen)


def pantalla_llena_vista(toma, aspecto):
    """True si las 4 esquinas de la vista caen DENTRO del rectángulo de la pantalla (la pantalla tapa todo)."""
    p = pantalla()
    c, n, up = p["centro"], p["normal"], p["arriba"]
    derecha_p = _cruz(up, n)             # en el plano de la pantalla
    f, r, u = ejes(toma)
    th = math.tan(math.radians(toma["fov"]) / 2)
    tv = math.tan(math.radians(fov_vertical(toma["fov"], aspecto)) / 2)
    for sx in (-1, 1):
        for sy in (-1, 1):
            rayo = tuple(f[i] + sx * th * r[i] + sy * tv * u[i] for i in range(3))
            den = _punto(rayo, n)
            if abs(den) < 1e-9:
                return False
            t = _punto(_resta(c, toma["position"]), n) / den
            if t <= 0:
                return False
            golpe = tuple(toma["position"][i] + rayo[i] * t for i in range(3))
            local = _resta(golpe, c)
            if abs(_punto(local, derecha_p)) > p["ancho"] / 2 or abs(_punto(local, up)) > p["alto"] / 2:
                return False
    return True


LETRAS_POR_LINEA = 24              # el nombre del nivel en el monitor (Text.wordwrap no se aplica al cambiar .text)


def partir_lineas(texto, ancho=LETRAS_POR_LINEA, maximo=3):
    """Parte `texto` en líneas de <= `ancho` letras por palabras (una palabra más larga va sola). Máximo `maximo` líneas
    (la última termina en «…» si sobra texto)."""
    lineas, actual = [], ""
    for palabra in str(texto).split():
        if actual and len(actual) + 1 + len(palabra) > ancho:
            lineas.append(actual)
            actual = palabra
        else:
            actual = f"{actual} {palabra}" if actual else palabra
    if actual:
        lineas.append(actual)
    if len(lineas) > maximo:
        lineas = lineas[:maximo]
        lineas[-1] = lineas[-1].rstrip(".,:;") + "…"
    return "\n".join(lineas)


# -- Estado de la antesala en la escena (puro: lo usa EscenaParkour) --

TOPE_ENTRADA = 8.0       # s: si la secuencia no terminó en este tiempo (fallo raro), se fuerza el final
TOPE_SALIDA = 6.0


def quiere_antesala(pedida, bandera_activa, hay_jugador):
    """¿Esta entrada pasa por la antesala? `pedida`: None = automática, False = no (el llamador hizo su animación),
    True = sí si se puede. Con la bandera apagada o sin partida (modo desarrollo) nunca."""
    if pedida is False or not bandera_activa or not hay_jugador:
        return False
    return True


def tapado(alfa_velo):
    """¿El fundido tapa la pantalla? (la secuencia espera debajo del negro, no se la come el fundido)."""
    try:
        return float(alfa_velo) >= 0.999
    except (TypeError, ValueError):
        return False
