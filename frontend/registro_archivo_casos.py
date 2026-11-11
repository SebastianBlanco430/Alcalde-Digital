# Registro del ARCHIVO DE CASOS (Ola 3, subagente E). frontend/extensiones.py llama a registrar(): crea el panel
# (frontend/archivo_casos_ui.py), el Entity que oye la tecla J y engancha el panel a EscenaMundo como «bloqueador»
# (mientras está abierto el jugador no se mueve, el ratón se libera y Escape lo cierra en vez de pausar).
#
# El GameState se lee de `escena_mundo.flujo` al pulsar J: en línea o con ALCALDE_GAMESTATE=0 no hay y el panel dice
# «Archivo no disponible». Apagado con economia_config.ARCHIVO_CASOS = False (no se crea nada).
#
# API: conexion.archivo_casos = ControlArchivoCasos (abrir_o_cerrar(), ui). Los textos salen de
# backend/datos/archivo_casos_textos.json; los nombres, del catálogo de casos y de los niveles de parkour.

import sys

from backend.datos import casos_loader, parkour_loader
from backend.datos.archivo_casos_textos import cargar_textos
from backend.logica import archivo_casos
from backend.logica.casos import CasoError
from frontend import economia_config, teclas


def _nombre_nivel(nivel_id):
    try:
        return parkour_loader.cargar_nivel(nivel_id).nombre
    except ValueError:
        return nivel_id


def _catalogo():
    try:
        return casos_loader.cargar_catalogo()
    except CasoError as error:
        print(f"[archivo de casos] sin nombres de casos: {error}", file=sys.stderr)
        return {}


# Quien pulsa J no puede abrirlo con otro panel o la pausa encima, ni con el teléfono abierto.
def _puede_abrir(escena_mundo):
    flujo = escena_mundo.flujo
    if not escena_mundo.enabled or flujo is None or escena_mundo.controles_bloqueados():
        return False
    try:
        return not flujo.jugador_activo().telefono.bloquea_movimiento()
    except AttributeError:
        return True


def registrar(gestor, conexion, escena_mundo):
    if not economia_config.ARCHIVO_CASOS or not economia_config.GAMESTATE:     # sin GameState no hay Archivo (J libre)
        return None
    try:
        textos = cargar_textos()
    except ValueError as error:
        print(f"[archivo de casos] desactivado: {error}", file=sys.stderr)
        return None
    from frontend.archivo_casos_ui import ArchivoCasosUI, ControlArchivoCasos

    ui = ArchivoCasosUI(textos)

    def abrir():
        gs = getattr(escena_mundo.flujo, "game_state", None)
        archivo = archivo_casos.construir(gs)
        ctx = archivo_casos.Contexto(textos, _catalogo(), _nombre_nivel)
        ui.abrir(archivo, ctx)
        escena_mundo._sincronizar_raton()      # libera el ratón ya, sin esperar al siguiente frame

    control = ControlArchivoCasos(ui, teclas.TECLA_ARCHIVO_CASOS, lambda: _puede_abrir(escena_mundo), abrir)
    escena_mundo.registrar_bloqueador(ui.abierto, ui.cerrar)

    # El inventario (I) no mira controles_bloqueados: se le impide abrirse encima del Archivo.
    economia = getattr(escena_mundo, "economia", None)
    if economia is not None:
        puede_abrir_original = economia.puede_abrir
        economia.puede_abrir = lambda: puede_abrir_original() and not ui.abierto()

    conexion.archivo_casos = control
    return control
