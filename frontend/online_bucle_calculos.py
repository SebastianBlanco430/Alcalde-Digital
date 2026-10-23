# Núcleo PURO (sin ursina) del bucle de red: drena los eventos de ClienteRed con tope por frame,
# envía la posición local a 20 Hz, reparte los eventos a los suscriptores y al FlujoEnLinea y
# traduce desconexión/reconexión a avisos con TEXTO (no solo color). Nunca bloquea.
import time
from collections import deque

from frontend import online_config

NORMAL, INESTABLE, RECONECTANDO, PERDIDA = "normal", "inestable", "reconectando", "perdida"
UMBRAL_INESTABLE = 0.5      # s sin mensajes del anfitrión
UMBRAL_RECUPERADO = 0.25
MAX_RETENIDOS = 256
DURACION_MENSAJE = 3.0

TEXTOS_MOTIVO = {
    "sala_cerrada": "El anfitrión cerró la sala.",
    "expulsado": "El anfitrión te expulsó de la sala.",
    "reconexion_agotada": "No se pudo reconectar a tiempo.",
    "conexion_perdida": "Se perdió la conexión.",
    "silencio_del_anfitrion": "El anfitrión dejó de responder.",
    "no_se_pudo_conectar": "No se pudo conectar con el anfitrión.",
    "codigo_malo": "Código de sala incorrecto.",
    "mundo_distinto": "Tu mundo no coincide con el del anfitrión.",
    "version": "Versión del juego distinta a la del anfitrión.",
}


class NucleoRed:

    def __init__(self, cliente, flujo=None, fuente_pos=None, max_eventos=None, hz_pos=None,
                 reloj=time.monotonic):
        self.cliente = cliente
        self.flujo = flujo
        self.fuente_pos = fuente_pos        # callable() -> (x, z, y, rumbo, velocidad, banderas) | None
        self.max_eventos = max_eventos or online_config.EVENTOS_POR_FRAME
        self.periodo_pos = 1.0 / (hz_pos or online_config.HZ_POS)
        self._reloj = reloj
        self._acum = 0.0
        self._suscriptores = []
        self._retenidos = deque(maxlen=MAX_RETENIDOS)
        self._bienvenida = None
        self.condicion = NORMAL
        self.motivo_perdida = None
        self._mensajes = []                 # [(texto, expira)]
        self.pos_enviadas = 0

    # -- Suscripción y retención --
    def suscribir(self, fn):
        if fn not in self._suscriptores:
            self._suscriptores.append(fn)

    def desuscribir(self, fn):
        if fn in self._suscriptores:
            self._suscriptores.remove(fn)

    def fijar_flujo(self, flujo):
        self.flujo = flujo

    # Eventos de sala/partida ya vistos (sin snap), con la última bienvenida delante.
    def eventos_retenidos(self):
        lista = list(self._retenidos)
        if self._bienvenida is not None and self._bienvenida not in lista:
            lista.insert(0, self._bienvenida)
        return lista

    # -- Avisos --
    def texto_condicion(self):
        if self.condicion == INESTABLE:
            return "Conexión inestable"
        if self.condicion == RECONECTANDO:
            return "Reconectando…"
        if self.condicion == PERDIDA:
            return TEXTOS_MOTIVO.get(self.motivo_perdida, "Conexión perdida.")
        return ""

    def mensaje_actual(self):
        ahora = self._reloj()
        self._mensajes = [m for m in self._mensajes if m[1] > ahora]
        return self._mensajes[-1][0] if self._mensajes else None

    def aviso(self):
        return self.texto_condicion() or self.mensaje_actual() or ""

    def _mensaje(self, texto):
        self._mensajes.append((texto, self._reloj() + DURACION_MENSAJE))

    # -- Un frame --
    def paso(self, dt):
        eventos = self.cliente.sacar_eventos(self.max_eventos)
        for ev in eventos:
            self._atender(ev)
        if self.flujo is not None:
            self.flujo.avanzar()
        self._revisar_silencio()
        self._enviar_pos(dt)
        return eventos

    def _atender(self, ev):
        t = ev.get("t")
        if t == "bienvenida":
            self._bienvenida = ev
        elif t not in ("snap", "estado"):
            self._retenidos.append(ev)
        self._avisos(ev)
        if self.flujo is not None:
            try:
                self.flujo.procesar_evento(ev)
            except Exception:       # noqa: BLE001 - un evento raro no debe tumbar el bucle
                import logging
                logging.getLogger("alcalde.online.bucle").exception("Fallo al procesar %s", t)
        for fn in list(self._suscriptores):
            try:
                fn(ev)
            except Exception:       # noqa: BLE001
                import logging
                logging.getLogger("alcalde.online.bucle").exception("Fallo en un suscriptor")

    def _avisos(self, ev):
        t = ev.get("t")
        if t == "reconectando":
            self.condicion = RECONECTANDO
        elif t == "reconectado":
            self.condicion = NORMAL
            self._mensaje("Reconectado")
        elif t in ("cerrado",):
            self.condicion = PERDIDA
            self.motivo_perdida = ev.get("motivo")
        elif t == "jugador_desconectado":
            self._mensaje("Un jugador perdió la conexión")
        elif t == "jugador_reconectado":
            self._mensaje("Un jugador volvió")
        elif t == "jugador_sale":
            self._mensaje("Un jugador salió de la sala")

    def _revisar_silencio(self):
        if self.condicion in (RECONECTANDO, PERDIDA) or getattr(self.cliente, "estado", None) != "en_juego":
            return
        silencio = self.cliente.silencio()
        if silencio > UMBRAL_INESTABLE:
            self.condicion = INESTABLE
        elif silencio < UMBRAL_RECUPERADO and self.condicion == INESTABLE:
            self.condicion = NORMAL

    def _enviar_pos(self, dt):
        self._acum += dt
        if self._acum < self.periodo_pos:
            return
        self._acum = 0.0 if self._acum > 2 * self.periodo_pos else self._acum - self.periodo_pos
        if self.fuente_pos is None or getattr(self.cliente, "estado", None) != "en_juego":
            return
        datos = self.fuente_pos()
        if datos is not None and self.cliente.enviar_pos(*datos):
            self.pos_enviadas += 1


# Fuente de posición: lee del FlujoEnLinea (x, z, «dentro») y del avatar local (y, rumbo,
# velocidad, aire, escalera). `obtener_avatar` es callable() -> Personaje | None; `vehiculos`
# opcional con `.conduciendo`.
def fuente_pos_local(flujo, obtener_avatar=None, vehiculos=None):
    def leer():
        j = flujo.jugador
        avatar = obtener_avatar() if obtener_avatar is not None else None
        y = float(getattr(avatar, "y", j.y) if avatar is not None else j.y)
        rumbo = float(getattr(avatar, "rumbo", j.rumbo) if avatar is not None else j.rumbo) % 360.0
        vel = max(0.0, float(getattr(avatar, "velocidad", 0.0) or 0.0))
        banderas = set()
        if avatar is not None and getattr(avatar, "_en_aire", False):
            banderas.add("en_aire")
        if avatar is not None and getattr(avatar, "_subiendo", False):
            banderas.add("escalera")
        if flujo.esta_dentro():
            banderas.add("dentro")
        if vehiculos is not None and getattr(vehiculos, "conduciendo", False):
            banderas.add("vehiculo")
        return (j.x, j.z, y, rumbo, vel, banderas)
    return leer
