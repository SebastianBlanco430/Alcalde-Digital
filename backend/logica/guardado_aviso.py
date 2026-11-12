# Aviso de privacidad del guardado y borrado manual (Python puro, sin ursina). Complementa a backend/logica/guardado.py
# sin tocarlo.
#
#   - AVISO de la primera vez: «Tu partida se guarda solo en este equipo; puedes borrarla en Ajustes.» Se muestra la
#     primera vez que se escribe un guardado; la marca queda en <directorio de ajustes>/aviso_guardado_visto (si no se
#     puede escribir, se muestra una vez por sesión y ya).
#   - BORRAR desde Ajustes: guardado.borrar() + suspender el autoguardado de la partida en curso (si no, el vigía la
#     volvería a escribir a los pocos segundos). Una partida nueva (otro flujo) vuelve a guardarse con normalidad.
#
# Bandera: AVISO_GUARDADO = False apaga solo el aviso (el botón de borrar sigue disponible).

from backend.logica import ajustes, guardado

AVISO_GUARDADO = True
NOMBRE_MARCA = "aviso_guardado_visto"
TEXTO_AVISO = "Tu partida se guarda solo en este equipo; puedes borrarla en Ajustes."

_visto_en_sesion = False
_suspendido = None


def ruta_marca(directorio=None):
    from pathlib import Path
    return (Path(directorio) if directorio is not None else ajustes.directorio_ajustes()) / NOMBRE_MARCA


def aviso_pendiente(directorio=None):
    if not AVISO_GUARDADO or _visto_en_sesion:
        return False
    try:
        return not ruta_marca(directorio).exists()
    except OSError:
        return True


def marcar_aviso_visto(directorio=None):
    global _visto_en_sesion
    _visto_en_sesion = True
    try:
        ruta = ruta_marca(directorio)
        ruta.parent.mkdir(parents=True, exist_ok=True)
        ruta.write_text("1", encoding="utf-8")
        return True
    except OSError:
        return False


def reiniciar_sesion():
    """Solo para pruebas: olvida lo visto y la suspensión de esta sesión."""
    global _visto_en_sesion, _suspendido
    _visto_en_sesion = False
    _suspendido = None


def borrar_partida(ruta=None):
    """Borra el guardado. Devuelve «borrado» o «nada» (no había guardado)."""
    return "borrado" if guardado.borrar(ruta) else "nada"


def suspender_autoguardado(identificador):
    """El jugador borró el guardado: la partida con este identificador (id del flujo) no se vuelve a autoguardar."""
    global _suspendido
    _suspendido = identificador


def autoguardado_suspendido_para(identificador):
    return _suspendido is not None and _suspendido == identificador
