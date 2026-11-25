# Decorado de los planos del final animado (Ursina). Cada Pieza de puesta.py se vuelve una entidad (o unas pocas) con el
# estilo del juego: color plano, casco de tinta en la MISMA malla (ciudad_viva.DibujoTinta: caras al revés, solo se ve
# el borde) y texto 3D con la fuente de títulos. Lo fijo de una pieza va fundido en una sola malla; lo que se anima
# (postigos, nota, íconos, confeti, ventanas, teléfono) va aparte y solo se mueve en avanzar() (sin crear ni destruir).
#
# Marco local de cada pieza: +z = frente del ancla (girado `giro`), +x = derecha, y arriba, origen en el suelo del punto.
# Todo es unlit (como las capas de ciudad_viva) con los colores multiplicados por la luz del final (noche más oscura).

import math
import sys

from ursina import Entity, Text, color
from ursina.shaders import unlit_shader

from frontend import estilo, tipografia
from frontend.ciudad_viva import DibujoTinta, mesh_confeti, mesh_fiesta, mesh_flores, mesh_fuego_vivo, mesh_guirnalda
from frontend.contorno_calculos import realzar_color
from frontend.final_animado import lugares, puesta as P
from frontend.props_mundo import caja, icosfera, prisma

LUZ_POR_FINAL = {"malo": 0.6, "neutro": 0.9, "bueno": 1.0}
ALTO_SOBRE_PLAZA = 0.17          # m: lo que va tirado en el suelo, por encima del mosaico de las plazas
MADERA = (150, 104, 62)
MADERA_OSCURA = (96, 64, 40)
METAL = (196, 198, 210)
PAPEL = (246, 242, 230)
AZUL_TRADICION = (28, 44, 96)
ORO = (232, 190, 70)
AZUL_RUEDAS = (44, 138, 214)
AMARILLO = estilo.ACENTO_PRIMARIO
ROJO = estilo.ESTADO_ERROR
VERDE = estilo.ESTADO_EXITO
LADRILLO = (176, 84, 96)
VENTANA_APAGADA = (40, 46, 66)
VENTANA_CALIDA = (255, 212, 120)


def _aviso(texto):
    print(f"[final_animado] {texto}", file=sys.stderr)


def _tono(c, f):
    return tuple(max(0, min(255, int(round(v * f)))) for v in c[:3])


class Lienzo:
    """DibujoTinta con la luz del final aplicada a todos los colores."""

    def __init__(self, luz):
        self.d = DibujoTinta()
        self.luz = luz

    def solido(self, forma, pos, escala, color_, giro=0.0, inclinacion=0.0, apoyado=False, degradado=(0.9, 1.05)):
        self.d.solido(forma, pos, escala, giro, _tono(realzar_color(color_), self.luz), degradado, inclinacion, apoyado)

    def caja(self, pos, escala, color_, giro=0.0, inclinacion=0.0):
        self.solido(caja(), pos, escala, color_, giro, inclinacion)

    def mesh(self):
        return self.d.mesh()


def _entidad(padre, mesh, **kw):
    if mesh is None:
        return Entity(parent=padre, **kw)
    return Entity(parent=padre, model=mesh, shader=unlit_shader, unlit=True, **kw)


def texto(padre, cadena, pos, alto_letra, color_rgb, ancho_max=None, rot_y=180.0):
    """Texto 3D centrado en `pos` (local de `padre`), mirando a +z local (lo lee quien está delante). `alto_letra` en m;
    si con ese alto no cabe en `ancho_max`, se achica."""
    lineas = str(cadena).split("\n")
    largo = max(len(l) for l in lineas)
    if ancho_max is not None and largo:
        alto_letra = min(alto_letra, ancho_max / (0.56 * largo))
    t = Text(cadena, parent=padre, origin=(0, 0), position=pos, rotation_y=rot_y, scale=alto_letra / 0.025,
             color=color.rgb32(*color_rgb), font=tipografia.FUENTE_TITULO)
    t.ignore = True
    return t


class PiezaViva:
    """Una pieza del decorado ya puesta en el mundo. `avanzar(t, s)` la anima (si se anima)."""

    def __init__(self, raiz):
        self.raiz = raiz

    def avanzar(self, t, segundos):
        pass


# -- Constructores: cada uno arma la pieza en el marco local de `raiz` ----------------------------------------------

def _mesa(l, x=0.0, z=0.0, ancho=1.2, fondo=0.65, alto=0.74, tono=MADERA):
    l.caja((x, alto, z), (ancho, 0.05, fondo), tono)
    for sx in (-1, 1):
        for sz in (-1, 1):
            l.caja((x + sx * (ancho / 2 - 0.06), alto / 2, z + sz * (fondo / 2 - 0.06)), (0.06, alto, 0.06), MADERA_OSCURA)


def _urna(l, y, variante):
    l.caja((0, y + 0.22, 0), (0.44, 0.44, 0.36), (200, 222, 238))
    l.caja((0, y + 0.455, 0), (0.48, 0.04, 0.4), (60, 110, 170))
    l.caja((0, y + 0.48, 0), (0.22, 0.012, 0.04), estilo.TINTA)
    if variante == 1:
        l.caja((0.0, y + 0.53, 0.0), (0.16, 0.06, 0.012), PAPEL, giro=10)


def _papeletas_mesa(l, y):
    for k in range(5):
        l.caja((0.0 + 0.01 * k, y + 0.012 + 0.014 * k, 0.0), (0.21, 0.012, 0.15), PAPEL, giro=6 * k)


def _monton(l, y, variante):
    n = 7 + variante
    for k in range(n):
        l.caja((0.006 * (k % 3), y + 0.012 + 0.016 * k, 0.004 * (k % 2)), (0.22, 0.014, 0.16), PAPEL, giro=4 * (k % 3) - 4)


def _rotulo(raiz, l, ancho, cadena, luz, final):
    alto = 1.0
    l.caja((0, 0, -0.04), (ancho + 0.16, alto + 0.16, 0.08), ORO)
    l.caja((0, 0, 0.0), (ancho, alto, 0.1), AZUL_TRADICION)
    texto(raiz, cadena, (0, -0.03, 0.07), 0.42, _tono((250, 246, 236), max(0.8, luz)), ancho_max=ancho - 0.6)


def _caballete(raiz, l, cadena, luz):
    for sx in (-1, 1):
        l.caja((sx * 0.45, 0.9, -0.05), (0.06, 1.8, 0.06), MADERA, giro=0, inclinacion=-6)
    l.caja((0, 0.85, -0.35), (0.05, 1.7, 0.05), MADERA, inclinacion=18)
    l.caja((0, 1.55, 0.0), (1.3, 0.95, 0.05), PAPEL)
    l.caja((0, 1.12, 0.03), (1.3, 0.12, 0.02), AMARILLO)
    l.caja((0, 1.99, 0.03), (1.3, 0.08, 0.02), AZUL_RUEDAS)
    texto(raiz, cadena, (0, 1.58, 0.045), 0.24, _tono(AZUL_RUEDAS, max(0.8, luz)), ancho_max=1.15)


def _podio(l):
    l.caja((0, 0.25, 0), (2.6, 0.5, 1.6), (72, 92, 150))
    l.caja((0, 0.27, 0.81), (2.62, 0.16, 0.02), AMARILLO)
    l.caja((1.55, 0.125, 0.0), (0.5, 0.25, 0.9), (60, 78, 130))
    l.caja((0, 0.51, 0), (2.5, 0.02, 1.5), (180, 60, 60))


def _atril(l):
    l.caja((0, 0.55, 0), (0.12, 1.1, 0.12), MADERA_OSCURA)
    l.caja((0, 0.05, 0), (0.5, 0.06, 0.4), MADERA_OSCURA)
    l.caja((0, 1.13, 0.02), (0.62, 0.06, 0.42), MADERA, inclinacion=-18)
    l.caja((0, 0.75, 0.08), (0.5, 0.42, 0.04), AZUL_RUEDAS)
    l.solido(icosfera(0), (0, 0.78, 0.11), (0.14, 0.14, 0.03), AMARILLO)


def _baranda(l, largo):
    n = max(2, int(largo / 1.25) + 1)
    for k in range(n):
        x = -largo / 2 + largo * k / (n - 1)
        l.caja((x, 0.52, 0), (0.07, 1.04, 0.07), METAL)
    l.caja((0, 1.04, 0), (largo + 0.07, 0.07, 0.09), METAL)
    l.caja((0, 0.55, 0), (largo, 0.04, 0.05), METAL)


def _puesto_flores(raiz, l, luz):
    _mesa(l, 0, 0, 1.5, 0.8, 0.8, (120, 150, 90))
    for sx in (-1, 1):
        l.caja((sx * 0.72, 1.35, -0.36), (0.05, 1.1, 0.05), MADERA_OSCURA)
    for k in range(4):
        l.caja((-0.56 + 0.375 * k, 1.92, -0.05), (0.375, 0.04, 0.9), ((230, 80, 90), PAPEL)[k % 2], inclinacion=-12)
    for k, x in enumerate((-0.38, 0.38)):
        Entity(parent=raiz, model=mesh_flores(k + 2, False), shader=unlit_shader, unlit=True, position=(x, 0.82, 0.0),
               scale=(0.7, 0.9, 0.9), color=color.rgb(luz, luz, luz))


def _mesa_redaccion(raiz, l):
    _mesa(l, 0, 0, 1.4, 0.7, 0.76, (110, 118, 132))
    l.caja((0.1, 0.8, -0.05), (0.42, 0.02, 0.3), (60, 64, 76))                 # portátil: base
    l.caja((0.1, 0.95, -0.2), (0.42, 0.28, 0.02), (60, 64, 76), inclinacion=-14)     # pantalla, hacia el periodista
    l.caja((0.1, 0.95, -0.215), (0.36, 0.22, 0.01), (120, 200, 240), inclinacion=-14)
    l.solido(prisma(8, 0.5, 0.5), (-0.45, 0.785, 0.05), (0.12, 0.02, 0.12), (40, 40, 48), apoyado=True)
    l.caja((-0.45, 0.9, 0.05), (0.025, 0.2, 0.025), (40, 40, 48))
    l.solido(icosfera(1), (-0.45, 1.02, 0.07), (0.09, 0.11, 0.09), (30, 30, 36))
    for k in range(3):
        l.caja((0.52 - 0.02 * k, 0.79 + 0.006 * k, 0.12), (0.2, 0.006, 0.28), PAPEL, giro=8 * k)


def _microfono(l):
    l.solido(prisma(10, 0.5, 0.5), (0, 0.0, 0), (0.34, 0.03, 0.34), (40, 40, 48), apoyado=True)
    l.caja((0, 0.72, 0), (0.035, 1.44, 0.035), (60, 60, 70))
    l.caja((0, 1.47, -0.08), (0.03, 0.03, 0.2), (60, 60, 70), inclinacion=30)
    l.solido(icosfera(1), (0, 1.52, -0.18), (0.08, 0.12, 0.08), (30, 30, 36), inclinacion=30)


def _guirnalda_corta(raiz, l, largo, variante, luz):
    for sx in (-1, 1):
        l.caja((sx * largo / 2, 1.3, 0), (0.07, 2.6, 0.07), MADERA)
    Entity(parent=raiz, model=mesh_guirnalda(largo, variante), shader=unlit_shader, unlit=True,
           position=(-largo / 2, 2.5, 0), color=color.rgb(luz, luz, luz))


# -- Piezas que se animan ---------------------------------------------------------------------------------------------

class Ventanas(PiezaViva):
    """Ventanas de la Prefeitura: un panel por ventana delante de la fachada; su brillo sale de puesta.ventanas()."""

    def __init__(self, raiz, plano_id, luz):
        super().__init__(raiz)
        self.plano_id = plano_id
        l = Lienzo(luz)
        for d, a in P.VENTANAS_PREFEITURA:
            l.caja((d, a, 0.0), (1.34, 1.5, 0.05), estilo.TINTA)
        _entidad(raiz, l.mesh())
        self.paneles = [Entity(parent=raiz, model="quad", shader=unlit_shader, unlit=True, position=(d, a, 0.035),
                               scale=(1.14, 1.3), rotation_y=180, color=color.rgb32(*VENTANA_APAGADA))
                        for d, a in P.VENTANAS_PREFEITURA]
        self._brillos = [None] * len(self.paneles)
        self.avanzar(0.0, 0.0)

    def avanzar(self, t, segundos):
        brillos = P.ventanas(self.plano_id, t) or (0.0,) * len(self.paneles)
        for k, (panel, b) in enumerate(zip(self.paneles, brillos)):
            b = round(b, 3)
            if b != self._brillos[k]:
                self._brillos[k] = b
                c = tuple(int(VENTANA_APAGADA[i] + (VENTANA_CALIDA[i] - VENTANA_APAGADA[i]) * b) for i in range(3))
                panel.color = color.rgb32(*c)


class Nota(PiezaViva):
    """La nota del periodista: sube desde la mesa y queda en el aire, publicada."""

    def __init__(self, raiz, pieza, luz, inicio_local):
        super().__init__(raiz)
        self.tramo = pieza.tramo or (0.3, 0.55)
        self.inicio = inicio_local
        self.hoja = Entity(parent=raiz)
        l = Lienzo(1.0)
        l.caja((0, 0, 0), (0.92, 1.18, 0.02), PAPEL)
        acento = (VERDE, ROJO, AMARILLO)[pieza.variante % 3]
        l.caja((0, 0.47, 0.012), (0.92, 0.18, 0.01), acento)
        for k in range(4):
            l.caja((-0.05, -0.18 - 0.11 * k, 0.012), (0.72, 0.03, 0.006), (150, 150, 160))
        _entidad(self.hoja, l.mesh())
        texto(self.hoja, pieza.texto, (0, 0.14, 0.024), 0.14, estilo.TINTA, ancho_max=0.82)
        texto(self.hoja, "CIVITAS · NOTA", (0, 0.47, 0.02), 0.08, PAPEL, ancho_max=0.8)
        self.avanzar(0.0, 0.0)

    def avanzar(self, t, segundos):
        t0, t1 = self.tramo
        k = max(0.0, min(1.0, (t - t0) / max(1e-6, t1 - t0)))
        k = k * k * (3 - 2 * k)
        x0, y0, z0 = self.inicio
        flota = 0.04 * math.sin(segundos * 1.6) if k >= 1.0 else 0.0
        self.hoja.position = (x0 * (1 - k), y0 * (1 - k) + flota, z0 * (1 - k))
        self.hoja.scale = 0.25 + 0.75 * k
        self.hoja.rotation = (-80 * (1 - k), 12 * math.sin(segundos * 0.7) * k, 0)


class VentanaMorro(PiezaViva):
    """Paño de fachada con ventana, alféizar, maceta, interior y dos postigos que abren o cierran en su tramo."""

    ALTO, ANCHO = 2.45, 2.7
    HUECO = (1.2, 1.0, 1.95)          # ancho, alféizar, dintel

    def __init__(self, raiz, pieza, luz):
        super().__init__(raiz)
        # ALCALDE_FINALES_PULIDOS: paño más alto y ancho (tapa el letrero de la casa), hueco a la altura de la cara de
        # los protagonistas v2, zócalo bajo el suelo y postigos que abren hacia fuera (final_pulido_calculos.py).
        from frontend.final_animado import final_pulido_calculos as pulido
        pulir = pulido.activo()
        l = Lienzo(luz)
        a, h = (pulido.VENTANA_ANCHO, pulido.VENTANA_ALTO) if pulir else (self.ANCHO, self.ALTO)
        w, y0, y1 = pulido.VENTANA_HUECO if pulir else self.HUECO
        zocalo = pulido.VENTANA_ZOCALO if pulir else 0.0
        self.giro = pulido.GIRO_POSTIGOS if pulir else -1.0
        fondo = 0.22
        lado = (a - w) / 2
        for sx in (-1, 1):
            l.caja((sx * (w / 2 + lado / 2), (h - zocalo) / 2, 0), (lado, h + zocalo, fondo), LADRILLO)
        l.caja((0, (y0 - zocalo) / 2, 0), (w, y0 + zocalo, fondo), LADRILLO)
        # Alero de chapa: el paño se lee como una casa, no como un muro
        if pulir:
            l.caja((0, h + 0.05, 0.2), (a + 0.3, 0.1, fondo + 0.5), (120, 124, 136), inclinacion=-8)
        l.caja((0, (y1 + h) / 2, 0), (w, h - y1, fondo), LADRILLO)
        l.caja((0, y0 + 0.03, 0.08), (w + 0.3, 0.07, fondo + 0.18), (226, 214, 196))          # alféizar
        l.caja((0, y1 + 0.04, 0.03), (w + 0.2, 0.08, fondo + 0.06), (226, 214, 196))          # dintel
        for sx in (-1, 1):
            l.caja((sx * (w / 2 + 0.03), (y0 + y1) / 2, 0.06), (0.06, y1 - y0, fondo + 0.04), (238, 230, 214))
        l.solido(prisma(8, 0.42, 0.5), (0.36, y0 + 0.065, 0.12), (0.22, 0.18, 0.22), (180, 96, 66), apoyado=True)
        for k, c in enumerate(((222, 64, 64), (248, 206, 56), (214, 70, 160))):
            l.solido(icosfera(0), (0.29 + 0.07 * k, y0 + 0.3 + 0.03 * (k % 2), 0.12), 0.11, c)
        _entidad(raiz, l.mesh())
        interior = {0: (96, 80, 70), 1: (130, 98, 58), 2: (88, 76, 70)}[pieza.variante]
        Entity(parent=raiz, model="quad", shader=unlit_shader, unlit=True, position=(0, (y0 + y1) / 2, -0.62),
               scale=(w + 0.4, y1 - y0 + 0.3), rotation_y=180, color=color.rgb32(*_tono(interior, luz)))
        self.modo = pieza.variante                     # 0 abre, 1 cierra, 2 abiertos siempre
        self.tramo = pieza.tramo
        self.postigos = []
        for sx in (-1, 1):
            bisagra = Entity(parent=raiz, position=(sx * w / 2, (y0 + y1) / 2, 0.13))
            lp = Lienzo(luz)
            lp.caja((-sx * w / 4, 0, 0), (w / 2 - 0.02, y1 - y0 - 0.04, 0.04), (60, 130, 110))
            for k in range(4):
                lp.caja((-sx * w / 4, -0.32 + 0.21 * k, 0.025), (w / 2 - 0.12, 0.05, 0.01), (44, 104, 88))
            _entidad(bisagra, lp.mesh())
            self.postigos.append((bisagra, sx))
        self.avanzar(0.0, 0.0)

    def avanzar(self, t, segundos):
        if self.modo == 2 or self.tramo is None:
            k = 1.0
        else:
            t0, t1 = self.tramo
            k = max(0.0, min(1.0, (t - t0) / max(1e-6, t1 - t0)))
            k = k * k * (3 - 2 * k)
            if self.modo == 1:
                k = 1.0 - k
        for bisagra, sx in self.postigos:
            bisagra.rotation_y = self.giro * sx * 165 * k        # abiertos: contra la pared, a cada lado


ICONOS = {0: ("corazon", "visto"), 1: ("pregunta", "cruz"), 2: ("corazon", "pregunta")}


def _icono(forma):
    d = DibujoTinta()
    # el billboard se ve desde -z sin espejo: la tinta va detrás (z +), el color en medio y el dibujo delante (z -)
    if forma == "corazon":
        pts = [(0.5 * 16 * math.sin(a) ** 3 / 16, 0.5 * (13 * math.cos(a) - 5 * math.cos(2 * a) - 2 * math.cos(3 * a)
                                                         - math.cos(4 * a)) / 16) for a in [2 * math.pi * k / 24 for k in range(24)]]
        d.relleno([(x * 1.12, y * 1.12) for x, y in pts], estilo.TINTA, 0.02)
        d.relleno(pts, realzar_color((236, 60, 96)), -0.01)
    elif forma == "visto":
        d.relleno([(math.cos(a) * 0.52, math.sin(a) * 0.52) for a in [2 * math.pi * k / 16 for k in range(16)]],
                  estilo.TINTA, 0.02)
        d.relleno([(math.cos(a) * 0.45, math.sin(a) * 0.45) for a in [2 * math.pi * k / 16 for k in range(16)]],
                  realzar_color(VERDE), -0.01)
        d.polilinea([(-0.22, 0.0), (-0.05, -0.18), (0.25, 0.2)], 0.11, PAPEL, -0.03)
    elif forma == "cruz":
        d.relleno([(math.cos(a) * 0.52, math.sin(a) * 0.52) for a in [2 * math.pi * k / 16 for k in range(16)]],
                  estilo.TINTA, 0.02)
        d.relleno([(math.cos(a) * 0.45, math.sin(a) * 0.45) for a in [2 * math.pi * k / 16 for k in range(16)]],
                  realzar_color(ROJO), -0.01)
        d.trazo((-0.2, -0.2), (0.2, 0.2), 0.11, PAPEL, -0.03)
        d.trazo((-0.2, 0.2), (0.2, -0.2), 0.11, PAPEL, -0.03)
    else:                                   # pregunta
        d.relleno([(math.cos(a) * 0.52, math.sin(a) * 0.52) for a in [2 * math.pi * k / 16 for k in range(16)]],
                  estilo.TINTA, 0.02)
        d.relleno([(math.cos(a) * 0.45, math.sin(a) * 0.45) for a in [2 * math.pi * k / 16 for k in range(16)]],
                  realzar_color(AMARILLO), -0.01)
        arco = [(0.16 * math.cos(a), 0.12 + 0.14 * math.sin(a)) for a in [math.radians(g) for g in range(160, -100, -20)]]
        d.polilinea(arco + [(0.0, -0.08)], 0.09, estilo.TINTA, -0.03)
        d.relleno([(0.05 * math.cos(a), -0.24 + 0.05 * math.sin(a)) for a in [2 * math.pi * k / 8 for k in range(8)]],
                  estilo.TINTA, -0.03)
    return d.mesh()


class Iconos(PiezaViva):
    """Íconos que suben desde el teléfono del directo (corazones y vistos; o «?» y «✕»), en bucle y desfasados."""

    N = 10
    VIDA = 2.2

    def __init__(self, raiz, pieza):
        super().__init__(raiz)
        formas = ICONOS[pieza.variante % 3]
        mallas = {f: _icono(f) for f in formas}
        self.iconos = []
        for k in range(self.N):
            forma = formas[k % 2]
            e = Entity(parent=raiz, model=mallas[forma], shader=unlit_shader, unlit=True, billboard=True,
                       double_sided=True, scale=0.3)
            self.iconos.append((e, k / self.N, (k * 0.37) % 1.0 - 0.5))
        self.avanzar(0.0, 0.0)

    def avanzar(self, t, segundos):
        for e, desfase, lado in self.iconos:
            u = (segundos / self.VIDA + desfase) % 1.0
            x = math.copysign(0.45 + abs(lado) * 1.2, lado if lado else 1.0)
            e.position = (x + 0.12 * math.sin(6.0 * u + desfase * 9), 1.1 * u, 0.0)
            e.scale = 0.3 * (0.4 + 0.6 * min(1.0, u * 4)) * (1.0 - max(0.0, u - 0.8) * 4)


class Tripode(PiezaViva):
    """Trípode con teléfono y aro de luz mirando a la influencer (en el malo, el teléfono baja y el aro se apaga)."""

    def __init__(self, raiz, pieza, luz):
        super().__init__(raiz)
        l = Lienzo(luz)
        for k in range(3):
            a = math.radians(120 * k + 30)
            l.caja((0.18 * math.sin(a), 0.42, 0.18 * math.cos(a)), (0.03, 0.9, 0.03), (40, 40, 48), giro=120 * k + 30,
                   inclinacion=-14)
        l.caja((0, 1.0, 0), (0.035, 0.75, 0.035), (40, 40, 48))
        _entidad(raiz, l.mesh())
        self.cabeza = Entity(parent=raiz, position=(0, 1.32, 0))
        la = Lienzo(1.0)
        for k in range(18):
            a = 2 * math.pi * k / 18
            la.caja((0.15 * math.cos(a), 0.15 * math.sin(a), 0), (0.055, 0.055, 0.04), (255, 246, 220), giro=0)
        la.caja((0, 0, 0.0), (0.09, 0.17, 0.012), (30, 30, 36))
        la.caja((0, 0, 0.008), (0.075, 0.15, 0.004), (90, 160, 230))
        self.aro = _entidad(self.cabeza, la.mesh())
        self.malo = pieza.variante == 1
        self.tramo = pieza.tramo
        self.avanzar(0.0, 0.0)

    def avanzar(self, t, segundos):
        if not self.malo or self.tramo is None:
            return
        t0, t1 = self.tramo
        k = max(0.0, min(1.0, (t - t0) / max(1e-6, t1 - t0)))
        k = k * k * (3 - 2 * k)
        self.cabeza.rotation_x = 75 * k
        g = 1.0 - 0.55 * k
        self.aro.color = color.rgb(g, g, g)


class Fogata(PiezaViva):
    """Fogata de la calle (m2, ALCALDE_FINALES_PULIDOS): la hoguera de cómic de la ciudad (ciudad_viva.mesh_fuego_vivo:
    leños, llamas rojas, naranja y amarillas y humo) con un latido suave. Unos conos sueltos se leían como conos de
    tráfico."""

    def __init__(self, raiz, pieza, luz):
        super().__init__(raiz)
        self.fase = 1.7 * pieza.variante
        self.hoguera = _entidad(raiz, mesh_fuego_vivo(pieza.variante))
        self.avanzar(0.0, 0.0)

    def avanzar(self, t, segundos):
        latido = 1.0 + 0.07 * math.sin(segundos * 9.0 + self.fase) + 0.04 * math.sin(segundos * 23.0 + self.fase)
        self.hoguera.scale = (1.0, latido, 1.0)


class Confeti(PiezaViva):
    """Nubes de confeti que caen sobre el podio en bucle (además del confeti de la capa de fiesta de la ciudad)."""

    def __init__(self, raiz, largo, luz):
        super().__init__(raiz)
        self.nubes = [Entity(parent=raiz, model=mesh_confeti(largo, 40 + k), shader=unlit_shader, unlit=True,
                             double_sided=True, scale=(1, 1, 0.35), color=color.rgb(luz, luz, luz)) for k in range(3)]
        self.avanzar(0.0, 0.0)

    def avanzar(self, t, segundos):
        for k, nube in enumerate(self.nubes):
            u = (segundos / 3.2 + k / 3) % 1.0
            nube.y = 5.2 - 5.0 * u
            nube.rotation_y = 40 * k + 25 * u


# -- Fábrica ----------------------------------------------------------------------------------------------------------

def construir(pieza, plano_id, raiz_plano, anclas, ancla_plano, mundo, final):
    """Crea la pieza bajo `raiz_plano` y devuelve su PiezaViva. Lanza si algo falla (escenografia lo envuelve)."""
    luz = LUZ_POR_FINAL.get(final, 1.0)
    ancla = anclas[pieza.ancla] if pieza.ancla else ancla_plano
    x, y, z = lugares.a_mundo(ancla, pieza.derecha, pieza.alto, pieza.frente)
    if not pieza.sobre_ancla and pieza.tipo not in ("ventanas", "rotulo"):
        y = float(mundo.altura(x, z)) + pieza.alto
    raiz = Entity(parent=raiz_plano, position=(x, y, z), rotation_y=ancla.rumbo + pieza.giro)
    l = Lienzo(luz)
    viva = PiezaViva(raiz)
    tipo = pieza.tipo
    if tipo == "mesa":
        _mesa(l)
    elif tipo == "urna":
        _urna(l, 0.0, pieza.variante)
    elif tipo == "papeletas_mesa":
        _papeletas_mesa(l, 0.0)
    elif tipo == "monton":
        _monton(l, 0.0, pieza.variante)
    elif tipo == "papeleta":
        raiz.y += ALTO_SOBRE_PLAZA - 0.16
        l.caja((0, 0.16, 0), (0.22, 0.008, 0.16), (PAPEL, (232, 228, 214), (250, 236, 200), (226, 232, 240))[pieza.variante % 4])
    elif tipo == "rotulo":
        _rotulo(raiz, l, pieza.medida, pieza.texto, luz, final)
    elif tipo == "caballete":
        _caballete(raiz, l, pieza.texto, luz)
    elif tipo == "podio":
        _podio(l)
    elif tipo == "atril":
        _atril(l)
    elif tipo == "confeti":
        viva = Confeti(raiz, pieza.medida, luz)
    elif tipo == "fogata":
        raiz.scale = pieza.medida
        viva = Fogata(raiz, pieza, luz)
    elif tipo == "baranda":
        _baranda(l, pieza.medida)
    elif tipo == "puesto_flores":
        _puesto_flores(raiz, l, luz)
    elif tipo == "guirnalda_calle":
        Entity(parent=raiz, model=mesh_fiesta(pieza.medida, pieza.variante), shader=unlit_shader, unlit=True,
               color=color.rgb(luz, luz, luz))
    elif tipo == "guirnalda_corta":
        _guirnalda_corta(raiz, l, pieza.medida, pieza.variante, luz)
    elif tipo == "banderin_ventana":
        raiz.y = y + 0.0
        Entity(parent=raiz, model=mesh_guirnalda(pieza.medida, pieza.variante), shader=unlit_shader, unlit=True,
               position=(-pieza.medida / 2, 0, 0.2), color=color.rgb(luz, luz, luz))
    elif tipo == "ventanas":
        viva = Ventanas(raiz, plano_id, luz)
    elif tipo == "ventana_morro":
        viva = VentanaMorro(raiz, pieza, luz)
    elif tipo == "mesa_redaccion":
        _mesa_redaccion(raiz, l)
    elif tipo == "nota":
        mesa = (0.0, 0.75)
        inicio = (mesa[0] - pieza.derecha, 0.82 - pieza.alto, mesa[1] - pieza.frente)
        viva = Nota(raiz, pieza, luz, inicio)
    elif tipo == "tripode":
        viva = Tripode(raiz, pieza, luz)
    elif tipo == "iconos":
        viva = Iconos(raiz, pieza)
    elif tipo == "microfono":
        _microfono(l)
    elif tipo == "pancarta_suelo":
        raiz.y += ALTO_SOBRE_PLAZA - 0.12
        _pancarta_suelo(raiz, l, pieza, luz)
    else:
        raise ValueError(f"pieza desconocida: {tipo}")
    mesh = l.mesh()
    if mesh is not None:
        _entidad(raiz, mesh)
    viva.raiz = raiz
    return viva


def _pancarta_suelo(raiz, l, pieza, luz):
    tabla = Entity(parent=raiz, rotation_x=-82 + 6 * (pieza.variante % 3), y=0.08)
    lt = Lienzo(luz)
    lt.caja((0, 0.33, 0), (1.15, 0.62, 0.03), PAPEL)
    lt.caja((0, 0.33, -0.02), (1.21, 0.68, 0.01), estilo.TINTA)
    _entidad(tabla, lt.mesh())
    texto(tabla, pieza.texto, (0, 0.33, 0.02), 0.2, _tono(ROJO, max(0.75, luz)), ancho_max=1.0)
    l.caja((0.15, 0.03, -0.5), (0.04, 0.04, 1.2), MADERA, giro=14)

