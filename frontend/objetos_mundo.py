# Objetos 3D del mundo (Ursina): avatar de jugador y computador de la misión.
# Son Entity placeholder armadas con primitivas (cubo, esfera, rombo). Cuelgan de
# `scene` (a través de EscenaMundo). La posición real vive en el modelo
# (Jugador.x/z); aquí solo se dibuja.

import math

from ursina import Entity, Text, color, time
from ursina.shaders import basic_lighting_shader

from frontend import estilo, geometria_mundo
from frontend.componentes import rgb

COLOR_PIEL = color.rgb32(235, 200, 170)
COLOR_MARCADOR = color.rgb32(255, 220, 60)


# Entity del mundo con sombreado simple (las caras de un cubo se distinguen).
def pieza(**opciones):
    opciones.setdefault("shader", basic_lighting_shader)
    return Entity(**opciones)


# Etiqueta de texto que siempre mira a la cámara (billboard), centrada y sobre un
# fondo oscuro translúcido (se lee igual sobre edificios claros y oscuros).
def etiqueta(texto, **opciones):
    opciones.setdefault("scale", 18)
    opciones.setdefault("color", rgb(estilo.COLOR_TEXTO))
    texto_3d = Text(texto, billboard=True, origin=(0, 0), **opciones)
    texto_3d.create_background(padding=(0.03, 0.015), radius=0.3, color=color.rgba32(10, 12, 20, 170))
    return texto_3d


# Muñeco de un jugador: cuerpo del color de su rol, cabeza, visor que marca hacia
# dónde mira y etiqueta con el nombre. El activo se resalta con un aro amarillo,
# más tamaño y la etiqueta en amarillo.
class AvatarJugador(Entity):

    VELOCIDAD_GIRO = 12          # rapidez del suavizado del rumbo
    ESCALA_ACTIVO = 1.25

    def __init__(self, nombre, color_rol, **opciones):
        super().__init__(**opciones)
        self.nombre = nombre
        self.rumbo = 0.0         # rotation_y del cuerpo (grados)
        self.rumbo_objetivo = 0.0

        self.aro = pieza(parent=self, model="circle", rotation_x=90, y=0.12, scale=1.9,
                         color=COLOR_MARCADOR, enabled=False)
        # `cuerpo` es el pivote que gira hacia donde camina; la etiqueta no gira.
        self.cuerpo = Entity(parent=self)
        pieza(parent=self.cuerpo, model="cube", color=rgb(color_rol), position=(0, 0.55, 0),
              scale=(0.75, 1.1, 0.5))
        pieza(parent=self.cuerpo, model="sphere", color=COLOR_PIEL, position=(0, 1.4, 0), scale=0.6)
        self.visor = pieza(parent=self.cuerpo, model="cube", color=color.rgb32(30, 30, 40),
                           position=(0, 1.45, 0.26), scale=(0.42, 0.14, 0.12))
        self.etiqueta = etiqueta(nombre, parent=self, y=2.3, scale=16)
        self._activo = False

    def colocar(self, x, z):
        self.position = (x, 0, z)

    # Fija el rumbo al que debe girar el cuerpo (el giro es suave en update()).
    def mirar_hacia(self, rumbo):
        self.rumbo_objetivo = rumbo

    def girar(self, dt):
        self.rumbo = geometria_mundo.suavizar_angulo(
            self.rumbo, self.rumbo_objetivo, self.VELOCIDAD_GIRO, dt)
        self.cuerpo.rotation_y = self.rumbo

    def resaltar(self, activo):
        self._activo = activo
        self.aro.enabled = activo
        self.cuerpo.scale = self.ESCALA_ACTIVO if activo else 1
        self.etiqueta.color = COLOR_MARCADOR if activo else rgb(estilo.COLOR_TEXTO)
        self.etiqueta.y = 2.7 if activo else 2.3

    def esta_resaltado(self):
        return self._activo

    # El giro suave corre solo mientras la escena está activa (Ursina salta update()
    # de entidades con un ancestro desactivado).
    def update(self):
        self.girar(time.dt)


# Computador placeholder: escritorio, monitor con pantalla cian y un rombo amarillo
# que flota sobre él para distinguirlo desde lejos. Va en el centro de la plaza
# del destino de la misión.
class ComputadorMision(Entity):

    def __init__(self, **opciones):
        super().__init__(**opciones)
        pieza(parent=self, model="cube", color=color.rgb32(110, 90, 70), position=(0, 0.4, 0),
              scale=(1.7, 0.8, 1.0))
        pieza(parent=self, model="cube", color=color.rgb32(40, 42, 52), position=(0, 1.2, 0.1),
              scale=(1.1, 0.75, 0.1))
        pieza(parent=self, model="cube", color=color.rgb32(90, 220, 235), position=(0, 1.2, 0.04),
              scale=(0.95, 0.6, 0.05), shader=None)
        pieza(parent=self, model="cube", color=color.rgb32(70, 72, 84), position=(0, 0.85, -0.2),
              scale=(0.9, 0.06, 0.3))
        self.baliza = pieza(parent=self, model="diamond", color=COLOR_MARCADOR,
                            position=(0, 2.6, 0), scale=(0.6, 0.9, 0.6), shader=None)
        self._tiempo = 0.0

    # La baliza sube y baja y gira (solo con la escena activa).
    def update(self):
        self._tiempo += time.dt
        self.baliza.y = 2.6 + 0.15 * math.sin(self._tiempo * 3)
        self.baliza.rotation_y = self._tiempo * 90
