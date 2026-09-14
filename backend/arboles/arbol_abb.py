class ArbolABB:
    def __init__(self):
        self.raiz = None

    def buscar(self, nodo, id):
        if nodo is None:
            return None

        if nodo.id == id:
            return nodo

        if id < nodo.id:
            return self.buscar(nodo.izquierdo, id)
        else:
            return self.buscar(nodo.derecho, id)

    def agregar_recursivo(self, nodo, nuevo_nodo):
        if nuevo_nodo.id < nodo.id:
            if nodo.izquierdo is None:
                nodo.izquierdo = nuevo_nodo
            else:
                self.agregar_recursivo(nodo.izquierdo, nuevo_nodo)

        else:
            if nodo.derecho is None:
                nodo.derecho = nuevo_nodo
            else:
                self.agregar_recursivo(nodo.derecho, nuevo_nodo)

    def encontrar_minimo(self, nodo):
        while nodo.izquierdo is not None:
            nodo = nodo.izquierdo

        return nodo

    def eliminar(self, id):
        self.raiz = self.eliminar_recursivo(self.raiz, id)

    def eliminar_recursivo(self, nodo, id):
        if nodo is None:
            return None

        if id < nodo.id:
            nodo.izquierdo = self.eliminar_recursivo(nodo.izquierdo, id)
        elif id > nodo.id:
            nodo.derecho = self.eliminar_recursivo(nodo.derecho, id)
        else:
            if nodo.izquierdo is None:
                return nodo.derecho
            elif nodo.derecho is None:
                return nodo.izquierdo

            temp = self.encontrar_minimo(nodo.derecho)

            nodo.id = temp.id

            nodo.derecho = self.eliminar_recursivo(nodo.derecho, temp.id)

        return nodo
