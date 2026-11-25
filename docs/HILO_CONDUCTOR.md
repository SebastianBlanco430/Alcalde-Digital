# Hilo conductor de las elecciones — banderas y funcionamiento

Las misiones, los minijuegos y el feed se unen con un hilo que el jugador **deduce** (ningún texto lo dice): la campaña
del alcalde de siempre firma la mayoría de los rumores falsos con el **sello de la Torre de la Tradición**. A eso se
suman la **Rádio Comunitária** (mañana y noche), los **comentarios de los NPC** según lo que hizo el jugador, una semana
de **15 minutos con las noches saltadas** y un **prólogo** antes de la intro. Todo va tras banderas: con `ALCALDE_HILO=0`
el juego queda como antes.

Ver también `docs/MODO_FERIA.md` (semana que avanza por misiones, sin reloj).

## Banderas

Valores: `0/false/no/off` apaga y `1/true/si/sí/on` enciende. `ALCALDE_HILO=0` apaga todas las de abajo salvo el
prólogo y la feria.

| Variable | Por defecto | Qué hace |
|---|---|---|
| `ALCALDE_HILO` | encendida | Maestra del hilo conductor. |
| `ALCALDE_HILO_SELLO` | encendida | Sello en mensajes, feed y minijuegos; carteles de campaña del día 5. |
| `ALCALDE_HILO_RADIO` | encendida | Rádio Comunitária. Apagada: no hay emisiones y la noche se salta sin pausa. |
| `ALCALDE_HILO_NPC` | encendida | Frases de vecinos según el tema y el resultado del día anterior. |
| `ALCALDE_HILO_NOCHES` | encendida | Días de 08:00 a 20:00, noches saltadas y fin el día 7 a las 20:00 (84 h activas ≈ 15 min). |
| `ALCALDE_HILO_LEY_SECA` | encendida | Cambia solo el `mensaje` de `candidato_ley_seca` («¡Atención! …»). |
| `ALCALDE_PROLOGO` | encendida | Prólogo 3D tras elegir personaje y antes del tutorial. `0` = directo al tutorial. |
| `ALCALDE_SEG_POR_HORA` | — | Sigue mandando sobre la escala del reloj (p. ej. `2` para probar la semana rápido). |

## Piezas

### Sello de la Torre de la Tradición
- Qué rumores lo llevan: `backend/datos/sello_rumores.json` y `backend/logica/sello_rumores.py`. De los 22 rumores
  falsos, 15 llevan sello y 7 no.
- Capas por día: **1**, diminuto y desvaído en la esquina del mensaje; **2**, junto al remitente y como marca de agua
  en «Señales de edición» y «Comparar»; **3**, tamaño completo y espejo en el mundo; **4**, igual que la 3.
- Dibujo con primitivas (sin texturas): `frontend/sello_tradicion.py` y `sello_tradicion_calculos.py`.
- Dónde se ve: banner y teléfono (`frontend/hud.py`) y marca de agua (`frontend/sello_marca_agua.py`, que usan
  `minijuegos_3d/senales_3d.py`, `comparar_3d.py` y la vista 2D de `escenas/escena_minijuego.py`).
- Espejo del día 5: `frontend/carteles_campana.py` pone carteles de campaña en tres plazas (Praça da Sé, Mercado
  Municipal y Morro da Esperança) y envía al teléfono el anuncio del debate. Tablero granate con el sello grande,
  «TOMÁS ARENAS», el debate y una franja con «PARTIDO DE LA TRADICIÓN»; se lee por las dos caras.
  - Sitio: el primero libre de una lista de puntos del borde de cada plaza. Pasada estricta con la misma reserva que
    el decorado (`props_mundo.Reserva`) más todos los puestos de comercio; si no cabe ninguno, pasada relajada que
    permite quedar junto a un camino, pero nunca sobre edificios, obstáculos o puestos, delante de un mostrador ni a
    menos de 3,5 m de una puerta.
- El sello NO va en la pantalla grande del teléfono (tecla L): allí se ven los avisos, dilemas y el feed de Civitas,
  no los mensajes de misión. El sello sobre los avisos de Civitas sugeriría que Civitas es de la campaña.

### Rádio Comunitária
- Textos editables sin código: `backend/datos/radio_textos.json`. El guion se elige en `backend/logica/radio_guion.py`.
- **Mañana** (una línea): según el día y el estado de la ciudad (`bien`, `tenso` o `mal`).
- **Noche** (días 1-6): qué hizo el jugador (`acierto`, `error`, `mixto` o `nada`), qué pasó en la red sin él y una
  consecuencia visible. No da números. Las misiones sin terminar cuentan como «sin verificar».
- **Puente** (día 7): una línea antes del final de siempre, que no cambia.
- Cuándo emite: `frontend/radio_calculos.py` espera a un momento libre (sin minijuego, diálogo, dilema, teléfono ni
  pausa). Desde las 19:30 no se anuncian misiones nuevas en el banner (siguen llegando al teléfono).
- Cómo se ve: `frontend/radio_emision.py`, sobre el componente de viñetas (`crear_vinetas`; Escape la salta), con
  una radio animada en 2D (cálculos puros en `frontend/radio_animacion_calculos.py`): cielo según el momento
  (`radio_momento`: noche estrellada con luna, amanecer con el sol subiendo o atardecer del día 7), silueta de la
  ladera con ventanas, radio que respira, altavoz que late con la voz, antena con luz, aguja del dial, ondas, letrero
  «AO VIVO» y texto letra a letra. Con «reducir movimiento» queda quieta y el texto sale entero. Más adelante se quiere
  pasar a 3D. La
  engancha `frontend/radio_registro.py`, que retiene la noche hasta que termina la emisión y luego llama a
  `pasar_noche()`. Si algo falla, suelta la noche y el juego sigue sin radio. En línea no hay radio porque no hay reloj.

### NPC
- `backend/logica/globos.py` admite como condición el tema del día anterior y el resultado del jugador. La radio fija
  ese contexto después de cada noche.
- Frases nuevas («Dijeron en la radio que…» y reacciones por resultado) en `backend/datos/frases_npc.json`.

### Reloj con noches saltadas
- `backend/logica/reloj_partida.py`: el reloj se para a las 20:00 (`noche_pendiente()`) hasta que se llama a
  `pasar_noche()`, que lo lleva a las 08:00 del día siguiente. Escala por defecto: 900 / 84 ≈ 10,71 s por hora.
- `backend/logica/flujo_tiempo.py`: si nadie retiene la noche, la salta solo. Expone `retener_noches()` y el diario del
  día que usa la radio.

### Prólogo (3D)
- En 3D en la Ciudad Nova real, con el motor y los modelos del juego: `frontend/prologo_cinematica.py` (vista) y
  `prologo_calculos.py` (puro), con el guion en `backend/datos/prologo_cinematica.json`.
- Cuándo: partida local nueva (normal o feria), DESPUÉS de elegir personaje, al entrar al mundo; nunca al «Continuar»
  ni en línea. Al terminar queda la pantalla en negro y sale la cinemática del tutorial (`intro_cinematica.py`, sin
  cambios): el prólogo pone `escena._cinematica = True` y el vigía del tutorial espera a que vuelva a `False`.
- Qué se ve: plano aéreo de la plaza («Ciudad Nova…»), los dos candidatos ante la Prefeitura (Tomás Arenas y Octavio
  Ruedas; «Faltan siete días para votar»), cartela «Dentro de siete días...», el futuro malo (Arenas reelegido, la
  ciudad ardiendo de noche), el bueno (Octavio gana, fiesta en la plaza) y la cartela final «La decisión depende de ti
  y de tus acciones.» (unos 70 s).
- Cómo: cada tramo «animado» lo rueda el director del final animado (`frontend/final_animado/director.py`) con un guion
  propio que reutiliza tomas y puestas ya hechas (`camaras.py`, `puesta.py`); el estado de la ciudad (neutro, malo,
  bueno) lo pone su escenografía. Un velo negro propio (`fundido_prologo`) tapa cargas y cortes.
- Saltar: mantener Espacio/Escape en los planos o Escape en una cartela salta todo el prólogo (después sale el
  tutorial). Si un tramo falla se salta y sigue; si falla todo, se va al tutorial.
- El menú ya no muestra nada: «Empezar» y «Modo feria» van directo a la selección de rol.

## Carga
`main.py` carga `radio_registro`, `modo_feria_registro`, `carteles_campana` y `prologo_cinematica` con
`extensiones.aplicar(..., modulos=MODULOS_HILO)`, después de las extensiones de siempre. No se editan los módulos
congelados (`registro_reloj.py`, `reloj_calculos.py`, `registro_tutorial.py`, `reparto_dias.py`, `extensiones.py`,
`guardado.py`, …): solo se usa su API pública.

## Cómo probar
- Partida normal con `ALCALDE_SEG_POR_HORA=2`: radio a las 08:00 y a las 20:00, fundido de noche, puente y final del
  día 7.
- Cada bandera en `0`: esa parte desaparece y el resto sigue.
- Tests sin ventana: `tests/test_hilo_conductor.py` y `tests/test_hilo_tiempo.py` (locales, ignorados por git).
