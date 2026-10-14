# Punto de entrada de Alcalde Digital (Ursina).
# Importar este módulo no abre ventana: todo se construye en crear_aplicacion().

from pathlib import Path

import ursina as ursina_paquete

from panda3d.core import ClockObject, WindowProperties, loadPrcFileData
# Ursina trae un PNG con perfil iCCP antiguo: libpng avisa en cada arranque (inofensivo).
loadPrcFileData("", "notify-level-pnmimage error")
from ursina import Entity, Ursina, application, window

from backend.datos.misiones_semilla import CATALOGO_MISIONES
from backend.datos.noticias_semilla import construir_arboles
from backend.grafos.grafo_social import construir_grafo_social_ejemplo
from backend.datos.ciudad_3d import ESCALA_MUNDO, construir_mundo_3d
from backend.logica.estado_partida import EstadoPartida
from backend.logica.flujo_partida import FlujoPartida
from backend.logica.misiones import SistemaMisiones
from backend.logica.sesion import SesionJuego
from frontend import compat_macos, estilo
from frontend.componentes import preparar_fuente, rgb
from frontend.conexion_flujo import INICIO, INTERIOR, JUEGO, MUNDO, SELECCION_ROL, ConexionFlujo
from frontend.escenas.escena_inicio import EscenaInicio
from frontend.escenas.escena_interior import EscenaInterior
from frontend.escenas.escena_juego import EscenaJuego
from frontend.escenas.escena_mundo import EscenaMundo
from frontend.escenas.escena_seleccion_rol import EscenaSeleccionRol
from frontend.gestor_escenas import GestorEscenas
from frontend import guion_cinematicas
from frontend.transicion import Transicion

# Ventana 16:9 (camera.ui: x en [-0.888, 0.888], y en [-0.5, 0.5]).
TAMANO_VENTANA = (1280, 720)
FPS_MAXIMOS = 60
DURACION_TRANSICION = 0.25   # segundos de salida y de entrada del fundido a negro
DURACION_CINEMATICA = 1.0    # factor de las duraciones del guion (0 = cinemáticas instantáneas, para los scripts)
RADIO_INTERACCION = 2.0      # m: "llegué" = a menos de esto de la PUERTA del edificio destino


# Espacio / Enter saltan la cinemática (y el fundido) en curso, en cualquier escena.
class AtajosCinematica(Entity):

    def __init__(self, conexion, **opciones):
        super().__init__(**opciones)
        self._conexion = conexion

    def input(self, key):
        if key in ("space", "enter"):
            self._conexion.saltar_cinematica()


def limitar_fps(fps):
    # En la prueba del mundo el juego corria a ~180 fps (la tasa del monitor) usando ~50 %
    # de un nucleo. Se limita el reloj de Panda3D a `fps`: dt estable (movimiento y
    # camara mas suaves) y menos CPU. No se usa `window.vsync = fps` porque en Ursina 8.3
    # ese setter, una vez abierta la ventana, solo escribe un prc que ya no se lee.
    reloj = ClockObject.get_global_clock()
    reloj.set_mode(ClockObject.M_limited)
    reloj.set_frame_rate(fps)


def fijar_tamano_ventana():
    # Impide redimensionar/maximizar: el layout está calculado para 16:9 y Ursina
    # solo reubica en x los hijos directos de camera.ui al cambiar el aspecto.
    propiedades = WindowProperties()
    propiedades.set_fixed_size(True)
    application.base.win.request_properties(propiedades)


# Sesión nueva con un EstadoPartida compartido (árboles del seed). Los spawns de los roles se
# escalan al mundo 3D (×4, 1 unidad = 1 m).
def crear_sesion():
    arbol_noticias, arbol_stats = construir_arboles()
    return SesionJuego(EstadoPartida(arbol_noticias, arbol_stats), escala_mundo=ESCALA_MUNDO)


def registrar_escenas(gestor, mundo, duracion_transicion=DURACION_TRANSICION,
                      duracion_cinematica=DURACION_CINEMATICA):
    # Crea las escenas y las conecta por callbacks (ninguna recibe al gestor).
    # duracion_transicion: segundos de cada mitad del fundido a negro (0 = sin fundido).
    # duracion_cinematica: factor de las cinemáticas de entrar/salir de un edificio (0 = instantáneas)
    # y del negro con el nombre del lugar.
    def crear_flujo(sesion):
        return FlujoPartida(sesion, SistemaMisiones(
            mundo, CATALOGO_MISIONES, radio_interaccion=RADIO_INTERACCION,
            punto_interaccion=mundo.punto_interaccion))

    transicion = Transicion(duracion_transicion, duracion_transicion)
    # Fundido de la entrada a un edificio: sale a negro, se queda en negro con el nombre del lugar, vuelve.
    transicion_lugar = Transicion(
        guion_cinematicas.NEGRO_SALIDA * duracion_cinematica, guion_cinematicas.NEGRO_ENTRADA * duracion_cinematica,
        guion_cinematicas.NEGRO_SOSTENER * duracion_cinematica)
    conexion = ConexionFlujo(gestor, mundo, crear_flujo, transicion=transicion,
                             grafo_social=construir_grafo_social_ejemplo(),
                             transicion_lugar=transicion_lugar, con_interior=True)
    gestor.registrar(INICIO, EscenaInicio(
        al_comenzar=conexion.ir_a_seleccion, al_salir=application.quit))
    gestor.registrar(SELECCION_ROL, EscenaSeleccionRol(
        fabrica_sesion=crear_sesion, al_comenzar=conexion.comenzar_partida))
    escena_mundo = EscenaMundo(
        al_interactuar=conexion.interactuar, mundo=mundo, al_menu=conexion.volver_al_menu,
        escala_tiempo=duracion_cinematica)
    gestor.registrar(MUNDO, escena_mundo)
    conexion.cinematicas = escena_mundo          # reproduce la cinemática de entrada al pulsar E
    escena_interior = EscenaInterior(escala_tiempo=duracion_cinematica)
    gestor.registrar(INTERIOR, escena_interior)
    gestor.registrar(JUEGO, EscenaJuego())
    # Orden de salto: primero los fundidos, luego las cinemáticas.
    conexion.saltadores = [transicion_lugar.saltar, transicion.saltar, escena_mundo.saltar_cinematica,
                           escena_interior.saltar_cinematica]
    conexion.atajos = AtajosCinematica(conexion)
    return conexion


def crear_aplicacion(duracion_transicion=DURACION_TRANSICION, duracion_cinematica=DURACION_CINEMATICA):
    # Retorna (aplicacion, gestor) sin iniciar el loop: quien llama hace aplicacion.run().
    # duracion_transicion=0 quita el fundido y duracion_cinematica=0 las cinemáticas (los scripts
    # de prueba lo usan para ser deterministas).
    # development_mode=False oculta el panel de desarrollo, pero en Ursina 8.3.0
    # activaría fullscreen por defecto, así que se pide ventana explícita.
    compat_macos.aplicar()
    # El icono por defecto ('textures/ursina.ico') es relativo y Panda no lo encuentra (un error por
    # cada cambio de propiedades de la ventana): se pasa la ruta absoluta del que trae Ursina.
    icono = Path(ursina_paquete.__file__).resolve().parent / "textures" / "ursina.ico"
    aplicacion = Ursina(title="Alcalde Digital", icon=icono.as_posix(), borderless=False, fullscreen=False,
                        development_mode=False, size=TAMANO_VENTANA)
    compat_macos.reaplicar()
    limitar_fps(FPS_MAXIMOS)
    application.asset_folder = Path(__file__).resolve().parent / "assets"
    window.color = rgb(estilo.COLOR_FONDO)
    fijar_tamano_ventana()
    preparar_fuente()

    gestor = GestorEscenas()
    registrar_escenas(gestor, construir_mundo_3d(), duracion_transicion, duracion_cinematica)
    gestor.cambiar_a(INICIO)
    return aplicacion, gestor


if __name__ == "__main__":
    aplicacion, _ = crear_aplicacion()
    aplicacion.run()
