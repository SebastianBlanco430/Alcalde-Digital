# Geometría pura de las piezas del rostro y sus accesorios (NO importa ursina ni panda3d).
# Genera mallas unitarias (esfera, caja, cilindro, anillo), las coloca (escala, giro, posición),
# les aplica «bandas de luz» tipo cel/toon POR TRIÁNGULO (2-3 tonos planos, sin shader) y las une
# en una sola malla con color por vértice. frontend/rostro_modelo.py solo traduce el resultado a un
# Geom de Panda3D.
#
# Convención de ejes: los del glb crudo de Blender (x a la izquierda del personaje, y hacia atrás, la
# cara mira a -y, z hacia arriba). El giro de una pieza estática se da en grados alrededor de los ejes
# x, y, z de ese sistema (aplicados en ese orden), distinto del HPR de Panda3D.
#
# Sentido de las caras: las mallas siguen el mismo convenio que las esferas de rostro_modelo
# («horario» visto desde fuera en el sistema derecho del glb, antihorario en el del juego), por eso
# la normal hacia fuera es el producto vectorial CAMBIADO de signo (ver normal_triangulo).

import math

# Dirección hacia la luz en los ejes de la cabeza (arriba, a un lado y al frente): fija, porque las bandas
# van horneadas en el color de los vértices y la cabeza gira con el personaje.
LUZ = (0.30, -0.72, 0.62)
CORTE_LUZ = 0.08            # producto punto sobre el que la cara está en luz plena
CORTE_SOMBRA = -0.30        # bajo este valor, tono de sombra
FACTOR_LUZ = (1.05, 1.05, 1.0)        # tono luz: ligeramente cálido y claro
FACTOR_MEDIO = (0.92, 0.91, 0.94)
FACTOR_SOMBRA = (0.76, 0.71, 0.84)    # sombra algo violeta, como el ambiente azul del mundo


def _normalizar(v):
    n = math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2])
    return (0.0, 0.0, 0.0) if n == 0 else (v[0] / n, v[1] / n, v[2] / n)


def _punto(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


# -- Mallas unitarias: (vértices, triángulos) --

def esfera(segmentos=10, anillos=6):
    # Esfera de radio 1 con polos en ±z.
    vertices = [(0.0, 0.0, 1.0)]
    for i in range(1, anillos):
        phi = math.pi * i / anillos
        for j in range(segmentos):
            theta = 2 * math.pi * j / segmentos
            vertices.append((math.sin(phi) * math.cos(theta), math.sin(phi) * math.sin(theta), math.cos(phi)))
    vertices.append((0.0, 0.0, -1.0))
    polo_sur = len(vertices) - 1
    triangulos = []
    base = 1 + (anillos - 2) * segmentos
    for j in range(segmentos):
        k = (j + 1) % segmentos
        triangulos.append((0, 1 + k, 1 + j))
        triangulos.append((polo_sur, base + j, base + k))
    for i in range(anillos - 2):
        for j in range(segmentos):
            k = (j + 1) % segmentos
            a, b = 1 + i * segmentos + j, 1 + i * segmentos + k
            c, d = a + segmentos, b + segmentos
            triangulos += [(a, b, d), (a, d, c)]
    return vertices, triangulos


def caja():
    # Cubo de lado 2.
    vertices = [(x, y, z) for x in (-1, 1) for y in (-1, 1) for z in (-1, 1)]
    caras = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    triangulos = []
    for a, b, c, d in caras:
        triangulos += [(a, c, b), (a, d, c)]      # mismo sentido que la esfera (comprobado en las pruebas)
    return [tuple(float(c) for c in v) for v in vertices], triangulos


def cilindro(segmentos=10):
    # Cilindro de radio 1 y altura 2 con el eje en z, con tapas.
    vertices = []
    for z in (-1.0, 1.0):
        for j in range(segmentos):
            theta = 2 * math.pi * j / segmentos
            vertices.append((math.cos(theta), math.sin(theta), z))
    vertices += [(0.0, 0.0, -1.0), (0.0, 0.0, 1.0)]
    centro_abajo, centro_arriba = 2 * segmentos, 2 * segmentos + 1
    triangulos = []
    for j in range(segmentos):
        k = (j + 1) % segmentos
        a, b, c, d = j, k, segmentos + k, segmentos + j
        triangulos += [(a, c, b), (a, d, c)]
        triangulos.append((centro_abajo, j, k))
        triangulos.append((centro_arriba, segmentos + k, segmentos + j))
    return vertices, triangulos


def anillo(segmentos=14, lados=5, tubo=0.14):
    # Toro en el plano xz (el hueco mira a lo largo de y): radio mayor 1, radio del tubo `tubo`.
    vertices = []
    for i in range(segmentos):
        theta = 2 * math.pi * i / segmentos
        for j in range(lados):
            phi = 2 * math.pi * j / lados
            radio = 1.0 + tubo * math.cos(phi)
            vertices.append((radio * math.cos(theta), tubo * math.sin(phi), radio * math.sin(theta)))
    triangulos = []
    for i in range(segmentos):
        i2 = (i + 1) % segmentos
        for j in range(lados):
            j2 = (j + 1) % lados
            a, b = i * lados + j, i2 * lados + j
            c, d = i2 * lados + j2, i * lados + j2
            triangulos += [(a, b, c), (a, c, d)]
    return vertices, triangulos


FORMAS_VALIDAS = ("esfera", "caja", "cilindro", "anillo")


def malla_unitaria(forma, detalle=None):
    # `detalle`: (segmentos, anillos) en la esfera; segmentos en el cilindro y el anillo; ignorado en la caja.
    if forma == "esfera":
        segmentos, anillos = detalle or (10, 6)
        return esfera(segmentos, anillos)
    if forma == "caja":
        return caja()
    if forma == "cilindro":
        return cilindro(detalle[0] if detalle else 10)
    if forma == "anillo":
        return anillo(detalle[0] if detalle else 14)
    raise ValueError(f"forma desconocida: {forma}")


def detalle_para(forma, escala):
    # Más caras en piezas grandes (pelo, gorra) y menos en las diminutas: el rostro entero queda en pocos miles de triángulos.
    mayor = max(escala)
    if forma == "esfera":
        if mayor >= 0.07:
            return (12, 8)
        return (8, 5) if mayor < 0.02 else (10, 6)
    if forma == "cilindro":
        return (8,) if mayor < 0.02 else (10,)
    if forma == "anillo":
        return (14,) if mayor >= 0.02 else (10,)
    return None


# -- Colocación --

def rotar(punto, giro):
    # Giro en grados alrededor de x, luego y, luego z.
    x, y, z = punto
    gx, gy, gz = (math.radians(a) for a in giro)
    if gx:
        c, s = math.cos(gx), math.sin(gx)
        y, z = y * c - z * s, y * s + z * c
    if gy:
        c, s = math.cos(gy), math.sin(gy)
        x, z = x * c + z * s, -x * s + z * c
    if gz:
        c, s = math.cos(gz), math.sin(gz)
        x, y = x * c - y * s, x * s + y * c
    return (x, y, z)


def colocar(vertices, escala, giro=(0.0, 0.0, 0.0), pos=(0.0, 0.0, 0.0)):
    # Escala, gira y traslada los vértices de una malla unitaria.
    salida = []
    for v in vertices:
        p = rotar((v[0] * escala[0], v[1] * escala[1], v[2] * escala[2]), giro)
        salida.append((p[0] + pos[0], p[1] + pos[1], p[2] + pos[2]))
    return salida


def normal_triangulo(a, b, c):
    # Normal hacia fuera con el convenio de las mallas de este módulo (producto vectorial cambiado de signo).
    u = (b[0] - a[0], b[1] - a[1], b[2] - a[2])
    w = (c[0] - a[0], c[1] - a[1], c[2] - a[2])
    cruz = (u[1] * w[2] - u[2] * w[1], u[2] * w[0] - u[0] * w[2], u[0] * w[1] - u[1] * w[0])
    return _normalizar((-cruz[0], -cruz[1], -cruz[2]))


# -- Bandas de luz --

def banda(intensidad):
    # 2: luz plena, 1: medio tono, 0: sombra. Cortes fijos: bordes duros de cómic.
    if intensidad >= CORTE_LUZ:
        return 2
    return 1 if intensidad >= CORTE_SOMBRA else 0


def color_en_banda(color, nivel):
    factor = (FACTOR_SOMBRA, FACTOR_MEDIO, FACTOR_LUZ)[nivel]
    return tuple(max(0.0, min(1.0, c * f)) for c, f in zip(color, factor))


def color_para_normal(color, normal, luz=LUZ):
    return color_en_banda(color, banda(_punto(normal, _normalizar(luz))))


# -- Unión de piezas --

def pieza_a_malla(pieza, grosor_extra=0.0):
    # (vértices, triángulos) de una pieza ({forma, pos, escala, giro?}) ya colocada. `grosor_extra` (m) infla
    # la pieza por cada lado: es el casco del contorno de tinta.
    escala = tuple(e + grosor_extra for e in pieza["escala"])
    detalle = pieza.get("detalle") or detalle_para(pieza["forma"], pieza["escala"])
    vertices, triangulos = malla_unitaria(pieza["forma"], detalle)
    return colocar(vertices, escala, pieza.get("giro", (0.0, 0.0, 0.0)), pieza["pos"]), triangulos


def unir_piezas(piezas, bandas=True, color_fijo=None, grosor_extra=0.0):
    # Une varias piezas en una malla de triángulos sueltos (vértices no compartidos) con un color por
    # triángulo: el de la pieza, afectado por su banda de luz. Devuelve (vértices, colores, triángulos).
    vertices, colores, triangulos = [], [], []
    for pieza in piezas:
        puntos, tris = pieza_a_malla(pieza, grosor_extra)
        base = color_fijo or pieza["color"]
        for a, b, c in tris:
            pa, pb, pc = puntos[a], puntos[b], puntos[c]
            if bandas and color_fijo is None:
                tono = color_para_normal(base, normal_triangulo(pa, pb, pc))
            else:
                tono = base
            n = len(vertices)
            vertices += [pa, pb, pc]
            colores += [tono, tono, tono]
            triangulos.append((n, n + 1, n + 2))
    return vertices, colores, triangulos


def limites(piezas):
    # Caja que envuelve las piezas (para pruebas): ((xmin, ymin, zmin), (xmax, ymax, zmax)).
    minimo = [math.inf] * 3
    maximo = [-math.inf] * 3
    for pieza in piezas:
        puntos, _ = pieza_a_malla(pieza)
        for p in puntos:
            for i in range(3):
                minimo[i] = min(minimo[i], p[i])
                maximo[i] = max(maximo[i], p[i])
    return tuple(minimo), tuple(maximo)


# -- Del glb crudo al muñeco procedural --

def matriz_procedural(escala, centro, destino=(0.0, 0.15, 0.0)):
    # Fila a fila (convenio de Panda: vector fila por matriz) la transformación que lleva un punto de la
    # cabeza en ejes del glb crudo (relativo al hueso) a la cabeza del muñeco procedural (y arriba, la cara
    # mira a +z, x del personaje a la derecha): salida = escala * (-(x-cx), (z-cz), -(y-cy)) + destino.
    s = escala
    return ((-s, 0.0, 0.0, 0.0),
            (0.0, 0.0, -s, 0.0),
            (0.0, s, 0.0, 0.0),
            (s * centro[0] + destino[0], -s * centro[2] + destino[1], s * centro[1] + destino[2], 1.0))


def aplicar_matriz_fila(matriz, punto):
    x, y, z = punto
    return tuple(x * matriz[0][i] + y * matriz[1][i] + z * matriz[2][i] + matriz[3][i] for i in range(3))
