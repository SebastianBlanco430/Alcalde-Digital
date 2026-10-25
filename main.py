# Punto de entrada de Alcalde Digital (Ursina).
# Importar este módulo no abre ventana: todo se construye en crear_aplicacion().

import os
from pathlib import Path

import ursina as ursina_paquete

from panda3d.core import ClockObject, Filename, WindowProperties, loadPrcFileData
# Ursina trae un PNG con perfil iCCP antiguo: libpng avisa en cada arranque (inofensivo).
loadPrcFileData("", "notify-level-pnmimage error")
from ursina import Entity, Ursina, application, window

from backend.datos.misiones_semilla import CATALOGO_MISIONES
from backend.datos.noticias_semilla import construir_arboles
from backend.grafos.grafo_social import construir_grafo_social_ejemplo
from backend.datos.ciudad_3d import ESCALA_MUNDO, SEMILLA_CASAS, construir_mundo_3d

from backend.logica.estado_partida import EstadoPartida
from backend.logica.flujo_partida import FlujoPartida
from backend.logica.misiones import SistemaMisiones
from backend.logica.sesion import SesionJuego
from frontend import online_config
from frontend import compat_macos, daltonismo, diseno_adaptable, estilo, medidor_fps, tipografia
from frontend import gpu_dedicada, rendimiento, telemetria
from frontend import audio_enganches      # sonido: observa el juego y dispara efectos/música (frontend/audio.py)
from frontend.componentes import preparar_fuente, rgb
from frontend.conexion_flujo import INICIO, INTERIOR, JUEGO, MUNDO, SELECCION_ROL, ConexionFlujo
from backend.logica import ajustes as ajustes_jugador
from frontend.escenas.escena_ajustes import AJUSTES_ESCENA, EscenaAjustes
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


# Con ONLINE, las escenas del mundo llaman a la conexión ACTIVA: la del hot-seat de siempre, o la ConexionEnLinea
# mientras dura una partida en línea. Delega cada atributo en el objeto que haya en `activa[0]`.
class ConexionActiva:

    def __init__(self, activa):
        self._activa = activa

    def __getattr__(self, nombre):
        # Solo se llega aquí si `nombre` no existe: sin `_activa` (copia/pickle antes de __init__) no se recursa.
        if nombre == "_activa":
            raise AttributeError(nombre)
        return getattr(self._activa[0], nombre)


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
                      duracion_cinematica=DURACION_CINEMATICA, semilla=SEMILLA_CASAS, al_empezar_online=None):
    # Con ONLINE y sin `al_empezar_online`, la partida en línea real la arranca frontend/online_arranque.py.
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
    # Ajustes (bandera AJUSTES): escena aparte accesible desde el inicio; «Atrás/Guardar» vuelven al inicio.
    al_ajustes = None
    if ajustes_jugador.AJUSTES:
        gestor.registrar(AJUSTES_ESCENA, EscenaAjustes(al_volver=lambda: gestor.cambiar_a(INICIO)))
        al_ajustes = lambda: gestor.cambiar_a(AJUSTES_ESCENA)
    # Modo online (bandera ONLINE en frontend/online_config): registro PEREZOSO; con False no se importa backend.red.
    al_online = None
    arranque_online = [None]       # callback real de «Iniciar partida»; lo fija _conectar_online al final
    if online_config.ONLINE:
        from frontend import online_registro
        al_online = online_registro.registrar(
            gestor, mundo, semilla, al_inicio=lambda: gestor.cambiar_a(INICIO),
            al_empezar=lambda cliente, info: arranque_online[0](cliente, info))
    # Con ONLINE las escenas del mundo hablan con la conexión «activa» (hot-seat u online); sin ONLINE, con la de siempre.
    activa = [conexion]
    destino = ConexionActiva(activa) if online_config.ONLINE else conexion
    gestor.registrar(INICIO, EscenaInicio(
        al_comenzar=conexion.ir_a_seleccion, al_salir=application.quit, al_ajustes=al_ajustes, al_online=al_online))
    gestor.registrar(SELECCION_ROL, EscenaSeleccionRol(
        fabrica_sesion=crear_sesion, al_comenzar=conexion.comenzar_partida))
    escena_mundo = EscenaMundo(
        al_interactuar=(lambda: destino.interactuar()) if online_config.ONLINE else conexion.interactuar,
        mundo=mundo, al_menu=(lambda: destino.volver_al_menu()) if online_config.ONLINE else conexion.volver_al_menu,
        escala_tiempo=duracion_cinematica)
    gestor.registrar(MUNDO, escena_mundo)
    conexion.cinematicas = escena_mundo          # reproduce la cinemática de entrada al pulsar E
    escena_interior = EscenaInterior(escala_tiempo=duracion_cinematica)
    gestor.registrar(INTERIOR, escena_interior)
    gestor.registrar(JUEGO, EscenaJuego())
    # Orden de salto: primero los fundidos, luego las cinemáticas.
    conexion.saltadores = [transicion_lugar.saltar, transicion.saltar, escena_mundo.saltar_cinematica,
                           escena_interior.saltar_cinematica]
    conexion.atajos = AtajosCinematica(destino)
    if online_config.ONLINE:
        _conectar_online(gestor, mundo, conexion, activa, escena_mundo, transicion, transicion_lugar,
                         al_empezar_online, arranque_online)
    return conexion


# Partida online real (solo con ONLINE): crea la ConexionEnLinea (misma cadena de escenas y fundidos que el hot-seat) y
# el ArranqueOnline que recibe el callback de la sala. Si `al_empezar_online` ya vino dado (pruebas), no se crea.
def _conectar_online(gestor, mundo, conexion, activa, escena_mundo, transicion, transicion_lugar, al_empezar_online,
                     arranque_online):
    from frontend.online_arranque import ArranqueOnline
    from frontend.online_conexion import ConexionEnLinea
    en_linea = ConexionEnLinea(gestor, mundo, transicion=transicion, grafo_social=conexion._grafo_social,
                               transicion_lugar=transicion_lugar, con_interior=True)
    en_linea.cinematicas = escena_mundo
    en_linea.saltadores = conexion.saltadores
    arranque = ArranqueOnline(gestor, mundo, en_linea, lambda on: activa.__setitem__(0, en_linea if on else conexion),
                              escena_mundo=escena_mundo)
    arranque_online[0] = arranque.al_empezar if al_empezar_online is None else al_empezar_online
    conexion.arranque_online = arranque


# Semilla de la favela: la variable de entorno ALCALDE_SEMILLA (entero) elige otra disposición de
# casas; sin ella, o si no es un entero, se usa la de siempre.
def leer_semilla():
    bruto = os.environ.get("ALCALDE_SEMILLA")
    if bruto is None:
        return SEMILLA_CASAS
    try:
        semilla = int(bruto)
    except ValueError:
        print(f"[Mundo] ALCALDE_SEMILLA={bruto!r} no es un entero; uso {SEMILLA_CASAS}.")
        return SEMILLA_CASAS
    print(f"[Mundo] semilla de la favela: {semilla}")
    return semilla


def crear_aplicacion(duracion_transicion=DURACION_TRANSICION, duracion_cinematica=DURACION_CINEMATICA):
    # Retorna (aplicacion, gestor) sin iniciar el loop: quien llama hace aplicacion.run().
    # duracion_transicion=0 quita el fundido y duracion_cinematica=0 las cinemáticas (los scripts
    # de prueba lo usan para ser deterministas).
    # development_mode=False oculta el panel de desarrollo, pero en Ursina 8.3.0
    # activaría fullscreen por defecto, así que se pide ventana explícita.
    compat_macos.aplicar()
    rendimiento.configurar_panda()   # opciones de Panda que deben ir antes de abrir la ventana
    # El icono por defecto ('textures/ursina.ico') es relativo y Panda no lo encuentra (un error por
    # cada cambio de propiedades de la ventana): se pasa la ruta absoluta del que trae Ursina, en
    # formato de Panda ('/c/...'); con 'C:/...' Panda tampoco la encuentra en Windows.
    icono = Filename.from_os_specific(str(Path(ursina_paquete.__file__).resolve().parent / "textures" / "ursina.ico"))
    aplicacion = Ursina(title="Alcalde Digital", icon=icono.get_fullpath(), borderless=False, fullscreen=False,
                        development_mode=False, size=TAMANO_VENTANA)
    compat_macos.reaplicar()
    rendimiento.preparar_raices()    # posición de la cámara para la niebla, en la raíz (frontend/rendimiento.py)
    if medidor_fps.modo() != "libre":
        limitar_fps(FPS_MAXIMOS)
    if medidor_fps.modo():
        medidor_fps.MedidorFps()
    application.asset_folder = Path(__file__).resolve().parent / "assets"
    window.color = rgb(estilo.COLOR_FONDO)
    fijar_tamano_ventana()
    diseno_adaptable.instalar()      # reancla/reescala la UI al cambiar la ventana (UI_ADAPTABLE)
    tipografia.aplicar()
    preparar_fuente()
    if ajustes_jugador.AJUSTES:
        daltonismo.instalar(ajustes_jugador.obtener())    # filtro de daltonismo según lo guardado, y en vivo

    gestor = GestorEscenas()
    semilla = leer_semilla()
    registrar_escenas(gestor, construir_mundo_3d(semilla=semilla), duracion_transicion, duracion_cinematica,
                      semilla=semilla)
    audio_enganches.instalar(gestor)       # AUDIO = False (frontend/audio.py) o ALCALDE_SIN_AUDIO=1 lo dejan mudo
    gestor.cambiar_a(INICIO)
    rendimiento.instalar()                 # silencia en el bucle de Ursina las entidades pasivas (frontend/rendimiento.py)
    telemetria.instalar()                  # F3: FPS y uso de CPU/RAM/GPU (frontend/telemetria.py)
    return aplicacion, gestor


if __name__ == "__main__":
    gpu_dedicada.asegurar()                # portátiles con dos GPU: pide a Windows la dedicada (frontend/gpu_dedicada.py)
    aplicacion, _ = crear_aplicacion()
    aplicacion.run()
