# Estado de la partida (modelo puro, sin motor gráfico): indicadores de la
# ciudad, noticia activa y resolución de una decisión del jugador.
#
# Flujo de decidir(): MazoNoticias.siguiente() da (nodo, camino); el camino se
# replica en ArbolStats.obtener_por_camino para obtener los deltas isomorfos;
# se aplican a los indicadores (recortados a [0, 100]) y se avanza la noticia.
#
# Sin estado global, sin I/O y sin random propio: el azar vive en el mazo, que
# se puede inyectar para pruebas deterministas.
#
# Carta de misión (A2d): forzar_noticia() pone en mesa una noticia que NO sale del mazo
# (el rumor de la misión, del par de árboles de backend/datos/noticias_mision.py) con SU
# árbol de stats; decidir() la resuelve igual que a las demás (mismos indicadores) y luego
# vuelve la carta del mazo que estaba esperando, así el mazo no pierde ninguna.

import logging

from backend.logica.mazo_noticias import MazoNoticias

_registro = logging.getLogger(__name__)

# Los indicadores viven en [0, 100]; todo delta se recorta a ese rango.
INDICADOR_MIN = 0
INDICADOR_MAX = 100

NOMBRES_INDICADORES = ("convivencia", "confianza", "desinformacion")

# Todos los indicadores arrancan al medio del rango.
VALOR_INICIAL = 50

_DECISIONES_VALIDAS = ("compartir", "reportar")


def recortar(valor, minimo=INDICADOR_MIN, maximo=INDICADOR_MAX):
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
        # Carta forzada: árbol de stats de la noticia en mesa (None = el del mazo) y la carta
        # del mazo que espera detrás ((nodo, camino) o None), que vuelve al resolverse la forzada.
        self._stats_actual = None
        self._forzada = False
        self._en_espera = None
        # Par de árboles de misión del mapa (noticias_mision.CartasMision) o None = sin cartas
        # de misión (en línea, sin GameState o con las consecuencias apagadas). Lo fija
        # FlujoConGameState; LoteMision lo lee para forzar la carta de la misión.
        self.cartas_mision = None
        self.siguiente_noticia()

    # -- Consulta --

    # copia: mutarla no altera el estado
    def indicadores(self):
        return dict(self._indicadores)

    # NodoNoticia activo, o None si no hay noticia
    def noticia_actual(self):
        return self._noticia_actual

    # camino ("izquierda"/"derecha") de la noticia activa, o None
    def camino_actual(self):
        return self._camino_actual

    def hay_noticia(self):
        return self._noticia_actual is not None

    # True si la noticia en mesa se puso con forzar_noticia (no salió del mazo).
    def noticia_forzada(self):
        return self._forzada

    # -- Cambios de estado --

    # Suma `deltas` y recorta a [0, 100]; clave ausente cuenta como 0 y las
    # claves que no son indicadores se ignoran.
    def aplicar_deltas(self, deltas):
        for nombre in NOMBRES_INDICADORES:
            self._indicadores[nombre] = recortar(self._indicadores[nombre] + deltas.get(nombre, 0))

    # Fija indicadores (p. ej. al restaurar una partida) recortando a [0, 100];
    # las claves ausentes no cambian y las que no son indicadores se ignoran.
    def fijar_indicadores(self, valores):
        for nombre in NOMBRES_INDICADORES:
            if nombre in valores:
                self._indicadores[nombre] = recortar(valores[nombre])

    # Pone en mesa `nodo` (NodoNoticia) con su `camino` y el `arbol_stats` isomorfo donde
    # ese camino lleva a sus deltas. La carta del mazo que estaba en mesa queda en espera y
    # vuelve al decidir (o con retirar_noticia_forzada). Forzar otra encima reemplaza a la
    # forzada anterior sin perder la del mazo.
    def forzar_noticia(self, nodo, camino, arbol_stats):
        if not self._forzada:
            self._en_espera = (
                (self._noticia_actual, self._camino_actual) if self._noticia_actual is not None else None)
        self._noticia_actual = nodo
        self._camino_actual = list(camino)
        self._stats_actual = arbol_stats
        self._forzada = True

    # Quita la carta forzada SIN decidirla (lote abandonado) y devuelve a la mesa la del
    # mazo que esperaba. True si había una forzada.
    def retirar_noticia_forzada(self):
        if not self._forzada:
            return False
        self.siguiente_noticia()
        return True

    # Pide la próxima noticia al mazo; si no hay, noticia_actual y camino_actual
    # quedan en None. Si había una carta forzada, vuelve la del mazo que esperaba (si
    # no esperaba ninguna, se pide una nueva).
    def siguiente_noticia(self):
        self._stats_actual = None
        if self._forzada:
            self._forzada = False
            en_espera, self._en_espera = self._en_espera, None
            if en_espera is not None:
                self._noticia_actual, self._camino_actual = en_espera
                return
        resultado = self.mazo.siguiente()
        if resultado is None:
            self._noticia_actual = None
            self._camino_actual = None
            return
        self._noticia_actual, self._camino_actual = resultado

    # -- Guardado (JSON) --

    # Indicadores y estado del mazo (qué noticias ya salieron en la ronda y cuál está en mesa). Una carta de misión
    # forzada NO se guarda: la partida solo se guarda fuera del minijuego, y lo que se anota es la carta del mazo.
    def a_dict(self):
        if self._forzada:
            en_mesa = self._en_espera[0] if self._en_espera is not None else None
        else:
            en_mesa = self._noticia_actual
        return {
            "indicadores": self.indicadores(),
            "mazo_vistos": sorted(getattr(self.mazo, "ids_vistos", ())),
            "mazo_ultimo": getattr(self.mazo, "_ultimo_id", None),
            "noticia": en_mesa.id if en_mesa is not None else None,
        }

    # Deja los indicadores, el mazo y la noticia en mesa como en `datos` (de a_dict). Tolerante: los ids que ya no
    # existen en el árbol se ignoran, y si la noticia guardada no existe se pide otra al mazo.
    def restaurar(self, datos):
        self.fijar_indicadores(datos.get("indicadores") or {})
        disponibles = set(getattr(self.mazo, "ids_disponibles", ()))
        if hasattr(self.mazo, "ids_vistos"):
            self.mazo.ids_vistos = {i for i in (datos.get("mazo_vistos") or ()) if i in disponibles}
            ultimo = datos.get("mazo_ultimo")
            self.mazo._ultimo_id = ultimo if ultimo in disponibles else None
        self._forzada, self._en_espera, self._stats_actual = False, None, None
        encontrada = self.arbol_noticias.buscar_con_camino(datos["noticia"]) if datos.get("noticia") in disponibles else None
        if encontrada is None:
            self.siguiente_noticia()
        else:
            self._noticia_actual, self._camino_actual = encontrada
            if hasattr(self.mazo, "ids_vistos"):
                self.mazo.ids_vistos.add(self._noticia_actual.id)

    # tipo: "compartir" o "reportar" (otro valor lanza ValueError). Retorna una
    # copia de los deltas aplicados, o None si no se aplicó nada (sin noticia
    # activa, o isomorfismo roto: registra un warning y descarta esa noticia).
    def decidir(self, tipo):
        if tipo not in _DECISIONES_VALIDAS:
            raise ValueError(
                f"Decisión inválida: {tipo!r}; se esperaba una de {_DECISIONES_VALIDAS}."
            )

        if self._noticia_actual is None or self._camino_actual is None:
            return None

        arbol_stats = self._stats_actual if self._stats_actual is not None else self.arbol_stats
        nodo_stats = arbol_stats.obtener_por_camino(self._camino_actual)
        if nodo_stats is None:
            # no debería pasar con árboles bien construidos; se ignora la decisión
            _registro.warning(
                "obtener_por_camino devolvió None para camino=%s (noticia id=%s): "
                "isomorfismo roto entre ArbolNoticias y ArbolStats; decisión ignorada.",
                self._camino_actual,
                self._noticia_actual.id,
            )
            # se descarta la noticia rota: si no, la misma tarjeta se repetiría sin salida
            self.siguiente_noticia()
            return None

        if tipo == "compartir":
            deltas = nodo_stats.deltas_compartir
        else:
            deltas = nodo_stats.deltas_reportar

        self.aplicar_deltas(deltas)
        self.siguiente_noticia()
        return dict(deltas)
