# Mazo de noticias: selección aleatoria, sin repetición, de las noticias de
# ArbolNoticias. Solo decide qué noticia (nodo + camino) toca mostrar; no conoce
# ArbolStats ni los indicadores.

import random


# Entrega noticias en orden aleatorio; al agotarlas reinicia la ronda.
# ids_disponibles se calcula una vez con recorrido_inorden(); ids_vistos son los
# ya entregados en la ronda actual.
class MazoNoticias:

    def __init__(self, arbol_noticias):
        self.arbol_noticias = arbol_noticias
        self.ids_disponibles = [
            nodo.id for nodo in arbol_noticias.recorrido_inorden()
        ]
        self.ids_vistos = set()

    # True si quedan ids sin ver en la ronda actual.
    def hay_pendientes(self):
        return len(self.ids_vistos) < len(self.ids_disponibles)

    def reiniciar(self):
        self.ids_vistos.clear()

    # Devuelve (NodoNoticia, camino) o None si el árbol está vacío.
    def siguiente(self):
        if not self.ids_disponibles:
            return None

        if not self.hay_pendientes():
            self.reiniciar()

        pendientes = [
            id_ for id_ in self.ids_disponibles if id_ not in self.ids_vistos
        ]
        id_elegido = random.choice(pendientes)

        nodo, camino = self.arbol_noticias.buscar_con_camino(id_elegido)
        self.ids_vistos.add(id_elegido)

        return nodo, camino
