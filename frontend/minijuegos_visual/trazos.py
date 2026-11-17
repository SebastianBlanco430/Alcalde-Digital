# Líneas para las vistas visuales de los minijuegos (Ursina): hilos rojos, círculos de rotulador, agujas de reloj.
# Una Linea es UNA entidad con su malla de líneas; fijar(puntos) reescribe los vértices de la misma malla (no crea
# entidades por frame). Los puntos los calcula frontend/minijuegos_visual/pistas_visuales_calculos.py.

from ursina import Entity, Mesh, color


def _rgba(tono, alfa=1.0):
    return color.rgba32(int(tono[0]), int(tono[1]), int(tono[2]), int(max(0.0, min(1.0, alfa)) * 255))


class Linea(Entity):

    def __init__(self, tono=(220, 50, 50), grosor=3, alfa=1.0, **opciones):
        super().__init__(**opciones)
        self._grosor = grosor
        self.model = Mesh(vertices=[(0, 0, 0), (0, 0, 0)], mode="line", thickness=grosor)
        self.color = _rgba(tono, alfa)
        self._vistos = None

    def fijar(self, puntos):
        """Polilínea por `puntos` [(x, y)] en coordenadas del padre. Menos de 2 puntos: se esconde."""
        if len(puntos) < 2:
            self.visible = False
            return
        self.visible = True
        clave = tuple((round(x, 4), round(y, 4)) for x, y in puntos)
        if clave == self._vistos:
            return
        self._vistos = clave
        self.model.vertices = [(x, y, 0) for x, y in puntos]
        self.model.generate()

    def tono(self, tono, alfa=1.0):
        self.color = _rgba(tono, alfa)
