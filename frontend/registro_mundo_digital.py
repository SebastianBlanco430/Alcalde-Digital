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
    return escena
