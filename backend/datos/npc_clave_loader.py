# Cargador de los NPC clave (puro, sin motor gráfico): lee backend/datos/npc_clave.json y devuelve NpcClave validados.
# Sus ids son las relaciones que lleva el GameState (backend/logica/flujo_gamestate.py las usa al crearlo). Un JSON
# roto lanza NpcClaveError con el motivo; nunca devuelve una lista a medias.

import json
from dataclasses import dataclass
from pathlib import Path

from backend.logica.game_state import GRUPOS

RUTA_NPC_CLAVE = Path(__file__).resolve().parent / "npc_clave.json"
ORIGENES = ("vendedor", "ancla")
MIN_NPC, MAX_NPC = 1, 8


class NpcClaveError(ValueError):
    pass


@dataclass(frozen=True)
class NpcClave:
    id: str
    nombre: str
    grupo: str
    rol: str
    origen: str
    ancla: dict | None
    modelo: int | None
    retrato: dict


def _texto(valor):
    return isinstance(valor, str) and valor.strip() != ""


def _npc(i, d, vistos):
    donde = f"npcs[{i}]"
    if not isinstance(d, dict):
        raise NpcClaveError(f"{donde}: debe ser un objeto.")
    for clave in ("id", "nombre", "rol"):
        if not _texto(d.get(clave)):
            raise NpcClaveError(f"{donde}: falta '{clave}' (texto no vacío).")
    ident = d["id"].strip()
    if ":" in ident or " " in ident:
        raise NpcClaveError(f"{donde}: el id {ident!r} no puede llevar ':' ni espacios (se usa en flags y rutas).")
    if ident in vistos:
        raise NpcClaveError(f"{donde}: id repetido {ident!r}.")
    if d.get("grupo") not in GRUPOS:
        raise NpcClaveError(f"{donde}: 'grupo' debe ser uno de {GRUPOS}, no {d.get('grupo')!r}.")
    origen = d.get("origen")
    if origen not in ORIGENES:
        raise NpcClaveError(f"{donde}: 'origen' debe ser uno de {ORIGENES}, no {origen!r}.")
    ancla, modelo = d.get("ancla"), d.get("modelo")
    if origen == "ancla":
        if not isinstance(ancla, dict) or ("zona" in ancla) == ("lugar" in ancla):
            raise NpcClaveError(f"{donde}: con origen 'ancla' hace falta un 'ancla' con 'zona' o 'lugar' (solo uno).")
        if isinstance(modelo, bool) or not isinstance(modelo, int) or modelo < 0:
            raise NpcClaveError(f"{donde}: con origen 'ancla' hace falta 'modelo' (entero >= 0).")
    retrato = d.get("retrato", {})
    if not isinstance(retrato, dict):
        raise NpcClaveError(f"{donde}: 'retrato' debe ser un objeto.")
    vistos.add(ident)
    return NpcClave(ident, d["nombre"].strip(), d["grupo"], d["rol"].strip(), origen,
                    dict(ancla) if origen == "ancla" else None, modelo if origen == "ancla" else None, dict(retrato))


def cargar_npcs(ruta=None):
    ruta = Path(ruta) if ruta is not None else RUTA_NPC_CLAVE
    try:
        datos = json.loads(ruta.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise NpcClaveError(f"{ruta.name}: el archivo no existe.") from None
    except json.JSONDecodeError as error:
        raise NpcClaveError(f"{ruta.name}: JSON inválido (línea {error.lineno}, columna {error.colno}): {error.msg}") from None
    lista = datos.get("npcs") if isinstance(datos, dict) else None
    if not isinstance(lista, list) or not MIN_NPC <= len(lista) <= MAX_NPC:
        raise NpcClaveError(f"{ruta.name}: 'npcs' debe ser una lista de {MIN_NPC} a {MAX_NPC} NPC.")
    vistos = set()
    return tuple(_npc(i, d, vistos) for i, d in enumerate(lista))


def ids_npc(npcs=None):
    return [n.id for n in (npcs if npcs is not None else cargar_npcs())]


def npc_por_id(ident, npcs=None):
    return next((n for n in (npcs if npcs is not None else cargar_npcs()) if n.id == ident), None)
