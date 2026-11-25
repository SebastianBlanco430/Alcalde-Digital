# Paridad del multijugador (Persona B, ronda 2)

Qué de la partida de 1 jugador llega al multijugador por turnos (hot-seat, 2-4 en un equipo) y en línea (anfitrión +
clientes), cómo se comporta con varios jugadores y qué quedó fuera (por qué y cómo se haría).

## Banderas

| Bandera | Por defecto | Qué hace | Dónde se lee |
|---|---|---|---|
| `ALCALDE_MULTI_PARIDAD` | 1 | Reloj de la sala en línea (15 min, noches, radio, sello y NPC del día), protocolo v7, prólogo y final animado en línea | `backend/red/multi_reloj.py` (`activo()`); `backend/red/protocolo.py` la lee con `os.environ` al importarse con la MISMA regla (por eso no hay constante en el código: solo el entorno) |

Con `ALCALDE_MULTI_PARIDAD=0` el multijugador es exactamente el de antes: protocolo v6, sin mensajes nuevos, sin reloj en
línea ni prólogo en línea. **Las máquinas de una sala tienen que tener la bandera igual**: cambia la versión del
protocolo y una sala v7 rechaza a un v6 (y al revés) con el mensaje de versión de siempre (`anfitrion.texto_version`).

## Diagnóstico (antes de este cambio)

**Por turnos.** Usa el mismo `crear_flujo` que la partida de 1 jugador (`main.py`), así que ya tenía reloj de 15 min con
noches saltadas, radio de mañana y noche, sello por días, NPC que comentan el día anterior, modo feria, prólogo e intro,
trabajos 3D, bancos sentados, misiones por días y casos v2. Un único reloj para todos; la radio cuenta el diario de todo
el grupo; cada turno es una misión (`FlujoPartida._dar_turno`).

**En línea.** `FlujoEnLinea` (`frontend/online_flujo.py`) es otra clase, sin `reloj`, y el protocolo v6 no tenía ningún
mensaje de tiempo. Por eso no había radio, noches, sello por días, NPC del día, prólogo ni intro, y además siguen
apagados a propósito los trabajos, los dilemas y el guardado. Las misiones se reparten por **progreso** con la semilla
del mundo (`mision_coop.ReservaMisiones`), no por reloj.

## Lo que se llevó

### Reloj de la sala en línea (lo que más pesaba)

- **El anfitrión manda** (`backend/red/multi_reloj.py`, `RelojSala`): un `RelojPartida` para toda la sala, que avanza con
  el tick del anfitrión (1 s; se suma en horas porque `RelojPartida.avanzar` recorta cada paso a 0,5 s) y se difunde en
  el mensaje `reloj` una vez por segundo y en cada cambio de día, de noche o de fin.
- **Noche**: a las 20:00 el reloj se para y en todos los clientes sale la radio de la noche. Pasa cuando **todos los
  conectados** avisan con `noche_lista` (al ponerse la viñeta de la mañana o al saltarla) o a los **20 s**
  (`PLAZO_NOCHE`); un desconectado no bloquea.
- **Fin por tiempo**: con el día 7 cerrado, `PartidaCooperativa` termina con motivo `tiempo` (el `fin` de siempre). Si
  alguien está dentro de un minijuego, se le espera hasta `GRACIA_FIN` (60 s) para que su decisión no se pierda.
- **Inicio**: el reloj no corre los primeros `ESPERA_INICIO` (65 s, lo que dura el prólogo; un test lo comprueba), como en
  la partida local, donde el reloj está parado durante las cinemáticas. Con `ALCALDE_PROLOGO=0` no se espera.
- **Siempre con noches saltadas** (como la feria), aunque el anfitrión tenga `ALCALDE_HILO_NOCHES=0`: la radio de la
  noche y el espejo de los clientes cuentan con el cierre de las 20:00.
- **Sin radio** (apagada o rota), el cliente avisa de la noche en cuanto llega, así no hace esperar 20 s a la sala.
- **Diario de la sala**: cada misión cerrada (de cualquiera) se anota con su veredicto; viaja con la noche y la radio
  cuenta el día del grupo.
- **Reconexión**: quien vuelve recibe la hora al momento (`_reconectar`).
- **Cliente** (`frontend/multi_reloj_linea.py`): `RelojEspejo` con la misma cara que `RelojPartida` (día, hora,
  `hora_texto`, `fraccion_partida`...) interpolando entre mensajes, y los métodos de `FlujoConTiempo` que usan la radio y
  el vigía (`noche_pendiente`, `pasar_noche` -> avisa al anfitrión una vez por noche, `retener_noches`, `diario_de`,
  `avanzar_tiempo`). Con eso funcionan sin tocarlos el chip «Día N · hh:mm», `ambiente_vivo.dia()/hora()` (ciclo de día
  y noche, **sello de los rumores por días**) y los globos de los NPC.
- **Radio en línea** (`frontend/multi_radio_linea.py`): subclase de la clase pública `radio_registro.Radio` (de A) que
  solo cambia la condición de «en línea» del frame y emite con `radio_emision.crear_emision` tal cual. Tras la noche fija
  el contexto de los NPC (**tema del día anterior** y resultado de la sala). El puente del final no sale en línea.
- **Pausas**: el reloj es de la sala, así que **no se para** porque un jugador esté en un minijuego, un panel o el
  teléfono (en la partida local sí). Es la consecuencia directa de «manda el anfitrión».

### Final en línea

Antes, en línea salía directamente el panel de consecuencias (`PanelFinal`), sin cinemática. Con la paridad el
`FlujoEnLinea` tiene `resumen_final()` (`multi_reloj_linea.TiempoEnLinea.resumen_final`): la misma cuenta que la partida
local con lo que manda el anfitrión en `fin` (confianza por grupo ponderada con los indicadores y final por etapas). Así
`registro_reloj.pintar_final_de` reproduce en cada cliente la cinemática del final (bueno, neutro o malo, con los roles
de la sala) y después la pantalla final de la semana. Todos reciben los mismos datos, así que todos ven el mismo final.

### Prólogo en línea

`frontend/prologo_cinematica.py`: con la bandera cada cliente ve el prólogo en local al entrar (es una cinemática: no hay
nada que sincronizar; los actores usan los roles de la sala). El reloj de la sala espera mientras dura (ver arriba); se
puede saltar como siempre. Al reconectarse a una sala ya empezada (el reloj pasó de las 08:00 del día 1) no vuelve a salir.

### Protocolo v7

| Mensaje | Sentido | Campos |
|---|---|---|
| `reloj` | anfitrión -> clientes | `dia` (1-31), `hora` (0-24), `noche` (bool), `fin` (bool), `diario` (opcional, hasta 16 «id\|veredicto») |
| `noche_lista` | cliente -> anfitrión | `dia` (1-31) |

Ningún campo de los mensajes de v6 cambia. La huella de contenido incluye la versión (`anfitrion.calcular_huellas`).

### Modo por turnos

Ya tenía todo. **Feria**: el reparto sortea 4 misiones por día **en total**, compartidas por todos los jugadores
(`reparto_dias.py`); multiplicar el límite por jugadores no da más misiones (solo frena la hora). Decisión del dueño: se
deja como está (28 misiones por semana repartidas entre los jugadores).

## Lo que NO se llevó (por qué y cómo)

| Qué | Por qué da problemas | Cómo se podría hacer |
|---|---|---|
| **Intro/tutorial en línea** | La bloquea `registro_tutorial.debe_abrirse(..., en_linea)` (archivo de A) | Petición de cambio a A (abajo): dejar abrirla en línea con la paridad; como el prólogo, es local a cada cliente |
| **Tutoriales por jugador en el modo por turnos** | Lo visto se guarda por equipo (`ajustes.json`): el jugador 2 no ve un tutorial que ya vio el 1 (archivos de A) | Petición de cambio a A: marcar por rol/jugador de la sesión |
| **Carteles de campaña en línea** (día 5) | `carteles_campana.py` corta en línea (`escena.online`); el archivo no tiene dueño | Con el reloj de la sala ya hay día: bastaría quitar esa condición cuando el flujo traiga `tiempo_en_linea` (asignar el archivo) |
| **Feria en línea** | El día lo cierra el progreso de UN jugador (`RitmoFeria.observar(hay_mision)`); en línea habría que contar las misiones de la sala en el anfitrión | `RelojSala` con un ritmo de feria propio que avance la hora con los cierres de `PartidaCooperativa` y cierre el día con las del reparto |
| **Trabajos 3D en línea** | La economía (dinero, fatiga, pagos) no se sincroniza: el anfitrión no la conoce. `TRABAJO_ONLINE` está en `economia_config.py` (sin dueño) y el gancho en `main.py` (A) | Economía por jugador en el anfitrión (mensajes `trabajo`/`pago`) y validación del pago del lado del anfitrión |
| **Casos v2, misiones digitales y Fiscalía en línea** | El catálogo en línea es `catalogo_de_mundo` (35 de verificar); añadirlas cambia la huella de contenido y el flujo de la Fiscalía es local | Entrarlas al catálogo coop con su reserva por progreso y los cierres por señal en el anfitrión |
| **Dilemas en línea** | Cada dilema mueve el estado compartido y se decide en el teléfono de un jugador | Mensaje `dilema` con autoridad del anfitrión (quién lo recibe, quién decide) |
| **Guardado en línea** | El estado vive en el anfitrión; reanudar exige reabrir la sala con los mismos roles y huellas | Guardado del lado del anfitrión (`PartidaCooperativa` + `RelojSala.reloj.a_dict()`) y «Reanudar sala» en el menú |
| **NPC sentados y corros sincronizados** | Son decorado local (cada cliente los genera igual por semilla, pero no se sincronizan sus clips) | No hace falta: ya se ven en todos los clientes |
| **Reparto de misiones por reloj en línea** | El en línea reparte por progreso (`ReservaMisiones`); con el reloj de la sala podría hacerlo por día como la local | Pasar el día del `RelojSala` a la reserva (`avanzar_a`) y emitir las caducadas |

## Peticiones de cambio para A (por escrito, vía los humanos)

1. `frontend/registro_tutorial.py`, `debe_abrirse(flujo, restaurada, en_linea)`: con `ALCALDE_MULTI_PARIDAD` encendida y
   un flujo en línea con reloj de la sala (`getattr(flujo, "tiempo_en_linea", None) is not None`), devolver lo mismo que
   en local (intro y tutorial en cada cliente).
2. Tutoriales por jugador en el modo por turnos: la marca de «tutorial visto» por rol de la sesión además de por equipo.

## Nombres de A que se usan (inventario para revisar antes de integrar)

- `frontend/radio_registro.py`: clase `Radio(escena, conexion, guion, crear=None)` y sus métodos `_avanzar`, `abierta`,
  `saltar`, atributos `apagada`, `escena`.
- `frontend/radio_emision.py`: `crear_emision(escena_mundo, vinetas, al_terminar, al_poner=None)` (vía `Radio`).
- `backend/logica/radio_guion.py`: `activo()`, `GuionRadio()`.
- `frontend/registro_tutorial.py`: `debe_abrirse`, `activo`.
- Piel BOTW (tarea 3): `frontend/estilo.py` (`COLOR_TEXTO`, `COLOR_TEXTO_TENUE`, `TINTA`, `ESTADO_*`...),
  `frontend/menu_botw_calculos.py` (`TINTA`, `VELO`, `AMARILLO`, `BLANCO`, `u`, `entrada_opcion`, `entrada_terminada`,
  `RAIZ`), `frontend/banderas_visuales.reducir_movimiento`, `frontend/fondo_menu.FocoTeclado` (`enfocado()`, `visible`).

## Anexo: piel BOTW de las pantallas de B (tarea 3)

| Bandera | Por defecto | Qué hace | Dónde se lee |
|---|---|---|---|
| `ALCALDE_UI_BOTW` (compartida con A) | 1 | Títulos en cursiva con sombra plana de tinta, velo violeta detrás del contenido, flecha amarilla junto al control enfocado y entrada escalonada | `frontend/ui_botw_b_calculos.activa()` (lee el entorno, no importa nada de A) |

- `frontend/ui_botw_b_calculos.py` (puro): paleta tomada de `ui_botw_calculos` de A si existe (mismos nombres); si no,
  del menú BOTW (`menu_botw_calculos`: TINTA, VELO, AMARILLO, BLANCO) y de `estilo.py`. Propio solo lo de composición
  (sombra de títulos, alfa del velo, separación de la flecha).
- `frontend/ui_botw_b.py` (visual): `vestir(raiz, titulos, foco, piezas, velo)`, con guardián (si algo falla, la
  pantalla queda como estaba y se avisa una vez) y «reducir movimiento» (sin entrada ni vaivén de la flecha).
- Pantallas vestidas: sala, menú en línea, error de red y cierre del HUD en línea; panel final, panel final de la
  semana, resultado del grafo y panel de propagación; intro y resultado de los trabajos (taller y mostrador); cartel de la
  medalla y panel «¡Nivel completado!» del parkour. Los widgets compartidos (botones, paneles de tinta) toman el aspecto nuevo cuando A suba su
  rediseño de `componentes.py`.
- Comprobado con `ALCALDE_UI_BOTW=0/1` (`scripts/ui_botw_b_capturas.py`, `probar_trabajo3d.py`, `probar_parkour.py`):
  con la bandera apagada las pantallas son idénticas a las de antes.
- `tests/test_b_ui_botw.py`: bandera, paleta (con y sin el módulo de A, sin valores inventados), entrada y fuente.

## Archivos

- Nuevos: `backend/red/multi_reloj.py`, `frontend/multi_reloj_linea.py`, `frontend/multi_radio_linea.py`.
- Tocados: `backend/red/{protocolo,partida_coop,anfitrion,cliente,servidor}.py`, `frontend/online_flujo.py`,
  `frontend/registro_reloj.py`, `frontend/prologo_cinematica.py`.
- Piel BOTW: nuevos `frontend/ui_botw_b.py`, `frontend/ui_botw_b_calculos.py`; enganches de una llamada en
  `frontend/escenas/{escena_sala,escena_online_menu,escena_error_red,escena_trabajo}.py`, `frontend/online_hud.py`,
  `frontend/{panel_final,panel_final_semana,panel_resultado_grafo,panel_propagacion,parkour_extra,parkour_hud}.py`.

## Pruebas

- `tests/test_b_multi_reloj.py`: reloj de la sala (tick de 1 s sin recorte, difusión, la noche espera a todos, plazo,
  desconectado, aviso de otro día, diario, fin), espejo del cliente y `PartidaCooperativa` (sin reloj no emite; con
  reloj emite y termina por tiempo).
- `tests/test_b_multi_protocolo.py`: v7 por defecto y v6 con la bandera apagada, esquema de `reloj` y `noche_lista`,
  direcciones, tamaño máximo y traducción del anfitrión.
- `tests/test_b_multi_enlace.py`: de punta a punta con `EnlaceSimulado` (latencia y jitter, codec real): dos clientes,
  la noche espera al lento y la semana acaba en los dos.
- `scripts/multi_paridad_humo.py` (local): anfitrión y cliente en dos procesos del juego real en el mismo equipo.
