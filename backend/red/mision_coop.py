# Misiones concurrentes para el modo cooperativo (modelo puro).
#
# - ReservaMisiones: registro COMPARTIDO por todos los jugadores de qué misiones están
#   completadas y cuáles están en curso (y quién las tiene). Es la única fuente de verdad
#   para repartir sin duplicar. `siguiente_para` replica la prioridad de
#   SistemaMisiones._buscar_pendiente (propia, genérica, de roles que nadie juega) pero
#   saltándose las que ya tomó otro jugador.
# - SistemaMisionesCoop: una máquina de estados POR JUGADOR (subclase de SistemaMisiones,
#   que no se modifica). Solo cambia de dónde sale "la siguiente misión": de la reserva.
#
# Nota: SistemaMisiones no tiene método público para buscar la pendiente, así que la
# subclase redefine `_buscar_pendiente` (interno). Un test fija la paridad con la
# implementación real para que un cambio en misiones.py no la rompa en silencio.

from backend.logica import misiones as _misiones
from backend.logica.misiones import SistemaMisiones

# Marca interna: "no se pasó el argumento" (None ya significa "roles desconocidos").
_SIN_DATO = object()


class ReservaMisiones:

    def __init__(self, catalogo):
        self._catalogo = list(catalogo)
        ids = [m.id for m in self._catalogo]
        if len(set(ids)) != len(ids):
            raise ValueError("Catálogo con ids de misión repetidos.")
        self._por_id = {m.id: m for m in self._catalogo}
        self._completadas = []          # ids en orden de cierre
        self._en_curso = {}             # id_mision -> id_jugador
        self._roles_en_juego = None     # None = desconocidos (sin tercer nivel de prioridad)

    # Roles que están en la sala (iterable) o None. Igual que SistemaMisiones.
    def fijar_roles_en_juego(self, roles):
        self._roles_en_juego = None if roles is None else frozenset(roles)

    # -- Consulta --

    def mision(self, id_mision):
        return self._por_id.get(id_mision)

    def completadas(self):
        return list(self._completadas)

    def en_curso(self):
        return dict(self._en_curso)

    def mision_de(self, id_jugador):
        for id_mision, dueno in self._en_curso.items():
            if dueno == id_jugador:
                return self._por_id[id_mision]
        return None

    def disponible(self, id_mision):
        return (id_mision in self._por_id and id_mision not in self._completadas
                and id_mision not in self._en_curso)

    # Primera misión libre para un jugador de `rol`: propia, luego genérica, luego de un rol
    # que nadie juega (si se conocen los roles). `roles_en_juego` opcional: sobrescribe los
    # fijados (útil para pruebas de paridad). None si no queda ninguna.
    def siguiente_para(self, rol, roles_en_juego=_SIN_DATO):
        roles = self._roles_en_juego if roles_en_juego is _SIN_DATO else (
            None if roles_en_juego is None else frozenset(roles_en_juego))
        for m in self._catalogo:
            if m.rol == rol and self.disponible(m.id):
                return m
        for m in self._catalogo:
            if m.rol is None and self.disponible(m.id):
                return m
        if roles is not None:
            for m in self._catalogo:
                if m.rol is not None and m.rol not in roles and self.disponible(m.id):
                    return m
        return None

    # True si alguien de estos roles aún puede recibir una misión libre.
    def quedan_para(self, roles):
        return any(self.siguiente_para(rol) is not None for rol in roles)

    # -- Cambios --

    # Reserva la misión para el jugador. ValueError si no existe o ya no está libre.
    def reservar(self, id_mision, id_jugador):
        if id_mision not in self._por_id:
            raise ValueError(f"Misión inexistente: {id_mision!r}")
        if not self.disponible(id_mision):
            raise ValueError(f"La misión {id_mision!r} ya no está disponible.")
        if self.mision_de(id_jugador) is not None:
            raise ValueError(f"El jugador {id_jugador!r} ya tiene una misión en curso.")
        self._en_curso[id_mision] = id_jugador

    # Devuelve la misión del jugador al fondo común. Devuelve la Mision o None.
    def liberar(self, id_jugador):
        mision = self.mision_de(id_jugador)
        if mision is not None:
            del self._en_curso[mision.id]
        return mision

    # Registra como completada la misión en curso del jugador (ValueError si no es suya).
    def completar(self, id_mision, id_jugador):
        if self._en_curso.get(id_mision) != id_jugador:
            raise ValueError(f"La misión {id_mision!r} no está en curso para el jugador {id_jugador!r}.")
        del self._en_curso[id_mision]
        self._completadas.append(id_mision)


class SistemaMisionesCoop(SistemaMisiones):

    def __init__(self, mapa, catalogo, reserva, id_jugador, **kwargs):
        super().__init__(mapa, catalogo, **kwargs)
        self._reserva = reserva
        self.id_jugador = id_jugador

    @property
    def reserva(self):
        return self._reserva

    # Mantiene sincronizados el sistema y la reserva compartida.
    def fijar_roles_en_juego(self, roles):
        roles = None if roles is None else list(roles)
        super().fijar_roles_en_juego(roles)
        self._reserva.fijar_roles_en_juego(roles)

    # La reserva manda: tiene en cuenta lo completado/en curso de TODOS los jugadores.
    def _buscar_pendiente(self, rol):
        return self._reserva.siguiente_para(rol)

    # Igual que SistemaMisiones.asignar, pero toma la misión de la reserva y la reserva.
    def asignar(self, jugador):
        mision = super().asignar(jugador)
        if mision is not None:
            self._reserva.reservar(mision.id, self.id_jugador)
        return mision

    # Asigna una misión concreta (decidida por el anfitrión). ValueError si ya hay una
    # activa, no existe o ya no está libre.
    def asignar_por_id(self, id_mision):
        if self._estado != _misiones.SIN_MISION:
            raise ValueError(
                f"Ya hay una misión activa (estado {self._estado!r}); termínala antes de asignar otra."
            )
        mision = self._reserva.mision(id_mision)
        if mision is None:
            raise ValueError(f"Misión inexistente: {id_mision!r}")
        self._reserva.reservar(id_mision, self.id_jugador)
        self._mision = mision
        self._estado = _misiones.NOTIFICADA
        return mision

    # Suelta la misión activa (jugador que sale o cae del todo) y vuelve a SIN_MISION sin
    # contarla como completada. Devuelve la Mision liberada o None.
    def liberar(self):
        mision = self._mision
        if mision is not None:
            self._reserva.liberar(self.id_jugador)
        self._mision = None
        self._estado = _misiones.SIN_MISION
        return mision

    # Completa y además la anota en la reserva compartida.
    def completar(self, resultado):
        mision = super().completar(resultado)
        self._reserva.completar(mision.id, self.id_jugador)
        return mision
