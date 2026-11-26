# Emisión de la radio en 3D (docs/RADIO_3D.md): la cámara del juego se acerca a la torre de la Rádio Comunitária y da
# vueltas alrededor de su antena mientras dura la emisión; solo cambian el cielo (según el momento) y el globo. Lógica
# PURA (sin ursina), con tests en tests/test_a_radio3d.py. La vista es frontend/radio3d_escena.py; la torre,
# frontend/radio_torre_modelo.py (sitio y piezas en frontend/radio_torre_calculos.py).
#
# BANDERA: ALCALDE_RADIO3D (encendida por defecto). =0 no construye la torre y, sin torre, no hay emisión (la radio 2D de
# antes se quitó; frontend/radio_emision.py): las noches pasan igual. Lo mismo si falta el sitio o la vista 3D falla.
# ÓRBITA: ORBITA elige el preset («media» por defecto, «aerea» más alta y abierta); ALCALDE_RADIO3D_ORBITA=aerea lo cambia
# sin tocar el código. Cada preset es un diccionario de ORBITAS: añadir otro es añadir una entrada.
# REDUCIR MOVIMIENTO (Ajustes › Movimiento o ALCALDE_REDUCIR_MOVIMIENTO=1): plano fijo de la torre, sin giro ni
# acercamiento.

import math
import os
import random

RADIO3D = True
VARIABLE = "ALCALDE_RADIO3D"
VARIABLE_ORBITA = "ALCALDE_RADIO3D_ORBITA"
_APAGADO = ("0", "false", "no", "off")
_ENCENDIDO = ("1", "true", "si", "sí", "on")

# -- Órbita de la cámara alrededor de la torre (m y s) --
# radio: distancia horizontal al eje de la torre; alto: altura de la cámara sobre la base; mirar: a qué fracción del alto
# de la torre apunta; vuelta_s: segundos por vuelta completa (360°). Con el FOV del juego (65) la «media» deja la torre
# entera de la plataforma a la luz y por encima de los techos de la ladera.
ORBITAS = {
    "media": {"radio": 22.0, "alto": 14.0, "mirar": 0.72, "vuelta_s": 24.0},
    "aerea": {"radio": 32.0, "alto": 24.0, "mirar": 0.6, "vuelta_s": 30.0},
}
ORBITA = "media"
ACERCAMIENTO_S = 1.6          # de la cámara del jugador a la órbita
SENTIDO = 1.0                 # 1 = antihorario visto desde arriba; -1 al revés

# -- Cielo por momento de la emisión (vineta["radio_momento"], frontend/radio_registro.py) --
HORAS = {"noche": 22.0, "manana": 6.2, "puente": 17.6}
MOMENTO_POR_DEFECTO = "noche"
ESTRELLAS = 260
SEMILLA_ESTRELLAS = 987       # 98,7 FM, la frecuencia de la emisora

# -- Globo --
EMISORA_POR_DEFECTO = "Rádio Comunitária"
SEPARADOR_ROTULO = " · "
LECTURA_BASE, LECTURA_POR_CARACTER, LECTURA_MINIMA = 1.5, 0.06, 2.5


def activo(entorno=None):
    """¿Emisión en 3D? ALCALDE_RADIO3D manda sobre RADIO3D."""
    valor = (os.environ if entorno is None else entorno).get(VARIABLE, "").strip().lower()
    if valor in _APAGADO:
        return False
    if valor in _ENCENDIDO:
        return True
    return bool(RADIO3D)


def orbita(entorno=None):
    """El preset de órbita vigente (ALCALDE_RADIO3D_ORBITA > ORBITA; uno desconocido cae a «media»)."""
    nombre = (os.environ if entorno is None else entorno).get(VARIABLE_ORBITA, "").strip().lower() or ORBITA
    return dict(ORBITAS.get(nombre, ORBITAS["media"]))


def suavizar(x):
    """0..1 → 0..1 con arranque y llegada suaves (coseno)."""
    x = min(1.0, max(0.0, x))
    return 0.5 - 0.5 * math.cos(math.pi * x)


def angulo_inicial(desde, centro):
    """Rumbo (grados) del punto `desde` (x, z) visto desde el eje de la torre: la órbita empieza del lado donde ya está la
    cámara, así el acercamiento es corto."""
    return math.degrees(math.atan2(desde[0] - centro[0], desde[1] - centro[1]))


def angulo_en(t, preset, angulo0=0.0, reducir=False):
    """Rumbo de la cámara a los `t` segundos: vueltas continuas (360° cada vuelta_s); quieto con «reducir»."""
    if reducir or preset["vuelta_s"] <= 0:
        return angulo0
    return angulo0 + SENTIDO * 360.0 * t / preset["vuelta_s"]


def posicion_orbita(centro, y_base, alto_torre, t, preset, angulo0=0.0, reducir=False):
    """((x, y, z) de la cámara, (x, y, z) adonde mira) en la órbita a los `t` segundos."""
    a = math.radians(angulo_en(t, preset, angulo0, reducir))
    cx, cz = centro
    camara = (cx + math.sin(a) * preset["radio"], y_base + preset["alto"], cz + math.cos(a) * preset["radio"])
    objetivo = (cx, y_base + alto_torre * preset["mirar"], cz)
    return camara, objetivo


def mirar(desde, hacia):
    """(pitch, yaw) en grados para que la cámara en `desde` mire a `hacia` (rotation de Ursina: pitch > 0 mira abajo)."""
    dx, dy, dz = (hacia[i] - desde[i] for i in range(3))
    yaw = math.degrees(math.atan2(dx, dz))
    pitch = -math.degrees(math.atan2(dy, math.hypot(dx, dz)))
    return pitch, yaw


def mezclar(a, b, f):
    return tuple(a[i] + (b[i] - a[i]) * f for i in range(len(a)))


def toma(t, inicio, centro, y_base, alto_torre, preset, angulo0, reducir=False):
    """La cámara a los `t` s de empezar: ((x, y, z), pitch, yaw). Los primeros ACERCAMIENTO_S va de `inicio`
    (posición y punto mirado de la cámara del jugador) a la órbita; luego, la órbita. Con «reducir», corte directo."""
    camara, objetivo = posicion_orbita(centro, y_base, alto_torre, t, preset, angulo0, reducir)
    if not reducir and inicio is not None and t < ACERCAMIENTO_S:
        f = suavizar(t / ACERCAMIENTO_S)
        camara = mezclar(inicio[0], camara, f)
        objetivo = mezclar(inicio[1], objetivo, f)
    pitch, yaw = mirar(camara, objetivo)
    return camara, pitch, yaw


def hora_de_momento(momento):
    """Hora con la que se pinta el cielo: noche estrellada con luna, amanecer o atardecer del día 7."""
    return HORAS.get(momento, HORAS[MOMENTO_POR_DEFECTO])


def con_estrellas(momento):
    return (momento or MOMENTO_POR_DEFECTO) == "noche"


def estrellas(n=ESTRELLAS, semilla=SEMILLA_ESTRELLAS):
    """[(x, y, z, brillo)] en la cúpula unidad (y > 0), siempre las mismas: más arriba, más densas."""
    azar = random.Random(semilla)
    salida = []
    for _ in range(n):
        rumbo = azar.uniform(0.0, 2 * math.pi)
        elevacion = math.asin(azar.uniform(math.sin(math.radians(12)), 0.98))
        c = math.cos(elevacion)
        salida.append((c * math.sin(rumbo), math.sin(elevacion), c * math.cos(rumbo), azar.uniform(0.45, 1.0)))
    return salida


def nombre_rotulo(titulo):
    """Lo que dice el rótulo amarillo: la emisora sola («Rádio Comunitária · Jandira Lopes» -> «Rádio Comunitária»)."""
    nombre = str(titulo or "").split(SEPARADOR_ROTULO)[0].strip()
    return nombre or EMISORA_POR_DEFECTO


def segundos_vineta(vineta):
    """Tiempo de lectura de una línea: el que trae la viñeta (radio_calculos.vinetas_de) o la regla de siempre (1,5 s +
    0,06 s por carácter, mínimo 2,5 s)."""
    segundos = vineta.get("segundos")
    if isinstance(segundos, (int, float)) and segundos > 0:
        return float(segundos)
    texto = str(vineta.get("texto") or "")
    return max(LECTURA_MINIMA, LECTURA_BASE + LECTURA_POR_CARACTER * len(texto))
