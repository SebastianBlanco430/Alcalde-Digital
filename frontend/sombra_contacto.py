# Sombra de contacto (T12 de docs/DISENO.md) y aro translúcido del jugador activo: discos planos
# sin shader (color con alfa, no reciben luz ni sombras horneadas) que no escriben profundidad y
# llevan un sesgo de profundidad para no parpadear con las capas del suelo.
# Cálculos (radio, alfa, alturas) en sombra_calculos.py.

from ursina import Entity, color

from frontend import sombra_calculos as sc
from frontend.piezas import COLOR_MARCADOR, silenciar

COLOR_SOMBRA = (10, 12, 30)       # tinta azul oscuro (docs/DISENO.md)


# Disco plano translúcido: sin shader, sin escribir profundidad y con sesgo hacia la cámara.
def _disco(parent, y, radio, rgba, **opciones):
    disco = Entity(parent=parent, model="circle", rotation_x=90, y=y, scale=radio * 2, color=rgba,
                   shader=None, **opciones)
    disco.setDepthWrite(False)
    disco.set_depth_offset(1)
    return silenciar(disco)


# Sombra bajo los pies, a `y` local del padre. Una sola Entity: se destruye con el padre.
class SombraContacto(Entity):

    def __init__(self, parent, y, altura=0.0):
        super().__init__(parent=parent)
        self.disco = _disco(self, 0, sc.radio_sombra(altura),
                            color.rgba32(*COLOR_SOMBRA, round(255 * sc.alfa_sombra(altura))))
        self.y = y
        silenciar(self)


# Aro de resaltado: disco amarillo translúcido por encima de las capas del suelo.
def crear_aro(parent, y=sc.Y_AURO):
    r, g, b, _ = COLOR_MARCADOR
    return _disco(parent, y, 0.85, color.rgba(r, g, b, sc.ALFA_AURO), enabled=False)
