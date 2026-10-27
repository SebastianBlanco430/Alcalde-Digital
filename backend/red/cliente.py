# Cliente de red del modo online (solo stdlib). Un hilo de red propio (asyncio) mantiene la
# conexión con el anfitrión; el hilo del juego (Ursina) solo llama a métodos no bloqueantes y
# drena eventos. Este módulo NUNCA importa ursina ni panda3d y el hilo de red nunca toca el motor.
#
# ============================== API PÚBLICA (para T6/T8) ==============================
#   cliente = ClienteRed(huella_mundo, huella_contenido, ids_misiones=None)
#       huella_*: hex de 64 car. calculados con backend.red.anfitrion.calcular_huellas(...)
#       ids_misiones: iterable opcional con los ids del catálogo local; si se da, los mensajes
#                     de red con ids de misión desconocidos se descartan.
#   cliente.conectar(host, puerto, codigo, nombre)   # no bloquea; ValueError si los datos son malos
#   cliente.estado        -> "conectando" | "en_sala" | "en_juego" | "reconectando" | "cerrado"
#   cliente.motivo_cierre -> texto corto cuando estado == "cerrado" (p. ej. "sala_cerrada",
#                            "codigo_malo", "mundo_distinto", "expulsado", "reconexion_agotada")
#   cliente.tu_id         -> slot 0..3 asignado por el anfitrión (None hasta la bienvenida)
#   cliente.latencia_ms   -> RTT suavizado en ms (None hasta el primer pong)
#   cliente.silencio()    -> segundos desde el último mensaje del anfitrión (para «inestable»)
#   cliente.sacar_eventos(maximo=64) -> lista de dicts YA validados y saneados (ver abajo)
#   Envío (thread-safe; devuelven True si se encoló):
#       enviar_pos(x, z, y=0, rumbo=0, velocidad=0, banderas=0, veh=None)  # coalescido a <= 20 Hz
#           banderas: máscara int (1 en_aire, 2 escalera, 4 dentro, 8 vehículo) o iterable de
#           nombres de backend.red.sesion_en_linea.BANDERAS. Con latido a 2 Hz si no cambia.
#       enviar_interactuar(), enviar_decision(mision, noticia, tipo), enviar_salir_edificio(),
#       enviar_rol(rol), enviar_listo(bool), enviar_iniciar(), enviar_saludo(indice 0..15)
#   cliente.cerrar()      # envía «adios», cierra y une el hilo (idempotente)
#
# EVENTOS que entrega sacar_eventos() (todos dict con clave "t"):
#   Propios del cliente:
#     {"t":"estado","estado":...,"motivo":...}   cambio de estado
#     {"t":"reconectando","intento":n,"espera":s} esperando para reintentar (1,2,4…30 s)
#     {"t":"reconectado"}                        la reconexión funcionó
#     {"t":"cerrado","motivo":str}               fin definitivo (el hilo termina)
#     {"t":"bienvenida","v","tu_id","semilla","sala"}  (el token de reconexión NO se expone)
#     {"t":"rechazo","codigo","texto"}           handshake rechazado, o rol_tomado en sesión
#   Del anfitrión (campos del esquema de backend.red.protocolo, textos ya saneados):
#     sala{jugadores[{id,nombre,rol,listo,conectado,anfitrion}],roles_libres}, inicio{cuenta,
#     spawns[{id,x,z,y}],mision}, snap{n,tt,jugadores[{i,x,z,y,r,v,f}],recibido}, corregir{x,z,y,seq},
#     mision{id,mano[ids de noticia COMO TEXTO, p. ej. "40"],hechas[ids]} (privado), ok, rechazo_interactuar{motivo},
#     ind{valores,autor,deltas}, mision_cerrada{id,siguiente} (solo la propia), fin{indicadores,
#     resumen}, jugador_entra/sale/desconectado/reconectado{id}, saludo{id,indice}, error{motivo},
#     sala_cerrada (el cliente pasa a «cerrado» y no reintenta).
#   `snap` lleva «recibido» (reloj del cliente al llegar) para InterpoladorRemoto.agregar().
#   ping/pong se resuelven dentro del hilo de red y no se entregan.
#
# Seguridad: el cliente aplica los mismos límites y esquemas a lo que recibe (anfitrión
# malicioso): tope de línea 16 KiB, JSON estricto, cubo de fichas, tope de infracciones, roles
# contra ROLES, ids de misión contra el catálogo y TODO texto mostrable pasa por
# sanear_texto_visible (Ursina interpreta «<tags>»). El token de reconexión vive solo en memoria.
import asyncio
import logging
import queue
import threading
import time

from backend.logica.roles import ROLES
from backend.red import huellas, protocolo, saneado
from backend.red.limites import LimiteConexion
from backend.red.sesion_en_linea import banderas_a_mascara
from backend.red.transporte import Conexion, ConexionCerrada, LimiteExcedido, abrir_conexion

registro = logging.getLogger("alcalde.red.cliente")

ESTADO_CONECTANDO = "conectando"
ESTADO_EN_SALA = "en_sala"
ESTADO_EN_JUEGO = "en_juego"
ESTADO_RECONECTANDO = "reconectando"
ESTADO_CERRADO = "cerrado"

ESPERAS_RECONEXION = (1.0, 2.0, 4.0, 8.0, 16.0, 30.0)
INTERVALO_PING = 1.0
MAX_EVENTOS_SNAP = 400          # por encima, los snap sobrantes se descartan
MAX_EVENTOS = 4000              # por encima, el anfitrión inunda: se corta
TIEMPOS_DEFECTO = {"handshake": protocolo.T_HANDSHAKE, "lectura": protocolo.T_LECTURA}
CODIGOS_TERMINALES_EN_SESION = ("expulsado",)


class _Terminal(Exception):
    """Fin definitivo (sin reintento): el motivo va en el evento «cerrado»."""

    def __init__(self, motivo):
        super().__init__(motivo)
        self.motivo = motivo


# ---------------------------------------------------------------------------
# Saneado de lo que llega del anfitrión (función pura, probada aparte)
# ---------------------------------------------------------------------------
def _sanear_dic(dic):
    salida = {}
    for clave, valor in dic.items():
        limpio = saneado.sanear_texto_visible(clave, 48)
        if limpio:
            salida[limpio] = valor
    return salida


def _sanear_vehiculos(lista):
    # T9: solo vehículos de tipo conocido; el resto del esquema ya está validado (rangos, ids 0..7).
    from backend.red.vehiculos_coop import TIPOS_VEHICULO
    return [dict(v) for v in lista if v.get("k") in TIPOS_VEHICULO]


def sanear_mensaje(msg, ids_misiones=None, vehiculos=False):
    """Copia segura de un mensaje H2C ya validado por esquema; None si hay que descartarlo.

    `vehiculos`: True si este cliente soporta vehículos online (T9); si no, se descarta `veh` del snap."""
    t = msg["t"]
    salida = dict(msg)
    if t == "sala":
        jugadores = []
        for j in msg["jugadores"]:
            nombre = saneado.sanear_texto_visible(j["nombre"], saneado.LARGO_MAX_NOMBRE + 4) or "?"
            rol = j["rol"] if j["rol"] in ROLES else None
            jugadores.append({"id": j["id"], "nombre": nombre, "rol": rol, "listo": j["listo"],
                              "conectado": j["conectado"], "anfitrion": j["anfitrion"]})
        salida["jugadores"] = jugadores
        salida["roles_libres"] = [r for r in msg["roles_libres"] if r in ROLES]
    elif t in ("rechazo",):
        salida["texto"] = saneado.sanear_texto_visible(msg["texto"], 200)
    elif t == "error":
        salida["motivo"] = saneado.sanear_texto_visible(msg["motivo"], 200)
    elif t == "rechazo_interactuar":
        salida["motivo"] = saneado.sanear_texto_visible(msg["motivo"], 120)
    elif t == "fin":
        salida["resumen"] = saneado.sanear_texto_visible(msg["resumen"], 1000)
        salida["indicadores"] = _sanear_dic(msg["indicadores"])
    elif t == "ind":
        salida["valores"] = _sanear_dic(msg["valores"])
        salida["deltas"] = _sanear_dic(msg["deltas"])
    elif t == "snap":
        if "ind" in msg:
            salida["ind"] = _sanear_dic(msg["ind"])
        if vehiculos and "veh" in msg:
            salida["veh"] = _sanear_vehiculos(msg["veh"])
        else:
            salida.pop("veh", None)  # sin VEHICULOS_ONLINE el cliente ignora los vehículos del anfitrión
    elif t == "mision":
        if ids_misiones is not None and msg["id"] not in ids_misiones:
            return None
        salida["hechas"] = [h for h in msg["hechas"] if ids_misiones is None or h in ids_misiones]
    elif t == "mision_cerrada":
        if ids_misiones is not None:
            if msg["id"] not in ids_misiones:
                return None
            if msg["siguiente"] is not None and msg["siguiente"] not in ids_misiones:
                salida["siguiente"] = None
    elif t == "inicio":
        if msg["mision"] is not None and ids_misiones is not None and msg["mision"] not in ids_misiones:
            salida["mision"] = None
    return salida


# ---------------------------------------------------------------------------
# Cliente
# ---------------------------------------------------------------------------
class ClienteRed:

    def __init__(self, huella_mundo, huella_contenido, ids_misiones=None, reloj=time.monotonic,
                 tiempos=None, esperas_reconexion=ESPERAS_RECONEXION,
                 max_reconexion=protocolo.GRACIA_RECONEXION, intervalo_ping=INTERVALO_PING,
                 reconectar=True, vehiculos=False):
        self._vehiculos = bool(vehiculos)      # T9: entender los vehículos online (VEHICULOS_ONLINE)
        self._huella_mundo = huella_mundo
        self._huella_contenido = huella_contenido
        self._ids_misiones = None if ids_misiones is None else frozenset(ids_misiones)
        self._reloj = reloj
        self._t = dict(TIEMPOS_DEFECTO)
        self._t.update(tiempos or {})
        self._esperas = tuple(esperas_reconexion) or ESPERAS_RECONEXION
        self._max_reconexion = float(max_reconexion)
        self._intervalo_ping = float(intervalo_ping)
        self._reconectar = bool(reconectar)
        self._cola = queue.SimpleQueue()
        self._lock = threading.Lock()
        self.estado = ESTADO_CERRADO
        self.motivo_cierre = None
        self.tu_id = None
        self.latencia_ms = None
        self._hilo = None
        self._loop = None
        self._tarea_vida = None
        self._despertar = None
        self._cerrando = False
        # Datos de la conexión
        self._destino = None
        self._codigo = None
        self._nombre = None
        self._token = None            # solo en memoria
        self._fase = "sala"           # "sala" | "juego": a qué estado volver tras reconectar
        self._conn = None
        self._ultimo_rx = self._reloj()
        # Posición (coalescencia)
        self._pos = None
        self._pos_programada = False
        self._ultima_pos = None
        self._n_pos = 0
        self._t_ultima_pos = 0.0
        self._pings = {}
        self._n_ping = 0
        self._n_decision = 0

    # ======================================================================
    # API pública (hilo del juego)
    # ======================================================================
    def conectar(self, host, puerto, codigo, nombre):
        """Empieza a conectar en segundo plano. Los resultados llegan como eventos."""
        if self._hilo is not None and self._hilo.is_alive():
            raise RuntimeError("El cliente ya está conectado o conectando.")
        if not isinstance(host, str) or not host or len(host) > 253 or any(
                c.isspace() or ord(c) < 32 for c in host):
            raise ValueError("Dirección del anfitrión no válida.")
        if type(puerto) is not int or not 1 <= puerto <= 65535:
            raise ValueError("Puerto no válido.")
        codigo_norm = huellas.normalizar_codigo(codigo)
        if codigo_norm is None:
            raise ValueError("Código de sala no válido.")
        nombre_ok = saneado.validar_nombre(nombre)
        if nombre_ok is None:
            raise ValueError("Nombre no válido: 1 a 16 letras, números, espacio, - _ .")
        self._destino = (host, puerto)
        self._codigo = codigo_norm
        self._nombre = nombre_ok
        self._token = None
        self._fase = "sala"
        self._cerrando = False
        self.motivo_cierre = None
        self.tu_id = None
        self.latencia_ms = None
        self._pos = None
        self._ultima_pos = None
        self._pos_programada = False
        self._n_pos = 0
        listo = threading.Event()
        self.estado = ESTADO_CONECTANDO
        self._emitir({"t": "estado", "estado": ESTADO_CONECTANDO})
        self._hilo = threading.Thread(target=self._hilo_red, args=(listo,), name="alcalde-cliente",
                                      daemon=True)
        self._hilo.start()
        listo.wait(5.0)

    def sacar_eventos(self, maximo=64):
        """Hasta `maximo` eventos pendientes, en orden de llegada (no bloquea)."""
        eventos = []
        while len(eventos) < maximo:
            try:
                eventos.append(self._cola.get_nowait())
            except queue.Empty:
                break
        return eventos

    def silencio(self):
        """Segundos desde el último mensaje recibido del anfitrión."""
        return max(0.0, self._reloj() - self._ultimo_rx)

    def cerrar(self, timeout=5.0):
        """Sale de la sala (envía «adios»), cierra y une el hilo. Idempotente."""
        hilo, loop = self._hilo, self._loop
        self._cerrando = True
        if hilo is not None and hilo.is_alive() and loop is not None:
            try:
                # (se crea la corrutina DENTRO del bucle: si ya se cerró, no queda ninguna sin esperar)
                loop.call_soon_threadsafe(lambda: loop.create_task(self._pedir_cierre()))
            except RuntimeError:
                pass
            hilo.join(timeout)
        if self.estado != ESTADO_CERRADO:
            self.estado = ESTADO_CERRADO
            self.motivo_cierre = self.motivo_cierre or "cerrado_por_el_usuario"

    # ---- Envío ----
    def enviar_pos(self, x, z, y=0.0, rumbo=0.0, velocidad=0.0, banderas=0, veh=None):
        """Propone la posición. Se fusiona: solo sale la última, a <= HZ_POS por segundo."""
        if self.estado != ESTADO_EN_JUEGO or self._loop is None:
            return False
        if not isinstance(banderas, int) or isinstance(banderas, bool):
            banderas = banderas_a_mascara(banderas)
        with self._lock:
            self._pos = (x, z, y, rumbo, velocidad, banderas, veh)
            programar = not self._pos_programada
            self._pos_programada = True
        if programar:
            self._llamar(self._vaciar_pos)
        return True

    def enviar_interactuar(self):
        return self._enviar_critico({"t": "interactuar"})

    def enviar_decision(self, mision, noticia, tipo):
        self._n_decision += 1
        return self._enviar_critico({"t": "decision", "mision": mision, "noticia": str(noticia),
                                     "tipo": tipo, "n": self._n_decision})

    def enviar_salir_edificio(self):
        return self._enviar_critico({"t": "salir_edificio"})

    def enviar_rol(self, rol):
        return self._enviar_critico({"t": "rol", "rol": rol})

    def enviar_listo(self, listo=True):
        return self._enviar_critico({"t": "listo", "listo": bool(listo)})

    def enviar_iniciar(self):
        # T8: solo vale del anfitrión-jugador y con todos listos; si no, llega «error» (solo_anfitrion / faltan_listos).
        return self._enviar_critico({"t": "iniciar"})

    # T9: pedir montar el vehículo número `veh` (0..7) / bajar. El anfitrión responde monta_ok o monta_no.
    def enviar_montar(self, veh):
        return self._enviar_critico({"t": "montar", "veh": int(veh)})

    def enviar_bajar(self):
        return self._enviar_critico({"t": "bajar"})

    # v4: pedir un viaje rápido (mototáxi / teleférico) a `destino` (id de protocolo.DESTINOS_VIAJE). El anfitrión responde
    # viaje_ok{destino,x,z,y} o viaje_no{motivo}.
    def enviar_viaje(self, destino):
        return self._enviar_critico({"t": "viaje", "destino": str(destino)})

    def enviar_saludo(self, indice):
        return self._enviar_critico({"t": "saludo_rapido", "indice": indice})

    # ======================================================================
    # Hilo de red
    # ======================================================================
    def _llamar(self, fn, *args):
        loop = self._loop
        if loop is None:
            return False
        try:
            loop.call_soon_threadsafe(fn, *args)
            return True
        except RuntimeError:                # el bucle ya se cerró
            return False

    def _enviar_critico(self, mensaje):
        if self.estado not in (ESTADO_EN_SALA, ESTADO_EN_JUEGO):
            return False
        return self._llamar(self._tx, mensaje, False)

    def _tx(self, mensaje, descartable):
        conn = self._conn
        if conn is not None and not conn.cerrada:
            conn.enviar(mensaje, descartable)

    def _hilo_red(self, listo):
        try:
            asyncio.run(self._principal(listo))
        except Exception as error:          # pragma: no cover - defensivo
            registro.error("El hilo del cliente terminó con %s", type(error).__name__)
            self._terminar("error_interno")
        finally:
            listo.set()

    async def _principal(self, listo):
        self._loop = asyncio.get_running_loop()
        self._despertar = asyncio.Event()
        self._tarea_vida = asyncio.create_task(self._vida())
        listo.set()
        try:
            await self._tarea_vida
        except asyncio.CancelledError:
            pass
        self._terminar(self.motivo_cierre or "cerrado_por_el_usuario")

    async def _pedir_cierre(self):
        self._cerrando = True
        conn = self._conn
        if conn is not None and not conn.cerrada:
            conn.enviar({"t": "adios"})
            await conn.cerrar(True, 0.5)
        if self._despertar is not None:
            self._despertar.set()
        if self._tarea_vida is not None:
            self._tarea_vida.cancel()

    def _cambiar_estado(self, estado, motivo=None):
        if self.estado == estado:
            return
        self.estado = estado
        evento = {"t": "estado", "estado": estado}
        if motivo:
            evento["motivo"] = motivo
        self._emitir(evento)

    def _terminar(self, motivo):
        if self.estado == ESTADO_CERRADO and self.motivo_cierre is not None:
            return
        self.motivo_cierre = motivo
        self._cambiar_estado(ESTADO_CERRADO, motivo)
        self._emitir({"t": "cerrado", "motivo": motivo})

    def _emitir(self, evento):
        self._cola.put(evento)

    # ---- Vida de la conexión (con reconexión) ----
    async def _vida(self):
        loop = asyncio.get_running_loop()
        perdido_desde = None
        intento = 0
        while not self._cerrando:
            tipo, motivo, conecto = await self._ciclo()
            if self._cerrando:
                return
            if tipo == "terminal":
                self.motivo_cierre = motivo
                return
            if conecto:
                perdido_desde = loop.time()
                intento = 0
            elif perdido_desde is None:
                self.motivo_cierre = motivo or "no_se_pudo_conectar"
                return
            if not self._reconectar or self._token is None:
                self.motivo_cierre = motivo or "conexion_perdida"
                return
            espera = self._esperas[min(intento, len(self._esperas) - 1)]
            intento += 1
            if loop.time() - perdido_desde + espera > self._max_reconexion:
                self.motivo_cierre = "reconexion_agotada"
                return
            self._cambiar_estado(ESTADO_RECONECTANDO)
            self._emitir({"t": "reconectando", "intento": intento, "espera": espera})
            try:
                async with asyncio.timeout(espera):
                    await self._despertar.wait()
            except TimeoutError:
                pass

    async def _ciclo(self):
        """Una conexión completa. Devuelve (tipo, motivo, conecto): tipo «terminal» o «perdida»."""
        conn = None
        conecto = False
        ping = None
        reconexion = self._token is not None
        try:
            host, puerto = self._destino
            try:
                conn = await abrir_conexion(host, puerto, protocolo.DIR_H2C, protocolo.DIR_C2H,
                                            self._t["handshake"])
            except (OSError, TimeoutError):
                return ("perdida", "no_se_pudo_conectar", False)
            self._conn = conn
            self._ultimo_rx = self._reloj()
            await self._handshake(conn)
            conecto = True
            conn.limite = LimiteConexion()
            self._fase_a_estado(reconexion)
            ping = asyncio.create_task(self._bucle_periodico(conn))
            while True:
                mensaje = await conn.recibir(timeout=self._t["lectura"])
                self._ultimo_rx = self._reloj()
                self._procesar(mensaje)
        except _Terminal as fin:
            return ("terminal", fin.motivo, conecto)
        except TimeoutError:
            return ("perdida", "silencio_del_anfitrion", conecto)
        except ConexionCerrada:
            return ("perdida", "conexion_perdida", conecto)
        except LimiteExcedido:
            return ("perdida", "anfitrion_inundando", conecto)
        except protocolo.ErrorProtocolo as error:
            motivo = "protocolo_invalido:" + error.codigo
            return ("perdida" if conecto else "terminal", motivo, conecto)
        finally:
            if ping is not None:
                ping.cancel()
                await asyncio.gather(ping, return_exceptions=True)
            self._conn = None
            if conn is not None:
                await conn.cerrar(False)

    async def _handshake(self, conn):
        try:
            reto = await conn.recibir(timeout=self._t["handshake"])
            if reto["t"] != "reto":
                raise _Terminal("protocolo_invalido:esperaba_reto")
            hola = {"t": "hola", "juego": protocolo.JUEGO, "v": protocolo.PROTOCOLO_V,
                    "nombre": self._nombre, "huella_mundo": self._huella_mundo,
                    "huella_contenido": self._huella_contenido,
                    "prueba": huellas.calcular_prueba(self._codigo, reto["nonce"], self._nombre)}
            if self._token is not None:
                hola["token"] = self._token
            if not conn.enviar(hola):
                raise _Terminal("datos_de_conexion_invalidos")
            respuesta = await conn.recibir(timeout=self._t["handshake"])
        except (TimeoutError, ConexionCerrada):
            raise
        except protocolo.ErrorProtocolo as error:
            raise _Terminal("protocolo_invalido:" + error.codigo)
        if respuesta["t"] == "rechazo":
            seguro = sanear_mensaje(respuesta)
            self._emitir({"t": "rechazo", "codigo": seguro["codigo"], "texto": seguro["texto"]})
            raise _Terminal(seguro["codigo"])
        if respuesta["t"] != "bienvenida":
            raise _Terminal("protocolo_invalido:esperaba_bienvenida")
        if respuesta["v"] != protocolo.PROTOCOLO_V:
            raise _Terminal("version")
        h = respuesta["huellas"]
        if h["mundo"] != self._huella_mundo or h["contenido"] != self._huella_contenido:
            raise _Terminal("mundo_distinto")
        self._token = respuesta["token"]
        self.tu_id = respuesta["tu_id"]
        self._emitir({"t": "bienvenida", "v": respuesta["v"], "tu_id": respuesta["tu_id"],
                      "semilla": respuesta["semilla"],
                      "sala": saneado.sanear_texto_visible(respuesta["sala"], 32)})

    def _fase_a_estado(self, reconexion):
        self._cambiar_estado(ESTADO_EN_JUEGO if self._fase == "juego" else ESTADO_EN_SALA)
        if reconexion:
            self._emitir({"t": "reconectado"})

    # ---- Mensajes del anfitrión ----
    def _procesar(self, msg):
        t = msg["t"]
        if t == "pong":
            self._pong(msg)
            return
        if t == "ping":
            self._tx({"t": "pong", "n": msg["n"], "tt": msg["tt"]}, False)
            return
        if t in ("reto", "bienvenida"):             # fuera de turno: se cuenta como infracción
            if self._conn is not None and self._conn.limite is not None:
                self._conn.limite.registrar_infraccion()
            return
        seguro = sanear_mensaje(msg, self._ids_misiones, self._vehiculos)
        if seguro is None:
            if self._conn is not None and self._conn.limite is not None:
                self._conn.limite.registrar_infraccion()
            return
        if t == "sala_cerrada":
            self._emitir(seguro)
            raise _Terminal("sala_cerrada")
        if t == "rechazo" and seguro["codigo"] in CODIGOS_TERMINALES_EN_SESION:
            self._emitir(seguro)
            raise _Terminal(seguro["codigo"])
        if t == "inicio":
            self._fase = "juego"
            self._cambiar_estado(ESTADO_EN_JUEGO)
        if t == "snap":
            if self._cola.qsize() > MAX_EVENTOS_SNAP:
                return
            seguro["recibido"] = self._ultimo_rx
        elif self._cola.qsize() > MAX_EVENTOS:
            raise _Terminal("anfitrion_inundando")
        self._emitir(seguro)

    def _pong(self, msg):
        enviado = self._pings.pop(msg["n"], None)
        if enviado is None:
            return
        rtt = (self._reloj() - enviado) * 1000.0
        if not 0.0 <= rtt <= 60000.0:
            return
        self.latencia_ms = rtt if self.latencia_ms is None else 0.8 * self.latencia_ms + 0.2 * rtt

    # ---- Ping y latido de posición ----
    async def _bucle_periodico(self, conn):
        paso = min(self._intervalo_ping, 1.0 / protocolo.HZ_LATIDO_POS) / 2.0
        proximo_ping = 0.0
        while not conn.cerrada:
            ahora = self._reloj()
            if ahora >= proximo_ping:
                proximo_ping = ahora + self._intervalo_ping
                self._n_ping = (self._n_ping + 1) % (2 ** 31)
                self._pings[self._n_ping] = ahora
                if len(self._pings) > 8:
                    self._pings.pop(next(iter(self._pings)))
                conn.enviar({"t": "ping", "n": self._n_ping, "tt": float(ahora)})
            if (self.estado == ESTADO_EN_JUEGO and self._ultima_pos is not None
                    and ahora - self._t_ultima_pos >= 1.0 / protocolo.HZ_LATIDO_POS):
                self._tx_pos(self._ultima_pos)           # latido: sigo aquí
            await asyncio.sleep(paso)

    def _vaciar_pos(self):
        """(hilo de red) Envía la última posición si ya pasó el intervalo mínimo; si no, espera."""
        loop = asyncio.get_running_loop()
        espera = self._t_ultima_pos + 1.0 / protocolo.HZ_POS - self._reloj()
        if espera > 0:
            loop.call_later(espera, self._vaciar_pos)
            return
        with self._lock:
            datos, self._pos = self._pos, None
            self._pos_programada = False
        if datos is not None:
            self._tx_pos(datos)

    def _tx_pos(self, datos):
        x, z, y, rumbo, velocidad, banderas, veh = datos
        self._n_pos = (self._n_pos + 1) % (2 ** 31)
        mensaje = {"t": "pos", "n": self._n_pos, "x": x, "z": z, "y": y, "r": rumbo,
                   "v": velocidad, "f": banderas}
        if veh is not None:
            mensaje["veh"] = veh
        self._ultima_pos = datos
        self._t_ultima_pos = self._reloj()
        conn = self._conn
        if conn is not None and not conn.cerrada:
            conn.enviar(mensaje, descartable=True)
