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
#
# REPARTO POR DÍAS (contrato-dias.md; ALCALDE_MISIONES_DIAS): «no hay nada HOY» ya no es «no queda nada». El salto de
# turno mira lo ofrecible hoy (hay_misiones_pendientes); la partida solo termina por misiones cuando no queda nada en la
# SEMANA (queda_algo_en_la_semana). Con el reloj, el aviso del día agotado es MENSAJE_SIN_MISIONES_HOY y, al cambiar de
# día (fijar_dia_misiones, lo llama FlujoConTiempo), el activo sin misión recibe una del día nuevo.

MENSAJE_SIN_MISIONES = "Sin misiones nuevas por ahora"
MENSAJE_SIN_MISIONES_HOY = "Sin misiones nuevas por hoy. Mañana llegan más."


class FlujoPartida:

    def __init__(self, sesion, sistema_misiones):
        self._sesion = sesion
        self._sistema = sistema_misiones
        self._sincronizar_roles()

    # Sesión que coordina (solo lectura): las vistas la usan para detectar partida nueva.
    @property
    def sesion(self):
        return self._sesion

    # -- Inicio --

    # Asigna misión al jugador activo. ValueError si la sesión no tiene jugadores.
    def iniciar(self):
        self._sincronizar_roles()
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

    # Catálogo de misiones de la partida, en orden (copia). FlujoConGameState lo usa para las cartas de misión y para
    # escalar la confianza por mapa.
    def catalogo_misiones(self):
        return self._sistema.catalogo()

    # Veredicto (A2d): ids de las misiones completadas que quedaron pasadas / falladas (copias).
    def misiones_pasadas(self):
        return self._sistema.pasadas()

    def misiones_falladas(self):
        return self._sistema.falladas()

    # True si no hay misión activa y a ningún jugador le quedan misiones (en toda la semana, con reparto por días).
    def partida_terminada(self):
        self._sincronizar_roles()
        if self.hay_mision_activa():
            return False
        return not any(self._queda_en_la_semana(j.rol) for j in self._sesion.jugadores())

    # -- Reparto por días (sin reparto: no hace nada, None y []) --

    # Lo llama quien tiene el reloj (FlujoConTiempo) en cada cambio de día (y de tramo de hora). Si el día cambió y el
    # activo está sin misión, le da una del día nuevo (o al siguiente que tenga). True si el día cambió.
    def fijar_dia_misiones(self, dia, hora=None):
        fijar = getattr(self._sistema, "fijar_dia", None)
        if not callable(fijar) or not fijar(dia, hora):
            return False
        if self._sistema.mision_actual() is None and self._sesion.jugador_activo() is not None:
            self._dar_turno(pasar_antes=False)
        return True

    # {"dia", "ofrecidas", "hechas", "pendientes", "arrastradas", "caducadas", "semana"} o None sin reparto por días.
    def resumen_dia(self):
        leer = getattr(self._sistema, "resumen_dia", None)
        return leer() if callable(leer) else None

    # Ids de las misiones caducadas, en el orden en que caducaron (no están ni en pasadas ni en falladas).
    def misiones_caducadas(self):
        leer = getattr(self._sistema, "caducadas", None)
        return list(leer()) if callable(leer) else []

    # Lo que se juega en la partida (semana sorteada + reservas abiertas); sin reparto, el catálogo entero.
    def catalogo_semana(self):
        leer = getattr(self._sistema, "catalogo_semana", None)
        return leer() if callable(leer) else self._sistema.catalogo()

    # Red de seguridad (FlujoConTiempo): vuelve al reparto de siempre y, si el activo quedó sin misión, le da una.
    def apagar_reparto_dias(self):
        apagar = getattr(self._sistema, "apagar_reparto", None)
        if not callable(apagar):
            return
        apagar()
        if self._sistema.mision_actual() is None and self._sesion.jugador_activo() is not None:
            self._dar_turno(pasar_antes=False)

    def _queda_en_la_semana(self, rol):
        queda = getattr(self._sistema, "queda_algo_en_la_semana", None)
        return queda(rol) if callable(queda) else self._sistema.hay_misiones_pendientes(rol)

    # -- Acciones --

    # Guarda la posición en el jugador activo (fuente de verdad) y delega.
    def actualizar_posicion(self, x, z):
        jugador = self._sesion.jugador_activo()
        if jugador is None:
            raise ValueError("No hay jugadores: no se puede actualizar la posición.")
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

    # Misiones digitales (parkour / investigación): si la misión activa se cumplió por la señal del `game_state`, la
    # cierra, pasa el turno (como completar_mision) y asigna al nuevo activo. True si cerró una; False si no (sin misión
    # activa, de verificar o sin señal). No toca nada en ese caso.
    def revisar_misiones_digitales(self, game_state):
        if self._sistema.completar_por_senal(game_state) is None:
            return False
        self._sistema.terminar()
        self._dar_turno(pasar_antes=True)
        return True

    # -- Guardado (JSON) --

    # Estado de las misiones (SistemaMisiones.a_dict): la activa, su estado, las completadas y sus veredictos.
    def misiones_a_dict(self):
        return self._sistema.a_dict()

    # Sustituye el sistema de misiones por el guardado en `datos`, con el MISMO mapa, catálogo y punto de interacción.
    # ValueError (sin cambiar nada) si los datos no cuadran con el catálogo de esta partida (p. ej. son de otro mapa).
    def restaurar_misiones(self, datos):
        viejo = self._sistema
        conocidos = {m.id for m in viejo.catalogo()}
        ajenos = [i for i in datos.get("completadas", ()) if i not in conocidos]
        if ajenos:
            raise ValueError(f"Misiones guardadas que no existen en este catálogo: {ajenos[:3]}")
        self._sistema = type(viejo).desde_dict(datos, viejo._mapa, viejo.catalogo(), viejo._punto_interaccion)
        self._sincronizar_roles()

    # -- Internos --

    # Deja como activo al primer jugador con misión pendiente (empezando por el actual si
    # `pasar_antes` es False, o por el siguiente si es True) y se la asigna. Devuelve la
    # misión, o None si a nadie le queda una (entonces, con `pasar_antes`, el turno
    # avanza una vez y el activo es el siguiente jugador).
    def _dar_turno(self, pasar_antes):
        self._sincronizar_roles()
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

    # Informa al sistema de misiones qué roles juegan (los jugadores pueden cambiar si se
    # carga otra partida); así las misiones de roles ausentes se reparten entre los presentes.
    def _sincronizar_roles(self):
        self._sistema.fijar_roles_en_juego(j.rol for j in self._sesion.jugadores())

    # No repite el aviso si el último mensaje del teléfono ya es ese. Con el reloj y algo aún en la semana, el aviso dice
    # que mañana llegan más.
    def _avisar_sin_misiones(self, jugador):
        texto = MENSAJE_SIN_MISIONES
        con_reloj = getattr(self._sistema, "reparto_con_reloj", None)
        if callable(con_reloj) and con_reloj() and self._queda_en_la_semana(jugador.rol):
            texto = MENSAJE_SIN_MISIONES_HOY
        mensajes = jugador.telefono.mensajes()
        if mensajes and mensajes[-1].texto == texto:
            return
        jugador.telefono.notificar(texto)
