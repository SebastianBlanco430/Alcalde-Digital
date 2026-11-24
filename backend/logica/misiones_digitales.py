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

#
# Fiscalía v2 (ALCALDE_FISCALIA_V2, sesión A): cada caso v2 declara su misión en su JSON (`mision`, contrato-caso.md §4).
# misiones_de_casos() las convierte en Mision (investigación, objetivo = id del caso, destino = la plaza de la Fiscalía)
# y dia_de(id) da su día. Con la bandera apagada no existen. La señal de cumplida es la de siempre (casos.resultado_de):
# el motor v2 deja el mismo rastro que el v1.

import sys

from backend.datos import casos_loader, parkour_loader
from backend.logica import casos, evidencia, fiscalia_bandera

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


def cobra(mision, game_state):
    """¿Se paga la misión digital al cerrarse? Siempre, salvo una investigación cuyo caso v2 se ABANDONÓ: se cierra (no
    queda atascada) con su veredicto y sus efectos, pero sin pago (sesión E, P5). La lee flujo_economia."""
    if getattr(mision, "tipo", None) != "investigacion":
        return True
    from backend.logica import casos_v2                 # import tardío: casos_v2 no hace falta con la bandera apagada
    return not casos_v2.abandonado(game_state, mision.objetivo)


def motivo_no_disponible(mision, game_state_activo, carpeta_niveles=None, carpeta_casos=None):
    """None si la misión se puede jugar; si no, el motivo (texto) por el que se omite."""
    if mision.tipo not in TIPOS_DIGITALES:
        return None
    if not game_state_activo:
        return "no hay GameState (partida en línea o ALCALDE_GAMESTATE=0)"
    try:
        if mision.tipo == "parkour":
            _evidencia_del_nivel(mision.objetivo, carpeta_niveles)
        elif fiscalia_bandera.activa() and mision.objetivo in casos_loader.cargar_catalogo_v2(carpeta_casos):
            pass                                        # caso v2 válido (Fiscalía v2)
        else:
            casos_loader.cargar_caso_por_id(mision.objetivo, carpeta_casos)
    except ValueError as error:
        return f"objetivo {mision.objetivo!r} no disponible: {error}"
    return None


def misiones_de_casos(carpeta=None):
    """Las Mision de los casos v2 válidos, ordenadas por día y luego por id (tupla). Vacía con la bandera apagada. Un id
    de misión repetido entre dos casos se omite (aviso por stderr): se queda el primero por nombre de archivo."""
    if not fiscalia_bandera.activa():
        return ()
    from backend.logica.misiones import Mision          # misiones.py importa este módulo: import tardío

    salida, vistas = [], set()
    for caso in casos_loader.cargar_catalogo_v2(carpeta).values():
        m = caso.mision
        if m["id"] in vistas:
            print(f"[casos v2] se omite la misión {m['id']!r} del caso {caso.id!r}: id repetido", file=sys.stderr)
            continue
        vistas.add(m["id"])
        salida.append(Mision(m["id"], None, m["titulo"], m["mensaje"], fiscalia_bandera.LUGAR_FISCALIA,
                             pago=m["pago"], dificultad=m["dificultad"], tipo="investigacion", objetivo=caso.id,
                             grupo=m["grupo"], dia=m["dia"]))
    return tuple(sorted(salida, key=lambda m: (m.dia, m.id)))


def dia_de(mision_id, carpeta=None):
    """Día (1-7) en que puede aparecer la misión de un caso v2, o None si no es de un caso v2 (o la bandera está apagada)."""
    return next((m.dia for m in misiones_de_casos(carpeta) if m.id == mision_id), None)


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
