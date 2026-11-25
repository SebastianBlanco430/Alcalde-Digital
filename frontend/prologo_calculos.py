# Prólogo: la parte PURA (no importa ursina). Ver frontend/prologo_cinematica.py (lo que dibuja) y el guion en
# backend/datos/prologo_cinematica.json. Hilo conductor: docs/HILO_CONDUCTOR.md.
#
# armar_vinetas(guion, cinematicas) -> lista de viñetas para cinematica_final.crear_vinetas, en orden:
#   1. CONTEXTO: las viñetas propias del guion (Ciudad Nova, el partido de siempre, los dos candidatos).
#   2. PRESAGIO: una cartela negra («Dentro de siete días...») y fragmentos de los dos finales, tomados POR REFERENCIA
#      ([final, índice]) de las cinemáticas de backend/datos/finales_historia.json (las mismas viñetas que pinta el final;
#      no se copian): se ve su dibujo y su título, sin el cuerpo (o con «texto_presagio» si el guion lo trae).
#   3. CIERRE: pantalla negra con «La decisión depende de ti y de tus acciones.».
# Cada viñeta lleva «segundos» = regla de lectura (radio_guion.segundos_lectura: 1,5 s + 0,06 s por carácter, mín. 2,5 s).
# Una referencia que no exista se salta (el prólogo nunca falla por un índice).

import copy
import json
from pathlib import Path

from backend.logica import radio_guion

RUTA_GUION = Path(__file__).resolve().parent.parent / "backend" / "datos" / "prologo_cinematica.json"
NEGRO = [0, 0, 0]


def cargar_guion(ruta=None):
    with open(ruta or RUTA_GUION, encoding="utf-8") as archivo:
        return json.load(archivo)


def _con_segundos(vineta):
    lectura = f"{vineta.get('titulo', '')} {vineta.get('texto', '')}".strip()
    vineta["segundos"] = radio_guion.segundos_lectura(lectura)
    return vineta


def _cartela(texto, fondo=NEGRO):
    return _con_segundos({"fondo": list(fondo), "figuras": [], "titulo": "", "texto": texto})


def presagios(guion, cinematicas):
    """Las viñetas de los finales a las que apunta el guion (copias), con el cuerpo del guion."""
    vinetas = []
    for referencia in guion.get("presagios", []):
        try:
            final, indice = referencia
            vineta = copy.deepcopy(cinematicas[final][int(indice)])
        except (KeyError, IndexError, TypeError, ValueError):
            continue
        vineta["texto"] = guion.get("texto_presagio", "")
        vinetas.append(_con_segundos(vineta))
    return vinetas


def armar_vinetas(guion, cinematicas):
    vinetas = [_con_segundos(copy.deepcopy(v)) for v in guion.get("contexto", [])]
    fragmentos = presagios(guion, cinematicas)
    if fragmentos:
        if guion.get("titulo_presagio"):
            vinetas.append(_cartela(guion["titulo_presagio"]))
        vinetas += fragmentos
    if guion.get("cierre"):
        vinetas.append(_cartela(guion["cierre"], guion.get("fondo_cierre", NEGRO)))
    return vinetas
