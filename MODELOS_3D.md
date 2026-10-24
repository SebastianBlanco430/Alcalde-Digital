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
| Praça da Sé (Lan House) | casa1 |
| Universidade de Ciudad Nova | casa1 |
| Rodoviária | casa2 |
| Parque do Povo (Biblioteca) | casa2 |
| Morro da Esperança | casa3 |
| Prefeitura | casa4 |
| Hospital Santa Casa | casa4 |

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
    Prefeitura (noroeste), sobre el mapa más 40 m alrededor, con un ondulado de ±1,5 m.
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
- Plazas, de la más alta a la más baja: Praça da Sé 15,5 · Prefeitura 15,4 · Universidad 14,6
  · Terminal 11,8 · Parque 11,6 · Barrio 9,0 · Hospital 6,9 m.
- **La red de calles sube unos 8,7 m.** Con plazas planas de radio 9 m y calles de 32 a 37 m,
  las rampas miden solo 12–16 m, así que a 14° no se puede subir mucho más. El resto de los
  25 m está en la ladera que rodea la red: el pasto y las casas decorativas de la fase E.
- La pendiente máxima en las calles es ≤ 15°, comprobada en el eje y en los bordes del
  asfalto.
- **Taludes**: el 0,4 % del terreno pasa de 30° (hasta 47°), donde un lote y una calle
  cercanos están a distinta altura (por ejemplo, entre Morro da Esperança y la calle a la
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
  Lo probé entrando a la Prefeitura: la toma, la puerta y el personaje quedan bien y se pasa al
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

### Fase G: detalles de favela (2026-10-19)

Ocho mejoras de la favela, hechas con subagentes en paralelo (bloques A–F) y unidas en `Ciudad3D`.
Todo es determinista (el azar sale de `azar_de(a, b)` en `frontend/azar_fijo.py`, nunca del
`random.Random` del backend) y el mundo plano (`ladera=False`) sigue funcionando.

| Mejora | Dónde | Qué hace y constantes |
|---|---|---|
| Muros de contención | `backend/datos/muros.py`, `frontend/muros_contencion.py` | Una losa por celda de talud no caminable, a lo largo de la curva de nivel, fusionadas en cadena (±15°, ≤ 0.6 pasos de desvío): 138 celdas dan 38 muros. Largo = paso × 1.1; base = mínimo de esquinas − 0.3 m; tope = máximo + 0.4 m. Excluye ~1.6 m en torno a escaleras, calles y accesos, y las cajas de edificios y casas. Dibujo: cubo de 0.35 m de grosor, `COLOR_MURO` (128, 124, 116) alternando con un tono 8 más oscuro, y tapa de 0.08 m. No cambian la colisión. |
| Semilla | `construir_mundo_3d(semilla=SEMILLA_CASAS)`, `main.py` | Casas con `semilla`, vegetación con `semilla + 1`, muros al final. `ALCALDE_SEMILLA` (entero) elige otra favela; con la semilla por defecto la favela es idéntica a la anterior. |
| Velocidad por pendiente | `backend/logica/navegacion.py`, `frontend/controlador_jugador.py` | `factor_pendiente`: subiendo `max(0.6, 1 − 0.9 t)` (≈ 0.76 a 15°), bajando `min(1.1, 1 + 0.3 \|t\|)`. Mide el desnivel 0.5 m adelante y escala el paso antes de las colisiones; también al correr. |
| Zócalos y pilotes | `frontend/ciudad_3d.py`, `frontend/geometria_mundo.py` | La planta baja se apoya en `alto` de `apoyo_de_caja` = (bajo, alto) sobre 9 puntos de la huella. Desnivel ≤ 1.5 m: zócalo `COLOR_ZOCALO` (150, 146, 138); mayor: losa (≥ 0.25 m, más gruesa si hace falta) y 4 pilotes de 0.3 × 0.3 m. Cada modelo de casa trae un plinto propio bajo el umbral (`hondo` en `modelos_edificios.py`, 0.17–0.54 u): la base lo tapa por completo y es 0.06 m más ancha por lado que la casa (`medidas_zocalo` / `medidas_losa`), así no hay caras coplanares ni textura de pared bajo la base. 125 casas con zócalo y 25 con pilotes (desnivel máximo 2.88 m). Las casas del lado alto suben 1–3 m. El cable de la farola llega al 80 % del alto total. |
| Ladrillo | `frontend/casas_decorativas.py` | 2.º piso con `TINTE_LADRILLO` (200, 124, 92) si `azar_de(cx + 3.1, cz) < 0.5`. |
| Terreno de una cara | `_malla_terreno` | Sin `double_sided`; se invirtió el orden de los vértices (antihorario visto desde +y), verificado con una captura aérea. |
| Antenas y ropa | `frontend/detalles_calculos.py`, `frontend/detalles_techos.py` | Antenas en ~20 % de las casas (32), en la esquina opuesta al tanque (mástil 0.05 × 0.6 m, plato de una esfera compartida). Hasta 40 tendederos entre casas con 1.2–4 m de separación, sin cruzar calles, accesos, escaleras ni otras casas; prendas cada ~0.5 m con borde inferior ≥ 2.15 m. Las cuerdas se suman a la malla de líneas de los cables. |
| Banderas | `frontend/banderas.py`, `frontend/banderas_calculos.py` | Una por edificio jugable, en la esquina trasera del techo opuesta a la puerta; 7 colores (`COLORES_BANDERA`). Mástil de `ALTO_MASTIL` = 4 m y tela de 6 franjas que ondea (25° en la punta, 3 rad/s). La del destino de la misión se agranda 1.4×, ondea 1.6× más rápido y lleva borde `COLOR_BALIZA`. Se anima desde `Ciudad3D.update()` y no proyecta sombra. |
| Neblina | `frontend/niebla.py`, `escena_mundo.py` | `activar_niebla()` con `COLOR_NIEBLA` = el horizonte del cielo (`COLOR_HORIZONTE` de `frontend/cielo.py`, (238, 224, 204)), `FIN_NIEBLA` = 260 e `INTENSIDAD_NIEBLA` = 0.65, al entrar al mundo; `desactivar_niebla()` al salir; a 30 m pesa ~7,5 %. Solo afecta a las entidades ya creadas y no a las de `shader=None`. |
| Cielo y sol | `frontend/cielo.py`, `frontend/ciudad_3d.py` | `CieloDegradado` reemplaza a `ursina.Sky`: domo con colores de vértice (horizonte crema → azul, resplandor hacia el sol), 15 nubes bajas que derivan y dos filas de cerros lejanos; `self.cielo` sigue fuera de `silenciar()`. Luz de tarde: `DIRECCION_SOL` = (1.0, -1.1, 0.8) (para volver a la luz alta, (1, -1.6, 0.8)). Una sola `DirectionalLight` + una `AmbientLight`. |
| Suelo, marcas y props | `frontend/ciudad_3d.py`, `frontend/props_mundo.py`, `frontend/azar_fijo.py` | Ruido de color por vértice en pasto, asfalto y aceras; líneas de borde y cebras junto a cada plaza; unas 90 piezas de decorado (árboles de 4 tipos, arbustos con flores, farolas, jardineras, canecas, bancos, vallas, carteles) en una sola malla con normales, más una fuente de tres niveles en la Praça da Sé. Sin colisión (el backend no los ve) y fuera de calles, huellas de edificios y pasos plaza-puerta. `combine(include_normals=True)` (`COMBINAR_CON_NORMALES`): sin normales el shader usa el último `normal` dibujado y las plazas cambian de brillo según el encuadre. |
| Minimapa | `frontend/hud.py` (`Minimapa`), `frontend/hud_calculos.py` | Casas (88, 92, 108, algo transparente) y escaleras (200, 190, 160) en una malla cada una; se reconstruyen solo si el yaw cambia más de 1.5°. |

**Orden en `Ciudad3D.__init__`:** suelo, calles, plazas, edificios, obstáculos (casas con base, tanques,
detalles, cables con la ropa), escaleras, muros, `combine()`, `silenciar()`, banderas, sombras.

**Refactor previo (Fase 0):** `azar_de` (antes `_azar_de`), `lineas_sueltas` en `piezas.py`,
`CasaDecorativa.alto_piso` / `alto_total` y `MASCARA_LUZ` definida solo en `piezas.py`.

**Mediciones:**
- `construir_mundo_3d()`: 1.69 s antes, 1.75 s después (límite del plan: +0.3 s).
- Entidades sin fundir nuevas: las 7 banderas (unas 63–70, todas silenciadas salvo su animación).
- FPS con tope y libre: **pendiente de medir a mano** (`$env:ALCALDE_FPS="1"` y `"libre"`; criterio: media ≥ 57 y 1 % bajo ≥ 30).
- Tests: 10 fallos preexistentes (1 desactualizado por la favela y 9 sin investigar: `test_flujo_partida`, `test_guion_cinematicas` ×7, `test_mazo_noticias`) y el resto pasa.

**Pendiente:**
- Medir FPS y mirar a ojo las banderas, la ropa, los pilotes y el minimapa.
- Las banderas quedan tapadas por casas más altas de la ladera; para verlas siempre haría falta un mástil de 8–12 m.
- Los muros no tienen collider de cámara (la cámara de tercera persona puede atravesarlos).
- Las entidades con `shader=None` (ventanas, luces, cables) no reciben la neblina.
- Una casa en el borde del minimapa desaparece entera y puede parpadear al girar.
- `tests/test_favela.py` y `tests/test_terreno.py` no están en el repo; las reglas de la favela se repiten en `tests/test_muros.py`.

### Personajes con modelo (periodista y candidato)

- **Archivos:** `assets/modelos/personajes/periodista.glb` (rol periodista) y `smoking.glb` (rol candidato); la tabla está en `frontend/modelo_calculos.py` (`MODELOS_POR_ROL`, puro). Ciudadano, influencer y peatones siguen con el muñeco procedural.
- **Código:** `frontend/personaje_modelo.py` (`PersonajeModelo`, misma API que `Personaje`, y la fábrica `crear_personaje`, usada por `escena_mundo.py` y `escena_interior.py`). Se carga cada .glb una vez por rol y se copia con `Actor(base)` por jugador. Se carga con `gltf.load_model` + `Actor(NodePath(...))`: `Actor(ruta)` deja la altura en Z (personaje tumbado).
- **Clips:** Idle, Caminar, Correr, Saludar, Hablar (mezcla de 0.2 s). Por velocidad: Idle < 0.1 m/s; Caminar hasta 6.5 m/s (el juego camina a 4.8; rate tope 2.0); Correr desde 6.5 (el juego corre a 8.5; rate tope 2.2). Las poses de `poses.py` se traducen a clip en `clip_para_pose` (idempotente, no reinicia el loop).
- **Escala:** 0.92 (1.84 m, como el muñeco de 1.83 m); pies en y = 0; el modelo mira a +z del cuerpo (comprobado con una captura de perfil).
- **Fallback:** si el archivo falta o no carga, `crear_personaje` devuelve el `Personaje` procedural y avisa una vez por rol por stderr (`[assets] <rol>: ... Se usa el modelo procedural.`).
- **Limitaciones:** no hay clip de sentado ni de teclear: en el interior el modelo queda de pie con Hablar, desplazado `OFFSET_SENTADO` = (0, 0, -0.7) detrás de la silla. Sin shader del juego: no recibe la niebla ni las sombras del shader (no se pudo probar el shader en una ventana offscreen, que solo da GL 2.1). Los pies patinan: el rate está topado por debajo de la velocidad real.
- **Rostro y pelo:** los .glb venían con la cabeza lisa. `frontend/rostro_calculos.py` (puro: medidas y colores por rol) y `frontend/rostro_modelo.py` (`colocar_rostro(actor, rol)`, nunca lanza) cuelgan ojos, cejas, nariz, boca, orejas y pelo del hueso `DEF-spine.006`, así que siguen la animación. Sin luz ni shader (color plano) y con contorno negro en el pelo. Los ojos miran fijo: sin parpadeo ni boca animada.
- **Cámara en pantalla completa (macOS):** el F11 de Ursina no obtiene el tamaño pedido y recentra el cursor desplazado, lo que sesgaba `mouse.velocity` y clavaba el pitch. `camara_calculos.quitar_reposo` resta ese sesgo (en ventana normal es 0).
- **Créditos:** modelos Periodista_Ursina y Smoking_Ursina aportados por el equipo; los .blend fuente NO se incluyen en el repo.
- **Autoría y licencia (a confirmar por el equipo):** los .glb solo declaran `asset.generator = "Khronos glTF Blender I/O v5.2.40"`; no traen `copyright`, licencia ni autor en `asset` ni en `extras`, y no incluyen imágenes incrustadas (colores por material). Por tanto la autoría y la licencia NO constan en los archivos. Autor/a: [COMPLETAR: nombre o «creación propia del equipo»]. Licencia: [COMPLETAR: p. ej. «creación propia, uso interno de aprendizaje» o la licencia de origen si se partió de un modelo/rig de terceros]. Uso: proyecto de aprendizaje sin fines comerciales.
- **Terceros por verificar (mismo criterio):** las texturas de `buildings/textures/` (p. ej. `Concrete-2767.jpg`, `Door-8850.jpg`, `janela01.jpg`) y las casas `casa1..4fav.blend`: anotar su origen y licencia antes de redistribuir el repo o publicar el juego. Dependencias de software (Ursina, Panda3D, panda3d-gltf, etc.): se usan bajo sus propias licencias de código abierto, listadas en `requirements.txt`; si se distribuye un ejecutable, incluir sus avisos de licencia.
- *Nota: es una anotación de trabajo, no sustituye revisión legal.*

### Pendiente del equipo
- Texturizar en Blender las caras que quedaron grises y reexportar.
- Pasar a quien lo necesite `buildings/textures/`, que no se sube al repo.
- Hacer los commits.

### Personajes con modelo: brasileña (influencer) y ciudadano (2026-10-21)
- **Autoría**: modelados y animados por el dueño en Blender; licencia propia del dueño. Origen: `Brasilena_Ursina.zip` y
  `Ciudadano_Ursina.zip` (cada uno con `LEEME.md`, clase demo, `blender/*.blend`, `modelos/*.glb`). Solo se copiaron los .glb a
  `assets/modelos/personajes/brasilena.glb` (2,1 MB) y `ciudadano.glb` (2,2 MB); los `.blend` quedan en los zips.
- **Brasileña** (`influencer`): 37 huesos (armadura `metarig`, hueso de la cabeza `Head`), piel oscura, pelo afro, camiseta verde con
  bandera, short de jean, joyería dorada. Mide 2,14 m con el afro (cuerpo 1,94 m): escala propia `ESCALA_POR_ROL["influencer"] = 0.86`
  (`modelo_calculos.escala_para_rol`), así el conjunto mide 1,84 m como los demás.
- **Ciudadano** (`ciudadano`): 160 huesos, misma armadura y misma cabeza que el periodista (`DEF-spine.006`), sin camisa y con pantalón
  corto azul. Mide 2,0 m; escala 0,92.
- Ambos traen los clips `Idle, Caminar, Correr, Saludar, Hablar` y ya miran a `forward` (con `setH(180)` igual que los otros).
  Contorno de tinta ya incluido como casco geométrico: no se añade otro.
- **Cara por código**: los dos llegan con la cabeza lisa, así que reciben ojos, cejas, nariz, boca y orejas animados con la misma API
  (`rostro_modelo.colocar_rostro_animado`). Datos nuevos en `rostro_calculos.py`: `DESCRIPTOR_MODELO_POR_ROL`, `ROSTRO_MODELO_POR_ROL`,
  `hueso_cabeza(rol)`, `reposo_cabeza(rol)`, `AJUSTE_ROSTRO_POR_ROL` (la cabeza de la brasileña es algo menor y más atrás: factor 0,93,
  dy +0,065, dz -0,045 respecto al periodista) y `ajustar_piezas`. El ciudadano lleva pelo corto negro; la brasileña no lleva pelo
  por código (el afro ya viene en el modelo). `ROSTRO_POR_ROL` y `DESCRIPTOR_POR_ROL` no cambiaron.
- Pies: iguales que los otros (bind pose a -0,005 m); con `ELEVACION_PIES` quedan sobre la ruta GPS sin flotar ni enterrarse.
- Limitaciones: sigue sin haber clip de sentado/teclear (en interiores, Hablar de pie); el Actor no recibe niebla ni sombras del juego;
  el retrato 2D de la selección de rol (`iconos.py`) no representa a los modelos nuevos.

### NPC (peatones) con los 4 modelos .glb (2026-10-21, ronda 2)
Los 12 peatones de `frontend/peatones.py` ya no son muñecos de cubos: cada uno es una **copia de uno de los 4 .glb** (periodista, smoking,
brasileña, ciudadano) con otra ropa. Bandera `peatones.USAR_MODELOS = True` (False vuelve a los muñecos de siempre); si un NPC no se puede
crear, `crear_npc` devuelve el `Personaje` procedural y avisa una vez por stderr.
- **Sin Blender**: no está instalado (`/Applications`, `which blender`), así que la ropa se cambia en Panda3D. Los .glb no tienen texturas:
  el color está en los vértices, un Geom por pieza (periodista `Camisa/Mangas/Pantalon/Cuerpo`, smoking `Saco/Pantalon/Cuerpo`, brasileña
  `Top/Short/TrajeBano/Pelo/Cuerpo`, ciudadano `Pantalon/Cuerpo/Ciudadano_Detalles`). `npc_color.recolorear_actor` reescribe el color de esas
  piezas **en la copia** (el .glb y los personajes principales no cambian; hay prueba): el tono más claro pasa a ser el color pedido y los
  demás conservan su proporción, así siguen las bandas de luz horneadas. Los Geoms casi negros son el casco de tinta y no se tocan.
- **Ciudadano sin camisa**: `npc_color.agregar_camiseta` añade a la copia un Geom nuevo con los triángulos del torso (elegidos por el peso de
  los huesos de la espalda/pecho/hombros, con manga o de tirantes), inflados 1,6 cm; sigue al esqueleto. El 20 % queda con el torso al aire.
- **Qué decide cada NPC** (`npc_calculos.plan_npc`, determinista, con su propio `Random`, no toca el azar de `crear_peatones`): modelo (de
  cada bloque de 4 NPC sale uno de cada modelo, barajado por semilla: 12 NPC = 3 de cada), tono de piel y pelo (los de `aspecto_peaton`),
  camiseta/pantalón/extra (paletas vivas), traje de una pieza en el smoking, escala 0,94-1,06 sobre la del modelo, fase de animación
  (`control.pose(f); loop(False)`: no van sincronizados) y mochila (40 %) colgada del hueso de la espalda con contorno de tinta.
- **Cara por código** con los rasgos del peatón (`rostro_calculos.descriptor_peaton` + `rostro_modelo.colocar_rostro_animado_piezas`),
  ajustada a la cabeza de cada modelo. La brasileña conserva su afro (sin peinado, gorra, bigote ni barba por código).
- **Código**: `npc_calculos.py` (puro), `npc_color.py`, `npc_modelo.py` (`PersonajeNPC(PersonajeModelo)`, `crear_npc`). En `personaje_modelo.py`
  solo se añadieron 5 ganchos (`_crear_actor`, `_escala_modelo`, `_poner_rostro`, `_iniciar_loop`, `_animar_rostro`) con el comportamiento
  de siempre por defecto. Cada .glb se carga UNA vez (caché `_bases`, compartida con los roles) y cada NPC es una copia (`Actor(base)`).
- **Rendimiento** (esta Mac, `ALCALDE_FPS=libre`, ventana real): juego normal 205-250 FPS con muñecos vs 200-230 con modelos; peor caso (los
  12 caminando a 3-8 m de la cámara) 145 vs 91-97 FPS. El coste es el esqueleto en CPU (≈0,4 ms por NPC con 160 huesos), no la cara.
  LOD cada 0,3 s: a más de 22 m se apaga la cara, a más de 45 m se congela el cuerpo (velocidad 0). Se mantuvieron los 4 modelos (no hizo falta
  limitarlos a los de menos huesos). No medido: GPU integrada de otro equipo.
- **Pruebas**: `tests/frontend_3d/test_npc_calculos.py` (14, puras) y `test_npc_modelo_offscreen.py` (subproceso: 12 NPC, caché, base intacta,
  caminar/parar, LOD, limpieza, respaldo). Capturas: scratchpad `npc/` (`b_quieto_*`, `b_camina_*`, `r*.png`).
- Limitaciones: la camiseta del ciudadano tiene bordes de triángulo y alguna costura de piel visible de cerca; el Actor sigue sin niebla ni
  sombras del juego; los NPC no se sientan ni saludan (solo Idle/Caminar).

---

## 5. Favela viva y de cómic (2026-10-21, rama favela-borderlands)

Todo es reversible con banderas y constantes con nombre. Para volver atrás: `construir_mundo_3d(denso=False)` (las 150 casas
sueltas de antes) y, en `frontend/ciudad_3d.py`, `SUELO_FAVELA`, `PLAZAS_PINTADAS`, `CASAS_VIVAS`, `CONTORNO_TINTA` y
`FAVELA_DETALLES` en `False`.

### Suelo (`frontend/suelo_calculos.py`, `suelo_favela.py`, `texturas_favela.py`)
- **Calles de arena**: solo la avenida `CALLES_ASFALTADAS` (Prefeitura - Praça da Sé - Universidad) sigue en asfalto; ahora gastado,
  con parches de arena y baches (`cinta_asfalto_gastado`) y aceras cálidas. El resto son cintas de arena de 11 m de ancho con
  bordes irregulares (`IRREGULAR_BORDE`), color por vértice (`ARENA_CLARA/MEDIA/ROJIZA`) que se funde con la ladera, y una textura
  procedural (PIL, sin archivos) con rodadas, huellas, piedras y grietas. Una sola malla con textura (`calles_arena`).
- **Ladera**: el pasto pasa a tierra roja junto a casas y calles (`MapaTierra`, `TIERRA_JUNTO_A_CASAS/CALLES`) con textura de grano.
  `_malla_terreno(terreno)` sin `color_en` produce la malla de siempre.
- **Plazas**: discos pintados de franjas ondulantes y bordillo a rayas, una paleta por plaza (`PALETAS_PLAZA`).
- Escaleras con peldaños pintados (`PALETAS_ESCALERA`) y muros de contención de colores (`PALETA_MUROS`).

### Favela (`backend/datos/barrio_favela.py`, `conectividad.py`; `frontend/favela_*.py`)
- **Barrio denso**: filas de casas que serpentean (como curvas de nivel), 1-3 pisos, `estiramiento` en profundidad (campo nuevo
  de `CasaDecorativa`), huecos de 1,6-2,8 m (`HUECO_CASA`), patios ocasionales, y mínimo duro de `CALLEJON_MIN` = 1,5 m entre casas.
  263 casas (antes 150) y ~300 callejones (`Callejon`, derivados de las casas). Filtros: fuera de plazas, calles, accesos, escaleras,
  spawns, edificios y zonas; `quitar_bolsas` elimina casas que encierren suelo aislado (BFS en rejilla de 0,5 m).
- **Zonas abiertas** (`Zona`): cancha de fútbol (el terreno se aplana: `Terreno(zonas_planas=...)`) y mercadito de toldos.
- **Detalle** (mallas combinadas, sin Entity por pieza): murales (sol, bandera, estrella, corazón, ola, ojo), carteles con letras,
  remiendos, grietas, manchas de humedad translúcidas, balcones, banderines que cruzan callejones, pasadizos (cuartos sobre el
  callejón), bidones, macetas, motos, bicis, cajas de fruta, perros, palmeras y bananeros, cancha y mercadito. Más cables
  enredados (`CABLES_POR_TRAMO`) y tendederos (`MAXIMO_TENDEDEROS` = 150).
- Callejón mínimo 1,5 m: el jugador (radio 0,35) cabe; la cámara en tercera persona se acerca por su raycast (mín. 1,2 m).

### Estilo de cómic (`frontend/casas_decorativas.py`, `props_mundo.py`)
- Texturas de los modelos aclaradas y aplanadas, pintura viva por piso (`PINTURAS`), ladrillo visto (~20-40 %), techos de zinc/teja.
  Edificios jugables pintados con el color de su lugar.
- **Contorno de tinta**: casco invertido (`GROSOR_CONTORNO` 0,12 m, solo caras traseras, sin luz, fuera del mapa de sombras) en casas,
  edificios jugables y árboles. Los geoms de techo se excluyen (`CLASES_SIN_CASCO`): su copia casi pegada al plano real parpadeaba.
- Sombra azul-violeta y más suave (`piezas.py`); sol dorado; cielo de atardecer con mar, picos y disco solar (`cielo.py`).

## Vehículos montables (bicicleta y moto) — Ronda 3, fase 1
- **Módulos nuevos** (nada existente se tocó): `frontend/vehiculo_calculos.py` (dinámica pura), `vehiculo_piezas.py` (geometría pura),
  `vehiculo_modelo.py` (Entity/Panda3D) y `vehiculo_mundo.py` (aparcados, aviso y controlador). Pruebas en
  `tests/frontend_3d/test_vehiculo_calculos.py` y `test_vehiculo_piezas.py`.
- **Modelos procedurales**: cada grupo (cuadro, manubrio con rueda delantera, rueda trasera, biela, pedales, pata de cabra, halo) son dos Geom
  con color por vértice (bandas de luz horneadas, sin luces) y casco de tinta (caras traseras, método de `contorno_calculos`). Sin shader:
  no reciben la niebla del mundo (igual que los Actor). `INVERTIR_CARAS = False` en `vehiculo_modelo.py` (comprobado con captura: las
  mallas de `malla_calculos` usadas sin espejo se ven bien con el orden normal).
- **Signos de Ursina** (medidos): `rotation_x > 0` baja el morro y hace avanzar una rueda; `rotation_z > 0` inclina a la derecha.
- **Piloto**: un `Personaje` procedural articulado (cuerpo/cara de cómic) con cinemática inversa: pies a los pedales/estribos y manos al
  manubrio. Los avatares `.glb` no se pueden articular, así que se les crea un maniquí con el color del rol y se oculta el avatar.
- **Controles**: relativos al vehículo (W/S, A/D, Shift turbo, Espacio freno de mano/derrape, sin salto); la cámara se recoloca detrás.
- **Pendiente de la fase 2**: integrar con `controlador_jugador.py`, `escena_mundo.py`, HUD y los atributos aditivos de la cámara.
