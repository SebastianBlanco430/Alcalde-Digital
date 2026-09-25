"""
Escena base: contenedor de Ursina (una `Entity`) que agrupa todo lo visible de
una pantalla del juego (menú, partida, resultado...).

Una escena es solo un contenedor con dos hooks vacíos; NO contiene lógica de
partida (esa vive en `backend/logica/`). Quien activa/desactiva escenas es el
`GestorEscenas` (frontend/gestor_escenas.py), que las maneja por duck typing:
pone `enabled` y llama a `al_entrar(**datos)` / `al_salir()`.

Al desactivar la escena (`enabled = False`) Ursina la oculta junto con todos
sus hijos, que además dejan de recibir update/input y de ser detectados por el
ratón; por eso las vistas cuelgan sus elementos de `self`.
"""

from ursina import Entity, camera


class Escena(Entity):
    """Contenedor de una pantalla. Nace desactivado.

    Args:
        parent: padre de la escena. Por defecto `camera.ui` (interfaz 2D, con
            coordenadas normalizadas: y en [-0.5, 0.5]); para mundos 2.5D
            futuros se puede pasar `scene`.
        **kwargs: se reenvían a `Entity` (salvo `enabled`, que siempre es False
            al nacer: solo el gestor activa escenas).
    """

    def __init__(self, parent=None, **kwargs):
        # camera.ui se resuelve aquí, no como valor por defecto, porque solo
        # existe una vez creada la aplicación Ursina.
        if parent is None:
            parent = camera.ui
        kwargs.pop("enabled", None)
        super().__init__(parent=parent, enabled=False, **kwargs)

    def al_entrar(self, **datos):
        """Hook: el gestor lo llama al activar la escena, con los `datos` de
        `cambiar_a(nombre, **datos)`. Las subclases lo sobrescriben."""

    def al_salir(self):
        """Hook: el gestor lo llama justo antes de desactivar la escena."""
