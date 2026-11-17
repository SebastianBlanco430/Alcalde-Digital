# Banderas y guardián comunes de las «misiones visuales» (plan: misiones más dinámicas, visuales y llamativas).
# Python puro (sin ursina): lo usan todas las piezas visuales nuevas para decidir si se encienden, para avisar UNA vez por
# stderr cuando una vista nueva falla (y se vuelve a la de siempre) y para saber si el jugador pidió «reducir movimiento».
#
# Cada pieza tiene una constante en MAYÚSCULAS en su módulo y una variable ALCALDE_* que manda sobre ella:
#   ALCALDE_X=0 / false / no / off  -> apagada (el juego queda idéntico a hoy)
#   ALCALDE_X=1 / true / si / on    -> encendida
#   sin variable                    -> lo que diga la constante
#
# REDUCIR MOVIMIENTO: sin temblores, destellos, partículas ni cámara lenta. Lo manda ALCALDE_REDUCIR_MOVIMIENTO y, si no
# está, el interruptor de Ajustes › Movimiento (frontend/movimiento_ajustes.py), guardado en ajustes.json como
# «reducir_movimiento» (clave extra: los ajustes antiguos que no la traen leen False).

import os
import sys

_APAGADO = ("0", "false", "no", "off")
_ENCENDIDO = ("1", "true", "si", "sí", "on")

REDUCIR_MOVIMIENTO = False           # valor por defecto si ni la variable ni los ajustes dicen nada
CLAVE_AJUSTE = "reducir_movimiento"
VARIABLE_REDUCIR = "ALCALDE_REDUCIR_MOVIMIENTO"

# Bandera MAESTRA: ALCALDE_MISIONES_VISUALES=0 apaga todas las piezas visuales de una vez (cada pieza la consulta).
MISIONES_VISUALES = True
VARIABLE_MAESTRA = "ALCALDE_MISIONES_VISUALES"

_avisados = set()


def _leer(constante, variable):
    valor = os.environ.get(variable, "").strip().lower()
    if valor in _APAGADO:
        return False
    if valor in _ENCENDIDO:
        return True
    return bool(constante)


def maestra():
    return _leer(MISIONES_VISUALES, VARIABLE_MAESTRA)


def activa(constante, variable):
    """¿Está encendida la pieza? Exige la bandera maestra; luego la variable `variable` manda sobre `constante`."""
    return maestra() and _leer(constante, variable)


def avisar_una_vez(clave, error):
    """Guardián: avisa por stderr UNA sola vez por `clave` (la pieza que falló). Devuelve True si avisó ahora."""
    if clave in _avisados:
        return False
    _avisados.add(clave)
    try:
        print(f"[visual] {clave}: falló ({error!r}); se usa la vista de siempre.", file=sys.stderr)
    except Exception:                    # noqa: BLE001  stderr cerrado: el aviso no puede tumbar el juego
        pass
    return True


def olvidar_avisos():
    """Solo para pruebas: vuelve a permitir los avisos."""
    _avisados.clear()


def reducir_movimiento():
    """¿El jugador pidió reducir el movimiento? Variable de entorno > ajuste guardado > REDUCIR_MOVIMIENTO."""
    valor = os.environ.get(VARIABLE_REDUCIR, "").strip().lower()
    if valor in _APAGADO:
        return False
    if valor in _ENCENDIDO:
        return True
    try:
        from backend.logica import ajustes
        return bool(ajustes.obtener().actual.extras.get(CLAVE_AJUSTE, REDUCIR_MOVIMIENTO))
    except Exception:                    # noqa: BLE001  sin ajustes legibles: el valor por defecto
        return bool(REDUCIR_MOVIMIENTO)


def envolver_vista(control, clase, fabrica):
    """Pone `fabrica(vista)` como vista del `control` (bandeja de Civitas o dilemas) y devuelve el envoltorio, o None si
    no hay vista o ya está envuelta con `clase`.
    CONVIVENCIA con el «teléfono en grande» (frontend/registro_telefono_grande.py, ALCALDE_TELEFONO_GRANDE): si la vista
    del control es su VistaTelefono, el teléfono manda y lo nuestro envuelve su RESPALDO (el panel de siempre, el que usa
    para los casos sin canal, si el teléfono falla o si está apagado). Así no se apilan dos teléfonos."""
    vista, anfitrion = getattr(control, "vista", None), None
    if type(vista).__name__ == "VistaTelefono" and getattr(vista, "respaldo", None) is not None:
        anfitrion, vista = vista, vista.respaldo
    if vista is None or isinstance(vista, clase):
        return None
    envoltorio = fabrica(vista)
    if anfitrion is not None:
        anfitrion.respaldo = envoltorio
    else:
        control.vista = envoltorio
    return envoltorio
