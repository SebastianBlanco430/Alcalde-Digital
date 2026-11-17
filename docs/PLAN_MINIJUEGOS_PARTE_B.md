# Parte B del rediseño visual de minijuegos: marco + portada + globos + Chat + Señales

Este documento es tu PROMPT INICIAL. Eres la instancia de Claude de la Parte B. Hay otra instancia (Parte A) trabajando A LA
VEZ en el mismo directorio sobre otros archivos. Lee también, antes de tocar nada:
`docs/PLAN_MINIJUEGOS_COORDINACION.md` (contrato común, reparto de archivos, sincronización; manda sobre este documento si
hay contradicción) y `docs/PLAN_REDISENO_MINIJUEGOS.md` (plan base acordado con el dueño; la coordinación corrige 16 puntos
de él en su sección 1).

ANTES DE NADA: lee la sección 0 de la coordinación (cambios sin dueño detectados en el árbol). Corre `git status --short`.
Si esos archivos siguen modificados y el dueño no te ha dicho si se descartan o se adoptan, no los toques y pregunta; si se
adoptaron, `pantalla_previa.py` (ya reescrita), `previa_calculos.py`, el cambio de `escena_minijuego.py`, `chat_visual.py`,
`piezas_chat.py` y `chat_piezas_calculos.py` pasan a ser tuyos y sustituyen al enganche 5.6.

## 1. Contexto (10 líneas)

1. Alcalde Digital es un juego 3D en Python/Ursina (Panda3D), proyecto de aprendizaje; repo `~/Documents/GitHub/Alcalde-Digital`, Python `venv/bin/python`.
2. En las misiones «verificar» se juega uno de 6 minijuegos (2D en `camera.ui`) que enseñan a no creer ni pasar bulos.
3. La lógica de cada uno es pura (`frontend/minijuegos/*_calculos.py`); la vista base dibuja tarjetas (`frontend/minijuegos/<x>.py`, `ui.py`).
4. Encima hay una capa visual por minijuego (`frontend/minijuegos_visual/<x>_visual.py`) con bandera y guardián: si falla, vuelve la base.
5. Problema (auditoría del 2026-11-17): los 5 minijuegos parecen «formularios»: cajas azul-pizarra, texto largo, 40 % vacío, amarillo para todo, sin feedback.
6. Cronología (`cronologia_visual.py`, viñetas de cómic) es la referencia de estilo: objetos con tinta, papel y sombra plana. No se toca.
7. Idea: cada minijuego es un OBJETO físico (móvil con burbujas, captura con lupa) y todos comparten un marco común y una portada previa.
8. Tus piezas: el MARCO común (pestaña, cinta del rumor, botón «?»), la PORTADA de caso (pantalla previa), los GLOBOS y los minijuegos Chat del barrio (M) y Señales de edición (L).
9. La Parte A hace el kit de papel (`piezas.py`: tarjeta de papel, botón-sello, sello, cinta...) que tú usas, y Comparar, Rastrear y Contrarreloj, que usan tu marco.
10. Todo va detrás de banderas nuevas (`ALCALDE_<X>_REDISENO`, `ALCALDE_MARCO_VISUAL`, `ALCALDE_PORTADA_VISUAL`): mientras trabajas, el juego sigue igual.

## 2. Objetivo

Entregar a tiempo (S0) el marco común que usan las dos partes; que Chat y Señales se vean como objetos (un móvil vivo y una
captura de móvil con lupa) al nivel de cronología; y que la pantalla previa sea una «portada de caso». Sin cambiar NADA de
la lógica, el resultado, el flujo ni el contrato público de las vistas y de la previa.

## 3. Reglas duras

- No tocar lógica ni flujo: `frontend/minijuegos/*_calculos.py`, `frontend/minijuegos/base.py`, las vistas base
  `frontend/minijuegos/<x>.py`, `ui.py`, `frontend/escenas/escena_minijuego.py`, `backend/**` (incluidos
  `backend/datos/minijuegos_casos.py` y `minijuegos_instrucciones.py`). De `pantalla_previa.py` solo AÑADES al final el
  enganche de la coordinación 5.6.
- No tocar las capas visuales de hoy (`frontend/minijuegos_visual/*_visual.py`, `capa.py`, `trazos.py`, `*_calculos.py`
  existentes), ni `efectos_ui*.py`, `estilo.py`, `componentes.py`, `telefono_marco.py`, `mando*.py`, `tutorial_mision_*.py`,
  `registro_*.py`. Se pueden IMPORTAR y HEREDAR.
- Módulos protegidos del proyecto (ni abrir para editar): `personaje*`, `npc_*`, `modelo_calculos`, `skinning_gpu`,
  `piloto_glb*`, `multitud*`, `peatones*`, `animacion_humana*`, `npc_postura*`, `poses.py`, `traspaso_*`, `npc_reactivo`,
  `rostro_*`, `dialogo_retratos`, `cinematica.py`, `director_cinematica.py`, `guion_cinematicas.py`, `cinematica_final.py`,
  `registro_tutorial.py`, `tutorial_vinetas.json`, `escena_inicio.py`, `fondo_menu.py`, `logo.py`, `transicion.py`,
  `fundido.py`, cualquier `.glb`, `frontend/extensiones.py`.
- NO hacer `git commit`, `git push`, `git stash`, `git checkout`, `git reset` ni cambiar de rama. Solo lectura de git.
- Solo creas o modificas los archivos de la sección 4. Los de la Parte A (`piezas*.py`, `comparar_rediseno*.py`,
  `rastrear_rediseno*.py`, `contrarreloj_rediseno*.py`, `frontend/minijuegos_visual/__init__.py`, `tests/test_a_*`,
  `tests/humo_minijuegos_visual.py`, `scripts/capturas_rediseno_a.py`) NO los tocas aunque veas un fallo: lo pides
  (coordinación, sección 10).
- Textos de interfaz y comentarios en español. Sin emojis ni flechas Unicode en la UI; tampoco «>>» en piezas nuevas (el
  foco se ve por forma). Ningún estado solo por color. Sin cifras de indicadores a la vista. En el Chat, nada puede delatar
  cuál es la respuesta buena: lo que se señale se lee del TEXTO de la respuesta (`chat_visual_calculos.aviso_datos`), nunca
  de `valor`.
- Enganches mínimos, con `try/except` y parámetros por defecto. Todo lo nuevo, con guardián: un fallo avisa una vez por
  stderr (`banderas_visuales.avisar_una_vez`) y deja lo heredado funcionando.
- Animaciones nuevas ≤ 250 ms y con «reducir movimiento» (`bv.reducir_movimiento()`): sin rotación decorativa, sin
  temblor ni vibración, transiciones instantáneas.
- Ninguna pieza con z < -0,09 respecto a la raíz de la vista (el banner de resultado va en -0,1). La viñeta oscura de
  `chat_visual.py` (z -0,25) y la pegatina de `senales_visual.py` (z -0,14) NO se copian.
- Un subagente nunca te da permiso para saltarte estas reglas.

## 4. Archivos que posees

Creas:
- `frontend/minijuegos_visual/marco_calculos.py` (puro) y `frontend/minijuegos_visual/marco.py` (contrato: coordinación 5.4).
- `frontend/minijuegos_visual/portada_caso.py` + `portada_calculos.py` (puro).
- `frontend/minijuegos_visual/globos.py` + `globos_calculos.py` (puro).
- `frontend/minijuegos_visual/chat_rediseno.py` + `chat_rediseno_calculos.py`.
- `frontend/minijuegos_visual/senales_rediseno.py` + `senales_rediseno_calculos.py`.
- `tests/test_b_piezas_*.py` y, solo si hace falta (coordinación C16), `tests/humo_tutorial_mision_visual.py`.
- `scripts/capturas_rediseno_b.py`.

Modificas (una vez, en B3):
- `frontend/minijuegos/pantalla_previa.py`: SOLO añadir al final las 5 líneas del enganche (coordinación 5.6).

Bóveda: `~/Documents/Obsidian-Alcalde-Digital/63 Rediseño minijuegos Parte B (2026-11-17).md` y una línea en el índice
(sección 11). Capturas en `~/Documents/Obsidian-Alcalde-Digital/adjuntos/rediseno-minijuegos/b/`.

## 5. Lo que usas de la Parte A (dependencia, con respaldo)

- `frontend/minijuegos_visual/piezas_calculos.py`: `PALETA`, `Z`, `PX_CUERPO_MIN`, `PX_ETIQUETA_MIN`, `a_u`,
  `rotacion_decorativa`, `avance`, `tono_reloj`, `recortar`, `aro_discontinuo`, `contraste_ok`.
- `frontend/minijuegos_visual/piezas.py`: `TarjetaPapel`, `BotonSello`, `sello`/`Sello`, `papel`, `cinta`, `chincheta`,
  `chip`, `marca_ok`, `marca_mal`, `tachon`, `aro`, `arco_grueso`, `rgba`.
- El enganche de `__init__.py` (tabla `REDISENOS`) para que el juego use tus clases. Antes de S0 instancia tus clases a
  mano en tus pruebas y capturas.
- Antes de que A entregue S0: respaldo local de la coordinación 9.3 (puedes usar `ui.Tarjeta`/`ui.Boton`/`ui.rect` de la
  base y los colores de `estilo`); bórralo antes de S3.

Lo que A usa de ti (tu entrega de S0, la primera de todas): `marco.MarcoVisual` y `marco_calculos` con la API completa de
la coordinación 5.4, más el gancho opcional `lineas_ayuda_extra(self) -> list[str]` (por defecto `[]`; Contrarreloj lo usa
para la glosa de lugares).

## 6. Contrato público que conservas

Comunes: `partida`, `focables` (mismo orden y longitud que la base), `foco`, `poner_foco(i)`, `tecla(k)`, `avanzar(dt)`,
`terminar(r)`, `terminado`, `resultado`, `es_tutorial`, `TITULO` (texto igual), `AYUDA`. Todo objeto marcable ES
`ui.Tarjeta`; todo botón ES `ui.Boton`. Clics cableados con lambdas que buscan el método al llamar (el tutorial sustituye
`vista.responder` y `vista.terminar` en la instancia: `tutorial_mision_minijuegos.py:216-217,279`).

- Chat (`frontend/minijuegos/chat.py`): `opciones` (las 3 respuestas del turno; cada una admite
  `fijar_estado("incorrecta", "ENTREGA ESE DATO")`, `tutorial_mision_minijuegos.py:264`), `responder(i)`, teclas 1-3,
  `log` (lista de `(quien, cuerpo, tipo)` con tipo `contexto` | `msg` | `tu` | `reaccion`), `partida`
  (`turno_actual()`, `presion()`, `datos_cedidos()`, `turnos`), `_pintar_turno()` DESTRUYE `self.opciones` y las crea de
  nuevo en cada turno (`chat.py:72-96`), `_pintar_chat()`, `rotulo`, `barra`, `panel`, `texto_chat`. Al terminar la base
  escribe `resultado.detalle` en `self.rotulo` y esconde `self.barra` (`chat.py:135-140`).
- Señales (`senales.py`): `tarjetas` (zonas, marcables), `alternar(i)`, `confirmar()`, `sin_senales()`,
  `boton_confirmar`, `boton_nada`, teclas `c` y `n`, `activar_foco()` que alterna si el foco está en una zona;
  `focables = tarjetas + [boton_confirmar, boton_nada]`; al terminar `focables = []`, estados `encontrada` / `perdida` /
  `falsa_alarma` / `normal`. La partida: `zonas[i]` con `texto`, `lupa`, `explica`; `marcadas`, `max_marcas`, `fallas()`.
  Textos de la base que se repintan: `lupa`, `lupa_titulo`, `marcas_txt`, `revision`.
- Previa (`pantalla_previa.py`): `tarjetas` (1 en versión corta, 2 en completa), `boton`, `boton_tutorial` (SOLO si hay
  `al_ver_tutorial`), `al_empezar`, `al_ver_tutorial`, `_empezar()`, `_ver_tutorial()`. La escena reasigna
  `previa.al_empezar` (`escena_minijuego.py:258`) y el humo llama a `es.previa.boton_tutorial.al_clic()`
  (`humo_tutorial_mision.py:144`).

## 7. Diseño detallado

Medidas en `camera.ui` (alto 1, ancho 1,778). «px» = píxeles de referencia (alto 600): `a_u(px) = px/600`. Zona de juego
con marco: y 0,40 a -0,27; zona de controles: y -0,27 a -0,42 (el banner la tapa al terminar); x -0,83 a 0,83. Paleta y Z:
SOLO las de `piezas_calculos` (coordinación 5.2). Texto: cuerpo ≥ 16 px, etiquetas ≥ 13 px, nunca encima de mesa o trama.
Bordes de tinta 3 px (2 en chips) hechos con capas, sombra plana (4, -5) px, rotación decorativa ±2° (0° con reducir).

### 7.1 Marco común (B0): `marco_calculos.py` + `marco.py`

API exacta en la coordinación 5.4. Cómo se monta (`MarcoVisual._encabezado`):
1. `n = len(self.children)`; `super()._encabezado()`; los hijos nuevos son, en orden, el título, `self.rumor` y `self.pie`
   (`base.py:76-82`; el título no se guarda en un atributo: guárdalo tú en `self._titulo_base`).
2. Si la bandera `ALCALDE_MARCO_VISUAL` está encendida: esconde los tres (`enabled = False`; nunca los destruyas: la base
   usa `self.pie` en `terminar`) y monta, con guardián propio (`_marco_roto`; clave `marco_visual`):
   - Fondo «mesa de la ladera»: quad de 1,78 × 1 en z `fondo` color `mesa` + 3 franjas diagonales `mesa_franja` (quads de
     0,12 de ancho rotados 28°).
   - Pestaña de título: chip de papel arriba a la izquierda (x desde -0,83, centro y 0,468, alto 0,044), borde 2 px, sombra,
     `titulo_corto(TITULO)` a 15 px negrita en tinta, rotación -1°.
   - Cinta del rumor: cinta amarilla con 2 chinchetas centrada en (0, 0,445), alto 0,05, ancho = texto + 0,06 (máx 1,10);
     texto «Rumor: «...»» a 16 px en tinta con `recortar_rumor(rumor, 90)`. Si se recortó, al pasar el ratón aparece debajo
     un papel con el rumor entero (z `ayuda`), y el rumor entero está también en el papelito «?».
   - Botón «?»: círculo de 0,062 en (0,80, 0,445), borde de tinta 3 px, cara de papel, «?» 22 px negrita; cursor encima =
     cara amarilla; clic = abre/cierra. NO entra en `focables` (cambiaría los índices del tutorial).
   - Papelito de ayuda (z `ayuda`): papel de 0,62 de ancho bajo el botón (esquina superior derecha en (0,83, 0,41)), con
     «Cómo se juega» 15 px negrita, el rumor entero si se recortó, `REGLA_CORTA` a 16 px, las teclas (`teclas_de_ayuda(AYUDA)`,
     una por línea, 16 px), `lineas_ayuda_extra()` y abajo «Cerrar: Esc o H» a 13 px en `tenue_papel`. Abre y cierra
     escalando en 0,2 s (instantáneo con reducir). No es modal: las demás teclas siguen llegando al juego y el tiempo no se
     para.
3. `tecla(k)`: si `k in ("h", "f1")` alterna la ayuda y devuelve True; si `k == "escape"` y está abierta, la cierra y
   devuelve True; en todo lo demás `return super().tecla(k)`.
4. `zona_juego()` devuelve `marco_calculos.zona_juego(self.marco_activo())`. Está lista antes de `construir()`.
5. Si algo falla: vuelve a enseñar título, rumor y pie, destruye lo montado y `marco_activo()` pasa a False.

### 7.2 Globos (B1): `globos_calculos.py` + `globos.py`

- `globo(padre, ancho, alto, cola="izq"|"der"|"abajo-izq"|"abajo-der"|None, tono="papel_blanco", position=(0, 0),
  z=Z["pieza"], borde_px=3) -> Entity`: rectángulo redondeado (radio 12 px) con capa de tinta detrás, sombra plana y cola
  triangular (tinta detrás + cara delante, como `cronologia_visual.py:119-122`). Geometría de la cola en
  `globos_calculos.cola(ancho, alto, lado, tam=0.03)`.
- `avatar(padre, nombre, diametro=0.05, position=(0, 0), z=Z["decor"]) -> Entity`: círculo con borde de tinta, cara de
  `globos_calculos.color_avatar(nombre)` (D3: `estilo.COLORES_ROL_PROPUESTOS` si el nombre es un rol; si no, uno de los 4
  tonos de `chat_visual.TONOS_AVATAR` COPIADOS en `globos_calculos` (no importes `chat_visual` desde un módulo puro: trae
  ursina), elegido con `zlib.crc32`) e inicial (`chat_visual_calculos.inicial`) a 15 px negrita en TINTA (medido:
  tinta sobre esos colores da de 5,1 a 14,2 de contraste). Los nombres de los remitentes van en tinta sobre el globo
  blanco, NUNCA en el color del rol (rol sobre blanco da 2,5-3,4: no pasa).
- `GloboRespuesta(ui.Tarjeta)`: `(ancho, alto, cuerpo, numero, px=17, cola="izq", al_clic=None, al_cursor=None,
  **opciones)`. Mismo patrón que `TarjetaPapel` de A (esconde borde/fondo de la base, `_papel_listo`, `_pintar()` por
  estado, etiqueta SIEMPRE en texto, sin «>>»): globo blanco con cola hacia el teléfono, número en círculo de tinta (1-3)
  a la izquierda, cuerpo 17 px. Estados: foco (halo amarillo 5 px + sombra larga), `incorrecta` con etiqueta (banda roja +
  aspa + «ENTREGA ESE DATO» para el tutorial), deshabilitada al terminar (papel apagado).
- `Escribiendo(Entity)`: globo pequeño con 3 puntos que suben y bajan (`chat_visual_calculos.puntos_escribiendo`; con reducir,
  fijos) y el texto «Ana está escribiendo» a 13 px. `.fijar_nombre(n)`, `.avanzar(dt, reducir)`.
- `RelojCircular(Entity)`: anillo de 0,09 de diámetro (`piezas.arco_grueso` de 90° a 90° - 360·f), tono
  `piezas_calculos.tono_reloj(f)` (cian > 0,5, amarillo > 0,25, rojo); dentro, sin cifras, un icono de reloj dibujado.
  `.fijar(fraccion_restante, reducir)`.

### 7.3 Chat del barrio (B2): `ChatRediseno(MarcoVisual, ChatVisual)`

Hereda de la vista visual de HOY para conservar «escribiendo…», sonido, vibración por umbrales y el aviso de datos leído del
texto; sobrescribe su dibujo: `_construir_vista`, `_quitar_vista`, `_pintar_chat_visual`, `_pintar_aviso`, `_animar`
(sin la viñeta), `_preparar_final`, `_animar_final`, y `_pintar_turno` (sustitución de `opciones`).
- Móvil grande a la izquierda: pantalla de 0,70 × 0,66 centrada en (-0,42, 0,065) (y 0,39 a -0,26), carcasa de tinta de
  0,014 con esquinas de 18 px, pantalla clara (236, 229, 221). Cabecera del grupo (alto 0,06): avatar del grupo, `caso["titulo"]`
  a 15 px negrita en tinta y «N participantes» a 13 px en `tenue_papel` (N = nombres distintos de `partida.turnos`).
- Burbujas (desde `self.log`, de abajo arriba, solo las que caben enteras, como `chat.py:59-70`): de otros = globo blanco
  con cola a la izquierda, ancho máx 0,50, nombre arriba a 13 px negrita en tinta + punto de color del avatar, texto 16 px;
  avatar de 0,04 al lado. Propias (`tu`) = globo cian (texto tinta: contraste 11,3) a la derecha con cola a la derecha.
  Reacciones = chip centrado a 13 px. Contexto (intro) = cartel de papel centrado a 14 px en `tenue_papel`. Abajo,
  `Escribiendo` mientras corre `_t_escribiendo` (la lógica de la clase madre).
- Respuestas: 3 `GloboRespuesta` a la derecha (x de 0,02 a 0,83, ancho 0,78), cola hacia el teléfono, número 1-3, apiladas
  desde y 0,26 con 0,025 de separación; sustituyen a `self.opciones` / `self.focables` en el mismo orden (patrón de
  sustitución, coordinación 5.7). Debajo de la que tiene el foco, el aviso de datos (`chat_visual_calculos.aviso_datos`,
  del texto) en una tira de papel a 15→16 px en `rojo_tinta`; sin resaltar en rojo la respuesta entera.
- Presión: `RelojCircular` en (0,72, 0,345) + chip con las palabras de la base («El grupo espera tu respuesta» / «se
  impacienta» / «¡Te están esperando ya!», que ya escribe en `self.rotulo`: lee ese texto o `partida.presion()`), y 3
  avatares «esperando» al lado del reloj (x 0,30-0,46) que se inclinan hasta 10° con la presión (0° con reducir) y a partir
  de 0,9 muestran un chip «!» (texto, no solo color). La barra y el rótulo de la base quedan escondidos.
- Cierre: resumen de una línea (`resultado.detalle`) en tira de papel bajo las respuestas, y sello sobre el móvil: «A SALVO»
  (`verde_tinta`) si `partida.datos_cedidos() == 0`, si no «DATOS REGALADOS» (`rojo_tinta`), con `piezas.sello` (22 px,
  -8°). Las respuestas quedan deshabilitadas. Opcional: el recorrido del dato de `chat_visual` (ruta y «Perfil
  desconocido») dibujado DENTRO de la pantalla del móvil con piezas de papel.
- `REGLA_CORTA = "Responde sin dar teléfonos, direcciones ni datos de nadie."`
- Posición del sello común VERIFICADO/BULO: `posicion_sello() = (0.45, -0.20)` (ajustar con captura); estrellas
  `(0.20, 0.36)`.
- Rendimiento: cuenta entidades por turno; si pasa de ~200 en el móvil, pinta solo las burbujas visibles y reutilízalas.

### 7.4 Portada de caso (B3): `portada_calculos.py` + `portada_caso.py` + enganche

- `envolver(clase)` y `PortadaCasoMezcla` según la coordinación 5.6. Bandera `ALCALDE_PORTADA_VISUAL` (constante
  `PORTADA_VISUAL = True` en `portada_caso.py`; se lee al construir). Clave del guardián: `portada_visual`.
- El id del minijuego sale del título: `portada_calculos.id_por_titulo(titulo)` («Rastrear» -> rastrear, «Comparar» ->
  comparar, «Ordenar» -> cronologia, «Chat» -> chat, «Señales» -> senales, «Contrarreloj» -> contrarreloj; otro -> None y
  dibujo genérico). Títulos reales en `frontend/minijuegos/*.py` (`TITULO = ...`).
- Maqueta (versión completa): arriba a la izquierda, recorte de periódico (papel blanco, borde dentado hecho con
  triángulos, rotación -1,5°) con chip «EL RUMOR» y el rumor a 18 px (recortado a 4 líneas); debajo, el dibujo del objeto del
  minijuego (0,45 × 0,30: dos hojas / corcho con hilo / viñetas / móvil / captura con lupa / mapa con teletipo, hecho con
  piezas); a la derecha, título a 28 px negrita y «Cómo se juega» con 3 iconos dibujados y una frase corta cada uno
  (`portada_calculos.PASOS_CORTOS[id]`, ≤ 45 caracteres, textos nuevos tuyos; no cambian los datos de
  `minijuegos_instrucciones.py`); «Lo que practicas en redes» como pósit amarillo con UNA frase
  (`portada_calculos.primera_frase(instrucciones["redes"])`, recortada a 110 caracteres); las teclas en una tira a 14 px.
  Botón «Empezar»: `BotonSello` primario de 0,36 × 0,09 a 22 px en (0, -0,37), sin «>>»; «Enter o Espacio» debajo a 13 px.
- Versión corta (tras el tutorial): recorte del rumor + pósit + Empezar + «Ver tutorial» (`BotonSello` secundario de
  0,24 × 0,05 en (-0,69, -0,37)).
- Conserva el contrato de la sección 6: los `tarjetas` de la base quedan en la lista (escondidos, misma longitud), y
  `boton`/`boton_tutorial` pasan a ser tus `BotonSello` cableados con `lambda: self._empezar()` y
  `lambda: self._ver_tutorial()` (la escena reasigna `al_empezar`, por eso hay que llamar al método, no guardar el
  callback). Destruye los botones originales tras el cambio.
- Añade el enganche al final de `pantalla_previa.py` (coordinación 5.6) y pasa `preservador` sobre ese diff.

### 7.5 Señales de edición (B4): `SenalesRediseno(MarcoVisual, CapaVisual, MinijuegoSenales)`

Clase hermana (no hereda de `SenalesVisual`: su lupa amplía texto y su pegatina va en z -0,14). Solo maquetación: zonas y
reglas no cambian.
- Captura de móvil dibujada a la izquierda: pantalla de 0,62 × 0,66 centrada en (-0,45, 0,065), carcasa de tinta, chip
  «CAPTURA QUE CIRCULA» a 13 px y `caso["titulo"]` a 15 px encima (dentro de la zona de juego).
- Cada zona es una REGIÓN del dibujo, no una fila. `senales_rediseno_calculos.region_de_zona(zona)` devuelve `barra` (texto
  corto con hora `\d{1,2}:\d{2}`), `cabecera` (empieza por «@» o la lupa habla de «cuenta»/«perfil»/«nombre»), `pie` (la
  lupa habla de «enlace», «botón», «link») o `burbuja` (lo demás). `maqueta_captura(zonas, ...)` reparte rectángulos: barra
  superior (alto 0,04: la hora a la izquierda, batería dibujada), cabecera (avatar + nombre, alto 0,07), burbujas apiladas
  (ancho máx 0,52, alternando lado), pie (botón dibujado). Prueba pura sobre los 5 casos de señales (6 zonas cada uno): todas
  las zonas tienen región y ningún rectángulo se pisa ni se sale de la pantalla.
- Zonas = `ZonaCaptura(ui.Tarjeta)` (en `senales_rediseno.py`, mismo patrón que `TarjetaPapel`), con la caja de golpe igual a
  su región y el texto a 16-17 px; `tarjetas` y `focables` en el mismo orden que la base.
- Lupa: aro cian (anillo de 3 px con `arco_grueso`, interior transparente) alrededor de la región con foco + halo
  amarillo alfa 0,35 un poco mayor, z `foco`; se mueve en 0,15 s (instantánea con reducir). Pestaña pegada al aro con la
  etiqueta corta de la zona: `senales_rediseno_calculos.etiqueta_zona(zona["lupa"])` («Cuenta», «Hora», «Lo que pide»,
  «Lugar y día», «Enlace», «Foto»...; si no reconoce, `recortar(lupa, 22)`), 13 px en tinta sobre papel. La lupa NUNCA tapa
  ni repite el texto de la zona.
- Marcar: sello «RARO» (`piezas.sello`, `rojo_tinta`, 16 px, -10°) en el borde derecho de la región + la etiqueta de estado
  «SOSPECHOSA» que pone la base. Contador: 3 casillas dibujadas (`max_marcas`) junto a la ficha que se rellenan con un aspa al
  marcar, y el texto «Marcas: 2 de 3» a 14 px (forma + texto).
- Ficha de pista a la derecha (papel con pestaña «LUPA», x de 0,05 a 0,83, desde y 0,39): la pregunta de la zona
  («Mirando: <lupa>.», el mismo texto que la base pone en `self.lupa`) a 17 px; si se pasa del máximo de marcas, el aviso de
  la base («Ya usaste todas tus marcas...»). Botones `BotonSello` «Confirmar marcas» (primario, icono `visto`) y «No veo nada
  raro» (secundario) en la zona de controles: y -0,335, x 0,24 y 0,62, ancho 0,34, alto 0,07; sustituyen a
  `boton_confirmar`/`boton_nada`.
- Cierre: señales reales con sello «TRUCO» (`rojo_tinta`) y estado `encontrada` o `perdida` (aro discontinuo), marcas falsas
  tachadas con `falsa_alarma` («ESTABA BIEN»); la ficha cambia a «LO QUE DELATABA LA CAPTURA» con las explicaciones de
  `partida.zonas[i]["explica"]` a 16 px, numeradas igual que un chip numerado sobre cada región. Prueba offscreen: en los 5
  casos caben a 16 px; si alguno no cabe, se pasa a numerar las explicaciones como notas pegadas junto a su región (no se
  baja de 16 px).
- `REGLA_CORTA = "Marca hasta 3 detalles que delaten una captura editada o un engaño."`
- Se elimina: la columna «LUPA» de texto, el título largo, el pie y la lista de cajas.

### 7.6 Lo que desaparece de pantalla o pasa al «?»

Desaparecen: título grande, línea larga «Rumor a verificar» (pasa a la cinta), el texto de la lupa en columna, la barra de
presión, el pie de teclas. Pasan al papelito «?»: `REGLA_CORTA`, teclas (de `AYUDA`), rumor entero si se recortó.

## 8. Banderas y guardián

| Pieza | Clase | Constante (nace) | Variable | Si falla |
|---|---|---|---|---|
| Marco | `MarcoVisual` | `MARCO_VISUAL = True` (es solo cabecera; con todas las vistas de rediseño apagadas no se usa) | `ALCALDE_MARCO_VISUAL` | Vuelven título, rumor y pie de la base |
| Portada | `PortadaCasoMezcla` | `PORTADA_VISUAL = False` hasta B3 terminado; `True` en S3 | `ALCALDE_PORTADA_VISUAL` | Se borra lo nuevo y queda la previa de siempre |
| Chat | `ChatRediseno` | `CHAT_REDISENO = False` | `ALCALDE_CHAT_REDISENO` | `_quitar_vista` deja el chat de la vista de hoy (como `chat_visual.py:130-139`) y las `opciones` originales si aún existen |
| Señales | `SenalesRediseno` | `SENALES_REDISENO = False` | `ALCALDE_SENALES_REDISENO` | Se borra lo nuevo y queda la vista base con la capa común |

Guardián por instancia (`_rediseno_roto`); claves `rediseno_chat`, `rediseno_senales`, `rediseno_<x>_animar`,
`marco_visual`, `portada_visual`, `piezas_globos`. Fallos en `avanzar_visual_propio` nunca lanzan.

## 9. Orden de trabajo (cada paso con su criterio de «hecho»)

B0. Paquete 0 de B (primero de todo; nada aquí depende de A).
  1. Captura de línea base de Chat, Señales y la previa de los 6 (estados de coordinación 7.4) con lo de HOY:
     `scripts/capturas_rediseno_b.py`. Hecho: imágenes en `adjuntos/rediseno-minijuegos/b/base_*.png`, revisadas.
  2. `marco_calculos.py` + `tests/test_b_piezas_marco.py`. Hecho: pruebas verdes (`titulo_corto` de los 6 títulos,
     `recortar_rumor` con rumores de 30, 90 y 200 caracteres, `teclas_de_ayuda` de las 6 `AYUDA`, `zona_juego`); no importa ursina.
  3. `marco.py` + prueba offscreen en `tests/test_b_piezas_ursina.py`: una clase de prueba
     `type("P", (MarcoVisual, CapaVisual, MinijuegoComparar), {})` empieza con un caso real; título/rumor/pie escondidos
     pero existentes; h abre, Esc cierra, h otra vez cierra; `terminar` no falla; un fallo forzado devuelve la cabecera de
     la base. Hecho: verde.
  4. Humo del tutorial (coordinación C16): corre `tests/humo_tutorial_mision.py`. En `HEAD` limpio pasa. Si el dueño
     ADOPTÓ los cambios de la sección 0 y falla en la línea 169, crea `tests/humo_tutorial_mision_visual.py`: lee el humo,
     sustituye EXACTAMENTE las aserciones de las líneas 169 y 173 por `print("5 omitido: falla con los cambios adoptados")`,
     comprueba que las dos sustituciones ocurrieron y ejecuta con `exec`. Hecho: `HUMO TUTORIAL MISION OK` con las vistas de hoy.
  5. Escribe «S0 entregado HH:MM» en tu nota de la bóveda. Lee la nota de A (62).
B1. Globos: `globos_calculos.py` + pruebas puras; `globos.py` + prueba offscreen (`GloboRespuesta` es `ui.Tarjeta`, admite
  los estados que usa el Chat y el del tutorial). Hecho: verde.
B2. Chat. Cálculos puros (maqueta de burbujas con medida inyectada, inclinación de avatares por presión) con pruebas; clase;
  prueba offscreen con los 5 casos de chat: jugar bien y mal por `responder`, dejar agotar la presión (`avanzar`),
  comprobar que `opciones` tiene 3 `ui.Tarjeta` por turno y que ninguna pieza nueva lee `valor`
  (`grep -n "valor" frontend/minijuegos_visual/chat_rediseno*.py` vacío); forzar fallo. Humo visual (de A) con
  `ALCALDE_CHAT_REDISENO=1` y tu humo del tutorial. Capturas revisadas (normal y reducir movimiento; presión baja, media y
  al límite). `security-auditor`, `code-reviewer`. Hecho = S1.
B3. Portada: cálculos puros (`id_por_titulo` de los 6 títulos, `PASOS_CORTOS` ≤ 45 caracteres, `primera_frase`); mezcla;
  prueba offscreen: con y sin `al_ver_tutorial`, corta y completa, `len(tarjetas)` igual que la base, `boton_tutorial` solo
  cuando toca, `al_empezar` reasignado funciona. Enganche al final de `pantalla_previa.py`; `preservador` sobre el diff.
  Humo del tutorial visual con `ALCALDE_PORTADA_VISUAL=1`. Capturas de las 6 portadas. Hecho: verde.
B4. Señales. Cálculos puros (`region_de_zona`, `maqueta_captura`, `etiqueta_zona`) probados sobre los 5 casos; clase;
  prueba offscreen (jugar bien y mal, marcar más de 3, sin señales; explicaciones caben a 16 px); forzar fallo. Humos con
  `ALCALDE_SENALES_REDISENO=1`. Capturas. `security-auditor`, `code-reviewer`. Hecho = S2.
B5. Pasada transversal: posiciones de sello/estrellas en captura, contraste de cada pareja texto/fondo
  (`piezas_calculos.contraste_ok`), reducir movimiento, teclado (Tab, flechas, 1-3, c, n, h, F1, Esc) y mando (D-pad, A, X)
  en ventana real, la ayuda «?» en los 5 minijuegos (también los de A); `auditor-diseno-generico` y `accessibility-tester`.
  Pon `CHAT_REDISENO`, `SENALES_REDISENO`, `PORTADA_VISUAL = True`. Suite completa contra la línea base + humos de la
  coordinación 8.2. `security-auditor`, `terminos-legales` (textos nuevos visibles), `code-reviewer`. Hecho = S3.

## 10. Pruebas

Escribes (en `tests/`, prefijo `test_b_piezas_`):
- `test_b_piezas_marco.py`, `test_b_piezas_globos.py`, `test_b_piezas_portada.py`, `test_b_piezas_chat.py`,
  `test_b_piezas_senales.py`: puras (sin ursina), sobre los datos reales de `backend/datos/minijuegos_casos.py` y
  `minijuegos_instrucciones.py`.
- `test_b_piezas_ursina.py`: offscreen (coordinación 7.2): marco, globos, portada, Chat y Señales; todas las piezas
  marcables son `ui.Tarjeta`, botones `ui.Boton`, nada con z < -0,09, texto ≥ 13 px, sin «>>» en ningún `Text` nuevo.
- `tests/humo_tutorial_mision_visual.py` solo si hace falta (C16).

Ejecutas (con el cerrojo de la coordinación 8.2): tus pruebas
(`venv/bin/python -m pytest -q -p no:cacheprovider tests/test_b_piezas_*.py`), el humo base, el humo visual de A y el humo
del tutorial (C16), y la suite completa contra la línea base del anexo de la coordinación (por ID).

## 11. Capturas, subagentes y bóveda

Capturas: `scripts/capturas_rediseno_b.py` según coordinación 7.4; ids `chat`, `senales` y la previa/portada de los 6;
revisar cada PNG con la herramienta de leer imágenes; comparar con las de línea base de B0.1. En la portada, capturar la
versión completa y la corta (tras el tutorial).

Subagentes (los pides tú; ninguno decide por ti):
- `preservador`: tras CUALQUIER cambio a código existente (aquí: `pantalla_previa.py`) y antes de dar por hecho cada paso
  donde heredas de una clase existente (`ChatVisual`).
- `security-auditor` y después `code-reviewer` (el revisor exige el APROBADO del auditor sobre el mismo cambio) al cerrar
  B2, B3, B4 y B5.
- `terminos-legales`: en B5, por los textos nuevos que ve el jugador (portada, ayuda, sellos).
- `auditor-diseno-generico`: en B0.1 sobre la línea base y en B5 sobre el resultado.
- `accessibility-tester`: en B5 (contraste, estados por forma + texto, teclado, mando, ayuda «?»).

Bóveda (`~/Documents/Obsidian-Alcalde-Digital`), con CADA paso:
- Nota `63 Rediseño minijuegos Parte B (2026-11-17).md` con: estado, entregas (S0..S3 con hora), archivos creados y
  modificados, decisiones, resultados de pruebas (contra línea base), capturas incrustadas
  (`![[adjuntos/rediseno-minijuegos/b/<archivo>.png]]`), «Peticiones a la otra parte», «Respuestas», pendientes.
- En `00 Índice Alcalde Digital.md`: añade con Edit (nunca reescribiendo el archivo), justo después de la última línea
  `- [[6x ...]]` de la lista «Mapa», una línea para la nota 63. Si el Edit falla porque la Parte A acaba de cambiar el
  índice, vuelve a leerlo y repite.

## 12. Riesgos propios

- `MarcoVisual` va delante de `CapaVisual` en el MRO: su `_encabezado` se ejecuta antes de que exista `self._fx`; no uses
  la capa común desde el marco.
- El Chat crea y destruye respuestas en cada turno: el tutorial guarda referencias a `vista.opciones[i]` solo durante su
  paso; no reutilices objetos destruidos (comprueba `is_empty()` antes de pintar, como `ui.Tarjeta._pintar`).
- La previa se construye ANTES que la vista (la escena la enseña entre la puerta y el minijuego) y también tras el
  tutorial: la portada no puede depender de nada de la vista; solo de sus argumentos.
- Escape: hoy la escena se lo pasa entero a la vista (`escena_minijuego.py:384-399`); si el juego empezara a usarlo para
  pausar, la ayuda lo taparía.
- `humo_tutorial_mision.py` cambia de vez en cuando: tu envoltorio debe fallar con un mensaje claro si no encuentra el texto
  exacto que sustituye.
