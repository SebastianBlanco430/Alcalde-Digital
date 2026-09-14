class NodoNoticia(Nodo):
    def __init__(self, id, noticia, veracidad, rol):
        super().__init__(id)
        self.noticia = noticia
        self.veracidad = veracidad
        self.rol = rol