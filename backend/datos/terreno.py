# Terreno en ladera de Ciudad Nova (datos puros, sin ursina): la función altura(x, z) que usan
# el backend (colocar edificios, puertas y spawns) y el frontend (malla del suelo, personajes,
# cámara). Determinista: misma ciudad, mismo terreno.
#
# Forma:
#   - Ladera natural: un plano inclinado de DESNIVEL m (de la esquina baja a la alta del mapa
#     más MARGEN_LADERA alrededor) más un ondulado suave de unos ±AMPLITUD_ONDULADO m.
#   - Terrazas planas: cada plaza (con su aro), cada lote de edificio y el camino plaza -> puerta
#     están a la altura de su plaza.
#   - Calles: rampas rectas entre las dos plazas que unen; planas dentro de cada plaza y lineales
#     en el tramo libre. La altura de las plazas se ajusta (ajustar_alturas) para que ninguna
#     rampa pase de PENDIENTE_MAXIMA grados.
#   - Entre una pieza y otra (y la ladera) la altura se mezcla por distancia (Shepard de potencia 2
#     con caída suave hasta TRANSICION m), así que adentro de cada pieza la altura es la suya
#     (error < 1 mm) y afuera la ladera la va recuperando.
#
# Con plazas planas de radio 9 m y calles de 32 a 37 m, las rampas miden 14-19 m: a 15° la red de
# calles sube como mucho ~13 m (hoy ~8.7 m). El resto del DESNIVEL está en la ladera alrededor.
# Donde un lote y una calle cercanos quedan a distinta altura la mezcla forma taludes empinados
# (~0.4 % del terreno pasa de 30°): son los lugares para muros de contención.
#
# altura(x, z) lee una grilla precalculada (PASO_GRILLA m) con interpolación bilineal: rápido para
# llamarla cada frame. altura_exacta(x, z) evalúa la fórmula (más lento, para tests y la grilla).

import math

DESNIVEL = 25.0                 # m entre lo más bajo y lo más alto de la ladera natural
DIRECCION_SUBIDA = (-0.8, 0.6)  # hacia dónde sube la ladera en (x, z): del Hospital a la Prefeitura
MARGEN_LADERA = 40.0            # m de ladera alrededor de los límites del mapa
AMPLITUD_ONDULADO = 1.5         # m
PENDIENTE_MAXIMA = 15.0         # grados, en las calles
PENDIENTE_CAMINABLE = 32.0      # grados: los taludes más empinados no se pueden caminar
MARGEN_PENDIENTE = 1.0          # grados: las plazas se ajustan a 14° porque la mezcla con lotes y
                                # accesos vecinos agrega un poco en algunas rampas
TRANSICION = 10.0               # m en los que una pieza plana se funde con la ladera
BORDE_PLAZA = 1.5               # m planos alrededor de la plaza (aro y un poco más)
BORDE_CALLE = 2.0               # m planos a cada lado del asfalto (aceras)
BORDE_LOTE = 1.5                # m planos alrededor de un edificio
SEMIANCHO_ACCESO = 2.5          # m: medio ancho del camino plaza -> puerta
BORDE_ZONA = 1.0                # m planos alrededor de una zona plana (cancha, mercadito)
PASO_GRILLA = 1.0               # m
_EPS2 = 0.05 ** 2               # suaviza el peso en distancia 0 (sin saltos entre piezas)
_ITERACIONES_AJUSTE = 500


def _suave(t):
    t = min(1.0, max(0.0, t))
    return t * t * (3 - 2 * t)


# -- Piezas planas ------------------------------------------------------------------------------
# Cada pieza devuelve (distancia, altura): distancia 0 adentro, y la altura de la pieza en el
# punto más cercano.


class _Circulo:
    def __init__(self, cx, cz, radio, altura):
        self.cx, self.cz, self.radio, self.h = cx, cz, radio, altura

    def medir(self, x, z):
        return max(0.0, math.hypot(x - self.cx, z - self.cz) - self.radio), self.h


class _Franja:
    """Segmento a -> b con medio ancho: plano en ha hasta `plano_a` m desde a, plano en hb en
    los últimos `plano_b` m, y una rampa lineal en el medio."""

    def __init__(self, a, b, semiancho, ha, hb, plano_a=0.0, plano_b=0.0):
        self.ax, self.az = a
        self.dx, self.dz = b[0] - a[0], b[1] - a[1]
        self.largo = math.hypot(self.dx, self.dz)
        self.semiancho = semiancho
        self.ha, self.hb = ha, hb
        self.plano_a, self.plano_b = plano_a, plano_b

    def altura_en(self, s):
        tramo = self.largo - self.plano_a - self.plano_b
        if tramo <= 1e-9:
            return (self.ha + self.hb) / 2
        t = min(1.0, max(0.0, (s - self.plano_a) / tramo))
        return self.ha + (self.hb - self.ha) * t

    def medir(self, x, z):
        if self.largo < 1e-9:
            return max(0.0, math.hypot(x - self.ax, z - self.az) - self.semiancho), self.ha
        s = ((x - self.ax) * self.dx + (z - self.az) * self.dz) / self.largo
        s = min(self.largo, max(0.0, s))
        px = self.ax + self.dx * s / self.largo
        pz = self.az + self.dz * s / self.largo
        return max(0.0, math.hypot(x - px, z - pz) - self.semiancho), self.altura_en(s)


class _Rectangulo:
    def __init__(self, xmin, xmax, zmin, zmax, altura):
        self.caja = (xmin, xmax, zmin, zmax)
        self.h = altura

    def medir(self, x, z):
        xmin, xmax, zmin, zmax = self.caja
        dx = max(xmin - x, 0.0, x - xmax)
        dz = max(zmin - z, 0.0, z - zmax)
        return math.hypot(dx, dz), self.h


# -- Terreno -------------------------------------------------------------------------------------


class Terreno:

    # limites: (xmin, xmax, zmin, zmax) del mapa; la ladera y la grilla los cubren con MARGEN_LADERA.
    # zonas_planas: rectángulos (cx, cz, ancho, fondo) que se aplanan a la altura natural de su centro
    # (la cancha y el mercadito de la favela); opcional: sin ellas el terreno es el de siempre.
    def __init__(self, mapa, edificios, limites, desnivel=DESNIVEL, pendiente_maxima=PENDIENTE_MAXIMA,
                 zonas_planas=()):
        self.pendiente_maxima = pendiente_maxima
        xmin, xmax, zmin, zmax = limites
        self.extension = (xmin - MARGEN_LADERA, xmax + MARGEN_LADERA, zmin - MARGEN_LADERA, zmax + MARGEN_LADERA)
        ux, uz = DIRECCION_SUBIDA
        norma = math.hypot(ux, uz)
        self._subida = (ux / norma, uz / norma)
        esquinas = [(x, z) for x in self.extension[:2] for z in self.extension[2:]]
        proyecciones = [x * self._subida[0] + z * self._subida[1] for x, z in esquinas]
        self._p_min, self._p_max = min(proyecciones), max(proyecciones)
        self._desnivel = desnivel

        self.plano_plaza = mapa.radio_plaza + BORDE_PLAZA
        naturales = {lugar: self.altura_natural(*mapa.coordenada(lugar)) for lugar in mapa.lugares()}
        self.calles = [(a, b, math.dist(mapa.coordenada(a), mapa.coordenada(b))) for a, b in mapa.segmentos()]
        self.alturas_plaza = ajustar_alturas(naturales, self.calles, self.plano_plaza,
                                             pendiente_maxima - MARGEN_PENDIENTE)

        self._piezas = []
        for lugar in mapa.lugares():
            cx, cz = mapa.coordenada(lugar)
            self._piezas.append(_Circulo(cx, cz, self.plano_plaza, self.alturas_plaza[lugar]))
        semiancho_calle = mapa.ancho_calle / 2 + BORDE_CALLE
        for a, b, _ in self.calles:
            self._piezas.append(_Franja(mapa.coordenada(a), mapa.coordenada(b), semiancho_calle,
                                        self.alturas_plaza[a], self.alturas_plaza[b],
                                        self.plano_plaza, self.plano_plaza))
        for e in edificios:
            h = self.alturas_plaza[e.lugar]
            self._piezas.append(_Rectangulo(e.cx - e.ancho / 2 - BORDE_LOTE, e.cx + e.ancho / 2 + BORDE_LOTE,
                                            e.cz - e.fondo / 2 - BORDE_LOTE, e.cz + e.fondo / 2 + BORDE_LOTE, h))
            self._piezas.append(_Franja(mapa.coordenada(e.lugar), e.puerta(), SEMIANCHO_ACCESO, h, h))
        for cx, cz, ancho, fondo in zonas_planas:
            self._piezas.append(_Rectangulo(cx - ancho / 2 - BORDE_ZONA, cx + ancho / 2 + BORDE_ZONA,
                                            cz - fondo / 2 - BORDE_ZONA, cz + fondo / 2 + BORDE_ZONA,
                                            self.altura_natural(cx, cz)))
        self._grilla = None

    # -- Consultas --

    def altura_natural(self, x, z):
        p = x * self._subida[0] + z * self._subida[1]
        plano = self._desnivel * (p - self._p_min) / (self._p_max - self._p_min)
        ondulado = AMPLITUD_ONDULADO * (0.6 * math.sin(x / 17.0 + 0.7) * math.cos(z / 23.0 - 0.4)
                                        + 0.4 * math.sin((x + z) / 11.0 + 1.9))
        return plano + ondulado

    def altura_exacta(self, x, z):
        suma_pesos = 1.0 / TRANSICION ** 2              # peso de la ladera natural
        suma = suma_pesos * self.altura_natural(x, z)
        for pieza in self._piezas:
            d, h = pieza.medir(x, z)
            if d >= TRANSICION:
                continue
            peso = (1 - _suave(d / TRANSICION)) / (d * d + _EPS2)
            suma += peso * h
            suma_pesos += peso
        return suma / suma_pesos

    # Bilineal sobre la grilla (fuera de la extensión, el borde más cercano).
    def altura(self, x, z):
        if self._grilla is None:
            self._construir_grilla()
        x0, _, z0, _ = self.extension
        fx = min(max((x - x0) / PASO_GRILLA, 0.0), self._nx - 1.000001)
        fz = min(max((z - z0) / PASO_GRILLA, 0.0), self._nz - 1.000001)
        i, j = int(fx), int(fz)
        tx, tz = fx - i, fz - j
        g = self._grilla
        fila0, fila1 = g[j], g[j + 1]
        abajo = fila0[i] + (fila0[i + 1] - fila0[i]) * tx
        arriba = fila1[i] + (fila1[i + 1] - fila1[i]) * tx
        return abajo + (arriba - abajo) * tz

    # (x0, z0, paso, filas): la grilla tal cual, filas[j][i] = altura en (x0 + i*paso, z0 + j*paso).
    # Para que el frontend arme la malla del suelo con los mismos vértices.
    def grilla(self):
        if self._grilla is None:
            self._construir_grilla()
        return self.extension[0], self.extension[2], PASO_GRILLA, self._grilla

    # Pendiente del suelo en (x, z), en grados (diferencias centrales sobre la grilla).
    def pendiente(self, x, z, h=0.5):
        gx = (self.altura(x + h, z) - self.altura(x - h, z)) / (2 * h)
        gz = (self.altura(x, z + h) - self.altura(x, z - h)) / (2 * h)
        return math.degrees(math.atan(math.hypot(gx, gz)))

    def caminable(self, x, z):
        return self.pendiente(x, z) <= PENDIENTE_CAMINABLE

    def altura_plaza(self, lugar):
        return self.alturas_plaza[lugar]

    def _construir_grilla(self):
        x0, x1, z0, z1 = self.extension
        self._nx = int(math.ceil((x1 - x0) / PASO_GRILLA)) + 1
        self._nz = int(math.ceil((z1 - z0) / PASO_GRILLA)) + 1
        self._grilla = [[self.altura_exacta(x0 + i * PASO_GRILLA, z0 + j * PASO_GRILLA)
                         for i in range(self._nx)] for j in range(self._nz)]


# Alturas de las plazas lo más cerca posible de `naturales` sin que ninguna calle supere la
# pendiente: |ha - hb| <= tan(pendiente) * (largo - 2 * plano) para cada calle (a, b, largo).
# Proyección iterativa: cada calle que se pasa acerca sus dos plazas a partes iguales.
def ajustar_alturas(naturales, calles, plano, pendiente_maxima=PENDIENTE_MAXIMA):
    alturas = dict(naturales)
    tangente = math.tan(math.radians(pendiente_maxima))
    for _ in range(_ITERACIONES_AJUSTE):
        cambio = False
        for a, b, largo in calles:
            limite = tangente * max(0.0, largo - 2 * plano)
            diferencia = alturas[a] - alturas[b]
            exceso = abs(diferencia) - limite
            if exceso > 1e-9:
                ajuste = math.copysign(exceso / 2 + 1e-9, diferencia)
                alturas[a] -= ajuste
                alturas[b] += ajuste
                cambio = True
        if not cambio:
            break
    return alturas
