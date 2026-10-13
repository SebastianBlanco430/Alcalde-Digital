# Sesión de juego (modelo puro): jugadores hot-seat (1 a 4) con roles
# exclusivos, turnos rotativos y UN EstadoPartida compartido (los indicadores
# son de la ciudad, no de cada jugador). Serializable a JSON.

from backend.logica.roles import ORDEN_ROLES, ROLES
from backend.logica.telefono import Telefono

MAX_JUGADORES = 4


# Un jugador: nombre, rol, posición (x, z) en el plano del mundo y su teléfono.
# La posición aquí es la fuente de verdad (el mundo gráfico solo la dibuja).
class Jugador:

    def __init__(self, nombre, rol, x, z, telefono=None):
        self.nombre = nombre
        self.rol = rol
        self.x = x
        self.z = z
        self.telefono = telefono if telefono is not None else Telefono()

    def a_dict(self):
        return {
            "nombre": self.nombre,
            "rol": self.rol,
            "x": self.x,
            "z": self.z,
            "telefono": self.telefono.a_dict(),
        }

    @classmethod
    def desde_dict(cls, datos):
        return cls(
            datos["nombre"], datos["rol"], datos["x"], datos["z"],
            Telefono.desde_dict(datos["telefono"]),
        )

    def __repr__(self):
        return f"Jugador({self.nombre!r}, {self.rol!r}, x={self.x}, z={self.z})"


# `estado_partida` se inyecta y se comparte entre todos los jugadores.
# `escala_mundo` multiplica el spawn de cada rol (roles.py guarda los del mapa pequeño;
# el mundo 3D usa ×4). ValueError si no es positiva.
class SesionJuego:

    def __init__(self, estado_partida, escala_mundo=1.0):
        if escala_mundo <= 0:
            raise ValueError("escala_mundo debe ser positiva.")
        self.estado_partida = estado_partida
        self.escala_mundo = escala_mundo
        self._jugadores = []
        self._indice_turno = 0
        self._numero_turno = 0

    # -- Jugadores --

    # Crea el jugador en el spawn de su rol. ValueError si el rol no existe,
    # ya está tomado o ya hay 4 jugadores. Nombre vacío -> "Jugador N".
    def agregar_jugador(self, nombre, rol):
        if rol not in ROLES:
            raise ValueError(f"Rol inexistente: {rol!r}")
        if len(self._jugadores) >= MAX_JUGADORES:
            raise ValueError(f"Ya hay {MAX_JUGADORES} jugadores; no caben más.")
        if any(j.rol == rol for j in self._jugadores):
            raise ValueError(f"El rol {rol!r} ya está tomado.")

        nombre = (nombre or "").strip()
        if not nombre:
            nombre = self._nombre_automatico()
        elif any(j.nombre.strip() == nombre for j in self._jugadores):
            # El mundo y el HUD usan el nombre como clave: no puede haber dos iguales.
            raise ValueError(f"Ya existe un jugador llamado {nombre!r}.")
        info = ROLES[rol]
        jugador = Jugador(nombre, rol, info.spawn_x * self.escala_mundo, info.spawn_y * self.escala_mundo)
        self._jugadores.append(jugador)
        return jugador

    # "Jugador N" con el primer N (desde jugadores+1) que no choque con un nombre ya usado.
    def _nombre_automatico(self):
        usados = {j.nombre.strip() for j in self._jugadores}
        n = len(self._jugadores) + 1
        while f"Jugador {n}" in usados:
            n += 1
        return f"Jugador {n}"

    # Roles libres, en ORDEN_ROLES.
    def roles_disponibles(self):
        tomados = {j.rol for j in self._jugadores}
        return [rol for rol in ORDEN_ROLES if rol not in tomados]

    # Copia de la lista (los Jugador son los mismos objetos).
    def jugadores(self):
        return list(self._jugadores)

    # -- Turnos --

    def jugador_activo(self):
        if not self._jugadores:
            return None
        return self._jugadores[self._indice_turno]

    # Rotación circular; devuelve el nuevo jugador activo.
    def pasar_turno(self):
        if not self._jugadores:
            raise ValueError("No hay jugadores: no se puede pasar el turno.")
        self._indice_turno = (self._indice_turno + 1) % len(self._jugadores)
        self._numero_turno += 1
        return self.jugador_activo()

    # Total de turnos pasados desde el inicio (arranca en 0).
    def numero_turno(self):
        return self._numero_turno

    # -- Serialización (JSON) --

    def a_dict(self):
        return {
            "jugadores": [j.a_dict() for j in self._jugadores],
            "indice_turno": self._indice_turno,
            "numero_turno": self._numero_turno,
            "indicadores": self.estado_partida.indicadores(),
        }

    # Reconstruye la sesión y fija los indicadores en el `estado_partida` dado.
    # ValueError (sin tocar el estado) si los datos violan las reglas de la sesión:
    # más de 4 jugadores, roles o nombres repetidos, o índice de turno fuera de rango.
    @classmethod
    def desde_dict(cls, datos, estado_partida, escala_mundo=1.0):
        jugadores = [Jugador.desde_dict(d) for d in datos["jugadores"]]
        if len(jugadores) > MAX_JUGADORES:
            raise ValueError(f"Datos guardados con más de {MAX_JUGADORES} jugadores.")
        roles = [j.rol for j in jugadores]
        if any(rol not in ROLES for rol in roles) or len(set(roles)) != len(roles):
            raise ValueError("Datos guardados con roles inexistentes o repetidos.")
        nombres = [j.nombre.strip() for j in jugadores]
        if len(set(nombres)) != len(nombres):
            raise ValueError("Datos guardados con nombres de jugador repetidos.")
        indice = datos["indice_turno"]
        if not 0 <= indice < max(len(jugadores), 1):
            raise ValueError(f"Índice de turno fuera de rango: {indice!r}.")

        sesion = cls(estado_partida, escala_mundo=escala_mundo)
        sesion._jugadores = jugadores
        sesion._indice_turno = indice
        sesion._numero_turno = datos["numero_turno"]
        estado_partida.fijar_indicadores(datos["indicadores"])
        return sesion

    def __repr__(self):
        return f"SesionJuego(jugadores={len(self._jugadores)}, turno={self._numero_turno})"
