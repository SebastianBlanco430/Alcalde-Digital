# Menú de inicio — 1 jugador directo y submenú «Multijugador»

«Empezar» / «Partida nueva» es una partida local de **un solo jugador**: va directo a elegir rol, sin la pregunta
«¿Cuántos jugadores?». El botón «En línea» pasa a llamarse **«Multijugador»**, sale siempre y abre dos opciones:
**«Local por turnos»** (2, 3 o 4 jugadores en el mismo computador, el hot-seat de siempre) y **«En línea»** (la pantalla
de siempre, `frontend/escenas/escena_online_menu.py`, solo con `ALCALDE_ONLINE` activo).

## Recorrido

| Nivel | Opciones | Esc / B / «Atrás» |
|---|---|---|
| Principal | Continuar, Empezar / Partida nueva, Modo feria, Multijugador, Ajustes, Salir | (nada, como siempre) |
| Multijugador | Local por turnos, En línea (solo con ONLINE), Atrás | Principal |
| Local por turnos | 2 jugadores, 3 jugadores, 4 jugadores, Atrás | Multijugador |

- «2/3/4 jugadores» con una partida guardada pide la misma confirmación que «Partida nueva» (BUG-005).
- Después de elegir cuántos, la selección de rol es la de siempre: cada jugador elige su rol por turnos. «Atrás» en la
  selección de rol vuelve al menú de inicio.
- «Continuar» reanuda cualquier guardado (1 jugador o por turnos), como antes.
- Al volver al inicio desde cualquier sitio, el menú arranca en el nivel principal.

## Banderas

| Variable | Por defecto | Qué hace |
|---|---|---|
| `ALCALDE_MENU_MULTIJUGADOR` | encendida | `0` deja el menú de siempre: «En línea» suelto (solo con ONLINE) y la pregunta «¿Cuántos jugadores?» en la selección de rol. |
| `ALCALDE_ONLINE` | encendida | `0` quita «En línea» del submenú; «Multijugador» sigue (el hot-seat no depende de ONLINE). |
| `ALCALDE_MENU_BOTW` | encendida | Con `0` el submenú se ve como una placa sobre un velo (como la confirmación); con la piel BOTW, como sus opciones en cursiva. |

## Funcionamiento
- Lógica pura: `frontend/menu_inicio_calculos.py` (`multijugador_activo`, `opciones_de`, `nivel_anterior`,
  `cantidad_inicial`).
- Vista: `frontend/escenas/escena_inicio.py` crea un botón por opción de cada submenú (`botones_submenu`) y cambia
  `self.botones` al entrar en un nivel, igual que la confirmación. `frontend/menu_botw.py` los añade a sus opciones
  dibujadas.
- La cantidad entra por el gestor: `main.py` pasa `al_local=lambda n: gestor.cambiar_a(SELECCION_ROL, jugadores=n)`.
  `EscenaSeleccionRol.al_entrar(jugadores=None)` arranca con esa cantidad (sin ella, 1). «Empezar» sigue llamando a
  `ConexionFlujo.ir_a_seleccion()` sin cambios. `comenzar_partida(sesion)` y el flujo hot-seat no cambian.
- Si falla «Continuar», `frontend/registro_guardado.py` vuelve a `ir_a_seleccion()`, que ahora es 1 jugador.

## Cómo probar
- Empezar: elige rol con «Jugador 1 de 1» y entra al mundo.
- Multijugador › Local por turnos › 3 jugadores: tres elecciones de rol seguidas y la partida por turnos de siempre.
- Esc dos veces desde «Local por turnos» vuelve al principal. Con `ALCALDE_ONLINE=0` no sale «En línea».
- `ALCALDE_MENU_MULTIJUGADOR=0`: el menú y la selección de rol de antes.
- Tests sin ventana: `tests/test_a_menu_multijugador.py`. Capturas: `pruebas_claude/captura_a_menu.py`.
