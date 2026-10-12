# Marco de monitor "Civitas" (Ursina, camera.ui) alrededor de la EscenaJuego cuando se juega
# DESDE un computador (tras la cinemática de sentarse). Es solo decoración: un bisel oscuro a
# pantalla completa por DETRÁS del juego, el recuadro de la pantalla, una barra superior
# "Civitas · <Rol> · <Lugar>" con tres botoncitos de ventana y un LED de encendido.
#
# EscenaJuego lo reduce a ESCALA_JUEGO y lo centra para que el contenido quepa dentro del
# marco (el panel de indicadores queda justo bajo la barra superior). Sin marco (el modo de
# siempre) la escena se ve exactamente igual que antes.

from ursina import Entity, Text, camera

from frontend import estilo
from frontend.componentes import escala_fuente, modelo_redondeado, rgb

ESCALA_JUEGO = 0.92              # tamaño del contenido de EscenaJuego dentro del marco
ALTO_BARRA = 0.044
Z_ATRAS = 0.8                    # más lejos de la cámara de camera.ui = detrás del juego
COLOR_BISEL = (14, 15, 22)
COLOR_BARRA = (30, 34, 56)
COLOR_LED = (80, 220, 110)


class MarcoPC(Entity):

    def __init__(self, **opciones):
        opciones.setdefault("parent", camera.ui)
        opciones.setdefault("enabled", False)
        super().__init__(**opciones)
        ancho = camera.aspect_ratio
        Entity(parent=self, model="quad", color=rgb(COLOR_BISEL), scale=(4, 4), z=Z_ATRAS)
        alto_pantalla = ESCALA_JUEGO + 0.02
        ancho_pantalla = ancho * ESCALA_JUEGO + 0.02
        Entity(parent=self, model=modelo_redondeado(ancho_pantalla, alto_pantalla, 12),
               scale=(ancho_pantalla, alto_pantalla), color=rgb(estilo.COLOR_FONDO), z=Z_ATRAS - 0.1)
        # Barra superior con el título y tres botones de ventana.
        y_barra = 0.5 - ALTO_BARRA / 2
        Entity(parent=self, model="quad", color=rgb(COLOR_BARRA), scale=(ancho, ALTO_BARRA),
               position=(0, y_barra), z=Z_ATRAS - 0.2)
        self.titulo = Text("", parent=self, origin=(-0.5, 0), position=(-ancho / 2 + 0.02, y_barra, Z_ATRAS - 0.3),
                           scale=escala_fuente(16), color=rgb(estilo.COLOR_TEXTO_TENUE))
        for i, tono in enumerate(((236, 96, 88), (240, 190, 70), (90, 200, 100))):
            Entity(parent=self, model="circle", color=rgb(tono), scale=0.014,
                   position=(ancho / 2 - 0.03 - i * 0.026, y_barra), z=Z_ATRAS - 0.3)
        # LED de encendido en el mentón del monitor.
        Entity(parent=self, model="circle", color=rgb(COLOR_LED), scale=0.01,
               position=(0, -0.5 + 0.018), z=Z_ATRAS - 0.2)

    # Texto de la barra: "Civitas · <Rol> · <Lugar>".
    def fijar(self, rol, lugar):
        partes = ["Civitas"] + [p for p in (rol, lugar) if p]
        self.titulo.text = " · ".join(partes).replace("<", "(").replace(">", ")")

    def mostrar(self, rol, lugar):
        self.fijar(rol, lugar)
        self.enabled = True

    def ocultar(self):
        self.enabled = False
