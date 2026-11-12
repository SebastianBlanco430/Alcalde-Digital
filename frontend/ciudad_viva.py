# Ciudad viva (punto 5 del plan final): la ciudad CAMBIA DE APARIENCIA con los indicadores, sin leer números y sin saltos.
# Lo que decide qué se ve es backend/logica/ciudad_viva_calculos.py (puro, con pruebas); este módulo lo dibuja. Lo instala
# frontend/registro_ciudad_viva.py (por frontend/extensiones.py) y NO toca ninguna clase existente.
#
# LEE el Ambiente suavizado de frontend/ambiente_vivo.py (obtener()): no crea otro AmbienteSuave ni lo alimenta.
#
# 1. ATMÓSFERA (cada ≤ 0,5 s y solo si cambió de verdad):
#      luz     ciudad.luz.color y ciudad.ambiente.color (la DIRECCIÓN del sol no se toca: las sombras horneadas siguen valiendo)
#      cielo   ciudad.cielo.color (factor sobre los colores por vértice del domo: sol, nubes, cerros y mar se tiñen juntos)
#      niebla  frontend.niebla.activar_niebla(color, fin, intensidad) con color = horizonte x tinte del cielo: cielo y niebla
#              siguen siendo el MISMO color (sin costura). scene.fog_color/fog_density recorren las entidades que ya existen y
#              cada chunk nuevo copia el valor al instalarse (ciudad_chunks._aplicar_niebla), así que llegan a todos.
#              Si otro módulo vuelve a llamar activar_niebla con sus valores (al entrar al mundo), se detecta y se reaplica.
#    No hay tinte global por posproceso: el FilterManager es de frontend/daltonismo.
# 2. CAPAS (objetos pequeños, SIN reconstruir chunks): piscinas fijas de entidades creadas UNA vez, repartidas entre sitios
#    fijos (azar de frontend/azar_fijo) cercanos a la cámara, que aparecen y desaparecen con fundido de escala:
#      basura (bolsas, papeles, cajas) · grafitis en paredes · carteles torcidos de «sin conexión» · flores vivas o marchitas ·
#      guirnaldas con banderines y bombillas cálidas entre farolas · farolas apagadas (capuchón oscuro sobre el foco) ·
#      bancos de plaza ocupados · corros de gente charlando en las plazas.
#    Son decorado: sin colisión, sin tocar el backend, el azar de favela_calculos / props_mundo ni los archivos de NPC.
# Rendimiento: lo único por frame es el fundido de las ranuras que están cambiando; el reparto de sitios corre cada ~0,3 s y
# solo si la cámara se movió o cambió el Ambiente. Cero entidades nuevas tras el arranque.

import math
import sys

from backend.logica import ciudad_viva_calculos as cv
from backend.logica import etapas_final
from frontend import ambiente_vivo, estilo
from frontend.contorno_calculos import realzar_color
from frontend.azar_fijo import azar_de
from frontend.props_mundo import Malla, caja, icosfera, prisma

PERIODO_ATMOSFERA = 0.5          # s entre dos revisiones de luz/cielo/niebla
PERIODO_CAPAS = 0.3              # s entre dos repartos de sitios
MOVIMIENTO_CAPAS = 1.5           # m que debe moverse la cámara para repartir de nuevo (si el Ambiente no cambió)
TINTE_OBJETOS = 0.88             # los objetos de las capas no tienen sombreado: se bajan un poco para casar con la ciudad
ALTURA_ACERA = 0.19              # m sobre el terreno de las aceras (ciudad_3d: ALTO_ACERA 0.20)
ALTURA_PLAZA = 0.16
ALTURA_FOCO = 4.25               # m del foco de la farola sobre el suelo (objetos_chunk.farola: suelo - 0.1 + 4.35)
ALTURA_GUIRNALDA = 3.75          # m a los que se cuelga la guirnalda (algo por debajo del foco)
SALES = {"basura": 1.0, "flores": 2.0, "marchitas": 6.0, "carteles": 4.0, "apagados": 5.0, "bancos": 8.0, "corros": 9.0,
         "guirnaldas": 11.0, "grafitis": 3.0}


def _aviso(texto):
    print(f"[ciudad_viva] {texto}", file=sys.stderr)


def _tono(c, f):
    return tuple(min(255, int(v * f)) for v in c)


def _desplazar(x, z, dx, dz, giro):
    """(x, z) mundo de un punto local (dx, dz) de un objeto en (x, z) girado `giro` grados (convención de Ursina)."""
    s, c = math.sin(math.radians(giro)), math.cos(math.radians(giro))
    return x + dx * c + dz * s, z - dx * s + dz * c


# -- Mallas de las piezas (se construyen UNA vez por ranura; todo mira hacia +z local y tiene el origen en el suelo) ----------


class Dibujo(Malla):
    """Malla con sólidos (Malla.agregar) y además triángulos y trazos planos de doble cara (pintadas, banderines, carteles)."""

    def __init__(self):
        super().__init__()
        self.transformar = None            # opcional: función de punto 3D -> punto 3D (p. ej. un giro del cartel)

    def tri(self, a, b, c, color):
        if self.transformar is not None:
            a, b, c = self.transformar(a), self.transformar(b), self.transformar(c)
        col = (color[0] / 255, color[1] / 255, color[2] / 255, 1.0)
        for p in ((a, b, c), (a, c, b)):
            for q in p:
                self.vertices.append(q)
                self.normales.append((0.0, 1.0, 0.0))
                self.colores.append(col)

    def quad(self, a, b, c, d, color):
        self.tri(a, b, c, color)
        self.tri(a, c, d, color)

    def trazo(self, p0, p1, grosor, color, z=0.03):
        dx, dy = p1[0] - p0[0], p1[1] - p0[1]
        largo = math.hypot(dx, dy) or 1.0
        nx, ny = -dy / largo * grosor / 2, dx / largo * grosor / 2
        self.quad((p0[0] + nx, p0[1] + ny, z), (p0[0] - nx, p0[1] - ny, z), (p1[0] - nx, p1[1] - ny, z), (p1[0] + nx, p1[1] + ny, z), color)

    def polilinea(self, puntos, grosor, color, z=0.03, cerrada=False):
        pares = list(zip(puntos, puntos[1:] + (puntos[:1] if cerrada else [])))
        for a, b in pares:
            self.trazo(a, b, grosor, color, z)

    def relleno(self, puntos, color, z=0.03):
        cx = sum(p[0] for p in puntos) / len(puntos)
        cy = sum(p[1] for p in puntos) / len(puntos)
        for a, b in zip(puntos, puntos[1:] + puntos[:1]):
            self.tri((cx, cy, z), (a[0], a[1], z), (b[0], b[1], z), color)


def _circulo(cx, cy, r, n=10, deformar=0.0, semilla=0.0):
    return [(cx + r * (1 + deformar * (azar_de(k, semilla) - 0.5)) * math.cos(2 * math.pi * k / n),
             cy + r * (1 + deformar * (azar_de(k, semilla) - 0.5)) * math.sin(2 * math.pi * k / n)) for k in range(n)]


def mesh_bolsa(v):
    d = Dibujo()
    c = ((28, 32, 36), (46, 84, 58), (206, 210, 220), (60, 60, 112))[v % 4]
    d.agregar(icosfera(1), (0, 0.22, 0), (0.66, 0.5, 0.58), v * 37, c, (0.7, 1.1), 0.1)
    d.agregar(icosfera(0), (0.05, 0.5, 0.0), (0.2, 0.18, 0.2), 0, _tono(c, 1.25), (0.9, 1.1))
    d.agregar(icosfera(1), (0.52, 0.13, 0.22), (0.4, 0.3, 0.36), v * 11, _tono(c, 0.9), (0.7, 1.1), 0.1)
    return d.mesh()


def mesh_papeles(v):
    d = Dibujo()
    for k, (dx, dz, col) in enumerate(((0.0, 0.0, (238, 234, 222)), (0.35, 0.22, (214, 210, 196)), (-0.3, 0.3, (244, 206, 120)))):
        d.agregar(caja(), (dx, 0.012, dz), (0.4, 0.02, 0.28), 40 * k + v * 23, col, (0.9, 1.05))
    d.agregar(icosfera(0), (-0.25, 0.1, -0.2), (0.22, 0.2, 0.22), v * 7, (226, 224, 214), (0.8, 1.1), 0.15)
    d.agregar(prisma(8, 0.5, 0.36), (0.45, 0.0, -0.3), (0.2, 0.28, 0.2), 0, (216, 62, 52), (0.8, 1.1))
    return d.mesh()


def mesh_caja(v):
    d = Dibujo()
    d.agregar(caja(), (0, 0.22, 0), (0.66, 0.44, 0.52), v * 29, (180, 138, 88), (0.8, 1.05), 0.08)
    d.agregar(caja(), (0.0, 0.45, -0.28), (0.62, 0.025, 0.26), v * 29, (160, 120, 74), (0.9, 1.0), 0.0, 38)
    d.agregar(caja(), (0.62, 0.16, 0.3), (0.42, 0.32, 0.34), v * 29 + 31, (170, 130, 82), (0.8, 1.05), 0.08)
    return d.mesh()


PALETA_PINTADA = ((236, 52, 146), (40, 204, 232), (252, 222, 48), (250, 128, 36))
OSCURO_PINTADA = (22, 22, 28)


def mesh_grafiti(v):
    d = Dibujo()
    c, c2 = PALETA_PINTADA[v % 4], PALETA_PINTADA[(v + 1) % 4]
    if v % 4 == 0:                                      # zigzag
        pts = [(-0.9, -0.3), (-0.55, 0.35), (-0.2, -0.3), (0.15, 0.4), (0.5, -0.3), (0.85, 0.3)]
        d.polilinea(pts, 0.22, OSCURO_PINTADA, 0.020)
        d.polilinea(pts, 0.12, c, 0.028)
        d.polilinea([(x, y - 0.45) for x, y in pts[:4]], 0.08, c2, 0.028)
    elif v % 4 == 1:                                    # estrella con aro
        for k in range(8):
            a = math.pi * k / 4
            d.trazo((0, 0), (0.5 * math.cos(a), 0.5 * math.sin(a)), 0.2, OSCURO_PINTADA, 0.020)
        for k in range(8):
            a = math.pi * k / 4
            d.trazo((0, 0), (0.5 * math.cos(a), 0.5 * math.sin(a)), 0.1, c, 0.028)
        d.polilinea(_circulo(0, 0, 0.72, 14), 0.2, OSCURO_PINTADA, 0.020, True)
        d.polilinea(_circulo(0, 0, 0.72, 14), 0.1, c2, 0.028, True)
    elif v % 4 == 2:                                    # X, O y subrayado
        for a, b in (((-0.9, -0.35), (-0.3, 0.35)), ((-0.9, 0.35), (-0.3, -0.35))):
            d.trazo(a, b, 0.22, OSCURO_PINTADA, 0.020)
            d.trazo(a, b, 0.12, c, 0.028)
        d.polilinea(_circulo(0.45, 0, 0.4, 10), 0.22, OSCURO_PINTADA, 0.020, True)
        d.polilinea(_circulo(0.45, 0, 0.4, 10), 0.12, c2, 0.028, True)
        d.trazo((-1.0, -0.62), (0.95, -0.55), 0.1, c, 0.028)
    else:                                               # mancha con goteras
        d.relleno(_circulo(0, 0.1, 0.52, 9, 0.5, v), OSCURO_PINTADA, 0.020)
        d.relleno(_circulo(0, 0.1, 0.42, 9, 0.5, v + 1), c, 0.028)
        for k, x in enumerate((-0.3, 0.05, 0.3)):
            largo = 0.35 + 0.35 * azar_de(k, v)
            d.trazo((x, -0.2), (x, -0.2 - largo), 0.09, c, 0.027)
        d.relleno(_circulo(-0.15, 0.2, 0.18, 7), c2, 0.03)
    return d.mesh()


def mesh_cartel(v):
    """Poste con un cartel torcido de «sin conexión»: icono de wifi tachado con una raya roja."""
    d = Dibujo()
    d.agregar(prisma(6, 0.5, 0.4), (0, -0.05, 0), (0.1, 2.35, 0.1), 0, (112, 114, 124), (0.8, 1.1))
    ang = math.radians(-15 if v % 2 else 13)
    pivote = (0.0, 2.1)

    def girar(p):
        x, y = p[0] - pivote[0], p[1] - pivote[1]
        return (pivote[0] + x * math.cos(ang) - y * math.sin(ang), pivote[1] + x * math.sin(ang) + y * math.cos(ang), p[2])

    d.transformar = girar
    d.quad((-0.62, 1.68, 0.075), (0.62, 1.68, 0.075), (0.62, 2.52, 0.075), (-0.62, 2.52, 0.075), (46, 50, 64))
    d.polilinea([(-0.58, 1.72), (0.58, 1.72), (0.58, 2.48), (-0.58, 2.48)], 0.05, (200, 204, 214), 0.085, True)
    for r in (0.16, 0.3, 0.44):
        arco = [(r * math.cos(math.radians(a)), 1.92 + r * math.sin(math.radians(a))) for a in range(40, 141, 20)]
        d.polilinea(arco, 0.07, (236, 238, 244), 0.09)
    d.relleno(_circulo(0, 1.9, 0.065, 8), (236, 238, 244), 0.09)
    d.trazo((-0.5, 1.8), (0.5, 2.42), 0.1, (214, 48, 48), 0.1)
    return d.mesh()


PALETA_FLORES = ((222, 64, 64), (248, 206, 56), (240, 240, 232), (214, 70, 160), (250, 140, 60), (150, 112, 204))


def mesh_flores(v, marchita):
    d = Dibujo()
    d.agregar(caja(), (0, 0.2, 0), (0.95, 0.4, 0.4), 0, (172, 94, 66), (0.8, 1.05), 0.06)
    d.agregar(caja(), (0, 0.405, 0), (0.86, 0.04, 0.3), 0, (70, 48, 34), (0.9, 1.0))
    verde = (58, 128, 56)
    for k in range(8):
        x = -0.38 + 0.76 * k / 7
        z0 = (azar_de(k, v) - 0.5) * 0.16
        h = 0.35 + 0.32 * azar_de(v + k, 3.1)
        giro = 360 * azar_de(k + 2.0, v)
        if not marchita:
            d.agregar(prisma(5, 0.5, 0.4), (x, 0.4, z0), (0.03, h, 0.03), 0, verde, (0.8, 1.1))
            d.agregar(icosfera(0), (x, 0.4 + h, z0), 0.2 + 0.07 * azar_de(k, 8.8), 0, PALETA_FLORES[(v + k) % len(PALETA_FLORES)], (0.9, 1.1))
            if k % 2 == 0:
                d.agregar(icosfera(0), (x + 0.07, 0.5, z0), (0.2, 0.08, 0.1), giro, verde, (0.8, 1.1))
        else:
            inc = 50 + 25 * azar_de(k, v + 4.4)
            dx, dz = _desplazar(0, 0, 0, math.sin(math.radians(inc)) * h, giro)
            d.agregar(prisma(5, 0.5, 0.4), (x, 0.4, z0), (0.03, h, 0.03), giro, (112, 96, 60), (0.8, 1.1), 0.0, inc)
            d.agregar(icosfera(0), (x + dx, 0.4 + h * math.cos(math.radians(inc)), z0 + dz), 0.15, 0, (118, 92, 60), (0.8, 1.0))
    return d.mesh()


PALETA_BANDERINES = ((222, 64, 64), (248, 206, 56), (44, 138, 214), (60, 170, 90), (250, 130, 50), (214, 70, 160))
LUZ_CALIDA = (255, 226, 150)


def mesh_guirnalda(largo, v):
    """Guirnalda de `largo` m a lo largo de +x (de 0 a largo), con la comba hacia abajo, banderines de colores y bombillas cálidas."""
    d = Dibujo()
    comba = 0.06 * largo + 0.2
    n = max(16, int(largo * 1.5))

    def punto(t):
        return (largo * t, -comba * 4.0 * t * (1.0 - t))

    pts = [punto(i / n) for i in range(n + 1)]
    for a, b in zip(pts, pts[1:]):                      # cuerda: dos cintas cruzadas para que se vea desde cualquier lado
        d.quad((a[0], a[1], -0.015), (b[0], b[1], -0.015), (b[0], b[1], 0.015), (a[0], a[1], 0.015), (70, 56, 44))
        d.quad((a[0], a[1] + 0.015, 0), (b[0], b[1] + 0.015, 0), (b[0], b[1] - 0.015, 0), (a[0], a[1] - 0.015, 0), (70, 56, 44))
    cuantos = max(6, int(largo / 0.9))
    for k in range(cuantos):
        t = (k + 0.5) / cuantos
        x, y = punto(t)
        ancho = min(0.2, 0.5 * largo / cuantos)
        c = PALETA_BANDERINES[(k + v) % len(PALETA_BANDERINES)]
        d.tri((x - ancho, y, 0.0), (x + ancho, y, 0.0), (x, y - 0.62 * ancho / 0.2 * 0.75, 0.0), c)
        d.tri((x, y, -ancho), (x, y, ancho), (x, y - 0.62 * ancho / 0.2 * 0.75, 0.0), _tono(c, 0.9))
        if k % 2 == 1:
            x2, y2 = punto(t + 0.5 / cuantos)
            d.agregar(icosfera(0), (x2, y2 - 0.12, 0.0), 0.2, 0, LUZ_CALIDA, (1.0, 1.0))
    return d.mesh()


PIELES = ((234, 192, 160), (196, 140, 104), (134, 92, 66), (246, 208, 178))
CAMISAS = ((214, 80, 70), (60, 120, 190), (240, 200, 70), (90, 160, 100), (180, 90, 170), (240, 240, 235), (240, 140, 60))
PANTALONES = ((52, 62, 96), (86, 74, 60), (40, 44, 52), (110, 120, 134))


def _persona(d, ox, oz, giro, k, sentada):
    """Una figura de bloques en (ox, oz) girada `giro` (su frente = +z local). Sentada: origen = asiento; de pie: origen = suelo."""
    piel, camisa, pantalon = PIELES[k % 4], CAMISAS[(k * 3 + 1) % len(CAMISAS)], PANTALONES[(k + 1) % 4]

    def p(dx, y, dz):
        x, z = _desplazar(ox, oz, dx, dz, giro)
        return (x, y, z)

    if sentada:
        d.agregar(caja(), p(0, 0.08, 0.2), (0.34, 0.15, 0.46), giro, pantalon, (0.8, 1.05))
        for lado in (-0.09, 0.09):
            d.agregar(caja(), p(lado, -0.22, 0.42), (0.14, 0.5, 0.14), giro, pantalon, (0.8, 1.05))
        d.agregar(caja(), p(0, 0.34, -0.06), (0.38, 0.52, 0.22), giro, camisa, (0.8, 1.1))
        for lado in (-0.25, 0.25):
            d.agregar(caja(), p(lado, 0.24, 0.02), (0.1, 0.4, 0.12), giro, camisa, (0.8, 1.05))
        d.agregar(icosfera(1), p(0, 0.76, -0.02), (0.27, 0.3, 0.27), giro, piel, (0.85, 1.1))
        d.agregar(icosfera(0), p(0, 0.86, -0.05), (0.3, 0.16, 0.3), giro, (50, 38, 30), (0.8, 1.1))
    else:
        for lado in (-0.1, 0.1):
            d.agregar(caja(), p(lado, 0.4, 0), (0.15, 0.8, 0.17), giro, pantalon, (0.8, 1.05))
        d.agregar(caja(), p(0, 1.12, 0), (0.42, 0.58, 0.24), giro, camisa, (0.8, 1.1))
        for lado in (-0.27, 0.27):
            d.agregar(caja(), p(lado, 1.1, 0), (0.1, 0.52, 0.12), giro, camisa, (0.8, 1.05))
        d.agregar(icosfera(1), p(0, 1.58, 0), (0.28, 0.31, 0.28), giro, piel, (0.85, 1.1))
        d.agregar(icosfera(0), p(0, 1.68, -0.02), (0.31, 0.16, 0.31), giro, (50, 38, 30), (0.8, 1.1))


def mesh_sentados(v):
    """Una o dos personas sentadas en un banco de 1,8 m (el frente mira a +z local; el banco se coloca girado 180)."""
    d = Dibujo()
    if v % 3 == 1:
        _persona(d, -0.45, 0.0, 0.0, v, True)
        _persona(d, 0.45, 0.0, 0.0, v + 2, True)
    else:
        _persona(d, -0.4 if v % 3 == 0 else 0.4, 0.0, 0.0, v, True)
        d.agregar(caja(), (0.4 if v % 3 == 0 else -0.4, 0.14, 0.0), (0.3, 0.26, 0.2), 0, (150, 70, 60), (0.8, 1.1))
    return d.mesh()


def mesh_corro(v):
    """Cinco personas en rueda mirando al centro, con una bocina portátil en medio."""
    d = Dibujo()
    n = 5
    for k in range(n):
        a = 2 * math.pi * (k + 0.3 * azar_de(k, v)) / n
        giro = math.degrees(math.atan2(-math.cos(a), -math.sin(a)))
        _persona(d, 1.15 * math.cos(a), 1.15 * math.sin(a), giro, v + k, False)
    d.agregar(caja(), (0, 0.18, 0), (0.34, 0.36, 0.24), 20 * v, (44, 46, 56), (0.8, 1.1))
    d.agregar(icosfera(0), (0, 0.2, 0.13), 0.18, 0, (236, 200, 70), (0.9, 1.1))
    return d.mesh()


def mesh_capuchon(v):
    d = Dibujo()
    d.agregar(icosfera(1), (0, 0.0, 0), (0.68, 0.62, 0.68), 0, (46, 48, 58), (0.7, 1.1))
    return d.mesh()


# -- Capas de los finales por etapas: fuego, rodadores y fiesta (docs/PLAN_FINALES_HISTORIA.md §2.2) ---------------------------
# Misma línea que el resto: low-poly, color plano sin sombreado y contorno de tinta. El contorno es el casco invertido de
# siempre, pero metido en la MISMA malla (las caras del casco van al revés, así el recorte de caras traseras deja ver solo
# el borde): una entidad por pieza, sin atributos de render nuevos.

GROSOR_TINTA_ETAPA = 0.035       # m por lado del casco de tinta de estas piezas
SALES_ETAPA = {"fuego": 13.0, "rodadores": 14.0, "fiesta": 15.0}
ROJO_FUEGO = realzar_color(estilo.ESTADO_ERROR)
NARANJA_FUEGO = realzar_color((240, 130, 40))
AMARILLO_FUEGO = realzar_color(estilo.ACENTO_PRIMARIO)
HUMO = (92, 92, 102)
MADERA_QUEMADA = (48, 38, 34)
SECO = realzar_color((158, 118, 70))
SECO_OSCURO = realzar_color((104, 76, 46))
POSTE_FIESTA = (70, 56, 44)
ALTO_FIESTA = 4.1                # m a los que cuelgan los banderines que cruzan la calle
PASO_CALLE_ETAPA = 26.0          # m entre dos sitios de rodador / de fiesta a lo largo de una calle
VELOCIDAD_RODADOR = 3.2          # m/s
CONFETI_POR_NUBE = 14
NUBES_CONFETI = 3
ALTO_CONFETI = 5.0               # m desde los que cae el confeti
SEGUNDOS_CONFETI = 5.0           # s de una caída


class DibujoTinta(Dibujo):
    """Dibujo cuyos sólidos llevan contorno de tinta (casco invertido en la misma malla)."""

    def solido(self, forma, posicion, escala=1.0, giro=0.0, color=(255, 255, 255), degradado=(0.9, 1.05), inclinacion=0.0,
               apoyado=False):
        """`apoyado`: el sólido nace en su base (prisma) y no en su centro; el casco baja un grosor para envolverlo."""
        if isinstance(escala, (int, float)):
            escala = (escala, escala, escala)
        g = GROSOR_TINTA_ETAPA
        desde = len(self.vertices)
        base = (posicion[0], posicion[1] - (g if apoyado else 0.0), posicion[2])
        self.agregar(forma, base, tuple(e + 2 * g for e in escala), giro, estilo.TINTA, (1.0, 1.0), 0.0, inclinacion)
        for i in range(desde, len(self.vertices), 3):           # caras al revés: solo se ve el borde
            self.vertices[i + 1], self.vertices[i + 2] = self.vertices[i + 2], self.vertices[i + 1]
            self.colores[i + 1], self.colores[i + 2] = self.colores[i + 2], self.colores[i + 1]
        self.agregar(forma, posicion, escala, giro, color, degradado, 0.0, inclinacion)

    def banderin(self, x, y, ancho, alto, color):
        """Banderín triangular plano (mira a ±z) con borde de tinta: tinta en medio y el color a cada lado."""
        b = 0.045
        self.tri((x - ancho - b, y + b, 0.0), (x + ancho + b, y + b, 0.0), (x, y - alto - 2 * b, 0.0), estilo.TINTA)
        for z in (-0.012, 0.012):
            self.tri((x - ancho, y, z), (x + ancho, y, z), (x, y - alto, z), color)


def mesh_fuego(v):
    """Hoguera de cómic: leños cruzados, llamas en tres tonos planos (rojo, naranja, amarillo) y tres bocanadas de humo."""
    d = DibujoTinta()
    for giro in (25 + 40 * v, -50 + 40 * v):
        d.solido(caja(), (0, 0.08, 0), (0.95, 0.14, 0.16), giro, MADERA_QUEMADA)
    cono = prisma(5, 0.5, 0.03)
    for k in range(3):                                   # llamas rojas de fuera
        a = 2 * math.pi * (k + 0.25 * v) / 3
        d.solido(cono, (0.26 * math.cos(a), 0.1, 0.26 * math.sin(a)), (0.46, 0.85 + 0.2 * azar_de(k, v + 1.3), 0.46), 40 * k,
                 ROJO_FUEGO, (1.0, 1.0), apoyado=True)
    d.solido(cono, (0, 0.12, 0), (0.5, 1.35, 0.5), 18 * v, NARANJA_FUEGO, (1.0, 1.0), apoyado=True)
    for k in range(3):                                   # lenguas amarillas, entre las rojas
        a = 2 * math.pi * (k + 0.5 + 0.25 * v) / 3
        d.agregar(cono, (0.34 * math.cos(a), 0.12, 0.34 * math.sin(a)), (0.24, 0.5 + 0.15 * azar_de(k, v + 7.7), 0.24), 30 * k,
                  AMARILLO_FUEGO, (1.0, 1.0))
    for k, (y, r) in enumerate(((1.6, 0.34), (2.0, 0.27), (2.35, 0.19))):
        d.solido(icosfera(1), (0.14 * (k - 1) + 0.08 * v, y, 0.1 * (1 - k)), (r, r * 0.8, r), 50 * k, _tono(HUMO, 1.0 + 0.12 * k),
                 (0.95, 1.05))
    return d.mesh()


def mesh_rodador(v):
    """Arbusto seco que rueda: bola de pocas caras con ramas que la atraviesan. Origen en el centro (radio ≈ 0,5 m)."""
    d = DibujoTinta()
    d.solido(icosfera(0), (0, 0, 0), (0.86, 0.8, 0.86), 20 * v, SECO, (0.85, 1.05))
    for k in range(7):
        giro = 360 * azar_de(k, v + 2.2)
        inc = 180 * azar_de(k + 5.0, v) - 90
        d.agregar(caja(), (0, 0, 0), (0.05, 0.05, 1.12), giro, SECO_OSCURO, (1.0, 1.0), 0.0, inc)
    return d.mesh()


def mesh_fiesta(largo, v=0):
    """Cuerda de banderines grandes de `largo` m (centrada, a lo largo de x) entre dos postes: cruza la calle de acera a acera."""
    d = DibujoTinta()
    medio = largo / 2.0
    for lado in (-medio, medio):
        d.solido(prisma(6, 0.5, 0.5), (lado, -0.5, 0), (0.14, ALTO_FIESTA + 0.6, 0.14), 0, POSTE_FIESTA, (0.9, 1.05), apoyado=True)
        d.solido(icosfera(0), (lado, ALTO_FIESTA + 0.2, 0), 0.3, 0, AMARILLO_FUEGO, (1.0, 1.0))
    comba = 0.05 * largo + 0.25
    n = max(12, int(largo * 1.5))

    def punto(t):
        return (-medio + largo * t, ALTO_FIESTA - comba * 4.0 * t * (1.0 - t))

    pts = [punto(i / n) for i in range(n + 1)]
    for a, b in zip(pts, pts[1:]):
        d.quad((a[0], a[1] + 0.02, 0), (b[0], b[1] + 0.02, 0), (b[0], b[1] - 0.02, 0), (a[0], a[1] - 0.02, 0), estilo.TINTA)
        d.quad((a[0], a[1], -0.02), (b[0], b[1], -0.02), (b[0], b[1], 0.02), (a[0], a[1], 0.02), estilo.TINTA)
    cuantos = max(5, int(largo / 0.8))
    for k in range(cuantos):
        x, y = punto((k + 0.5) / cuantos)
        d.banderin(x, y, 0.26, 0.5, realzar_color(PALETA_BANDERINES[(k + v) % len(PALETA_BANDERINES)]))
    return d.mesh()


def mesh_confeti(largo, v):
    """Una «nube» plana de papelitos de colores repartidos sobre la calle (cae entera y vuelve a empezar)."""
    d = Dibujo()
    for k in range(CONFETI_POR_NUBE):
        x = (azar_de(k, v + 0.5) - 0.5) * largo
        z = (azar_de(k + 3.0, v + 1.5) - 0.5) * 9.0
        y = (azar_de(k + 6.0, v + 2.5) - 0.5) * 1.2
        a = 2 * math.pi * azar_de(k + 9.0, v)
        ux, uz = 0.09 * math.cos(a), 0.09 * math.sin(a)
        alto = 0.06 + 0.05 * azar_de(k, v + 4.0)
        c = realzar_color(PALETA_BANDERINES[(k + v) % len(PALETA_BANDERINES)])
        d.quad((x - ux, y - alto, z - uz), (x + ux, y - alto * 0.4, z + uz), (x + ux, y + alto, z + uz), (x - ux, y + alto * 0.4, z - uz), c)
    return d.mesh()


def sitios_de_etapa(mundo, sitios):
    """Sitios fijos de las capas de etapa: fuego sobre parte de los puntos de basura (basura ardiendo), y rodadores y fiesta
    en el eje de las calles, cada PASO_CALLE_ETAPA m. Determinista."""
    suelo = mundo.altura
    out = {"fuego": [], "rodadores": [], "fiesta": []}
    for p in sitios["basura"]:
        if p.extra % 5 == 0:
            out["fuego"].append(_punto(p.x, p.z, cv.azar_sitio(p.x, p.z, SALES_ETAPA["fuego"]), p.y, p.giro, p.extra // 5))
    for (ax, az), (bx, bz) in _segmentos(mundo):
        dx, dz = bx - ax, bz - az
        largo = math.hypot(dx, dz)
        if largo < 12.0:
            continue
        ux, uz = dx / largo, dz / largo
        n = max(1, int(round(largo / PASO_CALLE_ETAPA)))
        for k in range(n):
            t = (k + 0.5) / n
            x, z = ax + dx * t, az + dz * t
            if not _libre(mundo, x, z):
                continue
            recorrido = max(8.0, min(18.0, 0.7 * largo / n))
            out["rodadores"].append(_punto(x, z, cv.azar_sitio(x, z, SALES_ETAPA["rodadores"]), suelo(x, z) + 0.5,
                                           math.degrees(math.atan2(ux, uz)), (ux, uz, recorrido)))
            out["fiesta"].append(_punto(x, z, cv.azar_sitio(x, z, SALES_ETAPA["fiesta"]), suelo(x, z),
                                        math.degrees(math.atan2(ux, uz)), 0))      # su +z local = la calle; la cuerda la cruza
    return out


# -- Piscinas ----------------------------------------------------------------------------------------------------------------


class Grupo:
    """Una piscina fija de ranuras (entidades creadas una vez) para UN modelo, repartida entre los sitios de su rejilla.
    sitios = [datos] con datos.x, datos.z, datos.u (cualquier objeto con esos campos); `colocar(entidad, dato, es)` pone la
    entidad en su sitio con la escala de fundido `es` (0..1)."""

    def __init__(self, raiz, nombre, fabrica, n, sitios, radio, colocar, colocar_inicial, maximo=None):
        from ursina import Entity
        from ursina.shaders import unlit_shader
        self.nombre, self.radio, self.sitios = nombre, radio, sitios
        self.maximo = maximo or n
        self.colocar, self.colocar_inicial = colocar, colocar_inicial
        self.rejilla = cv.Rejilla(32.0)
        for i, s in enumerate(sitios):
            self.rejilla.agregar(s.x, s.z, (i, s.x, s.z, s.u))
        self.ranuras = cv.Ranuras(n)
        self.entidades = []
        for k in range(n):
            e = Entity(parent=raiz, model=fabrica(), shader=unlit_shader, unlit=True, enabled=False, name=f"viva_{nombre}_{k}")
            e.ignore = True
            self.entidades.append(e)
        self.previos = set()

    def repartir(self, x, z, cantidad):
        """Elige los sitios que se quieren ahora y asigna ranuras. Devuelve True si hay algo animándose."""
        if self.sitios:
            candidatos = list(self.rejilla.cerca(x, z, self.radio * 1.2))
            elegidos = cv.elegir_sitios(candidatos, x, z, self.radio, cantidad, self.previos, self.maximo)
        else:
            elegidos = []
        self.previos = set(elegidos)
        for k, i in self.ranuras.actualizar(elegidos):
            e = self.entidades[k]
            self.colocar_inicial(e, self.sitios[i])
            self.colocar(e, self.sitios[i], 0.0)
            e.enabled = True
        return self.ranuras.animando()

    def avanzar(self, dt):
        for k, liberada in self.ranuras.avanzar(dt):
            e = self.entidades[k]
            if liberada:
                e.enabled = False
            else:
                self.colocar(e, self.sitios[self.ranuras.sitio[k]], cv.escala_fundida(self.ranuras.f[k]))
        return self.ranuras.animando()

    def visibles(self):
        return sum(1 for k, s in enumerate(self.ranuras.sitio) if s is not None and self.ranuras.f[k] > 0.0)


class Punto(tuple):
    """Sitio genérico con campos nombrados (x, z, u, y, giro, extra): tupla ligera."""
    __slots__ = ()
    x = property(lambda s: s[0])
    z = property(lambda s: s[1])
    u = property(lambda s: s[2])
    y = property(lambda s: s[3])
    giro = property(lambda s: s[4])
    extra = property(lambda s: s[5])


def _punto(x, z, u, y=0.0, giro=0.0, extra=None):
    return Punto((x, z, u, y, giro, extra))


def _fija_uniforme(entidad, dato):
    entidad.position = (dato.x, dato.y, dato.z)
    entidad.rotation_y = dato.giro


def _coloca_uniforme(entidad, dato, es):
    entidad.scale = max(0.001, es)


def _coloca_guirnalda(entidad, dato, es):
    entidad.scale = (dato.extra[0], max(0.001, es), max(0.001, es))


def _fija_guirnalda(entidad, dato):
    entidad.position = (dato.x, dato.y, dato.z)
    entidad.rotation = (0, dato.giro, -dato.extra[1])      # medido en ventana: el roll positivo baja el extremo +x


# -- Construcción de los sitios del mundo ---------------------------------------------------------------------------------


def _segmentos(mundo):
    return [(tuple(mundo.coordenada(a)), tuple(mundo.coordenada(b))) for a, b in mundo.segmentos()]


def _libre(mundo, x, z):
    try:
        return bool(mundo.es_transitable(x, z))
    except Exception:
        return True


def sitios_de_la_ciudad(mundo):
    """Todos los sitios fijos de las capas, a partir del mundo (chico o grande). Devuelve un dict nombre -> [Punto] / datos.
    Determinista: el mismo mundo da siempre los mismos sitios (nada de random)."""
    suelo = mundo.altura
    segs = _segmentos(mundo)
    ancho, radio_plaza = mundo.ancho_calle, mundo.radio_plaza
    plazas = [tuple(mundo.coordenada(lugar)) for lugar in mundo.lugares()]
    obst = mundo.obstaculos()
    out = {k: [] for k in ("basura", "flores", "marchitas", "carteles", "grafitis", "apagados", "bancos", "corros", "guirnaldas")}

    # Aceras y plazas: cada punto se reparte entre basura, flores y carteles (un solo uso por punto, para que no se pisen).
    puntos = [(s.x, s.z, s.giro, ALTURA_ACERA, False) for s in cv.sitios_de_borde(segs, ancho, radio_plaza, paso=4.0)]
    for p in plazas:
        puntos += [(s.x, s.z, s.giro, ALTURA_PLAZA, True) for s in cv.sitios_de_plaza(p, radio_plaza, 14, escalon=1.0)]
    for x, z, giro, alto, en_plaza in puntos:
        if not _libre(mundo, x, z):
            continue
        y = suelo(x, z) + alto
        r = azar_de(x * 1.9, z * 0.7 + 3.3)
        if r < 0.55:
            out["basura"].append(_punto(x, z, cv.azar_sitio(x, z, SALES["basura"]), y, giro, int(azar_de(z, x) * 1000)))
        elif r < 0.85 or (en_plaza and r < 0.93):
            out["flores"].append(_punto(x, z, cv.azar_sitio(x, z, SALES["flores"]), y, giro, int(azar_de(x, z) * 1000)))
            out["marchitas"].append(_punto(x, z, cv.azar_sitio(x, z, SALES["marchitas"]), y, giro, int(azar_de(x, z) * 1000)))
        elif not en_plaza and r < 0.88:
            out["carteles"].append(_punto(x, z, cv.azar_sitio(x, z, SALES["carteles"]), suelo(x, z) + 0.2, giro, int(azar_de(x, z) * 1000)))

    # Grafitis: una pared por casa que mira a una calle, con espacio libre delante.
    casas = [(o.cx, o.cz, o.ancho, o.fondo) for o in obst if o.tipo == "casa" and o.es_caja]
    from frontend.geometria_mundo import apoyo_de_caja
    piso = lambda cx, cz, a, f: apoyo_de_caja(suelo, cx, cz, a, f)[1]        # piso de la casa: el punto más alto de su huella
    for p in cv.paredes_de_calle(casas, segs, ancho, suelo, sal=SALES["grafitis"], piso=piso):
        if not _libre(mundo, p.x + p.nx * 1.0, p.z + p.nz * 1.0):
            continue
        giro = math.degrees(math.atan2(p.nx, p.nz))          # su +z local sale de la pared
        out["grafitis"].append(_punto(round(p.x + p.nx * 0.04, 3), round(p.z + p.nz * 0.04, 3), p.u, p.y0 + 1.1 + 0.6 * azar_de(p.x, p.z), giro, p.v))

    # Farolas: las del mundo; capuchones y guirnaldas.
    farolas = [(o.cx, o.cz) for o in obst if o.tipo == "farola"]
    for x, z in farolas:
        out["apagados"].append(_punto(x, z, cv.azar_sitio(x, z, SALES["apagados"]), suelo(x, z) - 0.1 + ALTURA_FOCO + 0.1, 0.0, 0))
    for i, j in cv.pares_de_farolas(farolas, 6.0, 24.0, 2):
        (ax, az), (bx, bz) = farolas[i], farolas[j]
        ya, yb = suelo(ax, az) - 0.1 + ALTURA_GUIRNALDA, suelo(bx, bz) - 0.1 + ALTURA_GUIRNALDA
        dx, dz, dy = bx - ax, bz - az, yb - ya
        horiz = math.hypot(dx, dz)
        largo = math.hypot(horiz, dy)
        mx, mz = (ax + bx) / 2, (az + bz) / 2
        giro = math.degrees(math.atan2(-dz, dx))
        inclinacion = math.degrees(math.atan2(dy, horiz))
        base = 10.0 if largo < 14.0 else 20.0
        out["guirnaldas"].append(_punto(ax, az, cv.azar_sitio(mx, mz, SALES["guirnaldas"]), ya, giro, (largo / base, inclinacion, base, mx, mz)))

    # Bancos y corros de las plazas.
    for o in obst:
        if o.tipo == "banco":
            out["bancos"].append(_punto(o.cx, o.cz, cv.azar_sitio(o.cx, o.cz, SALES["bancos"]), suelo(o.cx, o.cz) + 0.14 + 0.51, 180.0, int(azar_de(o.cx, o.cz) * 1000)))
    for p in plazas:
        for s in cv.sitios_de_plaza(p, radio_plaza, 2, sal=SALES["corros"], escalon=7.0):
            r = math.hypot(s.x - p[0], s.z - p[1])
            if all(_libre(mundo, s.x + 1.4 * math.cos(a), s.z + 1.4 * math.sin(a)) for a in (0, 1.6, 3.1, 4.7)):
                out["corros"].append(_punto(s.x, s.z, s.u, suelo(s.x, s.z) + ALTURA_PLAZA, s.giro, s.v))
    return out


# -- Niebla sin tirones ------------------------------------------------------------------------------------------------------


class PropagadorNiebla:
    """Cambia la niebla de la escena SIN recorrer todas las entidades de golpe. `scene.fog_color`/`scene.fog_density` de Ursina
    recorren las ~3000 entidades con has_ancestor() (medido: ~50 ms de un solo frame). Aquí: (1) se actualizan de una vez los
    valores de la escena (los chunks que se instalen después copian estos), y (2) las entidades con shader de niebla que YA
    existen reciben los nuevos valores en tandas de POR_FRAME por frame (un paso son ~4 microsegundos por entidad).
    Si Ursina cambiara por dentro (atributos privados ausentes) se usa `activar_niebla`, que hace lo mismo más despacio."""

    POR_FRAME = 120

    def __init__(self):
        self.cola = []
        self.color = None
        self.fin = None
        self._con_niebla = {}               # id(shader) -> ¿su fragment usa fog_color?
        self.lotes = 0

    def _usa_niebla(self, shader):
        k = id(shader)
        if k not in self._con_niebla:
            try:
                self._con_niebla[k] = "fog_color" in (shader.fragment or "")
            except Exception:
                self._con_niebla[k] = False
        return self._con_niebla[k]

    def aplicar(self, color, fin, intensidad):
        """Fija la niebla de la escena ya y deja en cola a las entidades existentes. Devuelve True si fue por el camino rápido."""
        from ursina import Color, scene
        valor = Color(color[0] / 255, color[1] / 255, color[2] / 255, intensidad)
        try:
            if not (hasattr(scene, "_fog_color") and hasattr(scene, "_fog_density") and hasattr(scene, "fog")):
                raise AttributeError("scene sin los atributos de niebla esperados")
            scene._fog_color = valor
            scene.fog.setColor(valor)
            scene._fog_density = (0, fin)
            scene.fog.setLinearRange(0, fin)
        except Exception:
            from frontend.niebla import activar_niebla
            activar_niebla(color=color, fin=fin, intensidad=intensidad)
            return False
        self.color, self.fin = valor, float(fin)
        self.cola = [e for e in scene.entities if e.shader is not None and not e.is_empty() and self._usa_niebla(e.shader)]
        return True

    def avanzar(self):
        """Una tanda de la cola. Devuelve cuántas entidades quedan por actualizar."""
        if not self.cola:
            return 0
        tanda, self.cola = self.cola[:self.POR_FRAME], self.cola[self.POR_FRAME:]
        self.lotes += 1
        for e in tanda:
            try:
                if e.is_empty():          # destruida mientras esperaba en la cola (Panda aborta si se le pide algo a un nodo vacío)
                    continue
                e.set_shader_input("fog_color", self.color)
                e.set_shader_input("fog_end", self.fin)
            except Exception:
                pass                      # entidad destruida mientras esperaba en la cola
        return len(self.cola)


# -- Controlador -------------------------------------------------------------------------------------------------------------


def crear_controlador(escena, atmosfera=True, capas=True):
    from ursina import Color, Entity, camera, scene, time
    from frontend import mundo_config
    from frontend.ciudad_3d import COLOR_LUZ_AMBIENTE, COLOR_LUZ_SOL, rgb_luz
    from frontend.cielo import COLOR_HORIZONTE
    from frontend.niebla import FIN_NIEBLA, INTENSIDAD_NIEBLA, activar_niebla

    class ControladorCiudadViva(Entity):

        def __init__(self, **opciones):
            super().__init__(**opciones)
            self.ignore = False
            self.con_atmosfera, self.con_capas = atmosfera, capas
            self.sol_base, self.ambiente_base = self._colores_de_luz()
            self.fin_base = float(escena._niebla.get("fin", FIN_NIEBLA)) if getattr(escena, "_niebla", None) is not None else FIN_NIEBLA
            self._t_atm = 0.0
            self._t_capas = 0.0
            self._params = None             # últimos parámetros de atmósfera aplicados
            self._niebla = None             # (color, fin, intensidad) que este controlador dejó puestos
            self._pos_capas = None
            self._version_capas = None
            self._cantidades = None
            self._animando = False
            self.con_etapas = etapas_final.activo()      # capas de los finales por etapas (ALCALDE_ETAPAS_FINAL=0 las quita)
            self._grupos_etapa = []                      # [(capa, Grupo)] que se animan cada frame
            self._t_etapa = 0.0
            self.grupos = {}
            self.raiz = Entity(parent=self, name="ciudad_viva_raiz")
            self.raiz.ignore = True
            self.aplicaciones_niebla = 0
            self.propagador = PropagadorNiebla()
            if self.con_capas:
                self._crear_capas()

        # -- Atmósfera --

        @staticmethod
        def _colores_de_luz():
            """Colores REALES de las luces al arrancar (RGB 0-255), no las constantes de ciudad_3d: Ursina crea la
            DirectionalLight sin su `color=` (se asigna antes de que exista la luz de Panda), así que el sol es blanco."""
            def leer(luz, respaldo):
                try:
                    c = luz._light.getColor()
                    return tuple(int(round(c[i] * 255)) for i in range(3))
                except Exception:
                    return respaldo
            return leer(escena.ciudad.luz, COLOR_LUZ_SOL), leer(escena.ciudad.ambiente, COLOR_LUZ_AMBIENTE)

        def _atmosfera(self, amb):
            p = cv.atmosfera(amb, sol=self.sol_base, ambiente=self.ambiente_base, horizonte=COLOR_HORIZONTE,
                             fin=self.fin_base, fuerza=INTENSIDAD_NIEBLA)
            ciudad = escena.ciudad
            if cv.cambio_apreciable(self._params, p):
                self._params = p
                ciudad.luz.color = rgb_luz(p["sol"])
                ciudad.ambiente.color = rgb_luz(p["ambiente"])
                ciudad.cielo.color = Color(p["cielo"][0], p["cielo"][1], p["cielo"][2], 1.0)
                brillo = TINTE_OBJETOS * (0.55 + 0.45 * sum(p["sol"]) / max(1, sum(self.sol_base)))
                self.raiz.color = Color(brillo, brillo, brillo * 1.0, 1.0)
                self._niebla = None
            self._aplicar_niebla()

        def _niebla_vigente(self):
            """¿Siguen puestos los valores de niebla de este controlador? (otro módulo pudo llamar activar_niebla)."""
            if self._niebla is None:
                return False
            color, fin, fuerza = self._niebla
            d = scene.fog_density
            c = scene.fog_color
            return (isinstance(d, tuple) and abs(d[1] - fin) < 1e-3
                    and abs(c[0] * 255 - color[0]) < 0.6 and abs(c[1] * 255 - color[1]) < 0.6 and abs(c[2] * 255 - color[2]) < 0.6
                    and abs(c[3] - fuerza) < 1e-3)

        def _aplicar_niebla(self):
            d = scene.fog_density
            activa = (isinstance(d, tuple) and d[1] > 0) or (not isinstance(d, tuple) and d)
            if not activa:                  # interior o menú: sin niebla; no la encendemos nosotros
                self._niebla = None
                return
            if self._niebla_vigente():
                return
            p = self._params
            self.propagador.aplicar(p["niebla_color"], p["niebla_fin"], p["niebla_fuerza"])
            self._niebla = (p["niebla_color"], p["niebla_fin"], p["niebla_fuerza"])
            self.aplicaciones_niebla += 1

        # -- Capas --

        def _crear_capas(self):
            mundo = escena._mundo
            s = sitios_de_la_ciudad(mundo)
            self.sitios = s
            raiz = self.raiz

            def variantes(nombre, cantidad, fabrica_de, n_variantes, n_por_variante, sitios, radio, variante_de=None, maximo=None):
                variante_de = variante_de or (lambda p: p.extra)
                for v in range(n_variantes):
                    propios = [p for p in sitios if variante_de(p) % n_variantes == v]
                    self.grupos[f"{nombre}{v}"] = (cantidad, Grupo(raiz, f"{nombre}{v}", fabrica_de(v), n_por_variante, propios, radio,
                                                                  _coloca_uniforme, _fija_uniforme, maximo))

            bolsas = [p for p in s["basura"] if p.extra % 3 == 0]
            papeles = [p for p in s["basura"] if p.extra % 3 == 1]
            cajas = [p for p in s["basura"] if p.extra % 3 == 2]
            por_tercio = lambda p: p.extra // 3
            variantes("bolsa", "basura", lambda v: (lambda: mesh_bolsa(v)), 3, 4, bolsas, 42, por_tercio)
            variantes("papel", "basura", lambda v: (lambda: mesh_papeles(v)), 3, 4, papeles, 42, por_tercio)
            variantes("caja", "basura", lambda v: (lambda: mesh_caja(v)), 2, 4, cajas, 42, por_tercio)
            variantes("grafiti", "grafitis", lambda v: (lambda: mesh_grafiti(v)), 4, 5, s["grafitis"], 55)
            variantes("cartel", "carteles", lambda v: (lambda: mesh_cartel(v)), 2, 2, s["carteles"], 55)
            variantes("flor", "flores", lambda v: (lambda: mesh_flores(v, False)), 4, 4, s["flores"], 45)
            variantes("seca", "marchitas", lambda v: (lambda: mesh_flores(v, True)), 2, 5, s["marchitas"], 45)
            cortas = [p for p in s["guirnaldas"] if p.extra[2] < 15]
            largas = [p for p in s["guirnaldas"] if p.extra[2] >= 15]
            self.grupos["guirnalda_c"] = ("guirnaldas", Grupo(raiz, "guirnalda_c", lambda: mesh_guirnalda(10.0, 0), 8, cortas, 60,
                                                              _coloca_guirnalda, _fija_guirnalda))
            self.grupos["guirnalda_l"] = ("guirnaldas", Grupo(raiz, "guirnalda_l", lambda: mesh_guirnalda(20.0, 1), 8, largas, 60,
                                                              _coloca_guirnalda, _fija_guirnalda))
            self.grupos["apagado"] = ("apagados", Grupo(raiz, "apagado", lambda: mesh_capuchon(0), 18, s["apagados"], 70,
                                                        _coloca_uniforme, _fija_uniforme))
            variantes("sentados", "bancos", lambda v: (lambda: mesh_sentados(v)), 3, 3, s["bancos"], 45)
            variantes("corro", "corros", lambda v: (lambda: mesh_corro(v)), 2, 2, s["corros"], 60)
            if self.con_etapas:
                self._crear_capas_etapa(mundo, s, variantes)

        def _crear_capas_etapa(self, mundo, s, variantes):
            """Fuego, rodadores y fiesta: mismas piscinas con sitios fijos; su cantidad sale de la ETAPA."""
            from ursina.shaders import unlit_shader
            raiz = self.raiz
            e = sitios_de_etapa(mundo, s)
            largo = float(mundo.ancho_calle) + 1.2
            variantes("fuego", "fuego", lambda v: (lambda: mesh_fuego(v)), 2, 5, e["fuego"], 55)
            self.grupos["rodador"] = ("rodadores", Grupo(raiz, "rodador", lambda: mesh_rodador(0), 5, e["rodadores"], 60,
                                                         _coloca_uniforme, _fija_uniforme))
            self.grupos["fiesta"] = ("fiesta", Grupo(raiz, "fiesta", lambda: mesh_fiesta(largo), 5, e["fiesta"], 75,
                                                     _coloca_uniforme, _fija_uniforme))
            for k, entidad in enumerate(self.grupos["fiesta"][1].entidades):      # confeti: nubes hijas que caen en bucle
                entidad.confeti = []
                for j in range(NUBES_CONFETI):
                    nube = Entity(parent=entidad, model=mesh_confeti(largo, k * NUBES_CONFETI + j), shader=unlit_shader, unlit=True,
                                  y=ALTO_CONFETI, name=f"viva_confeti_{k}_{j}")
                    nube.ignore = True
                    entidad.confeti.append(nube)
            self._suelo = mundo.altura
            self._grupos_etapa = [(capa, g) for nombre, (capa, g) in self.grupos.items() if capa in etapas_final.CAPAS_ETAPA]

        def _animar_etapa(self, dt):
            """Parpadeo del fuego, rodar de los arbustos y caída del confeti: solo las ranuras ocupadas (≤ 20)."""
            self._t_etapa += dt
            t = self._t_etapa
            for capa, grupo in self._grupos_etapa:
                ranuras = grupo.ranuras
                for k, sitio in enumerate(ranuras.sitio):
                    if sitio is None:
                        continue
                    e = grupo.entidades[k]
                    es = max(0.001, cv.escala_fundida(ranuras.f[k]))
                    if capa == "fuego":
                        ancho = es * (1.0 + 0.07 * math.sin(t * 11.0 + k * 2.1))
                        e.scale = (ancho, es * (1.0 + 0.16 * math.sin(t * 8.3 + k * 1.7)), ancho)
                    elif capa == "rodadores":
                        dato = grupo.sitios[sitio]
                        ux, uz, recorrido = dato.extra
                        fase = (t * VELOCIDAD_RODADOR / recorrido + k * 0.37) % 1.0
                        avance = (fase - 0.5) * recorrido
                        x, z = dato.x + ux * avance, dato.z + uz * avance
                        e.position = (x, self._suelo(x, z) + 0.5 + 0.22 * abs(math.sin(t * 4.0 + k)), z)
                        e.rotation_x = (t * 230.0 + k * 50.0) % 360.0
                        e.scale = es * min(1.0, 7.0 * fase, 7.0 * (1.0 - fase))          # nace y se va sin salto
                    else:
                        for j, nube in enumerate(e.confeti):
                            fase = (t / SEGUNDOS_CONFETI + j / NUBES_CONFETI + k * 0.21) % 1.0
                            nube.y = 0.4 + ALTO_CONFETI * (1.0 - fase)
                            nube.scale = max(0.001, min(1.0, 8.0 * fase, 8.0 * (1.0 - fase)))
                            nube.rotation_y = 25.0 * math.sin(t * 0.6 + j * 2.0)

        def _repartir(self, x, z):
            animando = False
            for cantidad, grupo in self.grupos.values():
                animando = grupo.repartir(x, z, self._cantidades[cantidad]) or animando
            self._animando = animando

        # -- Frame --

        def update(self):
            self.avanzar(min(time.dt, 0.1))

        def avanzar(self, dt, posicion=None):
            amb = ambiente_vivo.obtener()
            if self.propagador.cola:
                self.propagador.avanzar()
            self._t_atm -= dt
            if self.con_atmosfera and self._t_atm <= 0:
                self._t_atm = PERIODO_ATMOSFERA
                self._atmosfera(amb)
            if not self.con_capas:
                return
            self._t_capas -= dt
            if self._t_capas <= 0:
                self._t_capas = PERIODO_CAPAS
                x, z = posicion if posicion is not None else (camera.world_x, camera.world_z)
                movio = self._pos_capas is None or math.hypot(x - self._pos_capas[0], z - self._pos_capas[1]) >= MOVIMIENTO_CAPAS
                version = ambiente_vivo.version()
                if movio or version != self._version_capas or self._animando:
                    self._cantidades = cv.cantidades(amb, ambiente_vivo.etapa() if self.con_etapas else None)
                    self._pos_capas, self._version_capas = (x, z), version
                    self._repartir(x, z)
            if self._animando:
                animando = False
                for _, grupo in self.grupos.values():
                    animando = grupo.avanzar(dt) or animando
                self._animando = animando
            if self._grupos_etapa:
                self._animar_etapa(dt)

        # -- Informe (pruebas y depuración) --

        def estadisticas(self):
            vis = {}
            for cantidad, grupo in self.grupos.values():
                vis[cantidad] = vis.get(cantidad, 0) + grupo.visibles()
            return {"visibles": vis, "entidades": sum(len(g.entidades) for _, g in self.grupos.values()),
                    "params": self._params, "aplicaciones_niebla": self.aplicaciones_niebla, "niebla_en_cola": len(self.propagador.cola)}

        def restaurar_atmosfera(self):
            """Deja luz, cielo y niebla como antes de este módulo (para depurar)."""
            ciudad = escena.ciudad
            ciudad.luz.color = rgb_luz(self.sol_base)
            ciudad.ambiente.color = rgb_luz(self.ambiente_base)
            ciudad.cielo.color = Color(1, 1, 1, 1)
            d = scene.fog_density
            if isinstance(d, tuple) and d[1] > 0:
                activar_niebla(**escena._niebla)
            self._niebla = None

    return ControladorCiudadViva(parent=escena)
