# Cálculos puros de los NPC con modelo .glb (NO importa ursina ni panda3d): qué modelo usa cada peatón, con qué
# ropa, a qué escala, con qué accesorio y con qué desfase de animación. Todo es determinista por (indice, semilla)
# y usa generadores PROPIOS: no toca el azar de los caminantes (peatones_calculos.crear_peatones) ni el del
# aspecto/rasgos de los peatones, así que el recorrido de los 6 originales no cambia.
#
# Los .glb no tienen texturas: el color está en los vértices, un Geom por pieza. Los Geoms casi negros son el
# casco de tinta del contorno y NO se recolorean. Cada modelo declara qué piezas (nombre del nodo, índice de Geom)
# son piel, camiseta, pantalón, extras o pelo; frontend/npc_color.py las recolorea conservando las bandas de luz.

import random

# Los cuatro modelos de los personajes principales, como (archivo, rol de rostro). El rol decide el hueso de
# la cabeza y los ajustes del rostro (rostro_calculos.hueso_cabeza, AJUSTE_ROSTRO_POR_ROL).
MODELOS_NPC = (("periodista.glb", "periodista"), ("smoking.glb", "candidato"),
               ("brasilena.glb", "influencer"), ("ciudadano.glb", "ciudadano"))

ESCALA_MIN, ESCALA_MAX = 0.94, 1.06      # variación de altura respecto a la escala del modelo

# Piezas recoloreables de cada modelo: grupo -> lista de (nombre de nodo, índice de Geom).
# "piel" cambia con el tono de piel del peatón; "camiseta", "pantalon" y "extra" con la paleta de ropa.
GRUPOS_POR_MODELO = {
    "periodista.glb": {"piel": [("Cuerpo", 0)], "camiseta": [("Camisa", 0), ("Mangas", 0)],
                       "pantalon": [("Pantalon", 0)], "extra": []},
    "smoking.glb": {"piel": [("Cuerpo", 0)], "camiseta": [("Saco", 0)], "pantalon": [("Pantalon", 0)], "extra": []},
    "brasilena.glb": {"piel": [("Cuerpo", 0)], "camiseta": [("Top", 0)], "pantalon": [("Short", 0)],
                      "extra": [("TrajeBano", 0)], "pelo": [("Pelo", 0)]},
    "ciudadano.glb": {"piel": [("Cuerpo", 0)], "camiseta": [], "pantalon": [("Pantalon", 0)], "extra": [],
                      "costuras": [("Ciudadano_Detalles", 3), ("Ciudadano_Detalles", 4), ("Ciudadano_Detalles", 5)]},
}

# Modelos que traen el torso desnudo (el ciudadano): su camiseta se añade como una piel de triángulos del torso
# (frontend/npc_color.agregar_camiseta). Se eligen los triángulos por el hueso que más pesa en cada vértice.
MODELOS_SIN_CAMISETA = frozenset({"ciudadano.glb"})
HUESOS_TIRANTES = frozenset({"DEF-spine", "DEF-spine.001", "DEF-spine.002", "DEF-spine.003", "DEF-breast.L",
                             "DEF-breast.R", "DEF-shoulder.L", "DEF-shoulder.R"})
HUESOS_MANGA = HUESOS_TIRANTES | {"DEF-upper_arm.L", "DEF-upper_arm.R"}
PROBABILIDAD_CAMISETA = 0.8              # de los ciudadanos NPC, los que llevan camiseta (el resto, torso al aire)
PROBABILIDAD_TIRANTES = 0.3              # de los que la llevan, los de camiseta sin mangas
GROSOR_CAMISETA = 0.016                  # m que sobresale la camiseta de la piel (el casco de tinta es mayor)

# Colores vivos (0-1) de la ropa: la favela es de colores saturados, pero distintos de los 4 roles jugables.
CAMISETAS = ((0.93, 0.77, 0.15), (0.15, 0.62, 0.85), (0.85, 0.25, 0.22), (0.20, 0.65, 0.40), (0.95, 0.95, 0.92),
             (0.95, 0.50, 0.15), (0.55, 0.30, 0.70), (0.92, 0.45, 0.60), (0.15, 0.25, 0.55), (0.20, 0.20, 0.24))
PANTALONES = ((0.25, 0.35, 0.60), (0.12, 0.12, 0.15), (0.70, 0.60, 0.40), (0.90, 0.88, 0.80), (0.45, 0.45, 0.50),
              (0.35, 0.45, 0.28), (0.55, 0.18, 0.18), (0.18, 0.40, 0.45))
TRAJES = ((0.22, 0.24, 0.30), (0.12, 0.18, 0.38), (0.72, 0.66, 0.52), (0.45, 0.14, 0.18), (0.30, 0.30, 0.32))
MOCHILAS = ((0.85, 0.25, 0.22), (0.93, 0.77, 0.15), (0.15, 0.62, 0.85), (0.20, 0.65, 0.40), (0.55, 0.30, 0.70))
PROBABILIDAD_MOCHILA = 0.4

# Hueso de la espalda y centro de la mochila (ejes del glb crudo: x izquierda, y atrás, z arriba) por rol.
ESPALDA_POR_ROL = {"periodista": ("DEF-spine.003", (0.0, 0.16, 1.30)), "candidato": ("DEF-spine.003", (0.0, 0.17, 1.30)),
                   "influencer": ("Spine3", (0.0, 0.15, 1.28)), "ciudadano": ("DEF-spine.003", (0.0, 0.16, 1.30))}


# Rendimiento: la animación de la cara cuesta ~0,1 ms por NPC y a más de DISTANCIA_ROSTRO m no se distingue, así que
# se apaga (la cara queda congelada). Se revisa cada INTERVALO_LOD s (con un pequeño desfase por NPC).
# A más de DISTANCIA_CUERPO m se congela la animación del cuerpo (el esqueleto de 160 huesos cuesta ~0,4 ms por NPC
# en la CPU y a esa distancia mide unos pocos píxeles).
DISTANCIA_ROSTRO = 22.0
DISTANCIA_CUERPO = 45.0
INTERVALO_LOD = 0.3


# ¿Anima la cara un NPC a `distancia` metros de la cámara? Distancias inválidas (NaN, negativas) cuentan como cerca.
def rostro_activo(distancia):
    try:
        return not (distancia > DISTANCIA_ROSTRO)
    except TypeError:
        return True


# ¿Congela el cuerpo un NPC a `distancia` metros de la cámara? Distancias inválidas cuentan como cerca.
def cuerpo_congelado(distancia):
    try:
        return distancia > DISTANCIA_CUERPO
    except TypeError:
        return False


# Índice (0 a 1) de un color entre su sombra y su luz: brillo percibido.
def luminancia(color):
    return 0.299 * color[0] + 0.587 * color[1] + 0.114 * color[2]


def _limitar(valor):
    return max(0.0, min(1.0, valor))


# Recolorea los tonos de una pieza: el más claro pasa a ser `objetivo` y los demás conservan su proporción de
# brillo respecto a él (así las bandas de luz horneadas siguen siendo bandas). `colores`: lista de (r, g, b, a);
# devuelve otra lista igual de larga. Total: si la pieza es casi negra (casco de tinta) la devuelve igual.
def recolorear_tonos(colores, objetivo):
    if not colores:
        return []
    referencia = max(luminancia(c) for c in colores)
    if referencia < 0.02:
        return list(colores)
    return [(_limitar(objetivo[0] * luminancia(c) / referencia), _limitar(objetivo[1] * luminancia(c) / referencia),
             _limitar(objetivo[2] * luminancia(c) / referencia), c[3]) for c in colores]


# Huesos cuyo vértice dominante pertenece a la camiseta añadida de tipo `tipo` ("manga" o "tirantes").
def huesos_camiseta(tipo):
    return HUESOS_MANGA if tipo == "manga" else HUESOS_TIRANTES


# Archivo y rol del modelo del NPC `indice`: de cada bloque de 4 NPC sale uno de cada modelo, en orden barajado
# por (semilla, bloque). Así 12 NPC usan 3 de cada y nunca queda un modelo sin usar.
def modelo_npc(indice, semilla):
    bloque, posicion = divmod(indice, len(MODELOS_NPC))
    orden = list(range(len(MODELOS_NPC)))
    random.Random(semilla * 7919 + bloque * 104729).shuffle(orden)
    return MODELOS_NPC[orden[posicion]]


# Fase (0 a 1) de la animación del NPC: cada uno arranca su ciclo en otro punto para no ir sincronizados.
def fase_animacion(indice, semilla):
    return random.Random(semilla * 31 + indice * 7 + 5).random()


# Mezcla de dos colores (0 = a, 1 = b).
def mezclar(a, b, t):
    return tuple(a[i] + (b[i] - a[i]) * t for i in range(3))


def _a_unidad(rgb):
    return tuple(c / 255 for c in rgb)


# Plan completo del NPC `indice`: modelo, rol de rostro, escala relativa, colores por grupo (0-1), mochila y fase.
# `aspecto`: dict de peatones_calculos.aspecto_peaton (piel y pelo en 0-255); lo pone quien llama para no
# duplicar su azar. Determinista y sin tocar otros generadores.
def plan_npc(indice, semilla, aspecto):
    archivo, rol = modelo_npc(indice, semilla)
    azar = random.Random(semilla * 4099 + indice * 131 + 17)
    colores = {"piel": _a_unidad(aspecto["piel"]), "pantalon": azar.choice(PANTALONES)}
    if archivo == "smoking.glb":
        traje = azar.choice(TRAJES)
        colores["camiseta"] = traje
        colores["pantalon"] = traje
    else:
        colores["camiseta"] = azar.choice(CAMISETAS)
    if archivo == "brasilena.glb":
        colores["extra"] = azar.choice(CAMISETAS)
        colores["pelo"] = _a_unidad(aspecto["pelo"])
    colores["costuras"] = mezclar(colores["pantalon"], (1.0, 1.0, 1.0), 0.35)    # costuras y bolsillos de los vaqueros
    mochila = azar.choice(MOCHILAS) if azar.random() < PROBABILIDAD_MOCHILA else None
    camiseta_nueva = None                    # "manga", "tirantes" o None (torso al aire)
    if archivo in MODELOS_SIN_CAMISETA and azar.random() < PROBABILIDAD_CAMISETA:
        camiseta_nueva = "tirantes" if azar.random() < PROBABILIDAD_TIRANTES else "manga"
    return {"archivo": archivo, "rol": rol, "camiseta_nueva": camiseta_nueva, "escala": azar.uniform(ESCALA_MIN, ESCALA_MAX), "colores": colores,
            "mochila": mochila, "fase": fase_animacion(indice, semilla)}


# Objetivos de recolor {(nodo, geom): color} de un plan (solo los grupos que ese modelo tiene y el plan define).
def objetivos_recolor(plan):
    grupos = GRUPOS_POR_MODELO[plan["archivo"]]
    objetivos = {}
    for grupo, piezas in grupos.items():
        color = plan["colores"].get(grupo)
        if color is None:
            continue
        for pieza in piezas:
            objetivos[pieza] = color
    return objetivos


# Rasgos de la cara del NPC según su modelo: la brasileña trae el afro puesto (sin peinado ni gorra por código) y
# no recibe bigote ni barba; el resto usa los rasgos del peatón tal cual (menos la gorra, que no cabe sobre el
# peinado de peinado "afro"/"mono", ya resuelto en rasgos_peaton).
def rasgos_para_modelo(archivo, rasgos):
    rasgos = dict(rasgos)
    if archivo == "brasilena.glb":
        rasgos.update(peinado=None, gorra=None, bigote=False, barba=None)
    return rasgos
