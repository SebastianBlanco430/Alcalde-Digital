# Validación en el anfitrión del movimiento que PROPONE cada cliente (módulo PURO: sin red, sin ursina,
# sin panda3d). El cliente manda `pos` {n,x,z,y,r,v,f,veh?}; aquí se decide si se acepta, se descarta o se
# corrige. Hay un `ValidadorMovimiento` por jugador, con reloj inyectable para poder probarlo sin esperar.
#
# Comprobaciones (en este orden):
#   1. Tipos estrictos (int/float, nunca bool ni str), valores finitos (nada de NaN/Infinity) y rangos sanos.
#   2. `n` creciente: un `n` repetido se ignora en silencio; uno que retrocede cuenta como infracción.
#   3. Bandera `dentro` (el jugador está en un interior local): el anfitrión no conoce ese espacio, así que
#      solo guarda las banderas y NO valida ni mueve nada.
#   4. Transitable: la posición (y unas pocas muestras del tramo recorrido) cae en `mundo.es_transitable`.
#   5. Presupuesto de distancia (cubo de fichas): se recarga a la velocidad máxima permitida y guarda como
#      mucho RESERVA_S segundos de recorrido, así una ráfaga de paquetes agrupados por la red no es falso
#      positivo, pero un teletransporte sí se rechaza.
#   6. Altura: no por debajo del suelo (con escaleras) menos un margen, subida limitada por VELOCIDAD_SALTO,
#      bajada por VELOCIDAD_CAIDA_MAXIMA, tope de elevación (salto) y sin "flotar" mucho rato.
# Si algo falla: se descarta, se cuenta una infracción y se pide `corregir` (la última posición buena).
# Demasiadas infracciones (con fuga con el tiempo) -> `debe_desconectar`.

import math
import time
from dataclasses import dataclass
from typing import Optional

from backend.logica import salto_calculos as salto
from backend.logica.navegacion import PENDIENTE_FACTOR_MAXIMO

# --- Constantes de velocidad (m/s) -----------------------------------------------------------------------
# VELOCIDAD_CORRER vive en frontend/escenas/escena_mundo.py (importa ursina); aquí se repite el valor y un
# test lo compara con el fuente para que no se desincronicen.
VELOCIDAD_CORRER = 8.5
TOLERANCIA = 1.15                       # margen sobre lo legítimo (latencia, redondeos, pendiente)
VELOCIDAD_MAX_A_PIE = VELOCIDAD_CORRER * PENDIENTE_FACTOR_MAXIMO * TOLERANCIA
# vturbo de frontend/vehiculo_calculos.PERFILES (copia respaldo si no se puede importar; hay test de paridad).
VTURBO_RESPALDO = {"bicicleta": 9.2, "moto": 20.0}
RESERVA_S = 0.5                         # segundos de recorrido que puede acumular el cubo
# --- Altura ------------------------------------------------------------------------------------------------
MARGEN_SUELO = 0.3                      # m: por debajo del suelo con escaleras menos esto = infracción
MARGEN_VERTICAL = 0.5                   # m de holgura en |Δy| (peldaños suavizados, lag)
ELEVACION_MAX = salto.ALTURA_SALTO + 0.6    # m sobre el suelo hasta donde un salto puede subir
VUELO_MAX_S = 0.6                       # s seguidos muy arriba sin caer antes de llamarlo "vuelo"
VUELO_VEL_CAIDA = 2.0                   # m/s: caer más despacio que esto estando alto cuenta como flotar
DT_MIN = 0.05                           # s: dt mínimo para las holguras (paquetes agrupados)
DT_MAX = 2.0                            # s: dt máximo (tras un silencio largo no se acumula holgura infinita)
# --- Rangos de los campos ----------------------------------------------------------------------------------
LIMITE_COORD = 1.0e5
LIMITE_Y = 1.0e3
LIMITE_RUMBO = 1.0e4
LIMITE_VELOCIDAD = 100.0
LIMITE_N = 2 ** 53
PASO_TRAMO = 0.5                        # m entre muestras al comprobar el tramo recorrido
MAX_MUESTRAS_TRAMO = 12
# --- Banderas `f` (máscara de bits, la misma que usa el protocolo) -------------------------------------------
BANDERA_EN_AIRE = 1
BANDERA_ESCALERA = 2
BANDERA_DENTRO = 4
BANDERA_VEHICULO = 8
BANDERA_CABALLITO = 16          # rueda delantera levantada: solo se conserva con vehículo (ver validar)
BANDERAS_VALIDAS = BANDERA_EN_AIRE | BANDERA_ESCALERA | BANDERA_DENTRO | BANDERA_VEHICULO | BANDERA_CABALLITO
# --- Infracciones ---------------------------------------------------------------------------------------------
UMBRAL_DESCONEXION = 25.0               # puntos de infracción acumulados que desconectan
FUGA_POR_SEGUNDO = 0.5                  # puntos que se perdonan por segundo

# T9: sin control de vehículo (el anfitrión no gestiona montura: se fía de `veh` como siempre). Con
# `autorizar_vehiculo(tipo|None)` el anfitrión pasa a ser la autoridad: el vehículo válido es el que él dice.
SIN_CONTROL_VEHICULO = object()
GRACIA_BAJADA = 1.0            # s: tras bajar, un `pos` en vuelo (o el latido) aún puede declarar el vehículo: se ignora

CLAVES_OBLIGATORIAS = ("n", "x", "z", "y", "r", "v", "f")
CLAVES_PERMITIDAS = frozenset(CLAVES_OBLIGATORIAS + ("veh",))


# Resultado de validar un `pos`. (x, z, y) es la posición que vale en el anfitrión tras la validación: la
# propuesta si se aceptó, la última buena si no. `corregir` = enviar `corregir{x,z,y,seq}` al cliente.
@dataclass(frozen=True)
class Resultado:
    aceptado: bool
    x: float
    z: float
    y: float
    corregir: bool = False
    infraccion: Optional[str] = None    # código corto («tipos», «seq», «pared», «velocidad», «altura», «vuelo»…)
    ignorado: bool = False              # descartado sin culpa (n repetido, jugador `dentro`)
    seq: int = 0


def _es_numero(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _es_entero(v):
    return isinstance(v, int) and not isinstance(v, bool)


def _perfiles_por_defecto():
    # Las velocidades de turbo reales; si el módulo del frontend no se puede importar, la copia de respaldo.
    try:
        from frontend.vehiculo_calculos import PERFILES
        return {k: float(p.vturbo) for k, p in PERFILES.items()}
    except Exception:
        return dict(VTURBO_RESPALDO)


class ValidadorMovimiento:
    # `mundo`: MundoCiudad (es_transitable, limites_recorribles, altura_con_escaleras). `reloj`: función sin
    # argumentos que devuelve segundos (por defecto time.monotonic). `vturbo_vehiculos`: {tipo: m/s}.
    def __init__(self, mundo, reloj=time.monotonic, vturbo_vehiculos=None, umbral_desconexion=UMBRAL_DESCONEXION,
                 comprobar_tramo=True):
        self.mundo = mundo
        self.reloj = reloj
        self.vturbo = dict(vturbo_vehiculos) if vturbo_vehiculos is not None else _perfiles_por_defecto()
        self.umbral_desconexion = float(umbral_desconexion)
        self.comprobar_tramo = comprobar_tramo
        self.ultimo_n = -1
        self.x = self.z = self.y = 0.0
        self.r = 0.0
        self.v = 0.0
        self.f = 0
        self.veh = None
        self.veh_autorizado = SIN_CONTROL_VEHICULO
        self._t_bajada = -1e9
        self.tiene_posicion = False
        self.fichas = 0.0                 # metros de presupuesto disponibles
        self._t_ultimo = None             # reloj del último pos aceptado (o de colocar)
        self._t_fuga = None
        self._t_vuelo = 0.0
        self.infracciones = 0             # total histórico
        self.puntos = 0.0                 # puntos con fuga (los que cuentan para desconectar)
        self.ultima_infraccion = None

    # Fija la posición autorizada por el anfitrión (aparición, reaparición, salir de un edificio): NO es
    # una propuesta del cliente. Reinicia el cubo, la altura de referencia y el contador de vuelo.
    def colocar(self, x, z, y=None, ahora=None):
        t = self.reloj() if ahora is None else ahora
        self.x, self.z = float(x), float(z)
        self.y = float(self.mundo.altura_con_escaleras(self.x, self.z) if y is None else y)
        self.tiene_posicion = True
        self.fichas = self._vmax() * RESERVA_S
        self._t_ultimo = t
        self._t_vuelo = 0.0

    @property
    def debe_desconectar(self):
        return self.puntos >= self.umbral_desconexion

    # T9: el anfitrión fija qué vehículo (tipo) monta este jugador según SU reserva de monturas, o None si va a pie.
    # Desde entonces `veh` y la bandera de vehículo del cliente solo se comprueban contra esto, y la velocidad
    # máxima es la del vehículo autorizado (no la que el cliente diga). `olvidar_vehiculo()` vuelve al modo previo.
    def autorizar_vehiculo(self, tipo):
        if tipo is None and self.veh_autorizado not in (None, SIN_CONTROL_VEHICULO):
            self._t_bajada = self.reloj()
        self.veh_autorizado = tipo

    def olvidar_vehiculo(self):
        self.veh_autorizado = SIN_CONTROL_VEHICULO

    # Estado que el anfitrión publica en los snapshots de este jugador.
    def estado(self):
        return {"x": self.x, "z": self.z, "y": self.y, "r": self.r, "v": self.v, "f": self.f, "veh": self.veh}

    # Velocidad máxima (m/s) con el vehículo actual (o a pie).
    def _vmax(self, veh=None):
        veh = self.veh if veh is None else veh
        if veh is None:
            return VELOCIDAD_MAX_A_PIE
        return self.vturbo.get(veh, 0.0) * TOLERANCIA

    # ---------------------------------------------------------------------------------------------------
    # Valida un `pos` (dict). Devuelve Resultado; nunca lanza por datos malos.
    def validar(self, pos, ahora=None):
        t = self.reloj() if ahora is None else ahora
        self._fugar(t)
        error = self._revisar_forma(pos)
        if error:
            return self._rechazar(error, 0)
        n = pos["n"]
        if n == self.ultimo_n:
            return Resultado(False, self.x, self.z, self.y, ignorado=True, seq=n)
        if n < self.ultimo_n:
            return self._rechazar("seq", n)
        self.ultimo_n = n
        x, z, y = float(pos["x"]), float(pos["z"]), float(pos["y"])
        r, v, f, veh = float(pos["r"]), float(pos["v"]), pos["f"], pos.get("veh")
        if veh is not None and veh not in self.vturbo:
            return self._rechazar("vehiculo", n)
        autoridad = self.veh_autorizado is not SIN_CONTROL_VEHICULO
        if autoridad:
            # Reclamar un vehículo que el anfitrión no ha concedido (o uno distinto) es trampa o un error grave.
            if veh is not None and veh != self.veh_autorizado:
                if self.veh_autorizado is None and t - self._t_bajada <= GRACIA_BAJADA:
                    veh = None                   # recién bajado: el latido de 2 Hz repite la última posición
                else:
                    return self._rechazar("vehiculo", n)
            veh = self.veh_autorizado            # lo concedido manda, aunque el cliente aún no lo declare
            f = (f | BANDERA_VEHICULO) if veh else (f & ~BANDERA_VEHICULO)
        if not veh:
            f &= ~BANDERA_CABALLITO              # a pie no hay caballito
        # Interior local: el anfitrión solo anota banderas (los demás ven «dentro»), no valida ni mueve.
        if f & BANDERA_DENTRO:
            self.f = f
            self.r = r
            return Resultado(False, self.x, self.z, self.y, ignorado=True, seq=n)
        # Primera posición: se acepta si es transitable (la aparición normal usa colocar()).
        primera = not self.tiene_posicion
        dt = DT_MIN if primera else min(DT_MAX, max(DT_MIN, t - self._t_ultimo))
        vmax = (VELOCIDAD_MAX_A_PIE if veh is None else self._vmax(veh)) if autoridad else self._vmax(veh)
        if primera:
            self.fichas = vmax * RESERVA_S
        else:
            self.fichas = min(vmax * RESERVA_S, self.fichas + max(0.0, t - self._t_ultimo) * vmax)
        # 1. dentro de los límites y transitable.
        xmin, xmax, zmin, zmax = self.mundo.limites_recorribles()
        if not (xmin <= x <= xmax and zmin <= z <= zmax) or not self.mundo.es_transitable(x, z):
            return self._rechazar("pared", n)
        # 2. presupuesto de distancia (horizontal).
        dist = 0.0 if primera else math.hypot(x - self.x, z - self.z)
        if dist > self.fichas + 1e-9:
            return self._rechazar("velocidad", n)
        # 3. el tramo no atraviesa obstáculos (pocas muestras: el coste es unos µs por muestra).
        if self.comprobar_tramo and not primera and dist > PASO_TRAMO and not self._tramo_libre(x, z, dist):
            return self._rechazar("pared", n)
        # 4. altura.
        suelo = float(self.mundo.altura_con_escaleras(x, z))
        motivo = self._revisar_altura(y, suelo, dt, primera)
        if motivo:
            return self._rechazar(motivo, n)
        # Aceptado.
        self.fichas -= dist
        self.x, self.z, self.y = x, z, y
        self.r, self.v, self.f, self.veh = r, v, f, veh
        self.tiene_posicion = True
        self._t_ultimo = t
        return Resultado(True, x, z, y, seq=n)

    # -- Internos --

    # Comprueba tipos, claves, finitud y rangos. Devuelve el código de infracción o None.
    def _revisar_forma(self, pos):
        if not isinstance(pos, dict):
            return "tipos"
        if not CLAVES_PERMITIDAS.issuperset(pos) or any(k not in pos for k in CLAVES_OBLIGATORIAS):
            return "tipos"
        if not _es_entero(pos["n"]) or not (0 <= pos["n"] <= LIMITE_N):
            return "tipos"
        if not _es_entero(pos["f"]) or pos["f"] < 0 or pos["f"] & ~BANDERAS_VALIDAS:
            return "tipos"
        for clave, tope in (("x", LIMITE_COORD), ("z", LIMITE_COORD), ("y", LIMITE_Y), ("r", LIMITE_RUMBO)):
            valor = pos[clave]
            if not _es_numero(valor) or not math.isfinite(valor) or abs(valor) > tope:
                return "tipos"
        valor = pos["v"]
        if not _es_numero(valor) or not math.isfinite(valor) or not (0.0 <= valor <= LIMITE_VELOCIDAD):
            return "tipos"
        veh = pos.get("veh")
        if veh is not None and (not isinstance(veh, str) or len(veh) > 16):
            return "tipos"
        return None

    # ¿Las muestras intermedias del segmento (self -> x, z) son transitables?
    def _tramo_libre(self, x, z, dist):
        muestras = min(MAX_MUESTRAS_TRAMO, int(dist / PASO_TRAMO))
        for i in range(1, muestras + 1):
            k = i / (muestras + 1)
            if not self.mundo.es_transitable(self.x + (x - self.x) * k, self.z + (z - self.z) * k):
                return False
        return True

    # Devuelve el código de infracción de altura o None. Actualiza el contador de "vuelo".
    def _revisar_altura(self, y, suelo, dt, primera):
        if y < suelo - MARGEN_SUELO:
            return "altura"
        elevacion = y - suelo
        if primera:
            return "altura" if elevacion > ELEVACION_MAX else None
        dy = y - self.y
        if dy > salto.VELOCIDAD_SALTO * dt + MARGEN_VERTICAL:
            return "altura"
        if -dy > salto.VELOCIDAD_CAIDA_MAXIMA * dt + MARGEN_VERTICAL:
            return "altura"
        if elevacion > ELEVACION_MAX:
            # Muy por encima del suelo: solo vale si ya venía cayendo (caída libre legítima desde un
            # talud/techo). No puede seguir subiendo ni quedarse flotando.
            if dy > MARGEN_VERTICAL * 0.2:
                return "altura"
            if -dy / dt < VUELO_VEL_CAIDA:
                self._t_vuelo += dt
                if self._t_vuelo > VUELO_MAX_S:
                    return "vuelo"
            else:
                self._t_vuelo = 0.0
        else:
            self._t_vuelo = 0.0
        return None

    def _fugar(self, t):
        if self._t_fuga is not None and self.puntos > 0:
            self.puntos = max(0.0, self.puntos - (t - self._t_fuga) * FUGA_POR_SEGUNDO)
        self._t_fuga = t

    def _rechazar(self, codigo, n):
        self.infracciones += 1
        self.puntos += 1.0
        self.ultima_infraccion = codigo
        return Resultado(False, self.x, self.z, self.y, corregir=self.tiene_posicion, infraccion=codigo, seq=n)
