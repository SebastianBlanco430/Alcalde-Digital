# Registro del mundo digital (lo llama frontend/extensiones.aplicar desde main.py): crea el glitch y la escena
# MUNDO_DIGITAL, la registra en el gestor, instala un Computador por cada caso con `terminal` y añade a la conexión
# `ir_a_mundo_digital(caso_id)` y `volver_del_mundo_digital()` (no se edita conexion_flujo.py).
#
# El GameState se lee de `escena_mundo.flujo` en el momento de uso (None en línea o con GAMESTATE=0: «no disponible»).
# Un JSON de caso roto no tumba el juego: se avisa por stderr con el motivo y el mundo sigue sin ese caso.

import sys

from backend.datos import casos_loader
from backend.logica.casos import CasoError
from backend.logica.comercios import resolver_ancla
from frontend.conexion_flujo import MUNDO, MUNDO_DIGITAL


def _catalogo():
    try:
        return casos_loader.cargar_catalogo()
    except CasoError as error:
        print(f"[mundo digital] casos no cargados: {error}", file=sys.stderr)
        return {}


FUERA_TERMINAL, LATERAL_TERMINAL = 1.5, 1.4      # m desde la puerta del destino: a un lado, sin taparla
SEPARACION_TERMINAL = 1.6                        # m del punto del destino cuando el lugar no tiene edificio


# Dónde va el computador de un caso: junto al WAYPOINT de su misión digital (el destino que marcan el minimapa y la
# ruta), para que al llegar ya esté ahí. (x, z, rumbo) o None si el caso no tiene misión digital en este mundo (entonces
# vale el ancla `terminal` de su JSON).
def sitio_junto_al_destino(mundo, caso_id):
    import math
    from backend.logica import mundo_config
    try:
        digitales = [m for m in mundo_config.catalogo_misiones(mundo, con_game_state=True) if m.tipo != "verificar"]
    except Exception:
        return None
    mision = next((m for m in digitales if m.objetivo == caso_id), digitales[0] if digitales else None)
    if mision is None:
        return None
    try:                                         # con edificio: fuera de la puerta y a un lado, mirando a la calle
        return resolver_ancla(mundo, {"lugar": mision.destino, "fuera": FUERA_TERMINAL, "lateral": LATERAL_TERMINAL})
    except (ValueError, KeyError, AttributeError):
        pass
    try:
        px, pz = mundo.punto_interaccion(mision.destino)
    except (ValueError, KeyError, AttributeError):
        return None
    transitable = getattr(mundo, "es_transitable", None)
    for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        x, z = px + dx * SEPARACION_TERMINAL, pz + dz * SEPARACION_TERMINAL
        if transitable is None or transitable(x, z):
            return (x, z, math.degrees(math.atan2(-dx, -dz)))      # la silla queda del lado del waypoint
    return None


def registrar(gestor, conexion, escena_mundo):
    from frontend import economia_config
    if not economia_config.GAMESTATE:        # sin GameState (ALCALDE_GAMESTATE=0) el mundo es el de antes: sin computador
        return None
    from frontend.computador_mundo import Computador
    from frontend.escenas.escena_mundo_digital import EscenaMundoDigital
    from frontend.mundo_digital_glitch import GlitchOverlay

    glitch = GlitchOverlay()
    catalogo = _catalogo()
    escena = EscenaMundoDigital(glitch=glitch, catalogo=catalogo)
    gestor.registrar(MUNDO_DIGITAL, escena)
    computadores = []

    def volver():
        flujo = escena_mundo.flujo
        revisar = getattr(flujo, "revisar_misiones_digitales", None)
        if getattr(flujo, "game_state", None) is not None and revisar is not None:
            revisar()        # cierra la misión de parkour/investigación si su señal se cumplió (antes de pintar el mundo)
        gestor.cambiar_a(MUNDO, flujo=flujo)
        glitch.desvanecer()
        for c in computadores:
            if c.caso.id == escena._caso.id:
                r = escena._sesion
                c.decir("Sesión cerrada" if r is None or not r.terminado else f"Caso cerrado: {r.caso.nodo(r.nodo_id)['titulo']}")

    def ir(caso_id):
        flujo = escena_mundo.flujo
        if getattr(flujo, "game_state", None) is None or caso_id not in catalogo:
            return False
        gestor.cambiar_a(MUNDO_DIGITAL, flujo=flujo, caso_id=caso_id, al_terminar=volver)
        return True

    # Parkour «dentro del mundo virtual»: lo lanza el botón del caso (JSON `parkour`) y al terminar/salir REGRESA aquí,
    # a la misma sesión del caso (frontend/registro_parkour.py acepta `volver_a`). Sin parkour registrado: sin botón.
    def pedir_parkour(nivel_id):
        flujo, caso_id = escena_mundo.flujo, escena._caso.id
        lanzar = getattr(conexion, "ir_a_parkour", None)
        if lanzar is None:
            return False
        return lanzar(nivel_id, volver_a=lambda: gestor.cambiar_a(MUNDO_DIGITAL, flujo=flujo, caso_id=caso_id,
                                                                    al_terminar=volver))

    escena.al_pedir_parkour = pedir_parkour
    conexion.ir_a_mundo_digital = ir
    conexion.volver_del_mundo_digital = volver
    conexion.mundo_digital = escena
    conexion.saltadores.extend([escena.saltar] + [c.saltar for c in computadores])

    economia = escena_mundo.economia
    if economia is None:
        print("[mundo digital] ALCALDE_ECONOMIA=0: sin registro de interacciones; no hay computador en el mundo "
              "(la escena sigue accesible con conexion.ir_a_mundo_digital).", file=sys.stderr)
        return escena
    for caso in catalogo.values():
        if not caso.terminal:
            continue
        try:
            x, z, rumbo = resolver_ancla(escena_mundo._mundo, caso.terminal["ancla"])
        except (ValueError, KeyError, AttributeError) as error:
            print(f"[mundo digital] sin computador para {caso.id!r}: {error}", file=sys.stderr)
            continue
        junto = sitio_junto_al_destino(escena_mundo._mundo, caso.id)
        if junto is not None:                    # el terminal va en el waypoint de su misión, no en el ancla del JSON
            x, z, rumbo = junto
        computador = Computador(escena_mundo, caso, x, z, rumbo, abrir=lambda c: ir(c.id), glitch=glitch)
        computadores.append(computador)
        economia.registrar(computador)
        conexion.saltadores.append(computador.saltar)

    # Baliza de las misiones digitales: sobre el terminal exacto (el del caso de la misión; el parkour se lanza desde el
    # caso que lo trae en su JSON; si no se identifica, el primer terminal).
    def punto_de_mision(mision):
        if mision is None or getattr(mision, "tipo", "verificar") == "verificar" or not computadores:
            return None
        objetivo = getattr(mision, "objetivo", "")
        elegido = next((c for c in computadores if c.caso.id == objetivo), None)
        if elegido is None:
            elegido = next((c for c in computadores if objetivo and objetivo in str(getattr(c.caso, "parkour", ""))),
                           computadores[0])
        return (elegido.x, elegido.z)

    escena_mundo.punto_de_mision = punto_de_mision

    # Guía de las misiones digitales. No se juegan en la puerta de su destino sino en el terminal: quien llega a la
    # puerta (el minimapa lo lleva allí) lee a dónde ir, y en el terminal el aviso del parkour dice que dentro se pulsa K.
    def mision_digital():
        flujo = escena_mundo.flujo
        mision = flujo.mision_actual() if flujo is not None else None
        return mision if mision is not None and getattr(mision, "tipo", "verificar") != "verificar" else None

    def pista_del_terminal():
        mision = mision_digital()
        if mision is None or mision.tipo != "parkour":
            return None
        from frontend.escenas.escena_mundo_digital import TECLA_PARKOUR
        return f"dentro, pulsa {TECLA_PARKOUR.upper()} para el parkour de tu misión"

    for c in computadores:
        c.pista_mision = pista_del_terminal
    if computadores:
        economia.registrar(GuiaMisionDigital(escena_mundo, mision_digital, punto_de_mision))
    return escena


RADIO_GUIA = 9.0          # m de la puerta del destino donde se explica a dónde ir
RADIO_TERMINAL = 3.0      # más cerca que esto del terminal ya manda el aviso del computador


# Interacción solo informativa (Protocol Interaccion de economia_mundo): en la puerta del destino de una misión digital
# dice dónde se juega de verdad. No consume la E.
class GuiaMisionDigital:

    prioridad = 1

    def __init__(self, escena, mision_digital, punto_de_mision):
        self._escena, self._mision, self._punto = escena, mision_digital, punto_de_mision

    def aviso(self, jugador, x, z):
        import math
        try:
            mision = self._mision()
            if mision is None:
                return None
            terminal = self._punto(mision)
            px, pz = self._escena._mundo.punto_interaccion(mision.destino)
        except Exception:
            return None
        if terminal is None or math.hypot(x - px, z - pz) > RADIO_GUIA:
            return None
        metros = math.hypot(x - terminal[0], z - terminal[1])
        if metros <= RADIO_TERMINAL:
            return None
        return f"Misión digital: no es aquí. Sigue la baliza hasta la Terminal de la Fiscalía (a {int(round(metros))} m) y pulsa E"

    def usar(self, jugador, economia=None):
        return False

    def actualizar(self, dt):
        pass
