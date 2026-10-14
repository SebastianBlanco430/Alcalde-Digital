# ABB de Impactos (consecuencias), isomorfo a ArbolNoticias.
#
# Cada nodo guarda, para la misma noticia (mismo `id`), dos paquetes de deltas
# sobre convivencia, confianza y desinformación:
#   - deltas_compartir: impacto de la rama izquierda (compartir sin verificar).
#   - deltas_reportar: impacto de la rama derecha (reportar/verificar).
#
# Este árbol se ordena por `gravedad`, no por `id`. Para que tenga la misma forma
# que ArbolNoticias, el orden relativo de gravedad debe coincidir con el de id
# (ver backend/datos/noticias_semilla.py). Por eso el nodo isomorfo no se busca por
# id aquí: se usa ArbolNoticias.buscar_con_camino(id) y se replica el camino con
# obtener_por_camino.


# Nodo del ABB de impactos. `id` solo identifica la noticia; no se usa para ordenar.
class NodoStats:

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


# ABB de impactos, ordenado por `gravedad` ascendente.
class ArbolStats:

    def __init__(self):
        self.raiz = None

    # Acepta un NodoStats ya armado o los datos sueltos (id, gravedad, deltas).
    def insertar(self, nodo_o_id, gravedad=None, deltas_compartir=None, deltas_reportar=None):
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
                # gravedad duplicada: se conserva el nodo existente
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

    # Búsqueda O(n) por id, solo para pruebas/depuración: el árbol no se ordena por id.
    def buscar_por_id(self, id):

        def buscar(nodo):
            if nodo is None:
                return None
            if nodo.id == id:
                return nodo
            encontrado = buscar(nodo.izquierda)
            if encontrado is not None:
                return encontrado
            return buscar(nodo.derecha)

        return buscar(self.raiz)

    # Sigue `camino` (lista de "izquierda"/"derecha" de ArbolNoticias.buscar_con_camino)
    # y devuelve el NodoStats alcanzado. Devuelve None si el camino se corta,
    # lo que indicaría que los árboles no son isomorfos.
    def obtener_por_camino(self, camino):
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

    def contiene_id(self, id):
        return self.buscar_por_id(id) is not None

    # Nodos con desde <= gravedad <= hasta, en orden ascendente (poda el ABB).
    def rango(self, desde, hasta):
        resultado = []
        pila = []
        actual = self.raiz
        while pila or actual is not None:
            while actual is not None:
                pila.append(actual)
                actual = actual.izquierda if actual.gravedad >= desde else None
            actual = pila.pop()
            if actual.gravedad > hasta:
                break
            if actual.gravedad >= desde:
                resultado.append(actual)
            actual = actual.derecha
        return resultado

    # Gravedades repetidas o fuera de orden en el ABB (invariante de ordenación); True si es válido.
    def es_abb_valido(self):
        ids = [n.gravedad for n in self.recorrido_inorden()]
        return all(a < b for a, b in zip(ids, ids[1:]))
