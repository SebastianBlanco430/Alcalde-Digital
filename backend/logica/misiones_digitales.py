# Misiones digitales (modelo puro, sin ursina ni frontend): las de tipo «parkour» e «investigacion». No se juegan en el
# lugar: se completan por SEÑAL del GameState de la partida de solo.
#
#   parkour        -> el GameState tiene la evidencia que da la recompensa del nivel `objetivo`
#                     (parkour_calculos.otorgar_recompensa -> evidencia.tiene).
#   investigacion  -> el caso `objetivo` tiene un final registrado (casos.resultado_de); cualquier final cuenta.
#
# Sin GameState (partida en línea o ALCALDE_GAMESTATE=0) estas misiones serían imposibles, así que `evaluar` las descarta
# (con el motivo, para depurar) y `catalogo_solo` (misiones_semilla.py) no las incluye. Un nivel o un caso inexistente o
# con el JSON roto también las descarta: el juego no se cae por un dato.
#
# `mision` se usa por duck typing (tipo, objetivo, id): este módulo no importa misiones.py (misiones.py lo importa a él).

from backend.datos import casos_loader, parkour_loader
from backend.logica import casos, evidencia

TIPOS_DIGITALES = ("parkour", "investigacion")


def _evidencia_del_nivel(nivel_id, carpeta_niveles=None):
    """Id de la evidencia que da el nivel, o ValueError si no carga o no da ninguna."""
    nivel = parkour_loader.cargar_nivel(nivel_id, carpeta_niveles)
    id_evidencia = nivel.recompensa.get("evidencia")
    if not isinstance(id_evidencia, str) or not id_evidencia.strip():
        raise ValueError(f"el nivel {nivel_id!r} no da ninguna evidencia, la misión no se podría completar.")
    return id_evidencia


def cumplida(mision, game_state):
    """¿Se cumplió la señal de la misión digital? False para «verificar», sin GameState o con el objetivo roto."""
    if game_state is None or mision.tipo not in TIPOS_DIGITALES:
        return False
    try:
        if mision.tipo == "parkour":
            return bool(evidencia.tiene(game_state, _evidencia_del_nivel(mision.objetivo)))
        return casos.resultado_de(game_state, mision.objetivo) is not None
    except ValueError:      # nivel/caso inexistente o JSON inválido (CasoError es ValueError)
        return False


def motivo_no_disponible(mision, game_state_activo, carpeta_niveles=None, carpeta_casos=None):
    """None si la misión se puede jugar; si no, el motivo (texto) por el que se omite."""
    if mision.tipo not in TIPOS_DIGITALES:
        return None
    if not game_state_activo:
        return "no hay GameState (partida en línea o ALCALDE_GAMESTATE=0)"
    try:
        if mision.tipo == "parkour":
            _evidencia_del_nivel(mision.objetivo, carpeta_niveles)
        else:
            casos_loader.cargar_caso_por_id(mision.objetivo, carpeta_casos)
    except ValueError as error:
        return f"objetivo {mision.objetivo!r} no disponible: {error}"
    return None


def evaluar(misiones, game_state_activo, carpeta_niveles=None, carpeta_casos=None):
    """(utilizables, omitidas): las misiones jugables (en el orden dado; las de «verificar» siempre) y {id: motivo} de
    las descartadas."""
    utilizables, omitidas = [], {}
    for mision in misiones:
        motivo = motivo_no_disponible(mision, game_state_activo, carpeta_niveles, carpeta_casos)
        if motivo is None:
            utilizables.append(mision)
        else:
            omitidas[mision.id] = motivo
    return utilizables, omitidas


def disponibles(misiones, game_state_activo, carpeta_niveles=None, carpeta_casos=None):
    """Solo las misiones jugables (ver `evaluar` para conocer el motivo de las omitidas)."""
    return evaluar(misiones, game_state_activo, carpeta_niveles, carpeta_casos)[0]
