"""
Estado de la partida (modelo puro, sin motor gráfico).

`EstadoPartida` concentra lo que antes vivía dentro de la escena pygame original
(retirada en el Módulo 5): los indicadores de la ciudad, la
noticia activa y la resolución de una decisión del jugador. La vista (Ursina)
solo lo consume: le pide `indicadores`, `noticia_actual`, y le llama a
`decidir("compartir" | "reportar")`.

Flujo de una decisión (integración de los dos árboles isomorfos):
    MazoNoticias.siguiente() -> (nodo de ArbolNoticias, camino)
    ArbolStats.obtener_por_camino(camino) -> paquete de deltas isomorfo
    aplicar_deltas(...) sobre los indicadores (con recorte a [0, 100])
    avanzar a la siguiente noticia del mazo

Reglas de diseño:
    - Sin estado global, sin I/O y sin `random` propio: el azar vive en el mazo
      (que se puede inyectar para pruebas deterministas).
    - Este módulo NO importa ursina/pygame; lo verifica tests/test_backend_puro.py.
"""

import logging

from backend.logica.mazo_noticias import MazoNoticias

_log = logging.getLogger(__name__)

# Regla de negocio: los indicadores viven en el rango [0, 100]. Cualquier
# delta aplicado SIEMPRE se recorta (clamp) a ese rango.
INDICADOR_MIN = 0
INDICADOR_MAX = 100

NOMBRES_INDICADORES = ("convivencia", "confianza", "desinformacion")

# Todos los indicadores arrancan al medio del rango.
VALOR_INICIAL = 50

_DECISIONES_VALIDAS = ("compartir", "reportar")


def _clamp(valor, minimo=INDICADOR_MIN, maximo=INDICADOR_MAX):
    """Recorta `valor` al rango [minimo, maximo]."""
    return max(minimo, min(maximo, valor))


class EstadoPartida:
    """Estado de una partida en curso.

    Constructor:
        arbol_noticias (ArbolNoticias): catálogo de noticias.
        arbol_stats (ArbolStats): árbol de impactos isomorfo al anterior.
        mazo: objeto con `siguiente()` -> (nodo, camino) | None. Si es None se
            crea un `MazoNoticias(arbol_noticias)`; el parámetro existe para
            inyectar un mazo falso en los tests.

    Al construirse ya carga la primera noticia.
    """

    def __init__(self, arbol_noticias, arbol_stats, mazo=None):
        self.arbol_noticias = arbol_noticias
        self.arbol_stats = arbol_stats
        self.mazo = mazo if mazo is not None else MazoNoticias(arbol_noticias)

        self._indicadores = {nombre: VALOR_INICIAL for nombre in NOMBRES_INDICADORES}
        self._noticia_actual = None
        self._camino_actual = None
        self.siguiente_noticia()

    # -- Consulta ----------------------------------------------------------

    @property
    def indicadores(self):
        """Copia del dict de indicadores: mutarla no altera el estado."""
        return dict(self._indicadores)

    @property
    def noticia_actual(self):
        """NodoNoticia activo, o None si no hay noticia."""
        return self._noticia_actual

    @property
    def camino_actual(self):
        """Camino (lista de "izquierda"/"derecha") de la noticia activa, o None."""
        return self._camino_actual

    @property
    def hay_noticia(self):
        return self._noticia_actual is not None

    # -- Cambios de estado -------------------------------------------------

    def aplicar_deltas(self, deltas):
        """Suma `deltas` a los indicadores y recorta cada uno a [0, 100].

        Clave ausente cuenta como 0; claves que no son indicadores se ignoran.
        """
        for nombre in NOMBRES_INDICADORES:
            self._indicadores[nombre] = _clamp(self._indicadores[nombre] + deltas.get(nombre, 0))

    def siguiente_noticia(self):
        """Pide la próxima noticia al mazo. Si el mazo no tiene (None),
        noticia_actual y camino_actual quedan en None."""
        resultado = self.mazo.siguiente()
        if resultado is None:
            self._noticia_actual = None
            self._camino_actual = None
            return
        self._noticia_actual, self._camino_actual = resultado

    def decidir(self, tipo):
        """Resuelve la decisión del jugador sobre la noticia activa.

        Args:
            tipo: "compartir" o "reportar"; cualquier otro valor es un error de
                programación de quien llama y lanza ValueError.

        Retorna una COPIA del dict de deltas aplicado, o None si no se aplicó
        nada (no hay noticia activa, o el isomorfismo entre árboles está roto:
        en ese caso se registra un warning y el estado no cambia).
        """
        if tipo not in _DECISIONES_VALIDAS:
            raise ValueError(
                f"Decisión inválida: {tipo!r}; se esperaba una de {_DECISIONES_VALIDAS}."
            )

        if self._noticia_actual is None or self._camino_actual is None:
            return None

        nodo_stats = self.arbol_stats.obtener_por_camino(self._camino_actual)
        if nodo_stats is None:
            # No debería pasar si los árboles están bien construidos
            # (isomorfismo roto). Se avisa y se ignora la decisión sin romper la partida.
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
