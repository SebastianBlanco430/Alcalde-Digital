# Grafo de la ciudad: vértices = lugares de Ciudad Nova, aristas = conexiones.
# No dirigido y sin peso, con lista de adyacencia (dict[str, list[str]]) que
# conserva el orden de inserción, así BFS/DFS son deterministas.

from collections import deque


class GrafoCiudad:

    def __init__(self):
        self._adyacencia = {}

    # No hace nada si el lugar ya existe.
    def agregar_lugar(self, nombre):
        if nombre not in self._adyacencia:
            self._adyacencia[nombre] = []

    # Crea los lugares que falten, no duplica conexiones e ignora auto-conexiones.
    def agregar_conexion(self, lugar_a, lugar_b):
        if lugar_a == lugar_b:
            return

        self.agregar_lugar(lugar_a)
        self.agregar_lugar(lugar_b)

        if lugar_b not in self._adyacencia[lugar_a]:
            self._adyacencia[lugar_a].append(lugar_b)
        if lugar_a not in self._adyacencia[lugar_b]:
            self._adyacencia[lugar_b].append(lugar_a)

    # Lanza ValueError si el lugar no existe.
    def vecinos(self, lugar):
        if lugar not in self._adyacencia:
            raise ValueError(f"Lugar inexistente en el grafo: {lugar!r}")
        return list(self._adyacencia[lugar])

    # Consulta segura: False si algún lugar no existe.
    def existe_conexion(self, lugar_a, lugar_b):
        if lugar_a not in self._adyacencia or lugar_b not in self._adyacencia:
            return False
        return lugar_b in self._adyacencia[lugar_a]

    def lugares(self):
        return list(self._adyacencia.keys())

    def numero_lugares(self):
        return len(self._adyacencia)

    def numero_conexiones(self):
        total_grados = sum(len(vecinos) for vecinos in self._adyacencia.values())
        return total_grados // 2

    # Recorrido en anchura; lanza ValueError si `origen` no existe.
    def recorrido_bfs(self, origen):
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

    # Recorrido en profundidad; lanza ValueError si `origen` no existe.
    def recorrido_dfs(self, origen):
        if origen not in self._adyacencia:
            raise ValueError(f"Lugar inexistente en el grafo: {origen!r}")

        visitados = set()
        orden = []

        def visitar(lugar):
            visitados.add(lugar)
            orden.append(lugar)
            for vecino in self._adyacencia[lugar]:
                if vecino not in visitados:
                    visitar(vecino)

        visitar(origen)
        return orden

    def __repr__(self):
        return f"GrafoCiudad(lugares={self.numero_lugares()}, conexiones={self.numero_conexiones()})"


# Grafo de ejemplo con 7 lugares conexos, coherente con noticias_seed.py.
def construir_grafo_ciudad_demo():
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
