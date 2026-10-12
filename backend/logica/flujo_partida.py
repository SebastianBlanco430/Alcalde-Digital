# Flujo de partida (modelo puro): coordinador que une SesionJuego +
# SistemaMisiones + Telefono del jugador activo. Las escenas de Ursina solo lo
# llaman; no contienen lógica de turnos ni de misiones.
#
# Ciclo de un turno:
#   iniciar() -> asigna misión al activo y le notifica en SU teléfono
#   actualizar_posicion() por frame -> puede_interactuar() -> iniciar_minijuego()
#   completar_mision(resultado) -> termina, pasa turno y asigna al siguiente
#
# Fin del catálogo (Fase 5): si a un jugador ya no le quedan misiones (ni de su rol ni
# genéricas) su turno se SALTA sin bloquear la partida: el turno pasa al siguiente que
# todavía tenga una. Al saltado se le avisa en su teléfono ("Sin misiones nuevas por
# ahora"). Si a nadie le queda ninguna, la partida terminó (partida_terminada()) y el
# turno avanza una sola vez, al jugador siguiente.
#
# Las transiciones inválidas propagan el ValueError del SistemaMisiones.

MENSAJE_SIN_MISIONES = "Sin misiones nuevas por ahora"


class FlujoPartida:

    def __init__(self, sesion, sistema_misiones):
        self._sesion = sesion
        self._sistema = sistema_misiones

    # Sesión que coordina (solo lectura): las vistas la usan para detectar partida nueva.
    @property
    def sesion(self):
        return self._sesion

    # -- Inicio --

    # Asigna misión al jugador activo. ValueError si la sesión no tiene jugadores.
    def iniciar(self):
        if self._sesion.jugador_activo() is None:
            raise ValueError("No hay jugadores: no se puede iniciar la partida.")
        return self._dar_turno(pasar_antes=False)

    # -- Consulta --

    def mision_actual(self):
        return self._sistema.mision_actual()

    def jugador_activo(self):
        return self._sesion.jugador_activo()

    def estado_mision(self):
        return self._sistema.estado()

    def puede_interactuar(self):
        return self._sistema.puede_interactuar()

    def hay_mision_activa(self):
        return self._sistema.mision_actual() is not None

    # True si no hay misión activa y a ningún jugador le quedan misiones.
    def partida_terminada(self):
        if self.hay_mision_activa():
            return False
        return not any(
            self._sistema.hay_misiones_pendientes(j.rol) for j in self._sesion.jugadores()
        )

    # -- Acciones --

    # Guarda la posición en el jugador activo (fuente de verdad) y delega.
    def actualizar_posicion(self, x, z):
        jugador = self._sesion.jugador_activo()
        jugador.x = x
        jugador.z = z
        self._sistema.actualizar_posicion(x, z)

    # Contexto para la escena del minijuego.
    def iniciar_minijuego(self):
        self._sistema.iniciar_minijuego()
        return {
            "jugador": self._sesion.jugador_activo(),
            "mision": self._sistema.mision_actual(),
            "estado": self._sesion.estado_partida,
        }

    # Revierte iniciar_minijuego (EN_MINIJUEGO -> EN_RADIO) si la escena no pudo abrirse.
    # No toca el turno. ValueError fuera de EN_MINIJUEGO.
    def cancelar_minijuego(self):
        self._sistema.cancelar_minijuego()

    # Cierra la misión, pasa el turno (saltando a quien ya no tenga misiones) y asigna
    # al nuevo activo, que se devuelve.
    def completar_mision(self, resultado):
        self._sistema.completar(resultado)
        self._sistema.terminar()
        self._dar_turno(pasar_antes=True)
        return self._sesion.jugador_activo()

    # -- Internos --

    # Deja como activo al primer jugador con misión pendiente (empezando por el actual si
    # `pasar_antes` es False, o por el siguiente si es True) y se la asigna. Devuelve la
    # misión, o None si a nadie le queda una (entonces, con `pasar_antes`, el turno
    # avanza una vez y el activo es el siguiente jugador).
    def _dar_turno(self, pasar_antes):
        jugadores = self._sesion.jugadores()
        if not any(self._sistema.hay_misiones_pendientes(j.rol) for j in jugadores):
            if pasar_antes:
                self._sesion.pasar_turno()
            self._avisar_sin_misiones(self._sesion.jugador_activo())
            return None
        # Existe alguien con misión: a lo sumo se recorren los N jugadores una vez.
        for _ in range(len(jugadores)):
            if pasar_antes:
                self._sesion.pasar_turno()
            pasar_antes = True
            activo = self._sesion.jugador_activo()
            if self._sistema.hay_misiones_pendientes(activo.rol):
                mision = self._sistema.asignar(activo)
                activo.telefono.notificar(self._sistema.mensaje_notificacion())
                return mision
            self._avisar_sin_misiones(activo)
        return None   # inalcanzable: alguien tenía misión pendiente

    # No repite el aviso si el último mensaje del teléfono ya es ese.
    def _avisar_sin_misiones(self, jugador):
        mensajes = jugador.telefono.mensajes()
        if mensajes and mensajes[-1].texto == MENSAJE_SIN_MISIONES:
            return
        jugador.telefono.notificar(MENSAJE_SIN_MISIONES)
