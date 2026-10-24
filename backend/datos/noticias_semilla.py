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
#   id= 5  gravedad=14  reunión de vecinos en la Rádio Comunitária (verdadera)
#   id= 8  gravedad=20  debate de candidatos (verdadera)
#   id=10  gravedad=25  horario del Mercado Municipal (verdadera)
#   id=11  gravedad=30  rutas de buses nocturnos (verdadera)
#   id=15  gravedad=35  mantenimiento del teleférico (verdadera)
#   id=20  gravedad=40  vacunación en la Praça da Sé (verdadera)
#   id=25  gravedad=45  desfile de la Escola de Samba cancelado (falsa)
#   id=30  gravedad=50  foto del teleférico «colgando» (falsa)
#   id=35  gravedad=55  precio del feijão al doble (falsa)
#   id=40  gravedad=65  rumor cierre de hospital (falsa)
#   id=45  gravedad=70  cierre de la Rádio Comunitária (falsa)
#   id=50  gravedad=75  pasajes gratis en la Rodoviária (falsa, estafa)
#   id=55  gravedad=80  rumor agua contaminada (falsa)
#   id=60  gravedad=85  demolición de la Praça da Sé (falsa)
#   id=65  gravedad=90  alerta falsa de deslizamientos (falsa)
#   id=70  gravedad=95  rumor fraude electoral (falsa)
#   id=75  gravedad=98  elecciones suspendidas por una cuenta falsa (falsa)
#
# El orden de NOTICIAS_SEMILLA NO sigue el id: es el recorrido por niveles de un árbol equilibrado (30, luego 10 y
# 55, luego 5, 15, 40, 65...), así los dos árboles quedan con altura 5, la mínima para 18 noticias, y nunca
# degeneran en lista. Las 6 noticias de siempre (3, 8, 11, 40, 55, 70) no cambian; las otras 12 son de 2026-10
# (contexto de Ciudad Nova: Rádio, Mercado, Teleférico, Escola de Samba, Rodoviária).

from backend.arboles.arbol_noticias import ArbolNoticias
from backend.arboles.arbol_stats import ArbolStats
from backend.arboles.isomorfismo import validar_isomorfismo


# Cada entrada: (id, gravedad, texto, veracidad, deltas_compartir, deltas_reportar)
# Orden de la lista = orden de inserción en ambos árboles.
NOTICIAS_SEMILLA = [
    (
        30,
        50,
        "Una foto muestra el teleférico de Ciudad Nova «colgando» de un solo cable; en realidad "
        "es de otra ciudad y de hace años.",
        False,
        {"convivencia": -5, "confianza": -8, "desinformacion": +9},
        {"convivencia": +2, "confianza": +7, "desinformacion": -5},
    ),
    (
        10,
        25,
        "El Mercado Municipal amplía su horario los domingos durante las fiestas de junio, "
        "confirma su administración.",
        True,
        {"convivencia": +4, "confianza": +6, "desinformacion": 0},
        {"convivencia": -2, "confianza": -4, "desinformacion": 0},
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
        5,
        14,
        "La Rádio Comunitária 98,7 transmitirá en vivo la reunión de vecinos del Morro da "
        "Esperança este sábado.",
        True,
        {"convivencia": +5, "confianza": +6, "desinformacion": 0},
        {"convivencia": -1, "confianza": -2, "desinformacion": 0},
    ),
    (
        15,
        35,
        "La Estação do Teleférico cerrará dos días por mantenimiento programado; la Prefeitura "
        "ya publicó las fechas.",
        True,
        {"convivencia": +5, "confianza": +8, "desinformacion": 0},
        {"convivencia": -3, "confianza": -6, "desinformacion": +1},
    ),
    (
        40,
        65,
        "Circula en Civitas que el candidato Rojas planea cerrar el hospital "
        "público del Morro da Esperança si gana la alcaldía.",
        False,
        {"convivencia": -10, "confianza": -12, "desinformacion": +14},
        {"convivencia": +3, "confianza": +10, "desinformacion": -6},
    ),
    (
        65,
        90,
        "Un mensaje alarmista dice que esta noche habrá deslizamientos en todo el Morro y pide "
        "abandonar las casas; Defensa Civil no ha emitido ninguna alerta.",
        False,
        {"convivencia": -15, "confianza": -13, "desinformacion": +15},
        {"convivencia": +5, "confianza": +11, "desinformacion": -8},
    ),
    (
        3,
        10,
        "La Universidade de Ciudad Nova abre inscripciones a becas municipales "
        "para estudiantes de últimos semestres.",
        True,
        {"convivencia": +7, "confianza": +6, "desinformacion": 0},
        {"convivencia": -1, "confianza": -2, "desinformacion": 0},
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
        11,
        30,
        "La Prefeitura de Ciudad Nova anuncia nuevas rutas de buses nocturnos "
        "para el centro a partir del próximo mes.",
        True,
        {"convivencia": +5, "confianza": +8, "desinformacion": 0},
        {"convivencia": -2, "confianza": -4, "desinformacion": 0},
    ),
    (
        20,
        40,
        "El Hospital Santa Casa organiza una jornada gratuita de vacunación en la Praça da Sé "
        "este domingo.",
        True,
        {"convivencia": +8, "confianza": +8, "desinformacion": -2},
        {"convivencia": -3, "confianza": -7, "desinformacion": +2},
    ),
    (
        35,
        55,
        "Circula que el Mercado Municipal subirá al doble el precio del feijão desde mañana; los "
        "comerciantes lo desmienten.",
        False,
        {"convivencia": -9, "confianza": -6, "desinformacion": +10},
        {"convivencia": +4, "confianza": +6, "desinformacion": -6},
    ),
    (
        45,
        70,
        "Una cadena del zap asegura que la Rádio Comunitária fue cerrada «por decir la verdad»; la "
        "radio sigue al aire.",
        False,
        {"convivencia": -10, "confianza": -12, "desinformacion": +12},
        {"convivencia": +3, "confianza": +9, "desinformacion": -7},
    ),
    (
        60,
        85,
        "Un video afirma que la Praça da Sé será demolida para hacer un estacionamiento privado; la "
        "imagen es un montaje.",
        False,
        {"convivencia": -14, "confianza": -12, "desinformacion": +14},
        {"convivencia": +4, "confianza": +10, "desinformacion": -7},
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
    (
        25,
        45,
        "Un audio dice que la Escola de Samba se queda sin desfile por orden de la Prefeitura; no "
        "hay ningún comunicado.",
        False,
        {"convivencia": -6, "confianza": -7, "desinformacion": +8},
        {"convivencia": +2, "confianza": +6, "desinformacion": -4},
    ),
    (
        50,
        75,
        "Aseguran que en la Rodoviária regalan pasajes a quien comparta un enlace; es una estafa "
        "para robar datos.",
        False,
        {"convivencia": -8, "confianza": -13, "desinformacion": +13},
        {"convivencia": +3, "confianza": +10, "desinformacion": -8},
    ),
    (
        75,
        98,
        "Una cuenta que imita a la Prefeitura anuncia que las elecciones municipales se suspenden; "
        "la comisión electoral lo desmiente.",
        False,
        {"convivencia": -15, "confianza": -15, "desinformacion": +15},
        {"convivencia": +3, "confianza": +12, "desinformacion": -6},
    ),
]


# Crea ArbolNoticias y ArbolStats insertando las noticias en el mismo orden de
# NOTICIAS_SEMILLA, así quedan isomorfos. Retorna (arbol_noticias, arbol_stats).
def construir_arboles():
    arbol_noticias = ArbolNoticias()
    arbol_stats = ArbolStats()

    for id_, gravedad, texto, veracidad, deltas_compartir, deltas_reportar in NOTICIAS_SEMILLA:
        arbol_noticias.insertar(id_, texto=texto, veracidad=veracidad)
        arbol_stats.insertar(
            id_,
            gravedad=gravedad,
            deltas_compartir=deltas_compartir,
            deltas_reportar=deltas_reportar,
        )

    # Falla al arrancar si los datos semilla desincronizan los dos árboles.
    problemas = validar_isomorfismo(arbol_noticias, arbol_stats)
    if problemas:
        raise ValueError("Árboles de noticias no isomorfos: " + "; ".join(problemas))

    return arbol_noticias, arbol_stats


# Revisa NOTICIAS_SEMILLA (o el catálogo recibido) y devuelve la lista de problemas
# (vacía = datos sanos): ids/gravedades repetidos, gravedad que no sigue el orden de
# id (rompería el isomorfismo), deltas fuera de [-15, +15] o con claves distintas.
def validar_noticias_semilla(noticias=None):
    noticias = NOTICIAS_SEMILLA if noticias is None else noticias
    problemas = []
    claves = {"convivencia", "confianza", "desinformacion"}

    ids = [n[0] for n in noticias]
    gravedades = [n[1] for n in noticias]
    if len(set(ids)) != len(ids):
        problemas.append("hay ids de noticia repetidos")
    if len(set(gravedades)) != len(gravedades):
        problemas.append("hay gravedades repetidas")

    por_id = sorted(noticias, key=lambda n: n[0])
    if [n[1] for n in por_id] != sorted(gravedades):
        problemas.append("el orden de gravedad no coincide con el orden de id")

    for id_, _grav, _texto, _ver, compartir, reportar in noticias:
        for nombre, deltas in (("compartir", compartir), ("reportar", reportar)):
            if set(deltas) != claves:
                problemas.append(f"noticia {id_}: deltas de {nombre} con claves inválidas")
            elif any(not -15 <= v <= 15 for v in deltas.values()):
                problemas.append(f"noticia {id_}: deltas de {nombre} fuera de [-15, 15]")

    return problemas
