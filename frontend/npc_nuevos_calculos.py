# Cálculos puros (NO importa ursina ni panda3d) de los NPC NUEVOS: los cinco .glb low-poly npc_hombre_01..03 y
# npc_mujer_01..02 (assets/modelos/personajes). Qué modelo toca a cada peatón, con qué colores, a qué escala, y
# cómo se reparte el color de sus vértices. Determinista por (indice, semilla) con generadores PROPIOS.
#
# Cómo son esos .glb: sin texturas, sin materiales y SIN animaciones; una malla (los hombres) o dos (las mujeres:
# cuerpo y cabello) con un color PLANO por vértice para cada zona (piel, camiseta, pantalón, calzado, pelo) y sin
# casco de tinta. Los hombres traen el mismo esqueleto que el periodista (Rigify "DEF-*", 160 huesos) y las mujeres
# el de la brasileña ("Hips/Spine/Head", 37 huesos), así que la animación humana y la cara por código les sirven
# tal cual. El nodo del esqueleto viene escalado (0,85-0,91) para dar la altura de cada uno (1,66-1,80 m): al
# cargarlo se quita esa escala (el modelo queda en las medidas del periodista / la brasileña) y se aplica al Actor.

import random

from frontend import npc_calculos as nc

# (archivo, clave). La clave hace de «rol» del PersonajeModelo (caché de modelos, medidas de la marcha).
MODELOS_NUEVOS = (("npc_hombre_01.glb", "npc_hombre_01"), ("npc_hombre_02.glb", "npc_hombre_02"),
                  ("npc_hombre_03.glb", "npc_hombre_03"), ("npc_mujer_01.glb", "npc_mujer_01"),
                  ("npc_mujer_02.glb", "npc_mujer_02"))
ARCHIVOS_NUEVOS = frozenset(archivo for archivo, _ in MODELOS_NUEVOS)

# De cada bloque de 7 NPC salen los 5 nuevos y, para variar, el ciudadano y la brasileña (los nuevos predominan).
REPARTO = MODELOS_NUEVOS + (("ciudadano.glb", "ciudadano"), ("brasilena.glb", "influencer"))

# Zonas de color de cada modelo: (color de vértice original, grupo). Los grupos "piel", "camiseta", "pantalon",
# "pelo" y "zapatos" se recolorean con el plan; el resto (suela, calcetín) conserva su color.
# `rol_rostro`: de qué modelo conocido es la cabeza (hueso y medidas de rostro_calculos). `escala`: la del nodo del
# esqueleto en el .glb (altura real / altura del esqueleto). `mujer`: sin bigote ni barba, y el pelo ya viene puesto.
DATOS = {
    "npc_hombre_01.glb": {"rol_rostro": "periodista", "escala": 0.908, "mujer": False, "zonas": (
        ((0.710, 0.514, 0.369), "piel"), ((0.824, 0.643, 0.227), "camiseta"), ((0.294, 0.424, 0.588), "pantalon"),
        ((0.180, 0.545, 0.341), "zapatos"), ((0.110, 0.082, 0.063), "pelo"))},
    "npc_hombre_02.glb": {"rol_rostro": "periodista", "escala": 0.898, "mujer": False, "zonas": (
        ((0.353, 0.220, 0.149), "piel"), ((0.914, 0.898, 0.855), "camiseta"), ((0.227, 0.337, 0.498), "pantalon"),
        ((0.894, 0.886, 0.863), "zapatos"), ((0.420, 0.420, 0.420), "suela"), ((0.059, 0.043, 0.035), "pelo"))},
    "npc_hombre_03.glb": {"rol_rostro": "periodista", "escala": 0.881, "mujer": False, "zonas": (
        ((0.827, 0.635, 0.486), "piel"), ((0.435, 0.659, 0.788), "camiseta"), ((0.659, 0.569, 0.431), "pantalon"),
        ((0.353, 0.231, 0.149), "zapatos"), ((0.169, 0.129, 0.098), "suela"), ((0.165, 0.110, 0.078), "pelo"))},
    "npc_mujer_01.glb": {"rol_rostro": "influencer", "escala": 0.862, "mujer": True, "zonas": (
        ((0.545, 0.353, 0.235), "piel"), ((0.886, 0.404, 0.353), "camiseta"), ((0.443, 0.588, 0.761), "pantalon"),
        ((0.941, 0.753, 0.188), "zapatos"), ((0.086, 0.063, 0.051), "pelo"))},
    "npc_mujer_02.glb": {"rol_rostro": "influencer", "escala": 0.852, "mujer": True, "zonas": (
        ((0.922, 0.780, 0.675), "piel"), ((0.604, 0.510, 0.769), "camiseta"), ((0.431, 0.482, 0.290), "pantalon"),
        ((0.541, 0.541, 0.541), "zapatos"), ((0.929, 0.922, 0.902), "calcetin"), ((0.416, 0.290, 0.184), "pelo"))},
}
GRUPOS_RECOLOR = ("piel", "camiseta", "pantalon", "pelo", "zapatos")
TOLERANCIA_COLOR = 0.03          # distancia máxima (por canal) entre el color de un vértice y el de su zona

ZAPATOS = ((0.16, 0.15, 0.17), (0.90, 0.89, 0.86), (0.50, 0.32, 0.20), (0.75, 0.20, 0.18), (0.18, 0.45, 0.32),
           (0.20, 0.30, 0.55), (0.93, 0.77, 0.15))

# Bandas de luz de cómic: los .glb nuevos traen el color plano y el Actor no recibe luz, así que la banda se hornea
# en el color de vértice según la normal (luz desde arriba, delante y la izquierda del modelo). Ejes del glb crudo:
# x izquierda, y atrás, z arriba.
LUZ = (0.33, -0.52, 0.79)
BANDAS = ((0.30, 1.0), (-0.20, 0.86), (-2.0, 0.72))     # (coseno mínimo, brillo): luz, medio tono y sombra

GROSOR_CONTORNO = 0.011          # m (medidas del esqueleto): casco de tinta que se añade al cargar
COLOR_CONTORNO = (0.07, 0.078, 0.125)     # la tinta de todo el juego (rostro_calculos.TINTA)

# Mochila de los nuevos: hueso de la espalda y centro (ejes del glb crudo: x izquierda, y atrás, z arriba), como
# nc.ESPALDA_POR_ROL. El centro va ~3 cm por detrás de la espalda de cada modelo (medida en su malla).
ESPALDA_POR_ARCHIVO = {"npc_hombre_01.glb": ("DEF-spine.003", (0.0, 0.125, 1.30)),
                       "npc_hombre_02.glb": ("DEF-spine.003", (0.0, 0.110, 1.30)),
                       "npc_hombre_03.glb": ("DEF-spine.003", (0.0, 0.155, 1.30)),
                       "npc_mujer_01.glb": ("Spine3", (0.0, 0.095, 1.28)),
                       "npc_mujer_02.glb": ("Spine3", (0.0, 0.095, 1.28))}


def es_nuevo(archivo):
    return archivo in ARCHIVOS_NUEVOS


# Archivo y clave del NPC `indice` con el reparto nuevo: de cada bloque de 7 sale uno de cada (5 nuevos + ciudadano +
# brasileña), en orden barajado por (semilla, bloque). Generador propio: no toca el de nc.modelo_npc.
def modelo_variado(indice, semilla):
    bloque, posicion = divmod(indice, len(REPARTO))
    orden = list(range(len(REPARTO)))
    random.Random(semilla * 6007 + bloque * 15485863 + 11).shuffle(orden)
    return REPARTO[orden[posicion]]


# Grupo ("piel", "camiseta"...) al que pertenece un color de vértice del modelo, o None si no es de ninguna zona.
def grupo_de_color(archivo, color):
    mejor, distancia = None, TOLERANCIA_COLOR
    for referencia, grupo in DATOS[archivo]["zonas"]:
        d = max(abs(color[i] - referencia[i]) for i in range(3))
        if d <= distancia:
            mejor, distancia = grupo, d
    return mejor


# Brillo (0-1) de la banda de luz para una normal (ejes del glb crudo). Total: una normal nula da el medio tono.
def banda_luz(normal):
    largo = (normal[0] ** 2 + normal[1] ** 2 + normal[2] ** 2) ** 0.5
    if largo < 1e-6:
        return BANDAS[1][1]
    coseno = (normal[0] * LUZ[0] + normal[1] * LUZ[1] + normal[2] * LUZ[2]) / largo
    for minimo, brillo in BANDAS:
        if coseno >= minimo:
            return brillo
    return BANDAS[-1][1]


# Color final de un vértice: el color de su zona por el brillo de su banda.
def color_con_banda(color, brillo):
    return (color[0] * brillo, color[1] * brillo, color[2] * brillo)


# Plan del NPC `indice` con uno de los modelos nuevos (`modelo` = (archivo, clave)). Mismas claves que nc.plan_npc
# más: "nuevo" (True), "rol_rostro" (cabeza de qué modelo conocido), "escala_base" (la del modelo, en vez de la
# del rol) y los colores "pelo" y "zapatos". `aspecto`: dict de peatones_calculos.aspecto_peaton.
def plan_nuevo(indice, semilla, aspecto, modelo):
    archivo, clave = modelo
    datos = DATOS[archivo]
    azar = random.Random(semilla * 5231 + indice * 173 + 29)
    colores = {"piel": nc._a_unidad(aspecto["piel"]), "pelo": nc._a_unidad(aspecto["pelo"]),
               "camiseta": azar.choice(nc.CAMISETAS), "pantalon": azar.choice(nc.PANTALONES),
               "zapatos": azar.choice(ZAPATOS)}
    escala = azar.uniform(nc.ESCALA_MIN, nc.ESCALA_MAX)
    mochila = azar.choice(nc.MOCHILAS) if azar.random() < nc.PROBABILIDAD_MOCHILA else None
    return {"archivo": archivo, "rol": clave, "nuevo": True, "rol_rostro": datos["rol_rostro"],
            "camiseta_nueva": None, "escala_base": datos["escala"], "escala": escala, "colores": colores,
            "mochila": mochila, "fase": nc.fase_animacion(indice, semilla)}


# Colores por grupo que se pintan en un modelo nuevo: los del plan para los grupos recoloreables.
def objetivos_nuevo(plan):
    return {grupo: plan["colores"][grupo] for grupo in GRUPOS_RECOLOR if plan["colores"].get(grupo) is not None}


# Hueso de la espalda y centro de la mochila de un plan nuevo.
def espalda(plan):
    return ESPALDA_POR_ARCHIVO[plan["archivo"]]


# Rasgos de la cara para un modelo nuevo: las mujeres traen el cabello en el modelo (sin peinado ni gorra por código)
# y no reciben bigote ni barba; los hombres traen el pelo pintado al ras, así que el peinado por código va encima.
def rasgos_nuevo(archivo, rasgos):
    rasgos = dict(rasgos)
    if DATOS[archivo]["mujer"]:
        rasgos.update(peinado=None, gorra=None, bigote=False, barba=None)
    return rasgos
