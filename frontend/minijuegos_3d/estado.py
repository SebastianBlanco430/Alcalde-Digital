# Estado compartido mínimo del rework 3D entre la presentación (base.py), la escena del minijuego y ConexionFlujo (Python
# puro: NO importa ursina). Sirve para que la SALIDA del edificio sea coherente con lo que se vio:
#
#   - Minijuego3D.resultado() marca `jugado_en_3d(familia)` cuando el minijuego TERMINA en 3D;
#   - EscenaMinijuego borra la marca al empezar cada minijuego y cuando el 3D cae al 2D (respaldo);
#   - ConexionFlujo._salir_del_edificio la consume (`consumir_salida()`): con marca, sale directo al mundo (fundido + la
#     cinemática de salir por la puerta) sin la escena «levantarse» de la silla del PC del interior.
# Sin marca (2D, maestra apagada, respaldo) todo es el camino de hoy.

import time
import weakref

_estado = {"familia": None, "sin_destello": False, "abierta": False, "fundido": None, "salto": -1.0}

VENTANA_SALTO_S = 0.12       # una pulsación = un solo salto: lo que tarde el mismo Espacio en llegar a la otra escena


def vigilar_fundido(ocupado):
    """Sesión B: ConexionFlujo deja aquí su `_transicion_en_curso` (método ligado; se guarda sin retenerlo)."""
    try:
        _estado["fundido"] = weakref.WeakMethod(ocupado)
    except TypeError:
        _estado["fundido"] = None


def marcar_salto():
    """ConexionFlujo.saltar_cinematica acaba de saltar algo (un fundido, una cinemática) con esta pulsación."""
    _estado["salto"] = time.perf_counter()


def pulsacion_gastada():
    """¿Este Espacio/Enter ya saltó (o va a saltar) un fundido? Entonces NO salta además la entrada animada. Nunca lanza."""
    try:
        if 0.0 <= time.perf_counter() - _estado["salto"] <= VENTANA_SALTO_S:
            return True
        ref = _estado["fundido"]
        ocupado = ref() if ref is not None else None
        return bool(ocupado()) if ocupado is not None else False
    except Exception:                # noqa: BLE001
        return False


def presentacion_abierta(si=None):
    """Sesión B: ¿hay una presentación 3D abierta? (la marca base.abrir / cerrar). Con ella abierta, Espacio/Enter los
    trata EscenaMinijuego (salta la entrada/salida animadas sin que la tecla llegue a la previa ni al juego) y
    ConexionFlujo no las salta por su cuenta. `si` = True/False la fija; None solo la lee."""
    if si is not None:
        _estado["abierta"] = bool(si)
    return _estado["abierta"]


def entrada_sin_destello(si):
    """ConexionFlujo: la cinemática de sentarse llega al monitor SIN destello (familia PC en 3D)."""
    _estado["sin_destello"] = bool(si)


def consumir_sin_destello():
    """La presentación 3D lo lee (y lo borra) al abrirse: sin destello delante, no pone velo de entrada."""
    si, _estado["sin_destello"] = _estado["sin_destello"], False
    return si


def jugado_en_3d(familia):
    """El minijuego en curso terminó EN 3D con la familia `familia` ('pc' | 'corcho' | 'mesa')."""
    _estado["familia"] = familia


def olvidar():
    """Sin marca (nuevo minijuego, o el 3D cayó al 2D)."""
    _estado["familia"] = None


def familia_jugada():
    return _estado["familia"]


def consumir_salida():
    """Familia del último minijuego terminado en 3D (y borra la marca), o None."""
    familia, _estado["familia"] = _estado["familia"], None
    return familia
