# Plan final — base de backend: reloj, ambiente, manillas, efectos retardados y equilibrio

Estado: 2026-11-11, rama `plan-de-trabajo-final`, sin commit. Todo lo de este documento es **backend puro** (sin ursina ni
panda3d, sin importar `frontend/`), determinista (relojes y azar inyectables) y serializable a JSON. El reloj, el chip, los
avisos y la pantalla final ya están cableados en el juego (§9); el resto del frontend: ver «Lo que falta cablear».

## Mapa de módulos

| Módulo | Qué es | Bandera (constante / entorno) |
|---|---|---|
| `backend/logica/reloj_partida.py` | Reloj de 7 días de juego | `RELOJ` / `ALCALDE_RELOJ=0`, `ALCALDE_SEG_POR_HORA=<n>` |
| `backend/logica/flujo_tiempo.py` | `FlujoConTiempo`: envoltorio del flujo (fin por tiempo, cola, avisos, ambiente, guardado) | se crea solo con el reloj activo |
| `backend/logica/ambiente_ciudad.py` | Eje de los puntos 3-6: bienestar, conflictos, `Ambiente`, `AmbienteSuave`, perfil de NPC | — (solo lectura, no cambia nada por sí mismo) |
| `backend/logica/manillas.py` | Manillas tipo Bonfim accesibles (color + patrón + nudos + desgaste) | — |
| `backend/logica/efectos_retardados.py` | Cola de efectos programados y regla de consecuencia diferida | `EFECTOS_RETARDADOS` / `ALCALDE_EFECTOS_RETARDADOS=0` |
| `backend/logica/costo_aislamiento.py` | Decaimiento por no participar | `AISLAMIENTO` / `ALCALDE_AISLAMIENTO=0` |
| `backend/datos/noticias_mision.py` (añadido al final) | Tabla de consecuencias retardadas de la carta de misión | — |
| `backend/logica/dilemas.py` + `backend/datos/dilemas_loader.py` | Dilemas jugables: calendario, oferta, plazo, efectos inmediato/retardado/ignorar (§8) | `DILEMAS` / `ALCALDE_DILEMAS=0` |

Puntos de enganche en código existente (mínimos y aditivos; ninguna función existente se reescribió):

- `main.py`, `crear_flujo`: si `reloj_partida.activo()`, `flujo = FlujoConTiempo(flujo)` (4 líneas, por fuera de
  `FlujoConGameState`).
- `backend/logica/guardado.py`: `capturar` añade las claves opcionales que devuelva `flujo.tiempo_a_dict()` si existe;
  `restaurar` llama a `flujo.restaurar_tiempo(datos)` si existe. `VERSION` sigue en 1.

- `main.py`, `crear_flujo`: justo después, `flujo = dilemas.envolver(flujo)` (3 líneas; devuelve el mismo flujo con
  `ALCALDE_DILEMAS=0`, sin reloj o con el JSON roto). `frontend/extensiones.py` lista `frontend.registro_dilemas`;
  `frontend/teclas.py` reserva K (`TECLA_DILEMAS`).

Con `ALCALDE_RELOJ=0` el flujo es exactamente el de antes (no se crea el envoltorio).

## 1. Reloj de la partida (`reloj_partida.py`)

- La partida empieza el **día 1 a las 08:00** y termina al **completar el día 7** (24:00 del día 7): 160 h de juego.
- `SEGUNDOS_REALES_POR_HORA = 15`: 1 día = 6 min reales, partida = 40 min. `ALCALDE_SEG_POR_HORA=2` la deja en ~5 min.
- **Decisión: el tiempo corre solo con el mundo activo.** El reloj no lee la hora real; avanza únicamente cuando se llama
  a `avanzar(dt)`. El frontend debe llamarlo una vez por frame con el mundo en primer plano y no llamarlo (o `pausar()`)
  en menús, minijuegos, modales, cinemáticas y pausa. Así leer una carta o trabajar no gasta la semana.
- Un frame largo no se come horas: `avanzar(dt)` recorta `dt` a `DT_MAX = 0,5 s`. `avanzar_horas(h)` no recorta (pruebas).

```
RelojPartida(seg_por_hora=None, dias=7, hora_inicio=8.0)
  avanzar(dt) -> horas avanzadas      avanzar_horas(h)       pausar() / reanudar() / en_pausa()
  dia() -> 1..7        hora() -> 0..24        hora_texto() -> «Día 3 · 14:30»
  tiempo_absoluto() -> horas desde las 00:00 del día 1 (arranca en 8.0; marca de tiempo de efectos y avisos)
  horas_transcurridas(), horas_restantes(), fraccion_partida() -> 0..1, terminado()
  a_dict() / RelojPartida.desde_dict(datos)          # la escala y la pausa del frontend no son parte de la partida
reloj_partida.activo(), segundos_por_hora(), texto_de(tiempo_absoluto)
```

Decisión: el `GameState` sigue sellando sus impactos con el **número de turno** (no se cambió su reloj, para no mezclar
unidades en guardados existentes). Los eventos retardados llevan la hora de juego en `datos["hora_juego"]`.

## 2. Fin por tiempo y guardado (`flujo_tiempo.py`)

`FlujoConTiempo(flujo, reloj=None, efectos=None, aislamiento=None)` delega todo lo demás con `__getattr__`.

```
flujo.reloj                         RelojPartida
flujo.avanzar_tiempo(dt)            ÚNICA llamada por frame del frontend: reloj + efectos vencidos + aislamiento + ambiente
flujo.avanzar_horas(h)              lo mismo en horas de juego (pruebas / depuración); no suaviza el ambiente
flujo.pausar_tiempo() / reanudar_tiempo()
flujo.partida_terminada()           catálogo agotado (como antes) O reloj terminado
flujo.motivo_fin()                  "tiempo" | "misiones" | None
flujo.final_partida()               el de FlujoConGameState (evaluar_final: índice por grupos) + motivo, dia, hora_texto;
                                    None si la partida no tiene consecuencias (el frontend pinta su panel de siempre)
flujo.resumen_final()               SIEMPRE un dict: final_partida() o, sin GameState, evaluar_final_indicadores(...)
flujo.cola_efectos / flujo.aislamiento / flujo.ambiente_suave / flujo.ambiente()
flujo.avisos_retardados, flujo.ultimo_aviso_retardado, flujo.vaciar_avisos_retardados()
flujo.tiempo_a_dict() / flujo.restaurar_tiempo(datos)
```

- **Final sin GameState** (`evaluar_final_indicadores`): índice = promedio de convivencia, confianza e «información»
  (100 − desinformación); ≥ 70 bueno, 40-69 neutro, < 40 malo; cualquier componente < 20 → malo. Mismos umbrales que
  `confianza_misiones.evaluar_final`. Se entrega por `resumen_final()` y **no** por `final_partida()` porque
  `finales_textos.lineas_resumen` exige la confianza por grupo.
- Al terminar el reloj la partida termina aunque haya una misión activa, y los efectos retardados que quedaban en la
  cola **se aplican en ese momento** (compartir sin verificar el último día no sale gratis).
- **Guardado**: claves opcionales `reloj`, `efectos_retardados`, `aislamiento`, `ambiente`. Un guardado anterior carga
  igual y empieza en el día 1 a las 08:00; un guardado nuevo carga en un juego sin reloj (las claves se ignoran); una
  clave dañada se descarta con aviso por stderr y ese componente empieza de cero. `VERSION` no cambió.
- **En línea**: el flujo en línea no pasa por `crear_flujo`, así que no tiene reloj ni efectos; el protocolo no cambió.

## 3. Ambiente de la ciudad (`ambiente_ciudad.py`) — API para los demás agentes

Entradas: `indicadores` = `EstadoPartida.indicadores()`; `confianzas` = `GameState.confianzas()` o `None`.
No toca `NOMBRES_INDICADORES` ni el protocolo: bienestar y conflictos son derivados que se recalculan.

```
confianza_efectiva = confianza                                    (sin GameState)
                   = 0,5·confianza + 0,5·promedio(grupos)         (con GameState)
bienestar_digital  = 0,40·convivencia + 0,35·confianza_efectiva + 0,25·(100 − desinformacion)
conflictos         = 0,50·desinformacion + 0,35·(100 − convivencia) + 0,15·(100 − confianza_efectiva)
salud              = (bienestar − conflictos + 100) / 200         0 rota · 0,5 inicio · 1 plena
sociabilidad       = 0,02 + 0,90·salud^1,5
neutro             = 0,06 + 0,30·(1 − |2·salud − 1|)
resto (1 − sociabilidad − neutro) repartido por pesos:
  aislamiento 0,2 + (100 − convivencia)/100 · pegado_al_celular 0,2 + desinformacion/100 · enojo 0,2 + conflictos/100
nivel: florece (salud ≥ 0,75) · sano (≥ 0,50) · tenso (≥ 0,25) · apagado, con histéresis de 0,04
```

`Ambiente` (namedtuple inmutable): `salud, sociabilidad, aislamiento, enojo, pegado_al_celular` (0..1), `bienestar,
conflictos` (0-100), `nivel`.

| Función | Devuelve | Para quién |
|---|---|---|
| `derivar(ind, conf=None)` | `{"bienestar", "conflictos"}` | HUD |
| `calcular_ambiente(ind, conf=None, nivel_anterior=None)` | `Ambiente` | todos |
| `densidad_poblacion(amb)` | 0,35..1,0 | multitud / peatones (multiplica la densidad; componer con `factor_horario(reloj.hora())`) |
| `limpieza(amb)` | 0..1 | props de basura, pintadas |
| `actividad_plazas(amb)` | 0..1 | corros, música, juego en plazas |
| `luz_ambiente(amb)` | `{"tinte": (r,g,b), "saturacion", "brillo"}` (factores; brillo ≥ 0,78) | iluminación / postproceso |
| `probabilidades_npc(amb)` | `{estado: p}` (suman 1) | depuración, HUD |
| `estado_npc(semilla, amb)` / `perfil_npc(semilla, amb)` | estado / `PerfilNPC(estado, manilla)` | NPC y multitud |
| `umbral_npc(semilla)` | 0..1 fijo por NPC | — |

- **Estados de NPC**: `sociable, neutro, celular, aislado, enojado`. Cada NPC tiene un número fijo `u` (splitmix64 de un
  entero, CRC32 de un texto o mezcla de una tupla; no usa `hash()`), y los estados ocupan tramos consecutivos de 0..1 con
  el ancho de su probabilidad. La mezcla sigue al Ambiente y, si este cambia poco, solo cambian los NPC del borde.
  Medido en las pruebas: con indicadores 95/95/5 más del 80 % son sociables; con 5/5/95, menos del 6 %.
- **`AmbienteSuave`**: `actualizar(dt, indicadores, confianzas=None)` acerca cada entrada a su valor real con un filtro
  exponencial de `TAU_SEGUNDOS = 30` s reales (63 % en 30 s, 95 % en 90 s); `dt` se recorta a 1 s. La primera llamada fija
  sin interpolar. `ambiente()`, `fijar(...)`, `valores()`, `a_dict()/desde_dict()`. `FlujoConTiempo.avanzar_tiempo` ya lo
  actualiza: los consumidores leen `flujo.ambiente()`.

## 4. Manillas (`manillas.py`)

Fitinhas tipo Bonfim. El estado nunca depende solo del color: cuatro canales redundantes.

| Nivel (bondad) | Color RGB | Patrón | Nudos |
|---|---|---|---|
| florece (≥ 75) | (240, 228, 66) amarillo | lisa | 3 |
| sano (≥ 50) | (86, 180, 233) azul cielo | rayada | 2 |
| tenso (≥ 25) | (213, 94, 0) bermellón | punteada | 1 |
| apagado (< 25) | (60, 36, 84) violeta oscuro | deshilachada | 0 |

- Indicadores con manilla: `convivencia, confianza, desinformacion, bienestar, conflictos`. En desinformación y conflictos
  la bondad es `100 − valor`. Identidad del indicador sin color: `SIMBOLOS` (manos, llave, megáfono, sol, rayo).
- `desgaste = 1 − bondad/100` (0 nueva .. 1 a punto de romperse), continuo.
- NPC: sociable (amarillo, lisa, 3), neutro (crema, trenzada, 2), celular (azul cielo, rayada, 1), aislado (violeta,
  deshilachada, 0), enojado (bermellón, zigzag, 1).

```
manilla_de(indicador, valor) -> Manilla(color, patron, desgaste, descripcion)
detalle_manilla(indicador, valor) -> dict (+ nivel, nudos, nombre, simbolo)      manillas_de_ciudad(valores)
manilla_de_npc(estado) -> Manilla          detalle_manilla_npc(estado) -> dict
```

Accesibilidad medida con `frontend/daltonismo_calculos` (simulación; distancia «redmean», máx. ≈ 765). Mínimo entre dos
colores de una misma paleta:

| Modo | Paleta de niveles | Paleta de NPC |
|---|---|---|
| sin filtro | 288 | 260 |
| protanopia | 254 | 215 |
| deuteranopia | 261 | 241 |
| tritanopia | 292 | 104 |
| acromatopsia | 123 | 78 |

El par más justo es sociable/neutro (amarillo/crema) en acromatopsia y tritanopia; lo desambiguan el patrón (lisa/trenzada)
y los nudos (3/2). `tests/test_manillas.py` exige ≥ 100 en las dicromacias y ≥ 60 en acromatopsia.

## 5. Efectos retardados (`efectos_retardados.py`)

```
Efecto(clave, mensaje, deltas, confianza, origen)       crear_efecto(...) valida
ColaEfectos: programar(en_horas_abs, efecto) -> id · vencidos(ahora) -> [(hora, Efecto)] (los saca) · pendientes()
             cancelar(id) · a_dict() / desde_dict()
aplicar(efecto, estado_partida, game_state=None, ahora=None) -> aviso
consecuencia_de_mision(mision, resultado, ahora) -> (en_horas_abs, Efecto) | None
```

`aplicar` suma `deltas` a los indicadores y, con GameState, llama a `aplicar_evento(tipo="retardado:<clave>")` (queda en el
ArbolImpactos). Aviso: `{"clave", "mensaje", "deltas", "confianza", "hora", "hora_texto"}`.

Tabla de consecuencias (en `backend/datos/noticias_mision.py`; decide la **decisión sobre la carta de misión**):

| Decisión | Clave | Indicadores (base) | Grupo de la misión |
|---|---|---|---|
| compartir un rumor falso | `rebrote` | desinformación +3, confianza −2 | −1,0 |
| reportar un rumor falso | `verificado` | confianza +2, desinformación −1 | +1,0 |
| compartir un rumor verdadero | `buena_fuente` | convivencia +1,5 | +0,5 |
| reportar un rumor verdadero | `falsa_alarma` | confianza −1,5 | −0,5 |
| compartir un rumor falso de datos personales | `datos_expuestos` | convivencia −4, confianza −2 | −1,5 |

- Escala por dificultad: fácil ×1, media ×1,5, difícil ×2. Retardo: fácil 24 h, media 36 h, difícil 48 h;
  `datos_expuestos` siempre 48 h.
- Misiones de datos personales: `generica_mutirao` y `generica_lanhouse` (`MISIONES_DATOS_PERSONALES`).
- Sin carta de misión (lote sin `decision_mision`): si la desinformación del lote subió, `rebrote` proporcional
  (|delta| / 15); si bajó, `verificado` proporcional; a 24 h y sin grupo.
- Son a propósito ≈ un tercio del efecto inmediato de `PLANTILLA_DELTAS`.
- Mensajes: `MENSAJES_RETARDO` («Ayer compartiste sin verificar «…»: hoy el bulo volvió a circular…»).

## 6. Equilibrio: costo de aislamiento (`costo_aislamiento.py`)

- «Participar» = cerrar una misión (de verificar o digital).
- Tras `GRACIA_HORAS = 24` h de juego sin participar se acumulan `PUNTOS_POR_HORA = 0,25`; se cobran en puntos enteros.
  Cada punto resta 1 a los indicadores convivencia y confianza y, con GameState, 1 a ciudadanos e instituciones.
- `TOPE_PUNTOS = 16` en toda la partida. Aviso al empezar cada racha y al llegar al tope.
- Solo cuenta mientras hay una misión que atender (con el catálogo agotado no se cobra).

Simulación (`tests/simulacion_estrategias.py`; `PYTHONPATH=. venv/bin/python tests/simulacion_estrategias.py`), índice
final medio de 5 semillas, con «criterio» = 85 % de aciertos. Entre corchetes, mínimo y máximo.

Con GameState y el **final ponderado** (flujo_tiempo.ponderar_final, ver más abajo; medido el 2026-11-11, 5 semillas):

| Mapa · ritmo (misiones) | (a) ignorar | (b) compartir todo | (c) criterio |
|---|---|---|---|
| chico · 1/día (7) | 39,33 malo | 18,19 malo | 76,28 [67,4..85,1] bueno/neutro |
| chico · 2/día (14) | 39,33 malo | 13,97 malo | 81,76 [74,8..86,8] bueno |
| grande · 1/día (7) | 39,33 malo | 27,56 malo | 72,71 [57,5..79,3] bueno/neutro |
| grande · 2/día (14) | 39,33 malo | 22,42 malo | 74,17 [61,7..80,3] bueno/neutro |
| grande · 3/día (20) | 39,33 malo | 22,19 malo | 78,26 [67,5..82,8] bueno/neutro |
| grande · 7/día (47) | 39,33 malo | 12,48 malo | 88,65 [72,4..94,6] bueno |

Con 20 semillas en el mapa grande, «criterio» da final **bueno** en 17/20 (2 misiones/día) y 19/20 (3/día); el resto, neutro;
nunca malo. «Compartir todo» e «ignorar» dan **malo** en todas las semillas y ritmos probados.

Sin GameState (índice de los tres indicadores): ignorar 39,33 (malo) en todos los casos; compartir todo entre 0,9 y 5,6
(malo); criterio entre 91,8 y 98,1 (bueno).

En todos los casos **c > a y c > b, y (a) nunca es la mejor** (`tests/test_equilibrio_estrategias.py`). Ignorar siempre
deja convivencia y confianza en 34 y los grupos en 50 / 34 / 34.

### Ajuste de equilibrio: final ponderado (hecho)

Antes (solo confianza por grupo) el final «bueno» era casi inalcanzable con 7 días en el mapa grande (criterio 53-61:
neutro; los deltas por grupo están escalados a las 47 misiones, y en una semana se juegan 14-20) y «compartir todo» salía
**neutro** (44-48) con la ciudad en 0/0/100. Cambio mínimo, **en `backend/logica/flujo_tiempo.py` y sin tocar
`confianza_misiones.py`**: con GameState, `final_partida()` pasa por `ponderar_final(final, indicadores, peso)`:

```
índice = PESO_CIUDAD · índice de los tres indicadores (evaluar_final_indicadores) + (1 − PESO_CIUDAD) · índice por grupos
```

`PESO_CIUDAD = 0,5`; mismos umbrales (≥ 70 bueno, 40-69 neutro, < 40 malo) y un grupo crítico sigue dando final malo.
No modifica el dict original (devuelve una copia con `final`, `indice`, `indice_grupos`, `indice_ciudad`, `componentes`,
`indicadores`, `componente_critico`, `fuente: "ponderado"`). **Reversible**: `FINAL_PONDERADO = False` o
`ALCALDE_FINAL_PONDERADO=0` devuelve el final de antes (solo grupos); `PESO_CIUDAD` se ajusta sin tocar nada más.
Pruebas: `test_equilibrio_estrategias.py` (bueno en ≥ 8/10 semillas con 2 y 3 misiones/día, compartir e ignorar malos,
bandera, validación del peso).

Queda abierto (para decidir): con 1 misión/día en el mapa grande «criterio» sale bueno o neutro según la semilla (mínimo
57,5); es lo esperable con solo 7 misiones jugadas.

## 7. Frases de NPC (`backend/datos/frases_npc.json`) — solo datos

Globos de texto ocasionales: lo que piensa un vecino según su estado, cómo está la ciudad y la hora. 357 frases.

```
{"version": 1,
 "neutro": [...], "sociable": [...], "aislado": [...], "celular": [...], "enojado": [...],   # 37 cada una (mínimo 35)
 "ciudad": {"florece": [...], "sano": [...], "tenso": [...], "apagado": [...]},              # 26 cada una (mínimo 25)
 "hora":   {"madrugada": [...], "manana": [...], "tarde": [...], "noche": [...]}}            # 17 cada una (mínimo 15)
elemento: {"t": "texto", "dia_min": 3}      # dia_min opcional (1..7): la frase solo sale desde ese día
```

- Las claves coinciden con `ambiente_ciudad` (estados de NPC y `nivel`). Las franjas de `hora` no tienen aún límites
  en código: los decide el cargador (sugerencia: madrugada 0-6, mañana 6-12, tarde 12-19, noche 19-24).
- Reglas de voz (las vigila `tests/test_frases_npc.py`): máximo 90 caracteres, una línea, sin «indicador»,
  «desinformación», «algoritmo» ni números con %, sin duplicados ni casi-duplicados (parecido ≥ 0,88 tras normalizar),
  y ninguna palabra inicial abre más del 25 % de una categoría. Al menos el 80 % de cada categoría sale desde el día 1.
- **Glosas**: varias frases usan términos locales (feira, mutirão, sinuca, padaria, várzea, posto, lan house...). Si el
  globo pasa por `nombres_visibles.glosar_texto`, el texto crece y puede pasar de 90 caracteres: decidir en el
  cargador si los globos se glosan o no.
- Cargador (`globos.cargar_frases`) y globo en pantalla: hechos, ver la sección 9.

## 8. Dilemas jugables (`backend/datos/dilemas_extra.json`, `backend/logica/dilemas.py`, `frontend/registro_dilemas.py`)

Por qué va aparte: las 47 misiones de verificar y el mazo de 18 noticias tienen **una respuesta correcta** (`Mision`
exige `es_verdadera`, y la pista siempre permite deducir el veredicto). Un dilema no tiene veredicto, así que no cabe en
`Mision` ni en `CONSECUENCIAS_RETARDADAS` sin tocar código. El archivo trae 9 dilemas listos para que otro agente los
conecte (ya conectados: ver «Conexión» abajo).

```
{"version": 1, "_nota": "...", "dilemas": [ {
   "id", "titulo", "tema",
   "dia_min", "dia_max",            # ventana de días en que puede salir (dia_max ≤ 6: la consecuencia llega antes del fin)
   "situacion",                     # texto del planteamiento (≤ 360 caracteres)
   "opciones": [ {                  # 2 o 3
       "id", "etiqueta",            # etiqueta del botón (≤ 45)
       "inmediato": {"texto", "deltas": {indicador: n}, "confianza": {grupo: n}},
       "retardado": {"horas": 24..48, "clave", "mensaje", "deltas": {...}, "confianza": {...}} } ],
   "ignorar": {"horas": 24, "clave", "mensaje", "deltas", "confianza"},   # qué pasa si no contesta a tiempo (solo costo)
   "nota_diseno" } ] }              # para el equipo; no se muestra
```

- `deltas` usa `convivencia`, `confianza`, `desinformacion`; `confianza` usa `policia`, `ciudadanos`, `instituciones`.
  Son los mismos argumentos de `efectos_retardados.crear_efecto(clave, mensaje, deltas, confianza, origen)`.
- `retardado.mensaje` empieza con `{cuando}` («Ayer» / «Hace dos días»), como `MENSAJES_RETARDO`. Es más largo que los
  de misión (hasta 215 caracteres): cabe en el aviso de 4 líneas (verificado en ventana).
- Garantías (`tests/test_dilemas_extra.py`): toda opción tiene al menos un beneficio y un costo medibles; en
  `domingo_sin_pantalla`, apagar todo es la opción que menos suma (desconectarse por completo no es la mejor estrategia).
- Tabla «qué misiones ya son dilemas» y criterios: bóveda, nota «48 Frases de NPC y dilemas».

### Conexión (hecha; aditiva: no se reescribió ninguna clase que ya funcionaba)

El dilema no cabe en `Mision` (sin veredicto único), así que vive aparte y solo se ENGANCHA a lo que ya existía:

```
dilemas_loader.cargar_dilemas()   -> tupla de Dilema/Opcion (valida; ValueError con el id si algo no cuadra)
GestorDilemas(dilemas, azar)      estado puro: calendario, oferta abierta, plazo, respuestas, a_dict()/desde_dict()
FlujoConDilemas(FlujoConTiempo)   envoltorio ENCIMA de FlujoConTiempo (mismo patrón que los demás): oye el reloj, ofrece,
                                  aplica lo inmediato y programa lo retardado en la ColaEfectos del FlujoConTiempo
dilemas.envolver(flujo)           lo que llama main.crear_flujo (3 líneas): devuelve el mismo flujo si no aplica
```

- **Cuándo sale.** Días 1-6, **1 o 2 por día** (con 9: tres días de 2 y tres de 1, repartidos con el azar inyectado; 2 por día a
  las 09:00 y 19:00, 1 por día a las 13:00). Cada dilema una sola vez, dentro de su ventana `[dia_min, dia_max]`; entre los
  candidatos va primero el que antes se le cierra la ventana (en 500 semillas salen siempre los 9). Determinista con
  `random.Random(semilla)`. Las opciones se presentan en **orden aleatorio** (se guarda en la oferta).
- **Entrada sin bloquear.** Al tocar, el teléfono recibe «La foto del cumple: tienes un mensaje sin responder. Pulsa K para leerlo.»
  y aparece el chip «K · Mensaje sin responder» sobre el reloj. Nada se abre solo.
- **Panel (`frontend/registro_dilemas.py`, `dilemas_calculos.py`).** K abre un panel modal registrado como bloqueador de
  `EscenaMundo` (como el Archivo de casos): el reloj se detiene por el vigía de `registro_reloj` (`motivo_de_pausa == panel`),
  el jugador no se mueve y Esc lo cierra **sin decidir** (el mensaje sigue pendiente; la pausa no se abre). Título, situación y
  2-3 opciones con 1-3 o clic. Cada opción trae «Ahora: algo más de convivencia en el barrio; un poco peor con los vecinos.»,
  redactado desde el efecto **inmediato** en palabras (un poco / algo / bastante) y **sin cifras ni nombres de indicador**; lo
  retardado no se adelanta (si no, no sería un dilema). Al elegir, el mismo panel cuenta en palabras lo que pasó ya.
- **Al elegir.** Efecto inmediato a indicadores y GameState (evento `dilema:<id>` en el ArbolImpactos), retardado a 24-48 h en
  `cola_efectos` con su mensaje de causa-efecto (sale por el HUD de avisos de los efectos retardados: «Ayer subiste la foto…»), y
  cuenta como **participar** para el costo de aislamiento.
- **Ignorar.** Si no responde en `PLAZO_HORAS = 9` h de juego (con el panel abierto el reloj no corre) caduca como «ignorar»:
  NO es participar y dispara la consecuencia retardada `ignorar` de ese dilema (24 h). Cada dilema trae su bloque `ignorar`
  (solo costo: lo vigila `test_dilemas_extra.py`) y ignorar suma menos que la mejor opción en los 9.
- **Guardado.** Clave opcional `dilemas` (ofrecidos, respuestas, oferta abierta con su orden, plan del calendario) vía
  `tiempo_a_dict()`; los efectos pendientes ya iban en `efectos_retardados`. Un guardado anterior a los dilemas no la trae: el
  gestor nuevo da por pasadas las ofertas hasta la hora guardada (no se le cobra lo que nunca pudo ver). Un dato dañado empieza de cero.
- **En línea** no existe (como el reloj). **Bandera:** `DILEMAS` / `ALCALDE_DILEMAS=0`. Tecla K (`teclas.TECLA_DILEMAS`).
- **Aviso largo.** Los 28 mensajes retardados (9 dilemas, 19 opciones + ignorar) con el peor sufijo de cambios caben en el
  `AvisoCausa` de 4 líneas sin recortarse (el más largo mide 4 líneas; medido en ventana, `scripts/humo_dilemas.py`).
  `test_dilemas_extra.py` limita los mensajes a 215 caracteres para guardar ese margen.

### Equilibrio con dilemas (`tests/simulacion_estrategias.py`, `tests/test_dilemas.py`)

`simular_con_dilemas(estrategia_misiones, estrategia_dilema, catalogo, ritmo, acierto, semilla)` juega la semana con los dilemas.
«Criterio» = la opción que mejor suma entre lo inmediato y lo retardado; «A»/«B» = siempre la 1.ª/2.ª que se presenta; «ignorar»
= no contesta. Mapa grande, final ponderado, 20 semillas, misiones con criterio (índice medio; «criterio gana» = en cuántas de las
20 semillas el índice es mayor):

| Misiones · ritmo | criterio | siempre A | siempre B | aleatoria | ignorar dilemas |
|---|---|---|---|---|---|
| acierto 85 % · 2/día | 76,63 | 75,14 (18/20) | 75,83 (16/20) | 75,53 (18/20) | 74,47 (19/20) |
| acierto 85 % · 3/día | 79,97 | 78,71 (20/20) | 79,05 (19/20) | 78,99 (18/20) | 77,79 (20/20) |
| acierto 85 % · 1/día | 70,08 | 67,78 (17/20) | 67,71 (18/20) | 67,48 (18/20) | 64,99 (20/20) |
| acierto 55 % · 2/día | 43,94 | 42,04 (17/20) | 41,81 (18/20) | 41,75 (19/20) | 36,40 (20/20) |

Misiones también «ignorar» + dilemas ignorados: final **malo** (índice ≈ 33); «compartir todo» + dilemas con criterio: **malo** (≈ 23).

**Ajuste hecho al JSON (con criterio):** con los deltas de indicadores de la primera versión (×1) una decisión pesaba menos que un
décimo de misión (las misiones mueven ±5-13 por indicador; los dilemas ±1-5) y, con la ciudad ya saturada en 100/100/0 por las
misiones bien jugadas, no se notaba (aleatoria llegaba a salir mejor que criterio por ruido). Se **multiplicaron ×2 los deltas de
indicadores** (inmediato, retardado e ignorar); los de **grupos** (policía, ciudadanos, instituciones) quedan como estaban porque
su escala ya es la de las misiones (±1-2). Con eso criterio gana a toda estrategia fija en el promedio de los cuatro escenarios y
casi siempre semilla a semilla. Limitación honesta: con un jugador muy bueno en misiones (ciudad saturada) la ventaja de decidir
bien un dilema es de 1-3 puntos de índice; se nota sobre todo en el avance de la semana, en los avisos y con jugadores flojos.
El final sigue siendo el ponderado (`ponderar_final`; el test comprueba índice = 0,5 · ciudad + 0,5 · grupos y los umbrales).

## 9. Reloj en el HUD y fin de partida (`frontend/registro_reloj.py`, `reloj_calculos.py`, `panel_final_semana.py`)

Cableado del reloj al juego real. Se instala por `frontend/extensiones.py` (`registro_reloj`); un vigía cuelga del HUD del
mundo y por eso solo corre con el mundo a la vista. Bandera: `RELOJ_HUD` / `ALCALDE_RELOJ_HUD=0` (sin chip ni enganche; el
reloj queda parado en el día 1). `ALCALDE_RELOJ=0` o el juego en línea: no hace nada.

- **Chip «Día N · hh:mm»**: sol (06:00-18:00) o luna + barra fina de la semana, abajo a la izquierda justo encima del chip
  de dinero (`diseno_adaptable.anclar` «izquierda»). Oculto con mapa grande, panel modal (inventario, tienda, diálogos,
  Archivo de casos), pausa y partida terminada. Visible con el teléfono abierto.
- **Cuándo corre el tiempo** (`reloj_calculos.motivo_de_pausa`; una sola regla): solo cuando el jugador manda en el mundo.
  No corre: sin reloj, en línea, partida terminada, pausa, cinemática (entrar/salir de un edificio), mapa grande, panel
  modal, teléfono abierto, fundido, misión en minijuego/cerrándose. **Interiores, minijuego, trabajo, mundo digital,
  parkour y ajustes son otras escenas: no gastan semana** (decisión: leer una carta o trabajar no gasta la semana).
  **Conducir (bici, moto) sí gasta tiempo.**
- **Enganche**: `flujo.avanzar_tiempo(time.dt)` una vez por frame (el reloj recorta `dt` a 0,5 s). Nada más lo llama.
- **Avisos** (`AvisoGenerico` propio, 4 líneas, ancho 0,9; centro bajo el de veredicto/pagos): «Último día: la semana
  termina esta medianoche.» (a 24 h) y «Quedan 2 horas…» (a 2 h), una vez por partida (`AvisosFin`; «Continuar» no repite
  los ya pasados). Los avisos de efectos retardados salen de `flujo.vaciar_avisos_retardados()` como `texto_efecto` («Ayer
  compartiste sin verificar «…»: hoy el bulo volvió a circular. (Desinformación +3 · Confianza −2)») por una
  `ColaAvisosCausa` (de uno en uno, 6,5 s cada uno, 1 s entre dos, máximo 4 pendientes: los más viejos se descartan). Con un
  panel abierto esperan. Medido en ventana: los 9 textos más largos posibles caben sin recortarse.
- **Fin**: al cruzar el día 7 (o al terminar por misiones) el vigía hace un cierre ordenado (baja del vehículo, cierra
  paneles de economía, mapa grande, bloqueadores y teléfono), llama a `EscenaMundo.refrescar()` **en ese mismo frame** y la
  escena pinta `PanelFinalSemana` (gancho nuevo `EscenaMundo.pintar_final`, 5 líneas aditivas en `escena_mundo.py`; si
  devuelve `False` se usan los paneles de siempre). Muestra título y texto del final, motivo y hora, confianza de los tres
  grupos (solo con GameState), cómo terminó la ciudad (convivencia, confianza, desinformación) y «Volver al menú». **Sin la
  cifra «Índice de la ciudad: N de 100»** (punto 7: consecuencias, no números; el índice sigue en `resumen_final()` para el
  backend y los tests, solo se dejó de pintar; las barras y las palabras quedan). La misión
  abierta se retira (`mision_actual() -> None`). **No se guarda tras terminar** (`guardado.se_puede_guardar` lo impide y
  `registro_guardado` borra el guardado).
- **Guardado / Continuar**: el guardado ya traía día/hora y cola de efectos (§2); el vigía reconoce el flujo o el reloj nuevo y
  reinicia avisos y cola. Partida nueva: `crear_flujo` da un reloj nuevo (día 1, 08:00).
- **Pruebas**: `test_reloj_calculos.py` (20), `test_registro_reloj.py` (28, escena falsa + flujo real, incluye ida y vuelta de
  guardado), `test_reloj_ventana.py` (5; sube `scripts/humo_reloj.py`: ventana real, pausa, modal, «Continuar» real por el
  botón del menú, avisos, final; se salta sin GL).
- **Lo que NO se comprobó**: partida jugada a mano de principio a fin con teclado y ratón; ventanas muy estrechas (el chip
  se ancla al borde izquierdo y apila sobre el de dinero, pero no se midió); modo en línea en ventana (solo la rama
  `online is not None` con escena falsa); los efectos liquidados al terminar el reloj no se muestran en la pantalla final
  (se aplican a los indicadores y cuentan en el final, pero no hay aviso).

## 9. NPC: conducta por indicadores, densidad y globos (puntos 3, 4 y «cantidad de NPC» del 5)

Módulos: `frontend/ambiente_vivo.py` (punto único de lectura del Ambiente suavizado y de la hora/día de la partida),
`backend/logica/conducta_estados.py` (conducta y densidad, Python puro), `backend/logica/globos.py` (qué frase y cuándo,
Python puro), `frontend/globos_npc.py` (piscina de globos) y `frontend/registro_ambiente_npc.py` (controlador por frame, lo
engancha `frontend/extensiones.py`). Ediciones a código existente: solo `Multitud.densidad = None` + 2 líneas que lo
aplican en `frontend/multitud.py` (con `densidad = None` la multitud es la de antes).

| Bandera | Constante / entorno | Qué apaga |
|---|---|---|
| Conducta | `NPC_CONDUCTA` / `ALCALDE_NPC_CONDUCTA=0` | postura, ritmo, charlas, paradas del celular |
| Densidad | `NPC_DENSIDAD` / `ALCALDE_NPC_DENSIDAD=0` | gente en la calle según ambiente × hora |
| Globos | `NPC_GLOBOS` / `ALCALDE_NPC_GLOBOS=0` | globos de texto |
| Depuración | `ALCALDE_AMBIENTE_FIJO="conv,conf,desinf"` | fija los indicadores (p. ej. `95,95,5` ciudad sana, `5,5,95` rota) |

El controlador alimenta `ambiente_vivo` SIEMPRE (aunque las tres banderas estén apagadas); no depende de que alguien llame a
`flujo.avanzar_tiempo`, así que funciona con `ALCALDE_RELOJ=0` y con guardados viejos. La transición es gradual: `AmbienteSuave`
(τ = 30 s reales) y el ritmo de cada NPC se acerca a su valor a 0,35/s.

**Conducta** (`perfil_npc` → estado fijo por NPC: `umbral_npc(semilla)` contra los tramos de `probabilidades_npc(amb)`):

| Estado | Postura | Ritmo | Comportamiento |
|---|---|---|---|
| sociable | cara arriba | 0,94 | para más y más rato, camina en pareja con otro sociable, a veces se para a charlar vuelto hacia el otro |
| neutro | la de siempre | 1,00 | exactamente `multitud_conducta.Conducta` |
| celular | mirando el celular | 0,70 | paradas largas y seguidas, sin mirar a los lados |
| aislado | cabizbajo | 0,86 | casi no se detiene y se abre de lado (1,6 m) para no cruzarse con nadie |
| enojado | tenso | 1,30 | no se detiene y no aguanta cola: a los 2 s adelanta |

- Mapa grande, nivel A (actores): postura + movimiento. Nivel B (figuras horneadas): **solo movimiento**; una variante de
  figura por estado exigiría hornear 5x figuras (memoria y tiempo de carga) y a 10-40 m la postura no se distingue: no se hizo.
- Mapa chico (12 peatones): postura, ritmo (`caminante.velocidad`) y paradas «mirando el celular» (`_espera`).
- NPC clave del mercado: postura según su estado; mientras atienden al jugador (`mirando`) los de celular/aislado quedan en
  neutro para no parecer que lo ignoran. Su diálogo y su giro no se tocan.
- **En línea**: `ConductaConEstado.modular = False` y los peatones conservan su velocidad: la posición de la multitud sigue
  siendo función pura de (t, ruta, semilla) y nada viaja por la red. Quedan solo postura, globos y densidad (locales y visuales).
  Sin reloj de partida (`hora() = None`) el factor horario no recorta.

**Densidad**: gente en la calle = `densidad_poblacion(amb)` (0,35..1,0) × `factor_horario(hora de la partida)`. Cada NPC
tiene un umbral fijo: al bajar el factor se van siempre los mismos, al subir vuelven los mismos, y el `Asignador` aplaza altas
y bajas hasta que el agente está fuera de la vista (a menos de `RADIO_APARICION` y a la vista no cambia). Mundo chico:
`enabled` por peatón con umbrales repartidos por igual y la misma regla.

**Globos**: piscina fija de 4 ranuras (máximo 2 visibles) de `piezas.etiqueta` colgadas de `npc.ancla_cabeza()`; solo NPC a
menos de 16 m y a menos de ~39 grados del eje de la cámara; enfriamiento global 3-7 s y por NPC 30 s; 3-5 s en pantalla con
fundido de 0,35 s; memoria de las 8 últimas frases (no se repiten); frase = 60 % estado, 25 % nivel de la ciudad, 15 % franja
horaria, filtrada por `dia_min`. Los globos NO se glosan (`nombres_visibles.glosar_texto`): se muestran tal cual el JSON. Se
ocultan en pausa y en cinemáticas. Cero fugas: los `Text` se crean una vez en `GlobosNPC.__init__`.

**Medido** (esta máquina, macOS, 2026-11-11; ver la nota 45 de la bóveda): `tests/test_ambiente_npc_humo.py` (offscreen, mapa
grande y chico), `tests/test_multitud_ventana.py` (ventana real, 1000 frames: 0 entidades nuevas, Python de la multitud
0,16 ms de media), `tests/medir_fps_npc.py` (ventana real sin tope de 60 fps: ~96-104 fps con 20-40 figuras dibujadas, igual
con el ambiente encendido o apagado dentro del ruido de ±4 %).

## 10. Manillas de Bonfim en el juego (punto 6: `frontend/registro_manillas.py`, `manillas_calculos.py`, `manillas_dibujo.py`)

Homenaje a las fitinhas do Senhor do Bonfim (Salvador, Brasil): cintas de colores que se anudan en la muñeca (en el juego,
«tres nudos, tres deseos»). Sin afirmaciones religiosas ni estereotipos; los textos están en español y los vigila un test.
Son el termómetro físico de la ciudad y de cada vecino; el modelo y la paleta accesible son de `backend/logica/manillas.py` (§4).

| Pieza | Qué hace |
|---|---|
| Brazalete del HUD | chip «Manillas · B» en el borde izquierdo (`diseno_adaptable.anclar(..., "izquierda")`, y=-0,07: entre el panel de turno y los chips de reloj/dinero), una cinta por indicador (convivencia, confianza, desinformación, bienestar digital, conflictos) colgada de una cuerda, con su dije (símbolo, sin color) debajo |
| Cambio de aspecto | color, tejido (lisa, rayada, punteada, deshilachada), nudos (3-2-1-0) y desgaste (0-1, 6 grados) según el nivel; una cinta nueva **se funde** sobre la anterior en 0,6 s; el nivel tiene **histéresis** de 2 puntos (no parpadea en el umbral) |
| Datos | `ambiente_vivo.obtener()` y `suave().valores()` (el Ambiente suavizado de la nota 45): sigue a `ALCALDE_AMBIENTE_FIJO` |
| Tooltip | con el ratón libre, encima de una cinta: la frase («Confianza: se confía con cautela») y «Sano · rayada · 2 nudos · 50/100» |
| Leyenda | tecla **B** (libre en el mundo): qué es cada manilla de la ciudad (con su frase actual), de los vecinos, cómo leer nivel/tejido/nudos y una nota cultural. No bloquea el juego; se cierra con B, con la pausa o con cualquier modal |
| Visibilidad | se oculta con pausa, cinemática, mapa grande, paneles modales y fin de partida (mismos motivos que el chip del reloj) |
| Cintas en los NPC | aro + cola (dos cintas cruzadas, algo exageradas: aro 6 cm de radio, cola 25 cm) en la muñeca izquierda (`npc.ancla_muneca("i")`) de los NPC cercanos con el aspecto de su estado (`npc_postura.estado_de`): nivel A de la multitud del mapa grande, peatones del mundo chico y NPC clave del mercado |
| Piscina | `CAPACIDAD_NPC = 12` cintas creadas una vez; `elegir_cintas_npc` reparte entre los NPC dibujados a menos de 13 m y a la vista (conserva hasta 16 m; los cercanos desplazan a los lejanos); se repasa cada 4 frames; nada se crea ni se destruye tras el arranque |
| Texturas | Pillow (`manillas_dibujo.dibujar_cinta`, ~1,2 ms, doble contorno crema/tinta para leerse sobre fondo claro y oscuro); caché por (color, tejido, nudos, grado de desgaste) y **precalentadas** una por frame al arrancar |

Cómo leer (cuatro canales, el color nunca va solo): **florece** amarillo, lisa, 3 nudos · **sano** azul, rayada, 2 nudos ·
**tenso** bermellón, punteada, 1 nudo · **apagado** violeta oscuro, deshilachada, sin nudos. Vecinos: sociable (amarillo, lisa,
3), neutro (crema, trenzada, 2), celular (azul, rayada, 1), aislado (violeta, deshilachada, 0), enojado (bermellón, zigzag, 1).

**Accesibilidad** (`tests/test_manillas_calculos.py`): la paleta final (HUD, NPC y leyenda) se simula en protanopia,
deuteranopia, tritanopia, acromatopsia y alto contraste y exige una distancia mínima por modo (150 / 100 / 100 / 100 / 60 / 150);
con la simulación y con el filtro de corrección del juego, todo par que quede por debajo de 60 se desambigua por la forma
(tejido + nudos); y dibujadas TODAS en el mismo gris, las cintas siguen siendo distintas entre sí. El filtro de pantalla
(`daltonismo.py`) actúa sobre el HUD y el mundo, así que no se reimplementa.

Banderas: `ALCALDE_MANILLAS=0` (todo), `ALCALDE_MANILLAS_HUD=0` (brazalete y leyenda), `ALCALDE_MANILLAS_NPC=0` (cintas de NPC);
constantes `MANILLAS`, `MANILLAS_HUD`, `MANILLAS_NPC` en `registro_manillas.py`. Registrado en `frontend/extensiones.py`.

Pruebas: `test_manillas_calculos.py` (mapeo, histéresis, leyenda, reparto, accesibilidad), `test_manillas_dibujo.py`,
`test_registro_manillas.py` (control y piscina con escenas falsas, banderas) y `test_manillas_ventana.py` (ventana real:
brazalete, B, tooltip, fundido, 1000 frames sin entidades nuevas). Humo y capturas: `scripts/humo_manillas.py`
(`--ambiente 90,50,10 --junto --lupa --fugas --transicion --captura RUTA`).

## 11. Ciudad viva: la ciudad cambia de aspecto con los indicadores (punto 5, cambios FÍSICOS)

Módulos: `backend/logica/ciudad_viva_calculos.py` (puro: Ambiente -> luz/cielo/niebla y cantidades, sitios fijos, histéresis,
fundido, reparto de ranuras), `frontend/ciudad_viva.py` (dibujo y controlador) y `frontend/registro_ciudad_viva.py` (lo engancha
`frontend/extensiones.py`). Lee `ambiente_vivo.obtener()` (nunca lo alimenta). Banderas: `ALCALDE_CIUDAD_VIVA=0` deja todo como
antes; `ALCALDE_CIUDAD_VIVA_ATMOSFERA=0` y `ALCALDE_CIUDAD_VIVA_CAPAS=0` apagan cada mitad.

**Atmósfera** (con salud 0,5 = arranque 50/50/50 todo es EXACTAMENTE lo de antes; medido: captura igual a la de ciudad viva apagada):
- Luz: `ciudad.luz.color` y `ciudad.ambiente.color` = color real de arranque x tinte/brillo de `luz_ambiente` relativos a salud 0,5
  (tinte amplificado x1,6; brillo hacia abajo x1,5; tope de brillo 1,06 para no blanquear las plazas). La dirección del sol NO se toca.
  Nota: Ursina crea la DirectionalLight sin su `color=` (el sol real es blanco), por eso se leen los colores de la luz de Panda.
- Cielo: `ciudad.cielo.color` (factor sobre los colores por vértice): gris frío abajo (0,64/0,74/0,88), dorado arriba.
- Niebla: color = horizonte x tinte del cielo (sin costura), distancia x0,55 (rota) .. x1,15 (sana), fuerza x1,30 .. x0,85.
  Se aplica con `PropagadorNiebla`: `scene.fog_color/fog_density` de Ursina recorren ~3000 entidades (medido 25-50 ms de un frame),
  así que se fijan los valores de la escena de una vez (los chunks nuevos copian esos) y las entidades existentes con shader de
  niebla reciben el valor en tandas de 120 por frame. Si otro módulo llama `activar_niebla` (p. ej. al entrar al mundo) se detecta y se reaplica.
- Sin tinte global por posproceso (el FilterManager es de `daltonismo`).

**Capas** (piscinas fijas de 129 entidades `unlit` creadas una vez, sin colisión, sin reconstruir chunks, fundido de escala de 1,5 s,
umbral fijo por sitio con histéresis de 0,03; azar de `azar_fijo`):

| Capa | Se ve con | Sitios |
|---|---|---|
| basura (bolsas, papeles con vaso, cajas) | limpieza baja (0,62 -> 0,12) | aceras (cada ~4 m) y plazas, validados con `es_transitable` |
| grafitis (4 diseños) | limpieza < 0,45 | pared de cada casa que mira a una calle, sobre su piso (pilotes incluidos), con espacio libre delante |
| carteles torcidos «sin conexión» | salud < 0,35 | aceras |
| flores vivas / flores marchitas | salud > 0,55 / < 0,42 | mismos puntos (se cruzan al pasar de una a otra) |
| guirnaldas con banderines y bombillas cálidas | salud > 0,62 | entre farolas vecinas a 6-24 m (las del mundo) |
| farolas apagadas (capuchón oscuro sobre el foco) | salud < 0,40 (hasta 85 %) | las farolas del mundo |
| bancos ocupados (1-2 personas sentadas) | actividad de plazas | los bancos del mundo (48 en el grande) |
| corros (5 personas y una bocina) | actividad de plazas alta | 2 puntos por plaza |

Radio de aparición 42-70 m de la cámara; reparto cada 0,3 s solo si la cámara se movió 1,5 m o cambió el Ambiente.

**Medido** (macOS, ventana real, 2026-11-12; `scripts/humo_ciudad_viva.py`, `tests/test_ciudad_viva_ventana.py`): controlador 0,4 ms de
media por frame (p99 2,3 ms, máx 2,6 ms); 129 entidades constantes tras 600 frames con teletransportes y cambios de ambiente; la niebla llega a
534/534 entidades existentes; guirnalda con error 0,0 m en el extremo; fps sin tope de 60, ambiente roto: 97,8 con capas vs 106,5 sin las capas
vs 109,2 con la ciudad viva apagada. Capturas: `scripts/captura_ciudad_viva.py`.
**No verificado**: partida jugada a mano; en línea en ventana; ventanas con GPU integrada; los LOD1 (chunks lejanos con `unlit_shader`) que se
instalan nuevos nacen sin niebla, como ya ocurría antes de este módulo.

## Lo que falta cablear (frontend; fuera de este encargo)

- ~~Reloj por frame, chip, avisos y panel de final~~: hecho, ver §9.
- ~~Manillas en el HUD y en los NPC~~: hecho, ver §10.
- ~~Dilemas jugables (punto 7)~~: hecho, ver §8.
- Multitud / NPC: HECHO (sección 9). Plazas / luz: HECHO (sección 11).

## Pruebas

`tests/` está en `.gitignore` (pruebas locales). Nuevas: `test_reloj_partida.py`, `test_ambiente_ciudad.py`,
`test_manillas.py`, `test_efectos_retardados.py` (incluye el costo de aislamiento), `test_flujo_tiempo.py` (fin a los 7
días, guardado viejo/nuevo/dañado, pureza de los módulos) y `test_equilibrio_estrategias.py`, más el ayudante
`simulacion_estrategias.py`. Dilemas: `test_dilemas.py` (carga, calendario, plazo/ignorar, efectos, guardado, bandera y equilibrio),
`test_registro_dilemas.py` (redacción sin números, panel con escena falsa, el reloj se detiene) y `test_dilemas_ventana.py`
(ventana real, `scripts/humo_dilemas.py`; se salta sin GL), además de `test_dilemas_extra.py` (contenido del JSON).

---
## ACTUALIZACIÓN 2026-11-12 (minijuegos, nota 53)
- Las 47 misiones de verificar tienen 6 minijuegos distintos (rastrear, comparar, ordenar cadena, chat, señales, contrarreloj), con respaldo a la pantalla de siempre y `ALCALDE_MINIJUEGOS=0` para apagarlos. Ver [[53 Minijuegos de verificar]]. Sin commit.
