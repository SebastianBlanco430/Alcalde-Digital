# Conectividad del mundo caminable (datos puros, sin ursina): una rejilla de celdas libres sobre el
# plano (x, z) donde el CENTRO del jugador puede estar, y una búsqueda en anchura (BFS) para saber qué
# se alcanza desde dónde. Sirve para comprobar que los callejones de la favela no dejan bolsas
# cerradas y que los lugares, las puertas y los spawns siguen conectados.
#
# Cada obstáculo se "infla" por el radio del jugador (una caja se convierte en caja con esquinas
# redondeadas, un círculo suma su radio), así una celda libre es un lugar donde cabe el jugador. El
# paso entre celdas es de 8 vecinos, pero una diagonal solo vale si sus dos celdas laterales también
# están libres (no se corta la esquina de una pared).

import math
from collections import deque

from backend.logica.mundo_ciudad import RADIO_JUGADOR, _distancia_punto_caja

RESOLUCION = 0.5            # m por celda: un callejón de 1.5 m deja >= 2 celdas libres con radio 0.35


class Rejilla:

    # limites: (xmin, xmax, zmin, zmax) de la zona a evaluar.
    def __init__(self, limites, resolucion=RESOLUCION):
        self.limites = tuple(limites)
        self.paso = resolucion
        xmin, xmax, zmin, zmax = self.limites
        self.nx = int(math.floor((xmax - xmin) / resolucion)) + 1
        self.nz = int(math.floor((zmax - zmin) / resolucion)) + 1
        self.libre = bytearray(b"\x01") * (self.nx * self.nz)     # 1 = el jugador cabe aquí

    # Celda (i, j) que contiene el punto, o None si cae fuera de la rejilla.
    def celda(self, x, z):
        i = int(round((x - self.limites[0]) / self.paso))
        j = int(round((z - self.limites[2]) / self.paso))
        if 0 <= i < self.nx and 0 <= j < self.nz:
            return i, j
        return None

    def centro(self, i, j):
        return (self.limites[0] + i * self.paso, self.limites[2] + j * self.paso)

    def esta_libre(self, x, z):
        c = self.celda(x, z)
        return c is not None and bool(self.libre[c[1] * self.nx + c[0]])

    # Marca como ocupadas las celdas a menos de `radio` de la caja (xmin, xmax, zmin, zmax).
    def bloquear_caja(self, caja, radio):
        xmin, xmax, zmin, zmax = caja
        i0, i1 = self._rango(xmin - radio, xmax + radio, 0)
        j0, j1 = self._rango(zmin - radio, zmax + radio, 1)
        for j in range(j0, j1 + 1):
            z = self.limites[2] + j * self.paso
            fila = j * self.nx
            for i in range(i0, i1 + 1):
                x = self.limites[0] + i * self.paso
                if _distancia_punto_caja(x, z, caja) < radio:
                    self.libre[fila + i] = 0

    # Marca como ocupadas las celdas a menos de `radio` m del punto (cx, cz).
    def bloquear_circulo(self, cx, cz, radio):
        i0, i1 = self._rango(cx - radio, cx + radio, 0)
        j0, j1 = self._rango(cz - radio, cz + radio, 1)
        for j in range(j0, j1 + 1):
            z = self.limites[2] + j * self.paso
            for i in range(i0, i1 + 1):
                if math.hypot(self.limites[0] + i * self.paso - cx, z - cz) < radio:
                    self.libre[j * self.nx + i] = 0

    # Libera/ocupa celdas según `permitido(x, z)` (p. ej. pendiente caminable): lo que no se permite
    # queda ocupado, salvo las celdas que `excepcion(x, z)` rescata (p. ej. sobre una escalera).
    def bloquear_si_no(self, permitido, excepcion=None):
        for j in range(self.nz):
            z = self.limites[2] + j * self.paso
            for i in range(self.nx):
                if not self.libre[j * self.nx + i]:
                    continue
                x = self.limites[0] + i * self.paso
                if not permitido(x, z) and not (excepcion and excepcion(x, z)):
                    self.libre[j * self.nx + i] = 0

    def _rango(self, a, b, eje):
        origen = self.limites[2 * eje]
        n = self.nx if eje == 0 else self.nz
        return max(0, int(math.ceil((a - origen) / self.paso))), min(n - 1, int(math.floor((b - origen) / self.paso)))

    # Celdas libres alcanzables desde la celda libre más cercana a (x, z) (bytearray 0/1). Vacío si no
    # hay celda libre a menos de 1 m del punto.
    def alcanzables(self, x, z):
        visitadas = bytearray(self.nx * self.nz)
        inicio = self._libre_cercana(x, z)
        if inicio is None:
            return visitadas
        self._inundar(inicio, visitadas)
        return visitadas

    # Lista de componentes conexos de celdas libres: [(celdas, (i, j) de una de ellas)], de mayor a menor.
    def componentes(self):
        visitadas = bytearray(self.nx * self.nz)
        resultado = []
        for j in range(self.nz):
            for i in range(self.nx):
                k = j * self.nx + i
                if self.libre[k] and not visitadas[k]:
                    resultado.append((self._inundar((i, j), visitadas), (i, j)))
        resultado.sort(key=lambda c: -c[0])
        return resultado

    def conectados(self, a, b):
        """¿Se puede ir del punto `a` al punto `b` (ambos (x, z)) por celdas libres?"""
        vistas = self.alcanzables(*a)
        destino = self._libre_cercana(*b)
        return destino is not None and bool(vistas[destino[1] * self.nx + destino[0]])

    def _libre_cercana(self, x, z, maximo=1.0):
        c = self.celda(x, z)
        if c is None:
            return None
        radio = int(math.ceil(maximo / self.paso))
        mejor = None
        for dj in range(-radio, radio + 1):
            for di in range(-radio, radio + 1):
                i, j = c[0] + di, c[1] + dj
                if 0 <= i < self.nx and 0 <= j < self.nz and self.libre[j * self.nx + i]:
                    d = di * di + dj * dj
                    if mejor is None or d < mejor[0]:
                        mejor = (d, (i, j))
        return mejor[1] if mejor else None

    # Inunda desde `inicio` marcando `visitadas`; devuelve cuántas celdas visitó.
    def _inundar(self, inicio, visitadas):
        nx, nz, libre = self.nx, self.nz, self.libre
        cola = deque([inicio])
        visitadas[inicio[1] * nx + inicio[0]] = 1
        total = 0
        while cola:
            i, j = cola.popleft()
            total += 1
            for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)):
                a, b = i + di, j + dj
                if not (0 <= a < nx and 0 <= b < nz):
                    continue
                k = b * nx + a
                if visitadas[k] or not libre[k]:
                    continue
                if di and dj and not (libre[j * nx + a] and libre[b * nx + i]):
                    continue                      # no cortar la esquina de una pared
                visitadas[k] = 1
                cola.append((a, b))
        return total


# Rejilla del mundo jugable: los límites de `mundo` y, ocupadas, las zonas que bloquea (cajas de
# edificios y casas, círculos de árboles y farolas) inflada por el radio del jugador. Con
# `pendiente=True` también se bloquea el talud no caminable (salvo escaleras): es lo más lento.
# `recorrible=True` usa limites_recorribles() (toda la ladera dibujada, donde de verdad se camina) en lugar
# de limites() (el rectángulo de la ciudad); por defecto, como siempre.
def rejilla_del_mundo(mundo, resolucion=RESOLUCION, pendiente=False, radio=RADIO_JUGADOR, recorrible=False):
    limites = mundo.limites_recorribles() if recorrible and hasattr(mundo, "limites_recorribles") else mundo.limites()
    rejilla = Rejilla(limites, resolucion)
    for e in mundo.edificios():
        rejilla.bloquear_caja(e.caja(), radio)
    for o in mundo.obstaculos():
        if o.es_circulo:
            rejilla.bloquear_circulo(o.cx, o.cz, o.radio + radio)
        else:
            rejilla.bloquear_caja((o.cx - o.ancho / 2, o.cx + o.ancho / 2, o.cz - o.fondo / 2, o.cz + o.fondo / 2),
                                  radio)
    if pendiente and mundo.terreno is not None:
        escaleras = mundo.escaleras()
        rejilla.bloquear_si_no(mundo.terreno.caminable, lambda x, z: any(e.contiene(x, z) for e in escaleras))
    return rejilla
