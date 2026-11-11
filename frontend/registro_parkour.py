# Registro del PARKOUR (Ola 2, subagente B). frontend/extensiones.py llama a registrar(); no hay que editar main.py ni
# conexion_flujo.py: los métodos nuevos se cuelgan de la instancia de ConexionFlujo.
#
# API para la Ola 3 (mundo físico, minimapa):
#   entrar(nivel_id, reiniciar=False) -> bool   fundido -> escena PARKOUR. False si no se puede (sin partida, fundido en
#                                               curso, cinemática, partida terminada) o el nivel no existe.
#   resultado(nivel_id) -> dict | None          último resultado del nivel (puntos, medalla, eficiencia...), o None.
#   alturas(nivel_id) -> dict                   parkour_calculos.alturas_para_minimapa del nivel (para dibujar el minimapa).
#   niveles() -> [ids]                          niveles disponibles (backend/datos/parkour/*.json).
# La escena sale al mundo con conexion.salir_de_parkour() (fundido -> MUNDO).
# DESTINO DE RETORNO (Ola 3): entrar(..., volver_a=callable) / conexion.ir_a_parkour(..., volver_a=callable) hacen que,
# al terminar o salir, se ejecute `volver_a()` (con fundido) en vez de volver al MUNDO. Así el parkour que se lanza
# desde el mundo digital regresa al mundo digital. Sin `volver_a` (valor por defecto) todo sigue como antes: MUNDO.
#
# Prueba a mano sin pasar por el mundo: ALCALDE_PARKOUR=<nivel_id> python main.py abre ese nivel nada más arrancar
# (sin partida: no hay GameState, así que no otorga evidencia; Esc > Salir vuelve al menú de inicio).

import os

from backend.datos import parkour_loader
from backend.logica import parkour_calculos
from frontend.conexion_flujo import INICIO, PARKOUR

VARIABLE_DESARROLLO = "ALCALDE_PARKOUR"
RETRASO_DESARROLLO = 0.4      # s: tras el primer frame, para ganar al cambiar_a(INICIO) de main

_estado = {"conexion": None, "escena": None}


# True si ahora mismo se puede abrir el parkour desde el mundo.
def _puede_entrar(conexion):
    flujo = conexion.flujo
    return not (flujo is None or conexion._transicion_en_curso() or flujo.partida_terminada()
                or getattr(conexion.cinematicas, "_cinematica", False))


def entrar(nivel_id, reiniciar=False, volver_a=None):
    conexion = _estado["conexion"]
    if conexion is None:
        return False
    return conexion.ir_a_parkour(nivel_id, reiniciar=reiniciar, volver_a=volver_a)


def resultado(nivel_id):
    escena = _estado["escena"]
    return None if escena is None else escena.resultados.get(nivel_id)


def alturas(nivel_id):
    return parkour_calculos.alturas_para_minimapa(parkour_loader.cargar_nivel(nivel_id))


def niveles():
    return parkour_loader.listar_niveles()


def registrar(gestor, conexion, escena_mundo):
    from frontend.escenas.escena_parkour import EscenaParkour

    # `conexion.flujo` es None hasta que empieza la partida: se lee al terminar el nivel, no aquí.
    escena = EscenaParkour(game_state=lambda: getattr(conexion.flujo, "game_state", None))
    gestor.registrar(PARKOUR, escena)
    _estado.update(conexion=conexion, escena=escena)

    def salir_de_parkour():
        if conexion.flujo is None:                       # prueba de desarrollo: sin partida se vuelve al inicio
            gestor.cambiar_a(INICIO)
        else:
            conexion._con_transicion(conexion._volver_al_mundo)

    # Salida con destino propio: fundido -> volver_a(). Si no hay destino, la salida de siempre (MUNDO).
    def _salida(volver_a):
        if volver_a is None:
            return salir_de_parkour
        return lambda: conexion._con_transicion(volver_a)

    def ir_a_parkour(nivel_id, reiniciar=False, volver_a=None):
        if not _puede_entrar(conexion):
            return False
        try:
            nivel = parkour_loader.cargar_nivel(nivel_id)
        except ValueError:
            return False

        def abrir():
            gestor.cambiar_a(PARKOUR, nivel_id=nivel_id, reiniciar=reiniciar, salir=_salida(volver_a))

        conexion._con_transicion_lugar(abrir, texto=nivel.nombre)
        return True

    conexion.ir_a_parkour = ir_a_parkour
    conexion.salir_de_parkour = salir_de_parkour

    nivel_dev = os.environ.get(VARIABLE_DESARROLLO)
    if nivel_dev:
        from ursina import invoke
        invoke(lambda: gestor.cambiar_a(PARKOUR, nivel_id=nivel_dev, salir=salir_de_parkour),
               delay=RETRASO_DESARROLLO)
