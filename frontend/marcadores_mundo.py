# Marcadores del mundo 3D (Ursina): la baliza amarilla sobre la puerta del destino de la
# misión y la ruta del GPS dibujada en el piso hasta esa puerta. Solo vista: los puntos de
# la ruta salen de backend/logica/navegacion.ruta_gps_hasta_puerta.

import math

from ursina import Entity, color, time

from frontend import geometria_mundo
from frontend.componentes import rgb
from frontend.piezas import pieza

COLOR_RUTA = (70, 220, 255)
COLOR_BALIZA = (255, 220, 60)
Y_RUTA = 0.24             # por encima de aceras (0.20) y plazas (0.14)
ANCHO_RUTA = 0.7
PASO_RUTA = 2.0           # m entre puntos de la ruta (sigue el relieve del terreno)


# Rombo amarillo que flota y gira sobre la puerta, más un rayo de luz tenue que se ve de lejos.
class Baliza(Entity):

    def __init__(self, **opciones):
        super().__init__(**opciones)
        self.rombo = pieza(parent=self, model="diamond", color=rgb(COLOR_BALIZA), scale=(0.7, 1.1, 0.7),
                           shader=None)
        self.rayo = pieza(parent=self, model="cube", color=color.rgba32(255, 220, 60, 70),
                          scale=(0.35, 60, 0.35), y=30, shader=None)
        self.altura = 5.0
        self._tiempo = 0.0

    # Sobre (x, z), `altura` m por encima del suelo; `base` es la altura del terreno en (x, z).
    def colocar(self, x, z, altura=5.0, base=0.0):
        self.altura = altura
        self.position = (x, base, z)
        self.rombo.y = altura

    def update(self):
        self._tiempo += time.dt
        self.rombo.y = self.altura + 0.2 * math.sin(self._tiempo * 3)
        self.rombo.rotation_y = self._tiempo * 90


# Línea del GPS en el piso: cubos planos entre puntos consecutivos y un disco en cada junta.
class RutaPiso(Entity):

    # `altura_en(x, z)`: callable de la altura del suelo (None = plano).
    def __init__(self, altura_en=None, **opciones):
        super().__init__(**opciones)
        self._altura_en = altura_en
        self.segmentos = []
        self.juntas = []
        self._firma = None

    # `puntos`: [(x, z)] desde el jugador hasta la puerta ([] = sin ruta). Cada tramo se parte
    # cada PASO_RUTA m y se inclina para seguir el terreno.
    def actualizar(self, puntos):
        firma = tuple((round(x, 2), round(z, 2)) for x, z in puntos)
        if firma == self._firma:
            return
        self._firma = firma
        tono = rgb(COLOR_RUTA)
        trazo = self._subdividir(puntos)
        pares = list(zip(trazo, trazo[1:]))
        while len(self.segmentos) < len(pares):
            self.segmentos.append(pieza(parent=self, model="cube", color=tono, shader=None))
        while len(self.juntas) < len(trazo):
            self.juntas.append(pieza(parent=self, model="circle", rotation_x=90, color=tono, shader=None,
                                     scale=ANCHO_RUTA * 1.4))
        for cubo, (p0, p1) in zip(self.segmentos, pares):
            dx, dz, dy = p1[0] - p0[0], p1[1] - p0[1], p1[2] - p0[2]
            horizontal = math.hypot(dx, dz)
            cubo.position = ((p0[0] + p1[0]) / 2, (p0[2] + p1[2]) / 2, (p0[1] + p1[1]) / 2)
            cubo.scale = (ANCHO_RUTA, 0.02, max(math.hypot(horizontal, dy), 0.01))
            cubo.rotation = (-math.degrees(math.atan2(dy, horizontal)) if horizontal > 1e-6 else 0,
                             geometria_mundo.rumbo_de(dx, dz), 0)
            cubo.enabled = True
        for cubo in self.segmentos[len(pares):]:
            cubo.enabled = False
        for disco, (x, z, y) in zip(self.juntas, trazo):
            disco.position = (x, y + 0.015, z)
            disco.enabled = True
        for disco in self.juntas[len(trazo):]:
            disco.enabled = False

    # [(x, z, y)]: los puntos de la ruta más los intermedios, con y = suelo + Y_RUTA.
    def _subdividir(self, puntos):
        trazo = []
        for i, (x, z) in enumerate(puntos):
            if i > 0:
                x0, z0 = puntos[i - 1]
                partes = max(1, math.ceil(math.hypot(x - x0, z - z0) / PASO_RUTA)) if self._altura_en else 1
                for k in range(1, partes):
                    t = k / partes
                    trazo.append(self._con_altura(x0 + (x - x0) * t, z0 + (z - z0) * t))
            trazo.append(self._con_altura(x, z))
        return trazo

    def _con_altura(self, x, z):
        suelo = self._altura_en(x, z) if self._altura_en is not None else 0.0
        return (x, z, suelo + Y_RUTA)

    def segmentos_visibles(self):
        return [s for s in self.segmentos if s.enabled]
