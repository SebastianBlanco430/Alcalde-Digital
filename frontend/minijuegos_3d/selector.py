# Selector 2D / 3D de los minijuegos de verificar. Lo llama frontend/escenas/escena_minijuego.py al preparar el minijuego
# (y frontend/conexion_flujo.py para saber si la cinemática de sentarse al PC tiene sentido). No importa ursina al cargarse.
#
#   clase_3d(id) -> la clase de presentación 3D (subclase de frontend.minijuegos_3d.base.Minijuego3D) o None = 2D de hoy.
#
# Orden: banderas (maestra + la del minijuego) -> demostración (ALCALDE_3D_DEMO) -> módulo de la familia. El módulo de la
# familia se importa PEREZOSAMENTE por nombre (<id>_3d.py dentro de este paquete) y debe exponer `CLASE_3D`. Que el módulo
# no exista es lo normal mientras la familia no lo escriba (2D sin avisar); cualquier error al importarlo o una CLASE_3D
# inválida también da 2D (con un aviso por stderr una sola vez). NUNCA lanza.
#
# Los nombres de módulo se arman por partes (PAQUETE + "." + nombre) a propósito: la regla R6 de
# tests/test_arquitectura_mvc.py exige que toda cadena «frontend.x.y» literal resuelva, y los módulos de las familias aún no
# existen.

import importlib
import importlib.util

from frontend import banderas_visuales as bv
from frontend.minijuegos_3d import banderas

PAQUETE = __name__.rsplit(".", 1)[0]

# id -> familia (cámara y set que usa) y nombre del módulo (reservado a la familia; NO lo crea infra-3d)
FAMILIAS = {
    "chat": "pc",
    "contrarreloj": "pc",
    "rastrear": "corcho",
    "cronologia": "corcho",
    "comparar": "mesa",
    "senales": "mesa",
}
MODULOS = {mid: f"{mid}_3d" for mid in FAMILIAS}
ATRIBUTO_CLASE = "CLASE_3D"
MODULO_DEMO = "demo_monitor"


def familia_de(minijuego_id):
    """'pc' | 'corcho' | 'mesa' | None."""
    return FAMILIAS.get(minijuego_id)


def _valida(clase):
    return isinstance(clase, type) and callable(getattr(clase, "abrir", None)) and callable(getattr(clase, "cerrar", None))


def _importar(nombre):
    """Módulo `PAQUETE.nombre` o None si no existe. Lanza si existe y falla al importarse (lo captura el llamador)."""
    ruta = f"{PAQUETE}.{nombre}"
    if importlib.util.find_spec(ruta) is None:
        return None
    return importlib.import_module(ruta)


def clase_familia(minijuego_id):
    """CLASE_3D del módulo de la familia, sin mirar banderas. None si no existe o no vale. Nunca lanza."""
    nombre = MODULOS.get(minijuego_id)
    if nombre is None:
        return None
    try:
        modulo = _importar(nombre)
        if modulo is None:
            return None
        clase = getattr(modulo, ATRIBUTO_CLASE, None)
        if not _valida(clase):
            bv.avisar_una_vez(f"3d_{minijuego_id}", TypeError(f"{nombre}.{ATRIBUTO_CLASE} falta o no es una clase 3D"))
            return None
        return clase
    except Exception as error:      # noqa: BLE001  una familia rota nunca impide jugar: 2D
        bv.avisar_una_vez(f"3d_{minijuego_id}", error)
        return None


def clase_demo():
    try:
        modulo = _importar(MODULO_DEMO)
        clase = getattr(modulo, ATRIBUTO_CLASE, None) if modulo is not None else None
        return clase if _valida(clase) else None
    except Exception as error:      # noqa: BLE001
        bv.avisar_una_vez("3d_demo", error)
        return None


def clase_3d(minijuego_id, entorno=None):
    """Clase de presentación 3D para `minijuego_id`, o None = el 2D de hoy. Nunca lanza."""
    try:
        if not banderas.activa(minijuego_id, entorno):
            return None
        if banderas.demo_activa(minijuego_id, entorno):
            demo = clase_demo()
            if demo is not None:
                return demo
        return clase_familia(minijuego_id)
    except Exception as error:      # noqa: BLE001
        bv.avisar_una_vez("3d_selector", error)
        return None


def familia_efectiva(minijuego_id, entorno=None):
    """Familia de la presentación 3D que se usará ('pc' | 'corcho' | 'mesa'), o None si el minijuego irá en 2D.
    La demostración siempre es 'pc' (monitor). Nunca lanza."""
    clase = clase_3d(minijuego_id, entorno)
    if clase is None:
        return None
    return getattr(clase, "FAMILIA", None) or familia_de(minijuego_id)


def sentarse_al_pc(mision, entorno=None):
    """¿Tiene sentido la cinemática de sentarse al PC del interior para esta misión? False solo si el minijuego irá en 3D
    con una familia que no es la del PC (corcho o mesa): entonces el personaje entra y camina hasta el corcho o la mesa
    dentro de la presentación 3D. Ante cualquier duda (misión rara, error) True = el camino de hoy. Nunca lanza."""
    try:
        if not banderas.maestra(entorno):
            return True
        from backend.datos import minijuegos_asignacion as asignacion
        familia = familia_efectiva(asignacion.asignar(mision), entorno)
        return familia in (None, "pc")
    except Exception:               # noqa: BLE001
        return True
