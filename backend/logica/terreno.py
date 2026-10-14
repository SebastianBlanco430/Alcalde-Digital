# Terreno de Ciudad Nova (lógica pura, sin ursina): altura y pendiente en cualquier punto (x, z)
# del mundo. Es determinista (misma semilla -> mismo relieve) y no usa librerías externas.
#
# Composición de la altura:
#   natural(x, z) : la ladera base. Un plano inclinado (ajustado por mínimos cuadrados a las
#                   cotas de los lugares) más ondulaciones suaves (suma de senos con fase por
#                   semilla); o, si se da un heightmap, esa imagen (gris -> metros).
#   red(x, z)     : la cota de lo construido: plazas (disco plano a la cota de su lugar),
#                   edificios (caja plana con margen) y calles (rampa lineal entre las cotas de
#                   sus dos lugares, con un tramo plano al pie de cada plaza y plana a lo ancho).
#   final         : natural mezclado hacia red con un talud suave (smoothstep) de `ancho_talud` m
#                   alrededor de lo construido. Sobre lo construido la altura es EXACTAMENTE la de
#                   la red (los pisos y los edificios nunca flotan ni se hunden).
#
# `Terreno.plano()` devuelve altura 0 en todas partes: reproduce el mundo sin relieve.

import math
import random
from dataclasses import dataclass

ANCHO_TALUD = 8.0                 # m de transición entre lo construido y la ladera
MARGEN_EDIFICIO = 1.5             # m de plataforma plana alrededor de cada edificio
EXTRA_ACERA = 2.2                 # m a cada lado del asfalto que también quedan a cota de calle
PENDIENTE_MAXIMA_CALLE = 0.15     # 15 %: tope de la pendiente de una calle (rampa lineal)
_EPS = 0.05                       # m: suaviza el peso 1/d^3 de la mezcla entre elementos


def _suavizar(t):
    t = min(1.0, max(0.0, t))
    return t * t * (3 - 2 * t)


@dataclass(frozen=True)
class Plataforma:
    """Disco plano (una plaza) a una cota fija."""

    cx: float
    cz: float
    radio: float
    elevacion: float

    def distancia(self, x, z):
        return max(0.0, math.hypot(x - self.cx, z - self.cz) - self.radio)

    def cota(self, x, z):
        return self.elevacion


@dataclass(frozen=True)
class CajaPlana:
    """Rectángulo alineado a los ejes (la huella de un edificio con margen) a una cota fija."""

    xmin: float
    xmax: float
    zmin: float
    zmax: float
    elevacion: float

    def distancia(self, x, z):
        return math.hypot(x - min(max(x, self.xmin), self.xmax), z - min(max(z, self.zmin), self.zmax))

    def cota(self, x, z):
        return self.elevacion


@dataclass(frozen=True)
class Calle:
    """Segmento entre dos lugares: tramo plano al pie de cada plaza y rampa lineal en medio."""

    a: str
    b: str
    ax: float
    az: float
    bx: float
    bz: float
    elevacion_a: float
    elevacion_b: float
    semiancho: float
    plano_a: float                  # m planos desde el centro de `a`
    plano_b: float

    @property
    def largo(self):
        return math.hypot(self.bx - self.ax, self.bz - self.az)

    @property
    def largo_rampa(self):
        return max(self.largo - self.plano_a - self.plano_b, 0.0)

    # Pendiente de la rampa (positiva, fracción: 0.15 = 15 %).
    @property
    def pendiente(self):
        dif = abs(self.elevacion_b - self.elevacion_a)
        if dif == 0:
            return 0.0
        return dif / self.largo_rampa if self.largo_rampa > 0 else math.inf

    # (distancia al borde de la calle, parámetro s en metros a lo largo del eje).
    def _proyectar(self, x, z):
        largo = self.largo
        if largo == 0:
            return math.hypot(x - self.ax, z - self.az), 0.0
        ux, uz = (self.bx - self.ax) / largo, (self.bz - self.az) / largo
        s = (x - self.ax) * ux + (z - self.az) * uz
        s = min(max(s, 0.0), largo)
        px, pz = self.ax + ux * s, self.az + uz * s
        return math.hypot(x - px, z - pz), s

    def distancia(self, x, z):
        d, _ = self._proyectar(x, z)
        return max(0.0, d - self.semiancho)

    def cota(self, x, z):
        _, s = self._proyectar(x, z)
        return self.cota_en(s)

    # Cota sobre el eje a `s` metros del centro de `a`.
    def cota_en(self, s):
        rampa = self.largo_rampa
        if rampa <= 0:
            return self.elevacion_a if s < self.largo / 2 else self.elevacion_b
        u = min(1.0, max(0.0, (s - self.plano_a) / rampa))
        return self.elevacion_a + (self.elevacion_b - self.elevacion_a) * u


class MapaAlturas:
    """Heightmap en escala de grises (0..255) extendido sobre (xmin, xmax, zmin, zmax)."""

    def __init__(self, ancho, alto, datos, limites, minimo, maximo):
        if ancho < 2 or alto < 2 or len(datos) != ancho * alto:
            raise ValueError("MapaAlturas: dimensiones o datos inválidos.")
        self._ancho, self._alto, self._datos = ancho, alto, datos
        self._xmin, self._xmax, self._zmin, self._zmax = limites
        self._minimo, self._maximo = minimo, maximo

    # Altura en metros por interpolación bilineal (fuera de los límites se repite el borde).
    def altura(self, x, z):
        u = (x - self._xmin) / (self._xmax - self._xmin) * (self._ancho - 1)
        v = (z - self._zmin) / (self._zmax - self._zmin) * (self._alto - 1)
        u = min(max(u, 0.0), self._ancho - 1.0)
        v = min(max(v, 0.0), self._alto - 1.0)
        i0, j0 = min(int(u), self._ancho - 2), min(int(v), self._alto - 2)
        fu, fv = u - i0, v - j0
        d, w = self._datos, self._ancho
        g = (d[j0 * w + i0] * (1 - fu) + d[j0 * w + i0 + 1] * fu) * (1 - fv) \
            + (d[(j0 + 1) * w + i0] * (1 - fu) + d[(j0 + 1) * w + i0 + 1] * fu) * fv
        return self._minimo + g / 255.0 * (self._maximo - self._minimo)

    # Lee un PNG (cualquier modo; se convierte a gris). None si no existe o no se puede leer
    # (Pillow viene con Ursina; se importa aquí para que el backend no dependa de él).
    @staticmethod
    def desde_png(ruta, limites, minimo, maximo):
        try:
            from PIL import Image
            with Image.open(ruta) as imagen:
                gris = imagen.convert("L")
                ancho, alto = gris.size
                datos = list(gris.getdata())
            return MapaAlturas(ancho, alto, datos, limites, minimo, maximo)
        except (OSError, ImportError, ValueError):
            return None


class Terreno:

    def __init__(self, plataformas=(), cajas=(), calles=(), limites=(0.0, 0.0, 0.0, 0.0),
                 plano_ladera=(0.0, 0.0, 0.0), amplitud=0.0, longitud_onda=45.0, semilla=0,
                 ancho_talud=ANCHO_TALUD, mapa_alturas=None, elevaciones=None):
        self._plataformas = tuple(plataformas)
        self._cajas = tuple(cajas)
        self._calles = tuple(calles)
        self._limites = tuple(limites)
        self._plano = tuple(plano_ladera)          # (a, b, c): a·x + b·z + c
        self._amplitud = amplitud
        self._ancho_talud = max(ancho_talud, 0.1)
        self._mapa_alturas = mapa_alturas
        self.elevaciones = dict(elevaciones or {})
        # Tres ondas con dirección y fase fijadas por la semilla.
        azar = random.Random(semilla)
        k = 2 * math.pi / max(longitud_onda, 1.0)
        self._ondas = []
        for factor in (1.0, 1.7, 2.9):
            ang = azar.uniform(0, 2 * math.pi)
            self._ondas.append((math.cos(ang) * k * factor, math.sin(ang) * k * factor,
                                azar.uniform(0, 2 * math.pi), 1.0 / factor))
        self._elementos = self._plataformas + self._cajas + self._calles

    # Terreno sin relieve: altura 0 en todas partes.
    @staticmethod
    def plano(limites=(0.0, 0.0, 0.0, 0.0)):
        return Terreno(limites=limites)

    # Construye el terreno de un mundo (duck typing: `mapa` con lugares()/coordenada()/segmentos()/
    # ancho_calle/radio_plaza y `edificios` con .lugar y .caja()). `elevacion_lugar` {lugar: metros}.
    # ValueError si falta la cota de algún lugar.
    @staticmethod
    def desde_mundo(mapa, edificios, elevacion_lugar, limites, semilla=2026, amplitud=0.6,
                    longitud_onda=45.0, ruta_heightmap=None, heightmap_metros=(0.0, 10.0)):
        faltan = [lugar for lugar in mapa.lugares() if lugar not in elevacion_lugar]
        if faltan:
            raise ValueError(f"Falta la elevación de: {', '.join(map(str, faltan))}.")
        radio = mapa.radio_plaza
        plataformas = [Plataforma(*mapa.coordenada(lugar), radio + 0.9, elevacion_lugar[lugar])
                       for lugar in mapa.lugares()]
        cajas = []
        for e in edificios:
            x0, x1, z0, z1 = e.caja()
            cajas.append(CajaPlana(x0 - MARGEN_EDIFICIO, x1 + MARGEN_EDIFICIO,
                                   z0 - MARGEN_EDIFICIO, z1 + MARGEN_EDIFICIO, elevacion_lugar[e.lugar]))
        calles = []
        for a, b in mapa.segmentos():
            (ax, az), (bx, bz) = mapa.coordenada(a), mapa.coordenada(b)
            calles.append(Calle(a, b, ax, az, bx, bz, elevacion_lugar[a], elevacion_lugar[b],
                                mapa.ancho_calle / 2 + EXTRA_ACERA, radio + 0.9, radio + 0.9))
        mapa_alturas = None
        if ruta_heightmap is not None:
            mapa_alturas = MapaAlturas.desde_png(ruta_heightmap, limites, *heightmap_metros)
        puntos = [(*mapa.coordenada(lugar), elevacion_lugar[lugar]) for lugar in mapa.lugares()]
        return Terreno(plataformas, cajas, calles, limites, _ajustar_plano(puntos), amplitud,
                       longitud_onda, semilla, mapa_alturas=mapa_alturas,
                       elevaciones={lugar: elevacion_lugar[lugar] for lugar in mapa.lugares()})

    # -- Consulta --

    @property
    def es_plano(self):
        return (not self._elementos and self._mapa_alturas is None and self._amplitud == 0
                and not any(self._plano))

    @property
    def calles(self):
        return self._calles

    def limites(self):
        return self._limites

    def elevacion_lugar(self, lugar):
        return self.elevaciones.get(lugar, 0.0)

    # Relieve natural (sin lo construido).
    def natural(self, x, z):
        if self._mapa_alturas is not None:
            return self._mapa_alturas.altura(x, z)
        a, b, c = self._plano
        h = a * x + b * z + c
        if self._amplitud:
            h += self._amplitud * sum(
                peso * math.sin(kx * x + kz * z + fase) for kx, kz, fase, peso in self._ondas) / 1.6
        return h

    # Peso de cada elemento: 1/(d+eps)^3 (domina el más cercano y es exacto sobre lo construido);
    # la mezcla con la ladera usa el elemento más cercano y un smoothstep del talud.
    def altura(self, x, z):
        if self.es_plano:
            return 0.0
        natural = self.natural(x, z)
        if not self._elementos:
            return natural
        suma_w = suma_h = 0.0
        dmin = math.inf
        for elemento in self._elementos:
            d = elemento.distancia(x, z)
            if d < dmin:
                dmin = d
            if d < self._ancho_talud * 2:
                w = 1.0 / (d + _EPS) ** 3
                suma_w += w
                suma_h += w * elemento.cota(x, z)
        if suma_w == 0.0:
            return natural
        fuerza = 1.0 - _suavizar(dmin / self._ancho_talud)
        return natural + (suma_h / suma_w - natural) * fuerza

    # Distancia (m) al elemento construido más cercano (0 = sobre lo construido, inf = no hay).
    def distancia_a_lo_construido(self, x, z):
        return min((e.distancia(x, z) for e in self._elementos), default=math.inf)

    # Módulo del gradiente (fracción: 0.15 = 15 %), por diferencias centrales de `paso` m.
    def pendiente(self, x, z, paso=0.5):
        if self.es_plano:
            return 0.0
        dx = (self.altura(x + paso, z) - self.altura(x - paso, z)) / (2 * paso)
        dz = (self.altura(x, z + paso) - self.altura(x, z - paso)) / (2 * paso)
        return math.hypot(dx, dz)

    # Calles cuya rampa supera `maxima`: [(a, b, pendiente)]. Vacío = todo en orden.
    def calles_demasiado_empinadas(self, maxima=PENDIENTE_MAXIMA_CALLE):
        return [(c.a, c.b, c.pendiente) for c in self._calles if c.pendiente > maxima + 1e-9]

    # ValueError si alguna calle supera la pendiente máxima.
    def validar_calles(self, maxima=PENDIENTE_MAXIMA_CALLE):
        malas = self.calles_demasiado_empinadas(maxima)
        if malas:
            detalle = "; ".join(f"{a} - {b}: {p * 100:.1f} %" for a, b, p in malas)
            raise ValueError(f"Calles con pendiente mayor a {maxima * 100:.0f} %: {detalle}.")


# Plano a·x + b·z + c por mínimos cuadrados; (0, 0, media) si los puntos son colineales.
def _ajustar_plano(puntos):
    n = len(puntos)
    if n == 0:
        return (0.0, 0.0, 0.0)
    sx = sum(p[0] for p in puntos)
    sz = sum(p[1] for p in puntos)
    sh = sum(p[2] for p in puntos)
    sxx = sum(p[0] * p[0] for p in puntos)
    szz = sum(p[1] * p[1] for p in puntos)
    sxz = sum(p[0] * p[1] for p in puntos)
    sxh = sum(p[0] * p[2] for p in puntos)
    szh = sum(p[1] * p[2] for p in puntos)
    m = ((sxx, sxz, sx), (sxz, szz, sz), (sx, sz, n))
    r = (sxh, szh, sh)
    det = _det3(m)
    if abs(det) < 1e-9:
        return (0.0, 0.0, sh / n)
    sol = []
    for col in range(3):
        mc = tuple(tuple(r[i] if j == col else m[i][j] for j in range(3)) for i in range(3))
        sol.append(_det3(mc) / det)
    return tuple(sol)


def _det3(m):
    return (m[0][0] * (m[1][1] * m[2][2] - m[1][2] * m[2][1])
            - m[0][1] * (m[1][0] * m[2][2] - m[1][2] * m[2][0])
            + m[0][2] * (m[1][0] * m[2][1] - m[1][1] * m[2][0]))
