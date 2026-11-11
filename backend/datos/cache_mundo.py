# Caché en disco del mundo construido (Python puro). Construir el mundo grande son ~13 s de cálculo determinista: mismo
# código y misma semilla dan siempre el mismo mundo, así que se guarda ya construido (pickle, ~8 MB) y los arranques
# siguientes lo cargan en ~0,05 s.
#
#   construir_con_cache(nombre, semilla, constructor)   -> el mundo (de la caché si vale; si no, lo construye y lo guarda)
#
# CUÁNDO VALE: la clave del archivo incluye el nombre, la semilla, la versión de Python y una huella del CONTENIDO de todos
# los .py y .json de backend/ (cualquier cambio de código o de datos la invalida sola; no hay que acordarse de borrar
# nada). Un archivo ilegible, de otra versión o corrupto se ignora y se reconstruye: la caché nunca puede impedir jugar.
# Los archivos viejos del mismo mundo se borran al guardar uno nuevo.
#
# DÓNDE: $ALCALDE_CACHE_DIR o ~/.alcalde_digital/cache. Es un pickle escrito por el propio juego en la carpeta del
# usuario (no se cargan pickles de la red ni de la carpeta del repositorio).
# APAGARLA: ALCALDE_SIN_CACHE_MUNDO=1 (o CACHE_MUNDO = False) construye siempre, como antes.

import hashlib
import os
import pickle
import sys
import tempfile
from pathlib import Path

CACHE_MUNDO = True
FORMATO = 1                      # se sube si cambia la forma de guardar (invalida todo lo anterior)
_RAIZ_BACKEND = Path(__file__).resolve().parent.parent
_EXTENSIONES = (".py", ".json")
_huella = []


def activa():
    return CACHE_MUNDO and os.environ.get("ALCALDE_SIN_CACHE_MUNDO", "").strip().lower() not in ("1", "true", "si", "sí", "on")


def directorio():
    elegido = os.environ.get("ALCALDE_CACHE_DIR")
    return Path(elegido) if elegido else Path.home() / ".alcalde_digital" / "cache"


def huella_del_codigo(raiz=None):
    """Huella (hex) del contenido de los .py y .json de backend/ (ruta relativa + bytes, en orden). Se calcula una vez."""
    if raiz is None and _huella:
        return _huella[0]
    base = Path(raiz) if raiz is not None else _RAIZ_BACKEND
    h = hashlib.sha256()
    for ruta in sorted(p for p in base.rglob("*") if p.suffix in _EXTENSIONES and "__pycache__" not in p.parts):
        h.update(ruta.relative_to(base).as_posix().encode("utf-8"))
        h.update(b"\0")
        h.update(ruta.read_bytes())
        h.update(b"\0")
    valor = h.hexdigest()
    if raiz is None:
        _huella.append(valor)
    return valor


def ruta_de(nombre, semilla, carpeta=None, huella=None):
    clave = f"{FORMATO}|{nombre}|{semilla!r}|{sys.version_info[:3]}|{huella or huella_del_codigo()}"
    resumen = hashlib.sha256(clave.encode("utf-8")).hexdigest()[:20]
    return (Path(carpeta) if carpeta is not None else directorio()) / f"mundo_{nombre}_{resumen}.pickle"


def _cargar(ruta):
    try:
        with open(ruta, "rb") as archivo:
            return pickle.load(archivo)
    except Exception:      # noqa: BLE001 — ausente, truncado, de otra versión...: se reconstruye
        return None


def _guardar(ruta, mundo, nombre):
    try:
        ruta.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporal = tempfile.mkstemp(dir=str(ruta.parent), prefix=ruta.stem, suffix=".tmp")
        try:
            with os.fdopen(descriptor, "wb") as archivo:
                pickle.dump(mundo, archivo, protocol=pickle.HIGHEST_PROTOCOL)
            os.replace(temporal, ruta)
        finally:
            if os.path.exists(temporal):
                os.remove(temporal)
        for viejo in ruta.parent.glob(f"mundo_{nombre}_*.pickle"):       # los de otro código u otra semilla
            if viejo != ruta:
                try:
                    viejo.unlink()
                except OSError:
                    pass
        return True
    except Exception as error:      # noqa: BLE001 — disco lleno, sin permisos, algo no serializable: se juega igual
        print(f"[cache_mundo] no se pudo guardar {ruta.name}: {type(error).__name__}: {error}", file=sys.stderr)
        return False


def construir_con_cache(nombre, semilla, constructor, carpeta=None, huella=None):
    """El mundo `nombre` de `semilla`: de la caché si hay una válida; si no, `constructor()` y se guarda para la próxima."""
    if not activa():
        return constructor()
    try:
        ruta = ruta_de(nombre, semilla, carpeta, huella)
    except OSError:
        return constructor()
    if ruta.is_file():
        mundo = _cargar(ruta)
        if mundo is not None:
            return mundo
    mundo = constructor()
    _guardar(ruta, mundo, nombre)
    return mundo
