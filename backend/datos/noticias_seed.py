"""
Catálogo semilla de noticias para pruebas de ArbolNoticias / ArbolStats.

Ambientación: Ciudad Nova, campaña electoral a la alcaldía, red social ficticia
"Civitas". Mezcla de noticias verdaderas y falsas con su paquete de impacto
correspondiente sobre los indicadores globales:
    - convivencia
    - confianza
    - desinformacion

Criterio narrativo usado para los deltas (rango usado: -15 a +15):
    - Compartir una noticia FALSA: sube desinformacion, baja confianza,
      y suele bajar convivencia (genera roces entre ciudadanos).
    - Reportar una noticia FALSA: sube confianza (se frena el bulo), no
      empeora desinformacion (incluso puede bajarla un poco), efecto neutro
      o levemente positivo en convivencia.
    - Compartir una noticia VERDADERA: sube confianza y convivencia, no
      afecta (o mejora levemente) desinformacion.
    - Reportar una noticia VERDADERA (falso positivo, se está frenando
      información legítima): pequeña penalización en confianza y/o
      convivencia, sin beneficio real en desinformacion.

Criterio de `gravedad` (entero, mayor = más severo): se basa en la magnitud
del peor delta de cada noticia (el delta negativo más fuerte entre
deltas_compartir y deltas_reportar), y en cuánto compromete la convivencia o
la legitimidad institucional de Ciudad Nova. Las noticias verdaderas, cuyo
único riesgo es el "falso positivo" de ser reportadas/ocultadas, quedan con
gravedad baja. Las noticias falsas, cuyo riesgo es viralizarse, quedan con
gravedad media o alta según el daño potencial (un rumor sobre agua
contaminada o sobre fraude electoral es más grave que un rumor puntual sobre
un candidato).

IMPORTANTE — por qué los `id` fueron reasignados (restricción matemática):
En cualquier ABB, el recorrido in-order queda ordenado ascendentemente por la
clave de comparación. ArbolNoticias compara por `id`; ArbolStats (ver
backend/arboles/arbol_stats.py) ahora compara por `gravedad`. El juego ubica
el nodo isomorfo en ArbolStats replicando en ese árbol la MISMA secuencia de
decisiones izquierda/derecha que tomó la búsqueda por id en ArbolNoticias
(ArbolNoticias.buscar_con_camino + ArbolStats.obtener_por_camino). Para que
esa réplica de camino aterrice siempre en el nodo de la MISMA noticia, ambos
árboles deben tener la misma forma. Insertando la misma secuencia de
noticias en ambos árboles, la ÚNICA forma de garantizar formas idénticas
cuando un árbol compara por id y el otro por gravedad es que el orden
relativo de gravedad entre las noticias coincida con el orden relativo de
id (id ascendente = gravedad ascendente). Por eso aquí se reasignaron los
`id` para que su orden ascendente coincida exactamente con el orden
ascendente de `gravedad` diseñado para cada noticia.

Tabla id / gravedad (orden ascendente en ambas columnas, a propósito):
    id= 3  gravedad=10  becas municipales (verdadera)
    id= 8  gravedad=20  debate de candidatos (verdadera)
    id=11  gravedad=30  rutas de buses nocturnos (verdadera)
    id=40  gravedad=65  rumor cierre de hospital (falsa)
    id=55  gravedad=80  rumor agua contaminada (falsa)
    id=70  gravedad=95  rumor fraude electoral (falsa)

La secuencia de INSERCIÓN (orden de aparición en NOTICIAS_SEED) se mantiene
desordenada respecto a id/gravedad, para no producir un árbol degenerado
(tipo lista). Como id y gravedad varían en el mismo orden relativo entre
estas 6 noticias, insertar esa misma secuencia en ambos árboles produce
automáticamente la misma forma en los dos (se verifica más abajo).

`construir_arboles()` inserta las noticias en ArbolNoticias y en ArbolStats
EN EL MISMO ORDEN. Esa igualdad de orden, junto con la correlación id/gravedad
de arriba, es lo que garantiza el isomorfismo (misma forma, mismas
posiciones) entre ambos árboles.
"""

from backend.arboles.arbol_noticias import ArbolNoticias
from backend.arboles.arbol_stats import ArbolStats


# Cada entrada: (id, gravedad, texto, veracidad, deltas_compartir, deltas_reportar)
# Orden de la lista = orden de inserción en ambos árboles (ver docstring arriba).
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


def construir_arboles():
    """Crea un ArbolNoticias y un ArbolStats, insertando ambos con el MISMO
    orden de noticias (el orden en que aparecen en NOTICIAS_SEED) para
    garantizar que queden isomorfos. ArbolNoticias compara por `id`,
    ArbolStats compara por `gravedad`; ambos quedan con la misma forma porque
    id y gravedad están diseñados con el mismo orden relativo (ver docstring
    del módulo). Retorna (arbol_noticias, arbol_stats)."""
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


if __name__ == "__main__":
    arbol_noticias, arbol_stats = construir_arboles()

    print("=== In-order ArbolNoticias (por id ascendente) ===")
    ids_inorder = []
    for nodo in arbol_noticias.recorrido_inorden():
        ids_inorder.append(nodo.id)
        print(nodo)

    print("\n=== In-order ArbolStats (por gravedad ascendente) ===")
    gravedades_inorder = []
    for nodo in arbol_stats.recorrido_inorden():
        gravedades_inorder.append(nodo.gravedad)
        print(nodo)

    print("\n=== Comparación de órdenes (evidencia de por qué funciona la réplica de camino) ===")
    print(f"Orden de ids en ArbolNoticias:      {ids_inorder}")
    print(f"Orden de ids según gravedad (Stats): {[n.id for n in arbol_stats.recorrido_inorden()]}")
    print(f"Orden de gravedades en ArbolStats:    {gravedades_inorder}")
    print(
        "-> El orden de ids visto por ArbolStats.recorrido_inorden() coincide con "
        "el de ArbolNoticias.recorrido_inorden(): id ascendente == gravedad ascendente."
    )

    print("\n=== Prueba de isomorfismo por réplica de camino ===")
    for id_prueba in (11, 8, 3, 70, 999):
        noticia, camino = arbol_noticias.buscar_con_camino(id_prueba)
        print(f"\nID buscado: {id_prueba}")
        print(f"  ArbolNoticias.buscar_con_camino -> nodo={noticia}, camino={camino}")

        if noticia is None:
            print("  (ID inexistente, se esperaba None; no se replica camino)")
            continue

        stats = arbol_stats.obtener_por_camino(camino)
        print(f"  ArbolStats.obtener_por_camino(camino) -> {stats}")

        if stats is not None and stats.id == noticia.id:
            print(f"  OK: mismo id ({noticia.id}) en ambos árboles siguiendo el mismo camino.")
        else:
            print("  REVISAR: el camino replicado no aterrizó en el mismo id (bug de isomorfismo).")
