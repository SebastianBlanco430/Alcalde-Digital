# Detalles de los techos de la favela (Ursina): antenas parabólicas y ropa tendida entre casas.
# La geometría y el azar salen de frontend/detalles_calculos.py (puro); aquí solo se arman las
# piezas. Todo es estático y cuelga de un grupo de Ciudad3D que se funde con combine(), así que no
# hay update() ni una Entity suelta que sobreviva. Las cuerdas no son piezas: se devuelven como
# vértices para sumarlas a la malla de líneas de los cables.
#
# Rendimiento: el plato de todas las antenas usa UNA esfera compartida (cargada una vez).

from ursina import load_model

from frontend.azar_fijo import azar_de
from frontend.componentes import rgb
from frontend.detalles_calculos import ALTO_PRENDA, indices_con_antena, posicion_antena, prendas, tendederos, vertices_cuerda
from frontend.piezas import pieza

COLOR_ANTENA = (205, 205, 210)
MASTIL = (0.05, 0.6, 0.05)               # m (ancho, alto, fondo)
PLATO = (0.7, 0.16, 0.7)                 # m: esfera aplastada
INCLINACION_PLATO = 35                   # grados hacia el cielo
PRENDA = (0.35, ALTO_PRENDA, 0.03)       # m (ancho a lo largo de la cuerda, alto, grosor)


# Antenas y prendas en `grupo`; devuelve los vértices (de a pares) de las cuerdas de los tendederos.
# `apoyos`: lista alineada con `casas` de (bajo, alto) del suelo bajo cada huella. `prohibidos` y
# `suelo` son opcionales y van a detalles_calculos.tendederos (calles, accesos y escaleras que la
# ropa no puede cruzar; altura del suelo para medir la holgura).
def construir_detalles(grupo, casas, apoyos, prohibidos=(), suelo=None):
    _antenas(grupo, casas, apoyos)
    vertices = []
    for tendedero in tendederos(casas, apoyos, prohibidos=prohibidos, suelo=suelo):
        vertices += vertices_cuerda(tendedero)
        for prenda in prendas(tendedero):
            pieza(parent=grupo, model="cube", color=rgb(prenda.color), rotation_y=prenda.rumbo,
                  position=(prenda.x, prenda.y, prenda.z), scale=PRENDA)
    return vertices


# Mástil y plato en el techo de ~20 % de las casas, en la esquina opuesta al tanque de agua.
def _antenas(grupo, casas, apoyos):
    esfera = load_model("sphere")            # una sola malla para todos los platos
    for i in indices_con_antena(casas):
        casa = casas[i]
        x, z = posicion_antena(casa)
        techo = apoyos[i][1] + casa.alto_total
        giro = int(azar_de(casa.cx * 3.1, casa.cz * 1.7) * 4) * 90      # rumbo del plato: 0/90/180/270 grados
        # (argumentos propios: con los de indices_con_antena el azar sería < 0.2 y el giro siempre 0)
        pieza(parent=grupo, model="cube", color=rgb(COLOR_ANTENA),
              position=(x, techo + MASTIL[1] / 2, z), scale=MASTIL)
        pieza(parent=grupo, model=esfera, color=rgb(COLOR_ANTENA), rotation=(-INCLINACION_PLATO, giro, 0),
              position=(x, techo + MASTIL[1] + 0.05, z), scale=PLATO)
