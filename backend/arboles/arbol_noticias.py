# Árbol Genérico Narrativo: catálogo de noticias de Civitas.
# Es un ABB ordenado por `id`, isomorfo a ArbolStats: ambos se construyen
# insertando los mismos ids en el mismo orden.


# Nodo del ABB de noticias (id, texto, veracidad y subárboles izquierda/derecha).
class NodoNoticia:

    def __init__(self, id, texto, veracidad):
        self.id = id
        self.texto = texto
        self.veracidad = veracidad
        self.izquierda = None
        self.derecha = None

    def __repr__(self):
        etiqueta_veracidad = "verdadera" if self.veracidad else "falsa"
        return f"NodoNoticia(id={self.id}, veracidad={etiqueta_veracidad}, texto={self.texto!r})"


# ABB de noticias, ordenado por `id` ascendente.
class ArbolNoticias:

    def __init__(self):
        self.raiz = None

    # Acepta un NodoNoticia ya armado o los datos sueltos (id, texto, veracidad).
    def insertar(self, nodo_o_datos, texto=None, veracidad=None):
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
                # id duplicado: se conserva el nodo existente
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

    # Búsqueda por id, sin el camino.
    def buscar(self, id):
        nodo, _camino = self.buscar_con_camino(id)
        return nodo

    # Devuelve (nodo, camino) con el camino como lista de "izquierda"/"derecha".
    # Ese camino se replica en ArbolStats con obtener_por_camino.
    # Si el id no existe, devuelve (None, camino_parcial).
    def buscar_con_camino(self, id):
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
        resultado = []

        def visitar(nodo):
            if nodo is None:
                return
            visitar(nodo.izquierda)
            resultado.append(nodo)
            visitar(nodo.derecha)

        visitar(self.raiz)
        return resultado

    def recorrido_preorden(self):
        resultado = []

        def visitar(nodo):
            if nodo is None:
                return
            resultado.append(nodo)
            visitar(nodo.izquierda)
            visitar(nodo.derecha)

        visitar(self.raiz)
        return resultado

    def recorrido_postorden(self):
        resultado = []

        def visitar(nodo):
            if nodo is None:
                return
            visitar(nodo.izquierda)
            visitar(nodo.derecha)
            resultado.append(nodo)

        visitar(self.raiz)
        return resultado
