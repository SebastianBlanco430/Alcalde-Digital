# Catálogo semilla de noticias de Ciudad Nova (red "Civitas") con su paquete de
# impacto sobre convivencia, confianza y desinformación (deltas de -15 a +15).
#
# Criterio de deltas:
#   - Compartir una noticia falsa: sube desinformación, baja confianza y convivencia.
#   - Reportar una noticia falsa: sube confianza, baja desinformación.
#   - Compartir una noticia verdadera: sube confianza y convivencia.
#   - Reportar una noticia verdadera (falso positivo): leve penalización.
#
# `gravedad` (mayor = más severa) sale del peor delta negativo de cada noticia:
# las verdaderas quedan bajas y las falsas medias o altas según el daño potencial.
#
# Los `id` se asignaron para que su orden coincida con el de `gravedad`. Así,
# insertando las noticias en el mismo orden, ArbolNoticias (por id) y ArbolStats
# (por gravedad) tienen la misma forma y el camino de uno sirve en el otro.
#
#   id= 3  gravedad=10  becas municipales (verdadera)
#   id= 8  gravedad=20  debate de candidatos (verdadera)
#   id=11  gravedad=30  rutas de buses nocturnos (verdadera)
#   id=40  gravedad=65  rumor cierre de hospital (falsa)
#   id=55  gravedad=80  rumor agua contaminada (falsa)
#   id=70  gravedad=95  rumor fraude electoral (falsa)
#
# El orden de NOTICIAS_SEED es desordenado respecto a id/gravedad para no
# producir un árbol degenerado (tipo lista).

from backend.arboles.arbol_noticias import ArbolNoticias
from backend.arboles.arbol_stats import ArbolStats


# Cada entrada: (id, gravedad, texto, veracidad, deltas_compartir, deltas_reportar)
# Orden de la lista = orden de inserción en ambos árboles.
NOTICIAS_SEED = [
    (
        11,
        30,
        "La Alcaldía de Ciudad Nova anuncia nuevas rutas de buses nocturnos "
        "para el centro a partir del próximo mes.",
        True,
        {"convivencia": +5, "confianza": +8, "desinformacion": 0},
        {"convivencia": -2, "confianza": -4, "desinformacion": 0},
    ),
    (
        40,
        65,
        "Circula en Civitas que el candidato Rojas planea cerrar el hospital "
        "público del barrio Las Flores si gana la alcaldía.",
        False,
        {"convivencia": -10, "confianza": -12, "desinformacion": +14},
        {"convivencia": +3, "confianza": +10, "desinformacion": -6},
    ),
    (
        8,
        20,
        "El debate de candidatos a la alcaldía se transmitirá en vivo por "
        "Civitas este viernes a las 7pm, confirma la comisión electoral.",
        True,
        {"convivencia": +6, "confianza": +7, "desinformacion": 0},
        {"convivencia": -1, "confianza": -3, "desinformacion": 0},
    ),
    (
        55,
        80,
        "Un video viral asegura que el agua potable de Ciudad Nova está "
        "contaminada, aunque la empresa de acueducto no ha reportado ninguna alerta.",
        False,
        {"convivencia": -12, "confianza": -8, "desinformacion": +15},
        {"convivencia": +4, "confianza": +9, "desinformacion": -8},
    ),
    (
        3,
        10,
        "La Universidad de Ciudad Nova abre inscripciones a becas municipales "
        "para estudiantes de últimos semestres.",
        True,
        {"convivencia": +7, "confianza": +6, "desinformacion": 0},
        {"convivencia": -1, "confianza": -2, "desinformacion": 0},
    ),
    (
        70,
        95,
        "Una cuenta anónima en Civitas afirma que los resultados de la "
        "próxima elección ya están arreglados por el partido en el poder.",
        False,
        {"convivencia": -14, "confianza": -15, "desinformacion": +15},
        {"convivencia": +2, "confianza": +11, "desinformacion": -5},
    ),
]


# Crea ArbolNoticias y ArbolStats insertando las noticias en el mismo orden de
# NOTICIAS_SEED, así quedan isomorfos. Retorna (arbol_noticias, arbol_stats).
def construir_arboles():
    arbol_noticias = ArbolNoticias()
    arbol_stats = ArbolStats()

    for id_, gravedad, texto, veracidad, deltas_compartir, deltas_reportar in NOTICIAS_SEED:
        arbol_noticias.insertar(id_, texto=texto, veracidad=veracidad)
        arbol_stats.insertar(
            id_,
            gravedad=gravedad,
            deltas_compartir=deltas_compartir,
            deltas_reportar=deltas_reportar,
        )

    return arbol_noticias, arbol_stats
