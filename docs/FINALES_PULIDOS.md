# Finales pulidos (Persona B, ronda 2)

Revisión toma por toma de las cinemáticas finales (bueno, malo y neutro, con los cuatro roles) y arreglo de lo que se
veía mal. Todo va tras una bandera; los textos, la narrativa y las duraciones de los planos **no cambian**.

## Bandera

| Bandera | Por defecto | Qué hace | Dónde se lee |
|---|---|---|---|
| `ALCALDE_FINALES_PULIDOS` | 1 | Puestas, cámaras, poses, elenco y decorado corregidos del final animado | `frontend/final_animado/final_pulido_calculos.py` |

Con `ALCALDE_FINALES_PULIDOS=0` el final animado es exactamente el de antes (`puesta.vigentes()` devuelve `PUESTAS`,
`camaras._tomas()` devuelve `TOMAS`, `poses_final._accion` usa `ACCIONES` y `actores`/`decorado`/`ciudad` toman el camino
de siempre).

## ¿Hay final neutro? (diagnóstico)

Sí. Con los finales por etapas (`ALCALDE_ETAPAS_FINAL`, encendida) el índice de la ciudad (0-100) da la etapa
(`backend/logica/etapas_final.py`): ≥ 60 bueno, ≤ 40 malo y **entre 40 y 60 la etapa 0, «Ciudad en suspenso» = neutro**
(`final_de_etapa`). Lo que se ve:

- Con el final animado (`ALCALDE_FINAL_ANIMADO`, encendido): la secuencia 3D `animacion.neutro` de
  `backend/datos/finales_historia.json` (n1 conteo, n2 plaza a medias, n3 calle, n4 plano del rol, n5 candidatos, n6
  cierre; ~51 s) y después el panel «Ciudad Nova duda» (`finales_textos.py`, clave `neutro`).
- Las viñetas 2D (`cinematicas`) solo existen para bueno y malo: si el final animado falla o está apagado, el neutro va
  directo al panel (`registro_reloj.FINALES_VINETAS`).

Decisión del dueño: **se mantiene y se pule** igual que bueno y malo, sin textos nuevos. Para verlo:
`ALCALDE_INDICE_FORZADO=50`.

## Cómo se revisó

`scripts/final_pulido_capturas.py <final> <rol>` (local, no se versiona) abre el juego real, lanza el final con
`crear_final_animado` y guarda 3 fotogramas por plano en `capturas_claude/finales/`; `SOLO=m4,rol` reproduce solo esos
planos. Se revisaron los 3 finales con los 4 roles antes y después del arreglo. `scripts/final_pulido_poses.py` muestra
una pose en un personaje suelto (frente y perfil) para afinar poses sin cargar la ciudad.

## Defectos y arreglos

| # | Plano | Defecto (antes) | Arreglo | Archivo |
|---|---|---|---|---|
| 1 | m4/b5/n4 ciudadano | El paño de la ventana era más bajo que el letrero de la casa: el cartel «Morro da Esperança (Cerro de la Esperanza)» tapaba medio cuadro | Paño de fachada entero (3,7 × 5,2 m) con alero de chapa, que tapa el letrero de detrás; cámara más baja y cercana | `decorado.VentanaMorro`, `final_pulido_calculos` |
| 2 | m4/b5/n4 ciudadano | El hueco quedaba por debajo de la cabeza del protagonista v2: se veía el torso sin cara | Hueco a la altura de la cara (alféizar 1,05, dintel 2,25) y zócalo bajo el suelo (el Morro tiene pendiente) | `decorado.VentanaMorro` |
| 3 | m4 ciudadano (malo) | Los postigos se cerraban mientras él «abría» y lo tapaban del todo; el último gesto quedaba invisible | Mira el humo, baja la cabeza, se retira y **después** se cierran los postigos (t 0,74-0,94) | `final_pulido_calculos._ciudadano_pulido` |
| 4 | m4/b5/n4 ciudadano | Los postigos giraban hacia dentro, a través del hueco y de la pared | Abren hacia fuera, contra la fachada (`GIRO_POSTIGOS = +1`) | `decorado.VentanaMorro.avanzar` |
| 5 | b5 ciudadano | El banderín le tapaba la cabeza | Banderín por encima del dintel (2,55 m) | `final_pulido_calculos` |
| 6 | m3 protesta | El «puño» a media altura estiraba el brazo hacia delante y arriba con la palma abajo: se leía como otro tipo de saludo | Pose nueva `puno_medio_alto`: codo doblado y puño junto a la cabeza, alternando con el puño arriba | `poses_final.py` (`ACCIONES_PULIDAS`) |
| 7 | m3 protesta, n2 | Las pancartas bajas tapaban la cara de quien las llevaba; las altas flotaban sin manos | Abajo a la altura del pecho, arriba por encima de la cabeza | `actores.Pancarta`, `final_pulido_calculos` |
| 8 | Todos los planos con vecinos | Vecinos con cuerpos v1 (incluido el `ciudadano.glb` viejo) junto a los protagonistas v2 | Los 10 vecinos son la gente del barrio del elenco v2 (vecina, Seu Zé, Jandira, Nico, Lívia, Ramiro, Inês, Marcos, Eurico, Baltazar), sin la fiscal ni Arenas | `actores._vecino_v2`, `final_pulido_calculos.ELENCO_VECINOS` |
| 9 | Todos | La caché del horneado de poses usaba solo el rol: todos los NPC (sin rol) y el protagonista v2 con el vecino v1 del mismo rol compartían poses horneadas en otro esqueleto | La clave incluye tipo de cuerpo y archivo de modelo | `actores._clave_esqueleto` |
| 10 | m2 calles arden | Desde la toma aérea no se veía ni una llama | 6 hogueras de cómic de la propia ciudad (`ciudad_viva.mesh_fuego_vivo`: leños, llamas en tres tonos y humo) con un latido suave, en las calles que mira la cámara (una primera versión con conos sueltos se leía como conos de tráfico) | `decorado.Fogata`, `final_pulido_calculos.FOGATAS_M2` |
| 11 | m5 plaza vacía | La cámara subía mirando el edificio y las pancartas del suelo (de las que habla el subtítulo) salían del cuadro | Retrocede por detrás de las pancartas y termina con ellas delante y la Prefeitura al fondo | `final_pulido_calculos.TOMAS_PULIDAS` |
| 12 | b2 sede oscura | Arenas acababa en el borde del cuadro con solo la cabeza a la vista | Sale del cuadro del todo | `final_pulido_calculos` |
| 13 | b3 calles limpias | El gorro del panadero quedaba sobre la cara de los cuerpos v2 | Sin gorro con el pulido | `actores._bandeja` |
| 14 | b1, b6, b5/m4/n4 candidato | La banda de Octavio era más honda que el torso del smoking v2 y asomaba como una tabla | Banda más fina y pegada al pecho | `actores.vestir_fijo`, `final_pulido_calculos.BANDA` |
| 15 | b6 podio | Un papel del confeti pasaba pegado a la cámara (amarillo a medio cuadro); el final del travelling quedaba tras el atril y una cabeza del público | Confeti solo sobre el público; travelling más alto y algo de lado | `final_pulido_calculos` |
| 16 | b5/m4/n4 candidato | El pie del micrófono cruzaba el torso de Octavio; el vecino del apretón de manos quedaba entre la cámara y él | Micrófono a su izquierda y cámara más de frente | `final_pulido_calculos` |
| 17 | b5/m4/n4 influencer | Los íconos del directo subían pegados a la cámara (enormes y cortados arriba) | Salen detrás de ella | `final_pulido_calculos` |
| 18 | n5 candidatos | A Octavio lo tapaba el cartel amarillo de la calle | Más cerca de la puerta | `final_pulido_calculos` |
| 19 | b1, b6 (y planos de plaza) | Los NPC sentados en los bancos y los corros (cuelgan de las capas de ciudad_viva) se colaban mirando la fiesta | Se esconden durante el final, como los demás NPC del juego | `ciudad.EstadoCiudad._npc_de_capas` |
| 21 | Panel final en línea (y en el modo por turnos sin reloj) | La franja del desenlace de la recta final («Ciudad dividida»…, `recta_final_vista.FRANJA_Y`) se pensó para el hueco de `PanelFinalSemana`; `PanelFinal` era más bajo y la franja tapaba la última línea del resumen y medio botón «Volver al menú» | `PanelFinal` con el mismo alto (0,94), barras y resumen algo más arriba y botón como en el panel de la semana: la franja queda en su hueco. Comprobado con capturas en una partida en línea real | `frontend/panel_final.py`, `final_pulido_calculos.PANEL_FINAL_*` |
| 20 | Recta final en el modo feria | En la feria `FlujoConTiempo` oculta `misiones_a_dict` (para no guardar): el progreso lanzaba `AttributeError`, quedaba en 0 y la recta final no empezaba nunca (sin aviso de entrada, sin evento, sin multiplicador) | Se cuentan las misiones de la feria (`ritmo_feria.hechas_total`) y el progreso también sale del reloj. Comprobado en partidas completas de feria con 1 y 2 jugadores | `backend/logica/recta_final._hechas` (test: `tests/test_b_recta_feria.py`) |

### Revisado sin cambios

- Tiempos de lectura: los subtítulos ya se reparten con `_calculos.reparto_subtitulos` (mínimo 2,4 s por frase); en las
  capturas ninguna frase quedó cortada ni se solapó.
- Cielo y hora: cada final fija su hora (malo 22:00, bueno 7:30, neutro 17:48) y etapa; correctos en las capturas.
- Audio: el campo `musica` del JSON no lo reproduce nadie (solo `sonido`). No se inventa audio: queda anotado como
  pendiente para quien lleve el audio.
- Viñetas 2D (`cinematica_final.py`): son el respaldo cuando el final animado falla; no se tocaron.

## Archivos

- Nuevo: `frontend/final_animado/final_pulido_calculos.py` (puro: bandera, datos de las correcciones).
- Tocados (solo enganches tras la bandera): `frontend/final_animado/{puesta,camaras,decorado,actores,poses_final,
  escenografia,ciudad}.py`.

## Pruebas

`tests/test_b_final_pulido.py` (local): bandera encendida y apagada, que con la bandera apagada cada puesta es el mismo
objeto de antes, que nadie se toca en ninguna puesta corregida, que los postigos cierran después de que el ciudadano se
retira y abren hacia fuera, hueco a la altura de la cara, pancarta fuera de la cara, fuego en m2, el puño ya no estira el
brazo al frente, elenco sin repetir y existente, y micrófono fuera del eje de la cámara.
