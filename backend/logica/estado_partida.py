# Estado de la partida (modelo puro, sin motor gráfico): indicadores de la
# ciudad, noticia activa y resolución de una decisión del jugador.
#
# Flujo de decidir(): MazoNoticias.siguiente() da (nodo, camino); el camino se
# replica en ArbolStats.obtener_por_camino para obtener los deltas isomorfos;
# se aplican a los indicadores (recortados a [0, 100]) y se avanza la noticia.
#
# Sin estado global, sin I/O y sin random propio: el azar vive en el mazo, que
# se puede inyectar para pruebas deterministas.

import logging

from backend.logica.mazo_noticias import MazoNoticias

_log = logging.getLogger(__name__)

# Los indicadores viven en [0, 100]; todo delta se recorta a ese rango.
INDICADOR_MIN = 0
INDICADOR_MAX = 100

NOMBRES_INDICADORES = ("convivencia", "confianza", "desinformacion")

# Todos los indicadores arrancan al medio del rango.
VALOR_INICIAL = 50

_DECISIONES_VALIDAS = ("compartir", "reportar")


def _clamp(valor, minimo=INDICADOR_MIN, maximo=INDICADOR_MAX):
    return max(minimo, min(maximo, valor))


# Partida en curso. `mazo` es opcional (por defecto MazoNoticias) y permite
# inyectar un mazo falso en los tests. Al construirse carga la primera noticia.
class EstadoPartida:

    def __init__(self, arbol_noticias, arbol_stats, mazo=None):
        self.arbol_noticias = arbol_noticias
        self.arbol_stats = arbol_stats
        self.mazo = mazo if mazo is not None else MazoNoticias(arbol_noticias)

        self._indicadores = {nombre: VALOR_INICIAL for nombre in NOMBRES_INDICADORES}
        self._noticia_actual = None
        self._camino_actual = None
        self.siguiente_noticia()

    # -- Consulta --

    # copia: mutarla no altera el estado
    @property
    def indicadores(self):
        return dict(self._indicadores)

    # NodoNoticia activo, o None si no hay noticia
    @property
    def noticia_actual(self):
        return self._noticia_actual

    # camino ("izquierda"/"derecha") de la noticia activa, o None
    @property
    def camino_actual(self):
        return self._camino_actual

    @property
    def hay_noticia(self):
        return self._noticia_actual is not None

    # -- Cambios de estado --

    # Suma `deltas` y recorta a [0, 100]; clave ausente cuenta como 0 y las
    # claves que no son indicadores se ignoran.
    def aplicar_deltas(self, deltas):
        for nombre in NOMBRES_INDICADORES:
            self._indicadores[nombre] = _clamp(self._indicadores[nombre] + deltas.get(nombre, 0))

    # Pide la próxima noticia al mazo; si no hay, noticia_actual y camino_actual
    # quedan en None.
    def siguiente_noticia(self):
        resultado = self.mazo.siguiente()
        if resultado is None:
            self._noticia_actual = None
            self._camino_actual = None
            return
        self._noticia_actual, self._camino_actual = resultado

    # tipo: "compartir" o "reportar" (otro valor lanza ValueError). Retorna una
    # copia de los deltas aplicados, o None si no se aplicó nada (sin noticia
    # activa o isomorfismo roto, que registra un warning).
    def decidir(self, tipo):
        if tipo not in _DECISIONES_VALIDAS:
            raise ValueError(
                f"Decisión inválida: {tipo!r}; se esperaba una de {_DECISIONES_VALIDAS}."
            )

        if self._noticia_actual is None or self._camino_actual is None:
            return None

        nodo_stats = self.arbol_stats.obtener_por_camino(self._camino_actual)
        if nodo_stats is None:
            # no debería pasar con árboles bien construidos; se ignora la decisión
            _log.warning(
                "obtener_por_camino devolvió None para camino=%s (noticia id=%s): "
                "isomorfismo roto entre ArbolNoticias y ArbolStats; decisión ignorada.",
                self._camino_actual,
                self._noticia_actual.id,
            )
            return None

        if tipo == "compartir":
            deltas = nodo_stats.deltas_compartir
        else:
            deltas = nodo_stats.deltas_reportar

        self.aplicar_deltas(deltas)
        self.siguiente_noticia()
        return dict(deltas)
