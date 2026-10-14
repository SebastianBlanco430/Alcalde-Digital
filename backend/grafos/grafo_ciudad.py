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

        # DFS iterativo (pila de iteradores): mismo orden que el recursivo, sin
        # límite de recursión en grafos grandes.
        visitados = {origen}
        orden = [origen]
        pila = [iter(self._adyacencia[origen])]

        while pila:
            for vecino in pila[-1]:
                if vecino not in visitados:
                    visitados.add(vecino)
                    orden.append(vecino)
                    pila.append(iter(self._adyacencia[vecino]))
                    break
            else:
                pila.pop()

        return orden

    # BFS con padres; devuelve [origen, ..., destino], [origen] si son el mismo
    # lugar y [] si no hay camino. ValueError si algún lugar no existe.
    def ruta_mas_corta(self, origen, destino):
        for lugar in (origen, destino):
            if lugar not in self._adyacencia:
                raise ValueError(f"Lugar inexistente en el grafo: {lugar!r}")

        padres = {origen: None}
        cola = deque([origen])

        while cola and destino not in padres:
            actual = cola.popleft()
            for vecino in self._adyacencia[actual]:
                if vecino not in padres:
                    padres[vecino] = actual
                    cola.append(vecino)

        if destino not in padres:
            return []

        ruta = []
        lugar = destino
        while lugar is not None:
            ruta.append(lugar)
            lugar = padres[lugar]
        ruta.reverse()
        return ruta

    # --- Utilidades añadidas ---

    # Número de lugars directamente conectados; ValueError si no existe.
    def grado(self, lugar):
        return len(self.vecinos(lugar))

    # {nombre: grado} de todos, en orden de inserción.
    def grados(self):
        return {n: len(v) for n, v in self._adyacencia.items()}

    # Componentes conexas como listas de nombres; la más grande primero (en empate,
    # la que contiene al primero insertado). Cada una en orden BFS.
    def componentes_conexas(self):
        vistos = set()
        componentes = []
        for inicio in self._adyacencia:
            if inicio in vistos:
                continue
            componente = self.recorrido_bfs(inicio)
            vistos.update(componente)
            componentes.append(componente)
        componentes.sort(key=len, reverse=True)  # sort estable
        return componentes

    # El grafo vacío se considera conexo.
    def esta_conectado(self):
        return len(self.componentes_conexas()) <= 1

    # Saltos mínimos entre dos lugars; None si no hay camino. ValueError si no existen.
    def distancia(self, origen, destino):
        ruta = self.ruta_mas_corta(origen, destino)
        return len(ruta) - 1 if ruta else None

    # Puntos de articulación: quitarlos desconecta su componente (Tarjan iterativo).
    def puntos_de_articulacion(self):
        orden, bajo, padre = {}, {}, {}
        criticos = set()
        for raiz in self._adyacencia:
            if raiz in orden:
                continue
            orden[raiz] = bajo[raiz] = len(orden)
            padre[raiz] = None
            hijos_raiz = 0
            pila = [(raiz, iter(self._adyacencia[raiz]))]
            while pila:
                nodo, it = pila[-1]
                for vecino in it:
                    if vecino not in orden:
                        padre[vecino] = nodo
                        orden[vecino] = bajo[vecino] = len(orden)
                        if nodo == raiz:
                            hijos_raiz += 1
                        pila.append((vecino, iter(self._adyacencia[vecino])))
                        break
                    elif vecino != padre[nodo]:
                        bajo[nodo] = min(bajo[nodo], orden[vecino])
                else:
                    pila.pop()
                    if pila:
                        papa = pila[-1][0]
                        bajo[papa] = min(bajo[papa], bajo[nodo])
                        if papa != raiz and bajo[nodo] >= orden[papa]:
                            criticos.add(papa)
            if hijos_raiz > 1:
                criticos.add(raiz)
        return [n for n in self._adyacencia if n in criticos]

    def __repr__(self):
        return f"GrafoCiudad(lugares={self.numero_lugares()}, conexiones={self.numero_conexiones()})"


# Grafo de ejemplo con 7 lugares conexos, coherente con noticias_semilla.py.
def construir_grafo_ciudad_ejemplo():
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
