# Cableado del flujo de pantallas (sin Ursina, se prueba con escenas falsas):
# inicio -> seleccion_rol -> mundo <-> juego. Las escenas no conocen al gestor,
# reciben los métodos de esta clase como callbacks. Toda la lógica de turnos y
# misiones está en FlujoPartida (backend); aquí solo se decide a qué escena ir.
#
# Transición (opcional, inyectada): cualquier objeto con `ocupada` y `ejecutar(accion)`
# (frontend/fundido.Fundido o su Entity frontend/transicion.Transicion). E -> juego y
# juego -> mundo se hacen con un fundido a negro: el MODELO avanza en el acto (E marca
# EN_MINIJUEGO; al terminar el lote se completa la misión y pasa el turno) y solo el
# CAMBIO DE ESCENA espera a que la pantalla esté negra. Sin transición todo es inmediato.
#
# Mundo 3D (`con_interior=True`, lo pone main.py): E reproduce la cinemática de entrada (la
# EscenaMundo, inyectada en `cinematicas`), luego un fundido con el nombre del lugar
# (`transicion_lugar`, con negro sostenido) lleva al INTERIOR (modo 'sentarse'); cuando el
# personaje se sienta y la cámara llega al monitor viene el JUEGO con marco de monitor. Al
# terminar el lote: fundido -> INTERIOR ('levantarse') -> fundido -> MUNDO (con `salida`, la
# cinemática de salir por la puerta). El modelo NO tiene estados nuevos: E marca EN_MINIJUEGO
# al instante y el control queda congelado durante todo el camino. Si algo falla al abrir una
# escena se revierte EN_MINIJUEGO -> EN_RADIO (`cancelar_minijuego`) y se devuelve el control
# en el mundo; ningún camino deja la pantalla en negro (el Fundido se libera solo).

from backend.logica.misiones import EN_MINIJUEGO

# Nombres con que main.py registra las escenas en el gestor.
INICIO = "inicio"
SELECCION_ROL = "seleccion_rol"
MUNDO = "mundo"
JUEGO = "juego"
INTERIOR = "interior"


class ConexionFlujo:

    # gestor: GestorEscenas. mapa: MapaCiudad (se conserva para consultas futuras). fabrica_flujo(sesion)
    # -> FlujoPartida (inyectada para poder usar catálogos/mapas falsos). transicion: ver arriba.
    # grafo_social (opcional): GrafoSocial que se entrega a la escena de juego para animar
    # la propagación de cada decisión; sin él la escena no muestra el panel de alcance.
    # transicion_lugar: fundido con negro sostenido y texto (la entrada al edificio); sin él se
    # usa `transicion`. con_interior: cadena 3D (ver arriba). `cinematicas`: objeto con
    # reproducir_entrada(jugador, lugar, al_terminar) (la EscenaMundo); None = sin cinemática.
    def __init__(self, gestor, mapa, fabrica_flujo, transicion=None, grafo_social=None,
                 transicion_lugar=None, con_interior=False):
        self._gestor = gestor
        self._mapa = mapa
        self._fabrica_flujo = fabrica_flujo
        self._transicion = transicion
        self._transicion_lugar = transicion_lugar
        self._grafo_social = grafo_social
        self._con_interior = con_interior
        self.cinematicas = None
        # Callables sin argumentos que saltan lo que esté en curso (fundidos y cinemáticas de las
        # escenas); main los registra y Espacio/Enter los llama. Cada uno devuelve False si no hay nada.
        self.saltadores = []
        self.flujo = None

    # Inicio: "Empezar" lleva a la selección de roles.
    def ir_a_seleccion(self):
        self._gestor.cambiar_a(SELECCION_ROL)

    # Selección: la sesión está lista; se crea el flujo y se entra al mundo.
    def comenzar_partida(self, sesion):
        self.flujo = self._fabrica_flujo(sesion)
        self.flujo.iniciar()
        self._volver_al_mundo()

    # Mundo: tecla E. Solo abre el minijuego si el jugador activo ya llegó al radio
    # del destino (EN_RADIO); el controlador del mundo ya filtra, esto es defensa.
    def interactuar(self):
        flujo = self.flujo
        if flujo is None or self._transicion_en_curso() or not flujo.puede_interactuar():
            return
        contexto = flujo.iniciar_minijuego()
        if self._con_interior:
            self._entrar_al_edificio(flujo, contexto)
            return

        def abrir_juego():
            try:
                self._gestor.cambiar_a(
                    JUEGO, jugador=contexto["jugador"], estado=contexto["estado"],
                    mision=contexto["mision"], al_terminar=self.terminar_mision,
                    grafo_social=self._grafo_social,
                )
            except BaseException:
                # No se pudo abrir el minijuego: se revierte EN_MINIJUEGO -> EN_RADIO para
                # que la misión no quede atascada (el jugador puede volver a pulsar E).
                if flujo.estado_mision() == EN_MINIJUEGO:
                    flujo.cancelar_minijuego()
                raise

        self._con_transicion(abrir_juego)

    # Juego: terminó el lote; se cierra la misión, pasa el turno y se vuelve al mundo.
    # Si el cambio de escena de vuelta falla no hay nada que revertir ni colgado: el modelo
    # ya quedó coherente (misión cerrada, turno pasado, la siguiente misión asignada) y el
    # Fundido se libera solo antes de propagar la excepción.
    def terminar_mision(self, resultado):
        if self._con_interior:
            self._salir_del_edificio(resultado)
            return
        self.flujo.completar_mision(resultado)
        self._con_transicion(self._volver_al_mundo)

    # Espacio / Enter: salta lo primero que esté en curso (en el orden de `saltadores`; cada uno
    # devuelve True si actuó). Una pulsación no salta dos cosas a la vez.
    def saltar_cinematica(self):
        for saltar in list(self.saltadores):
            if saltar():
                return True
        return False

    # Mundo (panel "Partida terminada"): regresa al menú de inicio.
    def volver_al_menu(self):
        self._gestor.cambiar_a(INICIO)

    def _volver_al_mundo(self):
        self._gestor.cambiar_a(MUNDO, flujo=self.flujo)

    def _transicion_en_curso(self):
        return any(t is not None and t.ocupada for t in (self._transicion, self._transicion_lugar))

    def _con_transicion(self, accion):
        if self._transicion is None:
            accion()
        else:
            self._transicion.ejecutar(accion)

    # Como _con_transicion pero con el fundido del lugar (negro sostenido + nombre del lugar).
    def _con_transicion_lugar(self, accion, texto):
        if self._transicion_lugar is not None:
            self._transicion_lugar.ejecutar(accion, texto=texto)
        else:
            self._con_transicion(accion)

    # -- Cadena 3D --

    def _titulo_del_lugar(self, lugar):
        try:
            return self._mapa.edificio_de(lugar).titulo
        except (AttributeError, ValueError):
            return lugar

    # Revierte EN_MINIJUEGO -> EN_RADIO y devuelve el control en el mundo (sin cinemática).
    def _revertir_al_mundo(self, flujo):
        if flujo.estado_mision() == EN_MINIJUEGO:
            flujo.cancelar_minijuego()
        self._restaurar_mundo()

    # Mejor esfuerzo: si ni eso se puede, el error original es el que importa.
    def _restaurar_mundo(self):
        try:
            self._volver_al_mundo()
        except BaseException:  # noqa: BLE001
            pass

    def _entrar_al_edificio(self, flujo, contexto):
        jugador, mision = contexto["jugador"], contexto["mision"]
        lugar, titulo = mision.destino, self._titulo_del_lugar(mision.destino)

        def abrir_juego():
            try:
                self._gestor.cambiar_a(
                    JUEGO, jugador=jugador, estado=contexto["estado"], mision=mision,
                    al_terminar=self.terminar_mision, grafo_social=self._grafo_social,
                    marco=True, lugar=titulo)
            except BaseException:
                self._revertir_al_mundo(flujo)
                raise

        def abrir_interior():
            try:
                self._gestor.cambiar_a(INTERIOR, jugador=jugador, lugar=lugar, modo="sentarse",
                                       al_terminar=abrir_juego)
            except BaseException:
                self._revertir_al_mundo(flujo)
                raise

        def tras_la_entrada():
            self._con_transicion_lugar(abrir_interior, texto=titulo)

        if self.cinematicas is None:
            tras_la_entrada()
        else:
            self.cinematicas.reproducir_entrada(jugador, lugar, tras_la_entrada)

    def _salir_del_edificio(self, resultado):
        flujo = self.flujo
        saliente, lugar = flujo.jugador_activo(), flujo.mision_actual().destino
        flujo.completar_mision(resultado)       # el modelo avanza en el acto: pasa el turno

        def salir_al_mundo():
            def abrir_mundo():
                self._gestor.cambiar_a(MUNDO, flujo=flujo, salida={"jugador": saliente, "lugar": lugar})
            self._con_transicion(abrir_mundo)

        def volver_al_interior():
            try:
                self._gestor.cambiar_a(INTERIOR, jugador=saliente, lugar=lugar, modo="levantarse",
                                       al_terminar=salir_al_mundo)
            except BaseException:
                self._restaurar_mundo()
                raise

        self._con_transicion(volver_al_interior)
