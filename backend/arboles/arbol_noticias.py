"""
Arbol Genérico Narrativo: catálogo de noticias de Civitas.

Implementado como Árbol Binario de Búsqueda (ABB) ordenado por el `id` de la
noticia. Este árbol es isomorfo a ArbolStats (backend/arboles/arbol_stats.py):
ambos deben construirse insertando exactamente los mismos IDs, en el mismo
orden, para que compartan la misma forma y cada noticia quede en la misma
posición que su paquete de impacto correspondiente.
"""


class NodoNoticia:
    """Nodo del ABB de noticias.

    Atributos:
        id (int): clave del ABB, identifica la noticia de forma única.
        texto (str): contenido de la publicación tal como se muestra al jugador.
        veracidad (bool): True si la noticia es verdadera, False si es falsa.
        izquierda (NodoNoticia | None): subárbol con ids menores.
        derecha (NodoNoticia | None): subárbol con ids mayores.
    """

    def __init__(self, id, texto, veracidad):
        self.id = id
        self.texto = texto
        self.veracidad = veracidad
        self.izquierda = None
        self.derecha = None

    def __repr__(self):
        v = "verdadera" if self.veracidad else "falsa"
        return f"NodoNoticia(id={self.id}, veracidad={v}, texto={self.texto!r})"


class ArbolNoticias:
    """ABB de noticias, ordenado por `id` ascendente (izquierda < nodo < derecha)."""

    def __init__(self):
        self.raiz = None

    def insertar(self, nodo_o_datos, texto=None, veracidad=None):
        """Inserta una noticia en el árbol.

        Se puede llamar de dos formas:
            arbol.insertar(nodo_noticia)                  # con un NodoNoticia ya armado
            arbol.insertar(id, texto="...", veracidad=True)  # con los datos sueltos
        """
        if isinstance(nodo_o_datos, NodoNoticia):
            nuevo = nodo_o_datos
        else:
            nuevo = NodoNoticia(nodo_o_datos, texto, veracidad)

        if self.raiz is None:
            self.raiz = nuevo
            return nuevo

        actual = self.raiz
        while True:
            if nuevo.id == actual.id:
                # id duplicado: no se inserta de nuevo, se conserva el nodo existente.
                return actual
            elif nuevo.id < actual.id:
                if actual.izquierda is None:
                    actual.izquierda = nuevo
                    return nuevo
                actual = actual.izquierda
            else:
                if actual.derecha is None:
                    actual.derecha = nuevo
                    return nuevo
                actual = actual.derecha

    def buscar(self, id):
        """Búsqueda clásica de ABB por comparación de `id`. O(log n) en árbol balanceado.

        Reutiliza buscar_con_camino y descarta el camino cuando no hace falta.
        """
        nodo, _camino = self.buscar_con_camino(id)
        return nodo

    def buscar_con_camino(self, id):
        """Busca una noticia por `id` y además devuelve el camino recorrido
        desde la raíz hasta el nodo, como lista de strings "izquierda"/"derecha".

        Ese camino es lo que el juego debe replicar en ArbolStats
        (ver ArbolStats.obtener_por_camino) para llegar al paquete de impacto
        isomorfo, en vez de volver a buscar por id en ese árbol.

        Retorna (NodoNoticia | None, list[str]):
            - Si el id existe: (nodo, camino) con camino = [] si el nodo es la raíz.
            - Si el id no existe: (None, camino_parcial) con el camino recorrido
              hasta el punto donde la búsqueda se quedó sin subárbol.
        """
        camino = []
        actual = self.raiz
        while actual is not None:
            if id == actual.id:
                return actual, camino
            elif id < actual.id:
                camino.append("izquierda")
                actual = actual.izquierda
            else:
                camino.append("derecha")
                actual = actual.derecha
        return None, camino

    def recorrido_inorden(self):
        """Devuelve una lista de NodoNoticia en orden ascendente de id (útil para depurar)."""
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
