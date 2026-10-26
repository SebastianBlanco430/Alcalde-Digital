# Modo online cooperativo de Alcalde Digital

> **Borrador para revisión legal antes de publicar.** El autor de este texto no es abogado. Es material de un
> proyecto de aprendizaje con datos ficticios; no es asesoría legal.
>
> Versión 1.1 · 2026-10-24 · Protocolo de red v3

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
| `ALCALDE_VEHICULOS_ONLINE` | Bicis y motos en línea. Activo salvo que valga `0` | **Debe coincidir en todos** |
| `ALCALDE_SEMILLA=N` | Entero que decide la disposición de la favela | **Debe coincidir en todos** |

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
- Sin migración de anfitrión: si el anfitrión se va o se cae, **la sala se cierra** para todos.
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
mundo (semilla, lugares, calles y límites) y la del contenido (misiones con sus textos, roles, noticias, el grafo
social con sus relaciones y el ciudadano de cada rol). Si no coinciden, la sala rechaza la entrada.

- **Protocolo v3 (2026-10-24):** el grafo social ganó la relación puente Luana–Nayara (la comunidad del Morro ya
  no está separada de la red de Ana). Un equipo con la versión anterior recibe el rechazo «versión distinta».
- **Mapa grande (por defecto):** anfitrión y clientes construyen el MISMO mundo (`ALCALDE_MAPA_GRANDE`, por defecto 1: 24
  lugares, ~4600 casas) y el catálogo grande de 47 misiones. La huella del mundo añade la clave `casas` (firma de las casas
  generadas) solo con el mapa grande; la del mundo chico (`ALCALDE_MAPA_GRANDE=0`) no cambia. Un equipo con el mapa chico y
  otro con el grande no se emparejan («Tu mundo es distinto»): poned la misma variable en todos. Con el mapa grande el juego
  local tiene 24 vehículos, pero en línea solo existen los 8 primeros (el protocolo nombra 0..7; `N_VEHICULOS_MAX`).
- Los significados en español de los nombres brasileños («Prefeitura (Alcaldía)») son **solo de pantalla**: no
  entran en las huellas, así que dos equipos se emparejan aunque uno los tenga apagados (`ALCALDE_SIN_GLOSAS=1`).

## 9. Solución de problemas

| Síntoma | Causa probable | Qué hacer |
|---|---|---|
| «Tu mundo es distinto» | `ALCALDE_SEMILLA`, `ALCALDE_VEHICULOS_ONLINE` o `ALCALDE_MAPA_GRANDE` distintos | Igualarlos en todos y reiniciar |
| «Versión del protocolo distinta» | Un equipo tiene otra versión del juego (p. ej. sin el grafo social v3) | Actualizar todos a la misma versión |
| «Código incorrecto» | Código mal escrito | Pedirlo de nuevo; no distingue mayúsculas |
| «Sala ocupada» | Límite por IP (2) o sala llena (4) | Subir `--max-por-ip` o esperar |
| No se conecta por Tailscale/ZeroTier | Ámbito `lan` | Anfitrión con ámbito `abierto` |
| Conexión rechazada | Cortafuegos, puerto o IP errónea | Revisar cortafuegos de macOS, `IP:puerto` y la red |
| Rechazo por IP pública en `lan` | `lan` solo admite IP privadas | Usar VPN y `abierto` |
| Conexiones rechazadas de repente | Veto temporal de 60 s | Esperar un minuto |
| «Anfitrión desconectado» | El anfitrión cerró o se cayó | Volver al menú y crear otra sala |
| Un jugador no aparece | Pasó el límite de 90 s de reconexión | Volver a entrar a la sala |

## 10. Borrar datos locales

Los ajustes se guardan en `~/.alcalde_digital/ajustes.json`. Ver `docs/PRIVACIDAD_ONLINE.md`, sección 6.
