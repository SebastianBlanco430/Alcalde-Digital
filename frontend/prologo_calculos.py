# Prólogo en 3D: la parte PURA (no importa ursina). Ver frontend/prologo_cinematica.py (lo que se ve) y el guion en
# backend/datos/prologo_cinematica.json. Hilo conductor: docs/HILO_CONDUCTOR.md.
#
# El prólogo es una lista de TRAMOS:
#   - «animado»: planos rodados en la Ciudad Nova real con el director del final animado (frontend/final_animado/). Cada
#     plano reutiliza un id con toma (camaras.TOMAS) y puesta (puesta.py) ya escritas, con subtítulos propios; «final»
#     fija el estado de la ciudad (neutro = hoy, malo = etapa -3 de noche, bueno = etapa +3 de mañana).
#   - «cartela»: pantalla negra con un texto («Dentro de siete días...», «La decisión depende de ti...»).
#
#   cargar_guion(ruta=None)        -> dict del JSON
#   tramos(guion)                  -> tramos válidos (lo que no se pueda rodar se salta: el prólogo nunca falla por datos)
#   guion_animado(guion, tramo)    -> la sección «animacion» que espera final_animado.director (solo ese final)
#   segundos_cartela(texto)        -> cuánto dura una cartela (entrada + lectura + salida), sin voz
#   duracion_cartela(texto)        -> lo mismo, alargada si la narradora la dice (frontend/narrador_calculos.py)
#   alfa_cartela(t, segundos)      -> 0..1 del texto de la cartela en el instante t

import copy
import json
from pathlib import Path

from backend.logica import radio_guion
from frontend import narrador_calculos

RUTA_GUION = Path(__file__).resolve().parent.parent / "backend" / "datos" / "prologo_cinematica.json"
FINALES = ("bueno", "neutro", "malo")
CARTELA_ENTRADA = 0.7           # s en que aparece el texto de una cartela
CARTELA_SALIDA = 0.5            # s en que se va
SALTAR = "Mantén para saltar"


def cargar_guion(ruta=None):
    with open(ruta or RUTA_GUION, encoding="utf-8") as archivo:
        return json.load(archivo)


def _tomas():
    from frontend.final_animado import camaras
    return camaras.TOMAS


def _plano_valido(plano, tomas):
    try:
        return (str(plano["id"]) in tomas and float(plano["segundos"]) > 0 and bool(plano.get("ancla"))
                and isinstance(plano.get("subtitulos", []), list))
    except (KeyError, TypeError, ValueError):
        return False


def tramos(guion):
    """Los tramos que se pueden rodar, en orden. Un plano sin toma conocida se quita; un tramo sin planos o una cartela
    sin texto, también."""
    tomas = _tomas()
    salida = []
    for tramo in (guion or {}).get("tramos", []):
        if not isinstance(tramo, dict):
            continue
        if tramo.get("tipo") == "cartela" and str(tramo.get("texto", "")).strip():
            salida.append({"tipo": "cartela", "texto": str(tramo["texto"]).strip()})
        elif tramo.get("tipo") == "animado" and tramo.get("final") in FINALES:
            planos = [copy.deepcopy(p) for p in tramo.get("planos", []) if isinstance(p, dict) and _plano_valido(p, tomas)]
            if planos:
                salida.append({"tipo": "animado", "final": tramo["final"], "planos": planos})
    return salida


def guion_animado(guion, tramo):
    """Sección «animacion» con SOLO el final del tramo y sus planos (sin hueco de rol, sin sonido ni música: el estado
    de la ciudad, etapa y hora, lo pone la escenografía del final)."""
    return {"saltar": str((guion or {}).get("saltar", SALTAR)),
            tramo["final"]: {"musica": None, "sonido": None, "planos": copy.deepcopy(tramo["planos"])}}


def segundos_cartela(texto):
    return CARTELA_ENTRADA + radio_guion.segundos_lectura(texto) + CARTELA_SALIDA


def duracion_cartela(texto):
    """Lo que dura la cartela en pantalla: segundos_cartela, o lo que necesite la voz de la narradora si es más. Con
    ALCALDE_NARRADOR=0, sin audio o ante cualquier error, segundos_cartela."""
    base = segundos_cartela(texto)
    try:
        return max(base, float(narrador_calculos.segundos_cartela(texto, base, CARTELA_ENTRADA, CARTELA_SALIDA)))
    except Exception:
        return base


def alfa_cartela(t, segundos):
    if t <= 0.0 or t >= segundos:
        return 0.0
    if t < CARTELA_ENTRADA:
        return t / CARTELA_ENTRADA
    if t > segundos - CARTELA_SALIDA:
        return max(0.0, (segundos - t) / CARTELA_SALIDA)
    return 1.0


def duracion_estimada(lista):
    """Segundos aproximados del prólogo entero (sin las cargas), con los planos y las cartelas alargados por la voz."""
    from frontend.final_animado import _calculos as calc
    total = 0.0
    for tramo in lista:
        if tramo["tipo"] == "cartela":
            total += duracion_cartela(tramo["texto"])
        else:
            total += calc.duracion_total(calc.planos_de(tramo["final"], [], guion_animado(None, tramo))) + 1.8
    return total
