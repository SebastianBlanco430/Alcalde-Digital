# Plan final — base de backend: reloj, ambiente, manillas, efectos retardados y equilibrio

Estado: 2026-11-11, rama `plan-de-trabajo-final`, sin commit. Todo lo de este documento es **backend puro** (sin ursina ni
panda3d, sin importar `frontend/`), determinista (relojes y azar inyectables) y serializable a JSON. El frontend todavía
**no** lo consume: ver «Lo que falta cablear».

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

Puntos de enganche en código existente (mínimos y aditivos; ninguna función existente se reescribió):

- `main.py`, `crear_flujo`: si `reloj_partida.activo()`, `flujo = FlujoConTiempo(flujo)` (4 líneas, por fuera de
  `FlujoConGameState`).
- `backend/logica/guardado.py`: `capturar` añade las claves opcionales que devuelva `flujo.tiempo_a_dict()` si existe;
  `restaurar` llama a `flujo.restaurar_tiempo(datos)` si existe. `VERSION` sigue en 1.

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

Con GameState (índice = promedio de la confianza de los tres grupos):

| Mapa · ritmo | (a) ignorar | (b) compartir todo | (c) criterio |
|---|---|---|---|
| chico · 1 misión/día (7) | 39,33 malo | 35,42 malo | 64,59 [53,3..70,2] |
| chico · 2/día (14) | 39,33 malo | 27,18 malo | 68,64 [62,3..73,5] |
| grande · 1/día (7) | 39,33 malo | 48,19 neutro | 56,11 [53,6..58,6] |
| grande · 2/día (14) | 39,33 malo | 43,83 neutro | 56,85 [53,2..60,9] |
| grande · 3/día (20) | 39,33 malo | 38,26 malo | 60,46 [53,0..65,7] |
| grande · 7/día (47) | 39,33 malo | 20,43 malo | 80,94 [57,4..89,1] |

Sin GameState (índice de los tres indicadores): ignorar 39,33 (malo) en todos los casos; compartir todo entre 0,9 y 5,6
(malo); criterio entre 91,8 y 98,1 (bueno).

En todos los casos **c > a y c > b, y (a) nunca es la mejor** (`tests/test_equilibrio_estrategias.py`). Ignorar siempre
deja convivencia y confianza en 34 y los grupos en 50 / 34 / 34.

### Hallazgos de equilibrio que NO se tocaron (para decidir)

1. **Con el límite de 7 días el final «bueno» es casi inalcanzable en el mapa grande.** Los deltas de confianza por grupo
   se escalan para acertar las 47 misiones (`confianza_misiones.tabla_deltas`); con 14-20 misiones en la semana el
   jugador con criterio queda en 57-60 (neutro). Opciones: escalar `tabla_deltas` a las misiones jugables en 7 días, o
   bajar `UMBRAL_BUENO`. No se cambió porque es balance existente.
2. **«Compartir todo» puede terminar «neutro» en el mapa grande con pocas misiones** (48 con 7 misiones), aunque los
   indicadores de la ciudad queden en 0/0/100: el final con GameState solo mira la confianza por grupo. Sugerencia: que
   el final combine ambos (por ejemplo, final malo si algún componente de `evaluar_final_indicadores` < 20).

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
- Falta: el cargador y el globo en pantalla (otro agente).

## 8. Dilemas extra (`backend/datos/dilemas_extra.json`) — solo datos, sin conectar

Por qué va aparte: las 47 misiones de verificar y el mazo de 18 noticias tienen **una respuesta correcta** (`Mision`
exige `es_verdadera`, y la pista siempre permite deducir el veredicto). Un dilema no tiene veredicto, así que no cabe en
`Mision` ni en `CONSECUENCIAS_RETARDADAS` sin tocar código. El archivo trae 9 dilemas listos para que otro agente los
conecte.

```
{"version": 1, "_nota": "...", "dilemas": [ {
   "id", "titulo", "tema",
   "dia_min", "dia_max",            # ventana de días en que puede salir (dia_max ≤ 6: la consecuencia llega antes del fin)
   "situacion",                     # texto del planteamiento (≤ 360 caracteres)
   "opciones": [ {                  # 2 o 3
       "id", "etiqueta",            # etiqueta del botón (≤ 45)
       "inmediato": {"texto", "deltas": {indicador: n}, "confianza": {grupo: n}},
       "retardado": {"horas": 24..48, "clave", "mensaje", "deltas": {...}, "confianza": {...}} } ],
   "nota_diseno" } ] }              # para el equipo; no se muestra
```

- `deltas` usa `convivencia`, `confianza`, `desinformacion`; `confianza` usa `policia`, `ciudadanos`, `instituciones`.
  Son los mismos argumentos de `efectos_retardados.crear_efecto(clave, mensaje, deltas, confianza, origen)`.
- `retardado.mensaje` empieza con `{cuando}` («Ayer» / «Hace dos días»), como `MENSAJES_RETARDO`. Es más largo que los
  de misión (hasta 260 caracteres): comprobar que cabe en el aviso.
- Cómo conectarlo (propuesta): al elegir una opción, aplicar `inmediato` a los indicadores y al GameState, y programar
  `ColaEfectos.programar(ahora + horas, crear_efecto(clave, mensaje con {cuando} resuelto, deltas, confianza,
  origen="dilema:<id>"))`. Elegir cuenta como «participar» para `costo_aislamiento`.
- Garantías (`tests/test_dilemas_extra.py`): toda opción tiene al menos un beneficio y un costo medibles; en
  `domingo_sin_pantalla`, apagar todo es la opción que menos suma (desconectarse por completo no es la mejor estrategia).
- Tabla «qué misiones ya son dilemas» y criterios: bóveda, nota «48 Frases de NPC y dilemas».

## Lo que falta cablear (frontend; fuera de este encargo)

- Llamar a `flujo.avanzar_tiempo(time.dt)` una vez por frame en el mundo (con `hasattr`, porque el flujo en línea y el
  juego con `ALCALDE_RELOJ=0` no lo tienen) y no llamarlo en pausa, menús, minijuegos y cinemáticas. **Mientras nadie lo
  llame el reloj está parado en el día 1 a las 08:00** y nada de lo nuevo se nota en el juego.
- HUD: `flujo.reloj.hora_texto()`, manillas (`manillas.manillas_de_ciudad`), avisos (`vaciar_avisos_retardados()`).
- Panel de final: mostrar `final["motivo"]` y, sin GameState, `flujo.resumen_final()`.
- Multitud / NPC / plazas / luz: leer `flujo.ambiente()` y las funciones de la tabla del punto 3.

## Pruebas

`tests/` está en `.gitignore` (pruebas locales). Nuevas: `test_reloj_partida.py`, `test_ambiente_ciudad.py`,
`test_manillas.py`, `test_efectos_retardados.py` (incluye el costo de aislamiento), `test_flujo_tiempo.py` (fin a los 7
días, guardado viejo/nuevo/dañado, pureza de los módulos) y `test_equilibrio_estrategias.py`, más el ayudante
`simulacion_estrategias.py`.
