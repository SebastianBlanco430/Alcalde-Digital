# Anfitrión del modo online cooperativo (solo stdlib). Un servidor asyncio en un HILO propio
# que es el ÚNICO escritor del estado: ejecuta la PartidaCooperativa (backend.red.partida_coop),
# acepta conexiones de hasta 4 jugadores, traduce sus mensajes a llamadas de la partida y
# reparte los eventos de la partida como mensajes del protocolo v1 (backend.red.protocolo).
# El jugador anfitrión entra como un cliente más, por 127.0.0.1 (un solo camino de código).
# Este módulo NUNCA importa ursina ni panda3d.
#
# API pública (segura desde otros hilos; todo lo demás vive en el hilo de red):
#   anfitrion = Anfitrion(partida, mundo, semilla, codigo, huella_mundo, huella_contenido, ...)
#   host, puerto = anfitrion.iniciar()      # arranca el hilo; lanza OSError/ValueError si falla
#   anfitrion.iniciar_partida(forzar=False) # pasa de la sala al juego (ValueError si no procede)
#   anfitrion.expulsar(id_jugador)          # echa (y veta la IP en la sala); el anfitrión => cierre
#   anfitrion.estado()                      # dict de diagnóstico (sin IPs ni tokens)
#   anfitrion.ejecutar(fn)                  # corre fn() en el hilo de red y vuelca eventos
#   anfitrion.detener()                     # apagado ordenado: sala_cerrada, cierra y une el hilo
#
# Seguridad aplicada (ver también transporte.py y limites.py):
#   - Ámbito de red: «local» (127.0.0.1), «lan» (IP privada detectada + loopback; rechaza pares
#     con IP no privada) y «abierto» (0.0.0.0) SOLO si el llamador pasa abierto=True y el código
#     tiene >= LARGO_CODIGO_ABIERTO caracteres.
#   - Máx. 8 conexiones y 2 por IP, handshake 5 s, silencio 10 s, reto HMAC (el código no viaja),
#     5 fallos por IP/min => veto 60 s, cubos de fichas por conexión y por tipo, cola de salida
#     acotada, corte por infracciones, el anfitrión valida cada `pos` y manda `corregir`.
#   - Nombres saneados (validar_nombre/nombre_unico); nada de lo recibido se usa como ruta.
#   - Sin IPs de pares ni tokens en los registros.
import asyncio
import concurrent.futures
import ipaddress
import logging
import secrets
import socket
import threading
import time

from backend.logica.roles import ORDEN_ROLES, ROLES
from backend.logica.sesion import MAX_JUGADORES
from backend.red import huellas, protocolo, saneado
from backend.red.limites import ConteoConexiones, LimiteConexion, VetoPorIP
from backend.red.partida_coop import FASE_JUEGO, FASE_SALA
from backend.red.sesion_en_linea import mascara_a_banderas
from backend.red.transporte import Conexion, ConexionCerrada, LimiteExcedido, limite_lectura
from backend.red import vehiculos_coop
from backend.red.validacion_movimiento import BANDERA_DENTRO, ValidadorMovimiento

registro = logging.getLogger("alcalde.red.anfitrion")

AMBITOS = ("local", "lan", "abierto")
RED_CGNAT = ipaddress.ip_network("100.64.0.0/10")   # Tailscale y similares
IP_PRUEBA_RUTA = "192.0.2.1"       # TEST-NET-1 (RFC 5737): connect() de UDP no envía tráfico
TICK_S = 1.0                        # cada cuánto se llama a partida.tick() (gracia de reconexión)
CUENTA_INICIO = 3                   # s de cuenta atrás que se anuncian en «inicio» (solo cosmético)
LIMPIEZA_VETO_S = 60.0
ALTAS_POR_IP_MINUTO = 12
_MAX_IP_EN_ALTAS = 64                 # desde aquí se poda `_altas_por_ip` (IP sin altas en los últimos 60 s)
# Tasas por tipo (msg/s) además de las del protocolo: ningún tipo de acción debe poder usarse
# como arma (p. ej. salir_edificio repetido para recargar el presupuesto de movimiento).
LIMITES_POR_TIPO = dict(protocolo.LIMITES_POR_TIPO, salir_edificio=2, interactuar=5, rol=3, listo=5,
                        adios=2, hola=1, iniciar=2, montar=4, bajar=4)
TIEMPOS_DEFECTO = {
    "handshake": protocolo.T_HANDSHAKE,
    "silencio": protocolo.T_SILENCIO_PING,
    "escritura": 10.0,
    "tick": TICK_S,
}


# ---------------------------------------------------------------------------
# Utilidades puras (se pueden probar sin abrir sockets)
# ---------------------------------------------------------------------------
def ip_privada_detectada():
    """IP privada de este equipo hacia la red local, o None.

    Usa un socket UDP «conectado» a una dirección de documentación: el sistema elige la
    interfaz de salida y no se envía ningún paquete.
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect((IP_PRUEBA_RUTA, 9))
        ip = sock.getsockname()[0]
    except OSError:
        return None
    finally:
        sock.close()
    try:
        direccion = ipaddress.ip_address(ip)
    except ValueError:
        return None
    if direccion.is_unspecified or direccion.is_loopback:
        return None
    return ip if direccion.is_private else None


def resolver_ambito(ambito, abierto=False, codigo=None):
    """Devuelve la lista de IPs donde escuchar. ValueError si el ámbito no es permisible.

    - «local»: ["127.0.0.1"].
    - «lan»: [IP privada detectada, "127.0.0.1"] (solo loopback si no hay red privada).
    - «abierto»: ["0.0.0.0"] y SOLO con abierto=True y un código de >= LARGO_CODIGO_ABIERTO.
    """
    if ambito == "local":
        return ["127.0.0.1"]
    if ambito == "lan":
        privada = ip_privada_detectada()
        return [privada, "127.0.0.1"] if privada else ["127.0.0.1"]
    if ambito == "abierto":
        if abierto is not True:
            raise ValueError("El ámbito abierto exige abierto=True explícito.")
        if not isinstance(codigo, str) or len(codigo) < huellas.LARGO_CODIGO_ABIERTO:
            raise ValueError(
                f"El ámbito abierto exige un código de al menos {huellas.LARGO_CODIGO_ABIERTO} caracteres.")
        return ["0.0.0.0"]
    raise ValueError(f"Ámbito desconocido: {ambito!r}")


def ip_permitida(ip, ambito):
    """¿Se admite a un par con esta IP en este ámbito? (LAN: solo privada o loopback)."""
    if ambito == "abierto":
        return True
    try:
        direccion = ipaddress.ip_address(ip)
    except ValueError:
        return False
    if direccion.version == 6 and direccion.ipv4_mapped is not None:
        direccion = direccion.ipv4_mapped
    if ambito == "local":
        return direccion.is_loopback
    if direccion.is_loopback:
        return True
    # T8: el rango CGNAT 100.64.0.0/10 (Tailscale) cuenta como red privada en el ámbito lan.
    if direccion.version == 4 and direccion in RED_CGNAT:
        return True
    return direccion.is_private and not direccion.is_global


def es_ip_local(ip, ip_local):
    """True si `ip` es de esta misma máquina (loopback o la IP local del socket)."""
    try:
        return ipaddress.ip_address(ip).is_loopback or ip == ip_local
    except ValueError:
        return False


def calcular_huellas(mundo, semilla, catalogo, noticias=None, grafo_social=None):
    """(huella_mundo, huella_contenido) que deben coincidir en anfitrión y clientes.

    Mundo: semilla, lugares con su coordenada, calles y límites. Contenido: versión del protocolo, misiones (con
    sus textos), roles, noticias (id, gravedad, veracidad y deltas), el grafo social y el ciudadano de cada rol.
    `noticias` (tuplas de noticias_semilla) y `grafo_social` se inyectan; sin ellos se usan los de la semilla, que
    son los que usan main.py y el servidor. Dos equipos con cualquiera de estos datos distintos no se emparejan."""
    lugares = []
    for lugar in sorted(mundo.lugares()):
        x, z = mundo.coordenada(lugar)
        lugares.append([lugar, round(float(x), 2), round(float(z), 2)])
    calles = sorted(sorted([a, b]) for a, b in mundo.segmentos())
    limites = [round(float(v), 2) for v in mundo.limites_recorribles()]
    h_mundo = huellas.huella_mundo({"semilla": int(semilla), "lugares": lugares, "calles": calles,
                                    "limites": limites})
    if noticias is None:
        from backend.datos.noticias_semilla import NOTICIAS_SEMILLA as noticias
    if grafo_social is None:
        from backend.grafos.grafo_social import construir_grafo_social_ejemplo
        grafo_social = construir_grafo_social_ejemplo()
    from backend.logica.propagacion import CIUDADANO_POR_ROL
    misiones = sorted([m.id, m.rol, m.destino, m.cantidad_noticias, m.titulo, m.mensaje] for m in catalogo)
    lista_noticias = sorted([n[0], n[1], n[3], sorted(n[4].items()), sorted(n[5].items())] for n in noticias)
    relaciones = sorted(sorted([a, b]) for a in grafo_social.ciudadanos() for b in grafo_social.vecinos(a) if a < b)
    h_contenido = huellas.huella_contenido({
        "v": protocolo.PROTOCOLO_V, "misiones": misiones, "roles": list(ORDEN_ROLES), "noticias": lista_noticias,
        "ciudadanos": sorted(grafo_social.ciudadanos()), "relaciones": relaciones,
        "ciudadano_por_rol": sorted(CIUDADANO_POR_ROL.items())})
    return h_mundo, h_contenido


def _texto(valor, largo):
    return str(valor)[:largo]


class _Rechazo:
    """Resultado negativo de la admisión: código de CODIGOS_RECHAZO y texto para el jugador."""
    __slots__ = ("codigo", "texto")

    def __init__(self, codigo, texto):
        self.codigo = codigo
        self.texto = texto


# ---------------------------------------------------------------------------
# Un jugador conectado
# ---------------------------------------------------------------------------
class _Par:
    __slots__ = ("id", "conn", "ip", "validador", "ultimo_decision", "cierre", "reemplazado")

    def __init__(self, id_jugador, conn, ip, validador):
        self.id = id_jugador
        self.conn = conn
        self.ip = ip
        self.validador = validador
        self.ultimo_decision = -1
        self.cierre = None          # motivo si la salida ya se gestionó (adios, expulsado...)
        self.reemplazado = False    # otra conexión (reconexión) ocupó su lugar


class Anfitrion:

    def __init__(self, partida, mundo, semilla, codigo, huella_mundo, huella_contenido,
                 ambito="lan", puerto=0, abierto=False, reloj=time.monotonic, hz_snap=protocolo.HZ_SNAP,
                 tiempos=None, exigir_anfitrion_local=True, auto_iniciar=False,
                 cuenta_inicio=CUENTA_INICIO, bloquear_loopback=False, max_por_ip=protocolo.MAX_CONEXIONES_POR_IP,
                 max_infracciones=20, sndbuf=None, altas_por_minuto=ALTAS_POR_IP_MINUTO, vehiculos=False):
        codigo = huellas.normalizar_codigo(codigo)
        if codigo is None:
            raise ValueError("Código de sala inválido.")
        self.partida = partida
        self.mundo = mundo
        self.semilla = int(semilla)
        self.codigo = codigo
        self.ambito = ambito
        self.abierto = abierto
        self._ips_escucha = resolver_ambito(ambito, abierto, codigo)   # ValueError si no procede
        self._puerto_pedido = int(puerto)
        self.huella_mundo = huella_mundo
        self.huella_contenido = huella_contenido
        self._reloj = reloj                     # veto, validadores (inyectable en pruebas)
        self._hz_snap = max(1, int(hz_snap))
        self._t = dict(TIEMPOS_DEFECTO)
        self._t.update(tiempos or {})
        self.exigir_anfitrion_local = bool(exigir_anfitrion_local)
        self.auto_iniciar = bool(auto_iniciar)
        self._cuenta = int(cuenta_inicio)
        self._bloquear_loopback = bool(bloquear_loopback)
        self._max_infracciones = int(max_infracciones)
        self._sndbuf = sndbuf
        self.conteo = ConteoConexiones(protocolo.MAX_CONEXIONES, max_por_ip)
        self.veto = VetoPorIP(reloj)
        self._altas_max = int(altas_por_minuto)
        self._altas_por_ip = {}                 # ip -> instantes de altas recientes (freno a la ráfaga de altas/bajas)
        self.sala_id = "sala-" + secrets.token_hex(3)
        self.host = None
        self.puerto = None
        # Estado del hilo de red
        self._hilo = None
        self._loop = None
        self._parar = None
        self._arranque = threading.Event()
        self._error_arranque = None
        self._pares = {}            # id -> _Par
        self._ip_de = {}            # id -> ip (para reconectar por nombre+IP)
        self._expulsadas = set()
        self._tareas = set()
        self._servidores = []
        self._aceptando = False
        self._sala_cerrada = False
        self._snap_n = 0
        self._t0 = time.monotonic()
        # T9: vehículos online. Con vehiculos=False el anfitrión es el de siempre (monta_no «desactivado»).
        self.reserva_veh = None
        if vehiculos:
            self.reserva_veh = vehiculos_coop.ReservaVehiculos(vehiculos_coop.aparcados_deterministas(mundo))

    # ======================================================================
    # API pública (hilo del llamador)
    # ======================================================================
    def iniciar(self, timeout=10.0):
        """Arranca el hilo del servidor. Devuelve (host, puerto) donde se escucha."""
        if self._hilo is not None:
            raise RuntimeError("El anfitrión ya se inició.")
        self._hilo = threading.Thread(target=self._hilo_red, name="alcalde-anfitrion", daemon=True)
        self._hilo.start()
        if not self._arranque.wait(timeout):
            raise TimeoutError("El anfitrión no arrancó a tiempo.")
        if self._error_arranque is not None:
            self._hilo.join(2.0)
            raise self._error_arranque
        return self.host, self.puerto

    def activo(self):
        return self._hilo is not None and self._hilo.is_alive()

    def ejecutar(self, fn, timeout=5.0):
        """Ejecuta fn() en el hilo de red (único escritor), vuelca eventos y devuelve su valor."""
        if not self.activo() or self._loop is None:
            raise RuntimeError("El anfitrión no está activo.")
        resultado = concurrent.futures.Future()

        def correr():
            try:
                valor = fn()
                self._volcar_eventos()
                resultado.set_result(valor)
            except BaseException as error:           # se devuelve al hilo que llamó
                resultado.set_exception(error)

        try:
            self._loop.call_soon_threadsafe(correr)
        except RuntimeError:
            raise RuntimeError("El anfitrión no está activo.")
        fin = time.monotonic() + timeout
        while True:
            try:
                return resultado.result(0.05)
            except concurrent.futures.TimeoutError:
                if not resultado.done() and not self.activo():
                    raise RuntimeError("El anfitrión se apagó.")
                if time.monotonic() > fin:
                    raise TimeoutError("El anfitrión no respondió a tiempo.")

    def iniciar_partida(self, forzar=False):
        """Pasa de la sala al juego. ValueError si no hay nadie o falta algún «listo»."""
        return self.ejecutar(lambda: self._iniciar(forzar))

    def expulsar(self, id_jugador, texto="El anfitrión te ha expulsado de la sala."):
        """Echa a un jugador (y veta su IP durante la sala). Si es el anfitrión, cierra la sala."""
        return self.ejecutar(lambda: self._expulsar(self._pares.get(id_jugador), texto))

    def estado(self):
        """Diagnóstico sin datos personales: fase, jugadores y contadores por conexión."""
        return self.ejecutar(self._estado)

    def detener(self, timeout=8.0):
        """Apagado ordenado. Idempotente. Une el hilo (no deja hilos colgados)."""
        hilo = self._hilo
        if hilo is None:
            return
        loop, parar = self._loop, self._parar
        if hilo.is_alive() and loop is not None and parar is not None:
            try:
                loop.call_soon_threadsafe(parar.set)
            except RuntimeError:
                pass
        hilo.join(timeout)

    # ======================================================================
    # Hilo y bucle de red
    # ======================================================================
    def _hilo_red(self):
        try:
            asyncio.run(self._principal())
        except Exception as error:                     # un fallo del hilo no debe quedar mudo
            if not self._arranque.is_set():
                self._error_arranque = error
                self._arranque.set()
            else:
                registro.error("El hilo del anfitrión terminó con %s", type(error).__name__)
        finally:
            self._arranque.set()

    async def _principal(self):
        self._loop = asyncio.get_running_loop()
        self._parar = asyncio.Event()
        try:
            self._servidores = await self._abrir_servidores()
        except (OSError, ValueError) as error:
            self._error_arranque = error
            self._arranque.set()
            return
        self._aceptando = True
        fondo = [asyncio.create_task(self._bucle_snap()), asyncio.create_task(self._bucle_tick())]
        registro.info("Anfitrión escuchando (ámbito %s, puerto %s)", self.ambito, self.puerto)
        self._arranque.set()
        await self._parar.wait()
        await self._apagar(fondo)

    async def _abrir_servidores(self):
        servidores = []
        puerto = self._puerto_pedido
        try:
            for ip in self._ips_escucha:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                if self._sndbuf:
                    sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, int(self._sndbuf))
                try:
                    sock.bind((ip, puerto))
                except OSError:
                    sock.close()
                    raise
                sock.setblocking(False)
                puerto = sock.getsockname()[1]      # los demás sockets usan el mismo puerto
                servidor = await asyncio.start_server(
                    self._atender, sock=sock, limit=limite_lectura(protocolo.DIR_C2H))
                servidores.append(servidor)
        except OSError:
            for servidor in servidores:
                servidor.close()
            raise
        self.puerto = puerto
        primera = self._ips_escucha[0]
        self.host = primera if primera != "0.0.0.0" else (ip_privada_detectada() or "127.0.0.1")
        return servidores

    async def _apagar(self, fondo):
        self._aceptando = False
        for servidor in self._servidores:
            servidor.close()
        if not self._sala_cerrada and self._pares:
            self._sala_cerrada = True
            self._difundir({"t": "sala_cerrada"})
        for tarea in fondo:
            tarea.cancel()
        await asyncio.gather(*fondo, return_exceptions=True)
        await asyncio.gather(*[p.conn.cerrar(True, 1.0) for p in list(self._pares.values())],
                             return_exceptions=True)
        pendientes = list(self._tareas)
        for tarea in pendientes:
            tarea.cancel()
        await asyncio.gather(*pendientes, return_exceptions=True)
        for servidor in self._servidores:
            try:
                async with asyncio.timeout(2.0):
                    await servidor.wait_closed()
            except (TimeoutError, OSError):
                pass

    # ======================================================================
    # Conexiones entrantes
    # ======================================================================
    async def _atender(self, lector, escritor):
        tarea = asyncio.current_task()
        self._tareas.add(tarea)
        conn = None
        par = None
        contada = False
        ip = "?"
        try:
            if self._sndbuf:
                sock = escritor.get_extra_info("socket")
                if sock is not None:
                    sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, int(self._sndbuf))
            conn = Conexion(lector, escritor, protocolo.DIR_C2H, protocolo.DIR_H2C,
                            t_escritura=self._t["escritura"])
            ip = conn.ip
            if not self._aceptando or not ip_permitida(ip, self.ambito):
                conn.abortar("ip_no_permitida")      # sin respuesta: no se informa a desconocidos
                return
            if self.veto.vetada(ip):
                await self._rechazar(conn, "codigo_malo", "Demasiados intentos. Espera un minuto.")
                return
            if not self.conteo.entrar(ip):
                await self._rechazar(conn, "lleno_de_conexiones", "Demasiadas conexiones.")
                return
            contada = True
            par = await self._handshake(conn, ip)
            if par is None:
                return
            conn.limite = LimiteConexion(max_infracciones=self._max_infracciones,
                                         por_tipo=LIMITES_POR_TIPO)
            conn.al_descartar = lambda tipo, p=par: self._avisar_descarte(p, tipo)
            await self._bucle_par(par)
        except asyncio.CancelledError:
            raise
        except Exception as error:                   # nada de lo que haga un par tumba al servidor
            registro.warning("Conexión terminada por %s", type(error).__name__)
        finally:
            try:
                if par is not None:
                    self._desregistrar(par)
            except Exception as error:               # pragma: no cover - defensivo
                registro.error("Fallo al desregistrar: %s", type(error).__name__)
            if contada:
                self.conteo.salir(ip)
            if conn is not None:
                await conn.cerrar(True, 1.0)
            self._tareas.discard(tarea)

    def _alta_permitida(self, ip):
        """Máximo ALTAS_POR_IP_MINUTO entradas autenticadas por IP en 60 s: evita que un invitado
        inunde de `jugador_entra/sale` a los demás clientes (que cortan por `anfitrion_inundando`)."""
        ahora = self._reloj()
        if len(self._altas_por_ip) > _MAX_IP_EN_ALTAS:       # poda las IP sin altas recientes: el dict no crece sin límite
            self._altas_por_ip = {k: v for k, v in self._altas_por_ip.items() if v and ahora - v[-1] < 60.0}
        recientes = [t for t in self._altas_por_ip.get(ip, []) if ahora - t < 60.0]
        if len(recientes) >= self._altas_max:
            self._altas_por_ip[ip] = recientes
            return False
        recientes.append(ahora)
        self._altas_por_ip[ip] = recientes
        return True

    async def _rechazar(self, conn, codigo, texto):
        conn.enviar({"t": "rechazo", "codigo": codigo, "texto": _texto(texto, 200)})
        await conn.cerrar(True, 1.0)

    async def _handshake(self, conn, ip):
        """reto -> hola (HMAC). Devuelve el _Par ya registrado, o None si se rechazó."""
        nonce = huellas.generar_nonce()
        conn.enviar({"t": "reto", "nonce": nonce})
        try:
            hola = await conn.recibir(timeout=self._t["handshake"])
        except protocolo.ErrorProtocolo as error:
            if error.grave:
                self.veto.registrar_fallo(ip)
                return None
            await self._rechazar(conn, "version", "Mensaje inicial no válido (¿versión distinta?).")
            return None
        except TimeoutError:
            # Slowloris: quien abre la conexión y no manda «hola» ocupa un puesto (8 en total) durante T_HANDSHAKE.
            # Un cliente legítimo nunca llega a este punto; repetirlo acaba en veto de la IP (que ya no ocupa puesto).
            self.veto.registrar_fallo(ip)
            return None
        except (ConexionCerrada, LimiteExcedido):
            return None
        if hola["t"] != "hola":
            await self._rechazar(conn, "version", "Se esperaba el saludo inicial.")
            return None
        if hola["juego"] != protocolo.JUEGO or hola["v"] != protocolo.PROTOCOLO_V:
            await self._rechazar(conn, "version",
                                 f"Versión del protocolo distinta (anfitrión: {protocolo.PROTOCOLO_V}).")
            return None
        if ip in self._expulsadas:
            await self._rechazar(conn, "expulsado", "Te expulsaron de esta sala.")
            return None
        try:
            prueba_ok = huellas.verificar_prueba(self.codigo, nonce, hola["nombre"], hola["prueba"])
        except UnicodeError:                         # p. ej. un sustituto suelto en el nombre
            prueba_ok = False
        if not prueba_ok:
            self.veto.registrar_fallo(ip)
            await self._rechazar(conn, "codigo_malo", "Código de sala incorrecto.")
            return None
        self.veto.registrar_exito(ip)
        if hola["huella_mundo"] != self.huella_mundo or hola["huella_contenido"] != self.huella_contenido:
            await self._rechazar(conn, "mundo_distinto",
                                 f"Tu mundo es distinto. Reinicia con ALCALDE_SEMILLA={self.semilla}.")
            return None
        if not self._alta_permitida(ip):
            await self._rechazar(conn, "lleno_de_conexiones", "Demasiadas entradas seguidas. Espera un momento.")
            return None
        resultado = self._admitir(hola, conn, ip)
        if isinstance(resultado, _Rechazo):
            await self._rechazar(conn, resultado.codigo, resultado.texto)
            return None
        par, token = resultado
        conn.enviar({"t": "bienvenida", "v": protocolo.PROTOCOLO_V, "semilla": self.semilla,
                     "huellas": {"mundo": self.huella_mundo, "contenido": self.huella_contenido},
                     "tu_id": par.id, "token": token, "sala": self.sala_id})
        self._volcar_eventos()
        return par

    # ---- Admisión síncrona: sin await entre comprobar y registrar (atómica en el bucle) ----
    def _admitir(self, hola, conn, ip):
        """Devuelve (_Par, token) o un _Rechazo."""
        partida = self.partida
        sesion = partida.sesion
        if self._sala_cerrada or partida.terminada():
            return _Rechazo("sala_llena", "La sala está cerrada.")
        jugador = None
        token_hola = hola.get("token")
        if token_hola:
            jugador = sesion.por_token_hash(huellas.hash_token(token_hola))
        if jugador is None:
            for j in sesion.jugadores():
                if not j.conectado and j.nombre == hola["nombre"] and self._ip_de.get(j.id) == ip:
                    jugador = j
                    break
        if jugador is not None:
            return self._reanudar(jugador, bool(token_hola), conn, ip)
        # --- jugador nuevo ---
        if partida.fase != FASE_SALA:
            return _Rechazo("sala_llena", "La partida ya empezó.")
        if len(sesion.jugadores()) >= MAX_JUGADORES:
            return _Rechazo("sala_llena", "La sala está llena.")
        if (self.exigir_anfitrion_local and partida.anfitrion_id is None
                and not es_ip_local(ip, conn.ip_local())):
            return _Rechazo("sala_llena", "La sala aún no está abierta.")
        nombre = saneado.validar_nombre(hola["nombre"])
        if nombre is None:
            return _Rechazo("nombre_invalido", "Nombre no válido: 1 a 16 letras, números, espacio, - _ .")
        nombre = saneado.nombre_unico(nombre, [j.nombre for j in sesion.jugadores()])
        token = huellas.generar_token()
        try:
            jugador = partida.unir(nombre, None, token_hash=huellas.hash_token(token))
        except ValueError:
            return _Rechazo("sala_llena", "No se pudo entrar a la sala.")
        par = self._registrar(jugador, conn, ip)
        return par, token

    def _reanudar(self, jugador, por_token, conn, ip):
        """Reconexión de un jugador existente (por token, o por nombre+IP)."""
        partida = self.partida
        token = huellas.generar_token()
        viejo = self._pares.get(jugador.id)
        if jugador.conectado:
            # Conexión «zombi» (el corte aún no se detectó): la nueva sustituye a la vieja.
            if viejo is None:
                return _Rechazo("sala_llena", "Ese jugador ya está conectado.")
            if jugador.id != partida.anfitrion_id:
                partida.desconectar(jugador.id)
            viejo.reemplazado = True
            viejo.conn.abortar("reemplazada")
            self._pares.pop(jugador.id, None)
        if not jugador.conectado:
            if partida.reconectar_por_nombre(jugador.nombre, jugador.rol) is None:
                return _Rechazo("sala_llena", "No se pudo reanudar la sesión.")
        jugador.token_hash = huellas.hash_token(token)    # token nuevo en cada reconexión
        par = self._registrar(jugador, conn, ip, reconexion=True)
        return par, token

    def _registrar(self, jugador, conn, ip, reconexion=False):
        validador = ValidadorMovimiento(self.mundo, reloj=self._reloj)
        validador.colocar(jugador.x, jugador.z, jugador.y if reconexion and jugador.y else None)
        if self.reserva_veh is not None:
            self.reserva_veh.liberar_jugador(jugador.id)      # al (re)entrar nadie va montado
            validador.autorizar_vehiculo(None)
        else:
            validador.autorizar_vehiculo(None)    # sin vehículos online nadie puede declarar uno (velocidad de moto a pie)
        if reconexion:
            validador.ultimo_n = -1
        par = _Par(jugador.id, conn, ip, validador)
        self._pares[jugador.id] = par
        self._ip_de[jugador.id] = ip
        return par

    # ======================================================================
    # Sesión de un jugador
    # ======================================================================
    async def _bucle_par(self, par):
        conn = par.conn
        while not conn.cerrada and par.cierre is None:
            try:
                mensaje = await conn.recibir(timeout=self._t["silencio"])
            except TimeoutError:
                break                                    # silencio: se trata como corte
            except ConexionCerrada:
                break
            except protocolo.ErrorProtocolo:
                self.veto.registrar_fallo(par.ip)        # basura: corte (puede reconectar en gracia)
                break
            except LimiteExcedido:
                self._expulsar(par, "Demasiados mensajes por segundo.")
                break
            try:
                self._despachar(par, mensaje)
            except Exception as error:                  # un mensaje raro no debe cortar al jugador
                registro.warning("Fallo al procesar %s: %s", mensaje.get("t"), type(error).__name__)
                conn.limite.registrar_infraccion()
            self._volcar_eventos()
            if par.validador.debe_desconectar:
                self._expulsar(par, "Movimiento no válido repetido.")
                break

    def _desregistrar(self, par):
        if self._pares.get(par.id) is par:
            self._liberar_vehiculo(par)                  # T9: el vehículo queda aparcado donde estaba
            del self._pares[par.id]
        if par.reemplazado or par.cierre is not None:
            self._volcar_eventos()
            return
        partida = self.partida
        if partida.sesion.por_id(par.id) is not None:
            partida.desconectar(par.id)                  # corte de red: gracia de reconexión
        self._volcar_eventos()

    # Un mensaje que cuenta para la partida (decisión) se descartó por tasa: se avisa al cliente con un
    # error explícito para que reenvíe, en vez de dejar la mano desincronizada en silencio.
    def _avisar_descarte(self, par, tipo):
        if tipo == "decision":
            par.conn.enviar({"t": "error", "motivo": "decision_limite_tasa"})

    # ---- Despacho de mensajes C2H ----
    def _despachar(self, par, msg):
        t = msg["t"]
        partida = self.partida
        i = par.id
        if t == "pos":
            self._pos(par, msg)
        elif t == "ping":
            par.conn.enviar({"t": "pong", "n": msg["n"], "tt": msg["tt"]})
        elif t == "pong":
            pass
        elif t == "listo":
            try:
                partida.marcar_listo(i, msg["listo"])
            except ValueError:
                self._error(par, "fase_invalida")
                return
            if self.auto_iniciar and partida.fase == FASE_SALA and partida.todos_listos():
                self._iniciar(False)
        elif t == "iniciar":
            self._iniciar_por_cliente(par)
        elif t == "rol":
            self._cambiar_rol(par, msg["rol"])
        elif t == "montar":
            self._montar(par, msg["veh"])
        elif t == "bajar":
            self._bajar(par)
        elif t == "interactuar":
            if self.reserva_veh is not None and self.reserva_veh.de_jugador(i) is not None:
                par.conn.enviar({"t": "rechazo_interactuar", "motivo": "Baja del vehículo primero."})
                return
            partida.interactuar(i)
        elif t == "decision":
            if msg["n"] <= par.ultimo_decision:          # repetida o atrasada
                return
            par.ultimo_decision = msg["n"]
            # Las noticias del catálogo tienen id entero; en la red viajan como texto.
            noticia = next((n for n in partida.mano_de(i) if str(n) == msg["noticia"]), msg["noticia"])
            partida.decidir(i, msg["mision"], noticia, msg["tipo"])
        elif t == "salir_edificio":
            partida.salir_edificio(i)
            jugador = partida.sesion.por_id(i)
            if jugador is not None and "dentro" in jugador.banderas:
                # Reaparece en la puerta (la posición no cambió mientras estaba «dentro»). Solo
                # si realmente estaba dentro: si no, repetir este mensaje recargaría el presupuesto
                # de movimiento del validador.
                partida.sesion.mover(i, jugador.x, jugador.z, jugador.y, jugador.rumbo, 0.0, ())
                par.validador.colocar(jugador.x, jugador.z)
        elif t == "saludo_rapido":
            self._difundir({"t": "saludo", "id": i, "indice": msg["indice"]})
        elif t == "adios":
            par.cierre = "adios"
            partida.salir(i, "adios")
        else:                                            # «hola» repetido u otro tipo fuera de turno
            par.conn.limite.registrar_infraccion()

    def _pos(self, par, msg):
        partida = self.partida
        if partida.fase != FASE_JUEGO:
            return
        # El validador espera solo los campos de movimiento (sin la clave «t» del protocolo).
        res = par.validador.validar({k: v for k, v in msg.items() if k != "t"})
        if res.aceptado:
            # La bandera de vehículo la normaliza el validador con lo que concedió la reserva (T9).
            banderas = par.validador.f if self.reserva_veh is not None else msg["f"]
            partida.actualizar_posicion(par.id, res.x, res.z, res.y, msg["r"], msg["v"],
                                        mascara_a_banderas(banderas))
            if self.reserva_veh is not None:
                self.reserva_veh.mover(par.id, res.x, res.z, msg["r"])
        elif res.ignorado:
            if msg["f"] & BANDERA_DENTRO:
                self._liberar_vehiculo(par, avisar=True, motivo="dentro")     # entrar a un edificio = bajarse
                partida.actualizar_posicion(par.id, res.x, res.z, res.y, msg["r"], msg["v"],
                                            mascara_a_banderas(msg["f"]))
        elif res.corregir:
            par.conn.enviar({"t": "corregir", "x": res.x, "z": res.z, "y": res.y, "seq": res.seq})

    # ---- Vehículos (T9) ----
    def _montar(self, par, veh):
        reserva = self.reserva_veh
        if reserva is None:
            par.conn.enviar({"t": "monta_no", "motivo": vehiculos_coop.MOTIVO_DESACTIVADO})
            return
        partida = self.partida
        jugador = partida.sesion.por_id(par.id)
        if partida.fase != FASE_JUEGO or jugador is None or not jugador.conectado:
            par.conn.enviar({"t": "monta_no", "motivo": vehiculos_coop.MOTIVO_FASE})
            return
        if "dentro" in jugador.banderas:
            par.conn.enviar({"t": "monta_no", "motivo": vehiculos_coop.MOTIVO_DENTRO})
            return
        v = par.validador
        ok, resultado = reserva.montar(par.id, veh, v.x, v.z)      # posición AUTORIZADA, no la que diga el cliente
        if not ok:
            par.conn.enviar({"t": "monta_no", "motivo": resultado})
            return
        v.autorizar_vehiculo(resultado.tipo)
        par.conn.enviar({"t": "monta_ok", "veh": resultado.id})

    def _bajar(self, par):
        self._liberar_vehiculo(par)

    # Libera la montura del jugador (baja, desconexión, entrada a un edificio). `avisar`: manda «desmontado» al cliente.
    def _liberar_vehiculo(self, par, avisar=False, motivo="bajada"):
        reserva = self.reserva_veh
        if reserva is None:
            return
        liberado = reserva.bajar(par.id)
        par.validador.autorizar_vehiculo(None)
        if liberado is not None and avisar and not par.conn.cerrada:
            par.conn.enviar({"t": "desmontado", "motivo": motivo})

    def _cambiar_rol(self, par, rol):
        partida = self.partida
        if rol not in ROLES:
            self._error(par, "rol_invalido")
            return
        if any(j.rol == rol and j.id != par.id for j in partida.sesion.jugadores()):
            par.conn.enviar({"t": "rechazo", "codigo": "rol_tomado", "texto": "Ese rol ya está tomado."})
            return
        try:
            partida.cambiar_rol(par.id, rol)
        except ValueError:
            self._error(par, "fase_invalida")
            return
        jugador = partida.sesion.por_id(par.id)
        par.validador.colocar(jugador.x, jugador.z)

    def _iniciar_por_cliente(self, par):
        # T8: solo el anfitrión (primer jugador) puede iniciar, y solo desde la sala con todos listos.
        partida = self.partida
        if par.id != partida.anfitrion_id:
            self._error(par, "solo_anfitrion")
            return
        if partida.fase != FASE_SALA:
            return                                   # ya empezó: idempotente
        try:
            self._iniciar(False)
        except ValueError:
            self._error(par, "faltan_listos")

    def _error(self, par, motivo):
        par.conn.enviar({"t": "error", "motivo": _texto(motivo, 200)})

    # ---- Acciones del anfitrión ----
    def _iniciar(self, forzar):
        partida = self.partida
        partida.iniciar(forzar=forzar)
        if self.reserva_veh is not None:
            self.reserva_veh.reiniciar()
        # Posiciones iniciales autorizadas: spawns del rol, a la altura del suelo.
        for jugador in partida.sesion.jugadores():
            par = self._pares.get(jugador.id)
            y = float(self.mundo.altura_con_escaleras(jugador.x, jugador.z))
            partida.sesion.mover(jugador.id, jugador.x, jugador.z, y, 0.0, 0.0, ())
            if par is not None:
                par.validador.colocar(jugador.x, jugador.z, y)
                par.validador.ultimo_n = -1
        self._volcar_eventos()

    def _expulsar(self, par, texto="Expulsado de la sala."):
        if par is None:
            return False
        par.cierre = "expulsado"
        par.conn.enviar({"t": "rechazo", "codigo": "expulsado", "texto": _texto(texto, 200)})
        partida = self.partida
        if partida.sesion.por_id(par.id) is not None:
            partida.salir(par.id, "expulsado")
        if self._bloquear_loopback or not es_ip_local(par.ip, par.conn.ip_local()):
            self._expulsadas.add(par.ip)
        tarea = asyncio.get_running_loop().create_task(par.conn.cerrar(True, 1.0))
        self._tareas.add(tarea)                       # referencia fuerte hasta que termine
        tarea.add_done_callback(self._tareas.discard)
        self._volcar_eventos()
        return True

    def _estado(self):
        partida = self.partida
        return {
            "fase": partida.fase,
            "jugadores": [{"id": j.id, "nombre": j.nombre, "rol": j.rol, "conectado": j.conectado}
                          for j in sorted(partida.sesion.jugadores(), key=lambda j: j.id)],
            "conexiones": {
                i: {"snap_omitidos": p.conn.descartados, "enviados": p.conn.enviados,
                    "recibidos": p.conn.recibidos, "pendiente": p.conn.pendiente(),
                    "infracciones": p.conn.limite.infracciones if p.conn.limite else 0,
                    "puntos_movimiento": p.validador.puntos,
                    "errores_envio": p.conn.errores_envio}
                for i, p in self._pares.items()},
            "total_conexiones": self.conteo.total(),
            "sala_cerrada": self._sala_cerrada,
        }

    # ======================================================================
    # Eventos de la partida -> mensajes del protocolo
    # ======================================================================
    def _volcar_eventos(self):
        if self._loop is None:
            return
        for evento in self.partida.tomar_eventos():
            for destino, mensaje in self._traducir(evento):
                if destino is None:
                    self._difundir(mensaje)
                else:
                    par = self._pares.get(destino)
                    if par is not None:
                        par.conn.enviar(mensaje)
        if self._sala_cerrada and self._parar is not None and not self._parar.is_set():
            # El anfitrión se fue: tras repartir «sala_cerrada» se apaga el servidor.
            asyncio.get_running_loop().call_later(0.2, self._parar.set)

    def _difundir(self, mensaje, descartable=False):
        try:
            datos = protocolo.codificar(mensaje, protocolo.DIR_H2C)
        except protocolo.ErrorProtocolo as error:
            registro.warning("Mensaje %s no codificable: %s", mensaje.get("t"), error.codigo)
            return
        for par in list(self._pares.values()):
            par.conn.enviar_bytes(datos, descartable)

    def _traducir(self, ev):
        """Evento de PartidaCooperativa -> [(destino|None, mensaje)]. Solo campos del esquema."""
        t = ev["t"]
        para = ev.get("para")
        if t in ("jugador_entra", "jugador_sale", "jugador_desconectado", "jugador_reconectado"):
            return [(para, {"t": t, "id": ev["id"]})]
        if t == "sala":
            return [(para, {"t": "sala", "jugadores": ev["jugadores"], "roles_libres": ev["roles_libres"]})]
        if t == "inicio":
            spawns = []
            for i, (x, z) in sorted(ev["spawns"].items()):
                spawns.append({"id": i, "x": x, "z": z,
                               "y": round(float(self.mundo.altura_con_escaleras(x, z)), 3)})
            return [(para, {"t": "inicio", "cuenta": self._cuenta, "spawns": spawns, "mision": None})]
        if t == "ok":
            return [(para, {"t": "ok"})]
        if t == "rechazo_interactuar":
            return [(para, {"t": t, "motivo": _texto(ev["motivo"], 120)})]
        if t in ("rechazo_decision", "error"):
            prefijo = "decision_" if t == "rechazo_decision" else ""
            return [(para, {"t": "error", "motivo": _texto(prefijo + str(ev["motivo"]), 200)})]
        if t == "mision":
            hechas = [_texto(h, 64) for h in self.partida.reserva.completadas()][:16]
            return [(para, {"t": "mision", "id": ev["id"], "mano": [str(m["id"]) for m in ev["mano"]][:8],
                            "hechas": hechas})]
        if t == "ind":
            return [(para, {"t": "ind", "valores": ev["valores"], "autor": ev["autor"],
                            "deltas": ev["deltas"]})]
        if t == "mision_cerrada":
            # Solo a su dueño: los demás se enteran por «ind» y por las «hechas» de su próxima misión.
            return [(ev["jugador"], {"t": "mision_cerrada", "id": ev["id"], "siguiente": ev["siguiente"]})]
        if t == "fin":
            resumen = ev.get("resumen") or {}
            texto = ("Completadas: " + ", ".join(resumen.get("completadas", []))
                     + ". Pendientes: " + ", ".join(resumen.get("pendientes", [])) + ".")
            return [(para, {"t": "fin", "indicadores": ev["indicadores"], "resumen": _texto(texto, 1000)})]
        if t == "sala_cerrada":
            self._sala_cerrada = True
            return [(para, {"t": "sala_cerrada"})]
        return []

    # ======================================================================
    # Bucles de fondo
    # ======================================================================
    async def _bucle_snap(self):
        periodo = 1.0 / self._hz_snap
        loop = asyncio.get_running_loop()
        siguiente = loop.time() + periodo
        while True:
            await asyncio.sleep(max(0.0, siguiente - loop.time()))
            siguiente += periodo
            if siguiente < loop.time():                  # nos atrasamos: no recuperar a ráfagas
                siguiente = loop.time() + periodo
            if self.partida.fase != FASE_JUEGO or not self._pares:
                continue
            self._snap_n = (self._snap_n + 1) % (2 ** 31)
            jugadores = []
            for e in self.partida.sesion.snapshot_jugadores():
                jugadores.append({"i": e["i"], "x": round(e["x"], 3), "z": round(e["z"], 3),
                                  "y": round(e["y"], 3), "r": round(e["r"], 1),
                                  "v": round(e["v"], 2), "f": e["f"]})
            snap = {"t": "snap", "n": self._snap_n, "tt": round(time.monotonic() - self._t0, 3),
                    "jugadores": jugadores}
            if self.reserva_veh is not None and len(self.reserva_veh):
                snap["veh"] = self.reserva_veh.snapshot()
            try:
                datos = protocolo.codificar(snap, protocolo.DIR_H2C)
            except protocolo.ErrorProtocolo as error:
                registro.warning("Snapshot no codificable: %s", error.codigo)
                continue
            for par in list(self._pares.values()):
                par.conn.enviar_bytes(datos, descartable=True)

    async def _bucle_tick(self):
        ultimo_veto = time.monotonic()
        while True:
            await asyncio.sleep(self._t["tick"])
            try:
                self.partida.tick()
                self._volcar_eventos()
            except Exception as error:                  # el reloj de la sala no debe morir
                registro.error("Fallo en el tick: %s", type(error).__name__)
            if time.monotonic() - ultimo_veto > LIMPIEZA_VETO_S:
                self.veto.limpiar()
                ultimo_veto = time.monotonic()
