# Veredicto de misión, confianza por grupo y finales (A2d). Modelo puro: sin ursina, sin flujo de partida y sin estado
# propio. TODAS las constantes del balance viven aquí; el resto del juego solo llama a estas funciones.
#
# Son reutilizables tal cual desde backend/red/ (coop / en línea): reciben la misión (duck typing: tipo, grupo,
# es_verdadera, objetivo, id), la decisión y, para aplicar, cualquier objeto con la interfaz de GameState. No dependen de
# FlujoPartida ni de LoteMision.
#
#   veredicto(mision, decision)                 -> "pasada" | "fallada" | None
#   tabla_deltas(catalogo)                      -> {grupo: DeltasGrupo(acierto, error, misiones, bono_digital)}
#   delta_de_veredicto(tabla, mision, veredicto)-> (grupo, delta) | None
#   aplicar_veredicto(game_state, tabla, mision, veredicto) -> delta aplicado | None
#   bono_digital(mision, resultado_caso)        -> delta de policía de una misión de parkour / investigación
#   aplicar_bono_digital(game_state, mision)    -> delta aplicado
#   veredicto_digital(mision, game_state)       -> "pasada" | "fallada" | None
#   evaluar_final(confianzas, pasadas, falladas)-> dict con el final y el resumen
#
# OJO: la confianza de la que se habla aquí es la de GameState (tres grupos, 0-100, inicio 50), NO el indicador «confianza»
# de EstadoPartida. Los textos de los finales están en backend/datos/finales_textos.py.
#
# VEREDICTO. Las acciones del jugador sobre una carta son solo dos (EstadoPartida.decidir): "compartir" y "reportar".
# Correcto = compartir si el rumor es verdadero, reportar si es falso -> misión PASADA. Cualquier otra decisión -> FALLADA
# (hoy solo existe la contraria; si un día se añaden «ignorar» o «verificar», tampoco serían la correcta). Fallar es
# válido: la misión cuenta como completada y cobra el pago completo; solo baja la confianza. Sin decisión (None: el lote no
# llevó carta de misión, o la carta se descartó) NO hay veredicto y la confianza no se toca.
#
# ESCALADO POR MAPA (calculado, no a mano). Para cada grupo g, con n_g = misiones de verificar que lo mueven en ese mapa:
#   acierto_g = (OBJETIVO_PERFECTO - 50 - bono_digital_g) / n_g        error_g = RAZON_ERROR * acierto_g
# donde bono_digital_g es lo MÁXIMO que las misiones digitales del catálogo pueden sumar al grupo (parkour + mejor final
# del caso; hoy solo policía). Así acertarlo todo deja a cada grupo en OBJETIVO_PERFECTO, en el mapa chico (14 misiones) y
# en el grande (47). Los efectos que traen los JSON del caso y del parkour NO entran en este cálculo: se suman aparte, como
# siempre (pueden empujar un grupo por encima del objetivo; GameState recorta a 100).
#
# FINAL. El umbral se aplica al ÍNDICE = promedio de la confianza de los tres grupos: >= 70 bueno, 40-69 neutro, < 40 malo.
# Además, si CUALQUIER grupo queda por debajo de 20 el final es malo aunque el promedio sea alto.

import math
from collections import namedtuple

from backend.logica import casos

GRUPOS = ("policia", "ciudadanos", "instituciones")     # los de GameState.confianza
CONFIANZA_INICIAL = 50

# -- Balance --
OBJETIVO_PERFECTO = 88          # confianza de cada grupo si se acierta todo (el diseño pide ≈ 85-90)
RAZON_ERROR = 1.5               # un error resta 1,5 veces lo que suma un acierto

# Bonos de las misiones digitales (se SUMAN a los efectos de sus JSON). Todos van a policía.
GRUPO_BONO_DIGITAL = "policia"
BONO_PARKOUR = 5
BONO_INVESTIGACION = {"exito": 8, "parcial": 2, "fracaso": -4}     # según el `resultado` del final del caso

# -- Finales --
UMBRAL_BUENO = 70               # índice >= 70
UMBRAL_NEUTRO = 40              # 40 <= índice < 70; por debajo, malo
UMBRAL_GRUPO_CRITICO = 20       # cualquier grupo < 20 -> malo
FINALES = ("bueno", "neutro", "malo")

PASADA = "pasada"
FALLADA = "fallada"
VEREDICTOS = (PASADA, FALLADA)

_DECIMALES = 2

# acierto / error: puntos de confianza que suma un acierto y que resta un error (ambos >= 0). misiones: n_g.
DeltasGrupo = namedtuple("DeltasGrupo", "acierto error misiones bono_digital")


def _es_verificar(mision):
    return getattr(mision, "tipo", "verificar") == "verificar" and isinstance(getattr(mision, "es_verdadera", None), bool)


# -- Veredicto --

# "compartir" si el rumor de la misión es verdadero, "reportar" si es falso; None si la misión no es de verificar.
def decision_correcta(mision):
    if not _es_verificar(mision):
        return None
    return "compartir" if mision.es_verdadera else "reportar"


# PASADA si `decision` es la correcta; FALLADA con cualquier otra; None si no hay decisión o la misión no es de verificar.
def veredicto(mision, decision):
    correcta = decision_correcta(mision)
    if correcta is None or decision is None:
        return None
    return PASADA if decision == correcta else FALLADA


# Misiones digitales: el parkour completado es PASADA; la investigación, PASADA con final «exito» o «parcial» y FALLADA con
# «fracaso» (o sin resultado legible). None si la misión es de verificar.
def veredicto_digital(mision, game_state):
    tipo = getattr(mision, "tipo", "verificar")
    if tipo == "parkour":
        return PASADA
    if tipo == "investigacion":
        return PASADA if _resultado_del_caso(mision, game_state) in ("exito", "parcial") else FALLADA
    return None


def _resultado_del_caso(mision, game_state):
    if game_state is None:
        return None
    resultado = casos.resultado_de(game_state, mision.objetivo)
    return resultado.resultado if resultado is not None else None


# -- Deltas por mapa --

# Lo máximo que las misiones digitales del catálogo pueden sumar a cada grupo.
def bono_digital_maximo(catalogo):
    bonos = {grupo: 0 for grupo in GRUPOS}
    for mision in catalogo:
        tipo = getattr(mision, "tipo", "verificar")
        if tipo == "parkour":
            bonos[GRUPO_BONO_DIGITAL] += BONO_PARKOUR
        elif tipo == "investigacion":
            bonos[GRUPO_BONO_DIGITAL] += max(BONO_INVESTIGACION.values())
    return bonos


# {grupo: DeltasGrupo} del catálogo (el de UN mapa, con o sin digitales). Un grupo sin misiones de verificar no mueve nada.
def tabla_deltas(catalogo):
    catalogo = list(catalogo)
    bonos = bono_digital_maximo(catalogo)
    tabla = {}
    for grupo in GRUPOS:
        n = sum(1 for m in catalogo if _es_verificar(m) and m.grupo == grupo)
        acierto = max(0.0, (OBJETIVO_PERFECTO - CONFIANZA_INICIAL - bonos[grupo]) / n) if n else 0.0
        tabla[grupo] = DeltasGrupo(acierto, RAZON_ERROR * acierto, n, bonos[grupo])
    return tabla


# (grupo, delta con signo) que corresponde al veredicto de la misión; None si no hay veredicto o la misión no tiene grupo.
def delta_de_veredicto(tabla, mision, veredicto_mision):
    grupo = getattr(mision, "grupo", "")
    if veredicto_mision not in VEREDICTOS or grupo not in tabla:
        return None
    deltas = tabla[grupo]
    return grupo, (deltas.acierto if veredicto_mision == PASADA else -deltas.error)


# Mueve la confianza del grupo de la misión y deja el rastro en el ArbolImpactos («mision:pasada» / «mision:fallada»,
# origen «mision:<id>»). Devuelve el delta aplicado (redondeado como lo guarda GameState) o None si no había nada que aplicar.
def aplicar_veredicto(game_state, tabla, mision, veredicto_mision):
    par = delta_de_veredicto(tabla, mision, veredicto_mision)
    if game_state is None or par is None:
        return None
    grupo, delta = par
    return _aplicar(game_state, f"mision:{veredicto_mision}", grupo, delta, mision,
                    {"mision": mision.id, "veredicto": veredicto_mision})


# Bono de policía de una misión digital: parkour +BONO_PARKOUR; investigación según el resultado del final del caso
# («exito» / «parcial» / «fracaso»; None o desconocido = 0). Las de verificar, 0.
def bono_digital(mision, resultado_caso=None):
    tipo = getattr(mision, "tipo", "verificar")
    if tipo == "parkour":
        return BONO_PARKOUR
    if tipo == "investigacion":
        return BONO_INVESTIGACION.get(resultado_caso, 0)
    return 0


# Suma el bono de la misión digital a policía (y deja el rastro «mision:digital»). `resultado_caso`: si no se da, se lee
# del final del caso registrado en el GameState. Devuelve el delta aplicado (0 si no había bono).
def aplicar_bono_digital(game_state, mision, resultado_caso=None):
    if game_state is None or getattr(mision, "tipo", "verificar") == "verificar":
        return 0
    if resultado_caso is None and mision.tipo == "investigacion":
        resultado_caso = _resultado_del_caso(mision, game_state)
    delta = bono_digital(mision, resultado_caso)
    if delta == 0:
        return 0
    return _aplicar(game_state, "mision:digital", GRUPO_BONO_DIGITAL, delta, mision,
                    {"mision": mision.id, "tipo_mision": mision.tipo, "resultado_caso": resultado_caso})


# GameState.aplicar_evento calcula el delta como 0,5 * investigacion (+ moral y secundarios, aquí 0): para que el delta sea
# exactamente `delta` se le pasa investigacion = delta / 0,5. Así el cambio queda registrado con el tiempo de juego.
def _aplicar(game_state, tipo, grupo, delta, mision, datos):
    from backend.logica.game_state import PESO_INVESTIGACION
    antes = game_state.confianza(grupo)
    game_state.aplicar_evento(tipo, efectos={grupo: {"investigacion": delta / PESO_INVESTIGACION}},
                              origen=f"mision:{mision.id}", datos=datos)
    return round(game_state.confianza(grupo) - antes, _DECIMALES)


# -- Final --

# Final de la partida a partir de la confianza por grupo ({"policia", "ciudadanos", "instituciones"}: 0-100) y del recuento
# de misiones. Devuelve un dict JSON-serializable:
#   {"final": "bueno" | "neutro" | "malo", "indice": promedio de los tres grupos (2 decimales),
#    "confianza": {grupo: valor}, "pasadas": n, "falladas": n, "grupo_critico": grupo < 20 más bajo, o None}
# Perder es un final válido (no hay «game over»): la vista pinta el texto de finales_textos.texto_final(final).
def evaluar_final(confianzas, pasadas=0, falladas=0):
    faltan = [g for g in GRUPOS if g not in confianzas]
    if faltan:
        raise ValueError(f"Faltan grupos de confianza para evaluar el final: {faltan}.")
    valores = {g: confianzas[g] for g in GRUPOS}
    for grupo, valor in valores.items():
        if isinstance(valor, bool) or not isinstance(valor, (int, float)) or not math.isfinite(valor):
            raise ValueError(f"Confianza inválida de {grupo}: {valor!r}.")
    indice = round(sum(valores.values()) / len(GRUPOS), _DECIMALES)
    criticos = [g for g in GRUPOS if valores[g] < UMBRAL_GRUPO_CRITICO]
    grupo_critico = min(criticos, key=lambda g: valores[g]) if criticos else None
    if grupo_critico is not None or indice < UMBRAL_NEUTRO:
        final = "malo"
    elif indice >= UMBRAL_BUENO:
        final = "bueno"
    else:
        final = "neutro"
    return {"final": final, "indice": indice, "confianza": valores, "pasadas": int(pasadas), "falladas": int(falladas),
            "grupo_critico": grupo_critico}
