# Escena base: contenedor de Ursina (una Entity) que agrupa todo lo visible de
# una pantalla. No contiene lógica de partida (vive en backend/logica/).
# El GestorEscenas activa/desactiva escenas con `enabled` y llama a los hooks
# `al_entrar(**datos)` / `al_salir()`. Al desactivarla, Ursina oculta la escena y
# sus hijos, por eso las vistas cuelgan sus elementos de `self`.

from ursina import Entity, camera


# Contenedor de una pantalla; nace desactivado (solo el gestor activa escenas).
# `parent` por defecto es camera.ui; para mundos 2.5D se puede pasar `scene`.
class Escena(Entity):

    def __init__(self, parent=None, **opciones):
        # camera.ui se resuelve aquí porque solo existe tras crear la aplicación
        if parent is None:
            parent = camera.ui
        opciones.pop("enabled", None)
        super().__init__(parent=parent, enabled=False, **opciones)

    # Hook: el gestor lo llama al activar la escena con los `datos` de cambiar_a().
    def al_entrar(self, **datos):
        pass

    # Hook: el gestor lo llama justo antes de desactivar la escena.
    def al_salir(self):
        pass
