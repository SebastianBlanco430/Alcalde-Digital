# Controlador del jugador activo en el mundo (Controlador del MVC): lee el teclado,
# llama a las funciones puras de backend/logica/navegacion.py (modelo) y mueve el
# avatar (vista). Es hijo de EscenaMundo, así que Ursina NO le entrega update() ni
# input() mientras la escena está desactivada (p. ej. durante el minijuego).
#
# Teclas: WASD / flechas = mover (Shift = correr, si se configuró), Tab = teléfono, E =
# interactuar (solo si el modelo dice puede_interactuar(), es decir EN_RADIO del destino),
# Escape = pausa (solo si la escena la ofrece: `alternar_pausa()`). Espacio/Enter saltan las
# cinemáticas, pero eso es global (main.py) porque hay que poder saltar también en el interior.
#
# Mundo 3D: `obtener_yaw` devuelve el yaw ACTUAL de la cámara orbital y `velocidad_correr`
# activa Shift. La escena puede congelar los controles
# (`controles_bloqueados()`: pausa, cinemática). Tras las colisiones, la velocidad REAL
# (metros recorridos / dt) se le pasa al personaje (`fijar_velocidad`) para animar el
# caminar/correr/reposo.
#
# El modelo manda: la posición vive en Jugador.x/z (FlujoPartida.actualizar_posicion);
# el avatar solo se coloca a partir de ella.
#
# Yaw de la cámara: se pasa tal cual (sin invertir el signo). Con la fórmula del backend,
# dx = h·cosθ + v·sinθ, dz = -h·sinθ + v·cosθ, eso da W = hacia donde mira la cámara y
# D = su derecha (lo fija scripts/prueba_mundo.py con la cámara real y 5 yaw distintos).

from ursina import Entity, held_keys, time

from backend.logica import navegacion
from backend.logica.misiones import COMPLETADA, EN_MINIJUEGO
from frontend import geometria_mundo

VELOCIDAD = 7.0     # unidades de mundo por segundo
DT_MAXIMO = 0.05    # tope por frame: un tirón no atraviesa paredes ni salta la cámara


class ControladorJugador(Entity):

    # escena: EscenaMundo (da `flujo` y `avatar_de(jugador)`). mapa: MapaCiudad.
    # al_interactuar: callback sin argumentos que dispara la tecla E.
    def __init__(self, escena, mapa, al_interactuar, velocidad=VELOCIDAD, obtener_yaw=lambda: 0.0,
                 velocidad_correr=None):
        super().__init__(parent=escena)
        self._escena = escena
        self._mapa = mapa
        self._al_interactuar = al_interactuar
        self.velocidad = velocidad
        self.velocidad_correr = velocidad_correr
        self._obtener_yaw = obtener_yaw

    # Hay partida en curso: flujo creado y alguna misión por jugar.
    def activo(self):
        flujo = self._escena.flujo
        return flujo is not None and not flujo.partida_terminada()

    # La escena puede congelar los controles (menú de pausa, cinemática en curso).
    def _congelado(self):
        pregunta = getattr(self._escena, "controles_bloqueados", None)
        return bool(pregunta()) if callable(pregunta) else False

    def update(self):
        h, v = geometria_mundo.ejes_de_teclas(held_keys)
        correr = bool(held_keys["left shift"] or held_keys["right shift"])
        self.avanzar(h, v, time.dt, correr)

    # Un paso de movimiento con la entrada (h, v) durante dt segundos. Devuelve la
    # posición (x, z) del jugador activo, o None si el controlador está inactivo.
    def avanzar(self, h, v, dt, correr=False):
        if not self.activo():
            return None
        flujo = self._escena.flujo
        jugador = flujo.jugador_activo()
        avatar = self._escena.avatar_de(jugador)
        if flujo.estado_mision() in (EN_MINIJUEGO, COMPLETADA) or self._congelado():
            self._informar_velocidad(avatar, 0.0)
            return None                    # fundido, pausa o cinemática: nadie se mueve
        if jugador.telefono.bloquea_movimiento():
            h = v = 0                      # con el teléfono abierto no se camina
        dt = min(dt, DT_MAXIMO)
        velocidad = self.velocidad_correr if (correr and self.velocidad_correr) else self.velocidad
        dx, dz = navegacion.mover_isometrico(h, v, self._obtener_yaw(), velocidad, dt)
        x0, z0 = jugador.x, jugador.z
        x, z = x0, z0
        if dx != 0 or dz != 0:
            x, z = navegacion.mover_con_colisiones(self._mapa, x, z, dx, dz)
        # Se notifica siempre (también quieto): mantiene al día EN_RUTA / EN_RADIO.
        flujo.actualizar_posicion(x, z)

        if avatar is not None:
            avatar.colocar(x, z)
            if dx != 0 or dz != 0:
                avatar.mirar_hacia(geometria_mundo.rumbo_de(dx, dz))
            real = ((x - x0) ** 2 + (z - z0) ** 2) ** 0.5 / dt if dt > 0 else 0.0
            self._informar_velocidad(avatar, real)
        return (x, z)

    @staticmethod
    def _informar_velocidad(avatar, velocidad):
        informar = getattr(avatar, "fijar_velocidad", None)
        if callable(informar):
            informar(velocidad)

    def input(self, key):
        if not self.activo():
            return
        flujo = self._escena.flujo
        jugador = flujo.jugador_activo()
        # Pausa y saltar cinemática las ofrece la escena 3D .
        if key == "escape" and hasattr(self._escena, "alternar_pausa"):
            self._escena.alternar_pausa()
            return
        # Durante el fundido hacia/desde el minijuego nadie interactúa (igual que el movimiento).
        if flujo.estado_mision() in (EN_MINIJUEGO, COMPLETADA) or self._congelado():
            return
        if key == "tab":
            jugador.telefono.alternar()
        elif key == "e":
            # Con el teléfono abierto no se interactúa (tampoco se camina).
            if flujo.puede_interactuar() and not jugador.telefono.bloquea_movimiento():
                self._al_interactuar()
