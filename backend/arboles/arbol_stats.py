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
