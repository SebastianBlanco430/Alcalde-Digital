# Estilo BOTW — piel de toda la interfaz

La interfaz adopta el lenguaje del menú de inicio (`frontend/menu_botw.py`, `frontend/menu_botw_calculos.py`): tinta
violeta, velos translúcidos, letra en cursiva, amarillo para lo elegido y una flecha que señala el foco. Se distingue a
simple vista del estilo «cómic» de siempre (azul pizarra, borde de tinta grueso, sombra desplazada).

**Regla de convivencia:** en los módulos compartidos (`estilo`, `componentes`, `tipografia`, `campo_texto`, `iconos`,
`notificaciones`, `hud`, `minimapa_calculos`, `props_mundo`, `radio_emision`) solo se AÑADE. Ningún nombre existente
cambia de nombre, firma ni valor: la piel vive en nombres nuevos y cada pantalla se pasa a ella a propósito. Lo vigila
`tests/test_a_api_compartida.py`.

## Bandera

| Variable | Por defecto | Qué hace |
|---|---|---|
| `ALCALDE_UI_BOTW` | encendida | `0` deja la interfaz de siempre, idéntica. Sin variable manda el ajuste guardado «Estilo de interfaz» (`ui_botw` en `ajustes.json`; se aplica al reiniciar). |

`main.py` llama a `ui_botw_calculos.publicar_en_entorno()` al arrancar: si la variable no estaba, la escribe con el
valor efectivo, así cualquier módulo que solo mire el entorno ve lo mismo que el ajuste.

## Paleta (`frontend/estilo.py`, constantes `BOTW_*`, RGB 0-255)

| Constante | Valor | Uso |
|---|---|---|
| `BOTW_TINTA` | (30, 27, 46) `#1E1B2E` | contornos, sombras, texto sobre amarillo |
| `BOTW_VELO` + `BOTW_ALFA_VELO` | (24, 18, 44) a 222/255 | fondo de paneles (translúcido) |
| `BOTW_PANEL` | (36, 30, 58) | panel opaco |
| `BOTW_TARJETA` | (50, 43, 78) | tarjeta o fila dentro de un panel |
| `BOTW_SUPERFICIE_ALTA` | (66, 57, 100) | hover de tarjeta, chip |
| `BOTW_FONDO` | (20, 16, 34) | fondo de pantalla completa |
| `BOTW_TEXTO` | (244, 240, 255) `#F4F0FF` | texto principal |
| `BOTW_TEXTO_DETALLE` | (237, 231, 255) `#EDE7FF` | texto secundario |
| `BOTW_TEXTO_TENUE` | (184, 176, 214) | ayudas, rótulos apagados, deshabilitado |
| `BOTW_ACENTO` | (255, 217, 61) `#FFD93D` | opción elegida, acción principal, anillo de foco |
| `BOTW_ACENTO_SUAVE` | (255, 232, 140) | hover del amarillo |
| `BOTW_EXITO` / `AVISO` / `ERROR` / `INFO` | (110,214,140) / (255,186,72) / (240,98,98) / (120,214,255) | estados |
| `BOTW_BOTON` / `_RESALTADO` / `_PRESIONADO` / `_DESHABILITADO` | (60,51,96) / (78,67,122) / (44,37,72) / (48,44,62) | botón secundario |
| `BOTW_FILO` + `BOTW_ALFA_FILO` | (237, 231, 255) a 96/255 | borde fino claro |

Todas las parejas texto/fondo pasan WCAG AA (4,5:1); la lista está en `ui_botw_calculos.pares_de_texto()` y la prueba
`tests/test_a_ui_botw.py`. Colores de identidad (lugares, roles, retratos) no cambian con la piel.

## Formas y medidas

| Medida | Tinta (siempre) | BOTW |
|---|---|---|
| Borde | 3 px de tinta opaca (2 en HUD denso) | `BOTW_GROSOR_FILO_PX` = 2 px de filo claro translúcido |
| Radios chip / tarjeta / panel | 6 / 10 / 14 px | `BOTW_RADIO_CHIP_PX` 4 / `BOTW_RADIO_TARJETA_PX` 6 / `BOTW_RADIO_PANEL_PX` 8 |
| Sombra | plana desplazada (4, -5), alfa 160 | `BOTW_DESPLAZAMIENTO_SOMBRA_PX` (0, -4) recta, alfa 120 |
| Foco de teclado | anillo cian de 3 px | anillo amarillo de `BOTW_ALTO_FOCO_PX` = 2 px y flecha amarilla a la izquierda |
| Texto de controles | Atkinson Regular / Bold | `tipografia.FUENTE_BOTW` (Italic) / `FUENTE_BOTW_TITULO` (BoldItalic) |

Las medidas en px son de la referencia de `componentes.a_unidades` (600 px de alto); el menú de inicio usa 720 px
(`menu_botw_calculos.u`). Ningún texto baja de 16 px (`tests/test_tipografia_minima.py`).

## Estados

| Estado | Botón primario | Botón secundario |
|---|---|---|
| Normal | amarillo `BOTW_ACENTO`, texto tinta en cursiva negrita | violeta `BOTW_BOTON`, texto claro en cursiva |
| Hover | `BOTW_ACENTO_SUAVE`, escala 1,04, flecha | `BOTW_BOTON_RESALTADO`, escala 1,04, flecha |
| Pulsado | (232, 192, 40), escala 0,96, la sombra se acerca | `BOTW_BOTON_PRESIONADO`, igual |
| Foco (teclado / mando) | anillo amarillo y flecha | anillo amarillo y flecha |
| Deshabilitado | `BOTW_BOTON_DESHABILITADO`, texto `BOTW_TEXTO_TENUE`, sin sombra ni flecha | igual |

Peligro: rojo (172, 50, 60) / hover (186, 60, 70) / pulsado (148, 40, 50) con texto claro.

## Transiciones
- Curva de coseno (`ui_botw_calculos.suavizar`, la del menú).
- Aparición: `DURACION_ENTRADA_S` = 0,28 s, con fundido y deslizamiento desde 18 px a la derecha (`entrada(t, reducir)`).
- Hover 0,08 s y pulsado 0,06 s (las de `componentes`).
- **Reducir movimiento** (Ajustes › Movimiento o `ALCALDE_REDUCIR_MOVIMIENTO=1`): solo el fundido, sin deslizamientos.
- **Daltonismo y alto contraste**: son un filtro de pantalla completa (`frontend/daltonismo.py`), así que valen igual
  con la piel.

## Kit para las pantallas (API pública nueva)

`frontend/componentes.py`:

| Pieza | Para qué |
|---|---|
| `panel_botw(padre, ancho, alto, tono=None, radio_px=BOTW_RADIO_PANEL_PX, sombra=True, filo_px=None, alfa=None, **opciones)` | Panel BOTW. Devuelve el contenedor con `.sombra`, `.borde` y `.fondo`, como `panel_tinta`. |
| `panel_piel(...)` | Misma firma que `panel_tinta`: con la piel, `panel_botw` con colores y radios equivalentes; sin ella, `panel_tinta`. Es la forma más corta de pasar una pantalla. |
| `BotonBotwPrimario`, `BotonBotwSecundario`, `BotonBotwPeligro` | Misma API y argumentos que `BotonPrimario` y sus hermanos. |
| `boton_piel(texto, variante="secundario", **opciones)` | El botón BOTW o el de tinta según la bandera. |
| `boton_piel_primario`, `boton_piel_secundario`, `boton_piel_peligro` `(texto, *args, **opciones)` | Atajos con los MISMOS argumentos que `BotonPrimario` y sus hermanos: cambiar el nombre de la clase por el atajo basta. |
| `flecha_botw(padre, alto, **opciones)`, `textura_flecha_botw()` | La flecha del menú, para listas propias. |
| `piel_botw()`, `medidas_botw(filo_px)`, `RADIOS_BOTW`, `ESTILOS_BOTON["botw_*"]` | Consultas y datos. |

`frontend/ui_botw_calculos.py` (puro): `activo()`, `publicar_en_entorno()`, `tono(rgb, con_piel=None)` (equivalente
BOTW de un color de `estilo`, o el mismo color), `TONOS`, `ESTILOS_BOTON`, `estilo_boton()`, `suavizar()`,
`entrada()`, `pares_de_texto()` y las constantes de tiempo.

`frontend/tipografia.py`: `FUENTE_BOTW`, `FUENTE_BOTW_TITULO` y `fuente_piel(titulo=False)`.

### Cómo pasar una pantalla

```python
from frontend import componentes, estilo, tipografia, ui_botw_calculos as ui

panel = componentes.panel_piel(self, 0.9, 0.6, estilo.COLOR_PANEL)           # antes: panel_tinta(...)
boton = componentes.boton_piel("Aceptar", "primario", al_clic=self.aceptar)   # antes: BotonPrimario(...)
titulo = Text("Ajustes", font=tipografia.fuente_piel(titulo=True), color=rgb(ui.tono(estilo.COLOR_TEXTO)))
```

Los colores incrustados de una pantalla pasan por `ui.tono(...)`. Los que no tienen equivalente pasan tal cual.

## Pantallas pasadas a la piel
- Kit base: `estilo`, `componentes`, `tipografia`, `ui_botw_calculos`.
- Persona A, retocadas a mano (capturas antes/después en `capturas_claude/antes/hud` y `capturas_claude/despues/hud`):
  - Menú de inicio y submenú Multijugador (`escena_inicio`, `menu_botw`): ya eran BOTW.
  - HUD (`hud.py`): chips de misión, lugar, reloj, dinero, pulseras y teléfono en velo violeta con filo claro (todo lo
    que pasa por `_tinta`/`FondoTinta`), fondos sueltos (`_fondo_hud`, `_tono`), panel final de indicadores y su botón.
  - Minimapa y minimapa ampliado (marco `FondoTinta("minimapa")`), mapa grande (`mapa_grande_vista`: fondo y chips de
    nombres).
  - Pausa (`menu_pausa`): panel, título en cursiva, botones del menú y diálogo «¿Salir?».
  - Ajustes (`escena_ajustes`): panel, pestañas, pie, título, selectores y barra de foco amarilla; pestaña nueva
    «Estilo» con «Estilo de interfaz: BOTW / Clásico» (`hud_ajustes`, se aplica al reiniciar).
  - Pantalla de carga (`pantalla_carga`), tarjetas de aviso del teléfono abierto (`notificaciones`) y tarjeta de
    avisos de Civitas (`tarjeta_aviso`).
- Persona A, pasadas después (paneles `panel_piel`, botones `boton_piel_*`, títulos `fuente_piel`):
  - Teléfono por dentro y Civitas (`telefono_pantallas`, `telefono_marco`, `marco_telefono`, `civitas_visual`,
    `registro_telefono_grande`, que incluye el botón «Avisos de Civitas» de la pausa).
  - Diálogos y casos: `dialogo_ui`, `globo_dialogo`, `interrogatorio_vn`, `casos_interfaz`, `archivo_casos_ui`,
    `rectificar_visual`.
  - Dilemas (`dilemas_visual`, `registro_dilemas`) y tutoriales (`registro_tutorial`, con el botón «Cómo se juega» de
    la pausa, y `tutorial_mision_vista`).
  - Minijuegos: pantalla previa y resultado (`minijuegos/pantalla_previa`, `minijuegos/ui`, `escena_minijuego`) y los
    botones y paneles de cada mesa (`minijuegos_visual/*`). El papel, el corcho y las fichas de cada mesa son parte
    del decorado y no cambian.
  - Tienda e inventario (`tienda_ui`, `inventario_ui`), selección de rol (`escena_seleccion_rol`), efectos de botón
    (`efectos_ui`), campos de texto (`campo_texto`) y el interior de los controles de Ajustes (flechas del selector,
    interruptor «Activado/Desactivado»).
  - Capturas antes/después de todas: `capturas_claude/botw_antes_despues/` (ver su `LEEME.txt`).
- Persona B, con este mismo kit (`panel_piel`, `boton_piel_*`, `fuente_piel`) y `frontend/ui_botw_b.py` (`vestir`):
  menú y sala en línea, error de red, trabajos, parkour, paneles finales y de la semana, propagación, grafo y red
  social. `vestir` usa la flecha de `componentes.BotonBotw` (misma textura, alto y hueco), títulos sin sombra y la
  entrada de `ui_botw_calculos.entrada`; solo añade el velo violeta detrás de las pantallas completas, como el de la
  pausa.
- Pasadas después para que no quede nada con el estilo «cómic»: la Fiscalía (`frontend/fiscalia/`), los chips del HUD
  de economía, entregas, pulseras, hábitos, manillas, reloj y la franja «Confianza de Ciudad Nova»
  (`registro_momento_nivel`), los botones de la capa de pantalla de los minijuegos 3D y los de la cinemática final.
- Siguen igual a propósito, porque son decorado y no interfaz: viñetas y bocadillos de papel de las cinemáticas, el
  logo, las teclas dibujadas (pausa y laboratorio), los carteles 3D del mundo y las pantallas simuladas dentro del
  mundo (monitor, antesala del parkour, ordenador de trabajos). El menú de inicio clásico (`escena_inicio`) es el
  respaldo de `ALCALDE_MENU_BOTW=0`.

## Cómo probar
- `ALCALDE_UI_BOTW=0` frente a sin variable: misma partida, dos pieles. Con `0`, todo idéntico a antes.
- Ajustes › Estilo › «Estilo de interfaz», guardar, reiniciar y comprobar.
- Tests sin ventana: `tests/test_a_ui_botw.py` (bandera, equivalencias, contraste) y `tests/test_a_api_compartida.py`
  (los módulos compartidos solo crecen). Muestra visual: `pruebas_claude/captura_a_kit.py`.
