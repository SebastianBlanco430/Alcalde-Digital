"""
Punto de entrada de Alcalde Digital (Ursina).

Importar este modulo NO abre ninguna ventana: toda la construccion vive en
`crear_aplicacion()`. Reemplaza al punto de entrada pygame original, retirado
en el Modulo 5 de la migracion a Ursina.
"""

from pathlib import Path

from panda3d.core import WindowProperties
from ursina import Ursina, application, window

from frontend import estilo
from frontend.componentes import preparar_fuente, rgb
from frontend.escenas.escena_inicio import EscenaInicio
from frontend.escenas.escena_juego import EscenaJuego
from frontend.gestor_escenas import GestorEscenas

# Jugador de prueba: la seleccion real de jugador todavia no existe.
JUGADOR_PRUEBA = {"nombre": "Jugador 1", "rol": "ciudadano"}

# Ventana 16:9 de tamano explicito y reproducible (el layout de las escenas esta
# calculado para camera.ui a 16:9: x en [-0.888, 0.888], y en [-0.5, 0.5]).
TAMANO_VENTANA = (1280, 720)


def _fijar_tamano_ventana():
    """Impide que el usuario redimensione o maximice la ventana.

    Ursina, al cambiar el aspecto, solo reubica en x las entidades hijas directas
    de camera.ui (ursina/window.py: update_aspect_ratio), no su contenido; el
    layout de las escenas esta calculado para 16:9, asi que redimensionar lo
    deformaria. `forced_aspect_ratio` solo actua al fijar `window.size` por
    codigo, no frena al usuario; `fixed_size` de Panda3D si (quita el borde de
    redimension y el boton de maximizar).
    """
    propiedades = WindowProperties()
    propiedades.set_fixed_size(True)
    application.base.win.request_properties(propiedades)


def crear_aplicacion():
    """Crea la aplicacion Ursina, registra las escenas y activa "inicio".

    Retorna (app, gestor). No inicia el loop: quien llama hace `app.run()`
    (asi los scripts de prueba pueden programar pasos antes de arrancarlo).
    """
    # development_mode=False oculta el panel de desarrollo (contador de FPS, boton X
    # rojo, contadores de entidades, engranaje); pero en Ursina 8.3.0 tambien
    # activaria fullscreen por defecto, asi que se pide ventana explicita.
    app = Ursina(title="Alcalde Digital", borderless=False, fullscreen=False,
                 development_mode=False, size=TAMANO_VENTANA)
    application.asset_folder = Path(__file__).resolve().parent / "assets"
    window.color = rgb(estilo.COLOR_FONDO)
    _fijar_tamano_ventana()
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
