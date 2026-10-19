# Marcadores del mundo 3D (Ursina): la baliza amarilla sobre la puerta del destino de la
# misión y la ruta del GPS dibujada en el piso hasta esa puerta. Solo vista: los puntos de
# la ruta salen de backend/logica/navegacion.ruta_gps_hasta_puerta. En la ladera cada tramo se
# parte donde el suelo deja de ser recto (`suelo(x, z)`): en una rampa plana queda una sola pieza.

import math

from ursina import Entity, color, destroy, time

from frontend import geometria_mundo
from frontend.componentes import rgb
from frontend.piezas import pieza

COLOR_RUTA = (70, 220, 255)
COLOR_BALIZA = (255, 220, 60)
Y_RUTA = 0.24             # por encima de aceras (0.20) y plazas (0.14)
ANCHO_RUTA = 0.7
HOLGURA_POOL = 6          # piezas sobrantes que se conservan para rutas futuras
PASO_FIRMA = 0.25         # m: resolución con la que la ruta nota que el jugador se movió
TOLERANCIA_RUTA = 0.05    # m que la ruta puede apartarse del suelo antes de partir un tramo
TRAMO_MINIMO = 1.0        # m: no se parte más fino que esto


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

    # Sobre (x, suelo, z), `altura` m por encima del suelo.
    def colocar(self, x, z, altura=5.0, suelo=0.0):
        self.altura = altura
        self.position = (x, suelo, z)
        self.rombo.y = altura

    def update(self):
        self._tiempo += time.dt
        self.rombo.y = self.altura + 0.2 * math.sin(self._tiempo * 3)
        self.rombo.rotation_y = self._tiempo * 90


# Línea del GPS en el piso: cubos planos entre puntos consecutivos y un disco en cada junta.
class RutaPiso(Entity):

    def __init__(self, suelo=None, **opciones):
        super().__init__(**opciones)
        self.suelo = suelo or (lambda x, z: 0.0)
        self.segmentos = []
        self.juntas = []
        self._firma = None

    # `puntos`: [(x, z)] desde el jugador hasta la puerta ([] = sin ruta).
    def actualizar(self, puntos):
        # Se redibuja cuando algún punto se movió más de PASO_FIRMA (al caminar, no en cada frame).
        firma = tuple((round(x / PASO_FIRMA), round(z / PASO_FIRMA)) for x, z in puntos)
        if firma == self._firma:
            return
        self._firma = firma
        tono = rgb(COLOR_RUTA)
        pares = [par for p0, p1 in zip(puntos, puntos[1:]) for par in self._tramos(p0, p1)]
        while len(self.segmentos) < len(pares):
            self.segmentos.append(pieza(parent=self, model="cube", color=tono, shader=None))
        while len(self.juntas) < len(puntos):
            self.juntas.append(pieza(parent=self, model="circle", rotation_x=90, color=tono, shader=None,
                                     scale=ANCHO_RUTA * 1.4))
        for cubo, (p0, p1) in zip(self.segmentos, pares):
            dx, dz = p1[0] - p0[0], p1[1] - p0[1]
            y0, y1 = self.suelo(*p0), self.suelo(*p1)
            horizontal = math.hypot(dx, dz)
            cubo.position = ((p0[0] + p1[0]) / 2, (y0 + y1) / 2 + Y_RUTA, (p0[1] + p1[1]) / 2)
            cubo.scale = (ANCHO_RUTA, 0.02, max(math.hypot(horizontal, y1 - y0), 0.01))
            cubo.rotation = (-math.degrees(math.atan2(y1 - y0, max(horizontal, 1e-9))),  # - = sube hacia +z
                             geometria_mundo.rumbo_de(dx, dz), 0)
            cubo.enabled = True
        for cubo in self.segmentos[len(pares):]:
            cubo.enabled = False
        for disco, (x, z) in zip(self.juntas, puntos):
            disco.position = (x, self.suelo(x, z) + Y_RUTA + 0.015, z)
            disco.enabled = True
        for disco in self.juntas[len(puntos):]:
            disco.enabled = False
        self._recortar(self.segmentos, len(pares))
        self._recortar(self.juntas, len(puntos))

    # Libera las piezas que sobran (más de HOLGURA_POOL sin usar) para que el pool no crezca sin tope.
    @staticmethod
    def _recortar(pool, usadas):
        tope = usadas + HOLGURA_POOL
        while len(pool) > tope:
            destroy(pool.pop())

    def segmentos_visibles(self):
        return [s for s in self.segmentos if s.enabled]


    # Tramos [(p, q)] que cubren a -> b: se parte por la mitad mientras el suelo en 1/4, 1/2 o 3/4
    # se aparte más de TOLERANCIA_RUTA de la recta entre los extremos (con solo el medio, una
    # rampa simétrica entre dos plazas planas pasaría por recta).
    def _tramos(self, a, b):
        ya, yb = self.suelo(*a), self.suelo(*b)

        def desvio(t):
            return abs(self.suelo(a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t) - (ya + (yb - ya) * t))

        if math.dist(a, b) <= 2 * TRAMO_MINIMO or max(desvio(t) for t in (0.25, 0.5, 0.75)) <= TOLERANCIA_RUTA:
            return [(a, b)]
        medio = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
        return self._tramos(a, medio) + self._tramos(medio, b)
