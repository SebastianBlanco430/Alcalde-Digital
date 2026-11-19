# Piezas de papel (Ursina) para las vistas visuales de los minijuegos, estilo «cómic cívico»: hojas con sombra plana y
# borde de tinta, cinta adhesiva, chinchetas, sellos de goma, resaltador, polaroids, chips, ovillos y aros de rotulador.
# La geometría sale de frontend/minijuegos_visual/papel_calculos.py. Cada función devuelve un Entity contenedor; sus
# hijos usan coordenadas locales.

from ursina import Entity, Mesh, Text, camera, color

from frontend import tipografia
from frontend.estilo import ESTADO_ERROR, ESTADO_EXITO, PAPEL, TINTA
from frontend.minijuegos_visual import papel_calculos as pc

BORDE = 0.004                    # ~3 px de tinta
SOMBRA = (0.004, -0.005)         # sombra plana (4, -5) px
ALFA_SOMBRA = 160 / 255
AMARILLO = (255, 220, 60)
CIAN = (70, 220, 255)


def _rgba(tono, alfa=1.0):
    try:
        return color.rgba32(int(tono[0]), int(tono[1]), int(tono[2]), int(max(0.0, min(1.0, alfa)) * 255))
    except Exception:
        return color.white


def _padre(parent):
    return parent if parent is not None else camera.ui


def _pos3(pos, z=0.0):
    if len(pos) >= 3:
        return (pos[0], pos[1], pos[2])
    return (pos[0], pos[1], z)


def _poligono(puntos):
    """Malla rellena de un polígono convexo (abanico desde el primer vértice)."""
    vertices = [(x, y, 0) for x, y in puntos]
    triangulos = [(0, i, i + 1) for i in range(1, len(puntos) - 1)]
    return Mesh(vertices=vertices, triangles=triangulos, mode="triangle")


def _texto(parent, texto, pos, tam, tono, fuente=None, z=-0.003):
    try:
        return Text(str(texto), parent=parent, origin=(0, 0), position=(pos[0], pos[1], z), scale=tam / Text.size,
                    font=fuente or tipografia.FUENTE_TITULO, color=_rgba(tono))
    except Exception:
        return None


def sombra_plana(parent, pos, escala):
    try:
        return Entity(parent=_padre(parent), model="quad", position=_pos3((pos[0] + SOMBRA[0], pos[1] + SOMBRA[1]), 0.002),
                      scale=(escala[0], escala[1]), color=_rgba(TINTA, ALFA_SOMBRA))
    except Exception:
        return Entity(parent=_padre(parent))


def hoja(parent, pos, escala, color=PAPEL, giro=0, z=0, doblez=False):
    tono = color
    raiz = Entity(parent=_padre(parent), position=_pos3(pos, z), rotation_z=giro)
    try:
        ancho, alto = escala[0], escala[1]
        if doblez:
            tam = min(ancho, alto) * 0.18
            poli, tri = pc.esquina_doblada(ancho, alto, tam)
            Entity(parent=raiz, model=_poligono(poli), position=(SOMBRA[0], SOMBRA[1], 0.002),
                   color=_rgba(TINTA, ALFA_SOMBRA))
            borde, _ = pc.esquina_doblada(ancho + 2 * BORDE, alto + 2 * BORDE, tam + BORDE)
            Entity(parent=raiz, model=_poligono(borde), position=(0, 0, 0.001), color=_rgba(TINTA))
            Entity(parent=raiz, model=_poligono(poli), color=_rgba(tono))
            Entity(parent=raiz, model=_poligono(tri), position=(0, 0, -0.001), color=_rgba(pc.PAPEL_SOMBRA))
            for hijo in raiz.children:          # el abanico sale con la cara hacia atrás: dibujar ambas caras
                hijo.double_sided = True
        else:
            Entity(parent=raiz, model="quad", position=(SOMBRA[0], SOMBRA[1], 0.002), scale=(ancho, alto),
                   color=_rgba(TINTA, ALFA_SOMBRA))
            Entity(parent=raiz, model="quad", position=(0, 0, 0.001), scale=(ancho + 2 * BORDE, alto + 2 * BORDE),
                   color=_rgba(TINTA))
            Entity(parent=raiz, model="quad", scale=(ancho, alto), color=_rgba(tono))
    except Exception:
        pass
    return raiz


def cinta(parent, pos, giro=0):
    try:
        return Entity(parent=_padre(parent), model="quad", position=_pos3(pos, -0.004), scale=(0.08, 0.025),
                      rotation_z=giro, color=_rgba(CIAN, 0.55))
    except Exception:
        return Entity(parent=_padre(parent))


def chincheta(parent, pos, color=ESTADO_EXITO):
    raiz = Entity(parent=_padre(parent), position=_pos3(pos, -0.004))
    try:
        Entity(parent=raiz, model="circle", position=(SOMBRA[0] * 0.5, SOMBRA[1] * 0.5, 0.002), scale=0.026,
               color=_rgba(TINTA, ALFA_SOMBRA))
        Entity(parent=raiz, model="circle", position=(0, 0, 0.001), scale=0.026, color=_rgba(TINTA))
        Entity(parent=raiz, model="circle", scale=0.018, color=_rgba(color))
        Entity(parent=raiz, model="circle", position=(-0.003, 0.003, -0.001), scale=0.005, color=_rgba(PAPEL, 0.8))
    except Exception:
        pass
    return raiz


def sello_goma(parent, texto, pos, color, giro=-8, escala=(0.22, 0.07), ovalado=False):
    raiz = Entity(parent=_padre(parent), position=_pos3(pos, -0.005), rotation_z=giro)
    try:
        ancho, alto = escala
        for k, margen in enumerate((0.0, 0.009)):
            rx, ry = ancho / 2 - margen, alto / 2 - margen
            if ovalado:
                puntos = pc.arco(0, 0, 1, 0, 360, n=48)
                puntos = [(x * rx, y * ry) for x, y in puntos]
            else:
                puntos = [(-rx, -ry), (rx, -ry), (rx, ry), (-rx, ry), (-rx, -ry)]
            Entity(parent=raiz, model=Mesh(vertices=[(x, y, 0) for x, y in puntos], mode="line",
                                           thickness=3 if k == 0 else 2), color=_rgba(color, 0.9))
        _texto(raiz, str(texto).upper(), (0, 0), alto * 0.42, color)
    except Exception:
        pass
    return raiz


class _Resaltador(Entity):

    def __init__(self, ancho, **opciones):
        super().__init__(**opciones)
        self._ancho = ancho
        self._x0 = self.x - ancho / 2
        self.set_progreso(1.0)

    def set_progreso(self, p):
        try:
            p = max(0.0, min(1.0, float(p)))
            self.scale_x = max(1e-4, self._ancho * p)
            self.x = self._x0 + self.scale_x / 2
            self.visible = p > 0
        except Exception:
            pass


def resaltador(parent, pos, escala, color=(255, 220, 60), alfa=0.7):
    return _Resaltador(escala[0], parent=_padre(parent), model="quad", position=_pos3(pos, -0.002),
                       scale=(escala[0], escala[1]), color=_rgba(color, alfa))


def polaroid(parent, texto, pos, giro=2):
    raiz = hoja(parent, pos, (0.19, 0.24), color=PAPEL, giro=giro)
    try:
        Entity(parent=raiz, model="quad", position=(0, 0.025, -0.001), scale=(0.16, 0.15), color=_rgba(pc.PAPEL_SOMBRA))
        _texto(raiz, texto, (0, -0.085), 0.022, TINTA, fuente=tipografia.FUENTE_TEXTO)
    except Exception:
        pass
    return raiz


def chip(parent, texto, pos, color=(70, 220, 255)):
    raiz = Entity(parent=_padre(parent), position=_pos3(pos, -0.003))
    try:
        ancho, alto = max(0.06, 0.013 * len(str(texto)) + 0.03), 0.036
        Entity(parent=raiz, model="quad", position=(SOMBRA[0], SOMBRA[1], 0.002), scale=(ancho, alto),
               color=_rgba(TINTA, ALFA_SOMBRA))
        Entity(parent=raiz, model="quad", position=(0, 0, 0.001), scale=(ancho + 2 * BORDE, alto + 2 * BORDE),
               color=_rgba(TINTA))
        Entity(parent=raiz, model="quad", scale=(ancho, alto), color=_rgba(color))
        _texto(raiz, texto, (0, 0), 0.02, TINTA)
    except Exception:
        pass
    return raiz


class _Ovillo(Entity):

    def __init__(self, encendido=True, **opciones):
        super().__init__(**opciones)
        Entity(parent=self, model="circle", position=(0, 0, 0.001), scale=0.03, color=_rgba(TINTA))
        self._bola = Entity(parent=self, model="circle", scale=0.022)
        self._hebra = Entity(parent=self, model="quad", position=(0, 0, -0.001), scale=(0.018, 0.003), rotation_z=30,
                             color=_rgba(TINTA, 0.6))
        self.encender(encendido)

    def encender(self, encendido=True):
        try:
            self.encendido = bool(encendido)
            self._bola.color = _rgba(ESTADO_ERROR if self.encendido else pc.PAPEL_SOMBRA)
            self._hebra.color = _rgba(TINTA, 0.6 if self.encendido else 0.25)
        except Exception:
            pass


def ovillo(parent, pos, encendido=True):
    return _Ovillo(encendido=encendido, parent=_padre(parent), position=_pos3(pos, -0.003))


def aro_discontinuo(parent, pos, rx, ry, color=ESTADO_ERROR):
    raiz = Entity(parent=_padre(parent), position=_pos3(pos, -0.006))
    try:
        vertices = []
        for p0, p1 in pc.aro_discontinuo(rx, ry):
            vertices += [(p0[0], p0[1], 0), (p1[0], p1[1], 0)]
        pares = [(2 * k, 2 * k + 1) for k in range(len(vertices) // 2)]   # segmentos sueltos, con huecos
        Entity(parent=raiz, model=Mesh(vertices=vertices, triangles=pares, mode="line", thickness=4), color=_rgba(color))
    except Exception:
        pass
    return raiz


def polaroid_retrato(parent, texto, pos, giro=2, piel=(224, 172, 132), pelo=(52, 38, 34), camisa=(70, 120, 170)):
    """Polaroid con la cabeza y los hombros de un personaje (la foto del jugador) y la leyenda a rotulador debajo."""
    raiz = hoja(parent, pos, (0.19, 0.24), color=PAPEL, giro=giro)
    try:
        Entity(parent=raiz, model="quad", position=(0, 0.025, -0.001), scale=(0.16, 0.15), color=_rgba((196, 214, 226)))
        centro, radio, hombros = pc.cabeza_retrato()
        base = (0, 0.025, -0.002)
        poli = [(x, y + 0.0) for x, y in hombros]
        Entity(parent=raiz, model=_poligono([(x, y + 0.0) for x, y in poli]), position=base, color=_rgba(camisa))
        Entity(parent=raiz, model="circle", position=(centro[0], centro[1] + 0.006, -0.003), scale=radio * 2.5,
               color=_rgba(pelo))
        Entity(parent=raiz, model="circle", position=(centro[0], centro[1], -0.004), scale=radio * 2.0, color=_rgba(piel))
        for dx in (-0.011, 0.011):
            Entity(parent=raiz, model="circle", position=(dx, centro[1] + 0.003, -0.005), scale=0.006, color=_rgba(TINTA))
        for hijo in raiz.children:
            hijo.double_sided = True
        _texto(raiz, texto, (0, -0.075), 0.03, TINTA)
        Entity(parent=raiz, model=Mesh(vertices=[(-0.045, -0.097, 0), (-0.01, -0.1, 0), (0.02, -0.096, 0), (0.046, -0.099, 0)],
                                       mode="line", thickness=3), position=(0, 0, -0.003), color=_rgba(TINTA))
    except Exception:
        pass
    return raiz


def trazo_rotulador(parent, puntos, tono=(30, 90, 200), grosor=4, z=-0.004):
    """Polilínea suelta de rotulador (una entidad); `puntos` [(x, y)] locales."""
    try:
        return Entity(parent=_padre(parent), model=Mesh(vertices=[(x, y, 0) for x, y in puntos], mode="line", thickness=grosor),
                      position=(0, 0, z), color=_rgba(tono))
    except Exception:
        return Entity(parent=_padre(parent))
