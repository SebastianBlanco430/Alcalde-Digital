"""
Grafo social: vértices = ciudadanos de Ciudad Nova, aristas = relaciones
(amistad/confianza/seguimiento) en la red social ficticia "Civitas".

No dirigido y sin peso por ahora: una relación conecta a dos ciudadanos por
igual, no hay distinción de fuerza de la relación todavía. Se implementa con
lista de adyacencia (dict[str, list[str]]), igual que GrafoCiudad.

La propagación de una publicación se modela como un BFS por niveles (saltos)
desde un ciudadano origen: en el salto 1 se alcanza a sus contactos directos,
en el salto 2 a los contactos de esos contactos, etc. Este módulo NO decide
si una publicación es verdadera o falsa ni sus consecuencias (eso es de
ArbolNoticias/ArbolStats, en backend/arboles/) ni diferencia roles de
jugador (ciudadano/periodista/influencer/candidato, de una entrega
posterior): aquí solo se calcula el alcance (qué ciudadanos recibirían la
publicación) dado un origen y, opcionalmente, un límite de saltos.

Este módulo es base/fundacional para el laboratorio de Estructura de Datos II
(estructura de grafos obligatoria). NO se integra todavía con la jugabilidad
(PantallaJuego).
"""

from collections import deque


class GrafoSocial:
    """Grafo no dirigido y sin peso de ciudadanos de Ciudad Nova.

    Estructura interna: self._adyacencia es un dict[str, list[str]] donde
    cada clave es un ciudadano y el valor es la lista de ciudadanos con
    relación directa (amistad/confianza/seguimiento), sin duplicados.
    """

    def __init__(self):
        self._adyacencia = {}

    def agregar_ciudadano(self, nombre):
        """Agrega un ciudadano (vértice) al grafo si no existe todavía.

        Si el ciudadano ya existe, no hace nada (no duplica ni borra sus
        relaciones actuales).
        """
        if nombre not in self._adyacencia:
            self._adyacencia[nombre] = []

    def agregar_relacion(self, ciudadano_a, ciudadano_b):
        """Agrega una relación no dirigida entre ciudadano_a y ciudadano_b.

        Si alguno de los dos ciudadanos no existe todavía, se crea
        automáticamente (comodidad al construir el grafo). No se duplica la
        relación si ya existía. No se permiten auto-relaciones
        (ciudadano_a == ciudadano_b se ignora).
        """
        if ciudadano_a == ciudadano_b:
            return

        self.agregar_ciudadano(ciudadano_a)
        self.agregar_ciudadano(ciudadano_b)

        if ciudadano_b not in self._adyacencia[ciudadano_a]:
            self._adyacencia[ciudadano_a].append(ciudadano_b)
        if ciudadano_a not in self._adyacencia[ciudadano_b]:
            self._adyacencia[ciudadano_b].append(ciudadano_a)

    def vecinos(self, ciudadano):
        """Devuelve la lista de ciudadanos con relación directa a `ciudadano`.

        Lanza ValueError si `ciudadano` no existe en el grafo.
        """
        if ciudadano not in self._adyacencia:
            raise ValueError(f"Ciudadano inexistente en el grafo: {ciudadano!r}")
        return list(self._adyacencia[ciudadano])

    def existe_relacion(self, ciudadano_a, ciudadano_b):
        """True si hay una relación directa entre ciudadano_a y ciudadano_b.

        Si alguno de los dos ciudadanos no existe en el grafo, devuelve
        False en lugar de lanzar una excepción (consulta segura).
        """
        if ciudadano_a not in self._adyacencia or ciudadano_b not in self._adyacencia:
            return False
        return ciudadano_b in self._adyacencia[ciudadano_a]

    def ciudadanos(self):
        """Devuelve la lista de todos los ciudadanos (vértices) del grafo."""
        return list(self._adyacencia.keys())

    def numero_ciudadanos(self):
        return len(self._adyacencia)

    def numero_relaciones(self):
        """Número de aristas (relaciones no dirigidas) del grafo."""
        total_grados = sum(len(vecinos) for vecinos in self._adyacencia.values())
        return total_grados // 2

    def propagar_publicacion(self, origen, saltos_maximos=None):
        """Simula el alcance de una publicación compartida por `origen`,
        usando BFS por niveles (saltos) sobre la red de relaciones.

        - Salto 1: contactos directos de `origen`.
        - Salto 2: contactos de esos contactos (que no hayan sido alcanzados
          ya), y así sucesivamente.
        - Si `saltos_maximos` es None, la propagación continúa hasta agotar
          la componente conexa de `origen` (alcanza a todo el que esté
          conectado, sin importar la distancia).
        - Si `saltos_maximos` es un entero, la propagación se detiene al
          completar esa cantidad de saltos desde el origen (los ciudadanos
          más lejanos que eso no se alcanzan). Sirve, en una entrega futura,
          para diferenciar el alcance de un ciudadano normal (pocos saltos)
          de un influencer (más saltos o mayor grado); esa diferenciación de
          roles NO se implementa en este módulo.

        Devuelve la lista de ciudadanos alcanzados (SIN incluir a `origen`),
        en el orden en que fueron alcanzados por BFS (es decir, agrupados
        por salto: primero todos los del salto 1, luego todos los del
        salto 2, etc.).

        Lanza ValueError si `origen` no existe en el grafo, o si
        `saltos_maximos` es un número negativo.
        """
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


def construir_grafo_social_demo():
    """Construye un GrafoSocial de ejemplo con 10 ciudadanos de Ciudad Nova.

    Forma una componente conexa grande (8 ciudadanos) con Ana como nodo muy
    conectado (para demostrar alcance amplio de propagación) y Carlos con
    una sola relación (para demostrar alcance limitado). Diana queda
    completamente aislada (sin relaciones) como caso borde.

    Ciudadanos: Ana, Beto, Carlos, Diana, Elena, Fabio, Gina, Hugo, Iván, Julia.

    Relaciones (no dirigidas):
        Ana   -- Beto
        Ana   -- Elena
        Ana   -- Fabio
        Ana   -- Gina
        Beto  -- Carlos
        Elena -- Hugo
        Fabio -- Iván
        Gina  -- Julia
        Hugo  -- Iván
    (Diana no tiene ninguna relación: ciudadano aislado.)
    """
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


if __name__ == "__main__":
    grafo = construir_grafo_social_demo()

    print("=== Construcción de GrafoSocial (demo) ===")
    print(grafo)
    print(f"Ciudadanos ({grafo.numero_ciudadanos()}): {grafo.ciudadanos()}")
    print(f"Número de relaciones: {grafo.numero_relaciones()}")

    print("\n=== Vecinos de cada ciudadano ===")
    for ciudadano in grafo.ciudadanos():
        print(f"  {ciudadano}: {grafo.vecinos(ciudadano)}")

    print("\n=== Propagación desde 'Ana' (bien conectada, 4 vecinos directos) ===")
    print("Sin límite de saltos:")
    alcance = grafo.propagar_publicacion("Ana")
    print(f"  Alcanzados ({len(alcance)}): {alcance}")

    print("Con límite de 1 salto:")
    alcance_1 = grafo.propagar_publicacion("Ana", saltos_maximos=1)
    print(f"  Alcanzados ({len(alcance_1)}): {alcance_1}")

    print("Con límite de 2 saltos:")
    alcance_2 = grafo.propagar_publicacion("Ana", saltos_maximos=2)
    print(f"  Alcanzados ({len(alcance_2)}): {alcance_2}")

    print("\n=== Propagación desde 'Carlos' (poco conectado, 1 vecino directo) ===")
    print("Sin límite de saltos:")
    alcance_carlos = grafo.propagar_publicacion("Carlos")
    print(f"  Alcanzados ({len(alcance_carlos)}): {alcance_carlos}")

    print("Con límite de 1 salto:")
    alcance_carlos_1 = grafo.propagar_publicacion("Carlos", saltos_maximos=1)
    print(f"  Alcanzados ({len(alcance_carlos_1)}): {alcance_carlos_1}")

    print("\n=== Caso borde: propagación desde 'Diana' (ciudadana aislada) ===")
    alcance_diana = grafo.propagar_publicacion("Diana")
    print(f"  Alcanzados ({len(alcance_diana)}): {alcance_diana}")
    assert alcance_diana == [], "Un ciudadano aislado no debe alcanzar a nadie"

    print("\n=== Caso borde: saltos_maximos=0 (no se propaga a nadie) ===")
    alcance_0 = grafo.propagar_publicacion("Ana", saltos_maximos=0)
    print(f"  Alcanzados ({len(alcance_0)}): {alcance_0}")
    assert alcance_0 == [], "Con 0 saltos no debe alcanzar a nadie"

    print("\n=== Caso borde: origen inexistente ===")
    try:
        grafo.propagar_publicacion("Zoe")
    except ValueError as e:
        print(f"OK, lanzó ValueError: {e}")

    print("\n=== Caso borde: saltos_maximos negativo ===")
    try:
        grafo.propagar_publicacion("Ana", saltos_maximos=-1)
    except ValueError as e:
        print(f"OK, lanzó ValueError: {e}")

    print("\nTodas las pruebas de GrafoSocial pasaron.")
