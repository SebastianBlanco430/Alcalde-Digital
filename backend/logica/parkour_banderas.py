# Banderas de los sectores nuevos del parkour (sesión E): qué nivel juega de verdad cada parkour del laboratorio de un
# caso. Lógica pura, sin ursina.
#
# Un caso declara en su JSON el nivel nuevo y su respaldo:
#   "laboratorio": {"parkours": [{"nivel": "sector_3", "_respaldo": "sector_1", "nombre": …, "descripcion": …,
#                                 "evidencia": …}, …]}
# `nivel_de_caso` / `resolver` devuelven el nivel nuevo si su bandera ALCALDE_PK_SECTOR_<n> está encendida (lo está por
# defecto) Y su archivo existe y carga sin error; si no, el respaldo (el `_respaldo` declarado o, si falta,
# sector_1 para el primer parkour y sector_2 para el segundo). Los niveles que no son sectores nuevos pasan tal cual.
# `resolver_caso` aplica esto a todo el bloque laboratorio de un caso ANTES de validarlo (una sola resolución por
# carga: el resto de la Fiscalía ve un único id coherente).

import copy
import json
import os
from pathlib import Path

from backend.datos import parkour_loader

BANDERAS = {f"sector_{n}": f"ALCALDE_PK_SECTOR_{n}" for n in (3, 4, 5, 6)}
RESPALDOS = ("sector_1", "sector_2")          # respaldo por posición en laboratorio.parkours
CARPETA_CASOS = Path(__file__).resolve().parent.parent / "datos" / "casos"
_APAGADO = ("0", "false", "no", "off")


def bandera_activa(nivel_id):
    """True si el sector nuevo `nivel_id` no está apagado por su variable de entorno (encendido por defecto)."""
    clave = BANDERAS.get(nivel_id)
    if clave is None:
        return True
    return os.environ.get(clave, "").strip().lower() not in _APAGADO


def nivel_carga(nivel_id, carpeta=None):
    """True si el nivel existe y pasa el cargador (cualquier error de datos -> False)."""
    try:
        parkour_loader.cargar_nivel(nivel_id, carpeta=carpeta)
        return True
    except (ValueError, OSError, KeyError, TypeError):
        return False


def respaldo_de(indice):
    return RESPALDOS[min(max(int(indice), 0), len(RESPALDOS) - 1)]


def resolver(nivel, respaldo, carpeta=None):
    """Nivel efectivo: el sector nuevo si su bandera está encendida y carga; si no, `respaldo`."""
    if not isinstance(nivel, str) or not nivel:
        return respaldo
    if nivel not in BANDERAS:
        return nivel
    return nivel if bandera_activa(nivel) and nivel_carga(nivel, carpeta) else respaldo


def _respaldo_declarado(parkour, indice):
    valor = parkour.get("_respaldo") if isinstance(parkour, dict) else None
    return valor if isinstance(valor, str) and valor in RESPALDOS else respaldo_de(indice)


def _datos_de_caso(caso_id, carpeta_casos=None):
    for ruta in sorted(Path(carpeta_casos or CARPETA_CASOS).glob("caso_*.json")):
        try:
            datos = json.loads(ruta.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(datos, dict) and datos.get("id") == caso_id:
            return datos
    return None


def nivel_de_caso(caso_id, indice, datos_caso=None, carpeta=None, carpeta_casos=None):
    """Id del nivel que se juega en el parkour `indice` (0 o 1) del laboratorio del caso `caso_id`. `datos_caso`: el
    dict del JSON ya leído (si no, se busca el caso_*.json con ese id). Cualquier dato que falte -> respaldo."""
    datos = datos_caso if isinstance(datos_caso, dict) else _datos_de_caso(caso_id, carpeta_casos)
    try:
        parkour = datos["laboratorio"]["parkours"][indice]
    except (TypeError, KeyError, IndexError):
        return respaldo_de(indice)
    if not isinstance(parkour, dict):
        return respaldo_de(indice)
    return resolver(parkour.get("nivel"), _respaldo_declarado(parkour, indice), carpeta)


def resolver_caso(datos_caso, carpeta=None):
    """Copia del dict del caso con cada laboratorio.parkours[i].nivel ya resuelto (los demás campos intactos). Si dos
    parkours acabaran en el mismo nivel, ambos vuelven a su respaldo por posición. Datos raros -> se devuelven igual."""
    try:
        parkours = datos_caso["laboratorio"]["parkours"]
    except (TypeError, KeyError):
        return datos_caso
    if not isinstance(parkours, list):
        return datos_caso
    nuevo = dict(datos_caso)
    nuevo["laboratorio"] = dict(datos_caso["laboratorio"])
    copia = [copy.deepcopy(p) for p in parkours]
    for i, p in enumerate(copia):
        if isinstance(p, dict):
            p["nivel"] = nivel_de_caso(None, i, datos_caso=datos_caso, carpeta=carpeta)
    niveles = [p.get("nivel") for p in copia if isinstance(p, dict)]
    if len(set(niveles)) != len(niveles):
        for i, p in enumerate(copia):
            if isinstance(p, dict) and p.get("nivel") in BANDERAS:
                p["nivel"] = _respaldo_declarado(parkours[i], i)
    nuevo["laboratorio"]["parkours"] = copia
    return nuevo


def niveles_validos(carpeta=None):
    """Ids de nivel que un caso puede declarar tras resolver: sector_1, sector_2 y los sectores nuevos que cargan."""
    return tuple(RESPALDOS) + tuple(n for n in sorted(BANDERAS) if bandera_activa(n) and nivel_carga(n, carpeta))
