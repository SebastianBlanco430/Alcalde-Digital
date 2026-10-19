# Modelos 3D de Blender en Ciudad Nova

Estado del cambio que reemplaza los edificios de cubos por las casas hechas en Blender, lo que
queda pendiente y hacia dónde queremos llevar el mapa (favela brasileña en ladera).

> Estado: implementado y probado localmente. **Sin commit todavía.**

---

## 1. Qué se hizo

### Resultado
- Las casas de Blender (`buildings/casa1..4fav.blend`) reemplazan a los cubos en los 7 edificios
  del mapa. El funcionamiento del juego no cambia.
- Lo probé con una partida automática: llegar a la puerta del destino, pulsar E, ver la
  cinemática (se abre la puerta y el personaje entra) y pasar al interior.

| Edificio | Modelo |
|---|---|
| Plaza Central (Café Internet) | casa1 |
| Universidad de Ciudad Nova | casa1 |
| Terminal de Buses | casa2 |
| Parque Municipal (Biblioteca) | casa2 |
| Barrio Las Flores | casa3 |
| Alcaldía | casa4 |
| Hospital Las Flores | casa4 |

Las casas repetidas llevan un tinte suave para diferenciarlas.

### Cómo funciona (resumen)
1. **Exportación.** `buildings/exportar_edificios.py` se ejecuta con Blender en modo
   background y hace lo siguiente:
   - reenlaza las texturas a `buildings/textures/` y las reduce a 1024 px;
   - aplica las transformaciones y pone el origen en el centro de la planta baja, a la altura
     del umbral de la puerta;
   - detecta la puerta de entrada;
   - exporta `assets/modelos/edificios/casaN.glb` y `casaN_puerta.jpg`, e imprime las medidas
     del modelo.
2. **Catálogo.** `backend/datos/modelos_edificios.py` guarda esas medidas. Es Python puro, sin
   ursina.
3. **Backend.**
   - En `backend/datos/ciudad_3d.py`, cada edificio tiene ahora un *lote* (la caja anterior) y
     un modelo. La casa se escala sin deformarse, se ajusta a la fachada de la puerta y su caja
     de colisión pasa a ser la de la casa, siempre dentro del lote.
   - `Edificio` (`backend/logica/mundo_ciudad.py`) suma dos campos opcionales, `modelo` y
     `desfase_puerta`, porque la puerta del modelo no siempre está centrada.
4. **Frontend.** `frontend/ciudad_3d.py` carga el `.glb` en lugar de los cubos:
   - los modelos no se combinan, porque `combine()` pierde las texturas;
   - la puerta animada usa el tamaño y la textura de la puerta del modelo;
   - el letrero se centra en la fachada;
   - las sombras abarcan a los modelos.

### Decisiones tomadas
- **Escala limitada por la puerta** (`ALTO_PUERTA_MAXIMO = 3.2 m`). Sin ese límite, las puertas
  medirían hasta 6 m. Por eso las casas se ven más chicas que los cubos de antes.
- **Suelo a la altura del umbral.** La pared que el modelo tenía por debajo de la puerta queda
  bajo tierra.
- **Color base de los materiales.** Las caras sin textura se pintan con el color base del
  material (gris), porque el shader del juego lo ignora y salían blancas.
- **Fallback a cubos.** Con `modelo = ""`, un edificio vuelve a dibujarse con cubos.

### Archivos
- Nuevos:
  - `buildings/exportar_edificios.py`
  - `backend/datos/modelos_edificios.py`
  - `assets/modelos/edificios/*` (13 MB)
- Modificados:
  - `backend/logica/mundo_ciudad.py`
  - `backend/datos/ciudad_3d.py`
  - `frontend/ciudad_3d.py`

### Reexportar una casa
```
"C:\Program Files\Blender Foundation\Blender 5.2\blender.exe" -b buildings/casa1fav.blend --python buildings/exportar_edificios.py -- casa1
```
Después, pegar la línea `ModeloEdificio(...)` que imprime en `backend/datos/modelos_edificios.py`.

---

## 2. Pendiente

- [x] **Texturas faltantes.** Los `.blend` usan 4 imágenes que no están en `buildings/textures/`.
  Se reemplazan, **de forma definitiva**, por otras de la misma carpeta:
  - `Concrete-3012.jpg` → `Concrete-2767.jpg`
  - `WoodDoor-2044.jpg` → `Door-8850.jpg`
  - `Picsart_23-07-21_09-24-44-403.jpg` → `janela01.jpg`
  - `Picsart_23-07-21_09-23-07-056.jpg` → `janela01.jpg`
- [ ] **Caras sin textura.** Algunas caras de los modelos no tienen textura (se ven gris liso).
  Las texturiza el equipo en Blender y luego se reexporta.
- [x] **Rendimiento.** Medido en primer plano y corregido (ver «Resultados de la Fase A»).
- [x] **Escala.** `ALTO_PUERTA_MAXIMO = 3.2 m` se mantiene.
- [x] **Repositorio.** `buildings/textures/` (120 MB) va al `.gitignore`. Los `.glb` ya incluyen
  sus texturas.
- [ ] **Commit.** Lo hace el equipo.
- [ ] **Opcional.** Convertir los `.glb` a `.bam` (`gltf2bam`) si la carga se nota lenta. Por
  ahora no hace falta: los modelos tardan ~1 s en cargar.

---

## 3. Próxima etapa: topología de favela brasileña

### Objetivo
Que Ciudad Nova se vea como una favela brasileña:
- **terreno inclinado y montañoso** (una ladera, no un plano);
- **mucho más poblada**: casas apiladas y pegadas unas a otras, escaleras, callejones y calles
  que suben en curva por la ladera;
- los 7 lugares jugables siguen existiendo, ahora integrados en la ladera.

### Por qué no es solo un cambio visual
Hoy el mundo es **plano**: todo el backend trabaja en (x, z) y la altura es siempre y = 0. Una
ladera afecta a:

- **Movimiento:** el personaje, los peatones y la cámara necesitan la altura del terreno en
  cada punto.
- **Edificios y puertas:** cada casa se apoya a una altura distinta. La puerta, el punto de
  entrada, la cinemática, el letrero y la baliza dependen de esa altura.
- **Calles, plazas y aceras:** hoy son cubos planos. En la ladera tienen que seguir la
  pendiente o ser terrazas con escalones.
- **Colisión:** hoy son cajas y círculos en 2D. Es probable que alcance con sumar la altura del
  terreno, sin pasar a física 3D.
- **Cámara:** el raycast debería chocar también con el terreno, no solo con los edificios.
- **Sombras:** el volumen de sombra crece con el desnivel. Hay que revisar la resolución.

### Ideas para hacerlo (a definir, sin código todavía)
1. **Terreno.**
   - Modelarlo en Blender (ladera con terrazas) y exportarlo igual que las casas, o generarlo
     con un mapa de alturas.
   - El backend necesita una función pura `altura(x, z)` para colocar todo y mover a los
     personajes. Con un mapa de alturas compartido, el backend no depende de ursina.
2. **Más edificios.**
   - Además de los 7 jugables, agregar muchas **casas decorativas** (no interactivas): las 4
     casas actuales con variantes de rotación, escala, tinte y pisos apilados, más casas nuevas
     de Blender.
   - Repartirlas por reglas, como ya hace `_Despeje` con árboles y bancos, para que nunca
     bloqueen calles, accesos ni spawns.
   - Las casas decorativas son obstáculos con caja de colisión.
3. **Calles de favela.**
   - Escaleras y callejones angostos entre las casas.
   - El grafo de lugares (GPS) se mantiene y solo cambian las coordenadas y el trazado visual.
4. **Rendimiento.** Con cientos de casas ya no alcanza con una entidad por casa. Opciones:
   - agrupar por modelo y usar *instancing*;
   - combinar las casas decorativas lejanas;
   - usar versiones simplificadas (LOD) a distancia;
   - unificar texturas en un atlas para poder combinar sin perderlas.
5. **Ambientación (opcional).** Cables entre postes, tanques de agua en los techos, colores
   vivos en las fachadas y vegetación en la ladera.

### Preguntas abiertas (respondidas, ver sección 4)
- ¿El terreno se modela a mano en Blender o se genera por código? → **Por código.**
- ¿Cuánto desnivel total y cuánta pendiente máxima se puede caminar? → **~25 m, rampas ≤ 15°.**
- ¿Las calles siguen la pendiente o son terrazas planas unidas por escaleras? → **Mixto.**
- ¿Cuántas casas decorativas queremos y cuántos modelos nuevos se harán en Blender? →
  **~150, con las 4 casas actuales.**

---

## 4. Plan acordado

### Decisiones
| Tema | Decisión |
|---|---|
| Alcance | Cerrar los pendientes de la sección 2 y después hacer la favela |
| Git | **Sin commits**: los cambios quedan en el árbol de trabajo y los commitea el equipo |
| Repositorio | `buildings/textures/` va al `.gitignore`. Se versionan los `.glb`, los `.blend` y el script |
| Texturas faltantes | Los reemplazos actuales quedan como definitivos. Las caras grises se arreglan en Blender más adelante |
| Escala | `ALTO_PUERTA_MAXIMO = 3.2 m` se mantiene |
| Rendimiento | **Objetivo: 60 FPS** jugando en primer plano |
| Terreno | Generado por código: función pura `altura(x, z)` en el backend |
| Desnivel | Unos 25 m en total |
| Calles | Mixto: las calles del grafo son rampas ≤ 15°; las plazas y los lotes son terrazas planas; escaleras en callejones y atajos |
| Mapa | Se mantienen el grafo y las posiciones de los 7 lugares. Solo cambian la altura, el trazado visual y la densidad |
| Densidad | Unas 150 casas decorativas, sacadas de las 4 casas actuales con variantes |

> ⚠️ Antes de los modelos se midieron entre 8 y 21 FPS (en segundo plano, con mucho ruido).
> Si en primer plano tampoco se llega a 60, la fase B tiene que optimizar lo que ya existe
> antes de sumar casas.

### Fase A: cerrar los pendientes (sin commit)
1. Agregar `buildings/textures/` al `.gitignore`.
2. Documentar los reemplazos de textura como definitivos y dejar la tarea de las caras grises
   para Blender.
3. Medidor de FPS opcional, activado con una variable de entorno (por ejemplo
   `ALCALDE_FPS=1`), que registre los FPS mínimo, medio y máximo de un recorrido fijo.
4. Medir en primer plano con cubos (`modelo = ""`) y con modelos. Anotar los resultados aquí.
5. Si no se llega a 60 FPS: agrupar las piezas por material, convertir a `.bam` y bajar la
   resolución de las sombras. Medir de nuevo.

### Resultados de la Fase A (2026-10-18)

**Herramientas**
- `frontend/medidor_fps.py`: se activa con `ALCALDE_FPS=1` (mide con el tope de 60) o
  `ALCALDE_FPS=libre` (sin tope). Cada 5 s imprime la media, el mínimo y el 1 % bajo, y al
  cerrar imprime el resumen de la sesión.
- `scripts/medir_fps.py [modelos|cubos] [segundos]`: un recorrido fijo y automático. Es local,
  porque `scripts/` está en el `.gitignore`.

**Diagnóstico** (laptop con AMD Radeon integrada y RTX 2050, enchufada)
- El juego corre en la **gráfica integrada AMD**, no en la RTX.
- Antes del cambio y sin tope, la media rondaba los 26–45 FPS con modelos y los 32 FPS con cubos.
  **Las casas de Blender no eran el problema.**
- Lo que costaba la mitad de los FPS era **redibujar el mapa de sombras en cada frame**. Con
  las sombras apagadas se llegaba a 88–97 FPS. No cambiaba nada al bajar la resolución
  (4096 → 1024), al usar menos muestras PCF ni al dibujar solo la profundidad: el costo está
  en volver a dibujar la escena entera en esa pasada.

**Solución: sombras horneadas** (`frontend/ciudad_3d.py`)
- La luz y la ciudad son estáticas, así que el mapa de sombras se dibuja **una sola vez**
  (buffer *one-shot*) al entrar al mundo. También se redibuja mientras se mueve una puerta.
- Solo la ciudad va al mapa de sombras (`set_scene`). **Los personajes y los peatones ya no
  proyectan sombra.** Si se nota la falta, se puede agregar una sombra circular barata
  debajo de cada uno.

| Medición (AMD integrada, modelos) | Media | 1 % bajo |
|---|---|---|
| Antes, sin tope | 26–45 | 6–30 |
| Después, sin tope | 87–97 | 42–55 |
| Después, con el tope de 60 del juego | **59,7** | 41 |
| Después, RTX sin tope (`SHIM_MCCOMPAT`) | 95 | 50 |

- Las mediciones varían mucho entre corridas iguales (una dio 60 de media y otra 97), así que
  hay que repetirlas. Los tirones del 1 % bajo no vienen del GC de Python (`gc.freeze()` no
  cambió nada). Se revisan en la fase B.
- Para jugar con la RTX: en *Configuración de Windows → Pantalla → Gráficos*, elegir «Alto
  rendimiento» para el `python.exe` del `.venv`. Es un cambio del sistema y lo hace cada
  usuario.

### Fase B: base de rendimiento para muchas casas
6. Instancing por modelo en `frontend/ciudad_3d.py`: un nodo por modelo y por material, con N
   instancias (`setInstanceCount` o un shader de instancias), conservando las texturas.
7. Prueba de carga: 150 casas en el mapa plano actual. Tiene que llegar a 60 FPS antes de
   seguir. Si no llega: LOD (una caja con textura a distancia) o atlas de texturas para
   poder combinar.

### Resultados de la Fase B (2026-10-18)

**Qué se hizo**
- Backend: `CasaDecorativa` (`backend/logica/mundo_ciudad.py`) es un `Obstaculo` de caja con
  `modelo`, `rumbo` (múltiplo de 90), `escala` y `variante` (tinte).
  `casa_decorativa(modelo, cx, cz, rumbo, escala, variante)` (`backend/datos/ciudad_3d.py`)
  calcula su caja a partir del catálogo. Sigue siendo Python puro.
- Frontend: `frontend/casas_decorativas.py` copia todas las casas bajo una raíz y las **funde
  con `flatten_strong()`**. Las piezas que comparten material quedan en una sola, con la
  posición, el giro, la escala y el tinte de cada casa incluidos en los vértices. A diferencia
  de `combine()`, conserva las texturas.
  - Hace falta `clear_model_nodes()` antes de fundir: el `ModelRoot` de cada `.glb` impedía
    fundir las copias (quedaban 1373 piezas en lugar de 74).
  - `Ciudad3D` dibuja así los obstáculos de tipo `"casa"`, bajo la raíz de los edificios, de
    modo que también proyectan sombra. Cada casa tiene un collider de caja para la cámara.
- No hizo falta instancing por hardware: cada casa tiene solo unos 500 vértices, así que
  150 casas suman unos 75 000, y fundirlas es más simple y no exige un shader propio.

**Prueba de carga**: `CASAS=150 scripts/medir_fps.py` reparte 150 casas sobre el mapa plano
actual con las reglas de `_Despeje`. Es solo una prueba; el reparto real se hace en la fase E.

| Medición (AMD integrada) | Media | 1 % bajo |
|---|---|---|
| Sin casas, sin tope | 89–91 | 47–58 |
| 150 casas fundidas, sin tope | 73–80 | 34–40 |
| 150 casas fundidas, con el tope de 60 | **59** | 34 |
| 150 casas fundidas, sin colliders | 75–81 | 34–41 (los colliders no influyen) |

- **No hace falta LOD ni atlas** por ahora: hay margen por encima de 60.
- Pendiente: los tirones del 1 % bajo (~35 FPS) ya estaban sin las casas. Revisarlos si se
  notan al jugar.
- Lo fundido no se mueve ni se quita por separado. Para pisos apilados (fase E), cada piso
  es otra copia dentro del mismo lote.

### Fase C: terreno en ladera (backend puro, sin ursina)
8. Nuevo módulo `backend/datos/terreno.py` con `altura(x, z)` determinista: una ladera de
   ~25 m más ruido suave, y **terrazas planas** forzadas en las plazas y en los lotes de los 7
   edificios.
9. Calles: a lo largo de cada arista del grafo, la altura se interpola entre las dos plazas y
   se valida que la pendiente sea ≤ 15°. Si una arista no cumple, se ajusta la altura de las
   terrazas.
10. `MundoCiudad` expone `altura(x, z)`. Los edificios, las puertas, los puntos de entrada y
    los spawns toman su `y` del terreno. La colisión sigue en 2D.
11. Tests (locales, porque `tests/` está en el `.gitignore`) para la pendiente máxima de las
    calles, las terrazas planas bajo los lotes y que cada puerta quede al nivel de su plaza.

### Resultados de la Fase C (2026-10-18)

**Qué se hizo** (todo en el backend; el frontend todavía no usa la altura, así que el juego se
sigue viendo plano hasta la fase D)
- `backend/datos/terreno.py`, clase `Terreno`:
  - Ladera natural: un plano de **25 m** de desnivel que sube del Hospital (sureste) hacia la
    Alcaldía (noroeste), sobre el mapa más 40 m alrededor, con un ondulado de ±1,5 m.
  - Terrazas planas: las plazas (radio + 1,5 m), los lotes de los edificios (+1,5 m) y el
    camino plaza → puerta, a la altura de su plaza.
  - Calles: planas dentro de cada plaza y en rampa lineal en el tramo libre. Las alturas de
    las plazas parten de la ladera natural y se ajustan (`ajustar_alturas`) para que ninguna
    rampa pase de 14° (15° con 1° de margen para la mezcla con los lotes vecinos).
  - Mezcla: Shepard de potencia 2 con una caída suave de 10 m. Adentro de cada pieza la altura
    es exacta (error < 1 mm) y afuera la ladera se recupera.
  - `altura(x, z)` lee una grilla de 1 m con interpolación bilineal (se construye en ~0,8 s la
    primera vez). `altura_exacta(x, z)` evalúa la fórmula. `grilla()` entrega los vértices
    para la malla del frontend.
- `MundoCiudad(..., terreno=)` y `MundoCiudad.altura(x, z)` (0 en un mundo plano).
  `Edificio.y` es la altura del umbral, igual a la de su plaza.
- `construir_mundo_3d(ladera=True)`. Con `ladera=False` vuelve el mundo plano de antes.

**Números**
- Plazas, de la más alta a la más baja: Plaza Central 15,5 · Alcaldía 15,4 · Universidad 14,6
  · Terminal 11,8 · Parque 11,6 · Barrio 9,0 · Hospital 6,9 m.
- **La red de calles sube unos 8,7 m.** Con plazas planas de radio 9 m y calles de 32 a 37 m,
  las rampas miden solo 12–16 m, así que a 14° no se puede subir mucho más. El resto de los
  25 m está en la ladera que rodea la red: el pasto y las casas decorativas de la fase E.
- La pendiente máxima en las calles es ≤ 15°, comprobada en el eje y en los bordes del
  asfalto.
- **Taludes**: el 0,4 % del terreno pasa de 30° (hasta 47°), donde un lote y una calle
  cercanos están a distinta altura (por ejemplo, entre Barrio Las Flores y la calle a la
  Terminal). En la fase D conviene dibujarlos como muros de contención. La colisión sigue en
  2D, así que hoy se podrían caminar.

**Tests** (`tests/test_terreno.py`, locales): pendiente de calles y aceras, plazas y lotes
planos, puertas al nivel de su plaza, desnivel, grilla frente a fórmula, determinismo, mundo
plano y `ajustar_alturas`. Los 10 pasan. **pytest no está instalado** en el `.venv`; los corrí
con un ejecutor mínimo. Para usar pytest: `.venv/Scripts/python.exe -m pip install pytest`.

### Fase D: terreno en el frontend
12. Malla del terreno generada desde `altura(x, z)` (una grilla de ~1 m con normales), en
    lugar del piso plano.
13. Calles y plazas como cintas o mallas pegadas al terreno, no como cubos.
14. El personaje, los peatones y la cámara usan `altura(x, z)`. El raycast de la cámara choca
    también con el terreno.
15. Sombras: el volumen pasa a cubrir el desnivel. Revisar la resolución y los FPS.

### Resultados de la Fase D (2026-10-18)

**Qué se hizo**
- **Suelo** (`frontend/ciudad_3d.py`, `_malla_terreno`): una malla de la grilla del `Terreno`
  (1 m, unos 41 000 vértices) con normales. El pasto pasa a tierra en los taludes de 25 a 40°.
  Como la malla tiene normales y el shader le suma la luz, el color se oscurece
  (`BRILLO_LADERA = 0.6`) para que se vea como antes.
- **Calles** (`_cinta`): el asfalto, las aceras con bordillo y la línea central son cintas
  muestreadas cada metro que siguen al suelo y tienen paredes laterales, para que no se vean
  huecas en la pendiente. Reemplazan a los cubos, también en el mundo plano.
- **Todo apoyado en `mundo.altura(x, z)`**: plazas, edificios (en `Edificio.y`), puertas,
  colliders de la cámara, árboles, farolas, bancos y casas decorativas. Cada casa decorativa
  se apoya en el punto más bajo de su huella, así no flota del lado de abajo.
- **Personajes y peatones**: `Personaje.suelo`. `colocar(x, z)` toma la altura de ahí; en el
  interior queda en `None` y no cambia nada.
- **Cámara**: el pivote va sobre el suelo y, además del raycast contra los edificios,
  `camara_calculos.distancia_libre_de_suelo` muestrea la altura cada 0,5 m a lo largo del
  tramo y acerca la cámara si la ladera la tapa. No hay raycast contra la malla de 82 000
  triángulos.
- **Baliza y ruta del GPS**: la baliza se apoya en el suelo. La ruta parte cada tramo solo
  donde el suelo deja de ser recto (comprueba 1/4, 1/2 y 3/4 del tramo; con solo el medio, una
  rampa simétrica entre dos plazas pasaba por recta), se inclina con la pendiente y se rearma
  solo cuando el jugador se mueve más de 25 cm. Se aparta del suelo 4 cm como máximo.
- **Cinemáticas**: `guion_cinematicas.toma_fachada` y la órbita de salida usan `edificio.y`.
  Lo probé entrando a la Alcaldía: la toma, la puerta y el personaje quedan bien y se pasa al
  interior.
- **Sombras**: con ladera, el volumen de sombra abarca toda la ciudad (si no, el suelo más
  bajo que los edificios caía fuera del rango de profundidad). El suelo, las calles y las
  plazas solo reciben sombra: se ocultan a la cámara de la luz para que no haya *acne*.
- `scripts/medir_fps.py`: `PLANO=1` mide el mundo plano, para comparar.
- Ojo con los signos en Ursina: `rotation_x` **negativo** levanta el frente (+z) de una pieza.
  El `forward` de una `Entity` sugiere lo contrario.

**Rendimiento** (AMD integrada, mediciones intercaladas)

| Medición | Media | 1 % bajo |
|---|---|---|
| Ladera, sin tope | 75–78 | 37–38 |
| Plano, sin tope | 76–94 | 40–51 |
| Ladera, con el tope de 60 | 57–58 | 26–37 |
| Ladera + 150 casas, con el tope de 60 | 53–60 | 33–47 |

- La carga tarda ~1,5 s más: unos 0,8 s para la grilla del terreno y unos 0,7 s para la malla.
  Si molesta, se puede guardar la grilla en un archivo.
- Tests nuevos (locales): `tests/test_camara_suelo.py` (4). Los 14 tests pasan.

**Pendiente**
- Los taludes de más de 30° se ven como tierra, pero se pueden caminar porque la colisión es
  2D. Faltan muros de contención o bloquear el paso (fase E).
- La prueba de carga de 150 casas solo cuida los ejes de las calles: algunas casas pisan el
  borde de las plazas. El reparto real va en la fase E.

### Fase E: densidad de favela
16. Generador de casas decorativas por reglas (como `_Despeje`): lotes sobre terrazas con
    rotación, tinte y 1 a 3 pisos apilados, sin bloquear calles, accesos, puertas ni spawns.
    Cada casa es un obstáculo con caja.
17. Callejones angostos y escaleras decorativas entre las casas.
18. Medir que se mantengan los 60 FPS.

### Resultados de la Fase E (2026-10-18)

**Qué se hizo**
- **Generador** `_casas_favela` (`backend/datos/ciudad_3d.py`, Python puro y determinista,
  `SEMILLA_CASAS`):
  - Pase greedy sobre una grilla de candidatos cada 2 m con ruido, de más cerca a más lejos
    de la red de calles: la favela se apiña junto a las calles y se ralea hacia el borde.
  - Una casa entra si no pisa plazas (aro + 2,5 m) ni calles (asfalto + 3 m), cumple
    `_Despeje`, deja un **callejón de 1,2 m** con las otras casas y con árboles, farolas y
    bancos, y el suelo bajo su huella no varía más de 3 m.
  - Mira hacia la calle o plaza más cercana. Modelo, escala (2,2–2,7), tinte y pisos son al
    azar.
  - `construir_mundo_3d(casas=150)` genera **150 casas**: 90 dentro de la zona caminable y 60
    en la ladera de alrededor. Tarda ~1,8 s, incluida la grilla del terreno.
- **Pisos apilados**: `CasaDecorativa.pisos` (1 o 2; `PISOS_CASA = (1, 1, 1, 2)`). El frontend
  repite el modelo hacia arriba con el tinte siguiente, dentro del mismo lote fundido. Con 3
  pisos salían torres de ~25 m, porque cada modelo ya tiene ~2 plantas.
- **Taludes que hacen de muro**: `Terreno.pendiente(x, z)` y `Terreno.caminable(x, z)`;
  `MundoCiudad.es_transitable` rechaza lo que pasa de 32°. Es el 0,7 % de la zona caminable.
- `scripts/medir_fps.py`: `CASAS=N` cambia la cantidad de casas (0 = ninguna).

**Rendimiento** (AMD integrada, 150 casas)

| Medición | Media | 1 % bajo |
|---|---|---|
| Con el tope de 60 | 56–59 | 25–39 |
| Sin tope | 75 | 33–38 |

**Tests** (`tests/test_favela.py`, 8): cantidad, determinismo, ni plazas ni calles,
callejones, desnivel, variedad, rutas del GPS de cada spawn a cada lugar transitables y
taludes no caminables. Con los anteriores son 22, y todos pasan.

**No se hizo**
- ~~Escaleras decorativas~~: hechas en la fase F.
- Muros de contención visibles: los taludes se ven como tierra y bloquean el paso, pero no
  hay muros.
- Los edificios jugables se distinguen menos entre tantas casas. La baliza y el GPS ayudan;
  si hace falta, se puede despejar más alrededor de cada uno.

### Fase F: ambientación (opcional)
19. Cables entre postes, tanques de agua en los techos, fachadas de colores y vegetación.

### Resultados de la Fase F (2026-10-18)

**Escaleras de la favela**
- Backend: `Escalera` (`backend/logica/mundo_ciudad.py`) y `_escaleras` (`backend/datos/ciudad_3d.py`).
  Salen del borde de la acera, perpendiculares a la calle, y miden 14 m. En cada lado de cada
  calle se queda el arranque que más desnivel salva (como mínimo 1,5 m), siempre que no se
  acerque a plazas, otras calles, edificios, accesos, obstáculos u otras escaleras.
- Se calculan **antes que las casas**: `_Despeje.agregar_linea` suma su eje a las líneas
  libres, así las casas les dejan paso y cada escalera queda como un callejón.
- `MundoCiudad.escaleras()`; sobre una escalera se camina aunque el talud pase de 32°.
- Hoy salen **5 escaleras** que salvan de 1,6 a 3,6 m. La ladera natural es suave (unos
  25 m en 200 m), así que son escalinatas largas.
- Frontend: peldaños de 17 cm de contrahuella en dos tonos, con la tapa sobre el suelo y el
  cuerpo enterrado para seguir la ladera, más una baranda de postes y pasamanos.

**Ambientación** (`frontend/ciudad_3d.py`)
- **Fachadas de colores**: las casas decorativas usan `TINTES_FAVELA` (rosa, amarillo,
  celeste, verde, naranja, lila y blanco), que multiplican la textura. Los edificios jugables
  mantienen los tintes suaves.
- **Tanques de agua**: cilindro azul con tapa en el 45 % de las casas, en una esquina del
  último piso. La elección depende de la posición de cada casa, así que siempre son las mismas.
- **Cables**: de cada farola a la siguiente de su calle (en zigzag) y de cada farola a la
  casa más cercana a menos de 9 m, colgando en parábola. Es una sola malla de líneas
  (`GeomLines`), sin sombreado ni sombra. `Mesh(mode="line")` de Ursina une todos los
  vértices en una sola línea continua.
- **Vegetación**: `_vegetacion` (backend) suma 70 plantas (árboles y arbustos `"arbusto"`) en
  el pasto libre, con las reglas de las casas y 0,8 m de separación de todo.

**Rendimiento**
- ⚠️ `Cylinder()` de Ursina deja **~30 entidades auxiliares vivas** por llamada, y Ursina
  las recorre en cada frame. Con un cilindro por tanque había 2600 entidades sin silenciar y
  el juego caía a ~50 FPS. Con una sola malla compartida volvió a ~70–77 sin tope, igual que
  sin la ambientación.
- Con el tope de 60: **58–59 FPS** (1 % bajo de 32–37).

**Tests**: `tests/test_favela.py` suma 5 (escaleras con desnivel, casas y plantas que no las
tapan, escaleras que no cruzan calles ni plazas, que sobre una escalera se camine en un talud
y la vegetación). En total hay 27, y todos pasan.

### Pendiente del equipo
- Texturizar en Blender las caras que quedaron grises y reexportar.
- Pasar a quien lo necesite `buildings/textures/`, que no se sube al repo.
- Hacer los commits.
