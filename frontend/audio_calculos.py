# Matemática pura del audio del juego (sin ursina ni panda3d): saneo de volúmenes, atenuación por distancia,
# paso/zancada para los pasos, pitch del motor, detector de salto/aterrizaje y rampas de fundido.
# La usan frontend/audio.py (GestorAudio) y frontend/audio_enganches.py; se prueba sin dispositivo de audio.

import math
import os

# Pasos: metros por paso. Caminar ~0,8 m; correr ~1,3 m (zancada más larga). Por debajo de VEL_MIN_PASO no hay pasos.
VEL_MIN_PASO = 0.4
ZANCADA_CAMINAR = 0.82
ZANCADA_CORRER = 1.30
VEL_CAMINAR = 4.8          # m/s de referencia (VELOCIDAD_CAMINAR de la escena)
VEL_CORRER = 8.5
# Cadencia máxima (pasos por segundo). El jugador va a 4,8-8,5 m/s, mucho más rápido que una persona real, y con la
# zancada de arriba salían ~6 pasos/s: ráfagas de ruido pegadas que sonaban a locomotora. Con la cadencia acotada la
# zancada se alarga sola a esas velocidades. ALCALDE_PASOS_CADENCIA=0 vuelve al ritmo de antes.
PASOS_CADENCIA = True
CADENCIA_CAMINAR = 2.4
CADENCIA_CORRER = 2.9

DISTANCIA_CERCA = 2.0      # m: hasta aquí un sonido 3D suena entero
DISTANCIA_LEJOS = 45.0     # m: a partir de aquí no se oye


# Convierte a float en [0, 1]; texto, NaN o None dan `defecto`. Un valor >1 (hasta 100) se toma como porcentaje.
def acotar01(valor, defecto=1.0):
    if isinstance(valor, bool) or valor is None:
        return defecto
    try:
        v = float(valor)
    except (TypeError, ValueError):
        return defecto
    if v != v or v in (float("inf"), float("-inf")):
        return defecto
    if v > 1.0 and v <= 100.0:
        v = v / 100.0
    return max(0.0, min(1.0, v))


# Volumen de un canal: maestro × canal (× 0 si está silenciado).
def volumen_canal(maestro, canal, silenciado=False):
    if silenciado:
        return 0.0
    return acotar01(maestro, 1.0) * acotar01(canal, 1.0)


# Atenuación (0-1) de un sonido 3D simple por distancia: entero hasta CERCA, cae suave (cuadrática) hasta LEJOS.
def atenuacion_distancia(distancia, cerca=DISTANCIA_CERCA, lejos=DISTANCIA_LEJOS):
    if distancia != distancia:
        return 0.0
    if distancia <= cerca:
        return 1.0
    if distancia >= lejos:
        return 0.0
    t = (lejos - distancia) / (lejos - cerca)
    return t * t


# Balance estéreo (-1 izquierda, 1 derecha) de una fuente en (dx, dz) respecto del oyente que mira al `yaw`
# (grados, mismo convenio que la cámara del juego: avanzar con yaw=0 es +z). Fuente justo encima = centro.
def balance_estereo(dx, dz, yaw_grados=0.0):
    distancia = math.hypot(dx, dz)
    if distancia < 1e-6:
        return 0.0
    r = math.radians(yaw_grados)
    adelante = (math.sin(r), math.cos(r))
    derecha = (math.cos(r), -math.sin(r))
    lado = (dx * derecha[0] + dz * derecha[1]) / distancia
    return max(-1.0, min(1.0, lado)) * min(1.0, distancia / 4.0)


# Pitch (velocidad de reproducción) del motor según la velocidad: más agudo al ir más rápido.
def pitch_motor(velocidad, vmax, minimo=0.75, maximo=1.75):
    fraccion = max(0.0, min(1.0, abs(velocidad) / max(vmax, 1e-6)))
    return minimo + (maximo - minimo) * fraccion


# Caballito (`levantada` 0..1, ver vehiculo_calculos.fraccion_caballito): el motor de la moto se «revoluciona»
# (sube de tono y algo de volumen) con la rueda en el aire. Devuelve (factor de pitch, factor de volumen).
def factores_caballito(levantada, pitch_extra=0.28, volumen_extra=0.15):
    levantada = max(0.0, min(1.0, levantada))
    return 1.0 + pitch_extra * levantada, 1.0 + volumen_extra * levantada


# Volumen del motor: ralentí audible parado y más fuerte con velocidad.
def volumen_motor(velocidad, vmax, ralenti=0.35):
    fraccion = max(0.0, min(1.0, abs(velocidad) / max(vmax, 1e-6)))
    return ralenti + (1.0 - ralenti) * fraccion


# Cadena de bici: en silencio parada; suena y acelera su tictic al rodar.
def pitch_cadena(velocidad, vmax, minimo=0.6, maximo=1.9):
    fraccion = max(0.0, min(1.0, abs(velocidad) / max(vmax, 1e-6)))
    return minimo + (maximo - minimo) * fraccion


def volumen_cadena(velocidad, vmax):
    fraccion = max(0.0, min(1.0, abs(velocidad) / max(vmax, 1e-6)))
    return 0.0 if fraccion < 0.03 else min(1.0, 0.25 + 0.75 * fraccion)


# Metros por paso según la velocidad real (interpola entre caminar y correr).
def zancada_para(velocidad):
    t = (velocidad - VEL_CAMINAR) / max(VEL_CORRER - VEL_CAMINAR, 1e-6)
    t = max(0.0, min(1.0, t))
    zancada = ZANCADA_CAMINAR + (ZANCADA_CORRER - ZANCADA_CAMINAR) * t
    if not cadencia_activa():
        return zancada
    cadencia = CADENCIA_CAMINAR + (CADENCIA_CORRER - CADENCIA_CAMINAR) * t
    return max(zancada, velocidad / cadencia)


# Ambiente v2 (ALCALDE_AMBIENTE_V2): el nombre lógico «ambiente_favela» (escenas y perfiles de etapa) suena con el
# archivo ambiente_favela_v2.wav, sin latido de 6 Hz, y algo más bajo (0,8 -> 0,55 en el mundo normal).
AMBIENTE_V2 = True
GANANCIA_AMBIENTE_V2 = 0.55 / 0.8


def ambiente_v2_activo():
    valor = os.environ.get("ALCALDE_AMBIENTE_V2", "").strip().lower()
    if valor in ("1", "true", "si", "sí", "on"):
        return True
    if valor in ("0", "false", "no", "off"):
        return False
    return bool(AMBIENTE_V2)


# Archivo (sin .wav) que suena para el nombre lógico `nombre`.
def archivo_de_sonido(nombre):
    if nombre == "ambiente_favela" and ambiente_v2_activo():
        return "ambiente_favela_v2"
    return nombre


# Factor de volumen de un bucle según su nombre lógico (1 = sin cambio).
def ganancia_bucle(nombre):
    if nombre == "ambiente_favela" and ambiente_v2_activo():
        return GANANCIA_AMBIENTE_V2
    return 1.0


def cadencia_activa():
    valor = os.environ.get("ALCALDE_PASOS_CADENCIA", "").strip().lower()
    if valor in ("1", "true", "si", "sí", "on"):
        return True
    if valor in ("0", "false", "no", "off"):
        return False
    return bool(PASOS_CADENCIA)


# PASOS SOLO DEL JUGADOR (punto «pasos de los NPC»): con PASOS_NPC = False los pasos solo suenan si el JUGADOR LOCAL
# se desplaza de verdad (su posición en los datos de la partida, que solo mueve el controlador local). La velocidad
# del avatar puede venir de otro sitio (la muestra de red de un avatar remoto, una cinemática, un NPC que camina a su
# lado): si el jugador no se movió, no hay pasos. Los NPC no tienen pasos propios.
# PASOS_NPC = True (o ALCALDE_PASOS_NPC=1) deja el comportamiento de antes (la velocidad del avatar tal cual).
PASOS_NPC = False


def pasos_npc_activos():
    valor = os.environ.get("ALCALDE_PASOS_NPC", "").strip().lower()
    if valor in ("1", "true", "si", "sí", "on"):
        return True
    if valor in ("0", "false", "no", "off"):
        return False
    return bool(PASOS_NPC)


# SIN PASOS NI RUIDO DE AMBIENTE (2026-11-15): el sonido «de pasos o locomotora» que molestaba en la partida eran
# ráfagas de ruido filtrado: los pasos del jugador y el bucle de ambiente (viento + murmullo modulado a 3-7 Hz, que
# suena a «chu-chu»; ambiente_plaza late a 7 Hz). PASOS = False quita los pasos; AMBIENTE_RUIDO = False quita los
# bucles ambiente_favela / ambiente_plaza / ambiente_caos (la música sigue). ALCALDE_PASOS=1 o ALCALDE_AMBIENTE_RUIDO=1
# los devuelven.
PASOS = False
AMBIENTE_RUIDO = False


def _bandera(variable, defecto):
    valor = os.environ.get(variable, "").strip().lower()
    if valor in ("1", "true", "si", "sí", "on"):
        return True
    if valor in ("0", "false", "no", "off"):
        return False
    return bool(defecto)


def pasos_activos():
    return _bandera("ALCALDE_PASOS", PASOS)


def ambiente_ruido_activo():
    return _bandera("ALCALDE_AMBIENTE_RUIDO", AMBIENTE_RUIDO)


# Velocidad (m/s) con la que cuentan los pasos: la del avatar, pero nunca más que lo que se desplazó el jugador local
# en este frame (`desplazamiento` m en `dt` s). Sin datos del desplazamiento (None, primer frame) se fía del avatar.
def velocidad_para_pasos(velocidad_avatar, desplazamiento, dt):
    try:
        velocidad_avatar = float(velocidad_avatar or 0.0)
    except (TypeError, ValueError):
        return 0.0
    if desplazamiento is None or dt is None or dt <= 0:
        return velocidad_avatar
    return min(velocidad_avatar, max(0.0, float(desplazamiento)) / dt)


# Volumen de un paso: más fuerte al correr.
def volumen_paso(velocidad):
    t = max(0.0, min(1.0, velocidad / VEL_CORRER))
    return 0.55 + 0.45 * t


# Acumula distancia recorrida a pie y avisa cada vez que toca un paso. Va por distancia REAL (no por el clip
# de animación) y no cuenta en el aire. `avanzar` devuelve True en el frame en que cae un pie.
class ContadorPasos:

    def __init__(self):
        self.acumulado = 0.0
        self.lado = 0            # 0 / 1 = pie que va a pisar (alterna)

    def reiniciar(self):
        self.acumulado = 0.0

    def avanzar(self, velocidad, dt, en_aire=False):
        if en_aire or velocidad < VEL_MIN_PASO or dt <= 0:
            if velocidad < VEL_MIN_PASO or en_aire:
                self.acumulado = 0.0
            return False
        self.acumulado += velocidad * dt
        zancada = zancada_para(velocidad)
        if self.acumulado >= zancada:
            self.acumulado -= zancada
            if self.acumulado > zancada:      # un tirón de dt enorme: no suelta una ráfaga de pasos
                self.acumulado = 0.0
            self.lado ^= 1
            return True
        return False


# Detecta el despegue y el aterrizaje a partir del booleano `en_aire` de cada frame. Devuelve "salto",
# "aterrizaje" o None. El aterrizaje solo cuenta si se estuvo en el aire un mínimo (evita ruidos por
# pequeños rebotes en una escalera o una pendiente).
class DetectorSalto:

    def __init__(self, minimo_aire=0.12):
        self.en_aire = False
        self.tiempo_aire = 0.0
        self.minimo_aire = minimo_aire

    def actualizar(self, en_aire, dt):
        evento = None
        if en_aire and not self.en_aire:
            evento = "salto"
            self.tiempo_aire = 0.0
        elif not en_aire and self.en_aire:
            if self.tiempo_aire >= self.minimo_aire:
                evento = "aterrizaje"
        if en_aire:
            self.tiempo_aire += max(0.0, dt)
        self.en_aire = bool(en_aire)
        return evento


# Elige una variante distinta de la anterior (para que dos pasos seguidos no sean idénticos).
def siguiente_variante(anterior, cantidad):
    if cantidad <= 1:
        return 0
    return (anterior + 1) % cantidad


# Rampa lineal de un valor hacia un destino a velocidad fija (segundos para recorrer 0 -> 1).
class Rampa:

    def __init__(self, valor=0.0, duracion=0.5):
        self.valor = valor
        self.destino = valor
        self.duracion = max(1e-3, duracion)

    def ir_a(self, destino, duracion=None):
        self.destino = destino
        if duracion is not None:
            self.duracion = max(1e-3, duracion)

    def avanzar(self, dt):
        paso = dt / self.duracion
        if self.valor < self.destino:
            self.valor = min(self.destino, self.valor + paso)
        elif self.valor > self.destino:
            self.valor = max(self.destino, self.valor - paso)
        return self.valor

    @property
    def llegado(self):
        return abs(self.valor - self.destino) < 1e-6


# -- M3 del plan ambiente y pulseras: audio por capas según la salud de la ciudad (ALCALDE_AUDIO_SALUD=0 = como antes) --
# Mezcla CONTINUA (sin saltos de nivel) sobre la música del mundo: la base baja un poco con la ciudad rota, `musica_tensa`
# entra muy baja por debajo en tenso y apagado, y `musica_fiesta` asoma en florece cerca de una plaza. Los bucles de ruido
# `ambiente_plaza` (sube con la salud) y `ambiente_caos` (con la tensión) solo entran si el equipo vuelve a encender
# AMBIENTE_RUIDO (los quitó el 2026-11-15 por sonar a locomotora). La recta final por etapas manda cuando está activa.
AUDIO_SALUD = True
FUNDIDO_SALUD = 2.0              # s de fundido de cada capa
PERIODO_AUDIO_SALUD = 0.5        # s entre recálculos
VOL_BASE_MUNDO = 0.45            # = PERFIL_ESCENA[MUNDO] de audio_enganches
VOL_BASE_MIN = 0.32              # la base con salud 0
VOL_TENSA_MAX = 0.22             # musica_tensa con salud 0 (por debajo de la base)
VOL_FIESTA_MAX = 0.20            # musica_fiesta con salud 1 en el centro de una plaza
VOL_RUIDO_MAX = 0.5
PLAZA_CERCA, PLAZA_LEJOS = 12.0, 35.0     # m: a <= 12 m la capa de fiesta suena entera; a >= 35 m, nada
CAPAS_SALUD = ("musica_tensa", "musica_fiesta", "ambiente_plaza", "ambiente_caos")


def audio_salud_activo():
    return _bandera("ALCALDE_AUDIO_SALUD", AUDIO_SALUD)


def _suave(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3.0 - 2.0 * t)


def cercania_plaza(distancia):
    """1 a <= PLAZA_CERCA m de una plaza, 0 a >= PLAZA_LEJOS, suave en medio. None/inf = lejos."""
    if distancia is None:
        return 0.0
    return _suave((PLAZA_LEJOS - distancia) / (PLAZA_LEJOS - PLAZA_CERCA))


def volumenes_salud(salud, cercania=0.0, con_ruido=False):
    """{nombre: volumen} de la base del mundo y de cada capa para esa salud (0..1). Continua en la salud."""
    s = max(0.0, min(1.0, float(salud)))
    tension = _suave((0.5 - s) / 0.5)                  # 0 con salud >= 0,5; 1 con salud 0
    fiesta = _suave((s - 0.75) / 0.2) * max(0.0, min(1.0, cercania))
    vols = {
        "musica_ambiente": round(VOL_BASE_MUNDO - (VOL_BASE_MUNDO - VOL_BASE_MIN) * tension, 4),
        "musica_tensa": round(VOL_TENSA_MAX * tension, 4),
        "musica_fiesta": round(VOL_FIESTA_MAX * fiesta, 4),
        "ambiente_plaza": 0.0,
        "ambiente_caos": 0.0,
    }
    if con_ruido:
        vols["ambiente_plaza"] = round(VOL_RUIDO_MAX * s, 4)
        vols["ambiente_caos"] = round(VOL_RUIDO_MAX * (1.0 - s), 4)
    return vols
