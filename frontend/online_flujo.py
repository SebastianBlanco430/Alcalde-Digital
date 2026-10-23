# Flujo de partida del modo ONLINE (cliente). Es la fachada que usan las escenas en lugar de
# FlujoPartida cuando se juega en línea: expone la MISMA superficie pública (sesion,
# jugador_activo, mision_actual, estado_mision, puede_interactuar, hay_mision_activa,
# partida_terminada, actualizar_posicion, iniciar_minijuego, cancelar_minijuego,
# completar_mision) y por debajo habla con el anfitrión a través de ClienteRed.
#
# Reglas del cliente:
#   - jugador_activo() es SIEMPRE el jugador LOCAL (no hay turnos: todos juegan a la vez).
#   - El anfitrión es autoritativo. Aquí vive un ESPEJO (SistemaMisionesCoop, mismo código
#     que el del anfitrión) solo para que el «Presiona E» responda sin esperar a la red; lo
#     que decide el anfitrión (mision, ok, rechazo_interactuar, ind, mision_cerrada, fin)
#     corrige al espejo.
#   - interactuar es OPTIMISTA: iniciar_minijuego() pasa el espejo a EN_MINIJUEGO y manda
#     «interactuar»; si llega «ok» se confirma y si llega «rechazo_interactuar» se revierte
#     por el camino existente (ConexionEnLinea._revertir_al_mundo, vía `al_rechazo`).
#   - completar_mision() IGNORA el resultado calculado por el cliente: el anfitrión ya cerró
#     la misión con sus propios deltas (mision_cerrada); aquí solo se cierra el espejo.
#   - sesion devuelve un objeto NUEVO cada vez que cambia el roster (EscenaMundo reconstruye
#     los avatares al cambiar la identidad de flujo.sesion); los Jugador (y su teléfono) se
#     conservan entre una sesión y la siguiente.
#   - Los ids de noticia viajan como TEXTO en la red («40») y son enteros en la partida.
#
# Todo ocurre en el hilo del juego: procesar_evento() se llama desde BucleRed (online_bucle)
# con eventos YA validados por ClienteRed. Nada aquí bloquea ni toca sockets directamente
# (los envíos de ClienteRed son no bloqueantes).

import logging
import time

from backend.datos.ciudad_3d import ESCALA_MUNDO
from backend.datos.misiones_semilla import CATALOGO_MISIONES
from backend.datos.noticias_semilla import construir_arboles
from backend.logica.estado_partida import NOMBRES_INDICADORES, VALOR_INICIAL, recortar
from backend.logica.flujo_partida import MENSAJE_SIN_MISIONES
from backend.logica.misiones import COMPLETADA, EN_MINIJUEGO
from backend.logica.roles import ROLES
from backend.red.interpolacion_calculos import InterpoladorRemoto
from backend.red.mision_coop import ReservaMisiones, SistemaMisionesCoop
from backend.red.sesion_en_linea import JugadorEnLinea, SesionEnLinea, mascara_a_banderas
from frontend import online_config

_registro = logging.getLogger("alcalde.online.flujo")

DECISIONES_VALIDAS = ("compartir", "reportar")

# El anfitrión limita «decision» a 2/s (ráfaga 2): el cliente nunca manda más de DECISIONES_POR_VENTANA en
# VENTANA_DECISIONES s (con margen), y encola el resto.
DECISIONES_POR_VENTANA = 2
VENTANA_DECISIONES = 1.1

# Texto (para el teléfono) de cada motivo con que el anfitrión puede rechazar una interacción.
TEXTOS_RECHAZO = {
    "fuera_de_radio": "Civitas: aún estás lejos de la puerta. Acércate un poco más.",
    "no_disponible": "Civitas: no tienes una misión disponible en este momento.",
    "conexion_perdida": "Civitas: se perdió la conexión con la sala.",
}
TEXTO_RECHAZO_GENERICO = "Civitas: el anfitrión no te dejó entrar. Inténtalo de nuevo."


# ---------------------------------------------------------------------------
# Estado de la partida visto desde el cliente
# ---------------------------------------------------------------------------
# Hace de EstadoPartida para EscenaJuego (hay_noticia, noticia_actual().texto, decidir(tipo),
# indicadores) y para el mundo (sesion.estado_partida.indicadores()). Las noticias son las de
# la MANO que el anfitrión repartió a este jugador; los deltas de cada decisión se calculan
# aquí con los árboles locales (respuesta inmediata) y se mandan al anfitrión, que recalcula
# y devuelve los indicadores autoritativos («ind»), que los corrigen.
class EstadoRemoto:

    def __init__(self, arbol_noticias, arbol_stats, al_decidir=None, id_mision=None):
        self.arbol_noticias = arbol_noticias
        self.arbol_stats = arbol_stats
        self._al_decidir = al_decidir        # callable(id_mision, id_noticia, tipo) -> bool
        self._id_mision = id_mision          # callable() -> id de la misión activa o None
        self._indicadores = {nombre: VALOR_INICIAL for nombre in NOMBRES_INDICADORES}
        self._mano = []                      # [(NodoNoticia, camino)] por decidir
        self._copia = None                   # (mano, indicadores) guardados al abrir el minijuego

    # -- Consulta (misma API que EstadoPartida) --

    def indicadores(self):
        return dict(self._indicadores)

    def noticia_actual(self):
        return self._mano[0][0] if self._mano else None

    def camino_actual(self):
        return self._mano[0][1] if self._mano else None

    def hay_noticia(self):
        return bool(self._mano)

    def mano_ids(self):
        return [nodo.id for nodo, _ in self._mano]

    # -- Cambios --

    def aplicar_deltas(self, deltas):
        for nombre in NOMBRES_INDICADORES:
            self._indicadores[nombre] = recortar(self._indicadores[nombre] + deltas.get(nombre, 0))

    # Fija los indicadores AUTORITATIVOS (los del anfitrión) recortando a [0, 100].
    def fijar_indicadores(self, valores):
        for nombre in NOMBRES_INDICADORES:
            valor = valores.get(nombre)
            if isinstance(valor, (int, float)) and not isinstance(valor, bool):
                self._indicadores[nombre] = recortar(valor)

    # Sustituye la mano por las noticias de `ids` (TEXTO en la red, entero en la partida).
    # Los ids que no existen en el árbol local o no son números se descartan. Devuelve cuántas quedaron.
    def poner_mano(self, ids):
        mano = []
        for bruto in ids:
            id_noticia = _entero(bruto)
            if id_noticia is None:
                _registro.warning("Id de noticia no válido ignorado.")
                continue
            nodo, camino = self.arbol_noticias.buscar_con_camino(id_noticia)
            if nodo is None:
                _registro.warning("Noticia %s desconocida: se ignora.", id_noticia)
                continue
            mano.append((nodo, camino))
        self._mano = mano
        return len(mano)

    # Resuelve la noticia activa con los árboles locales, aplica los deltas de forma PROVISIONAL
    # y avisa al anfitrión. Devuelve los deltas (copia) o None si no hay noticia o misión.
    # Igual que EstadoPartida.decidir, un tipo inválido lanza ValueError.
    def decidir(self, tipo):
        if tipo not in DECISIONES_VALIDAS:
            raise ValueError(f"Decisión inválida: {tipo!r}; se esperaba una de {DECISIONES_VALIDAS}.")
        if not self._mano:
            return None
        id_mision = self._id_mision() if self._id_mision is not None else None
        if id_mision is None:
            return None
        nodo, camino = self._mano[0]
        nodo_stats = self.arbol_stats.obtener_por_camino(camino)
        if nodo_stats is None:
            _registro.warning("Isomorfismo roto para la noticia %s: se descarta.", nodo.id)
            self._mano.pop(0)
            return None
        deltas = dict(nodo_stats.deltas_compartir if tipo == "compartir" else nodo_stats.deltas_reportar)
        self.aplicar_deltas(deltas)
        self._mano.pop(0)
        if self._al_decidir is not None:
            self._al_decidir(id_mision, nodo.id, tipo)
        return deltas

    # Compatibilidad con EstadoPartida: aquí la mano la reparte el anfitrión, no se avanza sola.
    def siguiente_noticia(self):
        return None

    # -- Copia de seguridad (para revertir una interacción rechazada) --

    def guardar_copia(self):
        self._copia = (list(self._mano), dict(self._indicadores))

    def restaurar_copia(self):
        if self._copia is not None:
            self._mano, self._indicadores = list(self._copia[0]), dict(self._copia[1])
        self._copia = None

    def descartar_copia(self):
        self._copia = None


# Entero seguro desde un id de red (TEXTO «40» o ya entero); None si no es un número razonable.
def _entero(bruto):
    if isinstance(bruto, bool):
        return None
    if isinstance(bruto, int):
        return bruto
    if isinstance(bruto, str) and bruto.isascii() and bruto.isdigit() and len(bruto) <= 9:
        return int(bruto)
    return None


# ---------------------------------------------------------------------------
# Reserva y sesión locales
# ---------------------------------------------------------------------------
# Reserva del espejo: el árbitro real es el anfitrión, así que aquí solo se vigila que la
# misión no esté ya «en curso» por este mismo jugador; lo completado no la bloquea (el
# anfitrión puede volver a ofrecerla tras una reconexión) y completar es tolerante.
class _ReservaEspejo(ReservaMisiones):

    def disponible(self, id_mision):
        return id_mision in self._por_id and id_mision not in self._en_curso

    def completar(self, id_mision, id_jugador):
        if self._en_curso.get(id_mision) != id_jugador:
            return
        del self._en_curso[id_mision]
        if id_mision not in self._completadas:
            self._completadas.append(id_mision)


# Sesión que ve la escena: los jugadores (local primero en el turno) con un estado compartido.
# Sin turnos: pasar_turno() no rota. Se construye con objetos Jugador ya existentes.
class _SesionLocal(SesionEnLinea):

    def __init__(self, estado_partida, jugadores, indice_local, escala_mundo=1.0):
        super().__init__(estado_partida, escala_mundo=escala_mundo)
        self._jugadores = list(jugadores)
        self._indice_turno = indice_local

    def pasar_turno(self):
        return self.jugador_activo()


# ---------------------------------------------------------------------------
# Flujo en línea
# ---------------------------------------------------------------------------
class FlujoEnLinea:

    # cliente: ClienteRed (o falso con la misma API). mundo: MundoCiudad (punto_interaccion,
    # coordenada). tu_id: slot asignado por el anfitrión. jugadores: entradas de «sala»
    # [{id, nombre, rol, conectado, ...}] (debe incluir a tu_id con un rol válido).
    def __init__(self, cliente, mundo, tu_id, jugadores, catalogo=None, arboles=None,
                 radio_interaccion=None, escala_mundo=ESCALA_MUNDO, reloj=time.monotonic):
        self.cliente = cliente
        self.tu_id = tu_id
        self._mundo = mundo
        self._reloj = reloj
        self._escala = escala_mundo
        self._catalogo = tuple(CATALOGO_MISIONES if catalogo is None else catalogo)
        self._por_id = {m.id: m for m in self._catalogo}
        if arboles is None:
            arboles = construir_arboles()
        radio = online_config.RADIO_INTERACCION if radio_interaccion is None else radio_interaccion

        self.estado = EstadoRemoto(arboles[0], arboles[1], al_decidir=self._enviar_decision,
                                   id_mision=self._id_mision_actual)
        self._sistema = SistemaMisionesCoop(
            mundo, self._catalogo, _ReservaEspejo(self._catalogo), tu_id,
            punto_interaccion=mundo.punto_interaccion, radio_interaccion=radio)

        self._jugadores = {}            # id -> JugadorEnLinea (persisten entre sesiones)
        self._firma = None              # (id, nombre, rol) de todos: cambia ⇒ sesión nueva
        self._sesion = None
        self.version_roster = 0         # +1 cada vez que `sesion` se reconstruye
        self._interpoladores = {}       # id remoto -> InterpoladorRemoto
        self._muestras = {}             # id remoto -> última Muestra
        self._teletransportes = set()
        self._correccion = None
        self.vehiculos_snap = []        # T9: último `veh` del snapshot [{i,k,x,z,r,p?}] (vacío sin VEHICULOS_ONLINE)
        self.eventos_vehiculo = []      # T9: monta_ok / monta_no / desmontado por consumir (IntegracionVehiculosOnline)

        # Estado de la partida / interacción
        self.en_juego = False           # llegó «inicio»
        self._fin = False
        self.resumen_fin = ""
        self.misiones_hechas = []
        self._confirmacion = None       # None | "pendiente" | "ok" | "rechazada"
        self.ultimo_rechazo = None
        self._suprimir_envio = False    # al revertir por rechazo no se avisa «salir_edificio»
        self._decisiones_en_cola = []   # decisiones por enviar (espaciadas, ver _enviar_decision)
        self._envios_decision = []      # instantes de los últimos envíos de decisión (ventana deslizante)
        self._ultima_enviada = None     # (mision, noticia, tipo) por si el anfitrión avisa de un descarte
        self._cierre_pendiente = None   # {"id", "siguiente"}: el anfitrión cerró la misión; el espejo espera
        self._diferidos = []            # eventos «mision» retenidos hasta cerrar el espejo
        self._dentro = False            # el jugador está dentro de un edificio (bandera «dentro»)
        self.al_rechazo = None          # callable(motivo): ConexionEnLinea revierte las escenas
        self.ultimo_ind = None          # {"autor", "deltas", "propio", "n"}
        self._n_ind = 0
        self.ultimo_saludo = None       # (id, indice)
        self.ultimo_error = None
        self.reconectando = False
        self.cerrado_motivo = None      # motivo del cierre definitivo (None = sigue abierto)
        self.sala_cerrada = False

        self._aplicar_roster(jugadores)
        if tu_id not in self._jugadores:
            raise ValueError("El jugador local no está en el roster de la sala.")

    # Construye el flujo a partir de los eventos retenidos de la sala (BucleRed.eventos_retenidos()):
    # toma tu_id y el último roster y luego reproduce el resto en orden (inicio, mision, ind...).
    @classmethod
    def desde_eventos(cls, cliente, eventos, mundo, **opciones):
        tu_id = cliente.tu_id
        sala = None
        for ev in eventos:
            if ev.get("t") == "bienvenida":
                tu_id = ev.get("tu_id", tu_id)
            elif ev.get("t") == "sala":
                sala = ev
        if tu_id is None or sala is None:
            raise ValueError("Faltan la bienvenida o la sala para crear el flujo en línea.")
        flujo = cls(cliente, mundo, tu_id, sala["jugadores"], **opciones)
        for ev in eventos:
            if ev.get("t") not in ("bienvenida", "estado", "sala", "snap"):
                flujo.procesar_evento(ev)
        return flujo

    # ======================================================================
    # Superficie pública de FlujoPartida
    # ======================================================================
    @property
    def sesion(self):
        return self._sesion

    @property
    def jugador(self):
        return self._jugadores[self.tu_id]

    def iniciar(self):
        # El anfitrión es quien arranca la partida y asigna la misión (evento «mision»).
        return self.mision_actual()

    def mision_actual(self):
        return self._sistema.mision_actual()

    def jugador_activo(self):
        return self._jugadores[self.tu_id]

    def estado_mision(self):
        return self._sistema.estado()

    def puede_interactuar(self):
        # Sin conexión de juego no se abre el minijuego (el «E» no haría nada útil).
        return self._sistema.puede_interactuar() and self._conectado()

    def hay_mision_activa(self):
        return self._sistema.mision_actual() is not None

    # Fin de partida (evento «fin» del anfitrión) y el jugador ya cerró su último minijuego.
    def partida_terminada(self):
        return self._fin and self._sistema.estado() not in (EN_MINIJUEGO, COMPLETADA)

    def actualizar_posicion(self, x, z):
        jugador = self.jugador
        jugador.x = x
        jugador.z = z
        self._sistema.actualizar_posicion(x, z)

    # Abre el minijuego de forma OPTIMISTA: el espejo pasa a EN_MINIJUEGO ya y se pide al anfitrión.
    # Confirma «ok»; «rechazo_interactuar» revierte (ver al_rechazo).
    def iniciar_minijuego(self):
        self._sistema.iniciar_minijuego()
        self.estado.guardar_copia()
        self._confirmacion = "pendiente"
        self._dentro = True
        self.cliente.enviar_interactuar()
        return {"jugador": self.jugador, "mision": self._sistema.mision_actual(), "estado": self.estado}

    # EN_MINIJUEGO -> EN_RADIO (la escena no pudo abrirse o el anfitrión rechazó).
    def cancelar_minijuego(self):
        self._sistema.cancelar_minijuego()
        self._dentro = False
        self._confirmacion = None
        if self._suprimir_envio:
            return
        self.estado.descartar_copia()
        self.cliente.enviar_salir_edificio()      # el anfitrión devuelve la misión a EN_RADIO

    # Cierra el minijuego en el espejo. El resultado calculado por el cliente se IGNORA: el
    # anfitrión ya cerró la misión con sus deltas (mision_cerrada). Devuelve el jugador local.
    def completar_mision(self, resultado=None):
        sistema = self._sistema
        self._dentro = False
        self._confirmacion = None
        self.estado.descartar_copia()
        self.cliente.enviar_salir_edificio()      # libera la bandera «dentro» en el anfitrión
        if sistema.estado() == EN_MINIJUEGO:
            if self._cierre_pendiente is None:
                # El anfitrión aún no cerró la misión (decisiones perdidas o lag): no se inventa un
                # cierre; la misión vuelve a EN_RADIO y el cierre real llegará (o se reintenta con E).
                sistema.cancelar_minijuego()
                return self.jugador
            cierre, self._cierre_pendiente = self._cierre_pendiente, None
            sistema.completar({"mision": cierre["id"]})
            sistema.terminar()
            if cierre["siguiente"] is None and not self._hay_mision_diferida():
                self._avisar_sin_misiones()
        self._aplicar_diferidos()
        return self.jugador

    # ======================================================================
    # Extras para T7/T8 (mundo y HUD en línea)
    # ======================================================================
    def jugadores_remotos(self):
        return [j for i, j in sorted(self._jugadores.items()) if i != self.tu_id]

    def jugador_por_id(self, id_jugador):
        return self._jugadores.get(id_jugador)

    def esta_dentro(self):
        return self._dentro

    def confirmacion(self):
        return self._confirmacion

    @property
    def latencia_ms(self):
        return getattr(self.cliente, "latencia_ms", None)

    def estado_conexion(self):
        return getattr(self.cliente, "estado", None)

    # Corrección de posición enviada por el anfitrión ((x, z, y) o None); se consume al leerla.
    def tomar_correccion(self):
        correccion, self._correccion = self._correccion, None
        return correccion

    # True una sola vez tras un salto grande de un jugador remoto (colocar sin deslizar).
    def tomar_teletransporte(self, id_jugador):
        if id_jugador in self._teletransportes:
            self._teletransportes.discard(id_jugador)
            return True
        return False

    def muestra_de(self, id_jugador):
        return self._muestras.get(id_jugador)

    # Avanza a los jugadores remotos al instante de dibujo (interpolación); lo llama BucleRed cada frame.
    def avanzar(self, ahora=None):
        if self._decisiones_en_cola:
            self._vaciar_decisiones()
        for id_jugador, interpolador in self._interpoladores.items():
            jugador = self._jugadores.get(id_jugador)
            muestra = interpolador.muestrear(ahora)
            if jugador is None or muestra is None:
                continue
            jugador.x, jugador.z, jugador.y = muestra.x, muestra.z, muestra.y
            jugador.rumbo, jugador.velocidad = muestra.r, muestra.v
            jugador.fijar_banderas(mascara_a_banderas(muestra.f))
            self._muestras[id_jugador] = muestra
            if muestra.teletransporte:
                self._teletransportes.add(id_jugador)

    # ======================================================================
    # Eventos de red (llamados por BucleRed, hilo del juego)
    # ======================================================================
    def procesar_evento(self, ev):
        manejador = getattr(self, "_ev_" + str(ev.get("t")), None)
        if manejador is None:
            return
        manejador(ev)

    def _ev_sala(self, ev):
        self._aplicar_roster(ev["jugadores"])

    def _ev_inicio(self, ev):
        self.en_juego = True
        for spawn in ev.get("spawns", ()):
            jugador = self._jugadores.get(spawn["id"])
            if jugador is None:
                continue
            jugador.x, jugador.z, jugador.y = spawn["x"], spawn["z"], spawn["y"]
            if spawn["id"] == self.tu_id and self.hay_mision_activa():
                self._sistema.actualizar_posicion(jugador.x, jugador.z)

    def _ev_jugador_sale(self, ev):
        id_jugador = ev["id"]
        if id_jugador == self.tu_id or id_jugador not in self._jugadores:
            return
        del self._jugadores[id_jugador]
        self._interpoladores.pop(id_jugador, None)
        self._muestras.pop(id_jugador, None)
        self._teletransportes.discard(id_jugador)
        self._reconstruir_sesion()

    def _ev_jugador_desconectado(self, ev):
        jugador = self._jugadores.get(ev["id"])
        if jugador is not None:
            jugador.conectado = False

    def _ev_jugador_reconectado(self, ev):
        jugador = self._jugadores.get(ev["id"])
        if jugador is not None:
            jugador.conectado = True

    def _ev_snap(self, ev):
        recibido = ev.get("recibido")
        for entrada in ev["jugadores"]:
            id_jugador = entrada["i"]
            if id_jugador == self.tu_id or id_jugador not in self._jugadores:
                continue           # la posición propia la manda el cliente; los demás, el anfitrión
            interpolador = self._interpoladores.get(id_jugador)
            if interpolador is None:
                interpolador = self._interpoladores[id_jugador] = InterpoladorRemoto(reloj=self._reloj)
            interpolador.agregar(ev["tt"], entrada["x"], entrada["z"], entrada["y"], entrada["r"],
                                 entrada["v"], entrada["f"], recibido=recibido)
        if "ind" in ev:
            self.estado.fijar_indicadores(ev["ind"])
        if "veh" in ev:
            self.vehiculos_snap = ev["veh"]

    # T9: respuestas del anfitrión a montar / bajada forzosa. Se encolan y las consume la integración de vehículos.
    def _ev_monta_ok(self, ev):
        self._encolar_vehiculo(ev)

    def _ev_monta_no(self, ev):
        self._encolar_vehiculo(ev)

    def _ev_desmontado(self, ev):
        self._encolar_vehiculo(ev)

    def _encolar_vehiculo(self, ev):
        self.eventos_vehiculo.append(dict(ev))
        del self.eventos_vehiculo[:-16]       # tope: nadie debería acumular más

    def tomar_eventos_vehiculo(self):
        eventos, self.eventos_vehiculo = self.eventos_vehiculo, []
        return eventos

    def _ev_corregir(self, ev):
        jugador = self.jugador
        jugador.x, jugador.z, jugador.y = ev["x"], ev["z"], ev["y"]
        self._sistema.actualizar_posicion(jugador.x, jugador.z)
        self._correccion = (ev["x"], ev["z"], ev["y"])

    def _ev_mision(self, ev):
        if self._cierre_pendiente is not None:
            self._diferidos.append(ev)      # el espejo aún cierra la misión anterior
            return
        self._aplicar_mision(ev)

    def _ev_ok(self, ev):
        if self._confirmacion == "pendiente":
            self._confirmacion = "ok"
            self.estado.descartar_copia()

    def _ev_rechazo_interactuar(self, ev):
        if self._confirmacion != "pendiente" or self._sistema.estado() != EN_MINIJUEGO:
            return
        motivo = ev.get("motivo", "")
        self.ultimo_rechazo = motivo
        self._confirmacion = "rechazada"
        self._avisar(TEXTOS_RECHAZO.get(motivo, TEXTO_RECHAZO_GENERICO))
        self._revertir_minijuego(motivo)

    def _ev_ind(self, ev):
        self.estado.fijar_indicadores(ev["valores"])
        self._n_ind += 1
        self.ultimo_ind = {"autor": ev["autor"], "deltas": dict(ev["deltas"]),
                           "propio": ev["autor"] == self.tu_id, "n": self._n_ind}

    def _ev_mision_cerrada(self, ev):
        actual = self._sistema.mision_actual()
        if actual is None or actual.id != ev["id"]:
            return
        estado = self._sistema.estado()
        if estado == EN_MINIJUEGO:
            # La escena del minijuego sigue abierta: el espejo se cierra en completar_mision().
            self._cierre_pendiente = {"id": ev["id"], "siguiente": ev["siguiente"]}
            return
        if estado == COMPLETADA:
            self._sistema.terminar()
        else:
            self._sistema.liberar()      # el cierre llegó tarde (se había vuelto a EN_RADIO)
        if ev["siguiente"] is None:
            self._avisar_sin_misiones()

    def _ev_fin(self, ev):
        self.estado.fijar_indicadores(ev["indicadores"])
        self.resumen_fin = ev.get("resumen", "")
        self._fin = True

    def _ev_saludo(self, ev):
        self.ultimo_saludo = (ev["id"], ev["indice"])

    def _ev_error(self, ev):
        self.ultimo_error = ev.get("motivo")
        # El anfitrión descartó la última decisión por tasa: se reenvía (más espaciada) en vez de perderla.
        if self.ultimo_error == "decision_limite_tasa" and self._ultima_enviada is not None \
                and self._sistema.estado() == EN_MINIJUEGO and self._cierre_pendiente is None:
            self._decisiones_en_cola.insert(0, self._ultima_enviada)
            self._ultima_enviada = None
            self._envios_decision.append(self._reloj())      # la ventana se llena: el reenvío espera
            self._envios_decision.append(self._reloj())

    def _ev_reconectando(self, ev):
        self.reconectando = True

    def _ev_reconectado(self, ev):
        self.reconectando = False
        if self._sistema.estado() == EN_MINIJUEGO:
            # El anfitrión devolvió la misión a EN_RADIO al perderte: se pide de nuevo la interacción.
            self._confirmacion = "pendiente"
            self.cliente.enviar_interactuar()

    def _ev_sala_cerrada(self, ev):
        self.sala_cerrada = True

    def _ev_cerrado(self, ev):
        self.cerrado_motivo = ev.get("motivo") or "cerrado"
        self.reconectando = False
        if self._sistema.estado() == EN_MINIJUEGO and self._cierre_pendiente is None:
            self._avisar(TEXTOS_RECHAZO["conexion_perdida"])
            self._revertir_minijuego("conexion_perdida")

    # ======================================================================
    # Internos
    # ======================================================================
    def _conectado(self):
        return getattr(self.cliente, "estado", "en_juego") == "en_juego"

    def _id_mision_actual(self):
        mision = self._sistema.mision_actual()
        return mision.id if mision is not None else None

    # Las decisiones se envían separadas al menos SEPARACION_DECISIONES s: el anfitrión admite ~2/s y descartaba
    # el exceso. Si aún no toca, se encolan y avanzar() las manda a su hora (siempre en orden).
    def _enviar_decision(self, id_mision, id_noticia, tipo):
        self._decisiones_en_cola.append((id_mision, id_noticia, tipo))
        self._vaciar_decisiones()
        return True

    def _vaciar_decisiones(self):
        while self._decisiones_en_cola:
            ahora = self._reloj()
            while self._envios_decision and ahora - self._envios_decision[0] >= VENTANA_DECISIONES:
                self._envios_decision.pop(0)
            if len(self._envios_decision) >= DECISIONES_POR_VENTANA:
                return
            id_mision, id_noticia, tipo = self._decisiones_en_cola[0]
            if not self.cliente.enviar_decision(id_mision, id_noticia, tipo):
                return                            # sin conexión: se reintenta en el siguiente frame
            self._decisiones_en_cola.pop(0)
            self._ultima_enviada = (id_mision, id_noticia, tipo)
            self._envios_decision.append(ahora)

    def _avisar(self, texto):
        self.jugador.telefono.notificar(texto)

    def _avisar_sin_misiones(self):
        mensajes = self.jugador.telefono.mensajes()
        if mensajes and mensajes[-1].texto == MENSAJE_SIN_MISIONES:
            return
        self._avisar(MENSAJE_SIN_MISIONES)

    # Revierte el minijuego del espejo: primero deja que ConexionEnLinea devuelva las escenas al
    # mundo (que a su vez llama a cancelar_minijuego) y si nadie lo hizo, lo hace aquí. Restaura
    # la mano y los indicadores de antes de abrir (no se avisa «salir_edificio»: no hace falta).
    def _revertir_minijuego(self, motivo):
        self._suprimir_envio = True
        try:
            if self.al_rechazo is not None:
                try:
                    self.al_rechazo(motivo)
                except Exception:       # noqa: BLE001 - un fallo de la escena no debe dejar el espejo colgado
                    _registro.exception("Falló la reversión de escenas tras el rechazo.")
            if self._sistema.estado() == EN_MINIJUEGO:
                self._sistema.cancelar_minijuego()
        finally:
            self._suprimir_envio = False
            self._dentro = False
            self._decisiones_en_cola.clear()       # las decisiones sin enviar de un minijuego revertido ya no valen
            self.estado.restaurar_copia()

    def _hay_mision_diferida(self):
        return any(ev.get("t") == "mision" for ev in self._diferidos)

    def _aplicar_diferidos(self):
        pendientes, self._diferidos = self._diferidos, []
        for ev in pendientes:
            if self._cierre_pendiente is not None:
                self._diferidos.append(ev)
            else:
                self._aplicar_mision(ev)

    # Asigna (o refresca) la misión del evento «mision» en el espejo, con su mano de noticias.
    def _aplicar_mision(self, ev):
        mision = self._por_id.get(ev["id"])
        if mision is None:
            return
        self.misiones_hechas = list(ev.get("hechas", ()))
        actual = self._sistema.mision_actual()
        if actual is None or actual.id != mision.id:
            if actual is not None:
                if self._sistema.estado() == EN_MINIJUEGO:
                    self._diferidos.append(ev)     # no se pisa un minijuego abierto
                    return
                self._sistema.liberar()
            self._sistema.asignar_por_id(mision.id)
            self._avisar(mision.mensaje)
            self._sistema.actualizar_posicion(self.jugador.x, self.jugador.z)
        self.estado.poner_mano(ev.get("mano", ()))

    # Actualiza los jugadores con el roster de «sala» (conservando los objetos existentes) y,
    # si cambió quién está o con qué rol, reconstruye la sesión.
    def _aplicar_roster(self, entradas):
        nuevos = {}
        for entrada in entradas:
            rol = entrada.get("rol")
            if rol not in ROLES:
                continue
            id_jugador = entrada["id"]
            jugador = self._jugadores.get(id_jugador)
            if jugador is None:
                info = ROLES[rol]
                jugador = JugadorEnLinea(entrada["nombre"], rol, info.spawn_x * self._escala,
                                         info.spawn_y * self._escala, id=id_jugador)
            else:
                jugador.nombre = entrada["nombre"]
                if jugador.rol != rol:
                    info = ROLES[rol]
                    jugador.rol = rol
                    jugador.x, jugador.z = info.spawn_x * self._escala, info.spawn_y * self._escala
            jugador.conectado = bool(entrada.get("conectado", True))
            nuevos[id_jugador] = jugador
        # El jugador local no desaparece por un roster incompleto.
        local = self._jugadores.get(self.tu_id)
        if self.tu_id not in nuevos and local is not None:
            nuevos[self.tu_id] = local
        self._jugadores = nuevos
        self._reconstruir_sesion()

    def _reconstruir_sesion(self):
        firma = tuple(sorted((i, j.nombre, j.rol) for i, j in self._jugadores.items()))
        if firma == self._firma and self._sesion is not None:
            return
        self._firma = firma
        ordenados = [self._jugadores[i] for i in sorted(self._jugadores)]
        indice = next((k for k, j in enumerate(ordenados) if j.id == self.tu_id), 0)
        self._sesion = _SesionLocal(self.estado, ordenados, indice, self._escala)
        self.version_roster += 1
        self._sistema.fijar_roles_en_juego(j.rol for j in ordenados)
