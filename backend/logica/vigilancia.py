# Vigilancia policial (modelo puro, sin motor gráfico): decide QUÉ zonas y marcadores del minimapa hay según la
# confianza del GameState. Con confianza `policia` baja aparecen zonas «vigilancia» y «restringida»; con confianza
# alta, zonas «segura» y un marcador de ayuda. Elementos, umbrales y tiempo de refresco salen de
# backend/datos/vigilancia.json. La vista (frontend/registro_consecuencias.py) solo resuelve las anclas al mundo y
# los vuelca en el registro del minimapa; aquí no hay coordenadas del mundo ni dibujo.
#
# Sin GameState (en línea o ALCALDE_GAMESTATE=0) no hay elementos.

import json
from dataclasses import dataclass
from pathlib import Path

from backend.logica.game_state import GRUPOS

RUTA_VIGILANCIA = Path(__file__).resolve().parents[1] / "datos" / "vigilancia.json"
CLASES = ("zona", "marcador")
TIPOS_ZONA = ("restringida", "vigilancia", "segura")           # los mismos de frontend/minimapa_calculos.TIPOS_ZONA
TIPOS_MARCADOR = ("npc", "mision", "objetivo", "altura")      # ídem TIPOS_MARCADOR
REFRESCO_MIN_S = 0.2


class VigilanciaError(ValueError):
    pass


@dataclass(frozen=True)
class Elemento:
    id: str
    clase: str
    tipo: str
    etiqueta: str
    ancla: dict
    ancho: float = 0.0
    fondo: float = 0.0
    cuando: dict = None


@dataclass(frozen=True)
class ConfigVigilancia:
    refresco_s: float
    elementos: tuple


def _texto(v):
    return isinstance(v, str) and v.strip() != ""


def _numero(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _validar_cuando(donde, cuando):
    if not isinstance(cuando, dict) or not cuando:
        raise VigilanciaError(f"{donde}.cuando: debe ser un objeto no vacío")
    for clave, valor in cuando.items():
        if clave in ("flags", "sin_flags"):
            if not (isinstance(valor, list) and valor and all(_texto(f) for f in valor)):
                raise VigilanciaError(f"{donde}.cuando.{clave}: lista no vacía de textos")
        elif clave in GRUPOS:
            if not isinstance(valor, dict) or not valor or any(k not in ("min", "max") or not _numero(v) for k, v in valor.items()):
                raise VigilanciaError(f"{donde}.cuando.{clave}: rango {{min, max}} numérico")
        else:
            raise VigilanciaError(f"{donde}.cuando.{clave}: clave desconocida; usa {GRUPOS} o flags/sin_flags")


def _elemento(i, d, vistos):
    donde = f"elementos[{i}]"
    if not isinstance(d, dict) or not _texto(d.get("id")):
        raise VigilanciaError(f"{donde}: falta 'id'")
    if d["id"] in vistos:
        raise VigilanciaError(f"{donde}: id repetido {d['id']!r}")
    vistos.add(d["id"])
    clase = d.get("clase")
    if clase not in CLASES:
        raise VigilanciaError(f"{donde}: 'clase' debe ser una de {CLASES}")
    tipos = TIPOS_ZONA if clase == "zona" else TIPOS_MARCADOR
    if d.get("tipo") not in tipos:
        raise VigilanciaError(f"{donde}: 'tipo' de {clase} debe ser uno de {tipos}")
    ancla = d.get("ancla")
    if not isinstance(ancla, dict) or ("zona" in ancla) == ("lugar" in ancla):
        raise VigilanciaError(f"{donde}: 'ancla' necesita 'zona' o 'lugar' (solo uno)")
    ancho = fondo = 0.0
    if clase == "zona":
        ancho, fondo = d.get("ancho"), d.get("fondo")
        if not (_numero(ancho) and _numero(fondo) and ancho > 0 and fondo > 0):
            raise VigilanciaError(f"{donde}: una zona necesita 'ancho' y 'fondo' > 0")
    _validar_cuando(donde, d.get("cuando"))
    return Elemento(d["id"], clase, d["tipo"], str(d.get("etiqueta", "")), dict(ancla), float(ancho), float(fondo), dict(d["cuando"]))


def cargar(ruta=None):
    ruta = Path(ruta) if ruta is not None else RUTA_VIGILANCIA
    try:
        datos = json.loads(ruta.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise VigilanciaError(f"{ruta.name}: el archivo no existe.") from None
    except json.JSONDecodeError as error:
        raise VigilanciaError(f"{ruta.name}: JSON inválido (línea {error.lineno}, columna {error.colno}): {error.msg}") from None
    if not isinstance(datos, dict) or not isinstance(datos.get("elementos"), list):
        raise VigilanciaError(f"{ruta.name}: falta la lista 'elementos'")
    refresco = datos.get("refresco_s", 1.5)
    if not _numero(refresco) or refresco < REFRESCO_MIN_S:
        raise VigilanciaError(f"{ruta.name}: 'refresco_s' debe ser un número >= {REFRESCO_MIN_S}")
    vistos = set()
    return ConfigVigilancia(float(refresco), tuple(_elemento(i, d, vistos) for i, d in enumerate(datos["elementos"])))


def cumple(cuando, game_state):
    for grupo in GRUPOS:
        rango = cuando.get(grupo)
        if rango is None:
            continue
        valor = game_state.confianza(grupo)
        if not rango.get("min", float("-inf")) <= valor <= rango.get("max", float("inf")):
            return False
    if not all(game_state.flag(f) for f in cuando.get("flags", [])):
        return False
    return not any(game_state.flag(f) for f in cuando.get("sin_flags", []))


# Elementos que están activos ahora (tupla vacía sin GameState), en el orden del JSON.
def activos(config, game_state):
    if game_state is None:
        return ()
    return tuple(e for e in config.elementos if cumple(e.cuando, game_state))
