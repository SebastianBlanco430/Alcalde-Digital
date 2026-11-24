# Contrato interno de `frontend/fiscalia/` — escena (Módulo 3) ↔ interfaz (Módulo 4)

Escrito por el orquestador de la sesión A (Módulo 1, 2026-11-23). Manda sobre cualquier duda entre los dos subagentes. Si uno necesita cambiarlo, lo anota al final («Cambios») y avisa en su `informe.md`; nunca cambia la firma en silencio.

Fuentes: formato del caso en `sesiones-24nov\fiscalia\contrato-caso.md`; tipos en `backend/logica/casos_v2_tipos.py` (`VistaNodo`, `VistaOpcion`, `VistaParkour`, `Cambio`, `Diagrama`, `SesionCaso`); guion en `sesiones-24nov\fiscalia\guion.md`.

## 1. Reparto de archivos (dueño único)

| Dueño | Archivos |
|---|---|
| **Escena** (`fiscalia-escena`) | `__init__.py`, `registro.py` (lo carga `frontend/extensiones.py`), `edificio.py` (+ `edificio_calculos.py`), `escena_fiscalia.py`, `salas.py` (+ `salas_calculos.py`), `personajes.py`, `camaras.py` (+ `camaras_calculos.py`), `sentarse.py`, `flujo_calculos.py`; además `frontend/registro_mundo_digital.py`, `frontend/computador_mundo.py` y la línea de `frontend/extensiones.py`. |
| **Interfaz** (`rueda-ui`) | `hud_caso.py` (fachada), `rueda.py` (+ `rueda_calculos.py`), `medidor_solidez.py`, `subtitulos.py`, `laboratorio_ui.py`, `acusacion.py`, `diagrama_flujo.py` (+ `diagrama_flujo_calculos.py`), `pausa_caso.py`, `ui_calculos.py`. |

Los `*_calculos.py` son puros (no importan `ursina`) y llevan tests en `tests/test_fiscalia_*.py`. Nadie edita un archivo del otro: se pide por el informe o al orquestador.

## 2. Quién hace qué

- **La escena manda.** Es dueña de la `SesionCaso`, de la cámara, de los personajes 3D, de los fundidos y del orden del flujo. Decide cuándo se muestra cada cosa.
- **La interfaz dibuja y recoge la entrada.** Todo lo suyo cuelga de `camera.ui`. No toca la sesión, la cámara ni `scene`. Avisa por callbacks.
- La escena **no se congela nunca**: mientras hay una rueda o una línea en pantalla, los personajes siguen respirando y la cámara puede moverse.

## 3. Fachada de la interfaz: `frontend/fiscalia/hud_caso.py`

```python
class HudCaso(Entity):                       # parent = camera.ui
    def __init__(self, caso, *, al_elegir, al_continuar, al_abandonar, parent=None): ...
```

- `caso`: el `CasoV2` (lee `caso.titulo`, `caso.personajes[id]["nombre"]`, `caso.evidencias[id]["nombre"|"descripcion"]`, `caso.umbrales` → `{"solido": 85, ...}`).
- `al_elegir(id_opcion)`: el jugador eligió una opción **libre** de la rueda o de la acusación.
- `al_continuar()`: el jugador pidió avanzar un diálogo cuya línea ya está completa.
- `al_abandonar()`: el jugador confirmó «Abandonar caso» en la pausa.

| Método | Qué hace |
|---|---|
| `presentar(vista, *, ancla=None)` | Muestra el nodo `vista` (`VistaNodo`). Diálogo: nombre + texto letra a letra. Rueda: lo mismo y la rueda con `vista.opciones`. Acusación: tablero de sospechosos. Laboratorio: la línea del fiscal (los chips van con `mostrar_laboratorio`). No sirve para `final` (ver `mostrar_final`). Llamarla otra vez con el mismo nodo actualiza la rueda sin repetir la línea. |
| `fijar_ancla(ancla)` | Cada frame. `ancla` = `(x, y)` en unidades de `camera.ui` de **la cara de quien habla** (centro de la cabeza), o `None`. La rueda se coloca alrededor sin tapar la cara (§5). |
| `fijar_reloj(restante, total)` | Cada frame. `None, None` = sin reloj. |
| `fijar_solidez(valor)` | Pone el medidor sin animar (al abrir). |
| `aplicar_cambios(cambios, solidez)` | `cambios`: tupla de `Cambio` de `sesion.tomar_cambios()`. Anima «▲ +8 %» / «▼ −6 %» y la ficha de cada prueba nueva. `solidez`: valor final. |
| `linea_completa() -> bool` | ¿Ya salió todo el texto? |
| `completar_linea()` | Muestra de golpe el texto que falta. |
| `decir_jugador(texto)` | Muestra un momento la frase `dice` del jugador (o una acotación si empieza por «(»). |
| `mostrar_laboratorio(parkours, *, cerca=None, puerta=False)` | Chips de los terminales (`VistaParkour`): nombre, prueba y estado. `cerca` = `nivel` del terminal junto al que está el jugador (resalta «E — Sentarse»); `puerta=True` = está junto a la salida («E — Pasar a la sala»). Llamarla cada vez que cambie algo. |
| `ocultar_laboratorio()` | |
| `confirmar(titulo, texto, *, si, no, al_responder)` | Cuadro de confirmación modal. `al_responder(True|False)`. Lo usa la escena para salir del laboratorio; la pausa usa el suyo. |
| `mostrar_final(vista, diagrama, *, al_cerrar)` | Tarjeta del final (título, texto, resultado, solidez final) y después el diagrama de flujo (`Diagrama`). `al_cerrar()` cuando el jugador pulsa «Salir de la Fiscalía». |
| `abrir_pausa()` / `cerrar_pausa()` / `en_pausa` | Pausa del caso: «Seguir» y «Abandonar caso» (con confirmación: «El caso se archiva»). |
| `modal_abierto -> bool` | Hay pausa, confirmación o final en pantalla: la escena no debe mover al jugador ni correr el reloj. |
| `entrada(key) -> bool` | La escena le pasa **todas** las teclas (también las del mando, que llegan como teclas). `True` = consumida. |
| `actualizar(dt)` | Solo si la escena lo llama; la interfaz también puede usar su propio `update`. Debe funcionar de las dos formas sin avanzar doble (usar `time.dt` propio o un guardián). |
| `ocultar()` / `mostrar()` | Oculta todo durante un fundido o el parkour, sin perder el estado. |
| `destruir()` | Libera todo. Nunca lanza. |

**Entrada que maneja la interfaz** (dentro de `entrada`):

- Rueda y acusación: ratón (pasar por encima resalta, clic elige), teclas `1`–`4` (hueco `posicion + 1`), flechas / WASD para resaltar y `Enter`/`Espacio` para elegir, mando: dirección del stick izquierdo resalta el hueco de ese lado y el botón A elige. Una opción `BLOQUEADA` se puede resaltar (muestra su pista) pero no elegir (sonido/temblor corto de «no»).
- Diálogo: `Espacio`, `Enter`, clic o botón A → si la línea no está completa, `completar_linea()`; si lo está, `al_continuar()`.
- `Esc` (o Start): abre o cierra la pausa. Dentro de la pausa y de `confirmar`, la interfaz consume todo.
- Laboratorio: la interfaz **no** maneja `E` ni el movimiento (son de la escena); solo `Esc`.

## 4. Lo que hace la escena con la sesión (bucle)

```python
vista = sesion.vista()
hud.presentar(vista, ancla=...)
# cada frame, si no hud.modal_abierto:
if sesion.avanzar_tiempo(dt):            # el reloj eligió sola
    self._tras_decision()
hud.fijar_reloj(sesion.vista().restante, vista.reloj_segundos)
hud.fijar_ancla(self._ancla_de(vista.personaje))

def al_elegir(id_opcion):                # callback del hud
    opcion = next(o for o in vista.opciones if o.id == id_opcion)
    if opcion.dice: hud.decir_jugador(opcion.dice)
    sesion.elegir(id_opcion); self._tras_decision()

def _tras_decision(self):
    hud.aplicar_cambios(sesion.tomar_cambios(), sesion.solidez)
    nueva = sesion.vista()
    # cambio de escena -> fundido con el rótulo; cambio de personaje en la sala -> corte «sale/entra»
    # final -> hud.mostrar_final(nueva, sesion.diagrama(), al_cerrar=self._salir_al_mundo)
    hud.presentar(nueva, ancla=...)
```

- El reloj **no corre** mientras la línea del nodo no terminó de escribirse, ni con `hud.modal_abierto`, ni durante un fundido.
- En el nodo `laboratorio` el jugador camina libre por la sala; `E` junto a un terminal lanza la entrada al parkour; `E` junto a la puerta llama `hud.confirmar("¿Pasar a la sala?", "El laboratorio se cierra. No podrás volver.", si="Pasar", no="Quedarme", ...)` y con `True` → `sesion.salir_laboratorio()`.
- Al volver de un parkour **completado**: `sesion.completar_parkour(nivel)` y `hud.aplicar_cambios(...)`.
- `al_abandonar` → `sesion.abandonar()` y se muestra el final (`final_abandono`) como cualquier otro.

## 5. Reglas de pantalla (16:9; `camera.ui` va de −0,889 a 0,889 en x y de −0,5 a 0,5 en y)

| Zona | Dónde | De quién |
|---|---|---|
| Medidor «Solidez del caso NN %» | Arriba al centro, `y` ≥ 0,40. Siempre visible durante el caso (salvo fundidos). Marcas en los umbrales. | Interfaz |
| Reloj | Anillo alrededor del centro de la rueda (se vacía) + segundos; rojo y pulso por debajo de 4 s. | Interfaz |
| Rueda | Cuatro huecos fijos (arriba, derecha, abajo, izquierda = posiciones 0, 1, 2, 3) alrededor de un centro. El centro se pone **al lado** de la cara: si `ancla.x` < 0, a su derecha; si no, a su izquierda; a la altura del pecho. Ninguna etiqueta puede pisar un círculo de radio 0,11 alrededor de `ancla`. Sin `ancla`: centro en (0,34; −0,05). | Interfaz |
| Subtítulos (nombre + línea) | Franja inferior, `y` ≤ −0,30, ancho ≤ 1,2. | Interfaz |
| Frase del jugador (`dice`) | Encima de los subtítulos, 1,6 s, en cursiva o con otro color. | Interfaz |
| Rótulo de la sala en los fundidos | Centro. | Escena |
| Avisos de `E` en el laboratorio | Abajo al centro (encima de los subtítulos). | Interfaz (`mostrar_laboratorio`) |

- Letra: ≥ 14 px a 720p y ≥ 18 px a 1080p (usar `frontend/tipografia.py` / `diseno_adaptable`, como el resto del juego). Estilo del juego: tinta, paneles de cómic (`componentes.panel_tinta`, `estilo`).
- Hueco **bloqueado**: silueta con candado y la `pista`. Hueco de una opción ya usada: vacío y tenue (no se reordena la rueda).
- La rueda entra con una animación ≤ 0,25 s y puede entrar **antes** de que termine la línea si el texto tiene ≤ 60 caracteres.
- **Reducir movimiento** (`banderas_visuales.reducir_movimiento()`): texto de golpe, sin pulso ni temblor, la rueda aparece sin animación, los «▲ +8 %» aparecen y se van sin desplazarse.
- Orden de dibujo: todo lo de la interfaz por encima de los fundidos de la escena salvo el rótulo de sala.

## 6. Pruebas sin el otro módulo

- La interfaz se prueba con una escena vacía (fondo gris y una esfera como «cara») y una **sesión falsa** en su arnés (`sesiones-24nov\fiscalia\rueda-ui\arnes\`) que devuelva `VistaNodo` de `casos_v2_tipos`. Cuando exista `backend/logica/casos_v2.py`, se prueba con el caso real.
- La escena se prueba con un **hud falso** (una clase con los mismos métodos que imprime) hasta que exista `hud_caso.py`; el import va en `try/except` y, si `HudCaso` no está, se usa el falso con un aviso por stderr (ese mismo guardián es el respaldo de la demo).

## Cambios

**2026-11-23 — interfaz (`rueda-ui`, Módulo 4).** Ninguna firma cambia; son precisiones de cómo quedó `HudCaso`:

1. `modal_abierto` y `en_pausa` son **propiedades** (`hud.modal_abierto`, sin paréntesis), como en el bucle del §4.
2. `HudCaso` **no define `input`**: la escena debe pasarle todas las teclas por `entrada(key)` (si las recibiera también por Ursina, llegarían dos veces). Las teclas crudas del mando (`gamepad a`, `gamepad start`, cruceta) se ignoran si `frontend/mando.py` está instalado (ya llegan traducidas); si no lo está, se traducen dentro. El palo izquierdo se lee de `held_keys` en el propio `update`.
3. `actualizar(dt)` es opcional: la interfaz tiene su `update`; un guardián por número de frame evita avanzar dos veces.
4. Rueda: `1`–`4` **eligen** directamente; flechas/WASD/palo **resaltan** y `Enter`/`Espacio`/A eligen el resaltado; clic elige el hueco bajo el ratón. Si la rueda aún no está a la vista, `Espacio`/`Enter`/clic completan la línea.
5. Una rueda que **vuelve** a salir (tras `@volver`) muestra su línea de golpe y la rueda enseguida: `linea_completa()` es `True` casi de inmediato y el reloj puede correr ya.
6. Tras `decir_jugador`, la línea del siguiente `presentar` empieza a escribirse hasta 0,7 s después (mientras, `linea_completa()` es `False`).
7. Tras `al_continuar()` o `al_elegir()`, la interfaz no vuelve a llamarlos hasta el siguiente `presentar` (evita dobles pulsaciones).
8. En el nodo `laboratorio` la línea del fiscal se oculta sola 6 s después de completarse; los chips siguen.
9. Acusación = la misma rueda, con **fichas** (retrato dibujado con los colores del `retrato` del JSON, nombre y etiqueta).
10. Orden de dibujo: `HudCaso` va en `z = -100.5` de `camera.ui` (delante del velo de `transicion.py`, `-100`; detrás de su rótulo, `-101`). Si la escena usa otro fundido, que su velo quede en `z > -100.5`.
11. `abrir_pausa()` no hace nada con el HUD oculto (`ocultar()`) ni con el final en pantalla.
12. Guardián: si un método falla por dentro (o recibe datos imposibles), avisa una vez por stderr (`[hud_caso] …`) y la interfaz sigue en **texto plano** (línea + opciones numeradas; `1`–`4`, `Espacio`, `Esc` pausa, `Supr` abandona desde la pausa, `Enter` cierra el final). Un error dentro de un callback de la escena se avisa sin degradar.

**2026-11-24 — sesión E (`fiscalia-visual`).** Cambia el §5 (la firma no cambia):

1. **Rueda fija.** `rueda_calculos.colocar()` devuelve SIEMPRE `CENTRO_FIJO` = (0,48; −0,04): tercio derecho, altura del pecho, encima de los subtítulos; `ancla` se acepta y se ignora (`fijar_ancla` sigue existiendo y no hace daño). Antes iba al lado de la cara y cambiaba de lado cuando la cabeza cruzaba x = 0 al respirar: saltaba. Franja de la rueda: y de −0,25 a 0,32 (no pisa la ficha «Prueba nueva» ni la frase del jugador).
2. **Tomas encuadradas.** Toda toma de `camaras_calculos.toma()` deja la cara de quien habla en `CARA_EN_PANTALLA[plano]` (centro-izquierda, x entre −0,26 y −0,10), fuera de `rueda_calculos.rectangulo()`. El plano general ahora es desde detrás y a la derecha del jugador.
3. **Hueco usado.** Solo se dibuja si el jugador eligió esa opción en esa rueda: panel oscuro con ✓ y la etiqueta tachada en gris. Si una opción desaparece sin elegirla, su hueco no se dibuja. Ya no hay silueta vacía.
4. `CamaraFiscalia.ir_a/cortar(toma, seguir=None)`: `seguir()` devuelve la toma recalculada con la cabeza de ahora y la cámara la acompaña suave.
