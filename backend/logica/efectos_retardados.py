# Efectos retardados (modelo puro, serializable, sin ursina): lo que el jugador decide HOY tiene consecuencias MAÑANA.
# Una cola de efectos programados sobre el reloj de la partida (backend/logica/reloj_partida.py): cada efecto lleva la hora
# absoluta de juego en la que vence, los cambios que produce y un MENSAJE de causa-efecto para el jugador
# («Ayer compartiste X sin verificar: hoy circula un rumor»). Así el juego enseña que en la red nada es inmediato ni gratis.
#
#   cola = ColaEfectos()
#   cola.programar(en_horas_abs, efecto)   -> id del efecto en la cola (int)
#   cola.vencidos(ahora)                   -> [(en_horas_abs, Efecto)] que ya vencieron, en orden; SALEN de la cola
#   cola.pendientes()                      -> [(en_horas_abs, Efecto)] sin sacar nada (HUD / depuración)
#   cola.a_dict() / ColaEfectos.desde_dict(datos)
#
#   aplicar(efecto, estado_partida, game_state=None, ahora=None) -> aviso (dict) para el HUD
#   consecuencia_de_mision(mision, resultado, ahora)             -> (en_horas_abs, Efecto) | None
#
# EFECTO. Efecto(clave, mensaje, deltas, confianza, origen):
#   clave      nombre corto de la consecuencia («rebrote», «verificado»...); el evento del GameState es «retardado:<clave>»
#   mensaje    texto de causa-efecto que ve el jugador cuando el efecto se aplica
#   deltas     {indicador: delta} sobre los indicadores de la ciudad (EstadoPartida.aplicar_deltas; recorta a 0-100)
#   confianza  {grupo: delta} sobre la confianza por grupo del GameState; se ignora si la partida no tiene GameState
#   origen     de dónde viene («mision:<id>», «aislamiento»...): queda en el ArbolImpactos
#
# TABLA DE CONSECUENCIAS DE UNA MISIÓN (la regla vive en backend/datos/noticias_mision.py, junto a PLANTILLA_DELTAS; aquí
# solo se lee). Decide la DECISIÓN sobre la carta de misión (el rumor), según si el rumor era verdadero y su dificultad:
#   compartir un rumor FALSO (sin verificar)  -> «rebrote»: sube la desinformación y baja la confianza del grupo
#   reportar un rumor FALSO (verificar a tiempo) -> «verificado»: sube la confianza (indicador y grupo)
#   compartir un rumor VERDADERO              -> «buena_fuente»: sube un poco la convivencia
#   reportar un rumor VERDADERO (censurar)    -> «falsa_alarma»: baja un poco la confianza
#   además, si la misión es de DATOS PERSONALES (noticias_mision.MISIONES_DATOS_PERSONALES) y se compartió el rumor falso
#   («exponer datos de un amigo»)             -> «datos_expuestos»: baja la convivencia, a 48 h
# El retardo es RETARDO_HORAS por dificultad: facil 24 h, media 36 h, dificil 48 h (entre 1 y 2 días de juego).
# Sin carta de misión (en línea, sin consecuencias) la regla usa los deltas del lote: si la desinformación SUBIÓ en el lote
# es un «rebrote» proporcional; si BAJÓ, un «verificado» proporcional.
#
# BANDERA. EFECTOS_RETARDADOS = False (o ALCALDE_EFECTOS_RETARDADOS=0) apaga la cola en el flujo (flujo_tiempo.py): no se
# programa ni se aplica nada. Los efectos ya guardados se conservan en el guardado pero no se ejecutan.

import math
import os
from collections import namedtuple

from backend.logica.estado_partida import NOMBRES_INDICADORES

EFECTOS_RETARDADOS = True

GRUPOS = ("policia", "ciudadanos", "instituciones")     # los de GameState.confianza
PREFIJO_EVENTO = "retardado:"
MAX_EFECTOS = 256                                       # tope de la cola (un guardado dañado no la infla)

_VERSION = 1
_SI = ("1", "true", "si", "sí", "on")
_NO = ("0", "false", "no", "off")

Efecto = namedtuple("Efecto", "clave mensaje deltas confianza origen")


def activo():
    """¿Están encendidos los efectos retardados? ALCALDE_EFECTOS_RETARDADOS=1/0 manda sobre la constante."""
    valor = os.environ.get("ALCALDE_EFECTOS_RETARDADOS", "").strip().lower()
    if valor in _SI:
        return True
    if valor in _NO:
        return False
    return bool(EFECTOS_RETARDADOS)


def _numero(valor, nombre):
    if isinstance(valor, bool) or not isinstance(valor, (int, float)) or not math.isfinite(valor):
        raise ValueError(f"{nombre} inválido: {valor!r}; se esperaba un número finito.")
    return float(valor)


def _tabla(crudo, validas, nombre):
    tabla = {}
    for clave, delta in dict(crudo or {}).items():
        if clave not in validas:
            raise ValueError(f"{nombre} desconocido en un efecto retardado: {clave!r}; válidos: {validas}.")
        delta = _numero(delta, f"delta de {clave}")
        if delta:
            tabla[clave] = delta
    return tabla


def crear_efecto(clave, mensaje, deltas=None, confianza=None, origen=""):
    """Efecto validado (ValueError si algo no cuadra). `deltas`: indicadores de la ciudad; `confianza`: grupos del GameState."""
    if not isinstance(clave, str) or not clave.strip():
        raise ValueError("Un efecto retardado necesita una clave (texto no vacío).")
    if not isinstance(mensaje, str) or not mensaje.strip():
        raise ValueError(f"El efecto {clave!r} necesita un mensaje de causa-efecto para el jugador.")
    return Efecto(clave.strip(), mensaje.strip(), _tabla(deltas, NOMBRES_INDICADORES, "Indicador"),
                  _tabla(confianza, GRUPOS, "Grupo"), str(origen or ""))


def efecto_a_dict(efecto):
    return {"clave": efecto.clave, "mensaje": efecto.mensaje, "deltas": dict(efecto.deltas),
            "confianza": dict(efecto.confianza), "origen": efecto.origen}


def efecto_desde_dict(datos):
    return crear_efecto(datos["clave"], datos["mensaje"], datos.get("deltas"), datos.get("confianza"),
                        datos.get("origen", ""))


class ColaEfectos:

    def __init__(self):
        self._pendientes = []           # [(en_horas_abs, secuencia, Efecto)], sin ordenar
        self._secuencia = 0

    # Programa `efecto` para la hora absoluta de juego `en_horas_abs` (reloj.tiempo_absoluto() + retardo). Devuelve su
    # id en la cola. ValueError si la hora no es válida, el efecto no es un Efecto o la cola está llena.
    def programar(self, en_horas_abs, efecto):
        en_horas_abs = _numero(en_horas_abs, "en_horas_abs")
        if not isinstance(efecto, Efecto):
            raise ValueError("Se esperaba un Efecto (crear_efecto).")
        if len(self._pendientes) >= MAX_EFECTOS:
            raise ValueError(f"La cola de efectos retardados está llena ({MAX_EFECTOS}).")
        identificador = self._secuencia
        self._secuencia += 1
        self._pendientes.append((en_horas_abs, identificador, efecto))
        return identificador

    # Saca y devuelve los efectos con hora <= `ahora`, por hora y, a igual hora, en el orden en que se programaron.
    def vencidos(self, ahora):
        ahora = _numero(ahora, "ahora") if ahora != math.inf else math.inf
        listos = sorted((p for p in self._pendientes if p[0] <= ahora), key=lambda p: (p[0], p[1]))
        if listos:
            self._pendientes = [p for p in self._pendientes if p[0] > ahora]
        return [(hora, efecto) for hora, _sec, efecto in listos]

    def pendientes(self):
        return [(hora, efecto) for hora, _sec, efecto in sorted(self._pendientes, key=lambda p: (p[0], p[1]))]

    def cancelar(self, identificador):
        antes = len(self._pendientes)
        self._pendientes = [p for p in self._pendientes if p[1] != identificador]
        return len(self._pendientes) != antes

    def __len__(self):
        return len(self._pendientes)

    # -- Serialización (JSON) --

    def a_dict(self):
        return {"version": _VERSION, "secuencia": self._secuencia,
                "pendientes": [{"en": hora, "id": sec, "efecto": efecto_a_dict(efecto)}
                               for hora, sec, efecto in sorted(self._pendientes, key=lambda p: (p[0], p[1]))]}

    # ValueError si los datos no son válidos (quien restaura decide qué hacer: flujo_tiempo deja la cola vacía).
    @classmethod
    def desde_dict(cls, datos):
        if not isinstance(datos, dict) or datos.get("version") != _VERSION:
            raise ValueError("Cola de efectos retardados con formato desconocido.")
        crudos = datos.get("pendientes")
        if not isinstance(crudos, list) or len(crudos) > MAX_EFECTOS:
            raise ValueError("Cola de efectos retardados dañada.")
        cola = cls()
        try:
            for item in crudos:
                identificador = item["id"]
                if isinstance(identificador, bool) or not isinstance(identificador, int) or identificador < 0:
                    raise ValueError(f"id de efecto inválido: {identificador!r}.")
                cola._pendientes.append((_numero(item["en"], "en"), identificador, efecto_desde_dict(item["efecto"])))
        except (KeyError, TypeError) as error:
            raise ValueError(f"Cola de efectos retardados dañada: {type(error).__name__}: {error}") from error
        siguiente = max((p[1] for p in cola._pendientes), default=-1) + 1
        secuencia = datos.get("secuencia", siguiente)
        cola._secuencia = max(siguiente, secuencia if isinstance(secuencia, int) and not isinstance(secuencia, bool) else 0)
        return cola


# -- Aplicar ----------------------------------------------------------------------------------------------------------

# Aplica `efecto`: los deltas a los indicadores de `estado_partida` (recortados a 0-100) y, si hay `game_state`, la
# confianza por grupo con GameState.aplicar_evento(tipo «retardado:<clave>»), que deja el rastro en el ArbolImpactos.
# Devuelve el AVISO para el HUD (JSON-serializable):
#   {"clave", "mensaje", "deltas": lo que de verdad cambió cada indicador, "confianza": ídem por grupo, "hora": ahora}
def aplicar(efecto, estado_partida, game_state=None, ahora=None):
    cambios = {}
    if efecto.deltas and estado_partida is not None:
        antes = estado_partida.indicadores()
        estado_partida.aplicar_deltas(efecto.deltas)
        despues = estado_partida.indicadores()
        cambios = {n: round(despues[n] - antes[n], 2) for n in efecto.deltas if despues[n] != antes[n]}
    confianza = {}
    if efecto.confianza and game_state is not None:
        from backend.logica.game_state import PESO_INVESTIGACION
        antes = game_state.confianzas()
        # aplicar_evento calcula el delta como 0,5 * investigacion: se le pasa delta / 0,5 para que sea exacto.
        game_state.aplicar_evento(
            PREFIJO_EVENTO + efecto.clave,
            efectos={g: {"investigacion": d / PESO_INVESTIGACION} for g, d in efecto.confianza.items()},
            origen=efecto.origen or None, datos={"mensaje": efecto.mensaje, "hora_juego": ahora})
        despues = game_state.confianzas()
        confianza = {g: round(despues[g] - antes[g], 2) for g in efecto.confianza if despues[g] != antes[g]}
    return {"clave": efecto.clave, "mensaje": efecto.mensaje, "deltas": cambios, "confianza": confianza, "hora": ahora}


# -- Regla: consecuencia diferida de una misión ---------------------------------------------------------------------------

def _recortar_texto(texto, largo=70):
    texto = " ".join(str(texto or "").split()).rstrip(".")
    return texto if len(texto) <= largo else texto[:largo - 1].rstrip() + "…"


def _cuando(horas):
    return "Ayer" if horas <= 30 else "Hace dos días"


# (en_horas_abs, Efecto) de la consecuencia diferida de cerrar `mision` con `resultado` (el dict de LoteMision.resultado)
# a la hora absoluta `ahora`; None si la decisión no deja consecuencia (misión digital, lote sin decisiones...).
# Determinista: misma misión + misma decisión + misma hora = mismo efecto.
def consecuencia_de_mision(mision, resultado, ahora):
    from backend.datos import noticias_mision as tabla
    if mision is None or not isinstance(resultado, dict):
        return None
    origen = f"mision:{getattr(mision, 'id', '?')}"
    grupo = getattr(mision, "grupo", "") if getattr(mision, "grupo", "") in GRUPOS else None
    decision = resultado.get("decision_mision")
    es_verdadera = getattr(mision, "es_verdadera", None)
    if decision in ("compartir", "reportar") and isinstance(es_verdadera, bool):
        dificultad = getattr(mision, "dificultad", "facil")
        retardo = tabla.RETARDO_HORAS.get(dificultad, tabla.RETARDO_HORAS["facil"])
        de_datos = getattr(mision, "id", None) in tabla.MISIONES_DATOS_PERSONALES
        if de_datos and decision == "compartir" and not es_verdadera:
            clave, retardo = "datos_expuestos", tabla.RETARDO_DATOS_HORAS
        else:
            clave = tabla.CLAVE_RETARDO[(es_verdadera, decision)]
        deltas, delta_grupo = tabla.consecuencia_retardada(clave, dificultad)
        mensaje = tabla.MENSAJES_RETARDO[clave].format(
            cuando=_cuando(retardo), rumor=_recortar_texto(getattr(mision, "rumor", "") or getattr(mision, "titulo", "")))
        confianza = {grupo: delta_grupo} if grupo is not None and delta_grupo else {}
        return ahora + retardo, crear_efecto(clave, mensaje, deltas, confianza, origen)
    # Sin carta de misión: se mira qué le hizo el lote a la desinformación.
    deltas_lote = resultado.get("deltas") if isinstance(resultado.get("deltas"), dict) else {}
    desinformacion = deltas_lote.get("desinformacion", 0)
    if isinstance(desinformacion, bool) or not isinstance(desinformacion, (int, float)) or not desinformacion:
        return None
    clave = "rebrote" if desinformacion > 0 else "verificado"
    fuerza = min(1.0, abs(desinformacion) / tabla.DELTA_LOTE_PLENO)
    deltas, _delta_grupo = tabla.consecuencia_retardada(clave, "media")
    deltas = {n: round(d * fuerza, 2) for n, d in deltas.items()}
    retardo = tabla.RETARDO_HORAS["facil"]
    mensaje = tabla.MENSAJES_RETARDO[clave].format(
        cuando=_cuando(retardo), rumor=_recortar_texto(getattr(mision, "titulo", "") or "lo que decidiste"))
    return ahora + retardo, crear_efecto(clave, mensaje, deltas, {}, origen)
