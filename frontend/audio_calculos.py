# Matemática pura del audio del juego (sin ursina ni panda3d): saneo de volúmenes, atenuación por distancia,
# paso/zancada para los pasos, pitch del motor, detector de salto/aterrizaje y rampas de fundido.
# La usan frontend/audio.py (GestorAudio) y frontend/audio_enganches.py; se prueba sin dispositivo de audio.

import math

# Pasos: metros por paso. Caminar ~0,8 m; correr ~1,3 m (zancada más larga). Por debajo de VEL_MIN_PASO no hay pasos.
VEL_MIN_PASO = 0.4
ZANCADA_CAMINAR = 0.82
ZANCADA_CORRER = 1.30
VEL_CAMINAR = 4.8          # m/s de referencia (VELOCIDAD_CAMINAR de la escena)
VEL_CORRER = 8.5

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
    return ZANCADA_CAMINAR + (ZANCADA_CORRER - ZANCADA_CAMINAR) * t


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
