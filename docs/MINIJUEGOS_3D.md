# Minijuegos de verificar en 3D (rework 3D) — banderas y funcionamiento

Los 6 minijuegos de verificar (Chat del barrio, Contrarreloj, Rastrear la fuente, Ordenar la cadena/Cronología, Comparar dos
versiones, Señales de edición) pueden jugarse dentro de un escenario 3D con el protagonista imitando al jugador. **Solo cambia
la presentación**: la vista 2D de hoy (`frontend/minijuegos/`, `frontend/minijuegos_visual/`) se crea, se empieza y se juega
igual; su lógica (`*_calculos.py`), el `ResultadoMinijuego`, el cierre del lote, los pagos, la confianza, los efectos
retardados, el guardado y el tutorial por misión no cambian. Los controles (teclas, mouse, mando) son los mismos.

Código: `frontend/minijuegos_3d/` (paquete). Enganche: `frontend/escenas/escena_minijuego.py` (`_elegir_3d`, `_montar_3d`,
`_caer_a_2d`). Contrato para quien escriba la presentación 3D de un minijuego:
`D:\Proyectos\JuegoEstructura2\rework-3d\contrato.md`.

## Banderas

Valores: `0/false/no/off` apaga, `1/true/si/sí/on` enciende; sin variable manda la constante de
`frontend/minijuegos_3d/banderas.py`. Se leen en cada misión (no hace falta reiniciar).

| Variable | Por defecto | Qué hace |
|---|---|---|
| `ALCALDE_MINIJUEGOS_3D` | encendida (`MINIJUEGOS_3D`) | Maestra. `0` = los 6 minijuegos en 2D, idénticos a hoy, y la entrada al edificio con la cinemática de sentarse al PC de siempre. |
| `ALCALDE_3D_CHAT` | encendida | Chat del barrio en 3D (familia PC). `0` = 2D. |
| `ALCALDE_3D_CONTRARRELOJ` | encendida | Contrarreloj en 3D (familia PC). |
| `ALCALDE_3D_RASTREAR` | encendida | Rastrear la fuente en 3D (familia corcho). |
| `ALCALDE_3D_CRONOLOGIA` | encendida | Ordenar la cadena en 3D (familia corcho). |
| `ALCALDE_3D_COMPARAR` | encendida | Comparar dos versiones en 3D (familia mesa). |
| `ALCALDE_3D_SENALES` | encendida | Señales de edición en 3D (familia mesa). |
| `ALCALDE_3D_DEMO` | apagada | Demostración de la infraestructura: la vista 2D de hoy dentro del monitor 3D. `1`/`todos` = los 6; `chat,rastrear` = esos. Respeta la maestra y la bandera del minijuego. Solo para pruebas. |
| `ALCALDE_3D_PREVIA_MONITOR` | encendida | Familia PC en 3D: la pantalla «Antes de empezar» va DENTRO del monitor 3D (no a pantalla completa en 2D); al empezar, el minijuego ocupa su sitio en el mismo monitor. `0` = la previa de hoy en 2D y después el 3D. |
| `ALCALDE_3D_SIN_DESTELLO` | encendida | Familia PC en 3D: la cinemática de sentarse llega al monitor SIN el destello blanco (EscenaInterior con `sin_destello`) y la presentación no pone velo de entrada. `0` = con destello, como antes. |
| `ALCALDE_ANIM_SILLA` | encendida | Entrada y salida animadas (`frontend/cinematica_silla.py`): el personaje llega a la silla, la saca, se sienta, la acomoda y pone las manos donde juega (PC y mesa), o camina al corcho, levanta la vista y lleva la mano a una nota; la cámara hace un solo empuje continuo que termina EXACTAMENTE en la toma de juego. Incluye la antesala del parkour (terminal con silla). `0` = la entrada y la salida de antes, idénticas. |
| `ALCALDE_3D_FALLO` | (sin variable) | SOLO PRUEBAS: `abrir`, `avanzar`, `tecla` o `resultado` hace fallar la presentación 3D en esa fase para ver el respaldo al 2D. |

**Una bandera encendida no basta**: si la familia aún no escribió `frontend/minijuegos_3d/<id>_3d.py` (con `CLASE_3D`), o si
ese módulo falla al importarse, el selector (`frontend/minijuegos_3d/selector.py`) devuelve «2D» sin romper nada. Al cierre
del rework, cada `ALCALDE_3D_<ID>` queda encendida si su minijuego pasó la verificación y apagada si no (constantes en
`banderas.py`; la tabla de banderas de la bóveda, ARQ-009, la actualiza el orquestador).

## Red de seguridad

- **Respaldo al 2D**: cualquier excepción de la presentación 3D (al abrir, en `update`, en `input`, al terminar) hace que la
  escena devuelva la MISMA vista 2D (misma partida en curso, mismo foco) a `camera.ui`, con su fondo y su marco de PC, y siga
  en 2D. No pasa por el respaldo de la misión (la escena de juego) ni repite decisiones. Si ni el 2D se puede enseñar, se usa
  el respaldo de siempre (`al_respaldo`).
- Un fallo de la vista 2D sigue yendo al respaldo de siempre, como hoy.
- En línea: los minijuegos son locales a cada jugador; el protocolo y la huella no cambian. Si el jugador llega como `dict`
  se normaliza; si algo no cuadra, cae al 2D.

## Flujo

- Familia PC (Chat, Contrarreloj): entrar al edificio → cinemática de sentarse al PC de siempre → la cámara se separa del
  monitor hasta la toma sobre el hombro y se juega en el monitor 3D (la vista 2D pintada en una textura; el mouse funciona
  sobre el monitor).
- Familias corcho y mesa: entrar al edificio → fundido con el nombre del lugar → el personaje entra a la sala (oficina con
  tablero, sala de investigación o cuarto con mesa) y camina al corcho/mesa; la cámara pasa a la de la familia y se juega ahí.
  (Cambio aditivo en `ConexionFlujo._sentarse_al_pc`; con la maestra apagada o sin implementación 3D, el camino de hoy.)
- Al terminar: el banner de resultado y el panel del grafo son los de siempre. **Salida**: si el minijuego TERMINÓ en 3D,
  se sale directo al mundo (fundido + la cinemática de salir por la puerta), sin la escena «levantarse» de la silla del PC
  del interior (en PC el personaje ya se levantó en el 3D; en corcho y mesa nunca se sentó). Si el 3D cayó al 2D, con la
  maestra apagada o sin implementación 3D, la salida es la de hoy (`ConexionFlujo._salida_3d`, marca en
  `frontend/minijuegos_3d/estado.py`). En línea, `ConexionEnLinea` hereda la entrada y la salida (mismo comportamiento).
- Entrada en PC con 3D: cinemática de sentarse → la cámara llega al monitor SIN destello → el monitor ya muestra «Antes de
  empezar» → la cámara se separa hasta el hombro → «Empezar» (clic en el monitor o Enter/Espacio) → el minijuego en el mismo
  monitor. El tutorial de la primera vez sigue siendo el de hoy (2D, pantalla completa) y luego se pasa a la previa en el
  monitor.

### Entrada y salida animadas (`ALCALDE_ANIM_SILLA`, sesión B del 23-nov)

Con la bandera encendida (por defecto) y el minijuego en 3D, lo de arriba cambia así:

- **Sin cortes después del fundido.** Mundo → puerta → fundido con el nombre del lugar → `EscenaMinijuego` directamente,
  también en la familia PC (`ConexionFlujo._sentarse_al_pc` devuelve False; ya no se pasa por «sentarse» de
  `EscenaInterior`). La animación corre DENTRO de la presentación 3D (`Minijuego3D.abrir()` crea la secuencia con
  `auto=False` y `Minijuego3D.avanzar` la avanza): mismo set, mismo personaje y misma cámara con los que se juega.
- **Silla (Chat, Contrarreloj, Comparar):** `cinematica_silla.sentarse_en` — llegar, sacar la silla con la mano en el
  respaldo, sentarse, acomodarla y manos al teclado/ratón o a la mesa. 2,6 s la primera vez; 1,35 s desde la segunda.
  En PC la cámara termina sobre el hombro (`toma_juego()`), nunca llena el monitor. En Comparar se juega sentado.
- **Corcho (Rastrear, Ordenar la cadena):** `acercarse_a_corcho` — caminar, detenerse, levantar la vista, mano a una nota.
  2,2 s / 1,2 s.
- **Señales:** se queda con la entrada de antes (de pie): sentado, la mano no alcanza toda la foto (faltan 0,14–0,32 m).
  El código de la versión sentada está escrito y apagado.
- **Previa «Antes de empezar»:** en PC se ve en el monitor mientras se sienta; «Empezar» responde cuando la secuencia
  terminó.
- **Saltar:** Espacio / Enter / botón del mando saltan la secuencia (`conexion.saltadores` → `cinematica_silla.saltar_activa`)
  y dejan el estado final exacto; esa pulsación no llega a la previa ni al juego.
- **Versión rápida:** por `clave` (`pc`, `mesa`, `corcho`, `parkour`; la salida usa `<clave>_salida`) y por proceso: la
  primera vez la completa, después la rápida. Saltar cuenta como vista.
- **Salida:** al salir el resultado, `levantarse_de` (retira la silla, se levanta, la empuja a su sitio y se aparta;
  1,6 s / 0,9 s) o `dejar_corcho` (0,9 s / 0,5 s); el banner aparece cuando el personaje ya se apartó. Después, la salida
  al mundo de siempre.
- **Parkour:** `EscenaParkour` muestra una antesala (terminal con silla, `frontend/parkour_antesala.py`): se sienta, la
  cámara entra en la pantalla y el glitch da paso al nivel (3,0 s / 1,5 s); al salir, el camino inverso.
  `registro_parkour.entrar(..., antesala=False)` la omite (lo usa quien hace su propia animación, p. ej. el laboratorio
  de la Fiscalía).
- **Reducir movimiento:** velo negro 0,25 s → estado final → se quita en 0,15 s (sin caminata ni curva de cámara).
- **Red de seguridad:** cualquier excepción al crear o avanzar la secuencia deja el estado final de golpe (`fallo=True`) y
  se sigue con el comportamiento de antes; si el 3D entero falla, el respaldo al 2D de siempre.
- Contrato de la API (para otros módulos que quieran sentar a un personaje): `sesiones-24nov\animaciones\contrato-silla.md`
  (fuera del repo); duraciones y tramos en `frontend/cinematica_silla_calculos.py` (`DURACIONES`, `DURACIONES_RAPIDA`).

## Rendimiento

La textura de la interfaz (búfer fuera de pantalla, 1280×720 / 1920×1080 / 2560×1440 según la ventana) solo se dibuja mientras
el minijuego 3D está abierto. Medido (arnés de rework-3d, todos los efectos encendidos): Chat y Contrarreloj en el monitor a
1280×720 y 1920×1080, sala con corcho, oficina con corcho y cuarto con mesa: 59,9-60,1 fps, 0 frames de más de 50 ms.
Abrir el minijuego en 3D añade ~10-25 ms al frame de apertura (tapado por el destello o el fundido).
Prueba de respaldo: ALCALDE_3D_FALLO=abrir|avanzar|tecla|resultado (solo pruebas) hace fallar la presentación 3D en esa fase.
El paquete se importa perezosamente (el arranque del juego no lo carga).

## Otras banderas del rework 3D (bugs de la Fase 1)

Documentadas en `docs/DISENO.md` (las de bug-textura) y en `rework-3d\bug-pelo\informe.md`; todas encendidas, `=0` = como
antes, solo de dibujo (no cambian lógica, colisiones ni la huella en línea):

| Variable | Qué hace |
|---|---|
| `ALCALDE_PLINTO_RETRANQUEADO` | Fachadas: el plinto de los pisos altos se mete 2-3 cm (sin rayas de z-fighting). Ver `docs/DISENO.md`. |
| `ALCALDE_CAPAS_CALCOMANIAS` | Fachadas: las calcomanías solapadas de una pared van en capas distintas. Ver `docs/DISENO.md`. |
| `ALCALDE_ROSTRO_SKINNING` | Personajes: el pelo y las piezas fijas del rostro se deforman con el hueso de la cabeza en la misma llamada que el cráneo (sin «calva» al correr con hilos de dibujo). `frontend/rostro_skinning.py`. |
| `ALCALDE_PELO_EN_PIEL` | Personajes sin luz (protagonistas y NPC copia): los triángulos del pelo van en el mismo Geom que la piel de la cabeza (y su casco en el casco del cuerpo), una sola llamada de dibujo: sin «calva» al girar corriendo con hilos de dibujo. `frontend/rostro_skinning.py` (`fusionar_con_piel`). |
| `ALCALDE_PESOS_CABEZA` | Personajes Rigify: los pesos de los huesos faciales raíz pasan a `DEF-spine.006` al cargar (la coronilla no se separa del pelo al mezclar clips). `frontend/pesos_cabeza.py`. |
