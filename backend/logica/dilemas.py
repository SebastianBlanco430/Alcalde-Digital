# Dilemas jugables (modelo puro, serializable, sin ursina). Conecta backend/datos/dilemas_extra.json (9 dilemas de uso
# consciente de redes, SIN veredicto único) con el reloj de la partida y los efectos retardados. Punto 7 del plan del dueño:
# que el juego enseñe. Lo que el jugador decide HOY se ve un poco hoy y se cobra (o se agradece) en uno o dos días.
#
# PIEZAS (todo ADITIVO: no se reescribe ninguna clase que ya funcionaba)
#   GestorDilemas        estado puro: cuándo se ofrece cada dilema, cuál, en qué orden salen las opciones, plazo, respuestas.
#   plan_de_respuesta    qué pasa al elegir una opción: efecto inmediato + efecto retardado (con {cuando} ya resuelto).
#   FlujoConDilemas      envoltorio del flujo (mismo patrón que FlujoConTiempo): oye el reloj, ofrece, aplica y programa
#                        en la ColaEfectos del FlujoConTiempo que envuelve. Se pone ENCIMA de FlujoConTiempo.
#   envolver(flujo)      lo que llama main.crear_flujo: devuelve el mismo flujo si no aplica (bandera, sin reloj, JSON roto).
#
# CUÁNDO SE OFRECE. Días 1..6 (la consecuencia tiene que poder llegar antes del fin): 1 o 2 dilemas por día, repartidos al
# azar (el azar es inyectable: Random(semilla) -> determinista). Con 9 dilemas son 3 días de 2 y 3 de 1. Cada dilema sale como
# mucho una vez, solo dentro de su ventana [dia_min, dia_max], y entre los candidatos va primero el que antes se le cierra
# la ventana. Dos por día: 09:00 y 19:00; uno: 13:00. Si el jugador no responde en PLAZO_HORAS horas de juego (relojes
# parados por un panel no cuentan) cuenta como «ignorar»: no es participar y tiene su propia consecuencia retardada
# (la clave «ignorar» de cada dilema). Desconectarse o dejarlo pasar NO es lo óptimo (tests/test_dilemas.py lo mide).
#
# QUÉ PASA AL ELEGIR. responder_dilema(opcion) aplica el efecto INMEDIATO (indicadores y, con GameState, confianza por grupo;
# queda en el ArbolImpactos como «dilema:<id>»), programa el RETARDADO a 24-48 h en cola_efectos (su aviso de causa-efecto sale
# por el mismo HUD de avisos de los efectos retardados de misión: «Ayer subiste la foto...») y cuenta como PARTICIPAR para
# el costo de aislamiento. Las opciones se presentan en orden aleatorio (guardado en la oferta): la mejor no vive siempre
# en el mismo sitio.
#
# API del envoltorio (el resto se delega al flujo que envuelve):
#   flujo.dilemas                 GestorDilemas
#   flujo.dilema_pendiente()      dict de la oferta abierta o None: {"id","titulo","situacion","opciones":[{"id","etiqueta",
#                                 "deltas","confianza"}],"hasta","hasta_texto"}  (deltas: SOLO para redactar la pista
#                                 en palabras; la pantalla nunca muestra números)
#   flujo.responder_dilema(id)    dict {"dilema","opcion","texto","deltas","confianza","llega"} o None si no hay oferta,
#                                 la opción no existe o la partida terminó
#   flujo.avisos_dilema           [str] mensajes de teléfono ya enviados (pruebas / depuración)
#   flujo.tiempo_a_dict() / restaurar_tiempo(datos)   añaden la clave OPCIONAL «dilemas» al guardado (los guardados viejos
#                                 no la traen y empiezan con el gestor nuevo)
# En línea no existe (el flujo en línea no pasa por aquí, igual que el reloj).
#
# BANDERA. DILEMAS = False (o ALCALDE_DILEMAS=0): main no envuelve el flujo y no hay dilemas.

import math
import os
import random
import sys
from collections import namedtuple

from backend.logica import efectos_retardados, reloj_partida

DILEMAS = True

SLOTS_DOS = (9.0, 19.0)         # hora del día de las dos ofertas de un día de 2 dilemas
SLOTS_UNO = (13.0,)             # hora de la oferta de un día de 1 dilema
PLAZO_HORAS = 9.0               # horas de juego para contestar antes de que cuente como «ignorar»
DIAS_OFERTA = 6                 # se ofrece en los días 1..6
IGNORADO = "ignorado"
MENSAJE_TELEFONO = "{titulo}: tienes un mensaje sin responder. Pulsa K para leerlo."

_VERSION = 1
_SI = ("1", "true", "si", "sí", "on")
_NO = ("0", "false", "no", "off")

Evento = namedtuple("Evento", "tipo dilema hora")        # tipo: «ofrecida» | «ignorada»
Oferta = namedtuple("Oferta", "id desde hasta orden")
Plan = namedtuple("Plan", "inmediato retardado")         # retardado: (en_horas_abs, Efecto) | None


def activo():
    """¿Hay dilemas? ALCALDE_DILEMAS=1/0 manda sobre la constante (se lee en cada llamada)."""
    valor = os.environ.get("ALCALDE_DILEMAS", "").strip().lower()
    if valor in _SI:
        return True
    if valor in _NO:
        return False
    return bool(DILEMAS)


def cuando(horas):
    """«Ayer» o «Hace dos días» según el retardo (misma regla que los efectos retardados de misión)."""
    return efectos_retardados._cuando(horas)


# -- Qué pasa al elegir -----------------------------------------------------------------------------------------------

def efecto_inmediato(dilema, opcion):
    return efectos_retardados.crear_efecto(f"dilema_{dilema.id}_{opcion.id}", opcion.inmediato.texto,
                                           opcion.inmediato.deltas, opcion.inmediato.confianza, f"dilema:{dilema.id}")


def efecto_de_retardo(dilema, retardado, ahora):
    """(en_horas_abs, Efecto) de una consecuencia retardada (de una opción o de ignorar) pedida a la hora absoluta `ahora`."""
    mensaje = retardado.mensaje.format(cuando=cuando(retardado.horas))
    return ahora + retardado.horas, efectos_retardados.crear_efecto(
        retardado.clave, mensaje, retardado.deltas, retardado.confianza, f"dilema:{dilema.id}")


def plan_de_respuesta(dilema, opcion, ahora):
    return Plan(efecto_inmediato(dilema, opcion), efecto_de_retardo(dilema, opcion.retardado, ahora))


# Aplica el efecto inmediato. Como efectos_retardados.aplicar, pero el evento del GameState es «dilema:<id>» (no «retardado:»).
# Devuelve {"deltas": lo que de verdad cambió cada indicador, "confianza": ídem por grupo}.
def aplicar_inmediato(efecto, estado_partida, game_state, ahora, dilema_id):
    cambios, confianza = {}, {}
    if efecto.deltas and estado_partida is not None:
        antes = estado_partida.indicadores()
        estado_partida.aplicar_deltas(efecto.deltas)
        despues = estado_partida.indicadores()
        cambios = {n: round(despues[n] - antes[n], 2) for n in efecto.deltas if despues[n] != antes[n]}
    if efecto.confianza and game_state is not None:
        from backend.logica.game_state import PESO_INVESTIGACION
        antes = game_state.confianzas()
        game_state.aplicar_evento(
            f"dilema:{dilema_id}", efectos={g: {"investigacion": d / PESO_INVESTIGACION} for g, d in efecto.confianza.items()},
            origen=efecto.origen or None, datos={"mensaje": efecto.mensaje, "hora_juego": ahora})
        despues = game_state.confianzas()
        confianza = {g: round(despues[g] - antes[g], 2) for g in efecto.confianza if despues[g] != antes[g]}
    return {"deltas": cambios, "confianza": confianza}


# -- Gestor (estado puro) ---------------------------------------------------------------------------------------------

def _hora(valor, nombre="ahora"):
    if isinstance(valor, bool) or not isinstance(valor, (int, float)) or not math.isfinite(valor):
        raise ValueError(f"{nombre} inválido: {valor!r}; se esperaba un número finito de horas.")
    return float(valor)


class GestorDilemas:

    # `dilemas`: tupla de dilemas_loader.Dilema. `azar`: random.Random (None = uno nuevo). `plazo`: horas para contestar.
    def __init__(self, dilemas, azar=None, plazo=PLAZO_HORAS):
        self._dilemas = tuple(dilemas)
        self._por_id = {d.id: d for d in self._dilemas}
        self._azar = azar if azar is not None else random.Random()
        self._plazo = max(0.0, _hora(plazo, "plazo"))
        self._plan = self._plan_por_dia(len(self._dilemas))       # dilemas ofrecidos en el día 1..DIAS_OFERTA
        self._usados = 0                                          # ofertas del calendario ya intentadas
        self._ofrecidos = []                                      # ids, en el orden en que salieron
        self._respuestas = {}                                     # id -> id de opción | IGNORADO
        self._oferta = None                                       # Oferta abierta
        self._libre_desde = 0.0                                   # hora en que quedó libre la bandeja

    # Reparto de n dilemas en DIAS_OFERTA días, de 1 a 2 por día (los días extra, entre los primeros: allí caben más ventanas).
    def _plan_por_dia(self, n):
        n = min(n, 2 * DIAS_OFERTA)
        base, extra = divmod(n, DIAS_OFERTA)
        plan = [base] * DIAS_OFERTA
        candidatos = list(range(DIAS_OFERTA - 1)) if extra < DIAS_OFERTA else list(range(DIAS_OFERTA))
        for dia in self._azar.sample(candidatos, min(extra, len(candidatos))):
            plan[dia] += 1
        for dia in range(DIAS_OFERTA):                           # si no cabían entre los primeros, el sexto recoge el resto
            if sum(plan) < n and plan[dia] < 2:
                plan[dia] += 1
        return plan

    def calendario(self):
        """Horas absolutas en que toca ofrecer (una por dilema que cabe en la semana), en orden."""
        horas = []
        for dia, cuantos in enumerate(self._plan):
            slots = SLOTS_DOS if cuantos >= 2 else SLOTS_UNO if cuantos == 1 else ()
            horas += [dia * 24.0 + h for h in slots]
        return horas

    # -- Consulta --

    def dilemas(self):
        return self._dilemas

    def oferta(self):
        return self._oferta

    def dilema_de(self, ident):
        return self._por_id.get(ident)

    def ofrecidos(self):
        return list(self._ofrecidos)

    def respuestas(self):
        return dict(self._respuestas)

    def respondidos(self):
        return [i for i, r in self._respuestas.items() if r != IGNORADO]

    def ignorados(self):
        return [i for i, r in self._respuestas.items() if r == IGNORADO]

    # -- Avance --

    # Da por pasadas las ofertas del calendario hasta `ahora` SIN ofrecerlas ni cobrarlas como «ignoradas». Para una partida
    # restaurada de un guardado anterior a los dilemas (día 4 sin gestor guardado): no se le cobra lo que nunca pudo ver.
    def saltar_hasta(self, ahora):
        ahora = _hora(ahora)
        self._usados = sum(1 for hora in self.calendario() if hora <= ahora)
        self._libre_desde = max(self._libre_desde, ahora)

    def _elegir(self, dia):
        candidatos = [d for d in self._dilemas if d.id not in self._respuestas and d.id not in self._ofrecidos
                      and d.dia_min <= dia <= d.dia_max]
        if not candidatos:
            return None
        azar = {d.id: self._azar.random() for d in candidatos}
        return min(candidatos, key=lambda d: (d.dia_max, azar[d.id]))

    # Mueve el reloj a `ahora` (horas absolutas): cierra las ofertas vencidas como «ignorar» y abre la siguiente si toca.
    # Devuelve [Evento] en orden cronológico. Idempotente: llamarlo dos veces con la misma hora no repite nada.
    def avanzar(self, ahora):
        ahora = _hora(ahora)
        eventos, calendario = [], self.calendario()
        while True:
            if self._oferta is not None and ahora >= self._oferta.hasta:
                oferta, self._oferta = self._oferta, None
                self._respuestas[oferta.id] = IGNORADO
                self._libre_desde = oferta.hasta
                eventos.append(Evento("ignorada", self._por_id[oferta.id], oferta.hasta))
                continue
            if self._oferta is None and self._usados < len(calendario) and calendario[self._usados] <= ahora:
                slot = calendario[self._usados]
                self._usados += 1
                dilema = self._elegir(int(slot // 24.0) + 1)
                if dilema is not None:
                    desde = max(slot, self._libre_desde)
                    orden = [o.id for o in dilema.opciones]
                    self._azar.shuffle(orden)
                    self._ofrecidos.append(dilema.id)
                    self._oferta = Oferta(dilema.id, desde, desde + self._plazo, tuple(orden))
                    eventos.append(Evento("ofrecida", dilema, desde))
                continue
            break
        return eventos

    # El jugador elige `opcion_id` en la oferta abierta. Devuelve (dilema, opcion) o None si no hay oferta / no existe la opción.
    def responder(self, opcion_id, ahora):
        if self._oferta is None:
            return None
        dilema = self._por_id[self._oferta.id]
        opcion = next((o for o in dilema.opciones if o.id == opcion_id), None)
        if opcion is None:
            return None
        self._respuestas[dilema.id] = opcion.id
        self._oferta = None
        self._libre_desde = _hora(ahora)
        return dilema, opcion

    # -- Serialización (JSON) --

    def a_dict(self):
        oferta = None if self._oferta is None else {"id": self._oferta.id, "desde": self._oferta.desde,
                                                    "hasta": self._oferta.hasta, "orden": list(self._oferta.orden)}
        return {"version": _VERSION, "plan": list(self._plan), "usados": self._usados, "ofrecidos": list(self._ofrecidos),
                "respuestas": dict(self._respuestas), "oferta": oferta, "libre_desde": self._libre_desde}

    # ValueError si los datos no son válidos. Ids que ya no existen en el JSON se descartan (el JSON pudo cambiar).
    @classmethod
    def desde_dict(cls, datos, dilemas, azar=None, plazo=PLAZO_HORAS):
        if not isinstance(datos, dict) or datos.get("version") != _VERSION:
            raise ValueError("Dilemas guardados con formato desconocido.")
        gestor = cls(dilemas, azar, plazo)
        plan = datos.get("plan")
        if (not isinstance(plan, list) or len(plan) != DIAS_OFERTA
                or any(isinstance(n, bool) or not isinstance(n, int) or not 0 <= n <= 2 for n in plan)):
            raise ValueError("Plan de dilemas guardado inválido.")
        gestor._plan = list(plan)
        usados = datos.get("usados", 0)
        if isinstance(usados, bool) or not isinstance(usados, int) or not 0 <= usados <= 2 * DIAS_OFERTA:
            raise ValueError(f"usados inválido: {usados!r}.")
        gestor._usados = usados
        ofrecidos = datos.get("ofrecidos", [])
        respuestas = datos.get("respuestas", {})
        if not isinstance(ofrecidos, list) or not isinstance(respuestas, dict):
            raise ValueError("Dilemas guardados dañados.")
        gestor._ofrecidos = [i for i in ofrecidos if i in gestor._por_id]
        for ident, valor in respuestas.items():
            dilema = gestor._por_id.get(ident)
            if dilema is not None and (valor == IGNORADO or valor in {o.id for o in dilema.opciones}):
                gestor._respuestas[ident] = valor
        gestor._libre_desde = max(0.0, _hora(datos.get("libre_desde", 0.0), "libre_desde"))
        crudo = datos.get("oferta")
        if crudo is not None:
            if not isinstance(crudo, dict) or crudo.get("id") not in gestor._por_id:
                raise ValueError("Oferta de dilema guardada inválida.")
            dilema = gestor._por_id[crudo["id"]]
            ids = {o.id for o in dilema.opciones}
            orden = tuple(crudo.get("orden") or ())
            if set(orden) != ids or len(orden) != len(ids):
                orden = tuple(o.id for o in dilema.opciones)
            gestor._oferta = Oferta(dilema.id, _hora(crudo["desde"], "desde"), _hora(crudo["hasta"], "hasta"), orden)
            if dilema.id not in gestor._ofrecidos:
                gestor._ofrecidos.append(dilema.id)
        return gestor


# -- Envoltorio del flujo ---------------------------------------------------------------------------------------------

_PROPIOS = ("_flujo", "dilemas", "avisos_dilema")


class FlujoConDilemas:

    # `flujo`: FlujoConTiempo (necesita reloj; cola_efectos y aislamiento si hay, si no se omiten esas partes).
    def __init__(self, flujo, dilemas, azar=None):
        self._flujo = flujo
        self._cargados = tuple(dilemas)
        self.dilemas = GestorDilemas(self._cargados, azar)
        self.avisos_dilema = []

    # -- Tiempo --

    def avanzar_tiempo(self, dt):
        nuevos = self._flujo.avanzar_tiempo(dt)
        self._revisar()
        return nuevos

    def avanzar_horas(self, horas):
        nuevos = self._flujo.avanzar_horas(horas)
        self._revisar()
        return nuevos

    def _revisar(self):
        reloj = self._flujo.reloj
        if reloj.terminado() or self._flujo.partida_terminada():
            return
        for evento in self.dilemas.avanzar(reloj.tiempo_absoluto()):
            if evento.tipo == "ofrecida":
                self._avisar_telefono(evento.dilema)
            elif evento.tipo == "ignorada" and evento.dilema.ignorar is not None:
                self._programar_ignorada(evento)

    def _programar_ignorada(self, evento):
        try:        # una consecuencia mal formada nunca puede romper el reloj (tampoco al construirla)
            en_horas, efecto = efecto_de_retardo(evento.dilema, evento.dilema.ignorar, evento.hora)
        except (ValueError, TypeError, KeyError) as error:
            print(f"[dilemas] consecuencia no programada: {error}", file=sys.stderr)
            return
        self._programar(en_horas, efecto)

    def _programar(self, en_horas, efecto):
        cola = getattr(self._flujo, "cola_efectos", None)
        if cola is None:
            return
        try:        # una consecuencia mal formada nunca puede romper el reloj
            cola.programar(en_horas, efecto)
        except ValueError as error:
            print(f"[dilemas] consecuencia no programada: {error}", file=sys.stderr)

    def _avisar_telefono(self, dilema):
        texto = MENSAJE_TELEFONO.format(titulo=dilema.titulo)
        self.avisos_dilema.append(texto)
        del self.avisos_dilema[:-20]
        try:
            self._flujo.jugador_activo().telefono.notificar(texto)
        except (AttributeError, TypeError):
            pass

    # -- Oferta y respuesta --

    def dilema_pendiente(self):
        oferta = self.dilemas.oferta()
        if oferta is None or self._flujo.partida_terminada():
            return None
        dilema = self.dilemas.dilema_de(oferta.id)
        por_id = {o.id: o for o in dilema.opciones}
        return {"id": dilema.id, "titulo": dilema.titulo, "situacion": dilema.situacion, "hasta": oferta.hasta,
                "hasta_texto": reloj_partida.texto_de(oferta.hasta),
                "opciones": [{"id": i, "etiqueta": por_id[i].etiqueta, "deltas": dict(por_id[i].inmediato.deltas),
                              "confianza": dict(por_id[i].inmediato.confianza)} for i in oferta.orden]}

    def responder_dilema(self, opcion_id):
        if self._flujo.reloj.terminado() or self._flujo.partida_terminada():
            return None
        ahora = self._flujo.reloj.tiempo_absoluto()
        elegido = self.dilemas.responder(opcion_id, ahora)
        if elegido is None:
            return None
        dilema, opcion = elegido
        plan = plan_de_respuesta(dilema, opcion, ahora)
        estado = getattr(getattr(self._flujo, "sesion", None), "estado_partida", None)
        cambios = aplicar_inmediato(plan.inmediato, estado, getattr(self._flujo, "game_state", None), ahora, dilema.id)
        self._programar(*plan.retardado)
        aislamiento = getattr(self._flujo, "aislamiento", None)
        if aislamiento is not None:
            aislamiento.participar(ahora)                         # decidir es participar
        return {"dilema": dilema.id, "opcion": opcion.id, "texto": opcion.inmediato.texto,
                "deltas": cambios["deltas"], "confianza": cambios["confianza"],
                "llega": reloj_partida.texto_de(plan.retardado[0])}

    # -- Guardado --

    def tiempo_a_dict(self):
        datos = self._flujo.tiempo_a_dict()
        datos["dilemas"] = self.dilemas.a_dict()
        return datos

    def restaurar_tiempo(self, datos):
        self._flujo.restaurar_tiempo(datos)
        crudo = datos.get("dilemas") if isinstance(datos, dict) else None
        self.avisos_dilema = []
        if crudo is not None:
            try:
                self.dilemas = GestorDilemas.desde_dict(crudo, self._cargados)
                return
            except (ValueError, KeyError, TypeError, AttributeError) as error:
                print(f"[dilemas] «dilemas» del guardado no se pudo leer ({error}); se empieza de cero", file=sys.stderr)
        self.dilemas = GestorDilemas(self._cargados)
        self.dilemas.saltar_hasta(self._flujo.reloj.tiempo_absoluto())

    def __getattr__(self, nombre):
        if nombre.startswith("__") or nombre in _PROPIOS:
            raise AttributeError(nombre)
        return getattr(self._flujo, nombre)


# Lo que llama main.crear_flujo: envuelve `flujo` con dilemas si la bandera está encendida, el flujo tiene reloj y los
# dilemas cargan. Si no, devuelve `flujo` tal cual (nunca puede impedir jugar).
def envolver(flujo, ruta=None, azar=None):
    if not activo() or getattr(flujo, "reloj", None) is None or not callable(getattr(flujo, "avanzar_tiempo", None)):
        return flujo
    try:
        from backend.datos import dilemas_loader
        dilemas = dilemas_loader.cargar_dilemas(ruta)
    except ValueError as error:
        print(f"[dilemas] desactivados: {error}", file=sys.stderr)
        return flujo
    return FlujoConDilemas(flujo, dilemas, azar)
