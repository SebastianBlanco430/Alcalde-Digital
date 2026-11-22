# Caché de los clips horneados de la animación humana (Python puro: NO importa ursina ni panda3d).
# La usa frontend/animacion_humana._construir_clip.
#
# Por qué (M7.2): hornear los clips (marcha, escalón, salto, gestos, posturas...) de los ~8 modelos .glb costaba ~7 s
# de cada arranque. Es un cálculo determinista: el mismo esqueleto, las mismas poses y el mismo código dan siempre
# las mismas tablas h,p,r,x,y,z por hueso. Se guardan esas tablas (float32, que es lo que guarda Panda en
# PTA_stdfloat: no se pierde nada) y el AnimBundle se rearma con ellas sin recalcular la cinemática.
#
# CLAVE: huella del esqueleto (huesos, padres y matrices de reposo e Idle) + nombre del clip + las poses mismas (repr
#   exacto de sus floats) + huella del código que convierte poses en tablas (animacion_humana.py y
#   animacion_humana_calculos.py) + versión de Panda + FORMATO. Cambiar el modelo, las poses o ese código la invalida
#   sola. Además hay una caché en memoria (el mismo modelo se hornea dos veces: jugador y NPC con posturas).
# DÓNDE: <carpeta de backend/datos/cache_mundo.directorio()>/animacion/<huella del código>/<clave>.clip
#   ($ALCALDE_CACHE_DIR o ~/.alcalde_digital/cache). Al estrenar una huella de código nueva se borran las carpetas de
#   las huellas anteriores. Un archivo ausente, truncado o ilegible se ignora y el clip se recalcula: nunca impide jugar.
# APAGARLA: ALCALDE_CACHE_ANIMACION=0 (o CACHE_ANIMACION = False) recalcula siempre, como antes.

import hashlib
import os
import pickle
import shutil
import sys
import tempfile
from array import array
from pathlib import Path

CACHE_ANIMACION = True
FORMATO = 1                       # se sube si cambia la forma de guardar (invalida todo lo anterior)
CANALES = "hprxyz"
_FRONTEND = Path(__file__).resolve().parent
ARCHIVOS_CODIGO = ("animacion_humana.py", "animacion_humana_calculos.py", "cache_animacion_calculos.py")

_memoria = {}                     # clave -> tablas (también lo leído de disco)
_huella = []
_limpiadas = set()


def cache_animacion_activa(valor=None):
    valor = (os.environ.get("ALCALDE_CACHE_ANIMACION", "") if valor is None else valor).strip().lower()
    if valor in ("1", "true", "si", "sí", "on"):
        return True
    if valor in ("0", "false", "no", "off"):
        return False
    return bool(CACHE_ANIMACION)


def directorio_base():
    from backend.datos import cache_mundo       # misma ubicación que la caché del mundo
    return cache_mundo.directorio() / "animacion"


def huella_del_codigo(archivos=None):
    """Huella (hex, 16) del contenido de los .py que convierten poses en tablas. Se calcula una vez."""
    if archivos is None and _huella:
        return _huella[0]
    h = hashlib.sha256(f"{FORMATO}|{sys.version_info[:2]}".encode())
    if archivos is None:
        # ARQ-002: en el ejecutable los .py no están en disco (FileNotFoundError: la caché nunca funcionaba y se horneaban
        # todos los clips en cada arranque). Ahí la huella es la del propio ejecutable.
        from backend.datos import cache_mundo
        exe = cache_mundo.huella_ejecutable()
        if exe is not None:
            h.update(exe.encode())
            valor = h.hexdigest()[:16]
            _huella.append(valor)
            return valor
    for ruta in (archivos or [_FRONTEND / n for n in ARCHIVOS_CODIGO]):
        h.update(Path(ruta).name.encode())
        h.update(b"\0")
        h.update(Path(ruta).read_bytes())
    valor = h.hexdigest()[:16]
    if archivos is None:
        _huella.append(valor)
    return valor


def huella_esqueleto(orden, padres, matrices_reposo, matrices_idle):
    """orden: nombres de hueso; padres: {hueso: padre|None}; matrices_*: {hueso: 16 floats}."""
    h = hashlib.sha256()
    for nombre in orden:
        h.update(repr((nombre, padres.get(nombre), tuple(matrices_reposo[nombre]),
                       tuple(matrices_idle[nombre]) if nombre in matrices_idle else None)).encode())
    extra = sorted(n for n in matrices_idle if n not in padres)     # canales de Idle sin hueso: también cuentan
    for nombre in extra:
        h.update(repr((nombre, tuple(matrices_idle[nombre]))).encode())
    return h.hexdigest()


def clave_clip(huella_esq, nombre, fps, poses, version_panda="", huella_codigo=None):
    h = hashlib.sha256()
    h.update(repr((FORMATO, huella_esq, nombre, fps, len(poses), version_panda,
                   huella_codigo or huella_del_codigo())).encode())
    for pose in poses:
        h.update(repr(pose).encode())
    return h.hexdigest()[:32]


# -- Tablas: [(hueso, índice del padre en la lista o -1, {canal: [floats]})] en el orden en que se crean los canales --

def empaquetar(tablas):
    return [(hueso, padre, {k: array("f", v).tobytes() for k, v in series.items()}) for hueso, padre, series in tablas]


def desempaquetar(datos):
    tablas = []
    for hueso, padre, series in datos:
        if not isinstance(hueso, str) or not isinstance(padre, int) or set(series) != set(CANALES):
            raise ValueError("tabla de clip mal formada")
        valores = {}
        for k, crudo in series.items():
            a = array("f")
            a.frombytes(crudo)
            valores[k] = a.tolist()
        tablas.append((hueso, padre, valores))
    return tablas


def _ruta(clave, carpeta=None):
    return (Path(carpeta) if carpeta is not None else directorio_base() / huella_del_codigo()) / f"{clave}.clip"


def obtener(clave, carpeta=None):
    """Tablas del clip o None (no está, o el archivo no sirve)."""
    if clave in _memoria:
        return _memoria[clave]
    try:
        with open(_ruta(clave, carpeta), "rb") as archivo:
            tablas = desempaquetar(pickle.load(archivo))
    except Exception:      # noqa: BLE001 — ausente, truncado, de otra versión...: se recalcula
        return None
    _memoria[clave] = tablas
    return tablas


def _limpiar_viejas(carpeta):
    padre = carpeta.parent
    if padre in _limpiadas:
        return
    _limpiadas.add(padre)
    for otra in padre.iterdir():
        if otra.is_dir() and otra != carpeta:
            shutil.rmtree(otra, ignore_errors=True)


def guardar(clave, tablas, carpeta=None):
    """Guarda las tablas (memoria y disco). Devuelve True si quedó en disco. Nunca lanza."""
    _memoria[clave] = tablas
    try:
        ruta = _ruta(clave, carpeta)
        ruta.parent.mkdir(parents=True, exist_ok=True)
        if carpeta is None:
            _limpiar_viejas(ruta.parent)
        descriptor, temporal = tempfile.mkstemp(dir=str(ruta.parent), prefix=ruta.stem, suffix=".tmp")
        try:
            with os.fdopen(descriptor, "wb") as archivo:
                pickle.dump(empaquetar(tablas), archivo, protocol=pickle.HIGHEST_PROTOCOL)
            os.replace(temporal, ruta)
        finally:
            if os.path.exists(temporal):
                os.remove(temporal)
        return True
    except Exception as error:      # noqa: BLE001 — disco lleno, sin permisos...: se juega igual
        print(f"[cache_animacion] no se pudo guardar {clave}: {type(error).__name__}: {error}", file=sys.stderr)
        return False


def vaciar_memoria():
    _memoria.clear()
