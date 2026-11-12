# Ambiente de la ciudad (modelo puro, sin ursina): el EJE de los puntos 3 a 6 del plan final (docs/PLAN_FINAL.md). Traduce
# los indicadores de la partida a «cómo se ve y cómo se comporta la ciudad»: cuánta gente hay en la calle, si conversa o
# va pegada al celular, lo limpias que están las plazas, la luz... Los demás módulos (multitud, NPC, plazas, iluminación,
# HUD) SOLO leen de aquí; ninguno vuelve a interpretar los indicadores por su cuenta.
#
# No toca NOMBRES_INDICADORES ni el protocolo en línea: bienestar y conflictos son DERIVADOS (se recalculan, no se guardan
# como indicadores ni viajan por la red). En línea basta con los tres indicadores que ya viajan.
#
# ENTRADAS
#   indicadores  {"convivencia", "confianza", "desinformacion"}: 0-100 (EstadoPartida.indicadores())
#   confianzas   opcional, {"policia", "ciudadanos", "instituciones"}: 0-100 (GameState.confianzas()); None sin GameState
#
# DERIVADOS (0-100; fórmulas)
#   confianza_efectiva = confianza                                       sin GameState
#                      = 0,5 * confianza + 0,5 * promedio(grupos)        con GameState
#   bienestar_digital  = 0,40 * convivencia + 0,35 * confianza_efectiva + 0,25 * (100 - desinformacion)
#   conflictos         = 0,50 * desinformacion + 0,35 * (100 - convivencia) + 0,15 * (100 - confianza_efectiva)
#   Con todo en 50 (inicio de partida) ambos valen 50.
#
# AMBIENTE (inmutable; todos los factores 0..1)
#   salud             = (bienestar - conflictos + 100) / 200          0 = ciudad rota, 0,5 = inicio, 1 = ciudad plena
#   sociabilidad      = 0,02 + 0,90 * salud^1,5                       fracción de gente abierta a conversar
#   neutro (implícito)= 0,06 + 0,30 * (1 - |2*salud - 1|)             gente que va a lo suyo (máximo a media salud)
#   el resto (1 - sociabilidad - neutro) se reparte entre tres malestares según su peso:
#     aislamiento        peso 0,2 + (100 - convivencia) / 100         evita a la gente
#     pegado_al_celular  peso 0,2 + desinformacion / 100              camina mirando la pantalla
#     enojo              peso 0,2 + conflictos / 100                  crispado, discute
#   sociabilidad + neutro + aislamiento + pegado_al_celular + enojo = 1 (son las probabilidades de perfil_npc).
#   nivel             'florece' (salud >= 0,75) · 'sano' (>= 0,50) · 'tenso' (>= 0,25) · 'apagado'; con HISTÉRESIS: para
#                     cambiar de nivel la salud tiene que salir de la banda del nivel actual por más de HISTERESIS_NIVEL
#                     (0,04), así un valor que tiembla en el umbral no hace parpadear la ciudad.
#
# API
#   derivar(indicadores, confianzas=None)                 -> {"bienestar": x, "conflictos": y}
#   calcular_ambiente(indicadores, confianzas=None, nivel_anterior=None) -> Ambiente
#   densidad_poblacion(amb)   -> 0,35..1,0   factor de NPC en espacios públicos (multiplica la densidad de la multitud)
#   limpieza(amb)             -> 0..1        1 = plazas limpias; 0 = basura y pintadas
#   actividad_plazas(amb)     -> 0..1        cuánta vida hay en las plazas (corros, música, juego)
#   luz_ambiente(amb)         -> {"tinte": (r, g, b), "saturacion": s, "brillo": b}   factores multiplicativos de la luz
#   probabilidades_npc(amb)   -> {estado: probabilidad} de los 5 estados (suman 1)
#   perfil_npc(semilla_npc, amb) -> PerfilNPC(estado, manilla)   estado emocional determinista de UN NPC
#   AmbienteSuave             -> interpola el ambiente en el tiempo (nada cambia de golpe); ver la clase
#
# Todo es determinista: no usa random ni el reloj real.

import math
import zlib
from collections import namedtuple

from backend.logica import manillas
from backend.logica.estado_partida import NOMBRES_INDICADORES, VALOR_INICIAL

GRUPOS = ("policia", "ciudadanos", "instituciones")

NIVELES = ("florece", "sano", "tenso", "apagado")       # de mejor a peor
UMBRALES_NIVEL = (0.75, 0.50, 0.25)                     # salud mínima de florece, sano y tenso
HISTERESIS_NIVEL = 0.04

DENSIDAD_MIN = 0.35
DENSIDAD_MAX = 1.0

# Estados emocionales de un NPC, en el orden en que se reparten sobre el eje 0..1 de cada NPC (ver perfil_npc).
ESTADOS_NPC = ("sociable", "neutro", "celular", "aislado", "enojado")

# Suavizado: constante de tiempo (s REALES) del acercamiento exponencial al valor objetivo. En TAU se recorre el 63 % del
# camino y en 3 * TAU el 95 %: un cambio de indicadores tarda ~1,5 min en verse del todo. Paso máximo por llamada: DT_MAX.
TAU_SEGUNDOS = 30.0
DT_MAX = 1.0

_VERSION = 1

Ambiente = namedtuple(
    "Ambiente", "salud sociabilidad aislamiento enojo pegado_al_celular bienestar conflictos nivel")
PerfilNPC = namedtuple("PerfilNPC", "estado manilla")


def _recortar(valor, minimo=0.0, maximo=1.0):
    return max(minimo, min(maximo, valor))


def _valor(valor, nombre):
    if isinstance(valor, bool) or not isinstance(valor, (int, float)) or not math.isfinite(valor):
        raise ValueError(f"{nombre} inválido: {valor!r}; se esperaba un número finito.")
    return _recortar(float(valor), 0.0, 100.0)


def _leer_indicadores(indicadores):
    faltan = [n for n in NOMBRES_INDICADORES if n not in indicadores]
    if faltan:
        raise ValueError(f"Faltan indicadores para calcular el ambiente: {faltan}.")
    return {n: _valor(indicadores[n], n) for n in NOMBRES_INDICADORES}


def _leer_confianzas(confianzas):
    if confianzas is None:
        return None
    faltan = [g for g in GRUPOS if g not in confianzas]
    if faltan:
        raise ValueError(f"Faltan grupos de confianza para calcular el ambiente: {faltan}.")
    return {g: _valor(confianzas[g], g) for g in GRUPOS}


def confianza_efectiva(indicadores, confianzas=None):
    """El indicador «confianza» solo, o promediado a partes iguales con la confianza media de los tres grupos."""
    ind, grupos = _leer_indicadores(indicadores), _leer_confianzas(confianzas)
    if grupos is None:
        return ind["confianza"]
    return 0.5 * ind["confianza"] + 0.5 * sum(grupos.values()) / len(GRUPOS)


def derivar(indicadores, confianzas=None):
    """{"bienestar", "conflictos"} (0-100) derivados de los indicadores (y de la confianza por grupo, si se da)."""
    ind = _leer_indicadores(indicadores)
    confianza = confianza_efectiva(ind, confianzas)
    bienestar = 0.40 * ind["convivencia"] + 0.35 * confianza + 0.25 * (100.0 - ind["desinformacion"])
    conflictos = 0.50 * ind["desinformacion"] + 0.35 * (100.0 - ind["convivencia"]) + 0.15 * (100.0 - confianza)
    return {"bienestar": round(_recortar(bienestar, 0.0, 100.0), 4), "conflictos": round(_recortar(conflictos, 0.0, 100.0), 4)}


def nivel_de_salud(salud):
    """Nivel SIN histéresis de una salud 0..1."""
    for nivel, umbral in zip(NIVELES, UMBRALES_NIVEL):
        if salud >= umbral:
            return nivel
    return NIVELES[-1]


def nivel_con_histeresis(salud, nivel_anterior=None):
    """Nivel de `salud` recordando el anterior: solo cambia si la salud sale de la banda del nivel anterior por más de
    HISTERESIS_NIVEL. Sin anterior (o con uno desconocido) es nivel_de_salud."""
    if nivel_anterior not in NIVELES:
        return nivel_de_salud(salud)
    indice = NIVELES.index(nivel_anterior)
    techo = UMBRALES_NIVEL[indice - 1] if indice > 0 else math.inf          # por encima se sube de nivel
    suelo = UMBRALES_NIVEL[indice] if indice < len(UMBRALES_NIVEL) else -math.inf   # por debajo se baja
    if suelo - HISTERESIS_NIVEL <= salud < techo + HISTERESIS_NIVEL:
        return nivel_anterior
    return nivel_de_salud(salud)


def calcular_ambiente(indicadores, confianzas=None, nivel_anterior=None):
    """El Ambiente de esos indicadores. `nivel_anterior` activa la histéresis del nivel (pásale amb.nivel del anterior)."""
    ind = _leer_indicadores(indicadores)
    derivados = derivar(ind, confianzas)
    bienestar, conflictos = derivados["bienestar"], derivados["conflictos"]
    salud = _recortar((bienestar - conflictos + 100.0) / 200.0)
    sociabilidad = 0.02 + 0.90 * salud ** 1.5
    neutro = 0.06 + 0.30 * (1.0 - abs(2.0 * salud - 1.0))
    resto = max(0.0, 1.0 - sociabilidad - neutro)
    pesos = {
        "aislamiento": 0.2 + (100.0 - ind["convivencia"]) / 100.0,
        "pegado_al_celular": 0.2 + ind["desinformacion"] / 100.0,
        "enojo": 0.2 + conflictos / 100.0,
    }
    total = sum(pesos.values())
    return Ambiente(
        salud=round(salud, 6), sociabilidad=round(sociabilidad, 6),
        aislamiento=round(resto * pesos["aislamiento"] / total, 6), enojo=round(resto * pesos["enojo"] / total, 6),
        pegado_al_celular=round(resto * pesos["pegado_al_celular"] / total, 6),
        bienestar=bienestar, conflictos=conflictos, nivel=nivel_con_histeresis(salud, nivel_anterior))


AMBIENTE_INICIAL = calcular_ambiente({n: VALOR_INICIAL for n in NOMBRES_INDICADORES})


# -- Funciones para los consumidores --------------------------------------------------------------------------------------

def densidad_poblacion(amb):
    """Factor (0,35..1,0) de NPC en espacios públicos: una ciudad sana llena la calle; una rota la vacía (nunca del todo)."""
    return round(DENSIDAD_MIN + (DENSIDAD_MAX - DENSIDAD_MIN) * _recortar(amb.salud), 4)


def limpieza(amb):
    """0..1: 1 = plazas cuidadas; 0 = basura y pintadas. Sigue al bienestar y la estropean los conflictos."""
    return round(_recortar(0.7 * amb.bienestar / 100.0 + 0.3 * (1.0 - amb.conflictos / 100.0)), 4)


def actividad_plazas(amb):
    """0..1: vida en las plazas (corros, música, juego). Hace falta gente sociable Y que no esté crispada."""
    return round(_recortar((0.25 + 0.75 * amb.sociabilidad / 0.92) * (1.0 - 0.6 * amb.enojo) * (0.5 + 0.5 * amb.salud)), 4)


def luz_ambiente(amb):
    """Factores multiplicativos de la luz/postproceso: {"tinte": (r, g, b), "saturacion", "brillo"}. Con salud 1 es luz
    cálida y viva; con salud 0, fría, apagada y algo más oscura. Nunca tan oscuro que no se pueda jugar (brillo >= 0,78)."""
    s = _recortar(amb.salud)
    tinte = (round(0.86 + 0.16 * s, 4), round(0.90 + 0.10 * s, 4), round(1.04 - 0.10 * s, 4))
    return {"tinte": tinte, "saturacion": round(0.55 + 0.55 * s, 4), "brillo": round(0.78 + 0.24 * s, 4)}


def probabilidades_npc(amb):
    """{estado: probabilidad} de los cinco estados emocionales (suman 1), en el orden de ESTADOS_NPC."""
    negativos = amb.aislamiento + amb.pegado_al_celular + amb.enojo
    neutro = max(0.0, 1.0 - amb.sociabilidad - negativos)
    crudo = {"sociable": amb.sociabilidad, "neutro": neutro, "celular": amb.pegado_al_celular,
             "aislado": amb.aislamiento, "enojado": amb.enojo}
    total = sum(crudo.values()) or 1.0
    return {estado: crudo[estado] / total for estado in ESTADOS_NPC}


def _mezclar(n):
    # splitmix64: reparte bien enteros consecutivos (los índices de los agentes de la multitud).
    n = (n + 0x9E3779B97F4A7C15) & 0xFFFFFFFFFFFFFFFF
    n = ((n ^ (n >> 30)) * 0xBF58476D1CE4E5B9) & 0xFFFFFFFFFFFFFFFF
    n = ((n ^ (n >> 27)) * 0x94D049BB133111EB) & 0xFFFFFFFFFFFFFFFF
    return n ^ (n >> 31)


def umbral_npc(semilla_npc):
    """Número fijo 0..1 del NPC (entero, texto o tupla de ambos). No depende de hash() de Python: es igual en cada
    ejecución y en cada máquina."""
    if isinstance(semilla_npc, bool):
        raise ValueError("semilla_npc inválida: bool.")
    if isinstance(semilla_npc, int):
        numero = semilla_npc
    elif isinstance(semilla_npc, str):
        numero = zlib.crc32(semilla_npc.encode("utf-8"))
    elif isinstance(semilla_npc, tuple):
        numero = 0
        for parte in semilla_npc:
            numero = _mezclar(numero ^ int(umbral_npc(parte) * 0xFFFFFFFF))
    else:
        raise ValueError(f"semilla_npc inválida: {semilla_npc!r}; se esperaba int, str o tupla.")
    return (_mezclar(numero & 0xFFFFFFFFFFFFFFFF) >> 11) / float(1 << 53)


def estado_npc(semilla_npc, amb):
    """Estado emocional de UN NPC con este ambiente. Cada NPC tiene un número fijo u (umbral_npc) y los estados ocupan
    tramos consecutivos de 0..1 (sociable | neutro | celular | aislado | enojado) con el ancho de su probabilidad: la mezcla
    de la población sigue al Ambiente y, cuando este cambia poco, solo cambian de estado los NPC que están en el borde de
    un tramo (no se baraja a toda la ciudad)."""
    u = umbral_npc(semilla_npc)
    acumulado = 0.0
    for estado, probabilidad in probabilidades_npc(amb).items():
        acumulado += probabilidad
        if u < acumulado:
            return estado
    return ESTADOS_NPC[-1]


def perfil_npc(semilla_npc, amb):
    """PerfilNPC(estado, manilla): el estado emocional del NPC y la manilla que lleva (manillas.manilla_de_npc)."""
    estado = estado_npc(semilla_npc, amb)
    return PerfilNPC(estado, manillas.manilla_de_npc(estado))


def ambiente_a_dict(amb):
    return dict(amb._asdict())


# -- Suavizado en el tiempo -----------------------------------------------------------------------------------------------

# Ambiente que se acerca POCO A POCO al de los indicadores reales. Guarda una copia suavizada de cada entrada (los tres
# indicadores y, si hay, la confianza de los tres grupos) y en cada actualizar(dt, ...) la mueve hacia el valor real con
# un filtro exponencial de constante TAU_SEGUNDOS: valor += (objetivo - valor) * (1 - e^(-dt / tau)). El Ambiente se calcula
# con los valores suavizados, así todo lo que cuelga de él (densidad, luz, estados de los NPC) cambia gradualmente.
#
#   suave = AmbienteSuave()
#   suave.actualizar(dt, indicadores, confianzas=None) -> Ambiente    (dt en s REALES; se recorta a DT_MAX)
#   suave.ambiente()                                   -> el último Ambiente (AMBIENTE_INICIAL antes de la primera vez)
#   suave.fijar(indicadores, confianzas=None)          -> salta al valor real (inicio de partida / carga); devuelve Ambiente
#   suave.a_dict() / AmbienteSuave.desde_dict(datos)
#
# La PRIMERA llamada a actualizar() fija los valores sin interpolar (no hay «antes» desde el que venir). Si la partida
# gana o pierde el GameState a mitad (no pasa en el juego), las confianzas se fijan de golpe esa vez.
class AmbienteSuave:

    def __init__(self, tau=TAU_SEGUNDOS):
        if isinstance(tau, bool) or not isinstance(tau, (int, float)) or not math.isfinite(tau) or tau <= 0:
            raise ValueError(f"tau inválido: {tau!r}; debe ser un número positivo de segundos.")
        self._tau = float(tau)
        self._indicadores = None        # {indicador: valor suavizado} o None antes de la primera actualización
        self._confianzas = None         # {grupo: valor suavizado} o None sin GameState
        self._ambiente = AMBIENTE_INICIAL

    def ambiente(self):
        return self._ambiente

    def tau(self):
        return self._tau

    # Valores suavizados (copias): {"indicadores": {...} | None, "confianzas": {...} | None}.
    def valores(self):
        return {"indicadores": dict(self._indicadores) if self._indicadores is not None else None,
                "confianzas": dict(self._confianzas) if self._confianzas is not None else None}

    def fijar(self, indicadores, confianzas=None):
        self._indicadores = _leer_indicadores(indicadores)
        self._confianzas = _leer_confianzas(confianzas)
        self._ambiente = calcular_ambiente(self._indicadores, self._confianzas)
        return self._ambiente

    def actualizar(self, dt, indicadores, confianzas=None):
        if isinstance(dt, bool) or not isinstance(dt, (int, float)) or not math.isfinite(dt) or dt < 0:
            raise ValueError(f"dt inválido: {dt!r}; se esperaba un número de segundos >= 0.")
        objetivo, objetivo_grupos = _leer_indicadores(indicadores), _leer_confianzas(confianzas)
        if self._indicadores is None:
            return self.fijar(objetivo, objetivo_grupos)
        paso = 1.0 - math.exp(-min(float(dt), DT_MAX) / self._tau)
        for nombre in NOMBRES_INDICADORES:
            self._indicadores[nombre] += (objetivo[nombre] - self._indicadores[nombre]) * paso
        if objetivo_grupos is None or self._confianzas is None:
            self._confianzas = objetivo_grupos
        else:
            for grupo in GRUPOS:
                self._confianzas[grupo] += (objetivo_grupos[grupo] - self._confianzas[grupo]) * paso
        self._ambiente = calcular_ambiente(self._indicadores, self._confianzas, self._ambiente.nivel)
        return self._ambiente

    # -- Serialización (JSON) --

    def a_dict(self):
        return {"version": _VERSION, "tau": self._tau, "nivel": self._ambiente.nivel,
                "indicadores": dict(self._indicadores) if self._indicadores is not None else None,
                "confianzas": dict(self._confianzas) if self._confianzas is not None else None}

    # ValueError si los datos no son válidos (quien restaura decide: flujo_tiempo vuelve a un AmbienteSuave nuevo, que se
    # fija solo en la primera actualización).
    @classmethod
    def desde_dict(cls, datos):
        if not isinstance(datos, dict) or datos.get("version") != _VERSION:
            raise ValueError("Ambiente guardado con formato desconocido.")
        suave = cls(datos.get("tau", TAU_SEGUNDOS))
        indicadores, confianzas = datos.get("indicadores"), datos.get("confianzas")
        if indicadores is not None:
            if not isinstance(indicadores, dict) or (confianzas is not None and not isinstance(confianzas, dict)):
                raise ValueError("Ambiente guardado dañado.")
            suave._indicadores = _leer_indicadores(indicadores)
            suave._confianzas = _leer_confianzas(confianzas)
            nivel = datos.get("nivel")
            suave._ambiente = calcular_ambiente(suave._indicadores, suave._confianzas, nivel if nivel in NIVELES else None)
        return suave
