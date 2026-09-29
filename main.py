# Punto de entrada de Alcalde Digital (Ursina).
# Importar este módulo no abre ventana: todo se construye en crear_aplicacion().

from pathlib import Path

from panda3d.core import WindowProperties
from ursina import Ursina, application, window

from frontend import estilo
from frontend.componentes import preparar_fuente, rgb
from frontend.escenas.escena_inicio import EscenaInicio
from frontend.escenas.escena_juego import EscenaJuego
from frontend.gestor_escenas import GestorEscenas

# Jugador de prueba: aún no existe la selección real de jugador.
JUGADOR_PRUEBA = {"nombre": "Jugador 1", "rol": "ciudadano"}

# Ventana 16:9 (camera.ui: x en [-0.888, 0.888], y en [-0.5, 0.5]).
TAMANO_VENTANA = (1280, 720)


def fijar_tamano_ventana():
    # Impide redimensionar/maximizar: el layout está calculado para 16:9 y Ursina
    # solo reubica en x los hijos directos de camera.ui al cambiar el aspecto.
    propiedades = WindowProperties()
    propiedades.set_fixed_size(True)
    application.base.win.request_properties(propiedades)


def crear_aplicacion():
    # Retorna (app, gestor) sin iniciar el loop: quien llama hace app.run().
    # development_mode=False oculta el panel de desarrollo, pero en Ursina 8.3.0
    # activaría fullscreen por defecto, así que se pide ventana explícita.
    app = Ursina(title="Alcalde Digital", borderless=False, fullscreen=False,
                 development_mode=False, size=TAMANO_VENTANA)
    application.asset_folder = Path(__file__).resolve().parent / "assets"
    window.color = rgb(estilo.COLOR_FONDO)
    fijar_tamano_ventana()
    preparar_fuente()

    gestor = GestorEscenas()
    gestor.registrar("inicio", EscenaInicio(
        al_comenzar=lambda: gestor.cambiar_a("juego", jugador=JUGADOR_PRUEBA)))
    gestor.registrar("juego", EscenaJuego())
    gestor.cambiar_a("inicio")
    return app, gestor


if __name__ == "__main__":
    app, _ = crear_aplicacion()
    app.run()
