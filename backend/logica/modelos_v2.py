# Banderas y rutas de los modelos v2 de la fase Blender (sesión F, 2026-11-24). Puro, sin motor gráfico: lo leen el
# backend (personajes_loader) y el frontend (npc_modelo, fiscalia/personajes, personaje_modelo).
#
# ALCALDE_MODELOS_V2 es la maestra; cada grupo tiene la suya:
#   ALCALDE_ELENCO_V2         personajes con nombre con malla propia (assets/modelos/personajes/v2/<id>.glb)
#   ALCALDE_PROTAGONISTAS_V2  los 4 protagonistas arreglados (v2/ciudadano.glb, periodista, smoking, brasilena)
# Un grupo está activo si la maestra Y su bandera lo están. Con =0 se cargan los .glb y los parches de siempre.
# Valor por defecto de cada grupo en DEFECTO: solo se enciende el grupo que pasó la verificación. Se leen en cada
# llamada (los tests las cambian). Si un .glb v2 falta o no carga, ese personaje usa el de siempre y se avisa una vez.

import os
import sys

MAESTRA = "ALCALDE_MODELOS_V2"
ELENCO = "ALCALDE_ELENCO_V2"
PROTAGONISTAS = "ALCALDE_PROTAGONISTAS_V2"

DEFECTO = {MAESTRA: True, ELENCO: True, PROTAGONISTAS: True}

# Carpeta de los .glb v2, relativa a assets/modelos/personajes/ (los de siempre no se tocan).
CARPETA_V2 = "v2"
PROTAGONISTAS_V2 = {"ciudadano": "v2/ciudadano.glb", "periodista": "v2/periodista.glb",
                    "smoking": "v2/smoking.glb", "brasilena": "v2/brasilena.glb"}

_avisados = set()


def _leer(variable):
    valor = os.environ.get(variable, "").strip().lower()
    if valor in ("0", "false", "off", "no"):
        return False
    if valor:
        return True
    return DEFECTO[variable]


def maestra():
    return _leer(MAESTRA)


def elenco_activo():
    return maestra() and _leer(ELENCO)


def protagonistas_activo():
    return maestra() and _leer(PROTAGONISTAS)


def avisar_una_vez(clave, mensaje):
    """Aviso por stderr la primera vez que pasa `clave` (un .glb v2 que falta o no carga)."""
    if clave in _avisados:
        return False
    _avisados.add(clave)
    print(f"[modelos_v2] {mensaje}", file=sys.stderr)
    return True
