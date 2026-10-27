# Contenido sensible, dinero ficticio y clasificación por edades

> **Borrador para revisión legal antes de publicar.** No soy abogado y esto no es asesoría legal. El proyecto es
> de aprendizaje y no se publica en tiendas. Este texto cubre los requisitos que conozco; no afirma que ninguna
> tienda vaya a aprobar el juego ni que cumpla ninguna ley. Las políticas de Apple, Google y las autoridades de
> clasificación cambian: hay que releerlas el día de publicar.
>
> Versión 1.0 · 2026-10-25 (ronda 7, cambios sin commit)

## 1. Descripción del contenido

Juego de ficción en 3D sobre **desinformación** en una favela brasileña. El jugador camina, habla con vecinos,
resuelve misiones y toma decisiones.

Novedades de la ronda 7:

- **Inventario realista** (tecla I): bolsillo, cintura, manos, mochila; peso y espacio.
- **Dinero ficticio en reales (R$)** y tiendas del mercado. **No hay compras reales, ni moneda premium, ni cajas
  de botín (loot boxes), ni apuestas, ni publicidad.**
- **Trabajos** en minijuegos 2D con **cansancio** (con fatiga >= 100 no se puede trabajar).
- **Seu Zé**, vendedor de calle: vende una «bolsita de bicarbonato» (R$ 5) con un gesto de pasarla de mano a mano.
  El ítem se describe en el juego como bicarbonato de sodio: «sirve para cocinar y limpiar. No cura nada».
  Es parte de la ficción sobre bulos de salud.
- **Objetos sensibles** `pistola` y `cuchillo_pequeno` en el catálogo (`backend/datos/items_semilla.py`): objetos
  de cintura **sin precio, sin efecto, sin forma de obtenerlos** y ocultos tras `ITEMS_SENSIBLES = False`.
  No se disparan ni se usan; no hay combate en el juego.
- **Decorado preexistente** `puesto_talco` («TALCO SUSPEITO / só pra bebê ;)») y `armeria_juguete` («ARSENAL DE
  BRINQUEDO / só água!», pistolas de agua de colores), bajo la bandera de huevos de pascua (`EASTER_EGGS`).
- **Mapa más grande** con lugares como Posto de Saúde, Bar do Cabo e Igreja (referencias a salud, alcohol en un
  bar y religión; sin consumo representado).
- **Online:** sigue sin sincronizar inventario ni dinero (ver `docs/PRIVACIDAD_ONLINE.md`). Trabajar en línea está
  apagado (`TRABAJO_ONLINE = False`).

No hay: sangre, violencia mostrada, consumo de drogas o alcohol representado, desnudez, lenguaje soez grave,
chat libre, compras reales, apuestas simuladas.

## 2. Análisis de riesgo: vendedor de «polvo blanco» + armas + favela

**Ojo: es una combinación con riesgo real de revisión**, aunque cada pieza sola sea inocente.

- Un revisor humano o automático ve: *vendedor de calle + bolsita con polvo blanco + pistola en inventario +
  favela*. Eso evoca el estereotipo «tráfico de drogas y armas en la favela». Puede provocar: (a) un rechazo
  por «representación de drogas» o «armas realistas»; (b) una clasificación por edades más alta (p. ej. 16+/18+ o
  su equivalente) por referencias a drogas; (c) críticas de estigmatización de comunidades.
- La intención del juego (desinformación, bicarbonato inofensivo) es defendible, pero el revisor evalúa lo que
  **se ve en pantalla**, no la intención. Una bolsita blanca pasada de mano a mano es visualmente ambigua.
- Las pistolas de agua y el «TALCO SUSPEITO ;)» refuerzan la lectura de broma con drogas (el guiño «;)» es el
  elemento más arriesgado de todos).
- Qué sí ayuda: las armas están fuera por defecto, sin uso, sin obtención; el ítem dice qué es; todo el dinero
  es ficticio; no hay violencia ni consumo.

### Mitigaciones propuestas

**De texto** (mantienen lo que pide el dueño):

1. Mantener la descripción explícita del ítem y mostrarla **en el aviso de compra** («E: comprar bicarbonato de
   sodio (R$ 5)») y en la ficha de la tienda en las capturas.
2. Cartel visible en el puesto de Seu Zé: «Bicarbonato de sódio — cozinha e limpeza». Nombre completo, sin
   apodos ni jerga.
3. En la ficha de la tienda: «Ficción satírica sobre desinformación. Todo el dinero y los objetos son ficticios.
   No promueve drogas ni armas». Nunca describir al personaje como «traficante» ni «camello».
4. **Cambiar o retirar el guiño** de `puesto_talco`: «TALCO SUSPEITO / só pra bebê ;)» debería ser, por ejemplo,
   «TALCO DE BEBÊ» sin «suspeito» ni «;)», o dejarse solo en builds de desarrollo.
5. Diálogos de Seu Zé: nada de susurros, vigilancia policial, «calidad» o «pureza»; tono de feriante normal.

**De diseño:**

1. **Presentación del puesto:** ponerlo a plena luz en la feria (toldo, balanza, otros productos de cocina),
   no en un callejón. Bolsita con etiqueta legible «BICARBONATO» o caja de bicarbonato de cocina; evitar la bolsita
   transparente con polvo (la opción que más se parece a una droga). El gesto de mano a mano se mantiene.
2. **Armas:** conservar `ITEMS_SENSIBLES = False` en **toda build destinada a una tienda**. Si el dueño las quiere
   en una build propia: sin disparar, sin munición, sin daño, sin animación de apuntar, sin ninguna misión que las
   use, y sin que se puedan comprar, vender ni intercambiar. Mejor aún: tratarlas como «objeto de utilería» con
   un modelo claramente estilizado.
3. **Nunca activar a la vez** `ITEMS_SENSIBLES` y `VENDEDOR_CALLE` en una build para tiendas sin haber evaluado
   la clasificación más alta (ver sección 4). Sugerencia: un perfil de build `tienda` (sensibles apagados, huevos
   de pascua apagados) y otro `completo` (solo uso personal/estudio).
4. Mantener los huevos de pascua (`EASTER_EGGS`) desactivados en la build de tienda.
5. Que la bandera de sensibles no se pueda activar desde la interfaz del jugador, solo desde la configuración de
   la build.

## 3. Banderas para desactivar contenido sensible

| Bandera | Archivo | Por defecto | Efecto al apagar |
|---|---|---|---|
| `ITEMS_SENSIBLES` | `frontend/economia_config.py` | `False` | Oculta pistola y cuchillo pequeño |
| `VENDEDOR_CALLE` | `frontend/economia_config.py` | `True` | Quita a Seu Zé y la bolsita de bicarbonato |
| `GESTOS_MANO` | `frontend/economia_config.py` | `True` | Quita el gesto de dar/recibir |
| `COMERCIOS` | `frontend/economia_config.py` | `True` | Quita las tiendas |
| `TRABAJOS` | `frontend/economia_config.py` | `True` | Quita los trabajos |
| `CANSANCIO` | `frontend/economia_config.py` | `True` | Quita la fatiga |
| `TRABAJO_ONLINE` | `frontend/economia_config.py` | `False` | Trabajo en línea (apagado) |
| `ALCALDE_ECONOMIA=0` | variable de entorno | economía activa | Apaga inventario, dinero y pagos |
| `EASTER_EGGS` | `backend/datos/barrio_favela.py` | (ver archivo) | Quita `puesto_talco` y `armeria_juguete` |

**Pendiente de desarrollo:** el nombre y valor de `EASTER_EGGS` no se verificó aquí; confirmar que apagarlo
también oculta los letreros (`letreros_secretos`). Ninguna bandera sensible debería poder cambiarse desde el
juego ya en ejecución.

## 4. Dinero ficticio

- El R$ del juego es **moneda virtual sin valor real**: no se compra con dinero real, no se canjea, no se retira,
  no se transfiere entre jugadores (el online no sincroniza dinero ni inventario).
- Sin compras dentro de la app, sin suscripciones, sin cajas de botín, sin apuestas ni azar con dinero. Por eso
  no aplican, según lo que conozco, las reglas de juegos de azar ni las de probabilidades de loot boxes.
- Los precios (R$ 1 a R$ 100) son de ambientación. Evitar usar marcas reales o logotipos bancarios.
- Si algún día se añade una compra real, una moneda premium o publicidad, **este documento, las etiquetas de
  privacidad y la clasificación deben rehacerse**.
- Los trabajos con cansancio no deben presentarse como incentivo para pagar ni para esperar (sin «recarga de
  energía» de pago).

## 5. Cuestionario de clasificación por edades (sugerido)

Respuestas **propuestas** según el estado actual con `ITEMS_SENSIBLES = False` y EASTER_EGGS apagado. Son un
punto de partida para IARC (Google Play y otros), el cuestionario de Apple y la clasificación brasileña.
**Una persona con autoridad debe responderlo con las preguntas vigentes del día.**

| Tema | Respuesta sugerida (build tienda) | Si se activan sensibles/huevos |
|---|---|---|
| Violencia | Ninguna | Ninguna mostrada, pero hay armas en inventario: responder «referencias a armas» |
| Armas | Ninguna | Presentes, sin uso: **declarar** |
| Sangre / gore | No | No |
| Contenido sexual / desnudez | No | No |
| Lenguaje soez | No / leve (verificar diálogos) | Igual |
| Drogas, alcohol, tabaco | Una **referencia** a un polvo (bicarbonato) vendido en la calle; un bar. Sin consumo. Por prudencia, declarar «referencias a sustancias» y explicar en las notas | Declarar claramente: el guiño «talco suspeito» es referencia a drogas |
| Apuestas / casino simulado | No | No |
| Compras dentro de la app / loot boxes | No | No |
| Dinero real / moneda ficticia | Solo moneda ficticia | Igual |
| Chat entre usuarios / contenido generado | No hay chat libre; solo alias y saludos fijos | Igual |
| Ubicación, datos personales | No se recolecta ubicación real; IP en online (ver privacidad) | Igual |
| Interacción online con desconocidos | Sí (si se abre el online a internet) | Igual |
| Temática | Sátira sobre desinformación; contexto de favela | Igual |
| Menores | Sin dirigirse a menores; edad mínima a definir | Igual |

Resultado esperable (no garantizado): clasificación media («adolescentes» o equivalente) en la build tienda; más
alta si se declaran drogas y armas. El resultado lo decide la autoridad de clasificación, no este documento.

**Brasil:** el juego se ambienta allí y está en portugués/español. Un abogado debe confirmar si hay obligación de
clasificación indicativa (Classificação Indicativa) o normas de protección de menores en entornos digitales para
la distribución en ese país.

## 6. Pendiente de revisión legal

- Respuestas finales del cuestionario por edades y la clasificación obligatoria por país.
- Si el aspecto «vendedor de bolsitas + favela» puede considerarse estigmatizante o promotor de drogas en cada
  tienda y país; texto final de la ficha.
- Si las armas, aun tras bandera apagada y sin uso, deben declararse (el código está en el paquete).
- Edad mínima, consentimiento y menores en el modo online.
- Uso de nombres, lugares o símbolos religiosos (Igreja) y de salud (Posto de Saúde) sin dar a entender que
  son reales.

## 7. Preguntas para el dueño

1. ¿Se piensa publicar en tienda alguna vez, o es solo estudio? (hoy: estudio)
2. ¿Aceptas retirar el guiño «;)»/«suspeito» del puesto de talco y cambiar la bolsita a una etiqueta legible?
3. ¿Las armas deben quedar apagadas en la build de tienda?
4. País de publicación y datos del responsable (para la política pública).
