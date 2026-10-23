# Servicios de red del lobby online (sin ursina): crea el anfitrión local y el ClienteRed, y agrupa lo que
# comparten las escenas del lobby en una SesionLobby. Importa backend.red, por eso SOLO lo cargan las escenas
# online (main.py las registra de forma perezosa con ONLINE=True). No importa frontend/online_flujo.py: el
# paso a la escena de juego es el callback `al_empezar(cliente, info)` que conectan T6/T7.
#
# info (dict) que recibe `al_empezar(cliente, info)`:
#   "tu_id", "semilla", "sala", "es_anfitrion" (bool), "anfitrion" (Anfitrion|None: SIGUE VIVO, lo apaga quien
#   reciba la sesión), "jugadores" (lista de dicts del último «sala»), "inicio" (evento «inicio» completo),
#   "alias", "destino" ("ip:puerto" mostrado), "sesion" (la SesionLobby).
# Los eventos posteriores a «inicio» NO se drenan en el lobby: siguen en la cola de ClienteRed.

import logging

from backend.datos.misiones_semilla import CATALOGO_MISIONES
from backend.red import huellas
from backend.red.anfitrion import calcular_huellas
from backend.red.cliente import ClienteRed
from backend.red.servidor import construir_anfitrion
from frontend import online_config
from frontend.online_lobby_calculos import ModeloSala, formatear_destino


_log = logging.getLogger(__name__)


class SesionLobby:
    """Conexión viva del lobby: cliente, anfitrión (si este equipo aloja) y modelo de la sala."""

    def __init__(self, cliente, anfitrion=None, alias="", destino="", codigo=""):
        self.cliente = cliente
        self.anfitrion = anfitrion
        self.alias = alias
        self.destino = destino        # «ip:puerto» que se comparte
        self.codigo = codigo          # código de sala (solo el anfitrión lo conoce en claro aquí)
        self.modelo = ModeloSala()
        self.cerrada = False

    @property
    def es_anfitrion(self):
        return self.anfitrion is not None

    def cerrar(self):
        """Cierra cliente y anfitrión (idempotente)."""
        if self.cerrada:
            return
        self.cerrada = True
        try:
            self.cliente.cerrar()
        except Exception:
            _log.exception("No se pudo cerrar el cliente de red")
        if self.anfitrion is not None:
            try:
                self.anfitrion.detener()
            except Exception:
                _log.exception("No se pudo detener el anfitrión")


class ServiciosOnline:
    """Fábrica de anfitrión y cliente para un mundo concreto (el que construyó main.py)."""

    def __init__(self, mundo, semilla, catalogo=None, fabrica_anfitrion=None, fabrica_cliente=None):
        self.mundo = mundo
        self.semilla = semilla
        self.catalogo = CATALOGO_MISIONES if catalogo is None else catalogo
        self._fabrica_anfitrion = fabrica_anfitrion
        self._fabrica_cliente = fabrica_cliente

    def crear_cliente(self):
        if self._fabrica_cliente is not None:
            return self._fabrica_cliente()
        h_mundo, h_contenido = calcular_huellas(self.mundo, self.semilla, self.catalogo)
        return ClienteRed(h_mundo, h_contenido, ids_misiones=[m.id for m in self.catalogo],
                          vehiculos=online_config.VEHICULOS_ONLINE)

    def crear_anfitrion(self, ambito, puerto, abierto=False):
        """Anfitrión iniciado -> (anfitrion, ip_mostrada, puerto, codigo). OSError/ValueError si falla."""
        if self._fabrica_anfitrion is not None:
            return self._fabrica_anfitrion(ambito, puerto, abierto)
        codigo = huellas.generar_codigo_sala(
            huellas.LARGO_CODIGO_ABIERTO if ambito == "abierto" else huellas.LARGO_CODIGO)
        anfitrion = construir_anfitrion(puerto=puerto, ambito=ambito, semilla=self.semilla, abierto=abierto,
                                        mundo=self.mundo, codigo=codigo,
                                        vehiculos=online_config.VEHICULOS_ONLINE)
        host, puerto_real = anfitrion.iniciar()
        return anfitrion, host, puerto_real, anfitrion.codigo

    def abrir_como_anfitrion(self, alias, ambito, puerto, abierto=False):
        """Crea la sala y conecta el cliente del propio anfitrión por 127.0.0.1. -> SesionLobby."""
        anfitrion, host, puerto_real, codigo = self.crear_anfitrion(ambito, puerto, abierto)
        cliente = self.crear_cliente()
        sesion = SesionLobby(cliente, anfitrion, alias, formatear_destino(host, puerto_real), codigo)
        try:
            cliente.conectar("127.0.0.1", puerto_real, codigo, alias)
        except Exception:
            sesion.cerrar()
            raise
        return sesion

    def abrir_como_cliente(self, alias, host, puerto, codigo):
        cliente = self.crear_cliente()
        sesion = SesionLobby(cliente, None, alias, formatear_destino(host, puerto), "")
        try:
            cliente.conectar(host, puerto, codigo, alias)
        except Exception:
            sesion.cerrar()
            raise
        return sesion
