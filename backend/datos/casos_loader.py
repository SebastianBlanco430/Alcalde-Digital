# Cargador de casos de investigación (puro, sin motor gráfico): lee backend/datos/casos/*.json, valida con
# backend/logica/casos.py y devuelve objetos Caso. cargar_caso (UN archivo) lanza CasoError con el nombre del archivo
# (y la línea, si es un error de sintaxis) si el JSON está roto o es inválido; nunca devuelve un caso a medias.
# cargar_catalogo (la carpeta) se SALTA solo el archivo roto, avisa por stderr y sigue con los demás: un caso mal
# escrito no deja al juego sin los otros.

import json
import sys
from pathlib import Path

from backend.logica.casos import Caso, CasoError

CARPETA_CASOS = Path(__file__).resolve().parent / "casos"


# Carga y valida UN archivo de caso.
def cargar_caso(ruta):
    ruta = Path(ruta)
    try:
        datos = json.loads(ruta.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise CasoError(f"{ruta.name}: el archivo no existe.") from None
    except json.JSONDecodeError as error:
        raise CasoError(f"{ruta.name}: JSON inválido (línea {error.lineno}, columna {error.colno}): {error.msg}") from None
    try:
        return Caso.desde_dict(datos)
    except CasoError as error:
        raise CasoError(f"{ruta.name}: {error}") from None


# Todos los casos VÁLIDOS de la carpeta, por id y ordenados por nombre de archivo. Un archivo roto o inválido se omite
# (su mensaje va a stderr y, si se pasa, a la lista `errores`) y se sigue con los demás. Un id repetido entre dos casos
# válidos sí es un error del catálogo (CasoError): no hay forma de saber cuál es el bueno.
def cargar_catalogo(carpeta=None, errores=None):
    carpeta = Path(carpeta) if carpeta is not None else CARPETA_CASOS
    catalogo, origen = {}, {}
    for ruta in sorted(carpeta.glob("*.json")):
        try:
            caso = cargar_caso(ruta)
        except CasoError as error:
            print(f"[casos] se omite {error}", file=sys.stderr)
            if errores is not None:
                errores.append(str(error))
            continue
        if caso.id in catalogo:
            raise CasoError(f"{ruta.name}: el id {caso.id!r} ya lo usa {origen[caso.id]}.")
        catalogo[caso.id] = caso
        origen[caso.id] = ruta.name
    return catalogo


# El caso con ese id, o CasoError si no está (el mensaje incluye los archivos omitidos por estar rotos).
def cargar_caso_por_id(id_caso, carpeta=None):
    errores = []
    catalogo = cargar_catalogo(carpeta, errores=errores)
    if id_caso not in catalogo:
        omitidos = f" Archivos omitidos: {'; '.join(errores)}" if errores else ""
        raise CasoError(f"No hay un caso con id {id_caso!r}; hay: {sorted(catalogo)}.{omitidos}")
    return catalogo[id_caso]
