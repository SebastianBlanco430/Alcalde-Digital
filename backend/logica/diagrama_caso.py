# El caso v2 como GRAFO DIRIGIDO ACÍCLICO (modelo puro, sin motor gráfico) y su diagrama de flujo final. Sesión A.
#
# Grafo: un vértice por nodo del caso; una arista por cada salida concreta (`siguiente`, `destino` de las opciones y de
# los acusados, `rutas`, `al_terminar`). «@volver» NO es arista: regresa a la rueda desde la que se eligió, así las
# respuestas no crean ciclos. Lo usan el validador (backend/logica/casos_v2.py) y el diagrama.
#
# Algoritmos (con lista de adyacencia {id: [ids]}):
#   buscar_ciclo     DFS iterativo con colores (blanco/gris/negro): una arista a un vértice GRIS cierra un ciclo.
#   alcanzables      recorrido en profundidad desde el inicio.
#   orden_topologico Kahn (grados de entrada); capas = camino más largo desde las fuentes, en orden topológico.
#
# Diagrama (§12 del contrato): se dibujan los nodos con `hito`, todos los finales, el laboratorio y la acusación. Los
# demás se PLIEGAN: hay arista u -> v entre dos dibujados si existe un camino de u a v solo por nodos no dibujados. Un
# nodo que termina en «@volver» sigue, para el dibujo, por las salidas de su rueda (`al_terminar` y las opciones que no
# regresan). Luego, diseño por capas de Sugiyama (sesión E; explicado en docs/DIAGRAMA_FLUJO.md):
#   romper_ciclos        DFS con colores: se quitan los lazos y las aristas de retroceso (el grafo queda acíclico).
#   reduccion_transitiva se quitan los «atajos» u -> w cuando ya hay otro camino u -> ... -> w (una sola arista por par
#                        y nada de aristas redundantes); el recorrido del jugador se reduce aparte para que no se rompa.
#   capas                camino más largo desde las fuentes.
#   insertar_ficticios   las aristas que saltan más de una capa se parten con nodos ficticios (una arista por capa).
#   ordenar_capas        método del baricentro, pasadas hacia abajo y hacia arriba; se queda con el orden de menos
#                        cruces (cruces_entre_capas: inversiones entre dos capas vecinas, por mezcla, O(E log E)).

from backend.logica.casos_v2_tipos import VOLVER, Diagrama, NodoDiagrama

BLANCO, GRIS, NEGRO = 0, 1, 2
DIBUJADOS_SIEMPRE = ("final", "laboratorio", "acusacion")
# Rótulo de una caja sin `hito` (el final usa su `titulo`). Es genérico: el texto del caso sale del JSON.
ROTULO_POR_TIPO = {"laboratorio": "Laboratorio", "acusacion": "Acusación"}
PASADAS_BARICENTRO = 8          # pasadas (bajar, subir, ...); se corta antes si dos seguidas no mejoran
FICTICIO = "~"                  # prefijo de los nodos ficticios (los ids del caso nunca empiezan así)


# -- Estructura (lee el dict del JSON) --

def salidas(nodo):
    """Destinos concretos de un nodo, en orden y sin repetir (sin «@volver» ni destinos que no sean texto)."""
    if not isinstance(nodo, dict):
        return []
    destinos = [nodo.get("siguiente")]
    for clave in ("opciones", "acusados"):
        for opcion in nodo.get(clave) or []:
            if not isinstance(opcion, dict):
                continue
            destinos.extend(r.get("destino") for r in opcion.get("rutas") or [] if isinstance(r, dict))
            destinos.append(opcion.get("destino"))
    destinos.append(nodo.get("al_terminar"))
    vistos, salida = set(), []
    for d in destinos:
        if isinstance(d, str) and d != VOLVER and d not in vistos:
            vistos.add(d)
            salida.append(d)
    return salida


def aristas(nodos):
    """Lista de adyacencia del caso (solo destinos que existen)."""
    return {i: [d for d in salidas(n) if d in nodos] for i, n in nodos.items()}


# -- Algoritmos de grafo --

def buscar_ciclo(grafo):
    """Un ciclo [a, b, ..., a] si lo hay; None si el grafo es acíclico. DFS iterativo con colores."""
    color = {v: BLANCO for v in grafo}
    for raiz in grafo:
        if color[raiz] != BLANCO:
            continue
        color[raiz] = GRIS
        pila = [(raiz, iter(grafo[raiz]))]
        while pila:
            vertice, pendientes = pila[-1]
            siguiente = next(pendientes, None)
            if siguiente is None:
                color[vertice] = NEGRO
                pila.pop()
            elif color.get(siguiente, NEGRO) == GRIS:
                camino = [v for v, _ in pila]
                return camino[camino.index(siguiente):] + [siguiente]
            elif color.get(siguiente) == BLANCO:
                color[siguiente] = GRIS
                pila.append((siguiente, iter(grafo[siguiente])))
    return None


def alcanzables(grafo, inicio):
    vistos, pila = set(), [inicio]
    while pila:
        v = pila.pop()
        if v in vistos or v not in grafo:
            continue
        vistos.add(v)
        pila.extend(grafo[v])
    return vistos


def inalcanzables(grafo, inicio):
    alcanzados = alcanzables(grafo, inicio)
    return [v for v in grafo if v not in alcanzados]


def orden_topologico(grafo):
    """Orden topológico (Kahn), estable respecto al orden de declaración. ValueError si hay un ciclo."""
    entrada = {v: 0 for v in grafo}
    for v in grafo:
        for w in grafo[v]:
            entrada[w] += 1
    listos = [v for v in grafo if entrada[v] == 0]
    orden = []
    while listos:
        v = listos.pop(0)
        orden.append(v)
        for w in grafo[v]:
            entrada[w] -= 1
            if entrada[w] == 0:
                listos.append(w)
    if len(orden) != len(grafo):
        raise ValueError("el grafo tiene un ciclo: no hay orden topológico")
    return orden


def capas(grafo):
    """{vértice: capa}: longitud del camino más largo desde alguna fuente (capa 0). ValueError si hay un ciclo."""
    capa = {v: 0 for v in grafo}
    for v in orden_topologico(grafo):
        for w in grafo[v]:
            capa[w] = max(capa[w], capa[v] + 1)
    return capa


def romper_ciclos(grafo):
    """Copia acíclica del grafo: sin lazos (u -> u), sin repetidas y sin las aristas de retroceso de un DFS con colores
    (las que llegan a un vértice GRIS, que es lo que cierra un ciclo). El DFS arranca en las fuentes y después en el
    resto, en orden de declaración: es determinista. Un grafo que ya es acíclico sale igual. O(V + E)."""
    entrada = {v: 0 for v in grafo}
    for v in grafo:
        for w in grafo[v]:
            if w in entrada and w != v:
                entrada[w] += 1
    raices = [v for v in grafo if entrada[v] == 0] + [v for v in grafo if entrada[v] != 0]
    color = {v: BLANCO for v in grafo}
    salida = {v: [] for v in grafo}
    for raiz in raices:
        if color[raiz] != BLANCO:
            continue
        color[raiz] = GRIS
        pila = [(raiz, iter(grafo[raiz]))]
        while pila:
            vertice, pendientes = pila[-1]
            w = next(pendientes, None)
            if w is None:
                color[vertice] = NEGRO
                pila.pop()
            elif w not in grafo or w == vertice or color[w] == GRIS or w in salida[vertice]:
                continue                                  # destino ajeno, lazo, retroceso o repetida: fuera
            else:
                salida[vertice].append(w)
                if color[w] == BLANCO:
                    color[w] = GRIS
                    pila.append((w, iter(grafo[w])))
    return salida


def reduccion_transitiva(grafo):
    """Reducción transitiva de un DAG: se quita u -> w si w se alcanza desde OTRO sucesor de u (el camino largo ya lo
    dice). Es única en un DAG y conserva quién alcanza a quién. Los alcanzables de cada vértice se calculan en orden
    topológico inverso (conjuntos): O(V·E) en el peor caso, nada para los ~20 nodos de un caso."""
    orden = orden_topologico(grafo)
    alcance = {}
    for v in reversed(orden):
        a = set()
        for w in grafo[v]:
            a.add(w)
            a |= alcance[w]
        alcance[v] = a
    return {u: [w for w in grafo[u] if not any(w in alcance[v] for v in grafo[u] if v != w)] for u in grafo}


# -- Sugiyama: nodos ficticios, cruces y baricentro --

def es_ficticio(v):
    return isinstance(v, str) and v.startswith(FICTICIO)


def insertar_ficticios(grafo, capa_de):
    """Grafo «propio»: cada arista u -> v con capa(v) - capa(u) = k > 1 se parte en k aristas con k - 1 nodos ficticios
    (uno por capa intermedia). Devuelve (propio, capa de cada vértice, {(u, v): [u, f1, ..., v]}). O(V + E + ficticios)."""
    propio = {v: [] for v in grafo}
    capa = dict(capa_de)
    cadenas = {}
    for u in grafo:
        for v in grafo[u]:
            cadena = [u]
            for c in range(capa[u] + 1, capa[v]):
                f = f"{FICTICIO}{u}>{v}@{c}"
                propio[f] = []
                capa[f] = c
                cadena.append(f)
            cadena.append(v)
            for a, b in zip(cadena, cadena[1:]):
                propio[a].append(b)
            cadenas[(u, v)] = cadena
    return propio, capa, cadenas


def _inversiones(seq):
    """Pares i < j con seq[i] > seq[j], por mezcla (merge sort): O(n log n). Devuelve (inversiones, seq ordenada)."""
    if len(seq) < 2:
        return 0, list(seq)
    medio = len(seq) // 2
    ia, a = _inversiones(seq[:medio])
    ib, b = _inversiones(seq[medio:])
    total, mezcla, i, j = ia + ib, [], 0, 0
    while i < len(a) and j < len(b):
        if a[i] <= b[j]:
            mezcla.append(a[i])
            i += 1
        else:
            mezcla.append(b[j])
            total += len(a) - i
            j += 1
    mezcla.extend(a[i:])
    mezcla.extend(b[j:])
    return total, mezcla


def cruces_entre_capas(orden, propio):
    """Cruces de un orden por capas (lista de listas) del grafo propio. Dos aristas (u1, v1), (u2, v2) entre capas vecinas
    se cruzan si pos(u1) < pos(u2) y pos(v1) > pos(v2): se ordenan las aristas por (pos u, pos v) y se cuentan las
    inversiones de pos v. O(E log E)."""
    pos = {v: i for fila in orden for i, v in enumerate(fila)}
    total = 0
    for fila in orden:
        pares = sorted((pos[u], pos[v]) for u in fila for v in propio.get(u, ()) if v in pos)
        total += _inversiones([b for _, b in pares])[0]
    return total


def ordenar_capas(propio, capa_de, orden_inicial=None, pasadas=PASADAS_BARICENTRO):
    """Orden dentro de cada capa por el método del baricentro. Pasada hacia abajo: cada capa se ordena por la media de las
    posiciones de sus predecesores (la capa anterior queda fija); pasada hacia arriba: por la de sus sucesores. Un nodo
    sin vecinos conserva su posición; los empates, el orden previo (orden estable). Tras cada pasada se cuentan los
    cruces y se guarda el MEJOR orden visto; se para si dos pasadas seguidas no mejoran o ya no hay cruces."""
    n_capas = max(capa_de.values(), default=-1) + 1
    if orden_inicial is None:
        orden = [[v for v in propio if capa_de[v] == c] for c in range(n_capas)]
    else:
        orden = [list(f) for f in orden_inicial]
    padres = {v: [] for v in propio}
    for u in propio:
        for v in propio[u]:
            padres[v].append(u)

    def barrer(c, vecinos):
        pos = {v: i for fila in orden for i, v in enumerate(fila)}

        def clave(v):
            ref = [pos[w] for w in vecinos.get(v, ()) if w in pos]
            return sum(ref) / len(ref) if ref else pos[v]
        orden[c].sort(key=clave)                       # sort es estable: los empates guardan el orden previo

    mejor, mejor_cruces = [list(f) for f in orden], cruces_entre_capas(orden, propio)
    sin_mejora = 0
    for i in range(pasadas):
        if mejor_cruces == 0:
            break
        if i % 2 == 0:
            for c in range(1, n_capas):
                barrer(c, padres)
        else:
            for c in range(n_capas - 2, -1, -1):
                barrer(c, propio)
        cruces = cruces_entre_capas(orden, propio)
        if cruces < mejor_cruces:
            mejor, mejor_cruces, sin_mejora = [list(f) for f in orden], cruces, 0
        else:
            sin_mejora += 1
            if sin_mejora >= 2:
                break
    return mejor


# -- Diagrama --

def cadena_que_vuelve(nodos, inicio, limite=200):
    """¿El camino de `siguiente` (diálogos y laboratorio) que empieza en `inicio` termina en «@volver»? Devuelve el nodo
    que vuelve, o None si el camino llega a una rueda, una acusación, un final o un id que no existe."""
    actual = inicio
    for _ in range(limite):
        nodo = nodos.get(actual) if isinstance(actual, str) else None
        if not isinstance(nodo, dict) or nodo.get("tipo") not in ("dialogo", "laboratorio"):
            return None
        if nodo.get("siguiente") == VOLVER:
            return actual
        actual = nodo.get("siguiente")
    return None


def _aristas_de_volver(nodos):
    """{nodo que vuelve: [salidas de su rueda]}: cómo sigue el flujo, para el dibujo, tras una respuesta con «@volver»."""
    extra = {}
    for nodo in nodos.values():
        if not isinstance(nodo, dict) or nodo.get("tipo") != "rueda":
            continue
        vuelven, salidas_rueda = [], []
        for opcion in nodo.get("opciones") or []:
            destino = opcion.get("destino") if isinstance(opcion, dict) else None
            que_vuelve = cadena_que_vuelve(nodos, destino)
            if que_vuelve is not None:
                vuelven.append(que_vuelve)
            elif destino in nodos:
                salidas_rueda.append(destino)
        if nodo.get("al_terminar") in nodos:
            salidas_rueda.insert(0, nodo["al_terminar"])
        for v in vuelven:
            extra.setdefault(v, [])
            extra[v].extend(s for s in salidas_rueda if s not in extra[v])
    return extra


def _se_dibuja(nodo):
    return isinstance(nodo, dict) and (bool(nodo.get("hito")) or nodo.get("tipo") in DIBUJADOS_SIEMPRE)


def _plegar(grafo, dibujados):
    """Aristas entre dibujados: u -> v si hay un camino de u a v solo por nodos no dibujados."""
    plegado = {u: [] for u in dibujados}
    for u in dibujados:
        vistos, pila = set(), list(reversed(grafo.get(u, [])))
        while pila:
            v = pila.pop()
            if v in vistos:
                continue
            vistos.add(v)
            if v in plegado:
                if v != u and v not in plegado[u]:
                    plegado[u].append(v)
            else:
                pila.extend(reversed(grafo.get(v, [])))
    return plegado


def _filas(lineas, capa_de, dibujados):
    """Fila de cada nodo dibujado: orden por baricentro sobre el grafo propio (con ficticios), partiendo del orden de
    declaración (los ficticios, al final de su capa: la primera pasada los coloca)."""
    propio, capa_p, _ = insertar_ficticios(lineas, capa_de)
    n_capas = max(capa_de.values(), default=-1) + 1
    inicial = [[v for v in dibujados if capa_de[v] == c] for c in range(n_capas)]
    for f in propio:
        if es_ficticio(f):
            inicial[capa_p[f]].append(f)
    orden = ordenar_capas(propio, capa_p, inicial)
    return {v: i for fila in orden for i, v in enumerate(w for w in fila if not es_ficticio(w))}


def construir(nodos, inicio, visitados=()):
    """Diagrama (casos_v2_tipos.Diagrama) del caso: nodos dibujados con capa/fila/visto y UNA sola arista por par, sin
    atajos redundantes. Recorrida = sus dos extremos vistos; si el jugador pasó por un atajo (saltándose un nodo
    intermedio que no vio), ese atajo se conserva como arista recorrida para que el camino amarillo no se corte. Nunca
    lanza por un caso raro: los ciclos (que el validador ya rechaza) se rompen antes de hacer las capas."""
    visitados = set(visitados or ())
    nodos = nodos if isinstance(nodos, dict) else {}
    grafo = {i: list(d) for i, d in aristas(nodos).items()}
    for v, extra in _aristas_de_volver(nodos).items():
        grafo[v].extend(s for s in extra if s not in grafo[v])
    dibujados = [i for i, n in nodos.items() if _se_dibuja(n)]
    plegado = romper_ciclos(_plegar(grafo, dibujados))
    capa_de = capas(plegado)
    reducido = reduccion_transitiva(plegado)
    vistos_dib = [u for u in dibujados if u in visitados]
    recorrido = reduccion_transitiva({u: [v for v in plegado[u] if v in visitados] for u in vistos_dib})
    lineas = {u: list(reducido[u]) for u in dibujados}
    for u in vistos_dib:
        lineas[u].extend(v for v in recorrido[u] if v not in lineas[u])
    fila_de = _filas(lineas, capa_de, dibujados)
    cajas = []
    for i in dibujados:
        n = nodos[i]
        etiqueta = n.get("hito") or (n.get("titulo") if n.get("tipo") == "final" else "") \
            or ROTULO_POR_TIPO.get(n.get("tipo"), "")
        cajas.append(NodoDiagrama(i, etiqueta, n.get("tipo"), capa_de[i], fila_de[i], i in visitados,
                                  n.get("resultado") if n.get("tipo") == "final" else None))
    trazos = tuple((u, v, u in visitados and v in visitados) for u in dibujados for v in lineas[u])
    n_capas = max(capa_de.values(), default=-1) + 1
    filas_max = max((sum(1 for c in capa_de.values() if c == k) for k in range(n_capas)), default=0)
    vistos = sum(1 for c in cajas if c.visto)
    return Diagrama(tuple(cajas), trazos, n_capas, filas_max, vistos, len(cajas))
