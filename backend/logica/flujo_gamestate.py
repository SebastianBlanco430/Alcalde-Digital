# FlujoConGameState (modelo puro): envuelve un flujo (FlujoPartida o FlujoConEconomia) y le cuelga el GameState de la
# partida (`game_state`). El reloj del GameState es el número de turno de la sesión, así los impactos se ordenan por
# tiempo de juego. Lo demás se delega con __getattr__.
#
# CONSECUENCIAS (A2d; `consecuencias=True`, main.py pasa economia_config.CONSECUENCIAS): el veredicto de cada misión mueve
# GameState.confianza y al terminar la partida hay un final.
#   - Al crearse deja en el EstadoPartida de la sesión las cartas de misión del mapa (`estado.cartas_mision`,
#     backend/datos/noticias_mision.py): con eso LoteMision fuerza el rumor de la misión como una de las cartas del lote.
#   - completar_mision: tras delegar (pago, turno...) aplica el delta del veredicto al grupo de la misión
#     (confianza_misiones.aplicar_veredicto). Fallar no cambia nada más: la misión se completa y se cobra igual.
#   - Misiones digitales: al cerrarse por señal suman su bono a policía (confianza_misiones.aplicar_bono_digital).
#   - final_partida(): dict de confianza_misiones.evaluar_final con el resumen (pasadas, falladas, confianza por grupo).
# Con `consecuencias=False` (ALCALDE_CONSECUENCIAS=0) no hay cartas de misión, ni veredicto, ni cambios de confianza, y
# final_partida() devuelve None: todo queda como antes. Sin GameState (ALCALDE_GAMESTATE=0) esta clase ni se crea.

import sys

from backend.logica import confianza_misiones
from backend.logica.game_state import GameState


# Tope de misiones digitales que se cierran en cadena tras una asignación (evita un bucle si el catálogo es enorme o raro).
# Lo que no quepa se cierra en la siguiente revisión (completar_mision, revisar_misiones_digitales o volver del terminal).
TOPE_CASCADA = 10


# Ids de los NPC clave (backend/datos/npc_clave.json) para llevar su relación en el GameState. Si el JSON está roto se
# avisa y se sigue sin NPC (el juego no debe caerse por un dato): relacion() fallará solo para ellos.
def _ids_npc_clave():
    try:
        from backend.datos.npc_clave_loader import ids_npc
        return ids_npc()
    except Exception as error:
        print(f"[gamestate] NPC clave no cargados: {error}", file=sys.stderr)
        return []


class FlujoConGameState:

    def __init__(self, flujo, game_state=None, consecuencias=True):
        self._flujo = flujo
        self.game_state = game_state if game_state is not None else GameState(
            npcs=_ids_npc_clave(), reloj=lambda: flujo.sesion.numero_turno())
        # Último veredicto aplicado, para el aviso de la vista: {"mision", "veredicto", "grupo", "delta"}; None si la
        # última misión cerrada no tuvo veredicto. Los bonos digitales también lo dejan (grupo policía).
        self.ultimo_veredicto = None
        self._tabla = None                  # {grupo: DeltasGrupo} del catálogo; None = consecuencias apagadas
        if consecuencias:
            self._activar_consecuencias()

    # Calcula la tabla de deltas del mapa y reparte las cartas de misión. Un flujo sin catálogo (los falsos de las
    # pruebas) deja las consecuencias apagadas; un catálogo cuyas cartas no se pueden construir avisa y sigue sin cartas.
    def _activar_consecuencias(self):
        leer_catalogo = getattr(self._flujo, "catalogo_misiones", None)
        if leer_catalogo is None:
            return
        catalogo = leer_catalogo()
        self._tabla = confianza_misiones.tabla_deltas(catalogo)
        estado = getattr(getattr(self._flujo, "sesion", None), "estado_partida", None)
        if estado is None or not hasattr(estado, "forzar_noticia"):
            return
        try:
            from backend.datos.noticias_mision import construir_cartas_mision
            estado.cartas_mision = construir_cartas_mision(catalogo)
        except ValueError as error:
            print(f"[gamestate] cartas de misión no construidas: {error}", file=sys.stderr)

    # True si el veredicto de las misiones mueve la confianza en esta partida.
    def consecuencias_activas(self):
        return self._tabla is not None

    # Cierre inmediato: tras asignar la primera misión (por si su señal ya está) se revisan las digitales. Devuelve la misión
    # activa al terminar (la asignada, o la que quedó tras la cascada; None si ya no queda ninguna).
    def iniciar(self):
        asignada = self._flujo.iniciar()
        if self._cerrar_digitales_cumplidas():
            return self._flujo.mision_actual()
        return asignada

    # Delega (la misión se completa y se cobra SIEMPRE, también si se falló), aplica el veredicto a la confianza y revisa:
    # la misión que se asigna a continuación puede ser digital con la señal ya cumplida.
    def completar_mision(self, resultado):
        leer_mision = getattr(self._flujo, "mision_actual", None)
        mision = leer_mision() if leer_mision is not None else None      # antes de delegar: completar pasa el turno
        activo = self._flujo.completar_mision(resultado)
        self._aplicar_veredicto(mision, resultado)
        if self._cerrar_digitales_cumplidas():
            return self._flujo.jugador_activo()      # la cascada pasó el turno: el activo ya es otro
        return activo

    def _aplicar_veredicto(self, mision, resultado):
        self.ultimo_veredicto = None
        if self._tabla is None or mision is None or self.game_state is None:
            return
        decision = resultado.get("decision_mision") if isinstance(resultado, dict) else None
        veredicto = confianza_misiones.veredicto(mision, decision)
        delta = confianza_misiones.aplicar_veredicto(self.game_state, self._tabla, mision, veredicto)
        if delta is not None:
            self.ultimo_veredicto = {"mision": mision.id, "veredicto": veredicto, "grupo": mision.grupo, "delta": delta}

    # Misiones digitales: revisa la señal con el GameState de esta partida. True si cerró la misión activa (y, en cadena,
    # las digitales siguientes ya cumplidas).
    def revisar_misiones_digitales(self):
        return self._cerrar_digitales_cumplidas() > 0

    # Cierra la misión activa mientras sea digital y su señal esté cumplida, hasta TOPE_CASCADA veces. El cobro lo hace
    # cada revisar_misiones_digitales de la capa de economía (una vez por misión cerrada); aquí se suma el bono de
    # confianza de cada una. Devuelve cuántas cerró.
    def _cerrar_digitales_cumplidas(self):
        revisar = getattr(self._flujo, "revisar_misiones_digitales", None)
        if self.game_state is None or revisar is None:       # sin GameState o con un flujo sin misiones digitales
            return 0
        cerradas = 0
        while cerradas < TOPE_CASCADA:
            mision = self._flujo.mision_actual()             # antes de cerrar: cerrar asigna la siguiente
            if not revisar(self.game_state):
                break
            cerradas += 1
            self._aplicar_bono_digital(mision)
        return cerradas

    def _aplicar_bono_digital(self, mision):
        if self._tabla is None or mision is None:
            return
        delta = confianza_misiones.aplicar_bono_digital(self.game_state, mision)
        self.ultimo_veredicto = {
            "mision": mision.id, "veredicto": confianza_misiones.veredicto_digital(mision, self.game_state),
            "grupo": confianza_misiones.GRUPO_BONO_DIGITAL, "delta": delta}

    # Final de la partida con su resumen (ver confianza_misiones.evaluar_final): {"final", "indice", "confianza",
    # "pasadas", "falladas", "grupo_critico"}. Se puede pedir en cualquier momento (resume lo jugado hasta ahora); la vista
    # lo pide cuando partida_terminada(). None con las consecuencias apagadas. Textos: backend/datos/finales_textos.py.
    def final_partida(self):
        if self._tabla is None or self.game_state is None:
            return None
        pasadas = getattr(self._flujo, "misiones_pasadas", lambda: [])()
        falladas = getattr(self._flujo, "misiones_falladas", lambda: [])()
        return confianza_misiones.evaluar_final(self.game_state.confianzas(), len(pasadas), len(falladas))

    # Guardado: sustituye el GameState por el de `datos` (GameState.a_dict), con el reloj de esta partida. ValueError
    # (sin cambiar nada) si los datos no son válidos.
    def restaurar_game_state(self, datos):
        flujo = self._flujo
        self.game_state = GameState.desde_dict(datos, reloj=lambda: flujo.sesion.numero_turno())
        self.ultimo_veredicto = None

    def __getattr__(self, nombre):
        if nombre.startswith("__") or nombre in ("_flujo", "game_state", "_tabla", "ultimo_veredicto"):
            raise AttributeError(nombre)
        return getattr(self._flujo, nombre)
