from backend.arboles.arbol_abb import ArbolABB
from backend.nodos.nodo_noticia import NodoNoticia


class ArbolNoticias(ArbolABB):
    def __init__(self):
        super().__init__()

    def agregar(self, id, noticia, veracidad, rol):
        nuevo_nodo = NodoNoticia(id, noticia, veracidad, rol)

        if self.raiz is None:
            self.raiz = nuevo_nodo
            return

        self.agregar_recursivo(self.raiz, nuevo_nodo)
