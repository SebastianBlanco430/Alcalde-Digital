# ConexionFlujo para el modo ONLINE: solo sobrescribe lo necesario. La partida ya viene creada
# (FlujoEnLinea), no hay turnos y ante un rechazo del anfitrión se revierte por el camino
# existente (_revertir_al_mundo). Los fundidos programados antes de un rechazo se anulan con
# una «época» para que no abran el interior después de volver al mundo.
import threading

from backend.logica.misiones import EN_MINIJUEGO
from frontend.conexion_flujo import ConexionFlujo


class ConexionEnLinea(ConexionFlujo):

    # flujo: FlujoEnLinea (puede darse después con fijar_flujo). cerrar_red: callable opcional
    # que cierra el ClienteRed (se ejecuta en un hilo aparte para no bloquear).
    def __init__(self, gestor, mapa, flujo=None, cerrar_red=None, **opciones):
        super().__init__(gestor, mapa, lambda sesion: self._flujo_en_linea, **opciones)
        self._flujo_en_linea = None
        self._cerrar_red = cerrar_red
        self._al_cerrar = None           # callable() en el hilo del juego tras volver al inicio (ver fijar_cierre)
        self._epoca = 0
        if flujo is not None:
            self.fijar_flujo(flujo)

    def fijar_flujo(self, flujo):
        self._flujo_en_linea = flujo
        flujo.al_rechazo = self._al_rechazo

    # Cierre de la partida en curso: `cerrar_red` (hilo aparte) cierra cliente y anfitrión; `al_cerrar` corre en el
    # hilo del juego al volver al inicio (quita el BucleRed, devuelve las escenas al hot-seat...).
    def fijar_cierre(self, cerrar_red, al_cerrar=None):
        self._cerrar_red = cerrar_red
        self._al_cerrar = al_cerrar

    # La sesión de selección de rol no existe en línea: se usa el flujo ya fijado.
    def comenzar_partida(self, sesion=None):
        self.flujo = self._flujo_en_linea
        self.flujo.iniciar()
        self._volver_al_mundo()

    # El anfitrión rechazó la interacción (o se perdió la conexión): vuelve al mundo.
    def _al_rechazo(self, motivo):
        flujo = self.flujo
        if flujo is not None and flujo is self._flujo_en_linea and flujo.estado_mision() == EN_MINIJUEGO:
            self._revertir_al_mundo(flujo)

    def _revertir_al_mundo(self, flujo):
        self._epoca += 1                 # anula los fundidos/cinemáticas ya programados
        super()._revertir_al_mundo(flujo)

    def _guardada(self, accion):
        epoca = self._epoca

        def ejecutar():
            if epoca == self._epoca:
                accion()
        return ejecutar

    def _con_transicion(self, accion):
        super()._con_transicion(self._guardada(accion))

    def _con_transicion_lugar(self, accion, texto):
        super()._con_transicion_lugar(self._guardada(accion), texto)

    def terminar_mision(self, resultado):
        flujo = self.flujo
        if flujo is None or flujo.mision_actual() is None or flujo.estado_mision() != EN_MINIJUEGO:
            if flujo is not None:
                flujo.completar_mision(resultado)
            self._restaurar_mundo()
            return
        super().terminar_mision(resultado)

    # Salir de la partida: cierra la red sin bloquear el hilo del juego y vuelve al inicio.
    def volver_al_menu(self):
        if self._cerrar_red is not None:
            threading.Thread(target=self._cerrar_red, name="alcalde-cierre", daemon=True).start()
            self._cerrar_red = None
        super().volver_al_menu()
        al_cerrar, self._al_cerrar = self._al_cerrar, None
        if al_cerrar is not None:
            al_cerrar()
