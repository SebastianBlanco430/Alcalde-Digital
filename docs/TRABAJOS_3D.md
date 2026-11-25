# Trabajos 3D y correcciones (Persona B)

Cuatro cambios, cada uno tras su bandera `ALCALDE_*` (encendida por defecto; `=0` devuelve exactamente lo de antes).
La escena de trabajo (`frontend/escenas/escena_trabajo.py`) conserva su contrato: `al_entrar(jugador, trabajo,
al_terminar, semilla)` y `al_terminar(resultado)` con las mismas claves `{aciertos, errores, rendimiento, pago,
fatiga}`; el mostrador añade las opcionales `cambios_mal` y `convivencia`.

## Banderas

| Bandera | Por defecto | Qué hace | Dónde se lee |
|---|---|---|---|
| `ALCALDE_TALLER3D` | 1 | Taller de Beto en 3D | `frontend/taller3d_calculos.py` |
| `ALCALDE_TALLER3D_VELOCIDAD` | 1.2 | Rapidez de las flechas del taller 3D (1.2 = cruzan en 2,5 s en vez de 3,0 s; acota 0,5-2,5) | `frontend/taller3d_calculos.py` |
| `ALCALDE_TALLER3D_CADENCIA` | 1.4 | Cuán seguidas llegan las flechas del taller 3D (1.4 = de 1,5-1,05 s entre flechas a 1,07-0,75 s) | `frontend/taller3d_calculos.py` |
| `ALCALDE_MOSTRADOR3D` | 1 | Mostrador 3D en primera persona en los 4 trabajos ATENDER | `frontend/mostrador3d_escena.py` |
| `ALCALDE_PARKOUR_SIN_RUTA` | 1 | El panel final del parkour no enseña la ruta Dijkstra | `frontend/parkour_hud.py` |
| `ALCALDE_BANCOS_SENTADOS` | 1 | NPC de Blender sentados en los bancos (en vez de figuras de bloques) | `frontend/bancos_sentados_calculos.py` |
| `ALCALDE_BANCOS_CORROS` | 1 | Corros de las plazas con NPC de Blender charlando (en vez de figuras de bloques) | `frontend/bancos_sentados_calculos.py` |

## Taller 3D (motor RITMO)

- `frontend/taller3d_escena.py` — `JuegoTaller3D` hereda de `taller_vista.JuegoTaller`: reutiliza el carril de flechas,
  el cartel y los avisos (2D) y cambia el dibujo del taller por un set 3D (taller de favela en una malla, luz cálida,
  cámara fija en tercera persona). El personaje del jugador (modelo de su rol) martilla con IK de mano
  (`minijuegos_3d/poses_3d`) con el puño cerrado (`cerrar_puno`: dedos por `controlJoint`, según el esqueleto Rigify
  o el de la influencer) y el martillo saliendo del centro del puño. `PiezaGiratoria` muestra la pieza terminada en el
  panel de resultado.
- `frontend/taller3d_piezas.py` — 8 piezas por código (engranaje, llave inglesa, tuerca y tornillo, pistón, bisagra, rueda
  de bicicleta, lámpara, radio), formadas parte a parte con el progreso.
- `frontend/taller3d_calculos.py` — calidad -> acabado: prístina (calidad >= 0,9, con brillo) o deforme (ruido suave,
  una abolladura por golpe malo, óxido), con grados intermedios. Curva del martillazo.
- `backend/datos/piezas_taller.py` — `PIEZAS_TALLER_3D`: 21 entradas (8 piezas con 2-3 materiales) elegidas con la
  semilla del turno. `PIEZAS_TALLER` (2D) no cambia.
- `backend/logica/taller_ritmo.py` — `TurnoRitmo(..., velocidad=1.0, cadencia=1.0)`: `velocidad` acorta el viaje de las
  notas y `cadencia` las junta; ventana y pago (pago_max x calidad) iguales. El turno del taller dura 30 s
  (`backend/datos/trabajos_semilla.py`, antes 60).

## Mostrador 3D (motor ATENDER: panadería, supermercado, feria, bar)

- `backend/logica/mostrador3d_dinero.py` — reales en centavos: billetes R$ 2-200, monedas R$ 0,05-1, pago del cliente
  (billete superior o billete + centavos: NUNCA paga justo, siempre hay cambio que dar), cambio y validación. Puro y probado.
- `backend/logica/mostrador3d_turno.py` — `TurnoMostrador`: LLEGANDO -> PEDIDO -> CAMBIO -> SALIENDO por cliente.
  Meta de 2,5 s por acción (como el ATENDER de siempre); cada cambio mal dado = error y `cambios_mal`.
- `backend/datos/mostrador3d_locales.json` — productos (en el orden de las teclas 1-4), precios, forma, colores y toldo de
  cada local.
- `frontend/mostrador3d_escena.py` — primera persona detrás del puesto, calle del mercado de fondo, 4 cajones con
  letrero de precio, repisa, cliente NPC (3 que se turnan) con globo; enojado = sacudida + globo rojo. Cartel 2D con
  pedido, total, pago y cambio; botones «Dar cambio» y «Quitar».
- `frontend/mostrador3d_calculos.py` — mirada libre en primera persona: clic derecho + ratón (o flechas) gira la cabeza
  (topes: 75 grados a los lados, -40/+30 arriba/abajo), C la vuelve al cliente; el clic izquierdo sigue para productos y dinero.
  Los interiores están cerrados (pared detrás del jugador) y el cielo es una caja: no hay vacío al girar.
  Solo en la feria y el bar (`mirada_libre` en el JSON); en la panadería y el supermercado la cámara es fija.
- `frontend/mostrador3d_fondos.py` — un fondo por local (clave `fondo` del JSON): calle de la feria (exterior, con toldo),
  panadería (vitrina, canastas, pizarra con los precios del local, luz cálida), supermercado (góndolas, carteles de
  pasillo, otra caja, fluorescentes) y bar (mesas de plástico, cajas de cerveza, tele con el partido, guirnalda, portón
  a la calle al atardecer). Los interiores llevan techo con lámparas en vez de toldo.
- `frontend/mostrador3d_caja.py` — caja registradora: cajón con los 12 valores (clic = a la bandeja), bandeja del cambio
  (clic = devolver a la caja), pago del cliente sobre el mostrador.
- `frontend/mostrador3d_productos.py` — mallas por código de productos, cajones, billetes y monedas (colores
  genéricos, solo la denominación escrita).
- `frontend/mostrador3d_convivencia.py` — cada cambio mal dado baja 1 la convivencia (tope 3 por turno) con
  `EstadoPartida.aplicar_deltas` de la sesión del mundo; solo en partida local. Lo engancha
  `frontend/trabajo_mundo.conectar()` y lo aplica la escena (controlador), no la vista.

Tutorial del taller (`frontend/tutorial_mision_trabajo.py`, 2D): la animación avanza con el juego (las flechas ya resueltas
se encogen o caen y se borran; antes se quedaban en el carril y se solapaban), el cuerpo del trabajador acompaña el
martillazo y respira (`taller_vista.JuegoTaller`), y las flechas van tan rápidas como en el turno de verdad.

## Parkour sin ruta

`frontend/parkour_hud.py`: con la bandera, el panel de resultado omite la línea «Ruta óptima (Dijkstra)» y el bloque
`textos_ruta_dijkstra`. `parkour_calculos.py` y `parkour_loader.py` no cambian (el loader sigue validando con Dijkstra).
No había geometría de ruta en el mundo del parkour; las rutas del minimapa del mundo son el GPS de misiones.

## Bancos sentados

- Antes: `frontend/ciudad_viva.py` (capa «bancos») ponía figuras de cajas e icosferas (`mesh_sentados`).
- Ahora: `frontend/bancos_sentados.py` crea 6 NPC de Blender (`npc_hombre_01..03`, `npc_mujer_01..02`, aspecto de
  peatón determinista) en la MISMA piscina `ciudad_viva.Grupo` (reparto, fundido y cantidad de siempre), sin colisión,
  sin mochila, con el clip `HumSentado`: pose de sentado propia (`frontend/bancos_sentados_calculos.pose_sentado`:
  cadera baja, pies por delante de las rodillas para que la espinilla baje por fuera del asiento (antes cruzaba el
  canto de la tabla), manos en los muslos, respira y mira alrededor) que
  `frontend/animacion_humana.hornear_clips` hornea solo con la bandera encendida. Si algo falla, vuelven las figuras.
- Coste medido (`scripts/medir_fps.py`, 15 s): 63,9 FPS de media con NPC sentados frente a 66,3 sin ellos.

## Corros de las plazas

- Antes: `ciudad_viva.mesh_corro`, cinco figuras de bloques en rueda con una bocina.
- Ahora: `bancos_sentados.crear_grupo_corros` crea 2 corros (la piscina `ciudad_viva.Grupo` de la capa «corros») de 4
  NPC de Blender de pie, en rueda mirando al centro (`puestos_corro`), con el clip `HumCharla` (`pose_charla`: cambian el
  peso de pierna, gesticulan con una mano mientras hablan, asienten y miran a los demás), cada uno con su velocidad y
  fotograma de inicio para que no vayan sincronizados, y la bocina de siempre en el medio. Sin colisión ni mochila.
- Coste medido (15 s): 65,9 FPS de media con corros de NPC frente a 64,8 sin ellos (dentro del ruido).

## Cómo probar

```
python main.py                                   # todo encendido
ALCALDE_TALLER3D=0 python main.py                # taller 2D de antes
ALCALDE_TALLER3D_VELOCIDAD=1.0 python main.py    # flechas a la velocidad de antes en el taller 3D
ALCALDE_MOSTRADOR3D=0 python main.py             # ATENDER 2D de antes
ALCALDE_PARKOUR_SIN_RUTA=0 python main.py        # vuelve la ruta Dijkstra al panel del parkour
ALCALDE_BANCOS_SENTADOS=0 python main.py         # figuras de bloques en los bancos
ALCALDE_BANCOS_CORROS=0 python main.py           # figuras de bloques en los corros
pytest tests/test_taller3d_calculos.py tests/test_mostrador3d.py tests/test_bancos_sentados.py tests/test_parkour_sin_ruta.py
```
