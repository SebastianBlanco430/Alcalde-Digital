# Controlador del jugador activo en el mundo (Controlador del MVC): lee el teclado,
# llama a las funciones puras de backend/logica/navegacion.py (modelo) y mueve el
# avatar (vista). Es hijo de EscenaMundo, así que Ursina NO le entrega update() ni
# input() mientras la escena está desactivada (p. ej. durante el minijuego).
#
# Teclas: WASD / flechas = mover, Tab = teléfono, E = interactuar (solo si el
# modelo dice puede_interactuar(), es decir EN_RADIO del destino).
#
# El modelo manda: la posición vive en Jugador.x/z (FlujoPartida.actualizar_posicion);
# el avatar solo se coloca a partir de ella.
#
# Yaw de la cámara: se pasa tal cual el rotation_y de la cámara isométrica
# (geometria_mundo.yaw_de_camara() = -45), SIN invertir el signo. Con la fórmula del
# backend, dx = h·cosθ + v·sinθ, dz = -h·sinθ + v·cosθ, eso da W = arriba en la
# pantalla y D = derecha (lo fija tests/test_mundo_ventana.py con la cámara real).

from ursina import Entity, held_keys, time

from backend.logica import navegacion
from backend.logica.misiones import COMPLETADA, EN_MINIJUEGO
from frontend import geometria_mundo

VELOCIDAD = 7.0     # unidades de mundo por segundo
DT_MAXIMO = 0.05    # tope por frame: un tirón no atraviesa paredes ni salta la cámara


class ControladorJugador(Entity):

    # escena: EscenaMundo (da `flujo` y `avatar_de(jugador)`). mapa: MapaCiudad.
    # al_interactuar: callback sin argumentos que dispara la tecla E.
    def __init__(self, escena, mapa, al_interactuar, velocidad=VELOCIDAD):
        super().__init__(parent=escena)
        self._escena = escena
        self._mapa = mapa
        self._al_interactuar = al_interactuar
        self.velocidad = velocidad

    # Hay partida en curso: flujo creado y alguna misión por jugar.
    def activo(self):
        flujo = self._escena.flujo
        return flujo is not None and not flujo.partida_terminada()

    def update(self):
        h, v = geometria_mundo.ejes_de_teclas(held_keys)
        self.avanzar(h, v, time.dt)

    # Un paso de movimiento con la entrada (h, v) durante dt segundos. Devuelve la
    # posición (x, z) del jugador activo, o None si el controlador está inactivo.
    def avanzar(self, h, v, dt):
        if not self.activo():
            return None
        flujo = self._escena.flujo
        if flujo.estado_mision() in (EN_MINIJUEGO, COMPLETADA):
            return None                    # fundido hacia/desde el minijuego: nadie se mueve
        jugador = flujo.jugador_activo()
        if jugador.telefono.bloquea_movimiento():
            h = v = 0                      # con el teléfono abierto no se camina
        dt = min(dt, DT_MAXIMO)
        dx, dz = navegacion.mover_isometrico(
            h, v, geometria_mundo.yaw_de_camara(), self.velocidad, dt)
        x, z = jugador.x, jugador.z
        if dx != 0 or dz != 0:
            x, z = navegacion.mover_con_colisiones(self._mapa, x, z, dx, dz)
        # Se notifica siempre (también quieto): mantiene al día EN_RUTA / EN_RADIO.
        flujo.actualizar_posicion(x, z)

        avatar = self._escena.avatar_de(jugador)
        if avatar is not None:
            avatar.colocar(x, z)
            if dx != 0 or dz != 0:
                avatar.mirar_hacia(geometria_mundo.rumbo_de(dx, dz))
        return (x, z)

    def input(self, key):
        if not self.activo():
            return
        flujo = self._escena.flujo
        jugador = flujo.jugador_activo()
        # Durante el fundido hacia/desde el minijuego nadie interactúa (igual que el movimiento).
        if flujo.estado_mision() in (EN_MINIJUEGO, COMPLETADA):
            return
        if key == "tab":
            jugador.telefono.alternar()
        elif key == "e":
            # Con el teléfono abierto no se interactúa (tampoco se camina).
            if flujo.puede_interactuar() and not jugador.telefono.bloquea_movimiento():
                self._al_interactuar()
