# Mallas a Panda3D SIN pasar por ursina.Mesh (que arma cada malla con bucles de Python mucho más lentos): listas de
# vértices, normales, colores, uv y triángulos -> GeomNode. Lo usa el mapa grande (frontend/ciudad_chunks.py), que
# construye cientos de mallas pequeñas en pleno juego.
#
# Convenciones (las mismas de ursina.Mesh, para que las listas de props_mundo, suelo_favela, etc. sirvan tal cual):
# colores RGBA 0-1, triángulos como (a, b, c) tal cual se los pasa a Panda, uv (u, v).
#
#   Acumulador       lista de piezas (cajas, prismas, plantillas) con color por vértice; volcar_a_geom() las funde en un GeomNode.
#   escribir_geom()  generador: escribe los vértices por tandas (cede el control entre una y otra) para no pasar de ~3 ms.
#
# Parte pura (Acumulador, plantillas): sin ursina; solo usa panda3d.core al volcar (se prueba sin ventana).

import math
from array import array

from panda3d.core import (Geom, GeomNode, GeomTriangles, GeomVertexData, GeomVertexFormat, GeomVertexWriter,
                          NodePath)

TANDA_VERTICES = 1500        # vértices que se escriben entre una cesión y otra (~2 ms)


def _formato(con_uv):
    return GeomVertexFormat.get_v3n3c4t2() if con_uv else GeomVertexFormat.get_v3n3c4()


def escribir_geom(nombre, vertices, normales, colores, triangulos, uvs=None, tanda=TANDA_VERTICES):
    """Generador que arma el GeomNode de la malla; cede el control cada `tanda` vértices y su `StopIteration.value`
    es el GeomNode (usar `yield from` o recorrerlo con next()). Sin vértices devuelve None."""
    n = len(vertices)
    if n == 0 or not triangulos:
        return None
    datos = GeomVertexData(nombre, _formato(uvs is not None), Geom.UH_static)
    datos.set_num_rows(n)
    wv, wn, wc = (GeomVertexWriter(datos, c) for c in ("vertex", "normal", "color"))
    wt = GeomVertexWriter(datos, "texcoord") if uvs is not None else None
    for i0 in range(0, n, tanda):
        i1 = min(n, i0 + tanda)
        for i in range(i0, i1):
            v = vertices[i]
            wv.add_data3(v[0], v[1], v[2])
            q = normales[i]
            wn.add_data3(q[0], q[1], q[2])
            c = colores[i]
            wc.add_data4(c[0], c[1], c[2], c[3] if len(c) > 3 else 1.0)
            if wt is not None:
                wt.add_data2(uvs[i][0], uvs[i][1])
        if i1 < n:
            yield
    prim = GeomTriangles(Geom.UH_static)
    plano = array("H" if n < 65536 else "I", [i for t in triangulos for i in t])
    prim.set_index_type(Geom.NT_uint16 if n < 65536 else Geom.NT_uint32)
    prim.modify_vertices().modify_handle().copy_data_from(plano.tobytes())
    geom = Geom(datos)
    geom.add_primitive(prim)
    nodo = GeomNode(nombre)
    nodo.add_geom(geom)
    return nodo


def geom_completa(nombre, vertices, normales, colores, triangulos, uvs=None):
    """Lo mismo de golpe (pruebas y piezas globales). Devuelve el GeomNode o None."""
    gen = escribir_geom(nombre, vertices, normales, colores, triangulos, uvs, tanda=10 ** 9)
    try:
        while True:
            next(gen)
    except StopIteration as fin:
        return fin.value


# -- Plantillas de sólidos: (vértices, normales, triángulos) con normales SUAVES (esferas y troncos) --------------------


def _unitario(v):
    n = math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2]) or 1.0
    return (v[0] / n, v[1] / n, v[2] / n)


def icosfera_suave(subdivisiones=0):
    """Esfera de radio 0.5 con normales suaves, indexada: 12 vértices (0) o 42 (1). (vértices, normales, triángulos)."""
    from frontend.props_mundo import icosfera
    vertices, triangulos = icosfera(subdivisiones)
    normales = [_unitario(v) for v in vertices]
    return list(vertices), normales, list(triangulos)


def prisma_suave(lados=6, radio_base=0.5, radio_tope=0.5):
    """Prisma/cono de alto 1 con la base en y = 0, indexado, con normales radiales: 2*lados + 1 vértices."""
    from frontend.props_mundo import prisma
    vertices, triangulos = prisma(lados, radio_base, radio_tope)
    normales = []
    for x, y, z in vertices:
        if x == 0.0 and z == 0.0:
            normales.append((0.0, 1.0, 0.0))
        else:
            h = math.hypot(x, z)
            normales.append((x / h, 0.0 if radio_base == radio_tope else 0.35, z / h))
    return list(vertices), [_unitario(n) for n in normales], list(triangulos)


# -- Acumulador --------------------------------------------------------------------------------------------------------


class Acumulador:
    """Piezas con color por vértice acumuladas en listas planas (indexadas). Se vuelcan a UN GeomNode."""

    def __init__(self):
        self.vertices, self.normales, self.colores, self.triangulos = [], [], [], []
        self.uvs = None

    def __len__(self):
        return len(self.vertices)

    def vacio(self):
        return not self.vertices

    # Copia una plantilla (vértices, normales, triángulos) en `posicion` con `escala` (x, y, z o número) y `giro_y`
    # grados (convención de Ursina: sentido de props_mundo.Malla.agregar). El color (RGB 0-255) va de `degradado[0]`
    # abajo a `degradado[1]` arriba (multiplicadores), como las piezas de props_mundo.
    def solido(self, plantilla, posicion, escala=1.0, giro=0.0, color=(255, 255, 255), degradado=(0.8, 1.05)):
        sv, sn, st = plantilla
        if isinstance(escala, (int, float)):
            escala = (escala, escala, escala)
        seno, coseno = math.sin(math.radians(giro)), math.cos(math.radians(giro))
        ys = [v[1] for v in sv]
        base, alto = min(ys), (max(ys) - min(ys)) or 1.0
        i0 = len(self.vertices)
        px, py, pz = posicion
        ex, ey, ez = escala
        for (x, y, z), (nx, ny, nz) in zip(sv, sn):
            x, y, z = x * ex, y * ey, z * ez
            self.vertices.append((px + x * coseno + z * seno, py + y, pz - x * seno + z * coseno))
            # la normal solo gira (la escala no uniforme se ignora: son blobs de hojas y troncos)
            self.normales.append((nx * coseno + nz * seno, ny, -nx * seno + nz * coseno))
            f = degradado[0] + (degradado[1] - degradado[0]) * (y / ey - base) / alto
            self.colores.append((min(1.5, color[0] / 255 * f), min(1.5, color[1] / 255 * f),
                                 min(1.5, color[2] / 255 * f), 1.0))
        self.triangulos.extend((a + i0, b + i0, c + i0) for a, b, c in st)

    # Caja con caras planas (24 vértices; sin la de abajo: 20) centrada en (cx, cy, cz) de lados (ancho x, alto y, fondo z),
    # girada `giro` grados sobre y. Colores por cara: `color` (RGB 0-255) y `tapa` (RGB, la cara de arriba) si se da.
    def caja(self, cx, cy, cz, ancho, alto, fondo, giro=0.0, color=(200, 200, 200), tapa=None, degradado=(0.82, 1.0)):
        seno, coseno = math.sin(math.radians(giro)), math.cos(math.radians(giro))
        hx, hy, hz = ancho / 2, alto / 2, fondo / 2

        def p(x, y, z):
            return (cx + x * coseno + z * seno, cy + y, cz - x * seno + z * coseno)

        def n(x, y, z):
            return (x * coseno + z * seno, y, -x * seno + z * coseno)

        caras = (  # (normal local, 4 esquinas en sentido que props_mundo.caja() considera frontal)
            ((0, 1, 0), ((-hx, hy, -hz), (-hx, hy, hz), (hx, hy, hz), (hx, hy, -hz))),
            ((0, 0, 1), ((-hx, -hy, hz), (hx, -hy, hz), (hx, hy, hz), (-hx, hy, hz))),
            ((0, 0, -1), ((-hx, -hy, -hz), (-hx, hy, -hz), (hx, hy, -hz), (hx, -hy, -hz))),
            ((1, 0, 0), ((hx, -hy, -hz), (hx, hy, -hz), (hx, hy, hz), (hx, -hy, hz))),
            ((-1, 0, 0), ((-hx, -hy, -hz), (-hx, -hy, hz), (-hx, hy, hz), (-hx, hy, -hz))),
        )
        for normal, esquinas in caras:
            base = len(self.vertices)
            arriba = normal == (0, 1, 0)
            tono = tapa if (arriba and tapa is not None) else color
            for (x, y, z) in esquinas:
                self.vertices.append(p(x, y, z))
                self.normales.append(n(*normal))
                f = 1.0 if arriba else degradado[0] + (degradado[1] - degradado[0]) * (y + hy) / (alto or 1.0)
                self.colores.append((min(1.5, tono[0] / 255 * f), min(1.5, tono[1] / 255 * f), min(1.5, tono[2] / 255 * f), 1.0))
            self.triangulos += self._cuad(base, normal, esquinas, giro)

    @staticmethod
    def _cuad(base, normal, esquinas, giro):
        # El orden (a, b, c) debe dejar la cara frontal hacia afuera con la regla de props_mundo._orientar:
        # normal = cross(c - a, b - a) debe apuntar hacia `normal`. Se decide con las esquinas locales.
        a, b, c, d = esquinas
        u = tuple(c[i] - a[i] for i in range(3))
        v = tuple(b[i] - a[i] for i in range(3))
        cruz = (u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0])
        if sum(cruz[i] * normal[i] for i in range(3)) >= 0:
            return [(base, base + 1, base + 2), (base, base + 2, base + 3)]
        return [(base, base + 2, base + 1), (base, base + 3, base + 2)]

    # Suma una props_mundo.Malla (triángulos sueltos con normales planas y colores por vértice).
    def malla(self, m):
        i0 = len(self.vertices)
        n = len(m.vertices)
        if not n:
            return
        self.vertices.extend(m.vertices)
        self.normales.extend(m.normales)
        self.colores.extend(m.colores)
        self.triangulos.extend((i0 + k, i0 + k + 1, i0 + k + 2) for k in range(0, n, 3))

    def volcar_a_geom(self, nombre="acumulado", tanda=TANDA_VERTICES):
        """Generador (ver escribir_geom): GeomNode con todo lo acumulado, o None si está vacío."""
        return (yield from escribir_geom(nombre, self.vertices, self.normales, self.colores, self.triangulos,
                                         self.uvs, tanda))


def nodo_de(geom_node, nombre="geom"):
    """NodePath suelto (sin padre) de un GeomNode."""
    return NodePath(geom_node)
