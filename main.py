# Punto de entrada de Alcalde Digital (Ursina).
# Importar este módulo no abre ventana: todo se construye en crear_aplicacion().

from pathlib import Path

from panda3d.core import ClockObject, WindowProperties
from ursina import Ursina, application, window

from backend.datos.misiones_semilla import CATALOGO_MISIONES
from backend.datos.noticias_semilla import construir_arboles
from backend.grafos.grafo_social import construir_grafo_social_ejemplo
from backend.grafos.mapa_ciudad import construir_mapa_ejemplo
from backend.logica.estado_partida import EstadoPartida
from backend.logica.flujo_partida import FlujoPartida
from backend.logica.misiones import SistemaMisiones
from backend.logica.sesion import SesionJuego
from frontend import compat_macos, estilo
from frontend.componentes import preparar_fuente, rgb
from frontend.conexion_flujo import INICIO, JUEGO, MUNDO, SELECCION_ROL, ConexionFlujo
from frontend.escenas.escena_inicio import EscenaInicio
from frontend.escenas.escena_juego import EscenaJuego
from frontend.escenas.escena_mundo import EscenaMundo
from frontend.escenas.escena_seleccion_rol import EscenaSeleccionRol
from frontend.gestor_escenas import GestorEscenas
from frontend.transicion import Transicion

# Ventana 16:9 (camera.ui: x en [-0.888, 0.888], y en [-0.5, 0.5]).
TAMANO_VENTANA = (1280, 720)
FPS_MAXIMOS = 60
DURACION_TRANSICION = 0.25   # segundos de salida y de entrada del fundido a negro


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


# Sesión nueva con un EstadoPartida compartido (árboles del seed).
def crear_sesion():
    arbol_noticias, arbol_stats = construir_arboles()
    return SesionJuego(EstadoPartida(arbol_noticias, arbol_stats))


def registrar_escenas(gestor, mapa, duracion_transicion=DURACION_TRANSICION):
    # Crea las escenas y las conecta por callbacks (ninguna recibe al gestor).
    # duracion_transicion: segundos de cada mitad del fundido a negro (0 = sin fundido).
    def crear_flujo(sesion):
        return FlujoPartida(sesion, SistemaMisiones(mapa, CATALOGO_MISIONES))

    transicion = Transicion(duracion_transicion, duracion_transicion)
    conexion = ConexionFlujo(gestor, mapa, crear_flujo, transicion=transicion,
                             grafo_social=construir_grafo_social_ejemplo())
    gestor.registrar(INICIO, EscenaInicio(
        al_comenzar=conexion.ir_a_seleccion, al_salir=application.quit))
    gestor.registrar(SELECCION_ROL, EscenaSeleccionRol(
        fabrica_sesion=crear_sesion, al_comenzar=conexion.comenzar_partida))
    gestor.registrar(MUNDO, EscenaMundo(
        al_interactuar=conexion.interactuar, mapa=mapa, al_menu=conexion.volver_al_menu))
    gestor.registrar(JUEGO, EscenaJuego())
    return conexion


def crear_aplicacion(duracion_transicion=DURACION_TRANSICION):
    # Retorna (aplicacion, gestor) sin iniciar el loop: quien llama hace aplicacion.run().
    # duracion_transicion=0 quita el fundido (los scripts de prueba lo usan para ser deterministas).
    # development_mode=False oculta el panel de desarrollo, pero en Ursina 8.3.0
    # activaría fullscreen por defecto, así que se pide ventana explícita.
    compat_macos.aplicar()
    aplicacion = Ursina(title="Alcalde Digital", borderless=False, fullscreen=False,
                        development_mode=False, size=TAMANO_VENTANA)
    compat_macos.reaplicar()
    limitar_fps(FPS_MAXIMOS)
    application.asset_folder = Path(__file__).resolve().parent / "assets"
    window.color = rgb(estilo.COLOR_FONDO)
    fijar_tamano_ventana()
    preparar_fuente()

    gestor = GestorEscenas()
    registrar_escenas(gestor, construir_mapa_ejemplo(), duracion_transicion)
    gestor.cambiar_a(INICIO)
    return aplicacion, gestor


if __name__ == "__main__":
    aplicacion, _ = crear_aplicacion()
    aplicacion.run()
