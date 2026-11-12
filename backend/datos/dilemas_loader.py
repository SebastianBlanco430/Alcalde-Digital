# Cargador de los dilemas de uso consciente (puro, sin ursina): lee backend/datos/dilemas_extra.json, lo valida y devuelve
# objetos inmutables. Un dilema mal escrito NO se salta en silencio: ValueError con su id (un JSON a medias dejaría
# dilemas sin su consecuencia). Quien lo llama (backend/logica/dilemas.envolver) decide qué hacer: sin dilemas el juego
# sigue como antes.
#
# Esquema y reglas: docs/PLAN_FINAL.md §8 (y tests/test_dilemas_extra.py, que vigila el contenido). Aquí solo se vigila
# lo que haría fallar al juego: forma, tipos, indicadores y grupos válidos, ids únicos, ventana de días, un único
# marcador {cuando} en los mensajes retardados y que todo efecto se pueda crear con efectos_retardados.crear_efecto.

import json
from collections import namedtuple
from pathlib import Path

from backend.logica import efectos_retardados

RUTA_DILEMAS = Path(__file__).resolve().parent / "dilemas_extra.json"
VERSION = 1
DIAS_MAX = 7
MAX_TEXTO = 400            # caracteres por texto visible: un JSON editado a mano no puede meter textos enormes en la UI

Inmediato = namedtuple("Inmediato", "texto deltas confianza")
Retardado = namedtuple("Retardado", "horas clave mensaje deltas confianza")
Opcion = namedtuple("Opcion", "id etiqueta inmediato retardado")
Dilema = namedtuple("Dilema", "id titulo tema dia_min dia_max situacion opciones ignorar")


def _texto(valor, nombre):
    if not isinstance(valor, str) or not valor.strip():
        raise ValueError(f"{nombre}: se esperaba un texto no vacío.")
    if len(valor.strip()) > MAX_TEXTO:
        raise ValueError(f"{nombre}: el texto pasa de {MAX_TEXTO} caracteres ({len(valor.strip())}).")
    return valor.strip()


def _entero(valor, nombre, minimo, maximo):
    if isinstance(valor, bool) or not isinstance(valor, int) or not minimo <= valor <= maximo:
        raise ValueError(f"{nombre}: se esperaba un entero entre {minimo} y {maximo}, no {valor!r}.")
    return valor


def _tabla(crudo, nombre):
    if not isinstance(crudo, dict):
        raise ValueError(f"{nombre}: se esperaba un objeto.")
    return dict(crudo)


def _retardado(crudo, nombre, con_marcador=True):
    if not isinstance(crudo, dict):
        raise ValueError(f"{nombre}: se esperaba un objeto.")
    horas = crudo.get("horas")
    if isinstance(horas, bool) or not isinstance(horas, (int, float)) or not 1 <= horas <= 72:
        raise ValueError(f"{nombre}: «horas» debe estar entre 1 y 72, no {horas!r}.")
    mensaje = _texto(crudo.get("mensaje"), f"{nombre}.mensaje")
    if con_marcador and (not mensaje.startswith("{cuando} ") or mensaje.count("{") != 1 or mensaje.count("}") != 1):
        raise ValueError(f"{nombre}: el mensaje debe empezar con «{{cuando}} » y no llevar otro marcador.")
    clave = _texto(crudo.get("clave"), f"{nombre}.clave")
    deltas, confianza = _tabla(crudo.get("deltas", {}), f"{nombre}.deltas"), _tabla(crudo.get("confianza", {}), f"{nombre}.confianza")
    # Valida indicadores y grupos con la misma función que usará el juego (ValueError si algo no cuadra).
    efectos_retardados.crear_efecto(clave, mensaje.replace("{cuando}", "Ayer"), deltas, confianza)
    return Retardado(float(horas), clave, mensaje, deltas, confianza)


def _opcion(crudo, nombre):
    if not isinstance(crudo, dict):
        raise ValueError(f"{nombre}: se esperaba un objeto.")
    ident = _texto(crudo.get("id"), f"{nombre}.id")
    nombre = f"{nombre}/{ident}"
    inmediato = crudo.get("inmediato")
    if not isinstance(inmediato, dict):
        raise ValueError(f"{nombre}: falta «inmediato».")
    texto = _texto(inmediato.get("texto"), f"{nombre}.inmediato.texto")
    deltas = _tabla(inmediato.get("deltas", {}), f"{nombre}.inmediato.deltas")
    confianza = _tabla(inmediato.get("confianza", {}), f"{nombre}.inmediato.confianza")
    efectos_retardados.crear_efecto("inmediato", texto, deltas, confianza)
    return Opcion(ident, _texto(crudo.get("etiqueta"), f"{nombre}.etiqueta"), Inmediato(texto, deltas, confianza),
                  _retardado(crudo.get("retardado"), f"{nombre}.retardado"))


def _dilema(crudo):
    if not isinstance(crudo, dict):
        raise ValueError("Un dilema debe ser un objeto.")
    ident = _texto(crudo.get("id"), "dilema.id")
    dia_min = _entero(crudo.get("dia_min"), f"{ident}.dia_min", 1, DIAS_MAX)
    dia_max = _entero(crudo.get("dia_max"), f"{ident}.dia_max", 1, DIAS_MAX)
    if dia_min > dia_max:
        raise ValueError(f"{ident}: dia_min ({dia_min}) mayor que dia_max ({dia_max}).")
    crudas = crudo.get("opciones")
    if not isinstance(crudas, list) or not 2 <= len(crudas) <= 3:
        raise ValueError(f"{ident}: debe tener 2 o 3 opciones.")
    opciones = tuple(_opcion(o, ident) for o in crudas)
    if len({o.id for o in opciones}) != len(opciones):
        raise ValueError(f"{ident}: ids de opción repetidos.")
    ignorar = crudo.get("ignorar")
    return Dilema(ident, _texto(crudo.get("titulo"), f"{ident}.titulo"), str(crudo.get("tema", "")), dia_min, dia_max,
                  _texto(crudo.get("situacion"), f"{ident}.situacion"), opciones,
                  _retardado(ignorar, f"{ident}.ignorar") if ignorar is not None else None)


# Todos los dilemas válidos (tupla, en el orden del archivo). ValueError si el archivo no existe, no es JSON o algo no
# cuadra. Los ids de dilema y las claves de efecto no se pueden repetir.
def cargar_dilemas(ruta=None):
    ruta = Path(ruta) if ruta is not None else RUTA_DILEMAS
    try:
        datos = json.loads(ruta.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise ValueError(f"{ruta.name}: el archivo no existe.") from None
    except json.JSONDecodeError as error:
        raise ValueError(f"{ruta.name}: JSON inválido (línea {error.lineno}): {error.msg}") from None
    if not isinstance(datos, dict) or datos.get("version") != VERSION or not isinstance(datos.get("dilemas"), list):
        raise ValueError(f"{ruta.name}: formato desconocido (se esperaba version {VERSION} y una lista «dilemas»).")
    dilemas = tuple(_dilema(d) for d in datos["dilemas"])
    ids = [d.id for d in dilemas]
    if len(set(ids)) != len(ids):
        raise ValueError(f"{ruta.name}: ids de dilema repetidos.")
    claves = [o.retardado.clave for d in dilemas for o in d.opciones] + [d.ignorar.clave for d in dilemas if d.ignorar]
    if len(set(claves)) != len(claves):
        raise ValueError(f"{ruta.name}: claves de efecto repetidas.")
    return dilemas
