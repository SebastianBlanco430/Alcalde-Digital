# Privacidad del modo online y de los ajustes

> **Borrador para revisión legal antes de publicar.** No soy abogado y esto no es asesoría legal. El proyecto es
> de aprendizaje, con datos ficticios, y no se publica en tiendas. Este texto cubre los requisitos que conozco;
> no afirma que cumpla ninguna ley. Si algún día se distribuye al público, un abogado debe validarlo.
>
> Versión 1.0 · 2026-10-23

## 0. Estado por defecto

El modo online está **activo por defecto**. Para apagarlo por completo (sin red) arranca con `ALCALDE_ONLINE=0`.
Aun activo, no se conecta a nada hasta que tú crees una sala o te unas a una.

## 1. Quién trata los datos

No existe una empresa ni un servidor central. **La persona que aloja la sala** (el anfitrión) recibe y procesa
los datos de los demás mientras dura la partida. El autor del juego no recibe ningún dato.

## 2. Qué datos se tratan en el modo online

| Dato | Para qué | Quién lo ve |
|---|---|---|
| **Dirección IP** de cada jugador (inevitable al conectarse por red) | Establecer la conexión, limitar abusos (máximo por IP, veto temporal) | El anfitrión; y todos los equipos de la red por la que viaja el tráfico. Los demás jugadores **no** reciben tu IP en los mensajes del juego, pero si compartes IP:puerto de la sala o juegas en una VPN, otros pueden ver direcciones de la red |
| **Alias** que escribes | Identificarte en la sala | Todos los jugadores |
| **Rol** elegido y estado de listo | Organizar la partida | Todos |
| **Posición, rumbo, velocidad, si estás en el aire, en escalera, dentro de un edificio o montado en vehículo** (20 veces por segundo) | Mostrarte a los demás y validar el movimiento | Todos |
| **Decisiones y avance de misiones** | Jugar | El anfitrión; las decisiones privadas solo a su dueño y un resumen a los demás |
| **Saludos rápidos** (índice de una lista fija) | Comunicación mínima | Todos |
| Retardo de red (ping) | Mostrar la calidad de conexión | Cada jugador |

Notas para quien entre en una sala:

- Tu IP es visible para el anfitrión y para cualquier equipo que vea el tráfico, porque **no hay cifrado**.
- El anfitrión no registra las IP de los pares en archivos de registro (según la revisión del código); las
  mantiene en memoria para los límites y vetos.
- **No hay chat libre**: no se envía texto escrito por ti, salvo el alias.
- No se recolecta ubicación geográfica real, contactos, cámara ni micrófono.
- Los datos del juego (personas, misiones, dinero) son **ficticios**.
- El **inventario, el dinero (R$) y el cansancio son locales**: no se envían en el modo online ni se guardan en
  el equipo del anfitrión. Ver `docs/CONTENIDO_Y_CLASIFICACION.md` para el contenido y la clasificación.

## 3. Sin cifrado ni verificación del anfitrión

- El tráfico viaja **sin cifrar** (versión 1). Cualquiera en la misma red o en el camino podría leer alias,
  posiciones, IP y el token de reconexión.
- Tu cliente **no comprueba la identidad del anfitrión**. Puedes conectarte a un impostor si la dirección es
  falsa.
- El código de sala protege la entrada, pero en una red sin cifrar un atacante podría deducirlo a partir de un
  saludo capturado.

**Recomendación:** juega en tu red local o usa una VPN (Tailscale, ZeroTier, WireGuard). Detalles en
`docs/ONLINE.md`.

## 4. Ámbitos de exposición

- `local`: solo tu equipo.
- `lan`: tu red local (y el rango de Tailscale 100.64.0.0/10).
- `abierto`: escucha en todas las interfaces. Es la opción de mayor riesgo; exige código largo y confirmación.

Elige el más pequeño que te sirva. En macOS, el cortafuegos puede pedir permiso; concédelo solo mientras
alojes y revócalo después.

## 5. Retención

- **Ningún servidor externo** guarda datos.
- **El anfitrión no guarda nada en disco** de la partida (posiciones, alias, decisiones, IP): todo está en
  memoria y desaparece al cerrar la sala o el programa.
- Cada jugador conserva en su equipo solo sus propios ajustes (sección 6).
- Tras una desconexión, el anfitrión conserva tu rol y tu token en memoria hasta 90 segundos para permitir la
  reconexión.
- Cada persona puede copiar o capturar lo que ve en pantalla; el juego no puede impedirlo.

## 6. Ajustes locales y cómo borrarlos

El archivo `~/.alcalde_digital/ajustes.json` guarda: filtros de daltonismo, volúmenes, dispositivo de audio, **tu
último alias** (`nombre_en_linea`) y **la última dirección de anfitrión `IP:puerto`** (`ultimo_host`). El archivo
**no está cifrado**; cualquiera con acceso a tu cuenta de usuario puede leerlo.

Para borrarlo:

- Dentro del juego: Ajustes, sección Online, botón **Olvidar** (borra alias y último anfitrión).
- Manual: cierra el juego y ejecuta `rm ~/.alcalde_digital/ajustes.json` (o borra la carpeta
  `~/.alcalde_digital`). Se vuelve a crear con valores por defecto.

## 7. Menores de edad

El juego no pide edad, no tiene chat libre ni compras. Aun así, el modo online conecta tu equipo con el de
desconocidos si lo abres a internet. **Los menores deben jugar solo con personas de confianza, en red local o
VPN, y con permiso de un adulto responsable.** Si se publica, un abogado debe definir la edad mínima y el
consentimiento parental según la jurisdicción.

## 8. Tus derechos y límites

Como no existe un servidor central ni cuentas, no hay base de datos que consultar o suprimir: lo local lo
controlas tú (sección 6) y lo que tiene el anfitrión desaparece al cerrar la sala. Si alojas partidas de
terceros, informa a los participantes de que ves su IP y alias y no los uses para otro fin.

## 9. Cambios

Este documento puede cambiar si cambian las funciones (por ejemplo, al añadir cifrado). La versión y la fecha
están al inicio.

## 10. Pendiente de revisión legal

- Jurisdicción y ley aplicable (el contexto del proyecto es Colombia, solo como referencia).
- Si la IP es dato personal y quién es "responsable" cuando un particular aloja (rol del anfitrión).
- Edad mínima, consentimiento y tratamiento de menores.
- Cláusulas de responsabilidad por tráfico sin cifrar y por impostores de anfitrión.
- Si se distribuye en tiendas: política de privacidad pública, "App Privacy" de Apple y "Data safety" de Google.
