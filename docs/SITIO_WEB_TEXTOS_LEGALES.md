# Textos legales para el pie del sitio web de Alcalde Digital

> **Borrador para revisión legal antes de publicar.** No soy abogado y esto no es asesoría legal. Estos textos
> cubren los requisitos que conozco y se basan solo en lo que dicen `docs/AVISOS_LEGALES_Y_ACTIVOS.md`,
> `docs/PRIVACIDAD_ONLINE.md`, `docs/CONTENIDO_Y_CLASIFICACION.md` y `docs/ONLINE.md`. Lo que aparece como
> **[PENDIENTE]** falta por completar o confirmar antes de publicar.
>
> Versión 1.0 · 2026-11-17

Cada bloque está pensado para pegarse tal cual en una página o sección del pie. Los textos entre corchetes
son datos que debe poner el dueño.

---

## 1. Aviso de descarga y uso

**Qué descargas.** Un archivo .zip con «Alcalde Digital», un juego educativo en 3D para computador (PC), hecho en
Python con el motor Ursina. Trata sobre la desinformación y se ambienta en una favela brasileña ficticia. Todas
las personas, lugares, misiones y el dinero (R$) del juego son inventados y no tienen valor real.

**Es software de aprendizaje.** Es un proyecto educativo y de aprendizaje. No es un producto comercial ni un
servicio profesional.

**Sin garantías.** El juego se ofrece «tal cual», sin garantía de ningún tipo: puede tener errores, cambiar o
dejar de estar disponible sin aviso. En la medida que permita la ley, el autor no responde por daños derivados de
descargarlo o usarlo.

**Ejecútalo bajo tu propia responsabilidad.** Descarga el archivo solo desde esta página. Antes de abrirlo,
revisa con tu antivirus que no haya sido alterado. El programa se ejecuta con los permisos de tu usuario y
escribe archivos en tu carpeta personal (ver «Privacidad»). Si usas el modo online, lee los riesgos de esa
sección.

**Sin telemetría.** El juego no envía estadísticas, informes de errores ni datos de uso al autor. No tiene
cuentas, publicidad, compras reales, ni pide ubicación, cámara, micrófono ni contactos. La única conexión de red
posible es el modo online opcional, que solo se activa cuando tú creas una sala o te unes a una.

**Uso con menores.** El juego no está dirigido a menores y no pide la edad. Si lo usan menores, que sea con
permiso y acompañamiento de un adulto responsable. [PENDIENTE: edad mínima.]

---

## 2. Privacidad

**Esta web.** Es un sitio estático. No usa cookies, no usa rastreadores ni analítica, y no pide datos personales.
[PENDIENTE: confirmar antes de publicar. Si el alojamiento o una red de distribución (CDN) guarda registros de
visitas, o si se añade un formulario o contador, este párrafo debe cambiar.]

**Qué guarda el juego y dónde.** Todo se guarda solo en tu equipo, en la carpeta `~/.alcalde_digital`, sin cifrar.
Nada de esto se envía al autor:

- `partida.json`: tu partida (alias de los jugadores, rol, posición, teléfono y dinero **del juego**, misiones,
  decisiones y reloj).
- `ajustes.json`: filtros de daltonismo, volúmenes, dispositivo de audio, tu último alias y la última dirección
  de anfitrión (IP:puerto) del modo online.
- `cache/`: archivos de caché del mundo, generados por el propio juego.

**Consejo:** no uses tu nombre real como alias. Para borrar tus datos: en el juego, Ajustes, botón «Borrar
partida guardada» (partida) y Ajustes, sección Online, botón «Olvidar» (alias y último anfitrión). También puedes
cerrar el juego y borrar la carpeta `~/.alcalde_digital`.

**Modo online (opcional).** Está activo por defecto, pero no se conecta a nada hasta que crees una sala o te unas
a una (se apaga por completo arrancando con `ALCALDE_ONLINE=0`). No hay servidor del autor ni cuentas: una persona
(el anfitrión) aloja la sala y los demás se conectan a su equipo. Esto implica:

- El anfitrión ve tu **dirección IP**. Los demás jugadores ven tu **alias, rol, posición y movimiento**, tus
  decisiones públicas y tus saludos rápidos. No hay chat libre.
- **El tráfico no va cifrado** y tu juego **no comprueba quién es el anfitrión**. Quien esté en la ruta de red
  podría leer alias, posiciones e IP, o un impostor podría hacerse pasar por tu anfitrión. Juega en red local o
  con una VPN, y solo con personas de confianza.
- El anfitrión no guarda nada de la partida en disco: todo queda en memoria y desaparece al cerrar la sala. Tras
  una desconexión conserva tu rol 90 segundos para que puedas volver.
- El inventario, el dinero y el cansancio son locales y no se envían en el modo online.
- No se recolecta ubicación real, contactos, cámara ni micrófono.
- Si alojas una sala, ves la IP y el alias de los demás: úsalos solo para la partida.

**Responsable.** El autor del juego no recibe datos. En el modo online, quien aloja la sala trata los datos de los
participantes mientras dura la partida. [PENDIENTE: nombre y correo de contacto público del autor para dudas de
privacidad.]

---

## 3. Créditos y licencias

**Juego:** «Alcalde Digital». Autor/a: [PENDIENTE: nombre o seudónimo a publicar]. Licencia del código y de los
contenidos propios: [PENDIENTE: no consta en los documentos; elegir licencia, por ejemplo todos los derechos
reservados o una licencia abierta].

**Activos que constan en la documentación:**

| Activo | Autor/a y licencia | Estado |
|---|---|---|
| 5 modelos 3D de personajes nuevos (.glb) | El archivo declara solo el generador «Khronos glTF Blender I/O». No consta autor, origen ni licencia | **[PENDIENTE]** no publicar estos modelos hasta confirmar autoría y licencia. Si no se confirma, el juego usa los 4 modelos de respaldo |
| 4 modelos 3D de respaldo (los de siempre) | No consta en los documentos leídos | **[PENDIENTE]** |
| Textos, personajes, lugares, misiones y dilemas | No consta licencia | **[PENDIENTE]** |
| Música, sonidos, tipografías, imágenes y texturas | No constan en los documentos leídos | **[PENDIENTE]** inventario y licencia de cada uno |
| Motor Ursina, Python y bibliotecas del .zip | No constan en los documentos leídos | **[PENDIENTE]** listar y atribuir con la licencia de cada una (varias exigen incluir su aviso) |

El archivo `CREDITOS.md` de la raíz, que debía llevar el registro (archivo, autor, licencia, enlace y
modificaciones), todavía no consta como creado. Cuando exista, este apartado debe reflejarlo y enlazarlo.

**Inspiración cultural.** Las manillas del juego están inspiradas en una tradición popular de Salvador (Brasil).
Aquí son solo un recurso de juego y no representan ninguna práctica religiosa. La iglesia, el puesto de salud, la
escuela y los demás lugares son ficticios.

**Marcas y personas.** Todos los personajes y lugares son ficticios; cualquier parecido con personas, escuelas,
asociaciones o marcas reales es casual. Las marcas citadas pertenecen a sus dueños y el juego no está afiliado a
ellas.

---

## 4. Clasificación de contenido

Clasificación oficial: **ninguna asignada**. Este juego no se publica en tiendas y no ha pasado por IARC, Apple,
Classificação Indicativa ni otra autoridad. **[PENDIENTE]** Si se distribuye, la clasificación la decide la
autoridad correspondiente.

Descripción del contenido (según nuestra revisión interna, con las opciones sensibles apagadas):

- **Tema:** sátira educativa sobre desinformación, ambientada en una favela brasileña. Hay noticias falsas,
  dilemas morales y referencias a menores y a posibles estafas, tratados con tono educativo.
- **Violencia, sangre, desnudez, lenguaje soez grave, apuestas:** no hay.
- **Sustancias:** hay una referencia a una bolsita de bicarbonato de sodio vendida en un puesto de calle
  (el juego aclara que «no cura nada») y un bar en el mapa. No se muestra ningún consumo.
- **Armas:** el catálogo contiene objetos de utilería ocultos por defecto, sin uso, sin precio y sin forma de
  obtenerlos. Hay también decoración humorística (pistolas de agua) que está bajo una opción de huevos de
  pascua. **[PENDIENTE]** confirmar qué incluye exactamente el .zip publicado y apagar estas opciones.
- **Dinero:** solo moneda ficticia (R$ del juego). Sin compras reales, cajas de botín, publicidad ni apuestas.
- **Online:** posible interacción con otras personas si abres una sala a internet; sin chat libre (solo saludos
  fijos).
- **Recomendación:** no dirigido a menores. Edad mínima sugerida: [PENDIENTE, a definir con asesoría legal].

---

## Notas para quien publique (no pegar en la web)

- Estos textos suponen que el modo online y los guardados siguen como describen los documentos de la fecha
  indicada. Si cambia el código, hay que actualizarlos.
- Los docs fuente dicen que el contenido sensible se verifica con banderas (`ITEMS_SENSIBLES`, `EASTER_EGGS`);
  los docs mismos indican que el valor de `EASTER_EGGS` no se verificó. Revisar antes de empaquetar el .zip.
- El .zip no debe incluir la carpeta `~/.alcalde_digital` ni datos de pruebas.
- Los documentos fuente se refieren a que no se publica en tiendas; si el sitio cambia eso, rehacer privacidad
  y clasificación.
