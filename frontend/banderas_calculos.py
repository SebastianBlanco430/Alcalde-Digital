# Cálculos puros (sin ursina) de las banderas de los techos: dónde va cada una y de qué color. Solo
# geometría de los edificios jugables y azar determinista, así se prueba sin ventana.

import math

from backend.logica.mundo_ciudad import _NORMAL_FUERA, _TANGENTE
from frontend.azar_fijo import azar_de

RETIRO_BORDE = 0.4        # m que la bandera se retira de los bordes del techo
HUNDIMIENTO_BASE = 0.1    # m que el mástil se entierra en el techo (no queda flotando)

# 7 colores bien distintos entre sí y de los tintes pastel de la favela: rojo, azul rey, verde,
# naranja, morado, turquesa y blanco (un edificio jugable cada uno).
COLORES_BANDERA = ((205, 32, 40), (30, 70, 200), (30, 150, 70), (240, 125, 20),
                   (135, 45, 175), (20, 180, 170), (245, 245, 245))


# Posición (x, y, z) de la base del mástil sobre el techo de `e`: en la esquina trasera (la más
# lejos de la puerta) y del lado contrario al desfase de la puerta (si está centrada, hacia +tangente).
def posicion_bandera(e):
    nx, nz = _NORMAL_FUERA[e.lado_puerta]
    tx, tz = _TANGENTE[e.lado_puerta]
    # semiejes del techo: el de la normal es el fondo si la puerta mira a n/s y el ancho si mira a e/o
    medio_normal = (e.fondo if e.lado_puerta in ("n", "s") else e.ancho) / 2
    medio_tangente = (e.ancho if e.lado_puerta in ("n", "s") else e.fondo) / 2
    atras = medio_normal - RETIRO_BORDE
    lado = medio_tangente - RETIRO_BORDE
    signo = -1 if e.desfase_puerta > 0 else 1
    x = e.cx - nx * atras + tx * lado * signo
    z = e.cz - nz * atras + tz * lado * signo
    return (x, e.y + e.alto - HUNDIMIENTO_BASE, z)


# {lugar: (x, y, z)} de todos los edificios dados.
def posiciones_banderas(edificios):
    return {e.lugar: posicion_bandera(e) for e in edificios}


# {lugar: color} en el orden de los edificios (el color k se repite si hay más de 7).
def colores_banderas(edificios):
    return {e.lugar: COLORES_BANDERA[i % len(COLORES_BANDERA)] for i, e in enumerate(edificios)}


# Rumbo (grados) fijo por edificio hacia el que mira la tela: depende solo de su posición.
def rumbo_bandera(e):
    return azar_de(e.cx, e.cz) * 360.0


# Distancia en planta de la bandera de `e` a su puerta (para comprobar que queda lejos de ella).
def distancia_a_puerta(e):
    x, _, z = posicion_bandera(e)
    return math.dist((x, z), e.puerta())
