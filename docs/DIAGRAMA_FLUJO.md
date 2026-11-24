# Diagrama de flujo «Recorrido del caso» (diseño por capas de Sugiyama)

Pantalla final de un caso de la Fiscalía v2: después de la tarjeta del final, el botón «Ver el recorrido» muestra el
caso como un **diagrama de flujo** al estilo de Detroit: Become Human. Los momentos que el jugador vio salen con su
texto; los que no, como siluetas con «?»; el camino recorrido va en amarillo, y arriba, el porcentaje visto («Has visto
el 57 % del caso (12 de 21 momentos)»). Sesión E (24-nov) rehízo cómo se reparte y cómo se dibujan las aristas.

Código:

| Archivo | Qué hace |
|---|---|
| `backend/logica/diagrama_caso.py` | El caso como grafo, el plegado, romper ciclos, reducción transitiva, capas, nodos ficticios, conteo de cruces y orden por baricentro. Puro, sin `ursina`. |
| `frontend/fiscalia/diagrama_flujo_calculos.py` | `disponer()`: coordenadas, trazos (curvas), puntos de unión y la malla. Puro, sin `ursina`. |
| `frontend/fiscalia/diagrama_flujo.py` | Solo dibuja (en `camera.ui`) lo que calcula `disponer()`. |
| `tests/test_diagrama_caso.py`, `tests/test_fiscalia_diagrama_sugiyama.py` | Tests puros; `tests/_diagrama_viejo.py` guarda el algoritmo anterior para medir el «antes». |

## 1. El problema

El diagrama de antes se leía, pero era una maraña: en el caso «Cuentas fantasma» había **89 aristas** entre 21 cajas,
**549 cruces** y 45 aristas que pasaban **por encima** de una caja que no era la suya.

Causas (medidas, no supuestas):

1. **Aristas redundantes.** El diagrama solo dibuja los momentos importantes (hitos, laboratorio, acusación, finales) y
   «pliega» el resto: hay arista u → v si se puede ir de u a v pasando solo por nodos no dibujados. En un interrogatorio
   (una rueda de preguntas que vuelven con `@volver`), desde una respuesta se llega a **todas** las siguientes, y
   también a todas las de después. Así aparecían atajos u → w aunque ya existiera u → v → w: 89 aristas donde bastan 39.
2. **Aristas largas en línea recta.** Una arista que salta dos o más columnas se dibujaba como un segmento recto del
   borde de una caja al de otra, y atravesaba las cajas de las columnas de en medio.
3. **Haces «todos con todos».** Entre dos ruedas seguidas, cada respuesta de la primera lleva a cada respuesta de la
   segunda: un bipartito completo K(m, n). Dibujado arista por arista tiene **m(m−1)·n(n−1)/4 cruces sea cual sea el
   orden** (con m = n = 4, 36 cruces). Ningún reordenamiento lo arregla.
4. **Lo amarillo** era «las dos puntas vistas» sobre esas 89 aristas: con muchos momentos vistos, casi todo era amarillo.

## 2. El algoritmo, paso a paso

El método de Sugiyama (Sugiyama, Tagawa y Toda, 1981) dibuja un grafo dirigido por **capas**: 1) quitar ciclos,
2) asignar capas, 3) partir las aristas largas con nodos ficticios, 4) ordenar cada capa para cruzar poco,
5) asignar coordenadas y 6) trazar las aristas. Aquí, además, se reduce el grafo antes (paso 0) y se concentran los
haces completos al trazar (paso 6).

Notación: V = vértices (cajas dibujadas, ~20), E = aristas, F = nodos ficticios, V' = V + F y E' = aristas del grafo
«propio» (con ficticios).

### Paso 0. Plegado y una sola arista por par

`diagrama_caso._plegar()`: para cada nodo dibujado u, un **DFS** por los nodos no dibujados; cada nodo dibujado que se
alcanza es un destino de u. Las respuestas con `@volver` siguen, para el dibujo, por las salidas de su rueda
(`al_terminar` y las opciones que no regresan), así que una pregunta y su respuesta nunca forman un ciclo ni un lazo.
Cada destino se apunta una sola vez (conjunto de vistos): **varias opciones que llevan al mismo sitio son una sola
arista**, y u → u no se guarda nunca.

Complejidad: O(D·(V_caso + E_caso)), un DFS por nodo dibujado D.

### Paso 1. Romper ciclos

`diagrama_caso.romper_ciclos()`: DFS **con colores** (blanco = sin visitar, gris = en la pila, negro = terminado). Una
arista que llega a un vértice gris es una **arista de retroceso**: es la que cierra un ciclo, y se quita; los lazos
u → u y las repetidas también. Un grafo sin aristas de retroceso es acíclico (teorema del DFS). Se arranca por las
fuentes (grado de entrada 0) y luego por el resto, en orden de declaración, para que sea determinista. Los casos
válidos ya son acíclicos (el validador rechaza los ciclos) y salen igual; esto es para que un caso roto no tumbe la
pantalla final.

Complejidad: O(V + E).

### Paso 2. Reducción transitiva

`diagrama_caso.reduccion_transitiva()`: se quita u → w cuando w se alcanza desde **otro** sucesor de u. En un grafo
acíclico la reducción transitiva es **única** y conserva exactamente quién alcanza a quién: el dibujo dice lo mismo con
menos líneas (89 → 39 aristas en «Cuentas fantasma»). Se calculan los alcanzables de cada vértice en orden topológico
inverso (`alcance[v] = ∪ ({w} ∪ alcance[w])` para cada sucesor w) y se filtra.

El recorrido del jugador se reduce **aparte**, sobre el subgrafo de los nodos vistos: si el jugador fue de u a w sin
pasar por el v intermedio (que no vio), el atajo u → w se conserva como arista recorrida y el camino amarillo no se
corta. Una arista está recorrida si sus dos extremos están vistos.

Complejidad: O(V·E) tiempo y O(V²) memoria (conjuntos de alcanzables). Con ~20 nodos, menos de 1 ms.

### Paso 3. Capas por camino más largo

`diagrama_caso.capas()`: orden topológico de **Kahn** (cola de vértices con grado de entrada 0) y, en ese orden,
`capa[w] = max(capa[w], capa[v] + 1)` para cada arista v → w. Cada vértice queda en la capa del **camino más largo**
desde una fuente: todas las aristas van de izquierda a derecha. La reducción del paso 2 no cambia las capas (un atajo
nunca es el camino más largo).

Complejidad: O(V + E) con una cola (la implementación usa una lista; con ~20 nodos da igual).

### Paso 4. Nodos ficticios

`diagrama_caso.insertar_ficticios()`: una arista u → v que salta k > 1 capas se parte en k aristas con k − 1 **nodos
ficticios**, uno por capa intermedia (id `~u>v@capa`). El resultado es un grafo «propio»: todas sus aristas unen capas
vecinas. Los ficticios ocupan un hueco en su columna, así que la arista pasará **entre** las cajas, no por encima. Se
guarda la cadena `(u, v) → [u, f1, ..., v]` para saber de qué arista es cada tramo.

En los 3 casos reales, tras la reducción todas las aristas grises unen capas vecinas (0 ficticios); los ficticios
aparecen con los atajos del recorrido (paso 2) o en casos futuros.

Complejidad: O(V + E + F).

### Paso 5. Orden dentro de cada capa: método del baricentro

`diagrama_caso.ordenar_capas()`:

- **Pasada hacia abajo:** con la capa anterior fija, cada nodo de la capa c recibe como clave el **baricentro** (media)
  de las posiciones de sus predecesores, y la capa se ordena por esa clave.
- **Pasada hacia arriba:** igual, de derecha a izquierda, con la media de las posiciones de sus sucesores.
- Un nodo sin vecinos conserva su posición; los empates conservan el orden previo (ordenación estable): determinista.
- Tras cada pasada se **cuentan los cruces** y se guarda el **mejor orden visto**. Se para tras 8 pasadas, si dos
  seguidas no mejoran o si ya no hay cruces.

**Conteo de cruces entre dos capas** (`cruces_entre_capas()`): dos aristas (u1, v1) y (u2, v2) se cruzan si
pos(u1) < pos(u2) y pos(v1) > pos(v2). Se ordenan las aristas por (pos u, pos v) y se cuentan las **inversiones** de la
secuencia de pos v con **ordenación por mezcla** (cada vez que en la mezcla pasa antes un elemento de la mitad derecha,
suma los que quedan en la izquierda).

Complejidad: conteo O(E' log E'); cada pasada O(V' log V' + E') más un conteo; como mucho 8 pasadas.

El backend guarda la fila de cada caja en `NodoDiagrama.fila`; `disponer()` vuelve a llamar a `ordenar_capas()` con los
ficticios, partiendo de esas filas (solo puede mejorar: se queda con el mejor).

### Paso 6. Coordenadas alineadas

`diagrama_flujo_calculos.disponer()`:

- **Columnas** de igual ancho: la capa c va en x = x0 + ancho_columna·(c + ½). Todas las cajas de una capa tienen la
  misma x y todas las cajas son del mismo tamaño. Entre columnas queda un **canal** (0,065–0,075 unidades) para las
  curvas.
- **Mismo paso vertical** en todas las capas (0,122): la caja i de una capa está a i pasos de la primera. Los
  ficticios se reparten en el hueco entre dos cajas (o por encima / por debajo, a 0,016).
- **Alineación:** cada capa empieza centrada y se desplaza, en medios pasos, hacia la media de las alturas de sus
  vecinos (4 vueltas). Las cadenas quedan rectas y los abanicos, simétricos.
- **Cabe en pantalla:** si el alto total supera el área (entre el porcentaje y el botón «Salir»), se aplica una
  **escala uniforme** a todo (y a la letra). Los 3 casos caben a escala 1 en 16:9 (1280×720 y 1920×1080 dan el mismo
  `camera.ui`).
- Caja de 3 líneas de letra de 12 px: los títulos más largos («Ramiro y la página de apuestas», «Citado, pero sigue
  circulando») caben enteros.

Complejidad: O(V' + E') por vuelta.

### Paso 7. Trazado: curvas por los canales y concentración de haces

- Cada tramo va del **puerto de salida** (centro del borde derecho) al **de entrada** (centro del borde izquierdo) con
  una **curva de Bézier cúbica** de tangentes horizontales (12 segmentos). Su x avanza siempre de una columna a la
  siguiente, así que la curva **nunca entra en una caja**; un nodo ficticio es un tramo recto a su altura a través de su
  columna, por el hueco entre cajas.
- **Concentración de aristas:** en cada canal, los destinos con **el mismo conjunto de orígenes** forman un grupo. Si hay
  2 o más orígenes y 2 o más destinos (un bipartito completo, la forma de «cualquier pregunta de esta rueda lleva a
  cualquiera de la siguiente»), las m·n aristas se dibujan como m + n tramos que se juntan en un **punto de unión**
  (rombo) a mitad del canal. Las curvas que llegan a un mismo punto no se cruzan entre sí: los 36 cruces de un K(4, 4)
  pasan a 0. Es la técnica de *edge concentration* (Newbery, 1989; la opción `concentrate` de Graphviz).
- Un tramo es **recorrido** si alguna de las aristas que representa lo es. Se dibujan dos mallas: las grises (finas) y,
  encima, las amarillas (gruesas), con puntas de flecha y rombos.
- Solo se dibujan aristas entre cajas dibujadas (momentos vistos o siluetas «?»), hacia la derecha y sin lazos.

Complejidad: agrupar O(E' log E'); curvas O(12·E'); la malla, O(segmentos). Dos entidades en total para todas las
aristas: el diagrama no pesa en el frame.

## 3. Estructuras de datos

| Estructura | Dónde | Para qué |
|---|---|---|
| Lista de adyacencia `{id: [ids]}` (diccionario de listas) | todo el backend | El caso, el grafo plegado, el reducido y el «propio». O(V + E) de memoria. |
| Pila (lista) con iteradores | `romper_ciclos`, `buscar_ciclo`, `_plegar` | DFS iterativo (sin recursión). |
| Diccionario de colores | `romper_ciclos`, `buscar_ciclo` | Blanco / gris / negro del DFS. |
| Cola y grados de entrada | `orden_topologico` (Kahn) | Orden topológico; capas por camino más largo. |
| Conjuntos `alcance[v]` | `reduccion_transitiva` | Quién alcanza a quién, para quitar atajos. |
| Lista de listas (una por capa) | `ordenar_capas` | El orden de cada capa; diccionario `posición` para el baricentro. |
| Ordenación por mezcla | `_inversiones` | Contar cruces entre dos capas en O(E log E). |
| Diccionario de grupos `{orígenes: [destinos]}` | `disponer` | Encontrar los haces completos que se concentran. |
| Tuplas y dataclasses inmutables | `Diagrama`, `NodoDiagrama`, `Disposicion`, `Trazo`, `Union` | Resultado puro y comparable (test de determinismo). |
| Malla (lista de vértices + lista de triángulos) | `malla()` | Todas las aristas en una sola entidad de Ursina. |

## 4. Resultados

Cruces contados con `diagrama_flujo_calculos.cruces()` sobre lo que se dibuja (cada arista o tramo como polilínea; se
cuentan los puntos distintos donde se tocan dos de ellas, salvo los que son extremo de las dos, es decir, el mismo
puerto o el mismo punto de unión). «Antes» se mide con el algoritmo anterior guardado en `tests/_diagrama_viejo.py`
(dibujo de antes: todas las aristas plegadas, segmentos rectos). Sin recorrido (todo gris):

| Caso | Aristas antes → después | Cruces antes | Solo reducción transitiva | + Sugiyama (sin concentrar) | **Después** | Aristas sobre una caja, antes → después |
|---|---|---|---|---|---|---|
| Cuentas fantasma | 89 → 39 (33 trazos, 5 uniones) | 549 | 19 | 19 | **0** | 45 → 0 |
| La encuesta trucada | 78 → 45 (29 trazos, 2 uniones) | 488 | 72 | 72 | **0** | 32 → 0 |
| El audio del candidato | 68 → 37 (27 trazos, 2 uniones) | 294 | 36 | 36 | **0** | 25 → 0 |

Lectura de la tabla: la reducción transitiva quita la mayoría (de 549 a 19); lo que queda son los bipartitos completos
entre ruedas, que tienen el mismo número de cruces en cualquier orden (por eso el baricentro no puede bajarlos: 19 =
1 + 3 + 9 + 3 + 3 en «Cuentas fantasma»), y la concentración los deja en 0. El baricentro sigue siendo necesario para
casos con otra forma (los tests lo comprueban con cadenas cruzadas a propósito) y para colocar los ficticios.

Con recorridos de jugador (los de las capturas de la verificación: pocos y casi todos los momentos vistos) también salen
0 cruces en los 3 casos. Un recorrido inventado que se salta una columna entera de preguntas («Cuentas fantasma» con
los nodos 1, 5, 9... vistos) deja 3 cruces: el atajo amarillo pasa por un nodo ficticio junto a un haz.

Antes de la corrección del contador (que solo contaba cortes «propios» entre segmentos y no los que caen justo en un
vértice de una curva) el «antes» medía 485 / 448 / 284; la meta (menos de la cuarta parte) se cumple con cualquiera de
las dos cuentas.

Tiempo de `construir()` + `disponer()`: 1,4–2,1 ms por caso (medido en el portátil de desarrollo).

## 5. Qué comprueban los tests

`pytest tests\test_diagrama_caso.py tests\test_fiscalia_diagrama_sugiyama.py tests\test_fiscalia_ui_diagrama.py -q`

- Romper ciclos (lazos, retroceso, sin fuentes, un DAG sale igual), reducción transitiva (atajos fuera, el rombo se
  queda), ficticios (una arista por capa), conteo de inversiones (incluido K(2, 2) = 1) y baricentro (deshace cruces,
  determinista).
- El «antes» se reproduce con el algoritmo viejo; en los 3 casos y 3 recorridos, cruces × 4 < antes.
- Una sola arista por par; ningún trazo repetido; ningún segmento atraviesa una caja; mismas x por capa, mismo paso
  vertical y cajas iguales; todo dentro del área 16:9; ningún título se corta; mismo resultado en dos llamadas; el
  porcentaje y las «?» iguales que antes; el recorrido va en trazos amarillos; caso mínimo, vacío y con ciclo.
