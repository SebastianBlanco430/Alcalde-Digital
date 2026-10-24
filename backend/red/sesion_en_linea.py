# Sesión en línea (modelo puro, sin red ni ursina): extiende SesionJuego / Jugador con lo
# que necesita el juego cooperativo en tiempo real: un SLOT estable (0..3) por jugador,
# conexión/desconexión con reloj inyectado, posición completa (x, z, y, rumbo, velocidad,
# banderas) y el hash del token de reconexión (el token en claro NUNCA se guarda).
#
# No reescribe sesion.py: reutiliza SesionJuego.agregar_jugador (validación de rol, nombre
# único, máximo 4, spawn) y solo cambia el objeto creado por una subclase de Jugador.
# El hot-seat sigue usando SesionJuego/Jugador intactos.

import hashlib
import hmac
import math

from backend.logica.roles import ROLES
from backend.logica.sesion import MAX_JUGADORES, Jugador, SesionJuego

# Banderas de estado visibles para los demás jugadores (se sincronizan en cada snap). «caballito» (bit 16): la
# rueda delantera del vehículo que conduce está levantada (frontend/vehiculo_calculos.py); solo vale con vehículo.
BANDERAS = ("en_aire", "escalera", "dentro", "vehiculo", "caballito")


# Convierte un iterable de banderas a máscara de bits (las desconocidas se ignoran).
def banderas_a_mascara(banderas):
    mascara = 0
    for i, nombre in enumerate(BANDERAS):
        if nombre in banderas:
            mascara |= 1 << i
    return mascara


# Inversa de banderas_a_mascara; ignora bits fuera de rango.
def mascara_a_banderas(mascara):
    if not isinstance(mascara, int) or isinstance(mascara, bool):
        return frozenset()
    return frozenset(nombre for i, nombre in enumerate(BANDERAS) if mascara & (1 << i))


# Hash estable del token de reconexión (SHA-256 hex). El anfitrión solo guarda esto.
def hash_token(token):
    return hashlib.sha256(str(token).encode("utf-8")).hexdigest()


def _finito(*valores):
    return all(isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) for v in valores)


# Un jugador conectado por red. `id` es el slot (0..3) y no cambia mientras dura la sala.
class JugadorEnLinea(Jugador):

    def __init__(self, nombre, rol, x, z, id=0, telefono=None, token_hash=None):
        super().__init__(nombre, rol, x, z, telefono)
        self.id = id
        self.conectado = True
        self.desconectado_desde = None   # instante (reloj inyectado) del corte, o None
        self.y = 0.0
        self.rumbo = 0.0
        self.velocidad = 0.0
        self.banderas = frozenset()
        self.token_hash = token_hash

    # Fija las banderas conservando solo las conocidas.
    def fijar_banderas(self, banderas):
        self.banderas = frozenset(b for b in (banderas or ()) if b in BANDERAS)

    def tiene_bandera(self, nombre):
        return nombre in self.banderas

    # True si `token` (en claro) corresponde al hash guardado; comparación en tiempo constante.
    def coincide_token(self, token):
        if not self.token_hash or not isinstance(token, str) or not token:
            return False
        return hmac.compare_digest(self.token_hash, hash_token(token))

    # Estado de movimiento para el snapshot (claves cortas del protocolo).
    def estado_movimiento(self):
        return {
            "i": self.id, "x": self.x, "z": self.z, "y": self.y,
            "r": self.rumbo, "v": self.velocidad, "f": banderas_a_mascara(self.banderas),
        }

    # No incluye el hash del token (no debe salir del anfitrión ni a disco).
    def a_dict(self):
        datos = super().a_dict()
        datos.update({
            "id": self.id, "conectado": self.conectado,
            "y": self.y, "rumbo": self.rumbo, "velocidad": self.velocidad,
            "banderas": sorted(self.banderas),
        })
        return datos

    def __repr__(self):
        return (f"JugadorEnLinea(id={self.id}, {self.nombre!r}, {self.rol!r}, "
                f"conectado={self.conectado})")


class SesionEnLinea(SesionJuego):

    # Añade un jugador en el primer slot libre (0..3). Mismas ValueError que SesionJuego
    # (rol inexistente/tomado, 4 jugadores, nombre repetido). Los desconectados en gracia
    # siguen ocupando su slot y su rol.
    def agregar_jugador(self, nombre, rol, token_hash=None):
        base = super().agregar_jugador(nombre, rol)
        usados = {j.id for j in self._jugadores if isinstance(j, JugadorEnLinea)}
        slot = next(i for i in range(MAX_JUGADORES) if i not in usados)
        nuevo = JugadorEnLinea(base.nombre, base.rol, base.x, base.z, id=slot,
                               telefono=base.telefono, token_hash=token_hash)
        self._jugadores[-1] = nuevo
        return nuevo

    # -- Consulta --

    def por_id(self, id_jugador):
        for j in self._jugadores:
            if j.id == id_jugador:
                return j
        return None

    def por_token_hash(self, token_hash):
        for j in self._jugadores:
            if j.token_hash and token_hash and hmac.compare_digest(j.token_hash, token_hash):
                return j
        return None

    def por_nombre(self, nombre):
        for j in self._jugadores:
            if j.nombre == nombre:
                return j
        return None

    def jugadores_conectados(self):
        return [j for j in self._jugadores if j.conectado]

    # Roles de todos los que siguen en la sala (incluye los que están en gracia).
    def roles_en_juego(self):
        return [j.rol for j in self._jugadores]

    def roles_conectados(self):
        return [j.rol for j in self._jugadores if j.conectado]

    # -- Cambios --

    # Quita al jugador (libera slot, rol y nombre). Devuelve el jugador o None si no existe.
    def quitar_jugador(self, id_jugador):
        jugador = self.por_id(id_jugador)
        if jugador is None:
            return None
        self._jugadores.remove(jugador)
        if not 0 <= self._indice_turno < max(len(self._jugadores), 1):
            self._indice_turno = 0
        return jugador

    # Marca el corte de red; `ahora` viene del reloj inyectado. Idempotente.
    def desconectar(self, id_jugador, ahora):
        jugador = self.por_id(id_jugador)
        if jugador is None:
            raise ValueError(f"No existe el jugador {id_jugador!r}.")
        if jugador.conectado:
            jugador.conectado = False
            jugador.desconectado_desde = ahora
        return jugador

    def reconectar(self, id_jugador):
        jugador = self.por_id(id_jugador)
        if jugador is None:
            raise ValueError(f"No existe el jugador {id_jugador!r}.")
        jugador.conectado = True
        jugador.desconectado_desde = None
        return jugador

    # Cambia el rol si está libre. ValueError si no existe o lo tiene otro.
    def cambiar_rol(self, id_jugador, rol):
        jugador = self.por_id(id_jugador)
        if jugador is None:
            raise ValueError(f"No existe el jugador {id_jugador!r}.")
        if rol not in ROLES:
            raise ValueError(f"Rol inexistente: {rol!r}")
        if any(j.rol == rol and j is not jugador for j in self._jugadores):
            raise ValueError(f"El rol {rol!r} ya está tomado.")
        info = ROLES[rol]
        jugador.rol = rol
        jugador.x = info.spawn_x * self.escala_mundo
        jugador.z = info.spawn_y * self.escala_mundo
        return jugador

    # Guarda posición y estado de movimiento. Devuelve False (sin cambiar nada) si algún
    # número no es finito; la validación fina de movimiento vive en otro módulo.
    def mover(self, id_jugador, x, z, y=0.0, rumbo=0.0, velocidad=0.0, banderas=()):
        jugador = self.por_id(id_jugador)
        if jugador is None or not _finito(x, z, y, rumbo, velocidad):
            return False
        jugador.x, jugador.z, jugador.y = float(x), float(z), float(y)
        jugador.rumbo, jugador.velocidad = float(rumbo), float(velocidad)
        jugador.fijar_banderas(banderas)
        return True

    # Lista de estados de movimiento (para el snap), en orden de slot.
    def snapshot_jugadores(self):
        return [j.estado_movimiento() for j in sorted(self._jugadores, key=lambda j: j.id)]

    def __repr__(self):
        return f"SesionEnLinea(jugadores={len(self._jugadores)}, conectados={len(self.jugadores_conectados())})"
