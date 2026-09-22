"""
Grafo de la ciudad: vértices = lugares de Ciudad Nova, aristas = conexiones
(calles/rutas) entre ellos.

No dirigido y sin peso por ahora: solo interesa "se puede ir de un lugar a
otro", no distancias ni costos. Se implementa con lista de adyacencia
(dict[str, list[str]]), que preserva el orden de inserción de cada lugar y
de sus vecinos (relevante para que BFS/DFS den un orden determinista y
fácil de verificar en las pruebas).

Este módulo es base/fundacional para el laboratorio de Estructura de Datos II
(estructura de grafos obligatoria). NO se integra todavía con la jugabilidad
(PantallaJuego, roles de jugador): eso depende de mecánicas que se diseñan en
una entrega posterior.
"""

from collections import deque


class GrafoCiudad:
    """Grafo no dirigido y sin peso de lugares de Ciudad Nova.

    Estructura interna: self._adyacencia es un dict[str, list[str]] donde
    cada clave es un lugar y el valor es la lista de lugares vecinos
    (conexión directa), sin duplicados.
    """

    def __init__(self):
        self._adyacencia = {}

    def agregar_lugar(self, nombre):
        """Agrega un lugar (vértice) al grafo si no existe todavía.

        Si el lugar ya existe, no hace nada (no duplica ni borra sus
        conexiones actuales).
        """
        if nombre not in self._adyacencia:
            self._adyacencia[nombre] = []

    def agregar_conexion(self, lugar_a, lugar_b):
        """Agrega una conexión no dirigida entre lugar_a y lugar_b.

        Si alguno de los dos lugares no existe todavía, se crea
        automáticamente (comodidad al construir el grafo). No se duplica
        la conexión si ya existía. No se permiten auto-conexiones
        (lugar_a == lugar_b se ignora).
        """
        if lugar_a == lugar_b:
            return

        self.agregar_lugar(lugar_a)
        self.agregar_lugar(lugar_b)

        if lugar_b not in self._adyacencia[lugar_a]:
            self._adyacencia[lugar_a].append(lugar_b)
        if lugar_a not in self._adyacencia[lugar_b]:
            self._adyacencia[lugar_b].append(lugar_a)

    def vecinos(self, lugar):
        """Devuelve la lista de lugares directamente conectados a `lugar`.

        Lanza ValueError si `lugar` no existe en el grafo.
        """
        if lugar not in self._adyacencia:
            raise ValueError(f"Lugar inexistente en el grafo: {lugar!r}")
        return list(self._adyacencia[lugar])

    def existe_conexion(self, lugar_a, lugar_b):
        """True si hay una conexión directa entre lugar_a y lugar_b.

        Si alguno de los dos lugares no existe en el grafo, devuelve False
        en lugar de lanzar una excepción (consulta segura).
        """
        if lugar_a not in self._adyacencia or lugar_b not in self._adyacencia:
            return False
        return lugar_b in self._adyacencia[lugar_a]

    def lugares(self):
        """Devuelve la lista de todos los lugares (vértices) del grafo."""
        return list(self._adyacencia.keys())

    def numero_lugares(self):
        return len(self._adyacencia)

    def numero_conexiones(self):
        """Número de aristas (conexiones no dirigidas) del grafo."""
        total_grados = sum(len(vecinos) for vecinos in self._adyacencia.values())
        return total_grados // 2

    def recorrido_bfs(self, origen):
        """Recorrido en anchura (BFS) desde `origen`.

        Devuelve la lista de lugares en el orden en que fueron visitados.
        Lanza ValueError si `origen` no existe en el grafo.
        """
        if origen not in self._adyacencia:
            raise ValueError(f"Lugar inexistente en el grafo: {origen!r}")

        visitados = {origen}
        orden = [origen]
        cola = deque([origen])

        while cola:
            actual = cola.popleft()
            for vecino in self._adyacencia[actual]:
                if vecino not in visitados:
                    visitados.add(vecino)
                    orden.append(vecino)
                    cola.append(vecino)

        return orden

    def recorrido_dfs(self, origen):
        """Recorrido en profundidad (DFS) desde `origen`.

        Devuelve la lista de lugares en el orden en que fueron visitados,
        siguiendo el orden de la lista de vecinos de cada lugar. Lanza
        ValueError si `origen` no existe en el grafo.
        """
        if origen not in self._adyacencia:
            raise ValueError(f"Lugar inexistente en el grafo: {origen!r}")

        visitados = set()
        orden = []

        def _visitar(lugar):
            visitados.add(lugar)
            orden.append(lugar)
            for vecino in self._adyacencia[lugar]:
                if vecino not in visitados:
                    _visitar(vecino)

        _visitar(origen)
        return orden

    def __repr__(self):
        return f"GrafoCiudad(lugares={self.numero_lugares()}, conexiones={self.numero_conexiones()})"


def construir_grafo_ciudad_demo():
    """Construye un GrafoCiudad de ejemplo con 7 lugares de Ciudad Nova,
    coherentes con las noticias de backend/datos/noticias_seed.py (Alcaldía,
    Universidad, Hospital y Barrio Las Flores, rutas de buses). El grafo
    queda conexo: no hay lugares aislados.

    Lugares y conexiones (no dirigidas):
        Alcaldía          -- Plaza Central
        Plaza Central     -- Universidad de Ciudad Nova
        Plaza Central     -- Terminal de Buses
        Terminal de Buses -- Barrio Las Flores
        Barrio Las Flores -- Hospital Las Flores
        Barrio Las Flores -- Parque Municipal
        Universidad de Ciudad Nova -- Parque Municipal
    """
    grafo = GrafoCiudad()

    for lugar in (
        "Alcaldía",
        "Plaza Central",
        "Universidad de Ciudad Nova",
        "Hospital Las Flores",
        "Barrio Las Flores",
        "Parque Municipal",
        "Terminal de Buses",
    ):
        grafo.agregar_lugar(lugar)

    grafo.agregar_conexion("Alcaldía", "Plaza Central")
    grafo.agregar_conexion("Plaza Central", "Universidad de Ciudad Nova")
    grafo.agregar_conexion("Plaza Central", "Terminal de Buses")
    grafo.agregar_conexion("Terminal de Buses", "Barrio Las Flores")
    grafo.agregar_conexion("Barrio Las Flores", "Hospital Las Flores")
    grafo.agregar_conexion("Barrio Las Flores", "Parque Municipal")
    grafo.agregar_conexion("Universidad de Ciudad Nova", "Parque Municipal")

    return grafo


if __name__ == "__main__":
    grafo = construir_grafo_ciudad_demo()

    print("=== Construcción de GrafoCiudad (demo) ===")
    print(grafo)
    print(f"Lugares ({grafo.numero_lugares()}): {grafo.lugares()}")
    print(f"Número de conexiones: {grafo.numero_conexiones()}")

    print("\n=== Vecinos de cada lugar ===")
    for lugar in grafo.lugares():
        print(f"  {lugar}: {grafo.vecinos(lugar)}")

    print("\n=== existe_conexion ===")
    print("Alcaldía -- Plaza Central:", grafo.existe_conexion("Alcaldía", "Plaza Central"))
    print("Alcaldía -- Hospital Las Flores:", grafo.existe_conexion("Alcaldía", "Hospital Las Flores"))
    print("Lugar inexistente:", grafo.existe_conexion("Alcaldía", "Zona Fantasma"))

    print("\n=== Recorrido BFS desde 'Alcaldía' ===")
    orden_bfs = grafo.recorrido_bfs("Alcaldía")
    print(orden_bfs)
    assert len(orden_bfs) == grafo.numero_lugares(), "BFS debe alcanzar todos los lugares (grafo conexo)"

    print("\n=== Recorrido DFS desde 'Alcaldía' ===")
    orden_dfs = grafo.recorrido_dfs("Alcaldía")
    print(orden_dfs)
    assert len(orden_dfs) == grafo.numero_lugares(), "DFS debe alcanzar todos los lugares (grafo conexo)"

    print("\n=== Recorridos desde otro origen: 'Hospital Las Flores' ===")
    print("BFS:", grafo.recorrido_bfs("Hospital Las Flores"))
    print("DFS:", grafo.recorrido_dfs("Hospital Las Flores"))

    print("\n=== Caso borde: origen inexistente ===")
    try:
        grafo.recorrido_bfs("Zona Fantasma")
    except ValueError as e:
        print(f"OK, lanzó ValueError: {e}")

    print("\nTodas las pruebas de GrafoCiudad pasaron.")
