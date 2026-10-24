# Alcalde Digital: dirección visual y sistema de diseño

**Estado (2026-10-20):** especificación **implementada en gran parte**; las desviaciones están al final («Decisiones tomadas»). Valores RGB 0-255. Ursina 8.3.0 / Panda3D 1.10.16. Las capturas offscreen salen negras en macOS (GL 2.1): toda verificación visual se hace en **ventana real** y los FPS con `ALCALDE_FPS=1`. No pude usar las habilidades game-feel / game-ui-ux / camera-systems (no disponibles en esta sesión): la sección 9 aplica sus principios a mano.

## 1. Identidad y tono
**Concepto: «cómic cívico de una tarde en la ladera»**: tinta oscura, color plano, acento amarillo (lo que importa) y cian (el camino). Coincide con los modelos del periodista y el candidato (low poly, contorno negro).
Principios: 1) **Tinta**: todo elemento 2D lleva borde y sombra dura de tinta; 2) **Un solo foco**: amarillo = destino/acción principal, cian = ruta/información; nada más compite; 3) **Cálido y legible**: luz de tarde, texto grande, sin ruido.
Tono: cercano, claro y con ironía ligera sobre la desinformación; frases cortas, tuteo, sin jerga («Verifica antes de compartir»).
**Wordmark (por código)**: «ALCALDE» en Atkinson Hyperlegible Bold 64 px (la spec decía Nunito ExtraBold), amarillo, con copia idéntica en tinta desplazada (+5 px, -5 px) detrás; debajo, «DIGITAL» 28 px, tinta sobre placa cian redondeada (radio 8, borde tinta 3 px), inclinada -2°. Sobre la «A» un rombo amarillo con borde de tinta (la baliza del juego) a modo de pin. Subtítulo actual se conserva.

## 2. Paleta con roles
| Rol | RGB | Nota |
|---|---|---|
| TINTA (contornos, sombras duras, texto sobre amarillo) | 18,20,32 | nueva |
| Fondo / Panel / Tarjeta (ya existen) | 24,26,38 / 36,39,56 / 46,50,71 | no cambian |
| Superficie alta (hover de tarjeta, chip) | 58,62,88 | nueva |
| Papel (iconos, teclas, retratos) | 250,244,228 | nueva |
| Texto / Texto tenue | 235,235,240 / 170,172,190 | tenue sobre Panel: 6,2:1 (AA) |
| **Acento primario** (botón primario, destino) | 255,220,60 | con TINTA: 14:1 (AAA) |
| **Acento secundario** (ruta, información) | 70,220,255 | sobre Panel: 9:1 |
| Botón secundario | 70,90,150 (hover 95,118,185) | texto blanco: 5,8:1 |
| Éxito / Aviso / Error / Info | 80,190,110 / 215,180,60 / 214,62,62 / 70,220,255 | las barras ya usan estos tres tercios (34/66) |

**Roles** (hoy no coinciden con los modelos: periodista rojo con camisa verde; candidato verde con esmoquin marfil; influencer amarillo choca con el acento). Propuesta, **decisión del dueño** (toca `backend/logica/roles.py`, solo constantes): Ciudadano 66,133,244 (igual) · Periodista 46,184,116 · Influencer 232,84,150 · Candidato 240,226,190 (marfil, siempre con borde de tinta en minimapa).
**Lugares** (punto del minimapa, franja del letrero, bandera; alinear `COLORES_BANDERA`): Praça da Sé 240,200,90 · Prefeitura 70,110,190 · Universidade 140,110,200 · Parque 80,170,100 · Morro da Esperança 230,120,150 · Rodoviária 235,140,60 · Hospital 60,180,170. Regla: el color de lugar es identidad, nunca estado.
**Mundo**: cielo cenit 96,150,224 → horizonte 238,224,204 (= `COLOR_NIEBLA` = `cielo.COLOR_HORIZONTE`, empalma sin costura; la spec decía 206,222,224); luz solar 255,240,215 con dirección `cielo.DIRECCION_SOL` = (1, -1.1, 0.8); ambiente 118,126,150 (sombras algo azules, estilo cómic); sombra de contacto 10,12,30 alfa 110. Pasto 92,158,70 con variación ±8 % por vértice; asfalto 66,68,78 ±4 % por tramo; marcas viales blanco hueso 240,238,228.
**Cian y amarillo se cambian juntos** en `hud.py` y `marcadores_mundo.py` (duplicados); `estilo.py` pasa a ser su fuente única (tarea T1).

## 3. Tipografía
**DECISIÓN TOMADA: Atkinson Hyperlegible** Regular y Bold (SIL OFL 1.1) en `assets/fuentes/` con su `OFL.txt`, porque Nunito no publica TTF estáticas (solo la variable, que FreeType carga en ExtraLight) y generarlas exigía instalar fontTools. Texto original de la spec, que habla de Nunito: **Nunito** (SIL OFL 1.1, licencia clara, redondeada, cubre ñ, ¿, ¡, tildes y «·»). Usar los **estáticos** `Nunito-Regular.ttf` y `Nunito-ExtraBold.ttf` (los archivos «variable» de Google Fonts cargarían en FreeType la instancia por defecto, ExtraLight: no usarlos). Atkinson Hyperlegible Regular/Bold es el plan B si la prueba de anchos falla. Guardar en `assets/fuentes/` + copia de la licencia (`OFL.txt`).
**Carga sin romper nada**: Ursina busca en `application.asset_folder`. En `main.crear_aplicacion`, justo después de fijar `asset_folder` y **antes de `preparar_fuente()`**: `Text.default_font = "Nunito-Regular.ttf"` (módulo nuevo `frontend/tipografia.py` con `FUENTE_TEXTO`, `FUENTE_TITULO`, `aplicar()`). `Text.size` (0.025) NO cambia, así que `escala_fuente` y `a_unidades` quedan idénticas. Títulos: `Text(..., font=FUENTE_TITULO)` por instancia (no hay etiqueta de negrita). `preparar_fuente()` debe aplicar `setTextureMargin(4)` a **ambas** fuentes. Faltan flechas y ✓ ★ ▲ (siguen siendo mallas/iconos).
**Riesgo**: Nunito tiene otros anchos que OpenSans; revisar los tests de «texto dentro de la tarjeta» (`texto_dentro_de_la_tarjeta`, panel del teléfono) y añadir un test que cargue la fuente y mida «Convivencia: 100».
| Uso | px (de 600) | Fuente |
|---|---|---|
| Logo | 64 / 28 | ExtraBold |
| Título de pantalla | 40 (hoy 32-48) | ExtraBold |
| Subtítulo | 28 | ExtraBold |
| Cuerpo | 20 (mínimo 17) | Regular |
| Etiqueta / ayuda | 17 (mínimo absoluto 16) | Regular |
| Cifra grande (indicadores finales) | 48 | ExtraBold |
Interlineado 1,25 (ya usado). Nunca menos de 16 px.

## 4. Espaciado y formas
Escala 4/8/12/16/24/32 px (convertir con `a_unidades`). Radios: chip 6, tarjeta 10, panel 14, botón 10. **Borde de tinta** 3 px (2 px en HUD denso): quad trasero de TINTA con `modelo_redondeado(ancho+6, alto+6, radio+3)`. **Sombra plana**: otro quad de TINTA alfa 160 desplazado (+4, -5) px, sin desenfoque. Un solo nivel de sombra.
Jerarquía para no caer en «todo son tarjetas»: máximo 2 niveles de contenedor; indicadores y textos de HUD van sobre una franja única, no cada uno en su caja; la tarjeta con borde de tinta se reserva para lo que se puede pulsar o que es modal (pausa, fin, teléfono).
Componente nuevo (aditivo) `panel_tinta(padre, ancho, alto, tono, radio_px, sombra=True)` en `componentes.py`.
**Botón**: primario = fondo amarillo, texto TINTA 22 px ExtraBold, borde tinta; secundario = 70,90,150 con borde tinta. Estados: hover escala 1,04 (80 ms, `ease_out_quad`); pulsado escala 0,96 (60 ms) y sombra se hunde; deshabilitado 55,57,70 sin sombra; mantener 56 px de alto.

## 5. Iconografía (sin arte externo)
Módulo nuevo `frontend/iconos.py` con **Pillow** (ya llega con Ursina): se dibuja a 256×256 y se reduce a **64×64** (antialias), relleno papel/color, **contorno de tinta 4 px (a 256)**, `texture.filtering = "bilinear"` para que no salga pixelado. Función pura `dibujar_icono(nombre) -> PIL.Image` (testeable sin ventana) y `textura_icono(nombre)` con caché. Un icono se usa solo cuando acompaña un dato (indicador, tecla, acción); las etiquetas largas no llevan icono.
| Icono | Dibujo |
|---|---|
| teléfono | rectángulo redondeado vertical, pantalla cian, punto de altavoz |
| misión | rombo amarillo (como la baliza) sobre base corta |
| convivencia | dos cabezas circulares solapadas y dos arcos de hombros |
| confianza | escudo con marca de verificación hecha con polilínea |
| desinformación | burbuja de mensaje roja con signo «!» de barra y punto |
| E (interactuar) | **no es imagen**: quad papel con borde tinta y base gruesa (tecla) + `Text("E")` ExtraBold |

## 6. Pantallas 2D
- **Inicio (opción segura)**: fondo `frontend/fondo_menu.py`: cielo degradado por colores de vértice (zenit→horizonte), 3 capas de siluetas de casas en quads (tintes de la paleta de edificios, cada capa más oscura y con deriva lenta 0,01-0,03 u/s), rombo amarillo como sol bajo, velo TINTA alfa 90. Wordmark centrado arriba; «Empezar» primario, «Salir» secundario. **Opción grande**: ciudad 3D real orbitando (ver T17).
- **Selección de rol**: `retrato_rol(rol)` en `iconos.py`: busto (cabeza color piel, cuerpo del color del rol, contorno de tinta) con un objeto: libreta (periodista), teléfono con selfie (influencer), corbatín y banda (candidato), gorra (ciudadano). Se asigna como `texture` a la `muestras_rol[rol]` existente (de 0,04 de ancho a 0,09 cuadrado), sin cambiar nombres ni botones. Rol tomado: retrato en gris y sin sombra.
- **Pausa**: `panel_tinta` 0,5×0,52, velo alfa 170; «Reanudar» primario; fila de teclas (WASD mover · Shift correr · E entrar · Tab teléfono) con el componente tecla.
- **Fin**: `BarraIndicador` ×3 con su icono a la izquierda y la cifra en 48 px; las barras crecen 0→valor en 0,8 s (llamar `actualizar` con valores intermedios); frase de cierre por rango (bajo/medio/alto); «Volver al menú» primario.
- **HUD**: aviso E con tecla E + texto (conservar `TEXTO`); «Misión:» en amarillo; minimapa con calles 112,116,132 → 140,146,164 y puntos de lugar con color de lugar.

## 7. Mundo 3D (sin shaders nuevos: no se pueden validar offscreen; una DirectionalLight + una AmbientLight)
- **Luz**: solo cambiar colores (sección 2). Opcional (M): bajar la elevación (`look_at (1,-1.2,0.8)`) para sombras de tarde; revisar acné y no tocar `shadow_bias`.
- **Cielo** `frontend/cielo.py`: malla de esfera invertida con colores de vértice (degradado), `shader=None`, sigue a la cámara como el `Sky` actual (el que ya cuelga de la ciudad y se excluye de `silenciar`). 8-10 nubes: círculos aplanados blancos (alfa 235, 3 círculos solapados cada una), `shader=None`, deriva de 0,5 m/s, una sola malla `combine()` y un giro lento del conjunto (1 entidad con update).
- **Suelo**: ruido por vértice (±8 %, `azar_de` determinista) en `_malla_terreno`, sin UV ni textura. La textura procedural (Pillow, 256×256 tileable) queda como M2 y exige añadir UV.
- **Calles**: bordes blancos continuos de 0,12 m, cebras (5 franjas) en la entrada de cada plaza, tono de asfalto ±4 % por tramo. Cintas existentes con `combine()`.
- **Props** (módulo nuevo `frontend/props_mundo.py`, todo combinado en `vegetacion`/`mobiliario`): árboles con altura y escala por `azar_de`, copas 3 tonos de verde y algunos con flores (esferas 0,12 m amarillas/rosa); vallas bajas (postes + travesaño) alrededor de plazas con hueco en las calles; carteles de calle (poste + placa tinta); **fuente en Praça da Sé** sobre el emblema: cuenca (cilindro compartido bajo, piedra), disco de agua 90,190,230 `shader=None` con pulso de brillo ±6 %, chorro (`diamond`). Una sola entidad sin silenciar que anima.
- **Sombra de contacto** `frontend/sombra_contacto.py`: disco (`circle`, `rotation_x=90`, escala 0,9 m, 10,12,30 alfa 110, `shader=None`, `set_depth_offset`) hijo de cada personaje y peatón, a +0,05 m; verificar que no parpadee con las cintas (asfalto +0,10).
- **Peatones**: de 6 a 10-12 (medir FPS: cada `Personaje` son muchas entidades), ropa más saturada y distinta de los roles, escala 0,94-1,06 por peatón, accesorio (mochila/sombrero) en una parte.
- **Contorno de tinta (G)**: casco invertido (copia 1,03× con caras traseras, `shader=None`, TINTA) solo en los 7 edificios jugables y personajes procedurales; **no** usar `CommonFilters.setCartoonInk` (pantalla completa, caro en GPU integrada). Excluir del mapa de sombras con `hide(MASCARA_LUZ)`.
- **Rendimiento**: meta 60 FPS (hoy 56-59). Presupuesto: +0 luces, +0 shaders, +≤ 5 entidades sin silenciar fuera de peatones; todo estático con `combine()` + `silenciar()` (nubes, fuente y peatones se crean DESPUÉS del `silenciar` de la ciudad, como las banderas). Llamar a `activar_niebla` después de crear entidades. Medir antes/después de cada tarea M/G: media ≥ 57 y 1 % bajo ≥ 30.

## 8. Movimiento y game feel
Sobrio, sin animar por animar. Botones: ver 4. Aviso E: aparece en 120 ms (alfa + 6 px hacia arriba, `ease_out_quad`). Teléfono: el banner ya desliza en 0,2 s; añadir `ease_out`. Baliza: anillo cian que se expande de 1 a 1,6× y se desvanece cada 1,6 s. Al correr, FOV +4° en 250 ms (volver en 400 ms), coordinar con `camara_calculos.py` (puro). Barras de fin: 0,8 s. Sin sacudida de cámara ni audio en esta fase (no hay sonidos; **decisión del dueño** si quiere generarlos por código).

## 9. Orden de ejecución (S = solo constantes, M = media, G = grande)
Cada agente toca solo sus archivos; **un único agente para `ciudad_3d.py`** y **uno para `hud.py`**.
| Id | Tarea | Tipo | Archivos | Depende |
|---|---|---|---|---|
| T1 | Constantes de paleta (TINTA, papel, estados, lugares) y cian/amarillo con fuente única | S | `estilo.py` | - |
| T2 | Colores de luz, ambiente, pasto, cielo base, niebla | S | `ciudad_3d.py` (cabecera), `niebla.py` | - |
| T3 | Calles del minimapa 140,146,164 y color por lugar | S | `hud.py` | T1 |
| T4 | Nunito: `assets/fuentes/`, `tipografia.py`, línea en `main.py`, margen en `preparar_fuente`, test de anchos | M | `tipografia.py`, `main.py`, `componentes.py` | - |
| T5 | `panel_tinta`, botón primario/secundario y estados | M | `componentes.py` | T1 |
| T6 | `iconos.py` (6 iconos + 4 retratos) y tests puros | M | `iconos.py` (nuevo) | T1 |
| T7 | Inicio: wordmark + `fondo_menu.py` | M | `escena_inicio.py`, `fondo_menu.py`, `logo.py` | T4,T5 |
| T8 | Selección: retratos | M | `escena_seleccion_rol.py` | T6 |
| T9 | Pausa | M | `menu_pausa.py` | T5 |
| T10 | HUD: tecla E, «Misión:», fin con barras e iconos | M | `hud.py` | T3,T5,T6 |
| T11 | Mundo A: cielo y nubes, ruido de suelo, marcas viales, props y fuente | M | `ciudad_3d.py`, `cielo.py`, `props_mundo.py` | T2 |
| T12 | Sombra de contacto | M | `sombra_contacto.py`, `personaje.py`, `personaje_modelo.py` | - |
| T13 | Peatones 10-12 y variedad | M | `peatones.py` | T12 |
| T14 | Baliza con anillo; FOV al correr | M | `marcadores_mundo.py`, `camara_tercera_persona.py` | - |
| T15 | Colores de rol alineados a modelos | S | `backend/logica/roles.py` | **decisión dueño** |
| T16 | Luz de tarde baja | M | `ciudad_3d.py` | T11; revisar sombras |
| T17 | Inicio con ciudad 3D real orbitando | G | `escena_inicio.py`, `main.py`, `escena_mundo.py` | T7 |
| T18 | Contorno de tinta (casco invertido) | G | `contorno.py`, hooks | T11,T12 |
| T19 | Textura procedural de pasto/asfalto (UV nuevos) | G | `ciudad_3d.py` | T11 |
Paralelas sin choques: {T1,T2,T4,T6,T12,T14} → {T3 después de T1 = mismo agente que T10, T5, T7-T9, T11, T13}. Verificación de cada tarea: captura en ventana real antes/después (inicio, selección, mundo, fin) y `ALCALDE_FPS=1`; correr `pytest` y el humo `scripts/smoke_flujo.py offscreen`. Preguntas abiertas: ¿cambiar colores de rol (T15)?, ¿audio por código?, ¿licencia de Nunito aceptada (OFL)?

## Decisiones tomadas (desviaciones de la especificación, 2026-10-20)
- **Fuente:** Atkinson Hyperlegible Regular/Bold en lugar de Nunito (ver §3). `frontend/tipografia.py` las aplica.
- **Mundo:** horizonte/niebla (238,224,204) con intensidad 0.65 (no 206,222,224); luz de tarde `DIRECCION_SOL` = (1, -1.1, 0.8); cielo propio (`frontend/cielo.py`); props y fuente (`frontend/props_mundo.py`); causa del «blanco» de plazas y aceras: `combine()` sin normales, ahora `COMBINAR_CON_NORMALES = True`.
- **Pies y sombra de contacto:** `ELEVACION_PIES` = 0.26 m en el mundo (0.03 en el interior), sombra de contacto y aro de resaltado translúcido (`frontend/sombra_calculos.py`, `sombra_contacto.py`).
- **Peatones:** 12 en lugar de 6; los 6 originales conservan su recorrido (`crear_peatones`).
- **No hecho aún:** colores de rol (T15, decisión del dueño), T17 ciudad 3D orbitando en el inicio, T18 contorno de tinta en edificios, T19 textura procedural de pasto/asfalto.
