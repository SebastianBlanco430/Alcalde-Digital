# Partida cooperativa en tiempo real (modelo puro, sin red ni ursina). Es lo que ejecuta el
# ANFITRIÓN: único escritor del estado. T4 (transporte) solo traduce mensajes <-> métodos de
# esta clase y reparte los EVENTOS de salida.
#
# Qué comparte y qué no:
#   - UN EstadoPartida (los indicadores son de la ciudad).
#   - Una ReservaMisiones común y un SistemaMisionesCoop + LoteMision POR jugador, así que
#     varias misiones corren a la vez sin repetirse.
#   - Una MANO de noticias por jugador, robada del mazo compartido sin repetir entre manos.
#     El anfitrión calcula los deltas con el ArbolStats (mismo camino que EstadoPartida.decidir);
#     nunca confía en un resultado enviado por el cliente.
#
# API: métodos directos (unir, iniciar, actualizar_posicion, interactuar, decidir, salir,
# desconectar, reconectar_*, tick) o la cola determinista recibir()/procesar(), que ordena
# por (id_jugador, seq). Toda salida va al registro de EVENTOS (lista de dicts con clave "t"
# y "para": id del destinatario o None = a todos); se leen con tomar_eventos().
#
# Reloj inyectable (`reloj`, por defecto time.monotonic) para probar la gracia sin dormir.

import random
import time

from backend.logica.lote_mision import LoteMision
from backend.logica.mazo_noticias import MazoNoticias
from backend.logica.misiones import EN_MINIJUEGO
from backend.red.mision_coop import ReservaMisiones, SistemaMisionesCoop
from backend.red.sesion_en_linea import SesionEnLinea

# Segundos que se retiene el rol/misión de quien pierde la conexión antes de darlo por salido.
GRACIA_RECONEXION = 90.0

FASE_SALA = "sala"
FASE_JUEGO = "juego"
FASE_FIN = "fin"

DECISIONES_VALIDAS = ("compartir", "reportar")


# MazoNoticias con generador propio: la misma semilla da la misma secuencia de noticias sin
# tocar el `random` global. Clase nueva; MazoNoticias no se modifica.
class MazoSembrado(MazoNoticias):

    def __init__(self, arbol_noticias, semilla=None):
        super().__init__(arbol_noticias)
        self._rng = random.Random(semilla)

    def siguiente(self):
        if not self.ids_disponibles:
            return None
        if not self.hay_pendientes():
            self.reiniciar()
        pendientes = [i for i in self.ids_disponibles if i not in self.ids_vistos]
        if len(pendientes) > 1 and self._ultimo_id in pendientes:
            pendientes.remove(self._ultimo_id)
        elegido = self._rng.choice(pendientes)
        nodo, camino = self.arbol_noticias.buscar_con_camino(elegido)
        self.ids_vistos.add(elegido)
        self._ultimo_id = elegido
        return nodo, camino


class PartidaCooperativa:

    def __init__(self, estado_partida, mapa, catalogo, grafo_social=None, reloj=time.monotonic,
                 escala_mundo=1.0, punto_interaccion=None, radio_interaccion=1.5,
                 histeresis=0.3, gracia=GRACIA_RECONEXION):
        self.sesion = SesionEnLinea(estado_partida, escala_mundo=escala_mundo)
        self.reserva = ReservaMisiones(catalogo)
        self._mapa = mapa
        self._catalogo = list(catalogo)
        self._grafo = grafo_social
        self._reloj = reloj
        self._gracia = gracia
        self._opciones_sistema = {
            "punto_interaccion": punto_interaccion,
            "radio_interaccion": radio_interaccion,
            "histeresis": histeresis,
        }
        self._fase = FASE_SALA
        self._anfitrion_id = None
        self._listos = set()
        self._sistemas = {}    # id -> SistemaMisionesCoop
        self._lotes = {}       # id -> LoteMision de la misión activa
        self._manos = {}       # id -> [(NodoNoticia, camino)] por decidir
        self._cierres = []     # [{"mision", "jugador", "nombre", "decisiones"}] en orden
        self._entradas = []    # cola de recibir()
        self._ultimo_seq = {}  # id -> último seq procesado
        self._eventos = []
        self._fin_emitido = False

    # -- Consulta --

    @property
    def fase(self):
        return self._fase

    @property
    def estado_partida(self):
        return self.sesion.estado_partida

    @property
    def anfitrion_id(self):
        return self._anfitrion_id

    def terminada(self):
        return self._fase == FASE_FIN

    def sistema_de(self, id_jugador):
        return self._sistemas.get(id_jugador)

    def lote_de(self, id_jugador):
        return self._lotes.get(id_jugador)

    # Copia de la mano pendiente (ids de noticia) del jugador.
    def mano_de(self, id_jugador):
        return [nodo.id for nodo, _ in self._manos.get(id_jugador, [])]

    def todos_listos(self):
        conectados = self.sesion.jugadores_conectados()
        return bool(conectados) and all(j.id in self._listos for j in conectados)

    # Devuelve y vacía el registro de eventos de salida.
    def tomar_eventos(self):
        eventos, self._eventos = self._eventos, []
        return eventos

    def eventos(self):
        return list(self._eventos)

    # -- Sala --

    # Une a un jugador (solo en la sala). rol None = el primero libre. El primero en unirse es
    # el anfitrión. ValueError con las mismas reglas de SesionJuego (rol/nombre/aforo).
    def unir(self, nombre, rol=None, token_hash=None):
        if self._fase != FASE_SALA:
            raise ValueError("La partida ya empezó: no se admiten jugadores nuevos.")
        if rol is None:
            libres = self.sesion.roles_disponibles()
            if not libres:
                raise ValueError("No quedan roles libres.")
            rol = libres[0]
        jugador = self.sesion.agregar_jugador(nombre, rol, token_hash=token_hash)
        if self._anfitrion_id is None:
            self._anfitrion_id = jugador.id
        self._sistemas[jugador.id] = SistemaMisionesCoop(
            self._mapa, self._catalogo, self.reserva, jugador.id, **self._opciones_sistema)
        self._sincronizar_roles()
        self._emitir("jugador_entra", id=jugador.id, nombre=jugador.nombre, rol=jugador.rol)
        self._emitir_sala()
        return jugador

    def cambiar_rol(self, id_jugador, rol):
        self._exigir_fase(FASE_SALA, "cambiar de rol")
        self.sesion.cambiar_rol(id_jugador, rol)
        self._listos.discard(id_jugador)
        self._sincronizar_roles()
        self._emitir_sala()

    def marcar_listo(self, id_jugador, listo=True):
        self._exigir_fase(FASE_SALA, "marcar listo")
        if self.sesion.por_id(id_jugador) is None:
            raise ValueError(f"No existe el jugador {id_jugador!r}.")
        if listo:
            self._listos.add(id_jugador)
        else:
            self._listos.discard(id_jugador)
        self._emitir_sala()

    # Arranca la partida y asigna una misión a cada jugador (en orden de slot). ValueError si
    # no está en la sala, no hay nadie o falta algún listo (salvo `forzar`).
    def iniciar(self, forzar=False):
        self._exigir_fase(FASE_SALA, "iniciar")
        if not self.sesion.jugadores_conectados():
            raise ValueError("No hay jugadores: no se puede iniciar la partida.")
        if not forzar and not self.todos_listos():
            raise ValueError("No todos los jugadores están listos.")
        self._fase = FASE_JUEGO
        self._sincronizar_roles()
        spawns = {j.id: [j.x, j.z] for j in self._por_slot()}
        self._emitir("inicio", spawns=spawns)
        self._repartir_libres()
        self._comprobar_fin()

    # -- Conexión --

    # El jugador se despide: libera misión y rol. Si era el anfitrión, la partida se cierra.
    def salir(self, id_jugador, motivo="adios"):
        jugador = self.sesion.por_id(id_jugador)
        if jugador is None:
            return False
        if id_jugador == self._anfitrion_id:
            self._cerrar_por_anfitrion(motivo)
            return True
        sistema = self._sistemas.pop(id_jugador, None)
        if sistema is not None:
            sistema.liberar()
        self._lotes.pop(id_jugador, None)
        self._manos.pop(id_jugador, None)
        self._listos.discard(id_jugador)
        self._ultimo_seq.pop(id_jugador, None)
        self.sesion.quitar_jugador(id_jugador)
        self._sincronizar_roles()
        self._emitir("jugador_sale", id=id_jugador, nombre=jugador.nombre, motivo=motivo)
        if self._fase == FASE_SALA:
            self._emitir_sala()
        elif self._fase == FASE_JUEGO:
            self._repartir_libres()
            self._comprobar_fin()
        return True

    # Corte de red. En la sala se trata como salida; en juego se retienen rol y misión
    # GRACIA_RECONEXION segundos. Si estaba en un minijuego, se conserva lo decidido y la
    # misión vuelve a EN_RADIO. Anfitrión desconectado = fin de partida.
    def desconectar(self, id_jugador):
        jugador = self.sesion.por_id(id_jugador)
        if jugador is None or not jugador.conectado:
            return False
        if id_jugador == self._anfitrion_id:
            self._cerrar_por_anfitrion("anfitrion_desconectado")
            return True
        if self._fase != FASE_JUEGO:
            return self.salir(id_jugador, "desconectado")
        self.sesion.desconectar(id_jugador, self._reloj())
        self._cancelar_minijuego(id_jugador)
        self._emitir("jugador_desconectado", id=id_jugador)
        return True

    # Reconexión por token en claro (se compara contra el hash guardado). None si no procede.
    def reconectar_por_token(self, token):
        for jugador in self._por_slot():
            if not jugador.conectado and jugador.coincide_token(token):
                return self._reconectar(jugador)
        return None

    # Reconexión alternativa: mismo nombre y rol (T4 verifica además la IP).
    def reconectar_por_nombre(self, nombre, rol):
        for jugador in self._por_slot():
            if not jugador.conectado and jugador.nombre == nombre and jugador.rol == rol:
                return self._reconectar(jugador)
        return None

    # Da por salidos a quienes llevan más de la gracia sin conexión. Devuelve sus ids.
    def tick(self):
        ahora = self._reloj()
        vencidos = [j.id for j in self._por_slot()
                    if not j.conectado and j.desconectado_desde is not None
                    and ahora - j.desconectado_desde >= self._gracia]
        for id_jugador in vencidos:
            self.salir(id_jugador, "gracia_agotada")
        return vencidos

    # -- Juego --

    # Posición propuesta por el cliente (la validación fina es de otro módulo). Con la
    # bandera "dentro" (interior local) se guarda el estado pero NO la posición, para que el
    # radio de la misión siga contando desde la puerta. False si se descarta.
    def actualizar_posicion(self, id_jugador, x, z, y=0.0, rumbo=0.0, velocidad=0.0, banderas=()):
        jugador = self.sesion.por_id(id_jugador)
        if jugador is None or not jugador.conectado or self._fase == FASE_FIN:
            return False
        if "dentro" in banderas:
            return self.sesion.mover(id_jugador, jugador.x, jugador.z, y, rumbo, velocidad, banderas)
        if not self.sesion.mover(id_jugador, x, z, y, rumbo, velocidad, banderas):
            return False
        if self._fase == FASE_JUEGO:
            self._sistemas[id_jugador].actualizar_posicion(jugador.x, jugador.z)
        return True

    # Intento de abrir el minijuego de la misión. Responde con "ok" o "rechazo_interactuar".
    def interactuar(self, id_jugador):
        sistema = self._sistema_activo(id_jugador)
        if sistema is None:
            return self._rechazar("rechazo_interactuar", id_jugador, "no_disponible")
        if not sistema.puede_interactuar():
            return self._rechazar("rechazo_interactuar", id_jugador, "fuera_de_radio")
        sistema.iniciar_minijuego()
        self._emitir("ok", para=id_jugador, mision=sistema.mision_actual().id)
        lote = self._lotes[id_jugador]
        if lote.terminada():      # mazo vacío: nada que decidir
            self._cerrar_mision(id_jugador)
        return True

    # Decisión sobre una noticia de la mano. Devuelve los deltas aplicados o None si se
    # rechaza (mision/noticia/tipo inválidos, fuera de minijuego...).
    def decidir(self, id_jugador, id_mision, id_noticia, tipo):
        sistema = self._sistema_activo(id_jugador)
        if sistema is None or sistema.estado() != EN_MINIJUEGO:
            return self._rechazar("rechazo_decision", id_jugador, "sin_minijuego")
        if sistema.mision_actual().id != id_mision:
            return self._rechazar("rechazo_decision", id_jugador, "mision_distinta")
        if tipo not in DECISIONES_VALIDAS:
            return self._rechazar("rechazo_decision", id_jugador, "tipo_invalido")
        mano = self._manos.get(id_jugador, [])
        carta = next((c for c in mano if c[0].id == id_noticia), None)
        if carta is None:
            return self._rechazar("rechazo_decision", id_jugador, "noticia_no_esta_en_la_mano")
        nodo, camino = carta
        estado = self.estado_partida
        nodo_stats = estado.arbol_stats.obtener_por_camino(camino)
        if nodo_stats is None:
            return self._rechazar("rechazo_decision", id_jugador, "noticia_sin_stats")
        deltas = dict(nodo_stats.deltas_compartir if tipo == "compartir" else nodo_stats.deltas_reportar)
        estado.aplicar_deltas(deltas)
        mano.remove(carta)
        self._lotes[id_jugador].registrar(tipo, deltas, quedan_noticias=bool(mano))
        self._emitir("ind", valores=estado.indicadores(), autor=id_jugador, deltas=deltas)
        if self._lotes[id_jugador].terminada():
            self._cerrar_mision(id_jugador)
        return deltas

    # El jugador sale del edificio / abandona el minijuego sin terminarlo: la misión vuelve a
    # EN_RADIO y conserva lo ya decidido.
    def salir_edificio(self, id_jugador):
        return self._cancelar_minijuego(id_jugador)

    # -- Cola determinista --

    # Encola una acción. Se procesan juntas en procesar(), ordenadas por (id_jugador, seq).
    def recibir(self, id_jugador, seq, accion, **datos):
        if not isinstance(seq, int) or isinstance(seq, bool):
            return False
        self._entradas.append((id_jugador, seq, len(self._entradas), accion, datos))
        return True

    # Procesa la cola en orden (id_jugador, seq, llegada). Descarta repetidos y atrasados
    # (seq <= último procesado del jugador). Devuelve cuántas acciones se aplicaron.
    def procesar(self):
        entradas = sorted(self._entradas, key=lambda e: (e[0], e[1], e[2]))
        self._entradas = []
        aplicadas = 0
        for id_jugador, seq, _, accion, datos in entradas:
            if seq <= self._ultimo_seq.get(id_jugador, -1):
                continue
            self._ultimo_seq[id_jugador] = seq
            try:
                self._despachar(id_jugador, accion, datos)
                aplicadas += 1
            except (KeyError, TypeError, ValueError) as error:
                self._emitir("error", para=id_jugador, motivo=f"entrada_invalida:{type(error).__name__}")
        return aplicadas

    def _despachar(self, id_jugador, accion, datos):
        if accion == "pos":
            self.actualizar_posicion(id_jugador, datos["x"], datos["z"], datos.get("y", 0.0),
                                     datos.get("rumbo", 0.0), datos.get("velocidad", 0.0),
                                     datos.get("banderas", ()))
        elif accion == "interactuar":
            self.interactuar(id_jugador)
        elif accion == "decision":
            self.decidir(id_jugador, datos["mision"], datos["noticia"], datos["tipo"])
        elif accion == "salir_edificio":
            self.salir_edificio(id_jugador)
        elif accion == "adios":
            self.salir(id_jugador)
        elif accion == "desconectado":
            self.desconectar(id_jugador)
        else:
            raise ValueError(f"Acción desconocida: {accion!r}")

    # -- Internos --

    def _por_slot(self):
        return sorted(self.sesion.jugadores(), key=lambda j: j.id)

    def _exigir_fase(self, fase, accion):
        if self._fase != fase:
            raise ValueError(f"No se puede {accion} en la fase {self._fase!r}; se requiere {fase!r}.")

    def _emitir(self, tipo, para=None, **datos):
        evento = {"t": tipo, "para": para}
        evento.update(datos)
        self._eventos.append(evento)
        return evento

    def _rechazar(self, tipo, id_jugador, motivo):
        self._emitir(tipo, para=id_jugador, motivo=motivo)
        return None if tipo == "rechazo_decision" else False

    def _emitir_sala(self):
        self._emitir(
            "sala",
            jugadores=[{"id": j.id, "nombre": j.nombre, "rol": j.rol, "listo": j.id in self._listos,
                        "conectado": j.conectado, "anfitrion": j.id == self._anfitrion_id}
                       for j in self._por_slot()],
            roles_libres=self.sesion.roles_disponibles(),
        )

    # Roles de quienes siguen en la sala (los de la gracia cuentan) -> sistemas y reserva.
    def _sincronizar_roles(self):
        roles = self.sesion.roles_en_juego()
        self.reserva.fijar_roles_en_juego(roles)
        for sistema in self._sistemas.values():
            sistema.fijar_roles_en_juego(roles)

    # El sistema del jugador solo si la partida está en juego y el jugador está conectado.
    def _sistema_activo(self, id_jugador):
        jugador = self.sesion.por_id(id_jugador)
        if (self._fase != FASE_JUEGO or jugador is None or not jugador.conectado
                or id_jugador not in self._sistemas):
            return None
        return self._sistemas[id_jugador]

    def _cancelar_minijuego(self, id_jugador):
        sistema = self._sistemas.get(id_jugador)
        if sistema is None or sistema.estado() != EN_MINIJUEGO:
            return False
        sistema.cancelar_minijuego()
        return True

    # Roba `n` noticias del mazo compartido evitando las que ya están en otras manos.
    def _robar(self, n):
        mazo = self.estado_partida.mazo
        en_uso = {nodo.id for mano in self._manos.values() for nodo, _ in mano}
        mano = []
        intentos = n * (len(getattr(mazo, "ids_disponibles", ())) + 2)
        while len(mano) < n and intentos > 0:
            intentos -= 1
            carta = mazo.siguiente()
            if carta is None:
                break
            if carta[0].id in en_uso:
                continue
            en_uso.add(carta[0].id)
            mano.append(carta)
        # Mazo demasiado pequeño para no repetir: se completa aceptando repetidas.
        while len(mano) < n:
            carta = mazo.siguiente()
            if carta is None:
                break
            mano.append(carta)
        return mano

    # Asigna la siguiente misión libre al jugador (si está libre), arma su lote y su mano y
    # avisa. Devuelve la Mision o None.
    def _asignar(self, jugador, emitir=True):
        sistema = self._sistemas[jugador.id]
        if sistema.mision_actual() is not None:
            return None
        mision = sistema.asignar(jugador)
        if mision is None:
            return None
        jugador.telefono.notificar(sistema.mensaje_notificacion())
        lote = LoteMision(mision, self._grafo, jugador.rol)
        mano = self._robar(mision.cantidad_noticias)
        if not mano:
            lote.registrar("compartir", None, quedan_noticias=False)   # nada que decidir
        self._lotes[jugador.id] = lote
        self._manos[jugador.id] = mano
        if emitir:
            self._emitir_mision(jugador)
        return mision

    def _emitir_mision(self, jugador):
        sistema = self._sistemas[jugador.id]
        mision = sistema.mision_actual()
        if mision is None:
            return
        lote = self._lotes[jugador.id]
        self._emitir(
            "mision", para=jugador.id, id=mision.id, titulo=mision.titulo, mensaje=mision.mensaje,
            destino=mision.destino,
            mano=[{"id": nodo.id, "texto": nodo.texto} for nodo, _ in self._manos[jugador.id]],
            hechas=lote.decisiones,
        )

    # Da misión a todos los conectados que estén libres, en orden de slot.
    def _repartir_libres(self):
        if self._fase != FASE_JUEGO:
            return
        for jugador in self._por_slot():
            if jugador.conectado:
                self._asignar(jugador)

    def _cerrar_mision(self, id_jugador):
        jugador = self.sesion.por_id(id_jugador)
        sistema = self._sistemas[id_jugador]
        lote = self._lotes.pop(id_jugador)
        self._manos.pop(id_jugador, None)
        resultado = lote.resultado()
        mision = sistema.completar(resultado)
        sistema.terminar()
        self._cierres.append({"mision": mision.id, "jugador": id_jugador, "nombre": jugador.nombre,
                              "decisiones": resultado["decisiones"]})
        siguiente = self._asignar(jugador, emitir=False)
        self._emitir("mision_cerrada", id=mision.id, jugador=id_jugador,
                     siguiente=siguiente.id if siguiente is not None else None,
                     resultado=resultado)
        if siguiente is not None:
            self._emitir_mision(jugador)
        self._comprobar_fin()

    # Fin: nadie con misión activa y ninguna misión libre para los roles presentes.
    # Idempotente.
    def _comprobar_fin(self):
        if self._fase != FASE_JUEGO:
            return
        self._repartir_libres()
        if any(s.mision_actual() is not None for s in self._sistemas.values()):
            return
        if self.reserva.quedan_para(self.sesion.roles_en_juego()):
            return
        self._terminar("completada")

    def _cerrar_por_anfitrion(self, motivo):
        if self._fin_emitido:
            return
        # Sin "fin": si no, el cliente creia que la partida acabo bien y tapaba el aviso de sala cerrada.
        self._fin_emitido = True
        self._fase = FASE_FIN
        self._emitir("sala_cerrada", motivo=motivo)

    def _terminar(self, motivo):
        if self._fin_emitido:
            return
        self._fin_emitido = True
        self._fase = FASE_FIN
        self._emitir("fin", indicadores=self.estado_partida.indicadores(),
                     resumen=self._resumen(), motivo=motivo)

    def _resumen(self):
        hechas = set(self.reserva.completadas())
        return {
            "completadas": self.reserva.completadas(),
            "pendientes": [m.id for m in self._catalogo if m.id not in hechas],
            "cierres": [dict(c) for c in self._cierres],
        }

    def _reconectar(self, jugador):
        self.sesion.reconectar(jugador.id)
        self._emitir("jugador_reconectado", id=jugador.id)
        if self._fase == FASE_JUEGO:
            self._emitir_mision(jugador)
        return jugador
