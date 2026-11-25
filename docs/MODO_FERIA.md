# Modo feria — semana por misiones, sin reloj

Partida corta pensada para la Feria Gamer (26-nov-2026): la semana avanza al completar misiones y no con el tiempo
real. Con **4 misiones por día** salen unas 28 misiones (las mismas 4 por día que sortea `reparto_dias.py`).

## Cómo se elige
- Menú de inicio: la opción **«Modo feria»** está después de «Empezar» (`frontend/escenas/escena_inicio.py` y
  `frontend/menu_botw.py`). Pone `ALCALDE_FERIA=1` en el entorno antes de crear la partida. «Partida nueva» lo quita.
- Se puede forzar con `ALCALDE_FERIA=1` al lanzar el juego.

## Banderas

| Variable | Por defecto | Qué hace |
|---|---|---|
| `ALCALDE_FERIA` | apagada | La partida que se crea es de feria. La pone el menú; los demás módulos la leen del entorno. |
| `ALCALDE_FERIA_POR_DIA` | 4 | Misiones por día. Sin valor, se usa `POR_DIA` de `modo_feria.py` (`None` = catálogo ÷ 7). |
| `ALCALDE_FERIA_MENU` | encendida | `0` quita la opción «Modo feria» del menú. |

## Funcionamiento
- Lógica pura: `backend/logica/modo_feria.py` (`RitmoFeria`). Se usa desde `backend/logica/flujo_tiempo.py`.
- **Hora**: arranca a las 08:00 y, tras cada misión cerrada, va hacia 08:00 + 12 h · hechas/por día, animada para
  que el cielo cambie de verdad.
- **Cierre del día**: al cerrar las misiones del día, o cuando el jugador activo se queda sin misión, el reloj pasa a
  las 20:00 con la noche pendiente. Desde ahí sigue la misma ruta que el modo normal: la radio emite y
  `pasar_noche()` → `fijar_dia_misiones(dia, hora)`. Cerrar el día 7 lleva al final de siempre.
- **Chip «Día N · hh:mm»**: no se ve. `frontend/modo_feria_registro.py` envuelve `chip()` de la vista del vigía del
  reloj sin editar `registro_reloj.py`, así que el avance, los avisos y la pantalla final siguen igual.
- Desde las 19:30 los anuncios no se silencian, porque en feria la hora no es de reloj.
- **Guardado**: una partida de feria **no se guarda** ni se puede continuar (`FlujoConTiempo` oculta
  `misiones_a_dict`). El formato del guardado no cambia.
- El reparto por días (`reparto_dias.py`) no se toca: sortea 4 de las 5 misiones de cada día, y por eso la feria
  cierra el día a las 4. Con menos, la que sobraba caducaba cada noche sin verse. Algunos rumores con sello pueden no
  salir en todas las partidas; las capas del sello dependen del día, no de un rumor concreto.

## Cómo probar
- `ALCALDE_FERIA=1`: 4 misiones por día, sin chip, el ciclo día-noche avanza con cada misión y la radio emite entre
  días. Mide la duración real de la partida.
- `ALCALDE_FERIA_POR_DIA=1` para recorrer la semana muy rápido.
- Tests sin ventana: `tests/test_hilo_tiempo.py`.
