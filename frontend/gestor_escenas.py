# Gestor de escenas: registra escenas por nombre y mantiene una sola activa.
# Es ajeno a Ursina (duck typing): una escena es cualquier objeto con `enabled` y,
# opcionalmente, los hooks `al_entrar(**datos)` y `al_salir()`. Así se prueba con
# escenas falsas y las escenas no necesitan conocer al gestor.


# Máquina de estados simple: {nombre: escena} + una escena actual.
class GestorEscenas:

    def __init__(self):
        self._escenas = {}
        self._nombre_actual = None

    # Nombre de la escena activa, o None si aún no hay ninguna.
    def nombre_actual(self):
        return self._nombre_actual

    def escena_actual(self):
        if self._nombre_actual is None:
            return None
        return self._escenas[self._nombre_actual]

    # Registra la escena desactivada; lanza ValueError si el nombre ya existe.
    def registrar(self, nombre, escena):
        if nombre in self._escenas:
            raise ValueError(f"Ya existe una escena registrada con el nombre {nombre!r}.")
        escena.enabled = False
        self._escenas[nombre] = escena

    # Orden: al_salir() de la vieja -> vieja.enabled = False -> nueva.enabled = True
    # -> al_entrar(**datos) de la nueva. Cambiar a la escena activa la reinicia.
    # Lanza ValueError, sin alterar nada, si `nombre` no está registrada.
    def cambiar_a(self, nombre, **datos):
        if nombre not in self._escenas:
            raise ValueError(
                f"Escena no registrada: {nombre!r}. Registradas: {sorted(self._escenas)}."
            )

        actual = self.escena_actual()
        if actual is not None:
            gancho_salir = getattr(actual, "al_salir", None)
            if callable(gancho_salir):
                gancho_salir()
            actual.enabled = False

        nueva = self._escenas[nombre]
        self._nombre_actual = nombre
        nueva.enabled = True
        gancho_entrar = getattr(nueva, "al_entrar", None)
        if callable(gancho_entrar):
            gancho_entrar(**datos)
