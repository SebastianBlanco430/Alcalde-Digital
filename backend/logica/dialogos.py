# Diálogo reactivo (modelo puro, sin motor gráfico): dado un NPC clave y el GameState elige CÓMO habla. Todo el texto, los
# umbrales y las reglas viven en backend/datos/dialogos/*.json (_comun.json = valores por defecto; <npc>.json = lo
# propio de cada NPC). No hay frases ni números en el código.
#
# TONO (por la relación con el NPC y la confianza de su grupo; manda primero la relación personal):
#   cortante   relación <= cortante.relacion_max, o (relación neutra y) confianza <= cortante.confianza_max
#   exclusivo  relación >= exclusivo.relacion_min, o (relación neutra y) confianza >= exclusivo.confianza_min
#   normal     el resto
# ACTITUD (nervioso / evasiva / hostil): si alguna `reglas_actitud` se cumple (banderas del GameState: el jugador
# «mintió», acusó en falso, presionó...). Gana sobre el tono y la primera regla que cumple decide; las del NPC van antes
# que las comunes. Cada regla: {"actitud", "flags": [todas], "alguna": [al menos una], "sin": [ninguna]}.
# COOPERACIÓN: con relación >= `relacion_min`, sin actitud negativa, el NPC ofrece una pista y puede dar una
# evidencia (UNA vez: evidencia.otorgar es idempotente). El texto de la pista y de la entrega salen del JSON.
#
# Sin GameState (partida en línea o ALCALDE_GAMESTATE=0) siempre responde el tono «normal» y sin ayuda.

import copy
import json
from dataclasses import dataclass
from pathlib import Path

from backend.logica import evidencia
from backend.logica.game_state import RELACION_INICIAL

CARPETA_DIALOGOS = Path(__file__).resolve().parents[1] / "datos" / "dialogos"
ARCHIVO_COMUN = "_comun.json"
TONOS = ("cortante", "normal", "exclusivo")
ACTITUDES = ("nervioso", "evasiva", "hostil")
TONO_FIJO = "normal"


class DialogoError(ValueError):
    pass


@dataclass(frozen=True)
class Ayuda:
    evidencia: str | None
    entrega: str = ""


@dataclass(frozen=True)
class Respuesta:
    npc_id: str
    nombre: str
    tono: str
    actitud: str | None
    expresion: str
    lineas: tuple
    comentario: str = ""
    ayuda: Ayuda | None = None


def _texto(v):
    return isinstance(v, str) and v.strip() != ""


def _lista_textos(v):
    return isinstance(v, list) and bool(v) and all(_texto(t) for t in v)


def _leer(ruta):
    try:
        return json.loads(Path(ruta).read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise DialogoError(f"{Path(ruta).name}: el archivo no existe.") from None
    except json.JSONDecodeError as error:
        raise DialogoError(f"{Path(ruta).name}: JSON inválido (línea {error.lineno}, columna {error.colno}): {error.msg}") from None


# -- Catálogo (datos ya fusionados y validados) --

class CatalogoDialogos:

    def __init__(self, comun, por_npc):
        self.comun = comun
        self.por_npc = por_npc
        self._cache = {}

    # Datos efectivos de un NPC: lo común con lo propio encima (umbrales y líneas se fusionan clave a clave).
    def datos_de(self, npc_id):
        if npc_id not in self._cache:
            propio = self.por_npc.get(npc_id, {})
            umbrales = copy.deepcopy(self.comun["umbrales"])
            for clave, valor in (propio.get("umbrales") or {}).items():
                if isinstance(valor, dict):
                    umbrales.setdefault(clave, {}).update(valor)
                else:
                    umbrales[clave] = valor
            cooperacion = propio.get("cooperacion")
            if cooperacion is not None:
                cooperacion = dict(cooperacion)
                cooperacion.setdefault("relacion_min", umbrales["ayuda_relacion_min"])
            self._cache[npc_id] = {
                "umbrales": umbrales,
                "expresiones": {**self.comun["expresiones"], **(propio.get("expresiones") or {})},
                "reglas": list(propio.get("reglas_actitud") or []) + list(self.comun["reglas_actitud"]),
                "lineas": {**self.comun["lineas"], **(propio.get("lineas") or {})},
                "comentarios": dict(propio.get("comentarios") or {}),
                "cooperacion": cooperacion,
            }
        return self._cache[npc_id]


def _validar_reglas(donde, reglas, errores):
    if not isinstance(reglas, list):
        errores.append(f"{donde}.reglas_actitud: debe ser una lista")
        return
    for i, r in enumerate(reglas):
        d = f"{donde}.reglas_actitud[{i}]"
        if not isinstance(r, dict) or r.get("actitud") not in ACTITUDES:
            errores.append(f"{d}: 'actitud' debe ser una de {ACTITUDES}")
            continue
        claves = [k for k in ("flags", "alguna", "sin") if k in r]
        if not claves or not any(k in r for k in ("flags", "alguna")):
            errores.append(f"{d}: necesita 'flags' o 'alguna' (lista de banderas)")
        for k in claves:
            if not _lista_textos(r[k]):
                errores.append(f"{d}.{k}: lista no vacía de textos")


def _validar_lineas(donde, lineas, errores, completas):
    if not isinstance(lineas, dict):
        errores.append(f"{donde}.lineas: debe ser un objeto")
        return
    permitidas = TONOS + ACTITUDES
    for clave, valor in lineas.items():
        if clave not in permitidas:
            errores.append(f"{donde}.lineas.{clave}: clave desconocida; válidas: {permitidas}")
        elif not _lista_textos(valor):
            errores.append(f"{donde}.lineas.{clave}: lista no vacía de textos")
    if completas:
        for clave in permitidas:
            if clave not in lineas:
                errores.append(f"{donde}.lineas.{clave}: falta (el archivo común debe tener todas)")


def _validar_umbrales(donde, u, errores):
    if not isinstance(u, dict):
        errores.append(f"{donde}.umbrales: debe ser un objeto")
        return
    for clave, valor in u.items():
        if clave == "ayuda_relacion_min":
            ok = isinstance(valor, (int, float)) and not isinstance(valor, bool) and 0 <= valor <= 100
        elif clave in ("cortante", "exclusivo"):
            ok = isinstance(valor, dict) and all(
                k in ("relacion_max", "confianza_max", "relacion_min", "confianza_min")
                and isinstance(v, (int, float)) and not isinstance(v, bool) and 0 <= v <= 100 for k, v in valor.items())
        else:
            ok = False
        if not ok:
            errores.append(f"{donde}.umbrales.{clave}: valor o clave inválidos")


def _validar_comun(datos):
    errores = []
    if not isinstance(datos, dict):
        return ["_comun.json: debe ser un objeto"]
    _validar_umbrales("_comun", datos.get("umbrales"), errores)
    u = datos.get("umbrales") if isinstance(datos.get("umbrales"), dict) else {}
    for clave, campos in (("cortante", ("relacion_max", "confianza_max")), ("exclusivo", ("relacion_min", "confianza_min"))):
        for campo in campos:
            if campo not in (u.get(clave) or {}):
                errores.append(f"_comun.umbrales.{clave}.{campo}: falta")
    if "ayuda_relacion_min" not in u:
        errores.append("_comun.umbrales.ayuda_relacion_min: falta")
    exp = datos.get("expresiones")
    if not isinstance(exp, dict) or any(k not in TONOS + ACTITUDES or not _texto(v) for k, v in exp.items()) \
            or any(k not in exp for k in TONOS + ACTITUDES):
        errores.append(f"_comun.expresiones: debe dar un nombre de expresión para cada uno de {TONOS + ACTITUDES}")
    _validar_reglas("_comun", datos.get("reglas_actitud", []), errores)
    _validar_lineas("_comun", datos.get("lineas"), errores, completas=True)
    return errores


def _validar_npc(nombre, datos):
    errores = []
    if not isinstance(datos, dict) or not _texto(datos.get("npc")):
        return [f"{nombre}: falta 'npc' (id del NPC)"]
    d = datos["npc"]
    if "umbrales" in datos:
        _validar_umbrales(d, datos["umbrales"], errores)
    if "expresiones" in datos:
        exp = datos["expresiones"]
        if not isinstance(exp, dict) or any(k not in TONOS + ACTITUDES or not _texto(v) for k, v in exp.items()):
            errores.append(f"{d}.expresiones: claves de tono/actitud con nombre de expresión")
    _validar_reglas(d, datos.get("reglas_actitud", []), errores)
    _validar_lineas(d, datos.get("lineas", {}), errores, completas=False)
    com = datos.get("comentarios", {})
    if not isinstance(com, dict) or any(k not in TONOS + ACTITUDES or not _texto(v) for k, v in com.items()):
        errores.append(f"{d}.comentarios: claves de tono/actitud con texto")
    coop = datos.get("cooperacion")
    if coop is not None:
        if not isinstance(coop, dict) or not _lista_textos(coop.get("texto")):
            errores.append(f"{d}.cooperacion.texto: lista no vacía de textos")
        elif coop.get("evidencia") is not None and (not _texto(coop["evidencia"]) or ":" in coop["evidencia"]
                                                    or not _texto(coop.get("entrega"))):
            errores.append(f"{d}.cooperacion: con 'evidencia' (id sin ':') hace falta 'entrega' (texto)")
        rm = (coop or {}).get("relacion_min")
        if rm is not None and (isinstance(rm, bool) or not isinstance(rm, (int, float)) or not 0 <= rm <= 100):
            errores.append(f"{d}.cooperacion.relacion_min: número 0-100")
    return errores


# Carga _comun.json y todos los <npc>.json de la carpeta; todos los errores juntos en un solo DialogoError.
def cargar(carpeta=None):
    carpeta = Path(carpeta) if carpeta is not None else CARPETA_DIALOGOS
    comun = _leer(carpeta / ARCHIVO_COMUN)
    errores = _validar_comun(comun)
    por_npc = {}
    for ruta in sorted(carpeta.glob("*.json")):
        if ruta.name == ARCHIVO_COMUN:
            continue
        datos = _leer(ruta)
        errores += _validar_npc(ruta.name, datos)
        if isinstance(datos, dict) and _texto(datos.get("npc")):
            if datos["npc"] in por_npc:
                errores.append(f"{ruta.name}: el NPC {datos['npc']!r} ya tiene otro archivo")
            por_npc[datos["npc"]] = datos
    if errores:
        raise DialogoError(f"Diálogos inválidos ({len(errores)} error(es)):\n- " + "\n- ".join(errores))
    return CatalogoDialogos(comun, por_npc)


# -- Decisión --

def calcular_tono(umbrales, relacion, confianza):
    c, e = umbrales["cortante"], umbrales["exclusivo"]
    if relacion <= c["relacion_max"]:
        return "cortante"
    if relacion >= e["relacion_min"]:
        return "exclusivo"
    if confianza <= c["confianza_max"]:
        return "cortante"
    if confianza >= e["confianza_min"]:
        return "exclusivo"
    return "normal"


def _regla_cumple(regla, game_state):
    if not all(game_state.flag(f) for f in regla.get("flags", [])):
        return False
    alguna = regla.get("alguna")
    if alguna and not any(game_state.flag(f) for f in alguna):
        return False
    return not any(game_state.flag(f) for f in regla.get("sin", []))


def calcular_actitud(reglas, game_state):
    return next((r["actitud"] for r in reglas if _regla_cumple(r, game_state)), None)


def _relacion(game_state, npc_id):
    return game_state.relacion(npc_id) if npc_id in game_state.npcs() else float(RELACION_INICIAL)


def _ayuda_posible(cooperacion, game_state, relacion):
    if not cooperacion or relacion < cooperacion["relacion_min"]:
        return None
    ev = cooperacion.get("evidencia")
    if ev is not None and evidencia.tiene(game_state, ev):
        return None
    return Ayuda(ev, cooperacion.get("entrega", ""))


# `npc`: cualquier objeto con id, nombre y grupo (NpcClave). `catalogo`: CatalogoDialogos (si no, se carga el de disco).
# Nunca escribe en el GameState (la evidencia se entrega aparte, con aplicar_ayuda, cuando el jugador la recibe).
def elegir(npc, game_state, catalogo=None):
    catalogo = catalogo if catalogo is not None else cargar()
    datos = catalogo.datos_de(npc.id)
    if game_state is None:
        tono, actitud, ayuda = TONO_FIJO, None, None
    else:
        relacion = _relacion(game_state, npc.id)
        tono = calcular_tono(datos["umbrales"], relacion, game_state.confianza(npc.grupo))
        actitud = calcular_actitud(datos["reglas"], game_state)
        ayuda = None if actitud else _ayuda_posible(datos["cooperacion"], game_state, relacion)
    clave = actitud or tono
    lineas = list(datos["lineas"][clave])
    if ayuda is not None:
        lineas += datos["cooperacion"]["texto"]
        if ayuda.evidencia is not None:
            lineas.append(ayuda.entrega)
    comentario = datos["comentarios"].get(clave) or datos["comentarios"].get(tono, "")
    return Respuesta(npc.id, npc.nombre, tono, actitud, datos["expresiones"][clave], tuple(lineas), comentario, ayuda)


# Entrega la evidencia de la ayuda (una sola vez). True si era nueva; False si no había ayuda, no daba evidencia o ya
# se tenía. Se llama cuando el jugador RECIBE la ayuda (última línea del diálogo).
def aplicar_ayuda(game_state, respuesta):
    ayuda = respuesta.ayuda
    if game_state is None or ayuda is None or ayuda.evidencia is None:
        return False
    return evidencia.otorgar(game_state, ayuda.evidencia, f"npc:{respuesta.npc_id}", datos={"npc": respuesta.npc_id})


# Páginas de un diálogo (estado mínimo de la caja de texto, sin dibujo): una línea por página.
class Paginador:

    def __init__(self, lineas):
        self.lineas = tuple(lineas) or ("",)
        self.indice = 0

    @property
    def actual(self):
        return self.lineas[self.indice]

    @property
    def es_ultima(self):
        return self.indice >= len(self.lineas) - 1

    # Pasa a la página siguiente; False (sin mover nada) si ya era la última.
    def avanzar(self):
        if self.es_ultima:
            return False
        self.indice += 1
        return True
