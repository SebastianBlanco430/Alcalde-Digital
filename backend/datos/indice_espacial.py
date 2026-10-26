# Índices espaciales puros (sin ursina) para consultas "qué hay cerca de (x, z)" sin recorrer todo:
#   - IndiceUniforme: rejilla uniforme de celdas; guarda cualquier objeto con su caja.
#   - SegmentosIndexados: distancia mínima a un conjunto grande de segmentos (calles, callejones).
# Pensados para el mapa grande (miles de casas y segmentos); no cambian nada del mundo chico.

import math


def _distancia_punto_segmento(px, pz, ax, az, bx, bz):
    dx, dz = bx - ax, bz - az
    largo2 = dx * dx + dz * dz
    if largo2 < 1e-18:
        return math.hypot(px - ax, pz - az)
    t = ((px - ax) * dx + (pz - az) * dz) / largo2
    t = 0.0 if t < 0.0 else (1.0 if t > 1.0 else t)
    return math.hypot(px - (ax + dx * t), pz - (az + dz * t))


class IndiceUniforme:
    """Rejilla uniforme de `celda` m. insertar(item, caja) con caja = (xmin, xmax, zmin, zmax);
    cerca(x, z, r) devuelve los items cuya caja toca el cuadrado [x-r, x+r] x [z-r, z+r] (sin repetir y
    en orden de inserción). Es conservador: puede devolver items algo lejanos, nunca omite uno cercano."""

    def __init__(self, celda=16.0):
        if celda <= 0:
            raise ValueError("celda debe ser > 0")
        self.celda = float(celda)
        self._inv = 1.0 / self.celda
        self._celdas = {}        # (ix, iz) -> lista de (orden, item)
        self._n = 0

    def __len__(self):
        return self._n

    def _rango(self, xmin, xmax, zmin, zmax):
        f = math.floor
        inv = self._inv
        return f(xmin * inv), f(xmax * inv), f(zmin * inv), f(zmax * inv)

    def insertar(self, item, caja):
        xmin, xmax, zmin, zmax = caja
        if xmax < xmin or zmax < zmin:
            raise ValueError("caja invertida")
        orden = self._n
        self._n += 1
        i0, i1, j0, j1 = self._rango(xmin, xmax, zmin, zmax)
        celdas = self._celdas
        entrada = (orden, item)
        for i in range(i0, i1 + 1):
            for j in range(j0, j1 + 1):
                celdas.setdefault((i, j), []).append(entrada)

    def cerca(self, x, z, r=0.0):
        i0, i1, j0, j1 = self._rango(x - r, x + r, z - r, z + r)
        celdas = self._celdas
        if i0 == i1 and j0 == j1:
            lista = celdas.get((i0, j0))
            return [it for _, it in lista] if lista else []
        vistos = {}
        for i in range(i0, i1 + 1):
            for j in range(j0, j1 + 1):
                for orden, it in celdas.get((i, j), ()):
                    vistos[orden] = it
        return [vistos[o] for o in sorted(vistos)]

    def en_celda(self, x, z):
        """Camino rápido: la lista INTERNA de (orden, item) de la celda de (x, z). No la modifiques."""
        return self._celdas.get((math.floor(x * self._inv), math.floor(z * self._inv)), ())

    def celdas_ocupadas(self):
        return len(self._celdas)


class SegmentosIndexados:
    """Segmentos ((ax, az), (bx, bz)) indexados en una rejilla. distancia_minima(x, z, tope) devuelve la
    distancia al segmento más cercano si es menor que `tope`; si no hay ninguno a menos de `tope`
    devuelve `tope`. Con tope=None busca sin límite (ensancha el radio hasta encontrar)."""

    def __init__(self, segmentos=(), celda=32.0):
        self._indice = IndiceUniforme(celda)
        self._segmentos = []
        self._caja = None
        for s in segmentos:
            self.agregar(s)

    def __len__(self):
        return len(self._segmentos)

    def agregar(self, segmento):
        (ax, az), (bx, bz) = segmento
        k = len(self._segmentos)
        self._segmentos.append((ax, az, bx, bz))
        c = self._indice.celda
        mitad = c * 0.7071068            # media diagonal de la celda: criterio conservador
        xmin, xmax = min(ax, bx), max(ax, bx)
        zmin, zmax = min(az, bz), max(az, bz)
        self._caja = (xmin, xmax, zmin, zmax) if self._caja is None else (
            min(self._caja[0], xmin), max(self._caja[1], xmax), min(self._caja[2], zmin), max(self._caja[3], zmax))
        idx = self._indice
        i0, i1, j0, j1 = idx._rango(xmin, xmax, zmin, zmax)
        entrada = (k, k)
        for i in range(i0, i1 + 1):
            for j in range(j0, j1 + 1):
                if (i1 - i0 + 1) * (j1 - j0 + 1) > 1:
                    if _distancia_punto_segmento((i + 0.5) * c, (j + 0.5) * c, ax, az, bx, bz) > mitad:
                        continue
                idx._celdas.setdefault((i, j), []).append(entrada)
        idx._n += 1

    def _minimo(self, x, z, r):
        mejor = math.inf
        segs = self._segmentos
        for k in self._indice.cerca(x, z, r):
            ax, az, bx, bz = segs[k]
            d = _distancia_punto_segmento(x, z, ax, az, bx, bz)
            if d < mejor:
                mejor = d
        return mejor

    def distancia_minima(self, x, z, tope=None):
        if not self._segmentos:
            return math.inf if tope is None else tope
        if tope is not None:
            d = self._minimo(x, z, tope)
            return d if d < tope else tope
        xmin, xmax, zmin, zmax = self._caja
        maximo = math.hypot(max(abs(x - xmin), abs(x - xmax)), max(abs(z - zmin), abs(z - zmax))) + self._indice.celda
        r = self._indice.celda
        while True:
            d = self._minimo(x, z, r)
            if d <= r or r >= maximo:       # hallado a distancia <= r: ningún otro puede ser más cercano
                return d
            r *= 2.0

    def cerca(self, x, z, r):
        """Índices de los segmentos que podrían estar a menos de r de (x, z) (conservador)."""
        return self._indice.cerca(x, z, r)
