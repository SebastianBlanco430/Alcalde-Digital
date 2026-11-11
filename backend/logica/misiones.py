# Misiones (modelo puro). Una misión lleva a un jugador a un lugar del mapa,
# donde juega un lote de noticias. SistemaMisiones es la máquina de estados de
# UNA misión activa a la vez (hot-seat: la del jugador del turno):
#
#   SIN_MISION -asignar-> NOTIFICADA -actualizar_posicion-> EN_RUTA
#   EN_RUTA <-> EN_RADIO (con histéresis)
#   EN_RADIO -iniciar_minijuego-> EN_MINIJUEGO -completar-> COMPLETADA
#   EN_MINIJUEGO -cancelar_minijuego-> EN_RADIO (revierte si no se pudo abrir el minijuego)
#   COMPLETADA -terminar-> SIN_MISION (libera el sistema para el siguiente jugador)
#
# El mapa (necesita `coordenada(lugar)`) y el catálogo se INYECTAN; así los
# tests usan versiones falsas. Toda transición inválida lanza ValueError.
#
# Mundo 3D: `punto_interaccion(lugar) -> (x, z)` es opcional; si se da, "llegar" se mide
# contra él (la PUERTA del edificio) en vez de contra el centro de la plaza.

import copy
import math
from dataclasses import dataclass

from backend.logica import confianza_misiones, misiones_digitales

# m: «llegué» = a menos de esto de la PUERTA del destino. Única fuente: main.py, el modo online y el
# servidor la importan; el default del sistema coincide con el juego real.
RADIO_INTERACCION = 2.0

SIN_MISION = "sin_mision"
NOTIFICADA = "notificada"
EN_RUTA = "en_ruta"
EN_RADIO = "en_radio"
EN_MINIJUEGO = "en_minijuego"
COMPLETADA = "completada"
ESTADOS = (SIN_MISION, NOTIFICADA, EN_RUTA, EN_RADIO, EN_MINIJUEGO, COMPLETADA)


# Tipo de misión (cómo se juega) y dificultad (por TEMA del rumor, no por distancia). La dificultad multiplica el pago
# (ver docs/DISENO.md §10). «verificar» se juega en el lugar (lote de noticias); «parkour» e «investigacion» se completan
# por SEÑAL del GameState (backend/logica/misiones_digitales.py), solo en la partida de solo.
TIPOS_MISION = ("verificar", "parkour", "investigacion")
DIFICULTADES = ("facil", "media", "dificil")
MULTIPLICADOR_DIFICULTAD = {"facil": 1, "media": 1.5, "dificil": 2}

# Grupos de GameState.confianza a los que puede afectar una misión (veredicto, A2d). Ver docs/DISENO.md §10.
GRUPOS_CONFIANZA = ("policia", "ciudadanos", "instituciones")


# rol None = misión genérica (sirve a cualquier rol). destino = nombre de lugar.
@dataclass(frozen=True)
class Mision:
    id: str
    rol: str | None
    titulo: str
    mensaje: str
    destino: str
    cantidad_noticias: int = 2     # noticias que se deciden en el lote (LoteMision, mano coop, progreso "n/N")
    pago: int = 0           # R$ que cobra quien la completa (economía); 0 = no paga
    tipo: str = "verificar"     # uno de TIPOS_MISION
    dificultad: str = "facil"   # uno de DIFICULTADES; multiplica el pago
    objetivo: str = ""          # id del nivel de parkour o del caso; obligatorio en esos tipos, vacío en «verificar»
    # Veredicto (A2d): solo en «verificar», que lo EXIGE completo. El rumor (solo la afirmación, será la carta de misión) es
    # verdadero o falso; la pista es lo que se ve al llegar; el grupo es el de GameState.confianza al que afecta. Las digitales
    # NO llevan es_verdadera/rumor/pista; su grupo es "policia" por convención (o vacío).
    es_verdadera: bool | None = None
    rumor: str = ""
    pista: str = ""
    grupo: str = ""             # uno de GRUPOS_CONFIANZA

    def __post_init__(self):
        if self.tipo not in TIPOS_MISION:
            raise ValueError(f"Tipo de misión desconocido en {self.id!r}: {self.tipo!r}; válidos: {TIPOS_MISION}.")
        if self.dificultad not in DIFICULTADES:
            raise ValueError(f"Dificultad de misión desconocida en {self.id!r}: {self.dificultad!r}; válidas: {DIFICULTADES}.")
        if self.tipo == "verificar" and self.objetivo:
            raise ValueError(f"La misión de verificar {self.id!r} no lleva objetivo (tiene {self.objetivo!r}).")
        if self.tipo != "verificar" and not self.objetivo.strip():
            raise ValueError(f"La misión {self.id!r} de tipo {self.tipo!r} necesita un objetivo (id del nivel o del caso).")
        if self.grupo and self.grupo not in GRUPOS_CONFIANZA:
            raise ValueError(f"Grupo de confianza desconocido (grupo) en {self.id!r}: {self.grupo!r}; válidos: {GRUPOS_CONFIANZA}.")
        if self.tipo == "verificar":
            if not isinstance(self.es_verdadera, bool):
                raise ValueError(f"La misión de verificar {self.id!r} necesita es_verdadera (True o False), no {self.es_verdadera!r}.")
            if not self.rumor.strip():
                raise ValueError(f"La misión de verificar {self.id!r} necesita un rumor (la afirmación a verificar).")
            if not self.pista.strip():
                raise ValueError(f"La misión de verificar {self.id!r} necesita una pista (lo que se ve al llegar).")
            if not self.grupo:
                raise ValueError(f"La misión de verificar {self.id!r} necesita un grupo de confianza: {GRUPOS_CONFIANZA}.")
        else:
            if self.es_verdadera is not None:
                raise ValueError(f"La misión digital {self.id!r} no lleva es_verdadera (tiene {self.es_verdadera!r}).")
            if self.rumor or self.pista:
                raise ValueError(f"La misión digital {self.id!r} no lleva rumor ni pista.")


class SistemaMisiones:

    # Valida el catálogo: ids únicos y destinos con coordenada en el mapa
    # (ValueError si no).
    def __init__(self, mapa, catalogo, radio_interaccion=RADIO_INTERACCION, histeresis=0.3,
                 punto_interaccion=None):
        self._mapa = mapa
        self._punto_interaccion = punto_interaccion if punto_interaccion is not None else mapa.coordenada
        self._catalogo = list(catalogo)
        self.radio_interaccion = radio_interaccion
        self.histeresis = histeresis

        ids = set()
        for mision in self._catalogo:
            if mision.id in ids:
                raise ValueError(f"Id de misión repetido: {mision.id!r}")
            ids.add(mision.id)
            self._punto_interaccion(mision.destino)  # lanza ValueError si no existe

        self._estado = SIN_MISION
        self._mision = None
        self._completadas = []
        # Veredicto (A2d) de las misiones completadas: {id: "pasada" | "fallada"}. Fallar también es completar. Las que
        # se cerraron sin veredicto (lote sin carta de misión) no aparecen.
        self._veredictos = {}
        self._resultado = None
        self._roles_en_juego = None

    # Roles de los jugadores en juego (iterable) o None = desconocidos. Con roles conocidos,
    # las misiones de roles que NADIE juega (p. ej. influencer con 2 jugadores) pasan a ser
    # asignables a cualquiera, después de las propias y las genéricas; así la partida no
    # termina antes de tiempo ni deja misiones inalcanzables.
    def fijar_roles_en_juego(self, roles):
        self._roles_en_juego = None if roles is None else frozenset(roles)

    # -- Consulta --

    def estado(self):
        return self._estado

    def mision_actual(self):
        return self._mision

    # Ids de misiones completadas, en orden (copia).
    def completadas(self):
        return list(self._completadas)

    # El catálogo con el que se creó el sistema, en orden (copia).
    def catalogo(self):
        return list(self._catalogo)

    # Ids de las misiones completadas con veredicto «pasada» / «fallada», en el orden en que se completaron (copias).
    def pasadas(self):
        return [i for i in self._completadas if self._veredictos.get(i) == confianza_misiones.PASADA]

    def falladas(self):
        return [i for i in self._completadas if self._veredictos.get(i) == confianza_misiones.FALLADA]

    # "pasada" | "fallada" de una misión completada, o None si no se completó o se cerró sin veredicto.
    def veredicto_de(self, id_mision):
        return self._veredictos.get(id_mision)

    # Resultado de la última misión completada (se conserva tras terminar()).
    def resultado_ultimo(self):
        return self._resultado

    # Texto para el teléfono de la misión actual, o None si no hay.
    def mensaje_notificacion(self):
        return self._mision.mensaje if self._mision is not None else None

    # Solo las misiones de «verificar» se abren con E en el lugar; las digitales se completan por señal
    # (completar_por_senal), así que estar en el radio de su destino no abre nada.
    def puede_interactuar(self):
        return self._estado == EN_RADIO and self._mision.tipo == "verificar"

    # True si queda alguna misión sin completar del rol o genérica.
    def hay_misiones_pendientes(self, rol):
        return self._buscar_pendiente(rol) is not None

    # -- Transiciones --

    # Primera misión no completada del rol; si no hay, la primera genérica; si no, la primera
    # de un rol que nadie juega (ver fijar_roles_en_juego); si tampoco, None (queda SIN_MISION). ValueError si ya hay una misión activa.
    def asignar(self, jugador):
        if self._estado != SIN_MISION:
            raise ValueError(
                f"Ya hay una misión activa (estado {self._estado!r}); termínala antes de asignar otra."
            )
        mision = self._buscar_pendiente(jugador.rol)
        if mision is None:
            return None
        self._mision = mision
        self._estado = NOTIFICADA
        return mision

    # Actualiza el estado según la distancia XZ al destino. NOTIFICADA pasa a
    # EN_RUTA en la primera actualización y, en esa misma llamada, se evalúa el
    # radio (así no hace falta una segunda actualización si ya está cerca).
    # Histéresis: entra a EN_RADIO a <= radio; sale a > radio + histéresis.
    # En los demás estados no hace nada.
    def actualizar_posicion(self, x, z):
        if self._estado == NOTIFICADA:
            self._estado = EN_RUTA
        if self._estado not in (EN_RUTA, EN_RADIO):
            return

        cx, cz = self._punto_interaccion(self._mision.destino)
        distancia = math.hypot(x - cx, z - cz)
        if self._estado == EN_RUTA and distancia <= self.radio_interaccion:
            self._estado = EN_RADIO
        elif self._estado == EN_RADIO and distancia > self.radio_interaccion + self.histeresis:
            self._estado = EN_RUTA

    def iniciar_minijuego(self):
        self._exigir(EN_RADIO, "iniciar el minijuego")
        self._estado = EN_MINIJUEGO

    # Revierte iniciar_minijuego (EN_MINIJUEGO -> EN_RADIO) cuando el minijuego no llegó a
    # abrirse; la misión no cuenta como completada y se puede volver a intentar.
    def cancelar_minijuego(self):
        self._exigir(EN_MINIJUEGO, "cancelar el minijuego")
        self._estado = EN_RADIO

    # Guarda el resultado, registra la misión como completada y la devuelve. Veredicto (A2d): si el resultado trae
    # "decision_mision" (la decisión sobre la carta de misión, la pone LoteMision), se recuerda si la misión quedó pasada
    # o fallada (confianza_misiones.veredicto). Fallar NO impide completar: cuenta igual y cobra igual.
    def completar(self, resultado):
        self._exigir(EN_MINIJUEGO, "completar la misión")
        self._resultado = copy.deepcopy(resultado)
        decision = resultado.get("decision_mision") if isinstance(resultado, dict) else None
        self._anotar_veredicto(confianza_misiones.veredicto(self._mision, decision))
        self._completadas.append(self._mision.id)
        self._estado = COMPLETADA
        return self._mision

    # Misiones digitales: si la misión activa NO es de verificar y su señal del GameState se cumplió, la completa desde
    # cualquier estado activo (NOTIFICADA, EN_RUTA o EN_RADIO; no pasa por el minijuego) y la devuelve; si no, None sin
    # tocar nada. El resultado no trae deltas (no hubo noticias). El llamador cierra con terminar().
    def completar_por_senal(self, game_state):
        mision = self._mision
        if mision is None or mision.tipo == "verificar" or self._estado not in (NOTIFICADA, EN_RUTA, EN_RADIO):
            return None
        if not misiones_digitales.cumplida(mision, game_state):
            return None
        self._resultado = {"deltas": {}}
        self._anotar_veredicto(confianza_misiones.veredicto_digital(mision, game_state))
        self._completadas.append(mision.id)
        self._estado = COMPLETADA
        return mision

    def _anotar_veredicto(self, veredicto):
        if veredicto is not None:
            self._veredictos[self._mision.id] = veredicto

    # COMPLETADA -> SIN_MISION; el resultado_ultimo se conserva.
    def terminar(self):
        self._exigir(COMPLETADA, "terminar la misión")
        self._mision = None
        self._estado = SIN_MISION

    # -- Serialización (JSON) --
    # El resultado debe ser JSON-serializable (p. ej. dict de deltas).

    def a_dict(self):
        return {
            "estado": self._estado,
            "mision_actual": self._mision.id if self._mision is not None else None,
            "completadas": list(self._completadas),
            "veredictos": dict(self._veredictos),
            "resultado": copy.deepcopy(self._resultado),
            "radio_interaccion": self.radio_interaccion,
            "histeresis": self.histeresis,
        }

    # ValueError si el estado no existe o es incoherente con la misión guardada (un estado
    # activo exige misión; SIN_MISION no puede tener una). Los guardados antiguos sin
    # radio_interaccion / histeresis usan los valores por defecto.
    @classmethod
    def desde_dict(cls, datos, mapa, catalogo, punto_interaccion=None):
        estado = datos["estado"]
        if estado not in ESTADOS:
            raise ValueError(f"Estado de misión desconocido en los datos guardados: {estado!r}")
        id_actual = datos["mision_actual"]
        if (estado == SIN_MISION) != (id_actual is None):
            raise ValueError(
                f"Estado {estado!r} incoherente con la misión guardada {id_actual!r}."
            )
        extras = {k: datos[k] for k in ("radio_interaccion", "histeresis") if k in datos}
        sistema = cls(mapa, catalogo, punto_interaccion=punto_interaccion, **extras)
        por_id = {m.id: m for m in sistema._catalogo}
        if id_actual is not None and id_actual not in por_id:
            raise ValueError(f"Misión desconocida en los datos guardados: {id_actual!r}")
        sistema._estado = estado
        sistema._mision = por_id[id_actual] if id_actual is not None else None
        sistema._completadas = list(datos["completadas"])
        # Los guardados anteriores a A2d no traen veredictos: quedan sin ninguno.
        for id_mision, veredicto in dict(datos.get("veredictos") or {}).items():
            if veredicto not in confianza_misiones.VEREDICTOS:
                raise ValueError(f"Veredicto desconocido en los datos guardados para {id_mision!r}: {veredicto!r}")
            sistema._veredictos[id_mision] = veredicto
        sistema._resultado = copy.deepcopy(datos["resultado"])
        return sistema

    # -- Internos --

    def _exigir(self, estado_requerido, accion):
        if self._estado != estado_requerido:
            raise ValueError(
                f"No se puede {accion} en el estado {self._estado!r}; se requiere {estado_requerido!r}."
            )

    def _buscar_pendiente(self, rol):
        for mision in self._catalogo:
            if mision.rol == rol and mision.id not in self._completadas:
                return mision
        for mision in self._catalogo:
            if mision.rol is None and mision.id not in self._completadas:
                return mision
        if self._roles_en_juego is not None:
            for mision in self._catalogo:
                if (mision.rol is not None and mision.rol not in self._roles_en_juego
                        and mision.id not in self._completadas):
                    return mision
        return None
