# Grafo social: vértices = ciudadanos, aristas = relaciones en la red "Civitas".
# No dirigido y sin peso, con lista de adyacencia (igual que GrafoCiudad).
# La propagación de una publicación es un BFS por saltos desde un ciudadano origen;
# este módulo solo calcula el alcance, no decide veracidad ni roles.

from collections import deque


class GrafoSocial:

    def __init__(self):
        self._adyacencia = {}

    # No hace nada si el ciudadano ya existe.
    def agregar_ciudadano(self, nombre):
        if nombre not in self._adyacencia:
            self._adyacencia[nombre] = []

    # Crea los ciudadanos que falten, no duplica relaciones e ignora auto-relaciones.
    def agregar_relacion(self, ciudadano_a, ciudadano_b):
        if ciudadano_a == ciudadano_b:
            return

        self.agregar_ciudadano(ciudadano_a)
        self.agregar_ciudadano(ciudadano_b)

        if ciudadano_b not in self._adyacencia[ciudadano_a]:
            self._adyacencia[ciudadano_a].append(ciudadano_b)
        if ciudadano_a not in self._adyacencia[ciudadano_b]:
            self._adyacencia[ciudadano_b].append(ciudadano_a)

    # Lanza ValueError si el ciudadano no existe.
    def vecinos(self, ciudadano):
        if ciudadano not in self._adyacencia:
            raise ValueError(f"Ciudadano inexistente en el grafo: {ciudadano!r}")
        return list(self._adyacencia[ciudadano])

    # Consulta segura: False si algún ciudadano no existe.
    def existe_relacion(self, ciudadano_a, ciudadano_b):
        if ciudadano_a not in self._adyacencia or ciudadano_b not in self._adyacencia:
            return False
        return ciudadano_b in self._adyacencia[ciudadano_a]

    def ciudadanos(self):
        return list(self._adyacencia.keys())

    def numero_ciudadanos(self):
        return len(self._adyacencia)

    def numero_relaciones(self):
        total_grados = sum(len(vecinos) for vecinos in self._adyacencia.values())
        return total_grados // 2

    # BFS por saltos desde `origen`: salto 1 = contactos directos, salto 2 = sus
    # contactos, etc. Con `saltos_maximos=None` llega a toda la componente conexa.
    # Devuelve los alcanzados (sin `origen`) agrupados por salto.
    # Lanza ValueError si `origen` no existe o `saltos_maximos` es negativo.
    def propagar_publicacion(self, origen, saltos_maximos=None):
        if origen not in self._adyacencia:
            raise ValueError(f"Ciudadano inexistente en el grafo: {origen!r}")
        if saltos_maximos is not None and saltos_maximos < 0:
            raise ValueError("saltos_maximos no puede ser negativo")

        visitados = {origen}
        alcanzados = []
        # cada elemento de la cola es (ciudadano, salto_en_que_fue_alcanzado)
        cola = deque([(origen, 0)])

        while cola:
            actual, salto_actual = cola.popleft()

            if saltos_maximos is not None and salto_actual >= saltos_maximos:
                continue

            for vecino in self._adyacencia[actual]:
                if vecino not in visitados:
                    visitados.add(vecino)
                    alcanzados.append(vecino)
                    cola.append((vecino, salto_actual + 1))

        return alcanzados

    def __repr__(self):
        return f"GrafoSocial(ciudadanos={self.numero_ciudadanos()}, relaciones={self.numero_relaciones()})"


# Grafo de ejemplo con 10 ciudadanos: Ana muy conectada, Carlos con una sola
# relación y Diana aislada (caso borde).
def construir_grafo_social_ejemplo():
    grafo = GrafoSocial()

    for ciudadano in (
        "Ana",
        "Beto",
        "Carlos",
        "Diana",
        "Elena",
        "Fabio",
        "Gina",
        "Hugo",
        "Iván",
        "Julia",
    ):
        grafo.agregar_ciudadano(ciudadano)

    grafo.agregar_relacion("Ana", "Beto")
    grafo.agregar_relacion("Ana", "Elena")
    grafo.agregar_relacion("Ana", "Fabio")
    grafo.agregar_relacion("Ana", "Gina")
    grafo.agregar_relacion("Beto", "Carlos")
    grafo.agregar_relacion("Elena", "Hugo")
    grafo.agregar_relacion("Fabio", "Iván")
    grafo.agregar_relacion("Gina", "Julia")
    grafo.agregar_relacion("Hugo", "Iván")

    return grafo
