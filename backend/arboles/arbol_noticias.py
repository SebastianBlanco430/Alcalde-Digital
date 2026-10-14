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
        pila = []
        actual = self.raiz
        while pila or actual is not None:
            while actual is not None:
                pila.append(actual)
                actual = actual.izquierda
            actual = pila.pop()
            resultado.append(actual)
            actual = actual.derecha
        return resultado

    def recorrido_preorden(self):
        resultado = []
        pila = [self.raiz] if self.raiz is not None else []
        while pila:
            nodo = pila.pop()
            resultado.append(nodo)
            if nodo.derecha is not None:
                pila.append(nodo.derecha)
            if nodo.izquierda is not None:
                pila.append(nodo.izquierda)
        return resultado

    def recorrido_postorden(self):
        # preorden espejo (raíz, derecha, izquierda) invertido
        resultado = []
        pila = [self.raiz] if self.raiz is not None else []
        while pila:
            nodo = pila.pop()
            resultado.append(nodo)
            if nodo.izquierda is not None:
                pila.append(nodo.izquierda)
            if nodo.derecha is not None:
                pila.append(nodo.derecha)
        resultado.reverse()
        return resultado

    # --- Utilidades añadidas (iterativas: no fallan con árboles degenerados) ---

    def esta_vacio(self):
        return self.raiz is None

    def tamano(self):
        return len(self.recorrido_por_niveles())

    # Altura en nodos: 0 si está vacío, 1 con solo la raíz.
    def altura(self):
        return len(self.nodos_por_nivel())

    # Lista de listas: nodos de cada nivel (raíz = nivel 0), de izquierda a derecha.
    def nodos_por_nivel(self):
        niveles = []
        nivel = [self.raiz] if self.raiz is not None else []
        while nivel:
            niveles.append(nivel)
            siguiente = []
            for nodo in nivel:
                if nodo.izquierda is not None:
                    siguiente.append(nodo.izquierda)
                if nodo.derecha is not None:
                    siguiente.append(nodo.derecha)
            nivel = siguiente
        return niveles

    # Recorrido en anchura (BFS), nivel por nivel.
    def recorrido_por_niveles(self):
        return [nodo for nivel in self.nodos_por_nivel() for nodo in nivel]

    # Menor/mayor nodo según la clave de orden del árbol; None si está vacío.
    def minimo(self):
        actual = self.raiz
        while actual is not None and actual.izquierda is not None:
            actual = actual.izquierda
        return actual

    def maximo(self):
        actual = self.raiz
        while actual is not None and actual.derecha is not None:
            actual = actual.derecha
        return actual

    # Forma del árbol como tupla anidada (izquierda, derecha) o None; sirve para
    # comparar isomorfismo sin mirar los datos de los nodos.
    def forma(self):
        if self.raiz is None:
            return None
        formas = {}
        pila = [(self.raiz, False)]
        while pila:
            nodo, listo = pila.pop()
            if listo:
                formas[id(nodo)] = (
                    formas.get(id(nodo.izquierda)),
                    formas.get(id(nodo.derecha)),
                )
            else:
                pila.append((nodo, True))
                for hijo in (nodo.derecha, nodo.izquierda):
                    if hijo is not None:
                        pila.append((hijo, False))
        return formas[id(self.raiz)]

    def contiene(self, id):
        return self.buscar(id) is not None

    # Profundidad de un nodo (raíz = 0); None si el id no existe.
    def profundidad(self, id):
        nodo, camino = self.buscar_con_camino(id)
        return len(camino) if nodo is not None else None

    # Noticias con desde <= id <= hasta, en orden ascendente (poda el ABB).
    def rango(self, desde, hasta):
        resultado = []
        pila = []
        actual = self.raiz
        while pila or actual is not None:
            while actual is not None:
                pila.append(actual)
                actual = actual.izquierda if actual.id >= desde else None
            actual = pila.pop()
            if actual.id > hasta:
                break
            if actual.id >= desde:
                resultado.append(actual)
            actual = actual.derecha
        return resultado

    # Ids repetidos o fuera de orden en el ABB (invariante de ordenación); True si es válido.
    def es_abb_valido(self):
        ids = [n.id for n in self.recorrido_inorden()]
        return all(a < b for a, b in zip(ids, ids[1:]))
