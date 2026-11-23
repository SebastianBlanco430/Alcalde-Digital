# Cálculos puros de la familia PC de los minijuegos 3D (Chat del barrio y Contrarreloj). NO importa ursina ni panda3d.
#
#   - Toma «sobre el hombro» propia de la familia: cámara detrás y a la derecha del personaje sentado, por encima de su
#     cabeza, mirando el monitor. La DISTANCIA se resuelve para que el monitor ocupe exactamente `fraccion` del alto de la
#     ventana (legibilidad: nunca se achica el texto; si no llega, se acerca la cámara). Se ven la nuca con el pelo y el
#     hombro abajo a la izquierda, sin tapar la zona de contenido de la vista 2D (y de la UI > -0,30).
#   - Toma de ENTRADA/SALIDA: más abierta y más alta, con la mano sobre el ratón claro del escritorio a la vista.
#   - Ratón del escritorio: dónde está el ratón (y la mano) según la posición del puntero sobre el monitor (u, v).
#   - Teclado: dónde cae cada tecla de respuesta (para el resaltado de la tecla pulsada).
#   - Salida: reclinarse un instante y levantarse (fases y curvas), y cuándo se enseña el banner de siempre.
#
# Coordenadas de MUNDO (las del set: la oficina está en el origen sin rotar; +y arriba; el monitor mira a -z).
# Una TOMA es {"position", "target", "fov"} con fov HORIZONTAL (como camaras_calculos).

import math

# -- Proyección (misma convención que la cámara de Ursina: fov horizontal, aspecto ancho/alto) --


def _resta(a, b):
    return tuple(a[i] - b[i] for i in range(3))


def _suma(a, b):
    return tuple(a[i] + b[i] for i in range(3))


def _esc(a, k):
    return tuple(c * k for c in a)


def _punto(a, b):
    return sum(a[i] * b[i] for i in range(3))


def _cruz(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _unit(a):
    n = math.sqrt(_punto(a, a)) or 1.0
    return _esc(a, 1.0 / n)


def proyectar(toma, aspecto, punto):
    """NDC (x, y) en [-1, 1] de `punto` visto desde `toma`, o None si queda detrás de la cámara."""
    p, t = toma["position"], toma["target"]
    f = _unit(_resta(t, p))
    r = _unit(_cruz((0.0, 1.0, 0.0), f))
    u = _cruz(f, r)
    d = _resta(punto, p)
    z = _punto(d, f)
    if z <= 1e-4:
        return None
    th = math.tan(math.radians(toma["fov"]) / 2)
    return (_punto(d, r) / z / th, _punto(d, u) / z / (th / aspecto))


def punto_monitor(monitor, x_ui, y_ui, aspecto_ui=16 / 9):
    """Punto de mundo del monitor donde se ve (x_ui, y_ui) de la vista 2D (x en [-aspecto/2, aspecto/2], y en [-.5, .5])."""
    arriba = _unit(monitor["arriba"])
    derecha = _esc(_unit(_cruz(arriba, _unit(monitor["normal"]))), -1.0)
    return _suma(_suma(monitor["centro"], _esc(derecha, x_ui / aspecto_ui * monitor["ancho"])),
                 _esc(arriba, y_ui * monitor["alto"]))


def fraccion_monitor(toma, monitor, aspecto, x_ui=0.0):
    """Fracción del alto de la ventana que ocupa el monitor (medida en la vertical x_ui de la vista 2D)."""
    a = proyectar(toma, aspecto, punto_monitor(monitor, x_ui, -0.5))
    b = proyectar(toma, aspecto, punto_monitor(monitor, x_ui, 0.5))
    if a is None or b is None:
        return 0.0
    return (b[1] - a[1]) / 2


def esquinas_monitor(toma, monitor, aspecto):
    """NDC de las 4 esquinas del monitor (o None si alguna queda detrás)."""
    out = []
    for x in (-8 / 9, 8 / 9):
        for y in (-0.5, 0.5):
            q = proyectar(toma, aspecto, punto_monitor(monitor, x, y))
            if q is None:
                return None
            out.append(q)
    return out


# -- Toma sobre el hombro de la familia PC --

# Sesgo (grados a la derecha del eje del monitor), elevación (grados por encima) de la dirección de la cámara vista desde el
# punto mirado, punto mirado desplazado sobre la cara del monitor (m) y FOV horizontal. La distancia sale de la fracción.
# Elegida en ventana (rework-3d/familia-pc/busqueda_toma2.py + capturas de exploración): teleobjetivo (FOV 24) desde detrás
# y a la derecha del personaje, casi a la altura de su cabeza: nuca, pelo y oreja a la izquierda, hombro abajo a la izquierda,
# el monitor a la derecha sin que nada del cuerpo tape la zona de contenido de la vista 2D.
HOMBRO_PC = {"sesgo": 26.0, "elevacion": 5.0, "mirar_x": -0.06, "mirar_y": -0.03, "fov": 24.0}
# brasilena.glb (influencer) lleva un afro de ~0,28 m de radio: más de lado para que no tape el contenido.
HOMBRO_PC_POR_ROL = {"influencer": {"sesgo": 32.0, "elevacion": 3.0, "mirar_x": -0.08, "mirar_y": -0.03, "fov": 22.0}}
# Alto del monitor / alto de la ventana. El diseño pedía ~60 %; con el ratón del escritorio a la vista el monitor no puede
# pasar de ~0,55-0,61 (el ratón está 0,17 m por debajo del borde inferior de la pantalla y 0,4 m por delante: ver informe)
# y el texto de CONTENIDO de la vista 2D (respuestas, mensajes, cartas) no llega a 14 px a 720p por debajo de ~0,68; con
# 0,78 pasan además las etiquetas medianas (RUMOR, cabecera del chat, LLEGÓ AL BARRIO, barrios del mapa grandes). Medido en
# ventana: rework-3d/familia-pc/informe.md. Manda la legibilidad.
FRACCION_PC = 0.78


def parametros_hombro(rol=None):
    return dict(HOMBRO_PC_POR_ROL.get(rol, HOMBRO_PC))


def _direccion(monitor, sesgo, elevacion):
    """Dirección unitaria desde el monitor hacia la cámara: la normal girada `sesgo` grados a la derecha y `elevacion` arriba."""
    n = _unit(monitor["normal"])
    arriba = _unit(monitor["arriba"])
    derecha = _esc(_unit(_cruz(arriba, n)), -1.0)
    s, e = math.radians(sesgo), math.radians(elevacion)
    horizontal = _suma(_esc(n, math.cos(s)), _esc(derecha, math.sin(s)))
    return _unit(_suma(_esc(horizontal, math.cos(e)), _esc(arriba, math.sin(e))))


def toma_hombro(monitor, aspecto, fraccion=FRACCION_PC, rol=None, parametros=None):
    """Toma sobre el hombro con el monitor ocupando `fraccion` del alto de la ventana (resuelto por bisección sobre la
    distancia; la vertical medida es la central de la vista 2D)."""
    h = parametros or parametros_hombro(rol)
    arriba = _unit(monitor["arriba"])
    derecha = _esc(_unit(_cruz(arriba, _unit(monitor["normal"]))), -1.0)
    objetivo = _suma(_suma(monitor["centro"], _esc(derecha, h["mirar_x"])), _esc(arriba, h["mirar_y"]))
    d = _direccion(monitor, h["sesgo"], h["elevacion"])

    def toma_a(dist):
        return {"position": _suma(objetivo, _esc(d, dist)), "target": objetivo, "fov": h["fov"]}

    cerca, lejos = 0.05, 20.0                  # la fracción baja al alejarse
    for _ in range(60):
        medio = (cerca + lejos) / 2
        if fraccion_monitor(toma_a(medio), monitor, aspecto) > fraccion:
            cerca = medio
        else:
            lejos = medio
    return toma_a((cerca + lejos) / 2)


# Salida: más abierta, por detrás y a la derecha, con el personaje entero, la silla y el escritorio (ratón y teclado) a la vista.
SALIDA_PC = {"sesgo": 18.0, "elevacion": 12.0, "mirar_x": -0.15, "mirar_y": -0.12, "fov": 64.0, "fraccion": 0.18}


def toma_abierta(monitor, aspecto, datos):
    p = {k: datos[k] for k in ("sesgo", "elevacion", "mirar_x", "mirar_y", "fov")}
    return toma_hombro(monitor, aspecto, datos["fraccion"], parametros=p)


# -- Entrada: tras la cinemática de sentarse (que acaba con el monitor llenando la pantalla) y la pantalla previa --
# La cámara arranca con el monitor llenando la pantalla, en el MISMO eje que la toma de juego, y retrocede en línea recta
# (travelling: mismo punto mirado y mismo fov), todo él por detrás del personaje (con el FOV 24 de la toma, el monitor al
# 96 % queda a ~1,65 m): no gira ni pasa por delante de la cara. (Arrancar en «acercar_fin» de la cinemática, de frente,
# obligaba a cruzar por delante de la cara y del brazo: visto en rework-3d/capturas/chat/flujo2/flujo_c_000.png.)

FRACCION_ENTRADA = 0.96


def toma_entrada(monitor, aspecto, rol=None, parametros=None):
    return toma_hombro(monitor, aspecto, FRACCION_ENTRADA, rol=rol, parametros=parametros)


# -- Ratón del escritorio --

# El ratón claro se mueve en la mesa lo que haga falta para recorrer el monitor (ancho x fondo, m). Rango corto: no choca con
# el teclado (a la izquierda) ni con el libro que tapa el ratón oscuro de la oficina (a la derecha, al fondo).
RANGO_RATON = (0.055, 0.04)
MANO_SOBRE_RATON = (0.0, 0.045, -0.065)     # muñeca respecto al centro del ratón: la palma y los dedos quedan encima


def desplazamiento_raton(u, v):
    """(dx, dz) del ratón en la mesa (m) para el puntero en (u, v) del monitor (0..1; None = sin puntero -> centro).
    Derecha en el monitor = derecha en la mesa; arriba en el monitor = hacia el fondo de la mesa (como un ratón real)."""
    if u is None or v is None:
        return (0.0, 0.0)
    u = min(1.0, max(0.0, u))
    v = min(1.0, max(0.0, v))
    return ((u - 0.5) * RANGO_RATON[0], (v - 0.5) * RANGO_RATON[1])


def posicion_mano(centro_raton):
    return _suma(centro_raton, MANO_SOBRE_RATON)


# Pulsación del botón del ratón (el «clic» que se ve): baja y sube en DURACION_CLIC_RATON s.
DURACION_CLIC_RATON = 0.16
HUNDIDO_BOTON = 0.004                        # m que baja el botón del ratón
HUNDIDO_MANO_CLIC = 0.012                    # m extra que baja la mano en el clic (sobre el gesto de poses_3d)


def curva_pulso(t, duracion):
    """0 -> 1 -> 0 en `duracion` s (fuera de [0, duracion]: 0)."""
    if t <= 0 or t >= duracion:
        return 0.0
    return math.sin(math.pi * t / duracion)


# -- Teclado --

# Posición (x, z) en el teclado (m, centro del teclado; +x derecha, +z hacia el fondo) de las teclas que usan los minijuegos.
ANCHO_TECLA = 0.018
_FILAS = {"num": 0.05, "q": 0.03, "a": 0.01, "z": -0.01, "esp": -0.04}
TECLAS = {
    "1": (-0.19, _FILAS["num"]), "2": (-0.17, _FILAS["num"]), "3": (-0.15, _FILAS["num"]),
    "w": (-0.165, _FILAS["q"]), "a": (-0.18, _FILAS["a"]), "s": (-0.16, _FILAS["a"]), "d": (-0.14, _FILAS["a"]),
    "f": (-0.12, _FILAS["a"]), "tab": (-0.205, _FILAS["q"]),
    "space": (-0.06, _FILAS["esp"]), "enter": (0.135, _FILAS["a"]), "return": (0.135, _FILAS["a"]),
    "backspace": (0.13, _FILAS["num"]),
    "up arrow": (0.185, -0.025), "down arrow": (0.185, -0.045), "left arrow": (0.165, -0.045),
    "right arrow": (0.205, -0.045),
}


def tecla_en_teclado(k):
    """(x, z) de la tecla `k` sobre el teclado, o None si no es una tecla que se vea (mouse, mando, soltar...)."""
    if not isinstance(k, str) or k.endswith(" up"):
        return None
    return TECLAS.get(k)


# -- Salida: se reclina un instante y se levanta; después, el banner de siempre --

DURACION_RECLINAR = 0.5
DURACION_PAUSA = 0.2
DURACION_LEVANTAR = 0.75
DURACION_SALIDA = DURACION_RECLINAR + DURACION_PAUSA + DURACION_LEVANTAR
RECLINE_GRADOS = 16.0                         # el torso se echa hacia atrás
SUBIDA = 0.40                                 # m que sube el cuerpo al levantarse (sentado baja 0,45: queda casi de pie)
RETROCESO = 0.12                              # m que se aparta del escritorio al levantarse


def _suave(k):
    k = min(1.0, max(0.0, k))
    return k * k * (3 - 2 * k)


def salida(t):
    """Estado de la animación de salida a los `t` s: {"fase", "reclinar" (grados), "subida" (m), "retroceso" (m),
    "banner" (bool: ya se enseña el banner de siempre)}."""
    if t < DURACION_RECLINAR:
        k = _suave(t / DURACION_RECLINAR)
        return {"fase": "reclinar", "reclinar": RECLINE_GRADOS * k, "subida": 0.0, "retroceso": 0.0, "banner": False}
    t2 = t - DURACION_RECLINAR
    if t2 < DURACION_PAUSA:
        return {"fase": "pausa", "reclinar": RECLINE_GRADOS, "subida": 0.0, "retroceso": 0.0, "banner": False}
    t3 = t2 - DURACION_PAUSA
    k = _suave(t3 / DURACION_LEVANTAR)
    fin = t3 >= DURACION_LEVANTAR
    # al levantarse primero se inclina hacia delante (el peso sobre los pies) y termina erguido
    inclinacion = RECLINE_GRADOS * (1 - k) - 14.0 * math.sin(math.pi * k)
    return {"fase": "de_pie" if fin else "levantar", "reclinar": 0.0 if fin else inclinacion, "subida": SUBIDA * k,
            "retroceso": RETROCESO * k, "banner": fin}


def compensar_pivote(grados, altura_pivote):
    """(dy, dz) que hay que sumar a un cuerpo que gira `grados` alrededor del eje x de su origen para que el giro sea
    alrededor de un punto a `altura_pivote` m sobre el origen (la cadera): así se reclina sin despegarse del asiento.
    Convención de Ursina: rotation_x positivo inclina hacia delante (+z arriba)."""
    a = math.radians(grados)
    # punto del pivote (0, h, 0) girado: (0, h cos a, h sin a) con +a hacia delante
    return (altura_pivote - altura_pivote * math.cos(a), -altura_pivote * math.sin(a))
