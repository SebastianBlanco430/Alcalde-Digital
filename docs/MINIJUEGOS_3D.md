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
