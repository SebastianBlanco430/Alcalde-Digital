# Modo online cooperativo de Alcalde Digital

> **Borrador para revisión legal antes de publicar.** El autor de este texto no es abogado. Es material de un
> proyecto de aprendizaje con datos ficticios; no es asesoría legal.
>
> Versión 1.2 · 2026-11-22 · Protocolo de red v6

El modo online permite jugar en cooperación en tiempo real hasta 4 personas. **Una persona aloja la partida** y
las demás se conectan a su dirección IP y puerto. No hay servidores externos ni cuentas: todo ocurre entre los
equipos de los jugadores. Los datos que se tratan y cómo borrarlos están en `docs/PRIVACIDAD_ONLINE.md`.

El modo online **está activo por defecto**: el menú ofrece crear o unirse a una sala. Si lo prefieres apagado,
arranca con `ALCALDE_ONLINE=0` y el juego funciona como siempre (varios jugadores en un mismo equipo, sin red).

## 1. Opciones de arranque

Todos los jugadores deben arrancar el juego con las mismas opciones. Si difieren, la sala rechaza la entrada
(`mundo_distinto`) o los vehículos se verán mal.

| Variable | Qué hace | Regla |
|---|---|---|
| `ALCALDE_ONLINE` | Modo online activo por defecto; `0` lo apaga y deja el juego de un solo equipo | Cada jugador |
| `ALCALDE_VEHICULOS_ONLINE` | Bicis y motos en línea. Activo salvo que valga `0` | **Debe coincidir en todos** (entra en la huella: si difiere, «Mundo distinto») |
| `ALCALDE_SEMILLA=N` | Entero que decide la disposición de la favela | **Debe coincidir en todos** |
| `ALCALDE_PUESTOS_FIJOS` | Puestos de comercio fijos y feria alargada (activo por defecto) | **Debe coincidir en todos** (cambia el mundo: si difiere, «Mundo distinto») |

Ejemplo (macOS, desde la carpeta del proyecto):

```
ALCALDE_SEMILLA=7 venv/bin/python main.py
```

## 2. Anfitrión desde el juego (lo normal)

1. Menú de inicio, botón de modo online.
2. Escribe tu alias (se limpia: sin símbolos raros, y los `<` `>` se sustituyen).
3. Elige crear sala, un puerto y un ámbito (ver sección 4).
4. Anota la **dirección IP:puerto** y el **código de sala** que aparecen. Compártelos solo con quien quieras que
   juegue, por un canal que ya uses con esas personas.
5. Cuando todos estén listos, el anfitrión pulsa iniciar.

## 3. Anfitrión sin gráficos (equipo dedicado o pruebas)

```
python -m backend.red.servidor --puerto N --ambito lan|local|abierto --max-por-ip K
```

Opciones:

- `--puerto N`: puerto TCP. `0` (por defecto) elige uno libre.
- `--ambito`: `lan` (por defecto), `local` o `abierto` (ver sección 4).
- `--max-por-ip K`: conexiones simultáneas permitidas desde una misma IP. Súbelo (por ejemplo 4) si varias
  personas juegan desde el mismo equipo o la misma red con NAT. Sin esta opción, el valor es 2.
- `--semilla N`: igual que `ALCALDE_SEMILLA`.
- `--sin-vehiculos`: sin bicis ni motos (los clientes deben usar `ALCALDE_VEHICULOS_ONLINE=0`).
- `--sin-auto-iniciar`: no empieza sola; usa la orden `iniciar`.
- `--primero-cualquiera`: el primer jugador puede venir de otro equipo (por defecto debe entrar desde el
  propio equipo anfitrión).

En el servidor sin gráficos **nadie es «el anfitrión que cierra»**: si el primero en entrar se cae, recibe los mismos
90 s de reconexión que los demás y la sala sigue. Al terminar la partida, en cuanto no queda nadie conectado, el
servidor se apaga solo (para otra partida, se vuelve a lanzar).

El programa imprime `IP:puerto` y el **código de sala**. Órdenes por teclado: `iniciar`, `estado`, `salir`.
Con `abierto` te pide escribir `ABRIR` para confirmar.

## 4. Ámbitos

| Ámbito | Quién puede conectarse | Cuándo usarlo |
|---|---|---|
| `local` | Solo este equipo | Pruebas |
| `lan` | Equipos de tu red local (IP privadas y el rango 100.64.0.0/10 de Tailscale) y este equipo | Casa u oficina |
| `abierto` | Cualquier IP; escucha en todas las interfaces (0.0.0.0) | Internet o VPN. Exige código de 12 caracteres y confirmación `ABRIR` |

Nota: en `lan` el anfitrión solo escucha en la IP privada detectada y en loopback. Con Tailscale o ZeroTier hay
que usar `abierto`.

## 5. Unirse a una sala

1. Menú de modo online, opción de unirse.
2. Escribe la dirección `IP:puerto` del anfitrión y el **código de sala**. Las mayúsculas, espacios y guiones del
   código se ignoran.
3. Elige tu alias y rol. Espera en la sala; el anfitrión inicia.

Si se corta tu conexión, tienes unos **90 segundos** para reconectar y conservar rol y reservas.

## 6. Controles en línea

- **G** abre la lista de saludos rápidos; **1 a 8** envía el saludo elegido. Hay un enfriamiento de ~1,2 s.
  Saludos: ¡Hola!, ¡Buen trabajo!, ¡Ayuda, por favor!, Voy para allá, Espérame, Gracias, ¡Vamos!, Buena decisión.
- **No hay chat libre**: solo esos saludos fijos, a propósito (evita acoso y datos personales escritos).
- Vehículos: la tecla de interacción (E) pide montar; el anfitrión confirma. Un vehículo solo lo usa una persona.
- El resto de controles son los del juego normal.

## 7. Seguridad: lo que debes saber antes de jugar

- **El tráfico NO va cifrado** (sin TLS en la versión 1). Quien esté en la ruta de red puede leerlo.
- **El cliente no verifica al anfitrión.** Un anfitrión falso podría hacerse pasar por el tuyo. Comprueba la
  dirección con el anfitrión por otro canal.
- El código de sala (6 caracteres en `lan`, 12 en `abierto`) no viaja en claro, pero en una red sin cifrar se
  podría adivinar fuera de línea a partir de un saludo capturado. El código corto protege poco contra alguien con
  acceso a la red.
- **Recomendación: usa una VPN** (Tailscale, ZeroTier o WireGuard) para jugar por internet, en vez de abrir el
  puerto del router. Con una VPN, usa el ámbito `abierto` sobre la IP de la VPN.
- No juegues con desconocidos. No reenvíes (port forwarding) el puerto del router salvo que entiendas el riesgo.
- **Cortafuegos de macOS:** al abrir el servidor, macOS puede preguntar si permites conexiones entrantes a
  Python. Permítelo solo si vas a alojar. Revisa Ajustes del Sistema, Red, Cortafuegos, y cierra el permiso al
  terminar. Si no pregunta y nadie se conecta, añade manualmente el ejecutable de Python en las opciones del
  cortafuegos.

## 8. Límites conocidos

- Máximo 4 jugadores y 8 conexiones totales; 2 conexiones por IP por defecto (`--max-por-ip` lo cambia).
- Sin migración de anfitrión: si el anfitrión **con ventana** se va o se cae, **la sala se cierra** para todos (en el
  servidor sin gráficos no: ver la sección 3).
- Si un jugador se desconecta con misión, se le guarda 90 s para volver; pero si los demás ya no tienen nada que hacer,
  se le da por salido enseguida y su misión pasa a otro (o termina la partida) en vez de esperar.
- Una IP con 5 fallos de entrada en 60 s queda vetada 60 s; el veto afecta a todos los que comparten esa IP,
  incluidos jugadores legítimos que se reconectan.
- Un máximo de 12 altas por IP por minuto.
- Las decisiones se limitan a ~2 por segundo.
- El catálogo tiene pocas noticias; con 4 jugadores algunas se repiten entre manos.
- Los NPC no se sincronizan: cada jugador ve los suyos.
- Sin probar con dos equipos físicos distintos, alta latencia con vehículos, ni calidad real de audio.
- Posible etiqueta de alias mal colocada en el mundo (por revisar).
- Un nombre con letras de otros alfabetos parecidas a las latinas puede evadir la lista de nombres reservados.

### Versiones y contenido compartido

Todos los equipos deben tener **la misma versión del juego**. El anfitrión compara dos huellas (SHA-256): la del
mundo (semilla, lugares, calles, límites y, con `ALCALDE_PUESTOS_FIJOS`, la feria alargada y los puestos fijos) y la del contenido
(versión del protocolo, misiones con sus textos, roles, noticias, el grafo social con sus relaciones, el ciudadano de
cada rol y, desde el 2026-11-22, si hay bicis y motos en línea). Si no coinciden, la sala rechaza la entrada.

Versión actual del protocolo: **v6** (`backend/red/protocolo.PROTOCOLO_V`). Historia:

- **v2 (2026-10):** banderas de `pos`/`snap` (caballito) y huellas que cubren calles, noticias, grafo y misiones.
- **v3 (2026-10-24):** el grafo social ganó la relación puente Luana–Nayara (la comunidad del Morro ya no está
  separada de la red de Ana). Un equipo con la versión anterior recibe el rechazo «versión distinta».
- **v4 (2026-10):** vehículos en línea y rechazo con el texto de la versión.
- **v5 (2026-11):** veredicto y confianza de la ciudad en línea (campos opcionales nuevos).
- **v6 (2026-11, recta final):** campos opcionales `mult`/`nivel` en «ind» y `desenlace`/`claves` en «fin».
- **2026-11-22 (sin cambiar de versión):** la bandera de vehículos entra en la huella del contenido. Un equipo con el
  código anterior al 2026-11-22 no se empareja con uno actualizado («Mundo distinto»): **todos deben actualizar**.
- **2026-11-22, ajustes para la Feria (sin cambiar de versión):** la Oficina do Beto y Zeca pasan a la pared lateral
  oeste de la Rodoviária y, con `ALCALDE_PUESTOS_FIJOS`, la posición de todos los puestos fijos entra en la huella
  del mundo (clave `puestos`). Con la semilla por defecto la huella del mundo pasa de `7cc465e2…` a `42363471…`; la
  del contenido no cambia. Un equipo con el código anterior ve «Mundo distinto»: **todos con el mismo código**.
- **Un solo mundo:** anfitrión y clientes construyen el MISMO mundo (Ciudad3D, 11 lugares) y el catálogo de 14 misiones.
  En línea existen 8 vehículos (el protocolo nombra 0..7; `N_VEHICULOS_MAX = 8`). El «mapa grande» (900 x 650 m, 24 lugares,
  47 misiones, 24 vehículos, viaje rápido en mototáxi y teleférico, mensajes `viaje`/`viaje_ok`/`viaje_no`) y su variable
  `ALCALDE_MAPA_GRANDE` se eliminaron el 2026-11-18; el número de versión del protocolo no cambió porque nada que usara el
  mundo chico cambió en el cable.
- Los significados en español de los nombres brasileños («Prefeitura (Alcaldía)») son **solo de pantalla**: no
  entran en las huellas, así que dos equipos se emparejan aunque uno los tenga apagados (`ALCALDE_SIN_GLOSAS=1`).

## 9. Solución de problemas

| Síntoma | Causa probable | Qué hacer |
|---|---|---|
| «Tu mundo es distinto» | `ALCALDE_SEMILLA`, `ALCALDE_PUESTOS_FIJOS` o `ALCALDE_VEHICULOS_ONLINE` distintos, o código del juego distinto | Igualarlos en todos y reiniciar |
| «Versión del protocolo distinta» | Un equipo tiene otra versión del juego (p. ej. sin la recta final v6) | Actualizar todos a la misma versión |
| «Código incorrecto» | Código mal escrito, o varios intentos fallidos desde ese equipo (veto de 60 s) | Pedirlo de nuevo (no distingue mayúsculas); tras varios fallos, esperar un minuto |
| «Sala ocupada» | Límite por IP (2) o sala llena (4) | Subir `--max-por-ip` o esperar |
| No se conecta por Tailscale/ZeroTier | Ámbito `lan` | Anfitrión con ámbito `abierto` |
| Conexión rechazada | Cortafuegos, puerto o IP errónea | Revisar cortafuegos de macOS, `IP:puerto` y la red |
| Rechazo por IP pública en `lan` | `lan` solo admite IP privadas | Usar VPN y `abierto` |
| Conexiones rechazadas de repente | Veto temporal de 60 s | Esperar un minuto |
| «Anfitrión desconectado» | El anfitrión cerró o se cayó | Volver al menú y crear otra sala |
| Un jugador no aparece | Pasó el límite de 90 s de reconexión | Volver a entrar a la sala |

## 10. Borrar datos locales

Los ajustes se guardan en `~/.alcalde_digital/ajustes.json`. Ver `docs/PRIVACIDAD_ONLINE.md`, sección 6.
