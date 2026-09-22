"""
ABB de Impactos (consecuencias): isomorfo a ArbolNoticias.

Cada nodo guarda, para la MISMA noticia (mismo `id`), dos paquetes de deltas
sobre los indicadores globales (Convivencia, Confianza, Desinformación):
    - deltas_compartir: impacto de elegir la rama IZQUIERDA (compartir/publicar
      la noticia sin verificarla).
    - deltas_reportar: impacto de elegir la rama DERECHA (reportar/verificar
      antes de actuar).

Criterio de orden de este ABB: `gravedad` (entero que mide qué tan severo es
el impacto potencial de la noticia), NO `id`. El `id` se conserva en el nodo
únicamente para identificar a qué noticia corresponde el paquete y para
pruebas/depuración; ya no participa en las comparaciones de inserción.

Isomorfismo con ArbolNoticias: este árbol debe construirse insertando
exactamente los mismos IDs (con su gravedad), en el mismo orden, que
ArbolNoticias inserta sus ids. ArbolNoticias compara por `id`; este árbol
compara por `gravedad`. Para que ambas comparaciones produzcan la MISMA forma
de árbol al insertar la misma secuencia de noticias, el orden relativo de
`gravedad` entre las noticias debe coincidir con el orden relativo de `id`
(id ascendente = gravedad ascendente). Esa correlación se diseña y documenta
en backend/datos/noticias_seed.py.

Por eso, la forma correcta de localizar en este árbol el nodo isomorfo a un
`id` buscado en ArbolNoticias NO es buscar el id aquí (ya no está ordenado
por id), sino usar ArbolNoticias.buscar_con_camino(id) para obtener la
secuencia de decisiones izquierda/derecha, y luego replicar esa secuencia
aquí con obtener_por_camino(camino).
"""


class NodoStats:
    """Nodo del ABB de impactos.

    Atributos:
        id (int): misma clave que el NodoNoticia correspondiente en ArbolNoticias
            (no se usa para comparar/ordenar este árbol, solo para identificar
            la noticia).
        gravedad (int): clave de comparación de este ABB; mide qué tan severo
            es el impacto potencial de la noticia (mayor = más grave).
        deltas_compartir (dict): impacto de la rama izquierda, con claves
            "convivencia", "confianza", "desinformacion" (valores +/-).
        deltas_reportar (dict): impacto de la rama derecha, mismas claves.
        izquierda (NodoStats | None): subárbol con gravedad menor.
        derecha (NodoStats | None): subárbol con gravedad mayor.
    """

    def __init__(self, id, gravedad, deltas_compartir, deltas_reportar):
        self.id = id
        self.gravedad = gravedad
        self.deltas_compartir = deltas_compartir
        self.deltas_reportar = deltas_reportar
        self.izquierda = None
        self.derecha = None

    def __repr__(self):
        return (
            f"NodoStats(id={self.id}, gravedad={self.gravedad}, "
            f"deltas_compartir={self.deltas_compartir}, "
            f"deltas_reportar={self.deltas_reportar})"
        )


class ArbolStats:
    """ABB de impactos, ordenado por `gravedad` ascendente.

    La secuencia de inserción (mismo orden de noticias que ArbolNoticias) es
    lo que preserva el isomorfismo, apoyada en que gravedad e id están
    diseñados para variar en el mismo orden relativo (ver noticias_seed.py).
    """

    def __init__(self):
        self.raiz = None

    def insertar(self, nodo_o_id, gravedad=None, deltas_compartir=None, deltas_reportar=None):
        """Inserta un paquete de impacto en el árbol, comparando por `gravedad`.

        Se puede llamar de dos formas:
            arbol.insertar(nodo_stats)                                # con un NodoStats ya armado
            arbol.insertar(id, gravedad=30, deltas_compartir={...}, deltas_reportar={...})
        """
        if isinstance(nodo_o_id, NodoStats):
            nuevo = nodo_o_id
        else:
            nuevo = NodoStats(nodo_o_id, gravedad, deltas_compartir, deltas_reportar)

        if self.raiz is None:
            self.raiz = nuevo
            return nuevo

        actual = self.raiz
        while True:
            if nuevo.gravedad == actual.gravedad:
                # gravedad duplicada: no se inserta de nuevo, se conserva el nodo existente.
                return actual
            elif nuevo.gravedad < actual.gravedad:
                if actual.izquierda is None:
                    actual.izquierda = nuevo
                    return nuevo
                actual = actual.izquierda
            else:
                if actual.derecha is None:
                    actual.derecha = nuevo
                    return nuevo
                actual = actual.derecha

    def buscar_por_id(self, id):
        """Búsqueda de un NodoStats por `id`. O(n): recorre todo el árbol
        porque ArbolStats ya NO está ordenado por id (está ordenado por
        gravedad). Útil solo para pruebas/depuración; el juego NO debe usar
        este método para ubicar el nodo isomorfo a una búsqueda en
        ArbolNoticias — para eso se usa obtener_por_camino junto con
        ArbolNoticias.buscar_con_camino.
        """
        def _buscar(nodo):
            if nodo is None:
                return None
            if nodo.id == id:
                return nodo
            encontrado = _buscar(nodo.izquierda)
            if encontrado is not None:
                return encontrado
            return _buscar(nodo.derecha)

        return _buscar(self.raiz)

    def obtener_por_camino(self, camino):
        """Recorre el árbol desde la raíz siguiendo `camino`, una lista de
        strings "izquierda"/"derecha" (típicamente la que devuelve
        ArbolNoticias.buscar_con_camino). Devuelve el NodoStats alcanzado.

        Este es el mecanismo que debe usar el juego para ir de un id buscado
        en ArbolNoticias al paquete de impacto isomorfo en ArbolStats, sin
        volver a buscar por id aquí.

        Retorna None si el camino se corta antes de tiempo (subárbol
        inexistente), lo cual indicaría un bug de isomorfismo entre los
        árboles (formas distintas).
        """
        actual = self.raiz
        for paso in camino:
            if actual is None:
                return None
            if paso == "izquierda":
                actual = actual.izquierda
            elif paso == "derecha":
                actual = actual.derecha
            else:
                raise ValueError(f"Paso de camino inválido: {paso!r}")
        return actual

    def recorrido_inorden(self):
        """Devuelve una lista de NodoStats en orden ascendente de id (útil para depurar)."""
        resultado = []

        def _visitar(nodo):
            if nodo is None:
                return
            _visitar(nodo.izquierda)
            resultado.append(nodo)
            _visitar(nodo.derecha)

        _visitar(self.raiz)
        return resultado

    def recorrido_preorden(self):
        resultado = []

        def _visitar(nodo):
            if nodo is None:
                return
            resultado.append(nodo)
            _visitar(nodo.izquierda)
            _visitar(nodo.derecha)

        _visitar(self.raiz)
        return resultado

    def recorrido_postorden(self):
        resultado = []

        def _visitar(nodo):
            if nodo is None:
                return
            _visitar(nodo.izquierda)
            _visitar(nodo.derecha)
            resultado.append(nodo)

        _visitar(self.raiz)
        return resultado
