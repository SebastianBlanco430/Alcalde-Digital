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

    # Igual que propagar_publicacion pero agrupado: devuelve [nivel_1, nivel_2, ...] con los
    # ciudadanos alcanzados exactamente en cada salto (una sola pasada BFS). La concatenación
    # de los niveles equivale a propagar_publicacion(origen, saltos_maximos).
    def propagar_por_saltos(self, origen, saltos_maximos=None):
        if origen not in self._adyacencia:
            raise ValueError(f"Ciudadano inexistente en el grafo: {origen!r}")
        if saltos_maximos is not None and saltos_maximos < 0:
            raise ValueError("saltos_maximos no puede ser negativo")

        visitados = {origen}
        niveles = []
        frontera = [origen]
        while frontera and (saltos_maximos is None or len(niveles) < saltos_maximos):
            nivel = []
            for actual in frontera:
                for vecino in self._adyacencia[actual]:
                    if vecino not in visitados:
                        visitados.add(vecino)
                        nivel.append(vecino)
            if nivel:
                niveles.append(nivel)
            frontera = nivel
        return niveles

    # --- Utilidades añadidas ---

    # Número de ciudadanos directamente conectados; ValueError si no existe.
    def grado(self, ciudadano):
        return len(self.vecinos(ciudadano))

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
            componente = [inicio] + self.propagar_publicacion(inicio)
            vistos.update(componente)
            componentes.append(componente)
        componentes.sort(key=len, reverse=True)  # sort estable
        return componentes

    # El grafo vacío se considera conexo.
    def esta_conectado(self):
        return len(self.componentes_conexas()) <= 1

    # Saltos mínimos entre dos ciudadanos; None si no hay camino. ValueError si no existen.
    def distancia(self, origen, destino):
        ruta = self.camino_mas_corto(origen, destino)
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

    # BFS con padres; [origen, ..., destino], [origen] si son el mismo y [] si no hay
    # camino. ValueError si algún ciudadano no existe.
    def camino_mas_corto(self, origen, destino):
        for ciudadano in (origen, destino):
            if ciudadano not in self._adyacencia:
                raise ValueError(f"Ciudadano inexistente en el grafo: {ciudadano!r}")

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
        nodo = destino
        while nodo is not None:
            ruta.append(nodo)
            nodo = padres[nodo]
        ruta.reverse()
        return ruta

    # Centralidad de cercanía (normalizada por la componente, 0 si está aislado):
    # (alcanzables) / (suma de saltos). Mayor = difunde más rápido.
    def centralidad_cercania(self, ciudadano):
        if ciudadano not in self._adyacencia:
            raise ValueError(f"Ciudadano inexistente en el grafo: {ciudadano!r}")
        distancias = {ciudadano: 0}
        cola = deque([ciudadano])
        while cola:
            actual = cola.popleft()
            for vecino in self._adyacencia[actual]:
                if vecino not in distancias:
                    distancias[vecino] = distancias[actual] + 1
                    cola.append(vecino)
        total = sum(distancias.values())
        return (len(distancias) - 1) / total if total else 0.0

    # Los `n` ciudadanos más influyentes: mayor grado, desempate por cercanía y luego
    # por orden de inserción. Devuelve [(ciudadano, grado)]. `n=None` = todos.
    def ciudadanos_influyentes(self, n=3):
        if n is not None and n < 0:
            raise ValueError("n no puede ser negativo")
        orden = {c: i for i, c in enumerate(self._adyacencia)}
        ranking = sorted(
            self._adyacencia,
            key=lambda c: (-len(self._adyacencia[c]), -self.centralidad_cercania(c), orden[c]),
        )
        if n is not None:
            ranking = ranking[:n]
        return [(c, len(self._adyacencia[c])) for c in ranking]

    # Comunidades aisladas: componentes conexas que NO contienen al `origen` (una
    # publicación desde `origen` jamás las alcanza). Sin `origen`, todas salvo la mayor.
    def comunidades_aisladas(self, origen=None):
        componentes = self.componentes_conexas()
        if origen is None:
            return componentes[1:]
        if origen not in self._adyacencia:
            raise ValueError(f"Ciudadano inexistente en el grafo: {origen!r}")
        return [c for c in componentes if origen not in c]

    # Ciudadanos que ninguna publicación alcanzaría desde `origen` (unión de las
    # comunidades aisladas).
    def inalcanzables_desde(self, origen):
        return [c for comunidad in self.comunidades_aisladas(origen) for c in comunidad]

    def __repr__(self):
        return f"GrafoSocial(ciudadanos={self.numero_ciudadanos()}, relaciones={self.numero_relaciones()})"


# Relación Luana-Nayara: une la comunidad del Morro con la red de Ana, así los cuatro ciudadanos de rol quedan en la
# misma componente. False = sin el puente (el Morro queda aparte).
PUENTE_MORRO = True


# Grafo de ejemplo con 17 ciudadanos de Ciudad Nova (iniciales distintas, de la A a la Q: cada nodo se
# dibuja con su inicial) en dos componentes:
#   - la red de la ciudad (16): Ana muy conectada (4 relaciones), un ciclo Ana-Elena-Hugo-Ivan-Fábio, cadenas hacia
#     Luana y Kauã, y la comunidad del Morro (Marcos con 3 relaciones, un triángulo con Nayara y Otávio, Paula como
#     paso hacia Quitéria) unida a la red de Ana por el puente Luana-Nayara; puntos de articulación Ana, Beto,
#     Carlos, Gina, Júlia, Luana, Marcos, Nayara y Paula;
#   - Diana, aislada (caso borde).
# Los 10 primeros son los de siempre (solo cambia la grafía: Fábio, Ivan, Júlia); los 7 últimos, de 2026-10.
def construir_grafo_social_ejemplo():
    grafo = GrafoSocial()

    for ciudadano in (
        "Ana",
        "Beto",
        "Carlos",
        "Diana",
        "Elena",
        "Fábio",
        "Gina",
        "Hugo",
        "Ivan",
        "Júlia",
        "Kauã",
        "Luana",
        "Marcos",
        "Nayara",
        "Otávio",
        "Paula",
        "Quitéria",
    ):
        grafo.agregar_ciudadano(ciudadano)

    grafo.agregar_relacion("Ana", "Beto")
    grafo.agregar_relacion("Ana", "Elena")
    grafo.agregar_relacion("Ana", "Fábio")
    grafo.agregar_relacion("Ana", "Gina")
    grafo.agregar_relacion("Beto", "Carlos")
    grafo.agregar_relacion("Elena", "Hugo")
    grafo.agregar_relacion("Fábio", "Ivan")
    grafo.agregar_relacion("Gina", "Júlia")
    grafo.agregar_relacion("Hugo", "Ivan")
    grafo.agregar_relacion("Júlia", "Kauã")
    grafo.agregar_relacion("Carlos", "Luana")
    grafo.agregar_relacion("Marcos", "Nayara")
    grafo.agregar_relacion("Marcos", "Otávio")
    grafo.agregar_relacion("Nayara", "Otávio")
    grafo.agregar_relacion("Marcos", "Paula")
    grafo.agregar_relacion("Paula", "Quitéria")
    if PUENTE_MORRO:
        grafo.agregar_relacion("Luana", "Nayara")

    return grafo
