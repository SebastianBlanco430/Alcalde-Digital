# Transporte de red del modo online (solo stdlib, asyncio). Una `Conexion` envuelve un par
# StreamReader/StreamWriter y entrega/recibe mensajes YA validados por backend.red.protocolo
# (JSON por líneas). Se usa igual en el anfitrión y en el cliente; nunca toca ursina/panda3d.
#
# Qué hace:
#   - Lectura: una línea por mensaje con tope de bytes (StreamReader(limit=...)), timeout por
#     línea y `decodificar` (JSON estricto + esquema). Un error GRAVE (línea gigante, JSON roto,
#     NaN, UTF-8 inválido) se propaga para que quien llama cierre la conexión; un error NO grave
#     (campo desconocido, fuera de rango...) cuenta como infracción y se descarta el mensaje.
#   - Límites de tasa: si se da un `LimiteConexion`, cada mensaje debe ser admitido (60 msg/s
#     sostenido, ráfaga 120, cubos por tipo). Fuera de tasa: se descarta y se cuenta infracción;
#     al llegar al tope de infracciones se lanza LimiteExcedido (corte por spam).
#   - Escritura: cola acotada en bytes + hilo de escritura asíncrono. Los mensajes
#     «descartables» (pos, snap) NO se encolan si el búfer pendiente supera el umbral
#     (contrapresión); un mensaje crítico que no cabe en la cola cierra la conexión (cliente
#     demasiado lento) en vez de bloquear al resto. `enviar` nunca espera.
#   - TCP_NODELAY y keepalive, timeout de escritura (drain) y cierre limpio (drena y cierra).
#
# Todo el objeto vive en el bucle de asyncio que lo creó: no es seguro desde otros hilos.
import asyncio
import collections
import logging
import socket

from backend.red import protocolo
from backend.red.protocolo import ErrorProtocolo

registro = logging.getLogger("alcalde.red.transporte")

MAX_COLA_BYTES = 256 * 1024         # tope de bytes pendientes por conexión (cola + búfer del socket)
UMBRAL_CONTRAPRESION = 32 * 1024    # por encima, no se encolan mensajes descartables
T_ESCRITURA = 10.0                  # s máximos para vaciar el búfer hacia un par lento
MARGEN_LIMITE_LECTURA = 512         # holgura del StreamReader sobre el tope de línea del protocolo


class ConexionCerrada(Exception):
    """El par cerró (EOF), la conexión se abortó o ya estaba cerrada."""


class LimiteExcedido(Exception):
    """El par superó el tope de infracciones (spam o basura repetida)."""


def limite_lectura(direccion_entrante):
    """`limit` para open_connection/start_server según de dónde vienen las líneas."""
    tope = protocolo.MAX_LINEA_H2C if direccion_entrante == protocolo.DIR_H2C else protocolo.MAX_LINEA_SALUDO
    return tope + MARGEN_LIMITE_LECTURA


class Conexion:
    """Conexión de mensajes sobre un socket asyncio (ver el comentario del módulo)."""

    def __init__(self, lector, escritor, direccion_entrante, direccion_saliente, limite=None,
                 max_cola=MAX_COLA_BYTES, umbral=UMBRAL_CONTRAPRESION, t_escritura=T_ESCRITURA):
        self._lector = lector
        self._escritor = escritor
        self.direccion_entrante = direccion_entrante
        self.direccion_saliente = direccion_saliente
        self.limite = limite                     # LimiteConexion o None
        self._max_cola = int(max_cola)
        self._umbral = int(umbral)
        self._t_escritura = float(t_escritura)
        self._cola = collections.deque()
        self._bytes_cola = 0
        self._evento = asyncio.Event()
        self._cerrando = False
        self.cerrada = False
        self.motivo_cierre = None
        self.descartados = 0                      # mensajes descartables omitidos por contrapresión
        self.enviados = 0
        self.recibidos = 0
        self.errores_envio = 0                    # mensajes propios que no pasaron el esquema
        self.ip = self._leer_ip()
        self._preparar_socket()
        transporte = escritor.transport
        try:
            transporte.set_write_buffer_limits(high=64 * 1024, low=16 * 1024)
        except (AttributeError, NotImplementedError):
            pass
        self._tarea = asyncio.get_running_loop().create_task(self._bucle_escritura())

    # -- Información --

    def _leer_ip(self):
        par = self._escritor.get_extra_info("peername")
        return par[0] if par else "?"

    def ip_local(self):
        """IP local del socket (para saber si el par es de la misma máquina)."""
        nombre = self._escritor.get_extra_info("sockname")
        return nombre[0] if nombre else "?"

    def _preparar_socket(self):
        # TCP_NODELAY: nada de esperar a juntar paquetes (pos/snap son pequeños y frecuentes).
        sock = self._escritor.get_extra_info("socket")
        if sock is None:
            return
        try:
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
        except OSError:
            pass

    def pendiente(self):
        """Bytes por enviar: nuestra cola + lo que el transporte aún no entregó al sistema."""
        try:
            en_transporte = self._escritor.transport.get_write_buffer_size()
        except (AttributeError, RuntimeError):
            en_transporte = 0
        return self._bytes_cola + en_transporte

    def contrapresion(self):
        """True si el par va lento: no hay que enviarle más mensajes descartables."""
        return self.pendiente() > self._umbral

    # -- Lectura --

    async def recibir(self, timeout=None):
        """Espera un mensaje válido y lo devuelve como dict.

        Lanza ConexionCerrada (EOF/abortada), TimeoutError (sin línea completa en `timeout` s),
        ErrorProtocolo GRAVE (basura: hay que cerrar) o LimiteExcedido (spam). Los errores no
        graves y los mensajes fuera de tasa se descartan aquí si hay `limite`; sin `limite`
        todo error se propaga.
        """
        while True:
            linea = await self._leer_linea(timeout)
            try:
                mensaje = protocolo.decodificar(linea, self.direccion_entrante)
            except ErrorProtocolo as error:
                if error.grave or self.limite is None:
                    raise
                self.limite.registrar_infraccion()
                if self.limite.debe_cerrar():
                    raise LimiteExcedido("infracciones")
                continue
            if self.limite is not None:
                if not self.limite.admitir(mensaje["t"]):
                    if self.limite.debe_cerrar():
                        raise LimiteExcedido("tasa")
                    continue
            self.recibidos += 1
            return mensaje

    async def _leer_linea(self, timeout):
        if self.cerrada:
            raise ConexionCerrada(self.motivo_cierre or "cerrada")
        try:
            if timeout is None:
                linea = await self._lector.readline()
            else:
                async with asyncio.timeout(timeout):
                    linea = await self._lector.readline()
        except ValueError:                     # línea mayor que el `limit` del StreamReader
            raise ErrorProtocolo("demasiado_grande", True, "limite_lector")
        except asyncio.LimitOverrunError:
            raise ErrorProtocolo("demasiado_grande", True, "limite_lector")
        except TimeoutError:                   # (TimeoutError es subclase de OSError: va antes)
            raise
        except (ConnectionError, OSError):
            raise ConexionCerrada("error_socket")
        if not linea or not linea.endswith(b"\n"):
            raise ConexionCerrada("eof")        # EOF (una línea a medias se descarta)
        return linea

    # -- Escritura --

    def enviar(self, mensaje, descartable=False):
        """Codifica (con esquema) y encola. False si no se envió (cerrada, descarte, error)."""
        try:
            datos = protocolo.codificar(mensaje, self.direccion_saliente)
        except ErrorProtocolo as error:
            self.errores_envio += 1
            registro.warning("Mensaje %s no enviado: %s", mensaje.get("t") if isinstance(mensaje, dict) else "?", error.codigo)
            return False
        return self.enviar_bytes(datos, descartable)

    def enviar_bytes(self, datos, descartable=False):
        """Encola bytes ya codificados (sirve para repartir un mismo mensaje a varios pares)."""
        if self.cerrada or self._cerrando:
            return False
        if descartable and self.contrapresion():
            self.descartados += 1
            return False
        if self.pendiente() + len(datos) > self._max_cola:
            self.abortar("cola_llena")          # par demasiado lento: se le corta
            return False
        self._cola.append(datos)
        self._bytes_cola += len(datos)
        self.enviados += 1
        self._evento.set()
        return True

    async def _bucle_escritura(self):
        try:
            while True:
                while not self._cola:
                    if self._cerrando:
                        return
                    self._evento.clear()
                    await self._evento.wait()
                datos = self._cola.popleft()
                self._bytes_cola -= len(datos)
                self._escritor.write(datos)
                try:
                    async with asyncio.timeout(self._t_escritura):
                        await self._escritor.drain()
                except TimeoutError:
                    self.abortar("escritura_lenta")
                    return
        except (ConnectionError, OSError):
            self.abortar("error_socket")
        except asyncio.CancelledError:
            raise

    # -- Cierre --

    def abortar(self, motivo="abortada"):
        """Cierre inmediato, sin drenar (par lento o culpable). Idempotente."""
        if self.cerrada:
            return
        self.cerrada = True
        self.motivo_cierre = motivo
        self._cola.clear()
        self._bytes_cola = 0
        self._evento.set()
        try:
            self._escritor.transport.abort()
        except (AttributeError, RuntimeError, OSError):
            pass
        tarea = getattr(self, "_tarea", None)
        if tarea is not None and tarea is not asyncio.current_task():
            tarea.cancel()

    async def cerrar(self, drenar=True, timeout=1.0):
        """Cierre limpio: opcionalmente vacía lo pendiente (hasta `timeout` s) y cierra."""
        if self.cerrada:
            await self._esperar_tarea()
            return
        self._cerrando = True
        self._evento.set()
        if drenar and not self._tarea.done():
            try:
                async with asyncio.timeout(timeout):
                    await asyncio.shield(self._tarea)
            except (TimeoutError, asyncio.CancelledError, ConnectionError, OSError):
                pass
        self.cerrada = True
        self.motivo_cierre = self.motivo_cierre or "cerrada"
        self._cola.clear()
        self._bytes_cola = 0
        if not self._tarea.done():
            self._tarea.cancel()
        await self._esperar_tarea()
        try:
            self._escritor.close()
            async with asyncio.timeout(1.0):
                await self._escritor.wait_closed()
        except (TimeoutError, ConnectionError, OSError, RuntimeError):
            pass

    async def _esperar_tarea(self):
        try:
            await self._tarea
        except (asyncio.CancelledError, ConnectionError, OSError):
            pass


async def abrir_conexion(host, puerto, direccion_entrante, direccion_saliente, timeout, **kw):
    """Abre una conexión TCP saliente (lado cliente) y la envuelve en una `Conexion`."""
    async with asyncio.timeout(timeout):
        lector, escritor = await asyncio.open_connection(
            host, puerto, limit=limite_lectura(direccion_entrante))
    return Conexion(lector, escritor, direccion_entrante, direccion_saliente, **kw)

