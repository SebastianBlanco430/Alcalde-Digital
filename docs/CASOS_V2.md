# Casos de la Fiscalía v2

Motor de casos «estilo Detroit» de la Fiscalía de Ciudad Nova (sesión A, 2026-11-23). Código: `backend/logica/casos_v2.py`
(motor y validador), `backend/logica/diagrama_caso.py` (grafo y diagrama), `backend/logica/casos_v2_tipos.py` (tipos que
comparten el motor, la escena 3D y la interfaz). El formato completo del JSON está en el contrato de la sesión
(`sesiones-24nov/fiscalia/contrato-caso.md`); aquí va el resumen y, sobre todo, las **estructuras de datos**.

## 1. Bandera

`ALCALDE_FISCALIA_V2` (encendida por defecto; `backend/logica/fiscalia_bandera.activa()`).

| | Encendida | `=0` |
|---|---|---|
| Casos | v2 (`"formato": 2`), jugados en el edificio de la Fiscalía | v1 en el PC de siempre |
| Misiones digitales | las que declaran los JSON v2 (hoy: `investigacion_cuentas`, más las que añada la sesión D) | las tres de siempre (`parkour_sector_1`, `parkour_sector_2`, `investigacion_cuentas`) |
| Inés y Doña Neide en el mundo | hablan y cooperan, pero **no entregan pruebas** | entregan la bitácora / la lista como hoy |
| Archivo de casos | muestra también los finales v2 (`final_cargos`...) | como hoy |

## 2. Formato en una página

Archivo `backend/datos/casos/caso_<id>.json`, UTF-8, con `"formato": 2`.

- `mision`: la misión se registra sola (`misiones_digitales.misiones_de_casos()`): id, título (≤ 28), mensaje (≤ 140, dice
  «Fiscalía»), pago (20–120, múltiplo de 5), dificultad, grupo, `dia` (1–7).
- `solidez`: `inicial` (0–100) y 1–3 `umbrales` con nombre. Un solo medidor 0–100: sube con pruebas y buenas respuestas.
- `personajes` (2–5, siempre `fiscal`), `evidencias` (≤ 10; cada una la otorga **un** parkour o **un** `da_evidencia`).
- `laboratorio`: 1–2 parkours (`sector_1`, `sector_2`), cada uno da la prueba que **este** caso declare.
- `nodos`: `dialogo` (→ `siguiente`), `rueda` (2–4 opciones, `turnos`, `reloj`, `al_terminar`), `laboratorio`,
  `acusacion` (rutas por umbral) y `final` (`exito` / `parcial` / `fracaso`, con `efectos.grupos`).
- Condiciones (`requiere`): `evidencia`, `alguna_evidencia`, `sin_evidencia`, `marcas`, `sin_marcas`, `visitado`,
  `no_visitado`, `solidez {min, max}`. Efectos: `da_evidencia`, `marcas` y, solo en finales, `grupos`.
- Las pruebas se guardan en el GameState como `evidencia:<id_caso>.<id_prueba>`: dos casos no se mezclan.
- Al cerrar, el mismo rastro que el v1: `caso:<id>:jugado`, `:final:<nodo>`, `:resultado:<r>`, `:acusado:<opción>`.

Comprobar un caso sin abrir el juego:

```
.\venv\Scripts\python.exe scripts\validar_caso_v2.py backend\datos\casos\caso_<id>.json
```

## 3. El caso es un grafo dirigido acíclico (DAG)

Cada **nodo** del JSON es un vértice. Hay una **arista** u → v por cada salida concreta: `siguiente`, el `destino` de
cada opción y de cada acusado, las `rutas` de la acusación y `al_terminar`. Se guarda como **lista de adyacencia**
(`diagrama_caso.aristas(nodos)` → `{id: [ids]}`), que ocupa O(V + E).

`@volver` **no es una arista**: una respuesta termina en `@volver` y el juego regresa a la rueda desde la que se eligió
(guardada en el estado como `hub`). Así las preguntas de una rueda son ramas que vuelven sin crear ciclos.

Ejemplo pequeño:

```
n_intro ──> n_rueda ──(preguntar)──> r_resp ··@volver··> (n_rueda)
              │ └──(acusar)──> n_acusacion ──> final_bien
              └──al_terminar──────────┘                └──> final_mal

lista de adyacencia:
  n_intro:     [n_rueda]
  n_rueda:     [r_resp, n_acusacion]        (destinos de opciones + al_terminar, sin repetir)
  r_resp:      []                           (@volver no cuenta)
  n_acusacion: [final_bien, final_mal]
```

### 3.1 Detección de ciclos: DFS con colores

`diagrama_caso.buscar_ciclo(grafo)`. Cada vértice tiene un color: **blanco** (sin visitar), **gris** (en la pila del DFS:
es un antepasado del vértice actual) y **negro** (terminado). Si desde el vértice actual hay una arista hacia un vértice
**gris**, esa arista vuelve a un antepasado: hay un ciclo, y el ciclo es el trozo de la pila desde ese antepasado. El DFS es
iterativo (una pila de `(vértice, iterador de vecinos)`) para no depender del límite de recursión. Coste O(V + E).

```
a → b → c → a      DFS: a gris, b gris, c gris; c → a y a es GRIS  ⇒ ciclo [a, b, c, a]
a → b, a → c, b → d, c → d   (rombo): al llegar a d por c, d ya es NEGRO ⇒ no es ciclo
```

### 3.2 Alcanzabilidad

`diagrama_caso.alcanzables(grafo, inicio)`: recorrido en profundidad con una pila y un conjunto de vistos, O(V + E). Un
nodo fuera de ese conjunto es inalcanzable «por las aristas» y es un error. Además, para «desde todo nodo se llega a un
final» se recorre el grafo **invertido** desde los finales (añadiendo, solo para esto, la vuelta de cada respuesta con
`@volver` a su rueda).

### 3.3 Orden topológico por capas (para el diagrama de flujo)

`diagrama_caso.orden_topologico(grafo)` usa el algoritmo de **Kahn**: se cuentan las aristas que entran a cada vértice;
los que tienen 0 van a una cola; al sacar uno se «borran» sus aristas y los vecinos que quedan en 0 entran a la cola. Si al
final no salieron todos, hay un ciclo. `diagrama_caso.capas(grafo)` recorre ese orden y asigna a cada vértice la **longitud
del camino más largo** desde una fuente: `capa[v] = max(capa[u] + 1)` sobre sus predecesores. Así toda flecha va de una
columna a otra más a la derecha.

```
a → b → c → d,  a → d          capas: a 0, b 1, c 2, d 3   (d va después de c aunque a → d exista)
```

El **diagrama** (`diagrama_caso.construir`) dibuja solo los nodos con `hito`, los finales, el laboratorio y la acusación.
Los demás se **pliegan**: hay flecha u → v entre dos dibujados si existe un camino de u a v que solo pasa por nodos no
dibujados (un DFS desde cada dibujado que se detiene al tocar otro dibujado). Una respuesta con `@volver` sigue, para el
dibujo, por las salidas de su rueda. Dentro de cada capa, las filas se ordenan por **baricentro** (la media de las filas de
los vecinos), bajando y subiendo unas pasadas, para que las flechas se crucen poco. Lo visto sale iluminado; lo no visto,
como silueta.

## 4. El recorrido real: búsqueda sobre los estados del juego

Que un nodo sea alcanzable por las aristas no basta: una opción puede pedir una prueba que nunca se consigue. El
validador **juega** el caso entero (`casos_v2.analizar`).

- **Estado** (`casos_v2.Estado`, inmutable y con `hash`): nodo actual, solidez, rueda de `@volver`, opciones gastadas,
  turnos gastados por rueda, marcas, pruebas, nodos visitados y acusado.
- **Transiciones**: las mismas funciones que usa la partida de verdad (`_Reglas`: continuar, elegir una opción libre, que se
  acabe el reloj con `@terminar`, completar un parkour, salir del laboratorio). El validador y el juego no pueden discrepar.
- **Búsqueda en anchura** (BFS con una cola) desde el estado inicial. El conjunto de estados ya vistos es la
  **memoización**: un estado repetido no se vuelve a expandir. Se hace 4 veces: con 0 parkours, con cada uno y con los dos.
- **Canonización** para que no explote: se olvida lo que ya no puede influir (opciones y turnos de ruedas que ya no se
  pueden volver a pisar, visitas a nodos que no vuelven a salir ni se consultan en un `requiere`). Dos estados que solo
  difieren en eso se cuentan como uno. «Cuentas fantasma» queda en ~25 000 estados (~0,7 s).
- **Tope** de 200 000 estados: si se supera, es un **aviso** (no un error ni un cuelgue) y no se dan por buenos los
  resultados de ese recorrido.
- Con todos los estados y sus sucesores se comprueba: cada nodo se pisa en algún recorrido; ningún estado se queda **sin
  salida** (BFS hacia atrás desde los estados finales: el que no llega es un callejón); y la **tabla de solidez**: con 2
  parkours se alcanza el mejor final (el `exito` de mayor exigencia), con 1 se alcanza al menos un `exito` o `parcial` pero
  no el mejor, con 0 ningún `exito`.

Resultado con el caso real:

| Parkours | Solidez máxima | Mejor final |
|---|---|---|
| 2 | 99 | `final_justicia` (≥ 85) |
| `sector_1` | 73 | `final_cargos` (≥ 60) |
| `sector_2` | 75 | `final_cargos` |
| 0 | 35 | `final_sin_pruebas` (≥ 30) |

## 5. Complejidad (resumen para la sustentación)

| Operación | Estructura | Coste |
|---|---|---|
| Ciclos | DFS con colores sobre lista de adyacencia | O(V + E) |
| Alcanzables / llegan a un final | DFS (directo / invertido) | O(V + E) |
| Orden topológico y capas | Kahn + camino más largo en un DAG | O(V + E) |
| Aristas plegadas del diagrama | un DFS por nodo dibujado | O(D · (V + E)) |
| Recorrido real | BFS sobre el grafo de estados, con memo (conjunto hash) | O(S · A), S estados, A acciones por estado (≤ 4) |

## 6. La Fiscalía dentro del juego (escena e interfaz)

- **Edificio:** la casa de dos pisos junto a la Praça da Sé (`fiscalia_bandera.CASA_FISCALIA`), con el cartel «Fiscalía de
  Ciudad Nova». No es un lugar del grafo de la ciudad: las misiones de Fiscalía tienen como destino **Praça da Sé** y la
  baliza y el GPS llevan a la puerta de la casa. Con **E** delante de la puerta se abre el caso.
- **Recorrido:** despacho (el fiscal entrega el caso) → laboratorio forense (dos terminales = dos parkours, opcionales)
  → sala de interrogatorio (rueda de opciones con reloj) → acusación en el despacho → final con el diagrama del caso.
  No se sale a mitad; `Esc` abre la pausa del caso, que permite abandonarlo (final de archivo).
- **Código:** `frontend/fiscalia/` — `registro.py` (enganche en `frontend/extensiones.py`), `edificio.py`,
  `escena_fiscalia.py`, `salas.py`, `personajes.py`, `camaras.py`, `sentarse.py` (escena 3D) y `hud_caso.py`, `rueda.py`,
  `medidor_solidez.py`, `subtitulos.py`, `laboratorio_ui.py`, `acusacion.py`, `diagrama_flujo.py`, `pausa_caso.py`
  (interfaz). El reparto entre escena e interfaz está en `frontend/fiscalia/contrato_ui.md`. La matemática va en los
  `*_calculos.py`, sin `ursina` y con tests.
- **Respaldo:** si la escena falla al abrir o en un frame, o si no hay ningún caso v2 válido, el juego cae solo al flujo
  anterior (PC de la calle y sala digital). Con `ALCALDE_FISCALIA_V2=0` no se registra nada de `frontend/fiscalia/`.
- **Añadir un caso:** crear `backend/datos/casos/caso_<id>.json` con `"formato": 2` y pasarlo por
  `python scripts/validar_caso_v2.py` (dice qué final se alcanza con 0, 1 y 2 parkours). No hace falta tocar código.
