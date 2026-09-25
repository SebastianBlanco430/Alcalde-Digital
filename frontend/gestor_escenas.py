"""
Gestor de escenas: registra escenas por nombre y garantiza que solo UNA esté
activa a la vez.

Es deliberadamente ajeno a Ursina (duck typing): una "escena" es cualquier
objeto con el atributo `enabled` y, opcionalmente, los hooks
`al_entrar(**datos)` y `al_salir()`. Así se prueba con escenas falsas, sin
abrir ventana, y las escenas no necesitan conocer al gestor (reciben
callbacks, no una referencia a él).
"""


class GestorEscenas:
    """Máquina de estados simple: {nombre: escena} + una escena actual."""

    def __init__(self):
        self._escenas = {}
        self._nombre_actual = None

    @property
    def nombre_actual(self):
        """Nombre de la escena activa, o None si todavía no se ha activado ninguna."""
        return self._nombre_actual

    @property
    def escena_actual(self):
        """Objeto de la escena activa, o None."""
        if self._nombre_actual is None:
            return None
        return self._escenas[self._nombre_actual]

    def registrar(self, nombre, escena):
        """Registra `escena` bajo `nombre` y la deja desactivada.

        Lanza ValueError si el nombre ya está registrado.
        """
        if nombre in self._escenas:
            raise ValueError(f"Ya existe una escena registrada con el nombre {nombre!r}.")
        escena.enabled = False
        self._escenas[nombre] = escena

    def cambiar_a(self, nombre, **datos):
        """Activa la escena `nombre`, desactivando antes la actual.

        Orden: al_salir() de la vieja (si existe) -> vieja.enabled = False ->
        nueva.enabled = True -> al_entrar(**datos) de la nueva (si existe).
        Cambiar a la escena ya activa la reinicia (sale y vuelve a entrar).
        Lanza ValueError, sin alterar nada, si `nombre` no está registrada.
        """
        if nombre not in self._escenas:
            raise ValueError(
                f"Escena no registrada: {nombre!r}. Registradas: {sorted(self._escenas)}."
            )

        actual = self.escena_actual
        if actual is not None:
            hook_salir = getattr(actual, "al_salir", None)
            if callable(hook_salir):
                hook_salir()
            actual.enabled = False

        nueva = self._escenas[nombre]
        self._nombre_actual = nombre
        nueva.enabled = True
        hook_entrar = getattr(nueva, "al_entrar", None)
        if callable(hook_entrar):
            hook_entrar(**datos)
