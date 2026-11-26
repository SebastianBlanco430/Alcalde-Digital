# Modo feria — semana corta con el reloj de siempre

Partida corta pensada para la Feria Gamer (26-nov-2026). Corre con el **mismo reloj y ciclo día-noche** que la partida
normal (08:00 a 20:00, la radio entre días), pero más rápido: la semana dura **unos 9 minutos** (la normal, 15). Así da
tiempo a probar varios tipos de misión y las mecánicas principales sin jugar una partida entera.

## Cómo se elige
- Menú de inicio: la opción **«Modo feria»** está después de «Empezar» (`frontend/escenas/escena_inicio.py` y
  `frontend/menu_botw.py`). Pone `ALCALDE_FERIA=1` en el entorno antes de crear la partida. «Partida nueva» lo quita.
- Se puede forzar con `ALCALDE_FERIA=1` al lanzar el juego.

## Banderas

| Variable | Por defecto | Qué hace |
|---|---|---|
| `ALCALDE_FERIA` | apagada | La partida que se crea es de feria. La pone el menú; los demás módulos la leen del entorno. |
| `ALCALDE_FERIA_MINUTOS` | 9 | Minutos reales de la semana de feria (`MINUTOS_OBJETIVO` en `modo_feria.py`). |
| `ALCALDE_FERIA_SIN_RELOJ` | apagada | `1` esconde el chip del reloj y los avisos de fin, como la feria de antes. |
| `ALCALDE_FERIA_MENU` | encendida | `0` quita la opción «Modo feria» del menú. |

## Funcionamiento
- Lógica pura: `backend/logica/modo_feria.py` (`segundos_por_hora()`, `RitmoFeria`). Se usa desde
  `backend/logica/flujo_tiempo.py`: en feria el reloj se crea con `seg_por_hora = modo_feria.segundos_por_hora()`
  (9 min ÷ 84 h activas ≈ 6,4 s por hora, un día ≈ 77 s) y avanza con el tiempo real como en el modo normal.
- **Cierre del día**: a las 20:00, con la noche pendiente, igual que el modo normal: la radio emite (en su versión corta)
  y `pasar_noche()` → `fijar_dia_misiones(dia, hora)`. Cerrar el día 7 lleva al final de siempre.
- **Chip «Día N · hh:mm»** y avisos «Último día» / «Quedan 2 horas»: se ven, como en el modo normal.
- `RitmoFeria` ya no marca la hora: solo cuenta las misiones cerradas, que lee la recta final (la feria no se guarda).
- **Guardado**: una partida de feria **no se guarda** ni se puede continuar (`FlujoConTiempo` oculta
  `misiones_a_dict`). El formato del guardado no cambia.
- El reparto por días (`reparto_dias.py`) no se toca. Con el día más corto no da tiempo a todas las misiones del día:
  las que quedan caducan por la noche, como en el modo normal. Las capas del sello dependen del día, no de un rumor
  concreto, así que se ven igual.

## Cómo probar
- `ALCALDE_FERIA=1`: reloj visible, ciclo día-noche y radio entre días; la semana en ~9 min.
- `ALCALDE_FERIA_MINUTOS=3` para recorrer la semana muy rápido.
- Tests sin ventana: `tests/test_hilo_tiempo.py`.
