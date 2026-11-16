# Registro de los minijuegos de verificar (plan: «misiones que se sienten distintas»). frontend/extensiones.py llama a registrar().
# Registra la escena EscenaMinijuego y le pone a la conexión un selector: para una misión de verificar con carta de misión
# (solo con GameState y consecuencias) elige el minijuego de backend/datos/minijuegos_asignacion.py; para todo lo demás devuelve
# None y ConexionFlujo abre la escena de juego de siempre.
#
# APAGADO (no hace nada, el juego queda idéntico a hoy):
#   - ALCALDE_MINIJUEGOS=0;
#   - en línea con ALCALDE_MINIJUEGOS_ONLINE=0 (main._conectar_online le pasa este selector a ConexionEnLinea). En línea el
#     minijuego decide con EstadoRemoto.decidir, así que el anfitrión recibe las decisiones de siempre (sin cambiar el protocolo).
# La bandera se lee también en cada misión (el selector la consulta), así se puede apagar sin reiniciar en las pruebas.

from backend.datos import minijuegos_asignacion as asignacion
from backend.logica import minijuegos as mj
from backend.logica import online_config

MINIJUEGO = "minijuego"      # nombre de la escena en el gestor


def elegir_escena(contexto):
    """Nombre de escena para la misión del `contexto` (el dict de FlujoPartida.iniciar_minijuego) o None = escena de juego."""
    if not mj.activo():
        return None
    mision, estado = contexto.get("mision"), contexto.get("estado")
    if mision is None or estado is None or not _con_cartas_mision(estado):
        return None          # sin carta de misión no hay veredicto que traducir (sin GameState, consecuencias apagadas...)
    if asignacion.asignar(mision) == mj.ACTUAL:
        return None
    return MINIJUEGO


# ¿El estado trae cartas de misión? Hot-seat: EstadoPartida.cartas_mision; en línea: EstadoRemoto.tiene_cartas_mision().
def _con_cartas_mision(estado):
    if getattr(estado, "cartas_mision", None) is not None:
        return True
    en_linea = getattr(estado, "tiene_cartas_mision", None)
    return online_config.MINIJUEGOS_ONLINE and callable(en_linea) and bool(en_linea())


def registrar(gestor, conexion, escena_mundo):
    if not mj.activo():
        return
    from frontend.escenas.escena_minijuego import EscenaMinijuego
    gestor.registrar(MINIJUEGO, EscenaMinijuego())
    conexion.selector_escena = elegir_escena
