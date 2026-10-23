# Arranque de la partida ONLINE real: conecta el lobby (EscenaSala) con el juego. SOLO lo carga main.py con
# ONLINE=True (importa online_flujo y, por él, backend.red).
#
# Recibe `al_empezar(cliente, info)` (info: ver online_servicios) cuando todos están listos y el anfitrión pulsó
# «Iniciar partida», y:
#   1. crea el FlujoEnLinea (el rol viene de la sala: NO hay selección de rol) y le aplica el evento «inicio»;
#   2. instala el BucleRed global (drena la red, envía la posición local a 20 Hz, reparte eventos al flujo);
#   3. hace que las escenas usen la ConexionEnLinea (en vez de la del hot-seat) y entra a MUNDO;
#   4. al volver al menú (fin de partida, sala cerrada, pausa -> «Volver al menú»): quita el BucleRed, cierra cliente
#      y anfitrión (en un hilo aparte, ver ConexionEnLinea.volver_al_menu), devuelve las escenas al hot-seat y va al INICIO.
# Si algo falla al arrancar se limpia todo y se vuelve al INICIO (nunca queda un hilo ni un bucle colgado).

import logging

from frontend.conexion_flujo import INICIO

_registro = logging.getLogger("alcalde.online.arranque")


class ArranqueOnline:

    # gestor: GestorEscenas. mundo: MundoCiudad. conexion: ConexionEnLinea ya creada (comparte transiciones con la
    # del hot-seat). activar(bool): hace que las escenas usen la conexión en línea (True) o la de siempre (False).
    # escena_mundo: EscenaMundo (para leer el avatar local). instalar / quitar: inyectables (por defecto, online_bucle).
    def __init__(self, gestor, mundo, conexion, activar, escena_mundo=None, instalar=None, quitar=None):
        self._gestor = gestor
        self._mundo = mundo
        self._conexion = conexion
        self._activar = activar
        self._escena_mundo = escena_mundo
        self._instalar = instalar
        self._quitar = quitar
        self.flujo = None
        self.bucle = None
        self.activo = False

    # -- Callback del lobby --

    def al_empezar(self, cliente, info):
        if self.activo:
            self._soltar()
        sesion = info.get("sesion")
        try:
            self._arrancar(cliente, info, sesion)
        except Exception:                         # noqa: BLE001 - jamás dejar red ni bucle colgados
            _registro.exception("No se pudo arrancar la partida en línea.")
            self._abortar(cliente, sesion)

    def _arrancar(self, cliente, info, sesion):
        from frontend.online_flujo import FlujoEnLinea
        flujo = FlujoEnLinea(cliente, self._mundo, info["tu_id"], info["jugadores"])
        if info.get("inicio"):
            flujo.procesar_evento(info["inicio"])         # spawns de todos (el lobby ya consumió el «inicio»)
        self.flujo = flujo
        self.bucle = self._poner_bucle(cliente, flujo)
        self._conexion.fijar_flujo(flujo)
        cerrar = sesion.cerrar if sesion is not None else cliente.cerrar
        self._conexion.fijar_cierre(cerrar, self._soltar)
        self._activar(True)
        self.activo = True
        self._conexion.comenzar_partida()               # entra a MUNDO con el rol de la sala

    # Fuente de posición del jugador local: x, z y «dentro» del flujo; y, rumbo, velocidad y aire del avatar.
    def _fuente_pos(self, flujo):
        from frontend.online_bucle_calculos import fuente_pos_local
        escena = self._escena_mundo

        def avatar():
            return escena.avatar_de(flujo.jugador) if escena is not None else None
        return fuente_pos_local(flujo, avatar)

    def _poner_bucle(self, cliente, flujo):
        fuente = self._fuente_pos(flujo)
        if self._instalar is not None:
            return self._instalar(cliente, flujo, fuente)
        from frontend import online_bucle
        return online_bucle.instalar_bucle(cliente, flujo, fuente, forzar=True)

    def _quitar_bucle(self):
        if self._quitar is not None:
            self._quitar()
            return
        from frontend import online_bucle
        online_bucle.quitar_bucle()

    # Tras volver al inicio: quita el bucle y devuelve las escenas al hot-seat. Idempotente.
    def _soltar(self):
        try:
            self._quitar_bucle()
        finally:
            self.bucle = None
            self.flujo = None
            self.activo = False
            self._activar(False)

    # Fallo al arrancar: cierra la red (hilo aparte) y vuelve al inicio.
    def _abortar(self, cliente, sesion):
        import threading
        try:
            self._soltar()
        except Exception:                          # noqa: BLE001
            _registro.exception("Falló la limpieza tras un arranque fallido.")
        cerrar = sesion.cerrar if sesion is not None else cliente.cerrar
        threading.Thread(target=cerrar, name="alcalde-cierre", daemon=True).start()
        try:
            self._gestor.cambiar_a(INICIO)
        except Exception:                          # noqa: BLE001
            _registro.exception("No se pudo volver al inicio.")
