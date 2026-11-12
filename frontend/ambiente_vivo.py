# Ambiente VIVO de la ciudad: el punto ÚNICO del frontend para leer el Ambiente suavizado (backend/logica/
# ambiente_ciudad.py) y la hora de juego. Sin ursina ni panda3d: se puede importar desde cualquier módulo y en pruebas.
#
#   from frontend import ambiente_vivo
#   amb = ambiente_vivo.obtener()          # Ambiente (namedtuple); AMBIENTE_INICIAL si todavía no hay partida
#   ambiente_vivo.hora()                   # hora de juego 0..24 del reloj de la partida, o None (sin reloj / en línea)
#   ambiente_vivo.dia()                    # día 1..7, o None
#   ambiente_vivo.en_linea()               # ¿la partida actual es en línea? (ver «En línea»)
#   ambiente_vivo.version()                # entero que sube cada vez que se alimenta (para cachés por frame)
#
# QUIÉN LO ALIMENTA: frontend/registro_ambiente_npc.py llama a alimentar(dt, escena_mundo) UNA vez por frame con el mundo
# a la vista. Los demás módulos SOLO leen con obtener(); nadie más debe llamar a alimentar().
#
# DE DÓNDE SALE: de `escena_mundo._sesion.estado_partida.indicadores()` y, si el flujo tiene GameState, de
# `flujo.game_state.confianzas()`, pasados por un AmbienteSuave PROPIO (τ = 30 s reales: nada cambia de golpe). No depende
# de que alguien llame a flujo.avanzar_tiempo(): funciona igual con ALCALDE_RELOJ=0 y con guardados viejos.
#
# EN LÍNEA: los indicadores viajan por la red, así que el Ambiente también vale en línea; lo que NO hay es reloj de
# partida (hora() = None). Las capas que cambian la POSICIÓN de los NPC deben mirar en_linea() y limitarse a lo visual.
#
# Depuración: ALCALDE_AMBIENTE_FIJO="conv,conf,desinf" (p. ej. "95,95,5" o "5,5,95") fija los indicadores que se usan,
# sin tocar la partida: sirve para ver la ciudad sana o rota sin jugar una semana.

import os
import sys

from backend.logica import ambiente_ciudad as ac
from backend.logica import etapas_final

_suave = ac.AmbienteSuave()
_sesion = None              # la sesión con la que se alimentó por última vez (otra partida = se fija sin interpolar)
_flujo = None
_version = 0
_avisado = False
_etapa = 0                  # etapa de los finales por etapas (-3..+3); la fija frontend/etapas_final_vista.py
_indice = None              # último índice leído (finales por etapas)
_t_indice = 0.0             # s que faltan para volver a leerlo
PERIODO_INDICE = 0.5


def obtener():
    """El Ambiente suavizado actual (ambiente_ciudad.Ambiente). Nunca falla: sin partida es AMBIENTE_INICIAL."""
    return _suave.ambiente()


def suave():
    """El AmbienteSuave que hay detrás (valores(), a_dict()...). Solo lectura para los demás módulos."""
    return _suave


def version():
    return _version


def _flujo_en_linea(flujo):
    return flujo is not None and (hasattr(flujo, "cliente") or type(flujo).__name__ == "FlujoEnLinea")


def en_linea():
    """¿La partida con la que se alimentó es en línea? (sin reloj; la posición de la multitud debe seguir determinista)."""
    return _flujo_en_linea(_flujo)


def _reloj():
    reloj = getattr(_flujo, "reloj", None) if _flujo is not None else None
    return reloj if reloj is not None and hasattr(reloj, "hora") else None


def hora():
    """Hora de juego 0..24 (reloj_partida.hora()), o None sin reloj (ALCALDE_RELOJ=0, en línea, sin partida)."""
    reloj = _reloj()
    try:
        return None if reloj is None else float(reloj.hora())
    except Exception:
        return None


def dia():
    """Día de la partida 1..7, o None sin reloj."""
    reloj = _reloj()
    try:
        return None if reloj is None else int(reloj.dia())
    except Exception:
        return None


def indicadores_fijos(texto=None):
    """Indicadores de ALCALDE_AMBIENTE_FIJO («conv,conf,desinf») o None. Puro: `texto` sustituye a la variable."""
    texto = os.environ.get("ALCALDE_AMBIENTE_FIJO", "") if texto is None else texto
    partes = [p.strip() for p in texto.replace(";", ",").split(",") if p.strip()]
    if len(partes) != 3:
        return None
    try:
        valores = [max(0.0, min(100.0, float(p))) for p in partes]
    except ValueError:
        return None
    return {"convivencia": valores[0], "confianza": valores[1], "desinformacion": valores[2]}


def leer_fuentes(escena_mundo):
    """(indicadores, confianzas) de la partida de `escena_mundo`, o (None, None) si no hay partida. No lanza."""
    sesion = getattr(escena_mundo, "_sesion", None)
    flujo = getattr(escena_mundo, "flujo", None)
    if sesion is None:
        return None, None
    indicadores = sesion.estado_partida.indicadores()
    game_state = getattr(flujo, "game_state", None) if flujo is not None else None
    confianzas = None
    if game_state is not None and callable(getattr(game_state, "confianzas", None)):
        confianzas = game_state.confianzas()
    return indicadores, confianzas


def _leer_indice(dt, flujo, nuevo):
    """Índice de los finales por etapas (None con la bandera apagada o sin resumen): se relee como mucho cada 0,5 s."""
    global _indice, _t_indice
    if not etapas_final.activo():
        _indice = None
        return None
    _t_indice -= dt
    if nuevo or _t_indice <= 0:
        _t_indice = PERIODO_INDICE
        _indice = etapas_final.indice_de_flujo(flujo)
    return _indice


def etapa():
    """Etapa vigente de los finales por etapas (-3..+3; 0 = la ciudad de siempre)."""
    return _etapa


def fijar_etapa(e):
    """Cambia la etapa; si cambia de verdad sube la versión para que ciudad_viva reparta de nuevo sus capas."""
    global _etapa, _version
    e = max(etapas_final.ETAPA_MIN, min(etapas_final.ETAPA_MAX, int(e)))
    if e != _etapa:
        _etapa = e
        _version += 1
    return _etapa


def alimentar(dt, escena_mundo):
    """Un paso de `dt` s reales con la partida de `escena_mundo`. Devuelve el Ambiente. Nunca lanza: si la lectura falla
    avisa una vez por stderr y deja el ambiente como estaba."""
    global _sesion, _flujo, _version, _avisado
    try:
        indicadores, confianzas = leer_fuentes(escena_mundo)
        _flujo = getattr(escena_mundo, "flujo", None)
        if indicadores is None:
            return _suave.ambiente()
        fijos = indicadores_fijos()
        sesion = getattr(escena_mundo, "_sesion", None)
        indice = _leer_indice(max(0.0, float(dt)), _flujo, sesion is not _sesion)
        if fijos is not None:                     # indicadores fijos de depuración: mandan salvo que se fuerce el índice
            indicadores, confianzas = fijos, None
            indice = etapas_final.indice_forzado() if etapas_final.activo() else None
        if sesion is not _sesion:                 # otra partida (o carga de guardado): empieza en su valor real
            _sesion = sesion
            _suave.fijar(indicadores, confianzas, indice)
        else:
            _suave.actualizar(max(0.0, float(dt)), indicadores, confianzas, indice)
        _version += 1
    except Exception as error:
        if not _avisado:
            _avisado = True
            print(f"[ambiente_vivo] no se pudo leer el ambiente ({type(error).__name__}: {error})", file=sys.stderr)
    return _suave.ambiente()


def fijar(indicadores, confianzas=None):
    """Salta al ambiente de esos indicadores (pruebas, capturas y depuración)."""
    global _version
    _version += 1
    return _suave.fijar(indicadores, confianzas)


def reiniciar():
    """Vuelve al estado de arranque (pruebas)."""
    global _suave, _sesion, _flujo, _version, _avisado, _etapa, _indice, _t_indice
    _suave = ac.AmbienteSuave()
    _sesion = _flujo = None
    _version = 0
    _avisado = False
    _etapa = 0
    _indice = None
    _t_indice = 0.0
