# Avisos legales y de contenido: guardado, dilemas, manillas, modelos 3D y nombres

> **Borrador para revisión legal antes de publicar.** No soy abogado y esto no es asesoría legal. El proyecto es
> educativo, con datos ficticios, y no se publica en tiendas. Este texto cubre los requisitos que conozco; no
> afirma que cumpla ninguna ley ni que una tienda vaya a aprobar el juego. Complementa (no reemplaza) a
> `docs/PRIVACIDAD_ONLINE.md` y `docs/CONTENIDO_Y_CLASIFICACION.md`.
>
> Versión 1.0 · 2026-11-12 · rama `plan-de-trabajo-final`

## 1. Qué datos toca lo nuevo

| Función | Qué guarda o recolecta | Sale del equipo | Personal real |
|---|---|---|---|
| Guardado de partida (`backend/logica/guardado.py`) | `~/.alcalde_digital/partida.json`: alias de jugadores, rol, posición, teléfono y economía **del juego**, misiones, decisiones, reloj, semilla del mundo. Sin cifrar, hasta 4 MB | No | Solo si el jugador escribe su nombre real como alias |
| Reloj de partida y efectos retardados | Van dentro de `partida.json` (hora de juego, consecuencias pendientes) | No | No |
| Caché del mundo (`backend/datos/cache_mundo.py`) | `~/.alcalde_digital/cache/` (archivo pickle generado por el propio juego) | No | No |
| Frases de NPC (`frases_npc.json`) | Nada: texto fijo de ambientación | No | No |
| Dilemas (`dilemas_extra.json`) | Nada nuevo; las decisiones se guardan en `partida.json` | No | No |
| Manillas | Nada (solo dibujo y cálculo) | No | No |

Conclusión: no hay telemetría, cuentas, ubicación, cámara, micrófono ni contactos. `docs/PRIVACIDAD_ONLINE.md` sigue
vigente en lo sustancial; se le añadió la sección 6 bis para el guardado y la caché (que no estaban listados).

**Aviso al jugador (propuesto, para el menú de guardar/Ajustes):** «Tu partida se guarda solo en este equipo, en
`~/.alcalde_digital/partida.json`, sin cifrar. No uses tu nombre real como alias. Puedes borrarla desde el menú o
borrando esa carpeta.»

**Requisitos para desarrollo (no implementados aquí):**
1. Botón o comando visible «Borrar partida guardada» (existe `guardado.borrar()`; verificar que la interfaz lo ofrezca).
2. Mostrar el aviso anterior la primera vez que se guarda.
3. En modo tienda, valorar que la caché use un formato distinto de pickle (riesgo de seguridad si alguien sustituye
   el archivo); pasar por `security-auditor` y `preservador`.

## 2. Dilemas (`dilemas_extra.json`): revisión de contenido

Los ocho dilemas son educativos y de tono equilibrado (ninguna opción es gratis). Revisión por tema:

| Dilema | Observación | Ajuste sugerido |
|---|---|---|
| Foto del cumple, captura de la rifa, ensayo en vivo | Enseñan a **no exponer datos de terceros** (dirección, teléfonos, caras de niños). Coherente con el contexto educativo; ninguna instrucción real de vigilancia | Ninguno. Mantener la nota «personas y lugares ficticios» visible en la ficha |
| Captura de la rifa | Acusa de apropiación de dinero a un personaje (tesorero); es ficticio | Que no coincida con una persona real de una asociación real |
| Colecta de Kauã | Menor enfermo y posible estafa; tono serio | Evitar cuentas, bancos o plataformas reales de colecta |
| «Tipo raro» de la escuela | Menores, escuela y señalamiento de un inocente (lector de la luz) | Ver punto 4: nombre de escuela. Tono adecuado; la consecuencia muestra el daño del bulo |
| Pelo en el pan, balanza, corte de agua, domingo sin pantalla | Sin riesgo particular | Ninguno |

Tiendas de apps: no hay contenido generado por usuarios, compras, apuestas ni publicidad. La «rifa» es solo un
tema narrativo (no hay rifa jugable con dinero real). Para el cuestionario de edades declarar: referencias a
menores en situaciones de riesgo (leve), a dinero/estafas ficticias y a tema de desinformación. Para el contexto
educativo: recomendable una guía breve para el docente (sin datos reales de alumnos; los menores no deben
registrar su nombre real).

## 3. Manillas de Bonfim: tono y referencias culturales

- El texto «Inspiradas en las fitinhas do Bonfim… tres nudos, tres deseos» (`frontend/manillas_calculos.py`) es
  respetuoso: es un **homenaje**, no afirma nada religioso, y `PLAN_FINAL.md` §10 ya dice «sin afirmaciones
  religiosas ni estereotipos».
- Riesgos a vigilar: (a) usar la manilla como indicador de «mal estado» (deshilachada, gris) asociada a un símbolo
  de devoción real podría resultar irrespetuoso para algunas personas; (b) no usar en el juego imágenes de la
  iglesia real ni el nombre de la fiesta como marca.
- Sugerencia de texto de ficha: «Inspiradas en una tradición popular de Salvador (Brasil). Aquí son solo un
  recurso de juego y no representan ninguna práctica religiosa». Que alguien de la comunidad cultural o el profesor
  lo lea antes de publicar. La iglesia del mapa («Nossa Senhora da Esperança») es ficticia; debe decirse así.

## 4. Nombres de personas y marcas reales

Revisado el texto del juego (`backend/` y `frontend/`):

| Hallazgo | Dónde | Riesgo | Acción sugerida |
|---|---|---|---|
| ~~«Escola Municipal **Paulo Freire**»~~ **RESUELTO** | `ciudad_grande.py`, `nombres_visibles.py`, `misiones_semilla.py`, `dilemas_extra.json` y otros | Era el nombre de una persona real (educador) | Renombrada a «Escola Bairro Esperança» (visible: «Escuela Barrio Esperanza»), nombre inventado, en todos los archivos |
| ~~**WhatsApp**~~ **RESUELTO** (traducción de «zap», «corrente do zap», «Zap do Morro») | `nombres_visibles.py` | Era marca real en texto visible | Ahora «chat», «cadena del chat», «chat del cerro». Una prueba (`tests/test_pulido_legal.py`) vigila que no vuelvan nombres reales ni marcas en `backend/` y `frontend/` |
| «Globo» | `globos.py` etc. | Falso positivo (globo de texto) | Ninguno |
| Nombres de pila (Dani, doña Marta, Kauã, doña Cida, Seu Zé, doña Lu) | dilemas, frases | Comunes y ficticios | Ninguno; no se hallaron apellidos de personas reales |

No pude comprobar imágenes, murales ni letreros dibujados (solo texto); revisar carteles de `barrio_favela.py`.

## 5. Modelos 3D de los 5 NPC nuevos (autoría y licencia)

Estado: en `MODELOS_3D.md` (§ NPC nuevos) los .glb **no declaran autor, licencia ni copyright**; solo el
generador «Khronos glTF Blender I/O». Autoría y licencia están como `[COMPLETAR]`.

Qué falta para poder distribuirlos:

1. **Autor/a y origen.** Quién los modeló. Si son creación propia del equipo, basta una declaración firmada o por
   escrito. Si se partió de un modelo, rig o animaciones de terceros (Mixamo, Sketchfab, Quaternius, Kenney, etc.),
   anotar nombre, URL y fecha de descarga.
2. **Licencia exacta** y su texto: creación propia (elegir licencia: todos los derechos reservados o CC BY 4.0 /
   CC0), o la licencia de origen. Atención: CC BY exige atribución; CC NC (no comercial) y ND (sin derivadas)
   pueden impedir su uso o su modificación; Mixamo tiene términos propios; algunas licencias prohíben
   redistribuir el archivo tal cual dentro de un repositorio público.
3. **Derechos sobre las texturas y la apariencia** (si se basan en fotos o personas reales, necesitan permiso).
4. **Registro** en un archivo `CREDITOS.md` en la raíz: nombre del archivo, autor, licencia, enlace, modificaciones.
5. **Si el repositorio es público o se distribuye:** sin los puntos 1 a 3 confirmados, no publicar los .glb;
   dejar el modelo de respaldo (los 4 de siempre) como predeterminado. El juego ya cae a esos modelos si faltan.
6. Para el uso solo académico interno, la anotación «creación propia, uso interno de aprendizaje» es suficiente,
   pero hay que **decirlo con verdad**: si no es cierto, usar la licencia de origen.

Plantilla para completar (el dueño):

```
Archivos: <los 5 .glb>
Autor/a: [nombre o «creación propia del equipo»]
Origen: [nada / URL de la base usada y fecha]
Licencia: [...] · Texto: [enlace]
Modificaciones: [...]
Fecha: [...]
```

## 6. Pendiente de revisión legal

- Si las referencias a Bonfim y a una iglesia, aun con intención de homenaje, requieren
  permisos o aviso de ficción.
- Licencia y titularidad de los modelos 3D y de las animaciones.
- Si la IP y el alias guardados en el equipo del anfitrión son dato personal (ver `PRIVACIDAD_ONLINE.md` §10).
- Edad mínima y uso en aula con menores: consentimiento de la institución y de los acudientes; protección de
  datos de menores en la jurisdicción (Brasil: LGPD; Colombia: Ley 1581 de 2012, solo referencia).
- Clasificación por edades (Brasil, Classificação Indicativa) si se distribuye.

## 7. Qué debe completar el dueño

1. Autor y licencia de los 5 .glb (sección 5) y crear `CREDITOS.md`.
2. (Hecho) Cambio de nombre de la escuela y de las menciones a WhatsApp. Queda opcional revisar «Praça da Sé» en un
   texto de noticias (nombre de un lugar real de São Paulo, usado como sitio ficticio).
3. Confirmar si habrá uso en aula con menores y quién es el responsable (docente, universidad).
4. Contacto público y país de distribución si algún día se publica.

## 8. Guardado de la partida y caché del mundo (riesgos y controles)

- **Partida guardada** (`partida.json` en `~/.alcalde_digital/`): vive solo en el equipo del jugador. El juego avisa la
  primera vez que guarda («Tu partida se guarda solo en este equipo; puedes borrarla en Ajustes») y en Ajustes >
  «Partida» hay un botón «Borrar partida guardada» con confirmación de dos pasos. Tras borrar, la partida en curso no
  se vuelve a autoguardar; una partida nueva sí.
- **Topes de longitud**: cada texto de `dilemas_extra.json` admite como máximo 400 caracteres (si no, el cargador
  rechaza el archivo con el id del dilema) y el mensaje de un efecto retardado se recorta a 400 caracteres también
  cuando viene de un guardado manipulado. Así un JSON editado a mano no puede desbordar los paneles.
- **Riesgo del `pickle` (`backend/datos/cache_mundo.py`)**: la caché del mundo grande se guarda con `pickle`
  (~8 MB, en `~/.alcalde_digital/cache`, o `$ALCALDE_CACHE_DIR`). `pickle.load` puede ejecutar código arbitrario si
  alguien sustituye ese archivo. Mitigaciones actuales: el archivo lo escribe el propio juego en la carpeta del
  usuario, nunca se carga desde la red ni desde el repositorio, su nombre incluye una huella del código y de los datos,
  y un archivo ilegible o de otra versión se ignora y se reconstruye. **Riesgo residual**: quien ya pueda escribir en
  la carpeta del usuario ejecutaría código al arrancar (ya tendría acceso equivalente a ese usuario). No se cambió el
  formato. Si algún día la caché se distribuye o se comparte (p. ej. una carpeta de red o un aula), hay que cambiarla a
  un formato de datos (JSON o `marshal` de tipos simples) o firmarla con HMAC. Para anularla: `ALCALDE_SIN_CACHE_MUNDO=1`.
