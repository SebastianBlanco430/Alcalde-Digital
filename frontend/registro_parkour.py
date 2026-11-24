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
# ANTESALA (sesión B, ALCALDE_ANIM_SILLA): entrar(..., antesala=None) / conexion.ir_a_parkour(..., antesala=None).
#   None  = automática: con la bandera encendida y partida en curso, el nivel empieza en el «terminal del servidor»
#           (el protagonista se sienta y la cámara entra en la pantalla; frontend/parkour_antesala.py) y al salir se
#           levanta antes de la salida de siempre. Con la bandera en 0, exactamente lo de antes.
#   False = sin antesala: el llamador ya hizo su propia animación de terminal (el laboratorio de la Fiscalía, con
#           cinematica_silla.entrar_a_pantalla) y llama entrar() en su al_terminar. El fundido con el nombre del nivel se
#           CONSERVA (tapa la carga del nivel); como va por encima de todo (camera.ui, z=-100) cubre el velo del glitch,
#           que se desvanece solo debajo del negro: pantalla llena -> glitch -> negro con el nombre -> nivel.
#   True  = como None (no fuerza nada con la bandera apagada).
# Sin el argumento todo sigue igual para los llamadores de hoy.
#
# Prueba a mano sin pasar por el mundo: ALCALDE_PARKOUR=<nivel_id> python main.py abre ese nivel nada más arrancar
# (sin partida: no hay GameState, así que no otorga evidencia; Esc > Salir vuelve al menú de inicio).

import os
import sys

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


def entrar(nivel_id, reiniciar=False, volver_a=None, antesala=None):
    conexion = _estado["conexion"]
    if conexion is None:
        return False
    if antesala is None:                                 # llamadores de hoy: la misma llamada de siempre
        return conexion.ir_a_parkour(nivel_id, reiniciar=reiniciar, volver_a=volver_a)
    return conexion.ir_a_parkour(nivel_id, reiniciar=reiniciar, volver_a=volver_a, antesala=antesala)


def resultado(nivel_id):
    escena = _estado["escena"]
    return None if escena is None else escena.resultados.get(nivel_id)


def alturas(nivel_id):
    return parkour_calculos.alturas_para_minimapa(parkour_loader.cargar_nivel(nivel_id))


def niveles():
    return parkour_loader.listar_niveles()


# Antesala: la escena sabe si un fundido tapa la pantalla (la secuencia espera debajo del negro) y Espacio/Enter/mando
# la saltan por conexion.saltadores (una pulsación salta una sola cosa: primero el fundido, luego la antesala).
def _enganchar_antesala(escena, conexion):
    saltar = getattr(escena, "saltar_antesala", None)
    if saltar is None:
        return
    try:
        def velo():
            alfas = [t.alfa for t in (getattr(conexion, "_transicion", None), getattr(conexion, "_transicion_lugar", None))
                     if t is not None and t.ocupada]
            return max(alfas, default=0.0)
        escena.velo = velo
        conexion.saltadores.append(saltar)
    except Exception as error:                           # noqa: BLE001  sin saltador: la antesala termina sola
        print(f"[parkour] antesala sin enganches ({error!r})", file=sys.stderr)


def registrar(gestor, conexion, escena_mundo):
    from frontend.escenas.escena_parkour import EscenaParkour

    # `conexion.flujo` es None hasta que empieza la partida: se lee al terminar el nivel, no aquí.
    escena = EscenaParkour(game_state=lambda: getattr(conexion.flujo, "game_state", None),
                           jugador=lambda: conexion.flujo.jugador_activo() if conexion.flujo else None)
    gestor.registrar(PARKOUR, escena)
    _estado.update(conexion=conexion, escena=escena)
    _enganchar_antesala(escena, conexion)

    def salir_de_parkour():
        if conexion.flujo is None:                       # prueba de desarrollo: sin partida se vuelve al inicio
            gestor.cambiar_a(INICIO)
        else:
            conexion._con_transicion(conexion._volver_al_mundo)

    # Salida con destino propio: fundido -> volver_a(). Si no hay destino, la salida de siempre (MUNDO).
    def _salida(volver_a):
        if volver_a is None:
            return salir_de_parkour
        salida = lambda: conexion._con_transicion(volver_a)   # noqa: E731
        salida.con_retorno = True                        # la pausa del parkour dice «Volver», no «Salir al mundo»
        return salida

    def ir_a_parkour(nivel_id, reiniciar=False, volver_a=None, antesala=None):
        if not _puede_entrar(conexion):
            return False
        try:
            nivel = parkour_loader.cargar_nivel(nivel_id)
        except ValueError:
            return False

        def abrir():
            if antesala is None:                         # lo de siempre (la escena decide la antesala automática)
                gestor.cambiar_a(PARKOUR, nivel_id=nivel_id, reiniciar=reiniciar, salir=_salida(volver_a))
            else:
                gestor.cambiar_a(PARKOUR, nivel_id=nivel_id, reiniciar=reiniciar, salir=_salida(volver_a),
                                 antesala=antesala)

        conexion._con_transicion_lugar(abrir, texto=nivel.nombre)
        return True

    conexion.ir_a_parkour = ir_a_parkour
    conexion.salir_de_parkour = salir_de_parkour

    nivel_dev = os.environ.get(VARIABLE_DESARROLLO)
    if nivel_dev:
        from ursina import invoke
        def arranque_dev():
            try:
                gestor.cambiar_a(PARKOUR, nivel_id=nivel_dev, salir=salir_de_parkour)
            except ValueError as error:
                print(f"Aviso: no se pudo abrir el parkour de desarrollo {nivel_dev!r}: {error}", file=sys.stderr)

        invoke(arranque_dev, delay=RETRASO_DESARROLLO)
