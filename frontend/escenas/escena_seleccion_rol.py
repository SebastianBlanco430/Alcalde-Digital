# Escena de selección de jugadores y roles (Ursina), hot-seat en una sola PC.
# Paso 1: cuántos jugadores (1 a 4). Paso 2: cada jugador elige un rol exclusivo
# (los ya tomados se ven deshabilitados). Al terminar aparece "Comenzar".
# No conoce al gestor: recibe `fabrica_sesion` (crea una SesionJuego nueva en cada
# al_entrar) y el callback `al_comenzar(sesion)`. La lógica de roles vive en
# backend/logica/sesion.py; aquí solo se llama y se dibuja.

from ursina import Entity, Text

from backend.logica.roles import ORDEN_ROLES, ROLES
from backend.logica.sesion import MAX_JUGADORES
from frontend import estilo
from frontend.componentes import BotonAccion, a_unidades, escala_fuente, rgb
from frontend.escenas.escena_base import Escena


# Pantalla de elección de cantidad de jugadores y de rol de cada uno.
class EscenaSeleccionRol(Escena):

    Y_INSTRUCCION = 0.34
    Y_CANTIDAD = 0.05
    ANCHO_BOTON_CANTIDAD = 0.30
    SEPARACION_CANTIDAD = 0.36

    Y_PRIMER_ROL = 0.20
    SEPARACION_ROLES = 0.13
    ANCHO_BOTON_ROL = 0.50
    ALTO_BOTON_ROL = a_unidades(56)
    X_BOTON_ROL = -0.38
    X_MUESTRA_ROL = -0.70
    X_DESCRIPCION = -0.10

    Y_RESUMEN = -0.32
    Y_COMENZAR = -0.44

    def __init__(self, fabrica_sesion, al_comenzar, **opciones):
        super().__init__(**opciones)
        self._fabrica_sesion = fabrica_sesion
        self._al_comenzar = al_comenzar
        self.sesion = None
        self.total_jugadores = 0

        self.texto_instruccion = Text(
            "", parent=self, origin=(0, 0), position=(0, self.Y_INSTRUCCION),
            scale=escala_fuente(30), color=rgb(estilo.COLOR_TEXTO),
        )
        self.texto_resumen = Text(
            "", parent=self, origin=(0, 0), position=(0, self.Y_RESUMEN),
            scale=escala_fuente(18), color=rgb(estilo.COLOR_TEXTO_TENUE),
        )

        # Paso 1: cantidad de jugadores.
        self.grupo_cantidad = Entity(parent=self)
        self.botones_cantidad = {}
        for n in range(1, MAX_JUGADORES + 1):
            x = (n - 2.5) * self.SEPARACION_CANTIDAD
            etiqueta = "1 jugador" if n == 1 else f"{n} jugadores"
            self.botones_cantidad[n] = BotonAccion(
                etiqueta, al_clic=lambda n=n: self.elegir_cantidad(n),
                ancho=self.ANCHO_BOTON_CANTIDAD, parent=self.grupo_cantidad,
                position=(x, self.Y_CANTIDAD),
            )

        # Paso 2: un botón por rol, con una muestra de su color y su descripción.
        self.grupo_roles = Entity(parent=self)
        self.botones_rol = {}
        self.muestras_rol = {}
        for indice, rol in enumerate(ORDEN_ROLES):
            info = ROLES[rol]
            y = self.Y_PRIMER_ROL - indice * self.SEPARACION_ROLES
            self.muestras_rol[rol] = Entity(
                parent=self.grupo_roles, model="quad", color=rgb(info.color),
                scale=(0.04, self.ALTO_BOTON_ROL), position=(self.X_MUESTRA_ROL, y),
            )
            self.botones_rol[rol] = BotonAccion(
                info.nombre, al_clic=lambda rol=rol: self.elegir_rol(rol),
                ancho=self.ANCHO_BOTON_ROL, alto=self.ALTO_BOTON_ROL,
                parent=self.grupo_roles, position=(self.X_BOTON_ROL, y),
            )
            Text(
                info.descripcion, parent=self.grupo_roles, origin=(-0.5, 0),
                position=(self.X_DESCRIPCION, y), scale=escala_fuente(18),
                color=rgb(estilo.COLOR_TEXTO_TENUE),
            )

        self.boton_comenzar = BotonAccion(
            "Comenzar", al_clic=self.comenzar, parent=self, position=(0, self.Y_COMENZAR),
        )
        self._reiniciar()

    # -- Ciclo de vida --

    # Cada vez que se entra se parte de una sesión nueva (y de cero jugadores).
    def al_entrar(self, **datos):
        self._reiniciar()

    def _reiniciar(self):
        self.sesion = self._fabrica_sesion() if self._fabrica_sesion else None
        self.total_jugadores = 0
        self.refrescar()

    # -- Pasos --

    # Paso 1: fija cuántos jugadores jugarán (1 a 4) y pasa a elegir roles.
    def elegir_cantidad(self, cantidad):
        if self.total_jugadores or cantidad not in self.botones_cantidad:
            return
        self.total_jugadores = cantidad
        self.refrescar()

    # Paso 2: el siguiente jugador toma `rol` (nombre automático "Jugador N").
    def elegir_rol(self, rol):
        if not self.total_jugadores or self.todos_eligieron():
            return
        if rol not in self.sesion.roles_disponibles():
            return
        numero = len(self.sesion.jugadores()) + 1
        self.sesion.agregar_jugador(f"Jugador {numero}", rol)
        self.refrescar()

    def todos_eligieron(self):
        return self.total_jugadores > 0 and len(self.sesion.jugadores()) >= self.total_jugadores

    def comenzar(self):
        if self.todos_eligieron():
            self._al_comenzar(self.sesion)

    # -- Vista --

    def refrescar(self):
        eligiendo_cantidad = self.total_jugadores == 0
        listo = self.todos_eligieron()
        self.grupo_cantidad.enabled = eligiendo_cantidad
        self.grupo_roles.enabled = not eligiendo_cantidad
        self.boton_comenzar.enabled = listo

        if eligiendo_cantidad:
            self.texto_instruccion.text = "¿Cuántos jugadores?"
        elif listo:
            self.texto_instruccion.text = "Todo listo: pulsa Comenzar"
        else:
            numero = len(self.sesion.jugadores()) + 1
            self.texto_instruccion.text = f"Jugador {numero}: elige tu rol"

        libres = self.sesion.roles_disponibles() if self.sesion else list(ORDEN_ROLES)
        for rol, boton in self.botones_rol.items():
            boton.fijar_habilitado(rol in libres and not listo)

        elegidos = self.sesion.jugadores() if self.sesion else []
        self.texto_resumen.text = "   ".join(
            f"{j.nombre}: {ROLES[j.rol].nombre}" for j in elegidos
        )
