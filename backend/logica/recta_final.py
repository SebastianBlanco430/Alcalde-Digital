# Recta final de la partida (modelo PURO, sin ursina, serializable). En el último tramo de la partida cada decisión pesa
# más y lo que el equipo hizo antes vuelve como consecuencia. Todo se SUMA a lo que ya había: con la bandera apagada la
# partida es exactamente la de antes.
#
# TRAMO. progreso = máx(misiones completadas / catálogo, fracción del reloj de 7 días) (con el reloj la partida puede
# terminar por tiempo sin agotar el catálogo). La recta final es el último 30 %: progreso >= INICIO_RECTA (0,70).
#   nivel 1 (>= 0,70) -> decisiones ×1,2 · nivel 2 (>= 0,80) -> ×1,4 · nivel 3 (>= 0,90) -> ×1,6
#   Escalones (no una curva) para que el HUD muestre un número legible; con deltas de ±15 el máximo (±24) mueve mucho pero
#   no lleva la ciudad de 50 a 0/100 de un solo golpe.
#
# ECO (consecuencias acumuladas). En la recta, cada «compartir» arrastra los rumores que el equipo ya soltó:
#   desinformación += min(ECO_MAX_COMPARTIR, compartidas_previas // ECO_CADA); cada «reportar» aprovecha la red de
#   verificación que se fue armando: confianza += min(ECO_MAX_REPORTAR, reportadas_previas // ECO_CADA).
# EVENTO DE ENTRADA (una sola vez al entrar en la recta), según cómo jugó el equipo hasta entonces:
#   > 60 % compartir -> «Rumores acumulados» · > 60 % reportar -> «Red de verificadores» · si no -> «Ciudad en suspenso» (clave interna "vilo").
# MAZO PONDERADO. MazoPonderado ENVUELVE a cualquier mazo (MazoNoticias, MazoSembrado del cooperativo) sin tocarlo: en la
#   recta las noticias de gravedad alta (ArbolStats) salen más: peso = 1 + PESO_GRAVEDAD · intensidad · (gravedad/100)².
# DESENLACE al cerrar la partida (sobre los indicadores crudos, para que «tomada» dependa sobre todo de la desinformación):
#   tomada   desinformación >= 65, o desinformación >= 55 con confianza < 40
#   unida    convivencia >= 60, confianza >= 60 y desinformación <= 35
#   dividida el resto
#
# Uso:
#   controlador = ControladorRectaFinal(fuente_progreso)   # fuente_progreso() -> 0..1
#   deltas = controlador.ajustar(tipo, deltas_base, gravedad, noticia, estado)   # en EstadoPartida.decidir / coop
#   controlador.info()                                     # para el HUD
#   desenlace(indicadores, historial)                      # para la pantalla final
#   envolver(flujo)                                        # lo que llama main.crear_flujo (hot-seat)
#   preparar_coop(partida)                                 # lo que llama backend/red/servidor.py (anfitrión)
#
# BANDERAS (la variable de entorno manda sobre la constante):
#   RECTA_FINAL / ALCALDE_SIN_RECTA_FINAL=1      nada de esto: la partida queda exactamente como antes
#   MAZO_PONDERADO / ALCALDE_SIN_MAZO_PONDERADO=1    el mazo de siempre (sin preferir noticias graves)
#   ECO_DECISIONES / ALCALDE_SIN_ECO_DECISIONES=1    sin eco ni evento de entrada (solo el multiplicador)
#   DESENLACE / ALCALDE_SIN_DESENLACE=1              sin desenlace ni decisiones clave en el resumen final

import math
import os
import random
import sys

from backend.logica.estado_partida import NOMBRES_INDICADORES

RECTA_FINAL = True
MAZO_PONDERADO = True
ECO_DECISIONES = True
DESENLACE = True

INICIO_RECTA = 0.70
NIVELES = ((0.90, 3, 1.6), (0.80, 2, 1.4), (0.70, 1, 1.2))     # (progreso desde, nivel, multiplicador), de mayor a menor
MULTIPLICADOR_MAX = NIVELES[0][2]

ECO_CADA = 3
ECO_MAX_COMPARTIR = 4
ECO_MAX_REPORTAR = 3

UMBRAL_EVENTO = 0.6
EVENTOS_ENTRADA = {
    "rumores": ("Rumores acumulados",
                "Lo que se compartió sin verificar vuelve a circular: la recta final empieza cuesta arriba.",
                {"desinformacion": 5, "confianza": -3}),
    "verificadores": ("Red de verificadores",
                      "Los vecinos aprendieron a verificar contigo: la recta final empieza con apoyo.",
                      {"confianza": 5, "desinformacion": -3}),
    "vilo": ("Ciudad en suspenso",
             "La ciudad está atenta: desde ahora cada decisión pesa más.",
             {}),
}

PESO_GRAVEDAD = 3.0

DESENLACES = {
    "unida": ("Ciudad unida",
              "Ciudad Nova llega al final informada y con confianza: los rumores no lograron separarla."),
    "dividida": ("Ciudad dividida",
                 "Ciudad Nova sigue en pie, pero partida: cada barrio cree en una versión distinta de lo que pasó."),
    "tomada": ("Ciudad tomada por la desinformación",
               "Los rumores ganaron: nadie sabe ya qué es verdad y la desconfianza manda en Ciudad Nova."),
}
CLAVES_DESENLACE = tuple(DESENLACES)
MAX_CLAVES = 5              # decisiones de mayor impacto que se guardan
CLAVES_EN_PANTALLA = 3
LARGO_TEXTO = 46
ABREVIATURAS = {"convivencia": "conv.", "confianza": "conf.", "desinformacion": "desinf."}

_SI = ("1", "true", "si", "sí", "on")


def _variable(nombre):
    return os.environ.get(nombre, "").strip().lower() in _SI


def activo():
    return bool(RECTA_FINAL) and not _variable("ALCALDE_SIN_RECTA_FINAL")


def mazo_ponderado_activo():
    return activo() and bool(MAZO_PONDERADO) and not _variable("ALCALDE_SIN_MAZO_PONDERADO")


def eco_activo():
    return activo() and bool(ECO_DECISIONES) and not _variable("ALCALDE_SIN_ECO_DECISIONES")


def desenlace_activo():
    return activo() and bool(DESENLACE) and not _variable("ALCALDE_SIN_DESENLACE")


_avisados = set()


def _avisar_una_vez(clave, mensaje):
    if clave not in _avisados:
        _avisados.add(clave)
        print(mensaje, file=sys.stderr)


# -- Tramo --

def _fraccion(valor):
    try:
        valor = float(valor)
    except (TypeError, ValueError):
        return 0.0
    if math.isnan(valor):
        return 0.0
    return max(0.0, min(1.0, valor))


# Progreso 0..1 de la partida: el mayor entre las misiones completadas y la fracción del reloj (None = sin reloj).
def progreso(completadas, total, fraccion_reloj=None):
    por_misiones = _fraccion(completadas / total) if total and total > 0 else 0.0
    if fraccion_reloj is None:
        return por_misiones
    return max(por_misiones, _fraccion(fraccion_reloj))


# (en_recta, intensidad 0..1, nivel 0..3, multiplicador) para un progreso 0..1.
def estado_tramo(valor):
    valor = _fraccion(valor)
    if valor < INICIO_RECTA:
        return False, 0.0, 0, 1.0
    intensidad = min(1.0, (valor - INICIO_RECTA) / (1.0 - INICIO_RECTA))
    for desde, nivel, mult in NIVELES:
        if valor >= desde:
            return True, intensidad, nivel, mult
    return False, 0.0, 0, 1.0     # inalcanzable


def _redondear(valor):
    # alejándose de cero (round() de Python redondea al par: 2,5 -> 2)
    return int(math.floor(abs(valor) + 0.5)) * (1 if valor >= 0 else -1)


# Copia de `deltas` multiplicada: redondea alejándose de cero, conserva el signo y un delta distinto de cero nunca queda
# en 0. Con mult == 1 la copia es idéntica. Las claves que no son números se copian tal cual.
def escalar_deltas(deltas, mult):
    resultado = dict(deltas)
    if mult == 1:
        return resultado
    for clave, valor in deltas.items():
        if isinstance(valor, bool) or not isinstance(valor, (int, float)) or valor == 0:
            continue
        nuevo = _redondear(valor * mult)
        if nuevo == 0:
            nuevo = 1 if valor > 0 else -1
        resultado[clave] = nuevo
    return resultado


def sumar_deltas(a, b):
    resultado = dict(a)
    for clave, valor in b.items():
        resultado[clave] = resultado.get(clave, 0) + valor
    return resultado


# -- Historial de decisiones --

def _texto_corto(texto):
    texto = " ".join(str(texto or "").split())
    return texto if len(texto) <= LARGO_TEXTO else texto[:LARGO_TEXTO - 1].rstrip() + "…"


def _impacto(deltas):
    return sum(abs(v) for v in deltas.values() if isinstance(v, (int, float)) and not isinstance(v, bool))


class HistorialDecisiones:

    def __init__(self):
        self.compartir = 0
        self.reportar = 0
        self.compartir_recta = 0
        self.reportar_recta = 0
        self.claves = []            # dicts {id, texto, tipo, deltas, mult, recta}, de mayor a menor impacto

    def total(self):
        return self.compartir + self.reportar

    def fraccion_compartir(self):
        return self.compartir / self.total() if self.total() else 0.0

    def registrar(self, tipo, deltas, noticia=None, mult=1.0, en_recta=False):
        if tipo == "compartir":
            self.compartir += 1
            self.compartir_recta += 1 if en_recta else 0
        elif tipo == "reportar":
            self.reportar += 1
            self.reportar_recta += 1 if en_recta else 0
        else:
            return
        entrada = {
            "id": getattr(noticia, "id", None),
            "texto": _texto_corto(getattr(noticia, "texto", "")),
            "tipo": tipo,
            "deltas": {k: v for k, v in deltas.items() if k in NOMBRES_INDICADORES},
            "mult": float(mult),
            "recta": bool(en_recta),
        }
        self.claves.append(entrada)
        # estable: a igual impacto queda la más reciente delante (las de la recta pesan a la hora del desempate)
        self.claves.sort(key=lambda c: (_impacto(c["deltas"]), c["recta"]), reverse=True)
        del self.claves[MAX_CLAVES:]

    def a_dict(self):
        return {"compartir": self.compartir, "reportar": self.reportar, "compartir_recta": self.compartir_recta,
                "reportar_recta": self.reportar_recta, "claves": [dict(c, deltas=dict(c["deltas"])) for c in self.claves]}

    @classmethod
    def desde_dict(cls, datos):
        h = cls()
        datos = datos if isinstance(datos, dict) else {}
        for campo in ("compartir", "reportar", "compartir_recta", "reportar_recta"):
            valor = datos.get(campo, 0)
            setattr(h, campo, int(valor) if isinstance(valor, (int, float)) and not isinstance(valor, bool) else 0)
        claves = []
        for c in datos.get("claves") or ():
            if not isinstance(c, dict) or c.get("tipo") not in ("compartir", "reportar"):
                continue
            deltas = c.get("deltas") if isinstance(c.get("deltas"), dict) else {}
            claves.append({"id": c.get("id"), "texto": _texto_corto(c.get("texto", "")), "tipo": c["tipo"],
                           "deltas": {k: v for k, v in deltas.items() if k in NOMBRES_INDICADORES},
                           "mult": float(c.get("mult", 1.0) or 1.0), "recta": bool(c.get("recta", False))})
        h.claves = claves[:MAX_CLAVES]
        return h


# -- Eco y evento de entrada --

# Deltas extra del eco para una decisión EN LA RECTA según las decisiones anteriores ({} si no toca).
def eco(tipo, historial):
    if tipo == "compartir":
        extra = min(ECO_MAX_COMPARTIR, historial.compartir // ECO_CADA)
        return {"desinformacion": extra} if extra else {}
    if tipo == "reportar":
        extra = min(ECO_MAX_REPORTAR, historial.reportar // ECO_CADA)
        return {"confianza": extra} if extra else {}
    return {}


# Clave del evento de entrada según el historial: "rumores" | "verificadores" | "vilo".
def evento_entrada(historial):
    if historial.total() == 0:
        return "vilo"
    fraccion = historial.fraccion_compartir()
    if fraccion > UMBRAL_EVENTO:
        return "rumores"
    if (1.0 - fraccion) > UMBRAL_EVENTO:
        return "verificadores"
    return "vilo"


# -- Desenlace --

def clave_desenlace(indicadores):
    conv = float(indicadores.get("convivencia", 50))
    conf = float(indicadores.get("confianza", 50))
    desinfo = float(indicadores.get("desinformacion", 50))
    if desinfo >= 65 or (desinfo >= 55 and conf < 40):
        return "tomada"
    if conv >= 60 and conf >= 60 and desinfo <= 35:
        return "unida"
    return "dividida"


def texto_decision_clave(c):
    verbo = "Compartiste" if c["tipo"] == "compartir" else "Reportaste"
    partes = [f"{ABREVIATURAS.get(n, n)} {v:+d}" for n, v in c["deltas"].items() if v]
    sufijo = f" (×{c['mult']:.1f})".replace(".", ",") if c.get("mult", 1.0) != 1.0 else ""
    return f"{verbo} «{c['texto']}»: {', '.join(partes) or 'sin efecto'}{sufijo}"


# {clave, titulo, texto, decisiones_clave: [str], compartir, reportar} para la pantalla final.
def desenlace(indicadores, historial=None):
    historial = historial if historial is not None else HistorialDecisiones()
    clave = clave_desenlace(indicadores)
    titulo, texto = DESENLACES[clave]
    return {
        "clave": clave, "titulo": titulo, "texto": texto,
        "decisiones_clave": [texto_decision_clave(c) for c in historial.claves[:CLAVES_EN_PANTALLA]],
        "compartir": historial.compartir, "reportar": historial.reportar,
    }


SEPARADOR_CLAVES = " | "


# Texto plano (≤ 600 caracteres, una línea) de las decisiones clave, para el mensaje «fin» del cooperativo; el cliente lo
# separa con claves_de_texto.
def texto_claves(datos_desenlace, largo=600):
    texto = SEPARADOR_CLAVES.join(d.replace("|", "/") for d in (datos_desenlace.get("decisiones_clave") or ()))
    return texto[:largo]


def claves_de_texto(texto):
    return [t.strip() for t in str(texto or "").split(SEPARADOR_CLAVES.strip()) if t.strip()]


# -- Controlador (hot-seat y anfitrión cooperativo) --

class ControladorRectaFinal:

    def __init__(self, fuente_progreso, eco_on=None):
        self._fuente = fuente_progreso
        self.historial = HistorialDecisiones()
        self.entrada_hecha = False
        self.evento = None              # clave del evento de entrada aplicado (o None)
        self.decisiones = 0             # decisiones ajustadas (el HUD lo usa para el pulso)
        self.ultimo_eco = {}
        self.ultimo_mult = 1.0
        self._eco_on = eco_activo() if eco_on is None else bool(eco_on)

    def progreso(self):
        try:
            return _fraccion(self._fuente())
        except Exception as error:      # la recta final nunca debe tumbar la partida
            _avisar_una_vez("progreso", f"[recta_final] progreso no disponible: {error}")
            return 0.0

    def tramo(self):
        return estado_tramo(self.progreso())

    # Al entrar en la recta aplica (una vez) el evento de entrada a `estado` (EstadoPartida). Devuelve la clave del
    # evento si lo aplicó ahora, o None.
    def revisar_entrada(self, estado=None, en_recta=None):
        if self.entrada_hecha:
            return None
        if en_recta is None:
            en_recta = self.tramo()[0]
        if not en_recta:
            return None
        self.entrada_hecha = True
        if not self._eco_on:
            self.evento = "vilo"
            return self.evento
        self.evento = evento_entrada(self.historial)
        deltas = EVENTOS_ENTRADA[self.evento][2]     # con estado=None quien llama los suma a su decisión (ajustar)
        if deltas and estado is not None:
            estado.aplicar_deltas(deltas)
        return self.evento

    # Deltas finales de una decisión: multiplicador del tramo + eco; la registra en el historial. Si con esta decisión
    # se entra en la recta, los deltas del evento de entrada se SUMAN a los devueltos (así viajan en el «ind» del
    # cooperativo y en el lote como cualquier otro cambio); `estado` ya no se toca aquí.
    def ajustar(self, tipo, deltas_base, noticia=None, estado=None):
        en_recta, _intensidad, _nivel, mult = self.tramo()
        evento = self.revisar_entrada(None, en_recta)
        deltas = escalar_deltas(deltas_base, mult)
        extra = eco(tipo, self.historial) if (en_recta and self._eco_on) else {}
        if extra:
            deltas = sumar_deltas(deltas, extra)
        self.historial.registrar(tipo, deltas, noticia, mult, en_recta)
        if evento is not None and EVENTOS_ENTRADA[evento][2]:
            deltas = sumar_deltas(deltas, EVENTOS_ENTRADA[evento][2])
        self.decisiones += 1
        self.ultimo_eco = dict(extra)
        self.ultimo_mult = mult
        return deltas

    def info(self):
        en_recta, intensidad, nivel, mult = self.tramo()
        evento = self.evento
        return {"en_recta": en_recta, "intensidad": intensidad, "nivel": nivel, "mult": mult,
                "decisiones": self.decisiones, "eco": dict(self.ultimo_eco), "ultimo_mult": self.ultimo_mult,
                "evento": evento, "evento_titulo": EVENTOS_ENTRADA[evento][0] if evento else None,
                "evento_texto": EVENTOS_ENTRADA[evento][1] if evento else None}

    def a_dict(self):
        return {"historial": self.historial.a_dict(), "entrada_hecha": self.entrada_hecha, "evento": self.evento}

    def restaurar(self, datos):
        datos = datos if isinstance(datos, dict) else {}
        self.historial = HistorialDecisiones.desde_dict(datos.get("historial"))
        self.entrada_hecha = bool(datos.get("entrada_hecha", False))
        evento = datos.get("evento")
        self.evento = evento if evento in EVENTOS_ENTRADA else None

    @classmethod
    def desde_dict(cls, datos, fuente_progreso, eco_on=None):
        c = cls(fuente_progreso, eco_on=eco_on)
        c.restaurar(datos)
        return c


# -- Mazo ponderado --

# {id_noticia: gravedad} siguiendo el camino de cada noticia en el ArbolStats isomorfo (ids sin stats: gravedad 0).
def gravedades_por_id(arbol_noticias, arbol_stats):
    resultado = {}
    for nodo in arbol_noticias.recorrido_inorden():
        encontrado = arbol_noticias.buscar_con_camino(nodo.id)
        stats = arbol_stats.obtener_por_camino(encontrado[1]) if encontrado is not None else None
        resultado[nodo.id] = float(getattr(stats, "gravedad", 0) or 0)
    return resultado


def peso_gravedad(gravedad, intensidad):
    g = max(0.0, min(100.0, float(gravedad))) / 100.0
    return 1.0 + PESO_GRAVEDAD * max(0.0, min(1.0, intensidad)) * g * g


# Envuelve un mazo SIN modificarlo. Con intensidad 0 delega en mazo.siguiente() tal cual; con intensidad > 0 elige entre
# las pendientes de la ronda con peso por gravedad. `azar` necesita random() -> [0, 1).
class MazoPonderado:

    def __init__(self, mazo, gravedad_por_id, intensidad_fn, azar=None):
        self.__dict__["_mazo"] = mazo
        self.__dict__["_gravedad"] = dict(gravedad_por_id)
        self.__dict__["_intensidad_fn"] = intensidad_fn
        self.__dict__["_azar"] = azar if azar is not None else random

    # Atributos del mazo envuelto (ids_vistos, ids_disponibles, _ultimo_id, arbol_noticias...): lectura y escritura,
    # porque EstadoPartida.a_dict / restaurar los usan directamente.
    def __getattr__(self, nombre):
        if nombre.startswith("__"):
            raise AttributeError(nombre)
        return getattr(self.__dict__["_mazo"], nombre)

    def __setattr__(self, nombre, valor):
        setattr(self.__dict__["_mazo"], nombre, valor)

    @property
    def mazo_envuelto(self):
        return self.__dict__["_mazo"]

    def _intensidad(self):
        try:
            return _fraccion(self.__dict__["_intensidad_fn"]())
        except Exception as error:
            _avisar_una_vez("intensidad", f"[recta_final] intensidad no disponible: {error}")
            return 0.0

    def siguiente(self):
        mazo = self.__dict__["_mazo"]
        intensidad = self._intensidad()
        if intensidad <= 0.0 or not mazo.ids_disponibles:
            return mazo.siguiente()
        if not mazo.hay_pendientes():
            mazo.reiniciar()
        pendientes = [i for i in mazo.ids_disponibles if i not in mazo.ids_vistos]
        if len(pendientes) > 1 and mazo._ultimo_id in pendientes:
            pendientes.remove(mazo._ultimo_id)
        elegido = elegir_ponderado(pendientes, self.__dict__["_gravedad"], intensidad, self.__dict__["_azar"])
        nodo, camino = mazo.arbol_noticias.buscar_con_camino(elegido)
        mazo.ids_vistos.add(elegido)
        mazo._ultimo_id = elegido
        return nodo, camino


def elegir_ponderado(ids, gravedad_por_id, intensidad, azar):
    pesos = [peso_gravedad(gravedad_por_id.get(i, 0.0), intensidad) for i in ids]
    objetivo = azar.random() * sum(pesos)
    acumulado = 0.0
    for id_, peso in zip(ids, pesos):
        acumulado += peso
        if objetivo < acumulado:
            return id_
    return ids[-1]


# -- Enganche hot-seat: envoltorio del flujo (mismo patrón que consecuencia_graduada.envolver) --

_PROPIOS = ("_flujo", "recta_final", "_estado_rf")


class FlujoConRectaFinal:

    def __init__(self, flujo):
        self._flujo = flujo
        estado = flujo.sesion.estado_partida
        self._estado_rf = estado
        self.recta_final = ControladorRectaFinal(self._progreso)
        estado.recta_final = self.recta_final
        if mazo_ponderado_activo() and not isinstance(estado.mazo, MazoPonderado):
            estado.mazo = MazoPonderado(estado.mazo, gravedades_por_id(estado.arbol_noticias, estado.arbol_stats),
                                        lambda: self.recta_final.tramo()[1])

    def _progreso(self):
        flujo = self._flujo
        total = len(flujo.catalogo_misiones())
        hechas = len((flujo.misiones_a_dict() or {}).get("completadas") or ())
        reloj = getattr(flujo, "reloj", None)
        fraccion = reloj.fraccion_partida() if reloj is not None and hasattr(reloj, "fraccion_partida") else None
        return progreso(hechas, total, fraccion)

    def completar_mision(self, resultado):
        siguiente = self._flujo.completar_mision(resultado)
        self.recta_final.revisar_entrada(self._estado_rf)
        return siguiente

    # Desenlace (dict de desenlace()) con los indicadores de ahora; None si el desenlace está apagado. Existe aunque el
    # flujo no tenga resumen_final (sin reloj): la pantalla final lo lee de aquí.
    def desenlace_partida(self):
        if not desenlace_activo():
            return None
        return desenlace(self._estado_rf.indicadores(), self.recta_final.historial)

    def _con_desenlace(self, final):
        datos = self.desenlace_partida() if final is not None else None
        if datos is None:
            return final
        return dict(final, desenlace=datos, decisiones_clave=list(datos["decisiones_clave"]))

    def final_partida(self):
        leer = getattr(self._flujo, "final_partida", None)
        return self._con_desenlace(leer() if callable(leer) else None)

    def resumen_final(self):
        leer = getattr(self._flujo, "resumen_final", None)
        return self._con_desenlace(leer() if callable(leer) else None)

    def recta_final_a_dict(self):
        return self.recta_final.a_dict()

    def restaurar_recta_final(self, datos):
        self.recta_final.restaurar(datos)

    def __getattr__(self, nombre):
        if nombre.startswith("__") or nombre in _PROPIOS:
            raise AttributeError(nombre)
        return getattr(self._flujo, nombre)


# Lo que llama main.crear_flujo: devuelve el mismo flujo si la bandera está apagada o si el flujo no tiene sesión.
def envolver(flujo):
    if not activo():
        return flujo
    try:
        return FlujoConRectaFinal(flujo)
    except Exception as error:
        print(f"[recta_final] no se pudo activar ({error}); partida sin recta final", file=sys.stderr)
        return flujo


# -- Enganche cooperativo (anfitrión) --

# Deja en `partida` (PartidaCooperativa) el controlador y envuelve su mazo con el azar sembrado del MazoSembrado, así el
# mazo ponderado es determinista por semilla. Devuelve el controlador, o None si la bandera está apagada.
def preparar_coop(partida):
    if not activo():
        return None
    try:
        estado = partida.estado_partida

        def _progreso():
            return progreso(len(partida.reserva.completadas()), len(partida._catalogo))

        controlador = ControladorRectaFinal(_progreso)
        if mazo_ponderado_activo() and not isinstance(estado.mazo, MazoPonderado):
            azar = getattr(estado.mazo, "_rng", None)
            estado.mazo = MazoPonderado(estado.mazo, gravedades_por_id(estado.arbol_noticias, estado.arbol_stats),
                                        lambda: controlador.tramo()[1], azar=azar)
        partida.recta_final = controlador
        return controlador
    except Exception as error:
        print(f"[recta_final] cooperativo sin recta final ({error})", file=sys.stderr)
        return None


# Campos opcionales del mensaje «ind» (vacío si no hay controlador).
def campos_ind(controlador):
    if controlador is None:
        return {}
    _en, _int, nivel, mult = controlador.tramo()
    return {"mult": float(mult), "nivel": int(nivel)}


# Campos opcionales del mensaje «fin» (vacío si no hay controlador o el desenlace está apagado).
def campos_fin(controlador, indicadores):
    if controlador is None or not desenlace_activo():
        return {}
    datos = desenlace(indicadores, controlador.historial)
    return {"desenlace": datos["clave"], "claves": texto_claves(datos)}
