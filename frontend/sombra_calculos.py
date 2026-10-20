# Cálculos puros de la sombra de contacto y del aro de resaltado (NO importa ursina ni panda3d):
# elevación de los pies, radio y alfa del disco según la altura sobre la superficie.

ELEVACION_PIES = 0.26             # m: pies sobre la capa más alta del suelo del mundo (ruta GPS +0.255)
ELEVACION_PIES_INTERIOR = 0.03    # m: el piso del interior está en y = 0
SESGO_SOMBRA = 0.012              # m: la sombra va apenas sobre la superficie donde pisa el modelo
Y_AURO = 0.30                     # m: aro del jugador activo, por encima de la ruta GPS (0.255)
Y_AURO_INTERIOR = 0.05

RADIO_SOMBRA = 0.45               # m con los pies en la superficie
ALFA_SOMBRA = 0.35
ALTURA_SOMBRA_NULA = 1.5          # m de altura a la que la sombra ya no se ve
ALFA_AURO = 0.40


# Elevación de los pies: en el mundo (hay función de suelo) o en el interior (suelo None).
def elevacion_pies(hay_suelo):
    return ELEVACION_PIES if hay_suelo else ELEVACION_PIES_INTERIOR


def altura_aro(hay_suelo):
    return Y_AURO if hay_suelo else Y_AURO_INTERIOR


# Factor 1 -> 0 según lo alto que está el modelo sobre la superficie (altura <= 0 = apoyado).
def factor_altura(altura):
    return min(1.0, max(0.0, 1.0 - altura / ALTURA_SOMBRA_NULA))


def alfa_sombra(altura=0.0):
    return ALFA_SOMBRA * factor_altura(altura)


# Más alto, más difusa: el disco crece hasta un 60 % más.
def radio_sombra(altura=0.0):
    return RADIO_SOMBRA * (1.0 + 0.6 * (1.0 - factor_altura(altura)))
