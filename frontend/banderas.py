# Banderas en el techo de los edificios jugables: un mástil y una tela de franjas verticales que
# ondea. Sirven de referencia a distancia (se ven por encima de las casas de la favela) y la del
# destino de la misión se agranda y lleva un borde amarillo (`destacar`).
#
# Rendimiento: 1 raíz + mástil + 6 franjas (+ borde) por bandera, ~7 banderas. Sin update(): las anima
# Ciudad3D.update() llamando a `animar(dt)`. Las sombras están horneadas, así que mástil y tela se
# ocultan a la cámara de la luz (`hide(MASCARA_LUZ)`): lo que se mueve no puede estar en ese mapa.

import math

from ursina import Entity

from frontend.azar_fijo import azar_de
from frontend.banderas_calculos import colores_banderas, posiciones_banderas, rumbo_bandera
from frontend.componentes import rgb
from frontend.marcadores_mundo import COLOR_BALIZA
from frontend.piezas import MASCARA_LUZ, pieza, silenciar

# Alto del mástil. El techo del edificio queda por debajo de muchas casas de la ladera, así que un
# mástil corto deja la bandera tapada: con 3 m ya quedaba bajo las vecinas. Con 4 m se ve desde la
# mayoría de ángulos sin que parezca desproporcionado; 8-12 m la pondrían siempre por encima de las
# casas pero el mástil se vería como un poste enorme. Se puede subir ALTO_MASTIL si hace falta.
ALTO_MASTIL = 4.0         # m
GROSOR_MASTIL = 0.08      # m
COLOR_MASTIL = (60, 62, 70)
ANCHO_TELA, ALTO_TELA = 1.4, 0.9      # m
GROSOR_TELA = 0.03        # m
FRANJAS = 6               # franjas verticales de la tela (cantidad, sin unidad)
AMPLITUD_PUNTA = 25.0     # grados de giro en la punta de la tela (0 en el mástil)
VELOCIDAD_ONDEO = 3.0     # rad/s
DESFASE_FRANJA = 0.7      # rad entre franjas contiguas: la onda viaja hacia la punta
ESCALA_DESTACADA = 1.4    # veces el tamaño normal (factor de escala, sin unidad)
RAPIDEZ_DESTACADA = 1.6   # veces más rápido que el ondeo normal
MARGEN_BORDE = 0.07       # m que el borde amarillo sobresale de la tela por cada lado


# Amplitud (grados) de la franja k: crece linealmente de ~0 junto al mástil a AMPLITUD_PUNTA en la punta.
def amplitud_franja(k, franjas=FRANJAS):
    return AMPLITUD_PUNTA * (k + 1) / franjas


# Giro (grados) de la franja k en la fase dada: A_k * sin(fase + k * 0.7).
def giro_franja(k, fase, franjas=FRANJAS):
    return amplitud_franja(k, franjas) * math.sin(fase + k * DESFASE_FRANJA)


class BanderaTecho(Entity):

    # `posicion` (x, y, z) es la base del mástil; `color_tela` en RGB 0-255; `rumbo` hacia donde mira.
    def __init__(self, posicion, color_tela, rumbo=0.0, **opciones):
        super().__init__(position=posicion, rotation_y=rumbo, **opciones)
        self._fase = azar_de(posicion[0], posicion[2]) * math.tau     # cada bandera arranca en otro punto
        self._rapidez = 1.0
        self.destacada = False
        self.mastil = pieza(parent=self, model="cube", color=rgb(COLOR_MASTIL),
                            position=(0, ALTO_MASTIL / 2, 0), scale=(GROSOR_MASTIL, ALTO_MASTIL, GROSOR_MASTIL))
        ancho = ANCHO_TELA / FRANJAS
        y_tela = ALTO_MASTIL - ALTO_TELA / 2 - 0.1
        self.franjas = [
            pieza(parent=self, model="cube", color=rgb(color_tela),
                  position=(GROSOR_MASTIL / 2 + ancho * (k + 0.5), y_tela, 0), scale=(ancho, ALTO_TELA, GROSOR_TELA))
            for k in range(FRANJAS)]
        # Borde amarillo: una placa un poco mayor detrás de la tela, sin sombreado; oculta hasta destacar().
        self.borde = pieza(parent=self, model="cube", color=rgb(COLOR_BALIZA), shader=None, enabled=False,
                           position=(GROSOR_MASTIL / 2 + ANCHO_TELA / 2, y_tela, GROSOR_TELA),
                           scale=(ANCHO_TELA + 2 * MARGEN_BORDE, ALTO_TELA + 2 * MARGEN_BORDE, GROSOR_TELA))
        self.mastil.hide(MASCARA_LUZ)
        for pieza_ in self.franjas + [self.borde]:
            pieza_.hide(MASCARA_LUZ)
        silenciar(self)                      # ninguna tiene update(): la anima Ciudad3D
        self.animar(0)

    # Ondea `dt` segundos: cada franja gira sobre su eje vertical con fase propia. Rendimiento: las franjas solo
    # giran en y, así que se usa setH de Panda (H = -rotation_y en Ursina) en vez de la propiedad rotation_y,
    # que relee la rotación entera y arma dos Vec3 por llamada (42 por frame con 7 banderas).
    def animar(self, dt):
        self._fase += dt * VELOCIDAD_ONDEO * self._rapidez
        for k, franja in enumerate(self.franjas):
            franja.setH(-giro_franja(k, self._fase))

    # La bandera del destino de la misión: 1.4x más grande, ondea 1.6x más rápido y lleva borde amarillo.
    def destacar(self, activo):
        self.destacada = bool(activo)
        self.scale = ESCALA_DESTACADA if activo else 1.0
        self._rapidez = RAPIDEZ_DESTACADA if activo else 1.0
        self.borde.enabled = self.destacada


# {lugar: BanderaTecho} para los edificios dados (`padre` = Ciudad3D). Llamar después del bucle de silenciar().
def crear_banderas(edificios, padre):
    posiciones = posiciones_banderas(edificios)
    colores = colores_banderas(edificios)
    return {e.lugar: BanderaTecho(posiciones[e.lugar], colores[e.lugar], rumbo_bandera(e), parent=padre)
            for e in edificios}
