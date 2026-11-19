# Construcción del mundo de la partida y su catálogo de misiones (módulo mínimo, SIN importaciones del juego a nivel de
# módulo: se puede leer desde main.py y las escenas sin arrastrar nada).
#
# El mundo es uno solo: Ciudad3D, el mundo de ~280 x 230 m (backend/datos/ciudad_3d.py). (Hasta 2026-11-18 existió además
# un «mapa grande» de ~900 x 650 m con chunks, detrás de la bandera ALCALDE_MAPA_GRANDE; el dueño ordenó borrarlo.)

import os


def solo_digitales_activo():
    """DEPURACIÓN: ALCALDE_SOLO_DIGITALES=1 hace que la partida de solo tenga ÚNICAMENTE las misiones digitales (parkour e
    investigación) del mapa. Apagada por defecto; solo tiene efecto con GameState y economía encendidos."""
    return os.environ.get("ALCALDE_SOLO_DIGITALES", "").strip().lower() in ("1", "true", "si", "sí", "on")


def construir_mundo_activo(semilla):
    """El mundo que usa main.py (construir_mundo_3d, pasando por la caché en disco)."""
    return _construir(semilla)


# Construye el mundo pasando por la caché en disco (backend/datos/cache_mundo.py). El resultado es el mismo (la caché se
# invalida sola si cambia el código).
def _construir(semilla):
    from backend.datos import cache_mundo
    from backend.datos.ciudad_3d import construir_mundo_3d
    return cache_mundo.construir_con_cache("chico", semilla, lambda: construir_mundo_3d(semilla=semilla))


def catalogo_misiones(mundo, con_game_state=False):
    """El catálogo de misiones del mundo. Con `con_game_state` (partida de SOLO con GameState) añade al final las misiones
    digitales (parkour e investigación)."""
    from backend.datos.misiones_semilla import catalogo_de_mundo, catalogo_solo
    return catalogo_solo(mundo, True, solo_digitales=solo_digitales_activo()) if con_game_state else catalogo_de_mundo(mundo)


def mundo_para_red(semilla):
    """Construye el mundo que usan anfitrión y clientes online: el MISMO que el juego local."""
    return _construir(semilla)
