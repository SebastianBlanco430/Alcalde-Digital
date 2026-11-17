# Rediseño visual de 5 minijuegos: coordinación de las partes A y B (2026-11-17)

Documento de coordinación. Lo leen las DOS instancias de Claude (Parte A y Parte B) y quien integre al final. Es de solo
lectura para las partes: si una parte necesita cambiar algo de aquí, lo pide (sección 10); no lo edita.

- Plan base acordado con el dueño: `docs/PLAN_REDISENO_MINIJUEGOS.md` (diagnóstico, conceptos, fases, riesgos).
- Paquete de la Parte A: `docs/PLAN_MINIJUEGOS_PARTE_A.md` (kit de papel + Comparar + Rastrear + Contrarreloj).
- Paquete de la Parte B: `docs/PLAN_MINIJUEGOS_PARTE_B.md` (marco + portada + globos + Chat + Señales).
- Repo: `~/Documents/GitHub/Alcalde-Digital`, rama `main`, Python `venv/bin/python`. Las dos partes trabajan en el MISMO
  directorio de trabajo, a la vez, sin ramas ni commits: por eso la regla de oro es que cada archivo tiene UN dueño.

---

## 0. AVISO: cambios sin dueño en el árbol (detectados al cerrar este plan, 2026-11-17 13:55)

Al empezar este plan (≈ 12:20) el árbol solo tenía sin seguimiento `docs/PLAN_REDISENO_MINIJUEGOS.md`,
`docs/SITIO_WEB_TEXTOS_LEGALES.md` y `sitio_web/`. Entre las 13:38 y las 13:41 OTRA sesión (no este plan, no las partes A/B)
escribió esto, que sigue sin commit:

| Archivo | Cambio | Choca con |
|---|---|---|
| `frontend/escenas/escena_minijuego.py` | +1 línea: pasa `minijuego_id=self.minijuego_id` a `PantallaPrevia` (flujo) | Regla «el flujo no se toca» (C8) |
| `frontend/minijuegos/pantalla_previa.py` | reescrita (279 líneas cambiadas): portada de caso | Contrato 5.6 (B solo añadía un enganche) y portada de B (B3) |
| `frontend/minijuegos/previa_calculos.py` | nuevo, puro: recortes de pasos y rumor | `portada_calculos.py` de B |
| `frontend/minijuegos_visual/chat_visual.py` | 183 líneas cambiadas | C1 (las capas de hoy no se tocan) y Chat de B (B2) |
| `frontend/minijuegos_visual/piezas_chat.py`, `chat_piezas_calculos.py` | nuevos: globo, avatar, reloj, botón-sello, sombra | `globos.py` de B y `piezas.py` de A |
| `frontend/minijuegos_visual/contrarreloj_visual.py` | 231 líneas cambiadas | C1 y Contrarreloj de A (A3) |
| `frontend/minijuegos_visual/piezas_contrarreloj.py`, `contrarreloj_piezas_calculos.py` | nuevos: papel, cronómetro, discontinua, iconos, pulsador | `piezas.py` de A |

Esto es una decisión del DUEÑO antes de lanzar las partes (las partes no la toman):
1. Descartar ese trabajo (lo revierte el dueño o su sesión principal; las partes nunca usan `git checkout`/`stash`/`reset`)
   y seguir este plan tal cual. Recomendado: es lo único que respeta C1 y C8 y deja el árbol limpio para dos partes.
2. Adoptarlo: entonces `pantalla_previa.py`, `previa_calculos.py` y el cambio de `escena_minijuego.py` pasan a ser de la
   Parte B (sustituyen a 5.6 y a `portada_*`; B los revisa con `preservador`), y `chat_visual.py`, `piezas_chat.py`,
   `chat_piezas_calculos.py` también de B; `contrarreloj_visual.py`, `piezas_contrarreloj.py`,
   `contrarreloj_piezas_calculos.py` de la Parte A. Cada parte los reconcilia con el contrato (las piezas comunes salen de
   `piezas.py`/`globos.py`, no se duplican) y la línea base de la suite se vuelve a medir con ese estado.

Regla para las dos partes mientras el dueño no decida: esos archivos quedan CONGELADOS (nadie los edita) y, al empezar,
cada parte corre `git status --short` y compara con esta tabla; si aparecen otros cambios que no son suyos ni de la otra
parte, para y avisa en su nota.

---

## 1. Correcciones al plan base (verificadas en el código el 2026-11-17)

| # | El plan base dice | Lo que hay de verdad (referencia) | Qué se hace |
|---|---|---|---|
| C1 | «El rediseño REEMPLAZA el dibujo de las clases `*_visual.py`». | Esas clases ya funcionan (corcho, mesa de luz, lupa, mapa, teléfono) y nadie las prueba. Reescribirlas rompe la regla de no reescribir lo que funciona. | NO se editan. Cada rediseño es una clase NUEVA en un módulo nuevo `<x>_rediseno.py`, con su bandera `ALCALDE_<X>_REDISENO`. Apagada: se ve la vista visual de hoy. `ALCALDE_<X>_VISUAL=0`: la vista base de siempre. |
| C2 | «No hace falta registrar nada: las vistas se descubren por `VISTAS`». | `VISTAS` (`frontend/minijuegos_visual/__init__.py:22-33`) apunta a las clases de hoy. Para que el juego use un rediseño hay que tocar ese archivo. | Un único enganche en `__init__.py` (dueño: Parte A, en su paso A0): tabla `REDISENOS` + función `vista_redisenada()` + 2 líneas en `vista_propia()`. Nadie más toca ese archivo. |
| C3 | Los objetos nuevos deben «imitar `ui.Tarjeta`» para que `CapaVisual.repasar_revision` funcione, «truco ya usado por `Vineta`». | `capa._tarjetas_de` (`capa.py:145-157`) busca con `isinstance(nodo, ui.Tarjeta)`. `Vineta` (`cronologia_visual.py:74`) hereda de `Entity`, NO de `Tarjeta`: el repaso no la encuentra. | Todo objeto marcable nuevo HEREDA de `ui.Tarjeta` (o de `ui.Boton` los botones) en un módulo nuevo; `ui.py` no se toca. |
| C4 | `tests/humo_minijuegos_mundo.py` «debe seguir verde». | Hoy falla de dos maneras (medido el 2026-11-17): con las variables por defecto, `es.minijuego` es `None` (la pantalla previa/tutorial espera; línea 75); con `ALCALDE_MINIJUEGOS_INTRO=0 ALCALDE_TUTORIAL_MISION=0` falla con `AssertionError: CronologiaVisual` porque `resolver()` identifica la vista con `type(v).__name__ == "MinijuegoX"` (líneas 76-135). Solo pasa con `ALCALDE_MISIONES_VISUALES=0 ALCALDE_MINIJUEGOS_INTRO=0 ALCALDE_TUTORIAL_MISION=0` («HUMO MINIJUEGOS OK 47 misiones»), es decir, SIN ninguna capa visual. | El humo existente no se edita. La Parte A crea `tests/humo_minijuegos_visual.py`, que ejecuta el mismo humo identificando la vista por su clase base (MRO). Ese es el humo que vale para el rediseño. El existente se corre con las tres variables a 0 como prueba de que la vista base sigue igual. |
| C5 | La ayuda «?» «abre con clic o Tab». | `Tab` mueve el foco en todas las vistas (`base.py:114`, `contrarreloj.py:83`) y el botón Y / Back del mando manda `tab` (`mando_calculos.py:44-51`). | La ayuda abre y cierra con `h` o `f1` y con clic; `escape` la cierra. Sin botón de mando en esta ronda (decisión D5). |
| C6 | Marco y previa «en los 6»; se valida primero sobre cronología. A la vez: «cronología NO se toca». | Contradicción. Poner el marco en cronología obliga a editar `cronologia_visual.py`. | Cronología no se toca. El marco va en los 5 rediseños. La portada (previa) sí sale en los 6 porque es una pantalla aparte (no toca la vista). |
| C7 | `comic.py` extrae lo duplicado de cronología y cronología pasa a usarlo. | Lo duplicado son `_rgba` y `_triangulo` (3 líneas cada uno, `cronologia_visual.py:46-51`). | Se descarta `comic.py`. Las piezas se escriben nuevas (`piezas.py`, `globos.py`); cronología queda intacta. |
| C8 | «Se rediseña `pantalla_previa.py`». | La escena crea la previa con `PantallaPrevia(...)` dentro de `_mostrar_previa` (`escena_minijuego.py:197-209`). No hay enganche; la previa no recibe el id del minijuego. | `PantallaPrevia` no se reescribe. La Parte B añade al FINAL de `pantalla_previa.py` un enganche de 5 líneas que la envuelve con `portada_caso.envolver()`. El id se deduce del título (función pura). La escena (flujo) no se toca. |
| C9 | Chat: «sustituir el `Text` único del log por burbujas es el cambio más profundo de las vistas base». | No hace falta tocar la vista base: `ChatVisual._pintar_chat` ya la sobrescribe (`chat_visual.py:155-177`). | Las burbujas se dibujan en la clase de rediseño a partir de `self.log`. `chat.py` no se toca. |
| C10 | Señales: pestaña de la lupa con «Cuenta», «Hora», «Promesa». | Las zonas solo traen `id`, `texto`, `lupa`, `falla`, `explica` (`senales_calculos.py:14-16`; datos en `backend/datos/minijuegos_casos.py`). No hay campo de tipo. | Etiqueta corta deducida del texto de `lupa` con una función pura probada sobre los 5 casos (y respaldo: `lupa` recortada). |
| C11 | Contrarreloj: «las tarjetas con barras». | `MinijuegoContrarreloj._sincronizar` (`contrarreloj.py:138-157`) vuelve a poner `enabled` a `filas`, `barras` y `rotulos` EN CADA FRAME. | No se esconden esos objetos: se SUSTITUYEN las listas por objetos propios con la misma interfaz (`enabled`, `fijar_estado`, `fijar_foco`, `fijar(f, tono)`, `text`). |
| C12 | Animaciones de la capa común. | `efectos_ui_calculos.py:12-17`: rebote 0,38 s, temblor 0,42 s, destello 0,45 s, sello 0,34 s. | La regla «≤ 250 ms» es para las transiciones NUEVAS de las piezas. La capa común (`capa.py`, `efectos_ui.py`) no se toca. |
| C13 | Probar con `capturas_minijuegos.py` del scratchpad. | Ese guion escribe en `sitio_web/img/raw` (carpeta de la web) e identifica las vistas por `type(v).__name__ == "MinijuegoX"`, así que con capas visuales no juega ninguna. | Cada parte hace su propio guion de capturas en `scripts/` (ignorado por git) con salida fuera de `sitio_web/` (sección 7.4). |
| C14 | Z de las piezas: no se dice nada. | El banner de resultado de la escena va en z -0,1 (`escena_minijuego.py:274`) y el grafo social en z -0,3; la vista cuelga de `contenido` (z 0). Cualquier pieza con z < -0,1 se pintaría DELANTE del banner. | Toda pieza nueva vive en z ∈ [-0,09, 0,45] respecto a la raíz de la vista (tabla Z de la sección 5.1). |
| C15 | Línea base de la suite: «46 fallos + 6 errores». | Suite completa lanzada el 2026-11-17 a las 13:38: 47 fallos + 6 errores, 1238 pasan, 720 s. PERO a las 13:38:50-13:41 otra sesión cambió archivos de minijuegos (sección 0) mientras corría. Repetidas en una copia LIMPIA de `HEAD` (`git archive`) las pruebas de minijuegos: `test_tutorial_mision_humo` PASA en limpio; las demás de minijuegos fallan igual. Línea base limpia = **46 fallos + 6 errores** (coincide con la nota 58). | Se compara por IDENTIFICADOR de prueba (anexo), no por cuenta. |
| C16 | `tests/humo_tutorial_mision.py` «debe seguir verde». | En `HEAD` limpio pasa (`HUMO TUTORIAL MISION OK`, verificado en copia limpia). Con los cambios sin dueño de la sección 0 falla en el paso 5, línea 169 (`len(es.previa.tarjetas) == 2 and not hasattr(es.previa, "boton_tutorial")`) y ya no llega al paso 7b, el que juega los tutoriales de los 5 minijuegos. | Si el dueño descarta esos cambios (opción 1 de la sección 0), se usa `humo_tutorial_mision.py` tal cual y NO se crea envoltorio. Solo si se adoptan (opción 2) y el paso 5 sigue rojo, la Parte B crea `tests/humo_tutorial_mision_visual.py` (mismo guion cambiando SOLO las aserciones de las líneas 169 y 173 por un aviso, comprobando que la sustitución ocurrió). En lo que sigue, «humo del tutorial» = el que corresponda. |

Afirmaciones del plan base CONFIRMADAS en el código: `Contrarreloj.tecla()` sobrescribe `tecla` y `focables = []` (`contrarreloj.py:65,71`);
el banner ocupa y -0,28 a -0,45 (`escena_minijuego.py:37-38`: Y 0,365, alto 0,17); el pie se esconde al terminar
(`base.py:65`); la capa visual actual no tiene tests (ningún archivo de `tests/` nombra `minijuegos_visual` ni las clases
`*Visual`); `COLORES_ROL_PROPUESTOS` existe y no se usa (`estilo.py:120-125`); `ui.py` y `telefono_marco.py` los usan otras
pantallas.

---

## 2. Estrategia de división elegida y por qué

Opciones evaluadas:

- (a) A construye el kit y B espera. Simple, pero B queda parado hasta que el kit esté, y el kit sigue cambiando mientras A
  lo usa en sus minijuegos: B trabajaría contra un blanco móvil. Descartada.
- (b) Cada parte trae sus piezas en módulos propios y se unifican al final. Ninguna espera, pero se duplican sello, papel,
  botones y paleta, y la unificación final es justo la fase con más riesgo (cambiar piezas de 5 vistas ya probadas).
  Descartada como estrategia principal.
- (c) Paquete 0 mínimo y estable con contrato. Elegida, con una variante: el Paquete 0 se REPARTE. Cada parte entrega
  primero (pasos A0 y B0, en paralelo) los módulos comunes de los que es dueña, con la API del contrato completa aunque el
  dibujo sea mínimo. Mientras hace su A0/B0 ninguna parte necesita nada de la otra. Desde la sincronización S0 la API es
  estable: solo se AÑADEN parámetros opcionales, nunca se quitan ni se renombran. El aspecto fino de cada pieza puede seguir
  mejorando sin romper a nadie.

Por qué (c) repartido: elimina la espera (cada parte empieza por lo suyo), evita duplicar piezas (un solo sello, un solo
papel, una sola paleta), y la integración final es corta porque las dos partes ya usan el mismo kit desde S0. La única
dependencia inevitable es: B usa el kit de papel de A (`piezas.py`) y A usa el marco de B (`marco.py`). Ambas quedan
resueltas con el contrato de la sección 5 y con un respaldo local documentado por si una entrega se retrasa (sección 9.3).

Reparto de esfuerzo (S = 1, S-M = 1,5, M = 2, L = 3):

| Parte | Contenido | Esfuerzo |
|---|---|---|
| A | Kit de papel (`piezas_calculos`, `piezas`) M · enganche `__init__` + humo visual S · Comparar M · Rastrear S-M · Contrarreloj L | 2 + 1 + 2 + 1,5 + 3 = 9,5 |
| B | Marco (`marco_calculos`, `marco`) S-M · humo del tutorial visual (envoltorio) S- · Portada de caso M · Globos S · Chat M · Señales L | 1,5 + 0,5 + 2 + 1 + 2 + 3 = 10 |

Cada parte tiene un L, un M y piezas comunes. Ninguna queda bloqueada: lo que cada una necesita de la otra llega en S0
(el primer bloque de trabajo) y tiene respaldo local.

---

## 3. Reparto de archivos (dueño único)

Regla: un archivo pertenece a UNA parte. Solo su dueño lo crea o lo modifica. La otra parte solo lo IMPORTA (y solo la API
del contrato). Rutas relativas a la raíz del repo.

### 3.1 Parte A

| Acción | Archivo | Qué |
|---|---|---|
| crea | `frontend/minijuegos_visual/piezas_calculos.py` | Puro (sin ursina). Paleta, Z, medidas, geometría. Contrato 5.2. |
| crea | `frontend/minijuegos_visual/piezas.py` | Ursina. Kit de papel. Contrato 5.3. |
| crea | `frontend/minijuegos_visual/comparar_rediseno.py` | `CompararRediseno`. |
| crea | `frontend/minijuegos_visual/comparar_rediseno_calculos.py` | Puro: maquetación de las hojas. |
| crea | `frontend/minijuegos_visual/rastrear_rediseno.py` | `RastrearRediseno`. |
| crea | `frontend/minijuegos_visual/rastrear_rediseno_calculos.py` | Puro. |
| crea | `frontend/minijuegos_visual/contrarreloj_rediseno.py` | `ContrarrelojRediseno`. |
| crea | `frontend/minijuegos_visual/contrarreloj_rediseno_calculos.py` | Puro. |
| crea | `tests/humo_minijuegos_visual.py` | Humo de las 47 misiones con capas visuales (C4). Lo usan las dos partes. |
| crea | `tests/test_a_piezas_*.py` | Pruebas de la Parte A (sección 7.2). |
| crea | `scripts/capturas_rediseno_a.py` | Capturas en ventana real (sección 7.4). |
| modifica | `frontend/minijuegos_visual/__init__.py` | SOLO en A0: `REDISENOS`, `vista_redisenada()` y 2 líneas en `vista_propia()` (5.5). |

### 3.2 Parte B

| Acción | Archivo | Qué |
|---|---|---|
| crea | `frontend/minijuegos_visual/marco_calculos.py` | Puro. Zonas de pantalla y textos del marco. Contrato 5.4. |
| crea | `frontend/minijuegos_visual/marco.py` | `MarcoVisual` (mezcla). Contrato 5.4. |
| crea | `frontend/minijuegos_visual/portada_caso.py` | `PortadaCasoMezcla` y `envolver()`. |
| crea | `frontend/minijuegos_visual/portada_calculos.py` | Puro: id por título, frases cortas, iconos. |
| crea | `frontend/minijuegos_visual/globos.py` | Globo con cola, avatar, `GloboRespuesta`, escribiendo, reloj circular. |
| crea | `frontend/minijuegos_visual/globos_calculos.py` | Puro. |
| crea | `frontend/minijuegos_visual/chat_rediseno.py` | `ChatRediseno`. |
| crea | `frontend/minijuegos_visual/chat_rediseno_calculos.py` | Puro. |
| crea | `frontend/minijuegos_visual/senales_rediseno.py` | `SenalesRediseno`. |
| crea | `frontend/minijuegos_visual/senales_rediseno_calculos.py` | Puro. |
| crea | `tests/test_b_piezas_*.py` | Pruebas de la Parte B. |
| crea (solo si hace falta, C16) | `tests/humo_tutorial_mision_visual.py` | Envoltorio del humo del tutorial sin el paso 5. Lo usan las dos partes. |
| crea | `scripts/capturas_rediseno_b.py` | Capturas en ventana real. |
| modifica | `frontend/minijuegos/pantalla_previa.py` | SOLO añadir al final el enganche de 5 líneas (5.6). Nada más del archivo cambia. |

### 3.3 De nadie (no se tocan)

Todo lo demás. En particular: `frontend/minijuegos/*.py` salvo el enganche anterior (vistas base y `*_calculos`),
`frontend/minijuegos/ui.py`, `frontend/minijuegos/base.py`, `frontend/minijuegos_visual/capa.py`, `trazos.py`,
`pistas_visuales_calculos.py`, `mapa_barrio_calculos.py`, `chat_visual_calculos.py`, `cronologia_vinetas_calculos.py`, los
seis `*_visual.py` actuales, `frontend/efectos_ui.py`, `efectos_ui_calculos.py`, `estilo.py`, `componentes.py`,
`telefono_marco.py`, `mando*.py`, `frontend/escenas/escena_minijuego.py`, `frontend/tutorial_mision_*.py`,
`frontend/registro_*.py`, `backend/**`, `tests/humo_*.py` existentes, `tests/test_*.py` existentes, `main.py`, `docs/*`
salvo estos tres documentos (que tampoco editan las partes), `sitio_web/**`, y los protegidos del proyecto (lista en cada
paquete). No existe `conftest.py` en el repo: nadie lo crea.

Se puede IMPORTAR (sin modificar) lo que haga falta de esos archivos: `ui`, `estilo`, `componentes`, `trazos.Linea`,
`pistas_visuales_calculos`, `mapa_barrio_calculos`, `chat_visual_calculos`, `efectos_ui_calculos`, `telefono_marco`,
`banderas_visuales`, las clases `*Visual` actuales (para heredar de ellas).

---

## 4. Diagrama de dependencias

```
                     (de nadie, solo se importan)
   ui.Tarjeta  ui.Boton  estilo  componentes  banderas_visuales  efectos_ui_calculos  trazos.Linea
        |          |        |         |              |                   |                  |
        +----------+--------+---------+--------------+-------------------+------------------+
                                       |
          +----------------------------+-----------------------------+
          |                                                          |
   PARTE A (paquete 0: A0)                                   PARTE B (paquete 0: B0)
   piezas_calculos.py  (puro)                                marco_calculos.py (puro)
   piezas.py           (TarjetaPapel, BotonSello, sello...)  marco.py          (MarcoVisual)
   __init__.py: REDISENOS + vista_redisenada                 tests/humo_tutorial_mision_visual.py (si C16)
   tests/humo_minijuegos_visual.py                           (pantalla_previa.py: enganche, más tarde en B3)
          |            \                                 /           |
          |             \_____ S0: cada parte importa ___/            |
          |                    lo que la otra entregó                |
          v                                                          v
   comparar_rediseno ----> piezas, marco             globos.py ----> piezas_calculos (paleta)
   rastrear_rediseno ----> piezas, marco             chat_rediseno ----> globos, piezas, marco [hereda de ChatVisual]
   contrarreloj_rediseno -> piezas, marco            senales_rediseno -> globos, piezas, marco
        [hereda de ContrarrelojVisual]               portada_caso ----> piezas, portada_calculos
          |                                                          |
          +-------------------- S3 / Integración --------------------+
                (las dos partes encienden sus banderas; humos, suite, capturas, auditoría)
```

Dependencias cruzadas (las únicas):
- A necesita de B: `marco.MarcoVisual` y `marco_calculos.ZONA_*` (para sus 3 vistas).
- B necesita de A: `piezas_calculos.PALETA/Z/...`, `piezas.TarjetaPapel`, `piezas.BotonSello`, `piezas.sello`, `piezas.papel`,
  `piezas.cinta`, `piezas.chincheta`, `piezas.chip`, `piezas.marca_ok/marca_mal/tachon`.
- B necesita de A también el enganche de `__init__.py` para ver sus vistas en el juego (antes de S0 puede instanciarlas a
  mano en sus pruebas y capturas).

---

## 5. Contrato de piezas compartidas (fijo desde S0)

Unidades: `camera.ui` (alto 1, ancho 16/9 ≈ 1,778; centro 0,0; x de -0,889 a 0,889; y de -0,5 a 0,5). «px» = píxeles de
referencia de una pantalla de 600 de alto: `px / 600` unidades (`componentes.a_unidades`, `componentes.py:45`); el texto se
escala con `componentes.escala_fuente(px)`. Colores: tuplas RGB 0-255. Ángulos en grados (`rotation_z`, positivo = horario
en Ursina). Todo módulo de contrato lleva `CONTRATO = 1` a nivel de módulo; si un día cambia algo incompatible (no debería),
sube a 2 y se avisa (sección 10).

### 5.1 Zonas de pantalla y capas

| Zona | y arriba | y abajo | Uso |
|---|---|---|---|
| Barra del marco | 0,50 | 0,41 | Pestaña de título, cinta del rumor, botón «?» |
| Zona de juego (revisión) | 0,40 | -0,27 | Objetos y piezas que muestran estado al terminar |
| Zona de controles | -0,27 | -0,42 | Botones; el banner (y -0,28 a -0,45) los tapa al terminar, aceptado |
| Ancho útil | x -0,83 | x 0,83 | 1,66 de ancho |

Sin marco (bandera del marco apagada) la zona de juego es la de la base: 0,30 a -0,27 (`base.py:19-20`).

Capas Z respecto a la raíz de la vista (menor = más delante). Nunca menos de -0,09 (C14):

| Nombre (`piezas_calculos.Z[...]`) | z | Qué |
|---|---|---|
| `fondo` | 0,45 | Mesa de la ladera (fondo del marco) |
| `objeto` | 0,20 | Hoja, corcho, móvil, mapa, captura |
| `pieza` | 0,00 | Tarjetas/notas/globos (sus capas internas van de +0,004 a -0,03, como `ui.Tarjeta`) |
| `decor` | -0,04 | Cinta, chincheta, hilo, chip |
| `marca` | -0,05 | Resaltador, tachón, aro, palomita, cruz |
| `sello` | -0,06 | Sellos de pieza (RARO, FUENTE, FRENADA...) |
| `foco` | -0,07 | Lupa, halo de foco que se mueve |
| `marco` | -0,08 | Pestaña, cinta del rumor, botón «?» |
| `ayuda` | -0,09 | Papelito de ayuda abierto |

El sello y las estrellas finales de la capa común (`efectos_ui`) van en z -0,05/-0,04 dentro de su entidad: cada vista elige
`posicion_sello()`/`posicion_estrellas()` donde no tape texto de revisión.

### 5.2 `frontend/minijuegos_visual/piezas_calculos.py` (Parte A, puro, sin ursina)

```python
CONTRATO = 1

PALETA = {                       # RGB 0-255. Valores fijos del contrato.
    "tinta": (18, 20, 32),            # = estilo.TINTA
    "papel": (250, 244, 228),         # = estilo.PAPEL, crema
    "papel_viejo": (232, 220, 188),
    "papel_blanco": (252, 250, 244),  # globos
    "corcho": (150, 106, 66), "corcho_oscuro": (118, 80, 48),
    "mesa": (28, 31, 44), "mesa_franja": (34, 38, 54),
    "amarillo": (255, 220, 60),       # = estilo.COLOR_ACENTO: lo importante / seleccionable ahora / foco
    "resaltador": (255, 236, 60),     # con alfa 0,45
    "cian": (70, 220, 255),           # = estilo.ACENTO_SECUNDARIO: camino e información. NUNCA texto sobre papel
    "rojo": (214, 62, 62),            # = estilo.ESTADO_ERROR: error, bulo, hilo. Rellenos y trazos
    "rojo_tinta": (170, 30, 30),      # texto/trazo rojo SOBRE papel (contraste 6,6 con papel)
    "verde": (80, 190, 110),          # = estilo.ESTADO_EXITO: rellenos de acierto
    "verde_tinta": (28, 112, 56),     # texto/trazo verde sobre papel (5,6)
    "azul_secundario": (70, 90, 150), # = estilo.COLOR_BOTON: solo acciones secundarias
    "azul_tinta": (30, 80, 150),      # texto azul sobre papel (7,2)
    "tenue_papel": (96, 90, 80),      # texto secundario sobre papel (6,2)
    "texto_claro": (235, 235, 240), "texto_tenue": (170, 172, 190),   # sobre fondos oscuros
}
Z = {"fondo": 0.45, "objeto": 0.20, "pieza": 0.0, "decor": -0.04, "marca": -0.05, "sello": -0.06,
     "foco": -0.07, "marco": -0.08, "ayuda": -0.09}
PX_CUERPO_MIN = 16        # D1
PX_ETIQUETA_MIN = 13      # D1
BORDE_PX = 3              # borde de tinta de pieza (estilo.GROSOR_BORDE_PX)
BORDE_CHIP_PX = 2
SOMBRA_PX = (4, -5)       # sombra plana (estilo.DESPLAZAMIENTO_SOMBRA_PX), alfa 160/255
ROTACION_MAX = 2.0        # grados, decorativa
DUR_TRANSICION = 0.25     # s, tope de toda transición nueva de pieza
DUR_RESALTADOR = 0.18     # s

def a_u(px: float) -> float                       # px / 600
def rotacion_decorativa(semilla: str, reducir: bool = False) -> float
    # determinista en [-ROTACION_MAX, ROTACION_MAX] (hash estable, p. ej. zlib.crc32; NO hash()); 0.0 si reducir
def sombra_offset() -> tuple[float, float]       # (a_u(4), a_u(-5))
def avance(t: float, dur: float = DUR_TRANSICION, reducir: bool = False) -> float   # 0..1, suavizado; 1.0 si reducir
def tono_reloj(fraccion_restante: float) -> str  # "cian" si > 0,5; "amarillo" si > 0,25; "rojo" si no
def recortar(texto: str, maximo: int) -> str     # corta en palabra y añade «…» (U+2026) si no cabe
def esquina_doblada(ancho: float, alto: float, lado: float) -> list[tuple[float, float]]   # 3 vértices, esquina sup. der.
def discontinua(a, b, trazo: float = 0.012, hueco: float = 0.008) -> list[tuple[tuple, tuple]]
def aro_discontinuo(rx: float, ry: float, n: int = 24) -> list[tuple[tuple, tuple]]    # segmentos alternos de una elipse
def arco(cx, cy, r, desde: float, hasta: float, n: int = 24) -> list[tuple[float, float]]
def triangulos_abanico(n_vertices: int) -> list[tuple[int, int, int]]                 # polígono convexo
def contraste_ok(texto_rgb, fondo_rgb, minimo: float = 4.5) -> bool                    # usa estilo.contraste
```

### 5.3 `frontend/minijuegos_visual/piezas.py` (Parte A, Ursina)

Toda función devuelve una `Entity` hija de `padre`, con `position` = CENTRO de la pieza, y expone `.ancho` y `.alto` en
unidades. Bordes de tinta = capa de tinta DETRÁS de la cara (como `componentes.panel_tinta`), nunca líneas (el grosor de
`Mesh(mode="line")` no está garantizado en macOS). Nada de texto encima de corcho, trama o mesa: siempre papel debajo.

```python
CONTRATO = 1

def rgba(tono, alfa: float = 1.0)                          # tupla RGB o nombre de PALETA -> color de Ursina
def sombra_plana(padre, ancho, alto, radio_px=6, position=(0, 0), z=None) -> Entity
def papel(padre, ancho, alto, tono="papel", position=(0, 0), z=Z["objeto"], radio_px=4, rotacion=0.0,
          esquina=False, sombra=True, borde_px=BORDE_PX) -> Entity            # hijos .sombra .borde .fondo
def cinta(padre, ancho, alto=0.05, position=(0, 0), z=Z["decor"], rotacion=0.0, tono="amarillo",
          chinchetas=2) -> Entity                                              # cinta con 0-2 chinchetas
def chincheta(padre, position=(0, 0), z=Z["decor"], tono="rojo") -> Entity     # diámetro 0,024
def chip(padre, texto, px=13, tono="papel", position=(0, 0), z=Z["decor"], borde_px=BORDE_CHIP_PX) -> Entity  # .texto
def sello(padre, texto, tono="rojo_tinta", px=22, position=(0, 0), z=Z["sello"], rotacion=-8.0, ancho=None) -> Sello
class Sello(Entity):
    def golpear(self, retardo: float = 0.0) -> None      # cae y golpea en DUR_TRANSICION (usa efectos_ui_calculos.caida_sello(t, dur=0.25))
    def avanzar(self, dt: float, reducir: bool = False) -> None
    def fijar_alfa(self, alfa: float) -> None
def marca_ok(padre, position=(0, 0), lado=0.03, z=Z["marca"], tono="verde_tinta") -> Entity   # palomita con 2 quads
def marca_mal(padre, position=(0, 0), lado=0.03, z=Z["marca"], tono="rojo_tinta") -> Entity   # aspa con 2 quads
def tachon(padre, ancho, position=(0, 0), z=Z["marca"], tono="rojo_tinta", grosor_px=3) -> Entity
def aro(padre, ancho, alto, position=(0, 0), z=Z["marca"], tono="rojo_tinta", discontinuo=True) -> Entity
def resaltador(padre, ancho, alto, position=(0, 0), z=Z["marca"]) -> Resaltador
class Resaltador(Entity):
    def barrer(self) -> None                             # crece de izquierda a derecha en DUR_RESALTADOR
    def quitar(self) -> None
    def avanzar(self, dt: float, reducir: bool = False) -> None
def discontinua(padre, a, b, tono="cian", grosor_px=2, z=Z["decor"]) -> Entity
def poligono(padre, puntos, tono, z=0.0) -> Entity
def arco_grueso(padre, cx, cy, r, desde, hasta, tono, grosor_px=3, z=0.0) -> Entity

class TarjetaPapel(ui.Tarjeta):
    """ES una ui.Tarjeta (la encuentran capa._tarjetas_de, el tutorial y los humos). Misma firma posicional que
    ui.Tarjeta y, al final, opciones de papel."""
    def __init__(self, ancho, alto, cuerpo="", titulo="", px=17, px_titulo=13, tono=None, al_clic=None,
                 al_cursor=None, negrita_cuerpo=False, margen_px=10, reserva=0.0,
                 papel="papel", rotacion=0.0, esquina=False, con_borde=True, **opciones)
    # Hereda: estado, habilitada, al_clic, al_cursor, fijar_estado(estado, etiqueta=None), fijar_foco(v),
    #         fijar_texto_etiqueta(t), titulo, cuerpo, etiqueta, golpe, ancho, alto, ESTADOS.
    # Sobrescribe _pintar(): cara de papel + borde de tinta; NUNCA escribe «>>».
    #   foco: halo amarillo de 5 px por fuera + sombra 1,5 veces más larga (forma, no solo color)
    #   marcada/seleccionada: etiqueta en chip amarillo con texto de tinta (la etiqueta que pase la vista)
    #   correcta/encontrada: banda verde alfa 0,25 + marca_ok + etiqueta en verde_tinta
    #   incorrecta/falsa_alarma/propagada/alterada: banda roja alfa 0,2 + marca_mal + etiqueta en rojo_tinta
    #   perdida: aro rojo discontinuo + etiqueta «TE LA PERDISTE» en rojo_tinta
    #   descartada: papel apagado (alfa 0,55) + tachón + etiqueta
    #   frenada / liberada: chip con la etiqueta (azul_tinta / verde_tinta)
    # Ojo: ui.Tarjeta.__init__ llama a _pintar() antes de que existan las capas de papel: _pintar() comprueba
    # getattr(self, "_papel_listo", False) y el __init__ de TarjetaPapel lo llama otra vez al final.

class BotonSello(ui.Boton):
    """ES un ui.Boton. Botón con forma de sello de tinta."""
    def __init__(self, etiqueta, al_clic, ancho=0.30, alto=0.07, px=18, primario=False, icono=None, **opciones)
    # Hereda: habilitado, al_clic, fijar_foco, fijar_habilitado, fijar_etiqueta, texto, golpe.
    # primario: cara amarilla, texto tinta. Secundario: cara de papel, texto tinta. Deshabilitado: papel_viejo,
    # texto tenue_papel, sin sombra. Foco: halo amarillo de 5 px + sombra más larga; el texto NO lleva «>>».
    # icono: None | "mano" | "flecha" | "lupa" | "visto" (dibujado con quads; nunca un glifo Unicode).
```

### 5.4 `marco_calculos.py` y `marco.py` (Parte B)

```python
# frontend/minijuegos_visual/marco_calculos.py (puro)
CONTRATO = 1
ZONA_JUEGO = (0.40, -0.27)            # (y arriba, y abajo) con marco
ZONA_CONTROLES = (-0.27, -0.42)
ZONA_JUEGO_SIN_MARCO = (0.30, -0.27)  # = base.Y_CONTENIDO_ARRIBA .. Y_CONTENIDO_ABAJO
X_UTIL = (-0.83, 0.83)
PESTANA = {"x_izq": -0.83, "y": 0.468, "alto": 0.044, "px": 15}
CINTA_RUMOR = {"cx": 0.0, "cy": 0.445, "ancho_max": 1.10, "alto": 0.05, "px": 16}
BOTON_AYUDA = {"cx": 0.80, "cy": 0.445, "diametro": 0.062, "px": 22}
RUMOR_MAX = 90
TECLAS_ABRIR_AYUDA = ("h", "f1")
TECLA_CERRAR_AYUDA = "escape"
def titulo_corto(titulo: str) -> str                  # lo que va antes de «:»; «Contrarreloj», «Chat del barrio»
def recortar_rumor(rumor: str, maximo: int = RUMOR_MAX) -> tuple[str, bool]   # (texto, ¿se recortó?)
def teclas_de_ayuda(ayuda: str, maximo: int = 4) -> list[str]                  # trozos de AYUDA separados por 2+ espacios
def zona_juego(marco_activo: bool) -> tuple[float, float]

# frontend/minijuegos_visual/marco.py (Ursina)
CONTRATO = 1
MARCO_VISUAL = True                     # bandera: ALCALDE_MARCO_VISUAL
VARIABLE = "ALCALDE_MARCO_VISUAL"
class MarcoVisual:
    """Mezcla. Va PRIMERA en las bases: class XRediseno(MarcoVisual, CapaVisual, MinijuegoX) o
    class XRediseno(MarcoVisual, XVisual)."""
    REGLA_CORTA = ""                    # cada vista la define: una frase de ≤ 90 caracteres
    def lineas_ayuda_extra(self) -> list[str]   # gancho; por defecto []. Contrarreloj lo usa para la glosa de lugares (D4)
    def _encabezado(self) -> None       # super()._encabezado() y luego monta el marco (guardián propio)
    def marco_activo(self) -> bool
    def zona_juego(self) -> tuple[float, float]       # marco_calculos.zona_juego(self.marco_activo())
    def tecla(self, k) -> bool          # h/f1: abre/cierra ayuda; escape: la cierra si está abierta; si no, super().tecla(k)
    ayuda_abierta: bool                 # atributo
    # Conserva self.rumor y self.pie (la base los usa: base.py:65); solo los esconde.
    # Guardián propio (_marco_roto): un fallo avisa una vez (bv.avisar_una_vez("marco_visual", e)), vuelve a enseñar
    # título, rumor y pie, y marco_activo() pasa a False.
    # La ayuda NO es modal y NO para el tiempo: las demás teclas siguen llegando al juego.
```

Orden de llamada (importa): `Minijuego.empezar` llama a `_encabezado()` ANTES de `construir()` (`base.py:50-51`), y la capa
común se monta después (`capa.py:44-46`). Por eso `zona_juego()` ya es válida dentro de `construir()`.

### 5.5 Enganche en `frontend/minijuegos_visual/__init__.py` (Parte A, paso A0)

```python
REDISENOS = {   # id -> (módulo, clase, constante de bandera EN ese módulo, variable ALCALDE_*)
    "comparar": ("frontend.minijuegos_visual.comparar_rediseno", "CompararRediseno", "COMPARAR_REDISENO",
                 "ALCALDE_COMPARAR_REDISENO"),
    "rastrear": ("frontend.minijuegos_visual.rastrear_rediseno", "RastrearRediseno", "RASTREAR_REDISENO",
                 "ALCALDE_RASTREAR_REDISENO"),
    "contrarreloj": ("frontend.minijuegos_visual.contrarreloj_rediseno", "ContrarrelojRediseno",
                     "CONTRARRELOJ_REDISENO", "ALCALDE_CONTRARRELOJ_REDISENO"),
    "chat": ("frontend.minijuegos_visual.chat_rediseno", "ChatRediseno", "CHAT_REDISENO", "ALCALDE_CHAT_REDISENO"),
    "senales": ("frontend.minijuegos_visual.senales_rediseno", "SenalesRediseno", "SENALES_REDISENO",
                "ALCALDE_SENALES_REDISENO"),
}

def vista_redisenada(minijuego_id):
    """Clase del rediseño si existe, su módulo carga y su bandera está encendida; None si no. NUNCA lanza: un fallo
    avisa una vez (clave f"rediseno_{minijuego_id}") y devuelve None (se usa la vista visual de hoy)."""

# En vista_propia(), justo después de `if not bv.activa(True, variable): return None` (línea 48):
    nueva = vista_redisenada(minijuego_id)
    if nueva is not None:
        return nueva
```

Consecuencia: `ALCALDE_<X>_VISUAL=0` sigue dando la vista base (no se llega a mirar el rediseño); `ALCALDE_<X>_REDISENO=0`
o la constante a `False` da la vista visual de hoy; los dos encendidos dan el rediseño. Cada módulo de rediseño nace con
`<X>_REDISENO = False` y su dueño lo pasa a `True` solo en S3 (sección 9).

### 5.6 Enganche de la portada en `frontend/minijuegos/pantalla_previa.py` (Parte B, paso B3)

Se AÑADE al final del archivo, sin tocar nada de lo anterior:

```python
# Portada de caso (frontend/minijuegos_visual/portada_caso.py, ALCALDE_PORTADA_VISUAL=0 la apaga): misma interfaz.
try:
    from frontend.minijuegos_visual.portada_caso import envolver as _envolver_portada
    PantallaPrevia = _envolver_portada(PantallaPrevia)
except Exception:                        # noqa: BLE001  sin portada: la previa de siempre
    pass
```

`envolver(clase)` devuelve `type("PortadaCaso", (PortadaCasoMezcla, clase), {})` sin importar `pantalla_previa` (no hay
import circular). `PortadaCasoMezcla.__init__` llama a `super().__init__(...)` con los mismos argumentos y SOLO si la bandera
está encendida al construir viste la pantalla. Conserva: `tarjetas` (misma longitud: 1 en versión corta, 2 en completa),
`boton`, `boton_tutorial` (solo si hay `al_ver_tutorial`), `al_empezar`, `al_ver_tutorial`, `_empezar()`, `_ver_tutorial()`
(los usa `tests/humo_tutorial_mision.py:129-169,223-225`).

### 5.7 Contrato público de cada vista (no cambia; lo usan el tutorial y los humos)

Toda clase de rediseño conserva, con los mismos nombres y efectos:
- Todas: `partida`, `focables` (mismo orden y misma longitud que la vista base), `foco`, `poner_foco(i)`, `tecla(k)`,
  `avanzar(dt)`, `terminar(r)`, `terminado`, `resultado`, `es_tutorial`, `TITULO` (sin cambiar el texto), `AYUDA`.
- Rastrear: `elegir(i)`, `focables` (3 notas), teclas 1-3, `rastro`.
- Comparar: `tarjetas`, `izq`, `alternar(i)`, `confirmar()`, `sin_diferencias()`, `boton_confirmar`, `boton_igual`, c, n.
- Chat: `opciones` (cada una con `fijar_estado("incorrecta", "ENTREGA ESE DATO")`, lo usa
  `tutorial_mision_minijuegos.py:264`), `responder(i)`, `log`, teclas 1-3.
- Señales: `tarjetas`, `alternar(i)`, `confirmar()`, `sin_senales()`, `boton_confirmar`, `boton_nada`, c, n.
- Contrarreloj: `filas`, `barras`, `rotulos`, `frenar()`, `dejar()`, `boton_frenar`, `boton_pasar`, `foco`, `tecla()`
  (sobrescrita), `focables == []`.

Reglas que el tutorial impone (`tutorial_mision_minijuegos.py`):
- Sustituye en la INSTANCIA `vista.terminar` (Comparar, Señales, Cronología), `vista.responder` (Chat) y en la partida
  `elegir`, `frenar`, `dejar_pasar`, `declarar_sin_*`. Por eso: los clics se cablean con lambdas que buscan el método al
  llamar (`al_clic=lambda i=i: self.responder(i)`), nunca guardando el método enlazado al construir; y las vistas llaman
  siempre a `self.partida.<método>` y a `self.terminar(...)`.
- `elemento(vista, foco)` señala `focables[foco]` (o `filas`/`tarjetas`) y mide su caja con `getTightBounds`
  (`tutorial_mision_vista.py:111-121`): las piezas deben tener su caja de golpe del tamaño visible.

Cómo sustituir los objetos de la base sin romper nada (patrón obligatorio): se llama a `super()`, se construyen TODAS las
piezas nuevas, y solo cuando todo salió bien se cambian las listas (`self.tarjetas`, `self.focables`, `self.izq`,
`self.opciones`, `self.filas`, `self.barras`, `self.rotulos`, `self.boton_*`) y se destruyen los originales con
`componentes.destruir_arbol`. Si algo falla antes del cambio, se borra lo nuevo a medias y queda la vista heredada intacta.

---

## 6. Decisiones pendientes del plan base: valores por defecto (decidido por defecto, revisable)

Las dos partes usan EXACTAMENTE estos valores. Si el dueño cambia alguno, cambia aquí y en un solo sitio del código (la
constante indicada).

| # | Decisión | Valor por defecto | Dónde vive |
|---|---|---|---|
| D1 | Tamaño mínimo de texto | Cuerpo 16 px de referencia (≈ 25 px reales a 956 de alto), etiquetas 13 px; nada por debajo de 13. Los 10-12 px de hoy en el mapa y las notas suben a 13. | `piezas_calculos.PX_CUERPO_MIN`, `PX_ETIQUETA_MIN` |
| D2 | Sello «ORIGINAL» en Comparar | Sí, pequeño (16 px, rotado -8°) en la esquina de la hoja original. Decir cuál hoja es la buena no resuelve nada: hay que hallar qué cambió. | `comparar_rediseno.SELLO_ORIGINAL = True` |
| D3 | Paleta de roles para avatares | Se usa `estilo.COLORES_ROL_PROPUESTOS` cuando el nombre del remitente coincide con un rol (ciudadano, periodista, influencer, candidato). Si no, color estable por nombre (crc32) de una lista de 4 tonos COPIADOS en `globos_calculos` (los mismos valores que `chat_visual.TONOS_AVATAR`: (120,170,230), (230,170,90), (170,130,220), (110,200,170); no importar `chat_visual` desde un módulo puro: importa ursina). Siempre con la inicial en tinta encima (contraste 5,1-14,2); el nombre del remitente, en tinta (los colores de rol sobre blanco no llegan a 4,5). | `globos_calculos.color_avatar()` |
| D4 | Nombres en portugués del mapa | Se mantienen (Morro, Feira, Escola, Praça, Igreja, Ponto, Campinho; `mapa_barrio_calculos.py:12-20`) a 13 px, con su glosa en español en la ayuda «?» de Contrarreloj («Feira = mercado; Praça = plaza; Igreja = iglesia; Ponto = parada; Campinho = cancha; Escola = escuela; Morro = cerro»). | `contrarreloj_rediseno.GLOSA_LUGARES` |
| D5 | Quitar el pie de teclas | Sí: el pie se esconde y las teclas pasan al papelito «?» (abre con h, F1 o clic; cierra con Esc). La pantalla previa sigue diciendo las teclas. Mando: sin botón propio esta ronda (Y/Back mandan `tab`, que mueve el foco). | `marco.MarcoVisual` |
| D6 | Ritmo | En paralelo por partes, cada minijuego detrás de su bandera `ALCALDE_<X>_REDISENO` (constante a `False` hasta S3). Dentro de cada parte, un minijuego por vez. | Constantes `<X>_REDISENO` |

---

## 7. Convenciones comunes

### 7.1 Banderas y avisos

| Bandera | Constante (módulo) | Dueño |
|---|---|---|
| `ALCALDE_COMPARAR_REDISENO` | `COMPARAR_REDISENO` (`comparar_rediseno.py`) | A |
| `ALCALDE_RASTREAR_REDISENO` | `RASTREAR_REDISENO` (`rastrear_rediseno.py`) | A |
| `ALCALDE_CONTRARRELOJ_REDISENO` | `CONTRARRELOJ_REDISENO` (`contrarreloj_rediseno.py`) | A |
| `ALCALDE_CHAT_REDISENO` | `CHAT_REDISENO` (`chat_rediseno.py`) | B |
| `ALCALDE_SENALES_REDISENO` | `SENALES_REDISENO` (`senales_rediseno.py`) | B |
| `ALCALDE_MARCO_VISUAL` | `MARCO_VISUAL = True` (`marco.py`; solo actúa dentro de las clases de rediseño) | B |
| `ALCALDE_PORTADA_VISUAL` | `PORTADA_VISUAL` (`portada_caso.py`; `False` hasta S3) | B |

Las constantes `<X>_REDISENO` nacen en `False` y su dueño las pasa a `True` en S3.

Todas se leen con `banderas_visuales.activa(CONSTANTE, VARIABLE)`, que exige además la maestra
`ALCALDE_MISIONES_VISUALES`. Claves de `bv.avisar_una_vez`: `rediseno_<x>` (montaje/carga), `rediseno_<x>_animar`
(bucle), `marco_visual`, `portada_visual`, `piezas_<nombre>`. Nunca la misma clave en dos partes.

### 7.2 Pruebas

- Nombres: Parte A `tests/test_a_piezas_<tema>.py`; Parte B `tests/test_b_piezas_<tema>.py`. Funciones `test_...` en
  español. Ningún archivo de pruebas de una parte importa pruebas de la otra.
- Puras (sin ursina): todo `*_calculos.py` nuevo tiene su archivo de pruebas y no importa ursina (se comprueba con
  `venv/bin/python -c "import sys, frontend.minijuegos_visual.<m>; assert 'ursina' not in sys.modules"`).
- Con ursina offscreen: un archivo por parte (`test_a_piezas_ursina.py`, `test_b_piezas_ursina.py`) que crea la app sin
  ventana (`loadPrcFileData("", "window-type offscreen\naudio-library-name null")`) y construye cada vista de rediseño
  con un caso real de `backend/datos/minijuegos_casos.py`, juega bien y mal llamando al contrato público, y comprueba:
  `focables` con la longitud de la base, todas las piezas marcables son `ui.Tarjeta`, nada con z < -0,09, todo texto
  ≥ 13 px, y que forzar un fallo en el montaje deja la vista heredada funcionando.
- Humos nuevos (los corren las dos partes): `tests/humo_minijuegos_visual.py` (de A) y el humo del tutorial (C16; envoltorio de B solo si hace falta). Los humos existentes se corren tal cual, sin editarlos (sección 8).

### 7.3 Estilo de código

Textos de la interfaz y comentarios en español. Sin emojis ni flechas Unicode en la UI (tampoco «>>» en las piezas nuevas;
el foco se ve por forma). Cabecera de módulo como las de hoy (qué hace, bandera, guardián, reducir movimiento). Enganches
mínimos con `try/except` y parámetros por defecto. Nada de cifras de indicadores a la vista. Ningún estado solo por color.

### 7.4 Capturas en ventana real

- Guion propio por parte: `scripts/capturas_rediseno_a.py` y `scripts/capturas_rediseno_b.py` (carpeta `scripts/`,
  ignorada por git). Base: el guion de ejemplo
  `/private/tmp/claude-501/-Users-dg-amir/2f90e5e0-7698-4b72-a00a-748eb1a8943f/scratchpad/real/capturas_minijuegos.py`,
  con tres cambios: (1) salida en `~/Documents/Obsidian-Alcalde-Digital/adjuntos/rediseno-minijuegos/<a|b>/` (nunca en
  `sitio_web/`); (2) elegir el minijuego forzando la asignación como hace `tests/humo_tutorial_mision.py:239`
  (`asig.asignar = lambda mision, **k: "<id>"`) en vez de buscar misiones; (3) identificar la vista por su clase base:
  `next(k.__name__ for k in type(v).__mro__ if k.__name__.startswith("Minijuego") and k.__name__ != "Minijuego")`.
- Si ese archivo del scratchpad no se puede leer desde otra sesión, el guion se escribe de cero con el mismo esquema
  (`main.crear_aplicacion(0, 0)`, `gestor.cambiar_a(MINIJUEGO, jugador=..., estado=..., mision=..., al_terminar=lambda *a, **k: None,
  grafo_social=None, marco=True, lugar="Ciudad Nova")`, `app.win.saveScreenshot(...)`).
- Estados a capturar por minijuego: previa, inicio, foco, marcado, error, acierto, tiempo casi agotado (Chat y
  Contrarreloj), cierre (tras el sello), ayuda «?» abierta; y la serie completa otra vez con `ALCALDE_REDUCIR_MOVIMIENTO=1`.
  Nombre: `<id>_<estado>[_rm].png`.
- Ventana real: `window.fullscreen = True` como en el ejemplo. Revisar cada imagen con la herramienta de leer imágenes.

---

## 8. Reglas sobre pruebas compartidas y línea base

### 8.1 Quién toca qué

- `tests/humo_*.py` existentes y `tests/test_*.py` existentes: NADIE los edita. Si uno necesita otra cosa, se crea un archivo
  NUEVO con prefijo de parte (o, para el humo visual, el de la Parte A).
- `conftest.py`, `pytest.ini`: no existen; nadie los crea.
- Cada parte puede AÑADIR archivos nuevos en `tests/` y `scripts/` con su prefijo (`test_a_`, `test_b_`, `capturas_rediseno_a`,
  `capturas_rediseno_b`); además la Parte A crea `tests/humo_minijuegos_visual.py` y la Parte B
  `tests/humo_tutorial_mision_visual.py` solo si hace falta (C16). Los humos nuevos son de su dueño pero los corren las dos partes.

### 8.2 Cómo se corre

- Un solo proceso pesado a la vez en la máquina (las dos partes comparten CPU y los humos tienen tope de 600 s): antes de
  correr la suite completa o un humo, tomar el cerrojo con `mkdir tests/.cerrojo_suite` (falla si ya existe: esperar y
  reintentar cada 60 s; si tu entorno bloquea `sleep`, usa la herramienta Monitor con una condición de espera) y soltarlo con `rmdir tests/.cerrojo_suite` al acabar (también si falla).
  `tests/` está ignorada por git: el cerrojo no ensucia el repo.
- Suite completa: `venv/bin/python -m pytest -q -p no:cacheprovider -rfE tests > <tu scratchpad>/suite.txt 2>&1`, y
  luego los ID: `grep -E "^(FAILED|ERROR) tests/" suite.txt | sed -E 's/ - .*//' | sort` frente al anexo.
- Humo base (prueba de que la vista base sigue igual): `ALCALDE_MAPA_GRANDE=1 ALCALDE_TUTORIAL=0 ALCALDE_RUTAS=0
  ALCALDE_MINIJUEGOS_INTRO=0 ALCALDE_TUTORIAL_MISION=0 ALCALDE_MISIONES_VISUALES=0 venv/bin/python
  tests/humo_minijuegos_mundo.py` -> debe imprimir `HUMO MINIJUEGOS OK 47 misiones`.
- Humo visual: `ALCALDE_MAPA_GRANDE=1 ALCALDE_TUTORIAL=0 ALCALDE_RUTAS=0 venv/bin/python tests/humo_minijuegos_visual.py`
  (con las banderas de rediseño que se quieran probar) -> `HUMO MINIJUEGOS VISUAL OK 47 misiones` + la lista de clases usadas.
- Humo del tutorial: `ALCALDE_MAPA_GRANDE=1 venv/bin/python tests/humo_tutorial_mision.py` (o su envoltorio
  `tests/humo_tutorial_mision_visual.py` si existe, ver C16) ->
  `HUMO TUTORIAL MISION OK` (pasos 6, 7, 7b y 8; el 7b juega el tutorial de rastrear, comparar, cronología, chat y señales
  con las vistas que den las banderas; el 8, Contrarreloj).
- Duración medida de la suite completa: 720 s (12 min) sin otra carga.

### 8.3 Línea base

Ver el anexo al final de este documento (fallos y errores medidos el 2026-11-17 ANTES de cualquier cambio). Comparación por
IDENTIFICADOR: un ID que falla y ya estaba en la línea base no es tuyo; un ID nuevo que falla en un archivo tuyo, se arregla;
un ID nuevo que falla en un archivo de nadie, se investiga (sección 10) antes de seguir; uno en un archivo de la otra parte
se le avisa.

---

## 9. Orden y puntos de sincronización

### 9.1 Calendario

| Punto | Parte A entrega | Parte B entrega | Cómo se comprueba |
|---|---|---|---|
| S0 (fin del primer bloque) | A0: `piezas_calculos.py` + `piezas.py` con TODA la API 5.2/5.3 (dibujo mínimo válido), sus pruebas puras, el enganche 5.5 en `__init__.py`, `tests/humo_minijuegos_visual.py` | B0: `marco_calculos.py` + `marco.py` con TODA la API 5.4 (pestaña, cinta de rumor, «?» y papelito funcionando aunque sea sencillo), sus pruebas puras, y el humo del tutorial comprobado (C16) | `venv/bin/python -c "from frontend.minijuegos_visual import piezas_calculos as c, marco_calculos as m; assert c.CONTRATO == m.CONTRATO == 1"` y, con ursina offscreen, `import frontend.minijuegos_visual.piezas, frontend.minijuegos_visual.marco`. Cada parte escribe «S0 entregado» con la hora en su nota de la bóveda. |
| S1 | Comparar terminado (bandera aún en False) | Globos + Chat terminados (bandera en False) | Pruebas propias verdes; humo visual con su bandera encendida por variable; capturas revisadas. |
| S2 | Rastrear y Contrarreloj terminados | Señales y Portada terminadas (enganche 5.6 añadido) | Igual que S1; humo del tutorial (C16) verde con las banderas de la parte a 1. |
| S3 | Pasada transversal de A; constantes `*_REDISENO = True` en sus 3 módulos | Pasada transversal de B; `CHAT_REDISENO`, `SENALES_REDISENO`, `PORTADA_VISUAL = True` | Suite completa contra la línea base, los humos de 8.2, auditorías de la parte. «S3 entregado» en la nota. |
| I (integración) | — | — | Checklist de la sección 11, la hace quien integre (abajo). |

No hay que esperar a la otra parte entre S1 y S3: cada parte avanza a su ritmo. La única espera posible es en S0, y tiene
respaldo (9.3).

### 9.2 Quién integra

La sesión principal del dueño (la que repartió el trabajo). Si no la hay, la Parte que llegue segunda a S3 hace la
integración, siguiendo la sección 11, sin editar archivos de la otra parte: si encuentra un fallo en ellos, lo anota en la
nota de la otra parte y lo arregla su dueño.

### 9.3 Si la entrega de S0 de la otra parte se retrasa

- Nadie espera de brazos cruzados: hay trabajo que no depende de la otra parte (cálculos puros y sus pruebas, capturas de
  línea base, guion de capturas, maquetación con rectángulos).
- Si hace falta pintar antes de S0, se usa un respaldo LOCAL dentro del módulo propio, en un bloque marcado:

  ```python
  # --- RESPALDO HASTA S0 (quitar al integrar): import de la otra parte con respaldo mínimo ---
  try:
      from frontend.minijuegos_visual.marco import MarcoVisual
  except ImportError:
      class MarcoVisual:  # noqa: D101  respaldo: sin marco, zona de juego de la base
          def zona_juego(self):
              return (0.30, -0.27)
  ```

  Mismo patrón para `piezas`/`piezas_calculos` (B puede usar `ui.Tarjeta`/`ui.Boton` tal cual mientras tanto). Estos
  bloques se borran en cuanto la entrega existe y, en todo caso, antes de S3 (la checklist 11 lo comprueba con
  `grep -rn "RESPALDO HASTA S0" frontend/`).

---

## 10. Conflictos y peticiones entre partes

- Canal: la nota de cada parte en la bóveda tiene una sección «Peticiones a la otra parte» y otra «Respuestas». Cada parte
  la lee al empezar cada paso de su orden de trabajo y en cada punto S.
- Si necesitas algo de un archivo que no es tuyo: (1) no lo edites; (2) escribe la petición con la firma exacta que
  necesitas y por qué; (3) sigue con un respaldo local (9.3) o con otra tarea. El dueño responde con «hecho en <archivo>»
  o con una alternativa.
- Cambios al contrato: solo aditivos (parámetro opcional nuevo con valor por defecto que mantiene el comportamiento). Un
  cambio incompatible requiere que lo apruebe el dueño del proyecto y sube `CONTRATO` a 2.
- Si las dos partes tocaron el mismo archivo por error: para; `git diff <archivo>` para ver los dos cambios; el dueño del
  archivo (sección 3) conserva lo suyo y vuelve a aplicar lo ajeno solo si es necesario, avisando en la nota. Nunca
  `git checkout`/`git stash`/`git reset` sobre archivos que no son tuyos.
- Si una prueba de un archivo de nadie empieza a fallar: se mira primero `git diff --stat` para ver qué archivos cambiaron;
  quien tenga el cambio más probable lo investiga; si no está claro, las dos partes anotan lo que saben en su nota y lo
  resuelve quien integre.
- Un subagente nunca da permiso para saltarse estas reglas.

---

## 11. Checklist de integración final

1. `git status --short`: solo cambian los archivos de las secciones 3.1 y 3.2 (más `docs/` de planificación y los
   archivos ignorados de `tests/` y `scripts/`). `git diff frontend/minijuegos_visual/__init__.py frontend/minijuegos/pantalla_previa.py`:
   solo los enganches 5.5 y 5.6.
2. `grep -rn "RESPALDO HASTA S0" frontend/` vacío. `grep -rn ">>" frontend/minijuegos_visual/*rediseno*.py frontend/minijuegos_visual/piezas.py frontend/minijuegos_visual/globos.py frontend/minijuegos_visual/marco.py frontend/minijuegos_visual/portada_caso.py` sin texto de interfaz.
3. Pruebas puras de las dos partes: `venv/bin/python -m pytest -q -p no:cacheprovider tests/test_a_piezas_*.py tests/test_b_piezas_*.py`.
4. Suite completa contra la línea base del anexo: ningún ID nuevo en la lista de fallos.
5. Humo base (8.2) -> `HUMO MINIJUEGOS OK 47 misiones` (vista base idéntica).
6. Humo visual con todo encendido -> `HUMO MINIJUEGOS VISUAL OK 47 misiones` y las 5 clases `*Rediseno` + `CronologiaVisual`
   en la lista de clases usadas.
7. Humo visual con `ALCALDE_COMPARAR_REDISENO=0 ALCALDE_RASTREAR_REDISENO=0 ALCALDE_CONTRARRELOJ_REDISENO=0
   ALCALDE_CHAT_REDISENO=0 ALCALDE_SENALES_REDISENO=0` -> verde con las clases `*Visual` de hoy.
8. Humo del tutorial (C16) con las banderas por defecto -> `HUMO TUTORIAL MISION OK` (ejercita los 5
   rediseños, la portada y el marco).
9. Capturas de los 5 minijuegos + la portada de los 6 en ventana real, todos los estados de 7.4, normal y con reducir
   movimiento; revisadas una a una (texto legible, nada tapado por el banner, sello sin tapar la revisión).
10. Fallo forzado: con cada rediseño, un `raise` temporal en su montaje (en una copia de prueba, no en el código final) cae a
    la vista heredada y el humo sigue verde; quitarlo.
11. Auditoría final: `auditor-diseno-generico` sobre las capturas y el código de los 5 rediseños, `accessibility-tester`
    (contraste ≥ 4,5 con `estilo.contraste`, estados con forma + texto, teclado y mando), `preservador` sobre el diff de los
    dos enganches, `security-auditor` y `code-reviewer` sobre el conjunto. Ningún bloqueante.
12. Bóveda: notas 62 (Parte A) y 63 (Parte B) completas y enlazadas en «00 Índice Alcalde Digital»; la nota 61 actualizada
    con el estado final y un enlace a las dos. Sin commit (lo pide el dueño cuando quiera).

---

## 12. Riesgos que quedan

- Medidas de texto: `ui.lineas_de` necesita la fuente cargada (ursina). Las pruebas de «cabe a 16 px» son de las
  offscreen, no de las puras; si un caso no cabe, se reduce a 16 como mínimo y se recorta con «…» (nunca por debajo de 13).
- Rendimiento: el mapa y la cinta de Contrarreloj y las burbujas del Chat crean muchas entidades. Medir el número de
  entidades (`len(scene.entities)`) y el tiempo de frame en la captura; si sube mucho, agrupar en una sola malla.
- `Mesh(mode="line")`: el grosor puede no respetarse en macOS; los bordes se hacen con capas, y los hilos se revisan en la
  captura real.
- Trabajo simultáneo en el mismo directorio: `__pycache__` y ejecuciones a la vez. El cerrojo de 8.2 evita los choques de
  la suite; los import de módulos a medio escribir de la otra parte caen al guardián (la vista de hoy) porque las banderas
  de rediseño nacen en `False`.
- El tutorial sustituye métodos en la instancia: cualquier clic cableado con un método enlazado al construir se salta el
  tutorial (5.7). Lo prueba `humo_tutorial_mision.py` con las banderas encendidas (S3).
- Escape: si algún día la escena usa `escape` para pausar, el cierre de la ayuda con Esc lo taparía; hoy la escena se lo
  pasa entero a la vista (`escena_minijuego.py:384-399`).
- Las capturas dependen de la pantalla real (1470×956 en esta máquina). En otras proporciones, revisar que nada se salga de
  x ±0,83.

---

## Anexo: línea base de la suite (2026-11-17)

Comando: `venv/bin/python -m pytest -q -p no:cacheprovider -rfE tests`, lanzado a las 13:38. Resultado: `47 failed, 1238
passed, 11 skipped, 5 xfailed, 6 errors in 719.99s`. Contaminado: a mitad de la ejecución otra sesión cambió archivos de
minijuegos (sección 0). Las pruebas de minijuegos se repitieron en una copia limpia de `HEAD`: `test_tutorial_mision_humo`
PASA en limpio, así que la LÍNEA BASE LIMPIA son los 46 fallos de abajo SIN ese ID (+ 6 errores). Si el dueño adopta los
cambios de la sección 0, hay que volver a medir la suite entera antes de empezar. Humos medidos aparte el mismo día:
- `humo_minijuegos_mundo.py` por defecto: falla (`es.minijuego` es None, línea 75).
- con `ALCALDE_MINIJUEGOS_INTRO=0 ALCALDE_TUTORIAL_MISION=0`: falla (`AssertionError: CronologiaVisual`, línea 135).
- con esas dos y `ALCALDE_MISIONES_VISUALES=0`: `HUMO MINIJUEGOS OK 47 misiones {'cronologia': 9, 'rastrear': 8,
  'contrarreloj': 8, 'comparar': 8, 'chat': 8, 'senales': 6} pasadas 32 falladas 15`.
- `humo_tutorial_mision.py`: en `HEAD` limpio, verde; con los cambios de la sección 0, falla en la línea 169 (paso 5).

Errores (6):
```
ERROR tests/test_ambiente_npc_humo.py::test_coste_python_del_controlador[chico]
ERROR tests/test_ambiente_npc_humo.py::test_coste_python_del_controlador[grande]
ERROR tests/test_ambiente_npc_humo.py::test_globos_ocasionales_y_sin_fugas[chico]
ERROR tests/test_ambiente_npc_humo.py::test_globos_ocasionales_y_sin_fugas[grande]
ERROR tests/test_ambiente_npc_humo.py::test_la_ciudad_rota_tiene_menos_gente[chico]
ERROR tests/test_ambiente_npc_humo.py::test_la_ciudad_rota_tiene_menos_gente[grande]
```

Fallos (47 medidos; el último, `test_tutorial_mision_humo`, NO es de la línea base limpia):
```
FAILED tests/test_audio.py::test_contador_pasos
FAILED tests/test_ciudad_viva_ventana.py::test_capas_segun_el_ambiente[chico]
FAILED tests/test_ciudad_viva_ventana.py::test_capas_segun_el_ambiente[grande]
FAILED tests/test_ciudad_viva_ventana.py::test_coste_por_frame[chico]
FAILED tests/test_ciudad_viva_ventana.py::test_coste_por_frame[grande]
FAILED tests/test_ciudad_viva_ventana.py::test_la_niebla_llega_a_las_entidades_existentes[chico]
FAILED tests/test_ciudad_viva_ventana.py::test_la_niebla_llega_a_las_entidades_existentes[grande]
FAILED tests/test_ciudad_viva_ventana.py::test_sin_fugas[chico]
FAILED tests/test_ciudad_viva_ventana.py::test_sin_fugas[grande]
FAILED tests/test_comercios_humo.py::test_humo_comercios_offscreen
FAILED tests/test_dilemas_extra.py::test_cada_opcion_tiene_costo_y_beneficio
FAILED tests/test_dilemas_extra.py::test_cantidad_e_ids_unicos
FAILED tests/test_dilemas_extra.py::test_esquema_de_dilemas_y_opciones
FAILED tests/test_dilemas.py::test_carga_los_nueve_dilemas_con_su_ignorar
FAILED tests/test_dilemas.py::test_el_final_sigue_siendo_el_ponderado_y_coherente_con_sus_umbrales
FAILED tests/test_dilemas.py::test_la_simulacion_con_dilemas_es_determinista_y_responde_todo_lo_ofrecido
FAILED tests/test_economia_humo.py::test_humo_economia_offscreen
FAILED tests/test_flujo_tiempo.py::test_el_ambiente_sigue_a_los_indicadores_poco_a_poco
FAILED tests/test_flujo_tiempo.py::test_el_frontend_avanza_por_frames_y_la_pausa_lo_detiene
FAILED tests/test_integracion_mapa_grande.py::test_humo_mapa_grande_offscreen
FAILED tests/test_manillas_calculos.py::test_leyenda_cubre_indicadores_niveles_y_vecinos_en_espanol_sin_religion
FAILED tests/test_manillas_ventana.py::test_brazalete_y_cintas_instalados
FAILED tests/test_manillas_ventana.py::test_el_cambio_de_nivel_se_funde_y_termina
FAILED tests/test_manillas_ventana.py::test_leyenda_y_tooltip
FAILED tests/test_minijuegos_doble_efecto.py::test_escena_no_reabre_la_mision_si_decidir_falla_tras_mutar
FAILED tests/test_minijuegos_doble_efecto.py::test_fallo_en_el_panel_entrega_sin_pasar_por_el_respaldo
FAILED tests/test_minijuegos_doble_efecto.py::test_fallo_en_propagaciones_o_indicadores_tampoco_repite
FAILED tests/test_minijuegos_doble_efecto.py::test_respaldo_no_actua_si_el_lote_ya_aplico_decisiones
FAILED tests/test_minijuegos_humo.py::test_las_47_misiones_con_minijuegos_por_el_flujo_real
FAILED tests/test_minijuegos_humo.py::test_si_el_minijuego_falla_la_mision_se_juega_en_la_escena_de_siempre
FAILED tests/test_npc_nuevos_calculos.py::test_bandera_apagada_deja_los_cuatro_de_siempre
FAILED tests/test_npc_nuevos_calculos.py::test_los_npc_con_nombre_no_cambian_de_modelo
FAILED tests/test_npc_nuevos_calculos.py::test_modelo_forzado
FAILED tests/test_npc_nuevos_calculos.py::test_reparto_cada_bloque_de_siete_trae_los_cinco_nuevos
FAILED tests/test_npc_nuevos_humo.py::test_humo_npc_nuevos_offscreen
FAILED tests/test_registro_manillas.py::test_pinta_las_cinco_manillas_del_ambiente_vivo
FAILED tests/test_registro_reloj.py::test_aviso_de_causa_efecto_con_cola_espaciada
FAILED tests/test_registro_reloj.py::test_avisos_ultimo_dia_y_dos_horas_una_sola_vez
FAILED tests/test_registro_reloj.py::test_continuar_conserva_dia_hora_y_cola_de_efectos
FAILED tests/test_registro_reloj.py::test_efecto_retardado_espera_si_hay_un_panel_abierto_y_se_ve_al_cerrarlo
FAILED tests/test_registro_reloj.py::test_partida_nueva_reinicia_reloj_y_avisos
FAILED tests/test_reloj_partida.py::test_escala_un_dia_son_seis_minutos_reales
FAILED tests/test_reloj_ventana.py::test_el_reloj_corre_en_el_mundo_y_el_chip_lo_muestra
FAILED tests/test_trabajo_humo.py::test_humo_trabajo_offscreen
FAILED tests/test_trabajos.py::test_catalogo_semilla
FAILED tests/test_trabajos.py::test_secuencia
FAILED tests/test_tutorial_mision_humo.py::test_tutorial_contrarreloj_por_el_flujo_real
```

Nota: los fallos de `test_minijuegos_humo.py` y `test_minijuegos_doble_efecto.py` también fallan en `HEAD` limpio: son
anteriores a este trabajo (C4). Arreglarlos NO es parte del rediseño (tocaría el flujo o los humos existentes); se informa al dueño.
