# Cargador de los textos del Archivo de casos (backend/datos/archivo_casos_textos.json). Puro: sin motor gráfico.
# Los textos no viven en el código: la lógica (backend/logica/archivo_casos.py) y la vista los reciben ya cargados.

import json
from pathlib import Path

RUTA_TEXTOS = Path(__file__).resolve().parent / "archivo_casos_textos.json"
CLAVES_OBLIGATORIAS = ("titulo", "no_disponible", "vacio", "filtros", "categorias", "resultados", "grupos", "origenes",
                       "plantillas", "secciones", "pista", "posicion")


# Carga y comprueba el JSON. ValueError con el motivo si falta el archivo, está roto o le falta una clave.
def cargar_textos(ruta=None):
    ruta = Path(ruta) if ruta is not None else RUTA_TEXTOS
    try:
        datos = json.loads(ruta.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise ValueError(f"{ruta.name}: el archivo no existe.") from None
    except json.JSONDecodeError as error:
        raise ValueError(f"{ruta.name}: JSON inválido (línea {error.lineno}): {error.msg}") from None
    if not isinstance(datos, dict):
        raise ValueError(f"{ruta.name}: debe ser un objeto JSON.")
    faltan = [c for c in CLAVES_OBLIGATORIAS if c not in datos]
    if faltan:
        raise ValueError(f"{ruta.name}: faltan las claves {faltan}.")
    return datos
