from backend.arboles.arbol_abb import ArbolABB
from backend.nodos.nodo_stats import NodoStats


class ArbolStats(ArbolABB):

    def __init__(self):
        super().__init__()

    def agregar(self, id, lista_izq, lista_der):
        nuevo_nodo = NodoStats(id, lista_izq, lista_der)

        if self.raiz is None:
            self.raiz = nuevo_nodo
            return

        self.agregar_recursivo(self.raiz, nuevo_nodo)
