# Índice espacial mínimo y PRIVADO de la generación del barrio (datos puros, sin ursina). Una rejilla uniforme de
# celdas cuadradas donde cada elemento (un punto, una caja o un segmento) se apunta en TODAS las celdas que toca;
# `cerca(caja)` devuelve los identificadores de los elementos que pueden estar a distancia 0 de esa caja (un
# conjunto: sin repetidos). Quien consulta ensancha la caja por su margen y comprueba la distancia exacta, así el
# resultado es el mismo que recorrer todo. No depende de backend/datos/indice_espacial.py (lo escribe otro agente).

import math

from backend.logica.mundo_ciudad import _segmento_corta_caja

_EPS = 1e-6      # holgura de las celdas: un elemento que roza el borde de una celda cuenta como dentro


class RejillaBarrio:

    def __init__(self, celda=16.0):
        self.celda = celda
        self.celdas = {}

    def _rango(self, a, b):
        c = self.celda
        return int(math.floor(a / c)), int(math.floor(b / c))

    def insertar_punto(self, ident, x, z):
        self.celdas.setdefault(self._clave(x, z), []).append(ident)

    def _clave(self, x, z):
        c = self.celda
        return int(math.floor(x / c)), int(math.floor(z / c))

    def insertar_caja(self, ident, caja):
        i0, i1 = self._rango(caja[0], caja[1])
        j0, j1 = self._rango(caja[2], caja[3])
        for i in range(i0, i1 + 1):
            for j in range(j0, j1 + 1):
                self.celdas.setdefault((i, j), []).append(ident)

    # Solo las celdas que el segmento a-b atraviesa (no toda su caja envolvente).
    def insertar_segmento(self, ident, a, b):
        i0, i1 = self._rango(min(a[0], b[0]), max(a[0], b[0]))
        j0, j1 = self._rango(min(a[1], b[1]), max(a[1], b[1]))
        c = self.celda
        if i0 == i1 or j0 == j1:
            for i in range(i0, i1 + 1):
                for j in range(j0, j1 + 1):
                    self.celdas.setdefault((i, j), []).append(ident)
            return
        for i in range(i0, i1 + 1):
            for j in range(j0, j1 + 1):
                caja = (i * c - _EPS, (i + 1) * c + _EPS, j * c - _EPS, (j + 1) * c + _EPS)
                if _segmento_corta_caja(a, b, caja):
                    self.celdas.setdefault((i, j), []).append(ident)

    def numero_de_celdas(self, x0, x1, z0, z1):
        i0, i1 = self._rango(x0, x1)
        j0, j1 = self._rango(z0, z1)
        return (i1 - i0 + 1) * (j1 - j0 + 1)

    # Identificadores de los elementos que tocan alguna celda de la caja (x0, x1, z0, z1).
    def cerca(self, x0, x1, z0, z1):
        i0, i1 = self._rango(x0, x1)
        j0, j1 = self._rango(z0, z1)
        resultado = set()
        obtener = self.celdas.get
        for i in range(i0, i1 + 1):
            for j in range(j0, j1 + 1):
                lista = obtener((i, j))
                if lista:
                    resultado.update(lista)
        return resultado
