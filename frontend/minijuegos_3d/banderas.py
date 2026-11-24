# Banderas del rework 3D de los minijuegos de verificar (Python puro: NO importa ursina). Documentadas en
# docs/MINIJUEGOS_3D.md y en rework-3d/contrato.md.
#
#   ALCALDE_MINIJUEGOS_3D      maestra. 0 = los 6 minijuegos se ven como hoy (2D), pase lo que pase con las demás.
#   ALCALDE_3D_CHAT            una por minijuego. 0 = ese minijuego en 2D. Encendida y SIN implementación 3D de la familia
#   ALCALDE_3D_CONTRARRELOJ    (frontend/minijuegos_3d/<id>_3d.py con CLASE_3D) también da 2D: el selector
#   ALCALDE_3D_RASTREAR        (frontend/minijuegos_3d/selector.py) trata la ausencia o cualquier error como «2D».
#   ALCALDE_3D_CRONOLOGIA
#   ALCALDE_3D_COMPARAR
#   ALCALDE_3D_SENALES
#   ALCALDE_3D_DEMO            demostración de la infraestructura (la vista 2D de hoy dentro de un monitor 3D). Apagada
#                              por defecto. 1 / todos = los 6; «chat,rastrear» = esos. Gana a la implementación de la familia
#                              (solo para probar), pero respeta la maestra y la bandera del minijuego.
#
# Valores: 0/false/no/off apaga, 1/true/si/sí/on enciende, sin variable = la constante de abajo. Se leen en cada llamada
# (se pueden cambiar entre misiones en las pruebas sin reiniciar).

import os

MINIJUEGOS_3D = True                 # maestra (valor por defecto)
VARIABLE_MAESTRA = "ALCALDE_MINIJUEGOS_3D"
VARIABLE_DEMO = "ALCALDE_3D_DEMO"

# id del minijuego (backend/logica/minijuegos.py) -> (constante por defecto, variable)
POR_MINIJUEGO = {
    "chat": (True, "ALCALDE_3D_CHAT"),
    "contrarreloj": (True, "ALCALDE_3D_CONTRARRELOJ"),
    "rastrear": (True, "ALCALDE_3D_RASTREAR"),
    "cronologia": (True, "ALCALDE_3D_CRONOLOGIA"),
    "comparar": (True, "ALCALDE_3D_COMPARAR"),
    "senales": (True, "ALCALDE_3D_SENALES"),
}

_APAGADO = ("0", "false", "no", "off")
_ENCENDIDO = ("1", "true", "si", "sí", "on")


def _leer(constante, variable, entorno=None):
    valor = (entorno if entorno is not None else os.environ).get(variable, "").strip().lower()
    if valor in _APAGADO:
        return False
    if valor in _ENCENDIDO:
        return True
    return bool(constante)


def maestra(entorno=None):
    """¿Está encendida ALCALDE_MINIJUEGOS_3D?"""
    return _leer(MINIJUEGOS_3D, VARIABLE_MAESTRA, entorno)


def variable_de(minijuego_id):
    """Nombre de la variable ALCALDE_3D_* del minijuego (None si el id no es de los 6)."""
    entrada = POR_MINIJUEGO.get(minijuego_id)
    return entrada[1] if entrada else None


def activa(minijuego_id, entorno=None):
    """¿Puede ir en 3D `minijuego_id`? Maestra Y bandera propia. Un id desconocido nunca va en 3D."""
    entrada = POR_MINIJUEGO.get(minijuego_id)
    if entrada is None or not maestra(entorno):
        return False
    return _leer(entrada[0], entrada[1], entorno)


def demo_activa(minijuego_id, entorno=None):
    """¿Pide ALCALDE_3D_DEMO la demostración (vista 2D en un monitor 3D) para `minijuego_id`?"""
    if not activa(minijuego_id, entorno):
        return False
    valor = (entorno if entorno is not None else os.environ).get(VARIABLE_DEMO, "").strip().lower()
    if not valor or valor in _APAGADO:
        return False
    if valor in _ENCENDIDO or valor in ("todos", "all", "*"):
        return True
    return minijuego_id in {parte.strip() for parte in valor.split(",")}


PREVIA_EN_MONITOR = True             # familia PC: la pantalla «Antes de empezar» dentro del monitor 3D
VARIABLE_PREVIA = "ALCALDE_3D_PREVIA_MONITOR"
ENTRADA_SIN_DESTELLO = True          # familia PC: la cinemática de sentarse llega al monitor sin el destello blanco
VARIABLE_DESTELLO = "ALCALDE_3D_SIN_DESTELLO"


def previa_en_monitor(entorno=None):
    return maestra(entorno) and _leer(PREVIA_EN_MONITOR, VARIABLE_PREVIA, entorno)


def entrada_sin_destello(entorno=None):
    return maestra(entorno) and _leer(ENTRADA_SIN_DESTELLO, VARIABLE_DESTELLO, entorno)


ANIM_SILLA = True                    # sesión B: entrada/salida animadas (silla, corcho) DENTRO del 3D del minijuego
VARIABLE_ANIM_SILLA = "ALCALDE_ANIM_SILLA"
MODULO_SILLA = "frontend.cinematica_silla"


def anim_silla(entorno=None, modulo_existe=None):
    """¿Entrada y salida animadas de los minijuegos 3D (sesión B)? ALCALDE_ANIM_SILLA encendida (por defecto) Y el
    módulo frontend/cinematica_silla.py presente (sin él: el camino de hoy). No importa ursina. Nunca lanza."""
    try:
        if not _leer(ANIM_SILLA, VARIABLE_ANIM_SILLA, entorno):
            return False
        if modulo_existe is None:
            import importlib.util
            modulo_existe = importlib.util.find_spec(MODULO_SILLA) is not None
        return bool(modulo_existe)
    except Exception:                    # noqa: BLE001
        return False


VARIABLE_FALLO = "ALCALDE_3D_FALLO"
FASES_FALLO = ("abrir", "avanzar", "tecla", "resultado")


def fallo_inyectado(fase, entorno=None):
    """PRUEBAS: ALCALDE_3D_FALLO=abrir|avanzar|tecla|resultado hace que la presentación 3D lance en esa fase (para ver el
    respaldo al 2D). Sin variable (lo normal) nunca falla."""
    valor = (entorno if entorno is not None else os.environ).get(VARIABLE_FALLO, "").strip().lower()
    return bool(valor) and fase in {parte.strip() for parte in valor.split(",")}


def resumen(entorno=None):
    """{id: True/False} de las 6 banderas efectivas (maestra incluida), para registros y el informe."""
    return {mid: activa(mid, entorno) for mid in POR_MINIJUEGO}
