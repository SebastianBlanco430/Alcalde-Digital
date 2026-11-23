# Estado compartido mínimo del rework 3D entre la presentación (base.py), la escena del minijuego y ConexionFlujo (Python
# puro: NO importa ursina). Sirve para que la SALIDA del edificio sea coherente con lo que se vio:
#
#   - Minijuego3D.resultado() marca `jugado_en_3d(familia)` cuando el minijuego TERMINA en 3D;
#   - EscenaMinijuego borra la marca al empezar cada minijuego y cuando el 3D cae al 2D (respaldo);
#   - ConexionFlujo._salir_del_edificio la consume (`consumir_salida()`): con marca, sale directo al mundo (fundido + la
#     cinemática de salir por la puerta) sin la escena «levantarse» de la silla del PC del interior.
# Sin marca (2D, maestra apagada, respaldo) todo es el camino de hoy.

_estado = {"familia": None, "sin_destello": False}


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
