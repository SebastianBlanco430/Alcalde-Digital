# Estrellas por misión y medallas por minijuego (capa visual de las misiones). Python puro, con tests en
# tests/test_logros_minijuegos.py.
#
# Qué guarda: la mejor cantidad de estrellas (0..3) de cada misión y la medalla de «primer resultado perfecto» de cada
# minijuego. NO toca reglas, pago ni confianza: es solo un recuerdo para la interfaz.
#
# Dónde: un archivo NUEVO y opcional, <carpeta de ajustes>/logros_minijuegos.json (la misma carpeta que ajustes.json:
# ~/.alcalde_digital o $ALCALDE_AJUSTES_DIR). Si no existe o está roto se empieza sin ninguna estrella ni medalla; la
# partida guardada (partida.json) no cambia de formato.
#
# APAGADO: ALCALDE_LOGROS=0 (o LOGROS = False) no lee ni escribe el disco; las estrellas se muestran igual, sin recordarse.

import json
import os
from pathlib import Path

LOGROS = True
VERSION = 1
NOMBRE_ARCHIVO = "logros_minijuegos.json"
MAX_ENTRADAS = 500


def activo():
    valor = os.environ.get("ALCALDE_LOGROS", "").strip().lower()
    if valor in ("0", "false", "no", "off"):
        return False
    if valor in ("1", "true", "si", "sí", "on"):
        return True
    return bool(LOGROS)


def ruta_por_defecto():
    elegido = os.environ.get("ALCALDE_AJUSTES_DIR")
    carpeta = Path(elegido) if elegido else Path.home() / ".alcalde_digital"
    return carpeta / NOMBRE_ARCHIVO


def vacio():
    return {"version": VERSION, "estrellas": {}, "medallas": {}}


def sanear(datos):
    """Devuelve una copia válida de `datos` (lo inválido se descarta)."""
    limpio = vacio()
    if not isinstance(datos, dict):
        return limpio
    estrellas = datos.get("estrellas")
    if isinstance(estrellas, dict):
        for clave, valor in list(estrellas.items())[:MAX_ENTRADAS]:
            if isinstance(clave, str) and isinstance(valor, int) and not isinstance(valor, bool):
                limpio["estrellas"][clave] = max(0, min(3, valor))
    medallas = datos.get("medallas")
    if isinstance(medallas, dict):
        for clave, valor in list(medallas.items())[:MAX_ENTRADAS]:
            if isinstance(clave, str) and valor is True:
                limpio["medallas"][clave] = True
    return limpio


def cargar(ruta=None):
    if not activo():
        return vacio()
    ruta = Path(ruta) if ruta is not None else ruta_por_defecto()
    try:
        with open(ruta, encoding="utf-8") as archivo:
            return sanear(json.load(archivo))
    except (OSError, ValueError):
        return vacio()


def guardar(datos, ruta=None):
    """Escritura atómica. Devuelve True si se guardó (False con la bandera apagada o sin disco)."""
    if not activo():
        return False
    ruta = Path(ruta) if ruta is not None else ruta_por_defecto()
    try:
        ruta.parent.mkdir(parents=True, exist_ok=True)
        temporal = ruta.with_suffix(".tmp")
        with open(temporal, "w", encoding="utf-8") as archivo:
            json.dump(sanear(datos), archivo, ensure_ascii=False, indent=1)
        os.replace(temporal, ruta)
        return True
    except OSError:
        return False


def anotar(datos, mision_id, minijuego_id, estrellas, perfecto):
    """Anota un resultado en `datos` (lo modifica). Devuelve {"mejor": int, "mejoro": bool, "medalla_nueva": bool}."""
    datos.setdefault("estrellas", {})
    datos.setdefault("medallas", {})
    estrellas = max(0, min(3, int(estrellas)))
    previa = datos["estrellas"].get(mision_id, 0) if mision_id else 0
    mejoro = bool(mision_id) and estrellas > previa
    if mejoro:
        datos["estrellas"][mision_id] = estrellas
    medalla_nueva = bool(perfecto) and bool(minijuego_id) and not datos["medallas"].get(minijuego_id)
    if medalla_nueva:
        datos["medallas"][minijuego_id] = True
    return {"mejor": max(previa, estrellas), "mejoro": mejoro, "medalla_nueva": medalla_nueva}


def registrar(mision_id, minijuego_id, estrellas, perfecto, ruta=None):
    """Carga, anota y guarda. Nunca lanza: ante cualquier problema devuelve lo anotado en memoria."""
    try:
        datos = cargar(ruta)
        salida = anotar(datos, mision_id, minijuego_id, estrellas, perfecto)
        if salida["mejoro"] or salida["medalla_nueva"]:
            guardar(datos, ruta)
        return salida
    except Exception:                    # noqa: BLE001  los logros nunca pueden romper el cierre de una misión
        return {"mejor": int(estrellas), "mejoro": False, "medalla_nueva": False}
