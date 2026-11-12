# Finales por etapas (docs/PLAN_FINALES_HISTORIA.md). Lógica PURA (sin Ursina): del ÍNDICE de la partida (0-100, el de
# flujo.resumen_final()["indice"]) sale una ETAPA entera de -3 a +3, y de la etapa sale todo lo demás: el final
# (bueno / neutro / malo), las cantidades de las capas nuevas de la ciudad (fuego, rodadores, fiesta), el tinte de cámara
# y el perfil de audio del mundo. Los textos, los NPC y las viñetas viven en backend/datos/finales_historia.json.
#
# Banderas (la variable de entorno manda sobre la constante):
#   ETAPAS_FINAL / ALCALDE_ETAPAS_FINAL=0     nada de esto: el juego queda exactamente como antes
#   ALCALDE_INDICE_FORZADO=<0-100>            el índice que se usa en vez del real (pruebas y feria)
#
# Uso:
#   etapa = etapas_final.etapa_de_indice(indice, etapa_anterior)     # con histéresis de 2 puntos para SALIR de una etapa
#   etapas_final.final_de_etapa(etapa)                               # "bueno" | "neutro" | "malo"
#   etapas_final.indice_de_flujo(flujo)                              # forzado, o el del flujo, o None (en línea)

import json
import os
from pathlib import Path

ETAPAS_FINAL = True
ETAPA_MIN, ETAPA_MAX = -3, 3
ETAPAS = tuple(range(ETAPA_MIN, ETAPA_MAX + 1))
UMBRALES_BUENOS = (60.0, 75.0, 90.0)        # índice >= umbral -> +1, +2, +3
UMBRALES_MALOS = (40.0, 25.0, 10.0)         # índice <= umbral -> -1, -2, -3
HISTERESIS = 2.0                            # puntos de índice que hay que pasar para SALIR de una etapa

CANTIDADES = {                              # fracción (0..1) de sitios encendidos de cada capa nueva, por etapa
    "fuego": {-1: 0.15, -2: 0.45, -3: 0.9},
    "rodadores": {-3: 0.6},
    "fiesta": {3: 0.9},
}
CAPAS_ETAPA = tuple(CANTIDADES)

# Tinte de cámara (r, g, b, alfa) y alfa de la viñeta oscura; el JSON puede cambiarlos (claves "tinte" y "vineta").
TINTES = {-2: (0.55, 0.40, 0.20, 0.12), -3: (0.65, 0.20, 0.10, 0.20), 3: (0.55, 0.75, 1.0, 0.10)}
VINETAS = {-3: 0.45}
SIN_TINTE = (0.0, 0.0, 0.0, 0.0)

# Audio del mundo por etapa: (música | None, volumen, {bucle de ambiente: volumen}). La etapa 0 y las ±1 son el de siempre.
_NORMAL = ("musica_ambiente", 0.45, {"ambiente_favela": 0.8})
PERFILES_AUDIO = {
    -3: (None, 0.0, {"ambiente_favela": 0.35, "ambiente_caos": 0.8}),
    -2: ("musica_tensa", 0.5, {"ambiente_favela": 0.8}),
    -1: _NORMAL, 0: _NORMAL, 1: _NORMAL,
    2: ("musica_ambiente", 0.45, {"ambiente_favela": 0.7, "ambiente_plaza": 0.6}),
    3: ("musica_fiesta", 0.5, {"ambiente_favela": 0.5, "ambiente_plaza": 0.6}),
}
BUCLES_ETAPA = ("ambiente_plaza", "ambiente_caos")

RUTA_TEXTOS = Path(__file__).resolve().parent.parent / "datos" / "finales_historia.json"

_textos = None
_forzado_manual = None                      # índice puesto a mano (F8/F9, scripts); manda sobre la variable de entorno


def activo():
    valor = os.environ.get("ALCALDE_ETAPAS_FINAL", "").strip().lower()
    if valor in ("1", "true", "si", "sí", "on"):
        return True
    if valor in ("0", "false", "no", "off"):
        return False
    return bool(ETAPAS_FINAL)


def depuracion():
    return os.environ.get("ALCALDE_DEBUG", "").strip().lower() in ("1", "true", "si", "sí", "on")


# -- Índice -> etapa --------------------------------------------------------------------------------------------------


def _etapa_directa(indice):
    for etapa, umbral in zip((3, 2, 1), reversed(UMBRALES_BUENOS)):
        if indice >= umbral:
            return etapa
    for etapa, umbral in zip((-3, -2, -1), reversed(UMBRALES_MALOS)):
        if indice <= umbral:
            return etapa
    return 0


def _banda(etapa):
    """(mínimo, máximo) del índice dentro de la etapa, sin histéresis."""
    if etapa > 0:
        return UMBRALES_BUENOS[etapa - 1], (UMBRALES_BUENOS[etapa] if etapa < ETAPA_MAX else 100.0)
    if etapa < 0:
        return (UMBRALES_MALOS[-etapa] if etapa > ETAPA_MIN else 0.0), UMBRALES_MALOS[-etapa - 1]
    return UMBRALES_MALOS[0], UMBRALES_BUENOS[0]


def etapa_de_indice(indice, etapa_anterior=None):
    """Etapa (-3..+3) de un índice 0-100. Con `etapa_anterior` hay histéresis: se ENTRA a una etapa en su umbral exacto,
    pero solo se SALE hacia el centro al alejarse HISTERESIS puntos (p. ej. +1 entra en 60 y sale por debajo de 58)."""
    indice = max(0.0, min(100.0, float(indice)))
    directa = _etapa_directa(indice)
    if isinstance(etapa_anterior, bool) or not isinstance(etapa_anterior, int) or etapa_anterior not in ETAPAS:
        return directa
    if abs(directa) > abs(etapa_anterior) or directa * etapa_anterior < 0:
        return directa                      # se entra en una etapa más extrema (o del otro signo): sin demora
    if directa == etapa_anterior or etapa_anterior == 0:
        return directa
    # La directa está más cerca del centro que la anterior: se aguanta la anterior mientras el índice siga dentro del margen.
    etapa = etapa_anterior
    while etapa != directa:
        minimo, maximo = _banda(etapa)
        if etapa > 0 and indice >= minimo - HISTERESIS:
            break
        if etapa < 0 and indice <= maximo + HISTERESIS:
            break
        etapa += -1 if etapa > 0 else 1
    return etapa


def centro_de_etapa(etapa):
    """Índice en el centro de la banda de una etapa (depuración: F8/F9)."""
    minimo, maximo = _banda(max(ETAPA_MIN, min(ETAPA_MAX, int(etapa))))
    return round((minimo + maximo) / 2.0, 2)


def final_de_etapa(etapa):
    return "bueno" if etapa >= 1 else "malo" if etapa <= -1 else "neutro"


# -- Índice de la partida ---------------------------------------------------------------------------------------------


def fijar_indice_forzado(valor):
    """Fuerza el índice a mano (None lo suelta y vuelve a mandar ALCALDE_INDICE_FORZADO o el índice real)."""
    global _forzado_manual
    _forzado_manual = None if valor is None else max(0.0, min(100.0, float(valor)))


def indice_forzado():
    """El índice forzado (a mano o por ALCALDE_INDICE_FORZADO) o None."""
    if _forzado_manual is not None:
        return _forzado_manual
    bruto = os.environ.get("ALCALDE_INDICE_FORZADO", "").strip()
    if not bruto:
        return None
    try:
        return max(0.0, min(100.0, float(bruto.replace(",", "."))))
    except ValueError:
        return None


def indice_de_flujo(flujo):
    """El índice 0-100 que manda: el forzado si lo hay; si no, el de flujo.resumen_final(); None sin resumen (en línea)."""
    forzado = indice_forzado()
    if forzado is not None:
        return forzado
    leer = getattr(flujo, "resumen_final", None) if flujo is not None else None
    if not callable(leer):
        return None
    resumen = leer()
    indice = resumen.get("indice") if isinstance(resumen, dict) else None
    return None if indice is None else max(0.0, min(100.0, float(indice)))


# -- Lo que sale de la etapa ------------------------------------------------------------------------------------------


def cantidades_etapa(etapa):
    """{"fuego", "rodadores", "fiesta"}: fracción 0..1 de los sitios de cada capa nueva en esa etapa."""
    return {capa: float(por_etapa.get(etapa, 0.0)) for capa, por_etapa in CANTIDADES.items()}


def tinte(etapa):
    """{"color": (r, g, b, alfa), "vineta": alfa} de la cámara en esa etapa (todo 0 = sin tinte)."""
    tintes, vinetas = dict(TINTES), dict(VINETAS)
    try:
        datos = cargar_textos()
        tintes.update({int(k): tuple(float(v) for v in valor) for k, valor in datos.get("tinte", {}).items()})
        vinetas.update({int(k): float(v) for k, v in datos.get("vineta", {}).items()})
    except (OSError, ValueError, TypeError):
        pass
    color = tintes.get(etapa, SIN_TINTE)
    return {"color": tuple(color) if len(color) == 4 else SIN_TINTE, "vineta": float(vinetas.get(etapa, 0.0))}


def perfil_audio(etapa):
    """{"musica": nombre | None, "volumen_musica", "bucles": {nombre: volumen}} del MUNDO en esa etapa."""
    musica, volumen, bucles = PERFILES_AUDIO.get(etapa, _NORMAL)
    return {"musica": musica, "volumen_musica": volumen, "bucles": dict(bucles)}


# -- Textos (JSON) ----------------------------------------------------------------------------------------------------


def cargar_textos(ruta=None):
    """El contenido de finales_historia.json (se lee una vez; con `ruta` se lee ese archivo sin guardar)."""
    global _textos
    if ruta is not None:
        return json.loads(Path(ruta).read_text(encoding="utf-8"))
    if _textos is None:
        _textos = json.loads(RUTA_TEXTOS.read_text(encoding="utf-8"))
    return _textos


def nombre_de_etapa(etapa):
    return cargar_textos()["etapas"][str(int(etapa))]["nombre"]


def aviso_de_etapa(etapa):
    return cargar_textos()["etapas"][str(int(etapa))].get("aviso")


def npc_de_etapa(etapa):
    """Claves de los tipos de NPC que se ven en esa etapa (orden del JSON)."""
    return list(cargar_textos().get("npc_por_etapa", {}).get(str(int(etapa)), []))
