# Noticias de MISIÓN (A2d, opción B): un SEGUNDO par ArbolNoticias / ArbolStats, solo para las misiones de verificar de
# un mapa. Cada misión aporta UNA noticia: su `rumor` (la carta de misión del lote). No se escriben a mano: los deltas y la
# gravedad salen de una plantilla por veracidad + dificultad.
#
# Por qué un par aparte y no meterlas en el mazo de 18 (backend/datos/noticias_semilla.py, que NO se toca):
#   - ArbolStats.insertar descarta en silencio las gravedades repetidas, y 47 misiones con 6 plantillas las repetirían;
#   - el isomorfismo exige que el orden de `id` sea el orden de `gravedad`;
#   - MazoNoticias sortea TODO su árbol: las cartas de misión saldrían fuera de su misión.
#
# Cómo se garantiza el isomorfismo:
#   1. Las misiones se ordenan por (gravedad base de su plantilla, posición en el catálogo).
#   2. En ese orden reciben id = ID_BASE + 1, + 2... y gravedad = base + PASO_GRAVEDAD * (puesto dentro de su plantilla).
#      Así las gravedades son únicas y crecen igual que los ids.
#   3. Se insertan en ambos árboles en el MISMO orden: el recorrido por niveles de un árbol equilibrado (primero la
#      mediana), para que la altura sea la mínima y nunca degeneren en lista.
#   4. validar_isomorfismo lo comprueba al construir (ValueError si falla).
#
# La carta de misión se decide con el mismo EstadoPartida.decidir que las del mazo (EstadoPartida.forzar_noticia), así
# que también mueve los indicadores de la ciudad. El veredicto (pasada / fallada) y la confianza por grupo NO viven aquí:
# backend/logica/confianza_misiones.py.

from collections import namedtuple

from backend.arboles.arbol_noticias import ArbolNoticias
from backend.arboles.arbol_stats import ArbolStats
from backend.arboles.isomorfismo import validar_isomorfismo

# Los ids del mazo de 18 llegan a 75: los de misión empiezan muy por encima para no confundirse nunca.
ID_BASE = 1000

# Gravedad base por (es_verdadera, dificultad). Mismo criterio que el mazo: las verdaderas quedan bajas y las falsas, medias
# o altas; la dificultad (tema con más consecuencias) sube la gravedad. Entre dos bases hay al menos 10 puntos: caben hasta
# 99 misiones por plantilla con PASO_GRAVEDAD = 0.1 sin pisar la siguiente.
GRAVEDAD_BASE = {
    (True, "facil"): 10, (True, "media"): 20, (True, "dificil"): 30,
    (False, "facil"): 50, (False, "media"): 70, (False, "dificil"): 90,
}
PASO_GRAVEDAD = 0.1
MAX_POR_PLANTILLA = 99

# Deltas (convivencia, confianza, desinformacion) por (es_verdadera, dificultad): (al compartir, al reportar). Dentro de
# [-15, +15] como el mazo. Compartir un bulo desinforma y resta confianza; reportarlo la sube. Compartir algo cierto ayuda;
# reportarlo (falso positivo) penaliza poco.
_CLAVES = ("convivencia", "confianza", "desinformacion")
PLANTILLA_DELTAS = {
    (True, "facil"): ((+5, +6, 0), (-1, -2, 0)),
    (True, "media"): ((+6, +7, -1), (-2, -4, 0)),
    (True, "dificil"): ((+8, +8, -2), (-3, -7, +2)),
    (False, "facil"): ((-5, -6, +8), (+2, +6, -4)),
    (False, "media"): ((-9, -9, +11), (+3, +8, -6)),
    (False, "dificil"): ((-13, -13, +15), (+4, +11, -8)),
}

NoticiaMision = namedtuple(
    "NoticiaMision", "id gravedad texto veracidad deltas_compartir deltas_reportar mision_id")


def _es_de_verificar(mision):
    return getattr(mision, "tipo", "verificar") == "verificar" and isinstance(getattr(mision, "es_verdadera", None), bool)


# Lista de NoticiaMision del catálogo, ORDENADA por id (= por gravedad). Las misiones digitales no aportan noticia.
def noticias_de_mision(catalogo):
    verificar = [m for m in catalogo if _es_de_verificar(m)]
    ordenadas = sorted(
        enumerate(verificar), key=lambda par: (GRAVEDAD_BASE[(par[1].es_verdadera, par[1].dificultad)], par[0]))
    noticias, puesto = [], {}
    for numero, (_, mision) in enumerate(ordenadas, start=1):
        plantilla = (mision.es_verdadera, mision.dificultad)
        puesto[plantilla] = puesto.get(plantilla, 0) + 1
        if puesto[plantilla] > MAX_POR_PLANTILLA:
            raise ValueError(f"Demasiadas misiones con la plantilla {plantilla}: la gravedad pisaría la siguiente.")
        compartir, reportar = PLANTILLA_DELTAS[plantilla]
        noticias.append(NoticiaMision(
            id=ID_BASE + numero,
            gravedad=round(GRAVEDAD_BASE[plantilla] + PASO_GRAVEDAD * puesto[plantilla], 1),
            texto=mision.rumor, veracidad=mision.es_verdadera,
            deltas_compartir=dict(zip(_CLAVES, compartir)), deltas_reportar=dict(zip(_CLAVES, reportar)),
            mision_id=mision.id))
    return noticias


# Reordena una lista YA ordenada en el recorrido por niveles de un ABB equilibrado: primero la mediana, luego las
# medianas de cada mitad... Insertando en ese orden el árbol queda con la altura mínima.
def orden_equilibrado(ordenada):
    resultado, cola = [], [(0, len(ordenada))]
    while cola:
        desde, hasta = cola.pop(0)
        if desde >= hasta:
            continue
        medio = (desde + hasta) // 2
        resultado.append(ordenada[medio])
        cola.append((desde, medio))
        cola.append((medio + 1, hasta))
    return resultado


# El par de árboles de misión de UN mapa y la consulta «qué carta es la de esta misión».
class CartasMision:

    def __init__(self, arbol_noticias, arbol_stats, id_por_mision):
        self.arbol_noticias = arbol_noticias
        self.arbol_stats = arbol_stats
        self._id_por_mision = dict(id_por_mision)
        self._mision_por_id = {id_noticia: id_mision for id_mision, id_noticia in self._id_por_mision.items()}

    # ¿La misión (por id) tiene carta? Las digitales y las que no son del catálogo, no.
    def tiene(self, mision_id):
        return mision_id in self._id_por_mision

    def id_noticia(self, mision_id):
        return self._id_por_mision.get(mision_id)

    # (NodoNoticia, camino) de la carta de la misión, o None si no tiene. El camino sirve tal cual en arbol_stats.
    def carta(self, mision_id):
        id_noticia = self._id_por_mision.get(mision_id)
        if id_noticia is None:
            return None
        nodo, camino = self.arbol_noticias.buscar_con_camino(id_noticia)
        return (nodo, camino) if nodo is not None else None

    # Id de la misión a la que pertenece una noticia (por id de noticia), o None si es del mazo.
    def mision_de(self, id_noticia):
        return self._mision_por_id.get(id_noticia)

    # ¿Este NodoNoticia es una carta de misión de este par? (por identidad del nodo, no solo por id).
    def es_de_mision(self, nodo):
        return nodo is not None and self.arbol_noticias.buscar(getattr(nodo, "id", None)) is nodo

    def __len__(self):
        return len(self._id_por_mision)


# Construye el par de árboles de misión del catálogo (las digitales se ignoran). ValueError si no quedan isomorfos.
def construir_cartas_mision(catalogo):
    noticias = noticias_de_mision(catalogo)
    arbol_noticias, arbol_stats = ArbolNoticias(), ArbolStats()
    for n in orden_equilibrado(noticias):
        arbol_noticias.insertar(n.id, texto=n.texto, veracidad=n.veracidad)
        arbol_stats.insertar(n.id, gravedad=n.gravedad, deltas_compartir=dict(n.deltas_compartir),
                             deltas_reportar=dict(n.deltas_reportar))
    problemas = validar_isomorfismo(arbol_noticias, arbol_stats)
    if arbol_noticias.tamano() != len(noticias) or arbol_stats.tamano() != len(noticias):
        problemas.append("alguna noticia de misión no entró en los árboles (id o gravedad repetidos)")
    if problemas:
        raise ValueError("Árboles de noticias de misión no isomorfos: " + "; ".join(problemas))
    return CartasMision(arbol_noticias, arbol_stats, {n.mision_id: n.id for n in noticias})


# -- Consecuencias RETARDADAS de la carta de misión (plan final; las aplica backend/logica/efectos_retardados.py) ----------
# Además del efecto inmediato de PLANTILLA_DELTAS, la decisión sobre el rumor de la misión deja una consecuencia que llega
# entre 1 y 2 días de juego después (24-48 h del reloj de la partida), con un mensaje de causa-efecto. Es ADITIVO: nada de
# lo de arriba cambia, y con el reloj o los efectos retardados apagados estas tablas no se leen.
#
#   decisión sobre el rumor          clave             indicadores (base, dificultad «facil»)      grupo de la misión
#   compartir un rumor FALSO         rebrote           desinformación +3, confianza -2            -1,0
#   reportar un rumor FALSO          verificado        confianza +2, desinformación -1            +1,0
#   compartir un rumor VERDADERO     buena_fuente      convivencia +1,5                           +0,5
#   reportar un rumor VERDADERO      falsa_alarma      confianza -1,5                             -0,5
#   compartir un rumor FALSO de una misión de DATOS PERSONALES (MISIONES_DATOS_PERSONALES)
#                                    datos_expuestos   convivencia -4, confianza -2               -1,5
# La base se multiplica por ESCALA_RETARDO según la dificultad (facil x1, media x1,5, dificil x2) y llega a las
# RETARDO_HORAS de la dificultad (facil 24 h, media 36 h, dificil 48 h). «datos_expuestos» llega siempre a las 48 h.
# Son a propósito más chicas que el efecto inmediato (≈ un tercio): el eco de una decisión, no un segundo castigo.

CLAVE_RETARDO = {
    (False, "compartir"): "rebrote", (False, "reportar"): "verificado",
    (True, "compartir"): "buena_fuente", (True, "reportar"): "falsa_alarma",
}
# clave -> ((convivencia, confianza, desinformacion), delta de confianza del GRUPO de la misión)
CONSECUENCIAS_RETARDADAS = {
    "rebrote": ((0, -2, +3), -1.0),
    "verificado": ((0, +2, -1), +1.0),
    "buena_fuente": ((+1.5, 0, 0), +0.5),
    "falsa_alarma": ((0, -1.5, 0), -0.5),
    "datos_expuestos": ((-4, -2, 0), -1.5),
}
ESCALA_RETARDO = {"facil": 1.0, "media": 1.5, "dificil": 2.0}
RETARDO_HORAS = {"facil": 24.0, "media": 36.0, "dificil": 48.0}
RETARDO_DATOS_HORAS = 48.0
# Lotes sin carta de misión: |delta de desinformación del lote| que equivale a una consecuencia plena.
DELTA_LOTE_PLENO = 15.0

# Misiones cuyo rumor trata de datos personales de los vecinos (cuentas, documentos, teléfonos): difundirlo sin comprobar
# los expone. Solo ids que existen en backend/datos/misiones_semilla.py (lo vigila tests/test_efectos_retardados.py).
MISIONES_DATOS_PERSONALES = frozenset({"generica_mutirao", "generica_lanhouse"})

# {cuando} = «Ayer» / «Hace dos días»; {rumor} = el rumor de la misión, recortado.
MENSAJES_RETARDO = {
    "rebrote": "{cuando} compartiste sin verificar «{rumor}»: hoy el bulo volvió a circular y hay más desinformación.",
    "verificado": "{cuando} frenaste a tiempo «{rumor}»: hoy la gente confía más en lo que se publica.",
    "buena_fuente": "{cuando} compartiste algo cierto («{rumor}»): hoy los vecinos lo comentan y se organizan.",
    "falsa_alarma": "{cuando} reportaste como falso algo cierto («{rumor}»): hoy quien lo publicó desconfía de la red.",
    "datos_expuestos": ("{cuando} reenviaste sin comprobar «{rumor}», con nombres y teléfonos de vecinos: hoy se sienten "
                        "expuestos y la convivencia se resiente."),
}


# ({indicador: delta}, delta del grupo) de la consecuencia `clave` con esa dificultad. ValueError si la clave no existe.
def consecuencia_retardada(clave, dificultad="facil"):
    if clave not in CONSECUENCIAS_RETARDADAS:
        raise ValueError(f"Consecuencia retardada desconocida: {clave!r}; válidas: {tuple(CONSECUENCIAS_RETARDADAS)}.")
    base, delta_grupo = CONSECUENCIAS_RETARDADAS[clave]
    escala = ESCALA_RETARDO.get(dificultad, 1.0)
    deltas = {nombre: round(valor * escala, 2) for nombre, valor in zip(_CLAVES, base) if valor}
    return deltas, round(delta_grupo * escala, 2)
