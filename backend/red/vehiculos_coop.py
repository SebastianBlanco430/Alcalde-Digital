# Vehículos (bicis y motos) en el modo online, lado ANFITRIÓN (módulo PURO: sin red, sin ursina, sin panda3d).
# El anfitrión es el único dueño del estado: qué vehículos hay, dónde están aparcados y quién va montado. Los
# clientes piden `montar{veh}` / `bajar{}` y el anfitrión decide (exclusividad: un vehículo = un jugador).
#
# Reglas:
#   - Spawn DETERMINISTA: los aparcados (8 en el chico, 24 en el grande: aparcados_para_mundo) salen de frontend.vehiculo_calculos.puntos_de_aparcamiento(mundo, n=n,
#     semilla=SEMILLA_VEHICULOS) — la misma función y la misma semilla que usa MundoVehiculos en cada cliente,
#     así que el vehículo número i es el mismo en todos los equipos (el mundo ya se verifica con huella_mundo).
#   - montar: el jugador debe estar conectado, no «dentro» de un edificio, no ir ya montado, el vehículo debe
#     existir, estar libre y a menos de RADIO_MONTAR del jugador (RADIO_AVISO del juego + holgura por latencia).
#   - Mientras va montado, el vehículo SIGUE al piloto (mover); al bajar o desconectarse queda aparcado donde estaba.
#   - Nada de lo que llega por red se usa como ruta ni clase: `veh` es un entero 0..N_VEHICULOS_MAX-1 y el tipo sale del catálogo.
import math

from backend.red import protocolo

N_VEHICULOS = 8                  # mundo chico (y valor por defecto de aparcados_deterministas)
N_VEHICULOS_GRANDE = protocolo.N_VEHICULOS_MAX   # mapa grande (v4 del protocolo): 24, igual que frontend.vehiculo_mundo.N_VEHICULOS_GRANDE
SEMILLA_VEHICULOS = 7            # la misma que el valor por defecto de MundoVehiculos
RADIO_AVISO = 2.6                # m: igual que frontend/vehiculo_calculos.RADIO_AVISO (hay test de paridad)
HOLGURA_MONTAR = 1.6             # m de tolerancia por latencia y posiciones suavizadas
RADIO_MONTAR = RADIO_AVISO + HOLGURA_MONTAR
TIPOS_VEHICULO = ("bicicleta", "moto")

# Motivos de rechazo (un conjunto cerrado: el protocolo los admite como opciones, nunca texto libre).
MOTIVOS = protocolo.MOTIVOS_VEHICULO
MOTIVO_OCUPADO = "ocupado"
MOTIVO_LEJOS = "lejos"
MOTIVO_YA_MONTADO = "ya_montado"
MOTIVO_NO_EXISTE = "no_existe"
MOTIVO_FASE = "fase"
MOTIVO_DENTRO = "dentro"
MOTIVO_DESACTIVADO = "desactivado"
MOTIVO_DESCONECTADO = "desconectado"
MOTIVO_BAJADA = "bajada"


def aparcados_deterministas(mundo, n=N_VEHICULOS, semilla=SEMILLA_VEHICULOS):
    """[(tipo, x, z, rumbo)] de los vehículos aparcados. Siempre lo mismo para el mismo mundo."""
    from frontend import vehiculo_calculos as vc
    return [(a.tipo, float(a.x), float(a.z), float(a.rumbo))
            for a in vc.puntos_de_aparcamiento(mundo, n=n, semilla=semilla)]


def n_vehiculos_de(mundo):
    """Cuántos vehículos aparcados hay online en este mundo: 24 con un MundoGrande, 8 con el chico."""
    return N_VEHICULOS_GRANDE if hasattr(mundo, "contenido_de_chunk") else N_VEHICULOS


def aparcados_para_mundo(mundo, semilla=SEMILLA_VEHICULOS):
    """aparcados_deterministas con la cantidad que toca al mundo (los 8 primeros del grande son los del chico)."""
    return aparcados_deterministas(mundo, n=n_vehiculos_de(mundo), semilla=semilla)


class VehiculoCoop:
    __slots__ = ("id", "tipo", "x", "z", "rumbo", "piloto", "x0", "z0", "rumbo0")

    def __init__(self, id, tipo, x, z, rumbo):
        self.id = id
        self.tipo = tipo
        self.x, self.z, self.rumbo = float(x), float(z), float(rumbo)
        self.x0, self.z0, self.rumbo0 = self.x, self.z, self.rumbo
        self.piloto = None          # id del jugador que lo conduce, o None

    def a_snap(self):
        """Entrada del snapshot (esquema _VEHICULO_SNAP del protocolo)."""
        entrada = {"i": self.id, "k": self.tipo, "x": round(self.x, 2), "z": round(self.z, 2),
                   "r": round(self.rumbo, 1)}
        if self.piloto is not None:
            entrada["p"] = self.piloto
        return entrada


class ReservaVehiculos:
    """Quién conduce qué. Un solo hilo la usa (el del anfitrión), sin cerrojos."""

    def __init__(self, aparcados):
        self._vehiculos = [VehiculoCoop(i, tipo, x, z, r) for i, (tipo, x, z, r) in enumerate(aparcados)
                           if tipo in TIPOS_VEHICULO][:protocolo.N_VEHICULOS_MAX]
        self._de_jugador = {}       # id de jugador -> VehiculoCoop

    def __len__(self):
        return len(self._vehiculos)

    def vehiculos(self):
        return list(self._vehiculos)

    def por_id(self, veh_id):
        if type(veh_id) is not int or not 0 <= veh_id < len(self._vehiculos):
            return None
        return self._vehiculos[veh_id]

    def de_jugador(self, id_jugador):
        return self._de_jugador.get(id_jugador)

    def tipo_de(self, id_jugador):
        v = self._de_jugador.get(id_jugador)
        return None if v is None else v.tipo

    # Intenta montar. Devuelve (True, vehiculo) o (False, motivo). (x, z): posición autorizada del jugador.
    def montar(self, id_jugador, veh_id, x, z):
        if id_jugador in self._de_jugador:
            return False, MOTIVO_YA_MONTADO
        v = self.por_id(veh_id)
        if v is None:
            return False, MOTIVO_NO_EXISTE
        if v.piloto is not None:
            return False, MOTIVO_OCUPADO
        if not all(isinstance(c, (int, float)) and not isinstance(c, bool) and math.isfinite(c) for c in (x, z)):
            return False, MOTIVO_LEJOS
        if math.hypot(v.x - x, v.z - z) > RADIO_MONTAR:
            return False, MOTIVO_LEJOS
        v.piloto = id_jugador
        self._de_jugador[id_jugador] = v
        return True, v

    # Baja al jugador: el vehículo queda aparcado donde estaba. Devuelve el vehículo liberado o None.
    def bajar(self, id_jugador):
        v = self._de_jugador.pop(id_jugador, None)
        if v is not None:
            v.piloto = None
        return v

    # Desconexión / expulsión / salida: mismo efecto que bajar (idempotente).
    liberar_jugador = bajar

    # El vehículo sigue a su piloto (llamar con cada posición ACEPTADA).
    def mover(self, id_jugador, x, z, rumbo):
        v = self._de_jugador.get(id_jugador)
        if v is None:
            return False
        v.x, v.z, v.rumbo = float(x), float(z), float(rumbo) % 360.0
        return True

    # Vuelve todo a su sitio de aparcamiento inicial (nueva partida).
    def reiniciar(self):
        self._de_jugador.clear()
        for v in self._vehiculos:
            v.piloto = None
            v.x, v.z, v.rumbo = v.x0, v.z0, v.rumbo0

    def snapshot(self):
        return [v.a_snap() for v in self._vehiculos]

    def ocupados(self):
        return {v.id: v.piloto for v in self._vehiculos if v.piloto is not None}
