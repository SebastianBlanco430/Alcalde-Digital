# Qué interior se usa para jugar cada minijuego en 3D (Python puro: NO importa ursina). Lo consulta la presentación 3D
# (frontend/minijuegos_3d/base.py) al montar el set; la tabla de las 14 misiones del contrato sale de tabla_misiones().
#
# REGLA (una por familia; el interior de cada lugar es la misma oficina con un tema, frontend/temas_interior.py):
#   - pc (Chat, Contrarreloj): SIEMPRE el interior de la misión. Todas las oficinas tienen escritorio, silla y monitor, y es
#     donde el jugador ya se sentó en la cinemática de entrada: se juega en ese mismo PC.
#   - corcho (Rastrear, Cronología): el interior de la misión SOLO si su tema tiene un tablero de pared («pizarra» o
#     «mapa_rutas»): el corcho se cuelga en esa pared, en lugar de ese prop. Si no, la SALA DE INVESTIGACIÓN (set nuevo):
#     colgar un corcho de investigación en una oficina de recepción, una cafetería o una sala de guardia no tiene sentido.
#   - mesa (Comparar, Señales): SIEMPRE el CUARTO CON MESA DE MADERA (set nuevo). El escritorio de la oficina está ocupado
#     por el PC y el teclado, y la oficina no tiene techo ni luz de techo que apagar (Comparar la necesita).
# Los sets nuevos toman los colores de pared, piso y acento del tema del lugar (si lo hay), así se reconoce el edificio.

from dataclasses import dataclass

from frontend.temas_interior import TEMAS

INTERIOR = "interior"
SALA_INVESTIGACION = "sala_investigacion"
CUARTO_MESA = "cuarto_mesa"
CUARTO_PC = "cuarto_pc"               # set base con escritorio y monitor (lugar sin tema de interior)
SETS = (INTERIOR, SALA_INVESTIGACION, CUARTO_MESA, CUARTO_PC)

PROPS_TABLERO = ("pizarra", "mapa_rutas")
PAREDES_PROP = ("oeste", "norte", "este")         # índice del prop en Tema.props -> pared (EscenaInterior.ANCLAS)

_FAMILIA = {"chat": "pc", "contrarreloj": "pc", "rastrear": "corcho", "cronologia": "corcho",
            "comparar": "mesa", "senales": "mesa"}


@dataclass(frozen=True)
class Eleccion:
    set: str                 # uno de SETS
    motivo: str              # por qué (texto para el contrato y los registros)
    pared: str = ""          # corcho en el interior: pared del tablero ('oeste' | 'norte' | 'este'); '' si no aplica
    indice_prop: int = -1    # corcho en el interior: índice del prop que el corcho sustituye; -1 si no aplica


def elegir(minijuego_id, lugar, familia=None):
    """Eleccion para jugar `minijuego_id` en `lugar` (destino de la misión). `familia` fuerza la familia (la demostración
    es 'pc'). Un lugar sin tema da el set base de la familia."""
    familia = familia or _FAMILIA.get(minijuego_id)
    tema = TEMAS.get(lugar)
    if familia == "pc":
        if tema is None:
            return Eleccion(CUARTO_PC, "lugar sin interior propio: cuarto base con escritorio y PC")
        return Eleccion(INTERIOR, "la oficina del lugar ya tiene escritorio, silla y monitor (donde el jugador se sentó)")
    if familia == "corcho":
        if tema is not None:
            for indice, prop in enumerate(tema.props):
                if prop in PROPS_TABLERO:
                    return Eleccion(INTERIOR, f"la oficina tiene un tablero de pared ({prop}): el corcho cuelga ahí",
                                    pared=PAREDES_PROP[indice], indice_prop=indice)
        return Eleccion(SALA_INVESTIGACION, "la oficina no tiene pared de tablero: un corcho de investigación no encaja")
    if familia == "mesa":
        return Eleccion(CUARTO_MESA, "el escritorio de la oficina está ocupado por el PC y no hay luz de techo que apagar")
    raise ValueError(f"Minijuego sin familia 3D: {minijuego_id!r}")


def tabla_misiones(catalogo=None):
    """[(id de misión, minijuego, lugar, Eleccion)] de las misiones de verificar del catálogo (las 14 de hoy)."""
    from backend.datos import minijuegos_asignacion as asignacion
    from backend.logica import minijuegos as mj
    if catalogo is None:
        from backend.datos.misiones_semilla import CATALOGO_MISIONES as catalogo
    filas = []
    for mision in catalogo:
        minijuego = asignacion.asignar(mision)
        if minijuego == mj.ACTUAL or minijuego not in _FAMILIA:
            continue
        filas.append((mision.id, minijuego, mision.destino, elegir(minijuego, mision.destino)))
    return filas
