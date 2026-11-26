# Narradora y Rádio Comunitária con voz: la parte PURA (no importa ursina ni panda3d; se prueba con pytest).
# Lo que suena lo hace frontend/narrador.py. Diseño: Est2GameMem/00-Proyecto/investigacion-voz-narrador.md.
#
# Los audios están pregenerados (ElevenLabs) en assets/voz/ y se buscan POR EL TEXTO del subtítulo o de la línea de
# radio (assets/voz/indice.json). Una frase sin audio (texto editado y no regenerado) se queda muda con su subtítulo de
# siempre: nunca rompe.
#
#   activo() / radio_activa() / atenuar_activo()   banderas ALCALDE_NARRADOR, ALCALDE_NARRADOR_RADIO, ALCALDE_NARRADOR_ATENUAR
#   normalizar(texto) · voz_de(texto) -> dict|None · segundos_voz(texto) -> float|None · ruta_audio(texto) -> Path|None
#   segundos_plano(subtitulos, segundos, margen)   cuánto dura un plano para que quepan sus voces (>= el original)
#   reparto_con_voz(subtitulos, segundos, margen)  [(inicio, fin)] de cada subtítulo al ritmo de su voz, o None sin voces
#   segundos_cartela(texto, base) · segundos_radio(texto, base)

import json
import os
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DIR_VOZ = RAIZ / "assets" / "voz"
RUTA_INDICE = DIR_VOZ / "indice.json"

PAUSA_ENTRE = 0.35        # s de respiro después de cada frase hablada
ENTRADA_VOZ = 0.15        # s desde que aparece el subtítulo hasta que empieza a hablar
MARGEN_RADIO = 0.6        # s que la línea de radio sigue en pantalla después de la voz
MARGEN_CARTELA = 0.3
SIN_VOZ_BASE, SIN_VOZ_POR_CARACTER, SIN_VOZ_MINIMO = 1.5, 0.06, 2.4   # frases sin audio: regla de lectura
ATENUACION_MUSICA = 0.35  # la música baja a este factor mientras hay voz

_VERDAD = ("1", "true", "si", "sí", "on")
_FALSO = ("0", "false", "no", "off")
_indice = None


def _bandera(nombre, defecto=True):
    valor = os.environ.get(nombre, "").strip().lower()
    if valor in _VERDAD:
        return True
    if valor in _FALSO:
        return False
    return defecto


def activo():
    return _bandera("ALCALDE_NARRADOR", True)


def radio_activa():
    return activo() and _bandera("ALCALDE_NARRADOR_RADIO", True)


def atenuar_activo():
    return _bandera("ALCALDE_NARRADOR_ATENUAR", True)


def normalizar(texto):
    return " ".join(str(texto or "").split())


def cargar_indice(ruta=None, recargar=False):
    """{texto normalizado: {"archivo", "segundos", "voz", "bloque"}}. Vacío si no hay índice o está dañado."""
    global _indice
    if _indice is not None and ruta is None and not recargar:
        return _indice
    try:
        with open(ruta or RUTA_INDICE, encoding="utf-8") as f:
            datos = json.load(f)
        voces = datos.get("voces", datos) if isinstance(datos, dict) else {}
        indice = {normalizar(k): v for k, v in voces.items() if isinstance(v, dict) and not str(k).startswith("_")}
    except (OSError, ValueError):
        indice = {}
    if ruta is None:
        _indice = indice
    return indice


def fijar_indice(indice):
    """Pruebas: usa `indice` ({texto: {"archivo", "segundos", ...}}) en lugar del de disco. None = volver al de disco."""
    global _indice
    _indice = None if indice is None else {normalizar(k): v for k, v in indice.items()}


def voz_de(texto):
    if not activo():
        return None
    return cargar_indice().get(normalizar(texto))


def segundos_voz(texto):
    voz = voz_de(texto)
    try:
        segundos = float(voz["segundos"]) if voz else None
    except (KeyError, TypeError, ValueError):
        return None
    return segundos if segundos and segundos > 0 else None


def ruta_audio(texto):
    voz = voz_de(texto)
    if not voz or not voz.get("archivo"):
        return None
    ruta = DIR_VOZ / str(voz["archivo"])
    return ruta if ruta.exists() else None


def _lectura(texto):
    return max(SIN_VOZ_MINIMO, SIN_VOZ_BASE + SIN_VOZ_POR_CARACTER * len(normalizar(texto)))


def _necesarios(subtitulos):
    """[(segundos que necesita cada frase, tiene_voz)]."""
    salida = []
    for texto in subtitulos or ():
        voz = segundos_voz(texto)
        salida.append((ENTRADA_VOZ + voz + PAUSA_ENTRE, True) if voz else (_lectura(texto), False))
    return salida


def segundos_plano(subtitulos, segundos, margen=0.35):
    """Duración del plano para que quepan sus voces: nunca menos que `segundos`. Sin ninguna voz, `segundos`."""
    necesarios = _necesarios(subtitulos)
    if not any(con_voz for _d, con_voz in necesarios):
        return float(segundos)
    return max(float(segundos), 2.0 * margen + sum(d for d, _v in necesarios))


def reparto_con_voz(subtitulos, segundos, margen=0.35):
    """[(inicio, fin)] de cada subtítulo dentro de un plano de `segundos` (ya alargado con segundos_plano): cada frase
    dura lo que necesita su voz y el tiempo que sobre se reparte en proporción. None si ninguna frase tiene voz (el
    llamador usa entonces su reparto de siempre)."""
    necesarios = _necesarios(subtitulos)
    if not necesarios or not any(con_voz for _d, con_voz in necesarios):
        return None
    margen = min(margen, segundos / 4.0)
    disponible = max(0.0, float(segundos) - 2.0 * margen)
    total = sum(d for d, _v in necesarios)
    escala = disponible / total if total > 0 else 1.0
    tramos, inicio = [], margen
    for d, _v in necesarios:
        fin = inicio + d * escala
        tramos.append((inicio, fin))
        inicio = fin
    return tramos


def segundos_cartela(texto, base, entrada=0.7, salida=0.5):
    voz = segundos_voz(texto)
    return float(base) if not voz else max(float(base), entrada + voz + MARGEN_CARTELA + salida)


def segundos_radio(texto, base):
    if not radio_activa():
        return float(base)
    voz = segundos_voz(texto)
    return float(base) if not voz else max(float(base), voz + MARGEN_RADIO)
