# Cálculos puros de los vehículos montables: bicicleta y moto (NO importa ursina ni panda3d).
#
# Convenciones (las del mundo): plano (x, z), altura y. `rumbo` en grados como rotation_y de Ursina
# (0 = +z, 90 = +x); el vector hacia adelante es (sin rumbo, cos rumbo). Girar a la DERECHA = subir el rumbo.
# Inclinación (lean): positiva = hacia la derecha del piloto. Cabeceo: positivo = morro arriba.
#
# Dinámica arcade, no simulación: aceleración suave que se agota al acercarse a la velocidad máxima, freno,
# freno de mano con derrape ligero, giro tipo bicicleta (radio = batalla / tan(volante)) con el ángulo de
# volante limitado por la aceleración lateral (a más velocidad, curvas más abiertas), inclinación según la
# fuerza lateral, ruedas que giran distancia / radio, ciclo de pedaleo y balanceo del piloto, cabeceo según la
# pendiente, suspensión con muelle amortiguado y cinemática inversa de piernas y brazos para que el piloto
# llegue a los pedales / estribos y al manubrio. Colisión: reutiliza navegacion.mover_con_colisiones y
# comprueba además delante y detrás del vehículo (es más largo que el peatón).
#
# Los modelos 3D (vehiculo_modelo.py) y la colocación en el mundo (vehiculo_mundo.py) solo traducen esto.

import math
from dataclasses import dataclass

from backend.logica import navegacion
from frontend.azar_fijo import azar_de

G = 9.81
BICICLETA = "bicicleta"
MOTO = "moto"


@dataclass(frozen=True)
class PerfilVehiculo:
    tipo: str
    nombre: str                 # texto para el aviso («bicicleta», «moto»)
    vmax: float                 # m/s sin turbo
    vturbo: float               # m/s con turbo (Shift)
    vreversa: float             # m/s hacia atrás (empujando)
    acel: float                 # m/s² desde parado
    freno: float                # m/s² con S / freno
    freno_mano: float           # m/s² con Espacio (derrape)
    rodadura: float             # m/s² que frena al soltar el acelerador (constante)
    arrastre: float             # 1/s: frenada extra proporcional a la velocidad
    batalla: float              # m entre ejes
    radio_rueda: float          # m (incluye el neumático)
    semi_largo: float           # m del centro a los puntos delantero y trasero de colisión
    volante_max: float          # rad: ángulo máximo de la rueda delantera (giro del manubrio)
    a_lateral: float            # m/s²: aceleración lateral que el agarre tolera
    rapidez_volante: float      # 1/s: lo rápido que el volante sigue la tecla
    lean_max: float             # rad: inclinación máxima mostrada
    vuelta_pedal: float         # vueltas de rueda por vuelta de pedal (relación de marchas); 0 = sin pedales
    altura_asiento: float       # m del suelo a la parte alta del sillín
    altura_camara: float        # m extra de altura del pivote de la cámara (el piloto va más alto)


PERFIL_BICICLETA = PerfilVehiculo(
    tipo=BICICLETA, nombre="bicicleta", vmax=8.0, vturbo=9.2, vreversa=1.6, acel=2.6, freno=6.5, freno_mano=9.0,
    rodadura=0.9, arrastre=0.07, batalla=1.04, radio_rueda=0.34, semi_largo=0.55, volante_max=0.62,
    a_lateral=8.0, rapidez_volante=7.0, lean_max=math.radians(26), vuelta_pedal=2.4, altura_asiento=0.93,
    altura_camara=0.25)

PERFIL_MOTO = PerfilVehiculo(
    tipo=MOTO, nombre="moto", vmax=16.0, vturbo=20.0, vreversa=2.2, acel=4.2, freno=10.0, freno_mano=13.0,
    rodadura=1.1, arrastre=0.05, batalla=1.30, radio_rueda=0.32, semi_largo=0.75, volante_max=0.52,
    a_lateral=11.0, rapidez_volante=5.5, lean_max=math.radians(32), vuelta_pedal=0.0, altura_asiento=0.80,
    altura_camara=0.35)

PERFILES = {BICICLETA: PERFIL_BICICLETA, MOTO: PERFIL_MOTO}
TIPOS = (BICICLETA, MOTO)

DT_MAXIMO = 0.05                 # tope por frame, como el controlador del jugador
RADIO_AVISO = 2.6                # m: a esta distancia aparece «E para montar»
RADIO_BAJAR = 1.4                # m a un lado del vehículo donde aparece el piloto al bajar
PENDIENTE_VEHICULO = 0.55        # m/m: más empinado que esto (≈29°) no se sube (rampa de arena muy fuerte)


# Perfil por tipo (ValueError si no existe).
def perfil_de(tipo):
    if tipo not in PERFILES:
        raise ValueError(f"tipo de vehículo desconocido: {tipo!r}")
    return PERFILES[tipo]


# Entrada de un frame: acelerar en [-1, 1] (W = +1, S = -1), direccion en [-1, 1] (D = +1), turbo, freno de mano.
@dataclass(frozen=True)
class EntradaVehiculo:
    acelerar: float = 0.0
    direccion: float = 0.0
    turbo: bool = False
    freno_mano: bool = False


@dataclass
class EstadoVehiculo:
    x: float = 0.0
    z: float = 0.0
    rumbo: float = 0.0               # grados
    velocidad: float = 0.0           # m/s con signo (negativo = marcha atrás)
    deriva: float = 0.0              # rad: ángulo del movimiento respecto al rumbo del cuerpo (derrape)
    volante: float = 0.0             # -1..1 suavizado
    giro_manubrio: float = 0.0       # rad: ángulo real de la rueda delantera (positivo = derecha)
    velocidad_giro: float = 0.0      # rad/s de rumbo (positivo = derecha)
    inclinacion: float = 0.0         # rad (lean)
    cabeceo: float = 0.0             # rad (morro arriba positivo)
    giro_rueda_del: float = 0.0      # rad acumulados
    giro_rueda_tras: float = 0.0
    fase_pedal: float = 0.0          # rad
    balanceo: float = 0.0            # m: desplazamiento lateral del piloto
    rebote: float = 0.0              # m: compresión de la suspensión (positivo = baja el chasis)
    rebote_vel: float = 0.0
    aceleracion: float = 0.0         # m/s² longitudinal del último frame
    choque: float = 0.0              # 0..1: intensidad del último choque con un obstáculo
    altura_prev: float = 0.0


# -- Utilidades -------------------------------------------------------------------------------------------------


def _aproximar(actual, objetivo, rapidez, dt):
    # Exponencial independiente de los fps (igual que geometria_mundo.suavizar, sin importarla).
    return actual + (objetivo - actual) * (1.0 - math.exp(-rapidez * dt))


def _limitar(valor, minimo, maximo):
    return max(minimo, min(maximo, valor))


def vector_adelante(rumbo_grados):
    r = math.radians(rumbo_grados)
    return (math.sin(r), math.cos(r))


def vector_derecha(rumbo_grados):
    r = math.radians(rumbo_grados)
    return (math.cos(r), -math.sin(r))


def normalizar_angulo(grados):
    grados = (grados + 180.0) % 360.0 - 180.0
    return 180.0 if grados == -180.0 else grados


# -- Velocidad --------------------------------------------------------------------------------------------------


# Velocidad máxima útil: con turbo sube; la pendiente (navegacion.factor_pendiente) la modifica.
def velocidad_maxima(perfil, turbo=False, factor_pendiente=1.0):
    return (perfil.vturbo if turbo else perfil.vmax) * factor_pendiente


# Un paso de la velocidad longitudinal. Devuelve (velocidad_nueva, aceleración real). La aceleración se agota
# al acercarse al tope (curva 1 - (v/tope)²); sin acelerar el vehículo rueda y se detiene solo; con S frena y,
# ya parado, empuja hacia atrás despacio; el freno de mano frena fuerte y no deja acelerar.
def paso_velocidad(velocidad, acelerar, turbo, freno_mano, perfil, dt, factor_pendiente=1.0):
    tope = velocidad_maxima(perfil, turbo, factor_pendiente)
    v = velocidad
    if freno_mano:
        v = _frenar_hacia_cero(v, perfil.freno_mano, dt)
    elif acelerar > 0.05:
        if v < -0.2:
            v = _frenar_hacia_cero(v, perfil.freno, dt)                  # iba hacia atrás: primero frena
        elif v > tope:
            v = max(tope, v - 3.0 * dt)                                  # se pasó del tope (soltó el turbo)
        else:
            cociente = _limitar(v / tope, 0.0, 1.0)
            v += perfil.acel * acelerar * (1.0 - cociente * cociente) * dt + 0.35 * dt   # el 0.35 saca del reposo
    elif acelerar < -0.05:
        if v > 0.3:
            v = _frenar_hacia_cero(v, perfil.freno * -acelerar, dt)
        else:
            v = max(-perfil.vreversa, v - perfil.acel * 0.5 * -acelerar * dt)
    else:
        v = _frenar_hacia_cero(v, perfil.rodadura + perfil.arrastre * abs(v), dt)
    return v, (v - velocidad) / dt if dt > 0 else 0.0


def _frenar_hacia_cero(v, decel, dt):
    if v > 0:
        return max(0.0, v - decel * dt)
    return min(0.0, v + decel * dt)


# -- Dirección --------------------------------------------------------------------------------------------------


# El volante (-1..1) sigue a la tecla: rápido al girar, algo más al centrarse.
def paso_volante(volante, direccion, perfil, dt):
    rapidez = perfil.rapidez_volante * (1.0 if abs(direccion) > 0.05 else 1.4)
    return _aproximar(volante, _limitar(direccion, -1.0, 1.0), rapidez, dt)


# Ángulo real de la rueda delantera (rad) para un volante -1..1: limitado a baja velocidad por el giro máximo
# y a alta por la aceleración lateral que tolera el agarre (a_lat = v² / radio -> tan(ángulo) = a_lat·L / v²).
def angulo_manubrio(volante, velocidad, perfil):
    v = abs(velocidad)
    tope = perfil.volante_max
    if v > 0.5:
        tope = min(tope, math.atan(perfil.a_lateral * perfil.batalla / (v * v)))
    return _limitar(volante, -1.0, 1.0) * tope


# Velocidad de giro del rumbo (rad/s; positivo = derecha): v·tan(ángulo)/batalla. El freno de mano la aumenta
# (la trasera se desliza y el morro cierra).
def velocidad_de_giro(velocidad, angulo, perfil, freno_mano=False):
    omega = velocidad * math.tan(angulo) / perfil.batalla
    if freno_mano and abs(velocidad) > 2.0:
        omega *= 1.35
    return omega


# Radio de giro (m) con el volante a tope a esa velocidad.
def radio_de_giro(velocidad, perfil):
    angulo = abs(angulo_manubrio(1.0, velocidad, perfil))
    return perfil.batalla / math.tan(angulo) if angulo > 1e-6 else math.inf


# Inclinación (rad; derecha positiva) hacia el interior de la curva: atan(a_lat / g) escalada para que no se vea
# exagerada, con tope del perfil. a_lat = v·ω.
def inclinacion_objetivo(velocidad, omega, perfil):
    a_lat = velocidad * omega
    return _limitar(math.atan(a_lat / G) * 0.95, -perfil.lean_max, perfil.lean_max)


# Derrape ligero: el movimiento (rumbo_mov) persigue al morro con un agarre; normalmente es casi rígido (deriva
# de ~1°), con el freno de mano y velocidad el agarre baja y el movimiento se queda atrás respecto al morro, hacia
# el lado contrario del giro, hasta ~40°. Soltando, vuelve a alinearse. Devuelve la deriva nueva (rad) = ángulo
# del movimiento respecto al morro; d(deriva)/dt = -ω - agarre·deriva (solución exacta, estable con cualquier dt).
def paso_deriva(deriva, velocidad, omega, freno_mano, dt):
    agarre = 2.0 if (freno_mano and abs(velocidad) > 3.0) else 30.0
    reposo = -omega / agarre
    nueva = deriva + (reposo - deriva) * (1.0 - math.exp(-agarre * dt))
    return _limitar(nueva, -0.7, 0.7)


# -- Ruedas, pedales y piloto -----------------------------------------------------------------------------------


# Ángulo (rad) que gira una rueda al recorrer `distancia` m: distancia / radio (sin patinar).
def avance_rueda(angulo, distancia, radio):
    return (angulo + distancia / radio) % (2 * math.pi) if radio > 0 else angulo


# Fase del pedal: va con la rueda trasera (cadencia = giro de rueda / relación) mientras se pedalea; al soltar
# el acelerador queda en rueda libre y se detiene (el pedal no se queda girando en el vacío). Con turbo se pedalea
# con más energía (la fase avanza igual: la cadencia sale de la velocidad real).
def paso_fase_pedal(fase, velocidad, acelerar, perfil, dt):
    if perfil.vuelta_pedal <= 0:
        return fase
    if velocidad < 0.2 and acelerar <= 0.05:
        return fase
    cadencia = abs(velocidad) / perfil.radio_rueda / perfil.vuelta_pedal       # rad/s del pedal
    if acelerar <= 0.05:
        cadencia *= 0.0                                                         # rueda libre: pies quietos
    elif velocidad < 1.5:
        cadencia = max(cadencia, 4.0)                                           # arrancando: pedaleo enérgico
    return (fase + cadencia * dt) % (2 * math.pi)


# Posición (z adelante, y arriba) del eje del pedal respecto al eje del pedalier para la fase y el lado
# (+1 derecho, -1 izquierdo; opuestos 180°). Fase 0: pedal derecho adelante a la altura del eje.
def posicion_pedal(fase, lado, largo_biela=0.17):
    angulo = fase + (0.0 if lado > 0 else math.pi)
    return (largo_biela * math.cos(angulo), -largo_biela * math.sin(angulo))


# Balanceo lateral (m) del cuerpo del piloto al pedalear: una oscilación por cada pedalada, proporcional a la
# velocidad. En moto casi nada.
def balanceo_piloto(fase_pedal, velocidad, perfil):
    if perfil.vuelta_pedal <= 0:
        return 0.0
    return 0.028 * math.sin(fase_pedal) * _limitar(abs(velocidad) / perfil.vmax, 0.0, 1.0)


# Suspensión: muelle amortiguado. `empuje` es la fuerza (m/s²) que comprime (frenar o un bache). Devuelve
# (compresión, velocidad). Subamortiguado: rebota una o dos veces y se calma.
def paso_suspension(compresion, velocidad, empuje, dt, rigidez=140.0, amortiguacion=13.0):
    aceleracion = empuje - rigidez * compresion - amortiguacion * velocidad
    velocidad += aceleracion * dt
    compresion += velocidad * dt
    return _limitar(compresion, -0.08, 0.08), velocidad


# Cabeceo (rad) del vehículo según la altura del suelo bajo la rueda delantera y la trasera.
def cabeceo_por_alturas(altura_delantera, altura_trasera, batalla):
    return math.atan2(altura_delantera - altura_trasera, batalla)


# Puntos (x, z) bajo la rueda delantera y la trasera.
def puntos_de_contacto(x, z, rumbo, semi_largo):
    fx, fz = vector_adelante(rumbo)
    return ((x + fx * semi_largo, z + fz * semi_largo), (x - fx * semi_largo, z - fz * semi_largo))


# -- Cinemática inversa del piloto (plano sagital: z adelante, y arriba) ----------------------------------------


# Ángulos de pose (convención de frontend/poses.py: positivo = hacia adelante) de una pierna de muslo `l1` y
# pantorrilla `l2` cuya cadera está en el origen para que el tobillo llegue a `objetivo` = (z, y) (y negativo =
# por debajo de la cadera). La rodilla se dobla hacia adelante. Devuelve (muslo, rodilla) en grados; rodilla <= 0.
# Si el objetivo está fuera de alcance, estira la pierna hacia él.
def ik_pierna(objetivo, l1=0.45, l2=0.42):
    tz, ty = objetivo
    d = math.hypot(tz, ty)
    d = _limitar(d, abs(l1 - l2) + 1e-4, l1 + l2 - 1e-4)
    a = math.atan2(tz, -ty)                                     # ángulo desde la vertical hacia adelante
    cos_b = _limitar((l1 * l1 + d * d - l2 * l2) / (2 * l1 * d), -1.0, 1.0)
    beta = math.acos(cos_b)
    muslo = a + beta                                            # la rodilla queda más adelante que la línea cadera-tobillo
    kz, ky = l1 * math.sin(muslo), -l1 * math.cos(muslo)
    ez, ey = tz - kz, ty - ky                                   # pantorrilla: de la rodilla al tobillo
    ang_pantorrilla = math.atan2(ez, -ey)
    return math.degrees(muslo), math.degrees(ang_pantorrilla - muslo)


# Igual para un brazo (hombro en el origen, mano en `objetivo`): el codo se dobla hacia ATRÁS/afuera (el
# antebrazo queda más adelantado que el brazo). Devuelve (brazo, codo) en grados; codo >= 0 (positivo = el
# antebrazo se adelanta respecto al brazo, como en poses.py).
def ik_brazo(objetivo, l1=0.30, l2=0.28):
    tz, ty = objetivo
    d = math.hypot(tz, ty)
    d = _limitar(d, abs(l1 - l2) + 1e-4, l1 + l2 - 1e-4)
    a = math.atan2(tz, -ty)
    cos_b = _limitar((l1 * l1 + d * d - l2 * l2) / (2 * l1 * d), -1.0, 1.0)
    beta = math.acos(cos_b)
    brazo = a - beta                                            # el codo cae por debajo / detrás de la línea
    cz, cy = l1 * math.sin(brazo), -l1 * math.cos(brazo)
    ez, ey = tz - cz, ty - cy
    ang_antebrazo = math.atan2(ez, -ey)
    return math.degrees(brazo), math.degrees(ang_antebrazo - brazo)


# Punto al que llega un segmento de largo l1 (muslo/brazo) y luego l2 con los ángulos de pose (cinemática directa;
# sirve para probar la inversa). Devuelve (z, y) del extremo.
def extremo_de_miembro(angulo1, angulo2, l1, l2):
    a1 = math.radians(angulo1)
    a2 = math.radians(angulo1 + angulo2)
    return (l1 * math.sin(a1) + l2 * math.sin(a2), -l1 * math.cos(a1) - l2 * math.cos(a2))


# -- Colisión ---------------------------------------------------------------------------------------------------


# ¿Cabe el vehículo en (x, z) con ese rumbo? El centro, la rueda delantera y la trasera deben ser transitables
# y ninguna debe estar sobre una escalera (los vehículos no suben peldaños). El mapa puede no tener escaleras().
def posicion_valida(mapa, x, z, rumbo, perfil):
    puntos = [(x, z)] + list(puntos_de_contacto(x, z, rumbo, perfil.semi_largo))
    escaleras = getattr(mapa, "escaleras", None)
    lista = escaleras() if callable(escaleras) else []
    for px, pz in puntos:
        if not mapa.es_transitable(px, pz):
            return False
        if any(e.contiene(px, pz) for e in lista):
            return False
    return True


# Mueve el vehículo (dx, dz) con deslizamiento. Usa navegacion.mover_con_colisiones para el centro y luego
# exige que los puntos delantero y trasero también quepan; si no, prueba solo x y solo z. Devuelve
# (x, z, fracción_bloqueada) con la fracción en [0, 1] (0 = pasó entero, 1 = no se movió nada).
def mover_vehiculo(mapa, x, z, dx, dz, rumbo, perfil):
    deseado = math.hypot(dx, dz)
    if deseado < 1e-9:
        return x, z, 0.0
    nx, nz = navegacion.mover_con_colisiones(mapa, x, z, dx, dz)
    if not posicion_valida(mapa, nx, nz, rumbo, perfil):
        nx, nz = x, z
        for cx, cz in ((x + dx, z), (x, z + dz)):
            if posicion_valida(mapa, cx, cz, rumbo, perfil):
                nx, nz = cx, cz
                break
    movido = math.hypot(nx - x, nz - z)
    return nx, nz, _limitar(1.0 - movido / deseado, 0.0, 1.0)


# Holgura lateral (m a cada lado) alrededor de (x, z) perpendicular al rumbo, hasta `maximo`: sirve para colocar
# vehículos solo en calles anchas y plazas. Devuelve (izquierda, derecha).
def holgura_lateral(mapa, x, z, rumbo, maximo=5.0, paso=0.25):
    dx, dz = vector_derecha(rumbo)
    medidas = []
    for signo in (-1.0, 1.0):
        d = 0.0
        while d < maximo and mapa.es_transitable(x + dx * signo * (d + paso), z + dz * signo * (d + paso)):
            d += paso
        medidas.append(d)
    return tuple(medidas)


# -- Un paso completo --------------------------------------------------------------------------------------------


# Avanza el estado un frame. `mapa` da es_transitable() y (opcional) altura(x, z). `factor_pendiente` ya incluye
# el desnivel si se quiere; aquí se calcula con navegacion.factor_pendiente cuando el mapa tiene altura().
# Muta y devuelve `estado`.
def paso_vehiculo(estado, mapa, entrada, perfil, dt):
    dt = _limitar(dt, 0.0, DT_MAXIMO)
    if dt <= 0:
        return estado
    altura = getattr(mapa, "altura", None)
    fx, fz = vector_adelante(estado.rumbo)
    factor = 1.0
    if altura is not None and abs(estado.velocidad) > 0.1:
        signo = 1.0 if estado.velocidad > 0 else -1.0
        desnivel = altura(estado.x + fx * signo * 0.5, estado.z + fz * signo * 0.5) - altura(estado.x, estado.z)
        factor = navegacion.factor_pendiente(desnivel, 0.5)
        if signo < 0:
            factor = 1.0

    estado.velocidad, estado.aceleracion = paso_velocidad(
        estado.velocidad, entrada.acelerar, entrada.turbo, entrada.freno_mano, perfil, dt, factor)
    estado.volante = paso_volante(estado.volante, entrada.direccion, perfil, dt)
    angulo = angulo_manubrio(estado.volante, estado.velocidad, perfil)
    estado.giro_manubrio = angulo
    omega = velocidad_de_giro(estado.velocidad, angulo, perfil, entrada.freno_mano)
    estado.velocidad_giro = omega
    nuevo_rumbo = normalizar_angulo(estado.rumbo + math.degrees(omega) * dt)
    if posicion_valida(mapa, estado.x, estado.z, nuevo_rumbo, perfil):
        estado.rumbo = nuevo_rumbo
    else:                                               # girar aquí metería una rueda en la pared: se queda recto
        omega = 0.0
        estado.velocidad_giro = 0.0
    estado.deriva = paso_deriva(estado.deriva, estado.velocidad, omega, entrada.freno_mano, dt)

    # Desplazamiento: sigue la dirección del movimiento (morro + deriva), no la del morro.
    rumbo_mov = estado.rumbo + math.degrees(estado.deriva)
    mx, mz = vector_adelante(rumbo_mov)
    pasos = estado.velocidad * dt
    x0, z0 = estado.x, estado.z
    estado.x, estado.z, bloqueo = mover_vehiculo(mapa, x0, z0, mx * pasos, mz * pasos, estado.rumbo, perfil)
    estado.choque = 0.0
    if bloqueo > 0.5 and abs(estado.velocidad) > 2.5:           # choque contra pared / borde: rebote corto
        estado.choque = _limitar(abs(estado.velocidad) / perfil.vmax, 0.0, 1.0)
        estado.velocidad *= -0.18
        estado.deriva = 0.0
    elif bloqueo > 0.5:
        estado.velocidad *= 0.5
    recorrido = math.hypot(estado.x - x0, estado.z - z0) * (1.0 if estado.velocidad >= 0 else -1.0)
    if bloqueo > 0.5 and abs(estado.velocidad) < 0.3:
        recorrido = 0.0

    # Ruedas y pedales según lo recorrido de verdad (no patinan contra una pared).
    estado.giro_rueda_tras = avance_rueda(estado.giro_rueda_tras, recorrido, perfil.radio_rueda)
    estado.giro_rueda_del = avance_rueda(estado.giro_rueda_del, recorrido, perfil.radio_rueda)
    estado.fase_pedal = paso_fase_pedal(estado.fase_pedal, estado.velocidad, entrada.acelerar, perfil, dt)
    estado.balanceo = _aproximar(estado.balanceo, balanceo_piloto(estado.fase_pedal, estado.velocidad, perfil), 14.0, dt)

    # Inclinación hacia la curva, cabeceo por pendiente y suspensión.
    estado.inclinacion = _aproximar(estado.inclinacion, inclinacion_objetivo(estado.velocidad, omega, perfil), 7.0, dt)
    empuje = _limitar(-estado.aceleracion * 0.5, -4.0, 4.0)      # frenar comprime la suspensión, acelerar la descarga
    if altura is not None:
        d_front, d_rear = puntos_de_contacto(estado.x, estado.z, estado.rumbo, perfil.batalla / 2)
        hf, hr = altura(*d_front), altura(*d_rear)
        objetivo_cabeceo = cabeceo_por_alturas(hf, hr, perfil.batalla)
        estado.cabeceo = _aproximar(estado.cabeceo, objetivo_cabeceo, 9.0, dt)
        medio = (hf + hr) / 2
        if estado.altura_prev:                                  # un cambio brusco de altura (baches) sacude la suspensión
            empuje += _limitar((medio - estado.altura_prev) / dt * 3.0, -3.0, 3.0)
        estado.altura_prev = medio
    else:
        estado.cabeceo = _aproximar(estado.cabeceo, 0.0, 9.0, dt)
    estado.rebote, estado.rebote_vel = paso_suspension(estado.rebote, estado.rebote_vel, empuje, dt)
    return estado


# Estado inicial aparcado en (x, z) con ese rumbo.
def estado_inicial(x, z, rumbo=0.0):
    return EstadoVehiculo(x=x, z=z, rumbo=rumbo)


# -- Cámara -----------------------------------------------------------------------------------------------------


# Efectos de la velocidad sobre la cámara, ADITIVOS al comportamiento normal: (metros extra de distancia, grados
# extra de FOV, metros extra de altura del pivote). Curva suave: poco a baja velocidad, el máximo al tope turbo.
def efectos_de_camara(velocidad, perfil):
    t = _limitar(abs(velocidad) / perfil.vturbo, 0.0, 1.0)
    curva = t * t * (3 - 2 * t)
    if perfil.tipo == MOTO:
        return 2.6 * curva, 11.0 * curva, perfil.altura_camara
    return 1.4 * curva, 6.0 * curva, perfil.altura_camara


# Yaw de la cámara que se acerca al rumbo del vehículo (la cámara se coloca detrás al avanzar) cuando el jugador
# no mueve el ratón. Devuelve el yaw nuevo en grados. La fuerza sube con la velocidad; parado no se mueve.
def seguir_rumbo_camara(yaw_camara, rumbo, velocidad, perfil, dt, raton_activo=False, rapidez=1.6):
    if raton_activo or velocidad < 1.5:
        return yaw_camara
    fuerza = rapidez * _limitar(velocidad / perfil.vmax, 0.0, 1.0)
    diferencia = normalizar_angulo(rumbo - yaw_camara)
    return normalizar_angulo(yaw_camara + diferencia * (1.0 - math.exp(-fuerza * dt)))


# -- Aparcamiento (colocación determinista) ---------------------------------------------------------------------


# Paleta (cuerpo, acento, parche, caja) del vehículo número `indice` de su tipo: colores planos y saturados,
# siempre los mismos. Cada paleta es una tupla de cuatro RGB 0-255.
PALETAS = (
    ((222, 52, 48), (250, 205, 50), (40, 170, 190), (250, 140, 40)),     # rojo, amarillo, turquesa, naranja
    ((250, 196, 40), (30, 120, 210), (230, 70, 130), (60, 170, 90)),     # amarillo, azul, rosa, verde
    ((30, 170, 180), (250, 120, 40), (250, 235, 220), (200, 50, 60)),    # turquesa, naranja, crema, rojo
    ((60, 170, 80), (250, 230, 60), (220, 60, 50), (30, 110, 200)),      # verde, amarillo, rojo, azul
    ((244, 120, 36), (30, 80, 190), (250, 210, 60), (40, 170, 120)),     # naranja, azul, amarillo, verde
    ((46, 110, 220), (250, 200, 50), (230, 80, 70), (250, 245, 235)),    # azul, amarillo, rojo, blanco
    ((228, 78, 150), (40, 180, 190), (250, 215, 60), (110, 60, 190)),    # rosa, turquesa, amarillo, violeta
    ((130, 70, 200), (250, 190, 40), (50, 190, 120), (240, 90, 60)),     # violeta, amarillo, verde, coral
)


def paleta_de(tipo, indice):
    base = (indice * 3 + (1 if tipo == MOTO else 0)) % len(PALETAS)
    return PALETAS[base]


# Descripción de un vehículo aparcado.
@dataclass(frozen=True)
class Aparcado:
    tipo: str
    x: float
    z: float
    rumbo: float
    indice: int


# Puntos de aparcamiento deterministas: `n` vehículos repartidos entre las calles anchas (junto al borde, a ~2.4 m
# del eje, en el sentido de la calle) y el borde interior de las plazas. Se descartan sitios sin holgura lateral
# mínima (callejones), con escalera o fuera del mapa. Alterna bicis y motos. Siempre el mismo resultado.
def puntos_de_aparcamiento(mundo, n=8, semilla=7, holgura_minima=3.0, separacion_minima=7.0):
    candidatos = []
    ancho = getattr(mundo, "ancho_calle", 8.0)
    radio = getattr(mundo, "radio_plaza", 9.0)
    for a, b in mundo.segmentos():
        ax, az = mundo.coordenada(a)
        bx, bz = mundo.coordenada(b)
        largo = math.hypot(bx - ax, bz - az)
        if largo < 1e-6:
            continue
        ux, uz = (bx - ax) / largo, (bz - az) / largo
        rumbo_calle = math.degrees(math.atan2(ux, uz))
        for fraccion in (0.30, 0.50, 0.70):
            for lado in (-1.0, 1.0):
                px = ax + (bx - ax) * fraccion + uz * lado * min(2.6, ancho / 2 - 1.2)
                pz = az + (bz - az) * fraccion - ux * lado * min(2.6, ancho / 2 - 1.2)
                rumbo = rumbo_calle if azar_de(px, pz) < 0.5 else normalizar_angulo(rumbo_calle + 180.0)
                candidatos.append((px, pz, rumbo))
    for lugar in mundo.lugares():
        cx, cz = mundo.coordenada(lugar)
        for k in range(4):
            ang = (k * 90.0 + 45.0 + 17.0 * azar_de(cx, cz + k)) % 360.0
            px = cx + math.sin(math.radians(ang)) * (radio * 0.55)
            pz = cz + math.cos(math.radians(ang)) * (radio * 0.55)
            candidatos.append((px, pz, normalizar_angulo(ang + 90.0)))

    validos = []
    for px, pz, rumbo in candidatos:
        perfil = PERFIL_MOTO
        if not posicion_valida(mundo, px, pz, rumbo, perfil):
            continue
        izq, der = holgura_lateral(mundo, px, pz, rumbo, maximo=holgura_minima + 1.0)
        if min(izq, der) < holgura_minima:
            continue
        validos.append((azar_de(px * 0.37 + semilla, pz * 0.61), px, pz, rumbo))
    validos.sort()
    # Reparto parejo: el primero fijo y cada siguiente es el más lejano de los ya elegidos (muestreo del punto más
    # lejano), con la separación mínima. Determinista porque `validos` ya está ordenado por un azar fijo.
    elegidos = []
    if validos:
        elegidos.append(validos[0][1:])
    while len(elegidos) < n:
        mejor, mejor_d = None, separacion_minima
        for _, px, pz, rumbo in validos:
            d = min(math.hypot(px - e[0], pz - e[1]) for e in elegidos)
            if d >= mejor_d:
                mejor, mejor_d = (px, pz, rumbo), d
        if mejor is None:
            break
        elegidos.append(mejor)
    return [Aparcado(TIPOS[(i + (1 if semilla % 2 else 0)) % 2], x, z, r, i // 2) for i, (x, z, r) in enumerate(elegidos)]


# Vehículo aparcado más cercano (índice) a (x, z) dentro de `radio`, o None. `posiciones`: lista de (x, z).
def indice_cercano(posiciones, x, z, radio=RADIO_AVISO):
    mejor, mejor_d = None, radio
    for i, (px, pz) in enumerate(posiciones):
        d = math.hypot(px - x, pz - z)
        if d <= mejor_d:
            mejor, mejor_d = i, d
    return mejor


# Dónde aparece el piloto al bajar: a la izquierda del vehículo si cabe, si no a la derecha, delante o detrás; el
# primer punto transitable. Devuelve (x, z). Si no hay ninguno, el mismo centro del vehículo.
def punto_para_bajar(mapa, x, z, rumbo, distancia=RADIO_BAJAR):
    fx, fz = vector_adelante(rumbo)
    dx, dz = vector_derecha(rumbo)
    for ox, oz in ((-dx, -dz), (dx, dz), (fx, fz), (-fx, -fz)):
        for d in (distancia, distancia * 1.5, distancia * 2.2):
            px, pz = x + ox * d, z + oz * d
            if mapa.es_transitable(px, pz):
                return px, pz
    return x, z

