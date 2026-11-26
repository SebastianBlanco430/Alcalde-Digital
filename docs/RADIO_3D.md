# Radio en 3D — la cámara orbita la torre de la Rádio Comunitária

Cuando llega la emisión, la cámara del juego deja al jugador, se acerca a la **torre de la radio** y da vueltas alrededor
de la antena durante toda la emisión, mientras el globo pasa las líneas del recuento. Del resto de la escena solo
cambian el **cielo** (según el momento) y el **globo**. El HUD se esconde; los NPC y los coches siguen con lo suyo. Al
terminar, la cámara, el HUD, el cielo y el ratón vuelven como estaban.

## La torre
- Mástil de celosía de 15 m pintado a franjas rojas y blancas: tres patas que se estrechan, travesaños cada 1,5 m con
  diagonales en zigzag, zapatas de hormigón, plataforma de servicio y una antena de panel.
- **Luz roja de aviso** en la punta que parpadea **siempre**, no solo en la emisión. Con «reducir movimiento» late
  suave, sin cortes.
- Va **junto al edificio «Rádio Comunitária»** (lugar del mundo en `backend/datos/ciudad_3d.py`, x 48, z -70), detrás de
  la caseta o a un lado, **nunca delante de la puerta**. El sitio es el primero libre de una lista ordenada
  (`radio_torre_calculos.candidatos`). Respeta las reglas del decorado de `props_mundo.Reserva` (edificios, caminos
  plaza-puerta, calles, muros, puestos fijos), los props ya colocados y una pendiente máxima.
- Entra al modelo como obstáculo circular (origen `radio_torre`): el jugador no la atraviesa.
- Código: `frontend/radio_torre_calculos.py` (sitio, piezas y parpadeo, puro) y `frontend/radio_torre_modelo.py`
  (malla única con normales más la luz). La crea `frontend/ciudad_3d.py` después de silenciar lo estático, porque la
  luz necesita su `update()`.

## La emisión
- `frontend/radio_emision.py` conserva `crear_emision(escena_mundo, vinetas, al_terminar, al_poner=None)`. Si el mundo
  tiene torre, la emisión es `frontend/radio3d_escena.EmisionRadio3D`, con el mismo contrato: `.terminada`,
  `.saltar()`, `al_poner(vineta, indice)` en cada línea y `al_terminar()` una sola vez, **después** de devolverlo todo.
  Es la ÚNICA emisión: la radio 2D animada de antes se quitó. Si no hay torre o la 3D falla al crearse, no hay
  emisión: `al_terminar()` se llama igual y la noche pasa sin pantalla negra. Entra y sale con un fundido a negro
  (`frontend/radio_fundido.py`, `ALCALDE_RADIO_FUNDIDO=0` lo quita).
- **Cámara** (`frontend/radio3d_camara_calculos.py`, puro):
  - En 1,6 s pasa de la cámara del jugador a la órbita, empezando del lado donde ya estaba.
  - Después gira 360° de forma continua alrededor del eje de la torre, mirando a su parte alta.
- **Cielo por momento** (`vineta["radio_momento"]`, ya lo pone `frontend/radio_registro.py`). Se fuerza la hora con
  `ambiente_vivo.fijar_hora_forzada` (así cambian también la luz y la niebla) y al terminar se devuelve la hora real:

  | Momento | Hora | Qué se ve |
  |---|---|---|
  | `noche` | 22:00 | noche con luna y 260 estrellas, que solo existen durante la emisión |
  | `manana` | 06:12 | amanecer (la línea de la mañana que sigue al recuento de la noche) |
  | `puente` | 17:36 | atardecer del día 7, antes del final |

- **Globo**: el de las cinemáticas (`frontend/globo_dialogo.py`, como la intro): rótulo amarillo (`ACENTO_PRIMARIO`) con
  «Rádio Comunitária» en la esquina y la línea en el bocadillo.
  - Cada línea dura su tiempo de lectura: 1,5 s + 0,06 s por carácter, mínimo 2,5 s.
  - Espacio, Enter, clic o A adelantan; Escape, B o Start saltan la emisión entera.
- **Lo que no cambia** (`frontend/radio_registro.py`):
  - Cuándo se emite: por hora en el modo normal y por misiones en modo feria.
  - Que la emisión espera si hay minijuego, diálogo, dilema o teléfono.
  - Que mientras dura, el reloj, la pausa y los controles están frenados (la emisión es un bloqueador de la escena).
  - Que la noche se pasa al poner la línea de la mañana o al saltar.
  - Que en línea no hay radio.

## Banderas

| Variable | Por defecto | Qué hace |
|---|---|---|
| `ALCALDE_RADIO3D` | encendida | `0` quita la torre y con ella la emisión (las noches pasan sin radio). |
| `ALCALDE_RADIO3D_ORBITA` | `media` | `aerea` usa la órbita alta y abierta. Los presets están en `ORBITAS` de `radio3d_camara_calculos.py`: cambiar un valor o añadir uno es editar ese diccionario. |
| `ALCALDE_REDUCIR_MOVIMIENTO` (o Ajustes › Movimiento) | apagada | Plano fijo de la torre: sin acercamiento ni giro. |
| `ALCALDE_HILO_RADIO` | encendida | La radio entera (ver `docs/HILO_CONDUCTOR.md`). |

Presets de órbita (m y s):

| Preset | radio | alto sobre la base | mira a | vuelta |
|---|---|---|---|---|
| `media` | 22 | 14 | 72 % del alto de la torre | 24 s |
| `aerea` | 32 | 24 | 60 % | 30 s |

## Cómo probar
- `pruebas_claude/captura_a_radio.py` (local) entra al mundo y fuerza una emisión de noche más mañana, Escape a mitad, el
  puente del día 7 y «reducir movimiento». Comprueba que todo vuelve (HUD, cámara, hora del cielo, controles, que sigue
  en el mundo) y guarda capturas en `capturas_claude/radio/`.
- En partida: modo normal hasta las 20:00 del día 1, o `ALCALDE_FERIA=1` y cerrar las misiones del día.
- `ALCALDE_RADIO3D=0`: sin torre y sin emisión; las noches pasan igual.
- Tests sin ventana: `tests/test_a_radio3d.py` (órbita, cielo, rótulo, lectura) y `tests/test_a_radio_torre.py` (sitio
  en el mundo real, celosía, parpadeo). `tests/test_hilo_conductor.py` sigue valiendo para el contrato de
  `crear_emision`.
