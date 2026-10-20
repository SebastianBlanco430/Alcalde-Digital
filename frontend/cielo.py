# Cielo de la ciudad (Ursina) sin shaders nuevos ni texturas: un domo con COLORES DE VÉRTICE
# (horizonte cálido de tarde que sube a un azul más profundo), un resplandor suave hacia el sol y
# nubes de baja poligonización (esferas aplastadas de 42 vértices, blancas arriba y azuladas abajo).
#
# Reemplaza a ursina.Sky: Ciudad3D lo guarda en `self.cielo` (y lo excluye de silenciar() porque
# necesita update()). Igual que Sky, se dibuja en el bin 'background' con unlit_shader y su escala
# se ajusta al plano lejano de la cámara. Las nubes son un hijo que gira muy despacio.
#
# La parte pura (colores y geometría, sin ursina) se prueba en tests/frontend_3d/test_cielo.py.
# COLOR_HORIZONTE es también el color de la niebla (frontend/niebla.py): lo lejano se funde con el cielo.

import math

from ursina import Entity, Mesh, camera, time
from ursina.shaders import unlit_shader

from frontend.azar_fijo import azar_de

COLOR_HORIZONTE = (238, 224, 204)        # RGB 0-255: crema cálido; también el de la niebla
# (elevación = seno del ángulo sobre el horizonte, color): el degradado se interpola entre paradas.
PARADAS_CIELO = (
    (0.00, COLOR_HORIZONTE),
    (0.10, (206, 220, 232)),
    (0.30, (146, 190, 232)),
    (0.65, (100, 156, 224)),
    (1.00, (74, 128, 210)),
)
COLOR_RESPLANDOR = (255, 238, 198)
DIRECCION_SOL = (1.0, -1.1, 0.8)          # hacia donde apunta la luz; el resplandor sale del lado opuesto
FUERZA_RESPLANDOR = 0.45
ELEVACIONES_ANILLOS = (-0.35, 0.0, 0.025, 0.06, 0.11, 0.18, 0.28, 0.42, 0.6, 0.8, 1.0)   # senos
SEGMENTOS = 28
RADIO_NUBES = 0.955                       # dentro del domo (radio 1), para ganarle en profundidad
CANTIDAD_NUBES = 15
VELOCIDAD_NUBES = 0.35                    # grados por segundo
COLOR_NUBE_ARRIBA = (255, 252, 246)
COLOR_NUBE_ABAJO = (190, 206, 230)


def _mezclar(a, b, t):
    return tuple(a[i] + (b[i] - a[i]) * t for i in range(3))


# Color del degradado a esa elevación (seno del ángulo, 0 = horizonte; por debajo se queda en él).
def color_degradado(elevacion):
    e = min(1.0, max(0.0, elevacion))
    for (e0, c0), (e1, c1) in zip(PARADAS_CIELO, PARADAS_CIELO[1:]):
        if e <= e1:
            return _mezclar(c0, c1, (e - e0) / (e1 - e0))
    return PARADAS_CIELO[-1][1]


# Dirección unitaria HACIA el sol (opuesta a la de la luz).
def direccion_hacia_el_sol(direccion_luz=DIRECCION_SOL):
    x, y, z = direccion_luz
    largo = math.sqrt(x * x + y * y + z * z)
    return (-x / largo, -y / largo, -z / largo)


# Color del cielo en la dirección unitaria `d`: degradado más un resplandor cálido hacia el sol.
def color_en_direccion(d, sol):
    base = color_degradado(d[1])
    cos = max(0.0, d[0] * sol[0] + d[1] * sol[1] + d[2] * sol[2])
    return _mezclar(base, COLOR_RESPLANDOR, FUERZA_RESPLANDOR * cos ** 6)


# Siluetas de cerros lejanos: dos filas de picos bajos (la lejana más clara y velada) pegadas al
# horizonte, para que el fondo no sea una pared lisa. (vértices, triángulos, colores) como el domo.
CAPAS_CERROS = (          # (radio, altura base, amplitud, color, desfase de azar)
    (0.985, 0.020, 0.050, (186, 200, 214), 1.0),
    (0.975, 0.010, 0.032, (160, 180, 190), 2.0),
)
COLUMNAS_CERROS = 56


def geometria_cerros():
    vertices, triangulos, colores = [], [], []
    for radio, base, amplitud, tono, fase in CAPAS_CERROS:
        inicio = len(vertices)
        for k in range(COLUMNAS_CERROS):
            azimut = 2 * math.pi * k / COLUMNAS_CERROS
            # Dos ondas lentas y un diente por columna: cerros redondeados con picos irregulares.
            altura = base + amplitud * (0.45 + 0.3 * math.sin(azimut * 3 + fase) + 0.2 * math.sin(azimut * 7 + 2 * fase)
                                        + 0.35 * azar_de(k, fase))
            for seno, tono_vertice in ((-0.06, COLOR_HORIZONTE), (max(0.004, altura), tono)):
                coseno = math.sqrt(1 - seno * seno)
                vertices.append((radio * coseno * math.cos(azimut), radio * seno, radio * coseno * math.sin(azimut)))
                colores.append((tono_vertice[0] / 255, tono_vertice[1] / 255, tono_vertice[2] / 255, 1.0))
        for k in range(COLUMNAS_CERROS):
            a = inicio + 2 * k
            b = inicio + 2 * ((k + 1) % COLUMNAS_CERROS)
            triangulos += [(a, b, b + 1), (a, b + 1, a + 1)]
    return vertices, triangulos, colores


# Domo de radio 1: (vértices, triángulos, colores 0-1 RGBA). Los anillos van de bajo el horizonte
# al cenit; su elevación se concentra cerca del horizonte, donde cambia más el color.
def geometria_domo(direccion_luz=DIRECCION_SOL):
    sol = direccion_hacia_el_sol(direccion_luz)
    vertices, colores = [], []
    for seno in ELEVACIONES_ANILLOS:
        coseno = math.sqrt(max(0.0, 1 - seno * seno))
        for k in range(SEGMENTOS):
            azimut = 2 * math.pi * k / SEGMENTOS
            d = (coseno * math.cos(azimut), seno, coseno * math.sin(azimut))
            vertices.append(d)
            r, g, b = color_en_direccion(d, sol)
            colores.append((r / 255, g / 255, b / 255, 1.0))
    triangulos = []
    for fila in range(len(ELEVACIONES_ANILLOS) - 1):
        for k in range(SEGMENTOS):
            a = fila * SEGMENTOS + k
            b = fila * SEGMENTOS + (k + 1) % SEGMENTOS
            triangulos += [(a, b, b + SEGMENTOS), (a, b + SEGMENTOS, a + SEGMENTOS)]
    return vertices, triangulos, colores


# Esfera de 42 vértices y 80 triángulos (icosaedro subdividido una vez), de radio 1.
def icosfera():
    t = (1 + math.sqrt(5)) / 2
    base = [(-1, t, 0), (1, t, 0), (-1, -t, 0), (1, -t, 0), (0, -1, t), (0, 1, t), (0, -1, -t), (0, 1, -t),
            (t, 0, -1), (t, 0, 1), (-t, 0, -1), (-t, 0, 1)]
    caras = [(0, 11, 5), (0, 5, 1), (0, 1, 7), (0, 7, 10), (0, 10, 11), (1, 5, 9), (5, 11, 4), (11, 10, 2),
             (10, 7, 6), (7, 1, 8), (3, 9, 4), (3, 4, 2), (3, 2, 6), (3, 6, 8), (3, 8, 9), (4, 9, 5),
             (2, 4, 11), (6, 2, 10), (8, 6, 7), (9, 8, 1)]

    def unitario(v):
        n = math.sqrt(v[0] ** 2 + v[1] ** 2 + v[2] ** 2)
        return (v[0] / n, v[1] / n, v[2] / n)

    vertices = [unitario(v) for v in base]
    indices = {}

    def medio(i, j):
        clave = (min(i, j), max(i, j))
        if clave not in indices:
            a, b = vertices[i], vertices[j]
            vertices.append(unitario(((a[0] + b[0]) / 2, (a[1] + b[1]) / 2, (a[2] + b[2]) / 2)))
            indices[clave] = len(vertices) - 1
        return indices[clave]

    triangulos = []
    for a, b, c in caras:
        ab, bc, ca = medio(a, b), medio(b, c), medio(c, a)
        triangulos += [(a, ab, ca), (b, bc, ab), (c, ca, bc), (ab, bc, ca)]
    return vertices, triangulos


# Nubes: (vértices, triángulos, colores). Cada nube son varias esferas aplastadas en fila sobre el
# domo; los colores van de blanco (arriba) a azul grisáceo (abajo) y se tiñen de horizonte las bajas.
def geometria_nubes(cantidad=CANTIDAD_NUBES):
    base_v, base_t = icosfera()
    vertices, triangulos, colores = [], [], []
    for n in range(cantidad):
        azimut = 2 * math.pi * (n + 0.8 * azar_de(n, 3.1)) / cantidad
        elevacion = math.radians(9 + 38 * azar_de(n, 7.7) ** 1.4)
        tamano = 0.05 + 0.05 * azar_de(n, 1.3)
        blobs = 3 + int(azar_de(n, 5.9) * 3)
        centro = (math.cos(elevacion) * math.cos(azimut), math.sin(elevacion), math.cos(elevacion) * math.sin(azimut))
        tangente = (-math.sin(azimut), 0.0, math.cos(azimut))
        subida = (-math.sin(elevacion) * math.cos(azimut), math.cos(elevacion), -math.sin(elevacion) * math.sin(azimut))
        tinte = max(0.0, 1 - math.degrees(elevacion) / 24) * 0.45          # las bajas se tiñen de horizonte
        for j in range(blobs):
            fila = j - (blobs - 1) / 2
            radio = tamano * (1.0 - 0.28 * abs(fila) / max(1.0, blobs / 2)) * (0.85 + 0.3 * azar_de(n, j + 9.1))
            desplazamiento = fila * tamano * 1.15
            altura = (azar_de(n + 4.4, j) - 0.4) * tamano * 0.35
            pos = tuple(RADIO_NUBES * centro[i] + tangente[i] * desplazamiento + subida[i] * altura for i in range(3))
            largo = math.sqrt(sum(c * c for c in pos))
            pos = tuple(c / largo * RADIO_NUBES for c in pos)               # pegada a la esfera de las nubes
            radial = tuple(c / RADIO_NUBES for c in pos)
            inicio = len(vertices)
            for x, y, z in base_v:
                # x a lo largo de la fila, y hacia arriba (aplastada), z hacia el domo (muy fina)
                v = tuple(pos[i] + tangente[i] * x * radio * 1.35 + subida[i] * y * radio * 0.46
                          + radial[i] * z * radio * 0.35 for i in range(3))
                vertices.append(v)
                t = (y + 1) / 2
                arriba = _mezclar(COLOR_NUBE_ABAJO, COLOR_NUBE_ARRIBA, min(1.0, t * 1.25))
                r, g, b = _mezclar(arriba, COLOR_HORIZONTE, tinte)
                colores.append((r / 255, g / 255, b / 255, 1.0))
            triangulos += [(inicio + a, inicio + b, inicio + c) for a, b, c in base_t]
    return vertices, triangulos, colores


class CieloDegradado(Entity):

    def __init__(self, **opciones):
        vertices, triangulos, colores = geometria_domo()
        cv, ct, cc = geometria_cerros()
        ct = [(a + len(vertices), b + len(vertices), c + len(vertices)) for a, b, c in ct]
        vertices, triangulos, colores = vertices + cv, triangulos + ct, colores + cc
        opciones.setdefault("scale", 400)
        super().__init__(model=Mesh(vertices=vertices, triangles=triangulos, colors=colores),
                         shader=unlit_shader, unlit=True, double_sided=True, name="cielo", **opciones)
        self.setBin("background", 0)
        vn, tn, cn = geometria_nubes()
        self.nubes = Entity(parent=self, model=Mesh(vertices=vn, triangles=tn, colors=cn),
                            shader=unlit_shader, unlit=True, double_sided=True, name="nubes")
        self.nubes.setBin("background", 1)

    # Como Sky: del tamaño del plano lejano y sin giro propio; solo las nubes derivan despacio.
    def update(self):
        self.scale = camera.clip_plane_far * 0.8
        self.nubes.rotation_y += VELOCIDAD_NUBES * time.dt
