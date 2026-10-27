# Terreno para el mapa grande (datos puros, sin ursina). terreno.py NO se toca: esto es una subclase.
#
#   - TerrenoGrande(Terreno): ladera con más relieve y desnivel (~80 m en ~900 x 650 m), altura_exacta
#     indexada (solo evalúa las piezas a menos de TRANSICION m, no todas) y altura(x, z) con grillas de
#     chunk de 64 m calculadas perezosamente (caché LRU con candado). Los nodos de las grillas son los
#     MISMOS de la grilla global de Terreno (origen = extension, paso PASO_GRILLA), así que altura()
#     da el mismo número que Terreno.altura y en los nodos coincide con altura_exacta.
#   - acelerar_terreno(terreno): le pone a un Terreno ya construido (el del mundo chico) el mismo
#     altura_exacta indexado y una construcción de grilla más rápida, con resultados idénticos bit a bit.
#     Es opcional: quien la llame (detrás de una bandera) decide; sin llamarla nada cambia.
#
# Con los parámetros del mundo chico (desnivel=DESNIVEL, ondas=()) TerrenoGrande == Terreno.

import math
import threading
from collections import OrderedDict

from backend.datos import terreno as _t
from backend.datos.indice_espacial import IndiceUniforme
from backend.datos.terreno import Terreno, TRANSICION, PASO_GRILLA, _Circulo, _Franja, _Rectangulo, _EPS2

DESNIVEL_GRANDE = 80.0          # m entre lo más bajo y lo más alto de la ladera del mapa grande
LADO_CHUNK = 64.0               # m
CELDA_INDICE = 16.0             # m de cada celda del índice de piezas
CHUNKS_EN_CACHE = 128           # ~35 MB como máximo (65 x 65 alturas por chunk)

# (amplitud m, longitud_x m, longitud_z m, fase_x, fase_z): término a * sin(x/lx + fx) * sin(z/lz + fz).
# Lomas de ~250 m y ondulación media de ~70 m encima del plano y del ondulado de siempre.
ONDAS_GRANDES = (
    (4.5, 260.0 / (2 * math.pi), 310.0 / (2 * math.pi), 0.4, 1.1),
    (3.0, 190.0 / (2 * math.pi), 230.0 / (2 * math.pi), 2.3, 0.2),
    (1.2, 70.0 / (2 * math.pi), 85.0 / (2 * math.pi), 1.0, 2.7),
)

_PESO_LADERA = 1.0 / TRANSICION ** 2


def _caja_de_pieza(p, margen):
    """Caja (xmin, xmax, zmin, zmax) que contiene todo punto a menos de `margen` m de la pieza."""
    if isinstance(p, _Circulo):
        r = p.radio + margen
        return p.cx - r, p.cx + r, p.cz - r, p.cz + r
    if isinstance(p, _Franja):
        bx, bz = p.ax + p.dx, p.az + p.dz
        r = p.semiancho + margen
        return min(p.ax, bx) - r, max(p.ax, bx) + r, min(p.az, bz) - r, max(p.az, bz) + r
    if isinstance(p, _Rectangulo):
        xmin, xmax, zmin, zmax = p.caja
        return xmin - margen, xmax + margen, zmin - margen, zmax + margen
    return -1e12, 1e12, -1e12, 1e12      # pieza desconocida: siempre candidata


def _indexar_piezas(piezas):
    """IndiceUniforme de los `medir` de las piezas (en su orden original; ver Terreno.altura_exacta)."""
    indice = IndiceUniforme(CELDA_INDICE)
    for p in piezas:
        indice.insertar(p.medir, _caja_de_pieza(p, TRANSICION))
    return indice


def _sumar(x, z, natural, candidatos):
    """Misma cuenta que Terreno.altura_exacta (mismo orden de suma => mismo resultado bit a bit),
    pero solo con las piezas candidatas de la celda."""
    suma_pesos = _PESO_LADERA
    suma = suma_pesos * natural
    for _, medir in candidatos:
        d, h = medir(x, z)
        if d >= TRANSICION:
            continue
        u = d / TRANSICION
        peso = (1 - u * u * (3 - 2 * u)) / (d * d + _EPS2)
        suma += peso * h
        suma_pesos += peso
    return suma / suma_pesos


class _Evaluador:
    """altura_exacta indexada de un Terreno ya construido."""

    def __init__(self, terreno, natural=None):
        self.indice = _indexar_piezas(terreno._piezas)
        self._natural = natural or terreno.altura_natural
        self._inv = 1.0 / CELDA_INDICE

    def altura_exacta(self, x, z):
        f = math.floor
        inv = self._inv
        cand = self.indice._celdas.get((f(x * inv), f(z * inv)), ())
        return _sumar(x, z, self._natural(x, z), cand)

    def nodos(self, x_inicial, z_inicial, i0, i1, j0, j1):
        """filas[j - j0][i - i0] = altura_exacta(x_inicial + i*PASO, z_inicial + j*PASO)."""
        f = math.floor
        inv = self._inv
        celdas = self.indice._celdas
        natural = self._natural
        filas = []
        for j in range(j0, j1 + 1):
            z = z_inicial + j * PASO_GRILLA
            kz = f(z * inv)
            fila = []
            for i in range(i0, i1 + 1):
                x = x_inicial + i * PASO_GRILLA
                fila.append(_sumar(x, z, natural(x, z), celdas.get((f(x * inv), kz), ())))
            filas.append(fila)
        return filas


def acelerar_terreno(terreno):
    """Acelera un Terreno ya construido SIN cambiar ningún resultado: altura_exacta (y por tanto la
    grilla de altura/grilla()) evalúa solo las piezas cercanas. Devuelve el mismo objeto.
    Idempotente. Para volver atrás: del terreno.altura_exacta, del terreno._construir_grilla."""
    if getattr(terreno, "_acelerado", False):
        return terreno
    ev = _Evaluador(terreno)

    def _construir_grilla():
        x0, x1, z0, z1 = terreno.extension
        terreno._nx = int(math.ceil((x1 - x0) / PASO_GRILLA)) + 1
        terreno._nz = int(math.ceil((z1 - z0) / PASO_GRILLA)) + 1
        terreno._grilla = ev.nodos(x0, z0, 0, terreno._nx - 1, 0, terreno._nz - 1)

    terreno.altura_exacta = ev.altura_exacta
    terreno._construir_grilla = _construir_grilla
    terreno._acelerado = True
    return terreno


class TerrenoGrande(Terreno):
    """Terreno de mapa grande. Parámetros extra sobre Terreno:
       ondas: relieve extra (ver ONDAS_GRANDES); () = el ondulado de siempre.
       chunks_en_cache: tamaño de la caché LRU de grillas de chunk.
    Usa TerrenoGrande.para_mapa_grande(...) para desnivel 80 m y relieve grande."""

    def __init__(self, mapa, edificios, limites, desnivel=_t.DESNIVEL, pendiente_maxima=_t.PENDIENTE_MAXIMA,
                 zonas_planas=(), ondas=(), chunks_en_cache=CHUNKS_EN_CACHE):
        self._ondas = tuple(ondas)          # antes de super(): altura_natural se usa ahí dentro
        super().__init__(mapa, edificios, limites, desnivel=desnivel, pendiente_maxima=pendiente_maxima,
                         zonas_planas=zonas_planas)
        self._evaluador = _Evaluador(self, natural=self.altura_natural)
        x0, x1, z0, z1 = self.extension
        self._x0, self._z0 = x0, z0
        self._nx = int(math.ceil((x1 - x0) / PASO_GRILLA)) + 1
        self._nz = int(math.ceil((z1 - z0) / PASO_GRILLA)) + 1
        self.celdas_chunk = max(1, int(round(LADO_CHUNK / PASO_GRILLA)))
        self.chunks_x = (self._nx - 2) // self.celdas_chunk + 1
        self.chunks_z = (self._nz - 2) // self.celdas_chunk + 1
        self._max_cache = max(1, int(chunks_en_cache))
        self._cache = OrderedDict()
        self._candado = threading.Lock()
        self.chunks_calculados = 0

    @classmethod
    def para_mapa_grande(cls, mapa, edificios, limites, zonas_planas=(), **kw):
        kw.setdefault("desnivel", DESNIVEL_GRANDE)
        kw.setdefault("ondas", ONDAS_GRANDES)
        return cls(mapa, edificios, limites, zonas_planas=zonas_planas, **kw)

    # -- Consultas --

    def altura_natural(self, x, z):
        h = Terreno.altura_natural(self, x, z)
        for a, lx, lz, fx, fz in self._ondas:
            h += a * math.sin(x / lx + fx) * math.sin(z / lz + fz)
        return h

    def altura_exacta(self, x, z):
        return self._evaluador.altura_exacta(x, z)

    def grilla_de_chunk(self, ci, cj):
        """Filas del chunk (ci, cj): filas[j][i] = altura_exacta en el nodo global (ci*N + i, cj*N + j),
        N = celdas_chunk (65 x 65 nodos con el borde compartido; menos si toca el final de la grilla).
        Calculada la primera vez y guardada en la caché LRU."""
        if not (0 <= ci < self.chunks_x and 0 <= cj < self.chunks_z):
            raise IndexError(f"chunk ({ci}, {cj}) fuera de rango ({self.chunks_x} x {self.chunks_z})")
        clave = (ci, cj)
        with self._candado:
            g = self._cache.get(clave)
            if g is not None:
                self._cache.move_to_end(clave)
                return g
        g = self._calcular_chunk(ci, cj)         # fuera del candado: otro hilo puede pedir otro chunk
        with self._candado:
            previo = self._cache.get(clave)
            if previo is not None:               # otro hilo llegó primero: mismos números
                self._cache.move_to_end(clave)
                return previo
            self._cache[clave] = g
            self.chunks_calculados += 1
            while len(self._cache) > self._max_cache:
                self._cache.popitem(last=False)
        return g

    def _calcular_chunk(self, ci, cj):
        n = self.celdas_chunk
        i0, j0 = ci * n, cj * n
        i1, j1 = min(i0 + n, self._nx - 1), min(j0 + n, self._nz - 1)
        return self._evaluador.nodos(self._x0, self._z0, i0, i1, j0, j1)

    def origen_chunk(self, ci, cj):
        """(x, z) del primer nodo del chunk."""
        n = self.celdas_chunk
        return self._x0 + ci * n * PASO_GRILLA, self._z0 + cj * n * PASO_GRILLA

    def chunks_en_cache(self):
        with self._candado:
            return len(self._cache)

    # Bilineal sobre las grillas de chunk (mismos nodos que la grilla global de Terreno).
    def altura(self, x, z):
        fx = (x - self._x0) / PASO_GRILLA
        fz = (z - self._z0) / PASO_GRILLA
        if fx != fx:                              # NaN: se acota al borde (inf ya se acota abajo); nunca lanza
            fx = 0.0
        if fz != fz:
            fz = 0.0
        tope_x, tope_z = self._nx - 1.000001, self._nz - 1.000001
        fx = 0.0 if fx < 0.0 else (tope_x if fx > tope_x else fx)
        fz = 0.0 if fz < 0.0 else (tope_z if fz > tope_z else fz)
        i, j = int(fx), int(fz)
        tx, tz = fx - i, fz - j
        n = self.celdas_chunk
        ci, cj = i // n, j // n
        g = self._cache.get((ci, cj))            # lectura sin candado: dict.get es atómico
        if g is None:
            g = self.grilla_de_chunk(ci, cj)
        else:
            with self._candado:                  # marca de uso (LRU); si lo sacaron, no importa
                if (ci, cj) in self._cache:
                    self._cache.move_to_end((ci, cj))
        li, lj = i - ci * n, j - cj * n
        fila0 = g[lj]
        fila1 = g[lj + 1]
        abajo = fila0[li] + (fila0[li + 1] - fila0[li]) * tx
        arriba = fila1[li] + (fila1[li + 1] - fila1[li]) * tx
        return abajo + (arriba - abajo) * tz

    # Igual que Terreno.grilla() pero armada con los chunks: costosa en el mapa grande (no la guarda).
    def grilla(self):
        n = self.celdas_chunk
        filas = [[] for _ in range(self._nz)]
        for cj in range(self.chunks_z):
            for ci in range(self.chunks_x):
                g = self._calcular_chunk(ci, cj)
                for lj, fila in enumerate(g):
                    j = cj * n + lj
                    destino = filas[j]
                    ini = ci * n
                    if len(destino) > ini:      # el borde compartido ya está
                        del destino[ini:]
                    destino.extend(fila)
        return self._x0, self._z0, PASO_GRILLA, filas

    def _construir_grilla(self):
        raise NotImplementedError("TerrenoGrande usa grillas de chunk; ver grilla_de_chunk()")
