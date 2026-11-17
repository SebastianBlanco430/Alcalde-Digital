# Parte A del rediseño visual de minijuegos: kit de papel + Comparar + Rastrear + Contrarreloj

Este documento es tu PROMPT INICIAL. Eres la instancia de Claude de la Parte A. Hay otra instancia (Parte B) trabajando A LA
VEZ en el mismo directorio sobre otros archivos. Lee también, antes de tocar nada:
`docs/PLAN_MINIJUEGOS_COORDINACION.md` (contrato común, reparto de archivos, sincronización; manda sobre este documento si
hay contradicción) y `docs/PLAN_REDISENO_MINIJUEGOS.md` (plan base acordado con el dueño; la coordinación corrige 16 puntos
de él en su sección 1).

ANTES DE NADA: lee la sección 0 de la coordinación (cambios sin dueño detectados en el árbol). Corre `git status --short`.
Si esos archivos siguen modificados y el dueño no te ha dicho si se descartan o se adoptan, no los toques y pregunta; si se
adoptaron, `contrarreloj_visual.py`, `piezas_contrarreloj.py` y `contrarreloj_piezas_calculos.py` pasan a ser tuyos.

## 1. Contexto (10 líneas)

1. Alcalde Digital es un juego 3D en Python/Ursina (Panda3D), proyecto de aprendizaje; repo `~/Documents/GitHub/Alcalde-Digital`, Python `venv/bin/python`.
2. En las misiones «verificar» se juega uno de 6 minijuegos (2D en `camera.ui`) que enseñan a no creer ni pasar bulos.
3. La lógica de cada uno es pura (`frontend/minijuegos/*_calculos.py`); la vista base dibuja tarjetas (`frontend/minijuegos/<x>.py`, `ui.py`).
4. Encima hay una capa visual por minijuego (`frontend/minijuegos_visual/<x>_visual.py`) con bandera y guardián: si falla, vuelve la base.
5. Problema (auditoría del 2026-11-17): los 5 minijuegos parecen «formularios»: cajas azul-pizarra, texto largo, 40 % vacío, amarillo para todo, sin feedback.
6. Cronología (`cronologia_visual.py`, viñetas de cómic) es la referencia de estilo: objetos con tinta, papel y sombra plana. No se toca.
7. Idea: cada minijuego es un OBJETO físico (hojas, corcho, mapa con teletipo) hecho con un kit de piezas de papel con borde de tinta.
8. Tus minijuegos: Comparar dos versiones (M), Rastrear la fuente (S-M) y Contrarreloj (L). Y el kit de papel que también usa la Parte B.
9. La Parte B hace el marco común (pestaña de título, cinta del rumor, botón «?»), la portada previa, los globos, Chat y Señales.
10. Todo va detrás de banderas nuevas `ALCALDE_<X>_REDISENO` (nacen apagadas): mientras trabajas, el juego sigue igual.

## 2. Objetivo

Que Comparar, Rastrear y Contrarreloj se vean como objetos de papel y tinta (al nivel de cronología), con zona de juego
grande, estados claros por forma + texto + color, sin texto de ayuda permanente, sin cambiar NADA de su lógica, su resultado,
su flujo ni su contrato público; y entregar a tiempo el kit de papel común (S0) para que la Parte B lo use.

## 3. Reglas duras

- No tocar lógica ni flujo: `frontend/minijuegos/*_calculos.py`, `frontend/minijuegos/base.py`, las vistas base
  `frontend/minijuegos/<x>.py`, `ui.py`, `frontend/escenas/escena_minijuego.py`, `backend/**` (incluido
  `backend/logica/minijuegos.py`, `logros_minijuegos.py`, `backend/datos/minijuegos_*.py`).
- No tocar las capas visuales de hoy (`frontend/minijuegos_visual/*_visual.py`, `capa.py`, `trazos.py`, `*_calculos.py`
  existentes), ni `efectos_ui*.py`, `estilo.py`, `componentes.py`, `telefono_marco.py`, `mando*.py`, `tutorial_mision_*.py`,
  `registro_*.py`. Se pueden IMPORTAR y HEREDAR.
- Módulos protegidos del proyecto (ni abrir para editar): `personaje*`, `npc_*`, `modelo_calculos`, `skinning_gpu`,
  `piloto_glb*`, `multitud*`, `peatones*`, `animacion_humana*`, `npc_postura*`, `poses.py`, `traspaso_*`, `npc_reactivo`,
  `rostro_*`, `dialogo_retratos`, `cinematica.py`, `director_cinematica.py`, `guion_cinematicas.py`, `cinematica_final.py`,
  `registro_tutorial.py`, `tutorial_vinetas.json`, `escena_inicio.py`, `fondo_menu.py`, `logo.py`, `transicion.py`,
  `fundido.py`, cualquier `.glb`, `frontend/extensiones.py`.
- NO hacer `git commit`, `git push`, `git stash`, `git checkout`, `git reset` ni cambiar de rama. Solo lectura de git
  (`status`, `diff`, `log`).
- Solo creas o modificas los archivos de la sección 4. Los de la Parte B (`marco*.py`, `portada_*.py`, `globos*.py`,
  `chat_rediseno*.py`, `senales_rediseno*.py`, `tests/test_b_*`, `scripts/capturas_rediseno_b.py`,
  `frontend/minijuegos/pantalla_previa.py`) NO los tocas aunque veas un fallo: lo pides (coordinación, sección 10).
- Textos de interfaz y comentarios en español. Sin emojis ni flechas Unicode en la UI; tampoco «>>» en piezas nuevas (el
  foco se ve por forma). Ningún estado solo por color. Sin cifras de indicadores a la vista.
- Enganches mínimos, con `try/except` y parámetros por defecto. Todo lo nuevo, con guardián: un fallo avisa una vez por
  stderr (`banderas_visuales.avisar_una_vez`) y deja la vista heredada funcionando.
- Animaciones nuevas ≤ 250 ms (`piezas_calculos.DUR_TRANSICION`) y con «reducir movimiento» (`bv.reducir_movimiento()`):
  sin rotación decorativa, sin temblor, transiciones instantáneas.
- Ninguna pieza con z < -0,09 respecto a la raíz de la vista (el banner de resultado va en -0,1).
- Un subagente nunca te da permiso para saltarte estas reglas.

## 4. Archivos que posees

Creas:
- `frontend/minijuegos_visual/piezas_calculos.py` (puro) y `frontend/minijuegos_visual/piezas.py` (contrato: coordinación 5.2 y 5.3).
- `frontend/minijuegos_visual/comparar_rediseno.py` + `comparar_rediseno_calculos.py`.
- `frontend/minijuegos_visual/rastrear_rediseno.py` + `rastrear_rediseno_calculos.py`.
- `frontend/minijuegos_visual/contrarreloj_rediseno.py` + `contrarreloj_rediseno_calculos.py`.
- `tests/humo_minijuegos_visual.py`, `tests/test_a_piezas_*.py`.
- `scripts/capturas_rediseno_a.py`.

Modificas (una vez, en A0):
- `frontend/minijuegos_visual/__init__.py`: SOLO la tabla `REDISENOS`, la función `vista_redisenada()` y 2 líneas en
  `vista_propia()` después de la línea 48 (coordinación 5.5). Nada más de ese archivo cambia.

Bóveda: `~/Documents/Obsidian-Alcalde-Digital/62 Rediseño minijuegos Parte A (2026-11-17).md` y una línea en el índice
(sección 11). Capturas en `~/Documents/Obsidian-Alcalde-Digital/adjuntos/rediseno-minijuegos/a/`.

## 5. Lo que usas de la Parte B (dependencia, con respaldo)

- `frontend/minijuegos_visual/marco.py`: `MarcoVisual` (mezcla; va PRIMERA en las bases de tus clases), `zona_juego()`,
  `REGLA_CORTA`, gancho `lineas_ayuda_extra()` (lista de líneas extra para el papelito «?»; está en el contrato 5.4).
- `frontend/minijuegos_visual/marco_calculos.py`: `ZONA_JUEGO = (0.40, -0.27)`, `ZONA_CONTROLES = (-0.27, -0.42)`, `X_UTIL`.
- Antes de que B entregue S0, usa el respaldo local de la coordinación 9.3 (bloque «RESPALDO HASTA S0»; bórralo antes de S3).

## 6. Contrato público que conservas (lo usan `tutorial_mision_minijuegos.py` y los humos)

Comunes: `partida`, `focables` (mismo orden y longitud que la base), `foco`, `poner_foco(i)`, `tecla(k)`, `avanzar(dt)`,
`terminar(r)`, `terminado`, `resultado`, `es_tutorial`, `TITULO` (texto igual), `AYUDA`. Todo objeto marcable ES
`ui.Tarjeta` (usa `piezas.TarjetaPapel`); todo botón ES `ui.Boton` (usa `piezas.BotonSello`). Clics cableados con lambdas que
buscan el método al llamar. Llamadas siempre por `self.partida.<método>` y `self.terminar(...)` (el tutorial los sustituye en
la instancia: `tutorial_mision_minijuegos.py:158-159,183,216-217`).

- Comparar (`frontend/minijuegos/comparar.py`): `tarjetas` (copia, marcables), `izq` (original), `alternar(i)`,
  `confirmar()`, `sin_diferencias()`, `boton_confirmar`, `boton_igual`, teclas `c` y `n`, `activar_foco()` que alterna si el
  foco está en una tarjeta. `focables = tarjetas + [boton_confirmar, boton_igual]`; al terminar, `focables = []`.
  `al_terminar_propio` pone `encontrada` / `perdida` / `falsa_alarma` / `normal` (`comparar.py:93-106`).
- Rastrear (`rastrear.py`): `elegir(i)`, teclas 1-3, `focables` = 3 notas del salto (con `descartada` y `habilitada = False`
  las ya falladas), `rastro` (lista de nombres), `_pintar_ronda()` se llama en cada salto y DESTRUYE `self.ronda`
  (`rastrear.py:32-35`), `_pintar_origen(y)` al llegar, `estado_txt` / `rastro_txt` (textos de la base).
- Contrarreloj (`contrarreloj.py`): `filas`, `barras`, `rotulos` (la base les pone `enabled` y los repinta EN CADA FRAME en
  `_sincronizar`, líneas 138-157: SUSTITUYE las listas por objetos propios con la misma interfaz, no los escondas),
  `frenar()`, `dejar()`, `boton_frenar`, `boton_pasar` (el tutorial los señala con `f`, `d`, flechas), `foco`, `tecla()`
  sobrescrita (`contrarreloj.py:71-89`), `focables == []`. La partida: `p.cartas[i]["estado"]` (pendiente, frenada,
  liberada, propagada), `p.visible(i)`, `p.propagacion(i)`, `p.t`, `p.duracion`, `p.acierta(i)`.

## 7. Diseño detallado

Medidas en `camera.ui` (alto 1, ancho 1,778). «px» = píxeles de referencia (alto 600): `a_u(px) = px/600`. Zona de juego con
marco: y 0,40 a -0,27 (lo que muestra revisión); zona de controles: y -0,27 a -0,42 (el banner la tapa al terminar);
x -0,83 a 0,83. Paleta y Z: SOLO las de `piezas_calculos.PALETA` y `Z` (coordinación 5.2). Texto: cuerpo ≥ 16 px,
etiquetas ≥ 13 px, nunca encima de corcho, mesa o trama (siempre papel debajo). Bordes de tinta 3 px (2 en chips) hechos
con capas, sombra plana (4, -5) px, rotación decorativa ±2° determinista (`rotacion_decorativa(semilla)`; 0° con reducir).

### 7.1 Kit de papel (A0): `piezas_calculos.py` + `piezas.py`

Implementa EXACTAMENTE la API de la coordinación 5.2 y 5.3 (nombres, parámetros, valores por defecto, `CONTRATO = 1`).
En A0 basta con un dibujo correcto y sencillo; lo puedes pulir después sin cambiar firmas. Detalles:
- `TarjetaPapel(ui.Tarjeta)`: llama a `super().__init__(...)` con los argumentos de `ui.Tarjeta`, esconde `self.borde` y
  `self.fondo` de la base (`enabled = False`), crea sus capas (sombra, tinta, cara de papel, banda de estado, marca, halo de
  foco) y pone `_papel_listo = True`; `_pintar()` sale si no está listo y, si lo está, pinta según `self.estado` y
  `self._foco` y SIEMPRE escribe la etiqueta del estado en `self.etiqueta.text` (de `ui.Tarjeta.ESTADOS` o la propia de
  `fijar_estado(estado, etiqueta)`), en tinta sobre un chip, sin «>>». La caja de golpe (`self.golpe`) tiene el tamaño
  visible. `con_borde=False` sirve para renglones dentro de una hoja (sin tinta propia; el estado se ve igual).
- Estados (forma + texto + color): foco = halo amarillo 5 px por fuera y sombra más larga; marcada = resaltador amarillo
  que barre en 180 ms + chip con la etiqueta; correcta/encontrada = banda verde alfa 0,25 + palomita (`marca_ok`) + etiqueta
  en `verde_tinta`; incorrecta/falsa_alarma/propagada/alterada = banda roja alfa 0,2 + aspa (`marca_mal`) + etiqueta en
  `rojo_tinta`; perdida = aro rojo discontinuo + «TE LA PERDISTE»; descartada = papel al 55 % + tachón + «DESCARTADA».
- `BotonSello(ui.Boton)`: esconde la cara de la base y dibuja un sello rectangular de tinta 3 px, sombra plana, cara
  amarilla (primario) o de papel (secundario); sobrescribe `fijar_foco` para NO anteponer «>>» (`ui.py:246` lo hace) y
  marcar el foco con halo amarillo; `fijar_habilitado(False)` = cara `papel_viejo`, texto `tenue_papel`, sin sombra.
  Iconos dibujados con quads: `mano` (palma: rect + 4 dedos), `flecha` (cuerpo + punta con `poligono`), `lupa`, `visto`.
- `Sello`: texto en caja con borde doble (tinta del tono), rotado, que cae con
  `efectos_ui_calculos.caida_sello(t, dur=0.25, reducir=...)`.
- Hilos: sigue usando `trazos.Linea` (importar) con los puntos de `pistas_visuales_calculos.catenaria`.

### 7.2 Comparar dos versiones (`CompararRediseno(MarcoVisual, CapaVisual, MinijuegoComparar)`)

Objeto: dos DOCUMENTOS sobre la mesa, lado a lado.
- Hojas: ancho 0,78 cada una, centros x = -0,44 (original) y +0,44 (copia), hueco de 0,10 entre ellas; arriba y 0,39; alto
  = lo que pidan los renglones, sin bajar de y -0,25. Original: `papel` crema, rotación -0,8°. Copia: `papel_viejo`,
  rotación +0,8°, esquina doblada arriba a la derecha (lado 0,04) y una mancha de café (círculo marrón (120, 80, 40) alfa
  0,22, radio 0,035) abajo a la izquierda FUERA de los renglones.
- Cabecera de cada hoja: chip «ORIGINAL» / «COPIA QUE CIRCULA» (13 px, negrita) y debajo la fuente (`caso["original"]` /
  `caso["copia"]`) a 14 px en `tenue_papel`, recortada a una línea. Sello «ORIGINAL» pequeño (16 px, -8°) en la esquina de
  la hoja original (D2, constante `SELLO_ORIGINAL = True`).
- Renglones: `TarjetaPapel(..., con_borde=False)` del ancho de la hoja menos 0,04. Microetiqueta (`l["etiqueta"]`) arriba a
  13 px negrita `tenue_papel` (usa el `titulo` de la tarjeta), valor debajo a 17 px; si no caben, 16 px (mínimo). Separador
  fino de tinta alfa 0,25 entre renglones. `izq` = renglones del original (sin golpe: `golpe.collider = None`), `tarjetas` =
  renglones de la copia, en el mismo orden que la base.
- Pasarela: 6 puntos (diámetro 0,010) en el hueco entre hojas a la altura del renglón con foco, en cian alfa 1; los demás
  renglones no la tienen. Sin texto encima.
- Estados de la copia: normal; foco (halo amarillo + pasarela); marcado (resaltador que barre en 180 ms + chip
  «SOSPECHOSA», que pone la base); cierre: `encontrada` (banda verde + palomita), `falsa_alarma` (banda roja + tachón sobre el
  texto + aspa), `perdida` (aro rojo discontinuo alrededor del renglón), resto sin marca. Error/acierto inmediatos: no hay
  (la base no los da hasta confirmar).
- Botones: `BotonSello` «Confirmar marcas» (primario, icono `visto`) y «No veo diferencias» (secundario) bajo la hoja de la
  copia, en la zona de controles: y -0,335, x 0,24 y 0,64, ancho 0,36, alto 0,07, 18 px. Reemplazan a `boton_confirmar` y
  `boton_igual` (destruir los de la base tras el cambio).
- Cierre: sello común VERIFICADO/BULO sobre la copia: `posicion_sello() = (0.44, 0.30)`; estrellas `(0.06, 0.36)` (ajustar
  con la captura para no tapar revisión). Opcional: la «palabra que cambió» (`pistas_visuales_calculos.texto_salto`, no
  usa flechas) en un papelito de 0,6 × 0,08 sobre el hueco entre hojas durante 3 s, z `sello`.
- Se elimina: el encabezado largo de la base (lo esconde el marco), el pie de teclas, la mesa de luz y el texto fantasma de
  `comparar_visual.py` (no se heredan: clase hermana).
- `REGLA_CORTA = "Marca solo las líneas de la copia que no dicen lo mismo que el original."`

### 7.3 Rastrear la fuente (`RastrearRediseno(MarcoVisual, CapaVisual, MinijuegoRastrear)`)

Objeto: un TABLERO DE CORCHO donde el hilo es la estructura.
- Corcho: rectángulo `corcho` de x -0,83 a 0,83, y 0,39 a -0,26, borde de tinta 3 px, 30 motas `corcho_oscuro`
  deterministas (semilla fija). Nunca texto directo sobre el corcho.
- Franja superior (cadena, centro y 0,29, alto 0,16): crece de DERECHA a IZQUIERDA (hacia atrás en el tiempo). A la derecha,
  polaroid «TÚ» (0,11 × 0,13, papel blanco, foto = círculo con inicial «T» y color `azul_secundario`, pie «Tú» 13 px). Cada
  acierto añade una nota clavada (papel 0,17 × 0,075, chincheta, quién 13 px negrita + hora 13 px) a la izquierda de la
  anterior, unida con hilo rojo (`trazos.Linea` grosor 3, catenaria que llega floja y se tensa en 0,25 s:
  `pistas_visuales_calculos.caida_hilo(t, dur=0.25)`). Al llegar al origen, polaroid de la FUENTE a la izquierda del todo
  con sello «FUENTE» (rojo_tinta, 18 px). Posiciones: `rastrear_rediseno_calculos.posiciones_cadena(n, x_der=0.70,
  x_izq=-0.72)` (paso fijo 0,21; si no cabe, se comprime).
- Ovillos («rodeos»): `MAX_ERRORES - 1` ovillos (hoy 2) arriba a la izquierda del corcho (x -0,74 y 0,355; diámetro 0,04):
  círculo rojo con 3 arcos de hilo. Al errar, uno se apaga (gris + aspa) y su chip cambia a «gastado». Chip «Rodeos» 13 px
  al lado. Así desaparece el texto «rodeos permitidos: N».
- Pregunta del salto: tira de papel de 1,2 × 0,05 en y 0,175 con «Paso n de N: pregunta» a 17 px negrita (texto de la base).
  Debajo, la línea de estado de la base («Bien: ese mensaje es anterior...», «Ese mensaje es posterior...») en otra tira
  de 15→16 px, solo cuando hay mensaje.
- Franja inferior: las 3 notas candidatas `TarjetaPapel` de ancho 0,52, separadas 0,05, desde y 0,135 hasta como mucho
  -0,25 (alto = el máximo que pidan, mínimo 0,26). Cabecera (`titulo`) = «quién · hora» 14 px negrita; cuerpo 17 px; si el
  texto dice que es un reenvío (`rastrear_rediseno_calculos.es_reenvio(texto)`, que busca «reenviad» sin distinguir
  mayúsculas; se lee del TEXTO, nunca de `correcta`), esquina doblada y chip «REENVIADO» abajo a la derecha con dos
  chevrones dibujados. Chincheta roja arriba al centro; rotación decorativa por nota.
- Estados: foco = la nota sube 0,01 (0 con reducir) y halo amarillo; error = `self._fx.error(nota)` (temblor de la capa),
  el hilo hace un nudo junto a la última nota de la cadena (`pistas_visuales_calculos.enredo`) y la nota queda
  `descartada` (papel apagado + tachón + etiqueta, inerte: lo pone la base); acierto = partículas verdes de la capa sobre
  la nota, la nota «vuela» a la cadena (interpolación 0,25 s; instantánea con reducir) y el hilo se tensa; cierre = una luz
  cian (círculo 0,014) recorre la cadena de derecha a izquierda en 1,0 s (con reducir: la cadena entera en cian fijo) y la
  ficha del origen (`TarjetaPapel` estado `correcta` «LLEGASTE AL ORIGEN», texto `origen["detalle"]`) ocupa la franja
  inferior; si se pierde el rastro, los ovillos quedan gastados y la cadena en gris.
- Patrón de sustitución: `_pintar_ronda()` = `super()._pintar_ronda()` y después sustituye `self.focables` por notas
  nuevas en el MISMO orden, copiando `estado`/`habilitada` de las originales, y destruye las originales; `_pintar_origen(y)`
  igual con la ficha. `rastro_txt` y la `PISTA` de la base se esconden (la regla está en el «?» y en la forma).
- `REGLA_CORTA = "El original es el mensaje más antiguo y que no dice «reenviado»."`
- `posicion_sello() = (-0.30, 0.05)` sobre la zona de notas tras el cierre (ajustar con captura).

### 7.4 Contrarreloj (`ContrarrelojRediseno(MarcoVisual, ContrarrelojVisual)`)

Hereda de la vista visual de HOY para conservar música tensa, tic-tac y el cálculo de contagio, y sobrescribe su dibujo:
`_construir_mapa`, `_pintar_mapa`, `_radio_visible`, `_mostrar_contagio`, `_quitar_mapa` (el guardián de
`ContrarrelojVisual.construir`, `contrarreloj_visual.py:64-75`, ya envuelve `_construir_mapa`; tu `_quitar_mapa` debe además
devolver las listas `filas`/`barras`/`rotulos` y los botones originales si aún existen).
- Mesa-mapa (60 % del ancho): x -0,83 a 0,17 (ancho 1,00), y 0,39 a -0,26. `papel_viejo` con borde de tinta, calles (quads
  de tinta alfa 0,3, 0,008 de grosor), y las 7 zonas de `mapa_barrio_calculos.ZONAS` dibujadas como casitas (cuerpo 0,05 ×
  0,04 + tejado triangular con `poligono`, en `COLORES_LUGAR`-like tenues) con su nombre en chip de papel a 13 px (D4: nombres
  en portugués; glosa en el «?» vía `lineas_ayuda_extra()` con `GLOSA_LUGARES`). Coordenadas: `x = -0.33 + zx * 1.00`,
  `y = 0.065 + zy * 0.65` (función pura `a_mapa(zx, zy)`).
- Contagio: cada noticia visible es una MANCHA (círculo) en `mapa_barrio_calculos.posicion_foco(i)` cuyo radio sigue
  `radio_objetivo(estado, propagacion, congelada)` acotado al mapa; pendiente = amarillo alfa 0,35-0,6 (rojo si la
  difusión pasa de 0,72), frenada = azul_tinta alfa 0,5 + sello «FRENADA» (Sello, 14 px), liberada = verde alfa 0,3,
  propagada = rojo alfa 0,35. Encima de cada mancha, chip numerado (1..n) igual al de su tarjeta: el número, no el color,
  dice cuál es cuál.
- Teletipo (derecha): x 0,22 a 0,83 (ancho 0,61), y 0,33 a -0,26. Cabecera: cronómetro en cápsula (0,30 × 0,05, centro
  x 0,52 y 0,365): cápsula de papel con borde de tinta y relleno que se vacía (`1 - p.t / p.duracion`), tono
  `piezas_calculos.tono_reloj(fracción)` (cian > 0,5, amarillo > 0,25, rojo el último 25 %), con «Tiempo» 13 px; sin cifras.
- Tarjetas del teletipo: `TarjetaPapel` de 0,58 × alto de fila (como la base: `min(0.108, ...)`, recalculado para la zona
  y 0,33..-0,26), cuerpo a 16 px (sube desde 15), chip con su número a la izquierda. Debajo del texto, la «pista de
  difusión»: línea discontinua de tinta alfa 0,4 que acaba en una casita pequeña («llegó al barrio»); un chip con el número
  avanza por ella según `propagacion(i)`. ES el sustituto de `barras[i]`: objeto `PistaDifusion(Entity)` con
  `.fijar(f, tono=None)` y `enabled`. `rotulos[i]` = `Text` de 13 px dentro de la tarjeta (la base escribe «Recién llegó»,
  «Se está difundiendo», «¡Casi viral!»).
  Nota: el plan base pedía tarjetas que «bajan» hacia una línea. Se cambia por la pista dentro de cada tarjeta para que las
  tarjetas no se pisen cuando hay varias a la vez (decisión de diseño de la Parte A; revisable con la captura).
- Foco: la tarjeta con foco lleva halo amarillo y se une a su mancha con una línea cian discontinua
  (`piezas.discontinua`), z `decor`.
- Pulsadores: `BotonSello` «FRENAR (F)» (primario, icono `mano`) y «DEJAR PASAR (D)» (secundario, icono `flecha`) en la
  zona de controles: y -0,34, x 0,37 y 0,68, ancho 0,28, alto 0,09, 20 px. Sustituyen a `boton_frenar`/`boton_pasar`.
- Cierre: la base pone `correcta`/`incorrecta` con «BIEN: era cierta», «MAL: era falsa»... (`contrarreloj.py:159-169`); las
  tarjetas las enseñan con banda + palomita/aspa + etiqueta. Sello grande sobre el mapa: «BARRIO A SALVO» (verde_tinta) o
  «BARRIO CONTAGIADO» (rojo_tinta) según `mapa_barrio_calculos.zonas_contagiadas(...)`; las zonas contagiadas con mancha
  roja y chip «!» junto al nombre (texto, no solo color). Los pulsadores se esconden (como hoy).
- `REGLA_CORTA = "Frena lo que creas falso y deja pasar lo cierto antes de que llegue a todo el barrio."`
- Rendimiento: cuenta entidades antes/después (`len(scene.entities)`) y anótalo; si el mapa pasa de ~250 entidades nuevas,
  agrupa casitas y calles en una sola malla.

### 7.5 Pantalla de cada vista: lo que desaparece o pasa al «?»

Desaparecen de la pantalla: el título grande, la línea «Rumor a verificar» larga (pasa a la cinta del marco), el párrafo de
intro/regla (`PISTA` de Rastrear, `nota` de Contrarreloj, intro de Comparar) y el pie de teclas. Pasan al papelito «?»: la
`REGLA_CORTA`, las teclas (las saca el marco de `AYUDA`) y, en Contrarreloj, la glosa de lugares.

## 8. Banderas y guardián por vista

| Vista | Clase | Constante (nace) | Variable | Si falla el montaje |
|---|---|---|---|---|
| Comparar | `CompararRediseno` | `COMPARAR_REDISENO = False` | `ALCALDE_COMPARAR_REDISENO` | Se borra lo nuevo y queda la vista base con la capa común (patrón de sustitución, coordinación 5.7) |
| Rastrear | `RastrearRediseno` | `RASTREAR_REDISENO = False` | `ALCALDE_RASTREAR_REDISENO` | Igual; en cada salto, si falla, esa ronda queda con las tarjetas de la base |
| Contrarreloj | `ContrarrelojRediseno` | `CONTRARRELOJ_REDISENO = False` | `ALCALDE_CONTRARRELOJ_REDISENO` | `_quitar_mapa` deja la vista de la base (listas y botones originales) |

Guardián: `_rediseno_roto` por instancia; claves `rediseno_<x>` (montaje) y `rediseno_<x>_animar` (bucle). Fallos en
`avanzar_visual_propio` nunca lanzan: avisan y paran solo lo animado. Si el error ocurre DESPUÉS de cambiar las listas, se
deja lo nuevo quieto (no se intenta volver atrás a mitad de partida) y se avisa.

## 9. Orden de trabajo (cada paso con su criterio de «hecho»)

A0. Paquete 0 de A (primero de todo; nada aquí depende de B).
  1. Captura de línea base de tus 3 minijuegos (estados de coordinación 7.4) con las capas de HOY: `scripts/capturas_rediseno_a.py`.
     Hecho: imágenes guardadas en `adjuntos/rediseno-minijuegos/a/base_*.png` y revisadas.
  2. `piezas_calculos.py` + `tests/test_a_piezas_calculos.py`. Hecho: pruebas verdes; el módulo no importa ursina.
  3. `piezas.py` + `tests/test_a_piezas_ursina.py` (offscreen). Hecho: todas las funciones y clases de 5.3 existen con su
     firma; `TarjetaPapel` es `ui.Tarjeta` y acepta los 14 estados de `ui.Tarjeta.ESTADOS`; ningún texto contiene «>>».
  4. Enganche 5.5 en `__init__.py`. Pasa `preservador` sobre ese diff. Hecho: con las 5 constantes en False (y sin módulos
     de rediseño todavía) `clase_visual(id, clase_de(id))` devuelve las mismas clases que hoy (prueba en
     `tests/test_a_piezas_enganche.py`, con un módulo falso para comprobar que una bandera encendida devuelve el rediseño y
     que un módulo roto devuelve la vista de hoy y avisa una vez).
  5. `tests/humo_minijuegos_visual.py`: lee `tests/humo_minijuegos_mundo.py`, sustituye la línea
     `tipo = type(v).__name__` por la búsqueda de la clase base por MRO (coordinación 7.4), fija por defecto
     `ALCALDE_MINIJUEGOS_INTRO=0` y `ALCALDE_TUTORIAL_MISION=0`, ejecuta el resultado con `exec` y al final imprime
     `HUMO MINIJUEGOS VISUAL OK 47 misiones` + el conjunto de clases de vista usadas. Comprueba con `assert` que la
     sustitución se hizo (si el texto del humo cambia, falla claro). Añade `tests/test_a_piezas_humo_visual.py` que lo corre
     como subproceso (timeout 600). Hecho: verde HOY con las capas actuales (clases `*Visual`).
  6. Escribe «S0 entregado HH:MM» en tu nota de la bóveda. Lee la nota de B (63) para ver si B ya entregó.
A1. Comparar. Pasos: cálculos puros (maquetación de hojas y renglones, pasarela) con pruebas; clase; prueba offscreen con
  los 9 casos de comparar (`backend/datos/minijuegos_casos.py`): todos caben a ≥ 16 px; jugar bien y mal por el contrato;
  forzar fallo de montaje. Humo visual con `ALCALDE_COMPARAR_REDISENO=1`. Capturas (todos los estados + reducir movimiento)
  revisadas. `preservador` (si tocaste algo existente), `security-auditor`, `code-reviewer`. Hecho = S1.
A2. Rastrear. Igual, con los 5 casos de rastrear; error y acierto por el contrato (`elegir`), pérdida del rastro (3
  errores), llegada al origen. Hecho cuando todo lo anterior está verde.
A3. Contrarreloj. Igual, con los 5 casos; probar frenar, dejar pasar, dejar que se propague sola, cronómetro en los tres
  tonos, cierre a salvo y contagiado; medir entidades. Hecho = S2.
A4. Pasada transversal: `posicion_sello`/`posicion_estrellas` revisadas en captura; contraste (todas las parejas
  texto/fondo usadas con `piezas_calculos.contraste_ok`); reducir movimiento; teclado (Tab, flechas, 1-3, c, n, f, d, h,
  Esc) y mando (D-pad, A, X) en ventana real; `auditor-diseno-generico` y `accessibility-tester` sobre tus capturas.
  Pon `COMPARAR_REDISENO`, `RASTREAR_REDISENO`, `CONTRARRELOJ_REDISENO = True`. Suite completa contra la línea base +
  los humos de la coordinación 8.2 (base, visual y tutorial visual). `security-auditor`, `terminos-legales` (textos nuevos visibles), `code-reviewer`.
  Hecho = S3 (anotado en la bóveda).

## 10. Pruebas

Escribes (todas en `tests/`, prefijo `test_a_piezas_`):
- `test_a_piezas_calculos.py`: `rotacion_decorativa` determinista, en ±2 y 0 con reducir; `avance` 0..1 y 1 con reducir;
  `tono_reloj` en los umbrales 0,5 y 0,25; `recortar`; `esquina_doblada`; `discontinua` y `aro_discontinuo` (número y
  longitud de segmentos); `arco`; `triangulos_abanico`; `contraste_ok` verdadero para tinta, rojo_tinta, verde_tinta,
  azul_tinta y tenue_papel sobre papel y papel_viejo, y FALSO para cian y amarillo sobre papel (regla de color).
- `test_a_piezas_comparar.py`, `test_a_piezas_rastrear.py`, `test_a_piezas_contrarreloj.py`: cálculos puros de cada vista
  (posiciones dentro de la zona, sin solapes, `es_reenvio` sobre los textos reales de los 5 casos, `a_mapa`, etc.).
- `test_a_piezas_ursina.py` y `test_a_piezas_enganche.py`: offscreen (coordinación 7.2).
- `test_a_piezas_humo_visual.py`: subproceso del humo visual.

Ejecutas (con el cerrojo de la coordinación 8.2):
- Tus pruebas: `venv/bin/python -m pytest -q -p no:cacheprovider tests/test_a_piezas_*.py`.
- Humo base (vista base idéntica), humo visual (con tus banderas a 1) y el humo del tutorial (`tests/humo_tutorial_mision.py`, o
  el envoltorio de la Parte B si los cambios de la sección 0 se adoptaron: coordinación C16).
- Suite completa contra la línea base del anexo de la coordinación (por ID).

## 11. Capturas, subagentes y bóveda

Capturas: `scripts/capturas_rediseno_a.py` según coordinación 7.4; ids `comparar`, `rastrear`, `contrarreloj`; revisar
cada PNG con la herramienta de leer imágenes; comparar con las de línea base del paso A0.1.

Subagentes (los pides tú; ninguno decide por ti):
- `preservador`: tras CUALQUIER cambio a código existente (aquí: `__init__.py`) y antes de dar por hecho cada paso.
- `security-auditor` y después `code-reviewer` (el revisor exige el APROBADO del auditor sobre el mismo cambio) al cerrar
  A1, A2, A3 y A4.
- `terminos-legales`: en A4, por los textos nuevos que ve el jugador.
- `auditor-diseno-generico`: en A0.1 sobre la línea base y en A4 sobre el resultado.
- `accessibility-tester`: en A4 (contraste, estados por forma + texto, teclado y mando).

Bóveda (`~/Documents/Obsidian-Alcalde-Digital`), con CADA paso:
- Nota `62 Rediseño minijuegos Parte A (2026-11-17).md` con: estado, entregas (S0..S3 con hora), archivos creados y
  modificados, decisiones, resultados de pruebas (pasan / fallan contra línea base), capturas incrustadas
  (`![[adjuntos/rediseno-minijuegos/a/<archivo>.png]]`), «Peticiones a la otra parte», «Respuestas», pendientes.
- En `00 Índice Alcalde Digital.md`: añade, con Edit (nunca reescribiendo el archivo), justo después de la última línea
  `- [[6x ...]]` de la lista «Mapa», una línea para la nota 61 si no está y otra para la 62. Si el Edit falla porque la
  Parte B acaba de cambiar el índice, vuelve a leerlo y repite.

## 12. Riesgos propios

- `TarjetaPapel` hereda el `__init__` de `ui.Tarjeta`, que llama a `_pintar` antes de que existan tus capas (5.3).
- `ui.Tarjeta.alto_necesario` y `ui.lineas_de` miden con la fuente cargada: cálculo de alturas en la parte Ursina o con la
  medida inyectada como función en los cálculos puros (para poder probarlos con una medida falsa).
- Contrarreloj: la base reactiva `enabled` cada frame (C11); el tutorial pone tiempos fijos a las cartas
  (`tutorial_mision_minijuegos.py:128-134`) y sustituye `partida.frenar`/`dejar_pasar`: tus botones llaman a
  `self.frenar()`/`self.dejar()`, nunca a la partida directamente.
- El sello y las estrellas de la capa común no deben tapar texto de revisión: muévelos con `posicion_sello()` /
  `posicion_estrellas()` tras ver la captura.
