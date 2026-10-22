# Cálculos puros (sin ursina ni panda3d) del suelo de la favela: colores de tierra y arena, qué tanta
# tierra hay en cada punto de la ladera, geometría de las cintas de las calles de arena (con borde
# irregular) y del disco pintado de las plazas. Lo dibuja frontend/suelo_favela.py; aquí solo hay
# números, así que se prueba sin ventana (tests/frontend_3d/test_suelo_calculos.py).
#
# Colores: RGB 0-255 como albedo; en el shader del mundo la luz del sol multiplica el color y suma
# hasta ~0,3 más en lo iluminado, así que los tonos están pensados para NO pasar de ~0,85.
# Todo es ajustable desde las constantes de abajo; para volver al suelo de antes basta con no pasar
# `color_en` a la malla del terreno (ver ciudad_3d._malla_terreno).

import math

from frontend.azar_fijo import azar_de, ruido_suave

# -- Paleta de tierra y arena (de clara a rojiza) -----------------------------------------------
ARENA_CLARA = (232, 186, 116)       # arena seca de las calles
ARENA_MEDIA = (218, 154, 86)        # ocre naranja
ARENA_ROJIZA = (196, 110, 64)       # tierra roja compactada
TIERRA_OSCURA = (146, 84, 54)       # humedad al pie de las paredes y rodadas
PASTO_FAVELA = (86, 160, 66)        # pasto tropical de la ladera
PASTO_SECO = (132, 154, 70)         # pasto amarillento de los claros
COLOR_TALUD = (150, 98, 66)         # tierra de los taludes empinados

# -- Cuánta tierra hay alrededor de las casas y de las calles --
TIERRA_JUNTO_A_CASAS = (2.0, 7.5)   # m a la caja de una casa: del 100 % de tierra al 0 %
TIERRA_JUNTO_A_CALLES = (7.5, 12.0) # m al eje de una calle o al borde de una plaza: idem
RUIDO_BORDE_TIERRA = 2.2            # m que el ruido corre esos límites (manchas de pasto que entran)
TIERRA_ROJA_LADERA = 0.42           # fracción de ARENA_ROJIZA que se mezcla en la tierra de la ladera (la calle es más clara)
BRILLO_SUELO = 0.80                 # factor general: el sol suma luz sobre el albedo (ver arriba)

# -- Cinta de las calles de arena --
SEMIANCHO_CINTA = 5.5               # m de la cinta a cada lado del eje (el asfalto mide 4; el resto es tierra)
COLUMNAS_CINTA = 14                 # vértices a lo ancho
PASO_CINTA = 1.0                    # m entre muestras a lo largo
IRREGULAR_BORDE = 0.9               # m que se mueven los bordes de la cinta a un lado y otro
LARGO_TEXTURA_CAMINO = 8.0          # m de calle que cubre una repetición de la textura del camino


def _mezclar(a, b, t):
    return tuple(a[i] + (b[i] - a[i]) * t for i in range(3))


def _suave(t):
    t = min(1.0, max(0.0, t))
    return t * t * (3 - 2 * t)


# 1 si la distancia está por debajo de `inicio`, 0 por encima de `fin`, suave entre ambos.
def peso_por_distancia(distancia, inicio, fin):
    return 1.0 - _suave((distancia - inicio) / (fin - inicio))


def distancia_punto_caja(x, z, caja):
    xmin, xmax, zmin, zmax = caja
    return math.hypot(x - min(max(x, xmin), xmax), z - min(max(z, zmin), zmax))


def distancia_punto_segmento(x, z, a, b):
    dx, dz = b[0] - a[0], b[1] - a[1]
    largo2 = dx * dx + dz * dz
    t = 0.0 if largo2 < 1e-12 else min(1.0, max(0.0, ((x - a[0]) * dx + (z - a[1]) * dz) / largo2))
    return math.hypot(x - (a[0] + dx * t), z - (a[1] + dz * t))


# Color de la arena en (x, z): manchas amplias entre clara, ocre y rojiza; un grano fino y vetas.
# Devuelve RGB 0-255 (sin brillo general).
def color_arena(x, z):
    mancha = ruido_suave(x + 17.0, z - 5.0, 9.0)             # manchas de ~9 m
    parche = ruido_suave(x - 31.0, z + 11.0, 3.2)            # parches de ~3 m
    grano = azar_de(x * 2.3, z * 1.7) - 0.5
    base = _mezclar(ARENA_CLARA, ARENA_MEDIA, _suave(mancha * 1.6 - 0.1))
    base = _mezclar(base, ARENA_ROJIZA, _suave((parche - 0.55) * 3.0) * 0.8)
    f = 1.0 + 0.08 * grano
    return (base[0] * f, base[1] * f, base[2] * f)


# Mapa de dónde hay casas y calles, para calcular cuánta tierra tiene cada punto. `cajas`: casas y
# edificios (xmin, xmax, zmin, zmax); `calles`: [(a, b)] ejes; `plazas`: [(cx, cz)] con `radio_plaza`.
class MapaTierra:

    def __init__(self, cajas, calles, plazas, radio_plaza, celda=10.0):
        self.calles = list(calles)
        self.plazas = list(plazas)
        self.radio_plaza = radio_plaza
        self.celda = celda
        self._grilla = {}
        for caja in cajas:
            for i in range(int((caja[0] - TIERRA_JUNTO_A_CASAS[1]) // celda), int((caja[1] + TIERRA_JUNTO_A_CASAS[1]) // celda) + 1):
                for j in range(int((caja[2] - TIERRA_JUNTO_A_CASAS[1]) // celda), int((caja[3] + TIERRA_JUNTO_A_CASAS[1]) // celda) + 1):
                    self._grilla.setdefault((i, j), []).append(caja)

    # Distancia a la caja de casa más cercana (hasta TIERRA_JUNTO_A_CASAS[1] + 1 m; más lejos, un valor grande).
    def distancia_a_casas(self, x, z):
        cercanas = self._grilla.get((int(x // self.celda), int(z // self.celda)), ())
        return min((distancia_punto_caja(x, z, c) for c in cercanas), default=99.0)

    # Distancia al eje de calle o al borde de plaza más cercano.
    def distancia_a_calles(self, x, z):
        d = min((distancia_punto_segmento(x, z, a, b) for a, b in self.calles), default=99.0)
        return min(d, min((math.hypot(x - px, z - pz) - self.radio_plaza for px, pz in self.plazas), default=99.0))

    # Fracción (0-1) de tierra batida en (x, z): 1 junto a casas y calles, 0 en pleno pasto. Los límites
    # se corren con ruido para que el pasto entre en manchas y no en una franja pareja.
    def peso_tierra(self, x, z):
        corrimiento = (ruido_suave(x + 7.0, z + 3.0, 6.0) - 0.5) * 2 * RUIDO_BORDE_TIERRA
        w_casas = peso_por_distancia(self.distancia_a_casas(x, z) + corrimiento, *TIERRA_JUNTO_A_CASAS)
        w_calles = peso_por_distancia(self.distancia_a_calles(x, z) + corrimiento, *TIERRA_JUNTO_A_CALLES)
        return max(w_casas, w_calles)


# Color de la ladera en (x, z) (RGB 0-1 ya con brillo): pasto, tierra junto a casas y calles y tierra de
# talud según `talud` (0 = llano, 1 = empinado). `tierra` es el peso del MapaTierra en ese punto.
def color_ladera(x, z, tierra, talud):
    mancha = ruido_suave(x, z, 13.0) - 0.5
    pasto = _mezclar(PASTO_FAVELA, PASTO_SECO, _suave(ruido_suave(x - 9.0, z + 21.0, 15.0) * 1.5 - 0.3))
    pasto = tuple(c * (1 + 0.16 * mancha + 0.08 * (azar_de(x * 1.7, z * 2.3) - 0.5)) for c in pasto)
    # junto a las casas la tierra es más roja y oscura que la arena clara de las calles: así la calle se distingue
    suelo = _mezclar(pasto, _mezclar(color_arena(x, z), ARENA_ROJIZA, TIERRA_ROJA_LADERA), _suave(tierra * 1.15))
    # humedad: manchas más oscuras y rojizas dentro de la tierra
    oscuro = _suave((ruido_suave(x + 2.0, z - 8.0, 2.6) - 0.6) * 3.5) * 0.35 * tierra
    suelo = _mezclar(suelo, TIERRA_OSCURA, oscuro)
    suelo = _mezclar(suelo, COLOR_TALUD, _suave(talud))
    return tuple(min(1.0, c * BRILLO_SUELO / 255) for c in suelo)


# -- Cintas de las calles de arena ---------------------------------------------------------------


# Desplazamiento lateral (m) del borde de la cinta en `s` m a lo largo de la calle `semilla`, para que
# los bordes sean irregulares y distintos a cada lado (`lado` = -1 o 1). Suave a lo largo.
def borde_irregular(s, semilla, lado):
    return IRREGULAR_BORDE * (ruido_suave(s + 13.0 * lado, semilla * 7.3 + lado * 5.1, 3.0) - 0.5) * 2


# Posiciones a lo ancho de la cinta (d en m desde el eje), de borde a borde, con el borde corrido por
# `irregular_izq`/`irregular_der` (m, positivos = hacia afuera).
def columnas_cinta(irregular_izq, irregular_der, columnas=COLUMNAS_CINTA, semiancho=SEMIANCHO_CINTA):
    izq, der = -(semiancho + irregular_izq), semiancho + irregular_der
    return [izq + (der - izq) * c / columnas for c in range(columnas + 1)]


# Fracción (0 en el eje, 1 en el borde) a partir de la que el color de la cinta se funde con el del suelo.
INICIO_FUNDIDO_BORDE = 0.62


# Color (RGB 0-1) de la cinta en el punto (x, z) a la fracción lateral `t` (|d| / semiancho): arena de
# la calle en el centro y, hacia el borde, el color de la ladera (`ladera` RGB 0-1) para que no haya corte.
def color_cinta(x, z, t, ladera):
    arena = tuple(min(1.0, c * BRILLO_SUELO / 255) for c in color_arena(x, z))
    f = _suave((t - INICIO_FUNDIDO_BORDE) / (1.0 - INICIO_FUNDIDO_BORDE))
    return _mezclar(arena, ladera, f)


# -- Disco pintado de las plazas --------------------------------------------------------------------

# Paletas (de adentro hacia afuera) de las plazas: cemento pintado y adoquín de colores vivos.
PALETAS_PLAZA = (
    ((236, 120, 150), (250, 214, 90), (66, 190, 200), (250, 250, 240)),     # rosa, amarillo, turquesa, crema
    ((250, 160, 60), (240, 232, 200), (60, 170, 120), (232, 90, 70)),       # naranja, crema, verde, rojo
    ((70, 150, 220), (250, 220, 100), (240, 130, 160), (250, 246, 232)),    # azul, amarillo, rosa, blanco
    ((140, 210, 90), (250, 200, 70), (230, 110, 90), (60, 160, 190)),       # lima, amarillo, coral, turquesa
    ((226, 80, 100), (250, 226, 150), (80, 190, 190), (250, 160, 70)),      # rojo, crema, turquesa, naranja
    ((160, 110, 210), (250, 214, 90), (80, 200, 170), (240, 240, 235)),     # lila, amarillo, menta, blanco
    ((250, 190, 60), (60, 160, 200), (236, 100, 110), (246, 240, 220)),     # amarillo, azul, coral, crema
)
ANILLOS_PLAZA = 12                  # anillos radiales del disco
SECTORES_PLAZA = 64                 # sectores angulares del disco
ONDAS_PLAZA = 7                     # ondas por vuelta de la franja ondulada (como el paseo de Copacabana)
AMPLITUD_ONDA = 0.07                # fracción del radio que se mueve cada franja al ondular
BRILLO_PLAZA = 0.82
BANDAS_PLAZA = 9                    # franjas concéntricas del disco (los colores de la paleta se repiten)


# Índice de la paleta que le toca a cada plaza (por su orden), y la paleta.
def paleta_de_plaza(indice):
    return PALETAS_PLAZA[indice % len(PALETAS_PLAZA)]


# Color RGB 0-1 del punto del disco de la plaza a la fracción de radio `r` (0-1) y el ángulo `theta` (rad):
# franjas concéntricas que ondulan, con un poco de grano para que el cemento se vea pintado a mano.
def color_disco(r, theta, paleta, semilla=0.0):
    onda = math.sin(theta * ONDAS_PLAZA + semilla) * AMPLITUD_ONDA
    banda = int(max(0.0, r + onda) * BANDAS_PLAZA)
    base = paleta[banda % len(paleta)]
    grano = 1.0 + 0.07 * (azar_de(r * 91.0 + semilla, theta * 37.0) - 0.5)
    return tuple(min(1.0, c / 255 * BRILLO_PLAZA * grano) for c in base)
