# Cálculos PUROS (sin ursina ni panda3d) de los vehículos en el modo online (T9):
#   - pos del jugador LOCAL con vehículo (la fuente de posición del bucle de red manda el vehículo, no el avatar oculto);
#   - corrección suave del anfitrión al local que conduce (sin tirarlo del vehículo);
#   - AnimadorRemoto: estado visual (EstadoVehiculo) de un vehículo ajeno a partir de lo que llega por red (posición,
#     rumbo, velocidad): lean según la fuerza lateral, manubrio, ruedas, pedales y cabeceo derivados de la velocidad;
#   - qué vehículos están ocupados por remotos (a partir del `veh` del snapshot).
import math

from frontend import vehiculo_calculos as vc

BIT_VEHICULO = 8
BIT_CABALLITO = 16             # rueda delantera levantada (backend.red.sesion_en_linea.BANDERAS)
TAU_CORRECCION = 0.18          # s: constante de tiempo del difuminado de la corrección al conductor
UMBRAL_CORRECCION_BRUSCA = 6.0 # m: más que esto se coloca de golpe (sin bajarlo del vehículo)
FACTOR_VELOCIDAD_BRUSCA = 0.5  # tras un salto grande la velocidad se reduce (para no volver a infringir)
IGNORAR_SNAP_TRAS_BAJAR = 0.7  # s: tras bajar, los snapshots en vuelo aún traen la posición vieja del vehículo
TIMEOUT_MONTAR = 2.5           # s esperando monta_ok / monta_no antes de dar la petición por perdida


# Reemplaza la posición del peatón por la del vehículo en la tupla que consume ClienteRed.enviar_pos:
# (x, z, y, rumbo, velocidad, banderas[, veh]). `datos`: la tupla original (banderas: set de nombres o máscara).
# `caballito`: la rueda delantera va levantada (los demás lo ven con BIT_CABALLITO).
def datos_con_vehiculo(datos, x, z, y, rumbo, velocidad, tipo, caballito=False):
    banderas = datos[5]
    if isinstance(banderas, int) and not isinstance(banderas, bool):
        banderas = (banderas | BIT_VEHICULO | (BIT_CABALLITO if caballito else 0)) & ~(0 if caballito else BIT_CABALLITO)
    else:
        banderas = set(banderas) | {"vehiculo"}
        banderas.discard("en_aire")          # montado no hay salto
        banderas.discard("escalera")
        if caballito:
            banderas.add("caballito")
        else:
            banderas.discard("caballito")
    return (float(x), float(z), float(y), float(rumbo) % 360.0, max(0.0, abs(float(velocidad))), banderas, tipo)


# Corrección suave: el vehículo se acerca a (obj_x, obj_z) con constante de tiempo TAU. Devuelve (x, z, brusca).
# Si la distancia pasa de UMBRAL se coloca directamente en el objetivo (brusca=True).
def paso_correccion(x, z, obj_x, obj_z, dt, tau=TAU_CORRECCION, umbral=UMBRAL_CORRECCION_BRUSCA):
    distancia = math.hypot(obj_x - x, obj_z - z)
    if not math.isfinite(distancia):
        return x, z, False
    if distancia > umbral:
        return obj_x, obj_z, True
    k = 1.0 - math.exp(-max(0.0, dt) / tau) if tau > 0 else 1.0
    return x + (obj_x - x) * k, z + (obj_z - z) * k, False


# Vehículos ocupados por jugadores REMOTOS: {id_vehiculo: id_piloto} (excluye al jugador local).
def ocupados_por_remotos(lista_veh, tu_id):
    ocupados = {}
    for entrada in lista_veh or ():
        p = entrada.get("p")
        if p is not None and p != tu_id:
            ocupados[entrada["i"]] = p
    return ocupados


# Vehículo (entrada del snapshot) que conduce el jugador `id_jugador`, o None.
def vehiculo_de_piloto(lista_veh, id_jugador):
    for entrada in lista_veh or ():
        if entrada.get("p") == id_jugador:
            return entrada
    return None


def _angulo_corto(a, b):
    # diferencia a - b en grados normalizada a (-180, 180]
    return (a - b + 180.0) % 360.0 - 180.0


def _acercar(actual, objetivo, rapidez, dt):
    return actual + (objetivo - actual) * (1.0 - math.exp(-rapidez * max(0.0, dt)))


# Anima un vehículo conducido por otro jugador. Se alimenta cada frame con la posición interpolada.
class AnimadorRemoto:

    def __init__(self, tipo, altura=None):
        self.perfil = vc.perfil_de(tipo)
        self.altura = altura                    # callable(x, z) -> y del terreno, o None
        self.estado = vc.EstadoVehiculo()
        self._previo = None                     # (x, z, rumbo) del frame anterior
        self._omega = 0.0                       # rad/s de giro suavizado (derecha positiva)
        self.acelerando = False

    def colocar(self, x, z, rumbo):
        self.estado = vc.EstadoVehiculo(x=x, z=z, rumbo=rumbo)
        self._previo = (x, z, rumbo)
        self._omega = 0.0

    # Un paso. Devuelve el EstadoVehiculo listo para VehiculoModelo.aplicar_estado. `caballito`: el piloto remoto lleva
    # la rueda levantada (BIT_CABALLITO); se anima con la misma regla que el local (sube y baja suave).
    def avanzar(self, x, z, rumbo, velocidad, dt, caballito=False):
        e, p = self.estado, self.perfil
        if self._previo is None:
            self.colocar(x, z, rumbo)
        dt = max(1e-4, min(dt, 0.25))
        px, pz, prumbo = self._previo
        # Marcha atrás: si el movimiento va contra el morro, la velocidad lleva signo negativo (solo dibujo).
        recorrido = math.hypot(x - px, z - pz)
        signo = 1.0
        if recorrido > 1e-3:
            fx, fz = vc.vector_adelante(rumbo)
            signo = 1.0 if ((x - px) * fx + (z - pz) * fz) >= 0 else -1.0
        v = max(0.0, velocidad) * signo
        omega_bruta = math.radians(_angulo_corto(rumbo, prumbo)) / dt
        omega_bruta = max(-6.0, min(6.0, omega_bruta))
        self._omega = _acercar(self._omega, omega_bruta, 10.0, dt)
        e.x, e.z, e.rumbo = x, z, rumbo % 360.0
        e.velocidad = v
        e.velocidad_giro = self._omega
        # Manubrio: ángulo de dirección que da esa velocidad de giro (batalla·ω / v), acotado al del perfil.
        if abs(v) > 0.4:
            angulo = math.atan(p.batalla * self._omega / abs(v))
        else:
            angulo = 0.0
        angulo = max(-p.volante_max, min(p.volante_max, angulo))
        e.giro_manubrio = _acercar(e.giro_manubrio, angulo, 12.0, dt)
        e.inclinacion = _acercar(e.inclinacion, vc.inclinacion_objetivo(v, self._omega, p), 7.0, dt)
        e.giro_rueda_tras = vc.avance_rueda(e.giro_rueda_tras, signo * recorrido, p.radio_rueda)
        e.giro_rueda_del = vc.avance_rueda(e.giro_rueda_del, signo * recorrido, p.radio_rueda)
        self.acelerando = abs(v) > 0.5
        e.fase_pedal = vc.paso_fase_pedal(e.fase_pedal, v, 1.0 if self.acelerando else 0.0, p, dt)
        e.balanceo = _acercar(e.balanceo, vc.balanceo_piloto(e.fase_pedal, v, p), 14.0, dt)
        if self.altura is not None:
            delante, detras = vc.puntos_de_contacto(x, z, e.rumbo, p.batalla / 2)
            objetivo = vc.cabeceo_por_alturas(self.altura(*delante), self.altura(*detras), p.batalla)
            e.cabeceo = _acercar(e.cabeceo, objetivo, 9.0, dt)
        # El que conduce ya comprobó la velocidad mínima: con la bandera puesta se levanta sin volver a exigirla.
        e.caballito = vc.paso_caballito(e.caballito, caballito, max(abs(v), p.caballito_vmin) if caballito else abs(v),
                                        p, dt)
        self._previo = (x, z, rumbo)
        return e
