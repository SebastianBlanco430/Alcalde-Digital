# «Rectificar» (modelo puro, serializable, sin ursina): lo que pasa con algo que COMPARTISTE y resultó falso, impreciso
# o hiriente. Enseña que lo responsable es corregirlo en público y que borrarlo no deshace el daño.
#
# ORIGEN. Solo nace de una decisión real del jugador (nunca de un sorteo):
#   - una opción de dilema mapeada en backend/datos/rectificaciones.json («origenes»: dilema + opcion), p. ej. reenviar
#     el meme de Lucas o compartir sin confirmar el corte de agua;
#   - una misión de verificar con rumor FALSO que el jugador eligió «compartir» (el caso con «mision_falsa», que usa el
#     título del rumor).
# Se registra una publicación PENDIENTE con su caso, su origen y la hora del reloj de 7 días.
#
# AVISO. RETRASO_AVISO horas de juego después, entre HORA_MIN y HORA_MAX y como MUCHO UNO POR DÍA, llega a la bandeja de
# Civitas (tecla L, el mismo panel de frontend/registro_habitos.py) una tarjeta «Algo que compartiste resultó falso…»: el
# jugador MARCA la evidencia (mismo mecanismo que las estafas) y decide:
#   rectificar  corrección pública: vergüenza al momento (ciudadanos baja un poco) y, al día siguiente, mejor saldo.
#   borrar      desaparece de tu perfil, pero alguien guardó la captura: al día siguiente reaparece y pesa más.
#   defender    (también «ignorar»: dejar pasar el plazo) la mentira crece: la consecuencia más fuerte.
# Tras elegir, la revisión explica qué pasó y por qué (texto del caso + explicación de cada evidencia).
#
# Todo pasa por los sistemas de siempre (efectos_retardados.aplicar y la cola del FlujoConTiempo): los finales y las etapas
# −3..+3 se mueven solos porque salen de indicadores y confianza por grupo. El veredicto de una misión ya cerrada no cambia.
# FIN DE PARTIDA: lo que siga pendiente (en la bandeja o esperando su aviso) cuenta como «defender» y se aplica YA.
#
# Bandera: ALCALDE_RECTIFICAR (1 por defecto; 0 = la partida queda exactamente como antes). En línea no existe: el flujo
# en línea no pasa por main.crear_flujo, y el panel L no hace nada con escena.online.
#
# API del envoltorio (el resto se delega al flujo que envuelve):
#   flujo.rectificaciones                   GestorRectificaciones
#   flujo.evento_pendiente()                la tarjeta de rectificar abierta (tipo «rectificar») o la de hábitos
#   flujo.responder_evento(marcas, decision) resuelve la rectificación abierta o delega
#   flujo.avisos_rectificar                 textos enviados al teléfono (pruebas / depuración)
#   flujo.tiempo_a_dict() / restaurar_tiempo(datos)   clave OPCIONAL «rectificar» en el guardado

import json
import os
import sys
from collections import namedtuple
from pathlib import Path

from backend.datos.dilemas_loader import RUTA_DILEMAS
from backend.logica import efectos_retardados, reloj_partida
from backend.logica.dilemas import cuando
from backend.logica.habitos_digitales import Elemento, calificar

RECTIFICAR = True

RUTA_CASOS = Path(__file__).resolve().parent.parent / "datos" / "rectificaciones.json"
VERSION = 1
MAX_TEXTO = 400
MAX_RUMOR = 90

RETRASO_AVISO = 8.0
HORA_MIN = 8.0
HORA_MAX = 22.0
PLAZO_HORAS = 9.0
RETRASO_CONSECUENCIA = 24.0
MAX_PENDIENTES = 3
HORAS_POR_DIA = 24.0

RECTIFICAR_ID, BORRAR, DEFENDER = "rectificar", "borrar", "defender"
DECISIONES = (RECTIFICAR_ID, BORRAR, DEFENDER)
TIPOS = ("falso", "impreciso", "hiriente")
TIPO_TARJETA = "rectificar"
MENSAJE_TELEFONO = "Civitas: algo que compartiste resultó ser {tipo}. Pulsa L para revisarlo."

# (deltas inmediatos, confianza inmediata, deltas a las 24 h, confianza a las 24 h). Rectificar: la parte retardada se
# escala por lo bien que se marcó la evidencia (0,5 + 0,5 · calidad), como en las estafas.
EFECTOS = {
    RECTIFICAR_ID: ({}, {"ciudadanos": -1},
                    {"confianza": 2, "desinformacion": -2, "convivencia": 1}, {"ciudadanos": 2, "instituciones": 1}),
    BORRAR: ({}, {},
             {"confianza": -2, "desinformacion": 3, "convivencia": -1}, {"ciudadanos": -2, "instituciones": -1}),
    DEFENDER: ({}, {"ciudadanos": 1},
               {"confianza": -3, "desinformacion": 4, "convivencia": -2}, {"ciudadanos": -4, "instituciones": -2}),
}

Caso = namedtuple("Caso", "id tipo titulo remitente texto problema aviso origenes elementos etiquetas explicaciones "
                          "retardados repetible")
Plan = namedtuple("Plan", "texto inmediato retardado")      # inmediato: Efecto o None; retardado: (hora_abs, Efecto)

_SI = ("1", "true", "si", "sí", "on")
_NO = ("0", "false", "no", "off")


def activo():
    """¿Está encendido Rectificar? ALCALDE_RECTIFICAR=1/0 manda sobre la constante (se lee en cada llamada)."""
    valor = os.environ.get("ALCALDE_RECTIFICAR", "").strip().lower()
    if valor in _SI:
        return True
    if valor in _NO:
        return False
    return bool(RECTIFICAR)


# -- Datos ------------------------------------------------------------------------------------------------------------

def _texto(valor, nombre):
    if not isinstance(valor, str) or not valor.strip():
        raise ValueError(f"{nombre}: falta el texto.")
    if len(valor.strip()) > MAX_TEXTO:
        raise ValueError(f"{nombre}: el texto pasa de {MAX_TEXTO} caracteres.")
    return valor.strip()


# {(dilema, opcion)} de dilemas_extra.json, sin filtrar banderas (un dilema apagado no invalida el caso: no nacerá).
def _opciones_de_dilemas(ruta_dilemas=None):
    ruta = Path(ruta_dilemas) if ruta_dilemas is not None else RUTA_DILEMAS
    try:
        crudo = json.loads(ruta.read_text(encoding="utf-8"))
        return {(d["id"], o["id"]) for d in crudo["dilemas"] for o in d["opciones"]}
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise ValueError(f"{ruta.name}: no se pudieron leer los dilemas ({error}).") from None


def _origen(crudo, nombre, opciones):
    if not isinstance(crudo, dict):
        raise ValueError(f"{nombre}: cada origen debe ser un objeto.")
    if crudo.get("mision_falsa") is True:
        return ("mision",)
    clave = (crudo.get("dilema"), crudo.get("opcion"))
    if clave not in opciones:
        raise ValueError(f"{nombre}: el origen {clave[0]}/{clave[1]} no existe en los dilemas.")
    return ("dilema",) + clave


def _caso(crudo, opciones):
    if not isinstance(crudo, dict):
        raise ValueError("caso: se esperaba un objeto.")
    ident = _texto(crudo.get("id"), "caso.id")
    nombre = f"caso {ident}"
    tipo = crudo.get("tipo")
    if tipo not in TIPOS:
        raise ValueError(f"{nombre}: «tipo» debe ser uno de {TIPOS}.")
    origenes = crudo.get("origenes")
    if not isinstance(origenes, list) or not origenes:
        raise ValueError(f"{nombre}: necesita al menos un origen.")
    elementos = crudo.get("elementos")
    if not isinstance(elementos, list) or not 2 <= len(elementos) <= 4:
        raise ValueError(f"{nombre}: necesita de 2 a 4 elementos.")
    lista = []
    for e in elementos:
        if not isinstance(e, dict) or not isinstance(e.get("evidencia"), bool):
            raise ValueError(f"{nombre}: cada elemento necesita «evidencia» true o false.")
        eid = _texto(e.get("id"), f"{nombre}.elemento.id")
        lista.append(Elemento(eid, _texto(e.get("texto"), f"{nombre}/{eid}.texto"), e["evidencia"],
                              _texto(e.get("explicacion"), f"{nombre}/{eid}.explicacion"), "", None))
    if len({e.id for e in lista}) != len(lista):
        raise ValueError(f"{nombre}: ids de elementos repetidos.")
    if not any(e.marcar for e in lista):
        raise ValueError(f"{nombre}: al menos un elemento debe ser evidencia.")
    tablas = {}
    for campo in ("etiquetas", "explicaciones", "retardados"):
        tabla = crudo.get(campo)
        if not isinstance(tabla, dict) or set(tabla) != set(DECISIONES):
            raise ValueError(f"{nombre}: «{campo}» necesita exactamente {DECISIONES}.")
        tablas[campo] = {d: _texto(tabla[d], f"{nombre}.{campo}.{d}") for d in DECISIONES}
    for d, mensaje in tablas["retardados"].items():
        if not mensaje.startswith("{cuando} ") or mensaje.count("{cuando}") != 1:
            raise ValueError(f"{nombre}.retardados.{d}: debe empezar con un único «{{cuando}} ».")
    return Caso(ident, tipo, _texto(crudo.get("titulo"), f"{nombre}.titulo"),
                _texto(crudo.get("remitente"), f"{nombre}.remitente"), _texto(crudo.get("texto"), f"{nombre}.texto"),
                _texto(crudo.get("problema"), f"{nombre}.problema"), _texto(crudo.get("aviso"), f"{nombre}.aviso"),
                tuple(_origen(o, nombre, opciones) for o in origenes), tuple(lista), tablas["etiquetas"],
                tablas["explicaciones"], tablas["retardados"], crudo.get("repetible") is True)


def cargar_casos(ruta=None, ruta_dilemas=None):
    """Tupla de Caso de rectificaciones.json. ValueError ante cualquier error (nunca se salta un caso en silencio)."""
    ruta = Path(ruta) if ruta is not None else RUTA_CASOS
    try:
        datos = json.loads(ruta.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise ValueError(f"{ruta.name}: el archivo no existe.") from None
    except json.JSONDecodeError as error:
        raise ValueError(f"{ruta.name}: JSON inválido (línea {error.lineno}): {error.msg}") from None
    if not isinstance(datos, dict) or datos.get("version") != VERSION or not isinstance(datos.get("casos"), list):
        raise ValueError(f"{ruta.name}: formato desconocido (se esperaba version {VERSION} y una lista «casos»).")
    opciones = _opciones_de_dilemas(ruta_dilemas)
    casos = tuple(_caso(c, opciones) for c in datos["casos"])
    if not casos:
        raise ValueError(f"{ruta.name}: no hay casos.")
    if len({c.id for c in casos}) != len(casos):
        raise ValueError(f"{ruta.name}: ids de casos repetidos.")
    origenes = [o for c in casos for o in c.origenes]
    if len(set(origenes)) != len(origenes):
        raise ValueError(f"{ruta.name}: un mismo origen lleva a dos casos.")
    return casos


# -- Consecuencias (puras) --------------------------------------------------------------------------------------------

def _rumor(texto):
    texto = " ".join(str(texto or "").split()).rstrip(".")
    return texto if len(texto) <= MAX_RUMOR else texto[:MAX_RUMOR - 1].rstrip() + "…"


# Sustituye {rumor} (y {cuando} si se da) sin str.format: un rumor con llaves nunca puede romper el texto.
def redactar(texto, rumor="", cuando_texto=None):
    texto = texto.replace("{rumor}", rumor or "lo que compartiste")
    return texto.replace("{cuando}", cuando_texto) if cuando_texto is not None else texto


def _escalar(tabla, factor):
    return {k: round(v * factor, 2) for k, v in tabla.items()}


def plan_rectificacion(caso, pendiente, marcas, decision, ahora):
    """Plan de responder `caso` con `decision` a la hora absoluta `ahora`. La calidad sale de marcar la evidencia."""
    if decision not in DECISIONES:
        raise ValueError(f"decisión desconocida: {decision}")
    _revision, calidad = calificar(caso, marcas)
    rumor = pendiente.get("rumor", "")
    origen = f"rectificar:{caso.id}"
    deltas, confianza, deltas_ret, confianza_ret = EFECTOS[decision]
    if decision == RECTIFICAR_ID:
        factor = 0.5 + 0.5 * calidad
        deltas_ret, confianza_ret = _escalar(deltas_ret, factor), _escalar(confianza_ret, factor)
    texto = f"{redactar(caso.explicaciones[decision], rumor)} {redactar(caso.problema, rumor)}"
    inmediato = None
    if deltas or confianza:
        inmediato = efectos_retardados.crear_efecto(f"rectificar_{caso.id}_{decision}", texto, deltas, confianza, origen)
    mensaje = redactar(caso.retardados[decision], rumor, cuando(RETRASO_CONSECUENCIA))
    retardado = efectos_retardados.crear_efecto(f"rectificar_{caso.id}_{decision}_luego", mensaje, deltas_ret,
                                                confianza_ret, origen)
    return Plan(texto, inmediato, (ahora + RETRASO_CONSECUENCIA, retardado))


# -- Estado de la bandeja de rectificaciones (serializable) ---------------------------------------------------------

def _dia_de(hora_abs):
    return int(hora_abs // HORAS_POR_DIA) + 1


class GestorRectificaciones:

    def __init__(self, casos):
        self.casos = {c.id: c for c in casos}
        self._por_dilema = {}
        self._caso_mision = None
        for c in casos:
            for o in c.origenes:
                if o[0] == "dilema":
                    self._por_dilema[(o[1], o[2])] = c.id
                elif self._caso_mision is None:
                    self._caso_mision = c.id
        self.usados = set()             # claves ya registradas (no se repiten)
        self.pendientes = []            # [dict] esperando su aviso, en orden de registro
        self.oferta = None              # dict pendiente + desde/hasta, o None
        self.respuestas = []            # [{caso, clave, decision, motivo, dia, hora_texto}]
        self.dias_con_aviso = []        # días en que ya hubo un aviso (como mucho uno por día)

    # -- Origen --

    def caso_de_dilema(self, dilema_id, opcion_id):
        return self._por_dilema.get((dilema_id, opcion_id))

    def caso_de_mision(self):
        return self._caso_mision

    def registrar(self, caso_id, ahora, origen, rumor="", clave=None):
        """Registra una publicación problemática. Devuelve el pendiente o None (caso desconocido, repetido o cola llena)."""
        caso = self.casos.get(caso_id)
        if caso is None:
            return None
        clave = clave if caso.repetible and clave else caso.id
        if clave in self.usados or len(self.pendientes) >= MAX_PENDIENTES:
            return None
        self.usados.add(clave)
        pendiente = {"clave": clave, "caso": caso.id, "origen": str(origen), "rumor": _rumor(rumor),
                     "hora": float(ahora), "dia": _dia_de(ahora), "hora_texto": reloj_partida.texto_de(ahora)}
        self.pendientes.append(pendiente)
        return pendiente

    # -- Calendario --

    def avanzar(self, ahora):
        """[("vencido"|"ofrecido", pendiente)] de lo que cambió a la hora absoluta `ahora`."""
        # la oferta vencida la cierra quien la resuelve (FlujoConRectificar._resolver)
        if self.oferta is not None:
            return [("vencido", self.oferta)] if ahora >= self.oferta["hasta"] else []
        dia, hora = _dia_de(ahora), ahora % HORAS_POR_DIA
        if dia in self.dias_con_aviso or not HORA_MIN <= hora < HORA_MAX:
            return []
        for pendiente in self.pendientes:
            if ahora >= pendiente["hora"] + RETRASO_AVISO:
                self.pendientes.remove(pendiente)
                self.oferta = dict(pendiente, desde=float(ahora), hasta=float(ahora) + PLAZO_HORAS)
                self.dias_con_aviso.append(dia)
                return [("ofrecido", self.oferta)]
        return []

    def cerrar(self, pendiente, decision, motivo, ahora):
        """Anota la respuesta de `pendiente` (la oferta abierta o uno que esperaba) y lo saca de la bandeja."""
        if self.oferta is pendiente:
            self.oferta = None
        elif pendiente in self.pendientes:
            self.pendientes.remove(pendiente)
        self.respuestas.append({"caso": pendiente["caso"], "clave": pendiente["clave"], "decision": decision,
                                "motivo": motivo, "dia": _dia_de(ahora), "hora_texto": reloj_partida.texto_de(ahora)})

    def sin_resolver(self):
        return ([self.oferta] if self.oferta is not None else []) + list(self.pendientes)

    # -- Guardado --

    def a_dict(self):
        return {"version": VERSION, "usados": sorted(self.usados), "pendientes": [dict(p) for p in self.pendientes],
                "oferta": dict(self.oferta) if self.oferta is not None else None,
                "respuestas": [dict(r) for r in self.respuestas], "dias_con_aviso": list(self.dias_con_aviso)}

    @classmethod
    def desde_dict(cls, datos, casos):
        if not isinstance(datos, dict) or datos.get("version") != VERSION:
            raise ValueError("versión de «rectificar» desconocida")
        gestor = cls(casos)
        gestor.usados = {str(u) for u in datos.get("usados", [])}

        def _leer(p):
            p = dict(p)
            if p.get("caso") not in gestor.casos:
                raise ValueError(f"caso desconocido: {p.get('caso')}")
            p["hora"] = float(p["hora"])
            return p

        gestor.pendientes = [_leer(p) for p in datos.get("pendientes", [])]
        oferta = datos.get("oferta")
        if oferta is not None:
            oferta = _leer(oferta)
            oferta["desde"], oferta["hasta"] = float(oferta["desde"]), float(oferta["hasta"])
        gestor.oferta = oferta
        gestor.respuestas = [dict(r) for r in datos.get("respuestas", [])]
        gestor.dias_con_aviso = [int(d) for d in datos.get("dias_con_aviso", [])]
        return gestor


# -- Envoltorio del flujo ---------------------------------------------------------------------------------------------

_PROPIOS = ("_flujo", "rectificaciones", "avisos_rectificar", "_casos")


class FlujoConRectificar:

    # `flujo`: FlujoConTiempo (o algo que lo envuelve: dilemas, hábitos). Necesita reloj; la cola de efectos, el GameState
    # y la bandeja de hábitos se usan si están.
    def __init__(self, flujo, casos):
        self._flujo = flujo
        self._casos = tuple(casos)
        self.rectificaciones = GestorRectificaciones(self._casos)
        self.avisos_rectificar = []

    def _terminada(self):
        return self._flujo.reloj.terminado() or self._flujo.partida_terminada()

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
        if self._terminada():
            self._cerrar_pendientes()
            return
        ahora = self._flujo.reloj.tiempo_absoluto()
        for tipo, pendiente in self.rectificaciones.avanzar(ahora):
            if tipo == "ofrecido":
                caso = self.rectificaciones.casos[pendiente["caso"]]
                self._avisar_telefono(MENSAJE_TELEFONO.format(tipo=caso.tipo))
            else:
                self._resolver(pendiente, (), DEFENDER, "vencido")

    # -- Origen: dilemas y misiones --

    def _responder_dilema(self, original, opcion_id):
        resultado = original(opcion_id)
        if isinstance(resultado, dict):
            caso = self.rectificaciones.caso_de_dilema(resultado.get("dilema"), resultado.get("opcion"))
            if caso is not None:
                ahora = self._flujo.reloj.tiempo_absoluto()
                self.rectificaciones.registrar(caso, ahora, f"dilema:{resultado['dilema']}/{resultado['opcion']}")
        return resultado

    def completar_mision(self, resultado):
        leer_mision = getattr(self._flujo, "mision_actual", None)
        mision = leer_mision() if callable(leer_mision) else None        # antes de delegar: completar pasa el turno
        activo = self._flujo.completar_mision(resultado)
        try:        # registrar nunca puede impedir cerrar una misión
            decision = resultado.get("decision_mision") if isinstance(resultado, dict) else None
            caso = self.rectificaciones.caso_de_mision()
            if (caso is not None and mision is not None and decision == "compartir"
                    and getattr(mision, "tipo", "verificar") == "verificar"
                    and getattr(mision, "es_verdadera", None) is False and not self._terminada()):
                rumor = getattr(mision, "rumor", "") or getattr(mision, "titulo", "")
                self.rectificaciones.registrar(caso, self._flujo.reloj.tiempo_absoluto(), f"mision:{mision.id}",
                                               rumor, clave=f"{caso}:{mision.id}")
        except (AttributeError, TypeError, ValueError) as error:
            print(f"[rectificar] origen de misión no registrado: {error}", file=sys.stderr)
        return activo

    # -- Bandeja (el mismo panel L de hábitos) --

    def evento_pendiente(self):
        oferta = self.rectificaciones.oferta
        if oferta is not None and not self._terminada():
            caso = self.rectificaciones.casos[oferta["caso"]]
            rumor = oferta.get("rumor", "")
            texto = f"{redactar(caso.aviso, rumor)} Lo que compartiste: {redactar(caso.texto, rumor)}"
            return {"tipo": TIPO_TARJETA, "id": caso.id, "titulo": redactar(caso.titulo, rumor),
                    "remitente": caso.remitente, "texto": texto, "hasta_texto": reloj_partida.texto_de(oferta["hasta"]),
                    "elementos": [{"id": e.id, "texto": e.texto} for e in caso.elementos],
                    "opciones": [{"id": d, "etiqueta": caso.etiquetas[d]} for d in DECISIONES]}
        interno = getattr(self._flujo, "evento_pendiente", None)
        return interno() if callable(interno) else None

    def responder_evento(self, marcas, decision):
        oferta = self.rectificaciones.oferta
        if oferta is not None and decision in DECISIONES:
            if self._terminada():
                return None
            resultado = self._resolver(oferta, marcas, decision, "jugador")
            aislamiento = getattr(self._flujo, "aislamiento", None)
            if aislamiento is not None:
                aislamiento.participar(self._flujo.reloj.tiempo_absoluto())       # decidir es participar
            return resultado
        interno = getattr(self._flujo, "responder_evento", None)
        return interno(marcas, decision) if callable(interno) else None

    # Aplica la decisión sobre `pendiente`. `motivo`: «jugador», «vencido» o «fin» (en el fin todo se aplica YA, porque
    # la cola de efectos ya se vació). Devuelve el dict de la revisión (misma forma que la bandeja de hábitos).
    def _resolver(self, pendiente, marcas, decision, motivo):
        caso = self.rectificaciones.casos[pendiente["caso"]]
        ahora = self._flujo.reloj.tiempo_absoluto()
        self.rectificaciones.cerrar(pendiente, decision, motivo, ahora)
        try:
            plan = plan_rectificacion(caso, pendiente, marcas, decision, ahora)
        except ValueError as error:
            print(f"[rectificar] consecuencia no aplicada: {error}", file=sys.stderr)
            return None
        if plan.inmediato is not None:
            self._aplicar_ahora(plan.inmediato, anunciar=motivo != "jugador")
        cola = getattr(self._flujo, "cola_efectos", None)
        if motivo == "fin" or cola is None:
            self._aplicar_ahora(plan.retardado[1], anunciar=True)
        else:
            try:        # una consecuencia mal formada nunca puede romper el reloj
                cola.programar(*plan.retardado)
            except ValueError as error:
                print(f"[rectificar] consecuencia no programada: {error}", file=sys.stderr)
        revision, calidad = calificar(caso, marcas)
        return {"tipo": TIPO_TARJETA, "id": caso.id, "titulo": redactar(caso.titulo, pendiente.get("rumor", "")),
                "decision": decision, "texto": plan.texto, "perdida": 0, "calidad": round(calidad, 2), "llega": True,
                "revision": [{"texto": e.texto, "marcado": marcado, "acertado": ok, "explicacion": e.explicacion,
                              "debia_marcarse": e.marcar} for e, marcado, ok in revision]}

    # Fin de partida: lo que siga sin resolver cuenta como «defender» (ignorada). Idempotente.
    def _cerrar_pendientes(self):
        for pendiente in self.rectificaciones.sin_resolver():
            self._resolver(pendiente, (), DEFENDER, "fin")

    def final_partida(self):
        if self._terminada():
            self._cerrar_pendientes()
        interno = getattr(self._flujo, "final_partida", None)
        return interno() if callable(interno) else None

    def resumen_final(self):
        if self._terminada():
            self._cerrar_pendientes()
        return self._flujo.resumen_final()

    # -- Apoyo --

    def _aplicar_ahora(self, efecto, anunciar=True):
        estado = getattr(getattr(self._flujo, "sesion", None), "estado_partida", None)
        ahora = self._flujo.reloj.tiempo_absoluto()
        aviso = efectos_retardados.aplicar(efecto, estado, getattr(self._flujo, "game_state", None), ahora)
        if anunciar and callable(getattr(self._flujo, "_anunciar", None)):
            aviso["hora_texto"] = reloj_partida.texto_de(ahora)
            self._flujo._anunciar(aviso)
        return aviso

    def _avisar_telefono(self, texto):
        self.avisos_rectificar.append(texto)
        del self.avisos_rectificar[:-20]
        try:
            self._flujo.jugador_activo().telefono.notificar(texto)
        except (AttributeError, TypeError):
            pass

    # -- Guardado --

    def tiempo_a_dict(self):
        datos = self._flujo.tiempo_a_dict()
        datos["rectificar"] = self.rectificaciones.a_dict()
        return datos

    def restaurar_tiempo(self, datos):
        self._flujo.restaurar_tiempo(datos)
        crudo = datos.get("rectificar") if isinstance(datos, dict) else None
        self.avisos_rectificar = []
        if crudo is not None:
            try:
                self.rectificaciones = GestorRectificaciones.desde_dict(crudo, self._casos)
                return
            except (ValueError, KeyError, TypeError, AttributeError) as error:
                print(f"[rectificar] «rectificar» del guardado no se pudo leer ({error}); se empieza de cero",
                      file=sys.stderr)
        # Guardado anterior a Rectificar: no hay nada pendiente (solo nace de lo que se comparta desde ahora).
        self.rectificaciones = GestorRectificaciones(self._casos)

    def __getattr__(self, nombre):
        if nombre.startswith("__") or nombre in _PROPIOS:
            raise AttributeError(nombre)
        valor = getattr(self._flujo, nombre)
        # responder_dilema solo existe si hay dilemas: se intercepta aquí para no inventarlo cuando falta.
        if nombre == "responder_dilema" and callable(valor):
            return lambda opcion_id: self._responder_dilema(valor, opcion_id)
        return valor


# Lo que llama main.crear_flujo: envuelve `flujo` si la bandera está encendida, el flujo tiene reloj y los datos cargan.
# Si no, devuelve `flujo` tal cual (nunca puede impedir jugar).
def envolver(flujo, ruta=None):
    if not activo() or getattr(flujo, "reloj", None) is None or not callable(getattr(flujo, "avanzar_tiempo", None)):
        return flujo
    try:
        casos = cargar_casos(ruta)
    except ValueError as error:
        print(f"[rectificar] desactivado: {error}", file=sys.stderr)
        return flujo
    return FlujoConRectificar(flujo, casos)
