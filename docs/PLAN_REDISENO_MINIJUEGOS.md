# Plan de rediseño visual de 5 minijuegos (2026-11-17)

Minijuegos: Rastrear la fuente, Comparar dos versiones, Chat del barrio, Señales de edición y Contrarreloj.
Ordenar la cadena (cronología) NO se toca: es la referencia de estilo.
Estado: SOLO PLAN, nada implementado. Fuentes: auditoría de diseño, conceptos de UI, mapa técnico del código (informes de subagentes, 2026-11-17).

## 1. Diagnóstico

Los cinco usan la misma plantilla: título, rumor amarillo, párrafo, rejilla de cajas azul-pizarra de esquinas suaves, pie de teclas gris. Cronología funciona porque cada viñeta es un OBJETO con escena, personajes y globo.

Causas, de más a menos importante:
1. Sin objeto físico reconocible (corcho, hojas, móvil, captura, mesa). Son listas de texto dentro de una caja.
2. Estilo de «tarjeta de app»: sin borde grueso de tinta, sin papel, sombra difusa. El juego pide tinta, papel y sombra plana.
3. Espacio muerto y texto de ayuda permanente: la cabecera ocupa ~28 % del alto; Contrarreloj y Rastrear dejan ~40 % vacío.
4. Color sin intención: el amarillo es botón, rumor, selección y foco a la vez; el azul de «No veo…/Dejar pasar» no tiene rol.
5. Sin feedback visible de acierto, error ni cierre (sellos, aros, tachones).
6. Pantalla previa idéntica y de formulario (dos cajas de texto largo).

## 2. Qué NO se toca (contrato)

- Lógica: los seis `Partida*` (`frontend/minijuegos/*_calculos.py`), `backend/logica/minijuegos.py`, `logros_minijuegos.py`, `backend/datos/minijuegos_*.py`, `ResultadoMinijuego`.
- Flujo: `frontend/escenas/escena_minijuego.py`, `frontend/minijuegos/base.py`.
- Protegidos del proyecto y `frontend/extensiones.py`. No hace falta registrar nada: las vistas se descubren por `VISTAS` en `minijuegos_visual/__init__.py`.
- Contrato público por vista (lo usan el tutorial y los humos):
  - Rastrear: `elegir(i)`, `focables` (3 notas), teclas 1-3.
  - Comparar: `tarjetas`, `izq`, `alternar(i)`, `confirmar()`, `sin_diferencias()`, `boton_confirmar`, `boton_igual`, teclas c y n.
  - Chat: `opciones` (con `fijar_estado`), `responder(i)`, `partida`, `log`, teclas 1-3.
  - Señales: `tarjetas`, `alternar(i)`, `confirmar()`, `sin_senales()`, `boton_confirmar`, `boton_nada`, teclas c y n.
  - Contrarreloj: `filas`, `barras`, `rotulos`, `frenar()`, `dejar()`, `boton_frenar`, `boton_pasar`, `foco`, `tecla()`.
  - Todas: `focables`, `poner_foco`, `tecla`, `avanzar`, `terminar`, `es_tutorial`, y objetos marcables que imiten `ui.Tarjeta` (`estado`, `habilitada`, `al_clic`, `fijar_estado`, `fijar_foco`) para que `CapaVisual.repasar_revision` y el tutorial sigan funcionando (truco ya usado por `Vineta`).
- Sin cifras de indicadores a la vista; ningún estado solo por color (siempre forma o texto: palomita, tachón, aro discontinuo).

## 3. Arquitectura (cómo se construye)

El juego ya tiene una capa visual por minijuego (`frontend/minijuegos_visual/<x>_visual.py`, clase `XVisual(CapaVisual, MinijuegoX)` con guardián y bandera propia). El rediseño REEMPLAZA el dibujo de esas clases, no las vistas base:

- Se mantiene una bandera por vista (`ALCALDE_<X>_VISUAL`, ya existen) y el guardián: si algo falla, cae a la vista base de siempre.
- Se añaden módulos nuevos (nada de reescribir lo que funciona):
  - `minijuegos_visual/piezas_calculos.py` (puro, sin ursina, con tests): geometría de colas de globo, arcos, catenarias, discontinuas, esquinas dobladas, resaltador, colores por tercio.
  - `minijuegos_visual/comic.py`: extrae sin cambiar comportamiento lo duplicado en cronología (`_rgba`, `_triangulo`, marco de tinta, globo con cola, sello, cartela). Cronología pasa a usarlo solo si sus pruebas de captura siguen idénticas.
  - `minijuegos_visual/piezas.py`: las piezas (papel, cinta, chincheta, sello, globo, avatar, polaroid, resaltador, hilo, lupa, chip, botón-sello, indicador, «?»).
  - `minijuegos_visual/marco.py`: `MarcoMinijuego` (plantilla común de pantalla).
- Primitivas que faltan: `poligono`, `arco`, `discontinua`, `sombra`.
- Reutilizar lo que ya existe: `trazos.Linea`, `pistas_visuales_calculos` (catenaria, enredo, círculo de rotulador), `mapa_barrio_calculos`, `efectos_ui` (rebote, temblor, sello, estrellas), `iconos`/`dialogo_retratos` (avatares y retratos), `dibujos_avisos` (lupa, reloj, cadena de reenvíos), `telefono_marco`, `panel_tinta`.

### Plantilla común (MarcoMinijuego)
- Título del minijuego en una pestaña de tinta pequeña pegada al objeto (sale de la cabecera).
- Rumor: UNA línea en cinta amarilla con 2 chinchetas (máx. 90 caracteres, completo al enfocar).
- Intro, regla y pie de teclas: pasan a un botón «?» (papelito desplegable con regla + 3 teclas; abre con clic o Tab, cierra con Esc; también con el botón del mando).
- Zona de juego libre ≈ 0,80 de alto (hoy ≈ 0,50). Cuidado: el banner de resultado de la escena ocupa y -0,28 a -0,45; los controles que queden ahí se tapan solo al terminar, que es aceptable.
- Fondo «mesa de la ladera» (franja diagonal tenue) en vez del panel azul liso.
- Reglas de pieza: borde de tinta 3 px (2 px en chips), sombra plana (4,-5) px, rotación decorativa ±2° determinista (0° con «reducir movimiento»), texto mínimo ≥ 15-16 px en cuerpo y 13 px en etiquetas, nunca texto sobre textura (siempre papel debajo).
- Regla de color: amarillo = lo importante/seleccionable ahora; cian = camino/información (hilo, difusión, foco), nunca texto sobre papel; rojo = error, sello de bulo, hilo del rastro; verde = acierto. El azul-botón solo para acciones secundarias.

### Pantalla previa común
Se rediseña `pantalla_previa.py` como «portada de caso»: rumor como recorte de periódico, la escena/objeto del minijuego dibujado a la izquierda, «Cómo se juega» en 3 iconos con una frase corta cada uno, «Lo que practicas en redes» como etiqueta/post-it de una frase, botón Empezar grande sin «>>». Debe conservar `tarjetas` y `boton_tutorial` (los usa el humo del tutorial).

## 4. Conceptos por minijuego

### Comparar dos versiones (esfuerzo M, impacto alto)
Dos DOCUMENTOS lado a lado: original en papel crema (sello «ORIGINAL» opcional) y copia en papel viejo con arrugas, esquina doblada y mancha de café. Renglones con microetiqueta («Tema», «Efecto») sobre el valor. Pasarela de 6 puntos entre hojas que se enciende con el renglón enfocado. Marcar = resaltador amarillo que barre en 180 ms. Confirmar y «No veo diferencias» como botones-sello debajo de las hojas. Cierre: aciertos con banda verde y círculo, falsas alarmas con banda roja y tachón, la diferencia que faltó con aro rojo discontinuo; sello VERIFICADO/BULO sobre la copia. Se elimina el encabezado largo y el pie de teclas.

### Rastrear la fuente (esfuerzo S-M, impacto alto)
Tablero de corcho donde el hilo es la estructura: franja superior = cadena que crece de derecha a izquierda (polaroid «TÚ» → notas clavadas → polaroid de la fuente con sello «FUENTE»); franja inferior = 3 notas candidatas grandes en papel con cabecera (quién + hora), cuerpo y pie con chip «>>» si es reenvío (esquina doblada). La regla se vuelve visual y desaparece el párrafo. «Rodeos» = 2 ovillos que se apagan al errar. Foco: sube y borde amarillo; error: tiembla, el hilo hace un nudo, la nota queda inerte; acierto: el hilo se tensa y una luz cian recorre la cadena al cierre.

### Chat del barrio (esfuerzo M, impacto alto)
Móvil grande a la izquierda con cabecera de grupo, burbujas con cola y avatares con inicial/color, indicador «escribiendo…» con puntos, historial propio en cian. Las 3 respuestas NO caben legibles dentro del móvil: van como globos-botón de papel a la derecha con la cola hacia el teléfono y número en círculo. La presión pasa de barra a reloj circular (cian → aviso → rojo) con 3 avatares «esperando» que se inclinan y muestran «!» al final. Cierre con resumen en una línea y sello A SALVO / DATOS REGALADOS. Se mantiene sin delatar la respuesta (el aviso de datos se lee del texto, no de `valor`). Requiere sustituir el `Text` único del log por burbujas.

### Contrarreloj (esfuerzo L, impacto alto)
El mapa del barrio pasa a ser la «mesa» (≈ 60 % del ancho) con edificios dibujados y nombres de lugar; el contagio se ve como manchas que crecen (reutiliza `mapa_barrio_calculos`). A la derecha, cinta de teletipo con las noticias como tarjetas que bajan hacia una línea «llegó al barrio»; la tarjeta con foco se enlaza al mapa con línea cian discontinua. Reloj de la ronda como cápsula/cronómetro (rojo en el último 25 %). FRENA y DEJA PASAR como pulsadores grandes con icono (mano / flecha), sin azul genérico. Sellos FRENADA, ERA CIERTA y BARRIO A SALVO/CONTAGIADO. Atención: esta vista sobrescribe `tecla()` (no `tecla_propia`) y tiene `focables = []`; el foco es `foco`.

### Señales de edición (esfuerzo L, impacto alto; el último)
La «captura» deja de ser una lista: es una captura de móvil dibujada (barra superior con hora «25:70», avatar, burbujas) y cada zona es una región del dibujo, no una fila. La lupa pasa a ser un aro cian transparente con halo amarillo y una pestaña con la etiqueta de la zona («Cuenta», «Hora», «Promesa»); ya no tapa el texto ni lo repite. Marcar = sello rojo «RARO» inclinado; contador = 3 casillas que se rellenan. Ficha de pista (papel con pestaña) con la pregunta corta de la zona y los dos botones debajo. Cierre: señales reales con sello «TRUCO», marcas falsas tachadas. Solo maquetación: zonas y reglas no cambian.

## 5. Fases, entregables y criterio de «hecho»

Cada fase se prueba aparte y detrás de su bandera; entre fases el juego sigue funcionando.

| Fase | Contenido | Criterio de hecho |
|---|---|---|
| F0 Preparación | Capturar el estado actual (inicio, foco, acierto, error, cierre, previa) de las 5 como línea base. Confirmar cómo el humo identifica las vistas con capa (`type(v).__name__`) antes de renombrar nada. Decidir las preguntas de la sección 7. | Línea base guardada; decisiones anotadas. |
| F1 Kit | `piezas_calculos.py` + `comic.py` + `piezas.py` + primitivas, tests puros, y una escena «galería» que muestra todas las piezas y estados. | Tests puros verdes; galería en ventana real revisada; cronología sin cambios visibles. |
| F2 Marco y previa | `MarcoMinijuego`, botón «?», cinta de rumor, portada de caso. Se valida primero sobre cronología (sin empeorarla). | Previa y marco en los 6; tutorial y humos intactos. |
| F3 Comparar | Ver concepto. | Humos + tutorial verdes; capturas de todos los estados. |
| F4 Rastrear | Ver concepto. | Idem. |
| F5 Chat | Ver concepto. | Idem; legibilidad y reloj revisados. |
| F6 Contrarreloj | Ver concepto. | Idem; rendimiento (nº de entidades) medido. |
| F7 Señales | Ver concepto. | Idem. |
| F8 Pasada transversal | `posicion_sello`/`posicion_estrellas` por minijuego, reducir movimiento, contraste (`estilo.contraste` ≥ 4,5), mando (foco y botones), repaso con auditores, actualizar capturas de la web y la bóveda. | Auditoría de diseño y accesibilidad sin bloqueantes. |

Orden recomendado (impacto visible / esfuerzo): kit → marco+previa → Comparar → Rastrear → Chat → Contrarreloj → Señales. Si hay que recortar: Comparar, Rastrear y Contrarreloj dan el cambio más visible.

## 6. Verificación en cada fase
- Tests puros nuevos para todo cálculo (hoy los `*_visual_calculos` no tienen pruebas: se añaden).
- `tests/humo_minijuegos_mundo.py` (47 misiones) y `tests/humo_tutorial_mision.py`; ambos deben seguir verdes.
- Capturas en ventana real de cada estado (normal, foco, marcado, acierto, error, tiempo, cierre) y con «reducir movimiento».
- Con bandera apagada (`ALCALDE_<X>_VISUAL=0`) la vista base queda exactamente como hoy; con fallo forzado cae a la base.
- Suite completa contra la línea base (46 fallos + 6 errores previos).
- Subagentes por fase: `preservador` (regresión), `code-reviewer`, y al final `auditor-diseno-generico` y `accessibility-tester`.

## 7. Decisiones del dueño (con propuesta por defecto)
1. Tamaño mínimo de texto: propuesta 15-16 px cuerpo, 13 px etiquetas (los pies de hoy tienen 12-14 px y se leen mal).
2. Sello «ORIGINAL» en Comparar: revela cuál hoja es la buena; propuesta: dejarlo (la mecánica es hallar qué cambió).
3. Paleta de roles para avatares (`COLORES_ROL_PROPUESTOS`, marcada «decisión del dueño, aún no usada»): propuesta: usarla.
4. Nombres de lugar en portugués en el mapa de Contrarreloj (Feira, Praça, Igreja…): propuesta: mantenerlos con su glosa en la ayuda, como el resto del juego.
5. Quitar el pie de teclas y moverlo al «?» (también para mando): propuesta: sí.
6. Ritmo: una fase por vez con su bandera (recomendado) o todo junto.

## 8. Riesgos
- El tutorial y los humos dependen de nombres de atributos y botones (sección 2): cualquier objeto nuevo debe imitar `ui.Tarjeta`.
- `ui.py` y `telefono_marco.py` los usan otras pantallas (Civitas, rectificar): no se modifican; se añaden piezas aparte.
- Chat: sustituir el `Text` único por burbujas es el cambio más profundo de las vistas base.
- Rendimiento: muchas entidades pequeñas (mapa, cinta, burbujas); medir y agrupar en mallas si hace falta.
- Legibilidad: nada de texto sobre corcho o trama; el sello solo tras responder; la lupa nunca tapa texto necesario.
- Daltonismo: acierto = ✓ + verde, error = ✕ + rojo + forma distinta.
- Ausencia de pruebas de la capa visual actual: se escriben con el rediseño, no antes.
