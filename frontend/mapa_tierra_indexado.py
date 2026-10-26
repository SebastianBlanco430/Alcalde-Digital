# MapaTierra del mapa grande: mismos números que suelo_calculos.MapaTierra, pero la distancia a calles y plazas
# se busca en un índice (SegmentosIndexados / rejilla de plazas) en vez de recorrer todas: con 34 calles y 24 plazas
# el recorrido lineal costaba ~10 µs por vértice del terreno; indexado baja a ~2 µs. Sin ursina (se prueba sin ventana).

import math

from backend.datos.indice_espacial import IndiceUniforme, SegmentosIndexados
from frontend import suelo_calculos as sc


class MapaTierraIndexado(sc.MapaTierra):

    def __init__(self, cajas, calles, plazas, radio_plaza, celda=10.0):
        super().__init__(cajas, calles, plazas, radio_plaza, celda)
        self._calles_idx = SegmentosIndexados(self.calles, celda=32.0)
        self._plazas_idx = IndiceUniforme(32.0)
        for px, pz in self.plazas:
            self._plazas_idx.insertar((px, pz), (px, px, pz, pz))

    # Igual que MapaTierra.distancia_a_calles; más lejos de TOPE_CALLES no importa (el peso ya es 0): devuelve 99.
    def distancia_a_calles(self, x, z):
        tope = sc.TIERRA_JUNTO_A_CALLES[1] + 2 * sc.RUIDO_BORDE_TIERRA + 1.0
        d = self._calles_idx.distancia_minima(x, z, tope)
        r = self.radio_plaza
        for px, pz in self._plazas_idx.cerca(x, z, tope + r):
            d = min(d, math.hypot(x - px, z - pz) - r)
        return d if d < tope else 99.0
