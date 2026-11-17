# Cálculos puros del MANDO (Python puro: NO importa ursina, se prueba con pytest sin ventana).
#
# Ursina ya conecta los mandos que ve Panda3D: cada botón llega como una tecla («gamepad a», «gamepad a up», «gamepad dpad up»…) y
# los palos y gatillos quedan en `held_keys` («gamepad left stick x», «gamepad left stick y», «gamepad right stick x/y»,
# «gamepad right trigger»…; arriba = y positivo). Aquí solo se decide QUÉ HACE cada cosa con las reglas del juego:
#
#   MODO MUNDO (el ratón está capturado: se camina, se corre, se salta):
#       palo izquierdo = caminar · palo derecho = girar la cámara · A = saltar (Espacio) · B = interactuar (E)
#       X = reaparecer en el parkour (R) · Y = teléfono (Tab) · Atrás = seguir/dejar la misión (M) · Inicio = pausa (Escape)
#       gatillo derecho o botón RB = correr (Shift) · cruceta = flechas
#   MODO MENÚ (hay cursor: menús, teléfono, minijuegos, diálogos):
#       palo izquierdo = mover el cursor · palo derecho = rueda (listas) · A = clic si hay un botón bajo el cursor, si no Espacio
#       B / Inicio = Escape · X = Enter · Y = Tab · cruceta = flechas · LB / RB = Mayús+Tab / Tab (cambiar de campo)
#
# Los botones del mando NUNCA llegan al juego con su nombre: se traducen a las teclas de siempre, así que cada escena, el
# tutorial, los minijuegos y las pausas funcionan sin saber que existe el mando.

import math

ZONA_MUERTA = 0.22          # por debajo de esto el palo se considera quieto (los palos viejos «tiemblan» ~0.1)
VELOCIDAD_CURSOR = 1.15     # alturas de pantalla por segundo con el palo a fondo (camera.ui: la altura mide 1)
VELOCIDAD_CURSOR_LENTA = 0.35    # con el gatillo izquierdo apretado: puntería fina
GIRO_CAMARA = 140.0         # grados por segundo con el palo derecho a fondo
UMBRAL_GATILLO = 0.45       # el gatillo cuenta como «pulsado» al pasar de esto
UMBRAL_RUEDA = 0.55         # el palo derecho cuenta como una vuelta de rueda al pasar de esto
PERIODO_RUEDA = 0.16        # s entre dos vueltas de rueda con el palo sostenido
MARGEN_CURSOR = 0.02        # el cursor no sale de la ventana

PREFIJO = "gamepad"
PALO_IZQUIERDO = f"{PREFIJO} left stick"
PALO_DERECHO = f"{PREFIJO} right stick"
GATILLO_DERECHO = f"{PREFIJO} right trigger"
GATILLO_IZQUIERDO = f"{PREFIJO} left trigger"

# Qué teclas manda cada botón en cada modo. Una lista = todas a la vez (la pulsación y la suelta). «CLIC» no es una tecla: es
# «clic izquierdo si hay un botón bajo el cursor» y, si no lo hay, lo que diga el segundo valor.
CLIC = "<clic>"
MODO_MUNDO = "mundo"
MODO_MENU = "menu"

BOTONES = {
    MODO_MUNDO: {
        "a": ["space"], "b": ["e"], "x": ["r"], "y": ["tab"],
        "back": ["m"], "start": ["escape"],
        "right shoulder": ["left shift"], "left shoulder": ["m"],
        "dpad up": ["up arrow"], "dpad down": ["down arrow"], "dpad left": ["left arrow"], "dpad right": ["right arrow"],
        "left stick": [], "right stick": [],
    },
    MODO_MENU: {
        "a": [CLIC], "b": ["escape"], "x": ["enter"], "y": ["tab"],
        "back": ["tab"], "start": ["escape"],
        "right shoulder": ["tab"], "left shoulder": ["shift tab"],
        "dpad up": ["up arrow"], "dpad down": ["down arrow"], "dpad left": ["left arrow"], "dpad right": ["right arrow"],
        "left stick": [], "right stick": [],
    },
}

NOMBRES_BOTON = tuple(BOTONES[MODO_MUNDO])


def nombre_de_boton(tecla):
    """«gamepad a» -> («a», True); «gamepad a up» -> («a», False); cualquier otra cosa -> None.
    Acepta mandos extra («gamepad_1 a»): se trata igual (el primero que pulse manda)."""
    if not isinstance(tecla, str) or not tecla.startswith(PREFIJO):
        return None
    resto = tecla[len(PREFIJO):]
    if resto[:1] == "_":                              # «gamepad_1 a»: se quita el índice
        espacio = resto.find(" ")
        if espacio < 0:
            return None
        resto = resto[espacio:]
    if not resto.startswith(" "):
        return None
    resto = resto[1:]
    pulsado = True
    if resto.endswith(" up") and resto not in ("dpad up",):
        resto, pulsado = resto[:-3], False
    return (resto, pulsado) if resto in BOTONES[MODO_MUNDO] else None


def teclas_de(boton, modo):
    """Teclas que dispara `boton` en `modo` (lista, puede estar vacía)."""
    return list(BOTONES.get(modo, BOTONES[MODO_MUNDO]).get(boton, []))


def modo_de(raton_capturado):
    """Modo según el ratón: capturado = se camina (mundo); libre = hay cursor (menú)."""
    return MODO_MUNDO if raton_capturado else MODO_MENU


# -- Palos ------------------------------------------------------------------

def zona_muerta(x, y, umbral=ZONA_MUERTA):
    """Zona muerta RADIAL con reescalado: justo fuera del umbral el valor arranca en 0 (sin salto) y llega a 1 en el borde.
    Devuelve (x, y) con módulo <= 1."""
    largo = math.hypot(x, y)
    if largo <= umbral:
        return (0.0, 0.0)
    escala = min(1.0, (largo - umbral) / (1.0 - umbral)) / largo
    return (x * escala, y * escala)


def palo(held, nombre=PALO_IZQUIERDO, umbral=ZONA_MUERTA):
    """(x, y) del palo `nombre` leído de `held_keys`, con zona muerta. x: derecha +, y: arriba +."""
    try:
        x = float(held.get(f"{nombre} x", 0.0))
        y = float(held.get(f"{nombre} y", 0.0))
    except (TypeError, ValueError):
        return (0.0, 0.0)
    if not (math.isfinite(x) and math.isfinite(y)):
        return (0.0, 0.0)
    return zona_muerta(max(-1.0, min(1.0, x)), max(-1.0, min(1.0, y)), umbral)


def gatillo(held, nombre, umbral=UMBRAL_GATILLO):
    """True si el gatillo `nombre` pasa del umbral (los gatillos de Panda llegan de 0 a 1)."""
    try:
        return float(held.get(nombre, 0.0)) > umbral
    except (TypeError, ValueError):
        return False


def combinar_ejes(teclas, palo_xy):
    """(h, v) del teclado (enteros -1/0/1) combinado con el palo: si el teclado manda (algún eje distinto de 0) se queda tal cual
    —así el teclado se comporta EXACTAMENTE como siempre—; si no, el palo da una dirección analógica (módulo <= 1)."""
    h, v = teclas
    if h != 0 or v != 0:
        return (h, v)
    return (palo_xy[0], palo_xy[1])


# -- Cursor -----------------------------------------------------------------

def mover_cursor(pos, palo_xy, dt, velocidad, aspecto, dt_max=0.05):
    """Nueva posición (x, y) del cursor en coordenadas de camera.ui: x en [-aspecto/2, aspecto/2], y en [-0.5, 0.5].
    El palo da la velocidad (curva cuadrática: fino al principio, rápido a fondo)."""
    dt = max(0.0, min(dt, dt_max))
    sx, sy = palo_xy
    largo = math.hypot(sx, sy)
    if largo == 0 or dt == 0:
        return pos
    curva = largo                                      # |v|·|v| / |v| en cada eje -> módulo al cuadrado
    x = pos[0] + sx * curva * velocidad * dt
    y = pos[1] + sy * curva * velocidad * dt
    lim_x = aspecto / 2 - MARGEN_CURSOR
    lim_y = 0.5 - MARGEN_CURSOR
    return (max(-lim_x, min(lim_x, x)), max(-lim_y, min(lim_y, y)))


def a_pixeles(pos, ancho, alto, aspecto):
    """(x, y) de camera.ui -> píxeles de la ventana (origen arriba a la izquierda), para mover el puntero del sistema."""
    px = (pos[0] / aspecto + 0.5) * ancho
    py = (0.5 - pos[1]) * alto
    return (int(round(px)), int(round(py)))


# -- Cámara -----------------------------------------------------------------

def giro_camara(yaw, pitch, palo_xy, dt, pitch_min, pitch_max, dt_max=0.05):
    """Gira la cámara con el palo derecho (x = yaw, y = pitch; arriba = mirar hacia arriba, igual que subir el ratón)."""
    dt = max(0.0, min(dt, dt_max))
    sx, sy = palo_xy
    if sx == 0 and sy == 0:
        return yaw, pitch
    nuevo_yaw = yaw + sx * GIRO_CAMARA * dt
    while nuevo_yaw > 180.0:
        nuevo_yaw -= 360.0
    while nuevo_yaw <= -180.0:
        nuevo_yaw += 360.0
    return nuevo_yaw, min(pitch_max, max(pitch_min, pitch - sy * GIRO_CAMARA * dt))


# -- Rueda con el palo derecho ---------------------------------------------

class RuedaDelPalo:
    """Convierte el palo derecho (arriba/abajo) en vueltas de rueda a ritmo constante mientras se sostiene."""

    def __init__(self):
        self._espera = 0.0

    def avanzar(self, y, dt):
        """Devuelve 'scroll up' / 'scroll down' / None."""
        if abs(y) < UMBRAL_RUEDA:
            self._espera = 0.0
            return None
        self._espera -= dt
        if self._espera > 0:
            return None
        self._espera = PERIODO_RUEDA
        return "scroll up" if y > 0 else "scroll down"
