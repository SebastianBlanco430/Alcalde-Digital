"""
Mazo de noticias: selección aleatoria, sin repetición, de noticias disponibles
en ArbolNoticias.

MazoNoticias no conoce nada de ArbolStats, deltas ni indicadores globales:
solo decide QUÉ noticia (id + camino desde la raíz de ArbolNoticias) toca
mostrar a continuación. El módulo que aplique impactos consumirá el `camino`
devuelto aquí junto con ArbolStats.obtener_por_camino (ver arbol_stats.py).
"""

import random


class MazoNoticias:
    """Entrega noticias de ArbolNoticias en orden aleatorio sin repetición.

    Atributos:
        arbol_noticias (ArbolNoticias): árbol fuente de noticias.
        ids_disponibles (list[int]): todos los ids del árbol, calculados una
            vez en el constructor a partir de recorrido_inorden().
        ids_vistos (set[int]): ids ya entregados por siguiente() en la ronda
            actual. Se reinicia automáticamente cuando se agotan todos.
    """

    def __init__(self, arbol_noticias):
        self.arbol_noticias = arbol_noticias
        self.ids_disponibles = [
            nodo.id for nodo in arbol_noticias.recorrido_inorden()
        ]
        self.ids_vistos = set()

    def hay_pendientes(self):
        """True si quedan ids sin ver en la ronda actual (antes de reinicio automático)."""
        return len(self.ids_vistos) < len(self.ids_disponibles)

    def reiniciar(self):
        """Vacía manualmente la lista de vistos, reiniciando el catálogo."""
        self.ids_vistos.clear()

    def siguiente(self):
        """Elige aleatoriamente un id no visto, busca su nodo y camino, y lo
        marca como visto. Si ya se vieron todos, reinicia la ronda antes de
        elegir.

        Retorna (NodoNoticia, list[str]) o None si el árbol está vacío.
        """
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
