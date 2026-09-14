from backend.nodos.nodo import Nodo


class NodoStats(Nodo):
    def __init__(self, id, lista_izq, lista_der):
        super().__init__(id)
        self.lista_izq = lista_izq
        self.lista_der = lista_der
