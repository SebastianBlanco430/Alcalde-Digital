# Hábitos digitales jugables (modelo puro, serializable, sin ursina): la BANDEJA DE CIVITAS (tecla L, ver
# frontend/registro_habitos.py). Tres mecánicas que se suman a los dilemas y a los minijuegos, cada una con su bandera:
#
#   ESTAFAS (ALCALDE_ESTAFAS)        un mensaje de premio, código, trabajo fácil o banco. El jugador MARCA lo sospechoso
#                                    (remitente, enlace, prisa, qué pide) y decide: seguirlo, ignorarlo o reportarlo. Caer
#                                    cuesta reales DE VERDAD (sale de la billetera) y al día siguiente usan tu cuenta para
#                                    engañar a tus vecinos. Reportar bien marcado protege al barrio. Hay mensajes legítimos:
#                                    reportarlo todo también es un error (falsa alarma).
#   PUBLICAR (ALCALDE_PUBLICAR_FOTO) una foto tuya para Civitas. El jugador MARCA lo que oculta (uniforme, número de casa,
#                                    ubicación, «casa sola») y decide publicar o no. Lo que quedó a la vista vuelve en 1-2
#                                    días como aviso de causa-efecto Y queda en `expuestos`: la próxima estafa te escribe
#                                    sabiendo ese dato (más creíble y más cara). La huella digital se paga más adelante.
#   TIEMPO DE PANTALLA               el feed de Civitas (L sin mensajes pendientes): cada publicación que se desliza gasta
#   (ALCALDE_TIEMPO_PANTALLA)        MINUTOS_POR_PUBLICACION de la semana y sube la fatiga; de vez en cuando trae una pista
#                                    útil de la misión (el anzuelo). Al empezar cada día se hace el balance del anterior:
#                                    mucho tiempo -> amaneces cansado y te perdiste algo del barrio; poco -> dormiste bien.
#
# Todo pasa por los sistemas de siempre: billetera y fatiga (perfil_economia), indicadores (EstadoPartida), confianza por
# grupo (GameState) y la cola de efectos retardados del FlujoConTiempo. El final por etapas se mueve solo, porque sale de
# indicadores y confianza. La pantalla nunca muestra números de indicadores: los textos cuentan lo que pasó.
#
# CALENDARIO. Publicar: días 1, 3 y 5 a las 11:00. Estafas: días 1..6 a las 16:00, en el orden del JSON. Un mensaje queda en
# la bandeja PLAZO_HORAS horas de juego; si se deja pasar cuenta como «ignorar» (una estafa ignorada no cuesta nada; un
# aviso real ignorado, un poco; una foto sin publicar, nada). Si hay uno abierto, el siguiente espera.
#
# API del envoltorio (el resto se delega al flujo que envuelve):
#   flujo.habitos                          GestorHabitos
#   flujo.evento_pendiente()               dict del mensaje abierto o None (para el panel)
#   flujo.responder_evento(marcas, decision) dict con lo que pasó y la revisión de cada elemento, o None
#   flujo.deslizar_feed()                  dict de la publicación del feed (o None si no hay feed / la semana terminó)
#   flujo.tiempo_pantalla_hoy()            minutos de feed del día de hoy
#   flujo.avisos_habitos                   textos enviados al teléfono (pruebas / depuración)
#   flujo.tiempo_a_dict() / restaurar_tiempo(datos)   clave OPCIONAL «habitos» en el guardado
# En línea no existe (el flujo en línea no pasa por aquí, igual que el reloj).

import json
import math
import os
import sys
from collections import namedtuple
from pathlib import Path

from backend.logica import efectos_retardados, reloj_partida

ESTAFAS = True
PUBLICAR_FOTO = True
TIEMPO_PANTALLA = True

RUTA_EVENTOS = Path(__file__).resolve().parent.parent / "datos" / "eventos_digitales.json"
VERSION = 1
MAX_TEXTO = 400

HORA_PUBLICAR = 11.0
DIAS_PUBLICAR = (1, 3, 5)
HORA_ESTAFA = 16.0
DIAS_ESTAFA = (1, 2, 3, 4, 5, 6)
PLAZO_HORAS = 9.0
IGNORAR = "ignorar"
DECISIONES_ESTAFA = ("seguir", IGNORAR, "reportar")
DECISIONES_PUBLICAR = ("publicar", "no_publicar")
FACTOR_PERSONAL = 1.5           # una estafa que sabe un dato tuyo pide más (y suena más creíble)
HORAS_CUENTA_ROBADA = 24.0
HORAS_BLOQUEADA = 24.0
HORAS_EXPUESTO = 24.0           # el primer dato expuesto vuelve en 24 h; cada siguiente, 12 h después
PASO_EXPUESTO = 12.0
MENSAJE_TELEFONO = "Civitas: {titulo}. Pulsa L para abrir la bandeja."

MINUTOS_POR_PUBLICACION = 12    # minutos de juego que se van en cada publicación del feed
FATIGA_POR_PUBLICACION = 2
CADA_PISTA = 4                  # cada tantas publicaciones, una trae una pista de la misión activa
LIMITE_ALTO = 120               # minutos de feed en un día desde los que se paga al día siguiente
LIMITE_SANO = 30                # hasta estos minutos, el día siguiente se amanece descansado
FATIGA_TRASNOCHE = 20
DESCANSO_SANO = 5

_VERSION = 1
_SI = ("1", "true", "si", "sí", "on")
_NO = ("0", "false", "no", "off")

# Publicaciones del feed que no traen pista: el «relleno» entretenido que se come los minutos.
FEED = (
    "Un video de un perro que baila samba. Lo ves dos veces.",
    "Alguien discute en los comentarios si la mejor coxinha es la de la Padaria o la de la feria.",
    "Fotos del atardecer desde el teleférico. Cuarenta casi iguales.",
    "Un reto de baile que ya hizo medio barrio. Te sale la música en la cabeza.",
    "Una encuesta: «¿Playa o cachoeira?». Votas y miras los resultados.",
    "Un tutorial de trenzas de tres minutos que ves entero.",
    "Memes del partido de ayer. Te ríes con uno y sigues bajando.",
    "La tía de alguien comparte una receta de bolo de fubá con veinte fotos.",
    "Un clip de la batería de la escola de samba ensayando. Suena muy bien.",
    "Un «¿sabías que…?» sin fuente sobre el agua del morro. No lo compartes.",
)

Elemento = namedtuple("Elemento", "id texto marcar explicacion dato retardado")    # marcar: lo correcto es marcarlo
Evento = namedtuple("Evento", "tipo id titulo remitente texto legitimo monto etiquetas elementos")
Plan = namedtuple("Plan", "texto deltas confianza perdida retardados expuestos")     # retardados: [(en_horas_abs, Efecto)]
Oferta = namedtuple("Oferta", "tipo id desde hasta")


def _bandera(nombre, constante):
    valor = os.environ.get(nombre, "").strip().lower()
    if valor in _SI:
        return True
    if valor in _NO:
        return False
    return bool(constante)


def estafas_activas():
    return _bandera("ALCALDE_ESTAFAS", ESTAFAS)


def publicar_activo():
    return _bandera("ALCALDE_PUBLICAR_FOTO", PUBLICAR_FOTO)


def tiempo_pantalla_activo():
    return _bandera("ALCALDE_TIEMPO_PANTALLA", TIEMPO_PANTALLA)


def activo():
    """¿Hay alguna de las tres mecánicas encendida? (se lee en cada llamada)"""
    return estafas_activas() or publicar_activo() or tiempo_pantalla_activo()


# -- Datos ------------------------------------------------------------------------------------------------------------

def _texto(valor, nombre):
    if not isinstance(valor, str) or not valor.strip():
        raise ValueError(f"{nombre}: falta el texto.")
    if len(valor.strip()) > MAX_TEXTO:
        raise ValueError(f"{nombre}: el texto pasa de {MAX_TEXTO} caracteres.")
    return valor.strip()


def _elemento(crudo, nombre, clave_marcar):
    if not isinstance(crudo, dict):
        raise ValueError(f"{nombre}: se esperaba un objeto.")
    ident = _texto(crudo.get("id"), f"{nombre}.id")
    marcar = crudo.get(clave_marcar)
    if not isinstance(marcar, bool):
        raise ValueError(f"{nombre}/{ident}: «{clave_marcar}» debe ser true o false.")
    retardado = crudo.get("retardado")
    if retardado is not None and retardado.count("{cuando}") != 1:
        raise ValueError(f"{nombre}/{ident}: el retardado necesita un único {{cuando}}.")
    return Elemento(ident, _texto(crudo.get("texto"), f"{nombre}/{ident}.texto"), marcar,
                    _texto(crudo.get("explicacion"), f"{nombre}/{ident}.explicacion"),
                    str(crudo.get("dato") or ""), retardado)


def _evento(crudo, tipo):
    if not isinstance(crudo, dict):
        raise ValueError(f"Un evento de {tipo} debe ser un objeto.")
    ident = _texto(crudo.get("id"), f"{tipo}.id")
    clave = "sospechoso" if tipo == "estafa" else "sensible"
    elementos = tuple(_elemento(e, ident, clave) for e in crudo.get("elementos") or ())
    if not 2 <= len(elementos) <= 6:
        raise ValueError(f"{ident}: debe tener de 2 a 6 elementos.")
    if len({e.id for e in elementos}) != len(elementos):
        raise ValueError(f"{ident}: ids de elemento repetidos.")
    if tipo == "estafa":
        etiquetas = crudo.get("etiquetas") or {}
        if set(etiquetas) != set(DECISIONES_ESTAFA):
            raise ValueError(f"{ident}: «etiquetas» debe traer {DECISIONES_ESTAFA}.")
        monto = crudo.get("monto", 0)
        if isinstance(monto, bool) or not isinstance(monto, int) or not 0 <= monto <= 100:
            raise ValueError(f"{ident}: monto inválido.")
        return Evento(tipo, ident, _texto(crudo.get("titulo"), f"{ident}.titulo"),
                      _texto(crudo.get("remitente"), f"{ident}.remitente"), _texto(crudo.get("mensaje"), f"{ident}.mensaje"),
                      bool(crudo.get("legitimo")), monto, {k: _texto(v, f"{ident}.{k}") for k, v in etiquetas.items()},
                      elementos)
    if any(e.marcar and (not e.dato or not e.retardado) for e in elementos):
        raise ValueError(f"{ident}: cada elemento sensible necesita «dato» y «retardado».")
    return Evento(tipo, ident, _texto(crudo.get("titulo"), f"{ident}.titulo"), "Tu publicación",
                  _texto(crudo.get("descripcion"), f"{ident}.descripcion"), True, 0,
                  {"publicar": "Publicar con lo marcado tapado", "no_publicar": "No publicarla"}, elementos)


def cargar_eventos(ruta=None):
    """(estafas, publicaciones) del JSON, como tuplas de Evento. ValueError si el archivo no existe o algo no cuadra."""
    ruta = Path(ruta) if ruta is not None else RUTA_EVENTOS
    try:
        datos = json.loads(ruta.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise ValueError(f"{ruta.name}: el archivo no existe.") from None
    except json.JSONDecodeError as error:
        raise ValueError(f"{ruta.name}: JSON inválido (línea {error.lineno}): {error.msg}") from None
    if not isinstance(datos, dict) or datos.get("version") != VERSION:
        raise ValueError(f"{ruta.name}: formato desconocido (se esperaba version {VERSION}).")
    estafas = tuple(_evento(e, "estafa") for e in datos.get("estafas") or ())
    publicaciones = tuple(_evento(e, "publicar") for e in datos.get("publicaciones") or ())
    ids = [e.id for e in estafas + publicaciones]
    if len(set(ids)) != len(ids):
        raise ValueError(f"{ruta.name}: ids de evento repetidos.")
    return estafas, publicaciones


# -- Calificación y consecuencias (puras) -----------------------------------------------------------------------------

# Versión de una estafa que sabe un dato que publicaste: más creíble (un elemento más que delata) y más cara.
def personalizar(evento, expuestos):
    if evento.tipo != "estafa" or evento.legitimo or not expuestos:
        return evento
    dato = expuestos[-1]
    extra = Elemento("personal", f"Sabe {dato}", True,
                     f"Lo sacaron de lo que publicaste: los estafadores leen tus fotos para sonar creíbles ({dato}).", dato, None)
    monto = int(round(evento.monto * FACTOR_PERSONAL))
    # el importe que se lee en el mensaje es el que se cobra
    texto = evento.texto.replace(f"R$ {evento.monto} ", f"R$ {monto} ") if evento.monto else evento.texto
    return evento._replace(texto=f"(Te escriben por tu nombre y saben {dato}.) {texto}", monto=monto,
                           elementos=evento.elementos + (extra,))


# Revisión de las marcas: [(elemento, marcado, acertado)] y la calidad 0..1 (fracción de elementos bien juzgados).
def calificar(evento, marcas):
    marcas = set(marcas or ())
    revision = [(e, e.id in marcas, (e.id in marcas) == e.marcar) for e in evento.elementos]
    calidad = sum(1 for _, _, ok in revision if ok) / len(revision) if revision else 0.0
    return revision, calidad


def _efecto(clave, mensaje, deltas, confianza, evento):
    return efectos_retardados.crear_efecto(clave, mensaje, deltas, confianza, f"habito:{evento.id}")


def _escalar(tabla, factor):
    return {k: round(v * factor, 2) for k, v in tabla.items()}


def plan_estafa(evento, marcas, decision, ahora, saldo=0):
    """Lo que pasa al decidir sobre un mensaje (estafa o legítimo). `saldo`: reales en la billetera (tope de la pérdida)."""
    if decision not in DECISIONES_ESTAFA:
        raise ValueError(f"Decisión desconocida: {decision!r}.")
    _, calidad = calificar(evento, marcas)
    cuando = efectos_retardados._cuando
    if evento.legitimo:
        if decision == "seguir":
            return Plan("Era un mensaje de verdad: lo comprobaste y respondiste por el canal correcto.",
                        {"convivencia": 2}, {"ciudadanos": 1}, min(evento.monto, max(0, saldo)), [], [])
        if decision == "reportar":
            return Plan("Reportaste un mensaje real: tuvieron que explicar a todo el barrio que no era una estafa.",
                        {"convivencia": -1}, {"instituciones": -1}, 0, [], [])
        return Plan("No contestaste. Era un aviso real y te lo perdiste.", {"convivencia": -1}, {}, 0, [], [])
    if decision == "seguir":
        perdida = min(evento.monto, max(0, saldo))
        texto = (f"Pagaste R$ {perdida}. No llega nada y el número ya no contesta." if evento.monto > 0 else
                 "Mandaste el código: en un minuto te sacaron de tu propia cuenta.")
        mensaje = (f"{cuando(HORAS_CUENTA_ROBADA)} caíste en «{evento.titulo}»: con tu cuenta mandaron el mismo engaño a "
                   f"tus contactos y dos vecinos también cayeron.")
        retardado = (ahora + HORAS_CUENTA_ROBADA, _efecto(
            "cuenta_robada", mensaje, {"desinformacion": 3, "confianza": -2}, {"ciudadanos": -2}, evento))
        return Plan(texto, {}, {}, perdida, [retardado], [])
    if decision == "reportar":
        factor = 0.5 + 0.5 * calidad              # reportar sabiendo por qué ayuda más (la revisión lo explica)
        mensaje = (f"{cuando(HORAS_BLOQUEADA)} reportaste «{evento.titulo}»: Civitas bloqueó la cuenta y avisó al barrio. "
                   f"Dos vecinas no cayeron gracias a ti.")
        retardado = (ahora + HORAS_BLOQUEADA, _efecto(
            "estafa_bloqueada", mensaje, _escalar({"desinformacion": -2, "confianza": 2}, factor),
            _escalar({"ciudadanos": 1}, factor), evento))
        return Plan("Reportado. Civitas revisa el perfil.", {}, _escalar({"policia": 2}, factor), 0, [retardado], [])
    return Plan("Lo dejaste pasar: no perdiste nada, pero el mensaje sigue circulando por el barrio.", {}, {}, 0, [], [])


def plan_publicacion(evento, marcas, decision, ahora):
    """Lo que pasa al decidir sobre una foto. Lo sensible que quedó a la vista vuelve como aviso y queda en `expuestos`."""
    if decision not in DECISIONES_PUBLICAR:
        raise ValueError(f"Decisión desconocida: {decision!r}.")
    if decision == "no_publicar":
        return Plan("No la publicaste: nadie se enteró del momento, pero tampoco expusiste a nadie.", {}, {}, 0, [], [])
    marcas = set(marcas or ())
    a_la_vista = [e for e in evento.elementos if e.marcar and e.id not in marcas]
    de_mas = [e for e in evento.elementos if not e.marcar and e.id in marcas]
    retardados = []
    for i, e in enumerate(a_la_vista):
        horas = HORAS_EXPUESTO + PASO_EXPUESTO * i
        retardados.append((ahora + horas, _efecto(
            f"expuesto_{evento.id}_{e.id}", e.retardado.format(cuando=efectos_retardados._cuando(horas)),
            {"convivencia": -2, "confianza": -1}, {"ciudadanos": -1}, evento)))
    if not a_la_vista:
        texto = "Publicada sin regalar datos: muchas reacciones y nada que lamentar."
        confianza = {"ciudadanos": 1}
    else:
        texto = "Publicada: llueven las reacciones."
        confianza = {}
    if de_mas:
        texto += " Tapaste de más y la foto perdió gracia."
    return Plan(texto, {"convivencia": 1 if de_mas else 2}, confianza, 0, retardados, [e.dato for e in a_la_vista])


# Balance de un día de feed: (texto, deltas, cambio de fatiga) o None si no corresponde nada.
def balance_pantalla(minutos):
    if minutos >= LIMITE_ALTO:
        horas = minutos / 60
        return (f"Ayer pasaste {horas:.1f} horas deslizando Civitas: hoy amaneces cansado y te perdiste la charla del barrio."
                .replace(".", ",", 1), {"convivencia": -2}, FATIGA_TRASNOCHE)
    if minutos <= LIMITE_SANO:
        return ("Ayer usaste Civitas con medida: dormiste bien y amaneces con energía.", {}, -DESCANSO_SANO)
    return None


# -- Gestor (estado puro) ---------------------------------------------------------------------------------------------

def _hora(valor, nombre="ahora"):
    if isinstance(valor, bool) or not isinstance(valor, (int, float)) or not math.isfinite(valor):
        raise ValueError(f"{nombre} inválido: {valor!r}; se esperaba un número finito de horas.")
    return float(valor)


class GestorHabitos:

    def __init__(self, estafas, publicaciones, plazo=PLAZO_HORAS):
        self._estafas = tuple(estafas) if estafas_activas() else ()
        self._publicaciones = tuple(publicaciones) if publicar_activo() else ()
        self._por_id = {e.id: e for e in tuple(estafas) + tuple(publicaciones)}
        self._plazo = max(0.0, _hora(plazo, "plazo"))
        self._usados = 0                  # entradas del calendario ya intentadas
        self._oferta = None               # Oferta abierta
        self._respuestas = {}             # id -> decisión (o IGNORAR si venció)
        self.expuestos = []               # datos que el jugador dejó a la vista al publicar (los usan las estafas)
        self.minutos_por_dia = {}         # día -> minutos de feed
        self.publicaciones_vistas = 0
        self.dia_balance = 1              # último día cuyo comienzo ya hizo el balance del anterior

    def calendario(self):
        """[(hora_abs, tipo, id)] ordenado: publicaciones a las 11:00 de los días impares, estafas a las 16:00."""
        entradas = []
        for dia, evento in zip(DIAS_PUBLICAR, self._publicaciones):
            entradas.append(((dia - 1) * 24.0 + HORA_PUBLICAR, "publicar", evento.id))
        for dia, evento in zip(DIAS_ESTAFA, self._estafas):
            entradas.append(((dia - 1) * 24.0 + HORA_ESTAFA, "estafa", evento.id))
        return sorted(entradas)

    def oferta(self):
        return self._oferta

    def evento(self, ident):
        return self._por_id.get(ident)

    def respuestas(self):
        return dict(self._respuestas)

    # Avanza a `ahora`: vence la oferta abierta si pasó su plazo y abre la siguiente que ya tocó. Devuelve los cambios
    # [("ofrecido" | "vencido", Evento)] en orden.
    def avanzar(self, ahora):
        ahora = _hora(ahora)
        cambios = []
        if self._oferta is not None and ahora >= self._oferta.hasta:
            vencida = self._oferta
            self._respuestas[vencida.id] = IGNORAR
            self._oferta = None
            cambios.append(("vencido", self._por_id[vencida.id]))
        calendario = self.calendario()
        while self._oferta is None and self._usados < len(calendario) and calendario[self._usados][0] <= ahora:
            hora, tipo, ident = calendario[self._usados]
            self._usados += 1
            if ident in self._respuestas:
                continue
            desde = max(hora, ahora)
            self._oferta = Oferta(tipo, ident, desde, desde + self._plazo)
            cambios.append(("ofrecido", self._por_id[ident]))
        return cambios

    # El evento abierto tal como se juega ahora (las estafas, personalizadas con lo que publicaste).
    def evento_abierto(self):
        if self._oferta is None:
            return None
        return personalizar(self._por_id[self._oferta.id], self.expuestos)

    def cerrar_oferta(self, decision):
        if self._oferta is None:
            return None
        oferta, self._oferta = self._oferta, None
        self._respuestas[oferta.id] = decision
        return oferta

    def sumar_minutos(self, dia, minutos):
        self.minutos_por_dia[int(dia)] = self.minutos_por_dia.get(int(dia), 0) + int(minutos)

    # -- Guardado --

    def a_dict(self):
        oferta = None if self._oferta is None else {"tipo": self._oferta.tipo, "id": self._oferta.id,
                                                     "desde": self._oferta.desde, "hasta": self._oferta.hasta}
        return {"version": _VERSION, "usados": self._usados, "oferta": oferta, "respuestas": dict(self._respuestas),
                "expuestos": list(self.expuestos), "minutos": {str(k): v for k, v in self.minutos_por_dia.items()},
                "vistas": self.publicaciones_vistas, "dia_balance": self.dia_balance}

    @classmethod
    def desde_dict(cls, datos, estafas, publicaciones):
        if not isinstance(datos, dict) or datos.get("version") != _VERSION:
            raise ValueError("hábitos: formato desconocido")
        gestor = cls(estafas, publicaciones)
        gestor._usados = max(0, min(int(datos.get("usados", 0)), len(gestor.calendario())))
        gestor._respuestas = {str(k): str(v) for k, v in (datos.get("respuestas") or {}).items()
                              if k in gestor._por_id}
        gestor.expuestos = [str(d)[:60] for d in (datos.get("expuestos") or ())][-10:]
        gestor.minutos_por_dia = {int(k): max(0, int(v)) for k, v in (datos.get("minutos") or {}).items()}
        gestor.publicaciones_vistas = max(0, int(datos.get("vistas", 0)))
        gestor.dia_balance = max(1, int(datos.get("dia_balance", 1)))
        crudo = datos.get("oferta")
        if isinstance(crudo, dict) and crudo.get("id") in gestor._por_id:
            gestor._oferta = Oferta(str(crudo.get("tipo")), crudo["id"], _hora(crudo["desde"], "desde"),
                                    _hora(crudo["hasta"], "hasta"))
        return gestor


# -- Envoltorio del flujo ---------------------------------------------------------------------------------------------

_PROPIOS = ("_flujo", "habitos", "avisos_habitos", "_cargados")


class FlujoConHabitos:

    # `flujo`: FlujoConTiempo (o algo que lo envuelve, como FlujoConDilemas): necesita reloj; la cola de efectos, el
    # GameState y la economía se usan si están.
    def __init__(self, flujo, estafas, publicaciones):
        self._flujo = flujo
        self._cargados = (tuple(estafas), tuple(publicaciones))
        self.habitos = GestorHabitos(*self._cargados)
        self.avisos_habitos = []

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
        for tipo, evento in self.habitos.avanzar(reloj.tiempo_absoluto()):
            if tipo == "ofrecido":
                self._avisar_telefono(MENSAJE_TELEFONO.format(titulo=evento.titulo))
            elif tipo == "vencido":
                self._aplicar_plan(evento, self._plan(evento, (), IGNORAR if evento.tipo == "estafa" else "no_publicar"))
        if tiempo_pantalla_activo():
            self._balance_del_dia(reloj.dia())

    def _balance_del_dia(self, dia):
        while self.habitos.dia_balance < dia:
            anterior = self.habitos.dia_balance
            self.habitos.dia_balance += 1
            balance = balance_pantalla(self.habitos.minutos_por_dia.get(anterior, 0))
            if balance is None:
                continue
            texto, deltas, fatiga = balance
            self._cambiar_fatiga(fatiga)
            self._aplicar_ahora(efectos_retardados.crear_efecto("pantalla", texto, deltas, {}, "habito:pantalla"))

    # -- Mensajes de la bandeja --

    def evento_pendiente(self):
        if self._flujo.partida_terminada():
            return None
        evento = self.habitos.evento_abierto()
        if evento is None:
            return None
        oferta = self.habitos.oferta()
        decisiones = DECISIONES_ESTAFA if evento.tipo == "estafa" else DECISIONES_PUBLICAR
        return {"tipo": evento.tipo, "id": evento.id, "titulo": evento.titulo, "remitente": evento.remitente,
                "texto": evento.texto, "hasta_texto": reloj_partida.texto_de(oferta.hasta),
                "elementos": [{"id": e.id, "texto": e.texto} for e in evento.elementos],
                "opciones": [{"id": d, "etiqueta": evento.etiquetas[d]} for d in decisiones]}

    def responder_evento(self, marcas, decision):
        if self._flujo.reloj.terminado() or self._flujo.partida_terminada():
            return None
        evento = self.habitos.evento_abierto()
        validas = DECISIONES_ESTAFA if evento is not None and evento.tipo == "estafa" else DECISIONES_PUBLICAR
        if evento is None or decision not in validas:
            return None
        plan = self._plan(evento, marcas, decision)
        self.habitos.cerrar_oferta(decision)
        perdida = self._aplicar_plan(evento, plan)
        revision, calidad = calificar(evento, marcas)
        aislamiento = getattr(self._flujo, "aislamiento", None)
        if aislamiento is not None:
            aislamiento.participar(self._flujo.reloj.tiempo_absoluto())       # decidir es participar
        return {"tipo": evento.tipo, "id": evento.id, "titulo": evento.titulo, "decision": decision, "texto": plan.texto,
                "perdida": perdida, "calidad": round(calidad, 2), "llega": bool(plan.retardados),
                "revision": [{"texto": e.texto, "marcado": marcado, "acertado": ok, "explicacion": e.explicacion,
                              "debia_marcarse": e.marcar} for e, marcado, ok in revision]}

    def _plan(self, evento, marcas, decision):
        ahora = self._flujo.reloj.tiempo_absoluto()
        if evento.tipo == "estafa":
            return plan_estafa(evento, marcas, decision, ahora, self._saldo())
        return plan_publicacion(evento, marcas, decision, ahora)

    # Aplica un plan: dinero, efecto inmediato, retardados y datos expuestos. Devuelve los reales que se perdieron.
    def _aplicar_plan(self, evento, plan):
        perdida = 0
        if plan.perdida > 0:
            perfil = self._perfil()
            if perfil is not None and perfil.inventario.cobrar(plan.perdida).ok:
                concepto = f"Rifa: {evento.titulo}" if evento.legitimo else f"Estafa: {evento.titulo}"
                perfil.registrar(concepto, -plan.perdida)
                perdida = plan.perdida
        if plan.deltas or plan.confianza:
            self._aplicar_ahora(_efecto(f"habito_{evento.id}", plan.texto, plan.deltas, plan.confianza, evento), anunciar=False)
        cola = getattr(self._flujo, "cola_efectos", None)
        for en_horas, efecto in plan.retardados:
            if cola is not None:
                try:        # una consecuencia mal formada nunca puede romper el reloj
                    cola.programar(en_horas, efecto)
                except ValueError as error:
                    print(f"[habitos] consecuencia no programada: {error}", file=sys.stderr)
        for dato in plan.expuestos:
            if dato not in self.habitos.expuestos:
                self.habitos.expuestos.append(dato)
        return perdida

    # Aplica un efecto YA (indicadores y confianza, queda en el ArbolImpactos); con `anunciar` sale por los avisos.
    def _aplicar_ahora(self, efecto, anunciar=True):
        estado = getattr(getattr(self._flujo, "sesion", None), "estado_partida", None)
        ahora = self._flujo.reloj.tiempo_absoluto()
        aviso = efectos_retardados.aplicar(efecto, estado, getattr(self._flujo, "game_state", None), ahora)
        if anunciar and callable(getattr(self._flujo, "_anunciar", None)):
            aviso["hora_texto"] = reloj_partida.texto_de(ahora)
            self._flujo._anunciar(aviso)
        return aviso

    # -- Feed (tiempo de pantalla) --

    def deslizar_feed(self):
        """Una publicación más del feed: gasta minutos de la semana y fatiga; cada CADA_PISTA, una pista de la misión."""
        if not tiempo_pantalla_activo() or self._flujo.reloj.terminado() or self._flujo.partida_terminada():
            return None
        reloj = self._flujo.reloj
        dia = reloj.dia()
        self.habitos.publicaciones_vistas += 1
        n = self.habitos.publicaciones_vistas
        texto, pista = FEED[(n - 1) % len(FEED)], False
        mision = self._flujo.mision_actual() if callable(getattr(self._flujo, "mision_actual", None)) else None
        if n % CADA_PISTA == 0 and getattr(mision, "pista", None):
            texto, pista = f"Un vecino comenta sobre «{mision.titulo}»: {mision.pista}", True
        # El panel abierto pausa el reloj: se reanuda un instante para que el tiempo del feed se cobre de verdad.
        en_pausa = reloj.en_pausa()
        reloj.reanudar()
        self.avanzar_horas(MINUTOS_POR_PUBLICACION / 60.0)
        if en_pausa:
            reloj.pausar()
        self.habitos.sumar_minutos(dia, MINUTOS_POR_PUBLICACION)
        self._cambiar_fatiga(FATIGA_POR_PUBLICACION)
        return {"texto": texto, "pista": pista, "minutos_hoy": self.tiempo_pantalla_hoy(), "hora_texto": reloj.hora_texto()}

    def tiempo_pantalla_hoy(self):
        return self.habitos.minutos_por_dia.get(self._flujo.reloj.dia(), 0)

    # -- Apoyo --

    def _perfil(self):
        try:
            from backend.logica.perfil_economia import perfil_de
            return perfil_de(self._flujo.jugador_activo())
        except (AttributeError, TypeError):
            return None

    def _saldo(self):
        perfil = self._perfil()
        return perfil.inventario.saldo() if perfil is not None else 0

    def _cambiar_fatiga(self, cambio):
        from backend.logica.perfil_economia import FATIGA_MAX
        perfil = self._perfil()
        if perfil is not None:
            perfil.fatiga = max(0, min(FATIGA_MAX, perfil.fatiga + int(cambio)))

    def _avisar_telefono(self, texto):
        self.avisos_habitos.append(texto)
        del self.avisos_habitos[:-20]
        try:
            self._flujo.jugador_activo().telefono.notificar(texto)
        except (AttributeError, TypeError):
            pass

    # -- Guardado --

    def tiempo_a_dict(self):
        datos = self._flujo.tiempo_a_dict()
        datos["habitos"] = self.habitos.a_dict()
        return datos

    def restaurar_tiempo(self, datos):
        self._flujo.restaurar_tiempo(datos)
        crudo = datos.get("habitos") if isinstance(datos, dict) else None
        self.avisos_habitos = []
        if crudo is not None:
            try:
                self.habitos = GestorHabitos.desde_dict(crudo, *self._cargados)
                return
            except (ValueError, KeyError, TypeError, AttributeError) as error:
                print(f"[habitos] «habitos» del guardado no se pudo leer ({error}); se empieza de cero", file=sys.stderr)
        # Guardado anterior a los hábitos: no se cobra lo que nunca pudo ver (como dilemas.saltar_hasta).
        self.habitos = GestorHabitos(*self._cargados)
        ahora = self._flujo.reloj.tiempo_absoluto()
        self.habitos._usados = sum(1 for hora, _t, _i in self.habitos.calendario() if hora <= ahora)
        self.habitos.dia_balance = self._flujo.reloj.dia()

    def __getattr__(self, nombre):
        if nombre.startswith("__") or nombre in _PROPIOS:
            raise AttributeError(nombre)
        return getattr(self._flujo, nombre)


# Lo que llama main.crear_flujo: envuelve `flujo` si alguna mecánica está encendida, el flujo tiene reloj y los datos
# cargan. Si no, devuelve `flujo` tal cual (nunca puede impedir jugar).
def envolver(flujo, ruta=None):
    if not activo() or getattr(flujo, "reloj", None) is None or not callable(getattr(flujo, "avanzar_tiempo", None)):
        return flujo
    try:
        estafas, publicaciones = cargar_eventos(ruta)
    except ValueError as error:
        print(f"[habitos] desactivados: {error}", file=sys.stderr)
        return flujo
    return FlujoConHabitos(flujo, estafas, publicaciones)
