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

from backend.logica.misiones import EN_MINIJUEGO

# Nombres con que main.py registra las escenas en el gestor.
INICIO = "inicio"
SELECCION_ROL = "seleccion_rol"
MUNDO = "mundo"
JUEGO = "juego"


class ConexionFlujo:

    # gestor: GestorEscenas. mapa: MapaCiudad (se conserva para consultas futuras). fabrica_flujo(sesion)
    # -> FlujoPartida (inyectada para poder usar catálogos/mapas falsos). transicion: ver arriba.
    # grafo_social (opcional): GrafoSocial que se entrega a la escena de juego para animar
    # la propagación de cada decisión; sin él la escena no muestra el panel de alcance.
    def __init__(self, gestor, mapa, fabrica_flujo, transicion=None, grafo_social=None):
        self._gestor = gestor
        self._mapa = mapa
        self._fabrica_flujo = fabrica_flujo
        self._transicion = transicion
        self._grafo_social = grafo_social
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
        self.flujo.completar_mision(resultado)
        self._con_transicion(self._volver_al_mundo)

    # Mundo (panel "Partida terminada"): regresa al menú de inicio.
    def volver_al_menu(self):
        self._gestor.cambiar_a(INICIO)

    def _volver_al_mundo(self):
        self._gestor.cambiar_a(MUNDO, flujo=self.flujo)

    def _transicion_en_curso(self):
        return self._transicion is not None and self._transicion.ocupada

    def _con_transicion(self, accion):
        if self._transicion is None:
            accion()
        else:
            self._transicion.ejecutar(accion)
