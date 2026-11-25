# Sello de la Torre de la Tradición: QUÉ lleva sello y con qué capa (modelo puro, sin ursina). Hilo conductor:
# docs/HILO_CONDUCTOR.md. Datos en backend/datos/sello_rumores.json; el dibujo es de frontend/sello_tradicion.py.
#
# El antagonista es IMPLÍCITO: la campaña del alcalde de siempre firma la mayoría de los rumores falsos con su emblema,
# y el jugador lo deduce al verlo repetido (y en sus carteles de campaña desde el día 5). Ningún texto lo dice.
# Capas por día (campo «capas»): 1 diminuto y desvaído en la esquina del mensaje; 2 junto al remitente y marca de agua
# en las imágenes de «Señales de edición» y «Comparar»; 3 tamaño completo + espejo en el mundo; 4 como la 3 (los días
# en que hay más rumores falsos sin sello y la radio pregunta).
#
# BANDERA. SELLO = True (o ALCALDE_HILO_SELLO=0, o ALCALDE_HILO=0) lo apaga: ningún mensaje lleva sello.
#
#   sello_rumores.activo()
#   sello_rumores.lleva_sello(id_mision)   -> bool
#   sello_rumores.capa(dia)                -> 1..4
#   sello_rumores.capa_de(id_mision, dia)  -> 1..4 o None (sin sello o bandera apagada)
#   sello_rumores.capa_anuncio(texto, dia) -> capa del anuncio de campaña del día 5 (frontend/carteles_campana.py) o None

import json
import os
from pathlib import Path

from backend.logica import radio_guion

SELLO = True
RUTA_DATOS = Path(__file__).resolve().parent.parent / "datos" / "sello_rumores.json"
CAPA_MAXIMA = 4

_datos = None
_SI = ("1", "true", "si", "sí", "on")
_NO = ("0", "false", "no", "off")


def activo():
    """¿Hay sello? ALCALDE_HILO_SELLO=1/0 manda sobre SELLO; ALCALDE_HILO=0 lo apaga también."""
    if not radio_guion.hilo_activo():
        return False
    valor = os.environ.get("ALCALDE_HILO_SELLO", "").strip().lower()
    if valor in _SI:
        return True
    if valor in _NO:
        return False
    return bool(SELLO)


def datos(ruta=None):
    """El JSON del sello (cacheado si es el de siempre)."""
    global _datos
    if ruta is not None:
        with open(ruta, encoding="utf-8") as archivo:
            return json.load(archivo)
    if _datos is None:
        with open(RUTA_DATOS, encoding="utf-8") as archivo:
            _datos = json.load(archivo)
    return _datos


def lleva_sello(id_mision):
    return id_mision in set(datos().get("con_sello", ()))


def capa(dia):
    """Capa del día (1..4); un día desconocido usa la capa 1."""
    try:
        valor = int(datos().get("capas", {}).get(str(int(dia)), 1))
    except (TypeError, ValueError):
        valor = 1
    return max(1, min(CAPA_MAXIMA, valor))


def capa_de(id_mision, dia):
    if not activo() or not lleva_sello(id_mision):
        return None
    return capa(dia)


def capa_anuncio(texto, dia):
    """El anuncio de la campaña (el «espejo» del día 5) lleva el sello a tamaño completo; None si `texto` no lo es."""
    anuncio = datos().get("anuncio_debate")
    if not activo() or not anuncio or not texto or anuncio not in texto:
        return None
    return max(3, capa(dia))
